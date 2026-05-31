# Revision visual de intervalos sospechosos

Generado a partir de `results/auto_influx_extension_correction_visual_audit_table.csv`.

## Resultado de extraccion

- Intervalos procesados: 99
- Extracciones validas desde InfluxDB: 99
- Graficas generadas: 99
- Muestras raw extraidas: 283889
- Directorio revisable: `results/correction_visual_review/`
- Parquets raw locales: `salidas_test/correction_visual_review/raw/`

Los parquets raw se guardan en `salidas_test/` porque son artefactos locales
pesados e ignorados por git. El directorio `results/correction_visual_review/`
contiene el manifiesto, la plantilla de decision, el indice HTML y las graficas.

## Resumen por referencia

| Referencia | Correccion propuesta | Intervalos | Muestras raw |
|---|---:|---:|---:|
| `02548893X-118` | `not_walking` -> `walking` | 10 | 21433 |
| `04845288Q-121` | `not_walking` -> `walking` | 1 | 11615 |
| `47046344M-104` | `walking` -> `not_walking` | 5 | 13185 |
| `ACL1998-96` | `walking` -> `not_walking` | 36 | 89707 |
| `AEMDHUG060-70` | `not_walking` -> `walking` | 40 | 131668 |
| `AGCHUG064-10` | `not_walking` -> `walking` | 7 | 16281 |

## Ficheros principales

- `index.html`: revision visual navegable. La franja sombreada marca el intervalo propuesto para corregir.
- `manifest.csv`: estado tecnico de cada extraccion, rutas, numero de muestras y estado del audit JSON.
- `review_decisions_template.csv`: plantilla para confirmar, rechazar o matizar cada correccion.
- `plots/*.png`: grafica por intervalo con norma de acelerometro y giroscopio por pie.

## Siguiente paso recomendado

Revisar `index.html` y completar `review_decisions_template.csv` con una decision
por intervalo. Despues se debe aplicar solo el subconjunto confirmado y repetir
el entrenamiento ponderado por paciente/origen.
