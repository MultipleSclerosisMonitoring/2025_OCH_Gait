# Transformer false-positive audit: external all_valid

Input:
- `results/transformer_sequence_eval_predictions_new_influx_confirmed_final_all_valid.csv`
- threshold used for the base audit: `0.43`

## Main counts

- Valid rows: `780`
- False-positive windows: `254`
- True-positive windows: `4`
- False-positive runs: `35`

## Concentration by reference

- `05447093A-110`: `179` false-positive windows
- `47046344M-104`: `75` false-positive windows
- `02548893X-118`: `0` false-positive windows

## Concentration by segment

- `05447093A-110 | 2024-05-09 10:26:46 -> 2024-05-09 10:34:00`
  - false-positive windows: `179`
  - false-positive runs: `14`
  - mean probability: `0.7493`
  - max probability: `0.9932`
- `47046344M-104 | 2024-10-15 07:41:10 -> 2024-10-15 07:43:24`
  - false-positive windows: `63`
  - false-positive runs: `15`
  - mean probability: `0.7258`
  - max probability: `0.9918`
- `47046344M-104 | 2024-10-15 07:35:38 -> 2024-10-15 07:37:09`
  - false-positive windows: `12`
  - false-positive runs: `6`
  - mean probability: `0.8489`
  - max probability: `0.9664`

## What this means

- The false positives are not diffuse noise.
- They are concentrated in two not-walking intervals, one of them dominant.
- Raising the threshold reduces them, but does not eliminate the underlying issue.
- The next practical step is to inspect these two intervals as hard negatives and check whether:
  - the labels are correct,
  - the segment should be split,
  - or the model has learned motion-like patterns that are overgeneralized.

## Immediate follow-up

1. Review the two dominant intervals in raw signal.
2. Decide whether they should be re-labeled, split, or kept as hard negatives.
3. Refit calibration on a validation split that excludes these intervals.
