# MIFAL-ED/T2 Matched-Surface Evaluation Report v0

Generated at UTC: `2026-06-27T17:19:21.978102+00:00`
Matched key rows: `300`
Long matched prediction rows: `600`
Evaluation splits: `validation`
Reference rows: `none`

This report evaluates already-calibrated MIFAL predictions on an exact intersection of source, site, origin month, horizon, and split.
It does not fit calibrators, select thresholds, or use test rows unless `test` is explicitly requested.

## Inputs

- `no_current_chla`: `reports/mifal/mifal_observable_no_current_chla_validation_calibration_smoke_calibrated_predictions.csv`
- `current_chla`: `reports/mifal/mifal_observable_current_chla_validation_calibration_smoke_calibrated_predictions.csv`

## Metrics

| model | surface | split | horizon | rows | positives | predicted positive rate | PR-AUC | Brier | precision | recall | F-beta | MCC | risk RMSE | interval width | data reliability |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `current_chla` | `observable_current_chla` | `validation` | 1 | 100 | 15 | 0.2900 | 0.3986 | 0.1013 | 0.3448 | 0.6667 | 0.5618 | 0.3487 | 0.3711 | 0.6483 | 0.0255 |
| `current_chla` | `observable_current_chla` | `validation` | 2 | 100 | 11 | 0.3400 | 0.2927 | 0.0799 | 0.2941 | 0.9091 | 0.6410 | 0.4223 | 0.4287 | 0.6538 | 0.0199 |
| `current_chla` | `observable_current_chla` | `validation` | 3 | 100 | 16 | 0.7800 | 0.4291 | 0.1052 | 0.2051 | 1.0000 | 0.5634 | 0.2318 | 0.4023 | 0.6604 | 0.0203 |
| `no_current_chla` | `observable_no_current_chla` | `validation` | 1 | 100 | 15 | 0.5800 | 0.3601 | 0.1046 | 0.2414 | 0.9333 | 0.5932 | 0.3007 | 0.3624 | 0.6358 | 0.0216 |
| `no_current_chla` | `observable_no_current_chla` | `validation` | 2 | 100 | 11 | 0.6800 | 0.1810 | 0.0916 | 0.1618 | 1.0000 | 0.4911 | 0.2412 | 0.4210 | 0.6397 | 0.0159 |
| `no_current_chla` | `observable_no_current_chla` | `validation` | 3 | 100 | 16 | 0.6700 | 0.2494 | 0.1259 | 0.2090 | 0.8750 | 0.5344 | 0.1903 | 0.4147 | 0.6469 | 0.0162 |

## Comparison Against First Input

| baseline | comparison | split | horizon | delta PR-AUC | delta Brier | delta F-beta | delta MCC | delta recall | delta precision |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `no_current_chla` | `current_chla` | `validation` | 1 | 0.0385 | -0.0033 | -0.0314 | 0.0480 | -0.2667 | 0.1034 |
| `no_current_chla` | `current_chla` | `validation` | 2 | 0.1117 | -0.0117 | 0.1500 | 0.1812 | -0.0909 | 0.1324 |
| `no_current_chla` | `current_chla` | `validation` | 3 | 0.1796 | -0.0206 | 0.0290 | 0.0415 | 0.1250 | -0.0038 |

## Outputs

- Matched rows: `reports/mifal/mifal_observable_current_vs_no_current_matched_validation_smoke_matched_rows.csv`
- Metrics: `reports/mifal/mifal_observable_current_vs_no_current_matched_validation_smoke_metrics.csv`
- Comparison: `reports/mifal/mifal_observable_current_vs_no_current_matched_validation_smoke_comparison.csv`
- Manifest: `reports/mifal/mifal_observable_current_vs_no_current_matched_validation_smoke_manifest.json`
