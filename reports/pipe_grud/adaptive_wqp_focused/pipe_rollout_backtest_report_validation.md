# PIPE/GRU-D Rollout Backtest Report v0

Generated at UTC: `2026-06-15T16:55:31.492904+00:00`
Started at UTC: `2026-06-15T16:55:25.303630+00:00`

## Scope

This report evaluates recursive PIPE/GRU-D rollouts against observed future fuzzy states.
Unlike the operational rollout artifact, this is a historical backtest and can be used to judge predictive behavior.

## Configuration

- Split filter: `validation`
- Selected origins: `5,069`
- Evaluated rollout rows: `15,207`
- Max origins cap: `None`
- History length: `12`
- Rollout horizon: `3` month(s)
- Observed state source: `target`
- Samples per origin: `128`
- Deterministic mode: `False`
- Horizon policy: `complete`
- IRC weights: alpha=`0.5`, beta=`0.5`, gamma=`2.0`
- IRC alert threshold: `0.5`
- Alert probability threshold: `0.5`
- Random seed: `1729`
- Calibrated bloom horizons available: `[1, 2, 3]`

## Future Availability

| horizon | eligible origins | origins with observed future | selected origins | policy |
|---:|---:|---:|---:|---|
| 1 | 7,079 | 7,079 | 5,069 | `complete_horizons` |
| 2 | 7,079 | 6,038 | 5,069 | `complete_horizons` |
| 3 | 7,079 | 5,069 | 5,069 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | `all` | 45,621 | 0.1273 | 0.1726 | 0.2627 | 0.0752 | 0.7411 |
| `validation` | 1 | `irc1` | 5,069 | 0.1265 | 0.1391 | 0.0906 | 0.0865 | 0.8627 |
| `validation` | 2 | `all` | 45,621 | 0.1422 | 0.1761 | 0.1929 | 0.0870 | 0.7531 |
| `validation` | 2 | `irc1` | 5,069 | 0.1490 | 0.1757 | 0.1517 | 0.1138 | 0.8980 |
| `validation` | 3 | `all` | 45,621 | 0.1476 | 0.1842 | 0.1987 | 0.0924 | 0.7678 |
| `validation` | 3 | `irc1` | 5,069 | 0.1611 | 0.2011 | 0.1990 | 0.1292 | 0.9292 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `validation` | 1 | 3,049 | 0.1345 | 0.1154 | 0.5814 | 0.0854 | 0.5244 | 0.7510 |
| `bloom_h` | `validation` | 2 | 3,158 | 0.1396 | 0.0605 | 0.5531 | 0.0951 | 0.2993 | 0.6765 |
| `bloom_h` | `validation` | 3 | 3,184 | 0.1435 | 0.0393 | 0.5115 | 0.1021 | 0.1729 | 0.5991 |
| `irc_alert` | `validation` | 1 | 5,069 | 0.4403 | 0.4194 | 0.8703 | 0.1216 | 0.7997 | 0.8414 |
| `irc_alert` | `validation` | 2 | 5,069 | 0.4472 | 0.4131 | 0.8217 | 0.1507 | 0.7225 | 0.7817 |
| `irc_alert` | `validation` | 3 | 5,069 | 0.4478 | 0.3942 | 0.7910 | 0.1682 | 0.6656 | 0.7479 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.
- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_validation.parquet`
- State metrics: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_metrics_validation.csv`
- Alert metrics: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_alert_metrics_validation.csv`
- Diagnostic examples: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_examples_validation.csv`
- Manifest: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_manifest_validation.json`
