# 2025_OCH_Gait

## Descripción general

Este proyecto extrae señales de marcha desde InfluxDB y genera representaciones espectrales para su análisis posterior.

Actualmente el pipeline permite:

* contar registros por pie
* generar espectros de potencia a partir de señales IMU
* exportar resultados en formato `.parquet`, `.xlsx` y `.h5/.hdf5`
* asignar etiquetas temporales de ground truth a ventanas espectrales
* combinar datasets etiquetados válidos
* transformar datasets al formato tabular `wide` para aprendizaje automático
* ejecutar baselines simples de clasificación

La lógica principal está organizada dentro del paquete `gait_analysis/`.

## Entorno y dependencias

El proyecto usa **Poetry** para la gestión de dependencias.

Los ejemplos de este README utilizan comandos genéricos del entorno de Poetry:

```bash
poetry run python ...
```

## Configuración

Debe existir un fichero `.config.yaml` en la raíz del proyecto. En él se definen:

* la conexión a InfluxDB
* los nombres de los tags usados en las consultas
* la gestión temporal
* los parámetros del espectrograma

La configuración actual del espectrograma procesa estas señales IMU:

* acelerómetro: `Ax`, `Ay`, `Az`
* giroscopio: `Gx`, `Gy`, `Gz`

para ambos pies:

* `Right`
* `Left`

## Tratamiento horario

Las fechas introducidas por CLI se interpretan según la configuración temporal actual del proyecto y se envían a InfluxDB preservando la hora escrita por el usuario en el rango solicitado.

Este comportamiento es el que mantiene la compatibilidad con el dataset histórico y con la generación actual de espectrogramas usada en el pipeline principal.

Al comparar directamente con Grafana, puede observarse un desfase respecto a la hora local mostrada en la interfaz. La unificación completa del tratamiento horario entre Grafana, ground truth y pipeline queda como una mejora futura del proyecto.

## Modos principales de ejecución

### 1. Modo `count`

Se utiliza para comprobar que la extracción desde InfluxDB funciona correctamente.

Ejemplo:

```bash
poetry run python extract_influx_hdf5.py \
-f "2025-07-01 14:08:20" \
-u "2025-07-01 14:08:40" \
-q "TESTPATIENT-98" \
--mode count \
-v
```

Salida esperada:

```text
=== Pie: Right ===
Flux query enviada a Influx:
...
Registros obtenidos de InfluxDB: N

=== Pie: Left ===
Flux query enviada a Influx:
...
Registros obtenidos de InfluxDB: M
```

### 2. Modo `spectrogram`

Genera espectros de potencia usando ventanas deslizantes centradas.

Configuración actual por defecto:

* longitud de ventana: `10 s`
* paso temporal: `1 s`
* frecuencia máxima: `5 Hz`
* tipo de ventana: `hann`
* escala de potencia: `db`

Ejemplo:

```bash
poetry run python extract_influx_hdf5.py \
-f "2025-07-01 14:08:20" \
-u "2025-07-01 14:08:40" \
-q "TESTPATIENT-98" \
--mode spectrogram \
-o "salidas_test/test_full_imu.parquet" \
-v
```

### Comportamiento actual del modo `spectrogram`

El pipeline actual de espectrogramas trabaja de forma robusta sobre ambos pies:

* carga `Right` y `Left` por separado
* remuestrea ambos pies a una frecuencia común
* calcula la **intersección temporal real** entre ambos pies y el intervalo solicitado
* construye una **base temporal común**
* genera centros de ventana solo donde la ventana completa cabe dentro de la intersección
* conserva únicamente ventanas **completas y comparables**
* emite filas con los mismos `time_center` en ambos pies

Este comportamiento evita ventanas parciales al final del rango y permite comparar ambos pies sobre una base temporal emparejada.

## Formatos de salida soportados en `spectrogram`

Según la extensión indicada en `--output`, actualmente se soportan:

* `.parquet`
* `.xlsx`
* `.h5` o `.hdf5`

## Utilidades de ground truth

El proyecto incluye scripts auxiliares para preparar y analizar el ground truth:

* `gait_analysis/build_ground_truth_template.py`
* `gait_analysis/import_ground_truth_table.py`
* `gait_analysis/build_ground_truth_excel.py`
* `gait_analysis/build_window_configs.py`
* `gait_analysis/summarize_window_experiments.py`
* `gait_analysis/label_spectrogram_with_ground_truth.py`
* `gait_analysis/summarize_labeled_spectrogram.py`
* `gait_analysis/combine_labeled_datasets.py`
* `gait_analysis/build_wide_dataset.py`
* `gait_analysis/inspect_wide_dataset.py`
* `gait_analysis/clean_wide_dataset.py`
* `gait_analysis/prepare_ml_dataset.py`

