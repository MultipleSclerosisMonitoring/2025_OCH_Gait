#!/usr/bin/env python3
"""Extract time-domain window features from Influx intervals."""

from __future__ import annotations

import argparse
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from gait_analysis.config import ConfigLoader
from gait_analysis.flux import FluxQueryBuilder
from gait_analysis.influx_service import InfluxService
from gait_analysis.resampling import Resampler
from gait_analysis.time_utils import TimeProcessor


TARGET_MAP = {"not_walking": 0, "walking": 1}


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Extrae features temporales por ventana usando la misma rejilla "
            "temporal que el pipeline espectral."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="CSV con Reference/from_time/until_time/use_for_main_dataset.",
    )
    p.add_argument(
        "-g",
        "--ground-truth",
        required=True,
        help="Excel con columnas Reference/datefrom/dateuntil/mov_type.",
    )
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Configuracion YAML del pipeline.",
    )
    p.add_argument(
        "-o",
        "--output",
        required=True,
        help="Parquet de salida con una fila por ventana.",
    )
    return p


def load_foot_dataframe(
    influx: InfluxService,
    cfg,
    *,
    reference: str,
    foot: str,
    from_time: str,
    until_time: str,
) -> pd.DataFrame:
    """Load one foot interval from Influx."""
    tz = cfg.default_tz or "Europe/Madrid"
    start_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(from_time, tz)
    stop_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(until_time, tz)
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
    return influx.tables_to_dataframe(tables)


def build_common_time_index(
    start_ts: pd.Timestamp,
    stop_ts: pd.Timestamp,
    resample_hz: float,
) -> pd.DatetimeIndex:
    """Build a common UTC index for both feet."""
    step_ms = int(round(1000.0 / resample_hz))
    return pd.date_range(start=start_ts, end=stop_ts, freq=f"{step_ms}ms", tz="UTC")


def safe_slope(values: np.ndarray) -> float:
    """Return a least-squares slope over sample index."""
    if values.size < 2:
        return 0.0
    x = np.arange(values.size, dtype=float)
    return float(np.polyfit(x, values, deg=1)[0])


def zero_crossing_rate(values: np.ndarray) -> float:
    """Return zero-crossing rate after removing the window mean."""
    if values.size < 2:
        return 0.0
    centered = values - float(np.mean(values))
    signs = np.signbit(centered)
    return float(np.mean(signs[1:] != signs[:-1]))


def signal_features(values: np.ndarray, prefix: str) -> dict[str, float]:
    """Compute robust time-domain features for one signal window."""
    values = values.astype(float)
    diffs = np.diff(values)
    abs_diffs = np.abs(diffs)
    return {
        f"{prefix}_mean": float(np.mean(values)),
        f"{prefix}_std": float(np.std(values, ddof=0)),
        f"{prefix}_min": float(np.min(values)),
        f"{prefix}_max": float(np.max(values)),
        f"{prefix}_median": float(np.median(values)),
        f"{prefix}_iqr": float(np.percentile(values, 75) - np.percentile(values, 25)),
        f"{prefix}_ptp": float(np.ptp(values)),
        f"{prefix}_rms": float(np.sqrt(np.mean(values**2))),
        f"{prefix}_energy": float(np.mean(values**2)),
        f"{prefix}_abs_mean": float(np.mean(np.abs(values))),
        f"{prefix}_zcr": zero_crossing_rate(values),
        f"{prefix}_slope": safe_slope(values),
        f"{prefix}_mean_abs_diff": float(np.mean(abs_diffs)) if diffs.size else 0.0,
        f"{prefix}_std_diff": float(np.std(diffs, ddof=0)) if diffs.size else 0.0,
        f"{prefix}_max_abs_diff": float(np.max(abs_diffs)) if diffs.size else 0.0,
    }


