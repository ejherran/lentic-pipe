# PIPE/GRU-D Rollout Backtest Report v0

Generated at UTC: `2026-06-12T22:48:16.588729+00:00`
Started at UTC: `2026-06-12T22:48:10.513163+00:00`

## Scope

This report evaluates recursive PIPE/GRU-D rollouts against observed future fuzzy states.
Unlike the operational rollout artifact, this is a historical backtest and can be used to judge predictive behavior.

## Configuration

- Split filter: `validation`
- Selected origins: `5,069`
- Evaluated rollout rows: `15,207`
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
| 1 | 7,079 | 7,079 | 5,069 | `complete_horizons` |
| 2 | 7,079 | 6,038 | 5,069 | `complete_horizons` |
| 3 | 7,079 | 5,069 | 5,069 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | `all` | 45,621 | 0.1788 | 0.2426 | 0.2632 | 0.1182 | 0.7723 |
| `validation` | 1 | `irc1` | 5,069 | 0.1956 | 0.2381 | 0.1787 | 0.1658 | 0.7889 |
| `validation` | 2 | `all` | 45,621 | 0.2050 | 0.2531 | 0.1900 | 0.1385 | 0.7712 |
| `validation` | 2 | `irc1` | 5,069 | 0.2192 | 0.2774 | 0.2099 | 0.1860 | 0.8027 |
| `validation` | 3 | `all` | 45,621 | 0.2199 | 0.2664 | 0.1746 | 0.1518 | 0.7548 |
| `validation` | 3 | `irc1` | 5,069 | 0.2343 | 0.3120 | 0.2490 | 0.1975 | 0.7990 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc_alert` | `validation` | 1 | 5,069 | 0.4904 | 0.5508 | 0.8003 | 0.1669 | 0.8117 | 0.7546 |
| `irc_alert` | `validation` | 2 | 5,069 | 0.4910 | 0.4606 | 0.7585 | 0.1908 | 0.6657 | 0.7014 |
| `irc_alert` | `validation` | 3 | 5,069 | 0.4892 | 0.3916 | 0.7272 | 0.2057 | 0.5637 | 0.6660 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.
- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_rows_validation.parquet`
- State metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_metrics_validation.csv`
- Alert metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_alert_metrics_validation.csv`
- Diagnostic examples: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_examples_validation.csv`
- Manifest: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_manifest_validation.json`
