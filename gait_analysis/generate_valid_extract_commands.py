#!/usr/bin/env python3
"""Generate extraction commands for reference windows with confirmed Influx coverage."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Genera comandos de extracción para referencias con cobertura válida."
    )
    p.add_argument(
        "-i",
        "--input",
        default="experiment_configs/main_dataset_windows.csv",
        help="CSV con referencias, ventanas y columna has_data",
    )
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Ruta al fichero de configuración",
    )
    p.add_argument(
        "--output-dir",
        default="salidas_test/auto_extracts",
        help="Directorio de salida para los parquets generados",
    )
    return p


def main() -> None:
    """Read valid windows and print one extraction command per usable reference."""
    args = build_parser().parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    df = pd.read_csv(input_path)
    valid = df[df["use_for_main_dataset"] == True].copy()

    print(f"CSV de entrada: {input_path}")
    print(f"Referencias válidas: {len(valid)}")
    print()

    for _, row in valid.iterrows():
        ref = str(row["Reference"])
        from_time = str(row["from_time"])
        until_time = str(row["until_time"])
        safe_ref = ref.replace("-", "_")
        safe_from = from_time.replace("-", "").replace(":", "").replace(" ", "_")
        safe_until = until_time.replace("-", "").replace(":", "").replace(" ", "_")
        block_id = f"{safe_ref}_{safe_from}_{safe_until}"
        out_path = output_dir / f"{block_id}_window_1s.parquet"

        cmd = (
            "~/Library/Python/3.11/bin/poetry run python extract_influx_hdf5.py "
            f'--mode spectrogram --config {args.config} '
            f'-f "{from_time}" -u "{until_time}" -q "{ref}" '
            f'-o "{out_path}"'
        )
        print(cmd)


if __name__ == "__main__":
    main()
