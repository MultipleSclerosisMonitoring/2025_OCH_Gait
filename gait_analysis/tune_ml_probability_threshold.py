#!/usr/bin/env python3
"""Tune probability thresholds over saved out-of-fold ML predictions."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Evalua umbrales de probabilidad sobre predicciones out-of-fold "
            "sin aplicar reglas temporales rigidas."
        )
    )
    p.add_argument("-i", "--input", required=True, help="CSV de predicciones.")
    p.add_argument("-o", "--output", required=True, help="CSV con el barrido.")
    p.add_argument(
        "--model",
        default=None,
        help="Filtra un modelo concreto si el CSV contiene varios.",
    )
    p.add_argument("--min-threshold", type=float, default=0.05)
    p.add_argument("--max-threshold", type=float, default=0.95)
    p.add_argument("--step", type=float, default=0.01)
    return p


def confusion_counts(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, int]:
    """Return binary confusion matrix counts."""
    return {
        "tp": int(((y_true == 1) & (y_pred == 1)).sum()),
        "tn": int(((y_true == 0) & (y_pred == 0)).sum()),
        "fp": int(((y_true == 0) & (y_pred == 1)).sum()),
        "fn": int(((y_true == 1) & (y_pred == 0)).sum()),
    }


def score_thresholds(df: pd.DataFrame, thresholds: np.ndarray) -> pd.DataFrame:
    """Score all thresholds."""
    y_true = df["target"].astype(int).to_numpy()
    prob = df["prob_walking"].astype(float).to_numpy()
    rows = []
    for threshold in thresholds:
        y_pred = (prob >= threshold).astype(int)
        counts = confusion_counts(y_true, y_pred)
        not_walking = counts["tn"] + counts["fp"]
        walking = counts["tp"] + counts["fn"]
        rows.append(
            {
                "threshold": float(threshold),
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
                "f1_macro": f1_score(
                    y_true,
                    y_pred,
                    average="macro",
                    zero_division=0,
                ),
                "false_positive_rate": counts["fp"] / not_walking
                if not_walking
                else 0.0,
                "false_negative_rate": counts["fn"] / walking if walking else 0.0,
                **counts,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    """Tune thresholds and save scores."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    df = pd.read_csv(input_path)
    if args.model:
        df = df[df["model"].eq(args.model)].copy()
    if df.empty:
        raise ValueError("No hay predicciones para evaluar.")
    if df["prob_walking"].isna().any():
        raise ValueError("El CSV contiene probabilidades vacias.")

    thresholds = np.round(
        np.arange(args.min_threshold, args.max_threshold + args.step / 2, args.step),
        6,
    )
    scores = score_thresholds(df, thresholds)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scores.to_csv(output_path, index=False)

    best_f1 = scores.sort_values(
        ["f1_macro", "false_positive_rate"],
        ascending=[False, True],
    ).iloc[0]
    conservative = scores[scores["recall_walking"].ge(0.60)].sort_values(
        ["false_positive_rate", "f1_macro"],
        ascending=[True, False],
    )
    print(f"Input predictions: {input_path}")
    print(f"Rows: {len(df)}")
    print(f"Output: {output_path}")
    print()
    print("Best macro F1 threshold:")
    print(best_f1.round(4).to_string())
    if not conservative.empty:
        print()
        print("Lowest false-positive rate with recall_walking >= 0.60:")
        print(conservative.iloc[0].round(4).to_string())


if __name__ == "__main__":
    main()
