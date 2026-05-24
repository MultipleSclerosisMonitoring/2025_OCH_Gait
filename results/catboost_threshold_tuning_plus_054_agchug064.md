# CatBoost threshold tuning on leave-one-reference-out predictions

Date: 2026-05-24

Input:

- `results/ml_model_comparison_leave_reference_out_with_new_patients_plus_054_agchug064_predictions.csv`

Model:

- `catboost`

## Main sweep result

The best macro-F1 threshold is:

- `threshold = 0.70`
- `accuracy = 0.6937`
- `precision_walking = 0.4989`
- `recall_walking = 0.3971`
- `f1_walking = 0.4422`
- `f1_macro = 0.6156`
- `false_positive_rate = 0.1756`
- `false_negative_rate = 0.6029`

## Operational interpretation

- This is the best point if the priority is to cut false positives while keeping a usable classifier.
- It reduces the false-positive rate sharply compared with the default threshold.
- The trade-off is a clear drop in walking recall.

## Lower-threshold reference point

The lowest false-positive rate with `recall_walking >= 0.60` occurs at:

- `threshold = 0.44`
- `accuracy = 0.5353`
- `precision_walking = 0.3494`
- `recall_walking = 0.6035`
- `f1_walking = 0.4426`
- `f1_macro = 0.5221`
- `false_positive_rate = 0.4948`

This point preserves recall, but it does not improve the operating profile enough for the current sequence-like use.

## Conclusion

For the current project stage, `threshold = 0.70` is the most defensible operating point for CatBoost when the goal is to reduce false alarms on unseen patients.