def paired_features(
    left_values: np.ndarray,
    right_values: np.ndarray,
    prefix: str,
) -> dict[str, float]:
    """Compute features comparing both feet for one signal."""
    if left_values.size != right_values.size or left_values.size < 2:
        return {
            f"{prefix}_corr": 0.0,
            f"{prefix}_mean_abs_diff": 0.0,
            f"{prefix}_rms_diff": 0.0,
            f"{prefix}_std_diff": 0.0,
        }
    diff = right_values.astype(float) - left_values.astype(float)
    if np.std(right_values) == 0 or np.std(left_values) == 0:
        corr = 0.0
    else:
        corr = np.corrcoef(right_values, left_values)[0, 1]
        if not np.isfinite(corr):
            corr = 0.0
    return {
        f"{prefix}_corr": float(corr),
        f"{prefix}_mean_abs_diff": float(np.mean(np.abs(diff))),
        f"{prefix}_rms_diff": float(np.sqrt(np.mean(diff**2))),
        f"{prefix}_std_diff": float(np.std(diff, ddof=0)),
    }


def add_magnitude_columns(df: pd.DataFrame, signals: list[str]) -> pd.DataFrame:
    """Add accelerometer and gyroscope vector magnitudes when components exist."""
    enriched = df.copy()
    groups = {
        "A_mag": ["Ax", "Ay", "Az"],
        "G_mag": ["Gx", "Gy", "Gz"],
    }
    for name, cols in groups.items():
        if all(col in signals and col in enriched.columns for col in cols):
            enriched[name] = np.sqrt(sum(enriched[col].astype(float) ** 2 for col in cols))
    return enriched


def label_center(
    gt: pd.DataFrame,
    reference: str,
    time_center: pd.Timestamp,
) -> str:
    """Return ground-truth label for a window center."""
    ref_gt = gt[gt["Reference"].eq(reference)]
    for _, row in ref_gt.iterrows():
        if row["datefrom"] <= time_center < row["dateuntil"]:
            return str(row["mov_type"])
    return "NO_LABEL"


def extract_interval_features(
    *,
    influx: InfluxService,
    cfg,
    gt: pd.DataFrame,
    reference: str,
    from_time: str,
    until_time: str,
) -> list[dict[str, object]]:
    """Extract temporal features for all valid centers in one interval."""
    spec_cfg = cfg.spectrogram
    tz = cfg.default_tz or "Europe/Madrid"
    requested_start_local = TimeProcessor.to_local_datetime(from_time, tz)
    requested_stop_local = TimeProcessor.to_local_datetime(until_time, tz)

    foot_data = {}
    for foot in spec_cfg.feet:
        df = load_foot_dataframe(
            influx,
            cfg,
            reference=reference,
            foot=foot,
            from_time=from_time,
            until_time=until_time,
        )
        if df.empty:
            return []
        foot_data[foot] = df

    foot_rs = {}
    foot_min = {}
    foot_max = {}
    for foot, df in foot_data.items():
        df_rs = Resampler.resample_dataframe(
            df,
            spec_cfg.resample_hz,
            spec_cfg.signals,
            max_interpolate_gap_s=spec_cfg.max_interpolate_gap_s,
        )
        if df_rs.empty:
            return []
        df_rs = add_magnitude_columns(df_rs, spec_cfg.signals)
        foot_rs[foot] = df_rs
        foot_min[foot] = df_rs.index.min()
        foot_max[foot] = df_rs.index.max()

    requested_start_ts = pd.Timestamp(
        requested_start_local.replace(tzinfo=ZoneInfo("UTC"))
    )
    requested_stop_ts = pd.Timestamp(requested_stop_local.replace(tzinfo=ZoneInfo("UTC")))
    start_common = max(requested_start_ts, max(foot_min.values()))
    stop_common = min(requested_stop_ts, min(foot_max.values()))
    if stop_common <= start_common:
        return []

    half_window = timedelta(seconds=spec_cfg.window_s / 2.0)
    start_center = start_common + half_window
    stop_center = stop_common - half_window
    if stop_center <= start_center:
        return []

    common_index = build_common_time_index(
        start_ts=start_common,
        stop_ts=stop_common,
        resample_hz=spec_cfg.resample_hz,
    )
    for foot in spec_cfg.feet:
        foot_rs[foot] = foot_rs[foot].reindex(common_index)

    centers_local = TimeProcessor.generate_window_centers(
        start_dt=start_center.to_pydatetime(),
        stop_dt=stop_center.to_pydatetime(),
        window_s=spec_cfg.window_s,
        delta_t_s=spec_cfg.delta_t_s,
    )

    expected_samples = int(round(spec_cfg.window_s * spec_cfg.resample_hz)) + 1
    feature_signals = [*spec_cfg.signals]
    if {"Ax", "Ay", "Az"}.issubset(set(spec_cfg.signals)):
        feature_signals.append("A_mag")
    if {"Gx", "Gy", "Gz"}.issubset(set(spec_cfg.signals)):
        feature_signals.append("G_mag")

    rows = []
    for center_local in centers_local:
        center_ts = pd.Timestamp(center_local)
        start_ts = center_ts - half_window
        stop_ts = center_ts + half_window
        windows = {}
        valid = True
        completeness_values = []

        for foot in spec_cfg.feet:
            window_df = foot_rs[foot].loc[start_ts:stop_ts]
            if window_df.empty or len(window_df) < expected_samples:
                valid = False
                break
            completeness = Resampler.window_sample_completeness(
                window_df,
                spec_cfg.signals,
            )
            if completeness < spec_cfg.min_window_completeness:
                valid = False
                break
            window_df = Resampler.fill_short_window_gaps(
                window_df.copy(),
                spec_cfg.resample_hz,
                spec_cfg.signals,
                spec_cfg.max_interpolate_gap_s,
            )
            window_df = add_magnitude_columns(window_df, spec_cfg.signals)
            if window_df[feature_signals].isna().any().any():
                valid = False
                break
            windows[foot] = window_df
            completeness_values.append(completeness)

        if not valid:
            continue

        mov_type = label_center(gt, reference, center_ts)
        if mov_type not in TARGET_MAP:
            continue

        row: dict[str, object] = {
            "reference": reference,
            "time_center": center_ts,
            "mov_type": mov_type,
            "target": TARGET_MAP[mov_type],
            "sample_completeness": float(np.mean(completeness_values)),
        }
        for foot in spec_cfg.feet:
            for signal in feature_signals:
                prefix = f"{foot}_{signal}"
                row.update(signal_features(windows[foot][signal].to_numpy(), prefix))

        if set(spec_cfg.feet) >= {"Left", "Right"}:
            for signal in feature_signals:
                row.update(
                    paired_features(
                        windows["Left"][signal].to_numpy(),
                        windows["Right"][signal].to_numpy(),
                        f"feet_{signal}",
                    )
                )

        rows.append(row)

    return rows


