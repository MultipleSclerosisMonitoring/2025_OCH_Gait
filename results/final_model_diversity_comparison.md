# Comparacion del modelo final: baseline vs dataset ampliado

## Objetivo

Comprobar si el salto de diversidad de pacientes que ya mejoraba la CV3 tambien
se traduce en una mejora del modelo final entrenado sobre todos los datos.

## Datasets

- Baseline final:
  - `salidas_test/auto_extracts/main_binary_window_features.parquet`
  - 1.293 filas
  - 3 referencias
  - 11 grupos temporales
- Dataset ampliado:
  - `salidas_test/auto_extracts/main_binary_window_features_with_new_patients_plus_054.parquet`
  - 3.372 filas
  - 7 referencias
  - 25 grupos temporales

## Modelo

- `RandomForestClassifier`
- `n_estimators=300`
- `random_state=42`
- `class_weight=balanced`
- `max_depth=5`
- `min_samples_leaf=10`
- `max_features=sqrt`

## Resultados del modelo final

### Baseline

- Accuracy de entrenamiento: `0.8097`
- F1 marcha de entrenamiento: `0.7912`
- Accuracy out-of-fold temporal: `0.5800`
- F1 marcha out-of-fold temporal: `0.6079`
- Recall marcha out-of-fold temporal: `0.7989`

### Dataset ampliado

- Accuracy de entrenamiento: `0.8514`
- F1 marcha de entrenamiento: `0.8445`
- Accuracy out-of-fold temporal: `0.7337`
- F1 marcha out-of-fold temporal: `0.7349`
- Recall marcha out-of-fold temporal: `0.7217`

## Lectura

La mejora del dataset ampliado no se limita a la CV3. Tambien aparece en la
evaluacion temporal final, con una subida clara de accuracy y F1 de marcha.

El recall baja algo respecto al baseline, pero el balance global es mejor: el
modelo ampliado reduce errores de generalizacion y da una estimacion mas
solida del comportamiento real sobre bloques temporales nuevos.

## Conclusión breve

La diversidad adicional de pacientes sigue siendo el factor mas importante.
El modelo final sobre el dataset ampliado es claramente mas util que el
baseline de tres pacientes, y ya permite cerrar la parte metodologica de la
TFG con una base experimental bastante mas defendible.
