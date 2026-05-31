# Combined Auto Influx Extension

- Base dataset: `salidas_test/auto_extracts/main_combined_labeled_dataset_with_manual_newpatients_plus_direct_walking_plus_054walking.parquet`
- Auto extension: `salidas_test/data_extension_selected/auto_labeled_selected_blocks_spectrogram.parquet`
- Output dataset: `salidas_test/data_extension_selected/main_combined_labeled_dataset_with_auto_influx_extension.parquet`
- Base rows: 145920
- Extension rows: 111168
- Exact duplicate rows removed: 0
- Combined rows: 257088
- Combined patients: 19

## Totals By Source

| dataset_source | mov_type | rows |
| --- | --- | --- |
| auto_influx_heuristic | not_walking | 66252 |
| auto_influx_heuristic | walking | 44916 |
| previous_dataset | not_walking | 81936 |
| previous_dataset | walking | 63984 |

## Totals By Label

| mov_type | rows |
| --- | --- |
| not_walking | 148188 |
| walking | 108900 |

## Rows By Patient

| reference | dataset_source | mov_type | rows |
| --- | --- | --- | --- |
| 02548893X-118 | previous_dataset | not_walking | 1416 |
| 04845288Q-121 | previous_dataset | not_walking | 4656 |
| 04845288Q-121 | previous_dataset | walking | 1032 |
| 05447093A-110 | previous_dataset | walking | 552 |
| 330034-32 | previous_dataset | not_walking | 2268 |
| 330034-32 | previous_dataset | walking | 492 |
| 47046344M-104 | previous_dataset | not_walking | 3120 |
| 47046344M-104 | previous_dataset | walking | 5292 |
| 54217882M-109 | auto_influx_heuristic | not_walking | 3708 |
| 54217882M-109 | auto_influx_heuristic | walking | 4464 |
| 663495-44 | previous_dataset | not_walking | 360 |
| 663495-44 | previous_dataset | walking | 804 |
| 77370299R-115 | auto_influx_heuristic | not_walking | 4944 |
| 77370299R-115 | auto_influx_heuristic | walking | 4788 |
| ACL1998-96 | auto_influx_heuristic | not_walking | 8796 |
| ACL1998-96 | auto_influx_heuristic | walking | 5172 |
| ACL1998-96 | previous_dataset | not_walking | 32880 |
| ACL1998-96 | previous_dataset | walking | 43176 |
| AEMDHUG060-70 | auto_influx_heuristic | not_walking | 4896 |
| AEMDHUG060-70 | auto_influx_heuristic | walking | 1668 |
| AEMDHUG060-70 | previous_dataset | not_walking | 15696 |
| AGCHUG064-10 | auto_influx_heuristic | not_walking | 7992 |
| AGCHUG064-10 | auto_influx_heuristic | walking | 4104 |
| AGCHUG064-10 | previous_dataset | not_walking | 18720 |
| AMGHUG014-3 | auto_influx_heuristic | not_walking | 5736 |
| AMGHUG014-3 | auto_influx_heuristic | walking | 3240 |
| JOM250427-105 | auto_influx_heuristic | not_walking | 5160 |
| JOM250427-105 | auto_influx_heuristic | walking | 4944 |
| JOM250429-103 | auto_influx_heuristic | not_walking | 3300 |
| JOM250429-103 | auto_influx_heuristic | walking | 2556 |
| LFP1994-120 | auto_influx_heuristic | walking | 732 |
| TABUENCA01-45 | previous_dataset | not_walking | 2820 |
| TABUENCA01-45 | previous_dataset | walking | 12636 |
| VCLHUG026-16 | auto_influx_heuristic | not_walking | 9672 |
| VCLHUG026-16 | auto_influx_heuristic | walking | 5712 |
| VLGHUG049-29 | auto_influx_heuristic | not_walking | 7308 |
| VLGHUG049-29 | auto_influx_heuristic | walking | 3600 |
| X8439657Z-23 | auto_influx_heuristic | not_walking | 4740 |
| X8439657Z-23 | auto_influx_heuristic | walking | 3936 |
