from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ModuleNotFoundError:
    yaml = None

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

from gait_analysis.models import AppConfig, InfluxConfig, SpectrogramConfig

# Carga las variables de entorno desde un fichero .env en la raiz del
# repositorio (si existe), siguiendo la recomendacion del tutor de no
# guardar credenciales ni siquiera como placeholder en el .config.yaml
# versionado. .env esta en .gitignore y nunca debe subirse a git; ver
# .env.example para la plantilla de las variables esperadas.
if load_dotenv is not None:
    _dotenv_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=_dotenv_path)


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


def _resolve_secret(value: Any, env_var: str) -> str:
    """Resolve a config value that may reference an environment variable.

    Supports the placeholder syntax ``${VAR_NAME}`` in the YAML file, so
    that credentials (el token de InfluxDB) y datos identificativos del
    servidor (URL/IP, organización) nunca necesiten estar en texto plano
    en un fichero versionado. When the raw value is exactly ``${env_var}``
    it is replaced by the current value of that environment variable.

    Args:
        value: Raw value read from the YAML file (may be a placeholder).
        env_var: Name of the environment variable to resolve against.

    Returns:
        The resolved value.

    Raises:
        ValueError: If the value is a placeholder but the environment
            variable is not set (or is empty).
    """
    placeholder = f"${{{env_var}}}"
    if isinstance(value, str) and value.strip() == placeholder:
        resolved = os.environ.get(env_var)
        if not resolved:
            raise ValueError(
                f"El fichero de configuración espera la variable de entorno "
                f"{env_var}, pero no está definida. Expórtala antes de "
                f"ejecutar, p. ej.: export {env_var}=\"...\""
            )
        return resolved
    return value


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
            url=_resolve_secret(influx_raw["url"], "INFLUXDB_URL"),
            org=_resolve_secret(influx_raw["org"], "INFLUXDB_ORG"),
            bucket=_resolve_secret(influx_raw["bucket"], "INFLUXDB_BUCKET"),
            token=_resolve_secret(influx_raw["token"], "INFLUXDB_TOKEN"),
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
