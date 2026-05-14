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
* XGBoost
* CatBoost

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

También se ha añadido una comparación de modelos de aprendizaje automático con **Cross Validation estratificada de 3 folds**, siguiendo la evaluación solicitada para Random Forest, XGBoost y CatBoost. En esta comparación se calculan accuracy, precision, recall y F1-score, incluyendo media y desviación estándar por modelo.

Resultados principales para la clase `walking`:

* **Random Forest conservador**

  * accuracy: `0.7394 ± 0.0117`
  * precision (`walking`): `0.6497 ± 0.0205`
  * recall (`walking`): `0.7856 ± 0.0327`
  * `F1-score (walking)`: `0.7107 ± 0.0101`

* **XGBoost**

  * accuracy: `0.7618 ± 0.0119`
  * precision (`walking`): `0.6886 ± 0.0106`
  * recall (`walking`): `0.7590 ± 0.0481`
  * `F1-score (walking)`: `0.7216 ± 0.0221`

* **CatBoost**

  * accuracy: `0.7579 ± 0.0149`
  * precision (`walking`): `0.6847 ± 0.0118`
  * recall (`walking`): `0.7534 ± 0.0597`
  * `F1-score (walking)`: `0.7166 ± 0.0265`

En esta comparación, XGBoost obtiene el mejor rendimiento medio en accuracy y F1-score de la clase `walking`, aunque Random Forest conserva el mejor recall medio para detectar marcha.

## Modelo final

El modelo final actual se entrena sobre todo el dataset binario preparado, usando una versión conservadora del baseline con mejor comportamiento exploratorio: **Random Forest** con `class_weight="balanced"`, profundidad limitada y hojas mínimas de 10 muestras para reducir sobreajuste entre ventanas próximas.

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

La evaluación reportable del modelo final se genera con:

```bash
poetry run python gait_analysis/evaluate_final_model.py
```

Esta evaluación usa Leave-One-Group-Out por bloques temporales completos y genera:

* `results/final_model_evaluation.json`
  Resumen agregado con métricas out-of-fold, matriz de confusión e informe de clasificación.

* `results/final_model_grouped_cv_results.csv`
  Métricas por bloque temporal.

* `results/final_model_grouped_cv_predictions.csv`
  Predicciones out-of-fold por ventana.

* `results/final_model_feature_importances.csv`
  Importancia de las variables del Random Forest final.

Resultados principales de la evaluación por bloques del modelo final:

* accuracy out-of-fold: `0.5800`
* `F1-score (walking)` out-of-fold: `0.6079`
* recall out-of-fold (`walking`): `0.7989`
* matriz de confusión (`not_walking`, `walking`): `[[329, 437], [106, 421]]`

La inferencia sobre una secuencia temporal se ejecuta con:

```bash
poetry run python gait_analysis/predict_walking_sequence.py \
  -q "47046344M-104" \
  -f "2024-10-15 07:47:57" \
  -u "2024-10-15 07:48:44" \
  -o salidas_test/sequence_predictions/predictions.csv
```

Este comando aplica la forma de uso final del clasificador: extrae una secuencia temporal de datos IMU, recorre la señal con la ventana móvil configurada, calcula las características espectrales y devuelve una tabla temporal con:

* `time_center`
* `prediction`
* `prediction_label`
* `walking_probability`

Si el espectrograma ya se ha extraído previamente, se puede omitir la consulta a InfluxDB con `--spectrogram-input`.

Cuando existan segmentos marcados como `use_for_sequence_eval=True` en `experiment_configs/sequence_evaluation_windows.csv`, la evaluación automática contra ground truth se ejecuta con:

```bash
poetry run python -m gait_analysis.run_sequence_evaluation
```

Este script lanza la inferencia por ventana móvil para cada segmento, cruza cada `time_center` con `ground_truth_clean.xlsx` y genera métricas por segmento y agregadas.

Con las ventanas válidas comprobadas en InfluxDB, la primera evaluación secuencial genera 820 ventanas temporales evaluadas. El resultado agregado actual es:

