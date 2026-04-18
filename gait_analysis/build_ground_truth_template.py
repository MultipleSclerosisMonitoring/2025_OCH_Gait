#!/usr/bin/env python3
"""Build a blank ground-truth Excel template from fixed time intervals."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Genera una plantilla Excel de ground truth con intervalos fijos."
    )
    p.add_argument(
        "-r",
        "--reference",
        required=True,
        help="Referencia del paciente o sujeto",
    )
    p.add_argument(
        "-f",
        "--from_time",
        required=True,
        help='Inicio del rango temporal (ej: "2025-03-01 11:32:00")',
    )
    p.add_argument(
        "-u",
        "--until",
        required=True,
        help='Fin del rango temporal (ej: "2025-03-01 11:40:00")',
    )
    p.add_argument(
        "--step-seconds",
        type=int,
        default=60,
        help="Resolución temporal de cada intervalo en segundos",
    )
    p.add_argument(
        "-o",
        "--output",
        default="salidas_test/ground_truth_template.xlsx",
        help="Ruta del Excel de salida",
    )
    return p


def main() -> None:
    """Build a blank ground-truth template with fixed consecutive intervals."""
    args = build_parser().parse_args()

    reference = args.reference
    start = pd.to_datetime(args.from_time)
    end = pd.to_datetime(args.until)
    step = pd.Timedelta(seconds=args.step_seconds)
    output_path = Path(args.output)

    if end <= start:
        raise ValueError("--until debe ser posterior a --from_time")
    if args.step_seconds <= 0:
        raise ValueError("--step-seconds debe ser mayor que 0")

    rows = []
    current = start
    while current < end:
        next_time = min(current + step, end)
        rows.append(
            {
                "Reference": reference,
                "datefrom": current,
                "dateuntil": next_time,
                "mov_type": "",
                "Duration  (mins)": round((next_time - current).total_seconds() / 60.0, 6),
            }
        )
        current = next_time

    df = pd.DataFrame(rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False)

    print(f"Template guardada en: {output_path}")
    print(f"Reference: {reference}")
    print(f"Filas: {len(df)}")
    print(f"Resolución (s): {args.step_seconds}")
    print()
    print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
