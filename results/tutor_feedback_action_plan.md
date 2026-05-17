# Tutor feedback action plan

Date: 2026-05-17

## Critical points accepted

The current system is limited by dataset diversity and by methodological
assumptions in the signal pipeline:

- The input representation is mostly spectral power, so it can confuse gait
  with rhythmic low-frequency artifacts.
- Both feet are forced into a strict common time grid, which may hide clinically
  relevant asymmetry.
- The transformer is too data-hungry for the current number of patients and
  independent temporal blocks.
- Temporal smoothing and RF/Transformer consensus reduce false positives, but
  they are post-processing patches and do not solve the feature-learning issue.
- Manual ground-truth handling and possible timing offsets remain a risk.
- The dataset still has too few patients, so this is the main bottleneck.

## Code changes implemented now

Three low-risk technical changes were added to make the pipeline more robust:

1. Linear detrending before the periodogram
   - Config key: `spectrogram.detrend`
   - Current value in `experiment_configs/config_window_1s.yaml`: `linear`
   - Motivation: reduce low-frequency energy caused by drift or gradual sensor
     displacement.

2. Bounded interpolation during resampling
   - Config key: `spectrogram.max_interpolate_gap_s`
   - Current value: `0.25`
   - Motivation: avoid filling long sensor dropouts with artificial smooth
     curves that can look like slow gait.

3. Window completeness tracking
   - Config key: `spectrogram.min_window_completeness`
   - Current value: `0.95`
   - Output column: `sample_completeness`
   - Motivation: keep traceability of how much real data supports each spectral
     window.

## Validation change implemented now

Temporal-block cross-validation now supports an embargo zone:

```bash
poetry run python -m gait_analysis.run_baseline_grouped_cv \
  -i salidas_test/auto_extracts/main_binary_window_features.parquet \
  --embargo-seconds 15 \
  -o results/baseline_grouped_cv_embargo15.csv
```

This removes training rows from the same patient around the test block, reducing
leakage between overlapping or nearby windows.

With a 15-second embargo, the Random Forest result is:

- row-weighted accuracy: `0.5468`
- row-weighted F1 walking: `0.3838`
- row-weighted recall walking: `0.4986`

This is a more conservative estimate than validations without a temporal safety
margin.

## What should not be overclaimed

These changes do not solve generalization by themselves. They improve the
methodological rigor of the pipeline and reduce one plausible source of false
positives, but the main limitation remains the lack of diverse patients and
well-labeled hard negatives.

## Next data request

The most valuable next step is to obtain substantially more data:

- walking and not-walking segments from new patients,
- not-walking segments with movement artifacts,
- clinical clarification of the false-positive intervals in `47046344M-104`,
- confirmation of time-zone alignment between ground truth and InfluxDB.

Without those data, further architecture changes are likely to tune the current
small dataset rather than improve real generalization.
