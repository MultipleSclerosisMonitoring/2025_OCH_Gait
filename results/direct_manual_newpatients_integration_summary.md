# Direct manual new-patient integration

This step added three direct InfluxDB extractions to the ML pipeline and rebuilt the binary dataset:

## Direct extracts

- `AGCHUG064-10`  
  `2026-05-05 10:30:00` to `2026-05-05 12:00:00` local  
  labeled as `not_walking`
- `AEMDHUG060-70`  
  `2026-04-28 12:43:00` to `2026-04-28 12:58:00` local  
  labeled as `not_walking`
- `AEMDHUG060-70`  
  `2026-04-29 17:22:00` to `2026-04-29 17:29:30` local  
  labeled as `not_walking`
- `ACL1998-96`  
  `2025-07-16 10:15:00` to `2025-07-16 11:15:00` local  
  labeled as `walking`
- `ACL1998-96`  
  `2025-07-16 21:20:00` to `2025-07-17 00:00:00` local  
  labeled as `not_walking`

## Rebuilt dataset

- long combined dataset: `salidas_test/auto_extracts/main_combined_labeled_dataset_with_manual_newpatients.parquet`
- wide dataset: `salidas_test/auto_extracts/main_combined_labeled_dataset_with_manual_newpatients_wide.parquet`
- binary ML dataset: `salidas_test/auto_extracts/main_binary_window_features_with_manual_newpatients.parquet`

## Dataset size

- total rows: `10499`
- `not_walking`: `6374`
- `walking`: `4125`
- feature columns: `72`

## CV=3 comparison

- Random Forest: `f1_walking = 0.7043`
- XGBoost: `f1_walking = 0.7546`
- CatBoost: `f1_walking = 0.7624`

## Final RF training

- accuracy: `0.7822`
- `f1_walking`: `0.7407`
- `recall_walking`: `0.7918`

The direct Influx extraction path works. The limiting factor is not the pipeline anymore, but the availability of exact labeled intervals for additional patients.
