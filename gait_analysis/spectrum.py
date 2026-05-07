from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd
from scipy.signal import get_window, periodogram

from gait_analysis.models import SpectrogramConfig


class PowerSpectrumEngine:
    """Compute power spectra on centered windows."""

    def __init__(self, spec_cfg: SpectrogramConfig) -> None:
        """Initialize and cache invariant spectral vectors.

        Args:
            spec_cfg: Spectral analysis configuration.
        """
        self._cfg = spec_cfg
        self._expected_samples = int(round(spec_cfg.window_s * spec_cfg.resample_hz)) + 1
        self._window = get_window(spec_cfg.window_type, self._expected_samples)
        all_freqs = np.fft.rfftfreq(
            self._expected_samples,
            d=1.0 / spec_cfg.resample_hz,
        )
        self._freq_mask = all_freqs <= spec_cfg.fmax_hz
        self._freqs = all_freqs[self._freq_mask]

    def compute(self, signal_values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Compute power spectrum for one windowed signal.

        Args:
            signal_values: One-dimensional signal values inside the analysis window.

        Returns:
            Tuple (freqs, powers) after filtering frequencies above fmax_hz.

        Raises:
            ValueError: If the input signal is empty.
            ValueError: If the input length does not match the configured full window.
        """
        if signal_values.size == 0:
            raise ValueError("La señal de entrada está vacía.")
        if signal_values.size != self._expected_samples:
            raise ValueError(
                "La señal de entrada no coincide con la ventana completa esperada: "
                f"{signal_values.size} != {self._expected_samples}."
            )

        _, powers = periodogram(
            signal_values,
            fs=self._cfg.resample_hz,
            window=self._window,
            scaling="density",
            detrend="constant",
        )

        powers = powers[self._freq_mask]

        if self._cfg.power_scale.lower() == "db":
            powers = 10.0 * np.log10(powers + 1e-12)

        return self._freqs, powers


class ParquetRowBuilder:
    """Build parquet rows from spectral results."""

    @staticmethod
    def build_row(
        reference: str,
        foot: str,
        signal_name: str,
        time_center: pd.Timestamp,
        freqs: np.ndarray,
        powers: np.ndarray,
    ) -> Dict[str, Any]:
        """Build one parquet row.

        Args:
            reference: Reference identifier.
            foot: Foot label.
            signal_name: Processed signal name.
            time_center: Center time of the analysis window.
            freqs: Frequency vector.
            powers: Power vector for the given center.

        Returns:
            Dictionary representing one parquet row.
        """
        row: Dict[str, Any] = {
            "reference": reference,
            "foot": foot,
            "signal": signal_name,
            "time_center": time_center.isoformat(),
        }

        for i, (f, p) in enumerate(zip(freqs, powers)):
            row[f"f_{i:03d}_hz"] = float(f)
            row[f"p_{i:03d}"] = float(p)

        return row
