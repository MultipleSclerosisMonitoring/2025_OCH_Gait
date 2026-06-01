# Evaluacion tras revision visual automatica

## Revision de correcciones

Se revisaron los 99 intervalos sospechosos extraidos desde InfluxDB en
`results/correction_visual_review/`. El criterio automatico usa la actividad de
la senal raw dentro del intervalo auditado:

- `walking`: `acc_std_mean >= 0.05` y `gyro_std_mean >= 10.0`.
- `not_walking`: `acc_std_mean <= 0.05` y `gyro_std_mean <= 5.0`.

Resultado:

- Intervalos confirmados: 99 / 99
- Correcciones de ventana confirmadas: 1014 / 1014
- Rechazos automaticos: 0
- Casos ambiguos para revision manual: 0

La separacion observada fue amplia:

| Cambio | Intervalos | acc std min/med/max | gyro std min/med/max |
|---|---:|---:|---:|
| `not_walking` -> `walking` | 58 | 0.1600 / 0.5525 / 0.6954 | 74.4265 / 101.5310 / 118.1019 |
| `walking` -> `not_walking` | 41 | 0.0008 / 0.0017 / 0.0097 | 0.1266 / 0.3401 / 1.6803 |

Las 1014 correcciones confirmadas coinciden una a una con
`results/auto_influx_extension_audited_label_corrections.csv`.

## Evaluacion con folds fijos

Dataset evaluado:
`salidas_test/data_extension_selected/main_binary_window_features_with_auto_influx_extension_audit_corrected_no_transition_5s.parquet`

Protocolo:

- CV: `balanced_grouped`
- Folds: `results/auto_influx_extension_model_comparison_weighted_balanced_cv3_fold_plan.csv`
- Ponderacion: `patient_source`
- Metadatos excluidos de features: `dataset_source`

| Modelo | Accuracy | F1 walking | F1 macro | Recall walking |
|---|---:|---:|---:|---:|
| Random Forest | 0.7270 | 0.6885 | 0.7219 | 0.7213 |
| XGBoost | 0.7254 | 0.6866 | 0.7203 | 0.7153 |
| CatBoost | 0.7274 | 0.6872 | 0.7220 | 0.7110 |

Con folds fijos, CatBoost queda ligeramente por encima en F1 macro y Random
Forest queda ligeramente por encima en F1 walking. La diferencia entre modelos
clasicos es pequena; el resultado importante es que la correccion de etiquetas
queda respaldada por la senal raw y no solo por el consenso de modelos.

## Artefactos

- Metricas raw: `results/correction_visual_review/raw_signal_decision_metrics.csv`
- Decisiones automaticas: `results/correction_visual_review/review_decisions_auto.csv`
- Correcciones confirmadas: `results/correction_visual_review/confirmed_audited_label_corrections.csv`
- Resumen de revision: `results/correction_visual_review/auto_review_summary.md`
- Resultados globales: `results/visual_confirmed_notrans_fixed_weighted_cv3_summary.csv`
- Resultados por fold: `results/visual_confirmed_notrans_fixed_weighted_cv3_folds.csv`
- Resultados por origen: `results/visual_confirmed_notrans_fixed_weighted_cv3_by_source.csv`
- Predicciones: `results/visual_confirmed_notrans_fixed_weighted_cv3_predictions.csv`
