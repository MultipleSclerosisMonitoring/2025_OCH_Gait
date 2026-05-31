#!/usr/bin/env python3
"""Summarize a prepared ML dataset by label, patient and optional source."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(description="Resume un parquet ML preparado.")
    p.add_argument("-i", "--input", required=True, help="Parquet ML de entrada.")
    p.add_argument("-o", "--output", required=True, help="Markdown de salida.")
    p.add_argument(
        "--metadata-cols",
        nargs="*",
        default=[],
        help="Columnas de metadatos que no son features.",
    )
    return p


def markdown_table(df: pd.DataFrame) -> str:
    """Render a compact Markdown table."""
    if df.empty:
        return "_Sin filas._"
    rendered = df.astype(str)
    headers = list(rendered.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in rendered.iterrows():
        lines.append("| " + " | ".join(row[col] for col in headers) + " |")
    return "\n".join(lines)


def main() -> None:
    """Write ML dataset summary."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    df = pd.read_parquet(input_path)

    base_id_cols = ["reference", "time_center", "mov_type", "target"]
    metadata_cols = [col for col in args.metadata_cols if col in df.columns]
    feature_cols = [
        col for col in df.columns if col not in [*base_id_cols, *metadata_cols]
    ]

    source_group_cols = [*metadata_cols, "mov_type", "target"] if metadata_cols else ["mov_type", "target"]
    by_source = (
        df.groupby(source_group_cols, observed=True)
        .size()
        .reset_index(name="rows")
        .sort_values(source_group_cols)
    )
    patient_group_cols = ["reference", *metadata_cols, "mov_type"]
    by_patient = (
        df.groupby(patient_group_cols, observed=True)
        .size()
        .reset_index(name="rows")
        .sort_values(patient_group_cols)
    )

    lines = [
        "# ML Dataset Summary",
        "",
        f"- Input parquet: `{input_path}`",
        f"- Rows: {len(df)}",
        f"- Patients: {df['reference'].nunique()}",
        f"- Feature columns: {len(feature_cols)}",
        f"- Metadata columns: {', '.join(metadata_cols) if metadata_cols else 'none'}",
        f"- Metadata used as feature: {bool(set(metadata_cols) & set(feature_cols))}",
        "",
        "## By Source",
        "",
        markdown_table(by_source),
        "",
        "## By Patient",
        "",
        markdown_table(by_patient),
        "",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Rows: {len(df)}")
    print(f"Feature columns: {len(feature_cols)}")
    print(f"Metadata used as feature: {bool(set(metadata_cols) & set(feature_cols))}")


if __name__ == "__main__":
    main()
