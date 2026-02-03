#!/usr/bin/env python3
"""Extract IMU data from InfluxDB for each foot in a time window.

Current behavior:
- Queries InfluxDB for each foot (e.g., Left/Right) within a time interval.
- Prints how many records are returned per foot.
- Prints the Flux query when verbosity is enabled.

Planned:
- Store results into HDF5 with structure:
  /<reference>/<YYYYMMDDTHHMMSS>-<YYYYMMDDTHHMMSS>/<foot>
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

import yaml
from influxdb_client import InfluxDBClient


# ==============================
# Models
# ==============================
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
class AppConfig:
    """Application configuration loaded from YAML.

    Attributes:
        influx: InfluxDB configuration.
        default_tz: Optional default timezone name from YAML (Location.zoneInfo).
    """

    influx: InfluxConfig
    default_tz: Optional[str] = None


@dataclass(frozen=True)
class CliArgs:
    """Parsed CLI arguments.

    Attributes:
        from_time: Start datetime (local timezone) as string.
        until: End datetime (local timezone) as string.
        reference: Reference identifier (e.g., patient/session code).
        feet: Feet labels to extract.
        output: Output HDF5 file path (not used yet).
        from_tz: Timezone for input datetimes if config doesn't provide one.
        ref_tag: InfluxDB tag key for reference.
        foot_tag: InfluxDB tag key for foot.
        verbose: Verbosity level (0, 1, 2...).
    """

    from_time: str
    until: str
    reference: str
    feet: List[str]
    output: str
    from_tz: str
    ref_tag: str
    foot_tag: str
    verbose: int


# ==============================
# CLI
# ==============================
class CLI:
    """Command line parser."""

    @staticmethod
    def parse(argv: Optional[List[str]] = None) -> CliArgs:
        """Parse CLI arguments.

        Args:
            argv: Optional arguments list for testing. If None, uses sys.argv.

        Returns:
            Parsed CliArgs.
        """
        p = argparse.ArgumentParser(
            description="Extrae datos de InfluxDB y (más adelante) guarda por pie en HDF5."
        )
        p.add_argument("-f", "--from_time", required=True, help='Inicio (ej: "2025-07-01 15:59:14")')
        p.add_argument("-u", "--until", required=True, help='Fin (ej: "2025-07-01 16:05:18")')
        p.add_argument("-q", "--reference", required=True, help='Referencia (ej: "TESTPATIENT-98")')
        p.add_argument("--feet", nargs="+", default=["Left", "Right"], help="Pies a extraer (default: Left Right)")
        p.add_argument("-o", "--output", default="salida.h5", help="Fichero HDF5 de salida (default: salida.h5)")
        p.add_argument("--from-tz", default="Europe/Madrid", help="Zona horaria de las fechas de entrada")
        p.add_argument("--ref-tag", default="reference", help="Nombre del tag en InfluxDB para la referencia")
        p.add_argument("--foot-tag", default="Foot", help="Nombre del tag en InfluxDB para el pie (Left/Right)")
        p.add_argument("-v", "--verbose", action="count", default=0, help="Aumenta el nivel de detalle (-v, -vv)")

        ns = p.parse_args(argv)

        return CliArgs(
            from_time=ns.from_time,
            until=ns.until,
            reference=ns.reference,
            feet=list(ns.feet),
            output=ns.output,
            from_tz=ns.from_tz,
            ref_tag=ns.ref_tag,
            foot_tag=ns.foot_tag,
            verbose=ns.verbose,
        )


# ==============================
# Config
# ==============================
class ConfigLoader:
    """Loads YAML configuration from a file."""

    def __init__(self, config_path: Optional[str] = None) -> None:
        """Initialize loader.

        Args:
            config_path: Path to config file. Defaults to '.config.yaml'.
        """
        self._path = Path(config_path or ".config.yaml")

    def load(self) -> AppConfig:
        """Load configuration and validate required fields.

        Returns:
            AppConfig with InfluxDB settings.

        Raises:
            FileNotFoundError: If config file does not exist.
            ValueError: If required InfluxDB fields are missing.
        """
        if not self._path.exists():
            raise FileNotFoundError(
                f"No encuentro {self._path.resolve()}. Colócalo en la raíz del proyecto."
            )

        with self._path.open("r", encoding="utf-8") as f:
            cfg: Dict[str, Any] = yaml.safe_load(f) or {}

        influx_raw = cfg.get("influxdb") or {}
        required = ["url", "org", "bucket", "token"]
        missing = [k for k in required if k not in influx_raw]
        if missing:
            raise ValueError(f"Faltan campos en 'influxdb': {missing}. Revisa {self._path}.")

        influx = InfluxConfig(
            url=influx_raw["url"],
            org=influx_raw["org"],
            bucket=influx_raw["bucket"],
            token=influx_raw["token"],
            verify_ssl=bool(influx_raw.get("verify_ssl", False)),
        )
        default_tz = (cfg.get("Location") or {}).get("zoneInfo")
        return AppConfig(influx=influx, default_tz=default_tz)


# ==============================
# Time handling
# ==============================
class TimeProcessor:
    """Parses datetimes and converts them to UTC for InfluxDB."""

    @staticmethod
    def to_utc_rfc3339_and_key(dt_str: str, tz_name: str) -> Tuple[str, str]:
        """Convert local datetime string to UTC RFC3339 and local compact key.

        Args:
            dt_str: Datetime string, e.g. "2025-07-01 15:59:14" (or with 'T').
            tz_name: IANA timezone name, e.g. "Europe/Madrid".

        Returns:
            Tuple (utc_rfc3339, local_key) where:
                - utc_rfc3339: UTC RFC3339 string for InfluxDB (e.g., "...Z").
                - local_key: Local compact string YYYYMMDDTHHMMSS.

        Raises:
            ValueError: If dt_str does not match the expected format.
        """
        s = dt_str.strip().replace("T", " ")
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        dt_local = dt.replace(tzinfo=ZoneInfo(tz_name))

        dt_utc = dt_local.astimezone(ZoneInfo("UTC"))
        utc_rfc3339 = dt_utc.isoformat().replace("+00:00", "Z")

        key_str = dt_local.strftime("%Y%m%dT%H%M%S")
        return utc_rfc3339, key_str


# ==============================
# Flux query
# ==============================
class FluxQueryBuilder:
    """Builds Flux queries for IMU extraction."""

    DEFAULT_FIELDS = ("Ax", "Ay", "Az", "Gx", "Gy", "Gz", "Mx", "My", "Mz")

    @classmethod
    def build(
        cls,
        bucket: str,
        start_iso: str,
        stop_iso: str,
        ref_tag: str,
        reference: str,
        foot_tag: str,
        foot: str,
        fields: Iterable[str] = DEFAULT_FIELDS,
        pivot: bool = True,
    ) -> str:
        """Build a Flux query for a given foot and time range.

        Args:
            bucket: InfluxDB bucket.
            start_iso: UTC RFC3339 start time.
            stop_iso: UTC RFC3339 stop time.
            ref_tag: Tag key for reference.
            reference: Tag value for reference.
            foot_tag: Tag key for foot.
            foot: Tag value for foot.
            fields: Iterable of field names to keep (Ax, Ay, ...).
            pivot: Whether to pivot to wide format.

        Returns:
            Flux query string.
        """
        field_filters = " or ".join([f'r["_field"] == "{f}"' for f in fields])

        query = f'''
from(bucket: "{bucket}")
  |> range(start: time(v: "{start_iso}"), stop: time(v: "{stop_iso}"))
  |> filter(fn: (r) => r["{ref_tag}"] == "{reference}")
  |> filter(fn: (r) => r["{foot_tag}"] == "{foot}")
  |> filter(fn: (r) => {field_filters})
'''
        if pivot:
            query += '  |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")\n'
        return query


# ==============================
# Influx access
# ==============================
class InfluxService:
    """Service for querying InfluxDB."""

    def __init__(self, cfg: InfluxConfig) -> None:
        """Initialize InfluxDB client.

        Args:
            cfg: InfluxDB configuration.
        """
        self._client = InfluxDBClient(
            url=cfg.url,
            token=cfg.token,
            org=cfg.org,
            verify_ssl=cfg.verify_ssl,
        )
        self._query_api = self._client.query_api()

    def query(self, flux: str):
        """Execute a Flux query.

        Args:
            flux: Flux query string.

        Returns:
            Query result tables.
        """
        return self._query_api.query(flux)

    @staticmethod
    def count_records(tables) -> int:
        """Count total records in result tables.

        Args:
            tables: InfluxDB query result tables.

        Returns:
            Total record count.
        """
        return sum(len(t.records) for t in tables)


# ==============================
# Application
# ==============================
class ExtractApp:
    """Orchestrates extraction workflow."""

    def __init__(self, args: CliArgs, config: AppConfig) -> None:
        """Create the application.

        Args:
            args: CLI arguments.
            config: Loaded configuration.
        """
        self._args = args
        self._config = config
        self._influx = InfluxService(config.influx)

    def run(self) -> None:
        """Run extraction for each foot."""
        tz = self._config.default_tz or self._args.from_tz

        start_iso, start_key = TimeProcessor.to_utc_rfc3339_and_key(self._args.from_time, tz)
        stop_iso, stop_key = TimeProcessor.to_utc_rfc3339_and_key(self._args.until, tz)

        hdf5_base = f"/{self._args.reference}/{start_key}-{stop_key}"

        if self._args.verbose:
            print("Zona local usada:", tz)
            print("Inicio local:", self._args.from_time, "→ UTC (InfluxDB):", start_iso)
            print("Fin local:   ", self._args.until, "→ UTC (InfluxDB):", stop_iso)
            print("Ruta base HDF5 (sin pie aún):", hdf5_base + "/<Foot>")
            print()

        for foot in self._args.feet:
            flux = FluxQueryBuilder.build(
                bucket=self._config.influx.bucket,
                start_iso=start_iso,
                stop_iso=stop_iso,
                ref_tag=self._args.ref_tag,
                reference=self._args.reference,
                foot_tag=self._args.foot_tag,
                foot=foot,
                pivot=True,
            )

            print(f"=== Pie: {foot} ===")
            if self._args.verbose:
                print("Flux query enviada a Influx:")
                print(flux)

            tables = self._influx.query(flux)
            n = self._influx.count_records(tables)

            print(f"Registros obtenidos de InfluxDB: {n}")
            if n == 0:
                print("⚠️ No hay datos para este pie con esos filtros.")
            print()


def main() -> None:
    """Program entry point."""
    args = CLI.parse()
    config = ConfigLoader().load()
    app = ExtractApp(args=args, config=config)
    app.run()


if __name__ == "__main__":
    main()



