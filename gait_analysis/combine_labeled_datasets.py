#!/usr/bin/env python3
"""Combine multiple labeled spectrogram parquet datasets into one file."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Combina varios parquets etiquetados en un único dataset."
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        nargs="+",
        help="Una o varias rutas de parquet etiquetado",
    )
    p.add_argument(
        "-o",
        "--output",
        required=True,
        help="Ruta al parquet combinado de salida",
    )
    return p


def main() -> None:
    """Read labeled parquet files, concatenate them, and save one combined parquet."""
    args = build_parser().parse_args()

    input_paths = [Path(p) for p in args.input]
    output_path = Path(args.output)

    frames = [pd.read_parquet(path) for path in input_paths]
    df = pd.concat(frames, ignore_index=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)

    print("Inputs:")
    for path in input_paths:
        print(f" - {path}")
    print()
    print(f"Output parquet: {output_path}")
    print(f"Rows: {len(df)}")
    print()
    print("mov_type counts:")
    print(df["mov_type"].value_counts(dropna=False).to_string())
    print()
    print("References:")
    print(sorted(df["reference"].dropna().astype(str).unique().tolist()))


if __name__ == "__main__":
    main()
    