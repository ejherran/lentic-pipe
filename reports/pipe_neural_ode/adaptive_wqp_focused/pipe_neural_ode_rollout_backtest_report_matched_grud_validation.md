# PIPE Neural ODE Rollout Backtest Report v0

Generated at UTC: `2026-06-15T19:38:53.018662+00:00`
Started at UTC: `2026-06-15T19:38:47.719962+00:00`

## Scope

This report evaluates recursive PIPE Neural ODE rollouts against observed future fuzzy states.
It is a historical backtest and should be compared with PIPE/GRU-D rollout backtests on the same sequence surface.

## Configuration

- Split filter: `validation`
- Selected origins: `5,069`
- Evaluated rollout rows: `15,207`
- Max origins cap: `None`
- Rollout horizon: `3` month(s)
- Observed state source: `target`
- Reference backtest rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_validation.parquet`
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
| 1 | 5,069 | 5,069 | 5,069 | `complete_horizons` |
| 2 | 5,069 | 5,069 | 5,069 | `complete_horizons` |
| 3 | 5,069 | 5,069 | 5,069 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | `all` | 45,621 | 0.1290 | 0.1726 | 0.2529 | 0.0768 | 0.9306 |
| `validation` | 1 | `irc1` | 5,069 | 0.1274 | 0.1391 | 0.0845 | 0.0908 | 0.8919 |
| `validation` | 2 | `all` | 45,621 | 0.1439 | 0.1761 | 0.1833 | 0.0924 | 0.9416 |
| `validation` | 2 | `irc1` | 5,069 | 0.1508 | 0.1757 | 0.1416 | 0.1182 | 0.9187 |
| `validation` | 3 | `all` | 45,621 | 0.1528 | 0.1842 | 0.1706 | 0.1028 | 0.9521 |
| `validation` | 3 | `irc1` | 5,069 | 0.1622 | 0.2011 | 0.1934 | 0.1321 | 0.9410 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `validation` | 1 | 3,049 | 0.1345 | 0.1013 | 0.5542 | 0.0873 | 0.4512 | 0.7249 |
| `bloom_h` | `validation` | 2 | 3,158 | 0.1396 | 0.0475 | 0.5107 | 0.0978 | 0.2177 | 0.6276 |
| `bloom_h` | `validation` | 3 | 3,184 | 0.1435 | 0.0364 | 0.4550 | 0.1059 | 0.1554 | 0.5867 |
| `irc_alert` | `validation` | 1 | 5,069 | 0.4403 | 0.4186 | 0.8632 | 0.1191 | 0.7997 | 0.8422 |
| `irc_alert` | `validation` | 2 | 5,069 | 0.4472 | 0.4054 | 0.8214 | 0.1509 | 0.7142 | 0.7814 |
| `irc_alert` | `validation` | 3 | 5,069 | 0.4478 | 0.3630 | 0.7907 | 0.1686 | 0.6414 | 0.7549 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; it is not an operational deployment artifact.
- Recursive behavior can differ from one-step behavior because each forecast state becomes the next origin state.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_rows_matched_grud_validation.parquet`
- State metrics: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_metrics_matched_grud_validation.csv`
- Alert metrics: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_alert_metrics_matched_grud_validation.csv`
- Diagnostic examples: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_examples_matched_grud_validation.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_manifest_matched_grud_validation.json`
