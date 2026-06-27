# MIFAL-ED/T2 Observable Smoke Report v0

Generated at UTC: `2026-06-27T17:22:45.258342+00:00`
Surface: `observable_no_current_chla`
Rows evaluated: `9,391`
Reference rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_validation.parquet`
Include VOI: `False`

This is an isolated uncalibrated smoke evaluation. It must not be read as a final MIFAL-vs-PIPE comparison.

## Metrics

| split | horizon | rows | positives | PR-AUC | Brier | precision@0.5 | recall@0.5 | F2@0.5 | risk RMSE | interval coverage | interval width | data reliability |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | 3,049 | 410 | 0.1915 | 0.2852 | 0.1379 | 0.9512 | 0.4364 | 0.4321 | 0.7281 | 0.6605 | 0.0504 |
| `validation` | 2 | 3,158 | 441 | 0.1765 | 0.2878 | 0.1406 | 0.9433 | 0.4404 | 0.4321 | 0.7236 | 0.6646 | 0.0508 |
| `validation` | 3 | 3,184 | 457 | 0.1818 | 0.2867 | 0.1454 | 0.9344 | 0.4482 | 0.4319 | 0.7217 | 0.6636 | 0.0507 |

## Payload Availability

| variable | rows | present rows | coverage |
|---|---:|---:|---:|
| `Tw` | 9,391 | 4,209 | 0.4482 |
| `TP` | 9,391 | 7,821 | 0.8328 |
| `TN` | 9,391 | 5,990 | 0.6378 |
| `Secchi` | 9,391 | 8,389 | 0.8933 |
| `Turb` | 9,391 | 4,050 | 0.4313 |
| `DOb` | 9,391 | 4,103 | 0.4369 |
| `Chl` | 9,391 | 0 | 0.0000 |
| `Chl_prev` | 9,391 | 7,583 | 0.8075 |

## Outputs

- Predictions: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_validation_predictions.csv`
- Metrics: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_validation_metrics.csv`
- Availability: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_validation_availability.csv`
- Examples: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_validation_examples.csv`
- Manifest: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_validation_manifest.json`
