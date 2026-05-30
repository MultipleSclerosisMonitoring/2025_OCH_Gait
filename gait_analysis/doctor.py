#!/usr/bin/env python3
"""One-shot diagnostic command for InfluxDB extraction windows."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gait_analysis.audit_influx_window import build_flux, compute_status, summarize_foot
from gait_analysis.config import ConfigLoader
from gait_analysis.time_utils import TimeProcessor


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Diagnostica una ventana antes de extraer: valida fechas, muestra "
            "queries, prueba InfluxDB y recomienda el siguiente comando."
        )
    )
    p.add_argument("-f", "--from-time", required=True, help="Inicio local.")
    p.add_argument("-u", "--until", required=True, help="Fin local.")
    p.add_argument("-q", "--reference", required=True, help="Referencia a consultar.")
    p.add_argument("--config", default=".config.yaml", help="YAML de configuracion.")
    p.add_argument(
        "--from-tz",
        default="Europe/Madrid",
        help="Zona horaria si el YAML no define Location.zoneInfo.",
    )
    p.add_argument(
        "--print-query",
        action="store_true",
        help="Imprime las consultas Flux.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="No conecta a InfluxDB; solo valida config, fechas y queries.",
    )
    p.add_argument(
        "--json-output",
        help="Guarda el diagnostico completo en JSON.",
    )
    return p


def git_commit() -> str:
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


def json_default(value: Any) -> str:
    """Serialize timestamp-like values."""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def recommendation(status: str, *, reference: str, from_time: str, until: str) -> str:
    """Return a practical next step for a status."""
    if status == "valid_both_feet":
        return (
            "La ventana tiene ambos pies. Siguiente paso recomendado: ejecutar "
            f"--mode raw y despues --mode spectrogram para {reference}."
        )
    if status == "connection_failed":
        return (
            "No es un problema de fechas todavia: primero hay que resolver acceso "
            "a InfluxDB, VPN, firewall o URL/token."
        )
    if status == "dependency_missing":
        return "Activa el entorno virtual del proyecto antes de conectar a InfluxDB."
    if status == "no_records":
        return (
            "La consulta no devuelve registros. Revisa referencia, zona horaria y "
            "si el rango existe en Grafana/Influx."
        )
    if status == "only_some_feet":
        return (
            "Solo hay cobertura para parte de los pies. Se puede extraer raw para "
            "inspeccion, pero spectrogram bilateral no sera valido."
        )
    if status == "no_common_interval":
        return (
            "Ambos pies tienen datos, pero no se solapan temporalmente. Revisa "
            "sincronizacion o usa raw para inspeccion."
        )
    if status == "invalid_time_range":
        return f"Corrige el rango: until debe ser posterior a from ({from_time} -> {until})."
    return "Revisa el diagnostico y ejecuta audit_influx_window con --print-query."


def main() -> None:
    """Run the doctor diagnostic."""
    args = build_parser().parse_args()
    result: Dict[str, Any] = {
        "reference": args.reference,
        "from_local": args.from_time,
        "until_local": args.until,
        "config": args.config,
        "git_commit": git_commit(),
    }

    try:
        cfg = ConfigLoader(args.config).load()
    except Exception as exc:
        result.update(
            {
                "status": "config_failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        print("Config: ERROR")
        print(f"Detalle: {type(exc).__name__}: {exc}")
        if args.json_output:
            Path(args.json_output).write_text(
                json.dumps(result, indent=2, ensure_ascii=False, default=json_default),
                encoding="utf-8",
            )
        return

    tz = cfg.default_tz or args.from_tz
    try:
        start_dt = TimeProcessor.to_utc_datetime(args.from_time, tz)
        stop_dt = TimeProcessor.to_utc_datetime(args.until, tz)
        start_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(args.from_time, tz)
        stop_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(args.until, tz)
    except Exception as exc:
        result.update(
            {
                "status": "invalid_datetime",
                "timezone": tz,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        print("Fechas: ERROR")
        print(f"Detalle: {type(exc).__name__}: {exc}")
        if args.json_output:
            Path(args.json_output).write_text(
                json.dumps(result, indent=2, ensure_ascii=False, default=json_default),
                encoding="utf-8",
            )
        return

    result.update(
        {
            "timezone": tz,
            "from_utc": start_iso,
            "until_utc": stop_iso,
            "bucket": cfg.influx.bucket,
            "ref_tag": cfg.ref_tag,
            "foot_tag": cfg.foot_tag,
            "signals": list(cfg.spectrogram.signals),
            "feet": list(cfg.spectrogram.feet),
        }
    )

    print("Config: OK")
    print("Referencia:", args.reference)
    print("Zona local usada:", tz)
    print("Inicio local:", args.from_time, "-> UTC (InfluxDB):", start_iso)
    print("Fin local:   ", args.until, "-> UTC (InfluxDB):", stop_iso)
    print("Bucket:", cfg.influx.bucket)
    print("Tags:", cfg.ref_tag, "/", cfg.foot_tag)
    print()

    if stop_dt <= start_dt:
        result["status"] = "invalid_time_range"
        result["recommendation"] = recommendation(
            "invalid_time_range",
            reference=args.reference,
            from_time=args.from_time,
            until=args.until,
        )
        print("Status: invalid_time_range")
        print(result["recommendation"])
        if args.json_output:
            Path(args.json_output).write_text(
                json.dumps(result, indent=2, ensure_ascii=False, default=json_default),
                encoding="utf-8",
            )
        return

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
    result["queries_by_foot"] = flux_by_foot

    if args.print_query or args.dry_run:
        for foot, flux in flux_by_foot.items():
            print(f"=== Query {foot} ===")
            print(flux)

    if args.dry_run:
        result["status"] = "dry_run_ok"
        result["recommendation"] = "Ejecuta doctor sin --dry-run para probar InfluxDB."
        print("Status: dry_run_ok")
        print(result["recommendation"])
        if args.json_output:
            Path(args.json_output).write_text(
                json.dumps(result, indent=2, ensure_ascii=False, default=json_default),
                encoding="utf-8",
            )
        return

    foot_summaries: Dict[str, Dict[str, Any]] = {}
    try:
        from gait_analysis.influx_service import InfluxService

        with InfluxService(cfg.influx) as influx:
            for foot, flux in flux_by_foot.items():
                tables = influx.query(flux)
                df = influx.tables_to_dataframe(tables)
                foot_summaries[foot] = summarize_foot(df, foot)
    except ModuleNotFoundError as exc:
        result.update(
            {
                "status": "dependency_missing",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
    except Exception as exc:
        result.update(
            {
                "status": "connection_failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
    else:
        status, common_start, common_stop = compute_status(
            foot_summaries=foot_summaries,
            feet=list(cfg.spectrogram.feet),
        )
        result.update(
            {
                "status": status,
                "foot_summaries": foot_summaries,
                "common_start_utc": common_start,
                "common_stop_utc": common_stop,
            }
        )

    status = str(result["status"])
    result["recommendation"] = recommendation(
        status,
        reference=args.reference,
        from_time=args.from_time,
        until=args.until,
    )

    print("Status:", status)
    if foot_summaries:
        for foot in cfg.spectrogram.feet:
            summary = foot_summaries.get(foot, {})
            print(
                f"{foot}: {summary.get(foot.lower() + '_rows', 0)} filas "
                f"({summary.get(foot.lower() + '_min_time', '')} -> "
                f"{summary.get(foot.lower() + '_max_time', '')})"
            )
        if result.get("common_start_utc"):
            print(
                "Interseccion comun:",
                result["common_start_utc"],
                "->",
                result["common_stop_utc"],
            )
    if result.get("error"):
        print(f"Detalle: {result['error_type']}: {result['error']}")
    print("Recomendacion:", result["recommendation"])

    if args.json_output:
        output = Path(args.json_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False, default=json_default),
            encoding="utf-8",
        )
        print(f"JSON guardado en: {output}")


if __name__ == "__main__":
    main()
