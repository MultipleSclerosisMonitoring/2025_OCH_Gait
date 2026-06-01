#!/usr/bin/env python3
"""Review audited label-correction intervals using extracted raw signals."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


LABEL_TO_TARGET = {"not_walking": 0, "walking": 1}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Calcula metricas de actividad sobre los parquets raw extraidos para "
            "decidir si las correcciones auditadas quedan respaldadas por la senal."
        )
    )
    parser.add_argument(
        "--manifest",
        default="results/correction_visual_review/manifest.csv",
        help="Manifest generado por build_correction_visual_review_pack.py",
    )
    parser.add_argument(
        "--corrections",
        default="results/auto_influx_extension_audited_label_corrections.csv",
        help="CSV de ventanas corregidas originalmente.",
    )
    parser.add_argument(
        "--metrics-output",
        default="results/correction_visual_review/raw_signal_decision_metrics.csv",
        help="CSV con metricas raw por intervalo.",
    )
    parser.add_argument(
        "--decisions-output",
        default="results/correction_visual_review/review_decisions_auto.csv",
        help="CSV de decisiones pre-rellenadas.",
    )
    parser.add_argument(
        "--confirmed-corrections-output",
        default="results/correction_visual_review/confirmed_audited_label_corrections.csv",
        help="CSV de ventanas corregidas cubiertas por intervalos confirmados.",
    )
    parser.add_argument(
        "--summary-output",
        default="results/correction_visual_review/auto_review_summary.md",
        help="Resumen Markdown del criterio automatico.",
    )
    parser.add_argument(
        "--core-padding-seconds",
        type=float,
        default=0.5,
        help="Margen alrededor del intervalo auditado al medir la senal raw.",
    )
    parser.add_argument(
        "--walking-acc-std-min",
        type=float,
        default=0.05,
        help="Desviacion minima de norma de acelerometro para respaldar walking.",
    )
    parser.add_argument(
        "--walking-gyro-std-min",
        type=float,
        default=10.0,
        help="Desviacion minima de norma de giroscopio para respaldar walking.",
    )
    parser.add_argument(
        "--not-walking-acc-std-max",
        type=float,
        default=0.05,
        help="Desviacion maxima de norma de acelerometro para respaldar not_walking.",
    )
    parser.add_argument(
        "--not-walking-gyro-std-max",
        type=float,
        default=5.0,
        help="Desviacion maxima de norma de giroscopio para respaldar not_walking.",
    )
    return parser


def norm_columns(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    acc_cols = ["Ax", "Ay", "Az"]
    gyro_cols = ["Gx", "Gy", "Gz"]
    output["acc_norm"] = np.sqrt((output[acc_cols].astype(float).pow(2)).sum(axis=1))
    output["gyro_norm"] = np.sqrt((output[gyro_cols].astype(float).pow(2)).sum(axis=1))
    return output


def interval_metrics(row: pd.Series, core_padding_seconds: float) -> dict[str, object]:
    raw_path = Path(str(row["raw_path"]))
    raw = pd.read_parquet(raw_path)
    raw["_time"] = pd.to_datetime(raw["_time"], utc=True, format="mixed")
    raw = norm_columns(raw)

    start = pd.to_datetime(row["start_utc"], utc=True, format="mixed")
    end = pd.to_datetime(row["end_utc"], utc=True, format="mixed")
    padding = pd.Timedelta(seconds=core_padding_seconds)
    core = raw[raw["_time"].between(start - padding, end + padding)].copy()

    metrics: dict[str, object] = {
        "review_id": row["review_id"],
        "reference": row["reference"],
        "dataset_source": row["dataset_source"],
        "old_label": row["old_label"],
        "new_label": row["new_label"],
        "start_utc": row["start_utc"],
        "end_utc": row["end_utc"],
        "windows": row["windows"],
        "mean_prob_walking": row["mean_prob_walking"],
        "raw_rows": row["raw_rows"],
        "core_rows": len(core),
        "plot_path": row["plot_path"],
        "raw_path": row["raw_path"],
    }
    acc_std_values: list[float] = []
    gyro_std_values: list[float] = []
    for foot, foot_df in core.groupby("foot", sort=True):
        for signal in ["acc_norm", "gyro_norm"]:
            value = float(foot_df[signal].std()) if len(foot_df) > 1 else float("nan")
            metrics[f"{foot}_{signal}_std"] = value
            metrics[f"{foot}_{signal}_iqr"] = float(
                foot_df[signal].quantile(0.75) - foot_df[signal].quantile(0.25)
            ) if len(foot_df) else float("nan")
            if signal == "acc_norm" and np.isfinite(value):
                acc_std_values.append(value)
            if signal == "gyro_norm" and np.isfinite(value):
                gyro_std_values.append(value)
    metrics["acc_std_mean"] = float(np.mean(acc_std_values)) if acc_std_values else float("nan")
    metrics["gyro_std_mean"] = float(np.mean(gyro_std_values)) if gyro_std_values else float("nan")
    return metrics


def decide(row: pd.Series, args: argparse.Namespace) -> tuple[str, str]:
    acc_std = float(row["acc_std_mean"])
    gyro_std = float(row["gyro_std_mean"])
    proposed = str(row["new_label"])
    if not np.isfinite(acc_std) or not np.isfinite(gyro_std):
        return "review", "metricas raw incompletas"

    supports_walking = (
        acc_std >= args.walking_acc_std_min
        and gyro_std >= args.walking_gyro_std_min
    )
    supports_not_walking = (
        acc_std <= args.not_walking_acc_std_max
        and gyro_std <= args.not_walking_gyro_std_max
    )

    if proposed == "walking" and supports_walking:
        return (
            "confirm_auto",
            f"senal activa bilateral: acc_std_mean={acc_std:.4f}, gyro_std_mean={gyro_std:.4f}",
        )
    if proposed == "not_walking" and supports_not_walking:
        return (
            "confirm_auto",
            f"senal casi estacionaria: acc_std_mean={acc_std:.4f}, gyro_std_mean={gyro_std:.4f}",
        )
    if proposed == "walking" and supports_not_walking:
        return (
            "reject_auto",
            f"la senal parece not_walking: acc_std_mean={acc_std:.4f}, gyro_std_mean={gyro_std:.4f}",
        )
    if proposed == "not_walking" and supports_walking:
        return (
            "reject_auto",
            f"la senal parece walking: acc_std_mean={acc_std:.4f}, gyro_std_mean={gyro_std:.4f}",
        )
    return (
        "review",
        f"zona intermedia: acc_std_mean={acc_std:.4f}, gyro_std_mean={gyro_std:.4f}",
    )


def build_decisions(metrics: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    decisions = metrics.copy()
    decision_values = decisions.apply(lambda row: decide(row, args), axis=1)
    decisions["decision"] = [value[0] for value in decision_values]
    decisions["notes"] = [value[1] for value in decision_values]
    return decisions[
        [
            "review_id",
            "reference",
            "dataset_source",
            "old_label",
            "new_label",
            "start_utc",
            "end_utc",
            "decision",
            "notes",
            "acc_std_mean",
            "gyro_std_mean",
            "windows",
            "mean_prob_walking",
            "plot_path",
            "raw_path",
        ]
    ]


def confirmed_interval_mask(corrections: pd.DataFrame, decisions: pd.DataFrame) -> pd.Series:
    corrections = corrections.copy()
    corrections["time_center"] = pd.to_datetime(
        corrections["time_center"],
        utc=True,
        format="mixed",
    )
    mask = pd.Series(False, index=corrections.index)
    confirmed = decisions[decisions["decision"].eq("confirm_auto")]
    for _, interval in confirmed.iterrows():
        start = pd.to_datetime(interval["start_utc"], utc=True, format="mixed")
        end = pd.to_datetime(interval["end_utc"], utc=True, format="mixed")
        interval_mask = (
            corrections["reference"].astype(str).eq(str(interval["reference"]))
            & corrections["dataset_source"].astype(str).eq(str(interval["dataset_source"]))
            & corrections["mov_type"].astype(str).eq(str(interval["old_label"]))
            & corrections["new_mov_type"].astype(str).eq(str(interval["new_label"]))
            & corrections["time_center"].between(start, end)
        )
        mask = mask | interval_mask
    return mask


def write_summary(
    path: Path,
    metrics: pd.DataFrame,
    decisions: pd.DataFrame,
    confirmed_corrections: pd.DataFrame,
    total_corrections: int,
    args: argparse.Namespace,
) -> None:
    by_decision = decisions["decision"].value_counts().sort_index()
    by_ref = (
        decisions.groupby(["reference", "old_label", "new_label", "decision"], dropna=False)
        .agg(intervals=("review_id", "count"), windows=("windows", "sum"))
        .reset_index()
        .sort_values(["decision", "reference", "old_label", "new_label"])
    )
    lines = [
        "# Revision automatica de senal raw",
        "",
        "## Criterio",
        "",
        f"- `walking`: `acc_std_mean >= {args.walking_acc_std_min}` y `gyro_std_mean >= {args.walking_gyro_std_min}`.",
        f"- `not_walking`: `acc_std_mean <= {args.not_walking_acc_std_max}` y `gyro_std_mean <= {args.not_walking_gyro_std_max}`.",
        "- Las metricas se calculan dentro del intervalo auditado con padding de "
        f"{args.core_padding_seconds} s.",
        "",
        "## Resultado",
        "",
        f"- intervalos revisados: {len(decisions)}",
        f"- correcciones de ventana originales: {total_corrections}",
        f"- correcciones confirmadas por senal: {len(confirmed_corrections)}",
        "",
        "### Decisiones por tipo",
        "",
    ]
    for decision, count in by_decision.items():
        lines.append(f"- `{decision}`: {int(count)}")
    lines.extend(["", "### Resumen por referencia", ""])
    lines.append("| Referencia | Cambio | Decision | Intervalos | Ventanas |")
    lines.append("|---|---|---|---:|---:|")
    for _, row in by_ref.iterrows():
        change = f"`{row['old_label']}` -> `{row['new_label']}`"
        lines.append(
            f"| `{row['reference']}` | {change} | `{row['decision']}` | "
            f"{int(row['intervals'])} | {int(row['windows'])} |"
        )
    lines.extend(["", "### Separacion observada", ""])
    separation = (
        metrics.groupby(["old_label", "new_label"])
        .agg(
            intervals=("review_id", "count"),
            acc_std_mean_min=("acc_std_mean", "min"),
            acc_std_mean_median=("acc_std_mean", "median"),
            acc_std_mean_max=("acc_std_mean", "max"),
            gyro_std_mean_min=("gyro_std_mean", "min"),
            gyro_std_mean_median=("gyro_std_mean", "median"),
            gyro_std_mean_max=("gyro_std_mean", "max"),
        )
        .reset_index()
    )
    lines.append("| Cambio | Intervalos | acc std min/med/max | gyro std min/med/max |")
    lines.append("|---|---:|---:|---:|")
    for _, row in separation.iterrows():
        change = f"`{row['old_label']}` -> `{row['new_label']}`"
        acc = (
            f"{row['acc_std_mean_min']:.4f} / "
            f"{row['acc_std_mean_median']:.4f} / "
            f"{row['acc_std_mean_max']:.4f}"
        )
        gyro = (
            f"{row['gyro_std_mean_min']:.4f} / "
            f"{row['gyro_std_mean_median']:.4f} / "
            f"{row['gyro_std_mean_max']:.4f}"
        )
        lines.append(f"| {change} | {int(row['intervals'])} | {acc} | {gyro} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = build_parser().parse_args()
    manifest = pd.read_csv(args.manifest)
    metrics = pd.DataFrame(
        [interval_metrics(row, args.core_padding_seconds) for _, row in manifest.iterrows()]
    )
    decisions = build_decisions(metrics, args)

    corrections = pd.read_csv(args.corrections)
    confirmed_mask = confirmed_interval_mask(corrections, decisions)
    confirmed_corrections = corrections[confirmed_mask].copy()
    confirmed_corrections["visual_review_decision"] = "confirm_auto"
    confirmed_corrections["visual_review_source"] = str(args.decisions_output)

    metrics_output = Path(args.metrics_output)
    decisions_output = Path(args.decisions_output)
    confirmed_output = Path(args.confirmed_corrections_output)
    for path in [metrics_output, decisions_output, confirmed_output]:
        path.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(metrics_output, index=False)
    decisions.to_csv(decisions_output, index=False)
    confirmed_corrections.to_csv(confirmed_output, index=False)

    write_summary(
        Path(args.summary_output),
        metrics=metrics,
        decisions=decisions,
        confirmed_corrections=confirmed_corrections,
        total_corrections=len(corrections),
        args=args,
    )

    print(f"Intervals reviewed: {len(decisions)}")
    print(decisions["decision"].value_counts().sort_index().to_string())
    print(f"Original corrections: {len(corrections)}")
    print(f"Confirmed corrections: {len(confirmed_corrections)}")
    print(f"Metrics output: {metrics_output}")
    print(f"Decisions output: {decisions_output}")
    print(f"Confirmed corrections output: {confirmed_output}")
    print(f"Summary output: {args.summary_output}")


if __name__ == "__main__":
    main()
