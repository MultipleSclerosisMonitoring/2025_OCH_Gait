#!/usr/bin/env python3
"""Split a transformer sequence dataset into train and calibration subsets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from gait_analysis.transformer_sequence_core import load_sequence_dataset


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Divide un dataset secuencial en entrenamiento y calibracion "
            "segun referencias completas."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        required=True,
        help="NPZ secuencial de entrada",
    )
    p.add_argument(
        "--validation-references",
        default="experiment_configs/transformer_calibration_references.csv",
        help="CSV con las referencias que se reservaran para calibracion",
    )
    p.add_argument(
        "--train-output",
        required=True,
        help="NPZ de salida para el conjunto de entrenamiento",
    )
    p.add_argument(
        "--validation-output",
        required=True,
        help="NPZ de salida para el conjunto de calibracion",
    )
    p.add_argument(
        "--summary-output",
        default="results/transformer_sequence_calibration_split_summary.json",
        help="JSON resumen del split",
    )
    return p


def save_subset(
    path: Path,
    X: np.ndarray,
    y: np.ndarray,
    metadata: pd.DataFrame,
    feature_columns: np.ndarray,
) -> None:
    """Save one subset to NPZ."""
    np.savez_compressed(
        path,
        X=X,
        y=y,
        feature_columns=feature_columns,
        groups=metadata["group"].astype(str).to_numpy(),
        references=metadata["reference"].astype(str).to_numpy(),
        center_time=metadata["center_time"].astype(str).to_numpy(),
        sequence_start_time=metadata["sequence_start_time"].astype(str).to_numpy(),
        sequence_end_time=metadata["sequence_end_time"].astype(str).to_numpy(),
    )


def subset_summary(name: str, X: np.ndarray, y: np.ndarray, metadata: pd.DataFrame) -> dict:
    """Build a JSON-serializable summary for one subset."""
    class_counts = pd.Series(y).map({0: "not_walking", 1: "walking"}).value_counts()
    return {
        "name": name,
        "rows": int(len(y)),
        "sequence_shape": [int(v) for v in X.shape],
        "class_counts": {
            str(k): int(v) for k, v in class_counts.sort_index().to_dict().items()
        },
        "references": {
            str(k): int(v)
            for k, v in metadata["reference"].value_counts().sort_index().to_dict().items()
        },
        "groups": int(metadata["group"].nunique()),
    }


def main() -> None:
    """Split the dataset into train and calibration subsets."""
    args = build_parser().parse_args()
    input_path = Path(args.input)
    train_output = Path(args.train_output)
    validation_output = Path(args.validation_output)
    summary_output = Path(args.summary_output)

    X, y, metadata = load_sequence_dataset(input_path)
    ref_table = pd.read_csv(args.validation_references)
    if "reference" not in ref_table.columns:
        raise ValueError("validation-references debe incluir una columna reference.")
    validation_refs = ref_table["reference"].astype(str).tolist()

    mask = metadata["reference"].astype(str).isin(validation_refs)
    if not mask.any():
        raise ValueError("Ninguna referencia de calibracion aparece en el dataset.")

    X_val = X[mask.to_numpy()]
    y_val = y[mask.to_numpy()]
    meta_val = metadata.loc[mask].reset_index(drop=True)
    X_train = X[~mask.to_numpy()]
    y_train = y[~mask.to_numpy()]
    meta_train = metadata.loc[~mask].reset_index(drop=True)

    train_output.parent.mkdir(parents=True, exist_ok=True)
    validation_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)

    source = np.load(input_path, allow_pickle=True)
    feature_columns = source["feature_columns"]
    save_subset(train_output, X_train, y_train, meta_train, feature_columns)
    save_subset(validation_output, X_val, y_val, meta_val, feature_columns)

    summary = {
        "input": str(input_path),
        "validation_references": validation_refs,
        "train": subset_summary("train", X_train, y_train, meta_train),
        "validation": subset_summary("validation", X_val, y_val, meta_val),
    }
    summary_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Input: {input_path}")
    print(f"Train output: {train_output}")
    print(f"Validation output: {validation_output}")
    print(f"Summary: {summary_output}")
    print(pd.Series({"train_rows": len(y_train), "validation_rows": len(y_val)}).to_string())


if __name__ == "__main__":
    main()
