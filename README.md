# 2025_OCH_Gait

## Descripción general

Este proyecto extrae señales de marcha desde InfluxDB y genera representaciones espectrales para su análisis posterior.

Actualmente el pipeline permite:

- contar registros por pie
- generar espectros de potencia a partir de señales IMU
- exportar resultados en formato `.parquet`, `.xlsx` y `.h5`

La lógica principal está organizada dentro del paquete `gait_analysis/`.

## Entorno y dependencias

El proyecto usa **Poetry** para la gestión de dependencias.

Los ejemplos de este README utilizan el intérprete del entorno virtual de Poetry:

```bash
/Users/clarissaotanezgonzalez/Library/Caches/pypoetry/virtualenvs/gait-analysis-tfg-4Mpt7Deb-py3.11/bin/python

```


## Configuración

Debe existir un fichero `.config.yaml` en la raíz del proyecto. En él se definen:

- la conexión a InfluxDB
- los nombres de los tags usados en las consultas
- la gestión temporal
- los parámetros del espectrograma

La configuración actual del espectrograma procesa estas señales IMU:

- acelerómetro: `Ax`, `Ay`, `Az`
- giroscopio: `Gx`, `Gy`, `Gz`

para ambos pies:

- `Right`
- `Left`

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

- longitud de ventana: `10 s`
- paso temporal: `1 s`
- frecuencia máxima: `5 Hz`
- tipo de ventana: `hann`
- escala de potencia: `db`

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

- `.parquet`
- `.xlsx`
- `.h5` o `.hdf5`

## Utilidades de ground truth

El proyecto incluye scripts auxiliares para preparar y analizar el ground truth:

- `gait_analysis/build_ground_truth_excel.py`
- `gait_analysis/build_window_configs.py`
- `gait_analysis/summarize_window_experiments.py`

Estos scripts permiten:

- limpiar y normalizar Excels de etiquetas de marcha
- preparar configuraciones para distintas longitudes de ventana
- resumir experimentos comparativos entre ventanas

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

- filtrado por paciente mediante `CodeID`
- extracción por pie
- espectros para acelerómetro y giroscopio
- exportación en varios formatos
- limpieza básica de ground truth
- preparación de experimentos con distintas ventanas temporales
- documentación Sphinx con diagrama de arquitectura

