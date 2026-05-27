# Direct Influx walking refresh

This iteration bypassed Grafana and extracted walking segments directly from InfluxDB for `05447093A-110`.

## Directly extracted walking intervals

- `2024-05-09 11:57:45` to `2024-05-09 11:58:01` local
- `2024-05-09 12:19:26` to `2024-05-09 12:20:00` local

## Rebuilt dataset

- long combined dataset: `salidas_test/auto_extracts/main_combined_labeled_dataset_with_manual_newpatients_plus_direct_walking_plus_054walking.parquet`
- wide dataset: `salidas_test/auto_extracts/main_combined_labeled_dataset_with_manual_newpatients_plus_direct_walking_plus_054walking_wide.parquet`
- binary ML dataset: `salidas_test/auto_extracts/main_binary_window_features_with_manual_newpatients_plus_direct_walking_plus_054walking.parquet`

## Dataset size

- total rows: `12160`
- `not_walking`: `6828`
- `walking`: `5332`
- feature columns: `72`

## CV=3 comparison

- Random Forest: `f1_walking = 0.7122`
- XGBoost: `f1_walking = 0.7757`
- CatBoost: `f1_walking = 0.7772`

## Final RF training

- accuracy: `0.7622`
- `f1_walking`: `0.7277`
- `recall_walking`: `0.7249`

Direct Influx extraction remains the stable path. The new walking intervals from `05447093A-110` are now incorporated without requiring Grafana panel exports.
