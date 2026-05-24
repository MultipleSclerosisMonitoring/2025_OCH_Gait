#!/usr/bin/env python3
"""Scan Influx coverage for manually curated candidate patient windows."""

from __future__ import annotations

import argparse
from pathlib import Path
import warnings

import pandas as pd
import urllib3

from gait_analysis.build_patient_candidate_inventory import build_count_query
from gait_analysis.config import ConfigLoader
from gait_analysis.influx_service import InfluxService
from gait_analysis.time_utils import TimeProcessor


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Comprueba cobertura de Influx para una lista manual de candidatos "
            "con ventanas aproximadas."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        default="experiment_configs/high_priority_new_patient_candidates.csv",
        help="CSV con Reference/datefrom/dateuntil de candidatos manuales.",
    )
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Configuracion con credenciales/tags de Influx.",
    )
    p.add_argument(
        "-o",
        "--output",
        default="experiment_configs/high_priority_new_patient_candidates_coverage.csv",
        help="CSV de salida con cobertura por pie y candidato.",
    )
    p.add_argument(
        "--max-candidates",
        type=int,
        default=None,
        help="Limita el numero de candidatos a comprobar.",
    )
    p.add_argument(
        "--offset-minutes",
        nargs="+",
        type=int,
        default=[-720, -360, -180, -120, -60, -30, -15, -5, 0, 5, 15, 30, 60, 120, 180, 360, 720],
        help="Offsets en minutos que se aplican a cada ventana candidata.",
    )
    return p


def count_interval(
    influx: InfluxService,
    cfg,
    *,
    reference: str,
    start_ts: pd.Timestamp,
    stop_ts: pd.Timestamp,
) -> dict[str, int]:
    """Count records for both feet in one interval."""
    tz = cfg.default_tz or "Europe/Madrid"
    start_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(
        start_ts.strftime("%Y-%m-%d %H:%M:%S"),
        tz,
    )
    stop_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(
        stop_ts.strftime("%Y-%m-%d %H:%M:%S"),
        tz,
    )

    counts: dict[str, int] = {}
    for foot in cfg.spectrogram.feet:
        flux = build_count_query(
            bucket=cfg.influx.bucket,
            start_iso=start_iso,
            stop_iso=stop_iso,
            ref_tag=cfg.ref_tag,
            reference=reference,
            foot_tag=cfg.foot_tag,
            foot=foot,
            fields=cfg.spectrogram.signals,
        )
        total = 0
        for table in influx.query(flux):
            for record in table.records:
                value = record.get_value()
                if value is not None:
                    total += int(value)
        counts[f"{foot.lower()}_records"] = total
    return counts


def main() -> None:
    """Run coverage scan for the manual candidate list."""
    args = build_parser().parse_args()
    warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

    cfg = ConfigLoader(args.config).load()
    candidates = pd.read_csv(args.input)
    candidates["datefrom"] = pd.to_datetime(candidates["datefrom"], format="mixed")
    candidates["dateuntil"] = pd.to_datetime(candidates["dateuntil"], format="mixed")
    candidates["duration_s"] = (
        candidates["dateuntil"] - candidates["datefrom"]
    ).dt.total_seconds()
    candidates = candidates.sort_values(
        ["priority", "duration_s", "Reference"], ascending=[True, False, True]
    )
    if args.max_candidates is not None:
        candidates = candidates.head(args.max_candidates)

    rows = []
    with InfluxService(cfg.influx) as influx:
        for _, row in candidates.iterrows():
            for offset_min in args.offset_minutes:
                shifted_start = row["datefrom"] + pd.Timedelta(minutes=offset_min)
                shifted_stop = row["dateuntil"] + pd.Timedelta(minutes=offset_min)
                print(
                    "Checking",
                    row["Reference"],
                    f"offset={offset_min}m",
                    shifted_start,
                    shifted_stop,
                    f"priority={row['priority']}",
                )
                try:
                    counts = count_interval(
                        influx,
                        cfg,
                        reference=str(row["Reference"]),
                        start_ts=shifted_start,
                        stop_ts=shifted_stop,
                    )
                    error = ""
                except Exception as exc:  # noqa: BLE001 - scan should continue.
                    counts = {
                        f"{foot.lower()}_records": 0 for foot in cfg.spectrogram.feet
                    }
                    error = str(exc)

                rows.append(
                    {
                        "priority": row["priority"],
                        "Reference": row["Reference"],
                        "datefrom": row["datefrom"],
                        "dateuntil": row["dateuntil"],
                        "duration_s": row["duration_s"],
                        "offset_minutes": offset_min,
                        "shifted_datefrom": shifted_start,
                        "shifted_dateuntil": shifted_stop,
                        **counts,
                        "coverage_error": error,
                    }
                )

    candidates = pd.DataFrame(rows)
    record_cols = [f"{foot.lower()}_records" for foot in cfg.spectrogram.feet]
    record_values = candidates[record_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    candidates["valid_both_feet"] = record_values.gt(0).all(axis=1)
    candidates["total_records"] = record_values.sum(axis=1)
    candidates = candidates.sort_values(
        ["valid_both_feet", "total_records", "priority", "Reference", "offset_minutes"],
        ascending=[False, False, True, True, True],
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(output, index=False)

    print(f"Output: {output}")
    print(f"Rows: {len(candidates)}")
    print()
    print("Top candidates:")
    print(
        candidates[
            [
                "priority",
                "Reference",
                "datefrom",
                "dateuntil",
                "offset_minutes",
                "right_records",
                "left_records",
                "valid_both_feet",
                "total_records",
            ]
        ]
        .head(20)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
