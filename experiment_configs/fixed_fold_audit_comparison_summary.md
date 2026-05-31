# Comparacion con folds fijos y auditoria visual

## Objetivo

Se repitio la evaluacion usando exactamente el mismo `fold_plan` para tres escenarios:

1. Dataset original ampliado.
2. Dataset con correcciones auditadas.
3. Dataset con correcciones auditadas y filtro de transiciones +/-5 s.

El plan fijo usado fue `results/auto_influx_extension_model_comparison_weighted_balanced_cv3_fold_plan.csv`. Esto evita atribuir mejora a un cambio accidental en la asignacion de pacientes a folds.

## Resultados con folds fijos

| Escenario | Modelo | Accuracy | F1 walking | F1 macro | Recall walking |
| --- | --- | ---: | ---: | ---: | ---: |
| Original | Random Forest | 0.6493 | 0.5965 | 0.6417 | 0.6585 |
| Original | XGBoost | 0.6487 | 0.5914 | 0.6402 | 0.6464 |
| Original | CatBoost | 0.6493 | 0.5911 | 0.6402 | 0.6436 |
| Corregido | Random Forest | 0.7146 | 0.6812 | 0.7107 | 0.7281 |
| Corregido | XGBoost | 0.7164 | 0.6825 | 0.7124 | 0.7255 |
| Corregido | CatBoost | 0.7145 | 0.6780 | 0.7101 | 0.7142 |
| Corregido sin transiciones | Random Forest | 0.7270 | 0.6885 | 0.7219 | 0.7213 |
| Corregido sin transiciones | XGBoost | 0.7254 | 0.6866 | 0.7203 | 0.7153 |
| Corregido sin transiciones | CatBoost | 0.7274 | 0.6872 | 0.7220 | 0.7110 |

## Lectura

La mejora se mantiene con folds fijos, pero es mas moderada que cuando se recalculaba el plan de folds tras filtrar transiciones. La subida principal viene de la correccion auditada de etiquetas:

- F1 macro original: ~0.64
- F1 macro corregido: ~0.71
- F1 macro corregido sin transiciones: ~0.72

El filtro de transiciones aporta mejora adicional pequena y reduce ruido, pero no es el factor dominante.

## Auditoria visual

Se genero una tabla agrupando ventanas corregidas consecutivas en intervalos revisables:

- `results/auto_influx_extension_correction_visual_audit_table.csv`
- `results/auto_influx_extension_correction_visual_audit_table.md`

Los intervalos principales a revisar en Grafana son:

| Paciente | Origen | Cambio | Inicio local | Fin local | Ventanas |
| --- | --- | --- | --- | --- | ---: |
| 04845288Q-121 | previous_dataset | not_walking -> walking | 2025-03-01 12:36:16 | 2025-03-01 12:37:57 | 102 |
| AEMDHUG060-70 | previous_dataset | not_walking -> walking | 2026-04-29 17:26:44 | 2026-04-29 17:28:25 | 95 |
| AEMDHUG060-70 | previous_dataset | not_walking -> walking | 2026-04-29 17:22:53 | 2026-04-29 17:24:34 | 92 |
| AEMDHUG060-70 | previous_dataset | not_walking -> walking | 2026-04-29 17:24:37 | 2026-04-29 17:25:46 | 65 |
| ACL1998-96 | previous_dataset | walking -> not_walking | 2025-07-16 10:39:16 | 2025-07-16 10:40:25 | 62 |
| ACL1998-96 | previous_dataset | walking -> not_walking | 2025-07-16 10:29:54 | 2025-07-16 10:30:52 | 56 |

## Artefactos

- Resumen comparativo: `results/fixed_fold_audit_comparison_summary.csv`
- Folds comparativos: `results/fixed_fold_audit_comparison_folds.csv`
- Comparacion por origen: `results/fixed_fold_audit_comparison_by_source.csv`
- Tabla visual: `results/auto_influx_extension_correction_visual_audit_table.csv`
