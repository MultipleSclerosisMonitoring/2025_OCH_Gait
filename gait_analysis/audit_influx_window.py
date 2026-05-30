#!/usr/bin/env python3
"""Audit InfluxDB coverage for one reference and time window."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gait_analysis.config import ConfigLoader
from gait_analysis.flux import FluxQueryBuilder
from gait_analysis.time_utils import TimeProcessor


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Comprueba cobertura de InfluxDB para una referencia, rango temporal "
            "y pies configurados. Genera un CSV de auditoria reproducible."
        )
    )
    p.add_argument("-f", "--from-time", required=True, help="Inicio local.")
    p.add_argument("-u", "--until", required=True, help="Fin local.")
    p.add_argument("-q", "--reference", required=True, help="Referencia a consultar.")
    p.add_argument(
        "-o",
        "--output",
        default="influx_window_audit.csv",
        help="CSV de salida.",
    )
    p.add_argument(
        "--config",
        default=".config.yaml",
        help="Ruta al YAML de configuracion.",
    )
    p.add_argument(
        "--from-tz",
        default="Europe/Madrid",
        help="Zona horaria si el YAML no define Location.zoneInfo.",
    )
    p.add_argument(
        "--print-query",
        action="store_true",
        help="Imprime las consultas Flux por pie.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo imprime conversion horaria y queries; no conecta con InfluxDB.",
    )
    return p


def build_flux(
    *,
    cfg: Any,
    reference: str,
    foot: str,
    start_iso: str,
    stop_iso: str,
) -> str:
    """Build a foot-specific Flux query."""
    return FluxQueryBuilder.build(
        bucket=cfg.influx.bucket,
        start_iso=start_iso,
        stop_iso=stop_iso,
        ref_tag=cfg.ref_tag,
        reference=reference,
        foot_tag=cfg.foot_tag,
        foot=foot,
        fields=cfg.spectrogram.signals,
        pivot=True,
    )


def summarize_foot(df: pd.DataFrame, foot: str) -> Dict[str, Any]:
    """Return row count and temporal bounds for one foot DataFrame."""
    summary: Dict[str, Any] = {
        f"{foot.lower()}_rows": int(len(df)),
        f"{foot.lower()}_min_time": "",
        f"{foot.lower()}_max_time": "",
    }
    if not df.empty and "_time" in df.columns:
        times = pd.to_datetime(df["_time"], utc=True, format="mixed")
        summary[f"{foot.lower()}_min_time"] = times.min().isoformat()
        summary[f"{foot.lower()}_max_time"] = times.max().isoformat()
    return summary


def compute_status(
    *,
    foot_summaries: Dict[str, Dict[str, Any]],
    feet: list[str],
) -> tuple[str, Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    """Classify coverage status and common temporal interval."""
    missing_feet = [foot for foot in feet if foot_summaries[foot][f"{foot.lower()}_rows"] == 0]
    if len(missing_feet) == len(feet):
        return "no_records", None, None
    if missing_feet:
        return "only_some_feet", None, None

    min_times = []
    max_times = []
    for foot in feet:
        min_key = f"{foot.lower()}_min_time"
        max_key = f"{foot.lower()}_max_time"
        min_times.append(pd.Timestamp(foot_summaries[foot][min_key]))
        max_times.append(pd.Timestamp(foot_summaries[foot][max_key]))

    common_start = max(min_times)
    common_stop = min(max_times)
    if common_stop <= common_start:
        return "no_common_interval", common_start, common_stop
    return "valid_both_feet", common_start, common_stop


def main() -> None:
    """Run the audit."""
    args = build_parser().parse_args()
    cfg = ConfigLoader(args.config).load()
    tz = cfg.default_tz or args.from_tz
    start_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(args.from_time, tz)
    stop_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(args.until, tz)

    base_row: Dict[str, Any] = {
        "reference": args.reference,
        "from_local": args.from_time,
        "until_local": args.until,
        "timezone": tz,
        "from_utc": start_iso,
        "until_utc": stop_iso,
        "bucket": cfg.influx.bucket,
        "ref_tag": cfg.ref_tag,
        "foot_tag": cfg.foot_tag,
        "signals": ",".join(cfg.spectrogram.signals),
    }

    print("Referencia:", args.reference)
    print("Zona local usada:", tz)
    print("Inicio local:", args.from_time, "-> UTC (InfluxDB):", start_iso)
    print("Fin local:   ", args.until, "-> UTC (InfluxDB):", stop_iso)
    print()

    flux_by_foot = {
        foot: build_flux(
            cfg=cfg,
            reference=args.reference,
            foot=foot,
            start_iso=start_iso,
            stop_iso=stop_iso,
        )
        for foot in cfg.spectrogram.feet
    }
    if args.print_query or args.dry_run:
        for foot, flux in flux_by_foot.items():
            print(f"=== Query {foot} ===")
            print(flux)

    if args.dry_run:
        print("Dry run: no se consultara InfluxDB ni se escribira CSV.")
        return

    foot_summaries: Dict[str, Dict[str, Any]] = {}
    try:
        from gait_analysis.influx_service import InfluxService

        with InfluxService(cfg.influx) as influx:
            for foot, flux in flux_by_foot.items():
                tables = influx.query(flux)
                df = influx.tables_to_dataframe(tables)
                foot_summaries[foot] = summarize_foot(df, foot)
    except Exception as exc:
        row = dict(base_row)
        row["status"] = "connection_failed"
        row["error_type"] = type(exc).__name__
        row["error"] = str(exc)
        out = pd.DataFrame([row])
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(output, index=False)
        print("No se pudo consultar InfluxDB.")
        print(f"Detalle: {type(exc).__name__}: {exc}")
        print(f"Audit guardado en: {output}")
        return

    status, common_start, common_stop = compute_status(
        foot_summaries=foot_summaries,
        feet=list(cfg.spectrogram.feet),
    )

    row = dict(base_row)
    for summary in foot_summaries.values():
        row.update(summary)
    row["common_start_utc"] = common_start.isoformat() if common_start is not None else ""
    row["common_stop_utc"] = common_stop.isoformat() if common_stop is not None else ""
    row["status"] = status

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row]).to_csv(output, index=False)

    print(f"Audit guardado en: {output}")
    print("Status:", status)
    for foot in cfg.spectrogram.feet:
        prefix = foot.lower()
        print(
            f"{foot}: {row.get(prefix + '_rows', 0)} filas "
            f"({row.get(prefix + '_min_time', '')} -> {row.get(prefix + '_max_time', '')})"
        )
    if common_start is not None:
        print("Intersección común:", common_start, "->", common_stop)


if __name__ == "__main__":
    main()
