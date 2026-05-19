#!/usr/bin/env python3
"""Run spectrogram extraction in overlapping temporal chunks."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    p = argparse.ArgumentParser(
        description=(
            "Extrae espectrogramas en chunks temporales solapados para evitar "
            "cargar rangos largos completos en memoria."
        )
    )
    p.add_argument("-q", "--reference", required=True)
    p.add_argument("-f", "--from-time", required=True)
    p.add_argument("-u", "--until", required=True)
    p.add_argument(
        "--config",
        default="experiment_configs/config_window_1s.yaml",
        help="Configuracion YAML del extractor.",
    )
    p.add_argument("-o", "--output", required=True, help="Parquet final.")
    p.add_argument(
        "--chunk-minutes",
        type=float,
        default=10.0,
        help="Duracion del tramo central procesado por chunk.",
    )
    p.add_argument(
        "--overlap-seconds",
        type=float,
        default=5.0,
        help="Solape consultado a cada lado del chunk para conservar ventanas de borde.",
    )
    p.add_argument(
        "--keep-temp",
        action="store_true",
        help="Conserva parquets temporales para depuracion.",
    )
    p.add_argument(
        "--temp-dir",
        default=None,
        help="Directorio temporal opcional. Si no se indica se usa uno efimero.",
    )
    return p


def parse_dt(value: str) -> datetime:
    """Parse project datetime strings."""
    return datetime.strptime(value.strip().replace("T", " "), DATETIME_FORMAT)


def format_dt(value: datetime) -> str:
    """Format project datetime strings."""
    return value.strftime(DATETIME_FORMAT)


def iter_chunks(
    start: datetime,
    stop: datetime,
    *,
    chunk_minutes: float,
    overlap_seconds: float,
) -> list[dict[str, datetime]]:
    """Return central and query intervals for all chunks."""
    if stop <= start:
        raise ValueError("--until debe ser posterior a --from-time.")
    chunk_delta = timedelta(minutes=chunk_minutes)
    overlap = timedelta(seconds=overlap_seconds)
    if chunk_delta.total_seconds() <= 0:
        raise ValueError("--chunk-minutes debe ser positivo.")
    if overlap.total_seconds() < 0:
        raise ValueError("--overlap-seconds no puede ser negativo.")

    chunks = []
    core_start = start
    while core_start < stop:
        core_stop = min(core_start + chunk_delta, stop)
        query_start = max(start, core_start - overlap)
        query_stop = min(stop, core_stop + overlap)
        chunks.append(
            {
                "core_start": core_start,
                "core_stop": core_stop,
                "query_start": query_start,
                "query_stop": query_stop,
            }
        )
        core_start = core_stop
    return chunks


def run_one_chunk(
    *,
    reference: str,
    config: str,
    chunk: dict[str, datetime],
    output: Path,
) -> None:
    """Run the existing extractor for one query interval."""
    cmd = [
        sys.executable,
        "extract_influx_hdf5.py",
        "--mode",
        "spectrogram",
        "--config",
        config,
        "-q",
        reference,
        "-f",
        format_dt(chunk["query_start"]),
        "-u",
        format_dt(chunk["query_stop"]),
        "-o",
        str(output),
    ]
    print(">>>", " ".join(cmd))
    subprocess.run(cmd, check=True)


def filter_core_rows(
    chunk_path: Path,
    *,
    core_start: datetime,
    core_stop: datetime,
) -> pd.DataFrame:
    """Load a chunk parquet and keep only rows whose center belongs to its core."""
    df = pd.read_parquet(chunk_path)
    if df.empty:
        return df
    df["time_center"] = pd.to_datetime(df["time_center"], utc=True, format="mixed")
    core_start_ts = pd.Timestamp(core_start, tz="UTC")
    core_stop_ts = pd.Timestamp(core_stop, tz="UTC")
    core = df[df["time_center"].ge(core_start_ts) & df["time_center"].lt(core_stop_ts)]
    return core.copy()


def append_chunk(
    df: pd.DataFrame,
    *,
    output_path: Path,
    writer: pq.ParquetWriter | None,
) -> pq.ParquetWriter:
    """Append one filtered chunk and return an open writer."""
    if df.empty:
        if writer is None:
            raise ValueError("El primer chunk filtrado no puede estar vacio.")
        return writer
    table = pa.Table.from_pandas(df, preserve_index=False)
    if writer is None:
        writer = pq.ParquetWriter(output_path, table.schema)
    writer.write_table(table)
    return writer


def main() -> None:
    """Run chunked extraction and save a single parquet."""
    args = build_parser().parse_args()
    start = parse_dt(args.from_time)
    stop = parse_dt(args.until)
    chunks = iter_chunks(
        start,
        stop,
        chunk_minutes=args.chunk_minutes,
        overlap_seconds=args.overlap_seconds,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.unlink(missing_ok=True)

    if args.temp_dir:
        temp_context = None
        temp_root = Path(args.temp_dir)
    elif args.keep_temp:
        temp_context = None
        temp_root = Path("salidas_test/chunked_extraction_temp")
    else:
        temp_context = tempfile.TemporaryDirectory(prefix="gait_chunked_extract_")
        temp_root = Path(temp_context.name)
    temp_root.mkdir(parents=True, exist_ok=True)

    writer: pq.ParquetWriter | None = None
    total_rows = 0
    try:
        for idx, chunk in enumerate(chunks, start=1):
            chunk_path = temp_root / f"chunk_{idx:04d}.parquet"
            print(
                f"Chunk {idx}/{len(chunks)} core "
                f"{format_dt(chunk['core_start'])} -> {format_dt(chunk['core_stop'])}"
            )
            run_one_chunk(
                reference=args.reference,
                config=args.config,
                chunk=chunk,
                output=chunk_path,
            )
            core_rows = filter_core_rows(
                chunk_path,
                core_start=chunk["core_start"],
                core_stop=chunk["core_stop"],
            )
            if not core_rows.empty:
                writer = append_chunk(
                    core_rows,
                    output_path=output_path,
                    writer=writer,
                )
                total_rows += len(core_rows)
            if not args.keep_temp and args.temp_dir is not None:
                chunk_path.unlink(missing_ok=True)
    finally:
        if writer is not None:
            writer.close()
        if temp_context is not None:
            temp_context.cleanup()

    if total_rows == 0:
        output_path.unlink(missing_ok=True)
        raise ValueError("No se han generado filas en ningun chunk.")

    print()
    print(f"Output parquet: {output_path}")
    print(f"Chunks: {len(chunks)}")
    print(f"Rows: {total_rows}")


if __name__ == "__main__":
    main()
