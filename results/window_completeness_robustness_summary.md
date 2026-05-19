# Robustez frente a perdidas puntuales de señal

Este resumen responde a la critica sobre una validacion de ventanas demasiado
fragil ante fallos puntuales de telemetria.

## Politica actual del pipeline

La logica actual ya no descarta automaticamente una ventana por la aparicion de
un unico valor perdido. El pipeline aplica:

- interpolacion acotada con `spectrogram.max_interpolate_gap_s`;
- umbral minimo de completitud con `spectrogram.min_window_completeness`;
- rechazo de huecos largos que no deben inventarse por interpolacion;
- registro de `sample_completeness` en las features temporales.

Configuracion activa en `experiment_configs/config_window_1s.yaml`:

| Parametro | Valor |
|---|---:|
| `max_interpolate_gap_s` | 0.25 |
| `min_window_completeness` | 0.95 |

Esto significa que se toleran perdidas pequeñas compatibles con telemetria IoT,
pero no se rellenan desconexiones largas ni ventanas con perdida relevante.

## Evidencia en datasets actuales

Se auditaron los datasets principales:

| Dataset | Filas | Columna completitud | Media | Min | Filas < 1.00 | Filas < 0.95 |
|---|---:|---|---:|---:|---:|---:|
| Espectral + temporal ampliado | 3372 | `temp_sample_completeness` | 1.0 | 1.0 | 0 | 0 |
| Sin transiciones +/-5 s | 3298 | `temp_sample_completeness` | 1.0 | 1.0 | 0 | 0 |
| Sin transiciones + offset +2 s | 3259 | `temp_sample_completeness` | 1.0 | 1.0 | 0 | 0 |

El dataset espectral ancho antiguo no conserva una columna de completitud, por
eso aparece como `NONE` en el CSV de auditoria.

Archivo generado:

- `results/window_sample_completeness_summary.csv`

Script reproducible:

- `gait_analysis/summarize_window_completeness.py`

## Interpretacion

La critica original era valida para una politica de rechazo estricta, pero el
pipeline actual ya esta preparado para fallos pequenos de hardware. En los datos
finales usados hasta ahora, las ventanas aceptadas tienen completitud completa,
por lo que no se observa perdida parcial dentro de las ventanas conservadas.

La mejora tecnica relevante es que el sistema ya no depende de conectividad
perfecta por diseño: si aparecen huecos pequeños en nuevos pacientes, se pueden
tolerar hasta el umbral configurado; si aparecen huecos largos, la ventana se
rechaza para evitar introducir señales artificiales.
