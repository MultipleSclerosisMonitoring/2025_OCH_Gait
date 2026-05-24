#!/usr/bin/env python3
"""Reconstruct labeled spectrogram rows from raw CSV bundle exports.

The source bundles are one-signal-per-file CSV exports with second-precision
timestamps. This script rebuilds a per-foot time series, resamples it with the
project's standard pipeline, computes spectrogram rows, and labels every row as
not_walking so the bundle can be used as a hard-negative block.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from dataclasses import replace
from typing import Dict, List

import numpy as np
import pandas as pd

from gait_analysis.models import SpectrogramConfig
from gait_analysis.config import ConfigLoader
from gait_analysis.resampling import Resampler
from gait_analysis.spectrum import ParquetRowBuilder, PowerSpectrumEngine
from gait_analysis.time_utils import TimeProcessor


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Reconstruye espectrogramas etiquetados not_walking a partir de "
            "bundles CSV crudos de una sola señal por archivo."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        nargs="+",
        help="Uno o varios parquets raw_long generados por import_sensor_csv_bundle.",
    )
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Configuracion del espectrograma.",
    )
    p.add_argument(
        "-o",
        "--output",
        required=True,
        help="Parquet etiquetado long de salida.",
    )
    p.add_argument(
        "--label",
        default="not_walking",
        choices=["not_walking", "walking"],
        help="Etiqueta asignada a todo el bloque reconstruido.",
    )
    p.add_argument(
        "--min-window-completeness",
        type=float,
        default=0.03,
        help=(
            "Umbral minimo de completitud real para estos CSV reconstruidos. "
            "Debe ser mucho mas bajo que el del pipeline original porque la "
            "exportacion de origen es de baja densidad."
        ),
    )
    return p


def load_spec_config(config_path: Path) -> SpectrogramConfig:
    """Load the spectrogram section from a YAML config file."""
    config = ConfigLoader(str(config_path)).load()
    return config.spectrogram


def reconstruct_signal_time_series(signal_df: pd.DataFrame, signal: str) -> pd.DataFrame:
    """Rebuild pseudo-subsecond timestamps from second-precision samples."""
    ordered = signal_df.sort_values(["time", "sample_order"]).copy()
    ordered["time"] = pd.to_datetime(ordered["time"], format="mixed")

    rows = []
    for second_ts, group in ordered.groupby("time", sort=False):
        group = group.sort_values("sample_order")
        n = len(group)
        if n == 1:
            offsets = np.array([0.0], dtype=float)
        else:
            offsets = np.linspace(0.0, 1.0, n, endpoint=False, dtype=float)
        times = second_ts + pd.to_timedelta(offsets, unit="s")
        rows.append(
            pd.DataFrame(
                {
                    "_time": times,
                    signal: pd.to_numeric(group["value"], errors="coerce").to_numpy(),
                }
            )
        )

    if not rows:
        return pd.DataFrame(columns=["_time", signal])

    return pd.concat(rows, ignore_index=True)


def build_foot_frame(
    bundle: pd.DataFrame,
    foot: str,
    signals: List[str],
) -> pd.DataFrame:
    """Build one foot-specific wide time series from a raw bundle."""
    foot_rows = bundle[bundle["foot"].astype(str).eq(foot)].copy()
    if foot_rows.empty:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for signal in signals:
        sig_rows = foot_rows[foot_rows["signal"].astype(str).eq(signal)]
        if sig_rows.empty:
            continue
        frames.append(reconstruct_signal_time_series(sig_rows, signal))

    if not frames:
        return pd.DataFrame()

    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.merge(frame, on="_time", how="outer")

    return merged.sort_values("_time").reset_index(drop=True)


def process_bundle(
    bundle: pd.DataFrame,
    *,
    spec_cfg: SpectrogramConfig,
    label: str,
) -> pd.DataFrame:
    """Reconstruct one raw bundle into labeled spectrogram rows."""
    reference = str(bundle["reference"].iloc[0])
    interval_start = str(bundle["interval_start"].iloc[0])
    interval_end = str(bundle["interval_end"].iloc[0])

    foot_data: Dict[str, pd.DataFrame] = {}
    for foot in spec_cfg.feet:
        foot_df = build_foot_frame(bundle, foot, spec_cfg.signals)
        if foot_df.empty:
            return pd.DataFrame()
        foot_data[foot] = foot_df

    foot_rs: Dict[str, pd.DataFrame] = {}
    foot_min: Dict[str, pd.Timestamp] = {}
    foot_max: Dict[str, pd.Timestamp] = {}

    for foot, df in foot_data.items():
        df_rs = Resampler.resample_dataframe(
            df,
            spec_cfg.resample_hz,
            spec_cfg.signals,
            max_interpolate_gap_s=spec_cfg.max_interpolate_gap_s,
        )
        if df_rs.empty:
            return pd.DataFrame()
        foot_rs[foot] = df_rs
        foot_min[foot] = df_rs.index.min()
        foot_max[foot] = df_rs.index.max()

    requested_start_ts = pd.Timestamp(interval_start)
    requested_stop_ts = pd.Timestamp(interval_end)

    start_common = max(requested_start_ts, max(foot_min.values()))
    stop_common = min(requested_stop_ts, min(foot_max.values()))
    if stop_common <= start_common:
        return pd.DataFrame()

    half_window = pd.Timedelta(seconds=spec_cfg.window_s / 2.0)
    start_center = start_common + half_window
    stop_center = stop_common - half_window
    if stop_center <= start_center:
        return pd.DataFrame()

    common_index = pd.date_range(
        start=start_common,
        end=stop_common,
        freq=f"{int(round(1000.0 / spec_cfg.resample_hz))}ms",
    )
    for foot in spec_cfg.feet:
        foot_rs[foot] = foot_rs[foot].reindex(common_index)

    centers = TimeProcessor.generate_window_centers(
        start_dt=start_center.to_pydatetime(),
        stop_dt=stop_center.to_pydatetime(),
        window_s=spec_cfg.window_s,
        delta_t_s=spec_cfg.delta_t_s,
    )

    engine = PowerSpectrumEngine(spec_cfg)
    rows: list[dict[str, object]] = []
    for center_local in centers:
        center_ts = pd.Timestamp(center_local)
        start_ts = center_ts - half_window
        stop_ts = center_ts + half_window

        center_rows: list[dict[str, object]] = []
        center_valid = True
        for foot in spec_cfg.feet:
            window_df = foot_rs[foot].loc[start_ts:stop_ts]
            if window_df.empty:
                center_valid = False
                break

            available_signals = [s for s in spec_cfg.signals if s in window_df.columns]
            if not available_signals:
                center_valid = False
                break

            expected_samples = int(round(spec_cfg.window_s * spec_cfg.resample_hz)) + 1
            if len(window_df) < expected_samples:
                center_valid = False
                break

            completeness = Resampler.window_sample_completeness(window_df, available_signals)
            if completeness < spec_cfg.min_window_completeness:
                center_valid = False
                break

            window_df = Resampler.fill_short_window_gaps(
                window_df.copy(),
                spec_cfg.resample_hz,
                available_signals,
                spec_cfg.max_interpolate_gap_s,
            )
            if window_df[available_signals].isna().any().any():
                center_valid = False
                break

            freqs_ref: np.ndarray | None = None
            for signal_name in available_signals:
                signal_values = window_df[signal_name].to_numpy(dtype=float)
                if signal_values.size < 2:
                    continue
                freqs, powers = engine.compute(signal_values)
                freqs_ref = freqs
                row = ParquetRowBuilder.build_row(
                    reference=reference,
                    foot=foot,
                    signal_name=signal_name,
                    time_center=center_ts,
                    freqs=freqs,
                    powers=powers,
                )
                row["mov_type"] = label
                row["target"] = 0 if label == "not_walking" else 1
                row["sample_completeness"] = float(completeness)
                row["interval_start"] = interval_start
                row["interval_end"] = interval_end
                center_rows.append(row)

            if freqs_ref is None:
                center_valid = False
                break

            missing_signals = [s for s in spec_cfg.signals if s not in available_signals]
            for signal_name in missing_signals:
                row = ParquetRowBuilder.build_row(
                    reference=reference,
                    foot=foot,
                    signal_name=signal_name,
                    time_center=center_ts,
                    freqs=freqs_ref,
                    powers=np.zeros_like(freqs_ref, dtype=float),
                )
                row["mov_type"] = label
                row["target"] = 0 if label == "not_walking" else 1
                row["sample_completeness"] = float(completeness)
                row["interval_start"] = interval_start
                row["interval_end"] = interval_end
                center_rows.append(row)

        if center_valid:
            rows.extend(center_rows)

    return pd.DataFrame(rows)


def main() -> None:
    """Reconstruct one or more raw bundles into labeled spectrogram parquets."""
    args = build_parser().parse_args()
    input_paths = [Path(p) for p in args.input]
    output_path = Path(args.output)
    spec_cfg = load_spec_config(Path(args.config))
    spec_cfg = replace(spec_cfg, min_window_completeness=args.min_window_completeness)

    raw_frames = [pd.read_parquet(path) for path in input_paths]
    if any(frame.empty for frame in raw_frames):
        raise ValueError("Alguno de los parquets crudos de entrada está vacío.")
    raw = pd.concat(raw_frames, ignore_index=True)
    required_cols = {
        "reference",
        "interval_start",
        "interval_end",
        "foot",
        "signal",
        "sample_order",
        "time",
        "value",
    }
    missing = [c for c in required_cols if c not in raw.columns]
    if missing:
        raise ValueError(f"Faltan columnas en el bundle crudo: {missing}")

    group_cols = ["reference", "interval_start", "interval_end"]
    group_frames: list[pd.DataFrame] = []
    for _, group in raw.groupby(group_cols, sort=False):
        group_frames.append(process_bundle(group, spec_cfg=spec_cfg, label=args.label))

    out = pd.concat([frame for frame in group_frames if not frame.empty], ignore_index=True)
    if out.empty:
        raise ValueError("No se han generado filas espectrales a partir de los bundles.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output_path, index=False)

    print(f"Inputs: {len(input_paths)}")
    for path in input_paths:
        print(f" - {path}")
    print(f"Output parquet: {output_path}")
    print(f"Rows: {len(out)}")
    print(f"References: {sorted(out['reference'].dropna().astype(str).unique().tolist())}")
    print("mov_type counts:")
    print(out["mov_type"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
