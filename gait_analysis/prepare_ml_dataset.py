#!/usr/bin/env python3
"""Prepare a clean wide spectrogram dataset for binary classification."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Prepara un parquet wide limpio para clasificacion binaria 0/1."
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="Ruta al parquet wide limpio de entrada",
    )
    p.add_argument(
        "-o",
        "--output",
        required=True,
        help="Ruta del parquet preparado de salida",
    )
    return p


def main() -> None:
    """Read a clean wide parquet, add a binary target, and save an ML-ready table."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    df = pd.read_parquet(input_path)

    id_cols = ["reference", "time_center", "mov_type"]
    missing_id_cols = [c for c in id_cols if c not in df.columns]
    if missing_id_cols:
        raise ValueError(f"Faltan columnas identificadoras: {missing_id_cols}")

    feature_cols = [c for c in df.columns if c not in id_cols]
    target_map = {"not_walking": 0, "walking": 1}
    unknown_labels = sorted(set(df["mov_type"].dropna()) - set(target_map))
    if unknown_labels:
        raise ValueError(
            f"Etiquetas no soportadas para clasificacion binaria: {unknown_labels}"
        )

    output = df[id_cols + feature_cols].copy()
    output["target"] = output["mov_type"].map(target_map).astype("int8")
    output = output[["reference", "time_center", "mov_type", "target", *feature_cols]]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(output_path, index=False)

    print(f"Input parquet: {input_path}")
    print(f"Output parquet: {output_path}")
    print(f"Rows: {len(output)}")
    print(f"Feature columns: {len(feature_cols)}")
    print()
    print("Target counts:")
    print(output["target"].value_counts(dropna=False).sort_index().to_string())
    print()
    print(f"X shape: {(len(output), len(feature_cols))}")
    print(f"y shape: {(len(output),)}")
    print()
    print("First 10 feature columns:")
    print(feature_cols[:10])
    print()
    print("Target mapping:")
    print(target_map)


if __name__ == "__main__":
    main()
