from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

import pandas as pd


def write_signal_csv(path: Path, signal_name: str, base_value: float) -> None:
    """Write a small single-signal CSV with second-precision timestamps."""
    rows = []
    seconds = [
        "2024-10-15 07:35:38",
        "2024-10-15 07:35:39",
        "2024-10-15 07:35:40",
    ]
    for sec_idx, sec in enumerate(seconds):
        for sample_idx in range(40):
            rows.append(
                {
                    "Time": sec,
                    signal_name: base_value
                    + sec_idx * 0.1
                    + sample_idx * 0.01,
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False)


class HardNegativeBlockPipelineTest(unittest.TestCase):
    """Regression coverage for the hard-negative reconstruction wrapper."""

    def test_roundtrip(self) -> None:
        """The hard-negative wrapper should rebuild the full chain from CSVs."""
        tmp_root = Path(self._get_tmp_root())
        csv_dir = tmp_root / "csv"
        csv_dir.mkdir(parents=True, exist_ok=True)

        csv_specs = [
            ("Pie Izquierdo-data-test-1.csv", "S0 C1-2640", 900.0),
            ("Pie Derecho-data-test-1.csv", "S0 C1-9A3F", 860.0),
            ("Pie Izquierdo-data-test-2.csv", "Ax C1-2640", 0.10),
            ("Pie Derecho-data-test-2.csv", "Ax C1-9A3F", -0.20),
            ("Pie Izquierdo-data-test-3.csv", "Gx C1-2640", -12.0),
            ("Pie Derecho-data-test-3.csv", "Gx C1-9A3F", -8.0),
            ("Pie Izquierdo-data-test-4.csv", "Mx C1-2640", -0.08),
            ("Pie Derecho-data-test-4.csv", "Mx C1-9A3F", 0.42),
        ]

        csv_paths: list[str] = []
        for filename, signal_name, base_value in csv_specs:
            path = csv_dir / filename
            write_signal_csv(path, signal_name, base_value)
            csv_paths.append(str(path))

        out_dir = tmp_root / "hardneg_out"
        cmd = [
            sys.executable,
            "-m",
            "gait_analysis.run_hard_negative_block_pipeline",
            "--reference",
            "47046344M-104",
            "--interval-start",
            "2024-10-15 07:35:38",
            "--interval-end",
            "2024-10-15 07:37:09",
            "--output-dir",
            str(out_dir),
            *csv_paths,
        ]
        subprocess.run(cmd, check=True)

        raw_parquet = next(out_dir.glob("raw_bundle/*_raw_long.parquet"))
        spec_parquet = next(out_dir.glob("spectrogram/*_hardneg_spectrogram.parquet"))
        wide_parquet = next(out_dir.glob("wide/*_hardneg_wide.parquet"))
        binary_parquet = next(out_dir.glob("binary/*_hardneg_binary.parquet"))

        self.assertTrue(raw_parquet.exists())
        self.assertTrue(spec_parquet.exists())
        self.assertTrue(wide_parquet.exists())
        self.assertTrue(binary_parquet.exists())

        binary = pd.read_parquet(binary_parquet)
        self.assertFalse(binary.empty)
        self.assertEqual(binary["reference"].nunique(), 1)
        self.assertEqual(set(binary["target"].unique()), {0})
        self.assertIn("time_center", binary.columns)
        self.assertTrue(binary["time_center"].astype(str).str.contains("2024-10-15").all())

    def _get_tmp_root(self) -> str:
        """Return a dedicated temporary directory under /private/tmp."""
        from tempfile import mkdtemp

        return mkdtemp(prefix="hardneg_pipeline_test_")


if __name__ == "__main__":
    unittest.main()
