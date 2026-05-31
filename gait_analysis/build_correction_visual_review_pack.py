#!/usr/bin/env python3
"""Build local visual review artifacts for audited label corrections.

The script reads the correction audit table, extracts the suspicious intervals
from InfluxDB in raw mode, and generates plots plus a review template.
Raw parquet files are intentionally written under ``salidas_test/`` by default
so they remain local and do not bloat the repository history.
"""

from __future__ import annotations

import argparse
import json
import html
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = "results/auto_influx_extension_correction_visual_audit_table.csv"
DEFAULT_CONFIG = "experiment_configs/config_window_1s.yaml"
DEFAULT_OUTPUT_DIR = "results/correction_visual_review"
DEFAULT_RAW_DIR = "salidas_test/correction_visual_review/raw"
LOCAL_TZ = "Europe/Madrid"


@dataclass(frozen=True)
class ReviewInterval:
    """One suspicious interval selected for visual review."""

    review_id: str
    reference: str
    dataset_source: str
    old_label: str
    new_label: str
    start_utc: pd.Timestamp
    end_utc: pd.Timestamp
    windows: int
    duration_s: float
    models: int
    mean_prob_walking: float
    row: dict[str, object]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extrae de InfluxDB los intervalos sospechosos de la auditoria de "
            "etiquetas y genera un paquete local de revision visual."
        )
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="CSV de auditoria")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="YAML de configuracion")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directorio de artefactos revisables")
    parser.add_argument("--raw-dir", default=DEFAULT_RAW_DIR, help="Directorio local para parquets raw")
    parser.add_argument("--limit", type=int, default=None, help="Numero maximo de intervalos a procesar")
    parser.add_argument("--margin-seconds", type=float, default=10.0, help="Margen extra alrededor del intervalo")
    parser.add_argument("--from-tz", default=LOCAL_TZ, help="Zona horaria local usada por el extractor")
    parser.add_argument("--resume-existing", action="store_true", help="Reutiliza parquets raw existentes")
    parser.add_argument("--skip-extract", action="store_true", help="No conecta a InfluxDB; solo genera artefactos con raw existente")
    parser.add_argument(
        "--extract-timeout-seconds",
        type=float,
        default=120.0,
        help="Timeout maximo por intervalo al invocar el extractor raw",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Muestra la salida del extractor")
    return parser.parse_args()


def safe_token(value: object, max_len: int = 80) -> str:
    text = str(value)
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")
    return text[:max_len] or "value"


def local_cli_time(ts: pd.Timestamp, tz_name: str) -> str:
    return ts.tz_convert(tz_name).strftime("%Y-%m-%d %H:%M:%S")


def load_intervals(path: Path, limit: int | None) -> list[ReviewInterval]:
    df = pd.read_csv(path)
    required = {
        "reference",
        "dataset_source",
        "old_label",
        "new_label",
        "start_utc",
        "end_utc",
        "windows",
        "duration_s",
        "models",
        "mean_prob_walking",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas requeridas en {path}: {sorted(missing)}")

    df = df.copy()
    df["start_utc"] = df["start_utc"].map(lambda value: pd.to_datetime(value, utc=True))
    df["end_utc"] = df["end_utc"].map(lambda value: pd.to_datetime(value, utc=True))
    df = df.sort_values(
        ["models", "windows", "mean_prob_walking", "reference", "start_utc"],
        ascending=[False, False, False, True, True],
    ).reset_index(drop=True)
    if limit is not None:
        df = df.head(limit)

    intervals: list[ReviewInterval] = []
    for idx, row in df.iterrows():
        intervals.append(
            ReviewInterval(
                review_id=f"{idx + 1:03d}",
                reference=str(row["reference"]),
                dataset_source=str(row["dataset_source"]),
                old_label=str(row["old_label"]),
                new_label=str(row["new_label"]),
                start_utc=row["start_utc"],
                end_utc=row["end_utc"],
                windows=int(row["windows"]),
                duration_s=float(row["duration_s"]),
                models=int(row["models"]),
                mean_prob_walking=float(row["mean_prob_walking"]),
                row=row.to_dict(),
            )
        )
    return intervals


def raw_output_path(raw_dir: Path, interval: ReviewInterval) -> Path:
    filename = (
        f"{interval.review_id}_{safe_token(interval.reference)}_"
        f"{safe_token(interval.old_label)}_to_{safe_token(interval.new_label)}.parquet"
    )
    return raw_dir / filename


def audit_output_path(raw_path: Path) -> Path:
    if raw_path.suffix:
        return raw_path.with_suffix(".audit.json")
    return raw_path.with_name(raw_path.name + ".audit.json")


def read_audit_status(raw_path: Path) -> tuple[str, str]:
    audit_path = audit_output_path(raw_path)
    if not audit_path.exists():
        return ("", "")
    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return ("invalid_audit", str(exc))
    return (str(audit.get("status", "")), str(audit_path))


def run_extraction(
    interval: ReviewInterval,
    output_path: Path,
    config_path: Path,
    margin_seconds: float,
    from_tz: str,
    resume_existing: bool,
    skip_extract: bool,
    verbose: int,
    timeout_seconds: float,
) -> tuple[str, str]:
    if skip_extract:
        return ("skipped", "skip-extract activo")
    if resume_existing and output_path.exists() and output_path.stat().st_size > 0:
        return ("reused", "raw parquet existente")

    margin = pd.Timedelta(seconds=margin_seconds)
    from_time = local_cli_time(interval.start_utc - margin, from_tz)
    until = local_cli_time(interval.end_utc + margin, from_tz)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "extract_influx_hdf5.py",
        "--mode",
        "raw",
        "--config",
        str(config_path),
        "--from-tz",
        from_tz,
        "-f",
        from_time,
        "-u",
        until,
        "-q",
        interval.reference,
        "-o",
        str(output_path),
    ]
    if verbose:
        command.append("-" + ("v" * verbose))

    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        output = "\n".join(part.strip() for part in (exc.stdout, exc.stderr) if part)
        detail = f"timeout tras {timeout_seconds:g}s"
        if output:
            detail = f"{detail}\n{output[-4000:]}"
        return ("timeout", detail)
    combined = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part.strip())
    if proc.returncode == 0:
        return ("ok", combined)
    return ("failed", combined[-4000:] if combined else f"returncode={proc.returncode}")


