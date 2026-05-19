#!/usr/bin/env python3
"""Tune conservative Random Forest variants against false positives."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import LeaveOneGroupOut

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gait_analysis.run_ml_model_comparison_grouped import (
    add_groups,
    apply_temporal_embargo,
    get_feature_columns,
)


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Evalua variantes conservadoras de Random Forest penalizando mas "
            "los falsos positivos mediante pesos de clase y umbral."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="Parquet binario con features y target.",
    )
    p.add_argument(
        "--group-by",
        choices=["reference", "temporal_block"],
        default="temporal_block",
    )
    p.add_argument("--gap-seconds", type=float, default=5.0)
    p.add_argument("--embargo-seconds", type=float, default=15.0)
    p.add_argument(
        "--not-walking-weights",
        type=float,
        nargs="+",
        default=[1.0, 1.5, 2.0, 3.0],
        help="Pesos de clase para not_walking; walking mantiene peso 1.",
    )
    p.add_argument(
        "--thresholds",
        type=float,
        nargs="+",
        default=[0.5, 0.6, 0.7, 0.72, 0.8],
        help="Umbrales de probabilidad a evaluar.",
    )
    p.add_argument(
        "--fold-output",
        default="results/conservative_rf_temporal_block_folds.csv",
    )
    p.add_argument(
        "--summary-output",
        default="results/conservative_rf_threshold_summary.csv",
    )
    return p


def build_rf(not_walking_weight: float) -> RandomForestClassifier:
    """Build one conservative Random Forest candidate."""
    return RandomForestClassifier(
        n_estimators=300,
        random_state=42,
        class_weight={0: not_walking_weight, 1: 1.0},
        max_depth=5,
        min_samples_leaf=10,
        max_features="sqrt",
    )


def confusion_counts(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, int]:
    """Return binary confusion counts."""
    return {
        "tp": int(((y_true == 1) & (y_pred == 1)).sum()),
        "tn": int(((y_true == 0) & (y_pred == 0)).sum()),
        "fp": int(((y_true == 0) & (y_pred == 1)).sum()),
        "fn": int(((y_true == 1) & (y_pred == 0)).sum()),
    }


def score_predictions(
    y_true: np.ndarray,
    prob_walking: np.ndarray,
    threshold: float,
) -> dict[str, float | int]:
    """Score one threshold over out-of-fold probabilities."""
    y_pred = (prob_walking >= threshold).astype(int)
    counts = confusion_counts(y_true, y_pred)
    not_walking = counts["tn"] + counts["fp"]
    walking = counts["tp"] + counts["fn"]
    return {
        "threshold": float(threshold),
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
        "f1_macro": f1_score(
            y_true,
            y_pred,
            average="macro",
            zero_division=0,
        ),
        "false_positive_rate": counts["fp"] / not_walking if not_walking else 0.0,
        "false_negative_rate": counts["fn"] / walking if walking else 0.0,
        **counts,
    }


def main() -> None:
    """Tune RF class weights and thresholds."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    df = pd.read_parquet(input_path)
    if "target" not in df.columns:
        raise ValueError("El dataset debe contener target.")

    df = add_groups(df, args.group_by, args.gap_seconds)
    feature_cols = get_feature_columns(df)
    X = df[feature_cols].copy()
    y = df["target"].astype(int)
    groups = df["group"].astype(str)
    metadata = df[["reference", "time_center"]].copy()

    fold_rows = []
    summary_rows = []
    logo = LeaveOneGroupOut()

    for not_walking_weight in args.not_walking_weights:
        model = build_rf(not_walking_weight)
        probabilities = pd.Series(index=df.index, dtype=float)

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
            estimator = clone(model)
            estimator.fit(X.iloc[train_idx], y.iloc[train_idx])
            fold_prob = estimator.predict_proba(X.iloc[test_idx])[:, 1]
            probabilities.iloc[test_idx] = fold_prob

            fold_rows.append(
                {
                    "not_walking_weight": float(not_walking_weight),
                    "fold": int(fold_idx),
                    "group": str(groups.iloc[test_idx].iloc[0]),
                    "train_rows": int(len(train_idx)),
                    "test_rows": int(len(test_idx)),
                    "mean_prob_walking": float(np.mean(fold_prob)),
                }
            )

        if probabilities.isna().any():
            raise ValueError("Hay filas sin prediccion out-of-fold.")

        y_true = y.to_numpy()
        prob = probabilities.to_numpy()
        for threshold in args.thresholds:
            summary_rows.append(
                {
                    "not_walking_weight": float(not_walking_weight),
                    **score_predictions(y_true, prob, threshold),
                }
            )

    fold_output = Path(args.fold_output)
    summary_output = Path(args.summary_output)
    fold_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(fold_rows).to_csv(fold_output, index=False)
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(summary_output, index=False)

    best_conservative = summary[summary["recall_walking"].ge(0.60)].sort_values(
        ["false_positive_rate", "f1_macro"],
        ascending=[True, False],
    )
    best_f1 = summary.sort_values(
        ["f1_macro", "false_positive_rate"],
        ascending=[False, True],
    ).iloc[0]

    print(f"Input parquet: {input_path}")
    print(f"Rows: {len(df)}")
    print(f"Feature columns: {len(feature_cols)}")
    print(f"Fold output: {fold_output}")
    print(f"Summary output: {summary_output}")
    print()
    print("Best macro F1:")
    print(best_f1.round(4).to_string())
    if not best_conservative.empty:
        print()
        print("Best conservative option with recall_walking >= 0.60:")
        print(best_conservative.iloc[0].round(4).to_string())


if __name__ == "__main__":
    main()
