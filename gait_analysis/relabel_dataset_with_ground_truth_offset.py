#!/usr/bin/env python3
"""Relabel an ML dataset with a fixed ground-truth time offset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gait_analysis.audit_ground_truth_offset_sensitivity import (
    load_ground_truth,
    relabel_with_offset,
)


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Reetiqueta un parquet aplicando un offset fijo al ground truth."
    )
    p.add_argument("-i", "--input", required=True, help="Parquet de entrada.")
    p.add_argument("-o", "--output", required=True, help="Parquet reetiquetado.")
    p.add_argument(
        "-g",
        "--ground-truth",
        nargs="+",
        required=True,
        help="Excel(s) con Reference/datefrom/dateuntil/mov_type.",
    )
    p.add_argument("--offset-seconds", type=float, required=True)
    p.add_argument(
        "--summary-output",
        default=None,
        help="CSV opcional con resumen de cambios de etiqueta.",
    )
    return p


def build_change_summary(original: pd.DataFrame, relabeled: pd.DataFrame) -> pd.DataFrame:
    """Summarize label changes after relabeling."""
    before = original[["reference", "time_center", "mov_type", "target"]].copy()
    before["time_center"] = pd.to_datetime(before["time_center"], utc=True, format="mixed")
    before = before.rename(columns={"mov_type": "mov_type_before", "target": "target_before"})
    after = relabeled[["reference", "time_center", "mov_type", "target"]].copy()
    after["time_center"] = pd.to_datetime(after["time_center"], utc=True, format="mixed")
    after = after.rename(columns={"mov_type": "mov_type_after", "target": "target_after"})
    merged = before.merge(after, on=["reference", "time_center"], how="outer")
    merged["change"] = (
        merged["mov_type_before"].fillna("NO_LABEL")
        + "_to_"
        + merged["mov_type_after"].fillna("NO_LABEL")
    )
    return (
        merged.groupby("change", dropna=False)
        .size()
        .reset_index(name="rows")
        .sort_values("rows", ascending=False)
    )


def main() -> None:
    """Relabel and save a dataset."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    df = pd.read_parquet(input_path)
    gt = load_ground_truth(args.ground_truth)
    relabeled = relabel_with_offset(df, gt, args.offset_seconds)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    relabeled.to_parquet(output_path, index=False)

    if args.summary_output:
        summary = build_change_summary(df, relabeled)
        summary_path = Path(args.summary_output)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary.to_csv(summary_path, index=False)

    print(f"Input parquet: {input_path}")
    print(f"Output parquet: {output_path}")
    print(f"Offset seconds: {args.offset_seconds}")
    print(f"Rows input: {len(df)}")
    print(f"Rows output: {len(relabeled)}")
    print()
    print("Target counts:")
    print(relabeled["mov_type"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
