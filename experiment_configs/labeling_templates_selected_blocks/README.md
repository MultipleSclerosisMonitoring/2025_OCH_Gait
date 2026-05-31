# Selected Blocks Labeling Template

This template contains only blocks already verified as `valid_both_feet` in InfluxDB.

## How To Label

1. Open `review_from_local` to `review_until_local` in Grafana.
2. Fill `label_from_local` and `label_until_local` only for clear sub-intervals.
3. Set `mov_type` to `walking` or `not_walking`.
4. Use `label_quality` values such as `clear`, `transition`, `short` or `ambiguous`.
5. Leave unclear rows blank; do not force a label.

## Patients

| Reference | priority | blocks | first_review | last_review | total_records |
| --- | --- | --- | --- | --- | --- |
| 54217882M-109 | 1 | 5 | 2025-03-19 12:00:00 | 2025-03-19 12:50:00 | 1606086 |
| 77370299R-115 | 2 | 5 | 2024-11-04 07:50:00 | 2024-11-04 08:40:00 | 1572336 |
| ACL1998-96 | 3 | 5 | 2025-07-16 09:00:00 | 2025-07-16 09:50:00 | 1381764 |
| AEMDHUG060-70 | 5 | 3 | 2026-04-28 12:40:00 | 2026-04-28 13:10:00 | 718788 |
| AGCHUG064-10 | 6 | 5 | 2026-05-05 10:30:00 | 2026-05-05 11:20:00 | 1529598 |
| AMGHUG014-3 | 7 | 5 | 2026-05-04 00:00:00 | 2026-05-04 08:00:00 | 1349388 |
| X8439657Z-23 | 9 | 5 | 2025-03-21 20:10:00 | 2025-03-22 12:30:00 | 1230630 |
| JOM250427-105 | 10 | 5 | 2025-04-27 08:10:00 | 2025-04-27 09:00:00 | 1346700 |
| VCLHUG026-16 | 11 | 5 | 2026-02-10 09:50:00 | 2026-02-10 10:40:00 | 2430186 |
| VLGHUG049-29 | 12 | 5 | 2026-04-14 11:20:00 | 2026-04-14 12:10:00 | 2242176 |
| JOM250429-103 | 13 | 3 | 2025-04-29 19:30:00 | 2025-04-29 20:00:00 | 895572 |
| LFP1994-120 | 16 | 1 | 2025-08-01 16:30:00 | 2025-08-01 16:40:00 | 184014 |

## Import After Labeling

```bash
poetry run python gait_analysis/import_patient_labeling_template.py \
  -i experiment_configs/labeling_templates_selected_blocks/all_patients_labeling_template.csv \
  -o experiment_configs/manual_patient_ground_truth_utc.csv
```
