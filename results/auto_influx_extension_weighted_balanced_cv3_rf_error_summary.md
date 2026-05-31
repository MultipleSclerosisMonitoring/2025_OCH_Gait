# Model error analysis

- model: random_forest
- error_type: both
- rows: 21424
- false positives: 4209
- false negatives: 3482
- false positive rate: 0.3408
- false negative rate: 0.3837

## Main patients
- ACL1998-96: fp=1261, fn=2291, error_windows=3552, fp_rate=0.3631, fn_rate=0.5686
- AGCHUG064-10: fp=1080, fn=212, error_windows=1292, fp_rate=0.4852, fn_rate=0.6199
- AEMDHUG060-70: fp=1061, fn=0, error_windows=1061, fp_rate=0.6183, fn_rate=0.0000
- 47046344M-104: fp=8, fn=391, error_windows=399, fp_rate=0.0308, fn_rate=0.8866
- 04845288Q-121: fp=260, fn=20, error_windows=280, fp_rate=0.6701, fn_rate=0.2326
- AMGHUG014-3: fp=90, fn=85, error_windows=175, fp_rate=0.1883, fn_rate=0.3148
- 77370299R-115: fp=65, fn=76, error_windows=141, fp_rate=0.1578, fn_rate=0.1905
- 54217882M-109: fp=0, fn=126, error_windows=126, fp_rate=0.0000, fn_rate=0.3387
- VCLHUG026-16: fp=38, fn=82, error_windows=120, fp_rate=0.0471, fn_rate=0.1723
- TABUENCA01-45: fp=118, fn=1, error_windows=119, fp_rate=0.5021, fn_rate=0.0009

## Main runs
- AEMDHUG060-70 | 2026-04-29 15:22:01.010000+00:00 -> 2026-04-29 15:28:53.010000+00:00 | 413 windows | mean_prob=0.8085 | max_prob=0.8730
- AEMDHUG060-70 | 2026-04-28 10:51:39+00:00 -> 2026-04-28 10:53:43+00:00 | 125 windows | mean_prob=0.7527 | max_prob=0.8503
- 04845288Q-121 | 2025-03-01 11:36:15.010000+00:00 -> 2025-03-01 11:37:57.010000+00:00 | 103 windows | mean_prob=0.8931 | max_prob=0.9334
- ACL1998-96 | 2025-07-16 08:40:30.020000+00:00 -> 2025-07-16 08:42:04.020000+00:00 | 95 windows | mean_prob=0.1800 | max_prob=0.2724
- AEMDHUG060-70 | 2026-04-28 10:50:06+00:00 -> 2026-04-28 10:51:33+00:00 | 88 windows | mean_prob=0.7412 | max_prob=0.8319
- 02548893X-118 | 2025-02-28 09:48:08.010000+00:00 -> 2025-02-28 09:49:29.010000+00:00 | 82 windows | mean_prob=0.7274 | max_prob=0.8722
- ACL1998-96 | 2025-07-16 08:39:08.020000+00:00 -> 2025-07-16 08:40:26.020000+00:00 | 79 windows | mean_prob=0.1821 | max_prob=0.3547
- ACL1998-96 | 2025-07-16 08:36:30.020000+00:00 -> 2025-07-16 08:37:37.020000+00:00 | 68 windows | mean_prob=0.1891 | max_prob=0.2770
- ACL1998-96 | 2025-07-16 08:52:20.020000+00:00 -> 2025-07-16 08:53:23.020000+00:00 | 64 windows | mean_prob=0.1911 | max_prob=0.4109
- AEMDHUG060-70 | 2026-04-28 10:54:39+00:00 -> 2026-04-28 10:55:41+00:00 | 63 windows | mean_prob=0.7579 | max_prob=0.8440
