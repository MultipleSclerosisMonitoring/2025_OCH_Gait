#!/usr/bin/env python3
"""Build visual plots for reviewing a ground-truth offset candidate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gait_analysis.config import ConfigLoader
from gait_analysis.flux import FluxQueryBuilder
from gait_analysis.influx_service import InfluxService
from gait_analysis.time_utils import TimeProcessor


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Genera graficos de revision visual para tramos donde un offset de "
            "ground truth corrige o mantiene falsos positivos."
        )
    )
    p.add_argument("--runs", required=True, help="CSV de rachas de revision.")
    p.add_argument("--rows", required=True, help="CSV fila a fila de revision.")
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Configuracion YAML con Influx y señales.",
    )
    p.add_argument(
        "--output-dir",
        default="results/offset_visual_review_plots",
        help="Directorio de PNGs.",
    )
    p.add_argument(
        "--manifest-output",
        default="results/ground_truth_offset_plus2s_visual_review_plot_manifest.csv",
    )
    p.add_argument("--top-n", type=int, default=8)
    p.add_argument("--buffer-seconds", type=float, default=10.0)
    p.add_argument("--threshold", type=float, default=0.80)
    return p


def timestamp_to_query_string(ts: pd.Timestamp) -> str:
    """Format a timestamp for this project's Influx query convention."""
    return ts.tz_convert("UTC").strftime("%Y-%m-%d %H:%M:%S")


def load_foot_dataframe(
    influx: InfluxService,
    cfg,
    *,
    reference: str,
    foot: str,
    start: pd.Timestamp,
    stop: pd.Timestamp,
) -> pd.DataFrame:
    """Load one foot raw interval from Influx."""
    tz = cfg.default_tz or "Europe/Madrid"
    start_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(
        timestamp_to_query_string(start),
        tz,
    )
    stop_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(
        timestamp_to_query_string(stop),
        tz,
    )
    flux = FluxQueryBuilder.build(
        bucket=cfg.influx.bucket,
        start_iso=start_iso,
        stop_iso=stop_iso,
        ref_tag=cfg.ref_tag,
        reference=reference,
        foot_tag=cfg.foot_tag,
        foot=foot,
        fields=cfg.spectrogram.signals,
        pivot=True,
    )
    tables = influx.query(flux)
    df = influx.tables_to_dataframe(tables)
    if df.empty:
        return df
    df = df.set_index("_time").sort_index()
    if {"Ax", "Ay", "Az"}.issubset(df.columns):
        df["A_mag"] = np.sqrt(df["Ax"] ** 2 + df["Ay"] ** 2 + df["Az"] ** 2)
    if {"Gx", "Gy", "Gz"}.issubset(df.columns):
        df["G_mag"] = np.sqrt(df["Gx"] ** 2 + df["Gy"] ** 2 + df["Gz"] ** 2)
    return df


def plot_run(
    *,
    run: pd.Series,
    review_rows: pd.DataFrame,
    raw_by_foot: dict[str, pd.DataFrame],
    output_path: Path,
    threshold: float,
) -> None:
    """Create one review plot."""
    run_start = pd.to_datetime(run["run_start"], utc=True, format="mixed")
    run_end = pd.to_datetime(run["run_end"], utc=True, format="mixed")
    reference = str(run["reference"])

    fig, axes = plt.subplots(3, 1, figsize=(13, 8), sharex=True)
    fig.suptitle(
        f"{reference} | {run['review_reason']} | "
        f"{run_start.strftime('%Y-%m-%d %H:%M:%S')} -> {run_end.strftime('%H:%M:%S')}",
        fontsize=11,
    )

    for foot, df in raw_by_foot.items():
        if df.empty:
            continue
        if "A_mag" in df.columns:
            axes[0].plot(df.index, df["A_mag"], label=f"{foot} A_mag", linewidth=0.9)
        if "G_mag" in df.columns:
            axes[1].plot(df.index, df["G_mag"], label=f"{foot} G_mag", linewidth=0.9)

    run_rows = review_rows[
        review_rows["reference"].astype(str).eq(reference)
        & review_rows["time_center"].between(run_start, run_end)
    ].sort_values("time_center")
    axes[2].plot(
        run_rows["time_center"],
        run_rows["prob_baseline"],
        label="prob walking offset 0s",
        marker="o",
        linewidth=1.0,
        markersize=2,
    )
    axes[2].plot(
        run_rows["time_center"],
        run_rows["prob_offset"],
        label="prob walking offset +2s",
        marker="o",
        linewidth=1.0,
        markersize=2,
    )
    axes[2].axhline(threshold, color="black", linestyle="--", linewidth=0.8)
    axes[2].set_ylim(-0.05, 1.05)

    for ax in axes:
        ax.axvspan(run_start, run_end, color="tab:red", alpha=0.10)
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper right", fontsize=8)
    axes[0].set_ylabel("A_mag")
    axes[1].set_ylabel("G_mag")
    axes[2].set_ylabel("prob")
    axes[2].set_xlabel("time")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    """Generate offset review plots."""
    args = build_parser().parse_args()
    cfg = ConfigLoader(args.config).load()
    runs = pd.read_csv(args.runs)
    rows = pd.read_csv(args.rows)
    rows["time_center"] = pd.to_datetime(rows["time_center"], utc=True, format="mixed")
    runs["run_start"] = pd.to_datetime(runs["run_start"], utc=True, format="mixed")
    runs["run_end"] = pd.to_datetime(runs["run_end"], utc=True, format="mixed")

    selected = runs.sort_values(["windows", "baseline_max_prob"], ascending=False).head(
        args.top_n
    )
    output_dir = Path(args.output_dir)
    manifest_rows = []
    buffer = pd.Timedelta(seconds=args.buffer_seconds)

    with InfluxService(cfg.influx) as influx:
        for idx, run in selected.reset_index(drop=True).iterrows():
            start = run["run_start"] - buffer
            stop = run["run_end"] + buffer
            raw_by_foot = {}
            for foot in cfg.spectrogram.feet:
                raw_by_foot[foot] = load_foot_dataframe(
                    influx,
                    cfg,
                    reference=str(run["reference"]),
                    foot=foot,
                    start=start,
                    stop=stop,
                )

            safe_ref = str(run["reference"]).replace("-", "_")
            safe_reason = str(run["review_reason"]).replace(" ", "_")
            output_path = output_dir / f"{idx + 1:02d}_{safe_ref}_{safe_reason}.png"
            plot_run(
                run=run,
                review_rows=rows,
                raw_by_foot=raw_by_foot,
                output_path=output_path,
                threshold=args.threshold,
            )
            manifest_rows.append(
                {
                    "plot": str(output_path),
                    "reference": run["reference"],
                    "review_reason": run["review_reason"],
                    "run_start": run["run_start"],
                    "run_end": run["run_end"],
                    "windows": int(run["windows"]),
                    "baseline_max_prob": float(run["baseline_max_prob"]),
                    "offset_max_prob": float(run["offset_max_prob"]),
                    "right_rows": int(len(raw_by_foot.get("Right", []))),
                    "left_rows": int(len(raw_by_foot.get("Left", []))),
                }
            )
            print(f"Saved {output_path}")

    manifest = pd.DataFrame(manifest_rows)
    manifest_output = Path(args.manifest_output)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(manifest_output, index=False)
    print(f"Manifest: {manifest_output}")


if __name__ == "__main__":
    main()
