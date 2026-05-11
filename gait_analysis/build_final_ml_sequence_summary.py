#!/usr/bin/env python3
"""Build a final summary table for classical ML and sequence evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


OUTPUT_COLUMNS = [
    "method",
    "evaluation",
    "accuracy",
    "accuracy_sd",
    "precision_walking",
    "precision_walking_sd",
    "recall_walking",
    "recall_walking_sd",
    "f1_walking",
    "f1_walking_sd",
    "tn",
    "fp",
    "fn",
    "tp",
    "comment",
]


def rounded(value: float | int | None, digits: int = 4) -> float | None:
    """Round numeric values while preserving missing values."""
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def add_cv3_rows(rows: list[dict], path: Path) -> None:
    """Append RF, XGBoost and CatBoost CV=3 rows."""
    df = pd.read_csv(path)
    labels = {
        "random_forest": "Random Forest",
        "xgboost": "XGBoost",
        "catboost": "CatBoost",
    }
    comments = {
        "random_forest": "Baseline clasico con control de overfitting.",
        "xgboost": "Mejor F1 medio en CV=3.",
        "catboost": "Rendimiento similar a XGBoost en CV=3.",
    }
    for _, row in df.iterrows():
        model = str(row["model"])
        rows.append(
            {
                "method": labels.get(model, model),
                "evaluation": "Stratified CV=3",
                "accuracy": rounded(row["accuracy_mean"]),
                "accuracy_sd": rounded(row["accuracy_sd"]),
                "precision_walking": rounded(row["precision_walking_mean"]),
                "precision_walking_sd": rounded(row["precision_walking_sd"]),
                "recall_walking": rounded(row["recall_walking_mean"]),
                "recall_walking_sd": rounded(row["recall_walking_sd"]),
                "f1_walking": rounded(row["f1_walking_mean"]),
                "f1_walking_sd": rounded(row["f1_walking_sd"]),
                "comment": comments.get(model, ""),
            }
        )


def add_block_cv_row(rows: list[dict], path: Path) -> None:
    """Append temporal block validation row for the final Random Forest."""
    data = json.loads(path.read_text())
    report = data["classification_report"]["walking"]
    matrix = data["confusion_matrix"]["matrix"]
    rows.append(
        {
            "method": "Random Forest",
            "evaluation": "Temporal block CV",
            "accuracy": rounded(data["classification_report"]["accuracy"]),
            "precision_walking": rounded(report["precision"]),
            "recall_walking": rounded(report["recall"]),
            "f1_walking": rounded(report["f1-score"]),
            "tn": int(matrix[0][0]),
            "fp": int(matrix[0][1]),
            "fn": int(matrix[1][0]),
            "tp": int(matrix[1][1]),
            "comment": (
                "Validacion mas exigente; muestra caida de generalizacion "
                "por dependencia temporal entre ventanas."
            ),
        }
    )


def add_sequence_row(
    rows: list[dict],
    row: pd.Series,
    method: str,
    evaluation: str,
    comment: str,
) -> None:
    """Append one sequence-evaluation row."""
    rows.append(
        {
            "method": method,
            "evaluation": evaluation,
            "accuracy": rounded(row["accuracy"]),
            "precision_walking": rounded(row["precision_walking"]),
            "recall_walking": rounded(row["recall_walking"]),
            "f1_walking": rounded(row["f1_walking"]),
            "tn": int(row["tn"]),
            "fp": int(row["fp"]),
            "fn": int(row["fn"]),
            "tp": int(row["tp"]),
            "comment": comment,
        }
    )


def add_transformer_row(rows: list[dict], path: Path) -> None:
    """Append transformer grouped-evaluation row when available."""
    if not path.exists():
        return
    data = json.loads(path.read_text())
    metrics = data["out_of_fold_metrics"]
    matrix = data["confusion_matrix"]["matrix"]
    rows.append(
        {
            "method": "Transformer encoder",
            "evaluation": "Temporal sequence block CV",
            "accuracy": rounded(metrics["accuracy"]),
            "precision_walking": rounded(metrics["precision_walking"]),
            "recall_walking": rounded(metrics["recall_walking"]),
            "f1_walking": rounded(metrics["f1_walking"]),
            "tn": int(matrix[0][0]),
            "fp": int(matrix[0][1]),
            "fn": int(matrix[1][0]),
            "tp": int(matrix[1][1]),
            "comment": (
                "Modelo secuencial inicial con contexto de 9 ventanas; mejora "
                "frente a RF secuencial directo pero no supera al RF por bloques."
            ),
        }
    )


def build_summary() -> pd.DataFrame:
    """Build final summary dataframe from existing result artifacts."""
    rows: list[dict] = []
    add_cv3_rows(rows, Path("results/ml_model_comparison_cv3_summary.csv"))
    add_block_cv_row(rows, Path("results/final_model_evaluation.json"))

    sequence_summary = pd.read_csv("results/sequence_evaluation_summary.csv").iloc[0]
    add_sequence_row(
        rows,
        sequence_summary,
        method="Random Forest",
        evaluation="Sequence inference threshold=0.50",
        comment=(
            "Aplicacion directa por ventana movil; detecta marcha pero genera "
            "muchos falsos positivos."
        ),
    )

    threshold = pd.read_csv("results/sequence_threshold_sweep.csv")
    threshold_065 = threshold[threshold["threshold"].round(2) == 0.65].iloc[0]
    add_sequence_row(
        rows,
        threshold_065,
        method="Random Forest",
        evaluation="Sequence inference threshold=0.65",
        comment=(
            "Ajuste de umbral; reduce falsos positivos con perdida parcial "
            "de recall."
        ),
    )

    smoothing = pd.read_csv("results/sequence_temporal_smoothing_sweep.csv")
    best_smoothing = smoothing[
        (smoothing["threshold"].round(2) == 0.65)
        & (smoothing["min_run_windows"] == 2)
    ].iloc[0]
    add_sequence_row(
        rows,
        best_smoothing,
        method="Random Forest",
        evaluation="Sequence inference threshold=0.65 min_run=2",
        comment=(
            "Mejor postprocesado temporal actual; baja falsos positivos sin "
            "perder mas verdaderos positivos."
        ),
    )
    add_transformer_row(rows, Path("results/transformer_sequence_summary.json"))

    return pd.DataFrame(rows).reindex(columns=OUTPUT_COLUMNS)


def main() -> None:
    """Save the final ML and sequence summary table."""
    output = Path("results/final_ml_sequence_summary.csv")
    summary = build_summary()
    output.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output, index=False)
    print(f"Output: {output}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
