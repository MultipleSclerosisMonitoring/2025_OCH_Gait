# Comparacion con folds balanceados por paciente

## Objetivo

La comparacion anterior usaba `StratifiedGroupKFold`: separaba pacientes, pero podia dejar folds con una distribucion poco representativa de `walking/not_walking` y de origen de datos. Esta version construye folds agrupados por `reference` intentando balancear:

- numero de ventanas;
- ventanas `walking` y `not_walking`;
- origen `previous_dataset` y `auto_influx_heuristic`;
- combinacion origen-etiqueta.

## Entrada

- Dataset: `salidas_test/data_extension_selected/main_binary_window_features_with_auto_influx_extension.parquet`
- Ventanas: 21,424
- Pacientes/referencias: 19
- Features espectrales: 72
- Metadata excluida de features: `dataset_source`
- Validacion: 3 folds agrupados por `reference`, con asignacion balanceada greedy.

## Balance de folds

| Fold | Ventanas | Not walking | Walking | Previous dataset | Auto Influx | Pacientes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 6,162 | 4,128 | 2,034 | 2,810 | 3,352 | 8 |
| 2 | 6,302 | 3,864 | 2,438 | 3,012 | 3,290 | 7 |
| 3 | 8,960 | 4,357 | 4,603 | 6,338 | 2,622 | 4 |

El fold 3 queda mas grande porque `ACL1998-96` concentra muchas ventanas. Aun asi, los tres folds contienen ambas clases y ambos origenes, evitando el caso anterior en el que un subconjunto de test no tenia ejemplos `walking`.

## Resultados globales

| Modelo | Accuracy media | F1 walking medio | F1 macro medio | Recall walking medio |
| --- | ---: | ---: | ---: | ---: |
| Random Forest | 0.6177 | 0.5650 | 0.6103 | 0.6334 |
| XGBoost | 0.6143 | 0.5553 | 0.6062 | 0.6125 |
| CatBoost | 0.6219 | 0.5597 | 0.6124 | 0.6090 |

CatBoost queda ligeramente por encima en F1 macro, pero la diferencia entre modelos es pequena. Random Forest conserva el mejor F1 de marcha y el mejor recall de marcha.

## Resultados por origen

| Modelo | Origen | Accuracy media | F1 walking medio | F1 macro medio | Recall walking medio |
| --- | --- | ---: | ---: | ---: | ---: |
| Random Forest | auto_influx_heuristic | 0.8025 | 0.7565 | 0.7949 | 0.7418 |
| Random Forest | previous_dataset | 0.4850 | 0.4453 | 0.4767 | 0.6123 |
| XGBoost | auto_influx_heuristic | 0.7920 | 0.7341 | 0.7813 | 0.6924 |
| XGBoost | previous_dataset | 0.4845 | 0.4448 | 0.4774 | 0.6053 |
| CatBoost | auto_influx_heuristic | 0.8015 | 0.7420 | 0.7901 | 0.6997 |
| CatBoost | previous_dataset | 0.4937 | 0.4477 | 0.4845 | 0.5984 |

## Interpretacion

La bajada frente a los experimentos por ventana no indica necesariamente que el dataset haya empeorado. Este protocolo mide una tarea mas dificil: generalizacion a pacientes no vistos. Frente al grouped CV anterior, los folds son metodologicamente mas limpios, pero el rendimiento global baja ligeramente porque el test queda menos dominado por los segmentos auto-etiquetados faciles.

El cuello de botella sigue siendo la heterogeneidad entre pacientes y origenes, no la familia concreta de modelo. La accion mas util ahora es auditar etiquetas y errores por paciente, especialmente en `previous_dataset`, y despues entrenar con ponderacion por paciente/origen.

## Artefactos

- Plan de folds: `results/auto_influx_extension_model_comparison_balanced_grouped_cv3_fold_plan.csv`
- Resumen del plan: `results/auto_influx_extension_model_comparison_balanced_grouped_cv3_fold_plan_summary.csv`
- Folds: `results/auto_influx_extension_model_comparison_balanced_grouped_cv3_folds.csv`
- Resumen global: `results/auto_influx_extension_model_comparison_balanced_grouped_cv3_summary.csv`
- Resumen por origen: `results/auto_influx_extension_model_comparison_balanced_grouped_cv3_by_source.csv`
