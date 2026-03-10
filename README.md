# 2025_OCH_Gait
# Cambio de prueba para TFG
# Cómo probar el script

## Requisitos

Usar el entorno virtual del proyecto:

```bash
./vpy/bin/python3
```

Tener instaladas las dependencias necesarias:

```bash
./vpy/bin/python3 -m pip install influxdb-client pyyaml numpy pandas scipy pyarrow
```

## Configuración

Debe existir un fichero `.config.yaml` en la raíz del proyecto con la configuración de InfluxDB y los parámetros de procesado.

## Ejecución básica

Para comprobar que la extracción desde InfluxDB funciona:

```bash
./vpy/bin/python3 extract_influx_hdf5.py \
-f "2025-07-06 23:51:50" \
-u "2025-07-06 23:52:20" \
-q "TESTPATIENT-98" \
-v
```

## Qué hace ahora mismo

El script:

1. Lee la configuración desde `.config.yaml`
2. Convierte el intervalo temporal a UTC
3. Construye la consulta Flux
4. Consulta InfluxDB
5. Muestra por pantalla la query y el número de registros encontrados por pie

## Qué debería verse

Si los filtros son correctos, la salida debe mostrar algo como:

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

## Siguiente paso en desarrollo

El siguiente paso es calcular el espectro de potencia usando ventanas de 10 s centradas en cada instante de interés (ventana de Hanning), desplazadas cada 1 s, y guardar el resultado en parquet.
