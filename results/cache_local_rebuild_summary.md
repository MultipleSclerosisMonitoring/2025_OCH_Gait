# Cache-local reconstruction summary

Date: 2026-05-19

## What was rebuilt

The main dataset was successfully regenerated using only local cached parquet
files, without querying Influx:

- pipeline output directory: `salidas_test/auto_extracts_cached_rebuild`
- combined long dataset: `main_combined_labeled_dataset.parquet`
- final ML dataset: `main_binary_window_features.parquet`

## Inputs reused from cache

The rebuild reused these cached filtered parquets:

- `02548893X_118_20250228_094807_20250228_095007_window_1s_labeled_filtered.parquet`
- `04845288Q_121_20250301_113217_20250301_114040_window_1s_labeled_filtered.parquet`
- `47046344M_104_20241015_072858_20241015_073152_window_1s_labeled_filtered.parquet`
- `47046344M_104_20241015_073153_20241015_073530_window_1s_labeled_filtered.parquet`
- `47046344M_104_20241015_073718_20241015_074011_window_1s_labeled_filtered.parquet`
- `47046344M_104_20241015_074327_20241015_074648_window_1s_labeled_filtered.parquet`
- `47046344M_104_20241015_074757_20241015_074844_window_1s_labeled_filtered.parquet`

## Output size

- `1293` rows in the final binary dataset
- `3` references
- target counts:
  - `not_walking`: `766`
  - `walking`: `527`

## Interpretation

This confirms that the reconstruction failure was caused by the pipeline
trying to re-extract data that was already available on disk. The new
`--cache-dir` path in `run_main_dataset_pipeline.py` resolves that problem for
cached segments.

The hard-negative augmentation run is still blocked separately because the exact
raw intervals for the two strong `47046344M-104` negative runs are not cached
locally yet.
