#!/usr/bin/env python3
"""Summarize sample-completeness metadata in window datasets."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Resume columnas sample_completeness de datasets de ventanas."
    )
    p.add_argument(
        "-i",
        "--inputs",
        nargs="+",
        required=True,
        help="Parquets a resumir.",
    )
    p.add_argument("-o", "--output", required=True, help="CSV de salida.")
    return p


def summarize_one(path: str) -> list[dict[str, object]]:
    """Summarize completeness columns for one parquet."""
    df = pd.read_parquet(path)
    completeness_cols = [c for c in df.columns if "sample_completeness" in c]
    if not completeness_cols:
        return [
            {
                "dataset": path,
                "rows": int(len(df)),
                "completeness_column": "NONE",
                "mean": pd.NA,
                "std": pd.NA,
                "min": pd.NA,
                "p01": pd.NA,
                "p05": pd.NA,
                "p50": pd.NA,
                "p95": pd.NA,
                "max": pd.NA,
                "rows_below_100": pd.NA,
                "rows_below_99": pd.NA,
                "rows_below_95": pd.NA,
                "rows_below_90": pd.NA,
            }
        ]

    rows = []
    for col in completeness_cols:
        values = df[col].astype(float)
        rows.append(
            {
                "dataset": path,
                "rows": int(len(df)),
                "completeness_column": col,
                "mean": float(values.mean()),
                "std": float(values.std(ddof=0)),
                "min": float(values.min()),
                "p01": float(values.quantile(0.01)),
                "p05": float(values.quantile(0.05)),
                "p50": float(values.quantile(0.50)),
                "p95": float(values.quantile(0.95)),
                "max": float(values.max()),
                "rows_below_100": int(values.lt(1.0).sum()),
                "rows_below_99": int(values.lt(0.99).sum()),
                "rows_below_95": int(values.lt(0.95).sum()),
                "rows_below_90": int(values.lt(0.90).sum()),
            }
        )
    return rows


def main() -> None:
    """Summarize all requested datasets."""
    args = build_parser().parse_args()
    rows: list[dict[str, object]] = []
    for path in args.inputs:
        rows.extend(summarize_one(path))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(rows)
    summary.to_csv(output, index=False)

    print(f"Output: {output}")
    printable = summary.copy()
    for col in printable.select_dtypes(include="number").columns:
        printable[col] = printable[col].round(4)
    print(printable.to_string(index=False))


if __name__ == "__main__":
    main()
