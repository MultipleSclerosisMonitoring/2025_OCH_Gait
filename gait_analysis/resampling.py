from __future__ import annotations

from typing import List

import pandas as pd


class Resampler:
    """Resample time-indexed signals to a uniform sampling frequency."""

    @staticmethod
    def resample_dataframe(df: pd.DataFrame, fs_hz: float, signals: List[str]) -> pd.DataFrame:
        """Resample selected signal columns to a uniform frequency.

        Args:
            df: Input DataFrame with '_time' column.
            fs_hz: Target resampling frequency in Hz.
            signals: Signal names to keep and resample.

        Returns:
            Resampled DataFrame indexed by '_time'.

        Raises:
            ValueError: If '_time' column is missing.
        """
        if "_time" not in df.columns:
            raise ValueError("El DataFrame no contiene la columna '_time'.")

        use_cols = ["_time"] + [s for s in signals if s in df.columns]
        out = df[use_cols].copy()
        out = out.set_index("_time").sort_index()

        freq_ms = int(round(1000.0 / fs_hz))
        rule = f"{freq_ms}ms"

        out = out.resample(rule).mean().interpolate(method="time").ffill().bfill()
        return out