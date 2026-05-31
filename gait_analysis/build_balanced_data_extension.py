#!/usr/bin/env python3
"""Build a balanced ground-truth extension plan for gait models."""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd


LABEL_MAP = {
    "walking": "walking",
    "not_walking": "not_walking",
    "not walking": "not_walking",
    "not-walking": "not_walking",
}


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Construye una propuesta reproducible de ampliacion balanceada "
            "walking/not_walking a partir de ventanas etiquetadas."
        )
    )
    p.add_argument(
        "-i",
        "--inputs",
        nargs="+",
        default=["experiment_configs/reproducible_direct_influx_ground_truth_utc.csv"],
        help=(
            "CSV etiquetados. Soporta columnas Reference/datefrom/dateuntil/mov_type "
            "o Reference/from_time/until_time/expected_content."
        ),
    )
    p.add_argument(
        "--coverage-candidates",
        default="experiment_configs/high_priority_new_patient_candidates_coverage.csv",
        help="CSV opcional de candidatos con cobertura validada pero etiqueta desconocida.",
    )
    p.add_argument(
        "-o",
        "--output",
        default="experiment_configs/balanced_data_extension_ground_truth_utc.csv",
        help="CSV de ground truth balanceado de salida.",
    )
    p.add_argument(
        "--candidate-output",
        default="experiment_configs/balanced_data_extension_labeling_candidates.csv",
        help="CSV de candidatos que requieren etiquetado manual en Grafana.",
    )
    p.add_argument(
        "--summary-output",
        default="experiment_configs/balanced_data_extension_summary.md",
        help="Resumen Markdown de la seleccion.",
    )
    p.add_argument(
        "--input-tz",
        default="UTC",
        help="Zona horaria para timestamps sin zona explicita.",
    )
    p.add_argument(
        "--max-interval-s",
        type=float,
        default=180.0,
        help="Parte intervalos mas largos en bloques de esta duracion maxima.",
    )
    p.add_argument(
        "--negative-ratio",
        type=float,
        default=1.0,
        help="Segundos maximos de not_walking por cada segundo de walking.",
    )
    p.add_argument(
        "--min-duration-s",
        type=float,
        default=5.0,
        help="Descarta fragmentos mas cortos que este umbral.",
    )
    return p


def _normalize_label(value: object) -> str | None:
    """Normalize a movement label to the binary labels used by the project."""
    if pd.isna(value):
        return None
    return LABEL_MAP.get(str(value).strip().lower())


def _parse_timestamp(series: pd.Series, input_tz: str) -> pd.Series:
    """Parse timestamps and return UTC-aware timestamps."""
    parsed = pd.to_datetime(series, format="mixed", errors="raise")
    if parsed.dt.tz is None:
        parsed = parsed.dt.tz_localize(input_tz)
    return parsed.dt.tz_convert("UTC")


def load_labeled_input(path: Path, input_tz: str) -> pd.DataFrame:
    """Load one labeled CSV and normalize its schema."""
    raw = pd.read_csv(path)
    rename_map = {}
    if "from_time" in raw.columns:
        rename_map["from_time"] = "datefrom"
    if "until_time" in raw.columns:
        rename_map["until_time"] = "dateuntil"
    if "expected_content" in raw.columns:
        rename_map["expected_content"] = "mov_type"
    raw = raw.rename(columns=rename_map)

    required = {"Reference", "datefrom", "dateuntil", "mov_type"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"{path} no tiene columnas requeridas: {sorted(missing)}")

    df = raw[list(required)].copy()
    df["Reference"] = df["Reference"].astype(str)
    df["mov_type"] = df["mov_type"].map(_normalize_label)
    df = df[df["mov_type"].isin(["walking", "not_walking"])].copy()
    df["datefrom"] = _parse_timestamp(df["datefrom"], input_tz)
    df["dateuntil"] = _parse_timestamp(df["dateuntil"], input_tz)
    df["source"] = str(path)
    df["duration_s"] = (df["dateuntil"] - df["datefrom"]).dt.total_seconds()
    df = df[df["duration_s"] > 0].copy()
    return df


