# PIPE Neural ODE Continuous-Time Direct Backtest Report v2

Generated at UTC: `2026-06-27T15:25:24.861444+00:00`
Started at UTC: `2026-06-27T15:25:13.910783+00:00`

## Scope

This report evaluates direct multi-gap PIPE Neural ODE v2 forecasts against observed future fuzzy states.
Each h1/h2/h3 prediction starts from the same observed origin history instead of recursively feeding predictions.

## Configuration

- Split filter: `validation`
- Selected origins: `5,069`
- Evaluated direct rows: `15,207`
- Max origins cap: `None`
- Model version: `pipe_neural_ode_continuous_v2`
- History length: `12`
- Direct horizon: `3` month(s)
- Observed state source: `target`
- Reference backtest rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_validation.parquet`
- Samples per origin: `128`
- Deterministic mode: `False`
- Horizon policy: `complete`

## Future Availability

| horizon | eligible origins | observed future | direct sequence future | direct observed future | selected origins | policy |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 5,069 | 5,069 | 5,069 | 5,069 | 5,069 | `complete_direct_horizons` |
| 2 | 5,069 | 5,069 | 5,069 | 5,069 | 5,069 | `complete_direct_horizons` |
| 3 | 5,069 | 5,069 | 5,069 | 5,069 | 5,069 | `complete_direct_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | `all` | 45,621 | 0.1234 | 0.1726 | 0.2853 | 0.0715 | 0.9109 |
| `validation` | 1 | `irc1` | 5,069 | 0.1149 | 0.1391 | 0.1738 | 0.0816 | 0.9083 |
| `validation` | 2 | `all` | 45,621 | 0.1296 | 0.1761 | 0.2644 | 0.0767 | 0.8932 |
| `validation` | 2 | `irc1` | 5,069 | 0.1250 | 0.1757 | 0.2885 | 0.0924 | 0.8826 |
| `validation` | 3 | `all` | 45,621 | 0.1321 | 0.1842 | 0.2830 | 0.0798 | 0.8915 |
| `validation` | 3 | `irc1` | 5,069 | 0.1305 | 0.2011 | 0.3513 | 0.0983 | 0.8818 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc_alert` | `validation` | 1 | 5,069 | 0.4403 | 0.4506 | 0.9084 | 0.1038 | 0.8513 | 0.8570 |
| `irc_alert` | `validation` | 2 | 5,069 | 0.4472 | 0.4535 | 0.8926 | 0.1133 | 0.8324 | 0.8422 |
| `irc_alert` | `validation` | 3 | 5,069 | 0.4478 | 0.4545 | 0.8785 | 0.1199 | 0.8194 | 0.8299 |

## Interpretation Guardrails

- This is a direct multi-gap backtest, not a recursive rollout.
- Compare it with recursive v1/v0 evidence only after matching origins and keeping the direct/recursive distinction explicit.
- Calibration and 2B policy comparison require a later row-level calibration gate.

## Outputs

- Backtest rows: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_backtest_rows_matched_grud_validation.parquet`
- State metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_backtest_metrics_matched_grud_validation.csv`
- Alert metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_backtest_alert_metrics_matched_grud_validation.csv`
- Diagnostic examples: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_backtest_examples_matched_grud_validation.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_backtest_manifest_matched_grud_validation.json`
