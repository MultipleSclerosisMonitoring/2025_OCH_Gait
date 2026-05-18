#!/usr/bin/env python3
"""Compare ML classifiers with grouped cross-validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from sklearn.base import clone
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import LeaveOneGroupOut

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gait_analysis.run_ml_model_comparison_cv3 import build_models


ID_COLS = {
    "reference",
    "time_center",
    "mov_type",
    "target",
    "foot",
    "block_id",
    "group",
}


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Compara Random Forest, XGBoost y CatBoost con validacion agrupada "
            "para estimar generalizacion por paciente o bloque temporal."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        default="salidas_test/auto_extracts/main_binary_window_features.parquet",
        help="Parquet binario preparado con target y columnas espectrales.",
    )
    p.add_argument(
        "--group-by",
        choices=["reference", "temporal_block"],
        default="reference",
        help="Unidad que se deja fuera completa en cada fold.",
    )
    p.add_argument(
        "--gap-seconds",
        type=float,
        default=5.0,
        help="Salto entre ventanas para abrir bloque temporal si group-by=temporal_block.",
    )
    p.add_argument(
        "--embargo-seconds",
        type=float,
        default=0.0,
        help="Margen temporal excluido del entrenamiento alrededor del bloque de test.",
    )
    p.add_argument(
        "--fold-output",
        default="results/ml_model_comparison_grouped_folds.csv",
        help="CSV con metricas por fold.",
    )
    p.add_argument(
        "--summary-output",
        default="results/ml_model_comparison_grouped_summary.csv",
        help="CSV con media y desviacion estandar por modelo.",
    )
    p.add_argument(
        "--prediction-output",
        default=None,
        help="CSV opcional con predicciones y probabilidades out-of-fold.",
    )
    p.add_argument(
        "--models",
        nargs="+",
        choices=["random_forest", "xgboost", "catboost"],
        default=["random_forest", "xgboost", "catboost"],
        help="Modelos a evaluar.",
    )
    return p


def add_temporal_groups(df: pd.DataFrame, gap_seconds: float) -> pd.DataFrame:
    """Add temporal-block groups inferred from gaps within each reference."""
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


def add_groups(df: pd.DataFrame, group_by: str, gap_seconds: float) -> pd.DataFrame:
    """Add the group column requested by the CLI."""
    if group_by == "reference":
        grouped = df.copy()
        grouped["time_center"] = pd.to_datetime(grouped["time_center"], utc=True)
        grouped["group"] = grouped["reference"].astype(str)
        return grouped
    return add_temporal_groups(df, gap_seconds)


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return model feature columns."""
    return [c for c in df.columns if c not in ID_COLS]


def score_predictions(y_true: pd.Series, y_pred: pd.Series) -> dict[str, float]:
    """Return binary and macro metrics for one held-out group."""
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision_walking": precision_score(
            y_true,
            y_pred,
            pos_label=1,
            zero_division=0,
        ),
        "recall_walking": recall_score(
            y_true,
            y_pred,
            pos_label=1,
            zero_division=0,
        ),
        "f1_walking": f1_score(
            y_true,
            y_pred,
            pos_label=1,
            zero_division=0,
        ),
        "precision_macro": precision_score(
            y_true,
            y_pred,
            average="macro",
            zero_division=0,
        ),
        "recall_macro": recall_score(
            y_true,
            y_pred,
            average="macro",
            zero_division=0,
        ),
        "f1_macro": f1_score(
            y_true,
            y_pred,
            average="macro",
            zero_division=0,
        ),
    }


def apply_temporal_embargo(
    train_idx: pd.Index,
    test_metadata: pd.DataFrame,
    train_metadata: pd.DataFrame,
    embargo_seconds: float,
) -> pd.Index:
    """Remove same-reference training rows near the held-out temporal block."""
    if embargo_seconds <= 0:
        return train_idx
    test_reference = str(test_metadata["reference"].iloc[0])
    test_start = test_metadata["time_center"].min() - pd.Timedelta(
        seconds=embargo_seconds
    )
    test_stop = test_metadata["time_center"].max() + pd.Timedelta(seconds=embargo_seconds)
    keep_train = ~(
        train_metadata["reference"].astype(str).eq(test_reference)
        & train_metadata["time_center"].between(test_start, test_stop)
    )
    return train_idx[keep_train.to_numpy()]


