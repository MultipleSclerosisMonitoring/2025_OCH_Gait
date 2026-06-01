# False-positive review summary

Date: 2026-06-01

## Scope

This review focuses on the three dominant false-positive intervals from the
external transformer validation on `all_valid`:

- `47046344M-104`, `2024-10-15 07:41:10` to `07:43:24`
- `47046344M-104`, `2024-10-15 07:35:38` to `07:37:09`
- `05447093A-110`, `2024-05-09 10:26:46` to `10:34:00`

## Raw signal checks

The following raw extracts were queried from Influx and summarized with
`acc_norm` and `gyro_norm` statistics:

- `47046344M-104` short low-motion interval
  - `acc_std_mean = 0.0126`
  - `gyro_std_mean = 4.8631`
  - Interpretation: low-motion hard negative, keep as `not_walking`.

- `47046344M-104` high-activity interval
  - `acc_std_mean = 0.0516`
  - `gyro_std_mean = 13.4956`
  - Interpretation: structured movement, but not obviously clean walking from
    the raw summary alone. Keep as a review candidate.

- `05447093A-110` dominant false-positive run
  - `acc_std_mean = 0.1469`
  - `gyro_std_mean = 61.5069`
  - Interpretation: very strong movement, but the raw summary is not enough to
    auto-relabelling it as `walking`. Keep as a review candidate / hard
    negative until human confirmation.

- Known walking comparison for `47046344M-104`
  - `acc_std_mean = 0.0059`
  - `gyro_std_mean = 3.5956`
  - Interpretation: the false-positive intervals are not a trivial duplicate of
    this known walking reference.

## Decision

1. Keep `47046344M-104`, `07:35:38` to `07:37:09` as a hard negative.
2. Do not auto-relabel `47046344M-104`, `07:41:10` to `07:43:24`.
3. Do not auto-relabel `05447093A-110`, `10:26:46` to `10:34:00`.
4. Use these intervals as the next hard-negative review batch before retraining
   calibration.

## Next step

Build a small confirmed-correction batch from these intervals only after manual
review. Then retrain / recalibrate on a split that excludes those intervals from
the calibration set.
