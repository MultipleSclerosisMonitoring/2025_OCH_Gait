# Comparacion de representacion espectral y temporal

Este experimento responde a la limitacion metodologica de usar solo densidades
espectrales de potencia. Se anadio una representacion temporal por ventana para
capturar estructura interna de la señal, cambios muestra a muestra y relacion
entre pies.

## Features temporales añadidas

Para cada ventana, pie y señal se calcularon:

- media, desviacion tipica, minimo, maximo, mediana, IQR y rango pico a pico;
- RMS, energia y media absoluta;
- tasa de cruces por cero tras centrar la señal;
- pendiente lineal;
- media, desviacion y maximo de diferencias consecutivas.

Tambien se añadieron magnitudes vectoriales de acelerometro y giroscopio
(`A_mag`, `G_mag`) y comparaciones entre pies: correlacion, diferencia media
absoluta, RMS de diferencia y desviacion de diferencia.

Datasets generados localmente:

- Temporal solo: `salidas_test/temporal_features/main_temporal_window_features_with_new_patients_plus_054.parquet`
- Espectral + temporal: `salidas_test/temporal_features/main_spectral_temporal_window_features_with_new_patients_plus_054.parquet`

Ambos tienen 3.372 ventanas y las mismas etiquetas que el dataset espectral
ampliado.

## CV estratificada a 3 folds

F1 macro medio por representacion:

| Representacion | Random Forest | XGBoost | CatBoost |
|---|---:|---:|---:|
| Espectral | 0.8198 | 0.8376 | 0.8387 |
| Temporal | 0.8987 | 0.9336 | 0.9333 |
| Espectral + temporal | 0.8972 | 0.9339 | 0.9353 |

La representacion temporal mejora claramente la CV estratificada. La combinacion
espectral + temporal aporta una ligera mejora adicional en CatBoost.

## Leave-one-reference-out

F1 macro medio dejando fuera una referencia/paciente completo:

| Representacion | Random Forest | XGBoost | CatBoost |
|---|---:|---:|---:|
| Espectral | 0.5633 | 0.4961 | 0.5282 |
| Temporal | 0.5645 | 0.5265 | 0.5551 |
| Espectral + temporal | 0.5702 | 0.5326 | 0.5443 |

En la validacion por paciente, las features temporales mejoran XGBoost y CatBoost
respecto al uso puramente espectral. La mejor media global en esta prueba la da
Random Forest con espectral + temporal.

## Bloques temporales con embargo de 15 s

F1 macro medio dejando fuera bloques temporales y aplicando embargo:

| Representacion | Random Forest | XGBoost | CatBoost |
|---|---:|---:|---:|
| Espectral | 0.4699 | 0.4764 | 0.4823 |
| Temporal | 0.4916 | 0.4628 | 0.4734 |
| Espectral + temporal | 0.4958 | 0.4614 | 0.4737 |

En bloques temporales, Random Forest se beneficia de añadir estructura temporal.
XGBoost y CatBoost no mejoran en esta validacion, lo que sugiere que el aumento
de dimensionalidad puede introducir variabilidad si los bloques siguen siendo
pocos.

## Conclusion

La critica del tutor era metodologicamente correcta: la representacion espectral
pura pierde informacion temporal interna de la ventana. Al añadir features
temporales, las metricas mejoran de forma clara en CV estratificada y mejoran de
forma moderada en validacion por paciente. En la validacion mas exigente por
bloques temporales, la mejora es visible sobre todo en Random Forest.

La conclusion practica es mantener la comparacion espectral vs temporal vs
espectral+temporal en la memoria. Para el modelo final clasico, la opcion mas
defendible es usar espectral + temporal con Random Forest cuando se prioriza
generalizacion por paciente/bloque, y CatBoost cuando se reporta rendimiento en
CV estratificada.
