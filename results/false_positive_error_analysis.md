# False-positive error analysis

Date: 2026-05-16

## Purpose

Analyze where the remaining false positives occur while waiting for additional
patient data from Influx/clinical ground truth.

## Main finding

The remaining false positives are not mainly isolated noisy windows. They form
consecutive temporal runs, especially in the same-patient not-walking segments
from `47046344M-104`.

For the RF + Transformer consensus, the largest false-positive runs are:

- `47046344M-104`, `2024-10-15 07:41:10` to `2024-10-15 07:43:24`
  - longest run: 11 consecutive windows
  - transformer mean probability: 0.9949
  - transformer max probability: 0.9970
- `47046344M-104`, `2024-10-15 07:35:38` to `2024-10-15 07:37:09`
  - longest run: 8 consecutive windows
  - transformer mean probability: 0.9770
  - transformer max probability: 0.9954

This suggests that the model is confusing a repeated non-walking movement
pattern with gait, not merely producing random threshold errors.

## Generated artifacts

- `results/false_positive_runs_transformer_rf_consensus.csv`
- `results/false_positive_runs_rf_hardneg_unweighted_raw.csv`

These files list false-positive runs by segment, start/end time, length and
mean/max walking probability.

## Interpretation

The model needs examples of this type of negative activity during training.
Adding one hard negative from `02548893X-118` helped in some areas, especially
the new-patient negative segment, but did not solve the difficult same-patient
negative runs.

The next data request should focus on:

1. More not-walking periods with movement artifacts.
2. More walking periods from patients not used in training.
3. Clarification of what activity occurs in the problematic `47046344M-104`
   false-positive intervals, because the model assigns them very high walking
   probability.

## Suggested message to tutor

The remaining false positives appear as sustained runs, not isolated windows.
The most problematic intervals are in patient `47046344M-104`, especially
`2024-10-15 07:41:10` to `07:43:24` and `2024-10-15 07:35:38` to `07:37:09`.
The transformer assigns probabilities close to 1.0 in parts of these intervals
although they are labeled as not walking.

Could we review what kind of movement these intervals contain and obtain more
examples of similar not-walking movement artifacts? It would also be important
to obtain walking and not-walking segments from new patients, because otherwise
tightening the classifier reduces false positives but also loses sensitivity to
real gait.
