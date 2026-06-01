#!/usr/bin/env python3
"""Audit Influx references against labels and current datasets."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any
import warnings

import pandas as pd
import urllib3

from gait_analysis.config import ConfigLoader
from gait_analysis.influx_service import InfluxService


DEFAULT_DATASETS = [
    "salidas_test/data_extension_selected/"
    "main_binary_window_features_with_auto_influx_extension_audit_corrected_plus_054full_no_transition_5s.parquet",
    "salidas_test/data_extension_selected/"
    "main_binary_window_features_with_auto_influx_extension_audit_corrected_no_transition_5s.parquet",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audita referencias disponibles en Influx, las cruza con etiquetas "
            "existentes y genera una decision de extraccion por referencia."
        )
    )
    parser.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Configuracion con credenciales y tags de Influx.",
    )
    parser.add_argument(
        "--start",
        default="2024-01-01T00:00:00Z",
        help="Inicio UTC del rango de auditoria Influx.",
    )
    parser.add_argument(
        "--stop",
        default="2026-06-02T00:00:00Z",
        help="Fin UTC del rango de auditoria Influx.",
    )
    parser.add_argument(
        "--ground-truth",
        default="salidas_test/ground_truth_clean.xlsx",
        help="Ground truth limpio si existe.",
    )
    parser.add_argument(
        "--manual-candidates",
        default="experiment_configs/high_priority_new_patient_candidates.csv",
        help="CSV de referencias/ventanas indicadas manualmente.",
    )
    parser.add_argument(
        "--current-dataset",
        action="append",
        default=[],
        help="Parquet binario actual. Puede repetirse.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="experiment_configs/influx_reference_inventory_exhaustive.csv",
        help="CSV principal de auditoria.",
    )
    parser.add_argument(
        "--plan-output",
        default="experiment_configs/influx_reference_extraction_plan.csv",
        help="CSV filtrado con referencias accionables.",
    )
    parser.add_argument(
        "--summary",
        default="results/influx_reference_inventory_exhaustive_summary.md",
        help="Resumen Markdown.",
    )
    return parser


def field_filter(fields: list[str]) -> str:
    return " or ".join([f'r["_field"] == "{field}"' for field in fields])


def query_grouped_metric(
    influx: InfluxService,
    *,
    bucket: str,
    start: str,
    stop: str,
    ref_tag: str,
    foot_tag: str,
    fields: list[str],
    operation: str,
) -> pd.DataFrame:
    flux = f'''
from(bucket: "{bucket}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => {field_filter(fields)})
  |> group(columns: ["{ref_tag}", "{foot_tag}"])
  |> {operation}
'''
    rows: list[dict[str, Any]] = []
    for table in influx.query(flux):
        for record in table.records:
            values = record.values
            rows.append(
                {
                    "reference": str(values.get(ref_tag)),
                    "foot": str(values.get(foot_tag)),
                    "_time": values.get("_time"),
                    "_value": values.get("_value"),
                }
            )
    return pd.DataFrame(rows)


def load_current_references(paths: list[str]) -> set[str]:
    candidates = paths or DEFAULT_DATASETS
    for raw_path in candidates:
        path = Path(raw_path)
        if not path.exists():
            continue
        df = pd.read_parquet(path, columns=["reference"])
        return set(df["reference"].astype(str).unique())
    return set()


def load_ground_truth_summary(path: Path) -> pd.DataFrame:
    columns = [
        "reference",
        "gt_intervals",
        "gt_walking_intervals",
        "gt_not_walking_intervals",
        "gt_walking_s",
        "gt_not_walking_s",
        "gt_has_walking",
        "gt_has_not_walking",
        "gt_has_both_labels",
        "gt_first_label",
        "gt_last_label",
    ]
    if not path.exists():
        return pd.DataFrame(columns=columns)

    gt = pd.read_excel(path)
    gt["Reference"] = gt["Reference"].astype(str)
    gt["datefrom"] = pd.to_datetime(gt["datefrom"], format="mixed")
    gt["dateuntil"] = pd.to_datetime(gt["dateuntil"], format="mixed")
    gt["mov_type"] = gt["mov_type"].astype(str).str.strip()
    gt["duration_s"] = (gt["dateuntil"] - gt["datefrom"]).dt.total_seconds()

    rows = []
    for reference, group in gt.groupby("Reference"):
        label_durations = group.groupby("mov_type")["duration_s"].sum()
        label_counts = group.groupby("mov_type").size()
        walking_s = float(label_durations.get("walking", 0.0))
        not_walking_s = float(label_durations.get("not_walking", 0.0))
        rows.append(
            {
                "reference": reference,
                "gt_intervals": int(len(group)),
                "gt_walking_intervals": int(label_counts.get("walking", 0)),
                "gt_not_walking_intervals": int(label_counts.get("not_walking", 0)),
                "gt_walking_s": walking_s,
                "gt_not_walking_s": not_walking_s,
                "gt_has_walking": walking_s > 0,
                "gt_has_not_walking": not_walking_s > 0,
                "gt_has_both_labels": walking_s > 0 and not_walking_s > 0,
                "gt_first_label": group["datefrom"].min(),
                "gt_last_label": group["dateuntil"].max(),
            }
        )
    return pd.DataFrame(rows)


def load_manual_candidates(path: Path) -> pd.DataFrame:
    columns = [
        "reference",
        "manual_candidate",
        "manual_priority",
        "manual_first_from",
        "manual_last_until",
        "manual_candidate_rows",
    ]
    if not path.exists():
        return pd.DataFrame(columns=columns)
    df = pd.read_csv(path)
    df["Reference"] = df["Reference"].astype(str)
    df["datefrom"] = pd.to_datetime(df["datefrom"], format="mixed")
    df["dateuntil"] = pd.to_datetime(df["dateuntil"], format="mixed")
    rows = []
    for reference, group in df.groupby("Reference"):
        rows.append(
            {
                "reference": reference,
                "manual_candidate": True,
                "manual_priority": int(group["priority"].min())
                if "priority" in group
                else pd.NA,
                "manual_first_from": group["datefrom"].min(),
                "manual_last_until": group["dateuntil"].max(),
                "manual_candidate_rows": int(len(group)),
            }
        )
    return pd.DataFrame(rows)


def build_influx_inventory(cfg: Any, start: str, stop: str) -> pd.DataFrame:
    with InfluxService(cfg.influx) as influx:
        counts = query_grouped_metric(
            influx,
            bucket=cfg.influx.bucket,
            start=start,
            stop=stop,
            ref_tag=cfg.ref_tag,
            foot_tag=cfg.foot_tag,
            fields=cfg.spectrogram.signals,
            operation='count(column: "_value")',
        )
        first = query_grouped_metric(
            influx,
            bucket=cfg.influx.bucket,
            start=start,
            stop=stop,
            ref_tag=cfg.ref_tag,
            foot_tag=cfg.foot_tag,
            fields=cfg.spectrogram.signals,
            operation='first(column: "_value")',
        )
        last = query_grouped_metric(
            influx,
            bucket=cfg.influx.bucket,
            start=start,
            stop=stop,
            ref_tag=cfg.ref_tag,
            foot_tag=cfg.foot_tag,
            fields=cfg.spectrogram.signals,
            operation='last(column: "_value")',
        )

    counts = counts[counts["foot"].isin(cfg.spectrogram.feet)].copy()
    first = first[first["foot"].isin(cfg.spectrogram.feet)].copy()
    last = last[last["foot"].isin(cfg.spectrogram.feet)].copy()

    count_wide = counts.pivot_table(
        index="reference", columns="foot", values="_value", aggfunc="sum"
    ).reset_index()
    first_wide = first.pivot_table(
        index="reference", columns="foot", values="_time", aggfunc="min"
    ).reset_index()
    last_wide = last.pivot_table(
        index="reference", columns="foot", values="_time", aggfunc="max"
    ).reset_index()

    for foot in cfg.spectrogram.feet:
        count_wide = count_wide.rename(columns={foot: f"{foot.lower()}_records"})
        first_wide = first_wide.rename(columns={foot: f"{foot.lower()}_first_utc"})
        last_wide = last_wide.rename(columns={foot: f"{foot.lower()}_last_utc"})

    output = count_wide.merge(first_wide, on="reference", how="outer")
    output = output.merge(last_wide, on="reference", how="outer")
    for foot in cfg.spectrogram.feet:
        record_col = f"{foot.lower()}_records"
        first_col = f"{foot.lower()}_first_utc"
        last_col = f"{foot.lower()}_last_utc"
        if record_col not in output.columns:
            output[record_col] = 0
        if first_col not in output.columns:
            output[first_col] = pd.NaT
        if last_col not in output.columns:
            output[last_col] = pd.NaT

    record_cols = [f"{foot.lower()}_records" for foot in cfg.spectrogram.feet]
    output[record_cols] = output[record_cols].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
    output["total_records"] = output[record_cols].sum(axis=1)
    output["valid_both_feet"] = output[record_cols].gt(0).all(axis=1)

    first_cols = [f"{foot.lower()}_first_utc" for foot in cfg.spectrogram.feet]
    last_cols = [f"{foot.lower()}_last_utc" for foot in cfg.spectrogram.feet]
    for col in first_cols + last_cols:
        output[col] = pd.to_datetime(output[col], utc=True, errors="coerce")
    output["intersection_start_utc"] = output[first_cols].max(axis=1)
    output["intersection_stop_utc"] = output[last_cols].min(axis=1)
    output["intersection_duration_h"] = (
        output["intersection_stop_utc"] - output["intersection_start_utc"]
    ).dt.total_seconds() / 3600.0
    return output


def classify(row: pd.Series) -> tuple[str, str, str]:
    if bool(row["in_current_dataset"]):
        return (
            "already_integrated",
            "No extraer para baseline; ya esta en el dataset actual.",
            "Solo reextraer si se quiere auditar o ampliar ventanas concretas.",
        )
    if not bool(row["valid_both_feet"]):
        return (
            "blocked_no_bilateral_coverage",
            "No extraer para espectrogramas bilaterales.",
            "Revisar referencia/timestamp si se esperaba cobertura en Grafana.",
        )
    if bool(row["gt_has_both_labels"]):
        return (
            "ready_labeled_extract",
            "Extraer espectrogramas y anadir al dataset etiquetado.",
            "Prioridad alta: aporta etiquetas walking y not_walking.",
        )
    if bool(row["gt_has_walking"]) or bool(row["gt_has_not_walking"]):
        return (
            "partial_label_needs_complement",
            "Extraer solo como bloque parcial o pedir etiqueta complementaria.",
            "No usar como paciente binario completo hasta tener ambas clases.",
        )
    if bool(row["manual_candidate"]):
        return (
            "available_needs_labeling",
            "Extraer muestras/spectrogramas para etiquetado manual.",
            "Prioridad media: hay ventana candidata indicada, falta etiqueta fiable.",
        )
    return (
        "available_unlabeled",
        "No incorporar al entrenamiento todavia.",
        "Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado.",
    )


def markdown_table(df: pd.DataFrame, columns: list[str], limit: int | None = None) -> str:
    view = df[columns].copy()
    if limit is not None:
        view = view.head(limit)
    if view.empty:
        return "_Sin filas._"
    view = view.fillna("").astype(str)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(row[col] for col in columns) + " |")
    return "\n".join(lines)


def write_summary(path: Path, df: pd.DataFrame, plan: pd.DataFrame, args: argparse.Namespace) -> None:
    status_counts = df["audit_status"].value_counts().rename_axis("status").reset_index(name="refs")
    label_ready = df[df["audit_status"].eq("ready_labeled_extract")]
    needs_labeling = df[df["audit_status"].eq("available_needs_labeling")]
    available_unlabeled = df[df["audit_status"].eq("available_unlabeled")]
    lines = [
        "# Auditoria exhaustiva de referencias Influx",
        "",
        f"- Rango UTC auditado: `{args.start}` a `{args.stop}`",
        f"- Inventario CSV: `{args.output}`",
        f"- Plan de extraccion CSV: `{args.plan_output}`",
        f"- Referencias con senal en Influx: {len(df)}",
        f"- Referencias con ambos pies: {int(df['valid_both_feet'].sum())}",
        f"- Referencias ya integradas: {int(df['in_current_dataset'].sum())}",
        f"- Referencias listas con etiquetas walking/not_walking: {len(label_ready)}",
        f"- Referencias candidatas con senal pero pendientes de etiqueta: {len(needs_labeling) + len(available_unlabeled)}",
        "",
        "Lectura principal: hay senal bilateral suficiente para seguir ampliando "
        "diversidad, pero no hay referencias nuevas que ya tengan etiquetas "
        "`walking` y `not_walking` en el ground truth local. La siguiente tarea "
        "no es reextraer a ciegas, sino etiquetar bloques de las referencias "
        "con senal disponible.",
        "",
        "## Estados",
        "",
        markdown_table(status_counts, ["status", "refs"]),
        "",
        "## Listas para extraccion etiquetada",
        "",
        markdown_table(
            label_ready.sort_values("total_records", ascending=False),
            [
                "reference",
                "right_records",
                "left_records",
                "gt_walking_s",
                "gt_not_walking_s",
                "intersection_start_utc",
                "intersection_stop_utc",
            ],
            limit=30,
        ),
        "",
        "## Candidatas indicadas pero pendientes de etiqueta",
        "",
        markdown_table(
            needs_labeling.sort_values(["manual_priority", "total_records"], ascending=[True, False]),
            [
                "reference",
                "manual_priority",
                "right_records",
                "left_records",
                "manual_first_from",
                "manual_last_until",
                "intersection_start_utc",
                "intersection_stop_utc",
                "extraction_decision",
            ],
            limit=40,
        ),
        "",
        "## Mas senal disponible sin etiqueta local",
        "",
        markdown_table(
            available_unlabeled.sort_values("total_records", ascending=False),
            [
                "reference",
                "right_records",
                "left_records",
                "intersection_start_utc",
                "intersection_stop_utc",
                "recommended_next_step",
            ],
            limit=40,
        ),
        "",
        "## Criterio operativo",
        "",
        "- `ready_labeled_extract`: se puede extraer desde Influx e incorporar tras generar espectrogramas.",
        "- `available_needs_labeling`: hay senal bilateral y una ventana candidata, pero falta etiqueta fiable.",
        "- `available_unlabeled`: hay senal bilateral, pero antes hay que crear/revisar etiquetas.",
        "- `partial_label_needs_complement`: existe una sola clase etiquetada; no sirve por si sola para un paciente binario completo.",
        "- `blocked_no_bilateral_coverage`: no es util para el pipeline bilateral actual sin corregir referencia o timestamps.",
        "",
        "Para referencias sin etiqueta local, `intersection_start_utc` y "
        "`intersection_stop_utc` marcan el rango real con ambos pies detectado "
        "en Influx. Si difiere de las ventanas manuales, debe priorizarse este "
        "rango real para generar plantillas de etiquetado.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = build_parser().parse_args()
    warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
    cfg = ConfigLoader(args.config).load()

    inventory = build_influx_inventory(cfg, args.start, args.stop)
    current_refs = load_current_references(args.current_dataset)
    gt = load_ground_truth_summary(Path(args.ground_truth))
    manual = load_manual_candidates(Path(args.manual_candidates))

    df = inventory.merge(gt, on="reference", how="left")
    df = df.merge(manual, on="reference", how="left")
    df["in_current_dataset"] = df["reference"].isin(current_refs)
    df["in_ground_truth"] = df["gt_intervals"].notna()
    df["manual_candidate"] = df["manual_candidate"].where(
        df["manual_candidate"].notna(), False
    ).astype(bool)

    bool_cols = [
        "gt_has_walking",
        "gt_has_not_walking",
        "gt_has_both_labels",
    ]
    for col in bool_cols:
        df[col] = df[col].where(df[col].notna(), False).astype(bool)
    numeric_cols = [
        "gt_intervals",
        "gt_walking_intervals",
        "gt_not_walking_intervals",
        "gt_walking_s",
        "gt_not_walking_s",
        "manual_candidate_rows",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    classified = df.apply(classify, axis=1, result_type="expand")
    df["audit_status"] = classified[0]
    df["extraction_decision"] = classified[1]
    df["recommended_next_step"] = classified[2]
    df = df.sort_values(
        [
            "audit_status",
            "manual_priority",
            "total_records",
            "reference",
        ],
        ascending=[True, True, False, True],
    ).reset_index(drop=True)

    plan = df[
        df["audit_status"].isin(
            [
                "ready_labeled_extract",
                "available_needs_labeling",
                "available_unlabeled",
                "partial_label_needs_complement",
            ]
        )
    ].copy()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)

    plan_output = Path(args.plan_output)
    plan_output.parent.mkdir(parents=True, exist_ok=True)
    plan.to_csv(plan_output, index=False)
    write_summary(Path(args.summary), df, plan, args)

    print(f"Output: {output}")
    print(f"Rows: {len(df)}")
    print(f"Plan output: {plan_output}")
    print(f"Plan rows: {len(plan)}")
    print(f"Summary: {args.summary}")
    print()
    print(df["audit_status"].value_counts().to_string())


if __name__ == "__main__":
    main()
