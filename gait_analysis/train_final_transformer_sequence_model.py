#!/usr/bin/env python3
"""Train and save a final transformer sequence model for inference."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from gait_analysis.train_transformer_sequence_classifier import (
    TrainConfig,
    load_sequence_dataset,
    normalize_train_test,
    predict,
    score_predictions,
    set_seed,
    train_one_fold,
)


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Entrena el transformer final sobre todo el dataset secuencial."
    )
    p.add_argument(
        "-i",
        "--input",
        default="salidas_test/auto_extracts/transformer_sequence_dataset_len9.npz",
        help="NPZ secuencial generado para transformers",
    )
    p.add_argument(
        "-o",
        "--output",
        default="models/final_transformer_sequence_model_unweighted.pt",
        help="Artefacto torch de salida",
    )
    p.add_argument(
        "--summary-output",
        default="results/final_transformer_sequence_model_unweighted_summary.json",
        help="JSON resumen del entrenamiento final",
    )
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--learning-rate", type=float, default=1e-3)
    p.add_argument("--d-model", type=int, default=16)
    p.add_argument("--nhead", type=int, default=4)
    p.add_argument("--num-layers", type=int, default=1)
    p.add_argument("--dim-feedforward", type=int, default=32)
    p.add_argument("--dropout", type=float, default=0.3)
    p.add_argument("--patience", type=int, default=12)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--label-smoothing", type=float, default=0.05)
    p.add_argument("--weight-decay", type=float, default=1e-3)
    p.add_argument(
        "--class-weight-mode",
        choices=["balanced", "none"],
        default="none",
    )
    p.add_argument("--pooling", choices=["center", "mean"], default="center")
    return p


def load_feature_columns(path: Path) -> list[str]:
    """Load feature column names stored inside the NPZ artifact."""
    data = np.load(path, allow_pickle=True)
    return [str(v) for v in data["feature_columns"].tolist()]


def main() -> None:
    """Train and persist the final transformer model."""
    args = build_parser().parse_args()
    config = TrainConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        d_model=args.d_model,
        nhead=args.nhead,
        num_layers=args.num_layers,
        dim_feedforward=args.dim_feedforward,
        dropout=args.dropout,
        patience=args.patience,
        seed=args.seed,
        class_weight_mode=args.class_weight_mode,
        pooling=args.pooling,
        validation_mode="none",
        label_smoothing=args.label_smoothing,
        weight_decay=args.weight_decay,
    )
    set_seed(config.seed)

    input_path = Path(args.input)
    X, y, metadata = load_sequence_dataset(input_path)
    feature_columns = load_feature_columns(input_path)
    mean = X.mean(axis=(0, 1), keepdims=True)
    std = X.std(axis=(0, 1), keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    X_train, _ = normalize_train_test(X, X)

    model, train_loss, epochs_used = train_one_fold(X_train, y, config)
    y_pred, walking_probability = predict(model, X_train, config.batch_size)
    metrics = score_predictions(y, y_pred)

    output = Path(args.output)
    summary_output = Path(args.summary_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)

    artifact = {
        "state_dict": model.state_dict(),
        "feature_columns": feature_columns,
        "sequence_length": int(X.shape[1]),
        "input_dim": int(X.shape[2]),
        "normalization_mean": mean.astype(np.float32),
        "normalization_std": std.astype(np.float32),
        "config": asdict(config),
        "class_labels": {0: "not_walking", 1: "walking"},
    }
    torch.save(artifact, output)

    summary = {
        "input": str(input_path),
        "output": str(output),
        "rows": int(len(y)),
        "sequence_shape": [int(v) for v in X.shape],
        "feature_columns": int(len(feature_columns)),
        "class_counts": {
            "not_walking": int((y == 0).sum()),
            "walking": int((y == 1).sum()),
        },
        "references": {
            str(k): int(v)
            for k, v in metadata["reference"].value_counts().sort_index().to_dict().items()
        },
        "train_loss": float(train_loss),
        "epochs_used": int(epochs_used),
        "train_metrics": {k: float(v) for k, v in metrics.items()},
        "train_probability_mean": float(pd.Series(walking_probability).mean()),
        "config": asdict(config),
        "note": (
            "Métricas calculadas sobre el conjunto completo de entrenamiento; "
            "usar solo como comprobación de ajuste, no como generalización."
        ),
    }
    summary_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Input: {input_path}")
    print(f"Output model: {output}")
    print(f"Summary: {summary_output}")
    print(f"Rows: {len(y)}")
    print(f"Epochs used: {epochs_used}")
    print(pd.Series(metrics).round(4).to_string())


if __name__ == "__main__":
    main()
