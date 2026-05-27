# Direct walking segment search

This note summarizes the walking-like segments found by direct Influx extraction and model scoring, without relying on Grafana panel exports.

## TABUENCA01-45

Extracted two direct blocks:

- `2024-04-25 16:14:50` to `16:25:44` local
- `2024-04-25 16:38:56` to `16:49:44` local

The RF model (`models/final_random_forest_model_with_manual_newpatients.joblib`, threshold `0.70`) found repeated short walking runs inside both blocks. The densest windows are around:

- `2024-04-25 16:15:21` to `16:15:27` local
- `2024-04-25 16:17:40` to `16:17:42` local
- `2024-04-25 16:22:14` to `16:22:35` local
- `2024-04-25 16:39:26` to `16:39:30` local
- `2024-04-25 16:41:55` to `16:41:57` local
- `2024-04-25 16:46:55` to `16:46:56` local
- `2024-04-25 16:48:21` to `16:48:37` local
- `2024-04-25 16:49:41` to `16:49:42` local

## 663495-44

Extracted block:

- `2025-03-22 18:02:12` to `18:04:27` local

The RF model found short walking bursts inside the block, mainly around:

- `2025-03-22 19:03:43` to `19:03:46` local
- `2025-03-22 19:03:48` to `19:03:58` local
- `2025-03-22 19:04:08` to `19:04:10` local

## 330034-32

Extracted block:

- `2025-02-25 11:28:03` to `11:32:31` local

The RF model found a more sustained walking burst than in `663495-44`, around:

- `2025-02-25 12:28:11` to `12:28:19` local
- `2025-02-25 12:30:40` to `12:31:26` local

## JOM250427-105

Existing direct extract:

- `2025-04-27 08:00:00` to `15:30:00` local

The RF model found multiple walking runs in this longer block. The longest cluster at threshold `0.60` is around:

- `2025-04-27 08:25:48` to `08:25:53` local
- `2025-04-27 08:29:25` to `08:29:29` local
- `2025-04-27 10:32:41` to `10:32:46` local
- `2025-04-27 10:41:27` to `10:41:32` local
- `2025-04-27 11:18:45` to `11:18:49` local
- `2025-04-27 11:26:22` to `11:26:26` local
- `2025-04-27 13:09:14` to `13:09:19` local
- `2025-04-27 13:13:41` to `13:13:45` local

## Practical conclusion

For direct walking search, the strongest current candidates are:

1. `JOM250427-105` for longer repeated walking clusters.
2. `TABUENCA01-45` for the richest mix of walking and short transitions.
3. `330034-32` for a compact but clearly mixed block.
4. `663495-44` for short walking bursts.

