# Mejora: control de interpolacion en huecos de sensor

## Problema abordado

El remuestreo de las senales puede crear muestras uniformes a partir de datos irregulares. Si despues se permite una interpolacion sin limite dentro de cada ventana, un hueco real de comunicacion del sensor puede transformarse en una curva suave artificial. Esa curva puede concentrar energia en bajas frecuencias y parecerse a una marcha lenta.

## Cambio implementado

Se anadio `Resampler.fill_short_window_gaps(...)` y se usa tanto en:

- `gait_analysis/app.py`, para la extraccion espectral.
- `gait_analysis/extract_temporal_window_features.py`, para las caracteristicas temporales.

La interpolacion final dentro de cada ventana ya no rellena cualquier hueco. Ahora respeta `spectrogram.max_interpolate_gap_s`:

- Huecos cortos: se pueden rellenar.
- Huecos largos: permanecen como valores ausentes.
- Si queda cualquier valor ausente despues del relleno acotado, la ventana se descarta.

## Configuracion actual

En `experiment_configs/config_window_1s.yaml`:

- `max_interpolate_gap_s: 0.25`
- `min_window_completeness: 0.95`

Esto significa que el pipeline tolera pequenas perdidas de paquetes, pero no permite que desconexiones o bloqueos mas largos se conviertan en senal sintetica utilizable para el modelo.

## Verificacion

Se compilaron los modulos modificados y se hizo una prueba sintetica con un hueco largo dentro de una ventana. El hueco no se relleno completamente, quedo `NaN` residual y por tanto la ventana seria rechazada por el pipeline.

## Impacto esperado

Esta mejora reduce el riesgo de falsos positivos generados por interpolaciones artificiales de baja frecuencia. No soluciona por si sola la falta de diversidad de pacientes, pero elimina una fuente tecnica clara de senales falsas antes de entrenar o evaluar los modelos.
