#!/usr/bin/env python3
"""Run a very simple logistic-regression baseline on a wide gait dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Ejecuta un baseline simple con Logistic Regression."
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="Ruta al parquet wide limpio de entrada",
    )
    return p


def main() -> None:
    """Read dataset, split train/test, fit baseline, and print metrics."""
    args = build_parser().parse_args()
    input_path = Path(args.input)

    df = pd.read_parquet(input_path)

    id_cols = ["reference", "time_center", "mov_type"]
    feature_cols = [c for c in df.columns if c not in id_cols]

    X = df[feature_cols].copy()
    y = df["mov_type"].map({"not_walking": 0, "walking": 1})

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced"),
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    print(f"Input parquet: {input_path}")
    print(f"X_train shape: {X_train.shape}")
    print(f"X_test shape: {X_test.shape}")
    print()
    print("Confusion matrix:")
    print(confusion_matrix(y_test, y_pred))
    print()
    print("Classification report:")
    print(classification_report(y_test, y_pred, digits=4))


if __name__ == "__main__":
    main()
    