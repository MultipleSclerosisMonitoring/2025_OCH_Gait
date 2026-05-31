#!/usr/bin/env python3
"""Audit out-of-fold model predictions by patient and data source."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Resume errores y metricas por paciente/origen/modelo."
    )
    p.add_argument("-i", "--input", required=True, help="CSV de predicciones.")
    p.add_argument("-o", "--output", required=True, help="CSV de auditoria.")
    p.add_argument(
        "--summary-output",
        default=None,
        help="Markdown opcional con pacientes prioritarios a revisar.",
    )
    p.add_argument(
        "--source-col",
        default="dataset_source",
        help="Columna de origen de datos.",
    )
    p.add_argument(
        "--top-n",
        type=int,
        default=12,
        help="Numero de grupos prioritarios a incluir en el resumen.",
    )
    return p


def score_group(part: pd.DataFrame) -> dict[str, float | int]:
    """Return metrics and confusion counts for one prediction group."""
    y_true = part["target"].astype(int)
    y_pred = part["prediction"].astype(int)
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    walking = int((y_true == 1).sum())
    not_walking = int((y_true == 0).sum())
    return {
        "rows": int(len(part)),
        "not_walking": not_walking,
        "walking": walking,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "error_windows": fp + fn,
        "error_rate": (fp + fn) / len(part) if len(part) else 0.0,
        "fp_rate": fp / not_walking if not_walking else 0.0,
        "fn_rate": fn / walking if walking else 0.0,
        "accuracy": accuracy_score(y_true, y_pred),
        "precision_walking": precision_score(
            y_true,
            y_pred,
            pos_label=1,
            zero_division=0,
        ),
        "recall_walking": recall_score(
            y_true,
            y_pred,
            pos_label=1,
            zero_division=0,
        ),
        "f1_walking": f1_score(
            y_true,
            y_pred,
            pos_label=1,
            zero_division=0,
        ),
        "f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "mean_prob_walking": float(part["prob_walking"].mean())
        if "prob_walking" in part.columns
        else 0.0,
    }


def build_audit(df: pd.DataFrame, source_col: str) -> pd.DataFrame:
    """Build audit rows by model, patient and source."""
    required = {"model", "reference", "target", "prediction"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas: {sorted(missing)}")

    group_cols = ["model", "reference"]
    if source_col in df.columns:
        group_cols.append(source_col)

    rows = []
    for group_values, part in df.groupby(group_cols, sort=False):
        if not isinstance(group_values, tuple):
            group_values = (group_values,)
        row = dict(zip(group_cols, group_values, strict=False))
        row.update(score_group(part))
        rows.append(row)

    return pd.DataFrame(rows).sort_values(
        ["error_windows", "error_rate", "fn", "fp"],
        ascending=False,
    )


def write_summary(path: Path, audit: pd.DataFrame, *, top_n: int) -> None:
    """Write a compact markdown summary of priority review targets."""
    lines = [
        "# Auditoria de errores por paciente",
        "",
        "## Prioridad de revision",
        "",
    ]
    top = audit.head(top_n)
    if top.empty:
        lines.append("- No se han encontrado errores.")
    else:
        for _, row in top.iterrows():
            source = row.get("dataset_source", "unknown")
            lines.append(
                f"- {row['model']} | {row['reference']} | {source}: "
                f"errors={int(row['error_windows'])}, "
                f"fp={int(row['fp'])}, fn={int(row['fn'])}, "
                f"error_rate={row['error_rate']:.4f}, "
                f"f1_walking={row['f1_walking']:.4f}, "
                f"f1_macro={row['f1_macro']:.4f}"
            )

    lines.extend(
        [
            "",
            "## Lectura",
            "",
            (
                "Los grupos con muchos falsos negativos son candidatos a revisar "
                "etiquetas de marcha o variabilidad real no cubierta. Los grupos "
                "con muchos falsos positivos son candidatos a revisar actividades "
                "no marcha que se parecen a marcha."
            ),
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Run audit and save outputs."""
    args = build_parser().parse_args()
    df = pd.read_csv(args.input)
    audit = build_audit(df, source_col=args.source_col)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output, index=False)

    if args.summary_output:
        write_summary(Path(args.summary_output), audit, top_n=args.top_n)

    print(f"Input: {args.input}")
    print(f"Output: {output}")
    if args.summary_output:
        print(f"Summary output: {args.summary_output}")
    print(audit.head(args.top_n).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
