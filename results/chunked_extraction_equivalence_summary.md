# Validacion de equivalencia del extractor por chunks

Se valido el extractor por chunks contra InfluxDB usando un tramo corto con datos
reales.

## Configuracion

- Referencia: `47046344M-104`
- Rango: `2024-10-15 07:28:58` a `2024-10-15 07:31:52`
- Configuracion: `experiment_configs/config_window_1s.yaml`
- Extraccion normal:
  `salidas_test/chunked_equivalence/normal_47046344M_104_072858_073152.parquet`
- Extraccion por chunks:
  `salidas_test/chunked_equivalence/chunked_anchored_47046344M_104_072858_073152.parquet`
- Chunks: 1 minuto
- Solape: 5 segundos

## Resultado

| Medida | Valor |
|---|---:|
| Filas normales | 2064 |
| Filas chunked | 2076 |
| Filas comunes | 2064 |
| Claves normales no presentes en chunked | 0 |
| Claves chunked no presentes en normal | 12 |
| Centros temporales extra en chunked | 1 |
| Maxima diferencia absoluta de potencias en filas comunes | 0.0 |
| Diferencia media absoluta de potencias en filas comunes | 0.0 |

Las filas compartidas son identicas. El extractor por chunks produjo una ventana
adicional al final del intervalo, centrada en `2024-10-15 07:31:51.010000+00:00`.

## Correccion aplicada

La primera version chunked generaba algunos centros desplazados 10 ms en chunks
posteriores, porque el extractor original anclaba los centros al primer timestamp
real disponible dentro de cada consulta. Se corrigio añadiendo un ancla global
de centros:

- el primer chunk se extrae normalmente;
- se toma su primer `time_center` como `center_anchor_time`;
- los chunks posteriores generan centros alineados con esa misma secuencia.

Con esa correccion, todas las ventanas comunes coinciden exactamente con la
extraccion normal.

## Conclusion

La extraccion por chunks queda validada para las ventanas comunes y resuelve el
problema de memoria para rangos largos. Para comparaciones historicas
estrictamente bit a bit puede filtrarse el ultimo centro extra si aparece en el
borde final.
