# MIFAL-ED/T2 Matched-Surface Evaluation Report v0

Generated at UTC: `2026-06-27T17:23:29.198263+00:00`
Matched key rows: `9,391`
Long matched prediction rows: `18,782`
Evaluation splits: `validation`
Reference rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_validation.parquet`

This report evaluates already-calibrated MIFAL predictions on an exact intersection of source, site, origin month, horizon, and split.
It does not fit calibrators, select thresholds, or use test rows unless `test` is explicitly requested.

## Inputs

- `no_current_chla`: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_validation_calibration_calibrated_predictions.csv`
- `current_chla`: `reports/mifal/mifal_observable_current_chla_pipe_grud_validation_calibration_calibrated_predictions.csv`

## Metrics

| model | surface | split | horizon | rows | positives | predicted positive rate | PR-AUC | Brier | precision | recall | F-beta | MCC | risk RMSE | interval width | data reliability |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `current_chla` | `observable_current_chla` | `validation` | 1 | 3,049 | 410 | 0.2525 | 0.4102 | 0.0939 | 0.3143 | 0.5902 | 0.5021 | 0.3064 | 0.4189 | 0.6734 | 0.0542 |
| `current_chla` | `observable_current_chla` | `validation` | 2 | 3,158 | 441 | 0.5972 | 0.3391 | 0.1049 | 0.1808 | 0.7732 | 0.4671 | 0.1446 | 0.4282 | 0.6766 | 0.0544 |
| `current_chla` | `observable_current_chla` | `validation` | 3 | 3,184 | 457 | 0.5955 | 0.3043 | 0.1103 | 0.1841 | 0.7637 | 0.4686 | 0.1403 | 0.4301 | 0.6753 | 0.0541 |
| `no_current_chla` | `observable_no_current_chla` | `validation` | 1 | 3,049 | 410 | 0.3759 | 0.2371 | 0.1066 | 0.2574 | 0.7195 | 0.5294 | 0.2797 | 0.4156 | 0.6605 | 0.0504 |
| `no_current_chla` | `observable_no_current_chla` | `validation` | 2 | 3,158 | 441 | 0.4155 | 0.2199 | 0.1132 | 0.2340 | 0.6961 | 0.4990 | 0.2295 | 0.4249 | 0.6646 | 0.0508 |
| `no_current_chla` | `observable_no_current_chla` | `validation` | 3 | 3,184 | 457 | 0.4092 | 0.2233 | 0.1153 | 0.2464 | 0.7024 | 0.5126 | 0.2441 | 0.4251 | 0.6636 | 0.0507 |

## Comparison Against First Input

| baseline | comparison | split | horizon | delta PR-AUC | delta Brier | delta F-beta | delta MCC | delta recall | delta precision |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `no_current_chla` | `current_chla` | `validation` | 1 | 0.1731 | -0.0127 | -0.0274 | 0.0267 | -0.1293 | 0.0569 |
| `no_current_chla` | `current_chla` | `validation` | 2 | 0.1192 | -0.0083 | -0.0319 | -0.0849 | 0.0771 | -0.0532 |
| `no_current_chla` | `current_chla` | `validation` | 3 | 0.0810 | -0.0050 | -0.0440 | -0.1038 | 0.0613 | -0.0623 |

## Outputs

- Matched rows: `reports/mifal/mifal_observable_current_vs_no_current_pipe_grud_validation_matched_matched_rows.csv`
- Metrics: `reports/mifal/mifal_observable_current_vs_no_current_pipe_grud_validation_matched_metrics.csv`
- Comparison: `reports/mifal/mifal_observable_current_vs_no_current_pipe_grud_validation_matched_comparison.csv`
- Manifest: `reports/mifal/mifal_observable_current_vs_no_current_pipe_grud_validation_matched_manifest.json`
