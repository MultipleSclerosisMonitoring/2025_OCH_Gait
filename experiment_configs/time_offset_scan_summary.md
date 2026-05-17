# Time Offset Scan Summary

Date: 2026-05-17

## Goal

Find whether the missing new-patient walking intervals are truly absent from
Influx or shifted relative to the ground-truth timestamps.

## Outputs

- `experiment_configs/patient_walking_time_offset_scan.csv`
- `experiment_configs/patient_not_walking_time_offset_scan.csv`
- `experiment_configs/new_patient_shifted_windows.csv`

## Main finding

The issue is not simply lack of data. Several new-patient intervals have strong
two-foot Influx coverage when the ground-truth interval is shifted in time:

- `TABUENCA01-45`: best coverage with `-120 min`
- `330034-32`: best coverage with `-60 min`
- `663495-44`: best coverage with `-60 min`
- `05447093A-110`: walking intervals show coverage with `-120 min`

This indicates a patient/session-specific time alignment problem between the
ground-truth labels and the timestamps queried in Influx.

## Candidate windows generated

`experiment_configs/new_patient_shifted_windows.csv` contains shifted candidate
windows for:

- `TABUENCA01-45`
- `330034-32`
- `663495-44`

These references include both walking and not-walking intervals with data in
both feet after applying the detected offset.

## Important caution

The shifted windows should not be treated as final training data blindly. Before
training, the shifted labels must be cleaned for overlaps and reviewed as a
consistent session-level correction. In particular, `TABUENCA01-45` has dense
alternating labels and at least one suspicious overlap around the `16:48:19`
ground-truth timestamp.

## Next step

Clean `new_patient_shifted_windows.csv` into a non-overlapping extraction plan,
then extract spectrograms with the corrected signal pipeline:

- `detrend: linear`
- bounded interpolation
- `sample_completeness`

After extraction, rebuild the dataset and evaluate again with patient-level and
temporal-block validation.
