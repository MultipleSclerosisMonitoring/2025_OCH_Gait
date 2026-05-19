# Mejora: correccion de tendencia lineal antes del espectro

## Problema abordado

Las senales inerciales pueden contener deriva lenta por temperatura, colocacion del sensor o pequenos reajustes fisicos. Si esa deriva entra directamente al periodograma, aumenta la energia en frecuencias bajas, justo donde tambien aparece parte de la marcha humana.

## Estado del pipeline

El motor espectral ya aplica la opcion `detrend` de `scipy.signal.periodogram`:

- `detrend: linear` elimina una tendencia lineal antes de calcular la densidad espectral de potencia.
- `detrend: constant` solo elimina un desplazamiento constante.
- `detrend: none` permite desactivarlo.

La configuracion principal `config_window_1s.yaml` ya estaba usando:

- `detrend: linear`

## Cambio realizado

Se dejo explicito `detrend: linear` tambien en las configuraciones de ventana de 3s, 5s y 10s:

- `experiment_configs/config_window_3s.yaml`
- `experiment_configs/config_window_5s.yaml`
- `experiment_configs/config_window_10s.yaml`

Tambien se explicitaron las reglas de robustez ante huecos de sensor en esas configuraciones:

- `max_interpolate_gap_s: 0.25`
- `min_window_completeness: 0.95`

## Impacto esperado

La representacion espectral queda menos contaminada por rampas lentas no relacionadas con la marcha. Esto reduce la posibilidad de que derivas fisicas del sensor acumulen potencia artificial en baja frecuencia y sean confundidas por el clasificador con patrones de marcha.
