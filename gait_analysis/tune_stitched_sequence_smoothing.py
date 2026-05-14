#!/usr/bin/env python3
"""Sweep conservative temporal rules over stitched sequence predictions."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from gait_analysis.build_stitched_sequence_evaluation import (
    build_stitched_sequence,
    load_selected_segments,
)
from gait_analysis.run_sequence_evaluation import LABEL_MAP
from gait_analysis.tune_sequence_temporal_smoothing import apply_min_run_filter


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Evalua umbrales y persistencia temporal sobre secuencias "
            "concatenadas de segmentos no vistos."
        )
    )
    p.add_argument(
        "--predictions",
        default="results/sequence_evaluation_predictions.csv",
        help="CSV con predicciones por segmento generadas por run_sequence_evaluation",
    )
    p.add_argument(
        "--windows",
        default="experiment_configs/sequence_evaluation_windows.csv",
        help="CSV con la configuracion de segmentos de evaluacion",
    )
    p.add_argument(
        "--scope",
        choices=["same_patient", "new_patient", "all_valid"],
        default="same_patient",
        help="Segmentos a concatenar",
    )
    p.add_argument(
        "--thresholds",
        nargs="+",
        type=float,
        default=[0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95],
        help="Umbrales de probabilidad a evaluar",
    )
    p.add_argument(
        "--min-run-windows",
        nargs="+",
        type=int,
        default=[2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20],
        help="Longitudes minimas de bloques consecutivos positivos",
    )
    p.add_argument(
        "-o",
        "--output",
        default="results/stitched_sequence_smoothing_sweep.csv",
        help="CSV de salida con metricas por combinacion",
    )
    return p


def score_rule(
    stitched: pd.DataFrame,
    threshold: float,
    min_run_windows: int,
) -> dict[str, float | int]:
    """Compute binary metrics for one stitched-sequence rule."""
    y_true = stitched["true_label"].map(LABEL_MAP).astype(int)
    candidate = stitched["walking_probability"].astype(float) >= threshold
    y_pred = apply_min_run_filter(candidate, min_run_windows).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "threshold": round(float(threshold), 4),
        "min_run_windows": int(min_run_windows),
        "rows": int(len(stitched)),
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
    """Run the stitched-sequence smoothing sweep."""
    args = build_parser().parse_args()
    selected = load_selected_segments(Path(args.windows), scope=args.scope)
    predictions = pd.read_csv(args.predictions)
    stitched = build_stitched_sequence(predictions, selected)

    rows = []
    for threshold in args.thresholds:
        for min_run_windows in args.min_run_windows:
            row = score_rule(
                stitched,
                threshold=threshold,
                min_run_windows=min_run_windows,
            )
            row["scope"] = args.scope
            row["segments"] = int(stitched["segment_key"].nunique())
            rows.append(row)

    results = pd.DataFrame(rows)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output, index=False)

    best_f1 = results.sort_values(
        ["f1_walking", "fp", "accuracy"],
        ascending=[False, True, False],
    ).iloc[0]
    with_recall = results[results["recall_walking"] >= 0.5]
    print(f"Scope: {args.scope}")
    print(f"Output: {output}")
    print("\nBest F1:")
    print(best_f1.to_frame().T.to_string(index=False))
    if not with_recall.empty:
        print("\nLowest FP with recall >= 0.50:")
        best_fp = with_recall.sort_values(
            ["fp", "f1_walking", "accuracy"],
            ascending=[True, False, False],
        ).iloc[0]
        print(best_fp.to_frame().T.to_string(index=False))
    print("\nLowest FP overall:")
    best_low_fp = results.sort_values(
        ["fp", "f1_walking", "accuracy"],
        ascending=[True, False, False],
    ).iloc[0]
    print(best_low_fp.to_frame().T.to_string(index=False))


if __name__ == "__main__":
    main()
