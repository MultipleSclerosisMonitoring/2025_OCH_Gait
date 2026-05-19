# Mejora: modelado independiente por extremidad

## Problema abordado

El pipeline principal bilateral exige que ambos pies tengan ventanas validas en una rejilla temporal comun. Esta decision es robusta para comparar extremidades, pero puede descartar informacion clinicamente util cuando un paciente presenta asimetria fuerte, arrastre de un pie o disponibilidad parcial de sensores.

## Cambios implementados

### 1. Extraccion temporal unilateral

`gait_analysis/extract_temporal_window_features.py` incorpora ahora:

- `--foot-mode paired`: modo por defecto, exige ventanas validas simultaneas en ambos pies.
- `--foot-mode unilateral`: genera una fila independiente por pie disponible.
- `--fallback-label-column`: permite usar una etiqueta del CSV de entrada cuando el centro de ventana no aparece en el Excel de ground truth.

En modo unilateral:

- no se fuerza interseccion temporal Right/Left;
- cada pie se procesa con su propio rango temporal valido;
- la salida incluye columna `foot`;
- las features se nombran sin prefijo Right/Left para que el modelo pueda aprender una representacion comun por extremidad.

### 2. Conversor unilateral compatible con el dataset actual

`gait_analysis/build_unilateral_window_dataset.py` ya existia, pero esperaba columnas tipo `spec_Right_*` o `temp_Left_*`. Se ha actualizado para aceptar tambien el formato actual:

- `Right_Ax_p_000`
- `Left_Gz_p_003`
- etc.

Esto permite transformar el dataset bilateral existente en una vista unilateral sin reextraer datos.

## Verificacion

Se genero una vista unilateral desde:

- `salidas_test/auto_extracts/main_binary_window_features.parquet`

Salida:

- `results/unilateral_window_dataset_smoke.parquet`

Resultado:

- filas de entrada: `1293`
- filas unilaterales: `2586`
- pie izquierdo: `1293`
- pie derecho: `1293`
- features: `37`
- clase no marcha: `1532`
- clase marcha: `1054`

Tambien se intento un tramo marcado previamente como `invalid_single_foot`, pero con la configuracion actual no genero ventanas validas etiquetadas. Esto indica que esos tramos requieren revisar cobertura/offset/ground truth antes de incorporarlos automaticamente.

## Impacto esperado

El proyecto ya no queda limitado a una unica representacion bilateral rigida. Ahora hay dos contratos de datos:

- bilateral sincronizado, util cuando ambos pies estan disponibles y se quiere explotar la relacion entre extremidades;
- unilateral por pie, util para asimetrias, sensores parciales y pacientes donde una extremidad domina la senal.

Esto responde al comentario clinico del tutor sin introducir todavia una arquitectura compleja de atencion cruzada asincrona, que requeriria mas datos para entrenarse de forma fiable.
