# PIPE Neural ODE Rollout Backtest Report v1

Generated at UTC: `2026-06-15T20:52:38.531026+00:00`
Started at UTC: `2026-06-15T20:52:34.805261+00:00`

## Scope

This report evaluates recursive PIPE Neural ODE rollouts against observed future fuzzy states.
It is a historical backtest and should be compared with PIPE/GRU-D rollout backtests on the same sequence surface.

## Configuration

- Split filter: `validation`
- Selected origins: `512`
- Evaluated rollout rows: `1,536`
- Max origins cap: `512`
- Model version: `pipe_neural_ode_history_v1`
- History length: `12`
- Rollout horizon: `3` month(s)
- Observed state source: `target`
- Reference backtest rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_validation.parquet`
- Samples per origin: `32`
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
| 1 | 5,069 | 5,069 | 512 | `complete_horizons` |
| 2 | 5,069 | 5,069 | 512 | `complete_horizons` |
| 3 | 5,069 | 5,069 | 512 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | `all` | 4,608 | 0.1229 | 0.1785 | 0.3117 | 0.0710 | 0.8874 |
| `validation` | 1 | `irc1` | 512 | 0.1140 | 0.1454 | 0.2159 | 0.0789 | 0.8984 |
| `validation` | 2 | `all` | 4,608 | 0.1346 | 0.1735 | 0.2244 | 0.0811 | 0.8928 |
| `validation` | 2 | `irc1` | 512 | 0.1337 | 0.1751 | 0.2363 | 0.1046 | 0.9258 |
| `validation` | 3 | `all` | 4,608 | 0.1359 | 0.1860 | 0.2693 | 0.0840 | 0.9160 |
| `validation` | 3 | `irc1` | 512 | 0.1358 | 0.2038 | 0.3338 | 0.1099 | 0.9473 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc_alert` | `validation` | 1 | 512 | 0.4238 | 0.3926 | 0.8806 | 0.1093 | 0.7788 | 0.8383 |
| `irc_alert` | `validation` | 2 | 512 | 0.4375 | 0.4160 | 0.8781 | 0.1255 | 0.7812 | 0.8264 |
| `irc_alert` | `validation` | 3 | 512 | 0.4258 | 0.4531 | 0.8333 | 0.1357 | 0.8028 | 0.8018 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; it is not an operational deployment artifact.
- Recursive behavior can differ from one-step behavior because each forecast state becomes the next origin state.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_rows_matched_grud_validation_smoke.parquet`
- State metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_metrics_matched_grud_validation_smoke.csv`
- Alert metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_alert_metrics_matched_grud_validation_smoke.csv`
- Diagnostic examples: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_examples_matched_grud_validation_smoke.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_manifest_matched_grud_validation_smoke.json`
