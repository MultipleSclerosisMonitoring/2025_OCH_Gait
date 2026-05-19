from __future__ import annotations

from typing import List

import pandas as pd


class Resampler:
    """Resample time-indexed signals to a uniform sampling frequency."""

    OBSERVED_PREFIX = "observed_"

    @classmethod
    def observed_column(cls, signal: str) -> str:
        """Return the column name used to mark real observed samples."""
        return f"{cls.OBSERVED_PREFIX}{signal}"

    @staticmethod
    def resample_dataframe(
        df: pd.DataFrame,
        fs_hz: float,
        signals: List[str],
        max_interpolate_gap_s: float | None = None,
    ) -> pd.DataFrame:
        """Resample selected signal columns to a uniform frequency.

        Args:
            df: Input DataFrame with '_time' column.
            fs_hz: Target resampling frequency in Hz.
            signals: Signal names to keep and resample.
            max_interpolate_gap_s: Maximum gap filled by interpolation. Larger gaps
                remain missing so downstream window validation can reject them.

        Returns:
            Resampled DataFrame indexed by '_time'.

        Raises:
            ValueError: If '_time' column is missing.
        """
        if "_time" not in df.columns:
            raise ValueError("El DataFrame no contiene la columna '_time'.")

        existing_signals = [s for s in signals if s in df.columns]
        use_cols = ["_time"] + existing_signals
        out = df[use_cols].copy()
        out = out.set_index("_time").sort_index()

        freq_ms = int(round(1000.0 / fs_hz))
        rule = f"{freq_ms}ms"

        out = out.resample(rule).mean()
        observed = out[existing_signals].notna()
        for signal in existing_signals:
            out[Resampler.observed_column(signal)] = observed[signal].astype(float)

        if max_interpolate_gap_s is None or max_interpolate_gap_s <= 0:
            out[existing_signals] = (
                out[existing_signals].interpolate(method="time").ffill().bfill()
            )
            return out

        max_gap_samples = max(1, int(round(max_interpolate_gap_s * fs_hz)))
        out[existing_signals] = out[existing_signals].interpolate(
            method="time",
            limit=max_gap_samples,
            limit_area="inside",
        )
        return out

    @classmethod
    def window_sample_completeness(cls, df: pd.DataFrame, signals: List[str]) -> float:
        """Return real-sample density for a candidate window.

        Prefer observed-sample masks created before interpolation. If a caller
        passes legacy data without masks, fall back to non-null signal density.
        """
        observed_cols = [
            cls.observed_column(s)
            for s in signals
            if cls.observed_column(s) in df.columns
        ]
        if observed_cols:
            return float(df[observed_cols].mean().mean())
        existing_signals = [s for s in signals if s in df.columns]
        if not existing_signals:
            return 0.0
        return float(df[existing_signals].notna().mean().mean())

    @staticmethod
    def fill_short_window_gaps(
        df: pd.DataFrame,
        fs_hz: float,
        signals: List[str],
        max_interpolate_gap_s: float | None,
    ) -> pd.DataFrame:
        """Fill only short residual gaps inside an already-windowed dataframe.

        Larger gaps remain missing so the caller can reject the window instead
        of converting sensor dropouts into smooth low-frequency trajectories.
        """
        existing_signals = [s for s in signals if s in df.columns]
        if not existing_signals:
            return df

        if max_interpolate_gap_s is None or max_interpolate_gap_s <= 0:
            df[existing_signals] = df[existing_signals].interpolate(
                method="time",
                limit_area="inside",
            )
            return df

        max_gap_samples = max(1, int(round(max_interpolate_gap_s * fs_hz)))
        df[existing_signals] = df[existing_signals].interpolate(
            method="time",
            limit=max_gap_samples,
            limit_area="inside",
        )
        return df
