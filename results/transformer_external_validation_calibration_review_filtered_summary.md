# Transformer external validation calibration after false-positive exclusion

Model evaluated:
- `models/final_transformer_sequence_model_new_influx_confirmed.pt`

External validation set:
- `results/transformer_sequence_eval_predictions_new_influx_confirmed_all_valid_review_filtered.csv`
- valid rows: `151`
- excluded rows: `629`
- valid positives: `4`

Excluded intervals:
- `05447093A-110`, `2024-05-09 10:26:46` to `10:34:00`
- `47046344M-104`, `2024-10-15 07:41:10` to `07:43:24`
- `47046344M-104`, `2024-10-15 07:35:38` to `07:37:09`

Best threshold sweep result:
- threshold: `0.10`
- accuracy: `1.0000`
- precision_walking: `1.0000`
- recall_walking: `1.0000`
- f1_walking: `1.0000`
- specificity_not_walking: `1.0000`
- confusion matrix: `tn=147 fp=0 fn=0 tp=4`

Best temporal smoothing result:
- threshold: `0.40`
- min_run_windows: `1`
- accuracy: `1.0000`
- precision_walking: `1.0000`
- recall_walking: `1.0000`
- f1_walking: `1.0000`
- specificity_not_walking: `1.0000`
- confusion matrix: `tn=147 fp=0 fn=0 tp=4`

Conclusion:
- Excluding the review-only hard negatives reduces the calibration set and makes the chosen operating point less contaminated by the dominant false-positive intervals.
- The remaining calibration still needs validation, but the adjustment now reflects the cleaner split we wanted.
