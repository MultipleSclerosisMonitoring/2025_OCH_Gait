#!/usr/bin/env python3
"""Build short review blocks for labeling new Influx references."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_REFERENCES = [
    "AMIR-48",
    "MGM-202406-79",
    "AAMALMHUG057-66",
    "CHIHUG033-15",
    "LFCMHUG070-78",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Construye un lote corto de bloques revisables para etiquetar "
            "referencias nuevas con senal bilateral en Influx."
        )
    )
    parser.add_argument(
        "-i",
        "--inventory",
        default="experiment_configs/influx_reference_inventory_exhaustive.csv",
        help="Inventario exhaustivo de referencias Influx.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="experiment_configs/new_influx_labeling_review_batch.csv",
        help="CSV de bloques de revision.",
    )
    parser.add_argument(
        "--summary",
        default="results/new_influx_labeling_review_batch_summary.md",
        help="Resumen Markdown del lote.",
    )
    parser.add_argument(
        "--references",
        nargs="+",
        default=DEFAULT_REFERENCES,
        help="Referencias que se incluiran en el lote.",
    )
    parser.add_argument(
        "--blocks-per-reference",
        type=int,
        default=2,
        help="Numero de bloques cortos por referencia.",
    )
    parser.add_argument(
        "--block-minutes",
        type=float,
        default=30.0,
        help="Duracion de cada bloque de revision en minutos.",
    )
    parser.add_argument(
        "--timezone",
        default="Europe/Madrid",
        help="Zona horaria local para columnas review_*_local.",
    )
    return parser


def safe_timestamp(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def choose_block_starts(
    start: pd.Timestamp,
    stop: pd.Timestamp,
    *,
    blocks_per_reference: int,
    block_duration: pd.Timedelta,
) -> list[pd.Timestamp]:
    latest_start = stop - block_duration
    if latest_start < start:
        return [start]
    if blocks_per_reference <= 1:
        return [start]
    span_s = (latest_start - start).total_seconds()
    starts = [
        start + pd.to_timedelta(span_s * idx / (blocks_per_reference - 1), unit="s")
        for idx in range(blocks_per_reference)
    ]
    return [pd.Timestamp(ts).floor("s") for ts in starts]


def build_batch(
    inventory: pd.DataFrame,
    references: list[str],
    *,
    blocks_per_reference: int,
    block_minutes: float,
    timezone: str,
) -> pd.DataFrame:
    data = inventory[inventory["reference"].isin(references)].copy()
    missing = sorted(set(references) - set(data["reference"]))
    if missing:
        raise ValueError(f"Referencias no encontradas en inventario: {missing}")

    block_duration = pd.to_timedelta(block_minutes, unit="min")
    rows: list[dict[str, object]] = []
    priority = 1
    for reference in references:
        row = data[data["reference"].eq(reference)].iloc[0]
        start = pd.to_datetime(row["intersection_start_utc"], utc=True)
        stop = pd.to_datetime(row["intersection_stop_utc"], utc=True)
        if pd.isna(start) or pd.isna(stop) or stop <= start:
            continue

        starts = choose_block_starts(
            start,
            stop,
            blocks_per_reference=blocks_per_reference,
            block_duration=block_duration,
        )
        for block_idx, block_start in enumerate(starts, start=1):
            block_stop = min(block_start + block_duration, stop)
            local_start = block_start.tz_convert(timezone)
            local_stop = block_stop.tz_convert(timezone)
            rows.append(
                {
                    "Reference": reference,
                    "priority": priority,
                    "review_block": block_idx,
                    "review_from_local": safe_timestamp(local_start),
                    "review_until_local": safe_timestamp(local_stop),
                    "review_from_utc": block_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "review_until_utc": block_stop.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "review_duration_s": (block_stop - block_start).total_seconds(),
                    "source_status": row["audit_status"],
                    "manual_candidate": bool(row.get("manual_candidate", False)),
                    "manual_priority": row.get("manual_priority", ""),
                    "right_records_total": int(row["right_records"]),
                    "left_records_total": int(row["left_records"]),
                    "intersection_start_utc": row["intersection_start_utc"],
                    "intersection_stop_utc": row["intersection_stop_utc"],
                    "mov_type": "",
                    "label_quality": "",
                    "review_notes": "",
                }
            )
        priority += 1

    return pd.DataFrame(rows)


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_Sin filas._"
    view = df.astype(str)
    columns = view.columns.tolist()
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(row[col] for col in columns) + " |")
    return "\n".join(lines)


def write_summary(path: Path, batch: pd.DataFrame, output_path: Path) -> None:
    summary = (
        batch.groupby("Reference")
        .agg(
            priority=("priority", "min"),
            blocks=("review_block", "size"),
            first_local=("review_from_local", "min"),
            last_local=("review_until_local", "max"),
            status=("source_status", "first"),
        )
        .reset_index()
        .sort_values(["priority", "Reference"])
    )
    lines = [
        "# Lote de etiquetado Influx para referencias nuevas",
        "",
        f"- Plantilla: `{output_path}`",
        f"- Referencias: {batch['Reference'].nunique()}",
        f"- Bloques: {len(batch)}",
        "",
        "Este lote no incorpora etiquetas al dataset. Genera bloques cortos para "
        "extraer senal raw desde Influx, calcular sugerencias de actividad y "
        "revisar manualmente `walking` / `not_walking`.",
        "",
        "## Referencias",
        "",
        markdown_table(summary),
        "",
        "## Siguiente comando",
        "",
        "```bash",
        "poetry run python gait_analysis/extract_labeling_template_blocks.py \\",
        f"  -i {output_path} \\",
        "  --mode raw \\",
        "  -o salidas_test/new_influx_labeling_batch/raw_blocks \\",
        "  --manifest salidas_test/new_influx_labeling_batch/raw_manifest.csv \\",
        "  --resume-existing",
        "```",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = build_parser().parse_args()
    inventory = pd.read_csv(args.inventory)
    batch = build_batch(
        inventory,
        args.references,
        blocks_per_reference=args.blocks_per_reference,
        block_minutes=args.block_minutes,
        timezone=args.timezone,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    batch.to_csv(output, index=False)
    write_summary(Path(args.summary), batch, output)
    print(f"Output: {output}")
    print(f"Rows: {len(batch)}")
    print(f"References: {batch['Reference'].nunique()}")
    print(f"Summary: {args.summary}")


if __name__ == "__main__":
    main()
