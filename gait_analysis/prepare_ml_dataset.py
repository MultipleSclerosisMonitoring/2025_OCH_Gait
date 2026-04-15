#!/usr/bin/env python3
"""Prepare a wide spectrogram dataset for a first ML baseline."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Prepara un parquet wide limpio para un baseline de ML."
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="Ruta al parquet wide limpio de entrada",
    )
    return p


def main() -> None:
    """Read a clean wide parquet and report the ML-ready matrix structure."""
    args = build_parser().parse_args()
    input_path = Path(args.input)

    df = pd.read_parquet(input_path)

    id_cols = ["reference", "time_center", "mov_type"]
    feature_cols = [c for c in df.columns if c not in id_cols]

    X = df[feature_cols].copy()
    y = df["mov_type"].map({"not_walking": 0, "walking": 1})

    print(f"Input parquet: {input_path}")
    print(f"Rows: {len(df)}")
    print(f"Feature columns: {len(feature_cols)}")
    print()
    print("Target counts:")
    print(y.value_counts(dropna=False).sort_index().to_string())
    print()
    print(f"X shape: {X.shape}")
    print(f"y shape: {y.shape}")
    print()
    print("First 10 feature columns:")
    print(feature_cols[:10])
    print()
    print("Target mapping:")
    print("{'not_walking': 0, 'walking': 1}")


if __name__ == "__main__":
    main()
    