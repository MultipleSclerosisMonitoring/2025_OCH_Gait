# Ajuste de umbral probabilistico del modelo clasico

Este experimento responde al problema de falsos positivos sin recurrir a reglas
temporales rigidas de persistencia, histeresis o consenso con Transformer.

Se genero una prediccion out-of-fold del Random Forest con features espectrales
+ temporales usando validacion por bloques temporales y embargo de 15 segundos.
Despues se barrio el umbral de decision sobre la probabilidad de marcha.

Dataset evaluado:

- `salidas_test/temporal_features/main_spectral_temporal_window_features_with_new_patients_plus_054.parquet`

Salidas generadas:

- `results/ml_rf_temporal_block_embargo15_spectral_temporal_oof_predictions.csv`
- `results/ml_rf_temporal_block_embargo15_spectral_temporal_threshold_sweep.csv`

## Comparacion de umbrales

| Umbral | Accuracy | Precision marcha | Recall marcha | F1 macro | Falsos positivos | FPR |
|---:|---:|---:|---:|---:|---:|---:|
| 0.50 | 0.7515 | 0.7097 | 0.8701 | 0.7466 | 614 | 0.3728 |
| 0.60 | 0.7355 | 0.7217 | 0.7861 | 0.7342 | 523 | 0.3175 |
| 0.70 | 0.7120 | 0.7480 | 0.6591 | 0.7116 | 383 | 0.2325 |
| 0.72 | 0.7079 | 0.7654 | 0.6186 | 0.7062 | 327 | 0.1985 |
| 0.80 | 0.6756 | 0.8939 | 0.4151 | 0.6538 | 85 | 0.0516 |

El umbral que maximiza F1 macro es 0.29, pero no es adecuado si el objetivo es
reducir falsos positivos, porque mantiene una tasa de falsos positivos de
0.4451. Para un uso mas conservador, el umbral 0.72 reduce los falsos positivos
de 614 a 327 frente al umbral 0.50, manteniendo un recall de marcha de 0.6186.

## Decision

Para reducir falsas detecciones sin aplicar postprocesados temporales rigidos,
la opcion mas razonable ahora es usar el modelo clasico con un umbral
probabilistico conservador. El umbral recomendado actual es 0.72 cuando se
prioriza limitar falsos positivos, y 0.50 cuando se prioriza sensibilidad.

Esta correccion actua sobre la regla de decision del clasificador y se calibra
con predicciones out-of-fold por bloques temporales, por lo que es mas defendible
que imponer reglas de persistencia sobre secuencias ya defectuosas.
