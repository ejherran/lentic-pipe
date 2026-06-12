# PIPE/GRU-D Rollout Backtest Report v0

Generated at UTC: `2026-06-12T18:46:58.824292+00:00`
Started at UTC: `2026-06-12T18:46:53.739516+00:00`

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
| 1 | 17,420 | 17,420 | 512 | `complete_horizons` |
| 2 | 17,420 | 15,268 | 512 | `complete_horizons` |
| 3 | 17,420 | 13,327 | 512 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `test` | 1 | `all` | 4,608 | 0.1822 | 0.2384 | 0.2360 | 0.0936 | 0.3292 |
| `test` | 1 | `irc1` | 512 | 0.2481 | 0.2770 | 0.1044 | 0.2160 | 0.0000 |
| `test` | 2 | `all` | 4,608 | 0.2017 | 0.2404 | 0.1611 | 0.1101 | 0.3270 |
| `test` | 2 | `irc1` | 512 | 0.2570 | 0.2891 | 0.1112 | 0.2082 | 0.0000 |
| `test` | 3 | `all` | 4,608 | 0.2157 | 0.2475 | 0.1285 | 0.1150 | 0.3216 |
| `test` | 3 | `irc1` | 512 | 0.2876 | 0.3003 | 0.0423 | 0.2116 | 0.0000 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc_alert` | `test` | 1 | 512 | 0.3379 | 0.1777 | 0.4329 | 0.2930 | 0.3295 | 0.6172 |
| `irc_alert` | `test` | 2 | 512 | 0.3477 | 0.1211 | 0.4199 | 0.3086 | 0.2303 | 0.5701 |
| `irc_alert` | `test` | 3 | 512 | 0.3535 | 0.0645 | 0.4228 | 0.3125 | 0.1492 | 0.5274 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.
- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_test_smoke.parquet`
- State metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_metrics_test_smoke.csv`
- Alert metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_alert_metrics_test_smoke.csv`
- Diagnostic examples: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_examples_test_smoke.csv`
- Manifest: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_manifest_test_smoke.json`
