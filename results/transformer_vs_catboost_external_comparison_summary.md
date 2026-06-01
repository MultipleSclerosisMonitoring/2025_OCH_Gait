# Transformer vs CatBoost on external validation

External set:
- `experiment_configs/sequence_evaluation_windows.csv`
- valid windows with `coverage_status=valid_both_feet`

## Summary by scope

| Scope | Transformer F1 | CatBoost F1 | Transformer acc. | CatBoost acc. |
| --- | ---: | ---: | ---: | ---: |
| same_patient | 0.3478 | 0.1137 | 0.9579 | 0.5180 |
| new_patient | 0.0000 | 0.0000 | 0.9929 | 1.0000 |
| all_valid | 0.0899 | 0.0497 | 0.8962 | 0.4866 |

## Best temporal smoothing

| Scope | Transformer F1 | CatBoost F1 | Transformer acc. | CatBoost acc. |
| --- | ---: | ---: | ---: | ---: |
| same_patient | 0.3200 | 0.1644 | 0.9522 | 0.6856 |
| new_patient | 0.0000 | 0.0000 | 0.8302 | 0.8302 |
| all_valid | 0.0727 | 0.0731 | 0.8692 | 0.6598 |

## Reading

- The transformer is clearly better than CatBoost on `same_patient` and on the global `all_valid` scope.
- On `new_patient`, neither model recovers walking reliably under this evaluation set.
- Temporal smoothing helps the transformer a bit, but it does not solve the calibration problem.
- The original claim can now be stated more precisely: the transformer does improve over CatBoost, but the gain is modest and the model still needs more work on false positives and threshold calibration.
