# PIPE Neural ODE Rollout Backtest Report v0

Generated at UTC: `2026-06-15T19:41:12.832379+00:00`
Started at UTC: `2026-06-15T19:41:06.970719+00:00`

## Scope

This report evaluates recursive PIPE Neural ODE rollouts against observed future fuzzy states.
It is a historical backtest and should be compared with PIPE/GRU-D rollout backtests on the same sequence surface.

## Configuration

- Split filter: `test`
- Selected origins: `6,145`
- Evaluated rollout rows: `18,435`
- Max origins cap: `None`
- Rollout horizon: `3` month(s)
- Observed state source: `target`
- Reference backtest rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_test.parquet`
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
| 1 | 6,145 | 6,145 | 6,145 | `complete_horizons` |
| 2 | 6,145 | 6,145 | 6,145 | `complete_horizons` |
| 3 | 6,145 | 6,145 | 6,145 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `test` | 1 | `all` | 55,305 | 0.1237 | 0.1645 | 0.2483 | 0.0740 | 0.9375 |
| `test` | 1 | `irc1` | 6,145 | 0.1251 | 0.1367 | 0.0854 | 0.0883 | 0.8998 |
| `test` | 2 | `all` | 55,305 | 0.1368 | 0.1691 | 0.1911 | 0.0893 | 0.9499 |
| `test` | 2 | `irc1` | 6,145 | 0.1482 | 0.1736 | 0.1463 | 0.1143 | 0.9177 |
| `test` | 3 | `all` | 55,305 | 0.1466 | 0.1749 | 0.1621 | 0.1012 | 0.9619 |
| `test` | 3 | `irc1` | 6,145 | 0.1566 | 0.1934 | 0.1902 | 0.1261 | 0.9465 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.1344 | 0.6282 | 0.1111 | 0.4965 | 0.7455 |
| `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.0694 | 0.5883 | 0.1194 | 0.2665 | 0.6489 |
| `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.0578 | 0.5781 | 0.1260 | 0.2231 | 0.6244 |
| `irc_alert` | `test` | 1 | 6,145 | 0.4148 | 0.4073 | 0.8952 | 0.1046 | 0.8223 | 0.8555 |
| `irc_alert` | `test` | 2 | 6,145 | 0.4330 | 0.4093 | 0.8549 | 0.1322 | 0.7580 | 0.8094 |
| `irc_alert` | `test` | 3 | 6,145 | 0.4448 | 0.3958 | 0.8529 | 0.1424 | 0.7186 | 0.7934 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; it is not an operational deployment artifact.
- Recursive behavior can differ from one-step behavior because each forecast state becomes the next origin state.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_rows_matched_grud_test.parquet`
- State metrics: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_metrics_matched_grud_test.csv`
- Alert metrics: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_alert_metrics_matched_grud_test.csv`
- Diagnostic examples: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_examples_matched_grud_test.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_manifest_matched_grud_test.json`
