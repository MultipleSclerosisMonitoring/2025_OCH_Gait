# External comparison on `sequence_evaluation_windows.csv`

This summary compares the sequence models on the same five external windows:

- `47046344M-104 | 2024-10-15 07:30:02 -> 07:30:16` (`walking`)
- `47046344M-104 | 2024-10-15 07:41:10 -> 07:43:24` (`not_walking`)
- `47046344M-104 | 2024-10-15 07:35:38 -> 07:37:09` (`not_walking`)
- `02548893X-118 | 2025-02-28 09:59:46 -> 10:02:23` (`not_walking`)
- `05447093A-110 | 2024-05-09 10:26:46 -> 10:34:00` (`not_walking`, review-only)

## Raw evaluation at threshold 0.5

| Model | Rows | Accuracy | Precision walking | Recall walking | F1 walking | TN | FP | FN | TP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Random Forest | 820 | 0.7915 | 0.0062 | 0.0833 | 0.0116 | 648 | 160 | 11 | 1 |
| XGBoost | 820 | 0.7829 | 0.0060 | 0.0833 | 0.0111 | 641 | 167 | 11 | 1 |
| CatBoost | 820 | 0.6951 | 0.0163 | 0.3333 | 0.0310 | 566 | 242 | 8 | 4 |

## Best F1 on threshold sweep

| Model | Best threshold | Rows | Accuracy | Precision walking | Recall walking | F1 walking | TN | FP | FN | TP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Random Forest | 0.35 | 820 | 0.7695 | 0.0216 | 0.3333 | 0.0406 | 627 | 181 | 8 | 4 |
| XGBoost | 0.30 | 820 | 0.7780 | 0.0170 | 0.2500 | 0.0319 | 635 | 173 | 9 | 3 |
| CatBoost | 0.35 | 820 | 0.4695 | 0.0247 | 0.9167 | 0.0481 | 374 | 434 | 1 | 11 |
| Transformer, external validation | 0.95 | 820 | 0.8962 | 0.0471 | 1.0000 | 0.0899 | 695 | 81 | 0 | 4 |

## Interpretation

- The transformer remains the strongest model on this external comparison by F1 walking and by false-positive rate.
- CatBoost recovers more positives, but it does so with too many false positives.
- RF and XGBoost are much more conservative and miss most walking positives.
- The transformer still is not a finished deployment model: its calibration and review-only intervals need to stay in the pipeline.

## Artifacts

- `results/sequence_evaluation_summary_rf_new_influx_confirmed.csv`
- `results/sequence_evaluation_summary_xgb_new_influx_confirmed.csv`
- `results/sequence_evaluation_summary_catboost_new_influx_confirmed.csv`
- `results/transformer_external_validation_summary_new_influx_confirmed_by_scope.csv`
- `results/sequence_threshold_sweep_rf_new_influx_confirmed.csv`
- `results/sequence_threshold_sweep_xgb_new_influx_confirmed.csv`
- `results/sequence_threshold_sweep_catboost_new_influx_confirmed.csv`
