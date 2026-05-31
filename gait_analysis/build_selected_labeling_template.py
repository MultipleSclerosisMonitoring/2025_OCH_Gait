#!/usr/bin/env python3
"""Build a compact labeling template from selected covered blocks."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Genera una plantilla corta de etiquetado manual a partir de bloques "
            "ya verificados con datos en ambos pies."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        default="experiment_configs/all_labeling_template_selected_blocks.csv",
        help="CSV de bloques validos generado por scan_labeling_template_coverage.py.",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        default="experiment_configs/labeling_templates_selected_blocks",
        help="Directorio de salida para plantillas cortas.",
    )
    return p


def safe_reference(reference: str) -> str:
    """Return a filename-safe reference."""
    return "".join(char if char.isalnum() else "_" for char in reference)


def build_template(df: pd.DataFrame) -> pd.DataFrame:
    """Return the compact manual-labeling schema."""
    required = {
        "Reference",
        "priority",
        "review_block",
        "review_from_local",
        "review_until_local",
        "review_from_utc",
        "review_until_utc",
        "right_records",
        "left_records",
        "total_records",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {sorted(missing)}")

    template = df[
        [
            "Reference",
            "priority",
            "review_block",
            "review_from_local",
            "review_until_local",
            "review_from_utc",
            "review_until_utc",
            "right_records",
            "left_records",
            "total_records",
        ]
    ].copy()
    template["label_from_local"] = ""
    template["label_until_local"] = ""
    template["label_from_utc"] = ""
    template["label_until_utc"] = ""
    template["mov_type"] = ""
    template["label_quality"] = ""
    template["review_notes"] = ""

    ordered_cols = [
        "Reference",
        "priority",
        "review_block",
        "review_from_local",
        "review_until_local",
        "review_from_utc",
        "review_until_utc",
        "label_from_local",
        "label_until_local",
        "label_from_utc",
        "label_until_utc",
        "mov_type",
        "label_quality",
        "review_notes",
        "right_records",
        "left_records",
        "total_records",
    ]
    return template[ordered_cols].sort_values(
        ["priority", "Reference", "review_block"]
    )


def to_markdown_table(df: pd.DataFrame) -> str:
    """Render a compact Markdown table without optional dependencies."""
    if df.empty:
        return ""
    rendered = df.astype(str)
    headers = list(rendered.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in rendered.iterrows():
        lines.append("| " + " | ".join(row[col] for col in headers) + " |")
    return "\n".join(lines)


def write_readme(template: pd.DataFrame, output_dir: Path) -> None:
    """Write a short guide for manual labeling."""
    summary = (
        template.groupby("Reference")
        .agg(
            priority=("priority", "min"),
            blocks=("review_block", "size"),
            first_review=("review_from_local", "min"),
            last_review=("review_until_local", "max"),
            total_records=("total_records", "sum"),
        )
        .reset_index()
        .sort_values(["priority", "Reference"])
    )
    lines = [
        "# Selected Blocks Labeling Template",
        "",
        "This template contains only blocks already verified as `valid_both_feet` in InfluxDB.",
        "",
        "## How To Label",
        "",
        "1. Open `review_from_local` to `review_until_local` in Grafana.",
        "2. Fill `label_from_local` and `label_until_local` only for clear sub-intervals.",
        "3. Set `mov_type` to `walking` or `not_walking`.",
        "4. Use `label_quality` values such as `clear`, `transition`, `short` or `ambiguous`.",
        "5. Leave unclear rows blank; do not force a label.",
        "",
        "## Patients",
        "",
        to_markdown_table(summary),
        "",
        "## Import After Labeling",
        "",
        "```bash",
        "poetry run python gait_analysis/import_patient_labeling_template.py \\",
        "  -i experiment_configs/labeling_templates_selected_blocks/all_patients_labeling_template.csv \\",
        "  -o experiment_configs/manual_patient_ground_truth_utc.csv",
        "```",
        "",
    ]
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Build selected-block labeling templates."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)
    template = build_template(df)
    combined_path = output_dir / "all_patients_labeling_template.csv"
    template.to_csv(combined_path, index=False)

    for reference, ref_template in template.groupby("Reference", sort=False):
        ref_path = output_dir / f"{safe_reference(str(reference))}_labeling_template.csv"
        ref_template.to_csv(ref_path, index=False)

    write_readme(template, output_dir)

    print(f"Input: {input_path}")
    print(f"Output dir: {output_dir}")
    print(f"Rows: {len(template)}")
    print(f"Patients: {template['Reference'].nunique()}")
    print(f"Combined template: {combined_path}")


if __name__ == "__main__":
    main()
