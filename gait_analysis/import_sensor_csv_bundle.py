#!/usr/bin/env python3
"""Import a bundle of single-signal CSV exports into a long parquet bundle.

The source CSVs contain second-precision timestamps and one signal per file.
This importer preserves the raw order of every sample and stores the bundle in
long form so no artificial alignment is introduced.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Convierte varios CSV de una sola señal en un bundle long en parquet."
        )
    )
    p.add_argument(
        "--reference",
        required=True,
        help="Identificador del paciente/referencia.",
    )
    p.add_argument(
        "--interval-start",
        required=True,
        help="Inicio nominal del intervalo (texto).",
    )
    p.add_argument(
        "--interval-end",
        required=True,
        help="Fin nominal del intervalo (texto).",
    )
    p.add_argument(
        "--output-dir",
        required=True,
        help="Directorio de salida del bundle.",
    )
    p.add_argument(
        "csv_paths",
        nargs="+",
        help="CSV de entrada, uno por señal.",
    )
    return p


def infer_foot(path: Path) -> str:
    """Infer foot label from file name."""
    name = path.name.lower()
    if "izquierdo" in name or "left" in name:
        return "Left"
    if "derecho" in name or "right" in name:
        return "Right"
    raise ValueError(f"No se puede inferir el pie desde el nombre: {path.name}")


def normalize_signal_name(header: str) -> str:
    """Normalize the raw channel name to a compact signal label."""
    return header.split()[0].strip()


def read_signal_csv(
    csv_path: Path,
    *,
    reference: str,
    interval_start: str,
    interval_end: str,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Read one single-signal CSV and convert it to long form."""
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    if df.shape[1] < 2:
        raise ValueError(f"CSV inválido, se esperaban al menos 2 columnas: {csv_path}")

    time_col = df.columns[0]
    value_col = df.columns[1]

    foot = infer_foot(csv_path)
    signal = normalize_signal_name(str(value_col))

    out = pd.DataFrame(
        {
            "reference": reference,
            "interval_start": interval_start,
            "interval_end": interval_end,
            "foot": foot,
            "signal": signal,
            "raw_channel_name": value_col,
            "source_file": csv_path.name,
            "sample_order": range(len(df)),
            "time": df[time_col].astype(str),
            "value": pd.to_numeric(df[value_col], errors="coerce"),
        }
    )

    manifest_row = {
        "source_file": csv_path.name,
        "foot": foot,
        "signal": signal,
        "rows": int(len(df)),
        "unique_times": int(df[time_col].nunique(dropna=False)),
        "first_time": str(df[time_col].iloc[0]) if len(df) else "",
        "last_time": str(df[time_col].iloc[-1]) if len(df) else "",
        "min_value": float(pd.to_numeric(df[value_col], errors="coerce").min()),
        "max_value": float(pd.to_numeric(df[value_col], errors="coerce").max()),
    }
    return out, manifest_row


def main() -> None:
    """Convert a bundle of CSV files into a long parquet and a manifest."""
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frames: list[pd.DataFrame] = []
    manifest_rows: list[dict[str, object]] = []
    for csv_arg in args.csv_paths:
        csv_path = Path(csv_arg)
        frame, manifest_row = read_signal_csv(
            csv_path,
            reference=args.reference,
            interval_start=args.interval_start,
            interval_end=args.interval_end,
        )
        frames.append(frame)
        manifest_rows.append(manifest_row)

    bundle = pd.concat(frames, ignore_index=True)
    bundle["time"] = bundle["time"].astype(str)

    safe_ref = args.reference.replace("-", "_")
    safe_start = args.interval_start.replace("-", "").replace(":", "").replace(" ", "_")
    safe_end = args.interval_end.replace("-", "").replace(":", "").replace(" ", "_")
    base_name = f"{safe_ref}_{safe_start}_{safe_end}"

    parquet_path = output_dir / f"{base_name}_raw_long.parquet"
    manifest_path = output_dir / f"{base_name}_manifest.csv"
    notes_path = output_dir / f"{base_name}_notes.txt"
    summary_path = output_dir / f"{base_name}_summary.json"

    bundle.to_parquet(parquet_path, index=False)
    pd.DataFrame(manifest_rows).sort_values(["foot", "signal"]).to_csv(manifest_path, index=False)

    notes = [
        f"reference={args.reference}",
        f"interval_start={args.interval_start}",
        f"interval_end={args.interval_end}",
        "note=The source CSVs contain second-precision timestamps only.",
        "note=The bundle is stored in long form to avoid inventing subsecond alignment.",
    ]
    notes_path.write_text("\n".join(notes) + "\n", encoding="utf-8")

    summary = {
        "reference": args.reference,
        "interval_start": args.interval_start,
        "interval_end": args.interval_end,
        "rows_total": int(len(bundle)),
        "signals": len(manifest_rows),
        "files": [row["source_file"] for row in manifest_rows],
        "parquet": str(parquet_path),
        "manifest": str(manifest_path),
        "notes": str(notes_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Parquet: {parquet_path}")
    print(f"Manifest: {manifest_path}")
    print(f"Notes: {notes_path}")
    print(f"Summary: {summary_path}")
    print(f"Rows total: {len(bundle)}")
    print(f"Signals: {len(manifest_rows)}")


if __name__ == "__main__":
    main()
