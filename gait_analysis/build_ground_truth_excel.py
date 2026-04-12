#!/usr/bin/env python3
"""Clean and normalize a gait ground-truth Excel file."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Limpia y normaliza un Excel de ground truth de marcha."
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        nargs="+",
        help="Una o varias rutas de Excel de entrada",
    )

    p.add_argument(
        "-o",
        "--output",
        default="salidas_test/ground_truth_clean.xlsx",
        help="Ruta del Excel de salida",
    )
    return p


def main() -> None:
    """Read the reference Excel, keep relevant columns, normalize labels, and save a clean copy."""
    args = build_parser().parse_args()

    input_paths = [Path(p) for p in args.input]
    output_path = Path(args.output)
    issues_path = output_path.with_name(output_path.stem + "_overlaps.csv")

    frames = [pd.read_excel(path) for path in input_paths]
    df = pd.concat(frames, ignore_index=True)

    df = df[["Reference", "datefrom", "dateuntil", "mov_type", "Duration  (mins)"]].copy()

    df["datefrom"] = pd.to_datetime(df["datefrom"])
    df["dateuntil"] = pd.to_datetime(df["dateuntil"])

    df = df.dropna(subset=["mov_type"]).copy()
    df["mov_type"] = df["mov_type"].str.strip().str.lower()

    valid_labels = {"walking", "not_walking"}
    invalid = sorted(set(df["mov_type"].dropna()) - valid_labels)
    if invalid:
        raise ValueError(f"Etiquetas no válidas encontradas: {invalid}")

    duration_min = (df["dateuntil"] - df["datefrom"]).dt.total_seconds() / 60.0
    df["Duration  (mins)"] = duration_min.round(6)

    df = df.drop_duplicates(
        subset=["Reference", "datefrom", "dateuntil", "mov_type"]
    ).sort_values(
        by=["Reference", "datefrom", "dateuntil"]
    ).reset_index(drop=True)

    overlaps = []
    for ref, g in df.groupby("Reference"):
        g = g.sort_values(["datefrom", "dateuntil"]).reset_index(drop=True)
        for i in range(1, len(g)):
            prev_until = g.loc[i - 1, "dateuntil"]
            curr_from = g.loc[i, "datefrom"]
            if curr_from < prev_until:
                overlaps.append({
                    "Reference": ref,
                    "prev_datefrom": g.loc[i - 1, "datefrom"],
                    "prev_dateuntil": g.loc[i - 1, "dateuntil"],
                    "prev_mov_type": g.loc[i - 1, "mov_type"],
                    "curr_datefrom": g.loc[i, "datefrom"],
                    "curr_dateuntil": g.loc[i, "dateuntil"],
                    "curr_mov_type": g.loc[i, "mov_type"],
                })
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False)

    print(f"Excel limpio guardado en: {output_path}")
    print(f"Filas: {len(df)}")
    print("Columnas:", list(df.columns))
    print("Etiquetas:", sorted(df["mov_type"].dropna().unique().tolist()))

    if overlaps:
        overlaps_df = pd.DataFrame(overlaps)
        overlaps_df.to_csv(issues_path, index=False)

        print(f"AVISO: se han detectado {len(overlaps)} solapes temporales.")
        print(f"CSV de incidencias guardado en: {issues_path}")
        print(overlaps_df.to_string(index=False))
    

if __name__ == "__main__":
    main()