# Comparacion CV3 sobre el dataset ampliado

## Objetivo

Resumir el rendimiento de RF, XGBoost y CatBoost sobre el dataset ampliado con
nuevos pacientes, usando validacion cruzada estratificada de 3 folds y
reportando media y desviacion estandar.

## Dataset

- `salidas_test/auto_extracts/main_binary_window_features_with_new_patients_plus_054.parquet`
- 3.372 filas
- 7 referencias

## Resultados

### Random Forest

- Accuracy: `0.8203 +/- 0.0086`
- Precision marcha: `0.8800 +/- 0.0221`
- Recall marcha: `0.7519 +/- 0.0209`
- F1 marcha: `0.8106 +/- 0.0093`
- Precision macro: `0.8273 +/- 0.0100`
- Recall macro: `0.8219 +/- 0.0087`
- F1 macro: `0.8198 +/- 0.0086`

### XGBoost

- Accuracy: `0.8378 +/- 0.0019`
- Precision marcha: `0.8845 +/- 0.0175`
- Recall marcha: `0.7861 +/- 0.0198`
- F1 marcha: `0.8321 +/- 0.0036`
- Precision macro: `0.8420 +/- 0.0036`
- Recall macro: `0.8390 +/- 0.0020`
- F1 macro: `0.8376 +/- 0.0018`

### CatBoost

- Accuracy: `0.8390 +/- 0.0027`
- Precision marcha: `0.8884 +/- 0.0199`
- Recall marcha: `0.7843 +/- 0.0184`
- F1 marcha: `0.8329 +/- 0.0022`
- Precision macro: `0.8437 +/- 0.0053`
- Recall macro: `0.8403 +/- 0.0031`
- F1 macro: `0.8387 +/- 0.0025`

## Lectura breve

Los tres clasificadores mejoran de forma clara con el dataset ampliado. La
diferencia entre modelos es pequeña, pero CatBoost y XGBoost quedan por delante
de RF en F1 de marcha, y la dispersion entre folds es baja.

La conclusion metodologica es la misma que ya apuntaban los experimentos
anteriores: el cuello de botella principal no era la arquitectura, sino la
diversidad de pacientes y la representatividad del conjunto de datos.
