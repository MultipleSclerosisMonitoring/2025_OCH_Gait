# Model error analysis

- model: all
- error_type: both
- rows: 5642
- false positives: 688
- false negatives: 1040
- false positive rate: 0.1756
- false negative rate: 0.6029

## Main patients
- TABUENCA01-45: fp=31, fn=490, error_windows=521, fp_rate=0.1558, fn_rate=0.4667
- 47046344M-104: fp=0, fn=437, error_windows=437, fp_rate=0.0000, fn_rate=0.9909
- AGCHUG064-10: fp=328, fn=0, error_windows=328, fp_rate=0.1445, fn_rate=0.0000
- 04845288Q-121: fp=228, fn=26, error_windows=254, fp_rate=0.5876, fn_rate=0.3023
- 02548893X-118: fp=68, fn=0, error_windows=68, fp_rate=0.5763, fn_rate=0.0000
- 05447093A-110: fp=27, fn=36, error_windows=63, fp_rate=0.0576, fn_rate=0.7826
- 330034-32: fp=6, fn=27, error_windows=33, fp_rate=0.0324, fn_rate=0.6923
- 663495-44: fp=0, fn=24, error_windows=24, fp_rate=0.0000, fn_rate=0.3810

## Main runs
- 04845288Q-121 | 2025-03-01 11:36:15.010000+00:00 -> 2025-03-01 11:37:57.010000+00:00 | 103 windows | mean_prob=0.9456 | max_prob=0.9949
- 47046344M-104 | 2024-10-15 07:45:25.010000+00:00 -> 2024-10-15 07:46:46.010000+00:00 | 82 windows | mean_prob=0.0383 | max_prob=0.3382
- 47046344M-104 | 2024-10-15 07:37:19.010000+00:00 -> 2024-10-15 07:38:09.010000+00:00 | 51 windows | mean_prob=0.0139 | max_prob=0.0779
- 47046344M-104 | 2024-10-15 07:34:41.020000+00:00 -> 2024-10-15 07:35:28.020000+00:00 | 48 windows | mean_prob=0.1027 | max_prob=0.6286
- 02548893X-118 | 2025-02-28 09:48:33.010000+00:00 -> 2025-02-28 09:49:18.010000+00:00 | 46 windows | mean_prob=0.9318 | max_prob=0.9821
- 47046344M-104 | 2024-10-15 07:47:58.010000+00:00 -> 2024-10-15 07:48:42.010000+00:00 | 45 windows | mean_prob=0.0170 | max_prob=0.1414
- 47046344M-104 | 2024-10-15 07:43:28.010000+00:00 -> 2024-10-15 07:44:11.010000+00:00 | 44 windows | mean_prob=0.0775 | max_prob=0.4560
- 47046344M-104 | 2024-10-15 07:34:04.020000+00:00 -> 2024-10-15 07:34:39.020000+00:00 | 36 windows | mean_prob=0.0151 | max_prob=0.1618
- 47046344M-104 | 2024-10-15 07:31:54.020000+00:00 -> 2024-10-15 07:32:28.020000+00:00 | 35 windows | mean_prob=0.0231 | max_prob=0.1198
- 47046344M-104 | 2024-10-15 07:39:39.010000+00:00 -> 2024-10-15 07:40:09.010000+00:00 | 31 windows | mean_prob=0.0840 | max_prob=0.5721
