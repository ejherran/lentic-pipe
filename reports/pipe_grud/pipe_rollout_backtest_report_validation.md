# PIPE/GRU-D Rollout Backtest Report v0

Generated at UTC: `2026-06-12T14:33:17.329741+00:00`
Started at UTC: `2026-06-12T14:33:01.335899+00:00`

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
| 1 | 22,087 | 22,087 | 16,260 | `complete_horizons` |
| 2 | 22,087 | 19,058 | 16,260 | `complete_horizons` |
| 3 | 22,087 | 16,683 | 16,260 | `complete_horizons` |

## State Metrics

| split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE | coverage |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | `all` | 146,340 | 0.1475 | 0.2070 | 0.2876 | 0.0729 | 0.8836 |
| `validation` | 1 | `irc1` | 16,260 | 0.1668 | 0.1974 | 0.1553 | 0.1272 | 0.8185 |
| `validation` | 2 | `all` | 146,340 | 0.1603 | 0.2032 | 0.2111 | 0.0811 | 0.8922 |
| `validation` | 2 | `irc1` | 16,260 | 0.1813 | 0.2326 | 0.2209 | 0.1465 | 0.8403 |
| `validation` | 3 | `all` | 146,340 | 0.1644 | 0.2134 | 0.2294 | 0.0848 | 0.8992 |
| `validation` | 3 | `irc1` | 16,260 | 0.1891 | 0.2609 | 0.2752 | 0.1553 | 0.8451 |

## Alert Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `validation` | 1 | 14,212 | 0.1295 | 0.1127 | 0.5981 | 0.0804 | 0.5437 | 0.7619 |
| `bloom_h` | `validation` | 2 | 14,325 | 0.1321 | 0.0605 | 0.5739 | 0.0892 | 0.3356 | 0.7015 |
| `bloom_h` | `validation` | 3 | 14,352 | 0.1322 | 0.0452 | 0.5528 | 0.0931 | 0.2582 | 0.6624 |
| `irc_alert` | `validation` | 1 | 16,260 | 0.3604 | 0.3345 | 0.8354 | 0.1230 | 0.7321 | 0.8156 |
| `irc_alert` | `validation` | 2 | 16,260 | 0.3612 | 0.3035 | 0.8100 | 0.1316 | 0.6622 | 0.7900 |
| `irc_alert` | `validation` | 3 | 16,260 | 0.3577 | 0.2745 | 0.7945 | 0.1365 | 0.6098 | 0.7734 |

## Interpretation Guardrails

- This backtest measures historical predictive behavior; the operational rollout ranking remains a separate artifact.
- `irc_alert` evaluates whether simulated IRC crosses the configured IRC threshold.
- `bloom_h` metrics are emitted only when calibrated bloom probabilities and split targets are available.
- Source-level rows are diagnostic and can be unstable for sources with limited support.

## Outputs

- Backtest rows: `reports/pipe_grud/pipe_rollout_backtest_rows_validation.parquet`
- State metrics: `reports/pipe_grud/pipe_rollout_backtest_metrics_validation.csv`
- Alert metrics: `reports/pipe_grud/pipe_rollout_backtest_alert_metrics_validation.csv`
- Diagnostic examples: `reports/pipe_grud/pipe_rollout_backtest_examples_validation.csv`
- Manifest: `reports/pipe_grud/pipe_rollout_backtest_manifest_validation.json`