def split_long_intervals(
    df: pd.DataFrame,
    max_interval_s: float,
    min_duration_s: float,
) -> pd.DataFrame:
    """Split long intervals so one long negative block cannot dominate training."""
    rows: list[dict[str, object]] = []
    for _, row in df.iterrows():
        start = row["datefrom"]
        stop = row["dateuntil"]
        chunk_idx = 0
        while start < stop:
            chunk_stop = min(start + pd.Timedelta(seconds=max_interval_s), stop)
            duration_s = (chunk_stop - start).total_seconds()
            if duration_s >= min_duration_s:
                rows.append(
                    {
                        "Reference": row["Reference"],
                        "datefrom": start,
                        "dateuntil": chunk_stop,
                        "mov_type": row["mov_type"],
                        "source": row["source"],
                        "source_duration_s": row["duration_s"],
                        "chunk_index": chunk_idx,
                        "duration_s": duration_s,
                    }
                )
            start = chunk_stop
            chunk_idx += 1
    return pd.DataFrame(rows)


def select_balanced_rows(df: pd.DataFrame, negative_ratio: float) -> pd.DataFrame:
    """Select all walking rows and a duration-balanced, reference-diverse negative set."""
    walking = df[df["mov_type"] == "walking"].copy()
    negative = df[df["mov_type"] == "not_walking"].copy()
    walking_seconds = float(walking["duration_s"].sum())
    negative_budget = walking_seconds * negative_ratio

    selected_negative: list[pd.Series] = []
    selected_seconds_by_ref: defaultdict[str, float] = defaultdict(float)

    queues: dict[str, deque[pd.Series]] = {}
    for ref, ref_rows in negative.groupby("Reference", sort=True):
        ordered = ref_rows.sort_values(
            ["duration_s", "datefrom"],
            ascending=[False, True],
        )
        queues[str(ref)] = deque(row for _, row in ordered.iterrows())

    while queues and sum(row["duration_s"] for row in selected_negative) < negative_budget:
        refs = sorted(queues, key=lambda ref: (selected_seconds_by_ref[ref], ref))
        progressed = False
        for ref in refs:
            if not queues[ref]:
                queues.pop(ref, None)
                continue
            current_total = sum(row["duration_s"] for row in selected_negative)
            if current_total >= negative_budget:
                break
            row = queues[ref].popleft()
            selected_negative.append(row)
            selected_seconds_by_ref[ref] += float(row["duration_s"])
            progressed = True
        if not progressed:
            break

    negative_selected = pd.DataFrame(selected_negative)
    selected = pd.concat([walking, negative_selected], ignore_index=True)
    selected = selected.sort_values(["Reference", "datefrom", "dateuntil", "mov_type"])
    return selected.reset_index(drop=True)


def write_ground_truth(df: pd.DataFrame, output: Path) -> None:
    """Write the selected rows in the ground-truth schema expected by pipelines."""
    out = df[["Reference", "datefrom", "dateuntil", "mov_type"]].copy()
    out["datefrom"] = out["datefrom"].dt.strftime("%Y-%m-%d %H:%M:%S%z")
    out["dateuntil"] = out["dateuntil"].dt.strftime("%Y-%m-%d %H:%M:%S%z")
    out["datefrom"] = out["datefrom"].str.replace(r"(\+0000)$", "+00:00", regex=True)
    out["dateuntil"] = out["dateuntil"].str.replace(r"(\+0000)$", "+00:00", regex=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)


