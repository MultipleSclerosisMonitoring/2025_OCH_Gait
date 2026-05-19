# Entrenamiento conservador para reducir falsos positivos

Se probo una mejora en la etapa de aprendizaje: entrenar Random Forest con mas
peso para la clase `not_walking`, en lugar de corregir despues la secuencia con
persistencia o histeresis.

## Experimento

Dataset:

- `salidas_test/temporal_features/main_spectral_temporal_window_features_with_new_patients_plus_054.parquet`

Validacion:

- Leave-one-temporal-block-out.
- Embargo temporal de 15 s.
- Features espectrales + temporales.
- Random Forest con `max_depth=5`, `min_samples_leaf=10`, `n_estimators=300`.

Se probaron pesos para `not_walking`: `1.0`, `1.5`, `2.0`, `3.0`, combinados
con umbrales `0.50`, `0.60`, `0.70`, `0.72`, `0.80`.

## Mejores opciones

| Configuracion | FP | FPR | Recall marcha | Precision marcha | F1 macro |
|---|---:|---:|---:|---:|---:|
| Peso 1.0, umbral 0.50 | 639 | 0.3880 | 0.8730 | 0.7021 | 0.7399 |
| Peso 2.0, umbral 0.60 | 361 | 0.2192 | 0.6528 | 0.7572 | 0.7147 |
| Peso 3.0, umbral 0.60 | 263 | 0.1597 | 0.5814 | 0.7923 | 0.7041 |
| Peso 2.0, umbral 0.72 | 146 | 0.0886 | 0.4817 | 0.8506 | 0.6789 |
| Peso 3.0, umbral 0.72 | 48 | 0.0291 | 0.4290 | 0.9391 | 0.6724 |

## Decision

La configuracion mas equilibrada es `not_walking_weight=2.0` con umbral `0.60`:
reduce los falsos positivos respecto al umbral base, mantiene `recall_walking`
por encima de 0.60 y conserva un F1 macro razonable.

Si el objetivo clinico prioriza reducir falsos positivos por encima de detectar
todos los episodios cortos de marcha, se puede usar una configuracion mas dura:
`not_walking_weight=3.0` con umbral `0.60`, o incluso umbral `0.72`, aceptando
menor sensibilidad.

Se guardo un modelo final conservador con `not_walking_weight=2.0`:

- `models/final_random_forest_spectral_temporal_plus_054_conservative.joblib`
- `results/final_random_forest_spectral_temporal_plus_054_conservative_summary.json`

Los resultados completos estan en:

- `results/conservative_rf_temporal_block_embargo15_folds.csv`
- `results/conservative_rf_temporal_block_embargo15_threshold_summary.csv`
