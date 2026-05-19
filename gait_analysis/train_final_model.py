#!/usr/bin/env python3
"""Train and persist the final binary gait-classification model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, recall_score


TARGET_MAP = {"not_walking": 0, "walking": 1}
INVERSE_TARGET_MAP = {v: k for k, v in TARGET_MAP.items()}
ID_COLS = ["reference", "time_center", "mov_type", "target"]


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Entrena y guarda el modelo final de clasificacion de marcha."
    )
    p.add_argument(
        "-i",
        "--input",
        default="salidas_test/auto_extracts/main_binary_window_features.parquet",
        help="Parquet binario preparado con target y columnas espectrales",
    )
    p.add_argument(
        "-m",
        "--model-output",
        default="models/final_random_forest_model.joblib",
        help="Ruta donde guardar el modelo entrenado",
    )
    p.add_argument(
        "-s",
        "--summary-output",
        default="results/final_model_summary.json",
        help="Ruta donde guardar el resumen del entrenamiento",
    )
    p.add_argument(
        "--class-weight",
        choices=["balanced", "none"],
        default="balanced",
        help="Ponderacion de clases para el Random Forest.",
    )
    p.add_argument(
        "--max-depth",
        type=int,
        default=5,
        help="Profundidad maxima de cada arbol.",
    )
    p.add_argument(
        "--min-samples-leaf",
        type=int,
        default=10,
        help="Minimo de muestras por hoja.",
    )
    p.add_argument(
        "--not-walking-weight",
        type=float,
        default=None,
        help=(
            "Peso explicito para la clase not_walking. Si se indica, reemplaza "
            "--class-weight."
        ),
    )
    p.add_argument(
        "--walking-weight",
        type=float,
        default=1.0,
        help="Peso explicito para walking cuando se usa --not-walking-weight.",
    )
    return p


def build_model(
    class_weight: str,
    max_depth: int,
    min_samples_leaf: int,
    explicit_class_weight: dict[int, float] | None = None,
) -> RandomForestClassifier:
    """Return the selected final model with fixed parameters."""
    resolved_class_weight = (
        explicit_class_weight
        if explicit_class_weight is not None
        else None
        if class_weight == "none"
        else class_weight
    )
    return RandomForestClassifier(
        n_estimators=300,
        random_state=42,
        class_weight=resolved_class_weight,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        max_features="sqrt",
    )


def main() -> None:
    """Train the final model on all prepared rows and save model plus metadata."""
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

    feature_cols = [c for c in df.columns if c not in ID_COLS]
    if not feature_cols:
        raise ValueError("No se han encontrado columnas de atributos.")

    X = df[feature_cols].copy()
    y = df["target"].astype(int)

    model = build_model(
        class_weight=args.class_weight,
        max_depth=args.max_depth,
        min_samples_leaf=args.min_samples_leaf,
        explicit_class_weight={
            0: args.not_walking_weight,
            1: args.walking_weight,
        }
        if args.not_walking_weight is not None
        else None,
    )
    model.fit(X, y)

    y_pred = model.predict(X)
    summary = {
        "input": str(input_path),
        "model_output": str(model_output),
        "rows": int(len(df)),
        "feature_columns": int(len(feature_cols)),
        "references": sorted(df["reference"].dropna().astype(str).unique().tolist()),
        "class_counts": {
            INVERSE_TARGET_MAP[int(k)]: int(v)
            for k, v in y.value_counts().sort_index().items()
        },
        "model": {
            "type": "RandomForestClassifier",
            "n_estimators": model.n_estimators,
            "random_state": model.random_state,
            "class_weight": model.class_weight,
            "max_depth": model.max_depth,
            "min_samples_leaf": model.min_samples_leaf,
            "max_features": model.max_features,
        },
        "training_metrics": {
            "accuracy": round(float(accuracy_score(y, y_pred)), 4),
            "f1_walking": round(float(f1_score(y, y_pred, pos_label=1)), 4),
            "recall_walking": round(float(recall_score(y, y_pred, pos_label=1)), 4),
        },
        "target_map": TARGET_MAP,
        "feature_names": feature_cols,
        "sklearn_version": sklearn.__version__,
    }

    artifact = {
        "model": model,
        "feature_names": feature_cols,
        "target_map": TARGET_MAP,
        "inverse_target_map": INVERSE_TARGET_MAP,
        "summary": summary,
    }

    model_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_output)
    summary_output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Input parquet: {input_path}")
    print(f"Model output: {model_output}")
    print(f"Summary output: {summary_output}")
    print(f"Rows: {summary['rows']}")
    print(f"Feature columns: {summary['feature_columns']}")
    print()
    print("Class counts:")
    for label, count in summary["class_counts"].items():
        print(f"{label}: {count}")
    print()
    print("Training metrics:")
    for metric, value in summary["training_metrics"].items():
        print(f"{metric}: {value:.4f}")


if __name__ == "__main__":
    main()
