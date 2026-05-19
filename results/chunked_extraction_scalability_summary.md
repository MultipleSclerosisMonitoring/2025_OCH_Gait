# Extraccion por chunks para rangos largos

Este cambio aborda la limitacion tecnica señalada sobre escalabilidad: el flujo
original de `ExtractApp.run_spectrogram()` carga todo el rango temporal de cada
pie antes de remuestrear y calcular ventanas. Para monitorizaciones largas esto
puede consumir demasiada memoria.

## Mejora implementada

Se añadio:

- `gait_analysis/run_chunked_spectrogram_extraction.py`

El nuevo script divide el intervalo completo en chunks temporales. Para cada
chunk:

1. consulta solo un tramo corto de InfluxDB;
2. añade solape temporal a ambos lados para no perder ventanas de borde;
3. ejecuta el extractor espectral existente;
4. conserva solo las filas cuyo `time_center` cae en el tramo central del chunk;
5. escribe incrementalmente al parquet final.

De esta forma el extractor nunca necesita cargar horas completas en memoria.

## Ejemplo de uso

```bash
poetry run python gait_analysis/run_chunked_spectrogram_extraction.py \
  -q 47046344M-104 \
  -f "2024-10-15 07:00:00" \
  -u "2024-10-15 09:00:00" \
  --config experiment_configs/config_window_1s.yaml \
  --chunk-minutes 10 \
  --overlap-seconds 5 \
  -o salidas_test/chunked_predictions/47046344M_104_2h_spectrogram.parquet
```

## Criterio de diseño

El solape debe ser al menos igual o superior a media ventana de analisis. En la
configuracion actual de ventana de 1 segundo, `--overlap-seconds 5` es
conservador y evita perder ventanas en los bordes de cada chunk.

## Alcance

Esta mejora no cambia las features ni las metricas del modelo. Mejora la
robustez operativa para inferencia o extraccion sobre rangos largos. El pipeline
antiguo sigue disponible para segmentos cortos y comparabilidad historica.

El siguiente paso, si se quiere cerrar completamente esta limitacion, seria
usar este extractor por chunks como backend de la inferencia de secuencias largas
y añadir una prueba de equivalencia contra la extraccion no chunked en un tramo
corto con Influx disponible.
