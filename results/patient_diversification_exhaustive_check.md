# Revision exhaustiva de pacientes restantes

Tras incorporar `05447093A-110`, se reviso el inventario completo de ground truth
para buscar mas referencias no usadas que pudieran aumentar la diversidad de
pacientes.

## Referencias ya incorporadas

El dataset combinado actual incluye 7 referencias:

- `02548893X-118`
- `04845288Q-121`
- `47046344M-104`
- `05447093A-110`
- `330034-32`
- `663495-44`
- `TABUENCA01-45`

## Referencias restantes en ground truth

Solo quedan dos referencias no incorporadas:

| Reference | Etiqueta disponible | Duracion |
|---|---|---:|
| `05447093A-111` | `not_walking` | 12 s |
| `05447093A-112` | `not_walking` | 13 s |

Ambas tienen solo una etiqueta negativa muy corta y no tienen ejemplos de marcha.

## Escaneo amplio de offsets

Se genero `experiment_configs/patient_candidate_inventory_remaining_refs.csv` y se
ejecuto un escaneo amplio contra Influx para ambas referencias con offsets entre
`-360 min` y `+360 min`.

Salida:

- `experiment_configs/remaining_refs_wide_time_offset_scan.csv`

Resultado:

- `05447093A-111`: 0 registros en pie derecho y 0 en pie izquierdo para todos los offsets.
- `05447093A-112`: 0 registros en pie derecho y 0 en pie izquierdo para todos los offsets.

## Conclusion

Con el ground truth disponible actualmente, no quedan mas pacientes etiquetados
que puedan incorporarse de forma metodologicamente valida al dataset. Para seguir
aumentando diversidad de pacientes hace falta una de estas dos cosas:

1. Nuevas etiquetas de marcha/no marcha para pacientes adicionales.
2. Correccion externa de referencias/timestamps si existen datos en Influx pero
   no estan alineados con el ground truth actual.

Incorporar datos sin etiqueta o referencias sin cobertura no seria defendible,
porque no permitiria entrenar ni validar el clasificador de marcha/no marcha.
