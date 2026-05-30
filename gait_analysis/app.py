from __future__ import annotations

if __package__ is None or __package__ == "":
    from pathlib import Path
    import sys

    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

import json
import subprocess
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import TracebackType
from typing import Any, Dict, List, Optional, Type
from zoneinfo import ZoneInfo

import pandas as pd

from gait_analysis.flux import FluxQueryBuilder
from gait_analysis.models import AppConfig, CliArgs
from gait_analysis.resampling import Resampler
from gait_analysis.time_utils import TimeProcessor


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
        self._influx: Optional[Any] = None
        self._last_query_error: Optional[Dict[str, str]] = None

    def __enter__(self) -> "ExtractApp":
        """Enter the extraction app context.

        Returns:
            Active app instance.
        """
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """Exit the app context and release external resources.

        Args:
            exc_type: Exception type raised inside the context, if any.
            exc_value: Exception instance raised inside the context, if any.
            traceback: Traceback raised inside the context, if any.
        """
        self.close()

    def _get_tz(self) -> str:
        """Return active timezone name.

        Returns:
            Active timezone name.
        """
        return self._config.default_tz or self._args.from_tz

    def _effective_spectrogram_config(self):
        """Return spectrogram config with optional CLI overrides applied."""
        spec_cfg = self._config.spectrogram
        overrides = {}
        if self._args.window_s is not None:
            overrides["window_s"] = self._args.window_s
        if self._args.min_window_completeness is not None:
            overrides["min_window_completeness"] = self._args.min_window_completeness
        if self._args.max_interpolate_gap_s is not None:
            overrides["max_interpolate_gap_s"] = self._args.max_interpolate_gap_s
        if overrides:
            spec_cfg = replace(spec_cfg, **overrides)
        return spec_cfg

    def _get_influx(self):
        """Return a lazily-created InfluxDB service."""
        if self._influx is None:
            from gait_analysis.influx_service import InfluxService

            self._influx = InfluxService(self._config.influx)
        return self._influx

    def _build_foot_flux(self, foot: str) -> tuple[str, str, str]:
        """Build the Flux query and UTC bounds for a foot."""
        tz = self._get_tz()
        spec_cfg = self._effective_spectrogram_config()
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
            fields=spec_cfg.signals,
            pivot=True,
        )
        return flux, start_iso, stop_iso

    def _git_commit(self) -> str:
        """Return the current git commit if available."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception:
            return ""
        return result.stdout.strip()

    def _queries_by_foot(self) -> Dict[str, str]:
        """Return planned Flux queries for every configured foot."""
        spec_cfg = self._effective_spectrogram_config()
        return {foot: self._build_foot_flux(foot)[0] for foot in spec_cfg.feet}

    def _audit_json_path(self) -> Path:
        """Return the automatic audit JSON path for the current output."""
        output = Path(self._args.output)
        if output.suffix:
            return output.with_suffix(".audit.json")
        return output.with_name(output.name + ".audit.json")

    @staticmethod
    def _json_default(value: Any) -> str:
        """Serialize timestamp-like values for audit JSON."""
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    def _write_audit_json(self, status: str, **extra: Any) -> None:
        """Write a reproducibility manifest next to the extraction output."""
        spec_cfg = self._effective_spectrogram_config()
        tz = self._get_tz()
        start_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(self._args.from_time, tz)
        stop_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(self._args.until, tz)
        manifest: Dict[str, Any] = {
            "status": status,
            "mode": self._args.mode,
            "reference": self._args.reference,
            "output": self._args.output,
            "config": self._args.config,
            "git_commit": self._git_commit(),
            "from_local": self._args.from_time,
            "until_local": self._args.until,
            "timezone": tz,
            "from_utc": start_iso,
            "until_utc": stop_iso,
            "bucket": self._config.influx.bucket,
            "ref_tag": self._config.ref_tag,
            "foot_tag": self._config.foot_tag,
            "signals": list(spec_cfg.signals),
            "feet": list(spec_cfg.feet),
            "spectrogram": {
                "window_s": spec_cfg.window_s,
                "delta_t_s": spec_cfg.delta_t_s,
                "fmax_hz": spec_cfg.fmax_hz,
                "window_type": spec_cfg.window_type,
                "power_scale": spec_cfg.power_scale,
                "resample_hz": spec_cfg.resample_hz,
                "detrend": spec_cfg.detrend,
                "max_interpolate_gap_s": spec_cfg.max_interpolate_gap_s,
                "min_window_completeness": spec_cfg.min_window_completeness,
            },
            "queries_by_foot": self._queries_by_foot(),
        }
        if self._last_query_error is not None:
            manifest["query_error"] = self._last_query_error
        manifest.update(extra)

        path = self._audit_json_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, default=self._json_default),
            encoding="utf-8",
        )
        print(f"Audit JSON guardado en: {path}")

    @staticmethod
    def _summarize_foot_dataframe(df: pd.DataFrame, foot: str) -> Dict[str, Any]:
        """Return row count and temporal bounds for a foot DataFrame."""
        summary: Dict[str, Any] = {"foot": foot, "rows": int(len(df))}
        if not df.empty and "_time" in df.columns:
            times = pd.to_datetime(df["_time"], utc=True, format="mixed")
            summary["min_time_utc"] = times.min()
            summary["max_time_utc"] = times.max()
        else:
            summary["min_time_utc"] = ""
            summary["max_time_utc"] = ""
        return summary

    def _print_flux_debug(self, foot: str, flux: str, start_iso: str, stop_iso: str) -> None:
        """Print the query context for reproducibility."""
        tz = self._get_tz()
        print(f"[DEBUG] Query {foot}:")
        print("Zona local usada:", tz)
        print("Inicio local:", self._args.from_time, "-> UTC (InfluxDB):", start_iso)
        print("Fin local:   ", self._args.until, "-> UTC (InfluxDB):", stop_iso)
        print(flux)

    def _query_influx(self, flux: str):
        """Execute a Flux query and convert connection failures into CLI output."""
        try:
            self._last_query_error = None
            return self._get_influx().query(flux)
        except Exception as exc:
            self._last_query_error = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            print("No se pudo consultar InfluxDB.")
            print(f"Detalle: {type(exc).__name__}: {exc}")
            print(
                "Puedes usar --dry-run para validar la query y la conversión horaria "
                "sin abrir conexión al servidor."
            )
            return None

    def print_planned_queries(self) -> None:
        """Print all Flux queries that would be sent to InfluxDB."""
        spec_cfg = self._effective_spectrogram_config()
        print("Dry run: no se consultará InfluxDB.")
        print("Modo:", self._args.mode)
        print("Referencia:", self._args.reference)
        print("Bucket:", self._config.influx.bucket)
        print("Tag referencia:", self._config.ref_tag)
        print("Tag pie:", self._config.foot_tag)
        print("Señales:", spec_cfg.signals)
        print("Pies:", spec_cfg.feet)
        print()
        for foot in spec_cfg.feet:
            flux, start_iso, stop_iso = self._build_foot_flux(foot)
            self._print_flux_debug(foot, flux, start_iso, stop_iso)

    def run_count(self) -> None:
        """Run record counting for each configured foot."""
        tz = self._get_tz()
        spec_cfg = self._effective_spectrogram_config()

        start_iso, start_key = TimeProcessor.to_utc_rfc3339_and_key(self._args.from_time, tz)
        stop_iso, stop_key = TimeProcessor.to_utc_rfc3339_and_key(self._args.until, tz)

        hdf5_base = f"/{self._args.reference}/{start_key}-{stop_key}"

        if self._args.verbose:
            print("Zona local usada:", tz)
            print("Inicio local:", self._args.from_time, "→ UTC (InfluxDB):", start_iso)
            print("Fin local:   ", self._args.until, "→ UTC (InfluxDB):", stop_iso)
            print("Ruta base HDF5 (sin pie aún):", hdf5_base + "/<Foot>")
            print()

        for foot in spec_cfg.feet:
            flux, _, _ = self._build_foot_flux(foot)

            print(f"=== Pie: {foot} ===")
            if self._args.verbose:
                print("Flux query enviada a Influx:")
                print(flux)

            tables = self._query_influx(flux)
            if tables is None:
                return
            n = self._get_influx().count_records(tables)

            print(f"Registros obtenidos de InfluxDB: {n}")
            if n == 0:
                print("⚠️ No hay datos para este pie con esos filtros.")
            print()

    def _save_dataframe(self, df: pd.DataFrame, output: str) -> None:
        """Save a DataFrame using an extension-derived format."""
        output_path = output.lower()
        if output_path.endswith(".parquet"):
            df.to_parquet(output, index=False)
        elif output_path.endswith(".csv"):
            df.to_csv(output, index=False)
        elif output_path.endswith(".xlsx"):
            df.to_excel(output, index=False)
        else:
            raise ValueError(
                "Formato de salida no soportado. Usa un fichero .parquet, .csv o .xlsx"
            )

    def run_raw(self) -> None:
        """Extract raw samples for each configured foot and save them."""
        tz = self._get_tz()
        spec_cfg = self._effective_spectrogram_config()
        start_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(self._args.from_time, tz)
        stop_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(self._args.until, tz)

        if self._args.verbose:
            print("Modo raw activado")
            print("Zona local usada:", tz)
            print("Inicio local:", self._args.from_time, "-> UTC (InfluxDB):", start_iso)
            print("Fin local:   ", self._args.until, "-> UTC (InfluxDB):", stop_iso)
            print("Señales:", spec_cfg.signals)
            print("Pies:", spec_cfg.feet)
            print()

        frames: List[pd.DataFrame] = []
        rows_by_foot: Dict[str, int] = {}
        foot_summaries: Dict[str, Dict[str, Any]] = {}
        for foot in spec_cfg.feet:
            df = self._load_foot_dataframe(foot)
            if df is None:
                self._write_audit_json(
                    "connection_failed",
                    foot_summaries=foot_summaries,
                )
                return
            rows_by_foot[foot] = len(df)
            foot_summaries[foot] = self._summarize_foot_dataframe(df, foot)
            if df.empty:
                print(f"⚠️ No hay datos para el pie {foot}.")
                continue

            raw_df = df.copy()
            raw_df.insert(0, "foot", foot)
            raw_df.insert(0, "reference", self._args.reference)
            raw_df["from_local"] = self._args.from_time
            raw_df["until_local"] = self._args.until
            raw_df["timezone"] = tz
            raw_df["from_utc"] = start_iso
            raw_df["until_utc"] = stop_iso
            frames.append(raw_df)

        if not frames:
            print("No se han recuperado muestras raw para ningún pie.")
            print("Revisa el rango de fechas, la referencia y los tags configurados.")
            self._write_audit_json(
                "no_records",
                foot_summaries=foot_summaries,
                total_rows=0,
            )
            return

        out_df = pd.concat(frames, ignore_index=True).sort_values(["_time", "foot"])
        self._save_dataframe(out_df, self._args.output)

        print(f"Raw guardado en: {self._args.output}")
        print(f"Filas totales: {len(out_df)}")
        for foot in spec_cfg.feet:
            print(f"{foot}: {rows_by_foot.get(foot, 0)} filas")

        missing_feet = [foot for foot in spec_cfg.feet if rows_by_foot.get(foot, 0) == 0]
        status = "only_some_feet" if missing_feet else "valid_raw"
        self._write_audit_json(
            status,
            foot_summaries=foot_summaries,
            total_rows=int(len(out_df)),
            missing_feet=missing_feet,
        )

    def _load_foot_dataframe(self, foot: str) -> Optional[pd.DataFrame]:
        """Load full gait interval for one foot as a DataFrame.

        Args:
            foot: Foot label, e.g. 'Right' or 'Left'.

        Returns:
            DataFrame with '_time' and selected signal columns, or None if the
            external query failed.
        """
        flux, start_iso, stop_iso = self._build_foot_flux(foot)

        if self._args.verbose >= 2:
            self._print_flux_debug(foot, flux, start_iso, stop_iso)

        tables = self._query_influx(flux)
        if tables is None:
            return None
        df = self._get_influx().tables_to_dataframe(tables)
        if self._args.verbose >= 2:
            print(f"[DEBUG] Filas recibidas {foot}: {len(df)}")
            print()
        return df

    def _build_common_time_index(
        self,
        start_ts: pd.Timestamp,
        stop_ts: pd.Timestamp,
        resample_hz: float,
    ) -> pd.DatetimeIndex:
        """Build a common UTC time grid for both feet.

        Args:
            start_ts: Common inclusive start timestamp in UTC.
            stop_ts: Common inclusive stop timestamp in UTC.
            resample_hz: Target resampling frequency.

        Returns:
            UTC DatetimeIndex with fixed sampling step.
        """
        step_ms = int(round(1000.0 / resample_hz))
        return pd.date_range(start=start_ts, end=stop_ts, freq=f"{step_ms}ms", tz="UTC")

    def _generate_anchored_centers(
        self,
        *,
        anchor: pd.Timestamp,
        start_center: pd.Timestamp,
        stop_center: pd.Timestamp,
        core_start: pd.Timestamp,
        core_stop: pd.Timestamp,
        delta_t_s: float,
    ) -> List[pd.Timestamp]:
        """Generate centers aligned to a fixed global anchor."""
        step = pd.Timedelta(seconds=delta_t_s)
        lower = max(start_center, core_start)
        upper = min(stop_center, core_stop - pd.Timedelta(microseconds=1))
        if upper < lower:
            return []

        if anchor < lower:
            steps = int(((lower - anchor) / step))
            center = anchor + steps * step
            while center < lower:
                center += step
        else:
            center = anchor
            while center - step >= lower:
                center -= step

        centers = []
        while center <= upper:
            centers.append(center)
            center += step
        return centers

    def run_spectrogram(self) -> None:
        """Run sliding-window spectral processing and save output.

        The workflow enforces:
            - a real temporal intersection between both feet,
            - a common resampled time grid,
            - full windows only,
            - comparable time_center values for both feet.

        Raises:
            ValueError: If both feet have no common temporal intersection.
            ValueError: If the common intersection cannot contain complete windows.
            ValueError: If no output rows are generated.
            ValueError: If the output extension is unsupported.
        """
        tz = self._get_tz()
        spec_cfg = self._effective_spectrogram_config()
        from gait_analysis.spectrum import ParquetRowBuilder, PowerSpectrumEngine

        spectrum_engine = PowerSpectrumEngine(spec_cfg)
        rows_right = 0
        rows_left = 0
        total_rows = 0
        skipped_empty_window = 0
        skipped_short_window = 0
        skipped_low_completeness = 0
        skipped_remaining_nan = 0
        chunk_size = 5000
        chunk_rows: List[Dict[str, object]] = []
        excel_rows: List[Dict[str, object]] = []
        parquet_writer = None
        hdf_initialized = False

        output_path = self._args.output.lower()
        output_is_parquet = output_path.endswith(".parquet")
        output_is_excel = output_path.endswith(".xlsx")
        output_is_hdf = output_path.endswith(".h5") or output_path.endswith(".hdf5")
        if not (output_is_parquet or output_is_excel or output_is_hdf):
            raise ValueError(
                "Formato de salida no soportado. Usa un fichero .parquet, .xlsx o .h5"
            )

        def flush_chunk() -> None:
            """Write pending rows for chunk-friendly formats."""
            nonlocal hdf_initialized, parquet_writer

            if not chunk_rows:
                return

            if output_is_excel:
                excel_rows.extend(chunk_rows)
                chunk_rows.clear()
                return

            chunk_df = pd.DataFrame(chunk_rows)
            if output_is_parquet:
                import pyarrow as pa
                import pyarrow.parquet as pq

                table = pa.Table.from_pandas(chunk_df, preserve_index=False)
                if parquet_writer is None:
                    parquet_writer = pq.ParquetWriter(self._args.output, table.schema)
                parquet_writer.write_table(table)
            elif output_is_hdf:
                chunk_df.to_hdf(
                    self._args.output,
                    key="spectrogram",
                    mode="a" if hdf_initialized else "w",
                    format="table",
                    append=hdf_initialized,
                    index=False,
                )
                hdf_initialized = True

            chunk_rows.clear()

        requested_start_local = TimeProcessor.to_local_datetime(self._args.from_time, tz)
        requested_stop_local = TimeProcessor.to_local_datetime(self._args.until, tz)

        if self._args.verbose:
            print("Modo spectrogram activado")
            print("Zona local usada:", tz)
            print("Ventana de análisis (s):", spec_cfg.window_s)
            print("Delta t (s):", spec_cfg.delta_t_s)
            print("Frecuencia máxima (Hz):", spec_cfg.fmax_hz)
            print("Resample (Hz):", spec_cfg.resample_hz)
            print("Señales:", spec_cfg.signals)
            print("Pies:", spec_cfg.feet)
            print()

        # 1. Load both feet first
        foot_data: Dict[str, pd.DataFrame] = {}
        foot_summaries: Dict[str, Dict[str, Any]] = {}
        for foot in spec_cfg.feet:
            df = self._load_foot_dataframe(foot)
            if df is None:
                self._write_audit_json(
                    "connection_failed",
                    foot_summaries=foot_summaries,
                )
                return
            foot_summaries[foot] = self._summarize_foot_dataframe(df, foot)
            if df.empty:
                print(f"⚠️ No hay datos para el pie {foot}.")
                continue
            foot_data[foot] = df

        missing_feet = [
            f for f in spec_cfg.feet
            if foot_summaries.get(f, {}).get("rows", 0) == 0
        ]
        if missing_feet:
            self._write_audit_json(
                "no_records" if len(missing_feet) == len(spec_cfg.feet) else "only_some_feet",
                foot_summaries=foot_summaries,
                missing_feet=missing_feet,
            )
            return

        # 2. Resample each foot independently first
        foot_rs: Dict[str, pd.DataFrame] = {}
        foot_min: Dict[str, pd.Timestamp] = {}
        foot_max: Dict[str, pd.Timestamp] = {}

        for foot, df in foot_data.items():
            df_rs = Resampler.resample_dataframe(
                df,
                spec_cfg.resample_hz,
                spec_cfg.signals,
                max_interpolate_gap_s=spec_cfg.max_interpolate_gap_s,
            )
            if df_rs.empty:
                print(f"⚠️ No hay datos remuestreados para el pie {foot}.")
                self._write_audit_json(
                    "no_resampled_data",
                    foot_summaries=foot_summaries,
                    failed_foot=foot,
                )
                return

            foot_rs[foot] = df_rs
            foot_min[foot] = df_rs.index.min()
            foot_max[foot] = df_rs.index.max()

        # 3. Convert requested local interval to UTC-like timestamps used internally
        requested_start_ts = pd.Timestamp(
            TimeProcessor.to_utc_datetime(self._args.from_time, tz)
        )
        requested_stop_ts = pd.Timestamp(
            TimeProcessor.to_utc_datetime(self._args.until, tz)
        )

        # 4. Real intersection between both feet and requested interval
        start_common = max(
            requested_start_ts,
            max(foot_min.values()),
        )
        stop_common = min(
            requested_stop_ts,
            min(foot_max.values()),
        )

        if stop_common <= start_common:
            print("No existe intersección temporal común entre ambos pies.")
            print(
                "Revisa el rango de fechas, la referencia y que ambos pies tengan "
                "registros en el intervalo consultado."
            )
            self._write_audit_json(
                "no_common_interval",
                foot_summaries=foot_summaries,
                common_start_utc=start_common,
                common_stop_utc=stop_common,
            )
            return

        half_window = timedelta(seconds=spec_cfg.window_s / 2.0)
        start_center = start_common + half_window
        stop_center = stop_common - half_window

        if stop_center <= start_center:
            print("La intersección temporal común no permite ventanas completas.")
            print(
                "Amplía el rango de fechas o reduce spectrogram.window_s para poder "
                "generar al menos una ventana completa."
            )
            self._write_audit_json(
                "no_complete_windows",
                foot_summaries=foot_summaries,
                common_start_utc=start_common,
                common_stop_utc=stop_common,
                first_possible_center_utc=start_center,
                last_possible_center_utc=stop_center,
            )
            return

        # 5. Build common time grid and reindex both feet onto the same grid
        common_index = self._build_common_time_index(
            start_ts=start_common,
            stop_ts=stop_common,
            resample_hz=spec_cfg.resample_hz,
        )

        for foot in spec_cfg.feet:
            df_rs = foot_rs[foot].reindex(common_index)
            foot_rs[foot] = df_rs

        # 6. Generate centers only inside full-window common interval
        if self._args.center_anchor_time:
            core_from = self._args.core_from_time or self._args.from_time
            core_until = self._args.core_until or self._args.until
            core_start_ts = pd.Timestamp(
                TimeProcessor.to_utc_datetime(core_from, tz)
            )
            core_stop_ts = pd.Timestamp(
                TimeProcessor.to_utc_datetime(core_until, tz)
            )
            anchor_ts = pd.Timestamp(self._args.center_anchor_time)
            if anchor_ts.tzinfo is None:
                anchor_ts = anchor_ts.tz_localize("UTC")
            else:
                anchor_ts = anchor_ts.tz_convert("UTC")
            centers_local = self._generate_anchored_centers(
                anchor=anchor_ts,
                start_center=start_center,
                stop_center=stop_center,
                core_start=core_start_ts,
                core_stop=core_stop_ts,
                delta_t_s=spec_cfg.delta_t_s,
            )
        else:
            centers_local = TimeProcessor.generate_window_centers(
                start_dt=start_center.to_pydatetime(),
                stop_dt=stop_center.to_pydatetime(),
                window_s=spec_cfg.window_s,
                delta_t_s=spec_cfg.delta_t_s,
            )

        if self._args.verbose:
            print("Inicio común real:", start_common)
            print("Fin común real:", stop_common)
            print("Centros de ventana generados:", len(centers_local))
            print()

        # 7. Process centers, requiring complete windows for both feet
        for center_local in centers_local:
            center_ts = pd.Timestamp(center_local)
            start_ts = center_ts - half_window
            stop_ts = center_ts + half_window

            per_foot_windows: Dict[str, pd.DataFrame] = {}
            valid_for_both = True

            for foot in spec_cfg.feet:
                window_df = foot_rs[foot].loc[start_ts:stop_ts]

                if window_df.empty:
                    valid_for_both = False
                    skipped_empty_window += 1
                    break

                # Reject windows with insufficient real sensor samples.
                expected_samples = int(round(spec_cfg.window_s * spec_cfg.resample_hz)) + 1
                if len(window_df) < expected_samples:
                    valid_for_both = False
                    skipped_short_window += 1
                    break

                completeness = Resampler.window_sample_completeness(
                    window_df,
                    spec_cfg.signals,
                )
                if completeness < spec_cfg.min_window_completeness:
                    valid_for_both = False
                    skipped_low_completeness += 1
                    break

                window_df = Resampler.fill_short_window_gaps(
                    window_df.copy(),
                    spec_cfg.resample_hz,
                    spec_cfg.signals,
                    spec_cfg.max_interpolate_gap_s,
                )
                if window_df[spec_cfg.signals].isna().any().any():
                    valid_for_both = False
                    skipped_remaining_nan += 1
                    break

                window_df.attrs["sample_completeness"] = completeness
                per_foot_windows[foot] = window_df

            if not valid_for_both:
                continue

            for foot in spec_cfg.feet:
                window_df = per_foot_windows[foot]

                for signal_name in spec_cfg.signals:
                    signal_values = window_df[signal_name].to_numpy(dtype=float)
                    if signal_values.size < 2:
                        continue

                    freqs, powers = spectrum_engine.compute(signal_values)
                    row = ParquetRowBuilder.build_row(
                        reference=self._args.reference,
                        foot=foot,
                        signal_name=signal_name,
                        time_center=center_ts,
                        freqs=freqs,
                        powers=powers,
                    )
                    row["sample_completeness"] = float(
                        window_df.attrs.get("sample_completeness", 1.0)
                    )
                    chunk_rows.append(row)
                    total_rows += 1
                    if foot.lower() == "right":
                        rows_right += 1
                    else:
                        rows_left += 1

                    if len(chunk_rows) >= chunk_size:
                        flush_chunk()

        flush_chunk()
        if parquet_writer is not None:
            parquet_writer.close()

        if total_rows == 0:
            if self._args.verbose:
                print("Ventanas descartadas:")
                print(f"  vacías: {skipped_empty_window}")
                print(f"  demasiado cortas: {skipped_short_window}")
                print(f"  baja completitud: {skipped_low_completeness}")
                print(f"  NaN residuales: {skipped_remaining_nan}")
            print("No se han generado filas para el parquet.")
            print(
                "La consulta devolvió datos, pero ninguna ventana cumple los criterios "
                "de completitud, duración e intersección entre pies."
            )
            self._write_audit_json(
                "no_valid_windows",
                foot_summaries=foot_summaries,
                common_start_utc=start_common,
                common_stop_utc=stop_common,
                generated_centers=len(centers_local),
                skipped_windows={
                    "empty": skipped_empty_window,
                    "short": skipped_short_window,
                    "low_completeness": skipped_low_completeness,
                    "remaining_nan": skipped_remaining_nan,
                },
                total_rows=0,
            )
            return

        if output_is_parquet:
            print(f"Parquet guardado en: {self._args.output}")
        elif output_is_excel:
            out_df = pd.DataFrame(excel_rows)
            out_df.to_excel(self._args.output, index=False)
            print(f"Excel guardado en: {self._args.output}")
        elif output_is_hdf:
            print(f"HDF5 guardado en: {self._args.output}")

        print(f"Filas totales: {total_rows}")
        print(f"Right arriba: {rows_right} filas")
        print(f"Left abajo: {rows_left} filas")
        self._write_audit_json(
            "valid_spectrogram",
            foot_summaries=foot_summaries,
            common_start_utc=start_common,
            common_stop_utc=stop_common,
            generated_centers=len(centers_local),
            total_rows=total_rows,
            rows_by_foot={
                "Right": rows_right,
                "Left": rows_left,
            },
            skipped_windows={
                "empty": skipped_empty_window,
                "short": skipped_short_window,
                "low_completeness": skipped_low_completeness,
                "remaining_nan": skipped_remaining_nan,
            },
        )

    def run(self) -> None:
        """Run the selected extraction mode.

        Raises:
            ValueError: If the selected mode is unsupported or the spectrogram
                workflow cannot produce valid complete windows.
        """
        if self._args.dry_run:
            self.print_planned_queries()
            return

        if self._args.mode == "count":
            self.run_count()
        elif self._args.mode == "raw":
            self.run_raw()
        elif self._args.mode == "spectrogram":
            self.run_spectrogram()
        else:
            raise ValueError(f"Modo no soportado: {self._args.mode}")

    def close(self) -> None:
        """Close external resources."""
        if self._influx is not None:
            self._influx.close()


def main() -> None:
    """Run the extraction app directly from this module."""
    from gait_analysis.cli import CLI
    from gait_analysis.config import ConfigLoader

    args = CLI.parse()
    config = ConfigLoader(args.config).load()
    with ExtractApp(args=args, config=config) as app:
        app.run()


if __name__ == "__main__":
    main()
