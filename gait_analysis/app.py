from __future__ import annotations

from datetime import timedelta
from typing import Dict, List
from zoneinfo import ZoneInfo

import pandas as pd

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
        rows_right: List[Dict[str, object]] = []
        rows_left: List[Dict[str, object]] = []

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

            foot_rows: List[Dict[str, object]] = []
            half_window = timedelta(seconds=spec_cfg.window_s / 2.0)

            for center_local in centers_local:
                center_ts = pd.Timestamp(center_local.replace(tzinfo=ZoneInfo("UTC")))
                start_ts = pd.Timestamp((center_local - half_window).replace(tzinfo=ZoneInfo("UTC")))
                stop_ts = pd.Timestamp((center_local + half_window).replace(tzinfo=ZoneInfo("UTC")))

                window_df = df_rs.loc[start_ts:stop_ts]

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
                        time_center=center_ts,
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

        output_path = self._args.output.lower()
        if output_path.endswith(".parquet"):
            out_df.to_parquet(self._args.output, index=False)
            print(f"Parquet guardado en: {self._args.output}")
        elif output_path.endswith(".xlsx"):
            out_df.to_excel(self._args.output, index=False)
            print(f"Excel guardado en: {self._args.output}")
        elif output_path.endswith(".h5") or output_path.endswith(".hdf5"):
            out_df.to_hdf(self._args.output, key="spectrogram", mode="w")
            print(f"HDF5 guardado en: {self._args.output}")
        else:
            raise ValueError(
                "Formato de salida no soportado. Usa un fichero .parquet, .xlsx o .h5"
            )

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