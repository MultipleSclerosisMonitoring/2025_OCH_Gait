#!/usr/bin/env python3
"""Train and persist a final XGBoost gait-classification model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from xgboost import XGBClassifier


TARGET_MAP = {"not_walking": 0, "walking": 1}
INVERSE_TARGET_MAP = {v: k for k, v in TARGET_MAP.items()}
ID_COLS = ["reference", "time_center", "mov_type", "target"]


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Entrena y guarda el modelo final de XGBoost para marcha."
    )
    p.add_argument(
        "-i",
        "--input",
        default="salidas_test/new_influx_confirmed_spectrograms/new_influx_confirmed_binary.parquet",
        help="Parquet binario preparado con target y columnas espectrales",
    )
    p.add_argument(
        "-m",
        "--model-output",
        default="models/final_xgboost_model_new_influx_confirmed.joblib",
        help="Ruta donde guardar el modelo entrenado",
    )
    p.add_argument(
        "-s",
        "--summary-output",
        default="results/final_xgboost_model_new_influx_confirmed_summary.json",
        help="Ruta donde guardar el resumen del entrenamiento",
    )
    return p


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return numeric feature columns excluding identifiers and text metadata."""
    excluded = set(ID_COLS)
    numeric_cols = df.select_dtypes(include=["number", "bool"]).columns
    return [col for col in numeric_cols if col not in excluded]


def main() -> None:
    """Train and persist the final XGBoost model."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    model_output = Path(args.model_output)
    summary_output = Path(args.summary_output)

    df = pd.read_parquet(input_path)
    missing_cols = [c for c in ID_COLS if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Faltan columnas esperadas: {missing_cols}")

    expected_target = df["mov_type"].map(TARGET_MAP)
    target_mismatches = df[df["target"] != expected_target]
    if not target_mismatches.empty:
        raise ValueError(
            "La columna target no coincide con mov_type para "
            f"{len(target_mismatches)} filas."
        )

    feature_cols = get_feature_columns(df)
    if not feature_cols:
        raise ValueError("No se han encontrado columnas de atributos.")

    X = df[feature_cols].copy()
    y = df["target"].astype(int)
    neg = int((y == 0).sum())
    pos = int((y == 1).sum())
    scale_pos_weight = neg / max(pos, 1)

    model = XGBClassifier(
        n_estimators=300,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=2.0,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        n_jobs=1,
    )
    model.fit(X, y)

    artifact = {
        "model": model,
        "feature_names": feature_cols,
        "target_map": TARGET_MAP,
        "inverse_target_map": INVERSE_TARGET_MAP,
        "summary": {
            "input": str(input_path),
            "model_output": str(model_output),
            "rows": int(len(df)),
            "feature_columns": int(len(feature_cols)),
            "class_counts": {
                "not_walking": int((y == 0).sum()),
                "walking": int((y == 1).sum()),
            },
            "model": {
                "type": "XGBClassifier",
                "n_estimators": model.n_estimators,
                "max_depth": model.max_depth,
                "learning_rate": model.learning_rate,
                "subsample": model.subsample,
                "colsample_bytree": model.colsample_bytree,
                "reg_lambda": model.reg_lambda,
                "scale_pos_weight": scale_pos_weight,
                "random_state": model.random_state,
            },
            "feature_names": feature_cols,
        },
    }

    model_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_output)
    summary_output.write_text(
        json.dumps(artifact["summary"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Input parquet: {input_path}")
    print(f"Model output: {model_output}")
    print(f"Summary output: {summary_output}")
    print(f"Rows: {len(df)}")
    print(f"Feature columns: {len(feature_cols)}")


if __name__ == "__main__":
    main()
