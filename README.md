# 2025_OCH_Gait

## Descripción general

Este proyecto extrae señales de marcha desde InfluxDB y genera representaciones espectrales para su análisis posterior.

Actualmente el pipeline permite:

* contar registros por pie
* generar espectros de potencia a partir de señales IMU
* exportar resultados en formato `.parquet`, `.xlsx` y `.h5`
* asignar etiquetas temporales de ground truth a ventanas espectrales
* combinar datasets etiquetados válidos
* transformar datasets al formato tabular `wide` para aprendizaje automático
* ejecutar baselines simples de clasificación

La lógica principal está organizada dentro del paquete `gait_analysis/`.

## Entorno y dependencias

El proyecto usa **Poetry** para la gestión de dependencias.

Los ejemplos de este README utilizan el intérprete del entorno virtual de Poetry:

```bash
/Users/clarissaotanezgonzalez/Library/Caches/pypoetry/virtualenvs/gait-analysis-tfg-4Mpt7Deb-py3.11/bin/python
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

## Modos principales de ejecución

### 1. Modo `count`

Se utiliza para comprobar que la extracción desde InfluxDB funciona correctamente.

Ejemplo:

```bash
/Users/clarissaotanezgonzalez/Library/Caches/pypoetry/virtualenvs/gait-analysis-tfg-4Mpt7Deb-py3.11/bin/python extract_influx_hdf5.py \
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
/Users/clarissaotanezgonzalez/Library/Caches/pypoetry/virtualenvs/gait-analysis-tfg-4Mpt7Deb-py3.11/bin/python extract_influx_hdf5.py \
-f "2025-07-01 14:08:20" \
-u "2025-07-01 14:08:40" \
-q "TESTPATIENT-98" \
--mode spectrogram \
-o "salidas_test/test_full_imu.parquet" \
-v
```

## Formatos de salida soportados en `spectrogram`

Según la extensión indicada en `--output`, actualmente se soportan:

* `.parquet`
* `.xlsx`
* `.h5` o `.hdf5`

## Utilidades de ground truth

El proyecto incluye scripts auxiliares para preparar y analizar el ground truth:

* `gait_analysis/build_ground_truth_excel.py`
* `gait_analysis/build_window_configs.py`
* `gait_analysis/summarize_window_experiments.py`
* `gait_analysis/label_spectrogram_with_ground_truth.py`
* `gait_analysis/summarize_labeled_spectrogram.py`
* `gait_analysis/combine_labeled_datasets.py`
* `gait_analysis/build_wide_dataset.py`
* `gait_analysis/inspect_wide_dataset.py`
* `gait_analysis/prepare_ml_dataset.py`

Estos scripts permiten:

* limpiar y normalizar Excels de etiquetas de marcha
* preparar configuraciones para distintas longitudes de ventana
* resumir experimentos comparativos entre ventanas
* asignar etiquetas `walking` / `not_walking` a ventanas espectrales
* conservar o filtrar ventanas `NO_LABEL`
* combinar varios datasets etiquetados
* transformar datasets etiquetados de formato `long` a formato `wide`
* inspeccionar datasets preparados para ML
* preparar matrices de entrada y vectores objetivo para baselines

## Pipeline actual de etiquetado y preparación para ML

El flujo actual de preparación de datos incluye:

1. extracción de señales desde InfluxDB
2. generación de espectrogramas con IMU completa en ambos pies
3. asignación de etiquetas temporales desde el ground truth limpio
4. marcaje de ventanas ambiguas como `NO_LABEL`
5. filtrado opcional de dichas ventanas
6. combinación de referencias válidas
7. transformación del dataset a formato `wide`
8. preparación del dataset final para aprendizaje automático

En el formato `wide`, cada fila representa un centro temporal de ventana y contiene las variables espectrales de potencia asociadas a cada combinación de pie y señal.

## Baselines iniciales

Se han ejecutado baselines simples sobre el dataset `wide` limpio:

* clasificador trivial que predice siempre `not_walking`
* Logistic Regression
* Random Forest

La principal conclusión es que **la accuracy por sí sola no es suficiente** para evaluar este problema, ya que el dataset está desbalanceado. Aunque el clasificador trivial y Random Forest obtuvieron mayor accuracy, Logistic Regression mostró mejor capacidad para detectar la clase minoritaria `walking`, especialmente en términos de `recall` y `F1-score`. Por ello, actualmente se considera el baseline más informativo.

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
* preparación e inspección de datasets para clasificación
* baselines iniciales de clasificación
* documentación Sphinx con diagrama de arquitectura

## Limitaciones actuales

Por ahora, las principales limitaciones detectadas son:

* número limitado de referencias con cobertura válida en InfluxDB
* desbalance entre las clases `walking` y `not_walking`
* discrepancias entre el ground truth externo y la disponibilidad real de datos en la base de datos

## Siguientes pasos

Las siguientes líneas de trabajo previstas son:

* ampliar el número de referencias válidas
* mejorar la cobertura útil del dataset
* refinar la metodología de evaluación
* estudiar modelos de clasificación más avanzados a partir de una base de datos más robusta
