# Final model error analysis

Date: 2026-05-24

## Dataset used

- `salidas_test/auto_extracts/main_binary_window_features_with_new_patients_plus_054_agchug064.parquet`
- Rows: `5642`
- References: `8`

## 3-fold stratified comparison

| Model | Accuracy mean | Accuracy sd | Precision walking mean | Recall walking mean | F1 walking mean | F1 walking sd |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Random Forest | 0.8823 | 0.0074 | 0.8706 | 0.7229 | 0.7898 | 0.0113 |
| XGBoost | 0.8970 | 0.0027 | 0.8354 | 0.8261 | 0.8307 | 0.0027 |
| CatBoost | 0.8993 | 0.0044 | 0.8408 | 0.8278 | 0.8342 | 0.0048 |

Interpretation:

- `CatBoost` remains the best classical model on the closed, diversified dataset.
- `XGBoost` is very close and slightly more stable in accuracy than RF.
- `Random Forest` improves with diversity, but stays below XGBoost/CatBoost.

## Leave-one-reference-out validation

| Model | Accuracy mean | Recall walking mean | F1 walking mean |
| --- | ---: | ---: | ---: |
| Random Forest | 0.6037 | 0.3675 | 0.3321 |
| XGBoost | 0.5588 | 0.4176 | 0.3353 |
| CatBoost | 0.5959 | 0.4152 | 0.3424 |

Interpretation:

- When the test patient is fully unseen, performance drops sharply.
- The main limitation is still cross-patient generalization, not in-sample capacity.

## CatBoost error analysis on leave-one-reference-out predictions

Global counts:

- False positives: `1630`
- False negatives: `756`
- False positive rate: `0.4161`
- False negative rate: `0.4383`

### Main false-positive patients

- `AGCHUG064-10`: `1053` FP windows, `0` FN windows
- `04845288Q-121`: `244` FP windows
- `05447093A-110`: `141` FP windows
- `TABUENCA01-45`: `82` FP windows
- `02548893X-118`: `79` FP windows

### Main false-negative patients

- `47046344M-104`: `434` FN windows, only `1` FP window
- `TABUENCA01-45`: `245` FN windows
- `05447093A-110`: `24` FN windows
- `04845288Q-121`: `23` FN windows
- `330034-32`: `20` FN windows

### Run-level pattern

- False positives are concentrated in long, sustained runs, not isolated windows.
- The longest FP run is in `04845288Q-121`:
  - `2025-03-01 11:36:15` to `11:37:57`
  - `103` windows
- Other large FP runs are in `02548893X-118` and `AGCHUG064-10`.
- False negatives are dominated by long missed walking blocks in `47046344M-104`.

## Practical conclusion

The current bottleneck is no longer model capacity on the closed dataset.
The main problem is domain shift across patients and the difficulty of holding up on fully unseen references.
CatBoost is the best classical baseline, but the error profile still shows sustained patient-specific failure modes.
