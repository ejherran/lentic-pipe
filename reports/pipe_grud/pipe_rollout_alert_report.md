# PIPE/GRU-D Rollout Alert Report v0

Generated at UTC: `2026-05-18T16:42:01.074213+00:00`
Started at UTC: `2026-05-18T16:41:45.694327+00:00`

## Scope

This report recursively rolls the frozen PIPE/GRU-D state model forward and aggregates alert statistics.
It is an operational simulation over `S(t)`, not an observed validation/test metric table.
Alert probabilities are the share of sampled trajectories whose IRC reaches the configured threshold.

## Configuration

- Origin scope: `latest-sites`
- Split filter: `all`
- Selected origins: `11,954`
- History length: `12`
- Rollout horizon: `3` month(s)
- Samples per origin: `64`
- Deterministic mode: `False`
- IRC weights: alpha=`0.5`, beta=`0.5`, gamma=`2.0`
- IRC alert threshold: `0.5`
- Alert probability threshold: `0.5`
- Calibrated bloom horizons available: `[1, 2, 3]`

## Horizon Summary

| horizon | rows | sites | origin range | forecast range | predicted alerts | alert rate | mean P(IRC alert) | p95 P(IRC alert) | mean IRC | p95 IRC | mean calibrated bloom probability |
|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 11,954 | 11,954 | `1971-05..2026-03` | `1971-06..2026-04` | 3,980 | 0.3329 | 0.3401 | 1.0000 | 0.4148 | 0.9114 | 0.1219 |
| 2 | 11,954 | 11,954 | `1971-05..2026-03` | `1971-07..2026-05` | 3,683 | 0.3081 | 0.3312 | 0.9531 | 0.4118 | 0.9058 | 0.1271 |
| 3 | 11,954 | 11,954 | `1971-05..2026-03` | `1971-08..2026-06` | 3,469 | 0.2902 | 0.3228 | 0.9219 | 0.4081 | 0.8978 | 0.1292 |

## Recent Top Alert Preview

Recent window: last `24` months per horizon.

| horizon | rank | source | site | origin | forecast | P(IRC alert) | IRC p95 | calibrated bloom mean | band |
|---:|---:|---|---|---|---|---:|---:|---:|---|
| 1 | 1 | `wqp` | `wqp:21FLKWAT_WQX-CHA-SUNAPEE-1` | `2024-06` | `2024-07` | 1.0000 | 0.9999 | 0.6990 | `very_high` |
| 1 | 2 | `wqp` | `wqp:21FLKWAT_WQX-CHA-WF-6-2` | `2024-06` | `2024-07` | 1.0000 | 1.0000 | 0.6963 | `very_high` |
| 1 | 3 | `wqp` | `wqp:21FLKWAT_WQX-CHA-WF-6-1` | `2024-06` | `2024-07` | 1.0000 | 1.0000 | 0.6921 | `very_high` |
| 1 | 4 | `wqp` | `wqp:21FLKWAT_WQX-CHA-WF-2-3` | `2024-06` | `2024-07` | 1.0000 | 0.9989 | 0.6845 | `very_high` |
| 1 | 5 | `wqp` | `wqp:21FLKWAT_WQX-SAR-LAKE-M-9-3` | `2024-08` | `2024-09` | 1.0000 | 1.0000 | 0.6746 | `very_high` |
| 2 | 1 | `wqp` | `wqp:21FLKWAT_WQX-CHA-WF-6-1` | `2024-06` | `2024-08` | 1.0000 | 0.9966 | 0.5515 | `very_high` |
| 2 | 2 | `wqp` | `wqp:21FLKWAT_WQX-CHA-WF-2-3` | `2024-06` | `2024-08` | 1.0000 | 0.9855 | 0.5041 | `very_high` |
| 2 | 3 | `wqp` | `wqp:21FLKWAT_WQX-PIN-AUTUMN-2` | `2024-04` | `2024-06` | 1.0000 | 0.9374 | 0.4837 | `very_high` |
| 2 | 4 | `wqp` | `wqp:21FLKWAT_WQX-CHA-WF-5-2` | `2024-06` | `2024-08` | 1.0000 | 0.9674 | 0.4274 | `very_high` |
| 2 | 5 | `wqp` | `wqp:21FLKWAT_WQX-CHA-SUNAPEE-1` | `2024-06` | `2024-08` | 0.9844 | 0.9920 | 0.5386 | `very_high` |
| 3 | 1 | `wqp` | `wqp:21FLKWAT_WQX-CHA-WF-3-3` | `2024-06` | `2024-09` | 0.9844 | 0.9931 | 0.4157 | `very_high` |
| 3 | 2 | `wqp` | `wqp:21FLKWAT_WQX-PIN-AUTUMN-2` | `2024-04` | `2024-07` | 0.9844 | 0.9334 | 0.4006 | `very_high` |
| 3 | 3 | `wqp` | `wqp:21FLKWAT_WQX-CHA-WF-2-3` | `2024-06` | `2024-09` | 0.9688 | 0.9762 | 0.3880 | `very_high` |
| 3 | 4 | `wqp` | `wqp:21FLKWAT_WQX-ORA-FAIRVIEWSO-2` | `2024-04` | `2024-07` | 0.9688 | 0.9795 | 0.3713 | `very_high` |
| 3 | 5 | `wqp` | `wqp:21FLKWAT_WQX-CHA-WF-5-1` | `2024-06` | `2024-09` | 0.9688 | 0.9469 | 0.3657 | `very_high` |

## Outputs

- Rollout alerts: `data/pipe_grud/pipe_rollout_alerts_v0.parquet`
- Summary: `reports/pipe_grud/pipe_rollout_alert_summary.csv`
- Top alerts: `reports/pipe_grud/pipe_rollout_top_alerts.csv`
- Recent top alerts: `reports/pipe_grud/pipe_rollout_recent_top_alerts.csv`
- Manifest: `reports/pipe_grud/pipe_rollout_alert_manifest.json`
