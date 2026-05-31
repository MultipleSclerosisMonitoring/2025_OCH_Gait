#!/usr/bin/env python3
"""Generate reviewable walking/not_walking suggestions from raw gait blocks."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


SENSOR_COLUMNS = ["Ax", "Ay", "Az", "Gx", "Gy", "Gz"]


@dataclass(frozen=True)
class Thresholds:
    """Motion-score thresholds for one raw block."""

    low: float
    high: float


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Genera sugerencias revisables walking/not_walking desde bloques raw "
            "extraidos de InfluxDB. No escribe etiquetas finales: rellena "
            "suggested_mov_type y deja mov_type vacio."
        )
    )
    p.add_argument(
        "-i",
        "--input-dir",
        default="salidas_test/data_extension_round1/raw_blocks_first_success",
        help="Directorio con parquets raw por bloque.",
    )
    p.add_argument(
        "-o",
        "--output",
        default="experiment_configs/auto_label_suggestions_round1.csv",
        help="CSV de sugerencias revisables.",
    )
    p.add_argument(
        "--summary",
        default="experiment_configs/auto_label_suggestions_round1_summary.md",
        help="Resumen Markdown de la ejecucion.",
    )
    p.add_argument(
        "--timezone",
        default="Europe/Madrid",
        help="Zona horaria local para columnas *_local.",
    )
    p.add_argument(
        "--window-s",
        type=int,
        default=1,
        help="Tamano de ventana para calcular energia de movimiento.",
    )
    p.add_argument(
        "--min-segment-s",
        type=int,
        default=5,
        help="Duracion minima de un segmento sugerido.",
    )
    p.add_argument(
        "--low-quantile",
        type=float,
        default=0.25,
        help="Cuantil inferior usado para not_walking_candidate.",
    )
    p.add_argument(
        "--high-quantile",
        type=float,
        default=0.75,
        help="Cuantil superior usado para walking_candidate.",
    )
    p.add_argument(
        "--include-ambiguous",
        action="store_true",
        help="Incluye segmentos intermedios como ambiguous en la salida.",
    )
    return p


def safe_block_name(path: Path) -> str:
    """Return a stable block id from a raw parquet filename."""
    name = path.stem
    return re.sub(r"_raw$", "", name)


def require_columns(df: pd.DataFrame, path: Path) -> None:
    """Validate raw parquet schema."""
    required = {"reference", "foot", "_time", *SENSOR_COLUMNS}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path} no contiene columnas requeridas: {sorted(missing)}")


def robust_zscore(series: pd.Series) -> pd.Series:
    """Return a robust z-score using median absolute deviation."""
    median = series.median()
    mad = (series - median).abs().median()
    if pd.isna(mad) or mad == 0:
        std = series.std()
        if pd.isna(std) or std == 0:
            return pd.Series(np.zeros(len(series)), index=series.index)
        return (series - series.mean()) / std
    return 0.6745 * (series - median) / mad


def compute_motion_by_window(df: pd.DataFrame, window_s: int) -> pd.DataFrame:
    """Compute per-window motion scores from accelerometer and gyroscope energy."""
    require_columns(df, Path("<dataframe>"))
    data = df.copy()
    data["_time"] = pd.to_datetime(data["_time"], utc=True, errors="coerce")
    data = data.dropna(subset=["_time", "foot", *SENSOR_COLUMNS])
    if data.empty:
        return pd.DataFrame()

    data["acc_mag"] = np.sqrt(data["Ax"] ** 2 + data["Ay"] ** 2 + data["Az"] ** 2)
    data["gyro_mag"] = np.sqrt(data["Gx"] ** 2 + data["Gy"] ** 2 + data["Gz"] ** 2)
    data["window_start_utc"] = data["_time"].dt.floor(f"{window_s}s")

    per_foot = (
        data.groupby(["window_start_utc", "foot"], observed=True)
        .agg(
            acc_std=("acc_mag", "std"),
            gyro_std=("gyro_mag", "std"),
            samples=("_time", "size"),
        )
        .reset_index()
    )
    if per_foot.empty:
        return pd.DataFrame()

    per_foot["acc_std"] = per_foot["acc_std"].fillna(0.0)
    per_foot["gyro_std"] = per_foot["gyro_std"].fillna(0.0)
    per_foot["acc_score"] = robust_zscore(per_foot["acc_std"]).clip(lower=0)
    per_foot["gyro_score"] = robust_zscore(per_foot["gyro_std"]).clip(lower=0)
    per_foot["foot_motion_score"] = per_foot["acc_score"] + per_foot["gyro_score"]

    windows = (
        per_foot.groupby("window_start_utc", observed=True)
        .agg(
            motion_score=("foot_motion_score", "mean"),
            acc_std_mean=("acc_std", "mean"),
            gyro_std_mean=("gyro_std", "mean"),
            samples=("samples", "sum"),
            feet=("foot", "nunique"),
        )
        .reset_index()
        .sort_values("window_start_utc")
    )
    return windows


def compute_thresholds(windows: pd.DataFrame, low_quantile: float, high_quantile: float) -> Thresholds:
    """Compute low/high thresholds from one block."""
    scores = windows["motion_score"].replace([np.inf, -np.inf], np.nan).dropna()
    if scores.empty:
        return Thresholds(low=0.0, high=0.0)
    low = float(scores.quantile(low_quantile))
    high = float(scores.quantile(high_quantile))
    if high <= low:
        high = float(scores.max())
    return Thresholds(low=low, high=high)


def classify_windows(
    windows: pd.DataFrame,
    thresholds: Thresholds,
    include_ambiguous: bool,
) -> pd.DataFrame:
    """Assign a suggested movement class to each window."""
    out = windows.copy()
    out["suggested_mov_type"] = ""
    out.loc[out["motion_score"] <= thresholds.low, "suggested_mov_type"] = "not_walking"
    out.loc[out["motion_score"] >= thresholds.high, "suggested_mov_type"] = "walking"
    if include_ambiguous:
        out.loc[out["suggested_mov_type"] == "", "suggested_mov_type"] = "ambiguous"
    return out[out["suggested_mov_type"] != ""].copy()


def merge_segments(classified: pd.DataFrame, window_s: int, min_segment_s: int) -> pd.DataFrame:
    """Merge consecutive windows with the same suggested class."""
    if classified.empty:
        return classified

    data = classified.sort_values("window_start_utc").copy()
    previous_time = data["window_start_utc"].shift()
    previous_label = data["suggested_mov_type"].shift()
    gap = (data["window_start_utc"] - previous_time).dt.total_seconds().fillna(window_s)
    starts_new = (data["suggested_mov_type"] != previous_label) | (gap > window_s * 1.5)
    data["segment_id"] = starts_new.cumsum()

    segments = (
        data.groupby("segment_id", observed=True)
        .agg(
            label_from_utc=("window_start_utc", "min"),
            last_window_utc=("window_start_utc", "max"),
            suggested_mov_type=("suggested_mov_type", "first"),
            windows=("window_start_utc", "size"),
            motion_score_mean=("motion_score", "mean"),
            motion_score_min=("motion_score", "min"),
            motion_score_max=("motion_score", "max"),
            acc_std_mean=("acc_std_mean", "mean"),
            gyro_std_mean=("gyro_std_mean", "mean"),
            samples=("samples", "sum"),
            feet_min=("feet", "min"),
        )
        .reset_index(drop=True)
    )
    segments["label_until_utc"] = segments["last_window_utc"] + pd.to_timedelta(window_s, unit="s")
    segments["duration_s"] = (
        segments["label_until_utc"] - segments["label_from_utc"]
    ).dt.total_seconds()
    segments = segments[segments["duration_s"] >= min_segment_s].copy()
    return segments.drop(columns=["last_window_utc"])


def fmt_utc(series: pd.Series) -> pd.Series:
    """Format UTC timestamps as ISO-like strings with Z."""
    return series.dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt_local(series: pd.Series, timezone: str) -> pd.Series:
    """Format timestamps in a local timezone."""
    return series.dt.tz_convert(timezone).dt.strftime("%Y-%m-%d %H:%M:%S")


def build_rows_for_file(
    path: Path,
    timezone: str,
    window_s: int,
    min_segment_s: int,
    low_quantile: float,
    high_quantile: float,
    include_ambiguous: bool,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Build suggestion rows and a summary record for one raw parquet."""
    df = pd.read_parquet(path)
    require_columns(df, path)
    reference = str(df["reference"].dropna().iloc[0]) if not df["reference"].dropna().empty else ""
    block_id = safe_block_name(path)

    windows = compute_motion_by_window(df, window_s)
    if windows.empty:
        summary = {
            "source_raw": str(path),
            "Reference": reference,
            "review_block": block_id,
            "raw_rows": len(df),
            "windows": 0,
            "segments": 0,
            "status": "no_valid_windows",
        }
        return pd.DataFrame(), summary

    thresholds = compute_thresholds(windows, low_quantile, high_quantile)
    classified = classify_windows(windows, thresholds, include_ambiguous)
    segments = merge_segments(classified, window_s, min_segment_s)

    if segments.empty:
        summary = {
            "source_raw": str(path),
            "Reference": reference,
            "review_block": block_id,
            "raw_rows": len(df),
            "windows": len(windows),
            "segments": 0,
            "status": "no_segments_after_min_duration",
            "low_threshold": thresholds.low,
            "high_threshold": thresholds.high,
        }
        return pd.DataFrame(), summary

    segments.insert(0, "Reference", reference)
    segments.insert(1, "review_block", block_id)
    segments.insert(2, "source_raw", str(path))
    segments["label_from_local"] = fmt_local(segments["label_from_utc"], timezone)
    segments["label_until_local"] = fmt_local(segments["label_until_utc"], timezone)
    segments["label_from_utc"] = fmt_utc(segments["label_from_utc"])
    segments["label_until_utc"] = fmt_utc(segments["label_until_utc"])
    segments["mov_type"] = ""
    segments["label_quality"] = "auto_review"
    segments["review_notes"] = (
        "Sugerencia heuristica por energia de acelerometro/giroscopio; revisar en Grafana."
    )
    segments["low_threshold"] = thresholds.low
    segments["high_threshold"] = thresholds.high

    ordered_cols = [
        "Reference",
        "review_block",
        "source_raw",
        "label_from_local",
        "label_until_local",
        "label_from_utc",
        "label_until_utc",
        "suggested_mov_type",
        "mov_type",
        "label_quality",
        "review_notes",
        "duration_s",
        "windows",
        "samples",
        "feet_min",
        "motion_score_mean",
        "motion_score_min",
        "motion_score_max",
        "acc_std_mean",
        "gyro_std_mean",
        "low_threshold",
        "high_threshold",
    ]
    summary = {
        "source_raw": str(path),
        "Reference": reference,
        "review_block": block_id,
        "raw_rows": len(df),
        "windows": len(windows),
        "segments": len(segments),
        "walking_segments": int((segments["suggested_mov_type"] == "walking").sum()),
        "not_walking_segments": int((segments["suggested_mov_type"] == "not_walking").sum()),
        "status": "ok",
        "low_threshold": thresholds.low,
        "high_threshold": thresholds.high,
    }
    return segments[ordered_cols], summary


