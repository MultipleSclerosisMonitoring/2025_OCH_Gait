#!/usr/bin/env python3
"""Remove windows near label transitions from an ML dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Filtra ventanas cercanas a cambios de etiqueta para reducir ruido "
            "de ground truth en transiciones marcha/no marcha."
        )
    )
    p.add_argument("-i", "--input", required=True, help="Parquet de entrada.")
    p.add_argument("-o", "--output", required=True, help="Parquet filtrado.")
    p.add_argument(
        "--margin-seconds",
        type=float,
        default=5.0,
        help="Margen minimo requerido hasta una transicion de etiqueta.",
    )
    p.add_argument(
        "--gap-seconds",
        type=float,
        default=5.0,
        help="Salto temporal que separa bloques independientes.",
    )
    p.add_argument(
        "--removed-output",
        default=None,
        help="CSV opcional con ventanas eliminadas.",
    )
    p.add_argument(
        "--summary-output",
        default=None,
        help="CSV opcional con resumen por referencia.",
    )
    return p


def add_transition_distances(df: pd.DataFrame, gap_seconds: float) -> pd.DataFrame:
    """Add distance in seconds to nearest label transition."""
    output = df.copy()
    output["time_center"] = pd.to_datetime(
        output["time_center"],
        utc=True,
        format="mixed",
    )
    output = output.sort_values(["reference", "time_center"]).reset_index(drop=True)
    gap = output.groupby("reference")["time_center"].diff()
    ref_change = output["reference"].ne(output["reference"].shift())
    gap_change = gap.gt(pd.Timedelta(seconds=gap_seconds)).fillna(False)
    output["block_id"] = (ref_change | gap_change).cumsum().astype(int)

    prev_time = output.groupby(["reference", "block_id"])["time_center"].shift()
    next_time = output.groupby(["reference", "block_id"])["time_center"].shift(-1)
    prev_label = output.groupby(["reference", "block_id"])["mov_type"].shift()
    next_label = output.groupby(["reference", "block_id"])["mov_type"].shift(-1)

    prev_transition_distance = (
        output["time_center"] - prev_time
    ).dt.total_seconds().where(prev_label.ne(output["mov_type"]))
    next_transition_distance = (
        next_time - output["time_center"]
    ).dt.total_seconds().where(next_label.ne(output["mov_type"]))

    distances = pd.concat(
        [prev_transition_distance, next_transition_distance],
        axis=1,
    )
    output["nearest_transition_distance_s"] = distances.min(axis=1)
    output["near_transition"] = output["nearest_transition_distance_s"].notna()
    return output


def build_summary(df: pd.DataFrame, keep_mask: pd.Series) -> pd.DataFrame:
    """Build removal summary by reference and label."""
    summary = (
        df.assign(kept=keep_mask.to_numpy())
        .groupby(["reference", "mov_type"], dropna=False)
        .agg(
            rows=("target", "size"),
            kept=("kept", "sum"),
            removed=("kept", lambda s: int((~s).sum())),
        )
        .reset_index()
    )
    summary["removed_fraction"] = summary["removed"] / summary["rows"]
    return summary


def main() -> None:
    """Filter transition-adjacent windows and save outputs."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    df = pd.read_parquet(input_path)
    required = {"reference", "time_center", "mov_type", "target"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {sorted(missing)}")

    annotated = add_transition_distances(df, gap_seconds=args.gap_seconds)
    keep_mask = (
        annotated["nearest_transition_distance_s"].isna()
        | annotated["nearest_transition_distance_s"].ge(args.margin_seconds)
    )
    filtered = annotated[keep_mask].drop(
        columns=["block_id", "nearest_transition_distance_s", "near_transition"]
    )
    removed = annotated[~keep_mask].copy()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_parquet(output_path, index=False)

    if args.removed_output:
        removed_path = Path(args.removed_output)
        removed_path.parent.mkdir(parents=True, exist_ok=True)
        removed[
            [
                "reference",
                "time_center",
                "mov_type",
                "target",
                "block_id",
                "nearest_transition_distance_s",
            ]
        ].to_csv(removed_path, index=False)
    if args.summary_output:
        summary_path = Path(args.summary_output)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        build_summary(annotated, keep_mask).to_csv(summary_path, index=False)

    print(f"Input parquet: {input_path}")
    print(f"Rows input: {len(annotated)}")
    print(f"Rows kept: {len(filtered)}")
    print(f"Rows removed: {len(removed)}")
    print(f"Margin seconds: {args.margin_seconds}")
    print(f"Output parquet: {output_path}")
    print()
    print("Removed by label:")
    print(removed["mov_type"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
