# Auditoria exhaustiva de referencias Influx

- Rango UTC auditado: `2024-01-01T00:00:00Z` a `2026-06-02T00:00:00Z`
- Inventario CSV: `experiment_configs/influx_reference_inventory_exhaustive.csv`
- Plan de extraccion CSV: `experiment_configs/influx_reference_extraction_plan.csv`
- Referencias con senal en Influx: 135
- Referencias con ambos pies: 132
- Referencias ya integradas: 19
- Referencias listas con etiquetas walking/not_walking: 0
- Referencias candidatas con senal pero pendientes de etiqueta: 113

Lectura principal: hay senal bilateral suficiente para seguir ampliando diversidad, pero no hay referencias nuevas que ya tengan etiquetas `walking` y `not_walking` en el ground truth local. La siguiente tarea no es reextraer a ciegas, sino etiquetar bloques de las referencias con senal disponible.

## Estados

| status | refs |
| --- | --- |
| available_unlabeled | 110 |
| already_integrated | 19 |
| available_needs_labeling | 3 |
| blocked_no_bilateral_coverage | 3 |

## Listas para extraccion etiquetada

_Sin filas._

## Candidatas indicadas pero pendientes de etiqueta

| reference | manual_priority | right_records | left_records | manual_first_from | manual_last_until | intersection_start_utc | intersection_stop_utc | extraction_decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AMIR-48 | 4.0 | 4458156 | 4686672 | 2024-06-26 19:00:00 | 2024-06-27 16:00:00 | 2024-04-06 16:48:18.875000+00:00 | 2025-12-12 17:43:57.688000+00:00 | Extraer muestras/spectrogramas para etiquetado manual. |
| MGM-202406-79 | 8.0 | 21295668 | 15866646 | 2025-06-16 00:00:00 | 2025-06-16 23:59:00 | 2024-06-16 11:09:11.540000+00:00 | 2024-10-08 12:09:18.211000+00:00 | Extraer muestras/spectrogramas para etiquetado manual. |
| AAMALMHUG057-66 | 14.0 | 841362 | 855168 | 2024-04-25 20:00:00 | 2024-04-25 22:00:00 | 2026-04-25 18:49:04.375000+00:00 | 2026-04-25 19:37:28.957000+00:00 | Extraer muestras/spectrogramas para etiquetado manual. |

## Mas senal disponible sin etiqueta local

