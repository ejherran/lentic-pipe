# MIFAL-ED/T2 Observable Smoke Report v0

Generated at UTC: `2026-06-27T17:22:48.762116+00:00`
Surface: `observable_no_current_chla`
Rows evaluated: `23,531`
Reference rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibrated_backtest_rows.parquet`
Include VOI: `False`

This is an isolated uncalibrated smoke evaluation. It must not be read as a final MIFAL-vs-PIPE comparison.

## Metrics

| split | horizon | rows | positives | PR-AUC | Brier | precision@0.5 | recall@0.5 | F2@0.5 | risk RMSE | interval coverage | interval width | data reliability |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `test` | 1 | 4,673 | 852 | 0.3450 | 0.2802 | 0.1781 | 0.9026 | 0.4977 | 0.4382 | 0.6871 | 0.6581 | 0.0532 |
| `test` | 2 | 4,710 | 863 | 0.3137 | 0.2832 | 0.1751 | 0.8899 | 0.4899 | 0.4383 | 0.6824 | 0.6621 | 0.0533 |
| `test` | 3 | 4,757 | 883 | 0.2957 | 0.2833 | 0.1766 | 0.8867 | 0.4915 | 0.4371 | 0.6805 | 0.6622 | 0.0536 |
| `validation` | 1 | 3,049 | 410 | 0.1915 | 0.2852 | 0.1379 | 0.9512 | 0.4364 | 0.4321 | 0.7281 | 0.6605 | 0.0504 |
| `validation` | 2 | 3,158 | 441 | 0.1765 | 0.2878 | 0.1406 | 0.9433 | 0.4404 | 0.4321 | 0.7236 | 0.6646 | 0.0508 |
| `validation` | 3 | 3,184 | 457 | 0.1818 | 0.2867 | 0.1454 | 0.9344 | 0.4482 | 0.4319 | 0.7217 | 0.6636 | 0.0507 |

## Payload Availability

| variable | rows | present rows | coverage |
|---|---:|---:|---:|
| `Tw` | 23,531 | 11,157 | 0.4741 |
| `TP` | 23,531 | 20,866 | 0.8867 |
| `TN` | 23,531 | 15,688 | 0.6667 |
| `Secchi` | 23,531 | 21,282 | 0.9044 |
| `Turb` | 23,531 | 10,798 | 0.4589 |
| `DOb` | 23,531 | 10,861 | 0.4616 |
| `Chl` | 23,531 | 0 | 0.0000 |
| `Chl_prev` | 23,531 | 20,795 | 0.8837 |

## Outputs

- Predictions: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_holdout_predictions.csv`
- Metrics: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_holdout_metrics.csv`
- Availability: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_holdout_availability.csv`
- Examples: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_holdout_examples.csv`
- Manifest: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_holdout_manifest.json`
