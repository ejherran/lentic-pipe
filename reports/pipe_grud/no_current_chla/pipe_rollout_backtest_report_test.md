# PIPE/GRU-D Rollout Backtest Report v0

Generated at UTC: `2026-06-12T19:08:42.233783+00:00`
Started at UTC: `2026-06-12T19:08:30.029052+00:00`

## Scope

This report evaluates recursive PIPE/GRU-D rollouts against observed future fuzzy states.
Unlike the operational rollout artifact, this is a historical backtest and can be used to judge predictive behavior.

## Configuration

- Split filter: `test`
- Selected origins: `13,327`
- Evaluated rollout rows: `39,981`
- Max origins cap: `None`
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
| 1 | 17,420 | 17,420 | 13,327 | `complete_horizons` |
| 2 | 17,420 | 15,268 | 13,327 | `complete_horizons` |
| 3 | 17,420 | 13,327 | 13,327 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `test` | 1 | `all` | 119,943 | 0.1683 | 0.2367 | 0.2891 | 0.0948 | 0.8742 |
| `test` | 1 | `irc1` | 13,327 | 0.2288 | 0.2752 | 0.1685 | 0.2027 | 0.8479 |
| `test` | 2 | `all` | 119,943 | 0.1861 | 0.2404 | 0.2261 | 0.1119 | 0.8333 |
| `test` | 2 | `irc1` | 13,327 | 0.2319 | 0.2880 | 0.1950 | 0.1981 | 0.8642 |
| `test` | 3 | `all` | 119,943 | 0.1932 | 0.2448 | 0.2110 | 0.1176 | 0.8132 |
| `test` | 3 | `irc1` | 13,327 | 0.2390 | 0.2983 | 0.1987 | 0.1989 | 0.8617 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc_alert` | `test` | 1 | 13,327 | 0.3335 | 0.2354 | 0.6532 | 0.1805 | 0.4777 | 0.6926 |
| `irc_alert` | `test` | 2 | 13,327 | 0.3464 | 0.1768 | 0.6346 | 0.1852 | 0.3724 | 0.6568 |
| `irc_alert` | `test` | 3 | 13,327 | 0.3564 | 0.1379 | 0.6147 | 0.1967 | 0.2931 | 0.6165 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.
- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_test.parquet`
- State metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_metrics_test.csv`
- Alert metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_alert_metrics_test.csv`
- Diagnostic examples: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_examples_test.csv`
- Manifest: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_manifest_test.json`
