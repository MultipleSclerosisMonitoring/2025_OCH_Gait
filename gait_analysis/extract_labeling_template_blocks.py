#!/usr/bin/env python3
"""Extract raw or spectrogram data for manual-labeling template blocks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Extrae datos de InfluxDB para bloques de una plantilla de etiquetado "
            "por paciente, con salida reanudable y manifiesto de estado."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        default="experiment_configs/labeling_templates_round1/all_patients_labeling_template.csv",
        help="CSV de plantilla generado por build_patient_labeling_templates.py.",
    )
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Configuracion YAML del extractor.",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        default="salidas_test/data_extension_round1/extracted_blocks",
        help="Directorio de salida para parquets extraidos.",
    )
    p.add_argument(
        "--manifest",
        default="salidas_test/data_extension_round1/extracted_blocks_manifest.csv",
        help="CSV de estado de la extraccion.",
    )
    p.add_argument(
        "--mode",
        choices=["raw", "spectrogram"],
        default="spectrogram",
        help="Modo de extraccion.",
    )
    p.add_argument(
        "--references",
        nargs="+",
        default=None,
        help="Filtra por una o varias referencias.",
    )
    p.add_argument(
        "--max-blocks",
        type=int,
        default=None,
        help="Limita el numero total de bloques a extraer.",
    )
    p.add_argument(
        "--one-block-per-reference",
        action="store_true",
        help="Extrae solo el primer bloque de cada referencia tras aplicar filtros.",
    )
    p.add_argument(
        "--first-success-per-reference",
        action="store_true",
        help=(
            "Recorre bloques por referencia y se detiene al obtener la primera "
            "salida real para cada una."
        ),
    )
    p.add_argument(
        "--resume-existing",
        action="store_true",
        help="Omite salidas ya existentes.",
    )
    p.add_argument(
        "--retries",
        type=int,
        default=1,
        help="Intentos por bloque.",
    )
    p.add_argument(
        "--retry-sleep-seconds",
        type=float,
        default=5.0,
        help="Espera entre reintentos.",
    )
    return p


def safe_fragment(value: object) -> str:
    """Return a filename-safe fragment."""
    return (
        str(value)
        .replace("-", "_")
        .replace(":", "")
        .replace(" ", "_")
        .replace("+", "p")
    )


def build_output_path(row: pd.Series, output_dir: Path, mode: str) -> Path:
    """Build the output parquet path for one template block."""
    ref = safe_fragment(row["Reference"])
    start = safe_fragment(row["review_from_local"])
    stop = safe_fragment(row["review_until_local"])
    block = int(row["review_block"])
    return output_dir / f"{ref}_block{block:04d}_{start}_{stop}_{mode}.parquet"


def audit_path_for(output_path: Path) -> Path:
    """Return the audit JSON path written by the extractor."""
    return output_path.with_suffix(".audit.json")


def read_audit_status(output_path: Path) -> tuple[str, str]:
    """Read extractor audit status and total rows when available."""
    audit_path = audit_path_for(output_path)
    if not audit_path.exists():
        return "missing_audit", ""
    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return "invalid_audit", str(exc)
    status = str(audit.get("status", "unknown"))
    total_rows = audit.get("total_rows")
    if total_rows is None:
        total_rows = sum(
            int(summary.get("rows", 0))
            for summary in audit.get("foot_summaries", {}).values()
            if isinstance(summary, dict)
        )
    return status, str(total_rows)


def load_blocks(path: Path, references: list[str] | None) -> pd.DataFrame:
    """Load and filter template blocks."""
    df = pd.read_csv(path)
    required = {"Reference", "review_block", "review_from_local", "review_until_local"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {sorted(missing)}")
    df["Reference"] = df["Reference"].astype(str)
    if references:
        df = df[df["Reference"].isin(references)].copy()
    return df.sort_values(["priority", "Reference", "review_block"]).reset_index(drop=True)


def select_blocks(
    df: pd.DataFrame,
    *,
    one_block_per_reference: bool,
    max_blocks: int | None,
) -> pd.DataFrame:
    """Select blocks according to CLI limits."""
    selected = df
    if one_block_per_reference:
        selected = selected.groupby("Reference", sort=False).head(1).reset_index(drop=True)
    if max_blocks is not None:
        selected = selected.head(max_blocks).reset_index(drop=True)
    return selected


def iter_reference_batches(
    df: pd.DataFrame,
    *,
    first_success_per_reference: bool,
) -> list[pd.DataFrame]:
    """Return extraction batches, grouped when searching first success per reference."""
    if not first_success_per_reference:
        return [df]
    return [
        group.reset_index(drop=True)
        for _, group in df.groupby("Reference", sort=False)
    ]


def run_extraction(
    *,
    row: pd.Series,
    output_path: Path,
    mode: str,
    config: str,
    retries: int,
    retry_sleep_seconds: float,
) -> tuple[str, str, str]:
    """Run extraction for one block and return wrapper status, audit status and error."""
    cmd = [
        sys.executable,
        "extract_influx_hdf5.py",
        "--mode",
        mode,
        "--config",
        config,
        "-f",
        str(row["review_from_local"]),
        "-u",
        str(row["review_until_local"]),
        "-q",
        str(row["Reference"]),
        "-o",
        str(output_path),
    ]
    attempts = max(1, retries)
    for attempt in range(1, attempts + 1):
        print(">>>", " ".join(cmd))
        result = subprocess.run(cmd, text=True, capture_output=True)
        if result.returncode == 0:
            audit_status, audit_rows = read_audit_status(output_path)
            if output_path.exists():
                return "ok", audit_status, ""
            return "no_output", audit_status, f"rows={audit_rows}"
        if attempt < attempts:
            time.sleep(retry_sleep_seconds)
    audit_status, _ = read_audit_status(output_path)
    return "failed", audit_status, (result.stderr or result.stdout).strip()


def main() -> None:
    """Extract selected template blocks."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    manifest_path = Path(args.manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    blocks = load_blocks(input_path, args.references)
    selected = select_blocks(
        blocks,
        one_block_per_reference=args.one_block_per_reference,
        max_blocks=args.max_blocks,
    )
    if selected.empty:
        raise ValueError("No hay bloques para extraer.")

    rows: list[dict[str, object]] = []
    for batch in iter_reference_batches(
        selected,
        first_success_per_reference=args.first_success_per_reference,
    ):
        reference_done = False
        for _, row in batch.iterrows():
            if reference_done:
                break
            output_path = build_output_path(row, output_dir, args.mode)
            if args.resume_existing and output_path.exists():
                status = "skipped_existing"
                audit_status, _ = read_audit_status(output_path)
                error = ""
            elif args.resume_existing and audit_path_for(output_path).exists():
                status = "skipped_audited_no_output"
                audit_status, audit_rows = read_audit_status(output_path)
                error = f"rows={audit_rows}"
            else:
                status, audit_status, error = run_extraction(
                    row=row,
                    output_path=output_path,
                    mode=args.mode,
                    config=args.config,
                    retries=args.retries,
                    retry_sleep_seconds=args.retry_sleep_seconds,
                )

            rows.append(
                {
                    "Reference": row["Reference"],
                    "review_block": row["review_block"],
                    "review_from_local": row["review_from_local"],
                    "review_until_local": row["review_until_local"],
                    "mode": args.mode,
                    "output_path": str(output_path),
                    "status": status,
                    "audit_status": audit_status,
                    "error": error,
                }
            )
            pd.DataFrame(rows).to_csv(manifest_path, index=False)
            print(f"{row['Reference']} block {row['review_block']}: {status}")
            if args.first_success_per_reference and status in {
                "ok",
                "skipped_existing",
            }:
                reference_done = True

    print(f"Manifest: {manifest_path}")
    print(pd.DataFrame(rows)["status"].value_counts().to_string())


if __name__ == "__main__":
    main()