| reference | right_records | left_records | intersection_start_utc | intersection_stop_utc | recommended_next_step |
| --- | --- | --- | --- | --- | --- |
| CHIHUG033-15 | 29343522 | 69593778 | 2026-03-03 11:58:54.465000+00:00 | 2026-03-04 17:30:02.697000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| LFCMHUG070-78 | 54168780 | 39377760 | 2026-05-20 09:47:34.610000+00:00 | 2026-05-30 07:28:55.321000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| 53471345W-118 | 43494498 | 44271498 | 2024-04-16 05:36:18.446000+00:00 | 2025-02-27 11:13:36.661000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| IECHUG029-9 | 46090056 | 34394988 | 2026-02-18 10:20:11.173000+00:00 | 2026-02-20 09:10:30.978000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| SOMHUG003-31 | 37065774 | 31737330 | 2025-11-28 09:21:00.299000+00:00 | 2025-12-05 19:46:49.357000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| EMVHUG066-19 | 33388602 | 29568348 | 2026-05-12 10:52:04.059000+00:00 | 2026-05-13 12:01:47.939000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| EPGHUG006-25 | 31472508 | 31444206 | 2025-12-12 10:21:37.857000+00:00 | 2025-12-13 19:39:59.974000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| EPSHUG067-10 | 31088772 | 31182120 | 2026-05-13 07:47:48.944000+00:00 | 2026-05-16 12:38:30.468000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| JMGHUG016-10 | 30471990 | 30695220 | 2026-01-23 09:12:42.088000+00:00 | 2026-01-24 16:50:37.956000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| 01912299X-118 | 30922350 | 29424738 | 2024-04-24 08:47:58.124000+00:00 | 2026-04-09 10:08:50.487000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| BMAHUG058-14 | 29431356 | 27859698 | 2026-04-23 07:33:38.326000+00:00 | 2026-04-26 11:03:07.539000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| JCGMHUG007-73 | 27841038 | 28693326 | 2025-12-16 08:11:48.975000+00:00 | 2025-12-18 09:05:59.714000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| FMGHUG012-2 | 30785532 | 24850116 | 2025-12-26 08:27:28.866000+00:00 | 2025-12-27 19:52:42.400000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| JMAHUG009-2 | 14596380 | 40745988 | 2025-12-22 08:00:08.270000+00:00 | 2025-12-23 19:37:05.514000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| SSAHUG014-9 | 25667460 | 27462744 | 2026-01-12 13:26:42.593000+00:00 | 2026-01-13 15:51:47.867000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| LFPHUG013-21 | 22218828 | 22275354 | 2026-05-01 07:13:48.966000+00:00 | 2026-05-03 22:03:23.458000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| SMGHUG039-30 | 30125328 | 13596162 | 2026-03-17 10:38:48.601000+00:00 | 2026-03-18 14:09:43.017000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| ALLCHUG038-68 | 22187250 | 21307218 | 2026-03-17 08:43:41.387000+00:00 | 2026-03-18 10:36:21.383000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| RGDPHUG045-77 | 18941226 | 22008336 | 2026-04-07 11:20:11.137000+00:00 | 2026-04-08 18:52:42.994000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| GBARHUG032-90 | 25780212 | 13705026 | 2026-03-02 08:49:26.261000+00:00 | 2026-03-02 21:14:58.965000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| GGTHUG028-19 | 24731784 | 13103058 | 2026-02-16 11:42:27.082000+00:00 | 2026-02-17 12:17:48.414000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| EMMHUG008-0 | 22901304 | 14538018 | 2025-12-12 13:39:24.837000+00:00 | 2025-12-14 21:08:47.674000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| SPCHUG023-12 | 10008150 | 27328872 | 2026-02-06 07:38:15.357000+00:00 | 2026-02-08 12:02:02.798000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| LMGNHUG055-69 | 18806202 | 18472548 | 2026-04-22 07:14:16.985000+00:00 | 2026-04-23 09:06:52.230000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| CRP1997-96 | 19373016 | 17403930 | 2025-07-29 12:43:05.822000+00:00 | 2025-07-30 02:37:24.417000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| MGGSHUG069-92 | 18649980 | 17800974 | 2026-05-19 11:30:32.775000+00:00 | 2026-05-21 20:19:02.884000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| MJCRHUG013-89 | 20662782 | 15595350 | 2025-12-29 09:59:32.487000+00:00 | 2026-01-19 18:22:04.620000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| 01931018F-98 | 21180900 | 12863778 | 2024-04-27 09:21:37.749000+00:00 | 2024-05-05 18:00:54.371000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| JASAHUG010-85 | 18188358 | 15014976 | 2025-12-22 09:01:57.437000+00:00 | 2025-12-24 17:13:59.726000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| PLMHUG001-29 | 16062984 | 17034588 | 2025-11-27 08:56:36.620000+00:00 | 2025-11-28 08:00:47.126000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| JOM20241031-104 | 14895234 | 15807960 | 2024-10-31 18:35:20.985000+00:00 | 2024-11-02 22:31:59.774000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| PRCHGU025-11 | 12351126 | 18112632 | 2026-02-09 11:22:48.844000+00:00 | 2026-02-09 20:36:00.597000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| IMGFHUG042-78 | 15023538 | 15128214 | 2026-03-30 09:02:31.311000+00:00 | 2026-04-03 18:27:44.177000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| JOM20240407-104 | 10657206 | 19089984 | 2024-04-07 08:07:32.962000+00:00 | 2024-04-13 14:09:44.870000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| CGRHUG020-25 | 14547066 | 14669460 | 2026-01-29 13:27:00.433000+00:00 | 2026-02-01 18:16:13.282000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| LJMHUG031-4 | 14687886 | 14342058 | 2026-02-20 08:46:31.782000+00:00 | 2026-02-21 13:53:04.613000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| JMOHUG036-0 | 15337608 | 13399206 | 2026-03-10 10:44:10.475000+00:00 | 2026-03-11 21:23:35.901000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| MEVDLHHUG071-85 | 9536646 | 19136976 | 2026-05-26 09:24:45.099000+00:00 | 2026-05-27 21:01:57.964000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| CCGHUG034-13 | 12652248 | 15884940 | 2026-03-05 09:43:26.222000+00:00 | 2026-03-08 17:10:32.954000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |
| 05329567F-104 | 10378548 | 17849436 | 2025-04-02 09:10:22.033000+00:00 | 2025-04-02 19:00:46.499000+00:00 | Puede usarse para buscar ventanas candidatas y crear plantilla de etiquetado. |

## Criterio operativo

- `ready_labeled_extract`: se puede extraer desde Influx e incorporar tras generar espectrogramas.
- `available_needs_labeling`: hay senal bilateral y una ventana candidata, pero falta etiqueta fiable.
- `available_unlabeled`: hay senal bilateral, pero antes hay que crear/revisar etiquetas.
- `partial_label_needs_complement`: existe una sola clase etiquetada; no sirve por si sola para un paciente binario completo.
- `blocked_no_bilateral_coverage`: no es util para el pipeline bilateral actual sin corregir referencia o timestamps.

Para referencias sin etiqueta local, `intersection_start_utc` y `intersection_stop_utc` marcan el rango real con ambos pies detectado en Influx. Si difiere de las ventanas manuales, debe priorizarse este rango real para generar plantillas de etiquetado.
