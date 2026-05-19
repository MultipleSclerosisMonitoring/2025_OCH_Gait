# Auditoria de sensibilidad a desfase temporal del ground truth

Este experimento comprueba si pequeñas desviaciones temporales entre etiquetas y
señal afectan al modelo. Se aplicaron offsets al ground truth y se reetiquetaron
las ventanas del dataset ya filtrado sin transiciones +/-5 s.

## Protocolo

Dataset base:

- `salidas_test/temporal_features/main_spectral_temporal_window_features_with_new_patients_plus_054_no_transition_5s.parquet`

Ground truth combinado:

- `salidas_test/ground_truth_clean.xlsx`
- `salidas_test/ground_truth_new_patient_shifted_plus_054_clean.xlsx`

Offsets evaluados:

- `-10`, `-5`, `-2`, `0`, `+2`, `+5`, `+10` segundos.

La auditoria uso Random Forest con validacion por bloques temporales y embargo
de 15 s.

## Resultado de la auditoria

| Offset GT | Accuracy | F1 macro | FPR | Recall marcha | FP | FN |
|---:|---:|---:|---:|---:|---:|---:|
| -10 s | 0.6844 | 0.6793 | 0.4384 | 0.8059 | 673 | 301 |
| -5 s | 0.7207 | 0.7161 | 0.3960 | 0.8331 | 617 | 270 |
| -2 s | 0.7778 | 0.7764 | 0.2841 | 0.8368 | 452 | 272 |
| 0 s | 0.7395 | 0.7352 | 0.3733 | 0.8472 | 601 | 258 |
| +2 s | 0.7852 | 0.7839 | 0.2742 | 0.8418 | 436 | 264 |
| +5 s | 0.7284 | 0.7244 | 0.3789 | 0.8309 | 588 | 275 |
| +10 s | 0.6818 | 0.6749 | 0.4573 | 0.8175 | 697 | 285 |

Los offsets pequenos de +/-2 s mejoran respecto a 0 s, y +2 s es el mejor en
esta auditoria.

## Validacion completa del candidato +2 s

Se genero un dataset reetiquetado con `+2 s`:

- `salidas_test/temporal_features/main_spectral_temporal_window_features_with_new_patients_plus_054_no_transition_5s_gt_offset_plus2s.parquet`

Con el protocolo completo de RF usado en el resto del proyecto:

| Dataset | F1 macro medio por fold | Accuracy media |
|---|---:|---:|
| Sin transiciones, offset 0 s | 0.6312 | 0.7740 |
| Sin transiciones, offset +2 s | 0.6362 | 0.7696 |

La mejora por fold es moderada, pero el barrido de umbral sobre predicciones
out-of-fold mejora mucho el control de falsos positivos:

| Dataset | Umbral | FP | FPR | Recall marcha | Precision marcha | F1 macro global |
|---|---:|---:|---:|---:|---:|---:|
| Sin transiciones, offset 0 s | 0.80 | 170 | 0.1056 | 0.6084 | 0.8580 | 0.7440 |
| Sin transiciones, offset +2 s | 0.80 | 43 | 0.0270 | 0.6052 | 0.9592 | 0.7786 |

## Decision

El offset `+2 s` es un candidato fuerte para corregir un pequeño desfase de
sincronizacion, porque reduce de forma marcada los falsos positivos manteniendo
un recall de marcha similar.

Por prudencia metodologica, no se debe afirmar que el desfase real sea
definitivamente de +2 s sin validacion visual sobre algunos tramos. La decision
practica es conservar dos modelos:

- modelo limpio sin transiciones y offset 0 s;
- modelo limpio sin transiciones y offset +2 s como candidato sincronizado.

Modelo candidato guardado:

- `models/final_random_forest_spectral_temporal_plus_054_no_transition_5s_gt_offset_plus2s.joblib`

Resultados completos:

- `results/ground_truth_offset_sensitivity_no_transition_5s_summary.csv`
- `results/ml_rf_temporal_block_embargo15_no_transition_5s_gt_offset_plus2s_summary.csv`
- `results/ml_rf_temporal_block_embargo15_no_transition_5s_gt_offset_plus2s_threshold_sweep.csv`
