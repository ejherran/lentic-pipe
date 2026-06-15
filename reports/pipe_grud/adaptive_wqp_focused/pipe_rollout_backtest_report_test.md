# PIPE/GRU-D Rollout Backtest Report v0

Generated at UTC: `2026-06-15T16:59:27.216077+00:00`
Started at UTC: `2026-06-15T16:59:20.216378+00:00`

## Scope

This report evaluates recursive PIPE/GRU-D rollouts against observed future fuzzy states.
Unlike the operational rollout artifact, this is a historical backtest and can be used to judge predictive behavior.

## Configuration

- Split filter: `test`
- Selected origins: `6,145`
- Evaluated rollout rows: `18,435`
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
| 1 | 7,582 | 7,582 | 6,145 | `complete_horizons` |
| 2 | 7,582 | 6,826 | 6,145 | `complete_horizons` |
| 3 | 7,582 | 6,145 | 6,145 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `test` | 1 | `all` | 55,305 | 0.1233 | 0.1645 | 0.2503 | 0.0729 | 0.7483 |
| `test` | 1 | `irc1` | 6,145 | 0.1236 | 0.1367 | 0.0958 | 0.0837 | 0.8871 |
| `test` | 2 | `all` | 55,305 | 0.1342 | 0.1691 | 0.2066 | 0.0829 | 0.7662 |
| `test` | 2 | `irc1` | 6,145 | 0.1461 | 0.1736 | 0.1586 | 0.1097 | 0.9120 |
| `test` | 3 | `all` | 55,305 | 0.1394 | 0.1749 | 0.2031 | 0.0885 | 0.7801 |
| `test` | 3 | `irc1` | 6,145 | 0.1553 | 0.1934 | 0.1971 | 0.1233 | 0.9390 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.1385 | 0.6559 | 0.1086 | 0.5282 | 0.7620 |
| `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.0790 | 0.6131 | 0.1169 | 0.2990 | 0.6650 |
| `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.0677 | 0.5983 | 0.1236 | 0.2503 | 0.6375 |
| `irc_alert` | `test` | 1 | 6,145 | 0.4148 | 0.4099 | 0.9013 | 0.1059 | 0.8215 | 0.8523 |
| `irc_alert` | `test` | 2 | 6,145 | 0.4330 | 0.4093 | 0.8630 | 0.1329 | 0.7554 | 0.8071 |
| `irc_alert` | `test` | 3 | 6,145 | 0.4448 | 0.4057 | 0.8547 | 0.1424 | 0.7278 | 0.7923 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.
- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_test.parquet`
- State metrics: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_metrics_test.csv`
- Alert metrics: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_alert_metrics_test.csv`
- Diagnostic examples: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_examples_test.csv`
- Manifest: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_manifest_test.json`
