# Mejora: completitud basada en muestras reales

## Problema abordado

La validacion de ventanas no debe depender solo de si una senal tiene valores despues del remuestreo, porque algunos valores pueden haber sido interpolados. Para responder al problema de fallos de telemetria, la densidad de datos debe medirse sobre muestras realmente observadas.

## Cambio implementado

`Resampler.resample_dataframe(...)` crea ahora columnas de mascara:

- `observed_Ax`
- `observed_Ay`
- `observed_Az`
- `observed_Gx`
- `observed_Gy`
- `observed_Gz`

Estas columnas se calculan justo despues del remuestreo y antes de cualquier interpolacion. Por tanto, indican si habia una muestra real en cada bin temporal.

Se anadio tambien:

- `Resampler.window_sample_completeness(...)`

Esta funcion calcula la completitud de una ventana usando primero las columnas `observed_*`. Si se procesa un dataframe antiguo sin mascaras, mantiene compatibilidad usando la densidad de valores no nulos.

## Uso en el pipeline

La validacion de ventanas usa ahora completitud real en:

- `gait_analysis/app.py`, para espectros.
- `gait_analysis/extract_temporal_window_features.py`, para caracteristicas temporales.

Despues de esa comprobacion, los huecos cortos pueden interpolarse, pero los huecos largos siguen quedando ausentes y la ventana se descarta.

## Verificacion

Se hizo una prueba sintetica con una senal remuestreada donde faltaban muestras reales. Tras la interpolacion:

- valores no nulos despues de interpolar: `8/8`
- muestras realmente observadas: `6/8`
- completitud real reportada: `0.75`
- completitud ingenua por valores no nulos: `1.0`

Esto confirma que el pipeline ya no confunde datos interpolados con datos realmente medidos.

## Impacto esperado

La extraccion tolera pequenas perdidas de paquetes, pero evita aceptar ventanas donde la senal parece completa solo porque fue rellenada matematicamente. Esto reduce el riesgo de entrenar o evaluar con patrones de baja frecuencia generados por huecos de telemetria.
