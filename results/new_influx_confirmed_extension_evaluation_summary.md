# Integracion del lote Influx confirmado

## Datos anadidos

- Referencias nuevas: 5.
- Segmentos seleccionados y confirmados automaticamente por senal raw: 30 / 30.
- Ventanas binarias nuevas: 2.039.
- Distribucion nueva: 1.134 `not_walking` y 905 `walking`.
- Dataset combinado tras filtro de transiciones: 22.887 filas y 24 referencias.

## Distribucion de la extension

| reference | mov_type | rows |
| --- | --- | --- |
| AAMALMHUG057-66 | not_walking | 107 |
| AAMALMHUG057-66 | walking | 338 |
| CHIHUG033-15 | not_walking | 188 |
| CHIHUG033-15 | walking | 63 |
| IECHUG029-9 | not_walking | 247 |
| IECHUG029-9 | walking | 106 |
| LFCMHUG070-78 | not_walking | 52 |
| LFCMHUG070-78 | walking | 145 |
| MGM-202406-79 | not_walking | 540 |
| MGM-202406-79 | walking | 253 |

## Evaluacion clasica ponderada

CV: `balanced_grouped`, ponderacion `patient_source`, metadato excluido `dataset_source`.

| model | accuracy_mean | f1_walking_mean | f1_macro_mean | recall_walking_mean |
| --- | --- | --- | --- | --- |
| random_forest | 0.7705 | 0.7266 | 0.7635 | 0.7409 |
| xgboost | 0.7642 | 0.7206 | 0.7575 | 0.7431 |
| catboost | 0.7677 | 0.7255 | 0.7612 | 0.7470 |

## Comparacion orientativa contra plus_054full

La comparacion es orientativa porque al anadir 5 referencias nuevas los folds se regeneran; no es el mismo fold plan fijo anterior.

| model | f1_walking_mean_prev | f1_walking_mean_new | f1_walking_mean_delta | f1_macro_mean_prev | f1_macro_mean_new | f1_macro_mean_delta |
| --- | --- | --- | --- | --- | --- | --- |
| random_forest | 0.6792 | 0.7266 | 0.0475 | 0.7197 | 0.7635 | 0.0438 |
| xgboost | 0.6733 | 0.7206 | 0.0473 | 0.7154 | 0.7575 | 0.0421 |
| catboost | 0.6787 | 0.7255 | 0.0468 | 0.7193 | 0.7612 | 0.0419 |

## Artefactos

- Ground truth confirmado: `experiment_configs/new_influx_labeling_ground_truth_confirmed_auto_utc.csv`
- Plantilla confirmada: `experiment_configs/new_influx_labeling_suggestions_selected_confirmed_auto.csv`
- Espectrogramas combinados: `salidas_test/new_influx_confirmed_spectrograms/new_influx_confirmed_labeled_spectrograms.parquet`
- Binario nuevo: `salidas_test/new_influx_confirmed_spectrograms/new_influx_confirmed_binary.parquet`
- Binario combinado sin transiciones: `salidas_test/new_influx_confirmed_spectrograms/main_binary_with_new_influx_confirmed_no_transition_5s.parquet`
- Metricas CV: `results/new_influx_confirmed_notrans_weighted_cv3_summary.csv`

## Lectura

Este lote si cumple el objetivo operativo: anade pacientes nuevos, mantiene ambas clases por paciente y mejora el balance global. La mejora de metricas sugiere que conviene preparar un segundo lote con el mismo criterio antes de reentrenar definitivamente el transformer.
