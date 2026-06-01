# Auto Label Suggestions

These rows are review suggestions, not final ground truth.

- Output CSV: `experiment_configs/new_influx_labeling_suggestions.csv`
- Raw files processed: 12
- Suggestion rows: 209

## Counts

| Reference | suggested_mov_type | segments | seconds |
| --- | --- | --- | --- |
| AAMALMHUG057-66 | not_walking | 29 | 545.0 |
| AAMALMHUG057-66 | walking | 12 | 507.0 |
| CHIHUG033-15 | not_walking | 30 | 673.0 |
| CHIHUG033-15 | walking | 18 | 498.0 |
| IECHUG029-9 | not_walking | 26 | 691.0 |
| IECHUG029-9 | walking | 23 | 553.0 |
| LFCMHUG070-78 | not_walking | 10 | 138.0 |
| LFCMHUG070-78 | walking | 22 | 474.0 |
| MGM-202406-79 | not_walking | 27 | 1007.0 |
| MGM-202406-79 | walking | 12 | 364.0 |

## Files

| Reference | review_block | raw_rows | windows | segments | status |
| --- | --- | --- | --- | --- | --- |
| AAMALMHUG057-66 | AAMALMHUG057_66_block0001_2026_04_25_204904_2026_04_25_211904 | 175123 | 1800 | 34 | ok |
| AAMALMHUG057-66 | AAMALMHUG057_66_block0002_2026_04_25_210728_2026_04_25_213728 | 175066 | 1800 | 7 | ok |
| AMIR-48 | AMIR_48_block0001_2024_04_06_184818_2024_04_06_191818 | 11898 | 122 | 0 | no_segments_after_min_duration |
| AMIR-48 | AMIR_48_block0002_2025_12_12_181357_2025_12_12_184357 | 5634 | 47 | 0 | no_segments_after_min_duration |
| CHIHUG033-15 | CHIHUG033_15_block0001_2026_03_03_125854_2026_03_03_132854 | 358956 | 1712 | 30 | ok |
| CHIHUG033-15 | CHIHUG033_15_block0002_2026_03_04_180002_2026_03_04_183002 | 302052 | 1800 | 18 | ok |
| IECHUG029-9 | IECHUG029_9_block0001_2026_02_18_112011_2026_02_18_115011 | 324949 | 1800 | 36 | ok |
| IECHUG029-9 | IECHUG029_9_block0002_2026_02_20_094030_2026_02_20_101030 | 345449 | 1800 | 13 | ok |
| LFCMHUG070-78 | LFCMHUG070_78_block0001_2026_05_20_114734_2026_05_20_121734 | 79939 | 814 | 11 | ok |
| LFCMHUG070-78 | LFCMHUG070_78_block0002_2026_05_30_085855_2026_05_30_092855 | 178387 | 1800 | 21 | ok |
| MGM-202406-79 | MGM_202406_79_block0001_2024_06_16_130911_2024_06_16_133911 | 174403 | 1800 | 20 | ok |
| MGM-202406-79 | MGM_202406_79_block0002_2024_10_08_133918_2024_10_08_140918 | 174198 | 1800 | 19 | ok |

## Review Rule

`suggested_mov_type` is inferred from robust per-block motion energy. `mov_type` is intentionally empty so the import script does not accept these rows until a human reviewer copies an accepted value into `mov_type`.
