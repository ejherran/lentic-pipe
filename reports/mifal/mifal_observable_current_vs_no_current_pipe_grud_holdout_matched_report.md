# MIFAL-ED/T2 Matched-Surface Evaluation Report v0

Generated at UTC: `2026-06-27T17:23:29.817254+00:00`
Matched key rows: `23,531`
Long matched prediction rows: `47,062`
Evaluation splits: `validation, test`
Reference rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibrated_backtest_rows.parquet`

This report evaluates already-calibrated MIFAL predictions on an exact intersection of source, site, origin month, horizon, and split.
It does not fit calibrators, select thresholds, or use test rows unless `test` is explicitly requested.

## Inputs

- `no_current_chla`: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_holdout_calibration_calibrated_predictions.csv`
- `current_chla`: `reports/mifal/mifal_observable_current_chla_pipe_grud_holdout_calibration_calibrated_predictions.csv`

## Metrics

| model | surface | split | horizon | rows | positives | predicted positive rate | PR-AUC | Brier | precision | recall | F-beta | MCC | risk RMSE | interval width | data reliability |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `current_chla` | `observable_current_chla` | `test` | 1 | 4,673 | 852 | 0.3629 | 0.6147 | 0.1005 | 0.3815 | 0.7594 | 0.6338 | 0.3893 | 0.4104 | 0.6753 | 0.0581 |
| `current_chla` | `observable_current_chla` | `test` | 2 | 4,710 | 863 | 0.6671 | 0.5416 | 0.1118 | 0.2225 | 0.8100 | 0.5300 | 0.1436 | 0.4213 | 0.6790 | 0.0581 |
| `current_chla` | `observable_current_chla` | `test` | 3 | 4,757 | 883 | 0.6637 | 0.4872 | 0.1195 | 0.2211 | 0.7905 | 0.5218 | 0.1282 | 0.4267 | 0.6789 | 0.0583 |
| `current_chla` | `observable_current_chla` | `validation` | 1 | 3,049 | 410 | 0.2525 | 0.4102 | 0.0939 | 0.3143 | 0.5902 | 0.5021 | 0.3064 | 0.4189 | 0.6734 | 0.0542 |
| `current_chla` | `observable_current_chla` | `validation` | 2 | 3,158 | 441 | 0.5972 | 0.3391 | 0.1049 | 0.1808 | 0.7732 | 0.4671 | 0.1446 | 0.4282 | 0.6766 | 0.0544 |
| `current_chla` | `observable_current_chla` | `validation` | 3 | 3,184 | 457 | 0.5955 | 0.3043 | 0.1103 | 0.1841 | 0.7637 | 0.4686 | 0.1403 | 0.4301 | 0.6753 | 0.0541 |
| `no_current_chla` | `observable_no_current_chla` | `test` | 1 | 4,673 | 852 | 0.3266 | 0.3608 | 0.1344 | 0.3847 | 0.6890 | 0.5949 | 0.3649 | 0.4521 | 0.6581 | 0.0532 |
| `no_current_chla` | `observable_no_current_chla` | `test` | 2 | 4,710 | 863 | 0.3624 | 0.3307 | 0.1384 | 0.3579 | 0.7080 | 0.5922 | 0.3405 | 0.4571 | 0.6621 | 0.0533 |
| `no_current_chla` | `observable_no_current_chla` | `test` | 3 | 4,757 | 883 | 0.3616 | 0.3218 | 0.1398 | 0.3477 | 0.6772 | 0.5693 | 0.3137 | 0.4550 | 0.6622 | 0.0536 |
| `no_current_chla` | `observable_no_current_chla` | `validation` | 1 | 3,049 | 410 | 0.3759 | 0.2371 | 0.1066 | 0.2574 | 0.7195 | 0.5294 | 0.2797 | 0.4156 | 0.6605 | 0.0504 |
| `no_current_chla` | `observable_no_current_chla` | `validation` | 2 | 3,158 | 441 | 0.4155 | 0.2199 | 0.1132 | 0.2340 | 0.6961 | 0.4990 | 0.2295 | 0.4249 | 0.6646 | 0.0508 |
| `no_current_chla` | `observable_no_current_chla` | `validation` | 3 | 3,184 | 457 | 0.4092 | 0.2233 | 0.1153 | 0.2464 | 0.7024 | 0.5126 | 0.2441 | 0.4251 | 0.6636 | 0.0507 |

## Comparison Against First Input

| baseline | comparison | split | horizon | delta PR-AUC | delta Brier | delta F-beta | delta MCC | delta recall | delta precision |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `no_current_chla` | `current_chla` | `test` | 1 | 0.2539 | -0.0340 | 0.0390 | 0.0244 | 0.0704 | -0.0032 |
| `no_current_chla` | `current_chla` | `test` | 2 | 0.2108 | -0.0266 | -0.0621 | -0.1969 | 0.1020 | -0.1355 |
| `no_current_chla` | `current_chla` | `test` | 3 | 0.1653 | -0.0203 | -0.0476 | -0.1855 | 0.1133 | -0.1266 |
| `no_current_chla` | `current_chla` | `validation` | 1 | 0.1731 | -0.0127 | -0.0274 | 0.0267 | -0.1293 | 0.0569 |
| `no_current_chla` | `current_chla` | `validation` | 2 | 0.1192 | -0.0083 | -0.0319 | -0.0849 | 0.0771 | -0.0532 |
| `no_current_chla` | `current_chla` | `validation` | 3 | 0.0810 | -0.0050 | -0.0440 | -0.1038 | 0.0613 | -0.0623 |

## Outputs

- Matched rows: `reports/mifal/mifal_observable_current_vs_no_current_pipe_grud_holdout_matched_matched_rows.csv`
- Metrics: `reports/mifal/mifal_observable_current_vs_no_current_pipe_grud_holdout_matched_metrics.csv`
- Comparison: `reports/mifal/mifal_observable_current_vs_no_current_pipe_grud_holdout_matched_comparison.csv`
- Manifest: `reports/mifal/mifal_observable_current_vs_no_current_pipe_grud_holdout_matched_manifest.json`
