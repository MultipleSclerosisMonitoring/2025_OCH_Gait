#!/usr/bin/env python3
"""Sweep decision thresholds over saved sequence predictions."""

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
            "Recalcula metricas de evaluacion secuencial para distintos "
            "umbrales usando predicciones ya guardadas."
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
        default="results/sequence_threshold_sweep.csv",
        help="CSV de salida con metricas por umbral",
    )
    p.add_argument(
        "--start",
        type=float,
        default=0.30,
        help="Primer umbral a evaluar",
    )
    p.add_argument(
        "--stop",
        type=float,
        default=0.90,
        help="Ultimo umbral a evaluar",
    )
    p.add_argument(
        "--step",
        type=float,
        default=0.05,
        help="Incremento entre umbrales",
    )
    return p


def score_threshold(predictions: pd.DataFrame, threshold: float) -> dict[str, float | int]:
    """Compute aggregate metrics for one probability threshold."""
    valid = predictions[predictions["true_label"] != "NO_LABEL"].copy()
    y_true = valid["true_label"].map(LABEL_MAP).astype(int)
    y_pred = (valid["walking_probability"].astype(float) >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "threshold": round(float(threshold), 4),
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


def threshold_values(start: float, stop: float, step: float) -> np.ndarray:
    """Return inclusive threshold values, avoiding float endpoint surprises."""
    if step <= 0:
        raise ValueError("--step debe ser mayor que 0")
    count = int(np.floor((stop - start) / step)) + 1
    if count <= 0:
        raise ValueError("--stop debe ser mayor o igual que --start")
    return start + np.arange(count) * step


def main() -> None:
    """Run threshold sweep and save metrics."""
    args = build_parser().parse_args()
    predictions = pd.read_csv(args.input)
    thresholds = threshold_values(args.start, args.stop, args.step)
    results = pd.DataFrame(
        [score_threshold(predictions, threshold) for threshold in thresholds]
    )

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
