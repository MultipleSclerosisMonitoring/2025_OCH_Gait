#!/usr/bin/env python3
"""Summarize false-positive runs in sequence predictions."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Resume rachas de falsos positivos por segmento temporal."
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="CSV de predicciones con true_label y prediccion/probabilidad.",
    )
    p.add_argument(
        "-o",
        "--output",
        required=True,
        help="CSV de salida con rachas de falsos positivos.",
    )
    p.add_argument(
        "--prediction-col",
        default="prediction",
        help="Columna binaria de prediccion positiva.",
    )
    p.add_argument(
        "--probability-col",
        default="walking_probability",
        help="Columna de probabilidad de marcha.",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=None,
        help=(
            "Si se indica, recalcula la prediccion con probability_col >= threshold."
        ),
    )
    p.add_argument(
        "--gap-seconds",
        type=float,
        default=5.0,
        help="Salto temporal que separa segmentos si no hay columnas de segmento.",
    )
    p.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Numero de rachas principales a imprimir.",
    )
    return p


def segment_cols(df: pd.DataFrame) -> list[str]:
    """Return the columns that identify one temporal segment."""
    cols = ["reference", "segment_from_time", "segment_until_time"]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        return ["reference", "inferred_segment"]
    return cols


def add_inferred_segments(df: pd.DataFrame, gap_seconds: float) -> pd.DataFrame:
    """Add inferred temporal segments when explicit segment columns are absent."""
    if {"segment_from_time", "segment_until_time"}.issubset(df.columns):
        return df
    output = df.sort_values(["reference", "time_center"]).copy()
    gap = output.groupby("reference")["time_center"].diff()
    ref_change = output["reference"].ne(output["reference"].shift())
    gap_change = gap.gt(pd.Timedelta(seconds=gap_seconds)).fillna(False)
    output["inferred_segment_id"] = (ref_change | gap_change).cumsum().astype(int)
    output["inferred_segment"] = (
        output["reference"].astype(str)
        + "_segment_"
        + output["inferred_segment_id"].astype(str)
    )
    return output


def add_label_and_prediction_columns(
    df: pd.DataFrame,
    prediction_col: str,
    probability_col: str,
    threshold: float | None,
) -> pd.DataFrame:
    """Normalize label and prediction columns for false-positive analysis."""
    output = df.copy()
    if "true_label" not in output.columns:
        if "mov_type" in output.columns:
            output["true_label"] = output["mov_type"].astype(str)
        elif "target" in output.columns:
            output["true_label"] = output["target"].map(
                {0: "not_walking", 1: "walking"}
            )
        else:
            raise ValueError("Falta true_label, mov_type o target.")
    if threshold is not None:
        if probability_col not in output.columns:
            raise ValueError(f"No existe probability_col={probability_col}")
        output[prediction_col] = (
            output[probability_col].astype(float) >= threshold
        ).astype(int)
    return output


def summarize_runs(
    df: pd.DataFrame,
    prediction_col: str,
    probability_col: str,
    gap_seconds: float,
    threshold: float | None,
) -> pd.DataFrame:
    """Build one row per consecutive false-positive run."""
    if probability_col not in df.columns:
        raise ValueError(f"No existe probability_col={probability_col}")

    df = add_label_and_prediction_columns(
        df=df,
        prediction_col=prediction_col,
        probability_col=probability_col,
        threshold=threshold,
    )
    if prediction_col not in df.columns:
        raise ValueError(f"No existe prediction_col={prediction_col}")
    df["time_center"] = pd.to_datetime(df["time_center"], utc=True, format="mixed")
    df = add_inferred_segments(df, gap_seconds=gap_seconds)
    df = df.sort_values([*segment_cols(df), "time_center"]).reset_index(drop=True)
    df["is_false_positive"] = (
        (df["true_label"] == "not_walking") & (df[prediction_col].astype(int) == 1)
    )

    rows: list[dict] = []
    for segment_key, segment in df.groupby(segment_cols(df), sort=False):
        run_id = (segment["is_false_positive"] != segment["is_false_positive"].shift()).cumsum()
        fp_runs = segment[segment["is_false_positive"]].groupby(run_id, sort=False)
        for _, run in fp_runs:
            rows.append(
                {
                    "reference": segment_key[0],
                    "segment": "|".join(str(value) for value in segment_key),
                    "run_start": run["time_center"].iloc[0],
                    "run_end": run["time_center"].iloc[-1],
                    "windows": int(len(run)),
                    "mean_probability": float(run[probability_col].mean()),
                    "max_probability": float(run[probability_col].max()),
                    "threshold": threshold,
                    "expected_content": run["expected_content"].iloc[0]
                    if "expected_content" in run.columns
                    else "not_walking",
                    "seen_patient": bool(run["seen_patient"].iloc[0])
                    if "seen_patient" in run.columns
                    else pd.NA,
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "reference",
                "segment",
                "run_start",
                "run_end",
                "windows",
                "mean_probability",
                "max_probability",
                "threshold",
                "expected_content",
                "seen_patient",
            ]
        )

    return pd.DataFrame(rows).sort_values(
        ["windows", "max_probability"],
        ascending=False,
    )


def main() -> None:
    """Read predictions, summarize false-positive runs, and save CSV."""
    args = build_parser().parse_args()
    df = pd.read_csv(args.input)
    runs = summarize_runs(
        df=df,
        prediction_col=args.prediction_col,
        probability_col=args.probability_col,
        gap_seconds=args.gap_seconds,
        threshold=args.threshold,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    runs.to_csv(output, index=False)

    print(f"Input: {args.input}")
    print(f"Output: {output}")
    print(f"False-positive runs: {len(runs)}")
    if not runs.empty:
        print()
        print(runs.head(args.top_n).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
