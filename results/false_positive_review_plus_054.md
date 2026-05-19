# Revision de falsos positivos en pacientes no vistos

## Configuracion

- Dataset: `salidas_test/auto_extracts/main_binary_window_features_with_new_patients_plus_054.parquet`
- Validacion: leave-one-reference-out
- Modelos revisados: Random Forest, XGBoost y CatBoost

## Conteo global de falsos positivos

- XGBoost: 530
- CatBoost: 520
- Random Forest: 450

## Bloques con mas falsos positivos

### Random Forest

1. `04845288Q-121`, `11:32:31` a `11:40:38`
   - 257 falsos positivos acumulados
   - probabilidad media: `0.885`
   - bloque claramente problemático y de alta confianza
2. `02548893X-118`, `09:48:08` a `09:50:05`
   - 83 falsos positivos
   - probabilidad media: `0.693`
3. `TABUENCA01-45`, `14:15:19` a `14:49:41`
   - 54 falsos positivos
   - probabilidad media: `0.558`
4. `05447093A-110`, `08:27:03` a `09:44:50`
   - 48 falsos positivos
   - probabilidad media: `0.624`

### CatBoost

1. `04845288Q-121`, `11:32:31` a `11:40:38`
   - 255 falsos positivos
   - probabilidad media: `0.940`
2. `02548893X-118`, `09:48:24` a `09:49:18`
   - 53 falsos positivos
   - probabilidad media: `0.754`
3. `TABUENCA01-45`, `14:15:19` a `14:49:42`
   - 68 falsos positivos
   - probabilidad media: `0.630`
4. `05447093A-110`, `08:27:03` a `09:44:51`
   - 111 falsos positivos
   - probabilidad media: `0.614`

### XGBoost

1. `04845288Q-121`, `11:32:32` a `11:40:38`
   - 257 falsos positivos
   - probabilidad media: `0.935`
2. `02548893X-118`, `09:48:13` a `09:49:28`
   - 70 falsos positivos
   - probabilidad media: `0.811`
3. `05447093A-110`, `08:27:02` a `08:27:18`
   - 17 falsos positivos en una racha corta
   - probabilidad media: `0.702`
4. `TABUENCA01-45`, `14:15:19` a `14:49:42`
   - 34 falsos positivos
   - probabilidad media: `0.624`

## Lectura tecnica

El error no esta repartido de forma uniforme. Se concentra en dos referencias
claramente dominantes:

- `04845288Q-121`
- `02548893X-118`

Esas dos referencias concentran las rachas mas largas y las probabilidades mas
altas, por lo que son los mejores candidatos para:

1. revisar manualmente si hay desalineacion o transiciones mal etiquetadas,
2. extraer hard negatives,
3. reforzar el dataset con tramos no marcha visualmente parecidos a marcha.

El paciente nuevo `05447093A-110` aparece como fuente secundaria de errores, pero
con probabilidad bastante mas moderada. `TABUENCA01-45` muestra rachas largas,
aunque menos extremas. `330034-32` es marginal.

## Conclusión breve

Los falsos positivos no son aleatorios: se agrupan en pocos pacientes y en
bloques temporales largos. Eso encaja con el diagnostico previo de que el
problema principal sigue siendo la diversidad y la cobertura real de patrones
difíciles, no una falta de capacidad del clasificador.
