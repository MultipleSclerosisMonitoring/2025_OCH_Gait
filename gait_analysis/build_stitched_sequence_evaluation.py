#!/usr/bin/env python3
"""Build and evaluate a stitched walking/not-walking temporal sequence."""

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

from gait_analysis.interval_filters import exclude_windows_by_interval, load_interval_exclusions
from gait_analysis.run_sequence_evaluation import LABEL_MAP
from gait_analysis.tune_sequence_temporal_smoothing import apply_min_run_filter


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Concatena segmentos no vistos de marcha/no marcha y evalua la "
            "prediccion por ventana movil sobre una secuencia artificial continua."
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
        "--threshold",
        type=float,
        default=0.65,
        help="Umbral de probabilidad para clasificar walking",
    )
    p.add_argument(
        "--min-run-windows",
        type=int,
        default=2,
        help="Numero minimo de ventanas positivas consecutivas",
    )
    p.add_argument(
        "--predictions-output",
        default="results/stitched_sequence_predictions.csv",
        help="CSV de salida con la secuencia concatenada",
    )
    p.add_argument(
        "--summary-output",
        default="results/stitched_sequence_summary.csv",
        help="CSV de salida con metricas agregadas",
    )
    p.add_argument(
        "--exclude-intervals",
        default=None,
        help="CSV con intervalos a excluir antes de construir la secuencia.",
    )
    p.add_argument(
        "--timezone",
        default="UTC",
        help="Zona horaria usada por el CSV de ventanas si no viene con zona.",
    )
    return p


def filter_selected_segments(
    windows: pd.DataFrame,
    scope: str,
    exclude_intervals: str | None,
    timezone: str,
) -> pd.DataFrame:
    """Load configured segments and keep the requested evaluation scope."""
    selected = windows.copy()
    if exclude_intervals:
        exclusions = load_interval_exclusions(exclude_intervals)
        selected = exclude_windows_by_interval(
            selected,
            exclusions,
            window_timezone=None if timezone.upper() == "UTC" else timezone,
        )
    selected = selected[selected["use_for_sequence_eval"] == True].copy()
    if scope == "same_patient":
        selected = selected[selected["seen_patient"] == True].copy()
    elif scope == "new_patient":
        selected = selected[selected["seen_patient"] == False].copy()
    selected = selected[selected["coverage_status"] == "valid_both_feet"].copy()
    if selected.empty:
        raise ValueError(f"No hay segmentos validos para scope={scope}.")
    return selected.reset_index(drop=True)


def segment_key(reference: str, from_time: str, until_time: str) -> str:
    """Build a stable key for one segment."""
    return f"{reference}|{from_time}|{until_time}"


def build_stitched_sequence(
    predictions: pd.DataFrame,
    selected: pd.DataFrame,
) -> pd.DataFrame:
    """Concatenate selected prediction segments into one synthetic timeline."""
    predictions = predictions.copy()
    predictions["segment_key"] = predictions.apply(
        lambda row: segment_key(
            str(row["reference"]),
            str(row["segment_from_time"]),
            str(row["segment_until_time"]),
        ),
        axis=1,
    )
    selected["segment_key"] = selected.apply(
        lambda row: segment_key(
            str(row["Reference"]),
            str(row["from_time"]),
            str(row["until_time"]),
        ),
        axis=1,
    )

    chunks = []
    synthetic_offset = 0
    for order, segment in selected.iterrows():
        segment_predictions = predictions[
            predictions["segment_key"] == segment["segment_key"]
        ].copy()
        if segment_predictions.empty:
            continue
        segment_predictions["time_center"] = pd.to_datetime(
            segment_predictions["time_center"],
            utc=True,
        )
        segment_predictions = segment_predictions.sort_values("time_center")
        segment_predictions["stitched_segment_order"] = int(order)
        segment_predictions["stitched_row"] = range(
            synthetic_offset,
            synthetic_offset + len(segment_predictions),
        )
        segment_predictions["stitched_time_s"] = segment_predictions["stitched_row"]
        synthetic_offset += len(segment_predictions)
        chunks.append(segment_predictions)

    if not chunks:
        raise ValueError("No se encontraron predicciones para los segmentos elegidos.")

    stitched = pd.concat(chunks, ignore_index=True)
    return stitched.sort_values("stitched_row").reset_index(drop=True)


def score_predictions(stitched: pd.DataFrame) -> dict[str, float | int]:
    """Compute aggregate binary metrics for the stitched sequence."""
    valid = stitched[stitched["true_label"] != "NO_LABEL"].copy()
    y_true = valid["true_label"].map(LABEL_MAP).astype(int)
    y_pred = valid["stitched_prediction"].astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
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
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def main() -> None:
    """Build stitched sequence outputs and summary metrics."""
    args = build_parser().parse_args()
    windows = pd.read_csv(args.windows)
    selected = filter_selected_segments(
        windows,
        scope=args.scope,
        exclude_intervals=args.exclude_intervals,
        timezone=args.timezone,
    )
    predictions = pd.read_csv(args.predictions)
    stitched = build_stitched_sequence(predictions, selected)

    candidate = stitched["walking_probability"].astype(float) >= args.threshold
    stitched["stitched_prediction"] = apply_min_run_filter(
        candidate,
        min_run_windows=args.min_run_windows,
    ).astype(int)
    stitched["stitched_prediction_label"] = stitched["stitched_prediction"].map(
        {0: "not_walking", 1: "walking"}
    )

    summary = {
        "scope": args.scope,
        "segments": int(stitched["segment_key"].nunique()),
        "threshold": float(args.threshold),
        "min_run_windows": int(args.min_run_windows),
        **score_predictions(stitched),
    }
    summary_df = pd.DataFrame([summary])

    predictions_output = Path(args.predictions_output)
    summary_output = Path(args.summary_output)
    predictions_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    stitched.to_csv(predictions_output, index=False)
    summary_df.to_csv(summary_output, index=False)

    print(f"Scope: {args.scope}")
    print(f"Segments: {summary['segments']}")
    print(f"Predictions output: {predictions_output}")
    print(f"Summary output: {summary_output}")
    print()
    print(summary_df.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
