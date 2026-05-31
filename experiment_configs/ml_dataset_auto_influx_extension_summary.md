# ML Dataset Summary

- Input parquet: `salidas_test/data_extension_selected/main_binary_window_features_with_auto_influx_extension.parquet`
- Rows: 21424
- Patients: 19
- Feature columns: 72
- Metadata columns: dataset_source
- Metadata used as feature: False

## By Source

| dataset_source | mov_type | target | rows |
| --- | --- | --- | --- |
| auto_influx_heuristic | not_walking | 0 | 5521 |
| auto_influx_heuristic | walking | 1 | 3743 |
| previous_dataset | not_walking | 0 | 6828 |
| previous_dataset | walking | 1 | 5332 |

## By Patient

| reference | dataset_source | mov_type | rows |
| --- | --- | --- | --- |
| 02548893X-118 | previous_dataset | not_walking | 118 |
| 04845288Q-121 | previous_dataset | not_walking | 388 |
| 04845288Q-121 | previous_dataset | walking | 86 |
| 05447093A-110 | previous_dataset | walking | 46 |
| 330034-32 | previous_dataset | not_walking | 189 |
| 330034-32 | previous_dataset | walking | 41 |
| 47046344M-104 | previous_dataset | not_walking | 260 |
| 47046344M-104 | previous_dataset | walking | 441 |
| 54217882M-109 | auto_influx_heuristic | not_walking | 309 |
| 54217882M-109 | auto_influx_heuristic | walking | 372 |
| 663495-44 | previous_dataset | not_walking | 30 |
| 663495-44 | previous_dataset | walking | 67 |
| 77370299R-115 | auto_influx_heuristic | not_walking | 412 |
| 77370299R-115 | auto_influx_heuristic | walking | 399 |
| ACL1998-96 | auto_influx_heuristic | not_walking | 733 |
| ACL1998-96 | auto_influx_heuristic | walking | 431 |
| ACL1998-96 | previous_dataset | not_walking | 2740 |
| ACL1998-96 | previous_dataset | walking | 3598 |
| AEMDHUG060-70 | auto_influx_heuristic | not_walking | 408 |
| AEMDHUG060-70 | auto_influx_heuristic | walking | 139 |
| AEMDHUG060-70 | previous_dataset | not_walking | 1308 |
| AGCHUG064-10 | auto_influx_heuristic | not_walking | 666 |
| AGCHUG064-10 | auto_influx_heuristic | walking | 342 |
| AGCHUG064-10 | previous_dataset | not_walking | 1560 |
| AMGHUG014-3 | auto_influx_heuristic | not_walking | 478 |
| AMGHUG014-3 | auto_influx_heuristic | walking | 270 |
| JOM250427-105 | auto_influx_heuristic | not_walking | 430 |
| JOM250427-105 | auto_influx_heuristic | walking | 412 |
| JOM250429-103 | auto_influx_heuristic | not_walking | 275 |
| JOM250429-103 | auto_influx_heuristic | walking | 213 |
| LFP1994-120 | auto_influx_heuristic | walking | 61 |
| TABUENCA01-45 | previous_dataset | not_walking | 235 |
| TABUENCA01-45 | previous_dataset | walking | 1053 |
| VCLHUG026-16 | auto_influx_heuristic | not_walking | 806 |
| VCLHUG026-16 | auto_influx_heuristic | walking | 476 |
| VLGHUG049-29 | auto_influx_heuristic | not_walking | 609 |
| VLGHUG049-29 | auto_influx_heuristic | walking | 300 |
| X8439657Z-23 | auto_influx_heuristic | not_walking | 395 |
| X8439657Z-23 | auto_influx_heuristic | walking | 328 |
