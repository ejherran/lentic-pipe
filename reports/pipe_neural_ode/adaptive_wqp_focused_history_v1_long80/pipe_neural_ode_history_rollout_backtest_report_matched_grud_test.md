# PIPE Neural ODE Rollout Backtest Report v1

Generated at UTC: `2026-06-15T20:58:47.313637+00:00`
Started at UTC: `2026-06-15T20:58:37.694103+00:00`

## Scope

This report evaluates recursive PIPE Neural ODE rollouts against observed future fuzzy states.
It is a historical backtest and should be compared with PIPE/GRU-D rollout backtests on the same sequence surface.

## Configuration

- Split filter: `test`
- Selected origins: `6,145`
- Evaluated rollout rows: `18,435`
- Max origins cap: `None`
- Model version: `pipe_neural_ode_history_v1`
- History length: `12`
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
| `test` | 1 | `all` | 55,305 | 0.1125 | 0.1645 | 0.3164 | 0.0649 | 0.9080 |
| `test` | 1 | `irc1` | 6,145 | 0.1085 | 0.1367 | 0.2068 | 0.0755 | 0.9098 |
| `test` | 2 | `all` | 55,305 | 0.1217 | 0.1691 | 0.2807 | 0.0722 | 0.9252 |
| `test` | 2 | `irc1` | 6,145 | 0.1201 | 0.1736 | 0.3079 | 0.0885 | 0.9473 |
| `test` | 3 | `all` | 55,305 | 0.1242 | 0.1749 | 0.2902 | 0.0759 | 0.9365 |
| `test` | 3 | `irc1` | 6,145 | 0.1232 | 0.1934 | 0.3631 | 0.0942 | 0.9670 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.1108 | 0.6691 | 0.1102 | 0.4472 | 0.7400 |
| `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.0822 | 0.6426 | 0.1145 | 0.3244 | 0.6818 |
| `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.0889 | 0.6422 | 0.1185 | 0.3262 | 0.6761 |
| `irc_alert` | `test` | 1 | 6,145 | 0.4148 | 0.4286 | 0.9331 | 0.0869 | 0.8694 | 0.8747 |
| `irc_alert` | `test` | 2 | 6,145 | 0.4330 | 0.4467 | 0.9208 | 0.0999 | 0.8598 | 0.8629 |
| `irc_alert` | `test` | 3 | 6,145 | 0.4448 | 0.4679 | 0.9238 | 0.1048 | 0.8745 | 0.8642 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; it is not an operational deployment artifact.
- Recursive behavior can differ from one-step behavior because each forecast state becomes the next origin state.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_rows_matched_grud_test.parquet`
- State metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_metrics_matched_grud_test.csv`
- Alert metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_alert_metrics_matched_grud_test.csv`
- Diagnostic examples: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_examples_matched_grud_test.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_manifest_matched_grud_test.json`
