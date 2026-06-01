#!/usr/bin/env python3
"""Helpers to filter rows and windows by exclusion intervals."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def _first_existing(columns: list[str], candidates: list[str]) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    raise ValueError(f"No se encontro ninguna columna valida entre: {candidates}")


def load_interval_exclusions(path: str | Path) -> pd.DataFrame:
    """Load an interval exclusion table and normalize timestamps to UTC."""
    exclusions = pd.read_csv(path).copy()
    if exclusions.empty:
        return exclusions

    columns = exclusions.columns.tolist()
    reference_col = _first_existing(columns, ["reference", "Reference"])
    start_col = _first_existing(
        columns,
        ["start_utc", "from_utc", "datefrom", "from_time", "segment_from_time"],
    )
    end_col = _first_existing(
        columns,
        ["end_utc", "until_utc", "dateuntil", "until_time", "segment_until_time"],
    )

    normalized = exclusions.rename(
        columns={
            reference_col: "reference",
            start_col: "start_utc",
            end_col: "end_utc",
        }
    )
    normalized["reference"] = normalized["reference"].astype(str)
    normalized["start_utc"] = pd.to_datetime(
        normalized["start_utc"], utc=True, format="mixed"
    )
    normalized["end_utc"] = pd.to_datetime(normalized["end_utc"], utc=True, format="mixed")
    return normalized


def _local_to_utc(series: pd.Series, timezone: str) -> pd.Series:
    """Parse timestamps in a local timezone and convert them to UTC."""
    parsed = pd.to_datetime(series, format="mixed", errors="raise")
    if getattr(parsed.dt, "tz", None) is None:
        parsed = parsed.dt.tz_localize(timezone)
    return parsed.dt.tz_convert("UTC")


def exclude_windows_by_interval(
    windows: pd.DataFrame,
    exclusions: pd.DataFrame,
    *,
    reference_col: str = "Reference",
    start_col: str = "from_time",
    end_col: str = "until_time",
    window_timezone: str | None = None,
) -> pd.DataFrame:
    """Drop configured windows that match any exclusion interval exactly."""
    if exclusions.empty:
        return windows.copy()

    selected = windows.copy()
    selected[reference_col] = selected[reference_col].astype(str)
    if window_timezone is None:
        selected[start_col] = pd.to_datetime(selected[start_col], utc=True, format="mixed")
        selected[end_col] = pd.to_datetime(selected[end_col], utc=True, format="mixed")
    else:
        selected[start_col] = _local_to_utc(selected[start_col], window_timezone)
        selected[end_col] = _local_to_utc(selected[end_col], window_timezone)

    keep = pd.Series(True, index=selected.index)
    for _, interval in exclusions.iterrows():
        keep &= ~(
            selected[reference_col].eq(str(interval["reference"]))
            & selected[start_col].eq(interval["start_utc"])
            & selected[end_col].eq(interval["end_utc"])
        )
    return selected[keep].reset_index(drop=True)


def exclude_predictions_by_interval(
    predictions: pd.DataFrame,
    exclusions: pd.DataFrame,
    *,
    reference_col: str = "reference",
    time_col: str = "time_center",
    segment_start_col: str = "segment_from_time",
    segment_end_col: str = "segment_until_time",
) -> pd.DataFrame:
    """Drop prediction rows that belong to any excluded interval."""
    if exclusions.empty:
        return predictions.copy()

    selected = predictions.copy()
    selected[reference_col] = selected[reference_col].astype(str)
    if time_col in selected.columns:
        selected[time_col] = pd.to_datetime(selected[time_col], utc=True, format="mixed")
    if segment_start_col in selected.columns:
        selected[segment_start_col] = pd.to_datetime(
            selected[segment_start_col], utc=True, format="mixed"
        )
    if segment_end_col in selected.columns:
        selected[segment_end_col] = pd.to_datetime(
            selected[segment_end_col], utc=True, format="mixed"
        )

    keep = pd.Series(True, index=selected.index)
    for _, interval in exclusions.iterrows():
        interval_mask = selected[reference_col].eq(str(interval["reference"]))
        if time_col in selected.columns:
            interval_mask &= selected[time_col].between(
                interval["start_utc"],
                interval["end_utc"],
                inclusive="both",
            )
        if segment_start_col in selected.columns and segment_end_col in selected.columns:
            interval_mask &= selected[segment_start_col].eq(interval["start_utc"])
            interval_mask &= selected[segment_end_col].eq(interval["end_utc"])
        keep &= ~interval_mask
    return selected[keep].reset_index(drop=True)
