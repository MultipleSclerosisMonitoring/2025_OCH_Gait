# Model error analysis

- model: catboost
- error_type: both
- rows: 5642
- false positives: 1630
- false negatives: 756
- false positive rate: 0.4161
- false negative rate: 0.4383

## Main patients
- AGCHUG064-10: fp=1053, fn=0, error_windows=1053, fp_rate=0.4639, fn_rate=0.0000
- 47046344M-104: fp=1, fn=434, error_windows=435, fp_rate=0.0038, fn_rate=0.9841
- TABUENCA01-45: fp=82, fn=245, error_windows=327, fp_rate=0.4121, fn_rate=0.2333
- 04845288Q-121: fp=244, fn=23, error_windows=267, fp_rate=0.6289, fn_rate=0.2674
- 05447093A-110: fp=141, fn=24, error_windows=165, fp_rate=0.3006, fn_rate=0.5217
- 02548893X-118: fp=79, fn=0, error_windows=79, fp_rate=0.6695, fn_rate=0.0000
- 330034-32: fp=30, fn=20, error_windows=50, fp_rate=0.1622, fn_rate=0.5128
- 663495-44: fp=0, fn=10, error_windows=10, fp_rate=0.0000, fn_rate=0.1587

## Main runs
- 04845288Q-121 | 2025-03-01 11:36:15.010000+00:00 -> 2025-03-01 11:37:57.010000+00:00 | 103 windows | mean_prob=0.9456 | max_prob=0.9949
- 47046344M-104 | 2024-10-15 07:45:25.010000+00:00 -> 2024-10-15 07:46:46.010000+00:00 | 82 windows | mean_prob=0.0383 | max_prob=0.3382
- 47046344M-104 | 2024-10-15 07:37:19.010000+00:00 -> 2024-10-15 07:38:09.010000+00:00 | 51 windows | mean_prob=0.0139 | max_prob=0.0779
- 02548893X-118 | 2025-02-28 09:48:33.010000+00:00 -> 2025-02-28 09:49:19.010000+00:00 | 47 windows | mean_prob=0.9266 | max_prob=0.9821
- 47046344M-104 | 2024-10-15 07:47:58.010000+00:00 -> 2024-10-15 07:48:42.010000+00:00 | 45 windows | mean_prob=0.0170 | max_prob=0.1414
- 47046344M-104 | 2024-10-15 07:43:28.010000+00:00 -> 2024-10-15 07:44:11.010000+00:00 | 44 windows | mean_prob=0.0775 | max_prob=0.4560
- 04845288Q-121 | 2025-03-01 11:38:44.010000+00:00 -> 2025-03-01 11:39:22.010000+00:00 | 39 windows | mean_prob=0.9354 | max_prob=0.9883
- AGCHUG064-10 | 2026-05-05 09:10:33.030000+00:00 -> 2026-05-05 09:11:09.030000+00:00 | 37 windows | mean_prob=0.7065 | max_prob=0.8669
- 47046344M-104 | 2024-10-15 07:34:04.020000+00:00 -> 2024-10-15 07:34:39.020000+00:00 | 36 windows | mean_prob=0.0151 | max_prob=0.1618
- 47046344M-104 | 2024-10-15 07:31:54.020000+00:00 -> 2024-10-15 07:32:28.020000+00:00 | 35 windows | mean_prob=0.0231 | max_prob=0.1198