def build_summary(fold_results: pd.DataFrame) -> pd.DataFrame:
    """Build mean and standard-deviation summary by model."""
    metric_cols = [
        "accuracy",
        "precision_walking",
        "recall_walking",
        "f1_walking",
        "precision_macro",
        "recall_macro",
        "f1_macro",
    ]
    rows = []
    for model_name, model_results in fold_results.groupby("model", sort=False):
        row: dict[str, float | str] = {
            "model": model_name,
            "folds": int(len(model_results)),
            "test_rows_total": int(model_results["test_rows"].sum()),
        }
        for metric in metric_cols:
            row[f"{metric}_mean"] = model_results[metric].mean()
            row[f"{metric}_sd"] = model_results[metric].std(ddof=1)
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    """Run grouped model comparison and save fold-level plus summary outputs."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    fold_output = Path(args.fold_output)
    summary_output = Path(args.summary_output)

    df = pd.read_parquet(input_path)
    if "target" not in df.columns:
        raise ValueError("El dataset debe contener la columna target.")

    df = add_groups(df, args.group_by, args.gap_seconds)
    feature_cols = get_feature_columns(df)
    X = df[feature_cols].copy()
    y = df["target"].astype(int)
    groups = df["group"].astype(str)
    metadata = df[["reference", "time_center"]].copy()

    rows = []
    prediction_rows = []
    logo = LeaveOneGroupOut()

    selected_models = {
        name: model
        for name, model in build_models(y).items()
        if name in set(args.models)
    }
    for model_name, model in selected_models.items():
        for fold_idx, (train_idx_raw, test_idx_raw) in enumerate(
            logo.split(X, y, groups),
            start=1,
        ):
            train_idx = pd.Index(train_idx_raw)
            test_idx = pd.Index(test_idx_raw)
            test_metadata = metadata.iloc[test_idx]
            train_metadata = metadata.iloc[train_idx]
            train_idx = apply_temporal_embargo(
                train_idx=train_idx,
                test_metadata=test_metadata,
                train_metadata=train_metadata,
                embargo_seconds=args.embargo_seconds
                if args.group_by == "temporal_block"
                else 0.0,
            )
            if len(train_idx) == 0:
                raise ValueError(f"Fold {fold_idx} sin datos tras aplicar embargo.")

            estimator = clone(model)
            estimator.fit(X.iloc[train_idx], y.iloc[train_idx])
            y_test = y.iloc[test_idx]
            y_pred = pd.Series(
                estimator.predict(X.iloc[test_idx]),
                index=y_test.index,
            ).astype(int)
            if hasattr(estimator, "predict_proba"):
                y_prob = pd.Series(
                    estimator.predict_proba(X.iloc[test_idx])[:, 1],
                    index=y_test.index,
                ).astype(float)
            else:
                y_prob = pd.Series(float("nan"), index=y_test.index)

            group_name = str(groups.iloc[test_idx].iloc[0])
            rows.append(
                {
                    "model": model_name,
                    "fold": fold_idx,
                    "group": group_name,
                    "group_by": args.group_by,
                    "embargo_seconds": float(
                        args.embargo_seconds
                        if args.group_by == "temporal_block"
                        else 0.0
                    ),
                    "train_rows": int(len(train_idx)),
                    "test_rows": int(len(test_idx)),
                    "test_not_walking": int((y_test == 0).sum()),
                    "test_walking": int((y_test == 1).sum()),
                    **score_predictions(y_test, y_pred),
                }
            )
            if args.prediction_output:
                fold_predictions = df.iloc[test_idx][
                    ["reference", "time_center", "mov_type", "target"]
                ].copy()
                if "foot" in df.columns:
                    fold_predictions["foot"] = df.iloc[test_idx]["foot"].to_numpy()
                fold_predictions["model"] = model_name
                fold_predictions["fold"] = fold_idx
                fold_predictions["group"] = group_name
                fold_predictions["group_by"] = args.group_by
                fold_predictions["embargo_seconds"] = float(
                    args.embargo_seconds
                    if args.group_by == "temporal_block"
                    else 0.0
                )
                fold_predictions["prob_walking"] = y_prob.to_numpy()
                fold_predictions["prediction"] = y_pred.to_numpy()
                prediction_rows.append(fold_predictions)

    fold_results = pd.DataFrame(rows)
    summary = build_summary(fold_results)

    fold_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    fold_results.to_csv(fold_output, index=False)
    summary.to_csv(summary_output, index=False)
    if args.prediction_output:
        prediction_output = Path(args.prediction_output)
        prediction_output.parent.mkdir(parents=True, exist_ok=True)
        pd.concat(prediction_rows, ignore_index=True).to_csv(
            prediction_output,
            index=False,
        )

    print(f"Input parquet: {input_path}")
    print(f"Rows: {len(df)}")
    print(f"Feature columns: {len(feature_cols)}")
    print(f"Group by: {args.group_by}")
    print(f"Groups: {groups.nunique()}")
    print(f"Fold output: {fold_output}")
    print(f"Summary output: {summary_output}")
    if args.prediction_output:
        print(f"Prediction output: {args.prediction_output}")
    print()
    print("Summary mean +/- sd:")
    printable = summary.copy()
    for col in printable.columns:
        if col != "model":
            printable[col] = printable[col].round(4)
    print(printable.to_string(index=False))


if __name__ == "__main__":
    main()
