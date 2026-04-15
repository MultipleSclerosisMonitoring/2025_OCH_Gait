#!/usr/bin/env python3
"""Summarize a labeled spectrogram parquet dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Resume un parquet de espectrogramas etiquetado."
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="Ruta al parquet etiquetado de entrada",
    )
    return p


def main() -> None:
    """Read a labeled spectrogram parquet and print a compact summary."""
    args = build_parser().parse_args()
    input_path = Path(args.input)

    df = pd.read_parquet(input_path)

    print(f"Input parquet: {input_path}")
    print(f"Rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    print()
    print("mov_type counts:")
    print(df["mov_type"].value_counts(dropna=False).to_string())
    print()
    print("Unique centers by mov_type:")
    print(
        df[["time_center", "mov_type"]]
        .drop_duplicates()
        .groupby("mov_type")
        .size()
        .to_string()
    )
    print()
    print("References:")
    print(sorted(df["reference"].dropna().astype(str).unique().tolist()))
    print()
    print("Feet:")
    print(sorted(df["foot"].dropna().astype(str).unique().tolist()))
    print()
    print("Signals:")
    print(sorted(df["signal"].dropna().astype(str).unique().tolist()))


if __name__ == "__main__":
    main()
    