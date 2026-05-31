#!/usr/bin/env python3
"""Compare RF, XGBoost and CatBoost with 3-fold cross-validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
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
        "--prediction-output",
        default=None,
        help="CSV opcional con predicciones out-of-fold.",
    )
    p.add_argument(
        "--fold-plan-output",
        default=None,
        help="CSV opcional con diagnostico de los folds asignados.",
    )
    p.add_argument(
        "--fold-plan-input",
        default=None,
        help="CSV opcional con asignacion fija reference/fold para balanced_grouped.",
    )
    p.add_argument(
        "--metadata-cols",
        nargs="*",
        default=[],
        help="Columnas de metadatos a excluir de features.",
    )
    p.add_argument(
        "--cv",
        choices=["stratified", "grouped", "balanced_grouped"],
        default="stratified",
        help=(
            "Tipo de validacion cruzada: por fila estratificada, agrupada por "
            "referencia, o agrupada con balance por referencia/etiqueta/origen."
        ),
    )
    p.add_argument(
        "--group-col",
        default="reference",
        help="Columna de grupo si --cv grouped o balanced_grouped.",
    )
    p.add_argument(
        "--source-col",
        default="dataset_source",
        help="Columna de origen usada para balancear folds y desglosar metricas.",
    )
    p.add_argument(
        "--balanced-restarts",
        type=int,
        default=500,
        help="Intentos aleatorios para construir folds balanceados por grupo.",
    )
    p.add_argument(
        "--models",
        nargs="*",
        choices=["random_forest", "xgboost", "catboost"],
        default=None,
        help="Modelos a ejecutar. Por defecto ejecuta los tres.",
    )
    p.add_argument(
        "--sample-weighting",
        choices=["none", "patient", "patient_source"],
        default="none",
        help="Ponderacion opcional para que pacientes/origenes largos no dominen.",
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


def build_sample_weights(
    df: pd.DataFrame,
    *,
    mode: str,
    group_col: str,
    source_col: str,
) -> pd.Series:
    """Return row weights that equalize patients and optionally patient-source cells."""
    if mode == "none":
        return pd.Series(1.0, index=df.index)
    if group_col not in df.columns:
        raise ValueError(f"No existe group-col={group_col!r} para ponderar.")

    if mode == "patient":
        keys = [group_col]
    elif mode == "patient_source":
        if source_col not in df.columns:
            raise ValueError(f"No existe source-col={source_col!r} para ponderar.")
        keys = [group_col, source_col]
    else:
        raise ValueError(f"Modo de ponderacion no soportado: {mode}")

    counts = df.groupby(keys, sort=False)[keys[0]].transform("size").astype(float)
    cells = df[keys].drop_duplicates().shape[0]
    return (len(df) / (cells * counts)).astype(float)


def predict_walking_probability(estimator: object, X: pd.DataFrame) -> np.ndarray:
    """Return walking probabilities when the estimator exposes them."""
    if hasattr(estimator, "predict_proba"):
        probabilities = estimator.predict_proba(X)
        return np.asarray(probabilities)[:, 1].astype(float)
    return np.full(len(X), np.nan)


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


def build_group_fold_plan(
    df: pd.DataFrame,
    *,
    group_col: str,
    source_col: str | None,
    n_splits: int,
    restarts: int,
    random_state: int,
) -> pd.DataFrame:
    """Assign groups to folds while balancing rows, labels and data source."""
    stat_rows = []
    for group_value, group_df in df.groupby(group_col, sort=False):
        row: dict[str, object] = {
            group_col: group_value,
            "rows": int(len(group_df)),
            "target_0": int((group_df["target"] == 0).sum()),
            "target_1": int((group_df["target"] == 1).sum()),
        }
        if source_col and source_col in group_df.columns:
            for source_value, source_df in group_df.groupby(source_col, sort=False):
                safe_source = str(source_value).replace(" ", "_")
                row[f"source__{safe_source}"] = int(len(source_df))
                row[f"source_target__{safe_source}__0"] = int(
                    (source_df["target"] == 0).sum()
                )
                row[f"source_target__{safe_source}__1"] = int(
                    (source_df["target"] == 1).sum()
                )
        stat_rows.append(row)

    group_stats = pd.DataFrame(stat_rows).fillna(0)
    balance_cols = [
        col
        for col in group_stats.columns
        if col != group_col and col.startswith(("rows", "target_", "source__"))
    ]
    source_target_cols = [
        col for col in group_stats.columns if col.startswith("source_target__")
    ]
    balance_cols.extend(source_target_cols)
    desired = group_stats[balance_cols].sum() / n_splits
    weights = pd.Series(1.0, index=balance_cols)
    weights["target_0"] = 2.0
    weights["target_1"] = 2.0
    for col in source_target_cols:
        weights[col] = 2.0

    values = group_stats[balance_cols].to_numpy(dtype=float)
    desired_values = desired.to_numpy(dtype=float)
    denominator = np.where(desired_values > 0, desired_values, 1.0)
    weight_values = weights.to_numpy(dtype=float)

    def objective(fold_sums: np.ndarray) -> float:
        normalized = ((fold_sums - desired_values) / denominator) ** 2
        return float((normalized * weight_values).sum())

    rng = np.random.default_rng(random_state)
    sorted_indices = group_stats.sort_values(
        ["rows", "target_1", "target_0"],
        ascending=False,
    ).index.to_numpy()
    best_assignment: np.ndarray | None = None
    best_score = float("inf")
    attempts = max(1, restarts)

    for attempt in range(attempts):
        if attempt == 0:
            ordered_indices = sorted_indices
        else:
            ordered_indices = rng.permutation(len(group_stats))
        fold_sums = np.zeros((n_splits, len(balance_cols)), dtype=float)
        fold_group_counts = np.zeros(n_splits, dtype=float)
        assignment = np.zeros(len(group_stats), dtype=int)
        for group_idx in ordered_indices:
            candidate_scores = []
            for fold_idx in range(n_splits):
                candidate_sums = fold_sums.copy()
                candidate_sums[fold_idx] += values[group_idx]
                candidate_group_counts = fold_group_counts.copy()
                candidate_group_counts[fold_idx] += 1
                group_penalty = (
                    (candidate_group_counts - len(group_stats) / n_splits) ** 2
                ).sum()
                candidate_scores.append(
                    (objective(candidate_sums) + 0.05 * float(group_penalty), fold_idx)
                )
            _, selected_fold = min(candidate_scores)
            assignment[group_idx] = selected_fold + 1
            fold_sums[selected_fold] += values[group_idx]
            fold_group_counts[selected_fold] += 1

        score = objective(fold_sums)
        if score < best_score:
            best_score = score
            best_assignment = assignment.copy()

    if best_assignment is None:
        raise RuntimeError("No se pudo construir un plan de folds balanceados.")

    plan = group_stats.copy()
    plan["fold"] = best_assignment.astype(int)
    return plan.sort_values(["fold", group_col]).reset_index(drop=True)


def summarize_fold_plan(plan: pd.DataFrame, *, group_col: str) -> pd.DataFrame:
    """Summarize group-fold assignment for audit."""
    value_cols = [c for c in plan.columns if c not in {group_col, "fold"}]
    numeric_cols = [c for c in value_cols if pd.api.types.is_numeric_dtype(plan[c])]
    summary = plan.groupby("fold", as_index=False)[numeric_cols].sum()
    summary["groups"] = plan.groupby("fold").size().to_numpy()
    return summary


def iter_splits(
    *,
    cv_type: str,
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    fold_plan: pd.DataFrame | None = None,
    group_col: str = "reference",
) -> Iterable[tuple[int, object, object]]:
    """Yield fold index and train/test indices."""
    if cv_type == "balanced_grouped":
        if fold_plan is None:
            raise ValueError("balanced_grouped requiere fold_plan.")
        group_to_fold = fold_plan.set_index(group_col)["fold"]
        fold_ids = sorted(group_to_fold.unique())
        for fold_idx in fold_ids:
            test_mask = groups.map(group_to_fold).eq(fold_idx).to_numpy()
            test_idx = np.flatnonzero(test_mask)
            train_idx = np.flatnonzero(~test_mask)
            yield int(fold_idx), train_idx, test_idx
    elif cv_type == "grouped":
        splitter = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=42)
        split_iter = splitter.split(X, y, groups=groups)
        for fold_idx, (train_idx, test_idx) in enumerate(split_iter, start=1):
            yield fold_idx, train_idx, test_idx
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
    prediction_output = Path(args.prediction_output) if args.prediction_output else None
    fold_plan_output = Path(args.fold_plan_output) if args.fold_plan_output else None
    fold_plan_input = Path(args.fold_plan_input) if args.fold_plan_input else None

    df = pd.read_parquet(input_path)
    if "target" not in df.columns:
        raise ValueError("El dataset debe contener la columna target.")
    if args.cv in {"grouped", "balanced_grouped"} and args.group_col not in df.columns:
        raise ValueError(f"No existe group-col={args.group_col!r} en el dataset.")

    metadata_cols = set(args.metadata_cols)
    feature_cols = [c for c in df.columns if c not in ID_COLS and c not in metadata_cols]
    X = df[feature_cols].copy()
    y = df["target"].astype(int)
    if args.group_col in df.columns:
        groups = df[args.group_col].astype(str)
    else:
        groups = pd.Series(["all"] * len(df), index=df.index)
    sample_weights = build_sample_weights(
        df,
        mode=args.sample_weighting,
        group_col=args.group_col,
        source_col=args.source_col,
    )

    fold_plan = None
    if args.cv == "balanced_grouped":
        if fold_plan_input is not None:
            fold_plan = pd.read_csv(fold_plan_input)
            required_plan_cols = {args.group_col, "fold"}
            missing_plan_cols = required_plan_cols - set(fold_plan.columns)
            if missing_plan_cols:
                raise ValueError(
                    f"Faltan columnas en fold-plan-input: {sorted(missing_plan_cols)}"
                )
            missing_groups = sorted(set(groups) - set(fold_plan[args.group_col].astype(str)))
            if missing_groups:
                raise ValueError(
                    "El fold-plan-input no cubre todos los grupos: "
                    f"{missing_groups[:10]}"
                )
            fold_plan[args.group_col] = fold_plan[args.group_col].astype(str)
        else:
            fold_plan = build_group_fold_plan(
                df,
                group_col=args.group_col,
                source_col=args.source_col,
                n_splits=3,
                restarts=args.balanced_restarts,
                random_state=42,
            )
        if fold_plan_output is not None:
            fold_plan_output.parent.mkdir(parents=True, exist_ok=True)
            fold_plan.to_csv(fold_plan_output, index=False)
            summarize_fold_plan(fold_plan, group_col=args.group_col).to_csv(
                fold_plan_output.with_name(f"{fold_plan_output.stem}_summary.csv"),
                index=False,
            )

    rows = []
    source_rows = []
    prediction_rows = []

    models = build_models(y)
    if args.models:
        models = {name: models[name] for name in args.models}

    for model_name, model in models.items():
        for fold_idx, train_idx, test_idx in iter_splits(
            cv_type=args.cv,
            X=X,
            y=y,
            groups=groups,
            fold_plan=fold_plan,
            group_col=args.group_col,
        ):
            print(f"Training {model_name}, fold {fold_idx}...", flush=True)
            estimator = clone(model)
            fit_kwargs = {}
            if args.sample_weighting != "none":
                fit_kwargs["sample_weight"] = sample_weights.iloc[train_idx].to_numpy()
            estimator.fit(X.iloc[train_idx], y.iloc[train_idx], **fit_kwargs)
            y_test = y.iloc[test_idx]
            X_test = X.iloc[test_idx]
            y_pred = pd.Series(
                estimator.predict(X_test),
                index=y_test.index,
            ).astype(int)
            y_prob = pd.Series(
                predict_walking_probability(estimator, X_test),
                index=y_test.index,
            )

            rows.append(
                {
                    "model": model_name,
                    "fold": fold_idx,
                    "cv": args.cv,
                    "sample_weighting": args.sample_weighting,
                    "train_rows": int(len(train_idx)),
                    "test_rows": int(len(test_idx)),
                    "train_groups": int(groups.iloc[train_idx].nunique()),
                    "test_groups": int(groups.iloc[test_idx].nunique()),
                    "test_not_walking": int((y_test == 0).sum()),
                    "test_walking": int((y_test == 1).sum()),
                    **score_predictions(y_test, y_pred),
                }
            )
            source_metric_col = args.source_col if args.source_col in df.columns else None
            if source_output is not None and source_metric_col:
                source_rows.extend(
                    score_by_source(
                        df_test=df.iloc[test_idx],
                        y_test=y_test,
                        y_pred=y_pred,
                        model_name=model_name,
                        fold_idx=fold_idx,
                        source_col=source_metric_col,
                    )
                )
            if prediction_output is not None:
                keep_cols = [
                    col
                    for col in [
                        "reference",
                        "time_center",
                        "mov_type",
                        "target",
                        "foot",
                        args.source_col,
                    ]
                    if col in df.columns
                ]
                fold_predictions = df.iloc[test_idx][keep_cols].copy()
                fold_predictions["model"] = model_name
                fold_predictions["fold"] = fold_idx
                fold_predictions["cv"] = args.cv
                fold_predictions["sample_weighting"] = args.sample_weighting
                fold_predictions["train_groups"] = int(groups.iloc[train_idx].nunique())
                fold_predictions["test_groups"] = int(groups.iloc[test_idx].nunique())
                fold_predictions["prob_walking"] = y_prob.to_numpy()
                fold_predictions["prediction"] = y_pred.to_numpy()
                fold_predictions["prediction_label"] = np.where(
                    fold_predictions["prediction"].eq(1),
                    "walking",
                    "not_walking",
                )
                prediction_rows.append(fold_predictions)

    fold_results = pd.DataFrame(rows)
    summary = build_summary(fold_results)

    fold_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    fold_results.to_csv(fold_output, index=False)
    summary.to_csv(summary_output, index=False)
    if source_output is not None:
        source_output.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(source_rows).to_csv(source_output, index=False)
    if prediction_output is not None:
        prediction_output.parent.mkdir(parents=True, exist_ok=True)
        pd.concat(prediction_rows, ignore_index=True).to_csv(
            prediction_output,
            index=False,
        )

    print(f"Input parquet: {input_path}")
    print(f"Rows: {len(df)}")
    print(f"Feature columns: {len(feature_cols)}")
    print(f"CV: {args.cv}")
    print(f"Sample weighting: {args.sample_weighting}")
    if args.cv in {"grouped", "balanced_grouped"}:
        print(f"Groups ({args.group_col}): {groups.nunique()}")
    if fold_plan_input is not None:
        print(f"Fold plan input: {fold_plan_input}")
    if fold_plan_output is not None:
        print(f"Fold plan output: {fold_plan_output}")
    print(f"Fold output: {fold_output}")
    print(f"Summary output: {summary_output}")
    if source_output is not None:
        print(f"Source output: {source_output}")
    if prediction_output is not None:
        print(f"Prediction output: {prediction_output}")
    print()
    print("Summary mean +/- sd:")
    printable = summary.copy()
    for col in printable.columns:
        if col != "model":
            printable[col] = printable[col].round(4)
    print(printable.to_string(index=False))


if __name__ == "__main__":
    main()
