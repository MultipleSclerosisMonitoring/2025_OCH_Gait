# Balanced Data Extension

## Inputs

- `experiment_configs/reproducible_direct_influx_ground_truth_utc.csv`

## Output

- Balanced ground truth: `experiment_configs/balanced_data_extension_ground_truth_utc.csv`
- Labeling candidates: `experiment_configs/balanced_data_extension_labeling_candidates.csv`

## Class Balance

| mov_type | rows | duration_s |
| --- | --- | --- |
| not_walking | 11 | 1240.00 |
| walking | 18 | 1234.00 |

## Reference Coverage

| Reference | mov_type | rows | duration_s |
| --- | --- | --- | --- |
| 05447093A-110 | not_walking | 4 | 473.00 |
| 05447093A-110 | walking | 2 | 50.00 |
| 330034-32 | not_walking | 3 | 197.00 |
| 330034-32 | walking | 1 | 41.00 |
| 663495-44 | not_walking | 1 | 30.00 |
| 663495-44 | walking | 3 | 69.00 |
| TABUENCA01-45 | not_walking | 3 | 540.00 |
| TABUENCA01-45 | walking | 12 | 1074.00 |

## Manual Labeling Queue

These references have two-foot Influx coverage but still need Grafana/manual labels before they can be used for supervised training.

| Reference | priority | shifted_datefrom | shifted_dateuntil | offset_minutes | right_records | left_records | total_records |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 54217882M-109 | 1 | 2025-03-19 11:00:00 | 2025-03-20 02:00:00 | -60 | 15095238 | 15078372 | 30173610 |
| 77370299R-115 | 2 | 2024-11-04 06:00:00 | 2024-11-04 21:30:00 | -60 | 12320892 | 12223146 | 24544038 |
| ACL1998-96 | 3 | 2025-07-16 06:00:00 | 2025-07-16 12:00:00 | -120 | 4227516 | 3927426 | 8154942 |
| AEMDHUG060-70 | 5 | 2026-04-28 10:00:00 | 2026-04-28 12:00:00 | -120 | 358464 | 360324 | 718788 |
| AGCHUG064-10 | 6 | 2026-05-05 08:00:00 | 2026-05-06 12:00:00 | -120 | 27237912 | 26709792 | 53947704 |
| AMGHUG014-3 | 7 | 2026-05-03 21:00:00 | 2026-05-04 19:00:00 | -120 | 7814538 | 8917890 | 16732428 |
| X8439657Z-23 | 9 | 2025-03-21 19:00:00 | 2025-03-23 11:30:00 | -60 | 6552786 | 6665844 | 13218630 |
| JOM250427-105 | 10 | 2025-04-27 06:00:00 | 2025-04-27 13:30:00 | -120 | 4499010 | 4897566 | 9396576 |
| VCLHUG026-16 | 11 | 2026-02-10 06:00:00 | 2026-02-11 09:00:00 | -60 | 22113732 | 13334370 | 35448102 |
| VLGHUG049-29 | 12 | 2026-04-14 09:00:00 | 2026-04-14 16:00:00 | -120 | 7654062 | 6804576 | 14458638 |
| JOM250429-103 | 13 | 2025-04-29 17:00:00 | 2025-04-29 18:30:00 | -120 | 446322 | 449250 | 895572 |
| LFP1994-120 | 16 | 2025-08-01 14:30:00 | 2025-08-01 14:50:00 | -120 | 91458 | 92556 | 184014 |
