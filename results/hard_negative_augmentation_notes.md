# Hard-negative augmentation experiment

Date: 2026-05-16

## Goal

Reduce false positives by adding a difficult not-walking segment to the training
set and evaluating without training/test overlap.

## Data change

Added the local labeled not-walking block from `02548893X-118` to an
alternative training dataset:

- `salidas_test/auto_extracts/main_combined_labeled_dataset_v5_hardneg.parquet`
- `salidas_test/auto_extracts/main_binary_window_features_v5_hardneg.parquet`

The evaluation configuration excludes the same `02548893X-118` block:

- `experiment_configs/sequence_evaluation_windows_no_hardneg_train.csv`

This avoids evaluating on a segment used for training.

## Models tested

Two RF variants were trained:

- `models/final_random_forest_model_v5_hardneg.joblib`
  - Same RF settings as the final model, with `class_weight=balanced`.
- `models/final_random_forest_model_v5_hardneg_unweighted.joblib`
  - Same RF settings, but without class weighting.

## Main result

Compared with the baseline RF on the same no-overlap evaluation protocol:

- Baseline RF at threshold 0.5:
  - `fp=539`, `fn=0`, `tp=12`, `f1_walking=0.0426`
- Hard-negative RF with no class weighting, threshold 0.35 and min run 2:
  - `fp=348`, `fn=3`, `tp=9`, `f1_walking=0.0488`

This reduces false positives by 191 windows while keeping 9 of 12 walking
windows, but it still produces too many false positives for a robust final
system.

## Stitched sequence result

For the hard-negative unweighted RF with threshold 0.35 and min run 2:

- Same-patient stitched sequence:
  - `tn=20`, `fp=201`, `fn=3`, `tp=9`
- New-patient not-walking sequence:
  - `tn=285`, `fp=147`, `fn=0`, `tp=0`

The new-patient negative segment improves, but same-patient difficult negatives
remain a major limitation.

## Interpretation

Adding one difficult negative segment helps, but it is not enough. The model is
still learning a broad walking decision boundary from a small and low-diversity
dataset. The next useful step is to obtain more negative segments with movement
artifacts and, especially, walking segments from new patients. Without those
new walking patients, tightening the model only reduces false positives by
losing sensitivity.
