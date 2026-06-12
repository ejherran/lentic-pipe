# PIPE/GRU-D Rollout Backtest Report v0

Generated at UTC: `2026-06-12T22:25:11.880460+00:00`
Started at UTC: `2026-06-12T22:25:08.402547+00:00`

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
- Samples per origin: `1`
- Deterministic mode: `True`
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
| `test` | 1 | `all` | 4,608 | 0.2211 | 0.2521 | 0.1230 | 0.1393 | 0.0849 |
| `test` | 1 | `irc1` | 512 | 0.2449 | 0.2681 | 0.0868 | 0.2048 | 0.0000 |
| `test` | 2 | `all` | 4,608 | 0.2195 | 0.2573 | 0.1469 | 0.1415 | 0.0703 |
| `test` | 2 | `irc1` | 512 | 0.2686 | 0.3044 | 0.1176 | 0.2204 | 0.0000 |
| `test` | 3 | `all` | 4,608 | 0.2215 | 0.2685 | 0.1751 | 0.1417 | 0.0688 |
| `test` | 3 | `irc1` | 512 | 0.2867 | 0.3300 | 0.1314 | 0.2304 | 0.0000 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc_alert` | `test` | 1 | 512 | 0.4316 | 0.4863 | 0.5655 | 0.3125 | 0.7014 | 0.6854 |
| `irc_alert` | `test` | 2 | 512 | 0.4395 | 0.4102 | 0.5468 | 0.3379 | 0.5822 | 0.6543 |
| `irc_alert` | `test` | 3 | 512 | 0.4492 | 0.2969 | 0.5218 | 0.3750 | 0.4130 | 0.5992 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.
- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_rows_test_smoke.parquet`
- State metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_metrics_test_smoke.csv`
- Alert metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_alert_metrics_test_smoke.csv`
- Diagnostic examples: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_examples_test_smoke.csv`
- Manifest: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_manifest_test_smoke.json`