def main() -> None:
    """Extract temporal features for all selected intervals."""
    args = build_parser().parse_args()
    cfg = ConfigLoader(args.config).load()
    intervals = pd.read_csv(args.input)
    if "use_for_main_dataset" in intervals.columns:
        intervals = intervals[intervals["use_for_main_dataset"].eq(True)].copy()
    intervals = intervals.rename(
        columns={
            "from_time": "from_time",
            "until_time": "until_time",
        }
    )

    gt = pd.read_excel(args.ground_truth)
    gt["Reference"] = gt["Reference"].astype(str)
    gt["datefrom"] = pd.to_datetime(gt["datefrom"], utc=True)
    gt["dateuntil"] = pd.to_datetime(gt["dateuntil"], utc=True)
    gt["mov_type"] = gt["mov_type"].astype(str).str.strip()

    rows = []
    with InfluxService(cfg.influx) as influx:
        for _, interval in intervals.iterrows():
            reference = str(interval["Reference"])
            from_time = str(interval["from_time"])
            until_time = str(interval["until_time"])
            print("Extracting", reference, from_time, until_time)
            interval_rows = extract_interval_features(
                influx=influx,
                cfg=cfg,
                gt=gt,
                reference=reference,
                from_time=from_time,
                until_time=until_time,
            )
            print("Rows:", len(interval_rows))
            rows.extend(interval_rows)

    if not rows:
        raise ValueError("No se han generado features temporales.")

    output = pd.DataFrame(rows)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(output_path, index=False)

    feature_cols = [
        c for c in output.columns if c not in {"reference", "time_center", "mov_type", "target"}
    ]
    print(f"Output parquet: {output_path}")
    print(f"Rows: {len(output)}")
    print(f"Feature columns: {len(feature_cols)}")
    print()
    print("Target counts:")
    print(output["target"].value_counts().sort_index().to_string())
    print()
    print("References:")
    print(sorted(output["reference"].astype(str).unique().tolist()))


if __name__ == "__main__":
    main()
