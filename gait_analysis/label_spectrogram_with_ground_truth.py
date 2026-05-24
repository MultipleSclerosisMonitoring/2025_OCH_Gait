#!/usr/bin/env python3
"""Label spectrogram rows using a cleaned gait ground-truth file."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Etiqueta un parquet de espectrogramas usando ground truth limpio."
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="Ruta al parquet de espectrogramas de entrada",
    )
    p.add_argument(
        "-g",
        "--ground-truth",
        required=True,
        help="Ruta al Excel limpio de ground truth",
    )
    p.add_argument(
        "-o",
        "--output",
        required=True,
        help="Ruta al parquet etiquetado de salida",
    )
    return p


def main() -> None:
    """Read spectrogram and ground-truth files, then label rows by time interval."""
    args = build_parser().parse_args()

    input_path = Path(args.input)
    ground_truth_path = Path(args.ground_truth)
    output_path = Path(args.output)

    df = pd.read_parquet(input_path)
    if ground_truth_path.suffix.lower() == ".csv":
        gt = pd.read_csv(ground_truth_path)
    else:
        gt = pd.read_excel(ground_truth_path)

    df["time_center"] = pd.to_datetime(df["time_center"], utc=True)
    gt["datefrom"] = pd.to_datetime(gt["datefrom"], utc=True)
    gt["dateuntil"] = pd.to_datetime(gt["dateuntil"], utc=True)

    def label_row(reference: str, time_center: pd.Timestamp) -> str:
        """Return movement label for a spectrogram row time center."""
        ref_gt = gt[gt["Reference"] == reference]
        for _, row in ref_gt.iterrows():
            if row["datefrom"] <= time_center < row["dateuntil"]:
                return row["mov_type"]
        return "NO_LABEL"

    df["mov_type"] = df.apply(
        lambda row: label_row(row["reference"], row["time_center"]),
        axis=1,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)

    filtered_output_path = output_path.with_name(output_path.stem + "_filtered.parquet")
    df_filtered = df[df["mov_type"] != "NO_LABEL"].copy()
    df_filtered.to_parquet(filtered_output_path, index=False)

    print(df["mov_type"].value_counts(dropna=False).to_string())

    print()
    centers_summary = (
        df[["time_center", "mov_type"]]
        .drop_duplicates()
        .groupby("mov_type")
        .size()
        .sort_index()
    )
    print("Unique centers by mov_type:")
    print(centers_summary.to_string())
    print()
    no_label_rows = int((df["mov_type"] == "NO_LABEL").sum())
    print(f"NO_LABEL rows: {no_label_rows}")

    print(f"Input spectrogram: {input_path}")
    print(f"Input ground truth: {ground_truth_path}")
    print(f"Output labeled parquet: {output_path}")
    print(f"Output filtered parquet: {filtered_output_path}")
    print(f"Spectrogram rows: {len(df)}")
    print(f"Ground-truth rows: {len(gt)}")


if __name__ == "__main__":
    main()
