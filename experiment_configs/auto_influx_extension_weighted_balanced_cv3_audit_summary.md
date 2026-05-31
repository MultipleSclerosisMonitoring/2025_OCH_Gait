# Ponderacion paciente/origen y auditoria de errores

## Objetivo

Se evaluo el mismo protocolo de folds balanceados por paciente, etiqueta y origen, pero entrenando con `sample_weighting=patient_source`. La ponderacion hace que cada celda `reference + dataset_source` tenga peso comparable, evitando que pacientes u origenes con muchas ventanas dominen el ajuste.

## Comparacion global

| Modelo | Accuracy sin ponderar | F1 walking sin ponderar | F1 macro sin ponderar | Accuracy ponderado | F1 walking ponderado | F1 macro ponderado |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Random Forest | 0.6177 | 0.5650 | 0.6103 | 0.6493 | 0.5965 | 0.6417 |
| XGBoost | 0.6143 | 0.5553 | 0.6062 | 0.6487 | 0.5914 | 0.6402 |
| CatBoost | 0.6219 | 0.5597 | 0.6124 | 0.6493 | 0.5911 | 0.6402 |

La ponderacion mejora los tres modelos de forma consistente. Random Forest queda ligeramente por encima, con el mejor F1 de marcha y el mejor F1 macro.

## Resultado por origen

| Modelo | Origen | Accuracy | F1 walking | F1 macro | Recall walking |
| --- | --- | ---: | ---: | ---: | ---: |
| Random Forest | auto_influx_heuristic | 0.8619 | 0.8246 | 0.8553 | 0.8014 |
| Random Forest | previous_dataset | 0.4838 | 0.4294 | 0.4712 | 0.5688 |
| XGBoost | auto_influx_heuristic | 0.8503 | 0.8059 | 0.8420 | 0.7622 |
| XGBoost | previous_dataset | 0.4927 | 0.4350 | 0.4794 | 0.5732 |
| CatBoost | auto_influx_heuristic | 0.8502 | 0.8063 | 0.8420 | 0.7660 |
| CatBoost | previous_dataset | 0.4946 | 0.4347 | 0.4807 | 0.5694 |

El origen `auto_influx_heuristic` sigue siendo mucho mas facil que `previous_dataset`. Esto apunta a una diferencia de distribucion y/o calidad de etiqueta entre origenes.

## Pacientes prioritarios

La auditoria por paciente/origen identifica los focos principales:

- `ACL1998-96` en `previous_dataset`: concentra el mayor numero de errores en los tres modelos, sobre todo falsos negativos de marcha.
- `AEMDHUG060-70` en `previous_dataset`: muchos falsos positivos en tramos etiquetados como `not_walking`.
- `AGCHUG064-10` en `previous_dataset`: muchos falsos positivos en tramos `not_walking`.
- `47046344M-104` en `previous_dataset`: muchos falsos negativos de marcha.
- `AGCHUG064-10` en `auto_influx_heuristic`: errores mixtos relevantes, aunque menos graves que en `previous_dataset`.

## Rachas temporales a revisar

Para el modelo Random Forest ponderado, las rachas mas largas apuntan a ventanas concretas:

- `AEMDHUG060-70`, 2026-04-29 15:22:01 UTC a 15:28:53 UTC: 413 falsos positivos.
- `AEMDHUG060-70`, 2026-04-28 10:51:39 UTC a 10:53:43 UTC: 125 falsos positivos.
- `04845288Q-121`, 2025-03-01 11:36:15 UTC a 11:37:57 UTC: 103 falsos positivos.
- `ACL1998-96`, 2025-07-16 08:40:30 UTC a 08:42:04 UTC: 95 falsos negativos.
- `ACL1998-96`, 2025-07-16 08:39:08 UTC a 08:40:26 UTC: 79 falsos negativos.

Estas ventanas son candidatas directas para revisar etiqueta o contenido real en Grafana/Influx. Los falsos positivos de alta probabilidad pueden ser actividades no marcha similares a marcha; los falsos negativos largos pueden indicar marcha atipica o etiqueta desplazada/incompleta.

## Artefactos

- Comparacion ponderada: `results/auto_influx_extension_model_comparison_weighted_balanced_cv3_summary.csv`
- Predicciones ponderadas: `results/auto_influx_extension_model_comparison_weighted_balanced_cv3_predictions.csv`
- Auditoria por paciente/origen: `results/auto_influx_extension_weighted_balanced_cv3_patient_audit.csv`
- Rachas de error RF: `results/auto_influx_extension_weighted_balanced_cv3_rf_error_runs.csv`
- Resumen de rachas RF: `results/auto_influx_extension_weighted_balanced_cv3_rf_error_summary.md`
