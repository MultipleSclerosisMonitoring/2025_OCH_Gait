#!/usr/bin/env python3
"""Build a wide spectrogram dataset with one row per time center."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Convierte un parquet etiquetado long a formato wide."
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="Ruta al parquet etiquetado long de entrada",
    )
    p.add_argument(
        "-o",
        "--output",
        required=True,
        help="Ruta al parquet wide de salida",
    )
    return p


def main() -> None:
    """Read a labeled long parquet, pivot power columns, and save a wide parquet."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    df = pd.read_parquet(input_path)

    p_cols = [c for c in df.columns if c.startswith("p_")]
    wide = (
        df.set_index(["reference", "time_center", "mov_type", "foot", "signal"])[p_cols]
        .unstack(["foot", "signal"])
    )
    wide.columns = [f"{foot}_{signal}_{col}" for col, foot, signal in wide.columns]
    wide = wide.reset_index()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wide.to_parquet(output_path, index=False)

    print(f"Input parquet: {input_path}")
    print(f"Output parquet: {output_path}")
    print(f"Rows: {len(wide)}")
    print(f"Columns: {len(wide.columns)}")
    print()
    print("mov_type counts:")
    print(wide["mov_type"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
    