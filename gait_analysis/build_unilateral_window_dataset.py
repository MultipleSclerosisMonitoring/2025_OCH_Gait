#!/usr/bin/env python3
"""Build one-row-per-foot datasets from paired-foot window features."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


ID_COLS = ["reference", "time_center", "mov_type", "target"]
FOOT_PATTERNS = [
    re.compile(r"^(?P<kind>spec|temp)_(?P<foot>Right|Left)_(?P<rest>.+)$"),
    re.compile(r"^(?P<foot>Right|Left)_(?P<rest>.+)$"),
]


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Convierte un dataset de ventanas con ambos pies en una vista "
            "unilateral, con una fila por pie y ventana."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="Parquet bilateral con columnas spec_/temp_ por pie.",
    )
    p.add_argument(
        "-o",
        "--output",
        required=True,
        help="Parquet unilateral de salida.",
    )
    p.add_argument(
        "--include-foot-indicator",
        action="store_true",
        help="Incluye una columna numerica foot_is_right como feature auxiliar.",
    )
    return p


def split_foot_columns(columns: list[str]) -> dict[str, dict[str, str]]:
    """Return mapping foot -> output feature -> source column."""
    mapping: dict[str, dict[str, str]] = {"Right": {}, "Left": {}}
    for column in columns:
        match = next(
            (pattern.match(column) for pattern in FOOT_PATTERNS if pattern.match(column)),
            None,
        )
        if not match:
            continue
        foot = match.group("foot")
        kind = match.groupdict().get("kind")
        feature = (
            f"{kind}_{match.group('rest')}"
            if kind
            else match.group("rest")
        )
        mapping[foot][feature] = column
    return mapping


def build_unilateral_dataset(
    df: pd.DataFrame,
    *,
    include_foot_indicator: bool,
) -> pd.DataFrame:
    """Convert paired-foot feature rows into independent per-foot rows."""
    missing_ids = [col for col in ID_COLS if col not in df.columns]
    if missing_ids:
        raise ValueError(f"Faltan columnas identificadoras: {missing_ids}")

    mapping = split_foot_columns(list(df.columns))
    common_features = sorted(set(mapping["Right"]) & set(mapping["Left"]))
    if not common_features:
        raise ValueError("No se han encontrado features comunes Right/Left.")

    rows = []
    for foot in ["Right", "Left"]:
        foot_df = df[ID_COLS].copy()
        foot_df["foot"] = foot
        if include_foot_indicator:
            foot_df["foot_is_right"] = 1 if foot == "Right" else 0
        renamed = {
            mapping[foot][feature]: feature
            for feature in common_features
            if feature in mapping[foot]
        }
        feature_df = df[list(renamed)].rename(columns=renamed)
        rows.append(pd.concat([foot_df, feature_df], axis=1))

    output = pd.concat(rows, ignore_index=True)
    output["time_center"] = pd.to_datetime(output["time_center"], utc=True)
    output = output.sort_values(["reference", "time_center", "foot"]).reset_index(
        drop=True
    )
    return output


def main() -> None:
    """Build and save the unilateral dataset."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    df = pd.read_parquet(input_path)
    output = build_unilateral_dataset(
        df,
        include_foot_indicator=args.include_foot_indicator,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(output_path, index=False)

    feature_cols = [
        col
        for col in output.columns
        if col not in {"reference", "time_center", "mov_type", "target", "foot"}
    ]
    print(f"Input parquet: {input_path}")
    print(f"Input rows: {len(df)}")
    print(f"Output parquet: {output_path}")
    print(f"Output rows: {len(output)}")
    print(f"Feature columns: {len(feature_cols)}")
    print()
    print("Rows by foot:")
    print(output["foot"].value_counts().sort_index().to_string())
    print()
    print("Target counts:")
    print(output["target"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
