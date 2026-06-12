# PIPE/GRU-D Rollout Backtest Report v0

Generated at UTC: `2026-06-12T22:32:18.475819+00:00`
Started at UTC: `2026-06-12T22:32:14.670408+00:00`

## Scope

This report evaluates recursive PIPE/GRU-D rollouts against observed future fuzzy states.
Unlike the operational rollout artifact, this is a historical backtest and can be used to judge predictive behavior.

## Configuration

- Split filter: `test`
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
| 1 | 7,582 | 7,582 | 512 | `complete_horizons` |
| 2 | 7,582 | 6,826 | 512 | `complete_horizons` |
| 3 | 7,582 | 6,145 | 512 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `test` | 1 | `all` | 4,608 | 0.2286 | 0.2521 | 0.0932 | 0.1747 | 0.8490 |
| `test` | 1 | `irc1` | 512 | 0.2417 | 0.2681 | 0.0987 | 0.2069 | 0.8066 |
| `test` | 2 | `all` | 4,608 | 0.2571 | 0.2573 | 0.0007 | 0.2137 | 0.8644 |
| `test` | 2 | `irc1` | 512 | 0.2610 | 0.3044 | 0.1425 | 0.2254 | 0.8398 |
| `test` | 3 | `all` | 4,608 | 0.2881 | 0.2685 | -0.0727 | 0.2430 | 0.8689 |
| `test` | 3 | `irc1` | 512 | 0.2731 | 0.3300 | 0.1725 | 0.2344 | 0.8242 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc_alert` | `test` | 1 | 512 | 0.4316 | 0.4805 | 0.7281 | 0.2071 | 0.6923 | 0.6831 |
| `irc_alert` | `test` | 2 | 512 | 0.4395 | 0.3809 | 0.6596 | 0.2207 | 0.5200 | 0.6246 |
| `irc_alert` | `test` | 3 | 512 | 0.4492 | 0.2383 | 0.5967 | 0.2412 | 0.3391 | 0.5758 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.
- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_rows_test_stochastic_smoke.parquet`
- State metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_metrics_test_stochastic_smoke.csv`
- Alert metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_alert_metrics_test_stochastic_smoke.csv`
- Diagnostic examples: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_examples_test_stochastic_smoke.csv`
- Manifest: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_manifest_test_stochastic_smoke.json`
