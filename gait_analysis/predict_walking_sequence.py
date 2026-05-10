#!/usr/bin/env python3
"""Predict walking/not-walking over a raw temporal sequence from InfluxDB."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import joblib
import pandas as pd


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Extrae una secuencia temporal, calcula ventanas espectrales y aplica "
            "el modelo final para predecir marcha/no marcha por time_center."
        )
    )
    p.add_argument(
        "-q",
        "--reference",
        required=True,
        help='Referencia/paciente, por ejemplo "47046344M-104"',
    )
    p.add_argument(
        "-f",
        "--from-time",
        required=True,
        help='Inicio del intervalo, por ejemplo "2024-10-15 07:47:57"',
    )
    p.add_argument(
        "-u",
        "--until",
        required=True,
        help='Fin del intervalo, por ejemplo "2024-10-15 07:48:44"',
    )
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Configuracion de espectrograma a usar para la ventana movil",
    )
    p.add_argument(
        "-m",
        "--model",
        default="models/final_random_forest_model.joblib",
        help="Modelo entrenado en formato joblib",
    )
    p.add_argument(
        "-o",
        "--output",
        help="CSV de salida con time_center, prediccion y probabilidad",
    )
    p.add_argument(
        "--workdir",
        default="salidas_test/sequence_predictions",
        help="Directorio para artefactos intermedios",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Umbral de probabilidad para clasificar walking",
    )
    p.add_argument(
        "--keep-intermediate",
        action="store_true",
        help="Conserva el parquet de espectrograma intermedio",
    )
    p.add_argument(
        "--spectrogram-input",
        help=(
            "Parquet de espectrograma ya extraido. Si se indica, se omite la "
            "consulta a InfluxDB y se aplica solo la fase de inferencia."
        ),
    )
    return p


def make_block_id(reference: str, from_time: str, until: str) -> str:
    """Return a filesystem-safe identifier for one prediction interval."""
    safe_ref = reference.replace("-", "_")
    safe_from = from_time.replace("-", "").replace(":", "").replace(" ", "_")
    safe_until = until.replace("-", "").replace(":", "").replace(" ", "_")
    return f"{safe_ref}_{safe_from}_{safe_until}"


def run_spectrogram_extraction(
    reference: str,
    from_time: str,
    until: str,
    config: Path,
    output: Path,
) -> None:
    """Run the existing extraction script in spectrogram mode."""
    cmd = [
        sys.executable,
        "extract_influx_hdf5.py",
        "--mode",
        "spectrogram",
        "--config",
        str(config),
        "-f",
        from_time,
        "-u",
        until,
        "-q",
        reference,
        "-o",
        str(output),
    ]
    print(">>>", " ".join(cmd))
    subprocess.run(cmd, check=True)


def build_wide_features(spectrogram_path: Path) -> pd.DataFrame:
    """Convert a long spectrogram parquet into one wide row per time center."""
    df = pd.read_parquet(spectrogram_path)
    p_cols = [c for c in df.columns if c.startswith("p_")]
    if not p_cols:
        raise ValueError("No se han encontrado columnas de potencia p_*.")

    wide = (
        df.set_index(["reference", "time_center", "foot", "signal"])[p_cols]
        .unstack(["foot", "signal"])
    )
    wide.columns = [f"{foot}_{signal}_{col}" for col, foot, signal in wide.columns]
    return wide.reset_index()


def predict_sequence(
    wide: pd.DataFrame,
    model_path: Path,
    threshold: float,
) -> pd.DataFrame:
    """Apply the persisted model to a wide spectrogram table."""
    artifact = joblib.load(model_path)
    model = artifact["model"]
    feature_names = artifact["feature_names"]
    inverse_target_map = artifact["inverse_target_map"]

    missing_features = [c for c in feature_names if c not in wide.columns]
    if missing_features:
        raise ValueError(
            "La secuencia no contiene todas las columnas esperadas por el modelo: "
            f"{missing_features}"
        )

    X = wide[feature_names].copy()
    if hasattr(model, "predict_proba"):
        walking_probability = model.predict_proba(X)[:, 1]
    else:
        raise ValueError("El modelo guardado no soporta predict_proba.")

    prediction = (walking_probability >= threshold).astype(int)
    output = wide[["reference", "time_center"]].copy()
    output["walking_probability"] = walking_probability
    output["prediction"] = prediction
    output["prediction_label"] = output["prediction"].map(inverse_target_map)
    output = output[
        [
            "reference",
            "time_center",
            "prediction",
            "prediction_label",
            "walking_probability",
        ]
    ]
    return output.sort_values("time_center").reset_index(drop=True)


def main() -> None:
    """Extract a sequence, apply the final model, and save predictions."""
    args = build_parser().parse_args()
    config_path = Path(args.config)
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
        else workdir / f"{block_id}_walking_predictions.csv"
    )

    if args.spectrogram_input:
        print(f"Using existing spectrogram: {spectrogram_path}")
    else:
        run_spectrogram_extraction(
            reference=args.reference,
            from_time=args.from_time,
            until=args.until,
            config=config_path,
            output=spectrogram_path,
        )
    wide = build_wide_features(spectrogram_path)
    predictions = predict_sequence(
        wide=wide,
        model_path=model_path,
        threshold=args.threshold,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(output_path, index=False)

    if not args.keep_intermediate and not args.spectrogram_input:
        spectrogram_path.unlink(missing_ok=True)

    print()
    print(f"Model: {model_path}")
    print(f"Output predictions: {output_path}")
    print(f"Rows: {len(predictions)}")
    print()
    print("Prediction counts:")
    print(predictions["prediction_label"].value_counts(dropna=False).to_string())
    print()
    print("First rows:")
    print(predictions.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
