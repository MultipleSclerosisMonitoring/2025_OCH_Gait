# Transformer calibrated retrain summary

Date: 2026-06-01

## Calibration split

The internal calibration split was built from whole references:

- `47046344M-104`
- `05447093A-110`
- `02548893X-118`

Split size:

- train rows: `15,469`
- calibration rows: `1,114`
- train class balance: `8,082 not_walking` / `7,387 walking`
- calibration class balance: `742 not_walking` / `372 walking`

## Re-trained model

Artifact:

- `models/final_transformer_sequence_model_new_influx_confirmed_calibrated.pt`

Training setup:

- class weighting: `balanced`
- label smoothing: `0.05`
- batch size: `128`
- epochs used: `9`

## Internal calibration metrics

Validation on the reserved calibration split:

- accuracy: `0.5664`
- precision walking: `0.3712`
- recall walking: `0.4301`
- F1 walking: `0.3985`
- false positives: `271`
- true positives: `160`

## External validation

On `all_valid` using the cached spectrograms:

- threshold `0.43`, `min_run_windows=8`
  - accuracy: `0.6103`
  - precision walking: `0.0130`
  - recall walking: `1.0000`
  - F1 walking: `0.0256`
  - false positives: `304`

Best external operating point found after recalibration:

- threshold `0.60`, `min_run_windows=3`
  - accuracy: `0.8218`
  - precision walking: `0.0213`
  - recall walking: `0.7500`
  - F1 walking: `0.0414`
  - false positives: `138`
  - true positives: `3`

Stitched version at the same point:

- accuracy: `0.8667`
- precision walking: `0.0283`
- recall walking: `0.7500`
- F1 walking: `0.0545`
- false positives: `103`

## Interpretation

The split is now clean and reproducible, and calibration materially reduces the false-positive burden on the external validation compared with the previous operating point. Precision is still low, so this is not a final model, but it is a better operating point than the previous `0.43 / 8` configuration.
