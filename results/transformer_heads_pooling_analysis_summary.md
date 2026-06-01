# Transformer heads and pooling analysis

This note isolates small architectural changes on the transformer sequence model while keeping the calibration split fixed.

## Setup

- train split: `salidas_test/new_influx_confirmed_spectrograms/transformer_sequence_dataset_len9_new_influx_confirmed.npz`
- validation split: `salidas_test/new_influx_confirmed_spectrograms/transformer_sequence_dataset_len9_new_influx_confirmed_calibration.npz`
- fixed configuration:
  - `d_model=16`
  - `num_layers=1`
  - `dim_feedforward=32`
  - `dropout=0.3`
  - `batch_size=128`
  - `epochs=40`
  - `patience=8`
  - `class_weight_mode=balanced`
  - `label_smoothing=0.05`
  - `weight_decay=0.001`
  - `seed=42`

## Validation split results

| Variant | nhead | Pooling | Validation accuracy | Validation precision walking | Validation recall walking | Validation F1 walking | TN | FP | FN | TP |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Center | 2 | center | 0.6032 | 0.4074 | 0.4140 | 0.4107 | 518 | 224 | 218 | 154 |
| Center | 4 | center | 0.7801 | 0.6377 | 0.7903 | 0.7059 | 575 | 167 | 78 | 294 |
| Center | 8 | center | 0.8061 | 0.6902 | 0.7608 | 0.7238 | 615 | 127 | 89 | 283 |
| Mean | 4 | mean | 0.9057 | 0.8329 | 0.8978 | 0.8642 | 675 | 67 | 38 | 334 |

## External `all_valid` check

The `nhead=4`, `pooling=mean` variant was also evaluated on the external sequence windows with the same operating threshold used for the calibrated baseline:

- threshold `0.43`
- `min_run_windows=4`

Result:

- accuracy `0.6449`
- precision walking `0.0142`
- recall walking `1.0`
- F1 walking `0.0281`
- TN `499`
- FP `277`
- FN `0`
- TP `4`

Threshold sweep on the same predictions:

- best threshold `0.9`
- accuracy `0.8410`
- precision walking `0.03125`
- recall walking `1.0`
- F1 walking `0.0606`
- TN `652`
- FP `124`
- FN `0`
- TP `4`

## Takeaway

- Increasing `nhead` from 2 to 4 improves the model substantially.
- Going from 4 to 8 gives only a small extra gain.
- Switching pooling from `center` to `mean` helps more than increasing heads further.
- The external set still shows a calibration problem, but the `mean` pooling variant reduces false positives compared with the calibrated center-pooling baseline.

## Artifacts

- `results/final_transformer_sequence_model_heads_n2_summary.json`
- `results/final_transformer_sequence_model_heads_n4_summary.json`
- `results/final_transformer_sequence_model_heads_n8_summary.json`
- `results/final_transformer_sequence_model_heads_n4_mean_summary.json`
- `results/transformer_sequence_heads_n4_mean_summary.csv`
- `results/transformer_sequence_heads_n4_mean_stitched_summary.csv`
- `results/transformer_sequence_heads_n4_mean_threshold_sweep.csv`