def markdown_table(df: pd.DataFrame) -> str:
    """Render a simple Markdown table."""
    if df.empty:
        return "_Sin filas._"
    rendered = df.astype(str)
    headers = list(rendered.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in rendered.iterrows():
        lines.append("| " + " | ".join(row[col] for col in headers) + " |")
    return "\n".join(lines)


def write_summary(path: Path, output: Path, rows: pd.DataFrame, summaries: pd.DataFrame) -> None:
    """Write a short Markdown audit summary."""
    counts = (
        rows.groupby(["Reference", "suggested_mov_type"], observed=True)
        .agg(segments=("suggested_mov_type", "size"), seconds=("duration_s", "sum"))
        .reset_index()
        if not rows.empty
        else pd.DataFrame(columns=["Reference", "suggested_mov_type", "segments", "seconds"])
    )
    lines = [
        "# Auto Label Suggestions",
        "",
        "These rows are review suggestions, not final ground truth.",
        "",
        f"- Output CSV: `{output}`",
        f"- Raw files processed: {len(summaries)}",
        f"- Suggestion rows: {len(rows)}",
        "",
        "## Counts",
        "",
        markdown_table(counts),
        "",
        "## Files",
        "",
        markdown_table(
            summaries[
                [
                    "Reference",
                    "review_block",
                    "raw_rows",
                    "windows",
                    "segments",
                    "status",
                ]
            ]
        ),
        "",
        "## Review Rule",
        "",
        "`suggested_mov_type` is inferred from robust per-block motion energy. "
        "`mov_type` is intentionally empty so the import script does not accept "
        "these rows until a human reviewer copies an accepted value into `mov_type`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Generate auto-label suggestions for all raw block parquets."""
    args = build_parser().parse_args()
    input_dir = Path(args.input_dir)
    output = Path(args.output)
    summary_path = Path(args.summary)
    raw_files = sorted(input_dir.glob("*.parquet"))
    if not raw_files:
        raise ValueError(f"No se han encontrado parquets raw en {input_dir}")

    all_rows: list[pd.DataFrame] = []
    summaries: list[dict[str, object]] = []
    for raw_file in raw_files:
        rows, summary = build_rows_for_file(
            raw_file,
            args.timezone,
            args.window_s,
            args.min_segment_s,
            args.low_quantile,
            args.high_quantile,
            args.include_ambiguous,
        )
        if not rows.empty:
            all_rows.append(rows)
        summaries.append(summary)

    result = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    summary_df = pd.DataFrame(summaries)

    output.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)
    write_summary(summary_path, output, result, summary_df)

    print(f"Input dir: {input_dir}")
    print(f"Raw files: {len(raw_files)}")
    print(f"Output: {output}")
    print(f"Rows: {len(result)}")
    if not result.empty:
        print(result.groupby("suggested_mov_type").size().to_string())
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
