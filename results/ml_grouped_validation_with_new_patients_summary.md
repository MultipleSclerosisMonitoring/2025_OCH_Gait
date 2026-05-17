# Validacion agrupada con pacientes nuevos

Se amplio el dataset tabular de espectrogramas con ventanas de tres referencias nuevas
(`330034-32`, `663495-44` y `TABUENCA01-45`). El dataset combinado local contiene
2.857 ventanas, 72 variables espectrales y 6 referencias en total:

- No marcha: 1.178 ventanas.
- Marcha: 1.679 ventanas.

## CV estratificada a 3 folds

Sobre ventanas mezcladas de todos los pacientes, los modelos clasicos obtienen:

| Modelo | Accuracy media | F1 marcha medio | F1 macro medio |
|---|---:|---:|---:|
| Random Forest | 0.8113 | 0.8241 | 0.8103 |
| XGBoost | 0.8393 | 0.8552 | 0.8374 |
| CatBoost | 0.8393 | 0.8560 | 0.8371 |

Esta prueba responde a la comparacion inicial solicitada para RF, XGBoost y CatBoost,
pero puede ser optimista porque mezcla ventanas cercanas o del mismo paciente entre
entrenamiento y test.

## Leave-one-reference-out

Al dejar fuera una referencia completa en cada fold, la generalizacion baja de forma
clara:

| Modelo | Accuracy media | F1 marcha medio | F1 macro medio |
|---|---:|---:|---:|
| Random Forest | 0.5476 | 0.3996 | 0.4951 |
| XGBoost | 0.5034 | 0.3427 | 0.4516 |
| CatBoost | 0.5323 | 0.3665 | 0.4708 |

Esta evaluacion es mas representativa del caso clinico de aplicar el sistema sobre
pacientes no vistos. El resultado confirma que la diversidad sigue siendo limitada:
algunos pacientes nuevos, como `663495-44`, generalizan bien, pero otros muestran
patrones diferentes y reducen mucho el rendimiento.

## Bloques temporales con embargo de 15 s

Al dejar fuera bloques temporales completos y eliminar del entrenamiento ventanas
cercanas al bloque de test, los resultados son:

| Modelo | Accuracy media | F1 marcha medio | F1 macro medio |
|---|---:|---:|---:|
| Random Forest | 0.6299 | 0.3922 | 0.4810 |
| XGBoost | 0.6078 | 0.4168 | 0.4528 |
| CatBoost | 0.6299 | 0.4269 | 0.4672 |

Esta prueba mide mejor el uso sobre segmentos no vistos de los mismos pacientes. La
diferencia respecto a la CV estratificada indica que la dependencia temporal entre
ventanas y la baja diversidad por paciente siguen afectando a la capacidad de
generalizacion.

## Conclusion tecnica

La ampliacion con pacientes nuevos permite una evaluacion mas honesta. En CV
estratificada, XGBoost y CatBoost superan ligeramente a Random Forest. Sin embargo,
cuando se evalua por paciente completo o por bloques temporales separados, el
rendimiento cae de forma notable. Por tanto, el siguiente paso no deberia ser hacer
mas complejo el modelo, sino aumentar la diversidad de pacientes y revisar los casos
donde se concentran los falsos positivos/falsos negativos.
