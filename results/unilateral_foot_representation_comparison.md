# Comparacion bilateral y unilateral por pie

Este experimento responde a la limitacion metodologica sobre la alineacion
estricta entre ambos pies. El dataset principal seguia una representacion
bilateral: cada fila contenia simultaneamente las features del pie derecho y del
pie izquierdo en el mismo centro temporal.

Para comprobar si esa hipotesis estaba penalizando al modelo, se construyo una
vista unilateral a partir del dataset espectral + temporal ampliado. En esta
vista cada ventana genera dos filas independientes:

- una fila para el pie derecho;
- una fila para el pie izquierdo.

Las columnas especificas de pie se renombraron a un espacio comun de features
(`spec_*` y `temp_*`) y se eliminaron las comparaciones directas entre pies. El
dataset resultante contiene 6.744 filas, 157 features y las mismas etiquetas que
el dataset bilateral original.

## Comparacion de resultados

F1 macro medio:

| Validacion | Representacion | Random Forest | XGBoost | CatBoost |
|---|---|---:|---:|---:|
| CV estratificada 3 folds | Bilateral espectral + temporal | 0.8972 | 0.9339 | 0.9353 |
| CV estratificada 3 folds | Unilateral por pie | 0.8754 | 0.9075 | 0.9119 |
| Leave-one-reference-out | Bilateral espectral + temporal | 0.5702 | 0.5326 | 0.5443 |
| Leave-one-reference-out | Unilateral por pie | 0.5315 | 0.5297 | 0.5492 |
| Bloques temporales + embargo 15 s | Bilateral espectral + temporal | 0.4958 | 0.4614 | 0.4737 |
| Bloques temporales + embargo 15 s | Unilateral por pie | 0.4733 | 0.4528 | 0.4561 |

## Interpretacion

La representacion unilateral permite relajar parcialmente la dependencia del
modelo respecto a una lectura conjunta de ambos pies, porque el clasificador
aprende patrones de marcha/no marcha en cada extremidad por separado. Sin
embargo, con los datos actuales no mejora de forma global al enfoque bilateral.

En CV estratificada, el modelo bilateral es claramente superior. En validacion
por referencia, CatBoost unilateral mejora muy ligeramente a CatBoost bilateral,
pero Random Forest y XGBoost no mejoran. En bloques temporales con embargo, el
bilateral vuelve a ser superior.

La conclusion practica es que la critica del tutor queda evaluada, pero no
justifica sustituir ahora el modelo principal por uno unilateral. La mejor
opcion actual es conservar el modelo bilateral espectral + temporal como
referencia principal y documentar el unilateral como prueba de sensibilidad. Si
se incorporan mas pacientes con asimetrias severas o perdidas reales de un pie,
esta comparacion deberia repetirse, porque el resultado podria cambiar con mayor
diversidad clinica.