Estos scripts permiten:

* generar una plantilla Excel de ground truth con intervalos temporales fijos para su etiquetado manual posterior usando Grafana
* importar tablas exportadas y adaptarlas al formato estándar del proyecto
* limpiar y normalizar Excels de etiquetas de marcha
* preparar configuraciones para distintas longitudes de ventana
* resumir experimentos comparativos entre ventanas
* asignar etiquetas `walking` / `not_walking` a ventanas espectrales
* conservar o filtrar ventanas `NO_LABEL`
* combinar varios datasets etiquetados
* transformar datasets etiquetados de formato `long` a formato `wide`
* inspeccionar datasets preparados para ML
* limpiar datasets `wide` eliminando filas con valores faltantes
* preparar matrices de entrada y vectores objetivo para baselines

## Integración con Grafana

El proyecto soporta un flujo semiautomático para construir ground truth a partir de datos exportados desde Grafana.

Flujo actual:

1. inspección visual o exportación de datos desde un panel de Grafana
2. exportación de la tabla en formato CSV o Excel
3. adaptación al formato estándar del proyecto mediante `gait_analysis/import_ground_truth_table.py`
4. limpieza y normalización final con `gait_analysis/build_ground_truth_excel.py`

Este flujo permite convertir tablas exportadas desde Grafana al formato interno de ground truth usado por el pipeline:

* `Reference`
* `datefrom`
* `dateuntil`
* `mov_type`

La integración actual es **semiautomática**: Grafana se utiliza como fuente de datos exportables o apoyo visual para etiquetado, pero la construcción final del ground truth todavía requiere una fase intermedia de importación/normalización dentro del proyecto.

## Pipeline actual de etiquetado y preparación para ML

El flujo actual de preparación de datos incluye:

1. extracción de señales desde InfluxDB
2. generación de espectrogramas con IMU completa en ambos pies
3. alineación temporal robusta entre ambos pies
4. asignación de etiquetas temporales desde el ground truth limpio
5. marcaje de ventanas ambiguas como `NO_LABEL`
6. filtrado opcional de dichas ventanas
7. combinación de referencias válidas y bloques temporales válidos
8. transformación del dataset a formato `wide`
9. limpieza del dataset `wide`
10. preparación del dataset final para aprendizaje automático

En el formato `wide`, cada fila representa un centro temporal de ventana y contiene las variables espectrales de potencia asociadas a cada combinación de pie y señal.

## Baselines iniciales

Se han ejecutado baselines simples sobre el dataset principal en formato `wide` limpio.

Dataset actual usado para clasificación:

* muestras totales: `844`
* `not_walking`: `616`
* `walking`: `228`

Modelos comparados:

* clasificador trivial
* Logistic Regression
* Random Forest

En la versión robusta actual del dataset, la **Logistic Regression** se mantiene como el baseline más útil para este problema, ya que ofrece mejor capacidad para detectar la clase `walking`.

Resultados principales del dataset final actual:

* **Logistic Regression**

  * accuracy: `0.7145`
  * `F1-score (walking)`: `0.5503`
  * `recall (walking)`: `0.6494`

* **Random Forest**

  * accuracy: `0.7891`
  * `F1-score (walking)`: `0.4982`
  * `recall (walking)`: `0.3901`

La principal conclusión es que **la accuracy por sí sola no es suficiente** para evaluar este problema. Aunque Random Forest obtiene mayor accuracy, Logistic Regression detecta mejor la clase `walking`, por lo que actualmente se considera el baseline principal del proyecto.

## Documentación

La documentación con Sphinx está en:

```text
docs/
```

La versión HTML generada se encuentra en:

```text
docs/build/html
```

## Estado actual

En el estado actual del proyecto ya se dispone de:

* filtrado por paciente mediante `CodeID`
* extracción por pie
* espectros para acelerómetro y giroscopio
* exportación en varios formatos
* limpieza y normalización básica de ground truth
* preparación de experimentos con distintas ventanas temporales
* etiquetado temporal de espectrogramas
* combinación de datasets etiquetados
* transformación a formato `wide` para ML
* limpieza de datasets `wide`
* preparación e inspección de datasets para clasificación
* baselines iniciales de clasificación
* integración semiautomática con Grafana para el ground truth
* documentación Sphinx con diagrama de arquitectura
* alineación temporal robusta entre ambos pies, con ventanas completas y base temporal común

