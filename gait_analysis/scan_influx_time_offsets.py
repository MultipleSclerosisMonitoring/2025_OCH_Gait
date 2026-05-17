#!/usr/bin/env python3
"""Scan Influx coverage around labeled intervals with time offsets."""

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
            "Prueba offsets temporales alrededor de intervalos etiquetados para "
            "buscar cobertura Influx aunque el ground truth no coincida exactamente."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        default="experiment_configs/patient_candidate_inventory.csv",
        help="Inventario de candidatos generado desde ground truth.",
    )
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Configuracion con credenciales/tags de Influx.",
    )
    p.add_argument(
        "-o",
        "--output",
        default="experiment_configs/patient_candidate_time_offset_scan.csv",
        help="CSV de salida con cobertura por offset.",
    )
    p.add_argument(
        "--label",
        default="walking",
        choices=["walking", "not_walking"],
        help="Etiqueta a escanear.",
    )
    p.add_argument(
        "--new-patients-only",
        action="store_true",
        help="Escanea solo referencias no usadas en entrenamiento.",
    )
    p.add_argument(
        "--offset-minutes",
        nargs="+",
        type=int,
        default=[-120, -60, -30, -15, -5, 0, 5, 15, 30, 60, 120],
        help="Offsets en minutos que se aplican al intervalo etiquetado.",
    )
    p.add_argument(
        "--max-intervals",
        type=int,
        default=None,
        help="Limita el numero de intervalos a escanear.",
    )
    return p


def format_for_influx(ts: pd.Timestamp) -> str:
    """Format timestamp for the project's Influx time helper."""
    return pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def count_shifted_interval(
    *,
    influx: InfluxService,
    cfg,
    reference: str,
    start: pd.Timestamp,
    stop: pd.Timestamp,
) -> dict[str, int]:
    """Count records for one shifted interval and all configured feet."""
    tz = cfg.default_tz or "Europe/Madrid"
    start_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(format_for_influx(start), tz)
    stop_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(format_for_influx(stop), tz)

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
    """Run offset scan and save results."""
    args = build_parser().parse_args()
    warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

    cfg = ConfigLoader(args.config).load()
    candidates = pd.read_csv(args.input)
    candidates["datefrom"] = pd.to_datetime(candidates["datefrom"])
    candidates["dateuntil"] = pd.to_datetime(candidates["dateuntil"])
    selected = candidates[candidates["mov_type"].eq(args.label)].copy()
    if args.new_patients_only:
        selected = selected[selected["already_in_training"].eq(False)].copy()
    selected = selected.sort_values(["duration_s"], ascending=False)
    if args.max_intervals is not None:
        selected = selected.head(args.max_intervals)

    rows = []
    with InfluxService(cfg.influx) as influx:
        for _, interval in selected.iterrows():
            for offset_min in args.offset_minutes:
                delta = pd.Timedelta(minutes=offset_min)
                shifted_start = interval["datefrom"] + delta
                shifted_stop = interval["dateuntil"] + delta
                print(
                    "Checking",
                    interval["Reference"],
                    interval["mov_type"],
                    f"offset={offset_min}m",
                    shifted_start,
                    shifted_stop,
                )
                try:
                    counts = count_shifted_interval(
                        influx=influx,
                        cfg=cfg,
                        reference=str(interval["Reference"]),
                        start=shifted_start,
                        stop=shifted_stop,
                    )
                    error = ""
                except Exception as exc:  # noqa: BLE001 - scan should continue.
                    counts = {
                        f"{foot.lower()}_records": 0 for foot in cfg.spectrogram.feet
                    }
                    error = str(exc)

                rows.append(
                    {
                        "Reference": interval["Reference"],
                        "mov_type": interval["mov_type"],
                        "original_datefrom": interval["datefrom"],
                        "original_dateuntil": interval["dateuntil"],
                        "duration_s": interval["duration_s"],
                        "offset_minutes": offset_min,
                        "shifted_datefrom": shifted_start,
                        "shifted_dateuntil": shifted_stop,
                        **counts,
                        "coverage_error": error,
                    }
                )

    results = pd.DataFrame(rows)
    record_cols = [f"{foot.lower()}_records" for foot in cfg.spectrogram.feet]
    record_values = results[record_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    results["valid_both_feet"] = record_values.gt(0).all(axis=1)
    results["total_records"] = record_values.sum(axis=1)
    results = results.sort_values(
        ["valid_both_feet", "total_records", "Reference", "offset_minutes"],
        ascending=[False, False, True, True],
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output, index=False)

    print(f"Output: {output}")
    print(f"Rows: {len(results)}")
    print()
    print("Best matches:")
    print(
        results[
            [
                "Reference",
                "mov_type",
                "original_datefrom",
                "offset_minutes",
                "right_records",
                "left_records",
                "valid_both_feet",
            ]
        ]
        .head(20)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
