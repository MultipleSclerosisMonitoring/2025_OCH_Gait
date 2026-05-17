# Patient Candidate Inventory

Date: 2026-05-17

## Goal

Identify additional patients and intervals that can increase dataset diversity
before retraining the gait classifiers.

## Inventory output

- Full ground-truth candidate inventory:
  - `experiment_configs/patient_candidate_inventory.csv`
- Influx coverage check for the first 40 prioritized candidates:
  - `experiment_configs/patient_candidate_inventory_checked_top40.csv`

Candidates are prioritized as:

1. new patients with both `walking` and `not_walking` labels,
2. new patients with only one available label,
3. holdout intervals from patients already used in training.

## Findings

The ground truth contains promising new-patient labels for:

- `05447093A-110`
- `330034-32`
- `663495-44`
- `TABUENCA01-45`

However, the Influx coverage check shows that most of those labeled intervals
currently return no records for both feet.

Valid intervals found so far:

| Reference | Interval | Label | Right records | Left records |
| --- | --- | --- | ---: | ---: |
| `05447093A-110` | `2024-05-09 10:26:46` to `2024-05-09 10:34:00` | `not_walking` | 128640 | 128712 |
| `02548893X-118` | `2025-02-28 09:48:07` to `2025-02-28 09:59:47` | `not_walking` | 206394 | 206604 |

The `05447093A-110` interval is useful as an additional new-patient negative
segment, but it does not solve the need for new-patient walking examples.

## Patients checked with no usable coverage in reviewed intervals

- `330034-32`: walking and not-walking intervals checked, zero records.
- `663495-44`: walking and not-walking intervals checked, zero records.
- `TABUENCA01-45`: many walking and not-walking intervals checked, zero records.
- `05447093A-110`: walking intervals checked, zero records.

## Interpretation

The main blocker is now data availability rather than model architecture.
The project has labels for several new patients, but the corresponding Influx
intervals do not currently expose usable two-foot IMU data under the configured
reference/tag/time settings.

## Next practical step

Use `05447093A-110` as a new-patient hard negative only if we accept losing it
as a pure external negative test segment. For real generalization, we still need
at least one new patient with valid walking data in both feet.

Before retraining, the reference/time mapping for `330034-32`, `663495-44`,
`TABUENCA01-45`, and the walking intervals of `05447093A-110` should be checked.
