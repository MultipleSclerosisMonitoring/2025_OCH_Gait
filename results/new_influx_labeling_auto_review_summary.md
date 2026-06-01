# Revision automatica del lote de etiquetado Influx

- Seleccion revisada: `experiment_configs/new_influx_labeling_suggestions_selected.csv`
- Decisiones: `results/new_influx_labeling_auto_review_decisions.csv`
- Plantilla confirmada: `experiment_configs/new_influx_labeling_suggestions_selected_confirmed_auto.csv`
- Ground truth UTC confirmado: `experiment_configs/new_influx_labeling_ground_truth_confirmed_auto_utc.csv`
- Segmentos revisados: 30
- Segmentos confirmados automaticamente: 30
- Segmentos pendientes de revision manual: 0

## Criterio automatico

- `walking`: `feet_min >= 2`, `acc_std_mean >= 0.05` y `gyro_std_mean >= 10.0`.
- `not_walking`: `feet_min >= 2`, `acc_std_mean <= 0.05` y `gyro_std_mean <= 5.0`.

## Confirmados por referencia

| Reference | mov_type | segments | seconds |
| --- | --- | --- | --- |
| AAMALMHUG057-66 | not_walking | 3 | 113.0 |
| AAMALMHUG057-66 | walking | 3 | 344.0 |
| CHIHUG033-15 | not_walking | 3 | 195.0 |
| CHIHUG033-15 | walking | 3 | 69.0 |
| IECHUG029-9 | not_walking | 3 | 253.0 |
| IECHUG029-9 | walking | 3 | 112.0 |
| LFCMHUG070-78 | not_walking | 3 | 58.0 |
| LFCMHUG070-78 | walking | 3 | 151.0 |
| MGM-202406-79 | not_walking | 3 | 546.0 |
| MGM-202406-79 | walking | 3 | 259.0 |
