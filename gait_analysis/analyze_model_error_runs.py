#!/usr/bin/env python3
"""Summarize false-positive and false-negative runs from model predictions."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Resume rachas de errores de clasificacion por paciente y segmento."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="CSV de predicciones con target, prediction y probabilidad.",
    )
    p.add_argument(
        "-o",
        "--output",
        required=True,
        help="CSV de salida con las rachas de error.",
    )
    p.add_argument(
        "--patient-output",
        default=None,
        help="CSV opcional con resumen por paciente.",
    )
    p.add_argument(
        "--summary-output",
        default=None,
        help="Markdown opcional con resumen humano.",
    )
    p.add_argument(
        "--model",
        default=None,
        help="Filtra un modelo concreto si el CSV contiene varios.",
    )
    p.add_argument(
        "--prediction-col",
        default="prediction",
        help="Columna binaria de prediccion.",
    )
    p.add_argument(
        "--probability-col",
        default="prob_walking",
        help="Columna de probabilidad de marcha.",
    )
    p.add_argument(
        "--gap-seconds",
        type=float,
        default=5.0,
        help="Salto temporal que separa segmentos si no hay columnas de segmento.",
    )
    p.add_argument(
        "--error-type",
        choices=["fp", "fn", "both"],
        default="both",
        help="Tipo de error a resumir.",
    )
    p.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Numero de rachas principales a imprimir.",
    )
    return p


def normalize_predictions(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize label, prediction and time columns."""
    output = df.copy()
    if "target" not in output.columns:
        if "mov_type" in output.columns:
            output["target"] = output["mov_type"].map(
                {"not_walking": 0, "walking": 1}
            )
        else:
            raise ValueError("Falta target o mov_type.")
    output["target"] = output["target"].astype(int)
    if "prediction" not in output.columns:
        raise ValueError("Falta prediction.")
    output["prediction"] = output["prediction"].astype(int)
    if "time_center" not in output.columns:
        raise ValueError("Falta time_center.")
    output["time_center"] = pd.to_datetime(output["time_center"], utc=True, format="mixed")
    if "reference" not in output.columns:
        raise ValueError("Falta reference.")
    return output


def add_inferred_segments(df: pd.DataFrame, gap_seconds: float) -> pd.DataFrame:
    """Add inferred temporal segments when explicit segment columns are absent."""
    if {"segment_from_time", "segment_until_time"}.issubset(df.columns):
        return df
    output = df.sort_values(["reference", "time_center"]).copy()
    ref_change = output["reference"].ne(output["reference"].shift())
    gap = output.groupby("reference")["time_center"].diff()
    gap_change = gap.gt(pd.Timedelta(seconds=gap_seconds)).fillna(False)
    output["inferred_segment_id"] = (ref_change | gap_change).cumsum().astype(int)
    output["inferred_segment"] = (
        output["reference"].astype(str)
        + "_segment_"
        + output["inferred_segment_id"].astype(str)
    )
    return output


def segment_cols(df: pd.DataFrame) -> list[str]:
    """Return the columns that identify one temporal segment."""
    cols = ["reference", "segment_from_time", "segment_until_time"]
    if not set(cols).issubset(df.columns):
        return ["reference", "inferred_segment"]
    return cols


def error_mask(df: pd.DataFrame, error_type: str) -> pd.Series:
    """Return a boolean mask for the requested classification error."""
    if error_type == "fp":
        return (df["target"] == 0) & (df["prediction"] == 1)
    if error_type == "fn":
        return (df["target"] == 1) & (df["prediction"] == 0)
    return ((df["target"] == 0) & (df["prediction"] == 1)) | (
        (df["target"] == 1) & (df["prediction"] == 0)
    )


def summarize_runs(
    df: pd.DataFrame,
    probability_col: str,
    gap_seconds: float,
    error_type: str,
) -> pd.DataFrame:
    """Build one row per consecutive error run."""
    if probability_col not in df.columns:
        raise ValueError(f"No existe probability_col={probability_col}")

    df = add_inferred_segments(df, gap_seconds=gap_seconds)
    df = df.sort_values([*segment_cols(df), "time_center"]).reset_index(drop=True)
    df["is_error"] = error_mask(df, error_type)

    rows: list[dict] = []
    for segment_key, segment in df.groupby(segment_cols(df), sort=False):
        run_id = (segment["is_error"] != segment["is_error"].shift()).cumsum()
        runs = segment[segment["is_error"]].groupby(run_id, sort=False)
        for _, run in runs:
            if run.empty:
                continue
            fp = int(((run["target"] == 0) & (run["prediction"] == 1)).sum())
            fn = int(((run["target"] == 1) & (run["prediction"] == 0)).sum())
            if fp and fn:
                run_error_type = "mixed"
                true_label = "mixed"
                prediction_label = "mixed"
            elif fp:
                run_error_type = "fp"
                true_label = "not_walking"
                prediction_label = "walking"
            else:
                run_error_type = "fn"
                true_label = "walking"
                prediction_label = "not_walking"
            rows.append(
                {
                    "error_type": run_error_type,
                    "reference": segment_key[0],
                    "segment": "|".join(str(value) for value in segment_key),
                    "run_start": run["time_center"].iloc[0],
                    "run_end": run["time_center"].iloc[-1],
                    "windows": int(len(run)),
                    "fp_windows": fp,
                    "fn_windows": fn,
                    "mean_probability": float(run[probability_col].mean()),
                    "max_probability": float(run[probability_col].max()),
                    "true_label": true_label,
                    "prediction_label": prediction_label,
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "error_type",
                "reference",
                "segment",
                "run_start",
                "run_end",
                "windows",
                "fp_windows",
                "fn_windows",
                "mean_probability",
                "max_probability",
                "true_label",
                "prediction_label",
            ]
        )

    return pd.DataFrame(rows).sort_values(
        ["windows", "max_probability"],
        ascending=False,
    )


