from __future__ import annotations

from datetime import timedelta
from types import TracebackType
from typing import Dict, List, Optional, Type
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from gait_analysis.flux import FluxQueryBuilder
from gait_analysis.influx_service import InfluxService
from gait_analysis.models import AppConfig, CliArgs
from gait_analysis.resampling import Resampler
from gait_analysis.spectrum import ParquetRowBuilder, PowerSpectrumEngine
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
        self._influx = InfluxService(config.influx)

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
        spec_cfg = self._config.spectrogram
        spectrum_engine = PowerSpectrumEngine(spec_cfg)
        rows_right = 0
        rows_left = 0
        total_rows = 0
        chunk_size = 5000
        chunk_rows: List[Dict[str, object]] = []
        excel_rows: List[Dict[str, object]] = []
        parquet_writer: Optional[pq.ParquetWriter] = None
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
        for foot in spec_cfg.feet:
            df = self._load_foot_dataframe(foot)
            if df.empty:
                print(f"⚠️ No hay datos para el pie {foot}.")
                return
            foot_data[foot] = df

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
                return

            foot_rs[foot] = df_rs
            foot_min[foot] = df_rs.index.min()
            foot_max[foot] = df_rs.index.max()

        # 3. Convert requested local interval to UTC-like timestamps used internally
        requested_start_ts = pd.Timestamp(requested_start_local.replace(tzinfo=ZoneInfo("UTC")))
        requested_stop_ts = pd.Timestamp(requested_stop_local.replace(tzinfo=ZoneInfo("UTC")))

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
            raise ValueError("No existe intersección temporal común entre ambos pies.")

        half_window = timedelta(seconds=spec_cfg.window_s / 2.0)
        start_center = start_common + half_window
        stop_center = stop_common - half_window

        if stop_center <= start_center:
            raise ValueError("La intersección temporal común no permite ventanas completas.")

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
            core_start_ts = pd.Timestamp(core_from, tz="UTC")
            core_stop_ts = pd.Timestamp(core_until, tz="UTC")
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
                    break

                # Reject windows with insufficient real sensor samples.
                expected_samples = int(round(spec_cfg.window_s * spec_cfg.resample_hz)) + 1
                if len(window_df) < expected_samples:
                    valid_for_both = False
                    break

                completeness = Resampler.window_sample_completeness(
                    window_df,
                    spec_cfg.signals,
                )
                if completeness < spec_cfg.min_window_completeness:
                    valid_for_both = False
                    break

                window_df = Resampler.fill_short_window_gaps(
                    window_df.copy(),
                    spec_cfg.resample_hz,
                    spec_cfg.signals,
                    spec_cfg.max_interpolate_gap_s,
                )
                if window_df[spec_cfg.signals].isna().any().any():
                    valid_for_both = False
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
            raise ValueError("No se han generado filas para el parquet.")

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

    def run(self) -> None:
        """Run the selected extraction mode.

        Raises:
            ValueError: If the selected mode is unsupported or the spectrogram
                workflow cannot produce valid complete windows.
        """
        if self._args.mode == "count":
            self.run_count()
        elif self._args.mode == "spectrogram":
            self.run_spectrogram()
        else:
            raise ValueError(f"Modo no soportado: {self._args.mode}")

    def close(self) -> None:
        """Close external resources."""
        self._influx.close()
