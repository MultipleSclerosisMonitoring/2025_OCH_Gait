# Mejora: ingesta por chunks en el pipeline principal

## Problema abordado

El flujo principal de construccion del dataset podia invocar el extractor directo para un rango temporal completo. En monitorizaciones largas, esto obliga a consultar y remuestrear todo el intervalo de una vez antes de generar las ventanas, aumentando el riesgo de consumo excesivo de memoria.

## Estado previo

Ya existia un extractor por chunks:

- `gait_analysis/run_chunked_spectrogram_extraction.py`

Ese extractor divide el intervalo completo en tramos temporales, consulta cada chunk con solape, conserva solo el tramo central y escribe incrementalmente el parquet final. Tambien se valido previamente su equivalencia frente al extractor directo en las filas comunes.

## Cambio realizado

El pipeline principal `gait_analysis/run_main_dataset_pipeline.py` usa ahora la extraccion por chunks por defecto.

Parametros nuevos:

- `--chunk-minutes`: duracion central de cada chunk. Por defecto, `10`.
- `--chunk-overlap-seconds`: solape consultado a ambos lados. Por defecto, `5`.
- `--direct-extraction`: opcion de compatibilidad para usar el extractor directo antiguo.

## Impacto esperado

La generacion del dataset principal queda alineada con la recomendacion de procesar rangos largos de forma paginada. Esto evita cargar monitorizaciones prolongadas completas en memoria y mantiene el comportamiento de ventanas gracias al solape y al anclaje global de centros temporales.
