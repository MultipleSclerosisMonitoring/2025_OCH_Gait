# Comparacion de diversidad: baseline vs nuevo conjunto de pacientes

## Objetivo

Cuantificar si la incorporacion del conjunto de pacientes nuevos con la correccion
de tiempo `05447093A-110`, `330034-32`, `663495-44` y `TABUENCA01-45`
mejora de forma clara la capacidad de clasificacion respecto al dataset base
actual con tres pacientes.

## Datasets comparados

- Baseline actual:
  - `salidas_test/auto_extracts/main_binary_window_features.parquet`
  - 1.293 filas
  - 3 referencias
- Dataset ampliado con nuevos pacientes:
  - `salidas_test/auto_extracts/main_binary_window_features_with_new_patients_plus_054.parquet`
  - 3.372 filas
  - 7 referencias

## Resultados CV3

### Baseline actual

| Modelo | Accuracy | F1 marcha |
| --- | ---: | ---: |
| Random Forest | 0.7394 | 0.7107 |
| XGBoost | 0.7618 | 0.7216 |
| CatBoost | 0.7579 | 0.7166 |

### Dataset ampliado

| Modelo | Accuracy | F1 marcha |
| --- | ---: | ---: |
| Random Forest | 0.8203 | 0.8106 |
| XGBoost | 0.8378 | 0.8321 |
| CatBoost | 0.8390 | 0.8329 |

## Ganancia observada

| Modelo | Delta accuracy | Delta F1 marcha |
| --- | ---: | ---: |
| Random Forest | +0.0809 | +0.0999 |
| XGBoost | +0.0760 | +0.1105 |
| CatBoost | +0.0811 | +0.1163 |

## Interpretacion

La ganancia es demasiado grande para atribuirla a un simple ajuste de umbral o a una
pequena mejora de arquitectura. Lo que explica el salto es la diversidad adicional:
mas pacientes, mas sesiones y mas combinacion de patrones de marcha/no marcha.

Esto encaja con el diagnostico metodologico del tutor:

1. La capacidad del modelo ya era suficiente para aprender el problema.
2. El cuello de botella estaba en la variedad y representatividad de los datos.
3. Al ampliar pacientes, el rendimiento sube de forma consistente en los tres modelos.

## Conclusion breve

La diversidad nueva si mueve la aguja. El mejor modelo pasa de un F1 de marcha de
`0.7216` en el baseline actual a `0.8329` en el dataset ampliado, con una mejora
simultanea en accuracy y estabilidad entre folds.
