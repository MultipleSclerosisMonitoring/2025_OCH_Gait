# Auditoria de errores por paciente

## Prioridad de revision

- catboost | ACL1998-96 | previous_dataset: errors=3508, fp=1237, fn=2271, error_rate=0.5535, f1_walking=0.4307, f1_macro=0.4461
- random_forest | ACL1998-96 | previous_dataset: errors=3507, fp=1220, fn=2287, error_rate=0.5533, f1_walking=0.4278, f1_macro=0.4461
- xgboost | ACL1998-96 | previous_dataset: errors=3504, fp=1216, fn=2288, error_rate=0.5529, f1_walking=0.4278, f1_macro=0.4465
- random_forest | AEMDHUG060-70 | previous_dataset: errors=1040, fp=1040, fn=0, error_rate=0.7951, f1_walking=0.0000, f1_macro=0.1701
- xgboost | AEMDHUG060-70 | previous_dataset: errors=972, fp=972, fn=0, error_rate=0.7431, f1_walking=0.0000, f1_macro=0.2044
- catboost | AEMDHUG060-70 | previous_dataset: errors=967, fp=967, fn=0, error_rate=0.7393, f1_walking=0.0000, f1_macro=0.2068
- random_forest | AGCHUG064-10 | previous_dataset: errors=917, fp=917, fn=0, error_rate=0.5878, f1_walking=0.0000, f1_macro=0.2919
- xgboost | AGCHUG064-10 | previous_dataset: errors=897, fp=897, fn=0, error_rate=0.5750, f1_walking=0.0000, f1_macro=0.2982
- catboost | AGCHUG064-10 | previous_dataset: errors=886, fp=886, fn=0, error_rate=0.5679, f1_walking=0.0000, f1_macro=0.3017
- random_forest | 47046344M-104 | previous_dataset: errors=399, fp=8, fn=391, error_rate=0.5692, f1_walking=0.2004, f1_macro=0.3793
- catboost | 47046344M-104 | previous_dataset: errors=393, fp=11, fn=382, error_rate=0.5606, f1_walking=0.2309, f1_macro=0.3949
- xgboost | 47046344M-104 | previous_dataset: errors=387, fp=12, fn=375, error_rate=0.5521, f1_walking=0.2543, f1_macro=0.4080
- catboost | AGCHUG064-10 | auto_influx_heuristic: errors=375, fp=158, fn=217, error_rate=0.3720, f1_walking=0.4000, f1_macro=0.5652
- random_forest | AGCHUG064-10 | auto_influx_heuristic: errors=375, fp=163, fn=212, error_rate=0.3720, f1_walking=0.4094, f1_macro=0.5690
- xgboost | AGCHUG064-10 | auto_influx_heuristic: errors=365, fp=152, fn=213, error_rate=0.3621, f1_walking=0.4141, f1_macro=0.5761

## Lectura

Los grupos con muchos falsos negativos son candidatos a revisar etiquetas de marcha o variabilidad real no cubierta. Los grupos con muchos falsos positivos son candidatos a revisar actividades no marcha que se parecen a marcha.
