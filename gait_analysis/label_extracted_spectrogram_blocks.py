#!/usr/bin/env python3
"""Label extracted spectrogram block parquets from an extraction manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Etiqueta todos los parquets de espectrograma listados en un manifiesto "
            "y combina las salidas filtradas."
        )
    )
    p.add_argument(
        "--manifest",
        default="salidas_test/data_extension_selected/spectrogram_blocks_manifest.csv",
        help="Manifest CSV generado por extract_labeling_template_blocks.py.",
    )
    p.add_argument(
        "-g",
        "--ground-truth",
        default="experiment_configs/auto_labeled_selected_blocks_ground_truth_utc.csv",
        help="Ground truth UTC para etiquetar los espectrogramas.",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        default="salidas_test/data_extension_selected/labeled_spectrogram_blocks",
        help="Directorio para parquets etiquetados.",
    )
    p.add_argument(
        "--combined-output",
        default="salidas_test/data_extension_selected/auto_labeled_selected_blocks_spectrogram.parquet",
        help="Parquet combinado con filas etiquetadas.",
    )
    p.add_argument(
        "--summary",
        default="salidas_test/data_extension_selected/auto_labeled_selected_blocks_spectrogram_summary.md",
        help="Resumen Markdown.",
    )
    p.add_argument(
        "--resume-existing",
        action="store_true",
        help="Reutiliza parquets etiquetados ya existentes.",
    )
    return p


def labeled_path_for(input_path: Path, output_dir: Path) -> Path:
    """Return output path for one labeled spectrogram parquet."""
    return output_dir / f"{input_path.stem}_labeled.parquet"


def filtered_path_for(labeled_path: Path) -> Path:
    """Return filtered output path produced by label_spectrogram_with_ground_truth.py."""
    return labeled_path.with_name(labeled_path.stem + "_filtered.parquet")


def load_ground_truth(path: Path) -> pd.DataFrame:
    """Load UTC ground truth and normalize timestamps."""
    if path.suffix.lower() == ".csv":
        gt = pd.read_csv(path)
    else:
        gt = pd.read_excel(path)
    required = {"Reference", "datefrom", "dateuntil", "mov_type"}
    missing = required - set(gt.columns)
    if missing:
        raise ValueError(f"Faltan columnas requeridas en ground truth: {sorted(missing)}")
    gt = gt.copy()
    gt["datefrom"] = pd.to_datetime(gt["datefrom"], utc=True, format="mixed")
    gt["dateuntil"] = pd.to_datetime(gt["dateuntil"], utc=True, format="mixed")
    return gt.sort_values(["Reference", "datefrom", "dateuntil"]).reset_index(drop=True)


def label_spectrogram(input_path: Path, gt: pd.DataFrame, output_path: Path) -> Path:
    """Label one spectrogram parquet with vectorized interval masks."""
    df = pd.read_parquet(input_path)
    df["time_center"] = pd.to_datetime(df["time_center"], utc=True, format="mixed")
    df["mov_type"] = "NO_LABEL"

    for reference, ref_gt in gt.groupby("Reference", sort=False):
        ref_mask = df["reference"] == reference
        if not ref_mask.any():
            continue
        ref_times = df.loc[ref_mask, "time_center"]
        for _, interval in ref_gt.iterrows():
            label_mask = (
                ref_mask
                & (ref_times >= interval["datefrom"]).reindex(df.index, fill_value=False)
                & (ref_times < interval["dateuntil"]).reindex(df.index, fill_value=False)
            )
            if label_mask.any():
                df.loc[label_mask, "mov_type"] = interval["mov_type"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    filtered_path = filtered_path_for(output_path)
    df[df["mov_type"] != "NO_LABEL"].copy().to_parquet(filtered_path, index=False)
    return filtered_path


def load_manifest(path: Path) -> pd.DataFrame:
    """Load valid spectrogram rows from an extraction manifest."""
    df = pd.read_csv(path)
    required = {"Reference", "output_path", "status", "audit_status"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas requeridas en manifest: {sorted(missing)}")
    valid = df[(df["status"] == "ok") & (df["audit_status"] == "valid_spectrogram")]
    if valid.empty:
        raise ValueError("El manifest no contiene espectrogramas validos.")
    return valid.reset_index(drop=True)


def summarize_parquet(path: Path) -> dict[str, object]:
    """Return row and label counts for a parquet."""
    df = pd.read_parquet(path)
    counts = df["mov_type"].value_counts(dropna=False).to_dict()
    return {
        "path": str(path),
        "rows": len(df),
        "walking": int(counts.get("walking", 0)),
        "not_walking": int(counts.get("not_walking", 0)),
        "no_label": int(counts.get("NO_LABEL", 0)),
        "references": int(df["reference"].nunique()) if "reference" in df else 0,
    }


def markdown_table(df: pd.DataFrame) -> str:
    """Render a compact Markdown table."""
    if df.empty:
        return "_Sin filas._"
    rendered = df.astype(str)
    headers = list(rendered.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in rendered.iterrows():
        lines.append("| " + " | ".join(row[col] for col in headers) + " |")
    return "\n".join(lines)


def write_summary(path: Path, combined_output: Path, combined: pd.DataFrame, manifest: pd.DataFrame) -> None:
    """Write a summary markdown file."""
    counts = (
        combined.groupby(["reference", "mov_type"], observed=True)
        .size()
        .reset_index(name="rows")
        .sort_values(["reference", "mov_type"])
    )
    totals = (
        combined.groupby("mov_type", observed=True)
        .size()
        .reset_index(name="rows")
        .sort_values("mov_type")
    )
    lines = [
        "# Auto-Labeled Selected Spectrogram Blocks",
        "",
        f"- Combined output: `{combined_output}`",
        f"- Manifest rows used: {len(manifest)}",
        f"- Combined rows: {len(combined)}",
        f"- Patients: {combined['reference'].nunique()}",
        "",
        "## Totals",
        "",
        markdown_table(totals),
        "",
        "## By Patient",
        "",
        markdown_table(counts),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Label and combine extracted spectrogram blocks."""
    args = build_parser().parse_args()
    manifest_path = Path(args.manifest)
    ground_truth_path = Path(args.ground_truth)
    output_dir = Path(args.output_dir)
    combined_output = Path(args.combined_output)
    summary_path = Path(args.summary)

    output_dir.mkdir(parents=True, exist_ok=True)
    combined_output.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(manifest_path)
    ground_truth = load_ground_truth(ground_truth_path)
    filtered_paths: list[Path] = []
    rows: list[dict[str, object]] = []
    for _, row in manifest.iterrows():
        input_path = Path(str(row["output_path"]))
        output_path = labeled_path_for(input_path, output_dir)
        filtered_path = filtered_path_for(output_path)
        if not args.resume_existing or not filtered_path.exists():
            print(f">>> Labeling {input_path}")
            filtered_path = label_spectrogram(input_path, ground_truth, output_path)
        filtered_paths.append(filtered_path)
        summary = summarize_parquet(output_path)
        rows.append(
            {
                "Reference": row["Reference"],
                "input_path": str(input_path),
                "output_path": str(output_path),
                **summary,
            }
        )

    combined = pd.concat(
        [pd.read_parquet(path) for path in filtered_paths],
        ignore_index=True,
    )
    combined.to_parquet(combined_output, index=False)
    write_summary(summary_path, combined_output, combined, manifest)

    label_summary = pd.DataFrame(rows)
    label_manifest_path = output_dir / "label_manifest.csv"
    label_summary.to_csv(label_manifest_path, index=False)

    print(f"Manifest: {manifest_path}")
    print(f"Ground truth: {ground_truth_path}")
    print(f"Labeled blocks: {len(rows)}")
    print(f"Combined output: {combined_output}")
    print(f"Combined rows: {len(combined)}")
    print(combined["mov_type"].value_counts(dropna=False).to_string())
    print(f"Label manifest: {label_manifest_path}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
