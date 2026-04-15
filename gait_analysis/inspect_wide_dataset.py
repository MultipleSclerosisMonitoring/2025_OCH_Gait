#!/usr/bin/env python3
"""Inspect a wide spectrogram dataset prepared for ML."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Inspecciona un parquet wide preparado para ML."
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="Ruta al parquet wide de entrada",
    )
    return p


def main() -> None:
    """Read a wide parquet and print basic ML-oriented diagnostics."""
    args = build_parser().parse_args()
    input_path = Path(args.input)

    df = pd.read_parquet(input_path)

    id_cols = ["reference", "time_center", "mov_type"]
    feature_cols = [c for c in df.columns if c not in id_cols]

    print(f"Input parquet: {input_path}")
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")
    print(f"Feature columns: {len(feature_cols)}")
    print()

    print("mov_type counts:")
    print(df["mov_type"].value_counts(dropna=False).to_string())
    print()

    print("References:")
    print(sorted(df["reference"].dropna().astype(str).unique().tolist()))
    print()

    print("Missing values by column:")
    missing = df.isna().sum()
    missing = missing[missing > 0]
    if len(missing) == 0:
        print("No missing values.")
    else:
        print(missing.to_string())
    print()

    print("First 10 feature columns:")
    print(feature_cols[:10])


if __name__ == "__main__":
    main()
    