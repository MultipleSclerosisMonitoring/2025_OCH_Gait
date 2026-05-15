#!/usr/bin/env python3
"""Tune a consensus gate between RF and transformer sequence probabilities."""

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

from gait_analysis.run_sequence_evaluation import LABEL_MAP
from gait_analysis.tune_sequence_temporal_smoothing import apply_min_run_filter


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Combina probabilidades RF y transformer y acepta walking solo "
            "cuando ambos modelos superan su umbral."
        )
    )
    p.add_argument(
        "--rf-predictions",
        default="results/sequence_evaluation_predictions.csv",
        help="CSV de predicciones RF por ventana",
    )
    p.add_argument(
        "--transformer-predictions",
        default="results/transformer_sequence_eval_predictions_unweighted_nols.csv",
        help="CSV de predicciones transformer por ventana",
    )
    p.add_argument(
        "--transformer-thresholds",
        nargs="+",
        type=float,
        default=[0.43, 0.50, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90],
    )
    p.add_argument(
        "--rf-thresholds",
        nargs="+",
        type=float,
        default=[0.50, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90],
    )
    p.add_argument(
        "--min-run-windows",
        nargs="+",
        type=int,
        default=[1, 2, 3, 4, 5, 8, 10],
    )
    p.add_argument(
        "--selected-transformer-threshold",
        type=float,
        default=0.65,
        help="Umbral transformer usado para guardar la prediccion final",
    )
    p.add_argument(
        "--selected-rf-threshold",
        type=float,
        default=0.65,
        help="Umbral RF usado para guardar la prediccion final",
    )
    p.add_argument(
        "--selected-min-run-windows",
        type=int,
        default=3,
        help="Persistencia usada para guardar la prediccion final",
    )
    p.add_argument(
        "--sweep-output",
        default="results/transformer_rf_consensus_sweep_unweighted_nols.csv",
        help="CSV de salida del barrido",
    )
    p.add_argument(
        "--prediction-output",
        default="results/transformer_rf_consensus_predictions_unweighted_nols.csv",
        help="CSV de salida con predicciones de la regla seleccionada",
    )
    p.add_argument(
        "--summary-output",
        default="results/transformer_rf_consensus_summary_unweighted_nols.csv",
        help="CSV de salida con metricas de la regla seleccionada",
    )
    return p


def align_predictions(
    rf: pd.DataFrame,
    transformer: pd.DataFrame,
) -> pd.DataFrame:
    """Align RF and transformer predictions by nearest timestamp per reference."""
    rf = rf.copy()
    transformer = transformer.copy()
    rf["time_center"] = pd.to_datetime(rf["time_center"], utc=True)
    transformer["time_center"] = pd.to_datetime(transformer["time_center"], utc=True)
    rf["reference"] = rf["reference"].astype(str)
    transformer["reference"] = transformer["reference"].astype(str)

    aligned_parts = []
    for reference, transformer_segment in transformer.groupby("reference"):
        rf_segment = rf[rf["reference"].eq(reference)].sort_values("time_center")
        if rf_segment.empty:
            continue
        aligned = pd.merge_asof(
            transformer_segment.sort_values("time_center"),
            rf_segment[
                [
                    "time_center",
                    "walking_probability",
                    "prediction_file",
                ]
            ].sort_values("time_center"),
            on="time_center",
            direction="nearest",
            tolerance=pd.Timedelta(milliseconds=600),
            suffixes=("_transformer", "_rf"),
        )
        aligned_parts.append(aligned)

    if not aligned_parts:
        raise ValueError("No se han podido alinear predicciones RF y transformer.")
    return pd.concat(aligned_parts, ignore_index=True).dropna(
        subset=["walking_probability_rf"]
    )


def apply_consensus(
    predictions: pd.DataFrame,
    transformer_threshold: float,
    rf_threshold: float,
    min_run_windows: int,
) -> pd.Series:
    """Apply probability thresholds and temporal persistence."""
    candidate = (
        predictions["walking_probability_transformer"].astype(float)
        >= transformer_threshold
    ) & (predictions["walking_probability_rf"].astype(float) >= rf_threshold)
    return apply_min_run_filter(candidate, min_run_windows).astype(int)


def score_rule(
    predictions: pd.DataFrame,
    transformer_threshold: float,
    rf_threshold: float,
    min_run_windows: int,
) -> dict[str, float | int]:
    """Score one consensus rule."""
    y_true = predictions["true_label"].map(LABEL_MAP).astype(int)
    y_pred = apply_consensus(
        predictions,
        transformer_threshold=transformer_threshold,
        rf_threshold=rf_threshold,
        min_run_windows=min_run_windows,
    )
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "transformer_threshold": round(float(transformer_threshold), 4),
        "rf_threshold": round(float(rf_threshold), 4),
        "min_run_windows": int(min_run_windows),
        "rows": int(len(predictions)),
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
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def main() -> None:
    """Run consensus sweep and save selected predictions."""
    args = build_parser().parse_args()
    rf = pd.read_csv(args.rf_predictions)
    transformer = pd.read_csv(args.transformer_predictions)
    predictions = align_predictions(rf, transformer)

    rows = []
    for transformer_threshold in args.transformer_thresholds:
        for rf_threshold in args.rf_thresholds:
            for min_run_windows in args.min_run_windows:
                rows.append(
                    score_rule(
                        predictions,
                        transformer_threshold=transformer_threshold,
                        rf_threshold=rf_threshold,
                        min_run_windows=min_run_windows,
                    )
                )

    sweep = pd.DataFrame(rows)
    selected_pred = apply_consensus(
        predictions,
        transformer_threshold=args.selected_transformer_threshold,
        rf_threshold=args.selected_rf_threshold,
        min_run_windows=args.selected_min_run_windows,
    )
    predictions = predictions.copy()
    predictions["consensus_prediction"] = selected_pred
    predictions["consensus_prediction_label"] = predictions[
        "consensus_prediction"
    ].map({0: "not_walking", 1: "walking"})
    selected_summary = pd.DataFrame(
        [
            score_rule(
                predictions,
                transformer_threshold=args.selected_transformer_threshold,
                rf_threshold=args.selected_rf_threshold,
                min_run_windows=args.selected_min_run_windows,
            )
        ]
    )

    for path in [args.sweep_output, args.prediction_output, args.summary_output]:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    sweep.to_csv(args.sweep_output, index=False)
    predictions.to_csv(args.prediction_output, index=False)
    selected_summary.to_csv(args.summary_output, index=False)

    best = sweep.sort_values(
        ["f1_walking", "fp", "accuracy"],
        ascending=[False, True, False],
    ).iloc[0]
    print(f"Aligned rows: {len(predictions)}")
    print(f"Sweep output: {args.sweep_output}")
    print(f"Prediction output: {args.prediction_output}")
    print(f"Summary output: {args.summary_output}")
    print("\nSelected rule:")
    print(selected_summary.round(4).to_string(index=False))
    print("\nBest F1 rule:")
    print(best.to_frame().T.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
