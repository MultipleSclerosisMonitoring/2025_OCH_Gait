#!/usr/bin/env python3
"""Compare RF, XGBoost and CatBoost with 3-fold cross-validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from catboost import CatBoostClassifier
from sklearn.base import clone
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold
from xgboost import XGBClassifier

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gait_analysis.train_final_model import build_model


ID_COLS = {"reference", "time_center", "mov_type", "target"}


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Compara Random Forest, XGBoost y CatBoost con validacion cruzada "
            "estratificada de 3 folds."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        default="salidas_test/auto_extracts/main_binary_window_features.parquet",
        help="Parquet binario preparado con target y columnas espectrales",
    )
    p.add_argument(
        "--fold-output",
        default="results/ml_model_comparison_cv3_folds.csv",
        help="CSV con metricas por fold",
    )
    p.add_argument(
        "--summary-output",
        default="results/ml_model_comparison_cv3_summary.csv",
        help="CSV con media y desviacion estandar por modelo",
    )
    return p


def build_models(y: pd.Series) -> dict[str, object]:
    """Build the three models requested for comparison."""
    neg = int((y == 0).sum())
    pos = int((y == 1).sum())
    scale_pos_weight = neg / pos

    return {
        "random_forest": build_model(),
        "xgboost": XGBClassifier(
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
        ),
        "catboost": CatBoostClassifier(
            iterations=300,
            depth=4,
            learning_rate=0.05,
            l2_leaf_reg=3.0,
            loss_function="Logloss",
            eval_metric="F1",
            auto_class_weights="Balanced",
            random_seed=42,
            verbose=False,
            allow_writing_files=False,
        ),
    }


def score_predictions(y_true: pd.Series, y_pred: pd.Series) -> dict[str, float]:
    """Return classification metrics for one fold."""
    return {
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
        "precision_macro": precision_score(
            y_true,
            y_pred,
            average="macro",
            zero_division=0,
        ),
        "recall_macro": recall_score(
            y_true,
            y_pred,
            average="macro",
            zero_division=0,
        ),
        "f1_macro": f1_score(
            y_true,
            y_pred,
            average="macro",
            zero_division=0,
        ),
    }


def build_summary(fold_results: pd.DataFrame) -> pd.DataFrame:
    """Build mean and standard-deviation table by model."""
    metric_cols = [
        "accuracy",
        "precision_walking",
        "recall_walking",
        "f1_walking",
        "precision_macro",
        "recall_macro",
        "f1_macro",
    ]
    rows = []
    for model_name, model_results in fold_results.groupby("model", sort=False):
        row: dict[str, float | str] = {"model": model_name}
        for metric in metric_cols:
            row[f"{metric}_mean"] = model_results[metric].mean()
            row[f"{metric}_sd"] = model_results[metric].std(ddof=1)
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    """Run 3-fold model comparison and save fold-level and summary results."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    fold_output = Path(args.fold_output)
    summary_output = Path(args.summary_output)

    df = pd.read_parquet(input_path)
    if "target" not in df.columns:
        raise ValueError("El dataset debe contener la columna target.")

    feature_cols = [c for c in df.columns if c not in ID_COLS]
    X = df[feature_cols].copy()
    y = df["target"].astype(int)

    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    rows = []

    for model_name, model in build_models(y).items():
        for fold_idx, (train_idx, test_idx) in enumerate(cv.split(X, y), start=1):
            estimator = clone(model)
            estimator.fit(X.iloc[train_idx], y.iloc[train_idx])
            y_test = y.iloc[test_idx]
            y_pred = pd.Series(
                estimator.predict(X.iloc[test_idx]),
                index=y_test.index,
            ).astype(int)

            rows.append(
                {
                    "model": model_name,
                    "fold": fold_idx,
                    "train_rows": int(len(train_idx)),
                    "test_rows": int(len(test_idx)),
                    "test_not_walking": int((y_test == 0).sum()),
                    "test_walking": int((y_test == 1).sum()),
                    **score_predictions(y_test, y_pred),
                }
            )

    fold_results = pd.DataFrame(rows)
    summary = build_summary(fold_results)

    fold_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    fold_results.to_csv(fold_output, index=False)
    summary.to_csv(summary_output, index=False)

    print(f"Input parquet: {input_path}")
    print(f"Rows: {len(df)}")
    print(f"Feature columns: {len(feature_cols)}")
    print(f"Fold output: {fold_output}")
    print(f"Summary output: {summary_output}")
    print()
    print("Summary mean +/- sd:")
    printable = summary.copy()
    for col in printable.columns:
        if col != "model":
            printable[col] = printable[col].round(4)
    print(printable.to_string(index=False))


if __name__ == "__main__":
    main()
