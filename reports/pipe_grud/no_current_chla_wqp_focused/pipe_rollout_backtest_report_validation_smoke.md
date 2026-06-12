# PIPE/GRU-D Rollout Backtest Report v0

Generated at UTC: `2026-06-12T22:22:43.924578+00:00`
Started at UTC: `2026-06-12T22:22:40.465332+00:00`

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
| 1 | 7,079 | 7,079 | 512 | `complete_horizons` |
| 2 | 7,079 | 6,038 | 512 | `complete_horizons` |
| 3 | 7,079 | 5,069 | 512 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | `all` | 4,608 | 0.2197 | 0.2469 | 0.1102 | 0.1373 | 0.1111 |
| `validation` | 1 | `irc1` | 512 | 0.2158 | 0.2370 | 0.0893 | 0.1706 | 0.0000 |
| `validation` | 2 | `all` | 4,608 | 0.2235 | 0.2526 | 0.1153 | 0.1447 | 0.0924 |
| `validation` | 2 | `irc1` | 512 | 0.2515 | 0.2815 | 0.1065 | 0.2031 | 0.0000 |
| `validation` | 3 | `all` | 4,608 | 0.2334 | 0.2731 | 0.1452 | 0.1505 | 0.0924 |
| `validation` | 3 | `irc1` | 512 | 0.2804 | 0.3193 | 0.1217 | 0.2278 | 0.0000 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc_alert` | `validation` | 1 | 512 | 0.4707 | 0.4785 | 0.6847 | 0.2305 | 0.7635 | 0.7689 |
| `irc_alert` | `validation` | 2 | 512 | 0.4688 | 0.4023 | 0.6069 | 0.3086 | 0.6000 | 0.6862 |
| `irc_alert` | `validation` | 3 | 512 | 0.4707 | 0.3105 | 0.5716 | 0.3516 | 0.4564 | 0.6308 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.
- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_rows_validation_smoke.parquet`
- State metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_metrics_validation_smoke.csv`
- Alert metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_alert_metrics_validation_smoke.csv`
- Diagnostic examples: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_examples_validation_smoke.csv`
- Manifest: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_manifest_validation_smoke.json`
