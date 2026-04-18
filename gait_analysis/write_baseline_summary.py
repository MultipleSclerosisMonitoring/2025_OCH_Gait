#!/usr/bin/env python3
"""Write a compact baseline-results summary table."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def main() -> None:
    """Build and save a compact summary of baseline results."""
    rows = [
        {
            "model": "trivial_always_not_walking",
            "accuracy": 0.8409,
            "f1_walking": 0.0000,
            "recall_walking": 0.0000,
            "notes": "Predicts always not_walking",
        },
        {
            "model": "logreg_cv",
            "accuracy": 0.7850,
            "f1_walking": 0.4174,
            "recall_walking": 0.4762,
            "notes": "Main baseline",
        },
        {
            "model": "random_forest_cv",
            "accuracy": 0.8537,
            "f1_walking": 0.2333,
            "recall_walking": 0.1429,
            "notes": "Higher accuracy, worse walking detection",
        },
    ]

    df = pd.DataFrame(rows)

    output_csv = Path("salidas_test/baseline_results_summary_v2.csv")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)

    print(df.to_string(index=False))
    print()
    print(f"Saved: {output_csv}")


if __name__ == "__main__":
    main()
    