#!/usr/bin/env python3
"""Compare RF, XGBoost and CatBoost with 3-fold cross-validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd
from catboost import CatBoostClassifier
from sklearn.base import clone
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from xgboost import XGBClassifier

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gait_analysis.train_final_model import build_model


ID_COLS = {"reference", "time_center", "mov_type", "target", "foot"}


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Compara Random Forest, XGBoost y CatBoost con CV de 3 folds."
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
    p.add_argument(
        "--source-output",
        default=None,
        help="CSV opcional con metricas por fold y columna de origen.",
    )
    p.add_argument(
        "--metadata-cols",
        nargs="*",
        default=[],
        help="Columnas de metadatos a excluir de features.",
    )
    p.add_argument(
        "--cv",
        choices=["stratified", "grouped"],
        default="stratified",
        help="Tipo de validacion cruzada: por fila estratificada o agrupada por referencia.",
    )
    p.add_argument(
        "--group-col",
        default="reference",
        help="Columna de grupo si --cv grouped.",
    )
    return p


def build_models(y: pd.Series) -> dict[str, object]:
    """Build the three models requested for comparison."""
    neg = int((y == 0).sum())
    pos = int((y == 1).sum())
    scale_pos_weight = neg / pos

    return {
        "random_forest": build_model(
            class_weight="balanced",
            max_depth=5,
            min_samples_leaf=10,
        ),
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


def iter_splits(
    *,
    cv_type: str,
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
) -> Iterable[tuple[int, object, object]]:
    """Yield fold index and train/test indices."""
    if cv_type == "grouped":
        splitter = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=42)
        split_iter = splitter.split(X, y, groups=groups)
    else:
        splitter = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
        split_iter = splitter.split(X, y)
    for fold_idx, (train_idx, test_idx) in enumerate(split_iter, start=1):
        yield fold_idx, train_idx, test_idx


def score_by_source(
    *,
    df_test: pd.DataFrame,
    y_test: pd.Series,
    y_pred: pd.Series,
    model_name: str,
    fold_idx: int,
    source_col: str,
) -> list[dict[str, object]]:
    """Return metric rows split by dataset source."""
    rows: list[dict[str, object]] = []
    if source_col not in df_test.columns:
        return rows
    for source_value, source_df in df_test.groupby(source_col, sort=False):
        source_index = source_df.index
        source_y = y_test.loc[source_index]
        source_pred = y_pred.loc[source_index]
        metrics = score_predictions(source_y, source_pred)
        rows.append(
            {
                "model": model_name,
                "fold": fold_idx,
                source_col: source_value,
                "test_rows": int(len(source_y)),
                "test_not_walking": int((source_y == 0).sum()),
                "test_walking": int((source_y == 1).sum()),
                **metrics,
            }
        )
    return rows


def main() -> None:
    """Run 3-fold model comparison and save fold-level and summary results."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    fold_output = Path(args.fold_output)
    summary_output = Path(args.summary_output)
    source_output = Path(args.source_output) if args.source_output else None

    df = pd.read_parquet(input_path)
    if "target" not in df.columns:
        raise ValueError("El dataset debe contener la columna target.")
    if args.cv == "grouped" and args.group_col not in df.columns:
        raise ValueError(f"No existe group-col={args.group_col!r} en el dataset.")

    metadata_cols = set(args.metadata_cols)
    feature_cols = [c for c in df.columns if c not in ID_COLS and c not in metadata_cols]
    X = df[feature_cols].copy()
    y = df["target"].astype(int)
    if args.group_col in df.columns:
        groups = df[args.group_col].astype(str)
    else:
        groups = pd.Series(["all"] * len(df), index=df.index)

    rows = []
    source_rows = []

    for model_name, model in build_models(y).items():
        for fold_idx, train_idx, test_idx in iter_splits(
            cv_type=args.cv,
            X=X,
            y=y,
            groups=groups,
        ):
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
                    "cv": args.cv,
                    "train_rows": int(len(train_idx)),
                    "test_rows": int(len(test_idx)),
                    "train_groups": int(groups.iloc[train_idx].nunique()),
                    "test_groups": int(groups.iloc[test_idx].nunique()),
                    "test_not_walking": int((y_test == 0).sum()),
                    "test_walking": int((y_test == 1).sum()),
                    **score_predictions(y_test, y_pred),
                }
            )
            if source_output is not None and args.metadata_cols:
                source_rows.extend(
                    score_by_source(
                        df_test=df.iloc[test_idx],
                        y_test=y_test,
                        y_pred=y_pred,
                        model_name=model_name,
                        fold_idx=fold_idx,
                        source_col=args.metadata_cols[0],
                    )
                )

    fold_results = pd.DataFrame(rows)
    summary = build_summary(fold_results)

    fold_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    fold_results.to_csv(fold_output, index=False)
    summary.to_csv(summary_output, index=False)
    if source_output is not None:
        source_output.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(source_rows).to_csv(source_output, index=False)

    print(f"Input parquet: {input_path}")
    print(f"Rows: {len(df)}")
    print(f"Feature columns: {len(feature_cols)}")
    print(f"CV: {args.cv}")
    if args.cv == "grouped":
        print(f"Groups ({args.group_col}): {groups.nunique()}")
    print(f"Fold output: {fold_output}")
    print(f"Summary output: {summary_output}")
    if source_output is not None:
        print(f"Source output: {source_output}")
    print()
    print("Summary mean +/- sd:")
    printable = summary.copy()
    for col in printable.columns:
        if col != "model":
            printable[col] = printable[col].round(4)
    print(printable.to_string(index=False))


if __name__ == "__main__":
    main()
