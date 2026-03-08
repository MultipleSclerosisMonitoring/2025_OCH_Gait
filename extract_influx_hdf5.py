#!/usr/bin/env python3
"""Extract gait signals from InfluxDB and optionally build spectrum parquet files.

This script supports two modes:

1. count
   Query InfluxDB for each foot and print how many records are returned.

2. spectrogram
   Extract the full gait interval from InfluxDB, resample the selected signals,
   slide centered analysis windows, compute power spectra, keep frequencies
   below fmax_hz, and save the result to parquet.

Notes:
- The InfluxDB extraction interval is defined by --from_time / --until.
- The internal spectral analysis windows are defined in the YAML config.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yaml
from influxdb_client import InfluxDBClient
from scipy.signal import periodogram, get_window


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


# ==============================
# CLI
# ==============================
class CLI:
    """Command line parser."""

    @staticmethod
    def parse(argv: Optional[List[str]] = None) -> CliArgs:
        """Parse command-line arguments.

        Args:
            argv: Optional arguments list for testing. If None, uses sys.argv.

        Returns:
            Parsed CliArgs.
        """
        p = argparse.ArgumentParser(
            description=(
                "Extract gait data from InfluxDB. "
                "Mode 'count' prints record counts. "
                "Mode 'spectrogram' builds a parquet file with sliding power spectra."
            )
        )
        p.add_argument(
            "-f",
            "--from_time",
            required=True,
            help='Inicio (ej: "2025-07-01 15:59:14")',
        )
        p.add_argument(
            "-u",
            "--until",
            required=True,
            help='Fin (ej: "2025-07-01 16:05:18")',
        )
        p.add_argument(
            "-q",
            "--reference",
            required=True,
            help='Referencia (ej: "TESTPATIENT-98")',
        )
        p.add_argument(
            "-o",
            "--output",
            default="salida.h5",
            help=(
                "Fichero de salida. En mode=count no se usa. "
                "En mode=spectrogram debe ser un .parquet."
            ),
        )
        p.add_argument(
            "--from-tz",
            default="Europe/Madrid",
            help="Zona horaria de las fechas de entrada",
        )
        p.add_argument(
            "--config",
            default=".config.yaml",
            help="Ruta al fichero YAML de configuración",
        )
        p.add_argument(
            "--mode",
            choices=["count", "spectrogram"],
            default="count",
            help="Modo de ejecución",
        )
        p.add_argument(
            "-v",
            "--verbose",
            action="count",
            default=0,
            help="Aumenta el nivel de detalle (-v, -vv)",
        )

        ns = p.parse_args(argv)

        return CliArgs(
            from_time=ns.from_time,
            until=ns.until,
            reference=ns.reference,
            output=ns.output,
            from_tz=ns.from_tz,
            config=ns.config,
            mode=ns.mode,
            verbose=ns.verbose,
        )


# ==============================
# Config
# ==============================
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

        with self._path.open("r", encoding="utf-8") as f:
            cfg: Dict[str, Any] = yaml.safe_load(f) or {}

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
        )

        return AppConfig(
            influx=influx,
            default_tz=default_tz,
            ref_tag=ref_tag,
            foot_tag=foot_tag,
            spectrogram=spectrogram,
        )


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

    @staticmethod
    def to_local_datetime(dt_str: str, tz_name: str) -> datetime:
        """Parse local datetime string into timezone-aware datetime.

        Args:
            dt_str: Datetime string in '%Y-%m-%d %H:%M:%S' format.
            tz_name: IANA timezone name.

        Returns:
            Timezone-aware datetime in local timezone.
        """
        s = dt_str.strip().replace("T", " ")
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=ZoneInfo(tz_name))

    @staticmethod
    def generate_window_centers(
        start_dt: datetime,
        stop_dt: datetime,
        window_s: float,
        delta_t_s: float,
    ) -> List[datetime]:
        """Generate valid centered window times inside the gait interval.

        A center is valid only if the full analysis window is contained in the
        gait interval.

        Args:
            start_dt: Start of gait interval.
            stop_dt: End of gait interval.
            window_s: Duration of centered analysis window in seconds.
            delta_t_s: Step between consecutive centers in seconds.

        Returns:
            List of center times.
        """
        half = timedelta(seconds=window_s / 2.0)
        step = timedelta(seconds=delta_t_s)

        first_center = start_dt + half
        last_center = stop_dt - half

        centers: List[datetime] = []
        t = first_center
        while t <= last_center:
            centers.append(t)
            t += step

        return centers


# ==============================
# Flux query
# ==============================
class FluxQueryBuilder:
    """Builds Flux queries for IMU extraction."""

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
        fields: Iterable[str],
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
            fields: Iterable of field names to keep.
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

    @staticmethod
    def tables_to_dataframe(tables) -> pd.DataFrame:
        """Convert Influx tables to a pandas DataFrame.

        Args:
            tables: Query result tables from InfluxDB client.

        Returns:
            DataFrame with one row per timestamp and one column per selected field.
        """
        rows: List[Dict[str, Any]] = []
        for table in tables:
            for record in table.records:
                values = dict(record.values)
                rows.append(values)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)

        # Keep only useful columns if they exist
        preferred = ["_time"]
        preferred += [c for c in df.columns if c in {"Ax", "Ay", "Az", "Gx", "Gy", "Gz", "Mx", "My", "Mz", "S0", "S1", "S2"}]
        if preferred:
            preferred_existing = [c for c in preferred if c in df.columns]
            if preferred_existing:
                df = df[preferred_existing]

        if "_time" in df.columns:
            df["_time"] = pd.to_datetime(df["_time"], utc=True)
            df = df.sort_values("_time").drop_duplicates(subset=["_time"]).reset_index(drop=True)

        return df


# ==============================
# Signal processing
# ==============================
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


class PowerSpectrumEngine:
    """Compute power spectra on centered windows."""

    def __init__(self, spec_cfg: SpectrogramConfig) -> None:
        """Initialize the spectrum engine.

        Args:
            spec_cfg: Spectral analysis configuration.
        """
        self._cfg = spec_cfg

    def compute(self, signal_values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Compute power spectrum for one windowed signal.

        Args:
            signal_values: One-dimensional signal values inside the analysis window.

        Returns:
            Tuple (freqs, powers) after filtering frequencies above fmax_hz.

        Raises:
            ValueError: If the input signal is empty.
        """
        if signal_values.size == 0:
            raise ValueError("La señal de entrada está vacía.")

        window = get_window(self._cfg.window_type, signal_values.size)
        freqs, powers = periodogram(
            signal_values,
            fs=self._cfg.resample_hz,
            window=window,
            scaling="density",
            detrend="constant",
        )

        mask = freqs <= self._cfg.fmax_hz
        freqs = freqs[mask]
        powers = powers[mask]

        if self._cfg.power_scale.lower() == "db":
            powers = 10.0 * np.log10(powers + 1e-12)

        return freqs, powers


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

    def _get_tz(self) -> str:
        """Return active timezone name.

        Returns:
            Active timezone name.
        """
        return self._config.default_tz or self._args.from_tz

    def run_count(self) -> None:
        """Run record counting for each configured foot."""
        tz = self._get_tz()

        start_iso, start_key = TimeProcessor.to_utc_rfc3339_and_key(self._args.from_time, tz)
        stop_iso, stop_key = TimeProcessor.to_utc_rfc3339_and_key(self._args.until, tz)

        hdf5_base = f"/{self._args.reference}/{start_key}-{stop_key}"

        if self._args.verbose:
            print("Zona local usada:", tz)
            print("Inicio local:", self._args.from_time, "→ UTC (InfluxDB):", start_iso)
            print("Fin local:   ", self._args.until, "→ UTC (InfluxDB):", stop_iso)
            print("Ruta base HDF5 (sin pie aún):", hdf5_base + "/<Foot>")
            print()

        count_fields = self._config.spectrogram.signals

        for foot in self._config.spectrogram.feet:
            flux = FluxQueryBuilder.build(
                bucket=self._config.influx.bucket,
                start_iso=start_iso,
                stop_iso=stop_iso,
                ref_tag=self._config.ref_tag,
                reference=self._args.reference,
                foot_tag=self._config.foot_tag,
                foot=foot,
                fields=count_fields,
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

    def _load_foot_dataframe(self, foot: str) -> pd.DataFrame:
        """Load full gait interval for one foot as a DataFrame.

        Args:
            foot: Foot label, e.g. 'Right' or 'Left'.

        Returns:
            DataFrame with '_time' and selected signal columns.
        """
        tz = self._get_tz()
        start_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(self._args.from_time, tz)
        stop_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(self._args.until, tz)

        flux = FluxQueryBuilder.build(
            bucket=self._config.influx.bucket,
            start_iso=start_iso,
            stop_iso=stop_iso,
            ref_tag=self._config.ref_tag,
            reference=self._args.reference,
            foot_tag=self._config.foot_tag,
            foot=foot,
            fields=self._config.spectrogram.signals,
            pivot=True,
        )

        if self._args.verbose >= 2:
            print(f"[DEBUG] Query {foot}:")
            print(flux)

        tables = self._influx.query(flux)
        return self._influx.tables_to_dataframe(tables)

    def run_spectrogram(self) -> None:
        """Run sliding-window spectral processing and save parquet.

        Workflow:
            1. Extract the full gait interval for each foot.
            2. Resample signals to a uniform frequency.
            3. Generate centered 10-second windows every delta_t_s.
            4. Compute power spectra for each signal and each center.
            5. Keep frequencies below fmax_hz.
            6. Stack right-foot rows first and left-foot rows after.
            7. Save output to parquet.
        """
        tz = self._get_tz()
        spec_cfg = self._config.spectrogram
        spectrum_engine = PowerSpectrumEngine(spec_cfg)
        rows_right: List[Dict[str, Any]] = []
        rows_left: List[Dict[str, Any]] = []

        start_local = TimeProcessor.to_local_datetime(self._args.from_time, tz)
        stop_local = TimeProcessor.to_local_datetime(self._args.until, tz)
        centers_local = TimeProcessor.generate_window_centers(
            start_dt=start_local,
            stop_dt=stop_local,
            window_s=spec_cfg.window_s,
            delta_t_s=spec_cfg.delta_t_s,
        )

        if self._args.verbose:
            print("Modo spectrogram activado")
            print("Zona local usada:", tz)
            print("Ventana de análisis (s):", spec_cfg.window_s)
            print("Delta t (s):", spec_cfg.delta_t_s)
            print("Frecuencia máxima (Hz):", spec_cfg.fmax_hz)
            print("Resample (Hz):", spec_cfg.resample_hz)
            print("Señales:", spec_cfg.signals)
            print("Pies:", spec_cfg.feet)
            print("Centros de ventana generados:", len(centers_local))
            print()

        for foot in spec_cfg.feet:
            df = self._load_foot_dataframe(foot)
            if df.empty:
                print(f"⚠️ No hay datos para el pie {foot}.")
                continue

            df_rs = Resampler.resample_dataframe(df, spec_cfg.resample_hz, spec_cfg.signals)

            foot_rows: List[Dict[str, Any]] = []
            half_window = timedelta(seconds=spec_cfg.window_s / 2.0)

            for center_local in centers_local:
                center_utc = pd.Timestamp(center_local.astimezone(ZoneInfo("UTC")))
                start_utc = pd.Timestamp((center_local - half_window).astimezone(ZoneInfo("UTC")))
                stop_utc = pd.Timestamp((center_local + half_window).astimezone(ZoneInfo("UTC")))

                window_df = df_rs.loc[start_utc:stop_utc]

                if window_df.empty:
                    continue

                for signal_name in spec_cfg.signals:
                    if signal_name not in window_df.columns:
                        continue

                    signal_values = window_df[signal_name].to_numpy(dtype=float)
                    if signal_values.size < 2:
                        continue

                    freqs, powers = spectrum_engine.compute(signal_values)
                    row = ParquetRowBuilder.build_row(
                        reference=self._args.reference,
                        foot=foot,
                        signal_name=signal_name,
                        time_center=center_utc,
                        freqs=freqs,
                        powers=powers,
                    )
                    foot_rows.append(row)

            if foot.lower() == "right":
                rows_right.extend(foot_rows)
            else:
                rows_left.extend(foot_rows)

            if self._args.verbose:
                print(f"Pie {foot}: filas generadas = {len(foot_rows)}")

        all_rows = rows_right + rows_left
        if not all_rows:
            raise ValueError("No se han generado filas para el parquet.")

        out_df = pd.DataFrame(all_rows)
        out_df.to_parquet(self._args.output, index=False)

        print(f"Parquet guardado en: {self._args.output}")
        print(f"Filas totales: {len(out_df)}")
        print(f"Right arriba: {len(rows_right)} filas")
        print(f"Left abajo: {len(rows_left)} filas")

    def run(self) -> None:
        """Run the selected mode."""
        if self._args.mode == "count":
            self.run_count()
        elif self._args.mode == "spectrogram":
            self.run_spectrogram()
        else:
            raise ValueError(f"Modo no soportado: {self._args.mode}")


def main() -> None:
    """Program entry point."""
    args = CLI.parse()
    config = ConfigLoader(args.config).load()
    app = ExtractApp(args=args, config=config)
    app.run()


if __name__ == "__main__":
    main()



