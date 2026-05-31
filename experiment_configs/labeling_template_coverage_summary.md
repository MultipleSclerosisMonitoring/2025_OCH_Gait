# Labeling Template Coverage Scan

## Goal

Locate real data-bearing blocks inside the broad patient candidate windows before extracting raw data or generating spectrograms.

## Inputs

- Full labeling template: `experiment_configs/labeling_templates/all_patients_labeling_template.csv`
- Config: `experiment_configs/config_window_1s.yaml`

## Outputs

- Full scan: `experiment_configs/all_labeling_template_coverage_scan.csv`
- Selected useful blocks: `experiment_configs/all_labeling_template_selected_blocks.csv`
- Round 1 scan: `experiment_configs/round1_labeling_template_coverage_scan.csv`
- Round 1 selected blocks: `experiment_configs/round1_labeling_template_selected_blocks.csv`

## Scan Result

The full scan checked 245 ten-minute blocks across 12 candidate patients.

| Status | Blocks |
| --- | ---: |
| `valid_both_feet` | 52 |
| `no_records` | 193 |

The selected CSV keeps up to five valid two-foot blocks per patient.

## Selected Blocks By Patient

| Reference | Blocks | First local block | Last local block | Minimum records per foot | Total records |
| --- | ---: | --- | --- | ---: | ---: |
| `54217882M-109` | 5 | `2025-03-19 12:00:00` | `2025-03-19 12:50:00` | 99888 | 1606086 |
| `77370299R-115` | 5 | `2024-11-04 07:50:00` | `2024-11-04 08:40:00` | 87396 | 1572336 |
| `ACL1998-96` | 5 | `2025-07-16 09:00:00` | `2025-07-16 09:50:00` | 63408 | 1381764 |
| `AGCHUG064-10` | 5 | `2026-05-05 10:30:00` | `2026-05-05 11:20:00` | 57324 | 1529598 |
| `X8439657Z-23` | 5 | `2025-03-21 20:10:00` | `2025-03-22 12:30:00` | 49500 | 1230630 |
| `AMGHUG014-3` | 5 | `2026-05-04 00:00:00` | `2026-05-04 08:00:00` | 9780 | 1349388 |
| `JOM250427-105` | 5 | `2025-04-27 08:10:00` | `2025-04-27 09:00:00` | 67614 | 1346700 |
| `VCLHUG026-16` | 5 | `2026-02-10 09:50:00` | `2026-02-10 10:40:00` | 127530 | 2430186 |
| `VLGHUG049-29` | 5 | `2026-04-14 11:20:00` | `2026-04-14 12:10:00` | 48096 | 2242176 |
| `AEMDHUG060-70` | 3 | `2026-04-28 12:40:00` | `2026-04-28 13:10:00` | 51954 | 718788 |
| `JOM250429-103` | 3 | `2025-04-29 19:30:00` | `2025-04-29 20:00:00` | 124932 | 895572 |
| `LFP1994-120` | 1 | `2025-08-01 16:30:00` | `2025-08-01 16:40:00` | 91458 | 184014 |

## Next Step

Use `all_labeling_template_selected_blocks.csv` as the short queue for Grafana/manual labeling. These blocks have real two-foot data, so labeling effort is not wasted on empty windows.
