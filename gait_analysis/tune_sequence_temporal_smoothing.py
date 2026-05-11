#!/usr/bin/env python3
"""Sweep temporal persistence rules over saved sequence predictions."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from gait_analysis.run_sequence_evaluation import LABEL_MAP


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Prueba reglas de persistencia temporal sobre predicciones "
            "secuenciales ya guardadas."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        default="results/sequence_evaluation_predictions.csv",
        help="CSV de predicciones secuenciales con walking_probability y true_label",
    )
    p.add_argument(
        "-o",
        "--output",
        default="results/sequence_temporal_smoothing_sweep.csv",
        help="CSV de salida con metricas por combinacion de parametros",
    )
    p.add_argument(
        "--thresholds",
        nargs="+",
        type=float,
        default=[0.60, 0.65, 0.70],
        help="Umbrales de probabilidad a evaluar",
    )
    p.add_argument(
        "--min-run-windows",
        nargs="+",
        type=int,
        default=[1, 2, 3, 4, 5],
        help="Longitudes minimas de bloques consecutivos positivos",
    )
    return p


def apply_min_run_filter(candidate: pd.Series, min_run_windows: int) -> pd.Series:
    """Keep only positive runs with at least min_run_windows consecutive rows."""
    if min_run_windows <= 1:
        return candidate.astype(int)

    values = candidate.astype(bool).to_numpy()
    filtered = np.zeros(len(values), dtype=int)
    start: int | None = None

    for idx, value in enumerate(values):
        if value and start is None:
            start = idx
        if (not value or idx == len(values) - 1) and start is not None:
            end = idx if value and idx == len(values) - 1 else idx - 1
            if end - start + 1 >= min_run_windows:
                filtered[start : end + 1] = 1
            start = None

    return pd.Series(filtered, index=candidate.index)


def apply_temporal_rule(
    predictions: pd.DataFrame,
    threshold: float,
    min_run_windows: int,
) -> pd.Series:
    """Apply threshold and temporal persistence independently per segment."""
    ordered = predictions.sort_values(
        ["prediction_file", "time_center"],
        kind="mergesort",
    )
    y_pred = pd.Series(0, index=ordered.index, dtype=int)

    for _, segment in ordered.groupby("prediction_file", sort=False):
        candidate = segment["walking_probability"].astype(float) >= threshold
        y_pred.loc[segment.index] = apply_min_run_filter(
            candidate,
            min_run_windows=min_run_windows,
        )

    return y_pred.reindex(predictions.index).astype(int)


def score_temporal_rule(
    predictions: pd.DataFrame,
    threshold: float,
    min_run_windows: int,
) -> dict[str, float | int]:
    """Compute aggregate metrics for one temporal rule."""
    valid = predictions[predictions["true_label"] != "NO_LABEL"].copy()
    y_true = valid["true_label"].map(LABEL_MAP).astype(int)
    y_pred = apply_temporal_rule(
        valid,
        threshold=threshold,
        min_run_windows=min_run_windows,
    )
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "threshold": round(float(threshold), 4),
        "min_run_windows": int(min_run_windows),
        "rows": int(len(valid)),
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
        "specificity_not_walking": tn / (tn + fp) if (tn + fp) else 0.0,
        "false_positive_rate": fp / (tn + fp) if (tn + fp) else 0.0,
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def main() -> None:
    """Run temporal smoothing sweep and save metrics."""
    args = build_parser().parse_args()
    predictions = pd.read_csv(args.input)
    predictions["time_center"] = pd.to_datetime(predictions["time_center"], utc=True)

    rows = []
    for threshold in args.thresholds:
        for min_run_windows in args.min_run_windows:
            rows.append(
                score_temporal_rule(
                    predictions,
                    threshold=threshold,
                    min_run_windows=min_run_windows,
                )
            )
    results = pd.DataFrame(rows)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output, index=False)

    best_f1 = results.sort_values(
        ["f1_walking", "precision_walking", "accuracy"],
        ascending=False,
    ).iloc[0]
    best_precision = results.sort_values(
        ["precision_walking", "f1_walking", "accuracy"],
        ascending=False,
    ).iloc[0]

    print(f"Input predictions: {args.input}")
    print(f"Output: {output}")
    print("\nBest F1 walking:")
    print(best_f1.to_frame().T.to_string(index=False))
    print("\nBest precision walking:")
    print(best_precision.to_frame().T.to_string(index=False))


if __name__ == "__main__":
    main()
