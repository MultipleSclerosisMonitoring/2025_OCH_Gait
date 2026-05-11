#!/usr/bin/env python3
"""Train a small transformer classifier on temporal gait sequences."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import LeaveOneGroupOut
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


@dataclass
class TrainConfig:
    """Training configuration for reproducible summaries."""

    epochs: int
    batch_size: int
    learning_rate: float
    d_model: int
    nhead: int
    num_layers: int
    dim_feedforward: int
    dropout: float
    patience: int
    seed: int


class SequenceTransformerClassifier(nn.Module):
    """Small transformer encoder for central-window binary classification."""

    def __init__(
        self,
        input_dim: int,
        sequence_length: int,
        d_model: int,
        nhead: int,
        num_layers: int,
        dim_feedforward: int,
        dropout: float,
    ) -> None:
        super().__init__()
        self.input_projection = nn.Linear(input_dim, d_model)
        self.positional_embedding = nn.Parameter(
            torch.zeros(1, sequence_length, d_model)
        )
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=num_layers,
        )
        self.classifier = nn.Sequential(
            nn.LayerNorm(d_model),
            nn.Linear(d_model, 2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Return logits for a batch of sequences."""
        hidden = self.input_projection(x) + self.positional_embedding
        encoded = self.encoder(hidden)
        center = encoded[:, encoded.shape[1] // 2, :]
        return self.classifier(center)


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description="Entrena y evalua un transformer pequeño con CV por bloques."
    )
    p.add_argument(
        "-i",
        "--input",
        default="salidas_test/auto_extracts/transformer_sequence_dataset_len9.npz",
        help="NPZ secuencial generado para transformers",
    )
    p.add_argument(
        "--fold-output",
        default="results/transformer_sequence_cv_results.csv",
        help="CSV con metricas por fold",
    )
    p.add_argument(
        "--prediction-output",
        default="results/transformer_sequence_cv_predictions.csv",
        help="CSV con predicciones out-of-fold",
    )
    p.add_argument(
        "--summary-output",
        default="results/transformer_sequence_summary.json",
        help="JSON resumen de la evaluacion",
    )
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--learning-rate", type=float, default=1e-3)
    p.add_argument("--d-model", type=int, default=32)
    p.add_argument("--nhead", type=int, default=4)
    p.add_argument("--num-layers", type=int, default=1)
    p.add_argument("--dim-feedforward", type=int, default=64)
    p.add_argument("--dropout", type=float, default=0.15)
    p.add_argument("--patience", type=int, default=12)
    p.add_argument("--seed", type=int, default=42)
    return p


def set_seed(seed: int) -> None:
    """Set deterministic seeds for CPU training."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)


def load_sequence_dataset(path: Path) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Load X, y and metadata arrays from NPZ."""
    data = np.load(path, allow_pickle=True)
    X = data["X"].astype(np.float32)
    y = data["y"].astype(np.int64)
    metadata = pd.DataFrame(
        {
            "reference": data["references"].astype(str),
            "group": data["groups"].astype(str),
            "center_time": data["center_time"].astype(str),
        }
    )
    return X, y, metadata


def normalize_train_test(
    X_train: np.ndarray,
    X_test: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Standardize features using train statistics over samples and time."""
    mean = X_train.mean(axis=(0, 1), keepdims=True)
    std = X_train.std(axis=(0, 1), keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    return (X_train - mean) / std, (X_test - mean) / std


def make_loader(
    X: np.ndarray,
    y: np.ndarray,
    batch_size: int,
    shuffle: bool,
) -> DataLoader:
    """Build a DataLoader from numpy arrays."""
    dataset = TensorDataset(torch.as_tensor(X, dtype=torch.float32), torch.as_tensor(y))
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)


def class_weights(y_train: np.ndarray) -> torch.Tensor:
    """Return inverse-frequency class weights."""
    counts = np.bincount(y_train, minlength=2).astype(np.float32)
    weights = counts.sum() / np.maximum(counts, 1.0)
    weights = weights / weights.mean()
    return torch.as_tensor(weights, dtype=torch.float32)


def train_one_fold(
    X_train: np.ndarray,
    y_train: np.ndarray,
    config: TrainConfig,
) -> tuple[SequenceTransformerClassifier, float, int]:
    """Train one fold and return model, best loss and epochs used."""
    model = SequenceTransformerClassifier(
        input_dim=X_train.shape[2],
        sequence_length=X_train.shape[1],
        d_model=config.d_model,
        nhead=config.nhead,
        num_layers=config.num_layers,
        dim_feedforward=config.dim_feedforward,
        dropout=config.dropout,
    )
    criterion = nn.CrossEntropyLoss(weight=class_weights(y_train))
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=1e-3,
    )
    loader = make_loader(X_train, y_train, config.batch_size, shuffle=True)

    best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
    best_loss = float("inf")
    stale_epochs = 0
    epochs_used = 0

    for epoch in range(1, config.epochs + 1):
        model.train()
        losses = []
        for xb, yb in loader:
            optimizer.zero_grad()
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))

        epoch_loss = float(np.mean(losses))
        epochs_used = epoch
        if epoch_loss < best_loss - 1e-4:
            best_loss = epoch_loss
            stale_epochs = 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            stale_epochs += 1
            if stale_epochs >= config.patience:
                break

    model.load_state_dict(best_state)
    return model, best_loss, epochs_used


def predict(model: nn.Module, X: np.ndarray, batch_size: int) -> tuple[np.ndarray, np.ndarray]:
    """Predict classes and walking probabilities."""
    loader = make_loader(X, np.zeros(len(X), dtype=np.int64), batch_size, shuffle=False)
    probabilities = []
    predictions = []
    model.eval()
    with torch.no_grad():
        for xb, _ in loader:
            logits = model(xb)
            probs = torch.softmax(logits, dim=1)[:, 1]
            probabilities.append(probs.cpu().numpy())
            predictions.append(torch.argmax(logits, dim=1).cpu().numpy())
    return np.concatenate(predictions), np.concatenate(probabilities)


def score_predictions(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Compute binary classification metrics for walking."""
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision_walking": precision_score(y_true, y_pred, pos_label=1, zero_division=0),
        "recall_walking": recall_score(y_true, y_pred, pos_label=1, zero_division=0),
        "f1_walking": f1_score(y_true, y_pred, pos_label=1, zero_division=0),
    }


