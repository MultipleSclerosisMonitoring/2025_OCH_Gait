#!/usr/bin/env python3
"""Apply conservative label corrections from audited OOF error runs."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


TARGET_TO_LABEL = {0: "not_walking", 1: "walking"}


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Corrige etiquetas solo en rachas auditadas donde todos los modelos "
            "out-of-fold coinciden contra la etiqueta actual."
        )
    )
    p.add_argument("-i", "--input", required=True, help="Parquet ML de entrada.")
    p.add_argument("--predictions", required=True, help="CSV de predicciones OOF.")
    p.add_argument("--runs", required=True, help="CSV de rachas auditadas.")
    p.add_argument("-o", "--output", required=True, help="Parquet corregido.")
    p.add_argument(
        "--corrections-output",
        required=True,
        help="CSV auditable con ventanas corregidas.",
    )
    p.add_argument(
        "--summary-output",
        default=None,
        help="Markdown opcional con resumen de correcciones.",
    )
    p.add_argument(
        "--top-runs",
        type=int,
        default=15,
        help="Numero de rachas principales a considerar.",
    )
    p.add_argument(
        "--walk-threshold",
        type=float,
        default=0.75,
        help="Probabilidad minima en todos los modelos para corregir a walking.",
    )
    p.add_argument(
        "--not-walk-threshold",
        type=float,
        default=0.25,
        help="Probabilidad maxima en todos los modelos para corregir a not_walking.",
    )
    return p


def normalize_time(series: pd.Series) -> pd.Series:
    """Parse timestamps as UTC."""
    return pd.to_datetime(series, utc=True, format="mixed")


def build_consensus(predictions: pd.DataFrame) -> pd.DataFrame:
    """Build one consensus row per original window."""
    key_cols = ["reference", "time_center", "dataset_source"]
    predictions = predictions.copy()
    predictions["time_center"] = normalize_time(predictions["time_center"])
    consensus = (
        predictions.groupby(key_cols, sort=False)
        .agg(
            target=("target", "first"),
            mov_type=("mov_type", "first"),
            models=("model", "nunique"),
            votes_walking=("prediction", "sum"),
            min_prob_walking=("prob_walking", "min"),
            max_prob_walking=("prob_walking", "max"),
            mean_prob_walking=("prob_walking", "mean"),
        )
        .reset_index()
    )
    return consensus


def selected_run_mask(consensus: pd.DataFrame, runs: pd.DataFrame, top_runs: int) -> pd.Series:
    """Return mask for windows covered by top audited runs."""
    selected = runs.sort_values(["windows", "max_probability"], ascending=False).head(top_runs)
    mask = pd.Series(False, index=consensus.index)
    for _, run in selected.iterrows():
        start = pd.to_datetime(run["run_start"], utc=True, format="mixed")
        end = pd.to_datetime(run["run_end"], utc=True, format="mixed")
        run_mask = (
            consensus["reference"].astype(str).eq(str(run["reference"]))
            & consensus["time_center"].between(start, end)
        )
        mask = mask | run_mask
    return mask


def build_corrections(
    consensus: pd.DataFrame,
    *,
    run_mask: pd.Series,
    walk_threshold: float,
    not_walk_threshold: float,
) -> pd.DataFrame:
    """Select conservative consensus corrections inside audited runs."""
    to_walking = (
        consensus["target"].eq(0)
        & consensus["votes_walking"].eq(consensus["models"])
        & consensus["min_prob_walking"].ge(walk_threshold)
    )
    to_not_walking = (
        consensus["target"].eq(1)
        & consensus["votes_walking"].eq(0)
        & consensus["max_prob_walking"].le(not_walk_threshold)
    )
    corrections = consensus[run_mask & (to_walking | to_not_walking)].copy()
    corrections["new_target"] = corrections["target"].map({0: 1, 1: 0}).astype("int8")
    corrections["new_mov_type"] = corrections["new_target"].map(TARGET_TO_LABEL)
    corrections["correction_reason"] = "top_error_run_consensus_oof"
    return corrections


def apply_corrections(df: pd.DataFrame, corrections: pd.DataFrame) -> pd.DataFrame:
    """Apply corrections to target and mov_type columns."""
    output = df.copy()
    output["time_center"] = normalize_time(output["time_center"])
    key_cols = ["reference", "time_center", "dataset_source"]
    correction_values = corrections[key_cols + ["new_target", "new_mov_type"]]
    merged = output.merge(
        correction_values,
        on=key_cols,
        how="left",
        validate="one_to_one",
    )
    has_correction = merged["new_target"].notna()
    merged.loc[has_correction, "target"] = merged.loc[has_correction, "new_target"].astype(
        "int8"
    )
    merged.loc[has_correction, "mov_type"] = merged.loc[has_correction, "new_mov_type"]
    return merged.drop(columns=["new_target", "new_mov_type"])


def write_summary(path: Path, corrections: pd.DataFrame, rows_before: int) -> None:
    """Write a compact markdown correction summary."""
    lines = [
        "# Correccion auditada de etiquetas",
        "",
        f"- filas de entrada: {rows_before}",
        f"- ventanas corregidas: {len(corrections)}",
        "",
        "## Correcciones por paciente/origen",
        "",
    ]
    if corrections.empty:
        lines.append("- no se aplicaron correcciones")
    else:
        grouped = (
            corrections.groupby(["reference", "dataset_source", "target", "new_target"])
            .size()
            .reset_index(name="windows")
            .sort_values("windows", ascending=False)
        )
        for _, row in grouped.iterrows():
            lines.append(
                f"- {row['reference']} | {row['dataset_source']} | "
                f"{TARGET_TO_LABEL[int(row['target'])]} -> "
                f"{TARGET_TO_LABEL[int(row['new_target'])]}: {int(row['windows'])}"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Apply audited corrections."""
    args = build_parser().parse_args()
    df = pd.read_parquet(args.input)
    predictions = pd.read_csv(args.predictions)
    runs = pd.read_csv(args.runs)

    consensus = build_consensus(predictions)
    run_mask = selected_run_mask(consensus, runs, top_runs=args.top_runs)
    corrections = build_corrections(
        consensus,
        run_mask=run_mask,
        walk_threshold=args.walk_threshold,
        not_walk_threshold=args.not_walk_threshold,
    )
    corrected = apply_corrections(df, corrections)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    corrected.to_parquet(output, index=False)

    corrections_output = Path(args.corrections_output)
    corrections_output.parent.mkdir(parents=True, exist_ok=True)
    corrections.to_csv(corrections_output, index=False)

    if args.summary_output:
        write_summary(Path(args.summary_output), corrections, rows_before=len(df))

    print(f"Input parquet: {args.input}")
    print(f"Rows: {len(df)}")
    print(f"Corrections: {len(corrections)}")
    print(f"Output parquet: {output}")
    print(f"Corrections output: {corrections_output}")
    if args.summary_output:
        print(f"Summary output: {args.summary_output}")
    if not corrections.empty:
        print()
        print(
            corrections.groupby(["reference", "dataset_source", "target", "new_target"])
            .size()
            .reset_index(name="windows")
            .sort_values("windows", ascending=False)
            .to_string(index=False)
        )


if __name__ == "__main__":
    main()
