# MIFAL-ED/T2 Observable Smoke Report v0

Generated at UTC: `2026-06-27T17:22:45.630229+00:00`
Surface: `observable_current_chla`
Rows evaluated: `9,391`
Reference rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_validation.parquet`
Include VOI: `False`

This is an isolated uncalibrated smoke evaluation. It must not be read as a final MIFAL-vs-PIPE comparison.

## Metrics

| split | horizon | rows | positives | PR-AUC | Brier | precision@0.5 | recall@0.5 | F2@0.5 | risk RMSE | interval coverage | interval width | data reliability |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | 3,049 | 410 | 0.4162 | 0.2918 | 0.1368 | 0.9561 | 0.4350 | 0.4344 | 0.7324 | 0.6734 | 0.0542 |
| `validation` | 2 | 3,158 | 441 | 0.3361 | 0.2941 | 0.1402 | 0.9433 | 0.4397 | 0.4344 | 0.7324 | 0.6766 | 0.0544 |
| `validation` | 3 | 3,184 | 457 | 0.3070 | 0.2928 | 0.1450 | 0.9344 | 0.4474 | 0.4341 | 0.7274 | 0.6753 | 0.0541 |

## Payload Availability

| variable | rows | present rows | coverage |
|---|---:|---:|---:|
| `Tw` | 9,391 | 4,209 | 0.4482 |
| `TP` | 9,391 | 7,821 | 0.8328 |
| `TN` | 9,391 | 5,990 | 0.6378 |
| `Secchi` | 9,391 | 8,389 | 0.8933 |
| `Turb` | 9,391 | 4,050 | 0.4313 |
| `DOb` | 9,391 | 4,103 | 0.4369 |
| `Chl` | 9,391 | 7,997 | 0.8516 |
| `Chl_prev` | 9,391 | 7,583 | 0.8075 |

## Outputs

- Predictions: `reports/mifal/mifal_observable_current_chla_pipe_grud_validation_predictions.csv`
- Metrics: `reports/mifal/mifal_observable_current_chla_pipe_grud_validation_metrics.csv`
- Availability: `reports/mifal/mifal_observable_current_chla_pipe_grud_validation_availability.csv`
- Examples: `reports/mifal/mifal_observable_current_chla_pipe_grud_validation_examples.csv`
- Manifest: `reports/mifal/mifal_observable_current_chla_pipe_grud_validation_manifest.json`