def main() -> None:
    """Run grouped transformer evaluation."""
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
    )
    set_seed(config.seed)

    X, y, metadata = load_sequence_dataset(Path(args.input))
    groups = metadata["group"]
    logo = LeaveOneGroupOut()
    fold_rows = []
    prediction_frames = []

    for fold, (train_idx, test_idx) in enumerate(logo.split(X, y, groups), start=1):
        X_train, X_test = normalize_train_test(X[train_idx], X[test_idx])
        y_train, y_test = y[train_idx], y[test_idx]
        model, train_loss, epochs_used = train_one_fold(X_train, y_train, config)
        y_pred, walking_probability = predict(model, X_test, config.batch_size)
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred, labels=[0, 1]).ravel()
        group_name = str(groups.iloc[test_idx].iloc[0])

        fold_rows.append(
            {
                "fold": fold,
                "group": group_name,
                "test_rows": int(len(test_idx)),
                "test_not_walking": int((y_test == 0).sum()),
                "test_walking": int((y_test == 1).sum()),
                "train_loss": train_loss,
                "epochs_used": epochs_used,
                **score_predictions(y_test, y_pred),
                "tn": int(tn),
                "fp": int(fp),
                "fn": int(fn),
                "tp": int(tp),
            }
        )

        predictions = metadata.iloc[test_idx].copy()
        predictions["fold"] = fold
        predictions["target"] = y_test
        predictions["prediction"] = y_pred.astype(int)
        predictions["prediction_label"] = np.where(y_pred == 1, "walking", "not_walking")
        predictions["walking_probability"] = walking_probability
        prediction_frames.append(predictions)

        print(
            f"Fold {fold:02d} {group_name}: "
            f"rows={len(test_idx)} f1={fold_rows[-1]['f1_walking']:.4f}"
        )

    results = pd.DataFrame(fold_rows)
    predictions = pd.concat(prediction_frames, ignore_index=True)
    y_true_all = predictions["target"].astype(int).to_numpy()
    y_pred_all = predictions["prediction"].astype(int).to_numpy()
    matrix = confusion_matrix(y_true_all, y_pred_all, labels=[0, 1])
    report = classification_report(
        y_true_all,
        y_pred_all,
        labels=[0, 1],
        target_names=["not_walking", "walking"],
        output_dict=True,
        zero_division=0,
    )
    summary = {
        "input": args.input,
        "evaluation": "leave_one_temporal_group_out",
        "rows": int(len(y)),
        "sequence_shape": [int(v) for v in X.shape],
        "groups": int(groups.nunique()),
        "class_counts": {
            "not_walking": int((y == 0).sum()),
            "walking": int((y == 1).sum()),
        },
        "config": asdict(config),
        "out_of_fold_metrics": {
            "accuracy": float(accuracy_score(y_true_all, y_pred_all)),
            "precision_walking": float(
                precision_score(y_true_all, y_pred_all, pos_label=1, zero_division=0)
            ),
            "recall_walking": float(
                recall_score(y_true_all, y_pred_all, pos_label=1, zero_division=0)
            ),
            "f1_walking": float(
                f1_score(y_true_all, y_pred_all, pos_label=1, zero_division=0)
            ),
        },
        "confusion_matrix": {
            "labels": ["not_walking", "walking"],
            "matrix": matrix.astype(int).tolist(),
        },
        "classification_report": report,
    }

    for path in [args.fold_output, args.prediction_output, args.summary_output]:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.fold_output, index=False)
    predictions.to_csv(args.prediction_output, index=False)
    Path(args.summary_output).write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(f"Fold output: {args.fold_output}")
    print(f"Prediction output: {args.prediction_output}")
    print(f"Summary output: {args.summary_output}")
    print("Out-of-fold metrics:")
    print(json.dumps(summary["out_of_fold_metrics"], indent=2))


if __name__ == "__main__":
    main()
