# PIPE/GRU-D Rollout Backtest Report v0

Generated at UTC: `2026-06-12T18:46:34.699939+00:00`
Started at UTC: `2026-06-12T18:46:29.531978+00:00`

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
| 1 | 22,087 | 22,087 | 512 | `complete_horizons` |
| 2 | 22,087 | 19,058 | 512 | `complete_horizons` |
| 3 | 22,087 | 16,260 | 512 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | `all` | 4,608 | 0.1895 | 0.2440 | 0.2235 | 0.0924 | 0.3828 |
| `validation` | 1 | `irc1` | 512 | 0.2451 | 0.2724 | 0.1002 | 0.2170 | 0.0000 |
| `validation` | 2 | `all` | 4,608 | 0.2103 | 0.2477 | 0.1508 | 0.1081 | 0.3815 |
| `validation` | 2 | `irc1` | 512 | 0.2595 | 0.2910 | 0.1083 | 0.2139 | 0.0000 |
| `validation` | 3 | `all` | 4,608 | 0.2194 | 0.2508 | 0.1254 | 0.1083 | 0.3863 |
| `validation` | 3 | `irc1` | 512 | 0.2876 | 0.3041 | 0.0540 | 0.2160 | 0.0020 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc_alert` | `validation` | 1 | 512 | 0.3594 | 0.1348 | 0.4708 | 0.2910 | 0.2826 | 0.6089 |
| `irc_alert` | `validation` | 2 | 512 | 0.3496 | 0.1074 | 0.4109 | 0.3164 | 0.2011 | 0.5513 |
| `irc_alert` | `validation` | 3 | 512 | 0.3516 | 0.0723 | 0.3813 | 0.3379 | 0.1222 | 0.4942 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.
- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_validation_smoke.parquet`
- State metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_metrics_validation_smoke.csv`
- Alert metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_alert_metrics_validation_smoke.csv`
- Diagnostic examples: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_examples_validation_smoke.csv`
- Manifest: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_manifest_validation_smoke.json`
