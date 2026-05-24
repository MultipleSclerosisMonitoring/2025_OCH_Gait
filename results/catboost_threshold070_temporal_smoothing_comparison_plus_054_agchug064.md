# CatBoost threshold 0.70 temporal smoothing comparison

Date: 2026-05-24

Baseline:

- `threshold = 0.70`
- no temporal smoothing

## Comparison

| min_run_windows | Accuracy | Precision walking | Recall walking | F1 walking | Specificity not_walking | False positive rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.6937 | 0.4989 | 0.3971 | 0.4422 | 0.8244 | 0.1756 |
| 2 | 0.7054 | 0.5276 | 0.3490 | 0.4201 | 0.8624 | 0.1376 |
| 3 | 0.7068 | 0.5389 | 0.2852 | 0.3730 | 0.8925 | 0.1075 |
| 4 | 0.6969 | 0.5099 | 0.2238 | 0.3110 | 0.9053 | 0.0947 |
| 5 | 0.6870 | 0.4672 | 0.1693 | 0.2485 | 0.9150 | 0.0850 |

## Interpretation

- Temporal smoothing does reduce false positives.
- The best low-FP compromise is `min_run_windows = 2`.
- However, it also reduces recall and does not improve F1 over the unsmoothed thresholded baseline.

## Operational conclusion

For the current model, temporal smoothing is useful only if the priority is to suppress false alarms.
If the priority is the best balanced classifier, the unsmoothed thresholded `CatBoost` at `0.70` remains the better point.
