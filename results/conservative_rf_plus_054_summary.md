# Conservative RF tuning on diversified dataset

## Input

- `salidas_test/auto_extracts/main_binary_window_features_with_new_patients_plus_054.parquet`
- Leave-one-temporal-block-out with 15 s embargo

## Best conservative option with recall >= 0.60

- not_walking_weight: `2.0`
- threshold: `0.60`
- precision walking: `0.7857`
- recall walking: `0.6099`
- F1 walking: `0.6867`
- F1 macro: `0.7129`
- false positive rate: `0.1743`
- false negative rate: `0.3901`
- tp: `1052`
- tn: `1360`
- fp: `287`
- fn: `673`

## Reading

This setting reduces false positives from the temporal-block evaluation while keeping recall above 0.60. It is a better operating point for sequence-like use than the default 0.50 threshold, but it is still a trade-off: false positives drop, sensitivity also drops.

## Next step

Use the `not_walking_weight=2.0` and `threshold=0.60` setting as the conservative operating point, and decide whether to enrich training with the hardest remaining false-positive runs before touching architecture again.
