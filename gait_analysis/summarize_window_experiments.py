#!/usr/bin/env python3
"""Build a summary table for window-size spectrogram experiments."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


FILES = {
    1.0: Path("salidas_test/test_window_1s.parquet"),
    3.0: Path("salidas_test/test_window_3s.parquet"),
    5.0: Path("salidas_test/test_window_5s.parquet"),
    10.0: Path("salidas_test/test_window_10s.parquet"),
}

OUTPUT_CSV = Path("salidas_test/window_experiment_summary.csv")


def main() -> None:
    """Read experiment parquet files and build a summary CSV."""
    rows = []

    for window_s, path in FILES.items():
        if not path.exists():
            raise FileNotFoundError(f"No existe el fichero: {path}")

        df = pd.read_parquet(path)

        right_rows = int((df["foot"] == "Right").sum())
        left_rows = int((df["foot"] == "Left").sum())
        total_rows = int(len(df))

        centers = int(df["time_center"].nunique())

        rows.append(
            {
                "window_s": window_s,
                "centers": centers,
                "right_rows": right_rows,
                "left_rows": left_rows,
                "total_rows": total_rows,
            }
        )

    out_df = pd.DataFrame(rows).sort_values("window_s").reset_index(drop=True)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUTPUT_CSV, index=False)

    print(out_df.to_string(index=False))
    print()
    print(f"Resumen guardado en: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()