#!/usr/bin/env python3
"""Build visual-review tables for ground-truth offset candidates."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Compara predicciones out-of-fold con offset 0s y un offset candidato "
            "para priorizar tramos de revision visual."
        )
    )
    p.add_argument("--baseline-predictions", required=True)
    p.add_argument("--offset-predictions", required=True)
    p.add_argument("--threshold", type=float, default=0.80)
    p.add_argument("--row-output", required=True)
    p.add_argument("--run-output", required=True)
    p.add_argument("--top-n", type=int, default=30)
    return p


def load_predictions(path: str, suffix: str, threshold: float) -> pd.DataFrame:
    """Load predictions and normalize columns."""
    df = pd.read_csv(path)
    df["time_center"] = pd.to_datetime(df["time_center"], utc=True, format="mixed")
    df[f"mov_type_{suffix}"] = df["mov_type"].astype(str)
    df[f"target_{suffix}"] = df["target"].astype(int)
    df[f"prob_{suffix}"] = df["prob_walking"].astype(float)
    df[f"pred_{suffix}"] = (df[f"prob_{suffix}"] >= threshold).astype(int)
    return df[
        [
            "reference",
            "time_center",
            f"mov_type_{suffix}",
            f"target_{suffix}",
            f"prob_{suffix}",
            f"pred_{suffix}",
        ]
    ].copy()


def add_review_flags(merged: pd.DataFrame) -> pd.DataFrame:
    """Add review-oriented status flags."""
    output = merged.copy()
    output["baseline_status"] = "not_evaluated"
    output.loc[
        output["target_baseline"].eq(0) & output["pred_baseline"].eq(0),
        "baseline_status",
    ] = "TN"
    output.loc[
        output["target_baseline"].eq(0) & output["pred_baseline"].eq(1),
        "baseline_status",
    ] = "FP"
    output.loc[
        output["target_baseline"].eq(1) & output["pred_baseline"].eq(1),
        "baseline_status",
    ] = "TP"
    output.loc[
        output["target_baseline"].eq(1) & output["pred_baseline"].eq(0),
        "baseline_status",
    ] = "FN"

    output["offset_status"] = "not_evaluated"
    output.loc[
        output["target_offset"].eq(0) & output["pred_offset"].eq(0),
        "offset_status",
    ] = "TN"
    output.loc[
        output["target_offset"].eq(0) & output["pred_offset"].eq(1),
        "offset_status",
    ] = "FP"
    output.loc[
        output["target_offset"].eq(1) & output["pred_offset"].eq(1),
        "offset_status",
    ] = "TP"
    output.loc[
        output["target_offset"].eq(1) & output["pred_offset"].eq(0),
        "offset_status",
    ] = "FN"

    output["review_reason"] = "other"
    output.loc[
        output["baseline_status"].eq("FP") & output["offset_status"].eq("TN"),
        "review_reason",
    ] = "fp_corrected_by_offset"
    output.loc[
        output["baseline_status"].eq("FP") & output["offset_status"].eq("FP"),
        "review_reason",
    ] = "persistent_false_positive"
    output.loc[
        output["mov_type_baseline"].ne(output["mov_type_offset"]),
        "review_reason",
    ] = "label_changed_by_offset"
    output.loc[
        output["mov_type_offset"].isna(),
        "review_reason",
    ] = "dropped_by_offset_labeling"
    output["prob_delta_offset_minus_baseline"] = (
        output["prob_offset"] - output["prob_baseline"]
    )
    return output


def build_runs(rows: pd.DataFrame) -> pd.DataFrame:
    """Summarize consecutive review rows by reference and reason."""
    review = rows[
        rows["review_reason"].isin(
            [
                "fp_corrected_by_offset",
                "persistent_false_positive",
                "label_changed_by_offset",
                "dropped_by_offset_labeling",
            ]
        )
    ].copy()
    if review.empty:
        return pd.DataFrame()

    review = review.sort_values(["reference", "time_center"]).reset_index(drop=True)
    gap = review.groupby(["reference", "review_reason"])["time_center"].diff()
    new_run = (
        review["reference"].ne(review["reference"].shift())
        | review["review_reason"].ne(review["review_reason"].shift())
        | gap.gt(pd.Timedelta(seconds=2)).fillna(False)
    )
    review["run_id"] = new_run.cumsum().astype(int)
    runs = (
        review.groupby(["run_id", "reference", "review_reason"], sort=False)
        .agg(
            run_start=("time_center", "min"),
            run_end=("time_center", "max"),
            windows=("time_center", "size"),
            baseline_mean_prob=("prob_baseline", "mean"),
            baseline_max_prob=("prob_baseline", "max"),
            offset_mean_prob=("prob_offset", "mean"),
            offset_max_prob=("prob_offset", "max"),
            mean_prob_delta=("prob_delta_offset_minus_baseline", "mean"),
            baseline_labels=("mov_type_baseline", lambda s: ",".join(sorted(set(s.dropna())))),
            offset_labels=("mov_type_offset", lambda s: ",".join(sorted(set(s.dropna())))),
        )
        .reset_index()
        .drop(columns=["run_id"])
        .sort_values(["windows", "baseline_max_prob"], ascending=False)
    )
    return runs


def main() -> None:
    """Build row-level and run-level visual review tables."""
    args = build_parser().parse_args()
    baseline = load_predictions(args.baseline_predictions, "baseline", args.threshold)
    offset = load_predictions(args.offset_predictions, "offset", args.threshold)
    merged = baseline.merge(
        offset,
        on=["reference", "time_center"],
        how="outer",
        validate="one_to_one",
    ).sort_values(["reference", "time_center"])
    review_rows = add_review_flags(merged)
    review_runs = build_runs(review_rows)

    row_output = Path(args.row_output)
    run_output = Path(args.run_output)
    row_output.parent.mkdir(parents=True, exist_ok=True)
    run_output.parent.mkdir(parents=True, exist_ok=True)
    review_rows.to_csv(row_output, index=False)
    review_runs.to_csv(run_output, index=False)

    print(f"Baseline predictions: {args.baseline_predictions}")
    print(f"Offset predictions: {args.offset_predictions}")
    print(f"Threshold: {args.threshold}")
    print(f"Row output: {row_output}")
    print(f"Run output: {run_output}")
    print()
    print("Review reasons:")
    print(review_rows["review_reason"].value_counts(dropna=False).to_string())
    if not review_runs.empty:
        print()
        print(review_runs.head(args.top_n).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
