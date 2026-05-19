# Transformer sobre el dataset ampliado

## Objetivo

Evaluar el transformer secuencial sobre el dataset ampliado con pacientes nuevos
usando validacion por bloques temporales con embargo, y compararlo con los modelos
clasicos ya evaluados sobre la misma base.

## Dataset secuencial

- `salidas_test/auto_extracts/transformer_sequence_dataset_len9_plus_054.npz`
- 3.172 secuencias
- secuencia de longitud 9
- 25 bloques temporales

## Configuracion usada

- `validation_mode = group`
- `embargo_seconds = 10`
- `epochs = 20`
- `patience = 5`
- `batch_size = 128`
- `d_model = 16`
- `dim_feedforward = 32`

Se ha usado una version ligera para obtener una comparacion razonable en CPU sin
prolongar innecesariamente la ejecucion.

## Resultado

- Accuracy out-of-fold: `0.6860`
- Precision marcha out-of-fold: `0.6850`
- Recall marcha out-of-fold: `0.7138`
- F1 marcha out-of-fold: `0.6991`

## Lectura comparativa

Sobre el mismo dataset ampliado, los clasicos en CV3 obtenian:

- Random Forest: F1 marcha `0.8106`
- XGBoost: F1 marcha `0.8321`
- CatBoost: F1 marcha `0.8329`

El transformer secuencial queda por debajo de todos ellos en esta prueba.

## Conclusion breve

Con el dataset actual, el transformer no supera a los modelos clasicos. La
diversidad adicional de pacientes ayuda mucho a RF, XGBoost y CatBoost, pero no
parece suficiente para que un transformer pequeno saque ventaja clara.

Esto deja una conclusion metodologica bastante limpia:

1. La ampliacion de pacientes si era el cuello de botella principal.
2. La arquitectura clasica sigue siendo la mejor base en este punto.
3. El transformer puede mantenerse como comparacion secundaria, pero no como
   modelo principal por ahora.
