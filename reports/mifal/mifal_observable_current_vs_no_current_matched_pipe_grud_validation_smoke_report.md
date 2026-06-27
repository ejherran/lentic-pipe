# MIFAL-ED/T2 Matched-Surface Evaluation Report v0

Generated at UTC: `2026-06-27T17:19:22.057370+00:00`
Matched key rows: `7`
Long matched prediction rows: `14`
Evaluation splits: `validation`
Reference rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_validation.parquet`

This report evaluates already-calibrated MIFAL predictions on an exact intersection of source, site, origin month, horizon, and split.
It does not fit calibrators, select thresholds, or use test rows unless `test` is explicitly requested.

## Inputs

- `no_current_chla`: `reports/mifal/mifal_observable_no_current_chla_validation_calibration_smoke_calibrated_predictions.csv`
- `current_chla`: `reports/mifal/mifal_observable_current_chla_validation_calibration_smoke_calibrated_predictions.csv`

## Metrics

| model | surface | split | horizon | rows | positives | predicted positive rate | PR-AUC | Brier | precision | recall | F-beta | MCC | risk RMSE | interval width | data reliability |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `current_chla` | `observable_current_chla` | `validation` | 1 | 2 | 0 | 1.0000 | 0.0000 | 0.0997 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.2251 | 0.6827 | 0.0612 |
| `current_chla` | `observable_current_chla` | `validation` | 2 | 1 | 0 | 1.0000 | 0.0000 | 0.0963 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.3544 | 0.6762 | 0.0682 |
| `current_chla` | `observable_current_chla` | `validation` | 3 | 4 | 0 | 1.0000 | 0.0000 | 0.0317 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.1864 | 0.6773 | 0.0558 |
| `no_current_chla` | `observable_no_current_chla` | `validation` | 1 | 2 | 0 | 1.0000 | 0.0000 | 0.0922 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.1147 | 0.6691 | 0.0564 |
| `no_current_chla` | `observable_no_current_chla` | `validation` | 2 | 1 | 0 | 1.0000 | 0.0000 | 0.0242 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.5092 | 0.6645 | 0.0643 |
| `no_current_chla` | `observable_no_current_chla` | `validation` | 3 | 4 | 0 | 1.0000 | 0.0000 | 0.0415 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.1821 | 0.6661 | 0.0518 |

## Comparison Against First Input

| baseline | comparison | split | horizon | delta PR-AUC | delta Brier | delta F-beta | delta MCC | delta recall | delta precision |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `no_current_chla` | `current_chla` | `validation` | 1 | 0.0000 | 0.0075 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `no_current_chla` | `current_chla` | `validation` | 2 | 0.0000 | 0.0721 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `no_current_chla` | `current_chla` | `validation` | 3 | 0.0000 | -0.0098 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Outputs

- Matched rows: `reports/mifal/mifal_observable_current_vs_no_current_matched_pipe_grud_validation_smoke_matched_rows.csv`
- Metrics: `reports/mifal/mifal_observable_current_vs_no_current_matched_pipe_grud_validation_smoke_metrics.csv`
- Comparison: `reports/mifal/mifal_observable_current_vs_no_current_matched_pipe_grud_validation_smoke_comparison.csv`
- Manifest: `reports/mifal/mifal_observable_current_vs_no_current_matched_pipe_grud_validation_smoke_manifest.json`
