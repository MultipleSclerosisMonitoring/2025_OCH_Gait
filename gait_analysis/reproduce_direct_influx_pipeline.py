#!/usr/bin/env python3
"""Reproduce the direct-Influx gait pipeline end to end.

This script is the reproducible entry point for the current direct-Influx
walking-enriched dataset. It:

1. reads a UTC ground-truth CSV with labeled intervals,
2. extracts each interval from InfluxDB directly with Flux,
3. labels each extracted spectrogram block,
4. combines and cleans the labeled datasets,
5. prepares the binary ML table,
6. runs the RF/XGBoost/CatBoost CV=3 comparison,
7. trains the final RF model,
8. evaluates the final RF with temporal blocks.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Reproduce the direct-Influx walking pipeline end to end."
    )
    p.add_argument(
        "-g",
        "--ground-truth",
        default="experiment_configs/reproducible_direct_influx_ground_truth_utc.csv",
        help="CSV UTC con columnas Reference, datefrom, dateuntil, mov_type.",
    )
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s_manual_newpatients.yaml",
        help="Ruta al YAML de configuracion del espectrograma.",
    )
    p.add_argument(
        "--from-tz",
        default="Europe/Madrid",
        help="Zona horaria local usada para las consultas a InfluxDB.",
    )
    p.add_argument(
        "--workdir",
        default="salidas_test/reproducible_direct_influx",
        help="Directorio de trabajo para los artefactos intermedios.",
    )
    p.add_argument(
        "--results-dir",
        default="results",
        help="Directorio para CSV/MD/JSON de resultados.",
    )
    p.add_argument(
        "--models-dir",
        default="models",
        help="Directorio para guardar el modelo final.",
    )
    p.add_argument(
        "--cache-dir",
        default=None,
        help="Directorio opcional con parquets ya generados reutilizables.",
    )
    p.add_argument(
        "--resume-existing",
        action="store_true",
        help="Reutiliza artefactos ya generados dentro del workdir.",
    )
    p.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Numero de intentos por comando antes de fallar.",
    )
    p.add_argument(
        "--retry-sleep-seconds",
        type=float,
        default=10.0,
        help="Segundos de espera entre reintentos.",
    )
    return p


def run_cmd(cmd: list[str], retries: int, retry_sleep_seconds: float) -> None:
    """Run a subprocess command with retries."""
    attempts = max(1, retries)
    for attempt in range(1, attempts + 1):
        print(">>>", " ".join(cmd))
        try:
            subprocess.run(cmd, check=True)
            return
        except subprocess.CalledProcessError:
            if attempt >= attempts:
                raise
            print(
                f">>> Command failed; retrying in {retry_sleep_seconds:g}s "
                f"({attempt + 1}/{attempts})"
            )
            time.sleep(retry_sleep_seconds)


def _safe_fragment(ts: pd.Timestamp) -> str:
    """Return a filename-friendly local timestamp fragment."""
    return ts.strftime("%Y%m%dT%H%M%S")


def _localize_utc_to_tz(ts: pd.Series, tz_name: str) -> pd.Series:
    """Convert a UTC-aware timestamp series to naive local wall-clock strings."""
    tz = ZoneInfo(tz_name)
    localized = ts.dt.tz_convert(tz).dt.tz_localize(None)
    return localized


def main() -> None:
    """Rebuild the direct-Influx dataset and retrain/evaluate the models."""
    args = build_parser().parse_args()

    ground_truth_path = Path(args.ground_truth)
    config_path = Path(args.config)
    workdir = Path(args.workdir)
    results_dir = Path(args.results_dir)
    models_dir = Path(args.models_dir)
    cache_dir = Path(args.cache_dir) if args.cache_dir else None

    workdir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    gt = pd.read_csv(ground_truth_path)
    required_cols = {"Reference", "datefrom", "dateuntil", "mov_type"}
    missing_cols = required_cols - set(gt.columns)
    if missing_cols:
        raise ValueError(f"Faltan columnas en ground truth: {sorted(missing_cols)}")

    gt["datefrom"] = pd.to_datetime(gt["datefrom"], utc=True, format="mixed")
    gt["dateuntil"] = pd.to_datetime(gt["dateuntil"], utc=True, format="mixed")
    gt = gt.sort_values(["Reference", "datefrom", "dateuntil", "mov_type"]).reset_index(
        drop=True
    )
    gt_before = len(gt)
    gt = gt.drop_duplicates(subset=["Reference", "datefrom", "dateuntil", "mov_type"])
    if len(gt) != gt_before:
        print(
            f">>> Ground truth deduplicated: {gt_before} -> {len(gt)} rows "
            "(Reference/datefrom/dateuntil/mov_type)"
        )

    python_exe = sys.executable
    filtered_paths: list[str] = []

    def cached_path(path: Path) -> Path | None:
        if cache_dir is None:
            return None
        candidate = cache_dir / path.name
        if candidate.exists():
            return candidate
        return None

    for ref, ref_gt in gt.groupby("Reference", sort=False):
        ref_gt = ref_gt.copy().reset_index(drop=True)
        for idx, row in ref_gt.iterrows():
            from_utc = pd.Timestamp(row["datefrom"]).tz_convert("UTC")
            until_utc = pd.Timestamp(row["dateuntil"]).tz_convert("UTC")
            local_from = _localize_utc_to_tz(pd.Series([from_utc]), args.from_tz).iloc[0]
            local_until = _localize_utc_to_tz(pd.Series([until_utc]), args.from_tz).iloc[0]

            safe_ref = str(ref).replace("-", "_")
            block_id = (
                f"{safe_ref}_{_safe_fragment(pd.Timestamp(local_from))}_"
                f"{_safe_fragment(pd.Timestamp(local_until))}"
            )
            spectrogram_path = workdir / f"{block_id}_ws1_manual.parquet"
            labeled_path = workdir / f"{block_id}_ws1_manual_labeled.parquet"
            filtered_path = workdir / f"{block_id}_ws1_manual_labeled_filtered.parquet"

            cached_filtered = cached_path(filtered_path)
            if args.resume_existing and filtered_path.exists():
                print(f">>> Reusing existing filtered parquet: {filtered_path}")
                filtered_paths.append(str(filtered_path))
                continue
            if cached_filtered is not None:
                print(f">>> Reusing cached filtered parquet: {cached_filtered}")
                filtered_paths.append(str(cached_filtered))
                continue

            if args.resume_existing and spectrogram_path.exists():
                print(f">>> Reusing existing spectrogram parquet: {spectrogram_path}")
            else:
                extraction_cmd = [
                    python_exe,
                    "extract_influx_hdf5.py",
                    "--mode",
                    "spectrogram",
                    "--config",
                    str(config_path),
                    "--from-tz",
                    args.from_tz,
                    "-f",
                    local_from.strftime("%Y-%m-%d %H:%M:%S"),
                    "-u",
                    local_until.strftime("%Y-%m-%d %H:%M:%S"),
                    "-q",
                    str(ref),
                    "-o",
                    str(spectrogram_path),
                ]
                run_cmd(
                    extraction_cmd,
                    retries=args.retries,
                    retry_sleep_seconds=args.retry_sleep_seconds,
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
                ],
                retries=args.retries,
                retry_sleep_seconds=args.retry_sleep_seconds,
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
        ],
        retries=args.retries,
        retry_sleep_seconds=args.retry_sleep_seconds,
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
        ],
        retries=args.retries,
        retry_sleep_seconds=args.retry_sleep_seconds,
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
        ],
        retries=args.retries,
        retry_sleep_seconds=args.retry_sleep_seconds,
    )

    binary_path = workdir / "main_binary_window_features.parquet"
    run_cmd(
        [
            python_exe,
            "gait_analysis/prepare_ml_dataset.py",
            "-i",
            str(wide_clean_path),
            "-o",
            str(binary_path),
        ],
        retries=args.retries,
        retry_sleep_seconds=args.retry_sleep_seconds,
    )

    cv_fold_output = results_dir / "reproducible_direct_influx_cv3_folds.csv"
    cv_summary_output = results_dir / "reproducible_direct_influx_cv3_summary.csv"
    run_cmd(
        [
            python_exe,
            "gait_analysis/run_ml_model_comparison_cv3.py",
            "-i",
            str(binary_path),
            "--fold-output",
            str(cv_fold_output),
            "--summary-output",
            str(cv_summary_output),
        ],
        retries=args.retries,
        retry_sleep_seconds=args.retry_sleep_seconds,
    )

    final_model_output = models_dir / "final_random_forest_model_reproducible_direct_influx.joblib"
    final_summary_output = results_dir / "final_random_forest_model_reproducible_direct_influx.json"
    run_cmd(
        [
            python_exe,
            "gait_analysis/train_final_model.py",
            "-i",
            str(binary_path),
            "-m",
            str(final_model_output),
            "-s",
            str(final_summary_output),
        ],
        retries=args.retries,
        retry_sleep_seconds=args.retry_sleep_seconds,
    )

    eval_fold_output = results_dir / "final_model_reproducible_direct_influx_grouped_cv.csv"
    eval_pred_output = results_dir / "final_model_reproducible_direct_influx_predictions.csv"
    eval_importance_output = results_dir / "final_model_reproducible_direct_influx_importance.csv"
    eval_summary_output = results_dir / "final_model_reproducible_direct_influx_evaluation.json"
    run_cmd(
        [
            python_exe,
            "gait_analysis/evaluate_final_model.py",
            "-i",
            str(binary_path),
            "-m",
            str(final_model_output),
            "--fold-output",
            str(eval_fold_output),
            "--prediction-output",
            str(eval_pred_output),
            "--importance-output",
            str(eval_importance_output),
            "--summary-output",
            str(eval_summary_output),
        ],
        retries=args.retries,
        retry_sleep_seconds=args.retry_sleep_seconds,
    )

    summary_path = results_dir / "direct_influx_reproducible_pipeline_summary.md"
    summary_path.write_text(
        "\n".join(
            [
                "# Direct Influx reproducible pipeline",
                "",
                f"- Ground truth: `{ground_truth_path}`",
                f"- Workdir: `{workdir}`",
                f"- Binary dataset: `{binary_path}`",
                f"- CV3 summary: `{cv_summary_output}`",
                f"- Final model: `{final_model_output}`",
                f"- Final evaluation: `{eval_summary_output}`",
                "",
                "This run reproduces the current direct-Influx walking-enriched pipeline from a single ground-truth CSV.",
            ]
        ),
        encoding="utf-8",
    )

    print()
    print("Pipeline reproducible completado.")
    print(f"Ground truth: {ground_truth_path}")
    print(f"Combined dataset: {combined_path}")
    print(f"Wide dataset: {wide_path}")
    print(f"Binary dataset: {binary_path}")
    print(f"CV3 summary: {cv_summary_output}")
    print(f"Final model: {final_model_output}")
    print(f"Final evaluation: {eval_summary_output}")
    print(f"Summary note: {summary_path}")


if __name__ == "__main__":
    main()
