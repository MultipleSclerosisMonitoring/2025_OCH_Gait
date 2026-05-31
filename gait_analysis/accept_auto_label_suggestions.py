#!/usr/bin/env python3
"""Accept auto-label suggestions into an importable labeled template."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


VALID_LABELS = {"walking", "not_walking"}


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Convierte sugerencias automaticas generadas desde raw de InfluxDB "
            "en una plantilla etiquetada importable. Mantiene la trazabilidad "
            "y marca las filas como auto_influx_heuristic."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        default="experiment_configs/auto_label_suggestions_selected_blocks.csv",
        help="CSV generado por auto_label_from_raw_blocks.py.",
    )
    p.add_argument(
        "-o",
        "--output",
        default="experiment_configs/auto_labeled_selected_blocks.csv",
        help="CSV etiquetado con mov_type aceptado desde suggested_mov_type.",
    )
    p.add_argument(
        "--summary",
        default="experiment_configs/auto_labeled_selected_blocks_summary.md",
        help="Resumen Markdown del etiquetado aceptado.",
    )
    p.add_argument(
        "--min-duration-s",
        type=float,
        default=5.0,
        help="Duracion minima de segmento aceptado.",
    )
    p.add_argument(
        "--require-both-feet",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Acepta solo segmentos calculados con ambos pies.",
    )
    return p


def validate_input(df: pd.DataFrame) -> None:
    """Validate required suggestion columns."""
    required = {
        "Reference",
        "label_from_local",
        "label_until_local",
        "label_from_utc",
        "label_until_utc",
        "suggested_mov_type",
        "duration_s",
        "feet_min",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {sorted(missing)}")


def accept_labels(
    df: pd.DataFrame,
    *,
    min_duration_s: float,
    require_both_feet: bool,
) -> pd.DataFrame:
    """Return accepted auto-label rows."""
    validate_input(df)
    accepted = df.copy()
    accepted["suggested_mov_type"] = (
        accepted["suggested_mov_type"].astype(str).str.strip().str.lower()
    )
    accepted = accepted[accepted["suggested_mov_type"].isin(VALID_LABELS)].copy()
    accepted = accepted[pd.to_numeric(accepted["duration_s"], errors="coerce") >= min_duration_s]
    if require_both_feet:
        accepted = accepted[pd.to_numeric(accepted["feet_min"], errors="coerce") >= 2]
    if accepted.empty:
        raise ValueError("No hay sugerencias aceptables con los filtros indicados.")

    accepted["mov_type"] = accepted["suggested_mov_type"]
    accepted["label_quality"] = "auto_influx_heuristic"
    accepted["review_notes"] = (
        "Etiqueta automatica aceptada desde energia de movimiento en raw InfluxDB; "
        "no procede de revision manual."
    )
    accepted = accepted.sort_values(
        ["Reference", "label_from_utc", "label_until_utc", "mov_type"]
    ).reset_index(drop=True)
    return accepted


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


def write_summary(path: Path, output: Path, accepted: pd.DataFrame) -> None:
    """Write an acceptance summary."""
    counts = (
        accepted.groupby(["Reference", "mov_type"], observed=True)
        .agg(segments=("mov_type", "size"), seconds=("duration_s", "sum"))
        .reset_index()
    )
    totals = (
        accepted.groupby("mov_type", observed=True)
        .agg(segments=("mov_type", "size"), seconds=("duration_s", "sum"))
        .reset_index()
    )
    lines = [
        "# Auto Accepted Labels",
        "",
        "These labels are generated from raw InfluxDB signal energy, not manual review.",
        "",
        f"- Output CSV: `{output}`",
        f"- Rows: {len(accepted)}",
        f"- Patients: {accepted['Reference'].nunique()}",
        "",
        "## Totals",
        "",
        markdown_table(totals),
        "",
        "## By Patient",
        "",
        markdown_table(counts),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Accept auto-label suggestions."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    summary_path = Path(args.summary)

    suggestions = pd.read_csv(input_path)
    accepted = accept_labels(
        suggestions,
        min_duration_s=args.min_duration_s,
        require_both_feet=args.require_both_feet,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    accepted.to_csv(output_path, index=False)
    write_summary(summary_path, output_path, accepted)

    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Rows: {len(accepted)}")
    print(accepted.groupby("mov_type").size().to_string())
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
