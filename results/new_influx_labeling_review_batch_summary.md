# Lote de etiquetado Influx para referencias nuevas

- Plantilla: `experiment_configs/new_influx_labeling_review_batch.csv`
- Referencias: 5
- Bloques: 10

Este lote no incorpora etiquetas al dataset. Genera bloques cortos para extraer senal raw desde Influx, calcular sugerencias de actividad y revisar manualmente `walking` / `not_walking`.

## Referencias

| Reference | priority | blocks | first_local | last_local | status |
| --- | --- | --- | --- | --- | --- |
| MGM-202406-79 | 1 | 2 | 2024-06-16 13:09:11 | 2024-10-08 14:09:18 | available_needs_labeling |
| AAMALMHUG057-66 | 2 | 2 | 2026-04-25 20:49:04 | 2026-04-25 21:37:28 | available_needs_labeling |
| CHIHUG033-15 | 3 | 2 | 2026-03-03 12:58:54 | 2026-03-04 18:30:02 | available_unlabeled |
| LFCMHUG070-78 | 4 | 2 | 2026-05-20 11:47:34 | 2026-05-30 09:28:55 | available_unlabeled |
| IECHUG029-9 | 5 | 2 | 2026-02-18 11:20:11 | 2026-02-20 10:10:30 | available_unlabeled |

## Siguiente comando

```bash
poetry run python gait_analysis/extract_labeling_template_blocks.py \
  -i experiment_configs/new_influx_labeling_review_batch.csv \
  --mode raw \
  -o salidas_test/new_influx_labeling_batch/raw_blocks \
  --manifest salidas_test/new_influx_labeling_batch/raw_manifest.csv \
  --resume-existing
```
