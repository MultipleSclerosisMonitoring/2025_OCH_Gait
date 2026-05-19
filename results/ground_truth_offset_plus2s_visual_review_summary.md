# Tabla de revision visual del offset +2 s

Se genero una tabla para revisar visualmente si el offset `+2 s` alinea mejor
las etiquetas con la señal o si la mejora numerica es accidental.

Comparacion usada:

- baseline: dataset sin transiciones +/-5 s, offset 0 s;
- candidato: dataset sin transiciones +/-5 s, ground truth desplazado +2 s;
- umbral operativo: 0.80.

Archivos generados:

- `results/ground_truth_offset_plus2s_visual_review_rows.csv`
- `results/ground_truth_offset_plus2s_visual_review_runs.csv`

## Resumen de casos

| Categoria | Ventanas |
|---|---:|
| Sin cambio relevante / otros | 3082 |
| Falso positivo corregido por +2 s | 124 |
| Falso positivo persistente | 43 |
| Ventana perdida al reetiquetar +2 s | 39 |
| Etiqueta cambiada por +2 s | 10 |

## Tramos prioritarios para revisar

Los tramos mas importantes son:

| Referencia | Motivo | Inicio | Fin | Ventanas |
|---|---|---|---|---:|
| 47046344M-104 | FP corregido por +2 s | 2024-10-15 07:30:18 | 2024-10-15 07:31:02 | 42 |
| 47046344M-104 | FP persistente | 2024-10-15 07:31:10 | 2024-10-15 07:31:32 | 23 |
| 04845288Q-121 | FP corregido por +2 s | 2025-03-01 11:36:40 | 2025-03-01 11:36:48 | 9 |
| 04845288Q-121 | FP corregido por +2 s | 2025-03-01 11:37:22 | 2025-03-01 11:37:31 | 8 |
| 04845288Q-121 | FP corregido por +2 s | 2025-03-01 11:36:26 | 2025-03-01 11:36:34 | 7 |

## Criterio de decision

Al revisar estos tramos en la visualizacion:

- si el inicio/parada real de la marcha aparece aproximadamente 2 segundos
  despues de la etiqueta original, el offset `+2 s` queda apoyado visualmente;
- si los tramos corregidos siguen siendo claramente no marcha estable, entonces
  la mejora puede venir de regularizacion del modelo y no de sincronizacion;
- si los falsos positivos persistentes contienen movimientos ritmicos de piernas
  sin marcha, deben añadirse como negativos dificiles o mantenerse como casos
  limite.

La decision final sobre adoptar `+2 s` no deberia basarse solo en metricas; esta
tabla permite hacer una validacion visual focalizada.
