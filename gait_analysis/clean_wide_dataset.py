#!/usr/bin/env python3
"""Clean a wide spectrogram dataset by removing rows with missing values."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Limpia un parquet wide eliminando filas con valores faltantes."
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="Ruta al parquet wide de entrada",
    )
    p.add_argument(
        "-o",
        "--output",
        required=True,
        help="Ruta al parquet limpio de salida",
    )
    return p


def main() -> None:
    """Read a wide parquet, drop rows with missing values, and save the clean result."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    df = pd.read_parquet(input_path)
    n_before = len(df)
    df_clean = df.dropna().reset_index(drop=True)
    n_after = len(df_clean)
    dropped = n_before - n_after

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_parquet(output_path, index=False)

    print(f"Input parquet: {input_path}")
    print(f"Output parquet: {output_path}")
    print(f"Rows before: {n_before}")
    print(f"Rows after: {n_after}")
    print(f"Dropped rows: {dropped}")
    print()
    print("mov_type counts:")
    print(df_clean['mov_type'].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
