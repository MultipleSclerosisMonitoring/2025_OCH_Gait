#!/usr/bin/env python3
"""Build multiple YAML configs for window-size experiments."""

from __future__ import annotations

from pathlib import Path

import yaml


BASE_CONFIG = Path(".config.yaml")
OUTPUT_DIR = Path("experiment_configs")
WINDOWS_S = [1.0, 3.0, 5.0, 10.0]


def main() -> None:
    """Create one YAML config file per window length."""
    with BASE_CONFIG.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for window_s in WINDOWS_S:
        cfg_copy = dict(cfg)
        cfg_copy["spectrogram"] = dict(cfg["spectrogram"])
        cfg_copy["spectrogram"]["window_s"] = float(window_s)

        out_path = OUTPUT_DIR / f"config_window_{int(window_s)}s.yaml"
        with out_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(cfg_copy, f, sort_keys=False, allow_unicode=True)

        print(f"Config creada: {out_path}")


if __name__ == "__main__":
    main(