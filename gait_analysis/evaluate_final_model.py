#!/usr/bin/env python3
"""Evaluate the final gait model with temporal-block cross-validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    recall_score,
)
from sklearn.model_selection import LeaveOneGroupOut

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gait_analysis.run_baseline_grouped_cv import (
    add_temporal_groups,
    get_feature_columns,
    get_target,
)
from gait_analysis.train_final_model import INVERSE_TARGET_MAP, build_model


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Evalua el modelo final con Leave-One-Group-Out temporal."
    )
    p.add_argument(
        "-i",
        "--input",
        default="salidas_test/auto_extracts/main_binary_window_features.parquet",
        help="Parquet binario preparado con target y columnas espectrales",
    )
    p.add_argument(
        "-m",
        "--model",
        default="models/final_random_forest_model.joblib",
        help="Modelo final entrenado, usado para importancias de variables",
    )
    p.add_argument(
        "--gap-seconds",
        type=float,
        default=5.0,
        help="Salto minimo entre time_center consecutivos para abrir un bloque nuevo",
    )
    p.add_argument(
        "--fold-output",
        default="results/final_model_grouped_cv_results.csv",
        help="CSV con metricas por bloque",
    )
    p.add_argument(
        "--prediction-output",
        default="results/final_model_grouped_cv_predictions.csv",
        help="CSV con predicciones out-of-fold por ventana",
    )
    p.add_argument(
        "--importance-output",
        default="results/final_model_feature_importances.csv",
        help="CSV con importancia de variables del modelo final",
    )
    p.add_argument(
        "--summary-output",
        default="results/final_model_evaluation.json",
        help="JSON con resumen agregado de evaluacion",
    )
    return p


def score_fold(y_true: pd.Series, y_pred: pd.Series) -> dict[str, float]:
    """Compute the main metrics for one fold."""
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "f1_walking": f1_score(y_true, y_pred, pos_label=1, zero_division=0),
        "recall_walking": recall_score(y_true, y_pred, pos_label=1, zero_division=0),
    }


def build_weighted_means(fold_results: pd.DataFrame) -> dict[str, float]:
    """Compute row-weighted metric means across folds."""
    weights = fold_results["test_rows"]
    return {
        metric: round(
            float((fold_results[metric] * weights).sum() / weights.sum()),
            4,
        )
        for metric in ["accuracy", "f1_walking", "recall_walking"]
    }


def main() -> None:
    """Evaluate final model design and write reportable artifacts."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    model_path = Path(args.model)
    fold_output = Path(args.fold_output)
    prediction_output = Path(args.prediction_output)
    importance_output = Path(args.importance_output)
    summary_output = Path(args.summary_output)

    df = pd.read_parquet(input_path)
    df = add_temporal_groups(df, args.gap_seconds)
    y = get_target(df)
    feature_cols = get_feature_columns(df)
    X = df[feature_cols].copy()
    groups = df["group"]

    fold_rows = []
    prediction_frames = []
    logo = LeaveOneGroupOut()
    base_model = build_model()

    for fold_idx, (train_idx, test_idx) in enumerate(logo.split(X, y, groups), start=1):
        estimator = clone(base_model)
        estimator.fit(X.iloc[train_idx], y.iloc[train_idx])

        y_test = y.iloc[test_idx]
        y_pred = pd.Series(
            estimator.predict(X.iloc[test_idx]),
            index=y_test.index,
            name="prediction",
        )
        y_score = estimator.predict_proba(X.iloc[test_idx])[:, 1]
        metrics = score_fold(y_test, y_pred)
        group_name = str(groups.iloc[test_idx].iloc[0])

        fold_rows.append(
            {
                "fold": fold_idx,
                "group": group_name,
                "test_rows": int(len(test_idx)),
                "test_not_walking": int((y_test == 0).sum()),
                "test_walking": int((y_test == 1).sum()),
                **metrics,
            }
        )

        predictions = df.iloc[test_idx][["reference", "time_center", "mov_type", "target", "group"]].copy()
        predictions["fold"] = fold_idx
        predictions["prediction"] = y_pred.astype(int)
        predictions["prediction_label"] = predictions["prediction"].map(INVERSE_TARGET_MAP)
        predictions["walking_probability"] = y_score
        prediction_frames.append(predictions)

    fold_results = pd.DataFrame(fold_rows)
    predictions = pd.concat(prediction_frames, ignore_index=True)

    y_true_all = predictions["target"].astype(int)
    y_pred_all = predictions["prediction"].astype(int)
    labels = [0, 1]
    cm = confusion_matrix(y_true_all, y_pred_all, labels=labels)
    report = classification_report(
        y_true_all,
        y_pred_all,
        labels=labels,
        target_names=[INVERSE_TARGET_MAP[i] for i in labels],
        output_dict=True,
        zero_division=0,
    )

    artifact = joblib.load(model_path)
    final_model = artifact["model"]
    importances = pd.DataFrame(
        {
            "feature": artifact["feature_names"],
            "importance": final_model.feature_importances_,
        }
    ).sort_values("importance", ascending=False)

    summary = {
        "input": str(input_path),
        "model": str(model_path),
        "rows": int(len(df)),
        "feature_columns": int(len(feature_cols)),
        "groups": int(groups.nunique()),
        "references": sorted(df["reference"].dropna().astype(str).unique().tolist()),
        "class_counts": {
            INVERSE_TARGET_MAP[int(k)]: int(v)
            for k, v in y.value_counts().sort_index().items()
        },
        "evaluation": "temporal_block_leave_one_group_out",
        "weighted_mean_metrics": build_weighted_means(fold_results),
        "out_of_fold_metrics": {
            "accuracy": round(float(accuracy_score(y_true_all, y_pred_all)), 4),
            "f1_walking": round(float(f1_score(y_true_all, y_pred_all, pos_label=1, zero_division=0)), 4),
            "recall_walking": round(float(recall_score(y_true_all, y_pred_all, pos_label=1, zero_division=0)), 4),
        },
        "confusion_matrix": {
            "labels": [INVERSE_TARGET_MAP[i] for i in labels],
            "matrix": cm.astype(int).tolist(),
        },
        "classification_report": report,
        "top_features": importances.head(15).to_dict(orient="records"),
    }

    for path in [fold_output, prediction_output, importance_output, summary_output]:
        path.parent.mkdir(parents=True, exist_ok=True)

    fold_results.to_csv(fold_output, index=False)
    predictions.to_csv(prediction_output, index=False)
    importances.to_csv(importance_output, index=False)
    summary_output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Input parquet: {input_path}")
    print(f"Model: {model_path}")
    print(f"Rows: {summary['rows']}")
    print(f"Groups: {summary['groups']}")
    print()
    print("Out-of-fold metrics:")
    for metric, value in summary["out_of_fold_metrics"].items():
        print(f"{metric}: {value:.4f}")
    print()
    print("Row-weighted fold metrics:")
    for metric, value in summary["weighted_mean_metrics"].items():
        print(f"{metric}: {value:.4f}")
    print()
    print("Confusion matrix labels:", summary["confusion_matrix"]["labels"])
    print(summary["confusion_matrix"]["matrix"])
    print()
    print(f"Fold output: {fold_output}")
    print(f"Prediction output: {prediction_output}")
    print(f"Importance output: {importance_output}")
    print(f"Summary output: {summary_output}")


if __name__ == "__main__":
    main()
