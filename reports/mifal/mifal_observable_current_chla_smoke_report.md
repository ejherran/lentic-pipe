# MIFAL-ED/T2 Observable Smoke Report v0

Generated at UTC: `2026-06-27T17:19:02.948962+00:00`
Surface: `observable_current_chla`
Rows evaluated: `600`
Reference rows: `none`
Include VOI: `False`

This is an isolated uncalibrated smoke evaluation. It must not be read as a final MIFAL-vs-PIPE comparison.

## Metrics

| split | horizon | rows | positives | PR-AUC | Brier | precision@0.5 | recall@0.5 | F2@0.5 | risk RMSE | interval coverage | interval width | data reliability |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `test` | 1 | 100 | 16 | 0.4620 | 0.2723 | 0.1667 | 1.0000 | 0.5000 | 0.4238 | 0.7100 | 0.6561 | 0.0269 |
| `test` | 2 | 100 | 17 | 0.3615 | 0.2761 | 0.1828 | 1.0000 | 0.5280 | 0.4361 | 0.6900 | 0.6597 | 0.0307 |
| `test` | 3 | 100 | 14 | 0.3581 | 0.2806 | 0.1263 | 0.8571 | 0.3974 | 0.4521 | 0.7500 | 0.6567 | 0.0274 |
| `validation` | 1 | 100 | 15 | 0.3879 | 0.2710 | 0.1613 | 1.0000 | 0.4902 | 0.4250 | 0.8000 | 0.6483 | 0.0255 |
| `validation` | 2 | 100 | 11 | 0.2604 | 0.2787 | 0.1146 | 1.0000 | 0.3929 | 0.4377 | 0.7700 | 0.6538 | 0.0199 |
| `validation` | 3 | 100 | 16 | 0.4411 | 0.2781 | 0.1616 | 1.0000 | 0.4908 | 0.4490 | 0.7500 | 0.6604 | 0.0203 |

## Payload Availability

| variable | rows | present rows | coverage |
|---|---:|---:|---:|
| `Tw` | 600 | 122 | 0.2033 |
| `TP` | 600 | 197 | 0.3283 |
| `TN` | 600 | 123 | 0.2050 |
| `Secchi` | 600 | 196 | 0.3267 |
| `Turb` | 600 | 73 | 0.1217 |
| `DOb` | 600 | 105 | 0.1750 |
| `Chl` | 600 | 583 | 0.9717 |
| `Chl_prev` | 600 | 419 | 0.6983 |

## Outputs

- Predictions: `reports/mifal/mifal_observable_current_chla_smoke_predictions.csv`
- Metrics: `reports/mifal/mifal_observable_current_chla_smoke_metrics.csv`
- Availability: `reports/mifal/mifal_observable_current_chla_smoke_availability.csv`
- Examples: `reports/mifal/mifal_observable_current_chla_smoke_examples.csv`
- Manifest: `reports/mifal/mifal_observable_current_chla_smoke_manifest.json`
