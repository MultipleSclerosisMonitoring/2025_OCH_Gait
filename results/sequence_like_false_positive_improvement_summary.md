# Mejora operativa de falsos positivos en evaluacion tipo secuencia

Antes de continuar con los siguientes comentarios del tutor, se hizo una mejora
practica centrada en el uso real del clasificador: recorrer ventanas temporales,
obtener una probabilidad de marcha y decidir con un umbral calibrado.

## Cambios realizados

- Se entreno un Random Forest final con el dataset espectral + temporal ampliado
  con nuevos pacientes:
  `models/final_random_forest_spectral_temporal_plus_054.joblib`.
- Se guardo su resumen en:
  `results/final_random_forest_spectral_temporal_plus_054_summary.json`.
- Se usaron predicciones out-of-fold por bloques temporales con embargo de 15 s,
  no predicciones sobre el mismo entrenamiento.
- Se generalizo el analizador de rachas de falsos positivos para trabajar con
  probabilidades out-of-fold, etiquetas `mov_type/target` y segmentos temporales
  inferidos.

## Efecto del umbral conservador

Comparacion sobre el mismo conjunto de predicciones out-of-fold del Random
Forest espectral + temporal:

| Umbral | Falsos positivos | FPR | Recall marcha | Precision marcha | F1 macro |
|---:|---:|---:|---:|---:|---:|
| 0.50 | 614 | 0.3728 | 0.8701 | 0.7097 | 0.7466 |
| 0.72 | 327 | 0.1985 | 0.6186 | 0.7654 | 0.7062 |

El umbral 0.72 reduce los falsos positivos en 287 ventanas respecto a 0.50
sin aplicar reglas de persistencia temporal ni consenso con Transformer. El
coste es una menor sensibilidad a ventanas de marcha.

## Negativos dificiles detectados

Con umbral 0.72 todavia quedan 55 rachas de falsos positivos. Las rachas mas
largas se concentran sobre todo en:

- `47046344M-104`, entre `2024-10-15 07:30:16` y `2024-10-15 07:31:50`;
- `04845288Q-121`, entre `2025-03-01 11:36:15` y `2025-03-01 11:37:45`;
- `47046344M-104`, alrededor de `2024-10-15 07:38:11` a `07:38:31`.

Estas rachas estan guardadas en:

- `results/false_positive_runs_rf_spectral_temporal_threshold050.csv`
- `results/false_positive_runs_rf_spectral_temporal_threshold072.csv`

## Siguiente accion tecnica

El siguiente paso para mejorar, no solo justificar, es revisar esas rachas en la
visualizacion/ground truth y convertirlas en negativos dificiles confirmados.
Si el etiquetado es correcto, se pueden usar para reentrenar o ponderar el
modelo contra patrones de no marcha que parecen marcha.

Si alguna racha esta mal etiquetada o cae en transicion real, entonces el
problema no es el modelo sino el ground truth, y debe corregirse antes de seguir
entrenando.
