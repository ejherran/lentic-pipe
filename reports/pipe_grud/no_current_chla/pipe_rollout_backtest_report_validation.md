# PIPE/GRU-D Rollout Backtest Report v0

Generated at UTC: `2026-06-12T19:08:13.906558+00:00`
Started at UTC: `2026-06-12T19:08:00.376809+00:00`

## Scope

This report evaluates recursive PIPE/GRU-D rollouts against observed future fuzzy states.
Unlike the operational rollout artifact, this is a historical backtest and can be used to judge predictive behavior.

## Configuration

- Split filter: `validation`
- Selected origins: `16,260`
- Evaluated rollout rows: `48,780`
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
| 1 | 22,087 | 22,087 | 16,260 | `complete_horizons` |
| 2 | 22,087 | 19,058 | 16,260 | `complete_horizons` |
| 3 | 22,087 | 16,260 | 16,260 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | `all` | 146,340 | 0.1767 | 0.2387 | 0.2599 | 0.0914 | 0.8907 |
| `validation` | 1 | `irc1` | 16,260 | 0.2388 | 0.2688 | 0.1114 | 0.2099 | 0.8409 |
| `validation` | 2 | `all` | 146,340 | 0.2005 | 0.2424 | 0.1731 | 0.1129 | 0.8293 |
| `validation` | 2 | `irc1` | 16,260 | 0.2457 | 0.2810 | 0.1256 | 0.2088 | 0.8534 |
| `validation` | 3 | `all` | 146,340 | 0.2058 | 0.2470 | 0.1669 | 0.1167 | 0.8018 |
| `validation` | 3 | `irc1` | 16,260 | 0.2536 | 0.2931 | 0.1346 | 0.2087 | 0.8396 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc_alert` | `validation` | 1 | 16,260 | 0.3604 | 0.1737 | 0.6027 | 0.1981 | 0.3406 | 0.6314 |
| `irc_alert` | `validation` | 2 | 16,260 | 0.3612 | 0.1177 | 0.5790 | 0.2085 | 0.2408 | 0.5813 |
| `irc_alert` | `validation` | 3 | 16,260 | 0.3577 | 0.0752 | 0.5642 | 0.2179 | 0.1638 | 0.5347 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.
- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_validation.parquet`
- State metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_metrics_validation.csv`
- Alert metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_alert_metrics_validation.csv`
- Diagnostic examples: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_examples_validation.csv`
- Manifest: `reports/pipe_grud/no_current_chla/pipe_rollout_backtest_manifest_validation.json`
