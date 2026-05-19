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

## Validacion con Influx

Se comparo la extraccion normal contra la extraccion por chunks en un tramo
corto real:

- referencia: `47046344M-104`
- rango: `2024-10-15 07:28:58` a `2024-10-15 07:31:52`
- chunked: chunks de 1 minuto y solape de 5 segundos.

Resultados:

| Comparacion | Resultado |
|---|---:|
| Filas extraccion normal | 2064 |
| Filas chunked | 2076 |
| Filas comunes por `reference/foot/signal/time_center` | 2064 |
| Claves presentes en normal y ausentes en chunked | 0 |
| Claves extra en chunked | 12 |
| Centros temporales extra | 1 |
| Maxima diferencia absoluta en potencias comunes | 0.0 |

Las 2064 filas comunes son exactamente identicas. La extraccion por chunks
genera un centro adicional al final (`2024-10-15 07:31:51.010000+00:00`) por la
disponibilidad de borde del ultimo chunk. Esto no afecta a la equivalencia de
las ventanas compartidas y puede filtrarse si se requiere reproducir
estrictamente el comportamiento historico.

Durante la validacion se detecto que los chunks posteriores podian desplazar los
centros 10 ms si cada chunk generaba su propia rejilla desde el primer timestamp
real disponible. Se corrigio añadiendo parametros internos de anclaje:

- `--center-anchor-time`
- `--core-from-time`
- `--core-until`

El orquestador chunked usa el primer centro del primer chunk como anchor global
y fuerza a los chunks siguientes a usar esa misma secuencia de centros.
