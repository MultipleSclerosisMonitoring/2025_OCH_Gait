#!/usr/bin/env python3
"""Core utilities for the transformer sequence classifier."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch
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
    class_weight_mode: str
    pooling: str
    validation_mode: str
    label_smoothing: float
    weight_decay: float
    embargo_seconds: float


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
        pooling: str,
    ) -> None:
        super().__init__()
        self.pooling = pooling
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
        if self.pooling == "mean":
            pooled = encoded.mean(dim=1)
        else:
            pooled = encoded[:, encoded.shape[1] // 2, :]
        return self.classifier(pooled)


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
    if "sequence_start_time" in data.files and "sequence_end_time" in data.files:
        metadata["sequence_start_time"] = data["sequence_start_time"].astype(str)
        metadata["sequence_end_time"] = data["sequence_end_time"].astype(str)
    else:
        metadata["sequence_start_time"] = metadata["center_time"]
        metadata["sequence_end_time"] = metadata["center_time"]
    for col in ["center_time", "sequence_start_time", "sequence_end_time"]:
        metadata[col] = pd.to_datetime(metadata[col], utc=True, format="mixed")
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
    X_val: np.ndarray | None = None,
    y_val: np.ndarray | None = None,
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
        pooling=config.pooling,
    )
    weight = class_weights(y_train) if config.class_weight_mode == "balanced" else None
    criterion = nn.CrossEntropyLoss(
        weight=weight,
        label_smoothing=config.label_smoothing,
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    loader = make_loader(X_train, y_train, config.batch_size, shuffle=True)
    val_loader = (
        make_loader(X_val, y_val, config.batch_size, shuffle=False)
        if X_val is not None and y_val is not None and len(y_val) > 0
        else None
    )

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

        train_loss = float(np.mean(losses))
        if val_loader is not None:
            model.eval()
            val_losses = []
            with torch.no_grad():
                for xb, yb in val_loader:
                    val_losses.append(float(criterion(model(xb), yb).detach().cpu()))
            epoch_loss = float(np.mean(val_losses))
        else:
            epoch_loss = train_loss
        if val_loader is not None and len(y_val) > 0:
            print(
                f"Epoch {epoch:03d}/{config.epochs}: "
                f"train_loss={train_loss:.4f} val_loss={epoch_loss:.4f}",
                flush=True,
            )
        else:
            print(
                f"Epoch {epoch:03d}/{config.epochs}: "
                f"train_loss={train_loss:.4f}",
                flush=True,
            )
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


def predict(
    model: nn.Module,
    X: np.ndarray,
    batch_size: int,
) -> tuple[np.ndarray, np.ndarray]:
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
    y_true = np.asarray(y_true, dtype=np.int64)
    y_pred = np.asarray(y_pred, dtype=np.int64)
    accuracy = float((y_true == y_pred).mean())
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "accuracy": accuracy,
        "precision_walking": float(precision),
        "recall_walking": float(recall),
        "f1_walking": float(f1),
        "tn": float(tn),
        "fp": float(fp),
        "fn": float(fn),
        "tp": float(tp),
    }