## Mapa actual del proyecto

### Ejecución principal

Punto de entrada principal:

* `extract_influx_hdf5.py`

Módulos base del paquete:

* `gait_analysis/app.py`
* `gait_analysis/cli.py`
* `gait_analysis/config.py`
* `gait_analysis/flux.py`
* `gait_analysis/influx_service.py`
* `gait_analysis/models.py`
* `gait_analysis/resampling.py`
* `gait_analysis/spectrum.py`
* `gait_analysis/time_utils.py`

### Utilidades de ground truth

* `gait_analysis/build_ground_truth_template.py`
* `gait_analysis/import_ground_truth_table.py`
* `gait_analysis/build_ground_truth_excel.py`
* `gait_analysis/build_window_configs.py`
* `gait_analysis/summarize_window_experiments.py`
* `gait_analysis/label_spectrogram_with_ground_truth.py`

### Utilidades de preparación de datasets

* `gait_analysis/summarize_labeled_spectrogram.py`
* `gait_analysis/combine_labeled_datasets.py`
* `gait_analysis/build_wide_dataset.py`
* `gait_analysis/inspect_wide_dataset.py`
* `gait_analysis/clean_wide_dataset.py`
* `gait_analysis/prepare_ml_dataset.py`

### Utilidades de baselines

* `gait_analysis/run_baseline_logreg.py`
* `gait_analysis/run_baseline_logreg_cv.py`
* `gait_analysis/run_baseline_rf_cv.py`
* `gait_analysis/write_baseline_summary.py`

### Pipeline maestro

* `gait_analysis/run_main_dataset_pipeline.py`

Este script automatiza el flujo principal de:

* extracción
* etiquetado
* combinación
* paso a `wide`
* limpieza final

## Artefactos principales generados

Ficheros relevantes generados actualmente en `salidas_test/` y `salidas_test/auto_extracts/`:

* `salidas_test/ground_truth_clean.xlsx`
  Ground truth limpio.

* `salidas_test/ground_truth_clean_overlaps.csv`
  Solapes temporales detectados en el ground truth.

* `salidas_test/reference_coverage_summary.csv`
  Resumen de referencias con cobertura utilizable en InfluxDB.

* `salidas_test/window_experiment_summary.csv`
  Resumen de los experimentos con distintas longitudes de ventana.

* `salidas_test/auto_extracts/main_combined_labeled_dataset.parquet`
  Dataset combinado etiquetado en formato `long`.

* `salidas_test/auto_extracts/main_combined_labeled_dataset_wide.parquet`
  Dataset en formato `wide`.

* `salidas_test/auto_extracts/main_combined_labeled_dataset_wide_clean.parquet`
  Dataset limpio en formato `wide` usado para los baselines actuales.

* `salidas_test/final_baseline_results_robust_pipeline.csv`
  Resumen final de resultados de baselines sobre la versión robusta del pipeline.

## Artefactos de referencia recomendados

En el estado actual del proyecto, los ficheros de referencia principales son:

* `salidas_test/ground_truth_clean.xlsx`
* `salidas_test/reference_coverage_summary.csv`
* `salidas_test/window_experiment_summary.csv`
* `salidas_test/auto_extracts/main_combined_labeled_dataset.parquet`
* `salidas_test/auto_extracts/main_combined_labeled_dataset_wide_clean.parquet`
* `salidas_test/final_baseline_results_robust_pipeline.csv`

## Limitaciones actuales

Por ahora, las principales limitaciones detectadas son:

* número limitado de referencias con cobertura válida en InfluxDB
* desbalance entre las clases `walking` y `not_walking`
* integración con Grafana todavía semiautomática, no completamente automática
* el tratamiento horario completo entre Grafana, ground truth y pipeline aún no está unificado de forma general

## Siguientes pasos

Las siguientes líneas de trabajo previstas son:

* ampliar el número de referencias y bloques temporales válidos
* mejorar la cobertura útil del dataset
* construir atributos por ventana a partir de los HDF5/parquets ya alineados entre pies
* preparar el siguiente paso de clasificación binaria `0 => no marcha`, `1 => sí marcha`
* estudiar modelos de clasificación más avanzados a partir de una base de datos más robusta