def build_labeling_candidates(path: Path) -> pd.DataFrame:
    """Build a compact list of covered references that still require labels."""
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)
    if "valid_both_feet" not in df.columns:
        return pd.DataFrame()
    valid_mask = df["valid_both_feet"].astype(str).str.lower().isin(["true", "1", "yes"])
    valid = df[valid_mask].copy()
    if valid.empty:
        return pd.DataFrame()

    valid["total_records"] = pd.to_numeric(
        valid.get("total_records"),
        errors="coerce",
    ).fillna(0)
    valid = valid.sort_values(
        ["priority", "total_records", "Reference", "offset_minutes"],
        ascending=[True, False, True, True],
    )
    keep_cols = [
        "Reference",
        "priority",
        "shifted_datefrom",
        "shifted_dateuntil",
        "offset_minutes",
        "right_records",
        "left_records",
        "total_records",
    ]
    keep_cols = [col for col in keep_cols if col in valid.columns]
    return valid.drop_duplicates("Reference")[keep_cols].reset_index(drop=True)


def class_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Return rows and seconds by label."""
    return (
        df.groupby("mov_type")
        .agg(rows=("mov_type", "size"), duration_s=("duration_s", "sum"))
        .reset_index()
    )


def to_markdown_table(df: pd.DataFrame) -> str:
    """Render a small DataFrame as a Markdown table without optional dependencies."""
    if df.empty:
        return ""
    rendered = df.copy()
    for col in rendered.columns:
        if pd.api.types.is_float_dtype(rendered[col]):
            rendered[col] = rendered[col].map(lambda value: f"{value:.2f}")
        else:
            rendered[col] = rendered[col].astype(str)

    headers = list(rendered.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in rendered.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in headers) + " |")
    return "\n".join(lines)


def write_summary(
    *,
    summary_path: Path,
    inputs: list[str],
    selected: pd.DataFrame,
    candidates: pd.DataFrame,
    output: Path,
    candidate_output: Path,
) -> None:
    """Write a Markdown summary of the generated plan."""
    class_rows = class_summary(selected)
    by_ref = (
        selected.groupby(["Reference", "mov_type"])
        .agg(rows=("mov_type", "size"), duration_s=("duration_s", "sum"))
        .reset_index()
    )

    lines = [
        "# Balanced Data Extension",
        "",
        "## Inputs",
        "",
        *[f"- `{path}`" for path in inputs],
        "",
        "## Output",
        "",
        f"- Balanced ground truth: `{output}`",
        f"- Labeling candidates: `{candidate_output}`",
        "",
        "## Class Balance",
        "",
        to_markdown_table(class_rows),
        "",
        "## Reference Coverage",
        "",
        to_markdown_table(by_ref),
        "",
        "## Manual Labeling Queue",
        "",
    ]
    if candidates.empty:
        lines.append("No covered unlabeled candidates were available.")
    else:
        lines.extend(
            [
                "These references have two-foot Influx coverage but still need Grafana/manual labels before they can be used for supervised training.",
                "",
                to_markdown_table(candidates),
            ]
        )

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Build the balanced data extension artifacts."""
    args = build_parser().parse_args()
    inputs = [Path(path) for path in args.inputs]
    labeled = pd.concat(
        [load_labeled_input(path, args.input_tz) for path in inputs],
        ignore_index=True,
    )
    labeled = labeled.drop_duplicates(
        subset=["Reference", "datefrom", "dateuntil", "mov_type"]
    )
    split = split_long_intervals(labeled, args.max_interval_s, args.min_duration_s)
    selected = select_balanced_rows(split, args.negative_ratio)

    output = Path(args.output)
    candidate_output = Path(args.candidate_output)
    summary_output = Path(args.summary_output)

    write_ground_truth(selected, output)
    candidates = build_labeling_candidates(Path(args.coverage_candidates))
    candidate_output.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(candidate_output, index=False)
    write_summary(
        summary_path=summary_output,
        inputs=args.inputs,
        selected=selected,
        candidates=candidates,
        output=output,
        candidate_output=candidate_output,
    )

    print(f"Balanced ground truth: {output}")
    print(f"Rows: {len(selected)}")
    print(class_summary(selected).to_string(index=False))
    print(f"Labeling candidates: {candidate_output} ({len(candidates)} refs)")
    print(f"Summary: {summary_output}")


if __name__ == "__main__":
    main()
