# Limpieza de transiciones y sensibilidad del ground truth

Este experimento aborda el riesgo de desalineamiento temporal entre etiquetas y
señal. En vez de modificar la arquitectura, se limpio el dataset eliminando
ventanas cercanas a cambios de etiqueta, donde es mas probable mezclar
preparacion, inicio/parada de marcha o errores de sincronizacion.

## Filtro aplicado

Dataset de partida:

- `salidas_test/temporal_features/main_spectral_temporal_window_features_with_new_patients_plus_054.parquet`

Filtro:

- se ordenaron ventanas por `reference` y `time_center`;
- se detectaron cambios de `mov_type` dentro de cada bloque temporal;
- se eliminaron ventanas a menos de 5 segundos de una transicion de etiqueta.

Resultado:

| Dataset | Filas | Not walking | Walking |
|---|---:|---:|---:|
| Original | 3372 | 1647 | 1725 |
| Sin transiciones +/-5 s | 3298 | 1610 | 1688 |
| Eliminadas | 74 | 37 | 37 |

El filtro elimina pocas filas y lo hace de forma equilibrada entre clases.

## Impacto en validacion temporal

Random Forest con features espectrales + temporales, leave-one-temporal-block-out
y embargo de 15 s:

| Dataset | F1 macro | Accuracy |
|---|---:|---:|
| Original | 0.4958 | 0.6956 |
| Sin transiciones +/-5 s | 0.6312 | 0.7740 |

La mejora indica que parte del error venia de ventanas ambiguas o mal
sincronizadas alrededor de transiciones, no solo de la arquitectura del modelo.

## Impacto en falsos positivos

Comparacion de puntos operativos con recall de marcha similar:

| Dataset | Umbral | FP | FPR | Recall marcha | Precision marcha | F1 macro |
|---|---:|---:|---:|---:|---:|---:|
| Original | 0.72 | 327 | 0.1985 | 0.6186 | 0.7654 | 0.7062 |
| Sin transiciones +/-5 s | 0.80 | 170 | 0.1056 | 0.6084 | 0.8580 | 0.7440 |

Con el dataset filtrado se reducen los falsos positivos casi a la mitad
manteniendo una sensibilidad parecida.

## Artefactos generados

- `gait_analysis/filter_transition_windows.py`
- `salidas_test/temporal_features/main_spectral_temporal_window_features_with_new_patients_plus_054_no_transition_5s.parquet`
- `results/transition_window_filter_removed_5s.csv`
- `results/transition_window_filter_summary_5s.csv`
- `results/ml_rf_temporal_block_embargo15_spectral_temporal_no_transition_5s_summary.csv`
- `results/ml_rf_temporal_block_embargo15_spectral_temporal_no_transition_5s_threshold_sweep.csv`
- `models/final_random_forest_spectral_temporal_plus_054_no_transition_5s.joblib`

## Decision

Para el modelo clasico final, la version sin transiciones +/-5 s es mas
defendible que el dataset original. Reduce el ruido de ground truth, mejora la
validacion temporal y disminuye falsos positivos sin depender de postprocesados
rigidos.

El umbral operativo recomendado para esta version limpia es 0.80 si se busca
controlar falsos positivos manteniendo `recall_walking` cercano a 0.60.
