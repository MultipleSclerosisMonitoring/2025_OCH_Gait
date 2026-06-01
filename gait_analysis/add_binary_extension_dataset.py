#!/usr/bin/env python3
"""Add a binary ML extension dataset to an existing binary ML dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


KEY_COLS = ["reference", "time_center", "mov_type", "dataset_source"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Concatena un dataset binario ML base con una extension binaria, "
            "normalizando timestamps y eliminando duplicados por referencia, "
            "time_center, etiqueta y origen."
        )
    )
    parser.add_argument("--base", required=True, help="Parquet binario base.")
    parser.add_argument("--extension", required=True, help="Parquet binario de extension.")
    parser.add_argument("-o", "--output", required=True, help="Parquet combinado de salida.")
    parser.add_argument("--summary", default=None, help="Resumen Markdown opcional.")
    return parser


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    missing = [col for col in KEY_COLS if col not in output.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {missing}")
    output["reference"] = output["reference"].astype(str)
    output["mov_type"] = output["mov_type"].astype(str)
    output["dataset_source"] = output["dataset_source"].astype(str)
    output["time_center"] = pd.to_datetime(output["time_center"], utc=True, format="mixed")
    return output


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["reference", "dataset_source", "mov_type"], dropna=False)
        .size()
        .reset_index(name="rows")
        .sort_values(["reference", "dataset_source", "mov_type"])
    )


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_Sin filas._"
    rendered = df.astype(str)
    columns = rendered.columns.tolist()
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in rendered.iterrows():
        lines.append("| " + " | ".join(row[col] for col in columns) + " |")
    return "\n".join(lines)


def write_summary(
    path: Path,
    *,
    base_path: Path,
    extension_path: Path,
    output_path: Path,
    base: pd.DataFrame,
    extension: pd.DataFrame,
    combined: pd.DataFrame,
    duplicate_rows: int,
) -> None:
    lines = [
        "# Binary dataset extension",
        "",
        f"- Base: `{base_path}`",
        f"- Extension: `{extension_path}`",
        f"- Output: `{output_path}`",
        f"- Base rows: {len(base)}",
        f"- Extension rows: {len(extension)}",
        f"- Duplicate extension rows removed: {duplicate_rows}",
        f"- Combined rows: {len(combined)}",
        f"- Patients: {combined['reference'].nunique()}",
        "",
        "## Extension rows",
        "",
        markdown_table(summarize(extension)),
        "",
        "## Combined rows by patient/source/label",
        "",
        markdown_table(summarize(combined)),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = build_parser().parse_args()
    base_path = Path(args.base)
    extension_path = Path(args.extension)
    output_path = Path(args.output)

    base = normalize(pd.read_parquet(base_path))
    extension = normalize(pd.read_parquet(extension_path))
    if set(base.columns) != set(extension.columns):
        missing_in_extension = sorted(set(base.columns) - set(extension.columns))
        missing_in_base = sorted(set(extension.columns) - set(base.columns))
        raise ValueError(
            "Los esquemas no coinciden. "
            f"Faltan en extension: {missing_in_extension}; "
            f"faltan en base: {missing_in_base}"
        )
    extension = extension[base.columns]

    before = len(base) + len(extension)
    combined = (
        pd.concat([base, extension], ignore_index=True)
        .drop_duplicates(subset=KEY_COLS, keep="first")
        .reset_index(drop=True)
    )
    duplicate_rows = before - len(combined)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(output_path, index=False)
    if args.summary:
        write_summary(
            Path(args.summary),
            base_path=base_path,
            extension_path=extension_path,
            output_path=output_path,
            base=base,
            extension=extension,
            combined=combined,
            duplicate_rows=duplicate_rows,
        )

    print(f"Base rows: {len(base)}")
    print(f"Extension rows: {len(extension)}")
    print(f"Duplicate rows removed: {duplicate_rows}")
    print(f"Combined rows: {len(combined)}")
    print(f"Output: {output_path}")
    if args.summary:
        print(f"Summary: {args.summary}")
    print()
    print("Extension summary:")
    print(summarize(extension).to_string(index=False))


if __name__ == "__main__":
    main()
