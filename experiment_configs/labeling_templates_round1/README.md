# Patient Labeling Templates

Input timezone: `UTC`
Display timezone: `Europe/Madrid`
Review block length: `10` minutes

## How To Label

1. Open each review block in Grafana using `review_from_local` and `review_until_local`.
2. Add precise labeled intervals in `label_from_local` and `label_until_local`.
3. Set `mov_type` to `walking` or `not_walking` only when the segment is clear.
4. Leave ambiguous blocks blank and explain the reason in `review_notes`.
5. Use `label_quality` values such as `clear`, `short`, `transition` or `ambiguous`.

The UTC columns are included so accepted labels can be merged into the reproducible ground-truth CSV without another timezone guess.

## Patients

| Reference | priority | review_blocks | first_review | last_review | total_records |
| --- | --- | --- | --- | --- | --- |
| 54217882M-109 | 1 | 90 | 2025-03-19 12:00:00 | 2025-03-20 03:00:00 | 30173610 |
| 77370299R-115 | 2 | 93 | 2024-11-04 07:00:00 | 2024-11-04 22:30:00 | 24544038 |
| ACL1998-96 | 3 | 36 | 2025-07-16 08:00:00 | 2025-07-16 14:00:00 | 8154942 |
| AEMDHUG060-70 | 5 | 12 | 2026-04-28 12:00:00 | 2026-04-28 14:00:00 | 718788 |
| AGCHUG064-10 | 6 | 168 | 2026-05-05 10:00:00 | 2026-05-06 14:00:00 | 53947704 |

## Source Candidates

| Reference | priority | shifted_datefrom | shifted_dateuntil | offset_minutes | right_records | left_records | total_records |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 54217882M-109 | 1 | 2025-03-19 11:00:00 | 2025-03-20 02:00:00 | -60 | 15095238 | 15078372 | 30173610 |
| 77370299R-115 | 2 | 2024-11-04 06:00:00 | 2024-11-04 21:30:00 | -60 | 12320892 | 12223146 | 24544038 |
| ACL1998-96 | 3 | 2025-07-16 06:00:00 | 2025-07-16 12:00:00 | -120 | 4227516 | 3927426 | 8154942 |
| AEMDHUG060-70 | 5 | 2026-04-28 10:00:00 | 2026-04-28 12:00:00 | -120 | 358464 | 360324 | 718788 |
| AGCHUG064-10 | 6 | 2026-05-05 08:00:00 | 2026-05-06 12:00:00 | -120 | 27237912 | 26709792 | 53947704 |