* accuracy: `0.2341`
* precision (`walking`): `0.0188`
* recall (`walking`): `1.0000`
* F1-score (`walking`): `0.0368`
* matriz de confusión (`not_walking`, `walking`): `[[180, 628], [0, 12]]`

Estos resultados confirman que el clasificador conserva sensibilidad para detectar marcha, pero produce demasiados falsos positivos sobre segmentos de no marcha cuando se aplica como ventana móvil en secuencia temporal.

Para analizar este comportamiento sin volver a consultar InfluxDB, se puede recalcular la decisión final a partir de `walking_probability` probando varios umbrales:

```bash
poetry run python -m gait_analysis.tune_sequence_threshold
```

El barrido inicial muestra que el umbral `0.65` mejora el equilibrio actual frente al umbral por defecto `0.50`:

* umbral `0.50`: accuracy `0.2341`, precision `0.0188`, recall `1.0000`, F1 `0.0368`, falsos positivos `628`
* umbral `0.65`: accuracy `0.6061`, precision `0.0245`, recall `0.6667`, F1 `0.0472`, falsos positivos `319`

El ajuste reduce de forma clara los falsos positivos, aunque todavía mantiene una precision baja. Por tanto, el siguiente refinamiento metodológico debe incorporar suavizado temporal o reglas de persistencia para evitar que ventanas aisladas activen una predicción de marcha.

También se ha evaluado una regla de persistencia temporal: primero se aplica el umbral sobre `walking_probability` y después solo se aceptan como marcha los bloques con al menos `N` ventanas positivas consecutivas. El barrido se ejecuta con:

```bash
poetry run python -m gait_analysis.tune_sequence_temporal_smoothing
```

La mejor combinación del barrido actual es `threshold=0.65` y `min_run_windows=2`:

* accuracy: `0.6695`
* precision (`walking`): `0.0291`
* recall (`walking`): `0.6667`
* F1-score (`walking`): `0.0557`
* falsos positivos: `267`
* matriz de confusión (`not_walking`, `walking`): `[[541, 267], [4, 8]]`

Frente al umbral `0.65` sin suavizado, la regla temporal reduce los falsos positivos de `319` a `267` sin perder más verdaderos positivos. Aun así, la precisión sigue siendo limitada, por lo que este resultado debe reportarse como una mejora parcial y no como solución definitiva.

Para aproximar la evaluación pedida por el tutor, también se ha construido una secuencia concatenada con segmentos de marcha y no marcha no usados de pacientes ya vistos:

```bash
poetry run python -m gait_analysis.build_stitched_sequence_evaluation
```

El script toma los segmentos válidos de `sequence_evaluation_windows.csv`, concatena sus predicciones por ventana en una línea temporal sintética y aplica la regla final `threshold=0.65`, `min_run_windows=2`. Para los segmentos de mismos pacientes disponibles actualmente:

* segmentos concatenados: `4`
* ventanas evaluadas: `388`
* accuracy: `0.6366`
* precision (`walking`): `0.0552`
* recall (`walking`): `0.6667`
* F1-score (`walking`): `0.1019`
* matriz de confusión (`not_walking`, `walking`): `[[239, 137], [4, 8]]`

Este experimento ya produce la salida temporal solicitada (`t`, etiqueta real, predicción y probabilidad), guardada en `results/stitched_sequence_predictions.csv`. Debe interpretarse con cautela porque el conjunto disponible tiene muchos más puntos de no marcha que de marcha y solo un tramo corto de marcha válido para esta prueba.

Como los falsos positivos siguen siendo altos, se ha añadido un barrido específico de reglas más conservadoras:

```bash
poetry run python -m gait_analysis.tune_stitched_sequence_smoothing
```

En los segmentos concatenados de mismos pacientes, el mejor F1 sigue apareciendo con `threshold=0.65`, `min_run_windows=2`. Si se exige conservar al menos `recall >= 0.50`, la opción más conservadora es `threshold=0.65`, `min_run_windows=3`:

