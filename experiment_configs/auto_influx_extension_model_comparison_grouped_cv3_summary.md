# Comparacion de modelos con extension auto Influx

## Entrada

- Dataset: `salidas_test/data_extension_selected/main_binary_window_features_with_auto_influx_extension.parquet`
- Ventanas: 21,424
- Pacientes/referencias: 19
- Features espectrales: 72
- Metadata excluida de features: `dataset_source`
- Validacion: 3 folds con `StratifiedGroupKFold`, agrupando por `reference`

Esta validacion separa pacientes entre entrenamiento y prueba. Es mas exigente que la CV estratificada por ventana y evita que ventanas del mismo paciente aparezcan simultaneamente en train y test.

## Resultados globales

| Modelo | Accuracy media | F1 walking medio | F1 macro medio |
| --- | ---: | ---: | ---: |
| Random Forest | 0.6558 | 0.5919 | 0.6411 |
| XGBoost | 0.6404 | 0.5772 | 0.6273 |
| CatBoost | 0.6514 | 0.5806 | 0.6326 |

Random Forest queda ligeramente por encima en F1 macro, aunque los tres modelos estan cerca. La desviacion entre folds sigue siendo alta, lo que indica sensibilidad a que pacientes caen en cada fold.

## Resultados por origen de datos

| Modelo | Origen | Accuracy media | F1 walking medio | F1 macro medio | Recall walking medio |
| --- | --- | ---: | ---: | ---: | ---: |
| Random Forest | auto_influx_heuristic | 0.8798 | 0.8430 | 0.8728 | 0.8192 |
| Random Forest | previous_dataset | 0.4869 | 0.2948 | 0.4228 | 0.3587 |
| XGBoost | auto_influx_heuristic | 0.8563 | 0.8175 | 0.8494 | 0.7988 |
| XGBoost | previous_dataset | 0.4790 | 0.2976 | 0.4216 | 0.3635 |
| CatBoost | auto_influx_heuristic | 0.8611 | 0.8145 | 0.8517 | 0.7813 |
| CatBoost | previous_dataset | 0.5034 | 0.2929 | 0.4278 | 0.3482 |

## Lectura operativa

- El dataset nuevo auto-etiquetado aporta mucha senal interna, pero conviene no asumir que el rendimiento alto representa generalizacion completa.
- El dataset previo tiene folds dificiles: en uno de los folds, el subconjunto `previous_dataset` no contiene ventanas `walking` en test, porque la separacion se hace por paciente.
- La siguiente mejora metodologica razonable es generar folds predefinidos equilibrados por paciente, etiqueta y origen, o pasar a una evaluacion leave-one-subject-out con resumen por paciente.

## Artefactos

- Folds: `results/auto_influx_extension_model_comparison_grouped_cv3_folds.csv`
- Resumen global: `results/auto_influx_extension_model_comparison_grouped_cv3_summary.csv`
- Resumen por origen: `results/auto_influx_extension_model_comparison_grouped_cv3_by_source.csv`
