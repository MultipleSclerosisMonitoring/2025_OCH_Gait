#!/usr/bin/env python3
"""Build fixed-length temporal sequences for transformer experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from gait_analysis.run_baseline_grouped_cv import add_temporal_groups


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Construye un dataset secuencial a partir de ventanas tabulares "
            "para entrenar modelos tipo transformer."
        )
    )
    p.add_argument(
        "-i",
        "--input",
        default="salidas_test/auto_extracts/main_binary_window_features.parquet",
        help="Parquet binario con columnas espectrales y target",
    )
    p.add_argument(
        "-o",
        "--output",
        default="salidas_test/auto_extracts/transformer_sequence_dataset_len9.npz",
        help="NPZ de salida con X, y y metadatos numericos",
    )
    p.add_argument(
        "--metadata-output",
        default="salidas_test/auto_extracts/transformer_sequence_dataset_len9_metadata.csv",
        help="CSV de metadatos por secuencia",
    )
    p.add_argument(
        "--summary-output",
        default="results/transformer_sequence_dataset_summary.json",
        help="JSON resumen del dataset secuencial",
    )
    p.add_argument(
        "--sequence-length",
        type=int,
        default=9,
        help="Numero impar de ventanas consecutivas por muestra",
    )
    p.add_argument(
        "--gap-seconds",
        type=float,
        default=5.0,
        help="Salto minimo para separar bloques temporales",
    )
    return p


def validate_sequence_length(sequence_length: int) -> None:
    """Ensure the sequence length is valid for central-window labeling."""
    if sequence_length < 3:
        raise ValueError("--sequence-length debe ser al menos 3")
    if sequence_length % 2 == 0:
        raise ValueError("--sequence-length debe ser impar para etiquetar el centro")


def get_sequence_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return numeric feature columns suitable for transformer sequences."""
    excluded = {
        "reference",
        "time_center",
        "mov_type",
        "target",
        "block_id",
        "group",
    }
    numeric_cols = df.select_dtypes(include=["number", "bool"]).columns
    return [c for c in numeric_cols if c not in excluded]


def build_sequences(
    df: pd.DataFrame,
    feature_cols: list[str],
    sequence_length: int,
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Build fixed-length sequences within each temporal block."""
    half = sequence_length // 2
    sequences: list[np.ndarray] = []
    labels: list[int] = []
    metadata_rows: list[dict] = []

    for group, block in df.groupby("group", sort=False):
        block = block.sort_values("time_center").reset_index(drop=True)
        if len(block) < sequence_length:
            continue

        features = block[feature_cols].to_numpy(dtype=np.float32)
        targets = block["target"].to_numpy(dtype=np.int64)

        for center_idx in range(half, len(block) - half):
            start_idx = center_idx - half
            stop_idx = center_idx + half + 1
            center = block.iloc[center_idx]
            sequences.append(features[start_idx:stop_idx])
            labels.append(int(targets[center_idx]))
            metadata_rows.append(
                {
                    "reference": center["reference"],
                    "group": group,
                    "center_time": center["time_center"],
                    "center_mov_type": center["mov_type"],
                    "target": int(targets[center_idx]),
                    "sequence_start_time": block.iloc[start_idx]["time_center"],
                    "sequence_end_time": block.iloc[stop_idx - 1]["time_center"],
                    "source_center_index": int(center.name),
                }
            )

    if not sequences:
        raise ValueError("No se han podido construir secuencias con esos parametros.")

    X = np.stack(sequences).astype(np.float32)
    y = np.asarray(labels, dtype=np.int64)
    metadata = pd.DataFrame(metadata_rows)
    return X, y, metadata


def build_summary(
    df: pd.DataFrame,
    X: np.ndarray,
    y: np.ndarray,
    metadata: pd.DataFrame,
    feature_cols: list[str],
    sequence_length: int,
    gap_seconds: float,
) -> dict:
    """Build a JSON-serializable summary."""
    group_counts = metadata["group"].value_counts().sort_index()
    reference_counts = metadata["reference"].value_counts().sort_index()
    class_counts = pd.Series(y).map({0: "not_walking", 1: "walking"}).value_counts()

    return {
        "input_rows": int(len(df)),
        "sequences": int(X.shape[0]),
        "sequence_length": int(sequence_length),
        "features_per_window": int(X.shape[2]),
        "tensor_shape": [int(v) for v in X.shape],
        "gap_seconds": float(gap_seconds),
        "feature_columns": feature_cols,
        "class_counts": {
            str(k): int(v) for k, v in class_counts.sort_index().to_dict().items()
        },
        "references": {
            str(k): int(v) for k, v in reference_counts.to_dict().items()
        },
        "groups": {
            str(k): int(v) for k, v in group_counts.to_dict().items()
        },
        "label_strategy": "central_window_target",
        "split_recommendation": (
            "Usar la columna group de metadata para validacion por bloques "
            "temporales y evitar fuga entre ventanas contiguas."
        ),
    }


def main() -> None:
    """Build and save the transformer sequence dataset."""
    args = build_parser().parse_args()
    validate_sequence_length(args.sequence_length)

    input_path = Path(args.input)
    output_path = Path(args.output)
    metadata_output = Path(args.metadata_output)
    summary_output = Path(args.summary_output)

    df = pd.read_parquet(input_path)
    if "target" not in df.columns:
        raise ValueError("El dataset de entrada debe contener la columna target.")

    df = add_temporal_groups(df, gap_seconds=args.gap_seconds)
    feature_cols = get_sequence_feature_columns(df)
    X, y, metadata = build_sequences(
        df=df,
        feature_cols=feature_cols,
        sequence_length=args.sequence_length,
    )
    metadata["center_time"] = pd.to_datetime(metadata["center_time"], utc=True)
    metadata["sequence_start_time"] = pd.to_datetime(
        metadata["sequence_start_time"],
        utc=True,
    )
    metadata["sequence_end_time"] = pd.to_datetime(
        metadata["sequence_end_time"],
        utc=True,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(
        output_path,
        X=X,
        y=y,
        feature_columns=np.asarray(feature_cols, dtype=object),
        groups=metadata["group"].astype(str).to_numpy(),
        references=metadata["reference"].astype(str).to_numpy(),
        center_time=metadata["center_time"].astype(str).to_numpy(),
        sequence_start_time=metadata["sequence_start_time"].astype(str).to_numpy(),
        sequence_end_time=metadata["sequence_end_time"].astype(str).to_numpy(),
    )
    metadata.to_csv(metadata_output, index=False)

    summary = build_summary(
        df=df,
        X=X,
        y=y,
        metadata=metadata,
        feature_cols=feature_cols,
        sequence_length=args.sequence_length,
        gap_seconds=args.gap_seconds,
    )
    summary_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Metadata: {metadata_output}")
    print(f"Summary: {summary_output}")
    print(f"X shape: {X.shape}")
    print(f"y shape: {y.shape}")
    print("Class counts:")
    print(pd.Series(y).map({0: "not_walking", 1: "walking"}).value_counts().to_string())
    print("Groups:")
    print(metadata["group"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
