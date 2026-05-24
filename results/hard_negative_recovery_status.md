# Hard negative recovery status

Date: 2026-05-19

## Objective

Confirm or recover the exact hard-negative intervals suggested by the false-
positive review before rebuilding the training dataset.

## Confirmed intervals

The following same-patient negative runs on `47046344M-104` are already
confirmed by prior sequence outputs:

- `2024-10-15 07:35:38` to `2024-10-15 07:37:09`
- `2024-10-15 07:41:10` to `2024-10-15 07:43:24`

Evidence:

- `salidas_test/sequence_predictions/47046344M_104_20241015_073538_20241015_073709_predictions.csv`
- `salidas_test/sequence_predictions/47046344M_104_20241015_074110_20241015_074324_predictions.csv`
- `results/sequence_evaluation_results_v5_hardneg_unweighted_no_train_overlap.csv`

These are the two strongest hard-negative candidates from the false-positive
review:

- `47046344M-104`, `07:41:10` to `07:43:24`
  - 132 valid windows
  - `72` false positives under the hard-negative RF evaluation
- `47046344M-104`, `07:35:38` to `07:37:09`
  - 89 valid windows
  - `59` false positives under the hard-negative RF evaluation

## What is already cached

The dataset cache already contains the later `02548893X-118` not-walking block:

- `salidas_test/auto_extracts/02548893X_118_20250228_094807_20250228_095007_window_1s.parquet`

So the `02548893X-118` short block is not the blocker.

## What is not cached

The exact hard-negative raw parquets for the two `47046344M-104` intervals are
not present in `salidas_test/auto_extracts/`.

## Current blocker

Rebuilding the augmented dataset with live Influx access failed because the
requested extraction for `02548893X-118` returned no rows in this environment,
despite the interval being present in cached outputs. The hard-negative windows
for `47046344M-104` are also not available as raw cached parquets.

## Practical conclusion

The hard-negative intervals are confirmed as real evaluation problems, but the
dataset rebuild cannot be closed from the current cache alone. The next step is
to recover the exact raw parquets for those two `47046344M-104` windows, or to
re-run the extraction with a working Influx connection and verified coverage.
