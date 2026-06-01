# Seleccion compacta de sugerencias de etiquetado Influx

- Entrada completa: `experiment_configs/new_influx_labeling_suggestions.csv`
- Salida compacta: `experiment_configs/new_influx_labeling_suggestions_selected.csv`
- Referencias: 5
- Segmentos seleccionados: 30

La columna `suggested_mov_type` contiene la sugerencia heuristica. `mov_type` se deja vacia para que ninguna fila entre al entrenamiento sin revision humana.

## Seleccion compacta

| Reference | suggested_mov_type | segments | seconds |
| --- | --- | --- | --- |
| AAMALMHUG057-66 | not_walking | 3 | 113.0 |
| AAMALMHUG057-66 | walking | 3 | 344.0 |
| CHIHUG033-15 | not_walking | 3 | 195.0 |
| CHIHUG033-15 | walking | 3 | 283.0 |
| IECHUG029-9 | not_walking | 3 | 253.0 |
| IECHUG029-9 | walking | 3 | 112.0 |
| LFCMHUG070-78 | not_walking | 3 | 58.0 |
| LFCMHUG070-78 | walking | 3 | 151.0 |
| MGM-202406-79 | not_walking | 3 | 546.0 |
| MGM-202406-79 | walking | 3 | 259.0 |

## Sugerencias disponibles antes de seleccionar

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

## Criterio

- `walking`: se priorizan segmentos largos con mayor energia de acelerometro/giroscopio.
- `not_walking`: se priorizan segmentos largos con menor energia media.
- Maximo 3 segmentos por referencia y clase para que la revision sea manejable.
