# Comparacion CV3: bilateral vs unilateral

## Objetivo

Comparar la representacion bilateral sincronizada frente a una vista unilateral por extremidad usando los mismos clasificadores y la misma validacion cruzada estratificada de 3 folds.

## Resultados

| representation | model | accuracy_mean | accuracy_sd | precision_walking_mean | precision_walking_sd | recall_walking_mean | recall_walking_sd | f1_walking_mean | f1_walking_sd | f1_macro_mean | f1_macro_sd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bilateral | random_forest | 0.7394 | 0.0117 | 0.6497 | 0.0205 | 0.7856 | 0.0327 | 0.7107 | 0.0101 | 0.7367 | 0.0108 |
| bilateral | xgboost | 0.7618 | 0.0119 | 0.6886 | 0.0106 | 0.7590 | 0.0481 | 0.7216 | 0.0221 | 0.7566 | 0.0139 |
| bilateral | catboost | 0.7579 | 0.0149 | 0.6847 | 0.0118 | 0.7534 | 0.0597 | 0.7166 | 0.0265 | 0.7525 | 0.0170 |
| unilateral | random_forest | 0.7204 | 0.0151 | 0.6276 | 0.0135 | 0.7723 | 0.0310 | 0.6924 | 0.0189 | 0.7180 | 0.0155 |
| unilateral | xgboost | 0.7324 | 0.0182 | 0.6493 | 0.0217 | 0.7476 | 0.0158 | 0.6950 | 0.0182 | 0.7283 | 0.0180 |
| unilateral | catboost | 0.7343 | 0.0172 | 0.6452 | 0.0193 | 0.7742 | 0.0153 | 0.7038 | 0.0171 | 0.7315 | 0.0170 |

## Lectura principal

El mejor modelo bilateral es `xgboost` con F1 de marcha medio 0.7216.
El mejor modelo unilateral es `catboost` con F1 de marcha medio 0.7038.
La diferencia unilateral - bilateral en el mejor F1 de marcha es -0.0177.

## Interpretacion

La representacion bilateral sigue siendo superior cuando ambos pies estan disponibles, porque conserva informacion conjunta entre extremidades. La representacion unilateral pierde algo de rendimiento, pero mantiene resultados competitivos y permite trabajar con casos asimetricos o con un solo sensor util.

Por tanto, la recomendacion practica es mantener el modelo bilateral como modelo principal y usar la via unilateral como alternativa para pacientes/tramos donde la sincronizacion perfecta de ambos pies no sea clinicamente o tecnicamente fiable.