def summarize_by_patient(df: pd.DataFrame, error_type: str) -> pd.DataFrame:
    """Summarize errors by patient/reference."""
    grouped = df.groupby("reference", sort=False)
    rows: list[dict] = []
    for reference, part in grouped:
        fp = int(((part["target"] == 0) & (part["prediction"] == 1)).sum())
        fn = int(((part["target"] == 1) & (part["prediction"] == 0)).sum())
        tp = int(((part["target"] == 1) & (part["prediction"] == 1)).sum())
        tn = int(((part["target"] == 0) & (part["prediction"] == 0)).sum())
        total = int(len(part))
        walking = int((part["target"] == 1).sum())
        not_walking = total - walking
        row = {
            "reference": reference,
            "rows": total,
            "walking": walking,
            "not_walking": not_walking,
            "fp_windows": fp,
            "fn_windows": fn,
            "tp_windows": tp,
            "tn_windows": tn,
            "fp_rate": fp / not_walking if not_walking else 0.0,
            "fn_rate": fn / walking if walking else 0.0,
            "error_windows": fp + fn,
        }
        rows.append(row)
    out = pd.DataFrame(rows)
    if out.empty:
        return out

    if error_type == "fp":
        return out.sort_values(
            ["fp_windows", "error_windows", "fn_windows"],
            ascending=False,
        )
    if error_type == "fn":
        return out.sort_values(
            ["fn_windows", "error_windows", "fp_windows"],
            ascending=False,
        )
    return out.sort_values(
        ["error_windows", "fp_windows", "fn_windows"],
        ascending=False,
    )


def write_summary_markdown(
    path: Path,
    df: pd.DataFrame,
    runs: pd.DataFrame,
    patient_summary: pd.DataFrame,
    error_type: str,
    model: str | None,
) -> None:
    """Write a compact human-readable summary."""
    total = len(df)
    fp = int(((df["target"] == 0) & (df["prediction"] == 1)).sum())
    fn = int(((df["target"] == 1) & (df["prediction"] == 0)).sum())
    walking = int((df["target"] == 1).sum())
    not_walking = total - walking
    lines = [
        "# Model error analysis",
        "",
        f"- model: {model or 'all'}",
        f"- error_type: {error_type}",
        f"- rows: {total}",
        f"- false positives: {fp}",
        f"- false negatives: {fn}",
        f"- false positive rate: {fp / not_walking if not_walking else 0.0:.4f}",
        f"- false negative rate: {fn / walking if walking else 0.0:.4f}",
        "",
        "## Main patients",
    ]
    top_patients = patient_summary.head(10)
    if top_patients.empty:
        lines.append("- no errors found")
    else:
        for _, row in top_patients.iterrows():
            lines.append(
                f"- {row['reference']}: "
                f"fp={int(row['fp_windows'])}, "
                f"fn={int(row['fn_windows'])}, "
                f"error_windows={int(row['error_windows'])}, "
                f"fp_rate={row['fp_rate']:.4f}, "
                f"fn_rate={row['fn_rate']:.4f}"
            )
    lines.extend(["", "## Main runs"])
    top_runs = runs.head(10)
    if top_runs.empty:
        lines.append("- no error runs found")
    else:
        for _, row in top_runs.iterrows():
            lines.append(
                f"- {row['reference']} | {row['run_start']} -> {row['run_end']} | "
                f"{int(row['windows'])} windows | "
                f"mean_prob={row['mean_probability']:.4f} | "
                f"max_prob={row['max_probability']:.4f}"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Read predictions, summarize error runs, and save outputs."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    patient_output = Path(args.patient_output) if args.patient_output else None
    summary_output = Path(args.summary_output) if args.summary_output else None

    df = pd.read_csv(input_path)
    if args.model and "model" in df.columns:
        df = df[df["model"].eq(args.model)].copy()
    if df.empty:
        raise ValueError("No hay predicciones para evaluar.")
    df = normalize_predictions(df)

    runs = summarize_runs(
        df=df,
        probability_col=args.probability_col,
        gap_seconds=args.gap_seconds,
        error_type=args.error_type,
    )
    patient_summary = summarize_by_patient(df, error_type=args.error_type)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    runs.to_csv(output_path, index=False)
    if patient_output:
        patient_output.parent.mkdir(parents=True, exist_ok=True)
        patient_summary.to_csv(patient_output, index=False)
    if summary_output:
        write_summary_markdown(
            path=summary_output,
            df=df,
            runs=runs,
            patient_summary=patient_summary,
            error_type=args.error_type,
            model=args.model,
        )

    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    if patient_output:
        print(f"Patient output: {patient_output}")
    if summary_output:
        print(f"Summary output: {summary_output}")
    print(f"Error runs: {len(runs)}")
    if not runs.empty:
        print()
        print(runs.head(args.top_n).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
