#!/usr/bin/env python3
"""Import a ground-truth table exported from CSV/Excel into project format."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Importa una tabla exportada y la adapta al formato de ground truth del proyecto."
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="Ruta al CSV o Excel de entrada",
    )
    p.add_argument(
        "-o",
        "--output",
        default="salidas_test/ground_truth_imported.xlsx",
        help="Ruta del Excel normalizado de salida",
    )
    p.add_argument(
        "--reference-col",
        default="Reference",
        help="Nombre de la columna de referencia",
    )
    p.add_argument(
        "--from-col",
        default="datefrom",
        help="Nombre de la columna de inicio",
    )
    p.add_argument(
        "--until-col",
        default="dateuntil",
        help="Nombre de la columna de fin",
    )
    p.add_argument(
        "--label-col",
        default="mov_type",
        help="Nombre de la columna de etiqueta",
    )
    return p


def read_table(path: Path) -> pd.DataFrame:
    """Read CSV or Excel table depending on file extension."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise ValueError(f"Formato no soportado: {suffix}")


def main() -> None:
    """Read a table, rename required columns, normalize labels, and export project format."""
    args = build_parser().parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    df = read_table(input_path)

    rename_map = {
        args.reference_col: "Reference",
        args.from_col: "datefrom",
        args.until_col: "dateuntil",
        args.label_col: "mov_type",
    }

    missing = [src for src in rename_map if src not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas en la tabla de entrada: {missing}")

    df = df.rename(columns=rename_map)[list(rename_map.values())].copy()

    df["datefrom"] = pd.to_datetime(df["datefrom"])
    df["dateuntil"] = pd.to_datetime(df["dateuntil"])
    df["mov_type"] = df["mov_type"].astype(str).str.strip().str.lower()

    label_map = {
        "walk": "walking",
        "walking": "walking",
        "no_walk": "not_walking",
        "nowalk": "not_walking",
        "not_walking": "not_walking",
        "not walking": "not_walking",
    }
    df["mov_type"] = df["mov_type"].replace(label_map)

    valid_labels = {"walking", "not_walking"}
    invalid = sorted(set(df["mov_type"].dropna()) - valid_labels)
    if invalid:
        raise ValueError(f"Etiquetas no válidas encontradas: {invalid}")

    df["Duration  (mins)"] = (
        (df["dateuntil"] - df["datefrom"]).dt.total_seconds() / 60.0
    ).round(6)

    df = df.sort_values(["Reference", "datefrom", "dateuntil"]).reset_index(drop=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False)

    print(f"Tabla importada guardada en: {output_path}")
    print(f"Filas: {len(df)}")
    print("Columnas:", list(df.columns))
    print("Etiquetas:", sorted(df["mov_type"].dropna().unique().tolist()))
    print()
    print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
    