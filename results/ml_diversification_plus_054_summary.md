# Diversificacion adicional con 05447093A-110

Se incorporo el paciente `05447093A-110` al conjunto de pacientes nuevos usando
una correccion de tiempo de sesion de `-120 min`, coherente con el escaneo de
cobertura en Influx.

## Ventanas incorporadas de 05447093A-110

- No marcha:
  - `2024-05-09 08:26:46` a `2024-05-09 08:34:00`
  - `2024-05-09 09:44:00` a `2024-05-09 09:44:14`
  - `2024-05-09 09:44:18` a `2024-05-09 09:44:57`
- Marcha:
  - `2024-05-09 09:57:45` a `2024-05-09 09:58:01`
  - `2024-05-09 10:19:26` a `2024-05-09 10:20:00`

Todas las ventanas tienen cobertura en ambos pies y quedaron sin filas `NO_LABEL`
tras el etiquetado.

## Dataset resultante

Dataset de pacientes nuevos (`salidas_test/new_patient_shifted_extracts_plus_054`):

- Referencias nuevas: 4
- Ventanas: 2.079
- No marcha: 881
- Marcha: 1.198

Dataset combinado con el conjunto base:

- Referencias totales: 7
- Ventanas: 3.372
- No marcha: 1.647
- Marcha: 1.725

La incorporacion de `05447093A-110` mejora el equilibrio entre clases respecto al
dataset anterior.

## Resultados principales

### CV estratificada a 3 folds

| Modelo | Accuracy media | F1 marcha medio | F1 macro medio |
|---|---:|---:|---:|
| Random Forest | 0.8203 | 0.8106 | 0.8198 |
| XGBoost | 0.8378 | 0.8321 | 0.8376 |
| CatBoost | 0.8390 | 0.8329 | 0.8387 |

### Leave-one-reference-out

| Modelo | Accuracy media | F1 marcha medio | F1 macro medio |
|---|---:|---:|---:|
| Random Forest | 0.6293 | 0.4668 | 0.5633 |
| XGBoost | 0.5648 | 0.3674 | 0.4961 |
| CatBoost | 0.6116 | 0.4066 | 0.5282 |

Antes de incorporar `05447093A-110`, el mejor F1 macro por paciente era
aproximadamente 0.495. Con `05447093A-110`, Random Forest sube a 0.5633.

### Bloques temporales con embargo de 15 s

| Modelo | Accuracy media | F1 marcha medio | F1 macro medio |
|---|---:|---:|---:|
| Random Forest | 0.6681 | 0.3681 | 0.4699 |
| XGBoost | 0.6532 | 0.3936 | 0.4764 |
| CatBoost | 0.6689 | 0.3983 | 0.4823 |

La validacion por bloques mejora ligeramente respecto al conjunto anterior, pero
sigue mostrando mucha variabilidad entre bloques.

## Conclusion

La diversificacion con `05447093A-110` mejora el equilibrio del dataset y aporta
una mejora visible en la validacion por paciente, especialmente para Random Forest.
No obstante, la generalizacion sigue siendo limitada, por lo que el resultado
refuerza la conclusion metodologica: aumentar pacientes y sesiones tiene mas
impacto que aumentar la complejidad del modelo en esta fase.
