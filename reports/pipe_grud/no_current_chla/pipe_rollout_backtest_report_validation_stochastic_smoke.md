# PIPE/GRU-D Rollout Backtest Report v0

Generated at UTC: `2026-06-12T18:54:10.500203+00:00`
Started at UTC: `2026-06-12T18:54:05.174879+00:00`

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
| 1 | 22,087 | 22,087 | 512 | `complete_horizons` |
| 2 | 22,087 | 19,058 | 512 | `complete_horizons` |
| 3 | 22,087 | 16,260 | 512 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | `all` | 4,608 | 0.2128 | 0.2440 | 0.1277 | 0.1555 | 0.9184 |
| `validation` | 1 | `irc1` | 512 | 0.2479 | 0.2724 | 0.0899 | 0.2222 | 0.8574 |
| `validation` | 2 | `all` | 4,608 | 0.2534 | 0.2477 | -0.0229 | 0.1988 | 0.9280 |
| `validation` | 2 | `irc1` | 512 | 0.2555 | 0.2910 | 0.1220 | 0.2235 | 0.8750 |
| `validation` | 3 | `all` | 4,608 | 0.2885 | 0.2508 | -0.1502 | 0.2365 | 0.9297 |
| `validation` | 3 | `irc1` | 512 | 0.2616 | 0.3041 | 0.1397 | 0.2243 | 0.8809 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc_alert` | `validation` | 1 | 512 | 0.3594 | 0.1367 | 0.5465 | 0.2135 | 0.2663 | 0.5916 |
| `irc_alert` | `validation` | 2 | 512 | 0.3496 | 0.1035 | 0.5313 | 0.2098 | 0.1955 | 0.5486 |
| `irc_alert` | `validation` | 3 | 512 | 0.3516 | 0.0410 | 0.4707 | 0.2237 | 0.0778 | 0.4645 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.
- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_validation_stochastic_smoke.parquet`
- State metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_metrics_validation_stochastic_smoke.csv`
- Alert metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_alert_metrics_validation_stochastic_smoke.csv`
- Diagnostic examples: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_examples_validation_stochastic_smoke.csv`
- Manifest: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_manifest_validation_stochastic_smoke.json`
