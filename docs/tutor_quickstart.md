# Tutor quickstart

Esta guía sirve para comprobar una ventana temporal antes de generar datasets o discutir resultados del modelo.

## 1. Diagnosticar la ventana

Ejecutar primero:

```bash
poetry run python gait_analysis/doctor.py \
  -f "2026-05-05 10:25:00" \
  -u "2026-05-06 13:53:00" \
  -q "AGCHUG064-10" \
  --print-query \
  --json-output "salidas_test/AGCHUG064-10_doctor.json"
```

Si solo se quiere comprobar la query y la conversión horaria sin conectar con InfluxDB:

```bash
python gait_analysis/doctor.py \
  -f "2026-05-05 10:25:00" \
  -u "2026-05-06 13:53:00" \
  -q "AGCHUG064-10" \
  --dry-run \
  --print-query
```

## 2. Interpretar el estado

| Status | Significado | Siguiente paso |
| --- | --- | --- |
| `valid_both_feet` | Hay datos de ambos pies y se solapan temporalmente. | Extraer `raw` y después `spectrogram`. |
| `connection_failed` | No se ha podido conectar con InfluxDB. | Revisar VPN, red, URL, token o firewall. No es todavía un problema de fechas. |
| `no_records` | La query conecta, pero no devuelve registros. | Revisar referencia, rango temporal y zona horaria. Comparar con Grafana. |
| `only_some_feet` | Solo hay datos de alguno de los pies. | Extraer `raw` para inspección; el espectrograma bilateral no será válido. |
| `no_common_interval` | Ambos pies tienen datos, pero no se solapan. | Revisar sincronización o rango temporal. |
| `invalid_time_range` | La fecha final no es posterior a la inicial. | Corregir `-f` y `-u`. |
| `invalid_datetime` | Formato de fecha no reconocido. | Usar formato `YYYY-MM-DD HH:MM:SS`. |
| `config_failed` | No se ha podido cargar o validar la configuración. | Revisar `--config` y `.config.yaml`. |

## 3. Extraer señal cruda

Si `doctor` devuelve `valid_both_feet`, guardar primero la señal cruda:

```bash
poetry run python extract_influx_hdf5.py \
  -f "2026-05-05 10:25:00" \
  -u "2026-05-06 13:53:00" \
  -q "AGCHUG064-10" \
  --mode raw \
  -o "salidas_test/AGCHUG064-10_raw.csv" \
  -vv
```

Esta ejecución genera también:

```text
salidas_test/AGCHUG064-10_raw.audit.json
```

Ese JSON conserva la query Flux, la conversión local/UTC, el commit git, la configuración, las filas por pie y el estado final.

## 4. Extraer espectrograma

Si la señal cruda es correcta, generar el espectrograma:

```bash
poetry run python extract_influx_hdf5.py \
  -f "2026-05-05 10:25:00" \
  -u "2026-05-06 13:53:00" \
  -q "AGCHUG064-10" \
  --mode spectrogram \
  -o "salidas_test/AGCHUG064-10_spectrogram.parquet" \
  -vv
```

Esta ejecución genera también:

```text
salidas_test/AGCHUG064-10_spectrogram.audit.json
```

Si no se genera parquet, el JSON indica la causa: falta de conexión, ausencia de datos, falta de intersección común, ausencia de ventanas completas o descarte por completitud.

## 5. Regla práctica

No interpretar resultados del modelo si antes no existe al menos uno de estos ficheros de auditoría:

```text
*_doctor.json
*_raw.audit.json
*_spectrogram.audit.json
```

Así se puede distinguir entre un problema de modelo y un problema previo de extracción, fechas, cobertura o conexión.

## 6. Baseline actual

La comparación externa de referencia del repositorio usa las ventanas fijadas en `experiment_configs/sequence_evaluation_windows.csv`.

Resumen operativo:

| Modelo | F1 walking | FP |
| --- | ---: | ---: |
| Random Forest | 0.0406 | 181 |
| XGBoost | 0.0319 | 173 |
| CatBoost | 0.0481 | 434 |
| Transformer | 0.0899 | 81 |

Conclusión práctica:

* el transformer es el baseline actual para la comparación externa
* CatBoost recupera más positivos, pero con demasiados falsos positivos
* RF y XGBoost son más conservadores y detectan menos `walking`

La tabla completa vive en `results/sequence_model_external_comparison_summary.md`.

En el transformer también se probó una variación de arquitectura:

* 4 cabezas mejoró claramente frente a 2
* 8 cabezas apenas aportó mejora adicional
* `pooling=mean` funcionó mejor que `pooling=center` en la validación interna

En la práctica, el detalle de pooling fue más útil que seguir aumentando el número de cabezas.