* falsos positivos: baja de `137` a `121`
* verdaderos positivos: baja de `8` a `6`
* recall (`walking`): baja de `0.6667` a `0.5000`
* F1-score (`walking`): baja de `0.1019` a `0.0863`
* matriz de confusión (`not_walking`, `walking`): `[[255, 121], [6, 6]]`

Por tanto, aumentar la persistencia temporal reduce falsos positivos, pero empieza a eliminar marcha real. Las configuraciones que dejan los falsos positivos en `0` también dejan los verdaderos positivos en `0`, por lo que no son útiles como detector de marcha.

La evaluación separada en pacientes totalmente nuevos se ejecuta con:

```bash
poetry run python -m gait_analysis.build_stitched_sequence_evaluation \
  --scope new_patient \
  --predictions-output results/stitched_sequence_predictions_new_patient.csv \
  --summary-output results/stitched_sequence_summary_new_patient.csv
```

Con los datos disponibles actualmente solo hay un segmento válido de paciente nuevo, y corresponde a `not_walking`; los candidatos de marcha de pacientes nuevos no tienen datos válidos de ambos pies en InfluxDB. Por tanto, esta evaluación mide de momento la tasa de falsos positivos en paciente nuevo, no la capacidad de detectar marcha en paciente nuevo:

* segmentos concatenados: `1`
* ventanas evaluadas: `432`
* accuracy: `0.6991`
* verdaderos negativos: `302`
* falsos positivos: `130`
* matriz de confusión (`not_walking`, `walking`): `[[302, 130], [0, 0]]`

Con `min_run_windows=3`, los falsos positivos bajan de `130` a `102`, pero no es posible seleccionar una regla final solo con este segmento porque no contiene ningún positivo real. Las reglas que dejan `0` falsos positivos en paciente nuevo equivalen a no predecir marcha en ese tramo. Para cerrar completamente este punto faltan segmentos válidos de `walking` en pacientes nuevos.

La tabla final consolidada de la parte clásica de ML y evaluación secuencial se genera con:

```bash
poetry run python -m gait_analysis.build_final_ml_sequence_summary
```

El fichero resultante es `results/final_ml_sequence_summary.csv`. La conclusión principal es que las técnicas clásicas obtienen resultados razonables en validación estratificada aleatoria, pero su rendimiento baja al usar bloques temporales y cae de forma clara al aplicarlas sobre secuencias reales mediante ventana móvil. El ajuste de umbral y la persistencia temporal reducen falsos positivos, pero no resuelven completamente la baja precisión; esto justifica pasar a modelos secuenciales, como transformers, que puedan aprovechar mejor la dependencia temporal entre ventanas.

## Dataset secuencial para transformers

El primer paso para los modelos tipo transformer es transformar las ventanas tabulares independientes en secuencias temporales. El dataset secuencial se genera con:

```bash
poetry run python -m gait_analysis.build_transformer_sequence_dataset
```

La configuración inicial usa secuencias de `9` ventanas consecutivas y asigna como etiqueta la ventana central. No se cruzan pacientes ni bloques separados por huecos temporales, por lo que cada secuencia pertenece a un único bloque temporal.

Artefactos generados:

* `salidas_test/auto_extracts/transformer_sequence_dataset_len9.npz`
  Tensor `X` con forma `(1205, 9, 72)` y vector `y`.
* `salidas_test/auto_extracts/transformer_sequence_dataset_len9_metadata.csv`
  Metadatos por secuencia: referencia, bloque temporal, instante central y etiqueta.
* `results/transformer_sequence_dataset_summary.json`
  Resumen versionado del dataset secuencial.

El resumen actual contiene `1205` secuencias: `726` de `not_walking` y `479` de `walking`. Para entrenar transformers se debe usar la columna `group` de los metadatos como unidad de validación, evitando mezclar secuencias de un mismo bloque temporal entre entrenamiento y test.

El baseline inicial con transformer se entrena con:

