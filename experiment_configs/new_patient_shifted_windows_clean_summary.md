# Clean Shifted New-Patient Windows

Date: 2026-05-17

## Input

- `experiment_configs/new_patient_shifted_windows.csv`

This file contains candidate new-patient windows after applying the time offsets
detected in the Influx scan:

- `TABUENCA01-45`: `-120 min`
- `330034-32`: `-60 min`
- `663495-44`: `-60 min`

## Cleaning Rules

1. Timestamps were normalized to second precision for compatibility with the
   extraction scripts.
2. Windows with overlapping contradictory labels were detected per reference.
3. In a contradictory overlap, the shorter interval was dropped.
4. Very long negative intervals were kept for sequence evaluation but excluded
   from the main training dataset to avoid severe class imbalance.

## Output

- Clean windows:
  - `experiment_configs/new_patient_shifted_windows_clean.csv`
- Dropped windows:
  - `experiment_configs/new_patient_shifted_windows_dropped.csv`

## Result

- Input windows: 32
- Kept windows: 31
- Dropped windows: 1
- Remaining conflicting overlaps: 0

The dropped interval is:

- `TABUENCA01-45`, `2024-04-25 14:48:19` to `2024-04-25 14:48:37`,
  `not_walking`

It was removed because it overlaps a longer `walking` interval starting at the
same timestamp.

## Usable Data After Cleaning

Training/evaluation candidate windows:

- `330034-32`
  - walking: 41 s
  - not_walking: 197 s
- `663495-44`
  - walking: 69 s
  - not_walking: 30 s
- `TABUENCA01-45`
  - walking: 1074 s
  - not_walking: 218.95 s

Long negative evaluation-only window:

- `TABUENCA01-45`
  - not_walking: 1767 s

## Next Step

Extract spectrograms from `new_patient_shifted_windows_clean.csv` using the
corrected signal pipeline, then combine them with the current dataset and rerun
the ML/sequence evaluations.
