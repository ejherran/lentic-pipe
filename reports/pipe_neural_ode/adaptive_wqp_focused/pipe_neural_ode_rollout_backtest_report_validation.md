# PIPE Neural ODE Rollout Backtest Report v0

Generated at UTC: `2026-06-15T20:06:29.818146+00:00`
Started at UTC: `2026-06-15T20:06:09.461783+00:00`

## Scope

This report evaluates recursive PIPE Neural ODE rollouts against observed future fuzzy states.
It is a historical backtest and should be compared with PIPE/GRU-D rollout backtests on the same sequence surface.

## Configuration

- Split filter: `validation`
- Selected origins: `49,096`
- Evaluated rollout rows: `147,288`
- Max origins cap: `None`
- Rollout horizon: `3` month(s)
- Observed state source: `target`
- Reference backtest rows: `None`
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
| 1 | 91,226 | 91,226 | 49,096 | `complete_horizons` |
| 2 | 91,226 | 67,559 | 49,096 | `complete_horizons` |
| 3 | 91,226 | 49,096 | 49,096 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | `all` | 441,864 | 0.1304 | 0.1817 | 0.2823 | 0.0744 | 0.9197 |
| `validation` | 1 | `irc1` | 49,096 | 0.1323 | 0.1486 | 0.1101 | 0.0903 | 0.8761 |
| `validation` | 2 | `all` | 441,864 | 0.1386 | 0.1815 | 0.2367 | 0.0852 | 0.9345 |
| `validation` | 2 | `irc1` | 49,096 | 0.1506 | 0.1850 | 0.1859 | 0.1120 | 0.9050 |
| `validation` | 3 | `all` | 441,864 | 0.1463 | 0.1901 | 0.2302 | 0.0945 | 0.9449 |
| `validation` | 3 | `irc1` | 49,096 | 0.1584 | 0.2065 | 0.2327 | 0.1236 | 0.9323 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `validation` | 1 | 29,925 | 0.1488 | 0.1179 | 0.6177 | 0.0921 | 0.5052 | 0.7483 |
| `bloom_h` | `validation` | 2 | 29,905 | 0.1638 | 0.0694 | 0.5713 | 0.1093 | 0.2969 | 0.6701 |
| `bloom_h` | `validation` | 3 | 29,364 | 0.1660 | 0.0509 | 0.5309 | 0.1169 | 0.2088 | 0.6184 |
| `irc_alert` | `validation` | 1 | 49,096 | 0.3556 | 0.3096 | 0.8344 | 0.1196 | 0.7124 | 0.8214 |
| `irc_alert` | `validation` | 2 | 49,096 | 0.3755 | 0.3141 | 0.7912 | 0.1461 | 0.6422 | 0.7706 |
| `irc_alert` | `validation` | 3 | 49,096 | 0.3504 | 0.3009 | 0.7368 | 0.1573 | 0.6047 | 0.7410 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; it is not an operational deployment artifact.
- Recursive behavior can differ from one-step behavior because each forecast state becomes the next origin state.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_rows_validation.parquet`
- State metrics: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_metrics_validation.csv`
- Alert metrics: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_alert_metrics_validation.csv`
- Diagnostic examples: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_examples_validation.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_manifest_validation.json`
