# Mejora: embargo temporal en validacion secuencial

## Problema abordado

Las secuencias del Transformer se construyen con ventanas temporales solapadas. Si una secuencia de entrenamiento queda muy cerca de una secuencia de test del mismo paciente, ambas pueden compartir fragmentos de la misma onda fisica. Esto infla las metricas internas porque el modelo no evalua una muestra realmente independiente.

## Cambio implementado

Se anadio un embargo temporal al entrenamiento con validacion por grupos:

- `gait_analysis/build_transformer_sequence_dataset.py` guarda ahora `sequence_start_time` y `sequence_end_time` dentro del NPZ secuencial.
- `gait_analysis/train_transformer_sequence_classifier.py` incorpora `--embargo-seconds`.
- Por defecto, `--embargo-seconds 10.0`.
- En cada fold, antes de entrenar, se eliminan las secuencias de entrenamiento del mismo paciente que se solapan o quedan demasiado cerca del bloque de test expandido por ese margen.

## Por que 10 segundos

El dataset secuencial actual usa `sequence_length=9` con ventanas centradas cada 1 segundo. El contexto temporal completo queda alrededor de varios segundos, y el margen de 10 segundos es deliberadamente conservador para dejar una zona de silencio mayor que el contexto usado por la secuencia.

## Verificacion

Se regenero el dataset secuencial principal:

- `X shape: (1205, 9, 72)`
- `not_walking: 726`
- `walking: 479`
- `groups: 11`

Se ejecuto una prueba corta de entrenamiento de 1 epoca con `--embargo-seconds 10`.

Resultado de control:

- Filas totales: `1205`
- Filas eliminadas por embargo: `10`
- El entrenamiento completo de folds se ejecuto sin errores.

Esta prueba no debe interpretarse como resultado final de rendimiento, porque solo usa 1 epoca. Sirve para validar que el mecanismo de purga temporal funciona y queda reportado por fold.

## Impacto esperado

La validacion secuencial queda mas honesta: el modelo ya no puede entrenar con secuencias del mismo paciente situadas justo al lado del bloque que se esta evaluando. Esto reduce el sangrado de informacion entre train y test y hace mas defendibles las conclusiones sobre generalizacion temporal.
