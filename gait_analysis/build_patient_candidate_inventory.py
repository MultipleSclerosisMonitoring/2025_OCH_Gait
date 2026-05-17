#!/usr/bin/env python3
"""Build a candidate inventory for adding patient diversity."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any
import warnings

import pandas as pd
import urllib3

from gait_analysis.config import ConfigLoader
from gait_analysis.influx_service import InfluxService
from gait_analysis.time_utils import TimeProcessor


TRAINING_REFERENCES = {"02548893X-118", "04845288Q-121", "47046344M-104"}


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Construye un inventario de intervalos/pacientes candidatos para "
            "ampliar el dataset y, opcionalmente, comprueba cobertura en Influx."
        )
    )
    p.add_argument(
        "-g",
        "--ground-truth",
        default="salidas_test/ground_truth_clean.xlsx",
        help="Excel limpio de ground truth.",
    )
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Configuracion con credenciales/tags de Influx.",
    )
    p.add_argument(
        "-o",
        "--output",
        default="experiment_configs/patient_candidate_inventory.csv",
        help="CSV de salida con candidatos.",
    )
    p.add_argument(
        "--check-influx",
        action="store_true",
        help="Consulta Influx para contar muestras por pie en cada intervalo.",
    )
    p.add_argument(
        "--min-duration-s",
        type=float,
        default=10.0,
        help="Duracion minima del intervalo para considerarlo candidato.",
    )
    p.add_argument(
        "--max-candidates",
        type=int,
        default=None,
        help="Limita el numero de candidatos a comprobar en Influx.",
    )
    return p


def load_ground_truth(path: Path) -> pd.DataFrame:
    """Load and normalize ground truth intervals."""
    gt = pd.read_excel(path)
    gt["Reference"] = gt["Reference"].astype(str)
    gt["datefrom"] = pd.to_datetime(gt["datefrom"])
    gt["dateuntil"] = pd.to_datetime(gt["dateuntil"])
    gt["mov_type"] = gt["mov_type"].astype(str).str.strip()
    gt["duration_s"] = (gt["dateuntil"] - gt["datefrom"]).dt.total_seconds()
    return gt.sort_values(["Reference", "datefrom", "dateuntil"]).reset_index(drop=True)


def summarize_reference_labels(gt: pd.DataFrame) -> pd.DataFrame:
    """Summarize label availability by reference."""
    summary = (
        gt.groupby(["Reference", "mov_type"])
        .agg(intervals=("mov_type", "size"), duration_s=("duration_s", "sum"))
        .reset_index()
        .pivot(index="Reference", columns="mov_type", values=["intervals", "duration_s"])
        .fillna(0)
    )
    summary.columns = [f"{metric}_{label}" for metric, label in summary.columns]
    summary = summary.reset_index()
    for col in [
        "intervals_walking",
        "intervals_not_walking",
        "duration_s_walking",
        "duration_s_not_walking",
    ]:
        if col not in summary.columns:
            summary[col] = 0
    summary["has_walking"] = summary["duration_s_walking"] > 0
    summary["has_not_walking"] = summary["duration_s_not_walking"] > 0
    summary["has_both_labels"] = summary["has_walking"] & summary["has_not_walking"]
    summary["already_in_training"] = summary["Reference"].isin(TRAINING_REFERENCES)
    return summary


def build_inventory(gt: pd.DataFrame, min_duration_s: float) -> pd.DataFrame:
    """Create candidate rows enriched with per-reference context."""
    ref_summary = summarize_reference_labels(gt)
    candidates = gt[gt["duration_s"] >= min_duration_s].copy()
    candidates = candidates.merge(ref_summary, on="Reference", how="left")
    candidates["candidate_kind"] = candidates.apply(classify_candidate, axis=1)
    candidates["priority"] = candidates["candidate_kind"].map(
        {
            "new_patient_both_labels": 1,
            "new_patient_single_label": 2,
            "training_patient_holdout": 3,
        }
    )
    candidates = candidates.sort_values(
        ["priority", "Reference", "mov_type", "duration_s"],
        ascending=[True, True, True, False],
    ).reset_index(drop=True)
    return candidates


def classify_candidate(row: pd.Series) -> str:
    """Return candidate category for prioritization."""
    if bool(row["already_in_training"]):
        return "training_patient_holdout"
    if bool(row["has_both_labels"]):
        return "new_patient_both_labels"
    return "new_patient_single_label"


def build_count_query(
    *,
    bucket: str,
    start_iso: str,
    stop_iso: str,
    ref_tag: str,
    reference: str,
    foot_tag: str,
    foot: str,
    fields: list[str],
) -> str:
    """Build a compact Flux count query for one foot and interval."""
    field_filters = " or ".join([f'r["_field"] == "{field}"' for field in fields])
    return f'''
from(bucket: "{bucket}")
  |> range(start: time(v: "{start_iso}"), stop: time(v: "{stop_iso}"))
  |> filter(fn: (r) => r["{ref_tag}"] == "{reference}")
  |> filter(fn: (r) => r["{foot_tag}"] == "{foot}")
  |> filter(fn: (r) => {field_filters})
  |> group(columns: ["_field"])
  |> count()
'''


def count_interval(
    influx: InfluxService,
    cfg: Any,
    row: pd.Series,
) -> dict[str, int]:
    """Count records in Influx for each configured foot."""
    tz = cfg.default_tz or "Europe/Madrid"
    start_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(
        pd.Timestamp(row["datefrom"]).strftime("%Y-%m-%d %H:%M:%S"),
        tz,
    )
    stop_iso, _ = TimeProcessor.to_utc_rfc3339_and_key(
        pd.Timestamp(row["dateuntil"]).strftime("%Y-%m-%d %H:%M:%S"),
        tz,
    )

    counts: dict[str, int] = {}
    for foot in cfg.spectrogram.feet:
        flux = build_count_query(
            bucket=cfg.influx.bucket,
            start_iso=start_iso,
            stop_iso=stop_iso,
            ref_tag=cfg.ref_tag,
            reference=str(row["Reference"]),
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


def add_influx_counts(
    candidates: pd.DataFrame,
    config_path: Path,
    max_candidates: int | None,
) -> pd.DataFrame:
    """Add Influx record counts to candidate rows."""
    cfg = ConfigLoader(str(config_path)).load()
    checked = candidates.copy()
    for foot in cfg.spectrogram.feet:
        checked[f"{foot.lower()}_records"] = pd.NA
    checked["coverage_error"] = ""

    rows_to_check = checked.index
    if max_candidates is not None:
        rows_to_check = rows_to_check[:max_candidates]

    with InfluxService(cfg.influx) as influx:
        for idx in rows_to_check:
            row = checked.loc[idx]
            print(
                "Checking",
                row["Reference"],
                row["datefrom"],
                row["dateuntil"],
                row["mov_type"],
            )
            try:
                counts = count_interval(influx, cfg, row)
            except Exception as exc:  # noqa: BLE001 - keep long coverage runs alive.
                checked.loc[idx, "coverage_error"] = str(exc)
                continue
            else:
                for key, value in counts.items():
                    checked.loc[idx, key] = value

    record_cols = [f"{foot.lower()}_records" for foot in cfg.spectrogram.feet]
    record_values = checked[record_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    checked["valid_both_feet"] = record_values.gt(0).all(axis=1)
    return checked


def main() -> None:
    """Build candidate inventory and optionally check Influx coverage."""
    args = build_parser().parse_args()
    warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
    gt = load_ground_truth(Path(args.ground_truth))
    candidates = build_inventory(gt, min_duration_s=args.min_duration_s)
    if args.check_influx:
        candidates = add_influx_counts(
            candidates,
            config_path=Path(args.config),
            max_candidates=args.max_candidates,
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(output, index=False)

    print(f"Ground truth: {args.ground_truth}")
    print(f"Output: {output}")
    print(f"Candidates: {len(candidates)}")
    print()
    print("Candidate summary:")
    print(candidates["candidate_kind"].value_counts().to_string())
    print()
    preview_cols = [
        "Reference",
        "datefrom",
        "dateuntil",
        "mov_type",
        "duration_s",
        "candidate_kind",
        "has_both_labels",
        "already_in_training",
    ]
    extra_cols = [c for c in candidates.columns if c.endswith("_records")]
    preview_cols.extend(extra_cols)
    if "valid_both_feet" in candidates.columns:
        preview_cols.append("valid_both_feet")
    print(candidates[preview_cols].head(30).to_string(index=False))


if __name__ == "__main__":
    main()
