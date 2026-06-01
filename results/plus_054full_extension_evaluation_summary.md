# Extension con 05447093A-110 completo

## Criterio de inclusion

Se revisaron los candidatos locales que no estaban en el dataset final anterior.
No se incorporo ningun paciente completamente nuevo porque los candidatos
pendientes no tenian cobertura util en Influx o no tenian etiquetas suficientes
para formar un bloque binario fiable:

- `05447093A-111` y `05447093A-112`: sin registros validos de ambos pies en la
  comprobacion de cobertura y solo con etiqueta `not_walking`.
- `AMIR-48`, `AAMALMHUG057-66`, `AGCHUG046-10` y `MGM-202406-79`: sin registros
  recuperables en los offsets probados.

La extension segura fue completar `05447093A-110`, que ya estaba incluido pero
solo aportaba ventanas `walking`. Se anadieron sus ventanas `not_walking`
extraidas y etiquetadas localmente.

## Dataset resultante

- Base anterior sin transiciones:
  `salidas_test/data_extension_selected/main_binary_window_features_with_auto_influx_extension_audit_corrected_no_transition_5s.parquet`
- Dataset extendido sin transiciones:
  `salidas_test/data_extension_selected/main_binary_window_features_with_auto_influx_extension_audit_corrected_plus_054full_no_transition_5s.parquet`
- Filtrado de transiciones: 5 s.
- Referencias: 19.
- Filas anteriores: 20.379.
- Filas extendidas: 20.848.
- Incremento neto: 469 ventanas `not_walking`.

Distribucion global:

| Dataset | walking | not_walking | total |
|---|---:|---:|---:|
| Anterior | 8.897 | 11.482 | 20.379 |
| Extendido | 8.897 | 11.951 | 20.848 |

Distribucion de `05447093A-110`:

| Dataset | walking | not_walking |
|---|---:|---:|
| Anterior | 46 | 0 |
| Extendido | 46 | 469 |

## Evaluacion con folds fijos

Protocolo:

- CV: `balanced_grouped`
- Folds: `results/auto_influx_extension_model_comparison_weighted_balanced_cv3_fold_plan.csv`
- Ponderacion: `patient_source`
- Metadatos excluidos de features: `dataset_source`

| Modelo | F1 walking anterior | F1 walking extendido | F1 macro anterior | F1 macro extendido |
|---|---:|---:|---:|---:|
| Random Forest | 0.6885 | 0.6792 | 0.7219 | 0.7197 |
| XGBoost | 0.6866 | 0.6733 | 0.7203 | 0.7154 |
| CatBoost | 0.6872 | 0.6787 | 0.7220 | 0.7193 |

La extension mejora el balance interno de `05447093A-110`, pero no incrementa el
numero de pacientes. Las metricas quedan muy proximas al dataset anterior, con
una ligera bajada de F1 walking. Por tanto, este artefacto es util para analizar
robustez y balance por paciente, pero el baseline recomendado sigue siendo el
dataset auditado anterior salvo que se priorice explicitamente completar
pacientes ya incluidos.

## Artefactos

- Resumen de combinacion:
  `results/plus_054full_binary_extension_summary.md`
- Transiciones retiradas:
  `results/plus_054full_transition_removed_5s.csv`
- Resumen de transiciones:
  `results/plus_054full_transition_summary_5s.csv`
- Resultados globales:
  `results/plus_054full_notrans_fixed_weighted_cv3_summary.csv`
- Resultados por fold:
  `results/plus_054full_notrans_fixed_weighted_cv3_folds.csv`
- Resultados por origen:
  `results/plus_054full_notrans_fixed_weighted_cv3_by_source.csv`
- Predicciones:
  `results/plus_054full_notrans_fixed_weighted_cv3_predictions.csv`
