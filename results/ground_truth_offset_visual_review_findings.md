# Revision visual del offset de ground truth

## Objetivo

Se reviso si el desplazamiento de etiquetas de `+2s`, que mejoraba las metricas frente a falsos positivos, representa un desfase horario real o si esta actuando como una correccion indirecta de otros problemas de etiquetado/modelado.

La revision se hizo sobre las rachas mas relevantes de:

- `results/ground_truth_offset_plus2s_visual_review_runs.csv`
- `results/ground_truth_offset_plus2s_visual_review_rows.csv`

Tambien se generaron graficas con senal bruta de ambos pies y probabilidades comparando offset `0s` frente a `+2s`:

- `results/offset_visual_review_plots/`
- `results/ground_truth_offset_plus2s_visual_review_plot_manifest.csv`

## Hallazgos principales

1. El offset `+2s` reduce bastantes falsos positivos segun la probabilidad del modelo, pero la evidencia visual no demuestra de forma concluyente que exista un desfase global de exactamente dos segundos.

2. En `47046344M-104`, algunas rachas corregidas por el offset muestran movimiento ritmico principalmente en un solo pie. Esto encaja mejor con un negativo dificil/asimetrico que con un error horario claro.

3. En `04845288Q-121`, varias rachas etiquetadas como no marcha muestran oscilacion bilateral fuerte y regular en acelerometro y giroscopio. En estos casos, el hecho de que `+2s` reduzca la probabilidad no basta para aceptar el desplazamiento: primero hay que revisar si el tramo esta bien etiquetado como no marcha.

4. Persisten falsos positivos incluso con `+2s`, especialmente en `47046344M-104`. Por tanto, el offset no resuelve por si solo el problema de generalizacion ni sustituye la necesidad de negativos dificiles y mas diversidad de pacientes.

## Interpretacion por graficas revisadas

| Grafica | Tramo | Interpretacion |
| --- | --- | --- |
| `01_47046344M_104_fp_corrected_by_offset.png` | `47046344M-104`, 07:30:18-07:31:02 | El offset baja la probabilidad, pero hay movimiento ritmico claro sobre todo en el pie derecho. Parece negativo dificil/asimetrico. |
| `02_47046344M_104_persistent_false_positive.png` | `47046344M-104`, 07:31:10-07:31:32 | El offset no corrige la racha. Se observa activacion progresiva del pie derecho; sigue siendo caso dificil. |
| `03_04845288Q_121_fp_corrected_by_offset.png` | `04845288Q-121`, 11:36:40-11:36:48 | Hay movimiento bilateral fuerte y regular. Requiere revision de etiqueta antes de considerar este tramo como falso positivo real. |
| `04_04845288Q_121_fp_corrected_by_offset.png` | `04845288Q-121`, 11:37:22-11:37:31 | Patron bilateral muy periodico. De nuevo, posible tramo mal etiquetado o no marcha con movimiento muy parecido a marcha. |
| `06_47046344M_104_persistent_false_positive.png` | `47046344M-104`, 07:31:39-07:31:45 | Movimiento suave y periodico en pie derecho; `+2s` apenas baja la probabilidad. |

## Decision recomendada

No aplicar todavia `+2s` como correccion oficial del ground truth.

La opcion mas defendible ahora es:

1. Mantener el modelo sin offset como referencia principal.
2. Mantener el entrenamiento/evaluacion con `+2s` como analisis de sensibilidad.
3. Pedir revision visual/clinica de los tramos dudosos, especialmente `04845288Q-121` entre `11:36:18` y `11:37:31`.
4. Si la revision confirma que esos tramos estan mal etiquetados o desplazados, entonces si aplicar la correccion al ground truth.
5. Si no se confirma, tratar esos tramos como negativos dificiles y reforzar el dataset con mas pacientes y ejemplos similares.

## Conclusion breve

El offset `+2s` es una hipotesis util y mejora resultados, pero la inspeccion visual indica que parte de la mejora puede venir de mover la frontera de decision en tramos ambiguos, no necesariamente de corregir un desfase horario real. Antes de fijarlo en el pipeline, conviene validar manualmente las etiquetas de los tramos con movimiento ritmico claro.
