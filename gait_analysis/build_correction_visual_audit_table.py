#!/usr/bin/env python3
"""Build a compact visual-review table from audited label corrections."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Agrupa correcciones consecutivas en intervalos revisables."
    )
    p.add_argument("-i", "--input", required=True, help="CSV de correcciones.")
    p.add_argument("-o", "--output", required=True, help="CSV de auditoria visual.")
    p.add_argument(
        "--summary-output",
        default=None,
        help="Markdown opcional con los intervalos principales.",
    )
    p.add_argument(
        "--timezone",
        default="Europe/Madrid",
        help="Zona horaria para columnas locales.",
    )
    p.add_argument(
        "--gap-seconds",
        type=float,
        default=2.0,
        help="Salto temporal que separa intervalos corregidos.",
    )
    p.add_argument("--top-n", type=int, default=20)
    return p


def build_visual_table(df: pd.DataFrame, *, timezone: str, gap_seconds: float) -> pd.DataFrame:
    """Group consecutive corrected windows into visual-review intervals."""
    required = {
        "reference",
        "time_center",
        "dataset_source",
        "mov_type",
        "new_mov_type",
        "target",
        "new_target",
        "min_prob_walking",
        "max_prob_walking",
        "mean_prob_walking",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas: {sorted(missing)}")

    work = df.copy()
    work["time_center"] = pd.to_datetime(work["time_center"], utc=True, format="mixed")
    work = work.sort_values(
        ["reference", "dataset_source", "mov_type", "new_mov_type", "time_center"]
    )
    group_cols = ["reference", "dataset_source", "mov_type", "new_mov_type"]
    gap = work.groupby(group_cols)["time_center"].diff()
    new_group = gap.gt(pd.Timedelta(seconds=gap_seconds)).fillna(True)
    work["correction_run_id"] = new_group.groupby(
        [work[col] for col in group_cols], sort=False
    ).cumsum()

    rows = []
    for values, part in work.groupby([*group_cols, "correction_run_id"], sort=False):
        reference, source, old_label, new_label, _ = values
        start_utc = part["time_center"].min()
        end_utc = part["time_center"].max()
        rows.append(
            {
                "reference": reference,
                "dataset_source": source,
                "old_label": old_label,
                "new_label": new_label,
                "start_utc": start_utc,
                "end_utc": end_utc,
                "start_local": start_utc.tz_convert(timezone),
                "end_local": end_utc.tz_convert(timezone),
                "windows": int(len(part)),
                "duration_s": float((end_utc - start_utc).total_seconds() + 1),
                "models": int(part["models"].min()),
                "votes_walking_min": int(part["votes_walking"].min()),
                "votes_walking_max": int(part["votes_walking"].max()),
                "min_prob_walking": float(part["min_prob_walking"].min()),
                "max_prob_walking": float(part["max_prob_walking"].max()),
                "mean_prob_walking": float(part["mean_prob_walking"].mean()),
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["windows", "duration_s", "mean_prob_walking"],
        ascending=False,
    )


def write_summary(path: Path, table: pd.DataFrame, top_n: int) -> None:
    """Write a compact markdown summary."""
    lines = [
        "# Tabla de auditoria visual de correcciones",
        "",
        "Intervalos principales a revisar en Grafana:",
        "",
    ]
    for _, row in table.head(top_n).iterrows():
        lines.append(
            f"- {row['reference']} | {row['dataset_source']} | "
            f"{row['old_label']} -> {row['new_label']} | "
            f"{row['start_local']} a {row['end_local']} | "
            f"{int(row['windows'])} ventanas | "
            f"mean_prob={row['mean_prob_walking']:.4f}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Build the visual-review table."""
    args = build_parser().parse_args()
    table = build_visual_table(
        pd.read_csv(args.input),
        timezone=args.timezone,
        gap_seconds=args.gap_seconds,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output, index=False)
    if args.summary_output:
        write_summary(Path(args.summary_output), table, args.top_n)

    print(f"Input: {args.input}")
    print(f"Output: {output}")
    if args.summary_output:
        print(f"Summary output: {args.summary_output}")
    print(table.head(args.top_n).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
