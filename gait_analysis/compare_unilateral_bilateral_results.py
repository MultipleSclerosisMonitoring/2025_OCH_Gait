#!/usr/bin/env python3
"""Build a compact comparison between bilateral and unilateral CV results."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


INPUTS = {
    "bilateral": Path("results/ml_model_comparison_cv3_bilateral_summary.csv"),
    "unilateral": Path("results/ml_model_comparison_cv3_unilateral_summary.csv"),
}
OUTPUT_CSV = Path("results/unilateral_vs_bilateral_cv3_summary.csv")
OUTPUT_MD = Path("results/unilateral_vs_bilateral_cv3_summary.md")


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    """Render a simple GitHub-flavored Markdown table without extra deps."""
    columns = list(df.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in df.iterrows():
        values = [str(row[col]) for col in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main() -> None:
    """Create comparison outputs."""
    frames = []
    for representation, path in INPUTS.items():
        df = pd.read_csv(path)
        df.insert(0, "representation", representation)
        frames.append(df)

    comparison = pd.concat(frames, ignore_index=True)
    metric_cols = [
        "accuracy_mean",
        "accuracy_sd",
        "precision_walking_mean",
        "precision_walking_sd",
        "recall_walking_mean",
        "recall_walking_sd",
        "f1_walking_mean",
        "f1_walking_sd",
        "f1_macro_mean",
        "f1_macro_sd",
    ]
    compact = comparison[["representation", "model", *metric_cols]].copy()
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    compact.to_csv(OUTPUT_CSV, index=False)

    best_by_representation = compact.loc[
        compact.groupby("representation")["f1_walking_mean"].idxmax()
    ].sort_values("representation")
    best_bilateral = best_by_representation[
        best_by_representation["representation"].eq("bilateral")
    ].iloc[0]
    best_unilateral = best_by_representation[
        best_by_representation["representation"].eq("unilateral")
    ].iloc[0]
    delta_f1 = (
        best_unilateral["f1_walking_mean"] - best_bilateral["f1_walking_mean"]
    )

    rounded = compact.copy()
    for col in metric_cols:
        rounded[col] = rounded[col].map(lambda value: f"{value:.4f}")

    markdown = [
        "# Comparacion CV3: bilateral vs unilateral",
        "",
        "## Objetivo",
        "",
        (
            "Comparar la representacion bilateral sincronizada frente a una vista "
            "unilateral por extremidad usando los mismos clasificadores y la misma "
            "validacion cruzada estratificada de 3 folds."
        ),
        "",
        "## Resultados",
        "",
        dataframe_to_markdown(rounded),
        "",
        "## Lectura principal",
        "",
        (
            f"El mejor modelo bilateral es `{best_bilateral['model']}` con "
            f"F1 de marcha medio {best_bilateral['f1_walking_mean']:.4f}."
        ),
        (
            f"El mejor modelo unilateral es `{best_unilateral['model']}` con "
            f"F1 de marcha medio {best_unilateral['f1_walking_mean']:.4f}."
        ),
        (
            f"La diferencia unilateral - bilateral en el mejor F1 de marcha es "
            f"{delta_f1:.4f}."
        ),
        "",
        "## Interpretacion",
        "",
        (
            "La representacion bilateral sigue siendo superior cuando ambos pies "
            "estan disponibles, porque conserva informacion conjunta entre "
            "extremidades. La representacion unilateral pierde algo de rendimiento, "
            "pero mantiene resultados competitivos y permite trabajar con casos "
            "asimetricos o con un solo sensor util."
        ),
        "",
        (
            "Por tanto, la recomendacion practica es mantener el modelo bilateral "
            "como modelo principal y usar la via unilateral como alternativa para "
            "pacientes/tramos donde la sincronizacion perfecta de ambos pies no sea "
            "clinicamente o tecnicamente fiable."
        ),
        "",
    ]
    OUTPUT_MD.write_text("\n".join(markdown), encoding="utf-8")

    print(f"CSV: {OUTPUT_CSV}")
    print(f"Markdown: {OUTPUT_MD}")
    print(rounded.to_string(index=False))


if __name__ == "__main__":
    main()
