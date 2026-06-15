# PIPE Neural ODE Rollout Backtest Report v1

Generated at UTC: `2026-06-15T20:55:38.713101+00:00`
Started at UTC: `2026-06-15T20:55:30.020841+00:00`

## Scope

This report evaluates recursive PIPE Neural ODE rollouts against observed future fuzzy states.
It is a historical backtest and should be compared with PIPE/GRU-D rollout backtests on the same sequence surface.

## Configuration

- Split filter: `validation`
- Selected origins: `5,069`
- Evaluated rollout rows: `15,207`
- Max origins cap: `None`
- Model version: `pipe_neural_ode_history_v1`
- History length: `12`
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
| `validation` | 1 | `all` | 45,621 | 0.1182 | 0.1726 | 0.3153 | 0.0687 | 0.9023 |
| `validation` | 1 | `irc1` | 5,069 | 0.1130 | 0.1391 | 0.1879 | 0.0798 | 0.9069 |
| `validation` | 2 | `all` | 45,621 | 0.1298 | 0.1761 | 0.2629 | 0.0779 | 0.9164 |
| `validation` | 2 | `irc1` | 5,069 | 0.1269 | 0.1757 | 0.2777 | 0.0968 | 0.9323 |
| `validation` | 3 | `all` | 45,621 | 0.1330 | 0.1842 | 0.2777 | 0.0820 | 0.9300 |
| `validation` | 3 | `irc1` | 5,069 | 0.1331 | 0.2011 | 0.3382 | 0.1054 | 0.9529 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `validation` | 1 | 3,049 | 0.1345 | 0.0846 | 0.6134 | 0.0864 | 0.4415 | 0.7428 |
| `bloom_h` | `validation` | 2 | 3,158 | 0.1396 | 0.0567 | 0.5886 | 0.0941 | 0.2971 | 0.6799 |
| `bloom_h` | `validation` | 3 | 3,184 | 0.1435 | 0.0496 | 0.5689 | 0.0997 | 0.2429 | 0.6463 |
| `irc_alert` | `validation` | 1 | 5,069 | 0.4403 | 0.4401 | 0.9094 | 0.1017 | 0.8414 | 0.8585 |
| `irc_alert` | `validation` | 2 | 5,069 | 0.4472 | 0.4427 | 0.8911 | 0.1176 | 0.8231 | 0.8444 |
| `irc_alert` | `validation` | 3 | 5,069 | 0.4478 | 0.4453 | 0.8789 | 0.1265 | 0.8176 | 0.8374 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; it is not an operational deployment artifact.
- Recursive behavior can differ from one-step behavior because each forecast state becomes the next origin state.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_rows_matched_grud_validation.parquet`
- State metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_metrics_matched_grud_validation.csv`
- Alert metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_alert_metrics_matched_grud_validation.csv`
- Diagnostic examples: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_examples_matched_grud_validation.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_manifest_matched_grud_validation.json`
