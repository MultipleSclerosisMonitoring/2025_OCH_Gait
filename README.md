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

## Robustez de ejecución

El cliente de InfluxDB se gestiona con cierre explícito mediante gestor de contexto, de modo que las conexiones HTTP se liberan al terminar cada ejecución.

La configuración YAML se valida al cargarla:

* frecuencias y duraciones deben ser positivas
* `fmax_hz` no puede superar la frecuencia de Nyquist
* `signals` y `feet` no pueden estar vacíos
* `power_scale` debe ser `db` o `linear`

El motor espectral precalcula el vector de frecuencias y la ventana de análisis una sola vez a partir de `window_s` y `resample_hz`.

Para salidas `.parquet` y `.h5` / `.hdf5`, `spectrogram` escribe por fragmentos durante el procesamiento. Esto evita acumular todo el resultado en memoria para extracciones largas. La salida `.xlsx` se mantiene como formato de inspección y se construye en memoria.

Validación específica del intervalo `PRCHUG025-11` (`2026-02-09 22:31:30` a `2026-02-09 22:45:30`) con ventana de `10 s`:

* filas HDF5 generadas: `9600`
* `Right`: `4800` filas, `800` centros
* `Left`: `4800` filas, `800` centros
* mismos `time_center` en ambos pies: sí
* rango de centros: `22:31:40.020` a `22:44:59.020`
* valores nulos: `0`

## Formatos de salida soportados en `spectrogram`

Según la extensión indicada en `--output`, actualmente se soportan:

* `.parquet`
* `.xlsx`
* `.h5` o `.hdf5`

## Contrato de datos

El contrato interno del pipeline real usa:

* columna temporal `_time`
* señales IMU con nombres `Ax`, `Ay`, `Az`, `Gx`, `Gy`, `Gz`
* etiqueta de pie en el tag configurado por `foot_tag`

Los scripts `consulta_mock.py` de raíz y `proyecto-espectrograma/consulta_mock.py` son utilidades históricas de simulación y no alimentan directamente el pipeline principal. Esos mocks usan `time` y señales en minúscula (`ax`, `ay`, etc.), por lo que no deben interpretarse como contrato actual de entrada para `gait_analysis`.

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
* preparar atributos por ventana con objetivo binario `0` / `1`

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
10. preparación del dataset final para aprendizaje automático con `target` binario

En el formato `wide`, cada fila representa un centro temporal de ventana y contiene las variables espectrales de potencia asociadas a cada combinación de pie y señal.

El dataset binario preparado conserva los identificadores de ventana, añade `target` y mantiene las columnas espectrales como atributos:

* `not_walking` => `0`
* `walking` => `1`

## Baselines iniciales

Se han ejecutado baselines simples sobre el dataset principal en formato `wide` limpio.

Dataset actual usado para clasificación:

* muestras totales: `1293`
* `not_walking`: `766`
* `walking`: `527`

Modelos comparados:

* clasificador trivial
* Logistic Regression
* Random Forest

En la versión ampliada actual del dataset, **Random Forest** obtiene mayor accuracy y mejores métricas de la clase `walking` que la Logistic Regression.

Resultados principales del dataset final actual:

* **Logistic Regression**

  * accuracy: `0.6960`
  * `F1-score (walking)`: `0.6474`
  * `recall (walking)`: `0.6849`

* **Random Forest**

  * accuracy: `0.7672`
  * `F1-score (walking)`: `0.7092`
  * `recall (walking)`: `0.6963`

La principal conclusión es que **la accuracy por sí sola no es suficiente** para evaluar este problema. La ampliación de segmentos `walking` mejora la señal útil de ambos baselines, especialmente el `F1-score` de la clase positiva.

También se ha añadido una validación más conservadora por bloques temporales completos, usando Leave-One-Group-Out sobre bloques inferidos por saltos temporales. Esta evaluación evita mezclar ventanas temporalmente contiguas entre entrenamiento y test, por lo que sus resultados son más duros:

* **Logistic Regression agrupada**

  * accuracy ponderada por filas: `0.5228`
  * `F1-score (walking)` ponderado por filas: `0.4144`
  * `recall (walking)` ponderado por filas: `0.5698`

* **Random Forest agrupado**

  * accuracy ponderada por filas: `0.5553`
  * `F1-score (walking)` ponderado por filas: `0.3918`
  * `recall (walking)` ponderado por filas: `0.5079`

Esta diferencia indica que la validación estratificada aleatoria probablemente sobreestima la generalización, porque ventanas próximas comparten mucha estructura temporal.

