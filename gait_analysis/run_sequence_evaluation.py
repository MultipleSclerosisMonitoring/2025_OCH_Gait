#!/usr/bin/env python3
"""Evaluate sequence predictions against ground truth intervals."""

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


LABEL_MAP = {"not_walking": 0, "walking": 1}
INVERSE_LABEL_MAP = {v: k for k, v in LABEL_MAP.items()}


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Ejecuta inferencia por ventana movil sobre segmentos configurados "
            "y evalua las predicciones contra ground truth."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        default="experiment_configs/sequence_evaluation_windows.csv",
        help="CSV con segmentos de evaluacion de secuencias",
    )
    p.add_argument(
        "-g",
        "--ground-truth",
        default="salidas_test/ground_truth_clean.xlsx",
        help="Excel limpio de ground truth",
    )
    p.add_argument(
        "--prediction-dir",
        default="salidas_test/sequence_predictions",
        help="Directorio donde guardar predicciones por segmento",
    )
    p.add_argument(
        "--results-output",
        default="results/sequence_evaluation_results.csv",
        help="CSV con metricas por segmento",
    )
    p.add_argument(
        "--predictions-output",
        default="results/sequence_evaluation_predictions.csv",
        help="CSV con todas las predicciones etiquetadas",
    )
    p.add_argument(
        "--summary-output",
        default="results/sequence_evaluation_summary.csv",
        help="CSV con metricas agregadas",
    )
    p.add_argument(
        "--include-pending",
        action="store_true",
        help="Ejecuta tambien filas no marcadas como use_for_sequence_eval=True",
    )
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Configuracion de espectrograma para la inferencia",
    )
    p.add_argument(
        "--model",
        default="models/final_random_forest_model.joblib",
        help="Modelo entrenado en formato joblib",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Umbral de probabilidad para clasificar walking",
    )
    return p


def load_ground_truth(path: Path) -> pd.DataFrame:
    """Load ground truth intervals and normalize timestamps."""
    gt = pd.read_excel(path)
    gt["datefrom"] = pd.to_datetime(gt["datefrom"], utc=True)
    gt["dateuntil"] = pd.to_datetime(gt["dateuntil"], utc=True)
    return gt


def label_time_center(
    gt: pd.DataFrame,
    reference: str,
    time_center: pd.Timestamp,
) -> str:
    """Return ground-truth label for one prediction timestamp."""
    ref_gt = gt[gt["Reference"].astype(str).eq(str(reference))]
    for _, row in ref_gt.iterrows():
        if row["datefrom"] <= time_center < row["dateuntil"]:
            return str(row["mov_type"])
    return "NO_LABEL"


def run_prediction(
    row: pd.Series,
    prediction_dir: Path,
    config: str,
    model: str,
    threshold: float,
) -> Path:
    """Run predict_walking_sequence.py for one configured segment."""
    block_id = make_block_id(
        str(row["Reference"]),
        str(row["from_time"]),
        str(row["until_time"]),
    )
    output_path = prediction_dir / f"{block_id}_predictions.csv"
    cmd = [
        sys.executable,
        "gait_analysis/predict_walking_sequence.py",
        "-q",
        str(row["Reference"]),
        "-f",
        str(row["from_time"]),
        "-u",
        str(row["until_time"]),
        "--config",
        config,
        "--model",
        model,
        "--threshold",
        str(threshold),
        "-o",
        str(output_path),
    ]
    print(">>>", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return output_path


def score_segment(predictions: pd.DataFrame) -> dict[str, float | int]:
    """Compute metrics for one labeled prediction segment."""
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
    y_pred = valid["prediction"].astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "valid_rows": int(len(valid)),
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


def build_summary(all_predictions: pd.DataFrame) -> pd.DataFrame:
    """Build aggregate metrics over all labeled sequence predictions."""
    valid = all_predictions[all_predictions["true_label"] != "NO_LABEL"].copy()
    if valid.empty:
        return pd.DataFrame(
            [
                {
                    "scope": "all_segments",
                    "rows": 0,
                    "accuracy": float("nan"),
                    "precision_walking": float("nan"),
                    "recall_walking": float("nan"),
                    "f1_walking": float("nan"),
                    "tn": 0,
                    "fp": 0,
                    "fn": 0,
                    "tp": 0,
                }
            ]
        )

    metrics = score_segment(valid)
    return pd.DataFrame(
        [
            {
                "scope": "all_segments",
                "rows": int(len(valid)),
                **{k: v for k, v in metrics.items() if k != "valid_rows"},
            }
        ]
    )


def main() -> None:
    """Run configured sequence evaluation and save metrics."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    prediction_dir = Path(args.prediction_dir)
    results_output = Path(args.results_output)
    predictions_output = Path(args.predictions_output)
    summary_output = Path(args.summary_output)
    gt = load_ground_truth(Path(args.ground_truth))

    windows = pd.read_csv(input_path)
    if not args.include_pending:
        windows = windows[windows["use_for_sequence_eval"] == True].copy()

    if windows.empty:
        raise ValueError(
            "No hay segmentos marcados para evaluar. Marca "
            "use_for_sequence_eval=True o usa --include-pending."
        )

    prediction_dir.mkdir(parents=True, exist_ok=True)
    all_predictions = []
    result_rows = []

    for _, row in windows.iterrows():
        prediction_path = run_prediction(
            row=row,
            prediction_dir=prediction_dir,
            config=args.config,
            model=args.model,
            threshold=args.threshold,
        )
        predictions = pd.read_csv(prediction_path)
        predictions["time_center"] = pd.to_datetime(
            predictions["time_center"],
            utc=True,
        )
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

        metrics = score_segment(predictions)
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
    summary_df = build_summary(prediction_df)

    for path in [results_output, predictions_output, summary_output]:
        path.parent.mkdir(parents=True, exist_ok=True)

    result_df.to_csv(results_output, index=False)
    prediction_df.to_csv(predictions_output, index=False)
    summary_df.to_csv(summary_output, index=False)

    print(f"Input windows: {input_path}")
    print(f"Evaluated segments: {len(result_df)}")
    print(f"Results output: {results_output}")
    print(f"Predictions output: {predictions_output}")
    print(f"Summary output: {summary_output}")
    print()
    print("Per-segment metrics:")
    printable = result_df.copy()
    for col in ["accuracy", "precision_walking", "recall_walking", "f1_walking"]:
        if col in printable:
            printable[col] = printable[col].round(4)
    print(printable.to_string(index=False))
    print()
    print("Summary:")
    print(summary_df.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
