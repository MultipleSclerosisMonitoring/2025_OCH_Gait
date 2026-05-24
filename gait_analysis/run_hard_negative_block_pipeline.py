#!/usr/bin/env python3
"""Run the full hard-negative reconstruction pipeline for one interval.

This wrapper keeps the hard-negative workflow reproducible:
1. import one-signal CSV exports into a raw long parquet bundle,
2. reconstruct labeled spectrogram rows,
3. pivot to wide form,
4. convert to the binary ML table.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Ejecuta el pipeline completo de reconstruccion de un bloque duro "
            "a partir de CSVs crudos exportados manualmente."
        )
    )
    p.add_argument("--reference", required=True, help="Identificador del paciente.")
    p.add_argument("--interval-start", required=True, help="Inicio nominal.")
    p.add_argument("--interval-end", required=True, help="Fin nominal.")
    p.add_argument(
        "--output-dir",
        required=True,
        help="Directorio raiz donde guardar todos los artefactos del bloque.",
    )
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Configuracion espectral del proyecto.",
    )
    p.add_argument(
        "csv_paths",
        nargs="+",
        help="CSVs de una sola señal, uno por canal.",
    )
    return p


def run_cmd(cmd: list[str]) -> None:
    """Run one subprocess command and stop on failure."""
    print(">>>", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    """Execute the full hard-negative pipeline."""
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    python_exe = sys.executable

    raw_dir = output_dir / "raw_bundle"
    spec_dir = output_dir / "spectrogram"
    wide_dir = output_dir / "wide"
    binary_dir = output_dir / "binary"
    raw_dir.mkdir(parents=True, exist_ok=True)
    spec_dir.mkdir(parents=True, exist_ok=True)
    wide_dir.mkdir(parents=True, exist_ok=True)
    binary_dir.mkdir(parents=True, exist_ok=True)

    raw_base = (
        f"{args.reference.replace('-', '_')}_"
        f"{args.interval_start.replace('-', '').replace(':', '').replace(' ', '_')}_"
        f"{args.interval_end.replace('-', '').replace(':', '').replace(' ', '_')}"
    )
    raw_parquet = raw_dir / f"{raw_base}_raw_long.parquet"
    spec_parquet = spec_dir / f"{raw_base}_hardneg_spectrogram.parquet"
    wide_parquet = wide_dir / f"{raw_base}_hardneg_wide.parquet"
    binary_parquet = binary_dir / f"{raw_base}_hardneg_binary.parquet"
    summary_path = output_dir / f"{raw_base}_hardneg_pipeline_summary.json"

    run_cmd(
        [
            python_exe,
            "-m",
            "gait_analysis.import_sensor_csv_bundle",
            "--reference",
            args.reference,
            "--interval-start",
            args.interval_start,
            "--interval-end",
            args.interval_end,
            "--output-dir",
            str(raw_dir),
            *args.csv_paths,
        ]
    )

    if not raw_parquet.exists():
        raise FileNotFoundError(f"No encuentro el parquet crudo esperado: {raw_parquet}")

    run_cmd(
        [
            python_exe,
            "-m",
            "gait_analysis.reconstruct_hard_negative_spectrogram",
            "-i",
            str(raw_parquet),
            "--config",
            args.config,
            "-o",
            str(spec_parquet),
        ]
    )

    run_cmd(
        [
            python_exe,
            "-m",
            "gait_analysis.build_wide_dataset",
            "-i",
            str(spec_parquet),
            "-o",
            str(wide_parquet),
        ]
    )

    run_cmd(
        [
            python_exe,
            "-m",
            "gait_analysis.prepare_ml_dataset",
            "-i",
            str(wide_parquet),
            "-o",
            str(binary_parquet),
        ]
    )

    print()
    print("Bloque duro reconstruido correctamente.")
    print(f"Raw parquet: {raw_parquet}")
    print(f"Spectrogram parquet: {spec_parquet}")
    print(f"Wide parquet: {wide_parquet}")
    print(f"Binary parquet: {binary_parquet}")

    summary = {
        "reference": args.reference,
        "interval_start": args.interval_start,
        "interval_end": args.interval_end,
        "raw_parquet": str(raw_parquet),
        "spectrogram_parquet": str(spec_parquet),
        "wide_parquet": str(wide_parquet),
        "binary_parquet": str(binary_parquet),
        "csv_count": len(args.csv_paths),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
