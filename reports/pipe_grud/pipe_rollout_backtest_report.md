# PIPE/GRU-D Rollout Backtest Report v0

Generated at UTC: `2026-05-18T18:27:53.560392+00:00`
Started at UTC: `2026-05-18T18:27:40.395825+00:00`

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
- Samples per origin: `128`
- Deterministic mode: `False`
- Horizon policy: `complete`
- IRC weights: alpha=`0.5`, beta=`0.5`, gamma=`2.0`
- IRC alert threshold: `0.5`
- Alert probability threshold: `0.5`
- Random seed: `1729`
- Calibrated bloom horizons available: `[1, 2, 3]`

## Future Availability

| horizon | eligible origins | origins with observed future | selected origins | policy |
|---:|---:|---:|---:|---|
| 1 | 17,420 | 17,420 | 13,327 | `complete_horizons` |
| 2 | 17,420 | 15,268 | 13,327 | `complete_horizons` |
| 3 | 17,420 | 13,685 | 13,327 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `test` | 1 | `all` | 119,943 | 0.1341 | 0.1792 | 0.2518 | 0.0730 | 0.8815 |
| `test` | 1 | `irc1` | 13,327 | 0.1415 | 0.1627 | 0.1304 | 0.1084 | 0.8717 |
| `test` | 2 | `all` | 119,943 | 0.1475 | 0.1796 | 0.1788 | 0.0825 | 0.8893 |
| `test` | 2 | `irc1` | 13,327 | 0.1624 | 0.1992 | 0.1849 | 0.1316 | 0.8784 |
| `test` | 3 | `all` | 119,943 | 0.1543 | 0.1886 | 0.1821 | 0.0881 | 0.8935 |
| `test` | 3 | `irc1` | 13,327 | 0.1717 | 0.2237 | 0.2326 | 0.1412 | 0.8822 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `test` | 1 | 11,852 | 0.1243 | 0.1120 | 0.6737 | 0.0711 | 0.6083 | 0.7959 |
| `bloom_h` | `test` | 2 | 11,891 | 0.1298 | 0.0613 | 0.6366 | 0.0830 | 0.3543 | 0.7132 |
| `bloom_h` | `test` | 3 | 11,939 | 0.1335 | 0.0519 | 0.6106 | 0.0899 | 0.2880 | 0.6774 |
| `irc_alert` | `test` | 1 | 13,327 | 0.3335 | 0.3130 | 0.8894 | 0.0913 | 0.7826 | 0.8577 |
| `irc_alert` | `test` | 2 | 13,327 | 0.3464 | 0.2995 | 0.8769 | 0.1038 | 0.7244 | 0.8354 |
| `irc_alert` | `test` | 3 | 13,327 | 0.3564 | 0.2884 | 0.8702 | 0.1123 | 0.6853 | 0.8211 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.
- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- State metrics: `reports/pipe_grud/pipe_rollout_backtest_metrics.csv`
- Alert metrics: `reports/pipe_grud/pipe_rollout_backtest_alert_metrics.csv`
- Diagnostic examples: `reports/pipe_grud/pipe_rollout_backtest_examples.csv`
- Manifest: `reports/pipe_grud/pipe_rollout_backtest_manifest.json`
