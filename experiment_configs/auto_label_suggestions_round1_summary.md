# Auto Label Suggestions

These rows are review suggestions, not final ground truth.

- Output CSV: `experiment_configs/auto_label_suggestions_round1.csv`
- Raw files processed: 5
- Suggestion rows: 48

## Counts

| Reference | suggested_mov_type | segments | seconds |
| --- | --- | --- | --- |
| 54217882M-109 | not_walking | 7 | 60.0 |
| 54217882M-109 | walking | 7 | 55.0 |
| 77370299R-115 | not_walking | 1 | 5.0 |
| 77370299R-115 | walking | 1 | 27.0 |
| ACL1998-96 | not_walking | 8 | 82.0 |
| ACL1998-96 | walking | 5 | 51.0 |
| AEMDHUG060-70 | not_walking | 9 | 159.0 |
| AEMDHUG060-70 | walking | 7 | 82.0 |
| AGCHUG064-10 | not_walking | 1 | 5.0 |
| AGCHUG064-10 | walking | 2 | 25.0 |

## Files

| Reference | review_block | raw_rows | windows | segments | status |
| --- | --- | --- | --- | --- | --- |
| 54217882M-109 | 54217882M_109_block0001_2025_03_19_120000_2025_03_19_121000 | 33389 | 347 | 14 | ok |
| 77370299R-115 | 77370299R_115_block0006_2024_11_04_075000_2024_11_04_080000 | 29261 | 300 | 2 | ok |
| ACL1998-96 | ACL1998_96_block0007_2025_07_16_090000_2025_07_16_091000 | 21610 | 256 | 13 | ok |
| AEMDHUG060-70 | AEMDHUG060_70_block0005_2026_04_28_124000_2026_04_28_125000 | 43151 | 441 | 16 | ok |
| AGCHUG064-10 | AGCHUG064_10_block0004_2026_05_05_103000_2026_05_05_104000 | 19255 | 199 | 3 | ok |

## Review Rule

`suggested_mov_type` is inferred from robust per-block motion energy. `mov_type` is intentionally empty so the import script does not accept these rows until a human reviewer copies an accepted value into `mov_type`.