```bash
poetry run python -m gait_analysis.train_transformer_sequence_classifier
```

El modelo usa un `TransformerEncoder` pequeño con contexto de 9 ventanas y se evalúa con Leave-One-Group-Out sobre bloques temporales. Los resultados out-of-fold actuales son:

* accuracy: `0.5378`
* precision (`walking`): `0.4470`
* recall (`walking`): `0.6868`
* F1-score (`walking`): `0.5416`
* matriz de confusión (`not_walking`, `walking`): `[[319, 407], [150, 329]]`

También se ha probado un barrido de umbrales sobre las probabilidades out-of-fold del transformer:

```bash
poetry run python -m gait_analysis.tune_transformer_sequence_threshold
```

El mejor F1 aparece con umbral `0.01`:

* accuracy: `0.5071`
* precision (`walking`): `0.4347`
* recall (`walking`): `0.7996`
* F1-score (`walking`): `0.5632`
* matriz de confusión (`not_walking`, `walking`): `[[228, 498], [96, 383]]`

Este primer transformer mejora claramente la aplicación secuencial directa del Random Forest, pero todavía no supera al Random Forest evaluado por bloques temporales (`F1 walking = 0.6079`). El barrido de umbral mejora el recall y el F1, aunque confirma que las probabilidades están mal calibradas y todavía hay muchos falsos positivos. La lectura actual es que el enfoque secuencial es viable, pero el dataset sigue siendo pequeño para entrenar modelos neuronales con buena generalización.

Para reducir sobreajuste, se ha añadido una variante con early stopping usando un grupo temporal interno de validación dentro de cada fold:

```bash
poetry run python -m gait_analysis.train_transformer_sequence_classifier --validation-mode group
```

Esta variante mejora el resultado del transformer:

* accuracy: `0.5983`
* precision (`walking`): `0.4964`
* recall (`walking`): `0.7161`
* F1-score (`walking`): `0.5863`
* matriz de confusión (`not_walking`, `walking`): `[[378, 348], [136, 343]]`

Sigue ligeramente por debajo del Random Forest por bloques, pero reduce la distancia (`0.5863` frente a `0.6079`) y confirma que una validación interna más estricta mejora la generalización del modelo secuencial.

La mejor variante actual reduce además la capacidad del modelo (`d_model=16`, `dim_feedforward=32`) y aumenta la regularización (`dropout=0.3`):

```bash
poetry run python -m gait_analysis.train_transformer_sequence_classifier \
  --validation-mode group \
  --d-model 16 \
  --nhead 4 \
  --dim-feedforward 32 \
  --dropout 0.3
```

Resultados:

* accuracy: `0.6091`
* precision (`walking`): `0.5057`
* recall (`walking`): `0.7349`
* F1-score (`walking`): `0.5991`
* matriz de confusión (`not_walking`, `walking`): `[[382, 344], [127, 352]]`

Esta configuración queda muy cerca del Random Forest por bloques (`0.5991` frente a `0.6079`) y mejora al transformer anterior tanto en F1 como en precision, recall y accuracy.

Se ha añadido una regularización adicional con `label_smoothing=0.05`:

```bash
poetry run python -m gait_analysis.train_transformer_sequence_classifier \
  --validation-mode group \
  --d-model 16 \
  --nhead 4 \
  --dim-feedforward 32 \
  --dropout 0.3 \
  --label-smoothing 0.05
```

Sin ajustar el umbral, esta variante ya supera ligeramente al Random Forest por bloques:

* accuracy: `0.6133`
* precision (`walking`): `0.5091`
* recall (`walking`): `0.7578`
* F1-score (`walking`): `0.6091`
* matriz de confusión (`not_walking`, `walking`): `[[376, 350], [116, 363]]`

Después, al ajustar el umbral de decisión sobre las probabilidades out-of-fold, el mejor valor aparece con `threshold=0.43`:

