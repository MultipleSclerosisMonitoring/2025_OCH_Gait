#!/usr/bin/env python3
"""Evaluate final transformer inference on configured temporal segments."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from gait_analysis.predict_walking_sequence import make_block_id
from gait_analysis.run_sequence_evaluation import LABEL_MAP, label_time_center, load_ground_truth
from gait_analysis.tune_sequence_temporal_smoothing import apply_min_run_filter


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Ejecuta inferencia transformer por ventana movil sobre segmentos "
            "configurados y evalua las predicciones contra ground truth."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        default="experiment_configs/sequence_evaluation_windows.csv",
        help="CSV con segmentos de evaluacion",
    )
    p.add_argument(
        "-g",
        "--ground-truth",
        default="salidas_test/ground_truth_clean.xlsx",
        help="Excel limpio de ground truth",
    )
    p.add_argument(
        "--prediction-dir",
        default="salidas_test/transformer_sequence_predictions",
        help="Directorio donde guardar predicciones por segmento",
    )
    p.add_argument(
        "--results-output",
        default="results/transformer_sequence_eval_results.csv",
        help="CSV con metricas por segmento",
    )
    p.add_argument(
        "--predictions-output",
        default="results/transformer_sequence_eval_predictions.csv",
        help="CSV con todas las predicciones etiquetadas",
    )
    p.add_argument(
        "--summary-output",
        default="results/transformer_sequence_eval_summary.csv",
        help="CSV con metricas agregadas",
    )
    p.add_argument(
        "--stitched-output",
        default="results/transformer_stitched_sequence_predictions.csv",
        help="CSV con secuencia concatenada y postprocesada",
    )
    p.add_argument(
        "--stitched-summary-output",
        default="results/transformer_stitched_sequence_summary.csv",
        help="CSV con metricas de la secuencia concatenada",
    )
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Configuracion de espectrograma",
    )
    p.add_argument(
        "--model",
        default="models/final_transformer_sequence_model.pt",
        help="Artefacto transformer final",
    )
    p.add_argument("--threshold", type=float, default=0.43)
    p.add_argument("--min-run-windows", type=int, default=8)
    p.add_argument("--scope", choices=["same_patient", "new_patient", "all_valid"], default="same_patient")
    p.add_argument("--include-pending", action="store_true")
    return p


def score_predictions(predictions: pd.DataFrame, pred_col: str = "prediction") -> dict[str, float | int]:
    """Compute metrics on labeled predictions."""
    valid = predictions[predictions["true_label"] != "NO_LABEL"].copy()
    if valid.empty:
        return {
            "valid_rows": 0,
            "accuracy": float("nan"),
            "precision_walking": float("nan"),
            "recall_walking": float("nan"),
            "f1_walking": float("nan"),
            "tn": 0,
            "fp": 0,
            "fn": 0,
            "tp": 0,
        }
    y_true = valid["true_label"].map(LABEL_MAP).astype(int)
    y_pred = valid[pred_col].astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "valid_rows": int(len(valid)),
        "accuracy": accuracy_score(y_true, y_pred),
        "precision_walking": precision_score(y_true, y_pred, pos_label=1, zero_division=0),
        "recall_walking": recall_score(y_true, y_pred, pos_label=1, zero_division=0),
        "f1_walking": f1_score(y_true, y_pred, pos_label=1, zero_division=0),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def run_prediction(row: pd.Series, args: argparse.Namespace, prediction_dir: Path) -> Path:
    """Run transformer prediction for one configured segment."""
    block_id = make_block_id(str(row["Reference"]), str(row["from_time"]), str(row["until_time"]))
    output_path = prediction_dir / f"{block_id}_transformer_predictions.csv"
    cmd = [
        sys.executable,
        "-m",
        "gait_analysis.predict_transformer_walking_sequence",
        "-q",
        str(row["Reference"]),
        "-f",
        str(row["from_time"]),
        "-u",
        str(row["until_time"]),
        "--config",
        args.config,
        "--model",
        args.model,
        "--threshold",
        str(args.threshold),
        "-o",
        str(output_path),
    ]
    print(">>>", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return output_path


def select_windows(windows: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    """Filter configured windows according to scope."""
    selected = windows.copy()
    if not args.include_pending:
        selected = selected[selected["use_for_sequence_eval"] == True].copy()
    selected = selected[selected["coverage_status"] == "valid_both_feet"].copy()
    if args.scope == "same_patient":
        selected = selected[selected["seen_patient"] == True].copy()
    elif args.scope == "new_patient":
        selected = selected[selected["seen_patient"] == False].copy()
    if selected.empty:
        raise ValueError(f"No hay segmentos validos para scope={args.scope}.")
    return selected.reset_index(drop=True)


def build_stitched(predictions: pd.DataFrame, min_run_windows: int, threshold: float) -> pd.DataFrame:
    """Concatenate segment predictions and apply final temporal smoothing."""
    chunks = []
    offset = 0
    for order, (_, segment) in enumerate(predictions.groupby("prediction_file", sort=False)):
        segment = segment.sort_values("time_center").copy()
        segment["stitched_segment_order"] = order
        segment["stitched_row"] = range(offset, offset + len(segment))
        segment["stitched_time_s"] = segment["stitched_row"]
        offset += len(segment)
        chunks.append(segment)
    stitched = pd.concat(chunks, ignore_index=True)
    candidate = stitched["walking_probability"].astype(float) >= threshold
    stitched["stitched_prediction"] = apply_min_run_filter(candidate, min_run_windows).astype(int)
    stitched["stitched_prediction_label"] = stitched["stitched_prediction"].map(
        {0: "not_walking", 1: "walking"}
    )
    return stitched


def main() -> None:
    """Run transformer sequence evaluation."""
    args = build_parser().parse_args()
    gt = load_ground_truth(Path(args.ground_truth))
    windows = select_windows(pd.read_csv(args.input), args)
    prediction_dir = Path(args.prediction_dir)
    prediction_dir.mkdir(parents=True, exist_ok=True)

    all_predictions = []
    result_rows = []
    for _, row in windows.iterrows():
        prediction_path = run_prediction(row, args, prediction_dir)
        predictions = pd.read_csv(prediction_path)
        predictions["time_center"] = pd.to_datetime(predictions["time_center"], utc=True)
        predictions["true_label"] = predictions.apply(
            lambda pred: label_time_center(
                gt=gt,
                reference=str(pred["reference"]),
                time_center=pred["time_center"],
            ),
            axis=1,
        )
        predictions["expected_content"] = row["expected_content"]
        predictions["seen_patient"] = row["seen_patient"]
        predictions["segment_from_time"] = row["from_time"]
        predictions["segment_until_time"] = row["until_time"]
        predictions["prediction_file"] = str(prediction_path)

        metrics = score_predictions(predictions)
        result_rows.append(
            {
                "Reference": row["Reference"],
                "from_time": row["from_time"],
                "until_time": row["until_time"],
                "expected_content": row["expected_content"],
                "seen_patient": row["seen_patient"],
                "prediction_file": str(prediction_path),
                "rows": int(len(predictions)),
                **metrics,
            }
        )
        all_predictions.append(predictions)

    result_df = pd.DataFrame(result_rows)
    prediction_df = pd.concat(all_predictions, ignore_index=True)
    summary = score_predictions(prediction_df)
    summary_df = pd.DataFrame(
        [
            {
                "scope": args.scope,
                "segments": int(len(result_df)),
                "threshold": float(args.threshold),
                "rows": int(summary.pop("valid_rows")),
                **summary,
            }
        ]
    )
    stitched = build_stitched(
        prediction_df,
        min_run_windows=args.min_run_windows,
        threshold=args.threshold,
    )
    stitched_summary = score_predictions(stitched, pred_col="stitched_prediction")
    stitched_summary_df = pd.DataFrame(
        [
            {
                "scope": args.scope,
                "segments": int(len(result_df)),
                "threshold": float(args.threshold),
                "min_run_windows": int(args.min_run_windows),
                "rows": int(stitched_summary.pop("valid_rows")),
                **stitched_summary,
            }
        ]
    )

    outputs = [
        Path(args.results_output),
        Path(args.predictions_output),
        Path(args.summary_output),
        Path(args.stitched_output),
        Path(args.stitched_summary_output),
    ]
    for output in outputs:
        output.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(args.results_output, index=False)
    prediction_df.to_csv(args.predictions_output, index=False)
    summary_df.to_csv(args.summary_output, index=False)
    stitched.to_csv(args.stitched_output, index=False)
    stitched_summary_df.to_csv(args.stitched_summary_output, index=False)

    print(f"Evaluated segments: {len(result_df)}")
    print(f"Predictions output: {args.predictions_output}")
    print(f"Stitched output: {args.stitched_output}")
    print()
    print("Summary:")
    print(summary_df.round(4).to_string(index=False))
    print()
    print("Stitched summary:")
    print(stitched_summary_df.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
