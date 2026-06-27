# PIPE Neural ODE Continuous-Time Direct Backtest Report v2

Generated at UTC: `2026-06-27T15:28:52.725695+00:00`
Started at UTC: `2026-06-27T15:28:41.808664+00:00`

## Scope

This report evaluates direct multi-gap PIPE Neural ODE v2 forecasts against observed future fuzzy states.
Each h1/h2/h3 prediction starts from the same observed origin history instead of recursively feeding predictions.

## Configuration

- Split filter: `test`
- Selected origins: `6,145`
- Evaluated direct rows: `18,435`
- Max origins cap: `None`
- Model version: `pipe_neural_ode_continuous_v2`
- History length: `12`
- Direct horizon: `3` month(s)
- Observed state source: `target`
- Reference backtest rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_test.parquet`
- Samples per origin: `128`
- Deterministic mode: `False`
- Horizon policy: `complete`

## Future Availability

| horizon | eligible origins | observed future | direct sequence future | direct observed future | selected origins | policy |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 6,145 | 6,145 | 6,145 | 6,145 | 6,145 | `complete_direct_horizons` |
| 2 | 6,145 | 6,145 | 6,145 | 6,145 | 6,145 | `complete_direct_horizons` |
| 3 | 6,145 | 6,145 | 6,145 | 6,145 | 6,145 | `complete_direct_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `test` | 1 | `all` | 55,305 | 0.1176 | 0.1645 | 0.2850 | 0.0675 | 0.9172 |
| `test` | 1 | `irc1` | 6,145 | 0.1100 | 0.1367 | 0.1954 | 0.0768 | 0.9095 |
| `test` | 2 | `all` | 55,305 | 0.1222 | 0.1691 | 0.2778 | 0.0713 | 0.9018 |
| `test` | 2 | `irc1` | 6,145 | 0.1193 | 0.1736 | 0.3127 | 0.0843 | 0.9046 |
| `test` | 3 | `all` | 55,305 | 0.1238 | 0.1749 | 0.2923 | 0.0739 | 0.8997 |
| `test` | 3 | `irc1` | 6,145 | 0.1190 | 0.1934 | 0.3846 | 0.0852 | 0.9097 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc_alert` | `test` | 1 | 6,145 | 0.4148 | 0.4316 | 0.9298 | 0.0896 | 0.8721 | 0.8742 |
| `irc_alert` | `test` | 2 | 6,145 | 0.4330 | 0.4548 | 0.9218 | 0.0978 | 0.8715 | 0.8652 |
| `irc_alert` | `test` | 3 | 6,145 | 0.4448 | 0.4716 | 0.9292 | 0.0976 | 0.8771 | 0.8628 |

## Interpretation Guardrails

- This is a direct multi-gap backtest, not a recursive rollout.
- Compare it with recursive v1/v0 evidence only after matching origins and keeping the direct/recursive distinction explicit.
- Calibration and 2B policy comparison require a later row-level calibration gate.

## Outputs

- Backtest rows: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_backtest_rows_matched_grud_test.parquet`
- State metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_backtest_metrics_matched_grud_test.csv`
- Alert metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_backtest_alert_metrics_matched_grud_test.csv`
- Diagnostic examples: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_backtest_examples_matched_grud_test.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_backtest_manifest_matched_grud_test.json`
