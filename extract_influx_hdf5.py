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

from gait_analysis.app import ExtractApp
from gait_analysis.cli import CLI
from gait_analysis.config import ConfigLoader


def main() -> None:
    """Program entry point."""
    args = CLI.parse()
    config = ConfigLoader(args.config).load()
    app = ExtractApp(args=args, config=config)
    app.run()


if __name__ == "__main__":
    main()


