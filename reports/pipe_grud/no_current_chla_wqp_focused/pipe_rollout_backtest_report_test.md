# PIPE/GRU-D Rollout Backtest Report v0

Generated at UTC: `2026-06-12T22:50:01.544553+00:00`
Started at UTC: `2026-06-12T22:49:54.733961+00:00`

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
- Calibrated bloom horizons available: `[]`

## Future Availability

| horizon | eligible origins | origins with observed future | selected origins | policy |
|---:|---:|---:|---:|---|
| 1 | 7,582 | 7,582 | 6,145 | `complete_horizons` |
| 2 | 7,582 | 6,826 | 6,145 | `complete_horizons` |
| 3 | 7,582 | 6,145 | 6,145 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `test` | 1 | `all` | 55,305 | 0.1671 | 0.2424 | 0.3107 | 0.1111 | 0.7817 |
| `test` | 1 | `irc1` | 6,145 | 0.1969 | 0.2583 | 0.2378 | 0.1656 | 0.7689 |
| `test` | 2 | `all` | 55,305 | 0.1853 | 0.2501 | 0.2592 | 0.1276 | 0.7815 |
| `test` | 2 | `irc1` | 6,145 | 0.2120 | 0.2887 | 0.2658 | 0.1740 | 0.8024 |
| `test` | 3 | `all` | 55,305 | 0.2011 | 0.2599 | 0.2264 | 0.1424 | 0.7630 |
| `test` | 3 | `irc1` | 6,145 | 0.2217 | 0.3124 | 0.2901 | 0.1813 | 0.8088 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc_alert` | `test` | 1 | 6,145 | 0.4544 | 0.4915 | 0.7963 | 0.1684 | 0.7579 | 0.7421 |
| `irc_alert` | `test` | 2 | 6,145 | 0.4692 | 0.4343 | 0.7456 | 0.1754 | 0.6903 | 0.7418 |
| `irc_alert` | `test` | 3 | 6,145 | 0.4781 | 0.4037 | 0.7276 | 0.1857 | 0.6283 | 0.7150 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.
- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_rows_test.parquet`
- State metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_metrics_test.csv`
- Alert metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_alert_metrics_test.csv`
- Diagnostic examples: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_examples_test.csv`
- Manifest: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_manifest_test.json`