## Modelo final

El modelo final actual se entrena sobre todo el dataset binario preparado, usando el baseline con mejor comportamiento exploratorio: **Random Forest** con `class_weight="balanced"`.

Entrenamiento:

```bash
poetry run python gait_analysis/train_final_model.py
```

Este comando genera:

* `models/final_random_forest_model.joblib`
  Artefacto serializado con el modelo entrenado, columnas de entrada y mapa de clases.

* `results/final_model_summary.json`
  Resumen reproducible del entrenamiento, incluyendo filas, referencias, columnas de atributos y configuración del modelo.

Las métricas de rendimiento que deben reportarse siguen siendo las de validación cruzada y validación por bloques descritas en la sección anterior. Las métricas internas del resumen del modelo están calculadas sobre el conjunto completo usado para entrenar y solo sirven como comprobación de ajuste, no como estimación de generalización.

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
* `gait_analysis/run_baseline_grouped_cv.py`
* `gait_analysis/train_final_model.py`
* `gait_analysis/write_baseline_summary.py`

### Pipeline maestro

* `gait_analysis/run_main_dataset_pipeline.py`

Este script automatiza el flujo principal de:

* extracción
* etiquetado
* combinación
* paso a `wide`
* limpieza final
* generación del dataset binario por ventana

La definición versionada de los bloques usados por el dataset principal está en:

* `experiment_configs/main_dataset_windows.csv`

El pipeline se regenera con:

```text
poetry run python gait_analysis/run_main_dataset_pipeline.py
```

Los baselines principales se regeneran con:

```text
poetry run python gait_analysis/run_baseline_logreg_cv.py -i salidas_test/auto_extracts/main_combined_labeled_dataset_wide_clean.parquet
poetry run python gait_analysis/run_baseline_rf_cv.py -i salidas_test/auto_extracts/main_combined_labeled_dataset_wide_clean.parquet
poetry run python gait_analysis/run_baseline_grouped_cv.py -i salidas_test/auto_extracts/main_binary_window_features.parquet -o salidas_test/grouped_baseline_results.csv
```

El modelo final se entrena y guarda con:

```text
poetry run python gait_analysis/train_final_model.py
```

La tabla final versionada de resultados está en:

* `results/final_baseline_results.csv`

El resumen versionado del modelo final está en:

* `results/final_model_summary.json`

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

* `salidas_test/auto_extracts/main_binary_window_features.parquet`
  Dataset preparado para clasificación binaria, con `target=0` para `not_walking` y `target=1` para `walking`.

* `salidas_test/final_baseline_results_robust_pipeline.csv`
  Resumen final de resultados de baselines sobre la versión robusta del pipeline.

* `salidas_test/grouped_baseline_results.csv`
  Resultados por fold de la validación agrupada por bloques temporales.

Ficheros versionados de referencia metodológica:

* `experiment_configs/main_dataset_windows.csv`
  Definición reproducible de los bloques temporales usados por el dataset principal.

* `results/final_baseline_results.csv`
  Tabla final de resultados comparando validación estratificada aleatoria y validación agrupada por bloques temporales.

## Artefactos de referencia recomendados

En el estado actual del proyecto, los ficheros de referencia principales son:

* `experiment_configs/main_dataset_windows.csv`
* `results/final_baseline_results.csv`
* `salidas_test/ground_truth_clean.xlsx`
* `salidas_test/reference_coverage_summary.csv`
* `salidas_test/window_experiment_summary.csv`
* `salidas_test/auto_extracts/main_combined_labeled_dataset.parquet`
* `salidas_test/auto_extracts/main_combined_labeled_dataset_wide_clean.parquet`
* `salidas_test/auto_extracts/main_binary_window_features.parquet`

## Limitaciones actuales

Por ahora, las principales limitaciones detectadas son:

* número limitado de referencias con cobertura válida en InfluxDB
* dataset aún basado en pocos sujetos y bloques temporales
* integración con Grafana todavía semiautomática, no completamente automática
* el tratamiento horario completo entre Grafana, ground truth y pipeline aún no está unificado de forma general

## Siguientes pasos

Las siguientes líneas de trabajo previstas son:

* ampliar el número de referencias y bloques temporales válidos
* mejorar la cobertura útil del dataset
* validar por sujeto cuando haya más sujetos con cobertura real
* añadir atributos agregados por ventana además de las potencias espectrales
* estudiar modelos de clasificación más avanzados a partir de una base de datos más robusta
