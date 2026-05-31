#!/usr/bin/env python3
"""Build manual labeling templates from covered patient candidate windows."""

from __future__ import annotations

import argparse
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Genera plantillas CSV para etiquetar en Grafana las ventanas de "
            "pacientes con cobertura Influx validada."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        default="experiment_configs/balanced_data_extension_labeling_candidates.csv",
        help="CSV con ventanas candidatas y cobertura por pie.",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        default="experiment_configs/labeling_templates",
        help="Directorio de salida para plantillas por paciente.",
    )
    p.add_argument(
        "--chunk-minutes",
        type=float,
        default=10.0,
        help="Duracion de cada bloque de revision en minutos.",
    )
    p.add_argument(
        "--input-timezone",
        default="UTC",
        help="Zona horaria de shifted_datefrom/shifted_dateuntil si vienen sin offset.",
    )
    p.add_argument(
        "--display-timezone",
        default="Europe/Madrid",
        help="Zona horaria local que se escribira en las columnas *_local.",
    )
    p.add_argument(
        "--max-patients",
        type=int,
        default=None,
        help="Limita el numero de pacientes por prioridad.",
    )
    return p


def parse_candidate_timestamp(
    value: object,
    input_tz: str,
    display_tz: str,
) -> pd.Timestamp:
    """Parse a candidate timestamp and convert it to the display timezone."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize(input_tz)
    return ts.tz_convert(display_tz)


def iso_seconds(ts: pd.Timestamp) -> str:
    """Format a timestamp with seconds and timezone offset."""
    return ts.strftime("%Y-%m-%d %H:%M:%S%z")[:-2] + ":" + ts.strftime("%Y-%m-%d %H:%M:%S%z")[-2:]


def safe_reference(reference: str) -> str:
    """Return a filename-safe reference."""
    return "".join(char if char.isalnum() else "_" for char in reference)


def build_chunks(
    row: pd.Series,
    chunk_minutes: float,
    input_tz: str,
    display_tz: str,
) -> list[dict[str, object]]:
    """Split one covered candidate range into manual review blocks."""
    start = parse_candidate_timestamp(row["shifted_datefrom"], input_tz, display_tz)
    stop = parse_candidate_timestamp(row["shifted_dateuntil"], input_tz, display_tz)
    step = pd.Timedelta(minutes=chunk_minutes)
    chunks: list[dict[str, object]] = []
    chunk_index = 1
    current = start
    while current < stop:
        chunk_stop = min(current + step, stop)
        chunks.append(
            {
                "Reference": row["Reference"],
                "priority": row.get("priority", ""),
                "review_block": chunk_index,
                "review_from_local": current.strftime("%Y-%m-%d %H:%M:%S"),
                "review_until_local": chunk_stop.strftime("%Y-%m-%d %H:%M:%S"),
                "review_from_utc": iso_seconds(current.tz_convert("UTC")),
                "review_until_utc": iso_seconds(chunk_stop.tz_convert("UTC")),
                "label_from_local": "",
                "label_until_local": "",
                "label_from_utc": "",
                "label_until_utc": "",
                "mov_type": "",
                "label_quality": "",
                "review_notes": "",
                "offset_minutes": row.get("offset_minutes", ""),
                "right_records": row.get("right_records", ""),
                "left_records": row.get("left_records", ""),
                "total_records": row.get("total_records", ""),
            }
        )
        current = chunk_stop
        chunk_index += 1
    return chunks


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


def write_index(
    *,
    output_dir: Path,
    candidates: pd.DataFrame,
    all_template: pd.DataFrame,
    chunk_minutes: float,
    input_tz: str,
    display_tz: str,
) -> None:
    """Write a short index explaining how to use the generated templates."""
    summary = (
        all_template.groupby("Reference")
        .agg(
            priority=("priority", "min"),
            review_blocks=("review_block", "size"),
            first_review=("review_from_local", "min"),
            last_review=("review_until_local", "max"),
            total_records=("total_records", "max"),
        )
        .reset_index()
        .sort_values(["priority", "Reference"])
    )
    lines = [
        "# Patient Labeling Templates",
        "",
        f"Input timezone: `{input_tz}`",
        f"Display timezone: `{display_tz}`",
        f"Review block length: `{chunk_minutes:g}` minutes",
        "",
        "## How To Label",
        "",
        "1. Open each review block in Grafana using `review_from_local` and `review_until_local`.",
        "2. Add precise labeled intervals in `label_from_local` and `label_until_local`.",
        "3. Set `mov_type` to `walking` or `not_walking` only when the segment is clear.",
        "4. Leave ambiguous blocks blank and explain the reason in `review_notes`.",
        "5. Use `label_quality` values such as `clear`, `short`, `transition` or `ambiguous`.",
        "",
        "The UTC columns are included so accepted labels can be merged into the reproducible ground-truth CSV without another timezone guess.",
        "",
        "## Patients",
        "",
        to_markdown_table(summary),
        "",
        "## Source Candidates",
        "",
        to_markdown_table(candidates),
        "",
    ]
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Build per-patient and combined manual labeling templates."""
    args = build_parser().parse_args()
    if args.chunk_minutes <= 0:
        raise ValueError("--chunk-minutes debe ser mayor que 0")

    ZoneInfo(args.input_timezone)
    ZoneInfo(args.display_timezone)
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = pd.read_csv(input_path)
    required = {"Reference", "shifted_datefrom", "shifted_dateuntil"}
    missing = required - set(candidates.columns)
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {sorted(missing)}")

    candidates = candidates.sort_values(["priority", "Reference"]).reset_index(drop=True)
    if args.max_patients is not None:
        candidates = candidates.head(args.max_patients)

    all_rows: list[dict[str, object]] = []
    for _, row in candidates.iterrows():
        ref_rows = build_chunks(
            row,
            args.chunk_minutes,
            args.input_timezone,
            args.display_timezone,
        )
        all_rows.extend(ref_rows)
        ref_df = pd.DataFrame(ref_rows)
        ref_path = output_dir / f"{safe_reference(str(row['Reference']))}_labeling_template.csv"
        ref_df.to_csv(ref_path, index=False)

    all_template = pd.DataFrame(all_rows)
    all_path = output_dir / "all_patients_labeling_template.csv"
    all_template.to_csv(all_path, index=False)
    write_index(
        output_dir=output_dir,
        candidates=candidates,
        all_template=all_template,
        chunk_minutes=args.chunk_minutes,
        input_tz=args.input_timezone,
        display_tz=args.display_timezone,
    )

    print(f"Input: {input_path}")
    print(f"Output dir: {output_dir}")
    print(f"Patients: {candidates['Reference'].nunique()}")
    print(f"Review blocks: {len(all_template)}")
    print(f"Combined template: {all_path}")
    print(f"Index: {output_dir / 'README.md'}")


if __name__ == "__main__":
    main()
