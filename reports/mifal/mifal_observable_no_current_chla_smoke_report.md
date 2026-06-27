# MIFAL-ED/T2 Observable Smoke Report v0

Generated at UTC: `2026-06-27T17:19:03.135437+00:00`
Surface: `observable_no_current_chla`
Rows evaluated: `600`
Reference rows: `none`
Include VOI: `False`

This is an isolated uncalibrated smoke evaluation. It must not be read as a final MIFAL-vs-PIPE comparison.

## Metrics

| split | horizon | rows | positives | PR-AUC | Brier | precision@0.5 | recall@0.5 | F2@0.5 | risk RMSE | interval coverage | interval width | data reliability |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `test` | 1 | 100 | 16 | 0.3334 | 0.2670 | 0.1684 | 1.0000 | 0.5031 | 0.4236 | 0.7000 | 0.6403 | 0.0227 |
| `test` | 2 | 100 | 17 | 0.2705 | 0.2696 | 0.1868 | 1.0000 | 0.5346 | 0.4349 | 0.6900 | 0.6452 | 0.0264 |
| `test` | 3 | 100 | 14 | 0.2306 | 0.2731 | 0.1263 | 0.8571 | 0.3974 | 0.4487 | 0.7500 | 0.6427 | 0.0232 |
| `validation` | 1 | 100 | 15 | 0.3138 | 0.2643 | 0.1630 | 1.0000 | 0.4934 | 0.4212 | 0.8000 | 0.6358 | 0.0216 |
| `validation` | 2 | 100 | 11 | 0.1563 | 0.2719 | 0.1158 | 1.0000 | 0.3957 | 0.4357 | 0.7500 | 0.6397 | 0.0159 |
| `validation` | 3 | 100 | 16 | 0.2291 | 0.2727 | 0.1616 | 1.0000 | 0.4908 | 0.4468 | 0.7300 | 0.6469 | 0.0162 |

## Payload Availability

| variable | rows | present rows | coverage |
|---|---:|---:|---:|
| `Tw` | 600 | 122 | 0.2033 |
| `TP` | 600 | 197 | 0.3283 |
| `TN` | 600 | 123 | 0.2050 |
| `Secchi` | 600 | 196 | 0.3267 |
| `Turb` | 600 | 73 | 0.1217 |
| `DOb` | 600 | 105 | 0.1750 |
| `Chl` | 600 | 0 | 0.0000 |
| `Chl_prev` | 600 | 419 | 0.6983 |

## Outputs

- Predictions: `reports/mifal/mifal_observable_no_current_chla_smoke_predictions.csv`
- Metrics: `reports/mifal/mifal_observable_no_current_chla_smoke_metrics.csv`
- Availability: `reports/mifal/mifal_observable_no_current_chla_smoke_availability.csv`
- Examples: `reports/mifal/mifal_observable_no_current_chla_smoke_examples.csv`
- Manifest: `reports/mifal/mifal_observable_no_current_chla_smoke_manifest.json`