* accuracy: `0.6133`
* precision (`walking`): `0.5084`
* recall (`walking`): `0.8246`
* F1-score (`walking`): `0.6290`
* matriz de confusión (`not_walking`, `walking`): `[[344, 382], [84, 395]]`

Esta es la mejor configuración secuencial actual. Supera al Random Forest por bloques en F1 de la clase `walking`, aunque a costa de mantener un número considerable de falsos positivos.

Para reducir esos falsos positivos se ha añadido un postprocesado temporal sobre las probabilidades out-of-fold del transformer:

```bash
poetry run python -m gait_analysis.tune_transformer_temporal_smoothing
```

El mejor compromiso actual aparece con `threshold=0.43` y `min_run_windows=8`:

* accuracy: `0.6456`
* precision (`walking`): `0.5385`
* recall (`walking`): `0.7599`
* F1-score (`walking`): `0.6303`
* matriz de confusión (`not_walking`, `walking`): `[[414, 312], [115, 364]]`

Frente al ajuste de umbral sin suavizado, los falsos positivos bajan de `382` a `312` y el F1 sube ligeramente de `0.6290` a `0.6303`. Si se prioriza todavía más reducir falsos positivos, la combinación `threshold=0.49` y `min_run_windows=10` baja los falsos positivos a `280`, con F1 `0.6162`.

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
* `gait_analysis/build_transformer_sequence_dataset.py`

### Utilidades de baselines

* `gait_analysis/run_baseline_logreg.py`
* `gait_analysis/run_baseline_logreg_cv.py`
* `gait_analysis/run_baseline_rf_cv.py`
* `gait_analysis/run_baseline_grouped_cv.py`
* `gait_analysis/run_ml_model_comparison_cv3.py`
* `gait_analysis/train_final_model.py`
* `gait_analysis/evaluate_final_model.py`
* `gait_analysis/predict_walking_sequence.py`
* `gait_analysis/run_sequence_evaluation.py`
* `gait_analysis/build_stitched_sequence_evaluation.py`
* `gait_analysis/train_transformer_sequence_classifier.py`
* `gait_analysis/tune_stitched_sequence_smoothing.py`
* `gait_analysis/tune_transformer_sequence_threshold.py`
* `gait_analysis/tune_transformer_temporal_smoothing.py`
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

La comparativa de Random Forest, XGBoost y CatBoost con Cross Validation de 3 folds se regenera con:

```text
poetry run python gait_analysis/run_ml_model_comparison_cv3.py
```

El modelo final se entrena y guarda con:

```text
poetry run python gait_analysis/train_final_model.py
```

La evaluación reportable del modelo final se genera con:

```text
poetry run python gait_analysis/evaluate_final_model.py
```

La inferencia por ventana móvil sobre una secuencia temporal se ejecuta con:

```text
poetry run python gait_analysis/predict_walking_sequence.py -q "47046344M-104" -f "2024-10-15 07:47:57" -u "2024-10-15 07:48:44" -o salidas_test/sequence_predictions/predictions.csv
```

La evaluación automática de los segmentos configurados en `sequence_evaluation_windows.csv` se ejecuta con:

```text
poetry run python -m gait_analysis.run_sequence_evaluation --threshold 0.65
```

El barrido de umbrales sobre predicciones ya guardadas se ejecuta con:

```text
poetry run python -m gait_analysis.tune_sequence_threshold
```

El barrido de suavizado temporal por persistencia se ejecuta con:

```text
poetry run python -m gait_analysis.tune_sequence_temporal_smoothing
```

La evaluación con segmentos no vistos concatenados se ejecuta con:

```text
poetry run python -m gait_analysis.build_stitched_sequence_evaluation
```

La evaluación separada sobre pacientes nuevos se ejecuta con:

```text
poetry run python -m gait_analysis.build_stitched_sequence_evaluation --scope new_patient
```

El barrido conservador sobre la secuencia concatenada se ejecuta con:

```text
poetry run python -m gait_analysis.tune_stitched_sequence_smoothing
```

La tabla final consolidada de ML clásico y evaluación secuencial se genera con:

