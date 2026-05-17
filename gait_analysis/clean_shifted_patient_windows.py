#!/usr/bin/env python3
"""Clean shifted new-patient windows before extraction."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Limpia ventanas desplazadas: normaliza tiempos y elimina solapes."
    )
    p.add_argument(
        "-i",
        "--input",
        default="experiment_configs/new_patient_shifted_windows.csv",
        help="CSV con ventanas candidatas desplazadas.",
    )
    p.add_argument(
        "-o",
        "--output",
        default="experiment_configs/new_patient_shifted_windows_clean.csv",
        help="CSV limpio sin solapes conflictivos.",
    )
    p.add_argument(
        "--dropped-output",
        default="experiment_configs/new_patient_shifted_windows_dropped.csv",
        help="CSV con ventanas descartadas y motivo.",
    )
    p.add_argument(
        "--long-negative-threshold-s",
        type=float,
        default=600.0,
        help=(
            "Umbral para marcar negativos largos como evaluacion, no como "
            "dataset principal, para evitar desequilibrio."
        ),
    )
    return p


def normalize_time_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize timestamp columns and recompute duration."""
    normalized = df.copy()
    time_cols = ["from_time", "until_time", "original_datefrom", "original_dateuntil"]
    for col in time_cols:
        normalized[col] = pd.to_datetime(normalized[col], format="mixed")

    normalized = normalized.sort_values(["Reference", "from_time", "until_time"])
    normalized["duration_s"] = (
        normalized["until_time"] - normalized["from_time"]
    ).dt.total_seconds()
    if (normalized["duration_s"] <= 0).any():
        bad = normalized[normalized["duration_s"] <= 0]
        raise ValueError(f"Hay ventanas con duracion no positiva:\n{bad}")
    return normalized.reset_index(drop=True)


def find_conflicting_overlaps(df: pd.DataFrame) -> set[int]:
    """Return indexes of rows to drop because of conflicting overlaps."""
    drop_indexes: set[int] = set()
    for _, group in df.groupby("Reference", sort=False):
        ordered = group.sort_values(["from_time", "until_time"]).copy()
        rows = list(ordered.iterrows())
        for pos, (idx, row) in enumerate(rows):
            if idx in drop_indexes:
                continue
            for other_idx, other in rows[pos + 1 :]:
                if other_idx in drop_indexes:
                    continue
                if other["from_time"] >= row["until_time"]:
                    break
                if row["expected_content"] == other["expected_content"]:
                    continue

                row_duration = float(row["duration_s"])
                other_duration = float(other["duration_s"])
                if row_duration <= other_duration:
                    drop_indexes.add(idx)
                    break
                drop_indexes.add(other_idx)
    return drop_indexes


def prepare_clean_outputs(
    df: pd.DataFrame,
    long_negative_threshold_s: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clean windows and return kept/dropped DataFrames."""
    normalized = normalize_time_columns(df)
    drop_indexes = find_conflicting_overlaps(normalized)

    dropped = normalized.loc[sorted(drop_indexes)].copy()
    if not dropped.empty:
        dropped["drop_reason"] = "conflicting_label_overlap_shorter_interval"

    kept = normalized.drop(index=drop_indexes).copy().reset_index(drop=True)
    kept["use_for_main_dataset"] = True
    kept["use_for_sequence_eval"] = True
    kept["window_role"] = "new_patient_shifted_train_eval"

    long_negative = (
        kept["expected_content"].eq("not_walking")
        & kept["duration_s"].gt(long_negative_threshold_s)
    )
    kept.loc[long_negative, "use_for_main_dataset"] = False
    kept.loc[long_negative, "window_role"] = "new_patient_long_negative_eval"

    # Keep timestamp formatting stable for extraction scripts.
    for col in ["from_time", "until_time", "original_datefrom", "original_dateuntil"]:
        kept[col] = kept[col].dt.strftime("%Y-%m-%d %H:%M:%S")
        if not dropped.empty:
            dropped[col] = dropped[col].dt.strftime("%Y-%m-%d %H:%M:%S")

    kept = kept.sort_values(["Reference", "from_time", "until_time"]).reset_index(
        drop=True
    )
    return kept, dropped


def main() -> None:
    """Clean shifted windows and save outputs."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    dropped_output_path = Path(args.dropped_output)

    df = pd.read_csv(input_path)
    kept, dropped = prepare_clean_outputs(
        df,
        long_negative_threshold_s=args.long_negative_threshold_s,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    dropped_output_path.parent.mkdir(parents=True, exist_ok=True)
    kept.to_csv(output_path, index=False)
    dropped.to_csv(dropped_output_path, index=False)

    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Dropped output: {dropped_output_path}")
    print(f"Input rows: {len(df)}")
    print(f"Kept rows: {len(kept)}")
    print(f"Dropped rows: {len(dropped)}")
    print()
    print("Kept by reference/label:")
    print(
        kept.groupby(["Reference", "expected_content"])
        .size()
        .rename("rows")
        .reset_index()
        .to_string(index=False)
    )
    print()
    print("Roles:")
    print(kept["window_role"].value_counts().to_string())
    if not dropped.empty:
        print()
        print("Dropped:")
        print(
            dropped[
                [
                    "Reference",
                    "from_time",
                    "until_time",
                    "expected_content",
                    "duration_s",
                    "drop_reason",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
