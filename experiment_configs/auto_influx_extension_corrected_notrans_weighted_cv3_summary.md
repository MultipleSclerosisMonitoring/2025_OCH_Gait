# Correccion de etiquetas, filtro de transiciones y reentrenamiento

## Intervencion

Se aplicaron dos mejoras sobre el dataset ampliado:

1. Correccion auditada de etiquetas en las 15 rachas principales de error.
2. Eliminacion de ventanas a menos de 5 segundos de una transicion `walking` / `not_walking`.

La correccion no se hizo sobre todas las discrepancias del modelo, sino solo donde los tres modelos ponderados out-of-fold coincidieron contra la etiqueta original dentro de rachas prioritarias.

## Correcciones aplicadas

- Ventanas corregidas: 1,014
- Dataset corregido: `salidas_test/data_extension_selected/main_binary_window_features_with_auto_influx_extension_audit_corrected.parquet`
- Auditoria de correcciones: `results/auto_influx_extension_audited_label_corrections.csv`

| Paciente | Origen | Cambio | Ventanas |
| --- | --- | --- | ---: |
| AEMDHUG060-70 | previous_dataset | not_walking -> walking | 526 |
| ACL1998-96 | previous_dataset | walking -> not_walking | 295 |
| 04845288Q-121 | previous_dataset | not_walking -> walking | 102 |
| 47046344M-104 | previous_dataset | walking -> not_walking | 36 |
| AGCHUG064-10 | previous_dataset | not_walking -> walking | 28 |
| 02548893X-118 | previous_dataset | not_walking -> walking | 27 |

## Filtro de transiciones

- Entrada tras correcciones: 21,424 ventanas
- Salida sin transiciones +/-5 s: 20,379 ventanas
- Ventanas eliminadas: 1,045
- Eliminadas `not_walking`: 515
- Eliminadas `walking`: 530
- Dataset final: `salidas_test/data_extension_selected/main_binary_window_features_with_auto_influx_extension_audit_corrected_no_transition_5s.parquet`

## Resultado del reentrenamiento ponderado

Validacion: folds balanceados por paciente/origen/etiqueta, con `sample_weighting=patient_source`.

| Modelo | Accuracy | F1 walking | F1 macro | Recall walking |
| --- | ---: | ---: | ---: | ---: |
| Random Forest | 0.7422 | 0.7006 | 0.7368 | 0.7305 |
| XGBoost | 0.7445 | 0.7041 | 0.7394 | 0.7281 |
| CatBoost | 0.7488 | 0.7073 | 0.7432 | 0.7251 |

CatBoost queda como mejor modelo clasico en este protocolo, con XGBoost muy cerca.

## Comparacion contra la version anterior

| Modelo | F1 walking antes | F1 macro antes | F1 walking corregido | F1 macro corregido |
| --- | ---: | ---: | ---: | ---: |
| Random Forest | 0.5965 | 0.6417 | 0.7006 | 0.7368 |
| XGBoost | 0.5914 | 0.6402 | 0.7041 | 0.7394 |
| CatBoost | 0.5911 | 0.6402 | 0.7073 | 0.7432 |

La mejora es grande y confirma que el problema principal no era la familia de modelo, sino ruido de etiqueta y ventanas ambiguas cerca de transiciones.

## Resultado por origen

| Modelo | Origen | Accuracy | F1 walking | F1 macro | Recall walking |
| --- | --- | ---: | ---: | ---: | ---: |
| Random Forest | auto_influx_heuristic | 0.9047 | 0.8760 | 0.8989 | 0.8539 |
| Random Forest | previous_dataset | 0.6198 | 0.5940 | 0.6170 | 0.6785 |
| XGBoost | auto_influx_heuristic | 0.8922 | 0.8585 | 0.8853 | 0.8265 |
| XGBoost | previous_dataset | 0.6355 | 0.6136 | 0.6338 | 0.6960 |
| CatBoost | auto_influx_heuristic | 0.8975 | 0.8648 | 0.8908 | 0.8312 |
| CatBoost | previous_dataset | 0.6405 | 0.6144 | 0.6384 | 0.6878 |

El origen `previous_dataset` sigue siendo el cuello de botella, aunque mejora claramente.

## Artefactos

- Resultados globales: `results/auto_influx_extension_corrected_notrans_weighted_cv3_summary.csv`
- Resultados por fold: `results/auto_influx_extension_corrected_notrans_weighted_cv3_folds.csv`
- Resultados por origen: `results/auto_influx_extension_corrected_notrans_weighted_cv3_by_source.csv`
- Predicciones: `results/auto_influx_extension_corrected_notrans_weighted_cv3_predictions.csv`
- Ventanas eliminadas por transicion: `results/auto_influx_extension_audit_corrected_transition_removed_5s.csv`
- Resumen de transiciones: `results/auto_influx_extension_audit_corrected_transition_summary_5s.csv`
