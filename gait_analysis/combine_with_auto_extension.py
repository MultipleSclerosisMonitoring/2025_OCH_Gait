#!/usr/bin/env python3
"""Combine the previous labeled dataset with the auto-labeled Influx extension."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Combina el dataset etiquetado previo con la extension autoetiquetada "
            "desde Influx, conservando trazabilidad de origen."
        )
    )
    p.add_argument(
        "--base",
        default=(
            "salidas_test/auto_extracts/"
            "main_combined_labeled_dataset_with_manual_newpatients_plus_direct_walking_plus_054walking.parquet"
        ),
        help="Parquet etiquetado anterior.",
    )
    p.add_argument(
        "--extension",
        default="salidas_test/data_extension_selected/auto_labeled_selected_blocks_spectrogram.parquet",
        help="Parquet etiquetado de la ampliacion automatica.",
    )
    p.add_argument(
        "-o",
        "--output",
        default=(
            "salidas_test/data_extension_selected/"
            "main_combined_labeled_dataset_with_auto_influx_extension.parquet"
        ),
        help="Parquet combinado de salida.",
    )
    p.add_argument(
        "--summary",
        default="experiment_configs/combined_auto_influx_extension_summary.md",
        help="Resumen Markdown versionable.",
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


def add_source(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Return a copy with dataset source metadata."""
    out = df.copy()
    out["dataset_source"] = source
    return out


def summarize(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """Summarize rows by labels and optional groups."""
    return (
        df.groupby(group_cols, observed=True)
        .size()
        .reset_index(name="rows")
        .sort_values(group_cols)
    )


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
    """Write a Markdown summary."""
    lines = [
        "# Combined Auto Influx Extension",
        "",
        f"- Base dataset: `{base_path}`",
        f"- Auto extension: `{extension_path}`",
        f"- Output dataset: `{output_path}`",
        f"- Base rows: {len(base)}",
        f"- Extension rows: {len(extension)}",
        f"- Exact duplicate rows removed: {duplicate_rows}",
        f"- Combined rows: {len(combined)}",
        f"- Combined patients: {combined['reference'].nunique()}",
        "",
        "## Totals By Source",
        "",
        markdown_table(summarize(combined, ["dataset_source", "mov_type"])),
        "",
        "## Totals By Label",
        "",
        markdown_table(summarize(combined, ["mov_type"])),
        "",
        "## Rows By Patient",
        "",
        markdown_table(summarize(combined, ["reference", "dataset_source", "mov_type"])),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Combine previous and auto-extension labeled datasets."""
    args = build_parser().parse_args()
    base_path = Path(args.base)
    extension_path = Path(args.extension)
    output_path = Path(args.output)
    summary_path = Path(args.summary)

    base = pd.read_parquet(base_path)
    extension = pd.read_parquet(extension_path)

    base_cols = [col for col in base.columns if col != "dataset_source"]
    extension_cols = [col for col in extension.columns if col != "dataset_source"]
    if set(base_cols) != set(extension_cols):
        missing_in_extension = sorted(set(base_cols) - set(extension_cols))
        missing_in_base = sorted(set(extension_cols) - set(base_cols))
        raise ValueError(
            "Los esquemas no coinciden. "
            f"Faltan en extension: {missing_in_extension}; faltan en base: {missing_in_base}"
        )

    extension = extension[base_cols]
    combined_before = pd.concat(
        [
            add_source(base[base_cols], "previous_dataset"),
            add_source(extension, "auto_influx_heuristic"),
        ],
        ignore_index=True,
    )
    combined = combined_before.drop_duplicates(subset=base_cols, keep="first")
    duplicate_rows = len(combined_before) - len(combined)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(output_path, index=False)
    write_summary(
        summary_path,
        base_path=base_path,
        extension_path=extension_path,
        output_path=output_path,
        base=base,
        extension=extension,
        combined=combined,
        duplicate_rows=duplicate_rows,
    )

    print(f"Base: {base_path}")
    print(f"Extension: {extension_path}")
    print(f"Output: {output_path}")
    print(f"Summary: {summary_path}")
    print(f"Base rows: {len(base)}")
    print(f"Extension rows: {len(extension)}")
    print(f"Exact duplicate rows removed: {duplicate_rows}")
    print(f"Combined rows: {len(combined)}")
    print()
    print("mov_type counts:")
    print(combined["mov_type"].value_counts(dropna=False).to_string())
    print()
    print("dataset_source counts:")
    print(combined["dataset_source"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
