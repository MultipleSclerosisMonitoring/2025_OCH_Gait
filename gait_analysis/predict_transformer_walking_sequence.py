#!/usr/bin/env python3
"""Predict walking over a raw sequence with the final transformer model."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from gait_analysis.predict_walking_sequence import (
    build_wide_features,
    make_block_id,
    run_spectrogram_extraction,
)
from gait_analysis.train_transformer_sequence_classifier import (
    SequenceTransformerClassifier,
)


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Extrae una secuencia temporal, construye secuencias de ventanas "
            "y aplica el transformer final."
        )
    )
    p.add_argument("-q", "--reference", required=True)
    p.add_argument("-f", "--from-time", required=True)
    p.add_argument("-u", "--until", required=True)
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Configuracion de espectrograma",
    )
    p.add_argument(
        "-m",
        "--model",
        default="models/final_transformer_sequence_model_unweighted_nols.pt",
        help="Artefacto transformer guardado con torch.save",
    )
    p.add_argument("-o", "--output", help="CSV de salida")
    p.add_argument(
        "--workdir",
        default="salidas_test/transformer_sequence_predictions",
        help="Directorio para artefactos intermedios",
    )
    p.add_argument("--threshold", type=float, default=0.43)
    p.add_argument(
        "--spectrogram-input",
        help="Parquet de espectrograma ya extraido; evita consultar InfluxDB",
    )
    p.add_argument("--keep-intermediate", action="store_true")
    return p


def build_sequences_for_inference(
    wide: pd.DataFrame,
    feature_columns: list[str],
    sequence_length: int,
) -> tuple[np.ndarray, pd.DataFrame]:
    """Build fixed-length sequences and center metadata from wide features."""
    missing = [c for c in feature_columns if c not in wide.columns]
    if missing:
        raise ValueError(
            "La secuencia no contiene todas las columnas esperadas por el "
            f"transformer: {missing}"
        )

    ordered = wide.sort_values("time_center").reset_index(drop=True)
    if len(ordered) < sequence_length:
        raise ValueError(
            f"La secuencia tiene {len(ordered)} ventanas, menos que "
            f"sequence_length={sequence_length}."
        )

    half = sequence_length // 2
    features = ordered[feature_columns].to_numpy(dtype=np.float32)
    sequences = []
    center_rows = []
    for center_idx in range(half, len(ordered) - half):
        start_idx = center_idx - half
        stop_idx = center_idx + half + 1
        sequences.append(features[start_idx:stop_idx])
        center = ordered.iloc[center_idx]
        center_rows.append(
            {
                "reference": center["reference"],
                "time_center": center["time_center"],
                "sequence_start_time": ordered.iloc[start_idx]["time_center"],
                "sequence_end_time": ordered.iloc[stop_idx - 1]["time_center"],
            }
        )

    return np.stack(sequences).astype(np.float32), pd.DataFrame(center_rows)


def load_model(path: Path) -> tuple[SequenceTransformerClassifier, dict]:
    """Load transformer artifact and instantiate the model."""
    artifact = torch.load(path, map_location="cpu", weights_only=False)
    config = artifact["config"]
    model = SequenceTransformerClassifier(
        input_dim=int(artifact["input_dim"]),
        sequence_length=int(artifact["sequence_length"]),
        d_model=int(config["d_model"]),
        nhead=int(config["nhead"]),
        num_layers=int(config["num_layers"]),
        dim_feedforward=int(config["dim_feedforward"]),
        dropout=float(config["dropout"]),
        pooling=str(config["pooling"]),
    )
    model.load_state_dict(artifact["state_dict"])
    model.eval()
    return model, artifact


def predict_sequences(
    model: SequenceTransformerClassifier,
    artifact: dict,
    X: np.ndarray,
    threshold: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return binary predictions and walking probabilities."""
    mean = artifact["normalization_mean"]
    std = artifact["normalization_std"]
    X_norm = (X - mean) / std
    with torch.no_grad():
        logits = model(torch.as_tensor(X_norm, dtype=torch.float32))
        probabilities = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()
    predictions = (probabilities >= threshold).astype(int)
    return predictions, probabilities


def main() -> None:
    """Run transformer sequence inference."""
    args = build_parser().parse_args()
    model_path = Path(args.model)
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    block_id = make_block_id(args.reference, args.from_time, args.until)
    spectrogram_path = (
        Path(args.spectrogram_input)
        if args.spectrogram_input
        else workdir / f"{block_id}_spectrogram.parquet"
    )
    output_path = (
        Path(args.output)
        if args.output
        else workdir / f"{block_id}_transformer_predictions.csv"
    )

    if args.spectrogram_input:
        print(f"Using existing spectrogram: {spectrogram_path}")
    else:
        run_spectrogram_extraction(
            reference=args.reference,
            from_time=args.from_time,
            until=args.until,
            config=Path(args.config),
            output=spectrogram_path,
        )

    model, artifact = load_model(model_path)
    wide = build_wide_features(spectrogram_path)
    X, centers = build_sequences_for_inference(
        wide=wide,
        feature_columns=list(artifact["feature_columns"]),
        sequence_length=int(artifact["sequence_length"]),
    )
    predictions, probabilities = predict_sequences(
        model=model,
        artifact=artifact,
        X=X,
        threshold=args.threshold,
    )
    centers["walking_probability"] = probabilities
    centers["prediction"] = predictions
    centers["prediction_label"] = np.where(predictions == 1, "walking", "not_walking")
    centers = centers[
        [
            "reference",
            "time_center",
            "sequence_start_time",
            "sequence_end_time",
            "prediction",
            "prediction_label",
            "walking_probability",
        ]
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    centers.to_csv(output_path, index=False)
    if not args.keep_intermediate and not args.spectrogram_input:
        spectrogram_path.unlink(missing_ok=True)

    print(f"Model: {model_path}")
    print(f"Output predictions: {output_path}")
    print(f"Rows: {len(centers)}")
    print(centers["prediction_label"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
