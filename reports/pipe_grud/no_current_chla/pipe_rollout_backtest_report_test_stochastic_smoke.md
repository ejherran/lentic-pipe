# PIPE/GRU-D Rollout Backtest Report v0

Generated at UTC: `2026-06-12T18:54:26.622143+00:00`
Started at UTC: `2026-06-12T18:54:21.340812+00:00`

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
| 1 | 17,420 | 17,420 | 512 | `complete_horizons` |
| 2 | 17,420 | 15,268 | 512 | `complete_horizons` |
| 3 | 17,420 | 13,327 | 512 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `test` | 1 | `all` | 4,608 | 0.2057 | 0.2384 | 0.1374 | 0.1542 | 0.9076 |
| `test` | 1 | `irc1` | 512 | 0.2504 | 0.2770 | 0.0957 | 0.2211 | 0.8418 |
| `test` | 2 | `all` | 4,608 | 0.2474 | 0.2404 | -0.0293 | 0.1994 | 0.9175 |
| `test` | 2 | `irc1` | 512 | 0.2539 | 0.2891 | 0.1217 | 0.2196 | 0.8770 |
| `test` | 3 | `all` | 4,608 | 0.2871 | 0.2475 | -0.1598 | 0.2384 | 0.9191 |
| `test` | 3 | `irc1` | 512 | 0.2624 | 0.3003 | 0.1262 | 0.2231 | 0.8730 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc_alert` | `test` | 1 | 512 | 0.3379 | 0.1699 | 0.5311 | 0.2169 | 0.3006 | 0.5979 |
| `irc_alert` | `test` | 2 | 512 | 0.3477 | 0.1230 | 0.5374 | 0.2128 | 0.2303 | 0.5686 |
| `irc_alert` | `test` | 3 | 512 | 0.3535 | 0.0508 | 0.5008 | 0.2235 | 0.1160 | 0.5005 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.
- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_test_stochastic_smoke.parquet`
- State metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_metrics_test_stochastic_smoke.csv`
- Alert metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_alert_metrics_test_stochastic_smoke.csv`
- Diagnostic examples: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_examples_test_stochastic_smoke.csv`
- Manifest: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_manifest_test_stochastic_smoke.json`
