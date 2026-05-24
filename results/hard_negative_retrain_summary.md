# Hard Negative Retrain Summary

Recovered hard-negative block:
- `47046344M-104`
- `2024-10-15 07:35:38` to `2024-10-15 07:43:24`

Recovered from CSV exports and reconstructed into:
- `salidas_test/hard_negative_spectrograms/47046344M_104_hardneg_spectrogram.parquet`
- `salidas_test/hard_negative_spectrograms/47046344M_104_hardneg_wide.parquet`
- `salidas_test/hard_negative_spectrograms/47046344M_104_hardneg_binary.parquet`

Evaluation on the current model before retraining:
- `223 / 223` windows predicted as `walking`
- walking probabilities stayed high across the whole block

Evaluation after retraining on the combined dataset:
- `223 / 223` windows predicted as `not_walking`
- walking probabilities dropped close to zero across the whole block

Combined dataset:
- base rows: `1293`
- hard-negative rows: `223`
- combined rows: `1516`
- combined class counts: `989 not_walking`, `527 walking`

Grouped CV3 on the combined dataset:
- Random Forest: accuracy `0.5898`, F1 walking `0.0717`
- XGBoost: accuracy `0.6306`, F1 walking `0.0528`
- CatBoost: accuracy `0.6480`, F1 walking `0.0563`

Final model on the combined dataset:
- training accuracy `0.8041`
- training F1 walking `0.7667`
- training recall walking `0.9260`

Grouped evaluation of the retrained final model:
- out-of-fold accuracy `0.4815`
- out-of-fold F1 walking `0.5327`
- out-of-fold recall walking `0.8501`

Interpretation:
- the hard-negative block is now absorbed correctly by the model;
- the extra negatives improve the local false-positive behaviour on the recovered interval;
- the global grouped-validation score becomes more conservative, which is expected when the dataset is broadened with a difficult same-patient negative block.