def read_raw(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    df = pd.read_parquet(path)
    if "_time" in df.columns:
        df["_time"] = pd.to_datetime(df["_time"], utc=True, errors="coerce")
    return df


def add_norm_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    acc_cols = ["Ax", "Ay", "Az"]
    gyro_cols = ["Gx", "Gy", "Gz"]
    if set(acc_cols).issubset(df.columns):
        df["acc_norm"] = (df[acc_cols].astype(float).pow(2).sum(axis=1)).pow(0.5)
    if set(gyro_cols).issubset(df.columns):
        df["gyro_norm"] = (df[gyro_cols].astype(float).pow(2).sum(axis=1)).pow(0.5)
    return df


def plot_interval(interval: ReviewInterval, raw_df: pd.DataFrame, plot_path: Path) -> tuple[str, str]:
    if raw_df.empty:
        return ("skipped", "sin datos raw")
    if "_time" not in raw_df.columns:
        return ("skipped", "falta columna _time")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = add_norm_columns(raw_df)
    available = [name for name in ["acc_norm", "gyro_norm"] if name in df.columns]
    if not available:
        available = [name for name in ["Ax", "Ay", "Az", "Gx", "Gy", "Gz"] if name in df.columns]
    if not available:
        return ("skipped", "no hay senales graficables")

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(len(available), 1, figsize=(14, 3.2 * len(available)), sharex=True)
    if not isinstance(axes, Iterable):
        axes = [axes]

    for ax, signal in zip(axes, available):
        if "foot" in df.columns:
            for foot, foot_df in df.groupby("foot"):
                foot_df = foot_df.sort_values("_time")
                ax.plot(foot_df["_time"], foot_df[signal], linewidth=0.7, label=str(foot), alpha=0.9)
        else:
            ordered = df.sort_values("_time")
            ax.plot(ordered["_time"], ordered[signal], linewidth=0.7, alpha=0.9)
        ax.axvspan(interval.start_utc, interval.end_utc, color="#e76f51", alpha=0.18)
        ax.set_ylabel(signal)
        ax.grid(True, alpha=0.25)
        if "foot" in df.columns:
            ax.legend(loc="upper right")

    title = (
        f"{interval.review_id} {interval.reference} | {interval.old_label} -> {interval.new_label} | "
        f"{interval.start_utc.tz_convert(LOCAL_TZ):%Y-%m-%d %H:%M:%S} - "
        f"{interval.end_utc.tz_convert(LOCAL_TZ):%H:%M:%S} | p_walk={interval.mean_prob_walking:.3f}"
    )
    fig.suptitle(title)
    fig.autofmt_xdate()
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(plot_path, dpi=130)
    plt.close(fig)
    return ("ok", "plot generado")


def foot_counts(df: pd.DataFrame) -> str:
    if df.empty or "foot" not in df.columns:
        return ""
    counts = df["foot"].value_counts(dropna=False).to_dict()
    return ";".join(f"{key}:{value}" for key, value in sorted(counts.items()))


def write_review_template(rows: list[dict[str, object]], output_dir: Path) -> None:
    cols = [
        "review_id",
        "reference",
        "dataset_source",
        "old_label",
        "new_label",
        "start_local",
        "end_local",
        "start_utc",
        "end_utc",
        "decision",
        "notes",
        "plot_path",
        "raw_path",
    ]
    df = pd.DataFrame(rows)
    for col in cols:
        if col not in df.columns:
            df[col] = ""
    df[cols].to_csv(output_dir / "review_decisions_template.csv", index=False)


def write_index(rows: list[dict[str, object]], output_dir: Path) -> None:
    sections = []
    for row in rows:
        plot_rel = row.get("plot_path", "")
        if plot_rel:
            plot_rel = Path(str(plot_rel)).name
        image = f'<img src="plots/{html.escape(plot_rel)}" alt="{html.escape(str(row["review_id"]))}">' if plot_rel else "<p>Sin grafica.</p>"
        sections.append(
            f"""
<section>
  <h2>{html.escape(str(row["review_id"]))} {html.escape(str(row["reference"]))}: {html.escape(str(row["old_label"]))} -> {html.escape(str(row["new_label"]))}</h2>
  <p><strong>Origen:</strong> {html.escape(str(row["dataset_source"]))} |
     <strong>Local:</strong> {html.escape(str(row["start_local"]))} - {html.escape(str(row["end_local"]))} |
     <strong>Ventanas:</strong> {html.escape(str(row["windows"]))} |
     <strong>p_walk media:</strong> {html.escape(str(row["mean_prob_walking"]))}</p>
  <p><strong>Extraccion:</strong> {html.escape(str(row["extract_status"]))} |
     <strong>Filas raw:</strong> {html.escape(str(row["raw_rows"]))} |
     <strong>Pies:</strong> {html.escape(str(row["foot_counts"]))}</p>
  {image}
</section>
"""
        )

    html_text = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Revision visual de correcciones</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; color: #1f2933; }}
    h1 {{ margin-bottom: 0.25rem; }}
    section {{ border-top: 1px solid #d8dee4; padding: 1.4rem 0; }}
    img {{ display: block; max-width: 100%; height: auto; border: 1px solid #d8dee4; }}
    p {{ margin: 0.45rem 0; }}
  </style>
</head>
<body>
  <h1>Revision visual de correcciones de etiquetas</h1>
  <p>La franja sombreada marca el intervalo propuesto para corregir.</p>
  {''.join(sections)}
</body>
</html>
"""
    (output_dir / "index.html").write_text(html_text, encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    config_path = Path(args.config)
    output_dir = Path(args.output_dir)
    raw_dir = Path(args.raw_dir)
    plot_dir = output_dir / "plots"
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_dir.mkdir(parents=True, exist_ok=True)

    intervals = load_intervals(input_path, args.limit)
    manifest_rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []

    for interval in intervals:
        raw_path = raw_output_path(raw_dir, interval)
        plot_path = plot_dir / (raw_path.stem + ".png")
        extract_status, extract_message = run_extraction(
            interval=interval,
            output_path=raw_path,
            config_path=config_path,
            margin_seconds=args.margin_seconds,
            from_tz=args.from_tz,
            resume_existing=args.resume_existing,
            skip_extract=args.skip_extract,
            verbose=args.verbose,
            timeout_seconds=args.extract_timeout_seconds,
        )
        raw_df = read_raw(raw_path)
        audit_status, audit_path = read_audit_status(raw_path)
        if audit_status in {"connection_failed", "no_records"}:
            extract_status = audit_status
        plot_status, plot_message = plot_interval(interval, raw_df, plot_path)
        start_local = interval.start_utc.tz_convert(args.from_tz).isoformat()
        end_local = interval.end_utc.tz_convert(args.from_tz).isoformat()

        row = {
            "review_id": interval.review_id,
            "reference": interval.reference,
            "dataset_source": interval.dataset_source,
            "old_label": interval.old_label,
            "new_label": interval.new_label,
            "start_utc": interval.start_utc.isoformat(),
            "end_utc": interval.end_utc.isoformat(),
            "start_local": start_local,
            "end_local": end_local,
            "windows": interval.windows,
            "duration_s": interval.duration_s,
            "models": interval.models,
            "mean_prob_walking": round(interval.mean_prob_walking, 6),
            "extract_status": extract_status,
            "extract_message": extract_message,
            "audit_status": audit_status,
            "audit_path": audit_path,
            "raw_path": str(raw_path),
            "raw_rows": int(len(raw_df)),
            "foot_counts": foot_counts(raw_df),
            "plot_status": plot_status,
            "plot_message": plot_message,
            "plot_path": str(plot_path) if plot_path.exists() else "",
        }
        manifest_rows.append(row)
        review_rows.append({**row, "decision": "", "notes": ""})
        print(
            f"{interval.review_id} {interval.reference} "
            f"{interval.old_label}->{interval.new_label}: "
            f"extract={extract_status}, raw_rows={len(raw_df)}, plot={plot_status}",
            flush=True,
        )

    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(output_dir / "manifest.csv", index=False)
    write_review_template(review_rows, output_dir)
    write_index(review_rows, output_dir)

    failures = manifest[
        manifest["extract_status"].isin(["failed", "timeout", "connection_failed"])
    ] if not manifest.empty else manifest
    print()
    print(f"Intervalos procesados: {len(manifest)}")
    print(f"Extracciones fallidas: {len(failures)}")
    print(f"Manifest: {output_dir / 'manifest.csv'}")
    print(f"HTML: {output_dir / 'index.html'}")


if __name__ == "__main__":
    main()
