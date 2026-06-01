# Revision automatica de senal raw

## Criterio

- `walking`: `acc_std_mean >= 0.05` y `gyro_std_mean >= 10.0`.
- `not_walking`: `acc_std_mean <= 0.05` y `gyro_std_mean <= 5.0`.
- Las metricas se calculan dentro del intervalo auditado con padding de 0.5 s.

## Resultado

- intervalos revisados: 99
- correcciones de ventana originales: 1014
- correcciones confirmadas por senal: 1014

### Decisiones por tipo

- `confirm_auto`: 99

### Resumen por referencia

| Referencia | Cambio | Decision | Intervalos | Ventanas |
|---|---|---|---:|---:|
| `02548893X-118` | `not_walking` -> `walking` | `confirm_auto` | 10 | 27 |
| `04845288Q-121` | `not_walking` -> `walking` | `confirm_auto` | 1 | 102 |
| `47046344M-104` | `walking` -> `not_walking` | `confirm_auto` | 5 | 36 |
| `ACL1998-96` | `walking` -> `not_walking` | `confirm_auto` | 36 | 295 |
| `AEMDHUG060-70` | `not_walking` -> `walking` | `confirm_auto` | 40 | 526 |
| `AGCHUG064-10` | `not_walking` -> `walking` | `confirm_auto` | 7 | 28 |

### Separacion observada

| Cambio | Intervalos | acc std min/med/max | gyro std min/med/max |
|---|---:|---:|---:|
| `not_walking` -> `walking` | 58 | 0.1600 / 0.5525 / 0.6954 | 74.4265 / 101.5310 / 118.1019 |
| `walking` -> `not_walking` | 41 | 0.0008 / 0.0017 / 0.0097 | 0.1266 / 0.3401 / 1.6803 |
