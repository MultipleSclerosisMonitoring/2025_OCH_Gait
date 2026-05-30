from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class InfluxConfig:
    """InfluxDB connection configuration.

    Attributes:
        url: InfluxDB server URL.
        org: Organization name.
        bucket: Bucket name.
        token: Access token.
        verify_ssl: Whether SSL certificates are verified.
        timeout: HTTP timeout in milliseconds.
    """

    url: str
    org: str
    bucket: str
    token: str
    verify_ssl: bool = False
    timeout: int = 10000

    def __post_init__(self) -> None:
        """Validate InfluxDB connection values.

        Raises:
            ValueError: If any required connection field is empty.
        """
        for field_name in ["url", "org", "bucket", "token"]:
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"influxdb.{field_name} no puede estar vacío.")


@dataclass(frozen=True)
class SpectrogramConfig:
    """Spectral analysis configuration.

    Attributes:
        window_s: Duration of each centered analysis window in seconds.
        delta_t_s: Step between consecutive window centers in seconds.
        fmax_hz: Maximum frequency kept in the spectrum.
        window_type: Window function name, e.g. 'hann'.
        power_scale: Power representation, e.g. 'db' or 'linear'.
        signals: Signal names to process.
        feet: Foot labels to process.
        resample_hz: Resampling frequency in Hz.
        detrend: Baseline correction applied before periodogram.
        max_interpolate_gap_s: Maximum sensor gap filled by interpolation.
        min_window_completeness: Minimum real-sample completeness per window.
    """

    window_s: float
    delta_t_s: float
    fmax_hz: float
    window_type: str
    power_scale: str
    signals: List[str]
    feet: List[str]
    resample_hz: float
    detrend: str = "linear"
    max_interpolate_gap_s: float = 0.25
    min_window_completeness: float = 0.95

    def __post_init__(self) -> None:
        """Validate spectral analysis values.

        Raises:
            ValueError: If numeric values are invalid or required lists are empty.
        """
        if self.window_s <= 0:
            raise ValueError("spectrogram.window_s debe ser mayor que 0.")
        if self.delta_t_s <= 0:
            raise ValueError("spectrogram.delta_t_s debe ser mayor que 0.")
        if self.resample_hz <= 0:
            raise ValueError("spectrogram.resample_hz debe ser mayor que 0.")
        if self.fmax_hz <= 0:
            raise ValueError("spectrogram.fmax_hz debe ser mayor que 0.")
        nyquist_hz = self.resample_hz / 2.0
        if self.fmax_hz > nyquist_hz:
            raise ValueError(
                "spectrogram.fmax_hz no puede superar la frecuencia de Nyquist "
                f"({nyquist_hz:g} Hz)."
            )
        if not self.window_type.strip():
            raise ValueError("spectrogram.window_type no puede estar vacío.")
        if self.power_scale.lower() not in {"db", "linear"}:
            raise ValueError("spectrogram.power_scale debe ser 'db' o 'linear'.")
        if self.detrend.lower() not in {"constant", "linear", "none"}:
            raise ValueError(
                "spectrogram.detrend debe ser 'constant', 'linear' o 'none'."
            )
        if self.max_interpolate_gap_s < 0:
            raise ValueError("spectrogram.max_interpolate_gap_s no puede ser negativo.")
        if not 0 < self.min_window_completeness <= 1:
            raise ValueError(
                "spectrogram.min_window_completeness debe estar en el intervalo (0, 1]."
            )
        if not self.signals:
            raise ValueError("spectrogram.signals debe contener al menos una señal.")
        if not self.feet:
            raise ValueError("spectrogram.feet debe contener al menos un pie.")
        if any(not str(signal).strip() for signal in self.signals):
            raise ValueError("spectrogram.signals contiene nombres vacíos.")
        if any(not str(foot).strip() for foot in self.feet):
            raise ValueError("spectrogram.feet contiene nombres vacíos.")


@dataclass(frozen=True)
class AppConfig:
    """Application configuration loaded from YAML.

    Attributes:
        influx: InfluxDB configuration.
        default_tz: Optional default timezone name from YAML.
        ref_tag: InfluxDB tag key for reference.
        foot_tag: InfluxDB tag key for foot.
        spectrogram: Spectral analysis configuration.
    """

    influx: InfluxConfig
    default_tz: Optional[str]
    ref_tag: str
    foot_tag: str
    spectrogram: SpectrogramConfig


@dataclass(frozen=True)
class CliArgs:
    """Parsed CLI arguments.

    Attributes:
        from_time: Start datetime (local timezone) as string.
        until: End datetime (local timezone) as string.
        reference: Reference identifier.
        output: Output file path.
        from_tz: Timezone for input datetimes if config does not provide one.
        config: YAML configuration path.
        mode: Execution mode: 'count' or 'spectrogram'.
        verbose: Verbosity level.
        dry_run: Whether to print Flux queries without contacting InfluxDB.
        core_from_time: Optional central chunk start for anchored processing.
        core_until: Optional central chunk stop for anchored processing.
        center_anchor_time: Optional first window center used to align chunks.
    """

    from_time: str
    until: str
    reference: str
    output: str
    from_tz: str
    config: str
    mode: str
    verbose: int
    dry_run: bool = False
    core_from_time: Optional[str] = None
    core_until: Optional[str] = None
    center_anchor_time: Optional[str] = None
    window_s: Optional[float] = None
    min_window_completeness: Optional[float] = None
    max_interpolate_gap_s: Optional[float] = None
