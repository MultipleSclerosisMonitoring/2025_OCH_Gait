#!/usr/bin/env python3
"""Run a random-forest baseline with stratified cross-validation."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import make_scorer, f1_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_validate


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Ejecuta Random Forest con validación cruzada estratificada."
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="Ruta al parquet wide limpio de entrada",
    )
    return p


def main() -> None:
    """Read dataset and evaluate a random-forest baseline with cross-validation."""
    args = build_parser().parse_args()
    input_path = Path(args.input)

    df = pd.read_parquet(input_path)

    id_cols = ["reference", "time_center", "mov_type"]
    feature_cols = [c for c in df.columns if c not in id_cols]

    X = df[feature_cols].copy()
    y = df["mov_type"].map({"not_walking": 0, "walking": 1})

    model = RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        class_weight="balanced",
    )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scoring = {
        "accuracy": "accuracy",
        "f1_walking": make_scorer(f1_score, pos_label=1),
        "recall_walking": make_scorer(recall_score, pos_label=1),
    }

    scores = cross_validate(
        model,
        X,
        y,
        cv=cv,
        scoring=scoring,
        return_train_score=False,
    )

    print(f"Input parquet: {input_path}")
    print(f"Rows: {len(df)}")
    print(f"Feature columns: {len(feature_cols)}")
    print()
    for metric in ["test_accuracy", "test_f1_walking", "test_recall_walking"]:
        values = scores[metric]
        values = [float(v) for v in values]
        print(metric)
        print("values:", [round(v, 4) for v in values])
        print("mean:", round(sum(values) / len(values), 4))
        print()
        

if __name__ == "__main__":
    main()
    