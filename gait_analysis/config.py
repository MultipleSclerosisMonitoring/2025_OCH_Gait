from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ModuleNotFoundError:
    yaml = None

from gait_analysis.models import AppConfig, InfluxConfig, SpectrogramConfig


def _parse_scalar(value: str) -> Any:
    """Parse the scalar subset used by the project config."""
    value = value.strip()
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _load_simple_yaml(path: Path) -> Dict[str, Any]:
    """Load the small YAML subset used by .config.yaml without PyYAML."""
    root: Dict[str, Any] = {}
    current_section: Optional[Dict[str, Any]] = None
    current_list_key: Optional[str] = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line:
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0 and stripped.endswith(":"):
            section_name = stripped[:-1]
            current_section = {}
            root[section_name] = current_section
            current_list_key = None
            continue

        if current_section is None:
            continue

        if stripped.startswith("- ") and current_list_key is not None:
            current_section[current_list_key].append(_parse_scalar(stripped[2:]))
            continue

        if ":" not in stripped:
            continue

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            current_section[key] = _parse_scalar(value)
            current_list_key = None
        else:
            current_section[key] = []
            current_list_key = key

    return root


class ConfigLoader:
    """Loads YAML configuration from a file."""

    def __init__(self, config_path: str) -> None:
        """Initialize loader.

        Args:
            config_path: Path to config file.
        """
        self._path = Path(config_path)

    def load(self) -> AppConfig:
        """Load configuration and validate required fields.

        Returns:
            AppConfig with InfluxDB, tags, timezone, and spectral settings.

        Raises:
            FileNotFoundError: If config file does not exist.
            ValueError: If required fields are missing.
        """
        if not self._path.exists():
            raise FileNotFoundError(
                f"No encuentro {self._path.resolve()}. "
                "Revisa la ruta o pásalo con --config."
            )

        if yaml is not None:
            with self._path.open("r", encoding="utf-8") as f:
                cfg: Dict[str, Any] = yaml.safe_load(f) or {}
        else:
            cfg = _load_simple_yaml(self._path)

        influx_raw = cfg.get("influxdb") or {}
        required_influx = ["url", "org", "bucket", "token"]
        missing_influx = [k for k in required_influx if k not in influx_raw]
        if missing_influx:
            raise ValueError(
                f"Faltan campos en 'influxdb': {missing_influx}. Revisa {self._path}."
            )

        influx = InfluxConfig(
            url=influx_raw["url"],
            org=influx_raw["org"],
            bucket=influx_raw["bucket"],
            token=influx_raw["token"],
            verify_ssl=bool(influx_raw.get("verify_ssl", False)),
            timeout=int(influx_raw.get("timeout", 10000)),
        )

        default_tz = (cfg.get("Location") or {}).get("zoneInfo")

        tags_raw = cfg.get("tags") or {}
        ref_tag = tags_raw.get("ref_tag", "reference")
        foot_tag = tags_raw.get("foot_tag", "Foot")

        spec_raw = cfg.get("spectrogram") or {}
        required_spec = [
            "window_s",
            "delta_t_s",
            "fmax_hz",
            "window_type",
            "power_scale",
            "signals",
            "feet",
            "resample_hz",
        ]
        missing_spec = [k for k in required_spec if k not in spec_raw]
        if missing_spec:
            raise ValueError(
                f"Faltan campos en 'spectrogram': {missing_spec}. Revisa {self._path}."
            )

        spectrogram = SpectrogramConfig(
            window_s=float(spec_raw["window_s"]),
            delta_t_s=float(spec_raw["delta_t_s"]),
            fmax_hz=float(spec_raw["fmax_hz"]),
            window_type=str(spec_raw["window_type"]),
            power_scale=str(spec_raw["power_scale"]),
            signals=list(spec_raw["signals"]),
            feet=list(spec_raw["feet"]),
            resample_hz=float(spec_raw["resample_hz"]),
            detrend=str(spec_raw.get("detrend", "linear")),
            max_interpolate_gap_s=float(spec_raw.get("max_interpolate_gap_s", 0.25)),
            min_window_completeness=float(
                spec_raw.get("min_window_completeness", 0.95)
            ),
        )

        return AppConfig(
            influx=influx,
            default_tz=default_tz,
            ref_tag=ref_tag,
            foot_tag=foot_tag,
            spectrogram=spectrogram,
        )
