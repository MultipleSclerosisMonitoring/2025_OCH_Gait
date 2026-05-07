#!/usr/bin/env python3
"""Run the main labeled-dataset pipeline from valid reference windows."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Ejecuta el pipeline principal de dataset a partir de referencias válidas."
    )
    p.add_argument(
        "-i",
        "--input",
        default="experiment_configs/main_dataset_windows.csv",
        help="CSV con ventanas y columna use_for_main_dataset",
    )
    p.add_argument(
        "-g",
        "--ground-truth",
        default="salidas_test/ground_truth_clean.xlsx",
        help="Excel limpio de ground truth",
    )
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Ruta al fichero de configuración del espectrograma",
    )
    p.add_argument(
        "--workdir",
        default="salidas_test/auto_extracts",
        help="Directorio de trabajo para artefactos intermedios y finales",
    )
    return p


def run_cmd(cmd: list[str]) -> None:
    """Run one subprocess command and stop on failure."""
    print(">>>", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    """Execute extraction, labeling, combination, wide conversion, and cleaning."""
    args = build_parser().parse_args()

    input_path = Path(args.input)
    ground_truth_path = Path(args.ground_truth)
    config_path = Path(args.config)
    workdir = Path(args.workdir)

    workdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)
    valid = df[df["use_for_main_dataset"] == True].copy()

    if valid.empty:
        raise ValueError("No hay referencias marcadas con use_for_main_dataset=True")

    python_exe = sys.executable

    filtered_paths: list[str] = []

    for _, row in valid.iterrows():
        ref = str(row["Reference"])
        from_time = str(row["from_time"])
        until_time = str(row["until_time"])
        safe_ref = ref.replace("-", "_")
        safe_from = from_time.replace("-", "").replace(":", "").replace(" ", "_")
        safe_until = until_time.replace("-", "").replace(":", "").replace(" ", "_")
        block_id = f"{safe_ref}_{safe_from}_{safe_until}"

        spectrogram_path = workdir / f"{block_id}_window_1s.parquet"
        labeled_path = workdir / f"{block_id}_window_1s_labeled.parquet"
        filtered_path = workdir / f"{block_id}_window_1s_labeled_filtered.parquet"

        run_cmd(
            [
                python_exe,
                "extract_influx_hdf5.py",
                "--mode",
                "spectrogram",
                "--config",
                str(config_path),
                "-f",
                from_time,
                "-u",
                until_time,
                "-q",
                ref,
                "-o",
                str(spectrogram_path),
            ]
        )

        run_cmd(
            [
                python_exe,
                "gait_analysis/label_spectrogram_with_ground_truth.py",
                "-i",
                str(spectrogram_path),
                "-g",
                str(ground_truth_path),
                "-o",
                str(labeled_path),
            ]
        )

        filtered_paths.append(str(filtered_path))

    combined_path = workdir / "main_combined_labeled_dataset.parquet"
    run_cmd(
        [
            python_exe,
            "gait_analysis/combine_labeled_datasets.py",
            "-i",
            *filtered_paths,
            "-o",
            str(combined_path),
        ]
    )

    wide_path = workdir / "main_combined_labeled_dataset_wide.parquet"
    run_cmd(
        [
            python_exe,
            "gait_analysis/build_wide_dataset.py",
            "-i",
            str(combined_path),
            "-o",
            str(wide_path),
        ]
    )

    wide_clean_path = workdir / "main_combined_labeled_dataset_wide_clean.parquet"
    run_cmd(
        [
            python_exe,
            "gait_analysis/clean_wide_dataset.py",
            "-i",
            str(wide_path),
            "-o",
            str(wide_clean_path),
        ]
    )

    binary_features_path = workdir / "main_binary_window_features.parquet"
    run_cmd(
        [
            python_exe,
            "gait_analysis/prepare_ml_dataset.py",
            "-i",
            str(wide_clean_path),
            "-o",
            str(binary_features_path),
        ]
    )

    print()
    print("Pipeline completado.")
    print(f"Dataset long combinado: {combined_path}")
    print(f"Dataset wide: {wide_path}")
    print(f"Dataset wide limpio: {wide_clean_path}")
    print(f"Dataset binario ML: {binary_features_path}")


if __name__ == "__main__":
    main()
