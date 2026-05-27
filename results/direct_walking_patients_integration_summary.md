# Direct walking patients integration

This step added direct InfluxDB extractions with walking segments from three new patients and rebuilt the ML dataset.

## Patients integrated

- `TABUENCA01-45`
  - `2024-04-25 16:14:50` to `2024-04-25 16:25:44` local
  - `2024-04-25 16:38:56` to `2024-04-25 16:49:44` local
- `330034-32`
  - `2025-02-25 11:28:03` to `2025-02-25 11:32:31` local
- `663495-44`
  - `2025-03-22 18:02:12` to `2025-03-22 18:04:27` local

`05447093A-110` was labeled from the direct extract too, but the block used here only produced `not_walking`, so it was not added to the walking-enriched merge.

## Rebuilt dataset

- long combined dataset: `salidas_test/auto_extracts/main_combined_labeled_dataset_with_manual_newpatients_plus_direct_walking.parquet`
- wide dataset: `salidas_test/auto_extracts/main_combined_labeled_dataset_with_manual_newpatients_plus_direct_walking_wide.parquet`
- binary ML dataset: `salidas_test/auto_extracts/main_binary_window_features_with_manual_newpatients_plus_direct_walking.parquet`

## Dataset size

- total rows: `12114`
- `not_walking`: `6828`
- `walking`: `5286`
- feature columns: `72`

## CV=3 comparison

- Random Forest: `f1_walking = 0.7100`
- XGBoost: `f1_walking = 0.7750`
- CatBoost: `f1_walking = 0.7744`

## Final RF training

- accuracy: `0.7649`
- `f1_walking`: `0.7300`
- `recall_walking`: `0.7283`

The direct Influx path remains the correct extraction route. This step confirms that the new patients can be incorporated without Grafana panel exports and that they shift the dataset toward a richer mix of walking segments.
