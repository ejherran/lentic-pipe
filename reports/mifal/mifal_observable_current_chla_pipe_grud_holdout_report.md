# MIFAL-ED/T2 Observable Smoke Report v0

Generated at UTC: `2026-06-27T17:22:48.901731+00:00`
Surface: `observable_current_chla`
Rows evaluated: `23,531`
Reference rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibrated_backtest_rows.parquet`
Include VOI: `False`

This is an isolated uncalibrated smoke evaluation. It must not be read as a final MIFAL-vs-PIPE comparison.

## Metrics

| split | horizon | rows | positives | PR-AUC | Brier | precision@0.5 | recall@0.5 | F2@0.5 | risk RMSE | interval coverage | interval width | data reliability |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `test` | 1 | 4,673 | 852 | 0.6440 | 0.2872 | 0.1795 | 0.9214 | 0.5044 | 0.4398 | 0.6918 | 0.6753 | 0.0581 |
| `test` | 2 | 4,710 | 863 | 0.5640 | 0.2904 | 0.1759 | 0.9015 | 0.4940 | 0.4402 | 0.6868 | 0.6790 | 0.0581 |
| `test` | 3 | 4,757 | 883 | 0.5228 | 0.2905 | 0.1778 | 0.9003 | 0.4966 | 0.4390 | 0.6857 | 0.6789 | 0.0583 |
| `validation` | 1 | 3,049 | 410 | 0.4162 | 0.2918 | 0.1368 | 0.9561 | 0.4350 | 0.4344 | 0.7324 | 0.6734 | 0.0542 |
| `validation` | 2 | 3,158 | 441 | 0.3361 | 0.2941 | 0.1402 | 0.9433 | 0.4397 | 0.4344 | 0.7324 | 0.6766 | 0.0544 |
| `validation` | 3 | 3,184 | 457 | 0.3070 | 0.2928 | 0.1450 | 0.9344 | 0.4474 | 0.4341 | 0.7274 | 0.6753 | 0.0541 |

## Payload Availability

| variable | rows | present rows | coverage |
|---|---:|---:|---:|
| `Tw` | 23,531 | 11,157 | 0.4741 |
| `TP` | 23,531 | 20,866 | 0.8867 |
| `TN` | 23,531 | 15,688 | 0.6667 |
| `Secchi` | 23,531 | 21,282 | 0.9044 |
| `Turb` | 23,531 | 10,798 | 0.4589 |
| `DOb` | 23,531 | 10,861 | 0.4616 |
| `Chl` | 23,531 | 21,362 | 0.9078 |
| `Chl_prev` | 23,531 | 20,795 | 0.8837 |

## Outputs

- Predictions: `reports/mifal/mifal_observable_current_chla_pipe_grud_holdout_predictions.csv`
- Metrics: `reports/mifal/mifal_observable_current_chla_pipe_grud_holdout_metrics.csv`
- Availability: `reports/mifal/mifal_observable_current_chla_pipe_grud_holdout_availability.csv`
- Examples: `reports/mifal/mifal_observable_current_chla_pipe_grud_holdout_examples.csv`
- Manifest: `reports/mifal/mifal_observable_current_chla_pipe_grud_holdout_manifest.json`
