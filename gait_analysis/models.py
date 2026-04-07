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
    """

    url: str
    org: str
    bucket: str
    token: str
    verify_ssl: bool = False


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
    """

    window_s: float
    delta_t_s: float
    fmax_hz: float
    window_type: str
    power_scale: str
    signals: List[str]
    feet: List[str]
    resample_hz: float


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
    """

    from_time: str
    until: str
    reference: str
    output: str
    from_tz: str
    config: str
    mode: str
    verbose: int