```text
poetry run python -m gait_analysis.build_final_ml_sequence_summary
```

El dataset secuencial para transformers se genera con:

```text
poetry run python -m gait_analysis.build_transformer_sequence_dataset
```

El baseline transformer se entrena y evalúa con:

```text
poetry run python -m gait_analysis.train_transformer_sequence_classifier
```

La variante transformer con validación interna por grupo se ejecuta con:

```text
poetry run python -m gait_analysis.train_transformer_sequence_classifier --validation-mode group
```

El barrido de umbrales del transformer se ejecuta con:

```text
poetry run python -m gait_analysis.tune_transformer_sequence_threshold
```

El suavizado temporal del transformer para reducir falsos positivos se ejecuta con:

```text
poetry run python -m gait_analysis.tune_transformer_temporal_smoothing
```

La tabla final versionada de resultados está en:

* `results/final_baseline_results.csv`
* `results/final_ml_sequence_summary.csv`

La comparativa versionada de modelos ML con CV=3 está en:

* `results/ml_model_comparison_cv3_folds.csv`
* `results/ml_model_comparison_cv3_summary.csv`

El resumen versionado del modelo final está en:

* `results/final_model_summary.json`

Los artefactos versionados de evaluación del modelo final están en:

* `results/final_model_evaluation.json`
* `results/final_model_grouped_cv_results.csv`
* `results/final_model_grouped_cv_predictions.csv`
* `results/final_model_feature_importances.csv`

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

* `experiment_configs/sequence_evaluation_windows.csv`
  Candidatos no vistos para evaluar la inferencia por ventana móvil sobre secuencias temporales. Incluye segmentos validados en InfluxDB y segmentos descartados por falta de datos o cobertura incompleta de ambos pies.

* `results/final_baseline_results.csv`
  Tabla final de resultados comparando validación estratificada aleatoria y validación agrupada por bloques temporales.

* `results/final_ml_sequence_summary.csv`
  Tabla consolidada de CV=3, validación por bloques y evaluación secuencial con postprocesado.

* `results/sequence_evaluation_results.csv`
  Métricas por segmento para la evaluación por ventana móvil.

* `results/sequence_evaluation_summary.csv`
  Métricas agregadas de la evaluación por ventana móvil.

* `results/sequence_evaluation_predictions.csv`
  Predicciones temporales agregadas con `time_center`, etiqueta real, predicción y probabilidad de marcha.

* `results/sequence_threshold_sweep.csv`
  Barrido amplio de umbrales sobre `walking_probability`.

* `results/sequence_threshold_sweep_fine.csv`
  Barrido fino alrededor del mejor umbral encontrado.

* `results/sequence_temporal_smoothing_sweep.csv`
  Barrido de reglas de persistencia temporal sobre las predicciones secuenciales.

* `results/sequence_temporal_smoothing_sweep_fine.csv`
  Barrido fino de persistencia temporal alrededor de la mejor zona encontrada.

* `results/stitched_sequence_predictions.csv`
  Secuencia concatenada de segmentos no vistos de pacientes ya conocidos, con etiqueta real, predicción final y probabilidad.

* `results/stitched_sequence_summary.csv`
  Métricas agregadas de la secuencia concatenada de pacientes ya conocidos.

* `results/stitched_sequence_predictions_all_valid.csv`
  Secuencia concatenada exploratoria con todos los segmentos válidos disponibles.

* `results/stitched_sequence_summary_all_valid.csv`
  Métricas agregadas de la secuencia concatenada exploratoria con todos los segmentos válidos disponibles.

* `results/stitched_sequence_predictions_new_patient.csv`
  Secuencia concatenada con los segmentos válidos disponibles de pacientes nuevos.

* `results/stitched_sequence_summary_new_patient.csv`
  Métricas agregadas de la evaluación separada en pacientes nuevos.

* `results/stitched_sequence_predictions_conservative.csv`
  Variante más conservadora de la secuencia concatenada de pacientes ya conocidos.

