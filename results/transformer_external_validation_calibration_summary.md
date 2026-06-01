# Transformer external validation calibration

Model evaluated:
- `models/final_transformer_sequence_model_new_influx_confirmed.pt`

External validation set:
- `results/transformer_sequence_eval_predictions_new_influx_confirmed_final_all_valid.csv`
- valid rows: `780`
- valid positives: `4`

Best threshold sweep result:
- threshold: `0.95`
- accuracy: `0.8962`
- precision_walking: `0.0471`
- recall_walking: `1.0000`
- f1_walking: `0.0899`
- specificity_not_walking: `0.8956`
- confusion matrix: `tn=695 fp=81 fn=0 tp=4`

Best temporal smoothing result:
- threshold: `0.60`
- min_run_windows: `4`
- accuracy: `0.7513`
- precision_walking: `0.0202`
- recall_walking: `1.0000`
- f1_walking: `0.0396`
- specificity_not_walking: `0.7500`
- confusion matrix: `tn=582 fp=194 fn=0 tp=4`

Conclusion:
- Threshold recalibration helps a little, but the model still produces too many false positives.
- Temporal persistence at this scope does not rescue precision.
- Next step should be false-positive auditing by segment/reference, not more threshold tuning.
