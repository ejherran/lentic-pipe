# PIPE/GRU-D Rollout Backtest Report v0

Generated at UTC: `2026-06-12T22:26:48.127124+00:00`
Started at UTC: `2026-06-12T22:26:44.434637+00:00`

## Scope

This report evaluates recursive PIPE/GRU-D rollouts against observed future fuzzy states.
Unlike the operational rollout artifact, this is a historical backtest and can be used to judge predictive behavior.

## Configuration

- Split filter: `validation`
- Selected origins: `512`
- Evaluated rollout rows: `1,536`
- Max origins cap: `512`
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
| 1 | 7,079 | 7,079 | 512 | `complete_horizons` |
| 2 | 7,079 | 6,038 | 512 | `complete_horizons` |
| 3 | 7,079 | 5,069 | 512 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | `all` | 4,608 | 0.2258 | 0.2469 | 0.0852 | 0.1715 | 0.8694 |
| `validation` | 1 | `irc1` | 512 | 0.2139 | 0.2370 | 0.0973 | 0.1760 | 0.8516 |
| `validation` | 2 | `all` | 4,608 | 0.2628 | 0.2526 | -0.0403 | 0.2153 | 0.8678 |
| `validation` | 2 | `irc1` | 512 | 0.2475 | 0.2815 | 0.1208 | 0.2098 | 0.8594 |
| `validation` | 3 | `all` | 4,608 | 0.2951 | 0.2731 | -0.0808 | 0.2440 | 0.8689 |
| `validation` | 3 | `irc1` | 512 | 0.2654 | 0.3193 | 0.1689 | 0.2269 | 0.8438 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc_alert` | `validation` | 1 | 512 | 0.4707 | 0.4512 | 0.7650 | 0.1868 | 0.7054 | 0.7406 |
| `irc_alert` | `validation` | 2 | 512 | 0.4688 | 0.3691 | 0.6963 | 0.2159 | 0.5375 | 0.6570 |
| `irc_alert` | `validation` | 3 | 512 | 0.4707 | 0.2422 | 0.6133 | 0.2388 | 0.3527 | 0.5849 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.
- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_rows_validation_stochastic_smoke.parquet`
- State metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_metrics_validation_stochastic_smoke.csv`
- Alert metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_alert_metrics_validation_stochastic_smoke.csv`
- Diagnostic examples: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_examples_validation_stochastic_smoke.csv`
- Manifest: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_manifest_validation_stochastic_smoke.json`