* `results/stitched_sequence_summary_conservative.csv`
  Métricas de la variante más conservadora que conserva `recall >= 0.50`.

* `results/stitched_sequence_predictions_new_patient_conservative.csv`
  Variante más conservadora de la secuencia concatenada de pacientes nuevos.

* `results/stitched_sequence_summary_new_patient_conservative.csv`
  Métricas de la variante más conservadora en pacientes nuevos.

* `results/stitched_sequence_smoothing_sweep.csv`
  Barrido conservador de umbral y persistencia temporal sobre mismos pacientes.

* `results/stitched_sequence_smoothing_sweep_new_patient.csv`
  Barrido conservador de umbral y persistencia temporal sobre pacientes nuevos.

* `results/transformer_sequence_dataset_summary.json`
  Resumen del dataset secuencial inicial para modelos tipo transformer.

* `results/transformer_sequence_summary.json`
  Resumen de la evaluación out-of-fold del baseline transformer.

* `results/transformer_sequence_cv_results.csv`
  Métricas por fold/bloque temporal del baseline transformer.

* `results/transformer_sequence_cv_predictions.csv`
  Predicciones out-of-fold del baseline transformer.

* `results/transformer_sequence_threshold_sweep.csv`
  Barrido amplio de umbrales sobre las probabilidades out-of-fold del transformer.

* `results/transformer_sequence_threshold_sweep_fine.csv`
  Barrido fino de umbrales del transformer en la zona de mejor F1.

* `results/transformer_sequence_summary_group_val.json`
  Resumen de la variante transformer con early stopping por grupo interno.

* `results/transformer_sequence_cv_results_group_val.csv`
  Métricas por fold de la variante transformer con validación interna.

* `results/transformer_sequence_cv_predictions_group_val.csv`
  Predicciones out-of-fold de la variante transformer con validación interna.

* `results/transformer_sequence_threshold_sweep_group_val.csv`
  Barrido de umbrales de la variante transformer con validación interna.

* `results/transformer_sequence_summary_group_val_small.json`
  Resumen de la variante transformer más pequeña y regularizada.

* `results/transformer_sequence_cv_results_group_val_small.csv`
  Métricas por fold de la variante transformer más pequeña y regularizada.

* `results/transformer_sequence_cv_predictions_group_val_small.csv`
  Predicciones out-of-fold de la variante transformer más pequeña y regularizada.

* `results/transformer_sequence_threshold_sweep_group_val_small.csv`
  Barrido de umbrales de la variante transformer más pequeña y regularizada.

* `results/transformer_sequence_summary_group_val_small_ls005.json`
  Resumen de la mejor variante transformer actual con label smoothing.

* `results/transformer_sequence_cv_results_group_val_small_ls005.csv`
  Métricas por fold de la mejor variante transformer actual.

* `results/transformer_sequence_cv_predictions_group_val_small_ls005.csv`
  Predicciones out-of-fold de la mejor variante transformer actual.

* `results/transformer_sequence_threshold_sweep_group_val_small_ls005.csv`
  Barrido amplio de umbrales de la mejor variante transformer actual.

* `results/transformer_sequence_threshold_sweep_group_val_small_ls005_fine.csv`
  Barrido fino de umbrales de la mejor variante transformer actual.

* `results/transformer_temporal_smoothing_sweep.csv`
  Barrido amplio de suavizado temporal aplicado al mejor transformer actual.

* `results/transformer_temporal_smoothing_sweep_fine.csv`
  Barrido fino de suavizado temporal aplicado al mejor transformer actual.

## Artefactos de referencia recomendados

En el estado actual del proyecto, los ficheros de referencia principales son:

* `experiment_configs/main_dataset_windows.csv`
* `experiment_configs/sequence_evaluation_windows.csv`
* `results/final_baseline_results.csv`
* `results/final_ml_sequence_summary.csv`
* `results/transformer_sequence_dataset_summary.json`
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
* construir y comparar modelos secuenciales tipo transformer a partir de una base de datos más robusta
