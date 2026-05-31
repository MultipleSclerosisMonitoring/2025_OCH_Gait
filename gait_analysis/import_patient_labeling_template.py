#!/usr/bin/env python3
"""Convert completed patient labeling templates into ground-truth CSV."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


VALID_LABELS = {"walking", "not_walking"}


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Importa plantillas de etiquetado manual y genera un ground truth UTC "
            "con columnas Reference,datefrom,dateuntil,mov_type."
        )
    )
    p.add_argument(
        "-i",
        "--inputs",
        nargs="+",
        required=True,
        help="CSV de plantillas ya etiquetadas.",
    )
    p.add_argument(
        "-o",
        "--output",
        default="experiment_configs/manual_patient_ground_truth_utc.csv",
        help="CSV de ground truth UTC de salida.",
    )
    p.add_argument(
        "--timezone",
        default="Europe/Madrid",
        help="Zona horaria para label_from_local/label_until_local.",
    )
    p.add_argument(
        "--allow-review-window-labels",
        action="store_true",
        help=(
            "Permite usar review_from/review_until como intervalo etiquetado "
            "si label_from/label_until estan vacios."
        ),
    )
    return p


def normalize_label(value: object) -> str | None:
    """Normalize and validate a manual movement label."""
    if pd.isna(value):
        return None
    label = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if not label:
        return None
    if label not in VALID_LABELS:
        raise ValueError(f"Etiqueta no valida: {value!r}")
    return label


def parse_time(value: object, timezone: str, *, assume_local: bool) -> pd.Timestamp:
    """Parse one timestamp and return UTC-aware timestamp."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        if assume_local:
            ts = ts.tz_localize(timezone)
        else:
            ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def first_non_empty(row: pd.Series, columns: list[str]) -> object | None:
    """Return the first non-empty value among the provided columns."""
    for col in columns:
        if col in row and not pd.isna(row[col]) and str(row[col]).strip():
            return row[col]
    return None


def load_template(
    path: Path,
    timezone: str,
    allow_review_window_labels: bool,
) -> pd.DataFrame:
    """Load one completed template and return accepted labels."""
    df = pd.read_csv(path)
    rows: list[dict[str, object]] = []
    for idx, row in df.iterrows():
        label = normalize_label(row.get("mov_type"))
        if label is None:
            continue

        start_value = first_non_empty(row, ["label_from_utc", "label_from_local"])
        stop_value = first_non_empty(row, ["label_until_utc", "label_until_local"])
        start_is_local = bool(start_value == row.get("label_from_local"))
        stop_is_local = bool(stop_value == row.get("label_until_local"))

        if (start_value is None or stop_value is None) and allow_review_window_labels:
            start_value = first_non_empty(row, ["review_from_utc", "review_from_local"])
            stop_value = first_non_empty(row, ["review_until_utc", "review_until_local"])
            start_is_local = bool(start_value == row.get("review_from_local"))
            stop_is_local = bool(stop_value == row.get("review_until_local"))

        if start_value is None or stop_value is None:
            raise ValueError(
                f"{path}:{idx + 2} tiene mov_type={label!r} pero faltan fechas de etiqueta"
            )

        start = parse_time(start_value, timezone, assume_local=start_is_local)
        stop = parse_time(stop_value, timezone, assume_local=stop_is_local)
        if stop <= start:
            raise ValueError(f"{path}:{idx + 2} tiene dateuntil <= datefrom")

        rows.append(
            {
                "Reference": str(row["Reference"]),
                "datefrom": start,
                "dateuntil": stop,
                "mov_type": label,
                "source_template": str(path),
                "source_row": idx + 2,
            }
        )
    return pd.DataFrame(rows)


def format_utc(series: pd.Series) -> pd.Series:
    """Format UTC timestamps with a colon in the timezone offset."""
    values = series.dt.strftime("%Y-%m-%d %H:%M:%S%z")
    return values.str.replace(r"(\+0000)$", "+00:00", regex=True)


def main() -> None:
    """Import completed templates into a reproducible ground-truth CSV."""
    args = build_parser().parse_args()
    inputs = [Path(path) for path in args.inputs]
    labeled = pd.concat(
        [
            load_template(path, args.timezone, args.allow_review_window_labels)
            for path in inputs
        ],
        ignore_index=True,
    )
    if labeled.empty:
        raise ValueError("No se han encontrado filas etiquetadas.")

    labeled = labeled.sort_values(["Reference", "datefrom", "dateuntil", "mov_type"])
    labeled = labeled.drop_duplicates(
        subset=["Reference", "datefrom", "dateuntil", "mov_type"]
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    out = labeled[["Reference", "datefrom", "dateuntil", "mov_type"]].copy()
    out["datefrom"] = format_utc(out["datefrom"])
    out["dateuntil"] = format_utc(out["dateuntil"])
    out.to_csv(output, index=False)

    print(f"Output: {output}")
    print(f"Rows: {len(out)}")
    print(out.groupby("mov_type").size().to_string())


if __name__ == "__main__":
    main()
