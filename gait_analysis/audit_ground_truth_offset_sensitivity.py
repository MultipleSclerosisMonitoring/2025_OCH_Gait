#!/usr/bin/env python3
"""Audit model sensitivity to small ground-truth time offsets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import LeaveOneGroupOut

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gait_analysis.run_ml_model_comparison_grouped import (
    add_groups,
    apply_temporal_embargo,
    get_feature_columns,
)


TARGET_MAP = {"not_walking": 0, "walking": 1}


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Reetiqueta ventanas desplazando el ground truth unos segundos y "
            "evalua sensibilidad con validacion temporal agrupada."
        )
    )
    p.add_argument("-i", "--input", required=True, help="Parquet de features.")
    p.add_argument(
        "-g",
        "--ground-truth",
        nargs="+",
        required=True,
        help="Uno o varios Excel con Reference/datefrom/dateuntil/mov_type.",
    )
    p.add_argument(
        "--offsets",
        type=float,
        nargs="+",
        default=[-10, -5, -2, 0, 2, 5, 10],
        help="Offsets en segundos aplicados a datefrom/dateuntil.",
    )
    p.add_argument("--group-by", choices=["reference", "temporal_block"], default="temporal_block")
    p.add_argument("--gap-seconds", type=float, default=5.0)
    p.add_argument("--embargo-seconds", type=float, default=15.0)
    p.add_argument("--n-estimators", type=int, default=150)
    p.add_argument("--max-depth", type=int, default=5)
    p.add_argument("--min-samples-leaf", type=int, default=10)
    p.add_argument(
        "--summary-output",
        default="results/ground_truth_offset_sensitivity_summary.csv",
    )
    return p


def load_ground_truth(paths: list[str]) -> pd.DataFrame:
    """Load and merge ground-truth Excel files."""
    frames = []
    for path in paths:
        gt = pd.read_excel(path)
        required = {"Reference", "datefrom", "dateuntil", "mov_type"}
        missing = required - set(gt.columns)
        if missing:
            raise ValueError(f"{path} no contiene columnas: {sorted(missing)}")
        gt = gt[["Reference", "datefrom", "dateuntil", "mov_type"]].copy()
        gt["source"] = str(path)
        frames.append(gt)
    combined = pd.concat(frames, ignore_index=True)
    combined["Reference"] = combined["Reference"].astype(str)
    combined["datefrom"] = pd.to_datetime(
        combined["datefrom"],
        utc=True,
        format="mixed",
    )
    combined["dateuntil"] = pd.to_datetime(
        combined["dateuntil"],
        utc=True,
        format="mixed",
    )
    combined["mov_type"] = combined["mov_type"].astype(str).str.strip()
    combined = combined[combined["mov_type"].isin(TARGET_MAP)].copy()
    return combined.sort_values(["Reference", "datefrom", "dateuntil"]).reset_index(
        drop=True
    )


def relabel_with_offset(
    df: pd.DataFrame,
    gt: pd.DataFrame,
    offset_seconds: float,
) -> pd.DataFrame:
    """Return a copy of df relabeled with shifted ground-truth intervals."""
    shifted = gt.copy()
    offset = pd.Timedelta(seconds=offset_seconds)
    shifted["datefrom"] = shifted["datefrom"] + offset
    shifted["dateuntil"] = shifted["dateuntil"] + offset

    output = df.copy()
    output["time_center"] = pd.to_datetime(
        output["time_center"],
        utc=True,
        format="mixed",
    )
    labels = pd.Series("NO_LABEL", index=output.index, dtype=object)
    for reference, ref_gt in shifted.groupby("Reference", sort=False):
        ref_mask = output["reference"].astype(str).eq(str(reference))
        if not ref_mask.any():
            continue
        ref_times = output.loc[ref_mask, "time_center"]
        ref_labels = pd.Series("NO_LABEL", index=ref_times.index, dtype=object)
        for _, row in ref_gt.iterrows():
            interval_mask = ref_times.ge(row["datefrom"]) & ref_times.lt(row["dateuntil"])
            ref_labels.loc[interval_mask] = row["mov_type"]
        labels.loc[ref_labels.index] = ref_labels

    output["mov_type"] = labels
    output = output[output["mov_type"].isin(TARGET_MAP)].copy()
    output["target"] = output["mov_type"].map(TARGET_MAP).astype("int8")
    return output


def build_rf(args: argparse.Namespace) -> RandomForestClassifier:
    """Build the RF used for the offset audit."""
    return RandomForestClassifier(
        n_estimators=args.n_estimators,
        random_state=42,
        class_weight="balanced",
        max_depth=args.max_depth,
        min_samples_leaf=args.min_samples_leaf,
        max_features="sqrt",
    )


def confusion_counts(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, int]:
    """Return binary confusion counts."""
    return {
        "tp": int(((y_true == 1) & (y_pred == 1)).sum()),
        "tn": int(((y_true == 0) & (y_pred == 0)).sum()),
        "fp": int(((y_true == 0) & (y_pred == 1)).sum()),
        "fn": int(((y_true == 1) & (y_pred == 0)).sum()),
    }


def evaluate_offset(df: pd.DataFrame, args: argparse.Namespace) -> dict[str, float | int]:
    """Evaluate one relabeled dataset with grouped CV."""
    grouped = add_groups(df, args.group_by, args.gap_seconds)
    feature_cols = get_feature_columns(grouped)
    X = grouped[feature_cols].copy()
    y = grouped["target"].astype(int)
    groups = grouped["group"].astype(str)
    metadata = grouped[["reference", "time_center"]].copy()
    predictions = pd.Series(index=grouped.index, dtype=int)
    logo = LeaveOneGroupOut()
    model = build_rf(args)

    folds = 0
    for train_idx_raw, test_idx_raw in logo.split(X, y, groups):
        train_idx = pd.Index(train_idx_raw)
        test_idx = pd.Index(test_idx_raw)
        train_idx = apply_temporal_embargo(
            train_idx=train_idx,
            test_metadata=metadata.iloc[test_idx],
            train_metadata=metadata.iloc[train_idx],
            embargo_seconds=args.embargo_seconds
            if args.group_by == "temporal_block"
            else 0.0,
        )
        if len(train_idx) == 0:
            continue
        estimator = clone(model)
        estimator.fit(X.iloc[train_idx], y.iloc[train_idx])
        predictions.iloc[test_idx] = estimator.predict(X.iloc[test_idx]).astype(int)
        folds += 1

    valid = predictions.notna()
    y_true = y.loc[valid].to_numpy()
    y_pred = predictions.loc[valid].astype(int).to_numpy()
    counts = confusion_counts(y_true, y_pred)
    not_walking = counts["tn"] + counts["fp"]
    walking = counts["tp"] + counts["fn"]
    return {
        "rows": int(len(grouped)),
        "evaluated_rows": int(valid.sum()),
        "folds": int(folds),
        "groups": int(groups.nunique()),
        "not_walking": int((y == 0).sum()),
        "walking": int((y == 1).sum()),
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
        "false_positive_rate": counts["fp"] / not_walking if not_walking else 0.0,
        "false_negative_rate": counts["fn"] / walking if walking else 0.0,
        **counts,
    }


def main() -> None:
    """Run the offset sensitivity audit."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_path = Path(args.summary_output)

    base_df = pd.read_parquet(input_path)
    gt = load_ground_truth(args.ground_truth)
    rows = []
    for offset_seconds in args.offsets:
        relabeled = relabel_with_offset(base_df, gt, offset_seconds)
        metrics = evaluate_offset(relabeled, args)
        rows.append({"offset_seconds": float(offset_seconds), **metrics})

    summary = pd.DataFrame(rows).sort_values("offset_seconds")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=False)

    print(f"Input parquet: {input_path}")
    print(f"Ground truth files: {len(args.ground_truth)}")
    print(f"Output: {output_path}")
    print()
    printable = summary.copy()
    for col in printable.select_dtypes(include="number").columns:
        printable[col] = printable[col].round(4)
    print(printable.to_string(index=False))


if __name__ == "__main__":
    main()
