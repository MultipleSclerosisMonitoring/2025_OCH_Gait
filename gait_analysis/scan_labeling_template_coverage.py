#!/usr/bin/env python3
"""Scan Influx coverage for manual-labeling template blocks."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import warnings

import pandas as pd
import urllib3

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gait_analysis.build_patient_candidate_inventory import count_interval
from gait_analysis.config import ConfigLoader
from gait_analysis.influx_service import InfluxService


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Escanea bloques de una plantilla de etiquetado y cuenta muestras "
            "por pie en InfluxDB sin extraer la señal completa."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        default="experiment_configs/labeling_templates/all_patients_labeling_template.csv",
        help="CSV generado por build_patient_labeling_templates.py.",
    )
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Configuracion YAML con conexion/tags de Influx.",
    )
    p.add_argument(
        "-o",
        "--output",
        default="experiment_configs/labeling_template_coverage_scan.csv",
        help="CSV de salida con cobertura por bloque.",
    )
    p.add_argument(
        "--selected-output",
        default="experiment_configs/labeling_template_selected_blocks.csv",
        help="CSV con los bloques validos seleccionados para etiquetar.",
    )
    p.add_argument(
        "--references",
        nargs="+",
        default=None,
        help="Limita el escaneo a una o varias referencias.",
    )
    p.add_argument(
        "--max-valid-blocks-per-reference",
        type=int,
        default=5,
        help="Se detiene en cada referencia tras encontrar este numero de bloques validos.",
    )
    p.add_argument(
        "--max-scanned-blocks-per-reference",
        type=int,
        default=None,
        help="Limita los bloques comprobados por referencia.",
    )
    p.add_argument(
        "--min-records-per-foot",
        type=int,
        default=1000,
        help="Minimo de registros por pie para considerar util un bloque.",
    )
    p.add_argument(
        "--resume-existing",
        action="store_true",
        help="Reutiliza filas existentes del CSV de salida.",
    )
    return p


def load_blocks(path: Path, references: list[str] | None) -> pd.DataFrame:
    """Load template blocks and normalize the schema expected by count_interval."""
    df = pd.read_csv(path)
    required = {"Reference", "review_block", "review_from_local", "review_until_local"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {sorted(missing)}")
    df["Reference"] = df["Reference"].astype(str)
    if references:
        df = df[df["Reference"].isin(references)].copy()
    df["datefrom"] = df["review_from_local"]
    df["dateuntil"] = df["review_until_local"]
    return df.sort_values(["priority", "Reference", "review_block"]).reset_index(drop=True)


def block_key(row: pd.Series) -> tuple[str, int]:
    """Return a stable key for one template block."""
    return str(row["Reference"]), int(row["review_block"])


def load_existing(path: Path) -> dict[tuple[str, int], dict[str, object]]:
    """Load previous scan rows for resume mode."""
    if not path.exists():
        return {}
    existing = pd.read_csv(path)
    if existing.empty:
        return {}
    return {
        (str(row["Reference"]), int(row["review_block"])): row.to_dict()
        for _, row in existing.iterrows()
    }


def classify_status(counts: dict[str, int], min_records_per_foot: int) -> str:
    """Classify coverage from per-foot record counts."""
    values = list(counts.values())
    if not values or max(values) == 0:
        return "no_records"
    if all(value >= min_records_per_foot for value in values):
        return "valid_both_feet"
    if all(value > 0 for value in values):
        return "low_records_both_feet"
    return "only_some_feet"


def build_result_row(
    row: pd.Series,
    counts: dict[str, int],
    *,
    status: str,
    error: str,
) -> dict[str, object]:
    """Build one scan result row."""
    result = {
        "priority": row.get("priority", ""),
        "Reference": row["Reference"],
        "review_block": row["review_block"],
        "review_from_local": row["review_from_local"],
        "review_until_local": row["review_until_local"],
        "review_from_utc": row.get("review_from_utc", ""),
        "review_until_utc": row.get("review_until_utc", ""),
        "status": status,
        "error": error,
    }
    result.update(counts)
    result["min_records_per_foot"] = min(counts.values()) if counts else 0
    result["total_records"] = sum(counts.values()) if counts else 0
    return result


def write_outputs(
    rows: list[dict[str, object]],
    output: Path,
    selected_output: Path,
    min_records_per_foot: int,
) -> None:
    """Write full scan and selected valid blocks."""
    output.parent.mkdir(parents=True, exist_ok=True)
    selected_output.parent.mkdir(parents=True, exist_ok=True)

    full = pd.DataFrame(rows)
    full.to_csv(output, index=False)
    selected = full[full["status"] == "valid_both_feet"].copy()
    if not selected.empty:
        selected = selected.sort_values(
            ["priority", "Reference", "review_block"],
            ascending=[True, True, True],
        )
    selected.to_csv(selected_output, index=False)

    summary = full["status"].value_counts().to_string() if not full.empty else "empty"
    print(f"Output: {output}")
    print(f"Selected: {selected_output}")
    print(f"Min records per foot: {min_records_per_foot}")
    print(summary)


def main() -> None:
    """Scan template block coverage."""
    args = build_parser().parse_args()
    warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

    cfg = ConfigLoader(args.config).load()
    blocks = load_blocks(Path(args.input), args.references)
    output = Path(args.output)
    selected_output = Path(args.selected_output)
    existing = load_existing(output) if args.resume_existing else {}

    rows: list[dict[str, object]] = []
    valid_by_ref: dict[str, int] = {}
    scanned_by_ref: dict[str, int] = {}

    with InfluxService(cfg.influx) as influx:
        for _, row in blocks.iterrows():
            ref = str(row["Reference"])
            if valid_by_ref.get(ref, 0) >= args.max_valid_blocks_per_reference:
                continue
            if (
                args.max_scanned_blocks_per_reference is not None
                and scanned_by_ref.get(ref, 0) >= args.max_scanned_blocks_per_reference
            ):
                continue

            key = block_key(row)
            if key in existing:
                result = existing[key]
                status = str(result.get("status", ""))
            else:
                print(
                    "Scanning",
                    ref,
                    f"block={row['review_block']}",
                    row["review_from_local"],
                    row["review_until_local"],
                )
                try:
                    counts = count_interval(influx, cfg, row)
                    status = classify_status(counts, args.min_records_per_foot)
                    result = build_result_row(row, counts, status=status, error="")
                except Exception as exc:  # noqa: BLE001 - keep long scans alive.
                    status = "error"
                    result = build_result_row(row, {}, status=status, error=str(exc))

            rows.append(result)
            scanned_by_ref[ref] = scanned_by_ref.get(ref, 0) + 1
            if status == "valid_both_feet":
                valid_by_ref[ref] = valid_by_ref.get(ref, 0) + 1

            write_outputs(rows, output, selected_output, args.min_records_per_foot)

    print()
    print("Valid blocks by reference:")
    print(pd.Series(valid_by_ref).sort_index().to_string() if valid_by_ref else "none")


if __name__ == "__main__":
    main()
