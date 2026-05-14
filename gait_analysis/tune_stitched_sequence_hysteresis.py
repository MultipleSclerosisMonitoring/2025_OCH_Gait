#!/usr/bin/env python3
"""Sweep hysteresis rules over stitched sequence predictions."""

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

from gait_analysis.build_stitched_sequence_evaluation import (
    build_stitched_sequence,
    load_selected_segments,
)
from gait_analysis.run_sequence_evaluation import LABEL_MAP


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Evalua reglas de histeresis sobre secuencias concatenadas: "
            "umbral alto para activar marcha y umbral bajo para apagarla."
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
        "--enter-thresholds",
        nargs="+",
        type=float,
        default=[0.65, 0.70, 0.75, 0.80, 0.85],
        help="Umbrales altos para activar walking",
    )
    p.add_argument(
        "--exit-thresholds",
        nargs="+",
        type=float,
        default=[0.40, 0.45, 0.50, 0.55, 0.60, 0.65],
        help="Umbrales bajos para desactivar walking",
    )
    p.add_argument(
        "--enter-run-windows",
        nargs="+",
        type=int,
        default=[1, 2, 3, 4],
        help="Ventanas consecutivas por encima del umbral alto para activar",
    )
    p.add_argument(
        "--exit-run-windows",
        nargs="+",
        type=int,
        default=[1, 2, 3, 4, 5],
        help="Ventanas consecutivas por debajo del umbral bajo para apagar",
    )
    p.add_argument(
        "-o",
        "--output",
        default="results/stitched_sequence_hysteresis_sweep.csv",
        help="CSV de salida con metricas por combinacion",
    )
    return p


def apply_hysteresis(
    probabilities: pd.Series,
    enter_threshold: float,
    exit_threshold: float,
    enter_run_windows: int,
    exit_run_windows: int,
) -> pd.Series:
    """Apply a two-threshold state machine to probability values."""
    values = probabilities.astype(float).to_numpy()
    predictions = np.zeros(len(values), dtype=int)
    active = False
    enter_count = 0
    exit_count = 0

    for idx, probability in enumerate(values):
        if active:
            predictions[idx] = 1
            if probability < exit_threshold:
                exit_count += 1
            else:
                exit_count = 0
            if exit_count >= exit_run_windows:
                start = idx - exit_count + 1
                predictions[start : idx + 1] = 0
                active = False
                exit_count = 0
                enter_count = 0
        else:
            if probability >= enter_threshold:
                enter_count += 1
            else:
                enter_count = 0
            if enter_count >= enter_run_windows:
                start = idx - enter_count + 1
                predictions[start : idx + 1] = 1
                active = True
                exit_count = 0

    return pd.Series(predictions, index=probabilities.index)


def score_rule(
    stitched: pd.DataFrame,
    enter_threshold: float,
    exit_threshold: float,
    enter_run_windows: int,
    exit_run_windows: int,
) -> dict[str, float | int]:
    """Compute binary metrics for one hysteresis rule."""
    y_true = stitched["true_label"].map(LABEL_MAP).astype(int)
    y_pred = apply_hysteresis(
        stitched["walking_probability"],
        enter_threshold=enter_threshold,
        exit_threshold=exit_threshold,
        enter_run_windows=enter_run_windows,
        exit_run_windows=exit_run_windows,
    ).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "enter_threshold": round(float(enter_threshold), 4),
        "exit_threshold": round(float(exit_threshold), 4),
        "enter_run_windows": int(enter_run_windows),
        "exit_run_windows": int(exit_run_windows),
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
    """Run the stitched-sequence hysteresis sweep."""
    args = build_parser().parse_args()
    selected = load_selected_segments(Path(args.windows), scope=args.scope)
    predictions = pd.read_csv(args.predictions)
    stitched = build_stitched_sequence(predictions, selected)

    rows = []
    for enter_threshold in args.enter_thresholds:
        for exit_threshold in args.exit_thresholds:
            if exit_threshold > enter_threshold:
                continue
            for enter_run_windows in args.enter_run_windows:
                for exit_run_windows in args.exit_run_windows:
                    row = score_rule(
                        stitched,
                        enter_threshold=enter_threshold,
                        exit_threshold=exit_threshold,
                        enter_run_windows=enter_run_windows,
                        exit_run_windows=exit_run_windows,
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
