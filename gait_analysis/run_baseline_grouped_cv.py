#!/usr/bin/env python3
"""Run binary baselines with temporal-block grouped cross-validation."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, recall_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Evalua baselines con CV agrupada por bloques temporales."
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="Ruta al parquet binario preparado o wide limpio",
    )
    p.add_argument(
        "--gap-seconds",
        type=float,
        default=5.0,
        help="Salto minimo entre time_center consecutivos para abrir un bloque nuevo",
    )
    p.add_argument(
        "-o",
        "--output",
        help="CSV opcional para guardar los resultados por fold",
    )
    return p


def add_temporal_groups(df: pd.DataFrame, gap_seconds: float) -> pd.DataFrame:
    """Add a stable temporal block group column inferred from time gaps."""
    grouped = df.copy()
    grouped["time_center"] = pd.to_datetime(grouped["time_center"], utc=True)
    grouped = grouped.sort_values(["reference", "time_center"]).reset_index(drop=True)

    ref_change = grouped["reference"].ne(grouped["reference"].shift())
    gap = grouped.groupby("reference")["time_center"].diff()
    gap_change = gap.gt(pd.Timedelta(seconds=gap_seconds)).fillna(False)
    grouped["block_id"] = (ref_change | gap_change).cumsum().astype(int)
    grouped["group"] = (
        grouped["reference"].astype(str) + "_block_" + grouped["block_id"].astype(str)
    )
    return grouped


def get_target(df: pd.DataFrame) -> pd.Series:
    """Return binary target from either target or mov_type columns."""
    if "target" in df.columns:
        return df["target"].astype(int)
    if "mov_type" not in df.columns:
        raise ValueError("El dataset debe contener target o mov_type.")
    return df["mov_type"].map({"not_walking": 0, "walking": 1}).astype(int)


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return feature columns, excluding identifiers and target columns."""
    excluded = {"reference", "time_center", "mov_type", "target", "block_id", "group"}
    return [c for c in df.columns if c not in excluded]


def build_models() -> dict[str, object]:
    """Build the baseline models used for grouped validation."""
    return {
        "logreg": make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000, class_weight="balanced"),
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=200,
            random_state=42,
            class_weight="balanced",
        ),
    }


def score_model(
    model_name: str,
    model: object,
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
) -> pd.DataFrame:
    """Evaluate one model with Leave-One-Group-Out CV and return per-fold rows."""
    rows = []
    logo = LeaveOneGroupOut()

    for fold_idx, (train_idx, test_idx) in enumerate(logo.split(X, y, groups), start=1):
        estimator = clone(model)
        estimator.fit(X.iloc[train_idx], y.iloc[train_idx])
        y_test = y.iloc[test_idx]
        y_pred = estimator.predict(X.iloc[test_idx])
        group_name = str(groups.iloc[test_idx].iloc[0])

        rows.append(
            {
                "model": model_name,
                "fold": fold_idx,
                "group": group_name,
                "test_rows": int(len(test_idx)),
                "test_not_walking": int((y_test == 0).sum()),
                "test_walking": int((y_test == 1).sum()),
                "accuracy": accuracy_score(y_test, y_pred),
                "f1_walking": f1_score(y_test, y_pred, pos_label=1, zero_division=0),
                "recall_walking": recall_score(
                    y_test,
                    y_pred,
                    pos_label=1,
                    zero_division=0,
                ),
            }
        )

    return pd.DataFrame(rows)


def build_weighted_means(results: pd.DataFrame) -> pd.DataFrame:
    """Compute row-weighted metric means by model."""
    rows = []
    for model_name, model_results in results.groupby("model"):
        weights = model_results["test_rows"]
        rows.append(
            {
                "model": model_name,
                "accuracy": (model_results["accuracy"] * weights).sum() / weights.sum(),
                "f1_walking": (
                    model_results["f1_walking"] * weights
                ).sum()
                / weights.sum(),
                "recall_walking": (
                    model_results["recall_walking"] * weights
                ).sum()
                / weights.sum(),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    """Read the dataset and evaluate baselines by temporal block."""
    args = build_parser().parse_args()
    input_path = Path(args.input)

    df = pd.read_parquet(input_path)
    df = add_temporal_groups(df, args.gap_seconds)
    y = get_target(df)
    feature_cols = get_feature_columns(df)
    X = df[feature_cols].copy()
    groups = df["group"]

    print(f"Input parquet: {input_path}")
    print(f"Rows: {len(df)}")
    print(f"Feature columns: {len(feature_cols)}")
    print(f"Groups: {groups.nunique()}")
    print()
    print("Group summary:")
    summary = (
        df.assign(target=y)
        .groupby("group")
        .agg(
            rows=("target", "size"),
            not_walking=("target", lambda s: int((s == 0).sum())),
            walking=("target", lambda s: int((s == 1).sum())),
            reference=("reference", "first"),
            start=("time_center", "min"),
            stop=("time_center", "max"),
        )
        .reset_index()
    )
    print(summary.to_string(index=False))
    print()

    result_frames = [
        score_model(name, model, X, y, groups)
        for name, model in build_models().items()
    ]
    results = pd.concat(result_frames, ignore_index=True)

    print("Per-fold results:")
    printable = results.copy()
    for col in ["accuracy", "f1_walking", "recall_walking"]:
        printable[col] = printable[col].round(4)
    print(printable.to_string(index=False))
    print()

    print("Mean results:")
    means = (
        results.groupby("model")[["accuracy", "f1_walking", "recall_walking"]]
        .agg(["mean", "std"])
        .round(4)
    )
    print(means.to_string())
    print()

    print("Row-weighted mean results:")
    weighted_means = build_weighted_means(results).round(4)
    print(weighted_means.to_string(index=False))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(output_path, index=False)
        print()
        print(f"Saved per-fold results: {output_path}")


if __name__ == "__main__":
    main()
