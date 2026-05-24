from __future__ import annotations

import argparse
from typing import List, Optional

from gait_analysis.models import CliArgs


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
            default="salida.parquet",
            help=(
                "Fichero de salida. En mode=count no se usa. "
                "En mode=spectrogram se soportan .parquet, .xlsx, .h5 y .hdf5."
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
        p.add_argument(
            "--core-from-time",
            default=None,
            help=argparse.SUPPRESS,
        )
        p.add_argument(
            "--core-until",
            default=None,
            help=argparse.SUPPRESS,
        )
        p.add_argument(
            "--center-anchor-time",
            default=None,
            help=argparse.SUPPRESS,
        )
        p.add_argument(
            "--window-s",
            type=float,
            default=None,
            help=argparse.SUPPRESS,
        )
        p.add_argument(
            "--min-window-completeness",
            type=float,
            default=None,
            help=argparse.SUPPRESS,
        )
        p.add_argument(
            "--max-interpolate-gap-s",
            type=float,
            default=None,
            help=argparse.SUPPRESS,
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
            core_from_time=ns.core_from_time,
            core_until=ns.core_until,
            center_anchor_time=ns.center_anchor_time,
            window_s=ns.window_s,
            min_window_completeness=ns.min_window_completeness,
            max_interpolate_gap_s=ns.max_interpolate_gap_s,
        )
