# MIFAL-ED/T2 Validation Calibration Report v0

Generated at UTC: `2026-06-27T17:23:07.582764+00:00`
Surface: `observable_current_chla`
Predictions: `reports/mifal/mifal_observable_current_chla_pipe_grud_validation_predictions.csv`
Calibration split: `validation`
Evaluation splits: `validation`

Thresholds and calibrators are selected only on the calibration split. Do not read this report as held-out test evidence unless `test` is explicitly included as an evaluation split in a later run.

## Thresholds

| horizon | score | threshold | rows | positives | recall | precision | F-beta | method |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | `mifal_probability_bloom_calibrated` | 0.1087 | 3,049 | 410 | 0.5902 | 0.3143 | 0.5021 | `isotonic` |
| 2 | `mifal_probability_bloom_calibrated` | 0.1000 | 3,158 | 441 | 0.7732 | 0.1808 | 0.4671 | `isotonic` |
| 3 | `mifal_probability_bloom_calibrated` | 0.1110 | 3,184 | 457 | 0.7637 | 0.1841 | 0.4686 | `isotonic` |

## Metrics

| split | horizon | rows | positives | threshold | PR-AUC | Brier | recall | precision | F-beta | MCC | risk RMSE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | 3,049 | 410 | 0.1087 | 0.4102 | 0.0939 | 0.5902 | 0.3143 | 0.5021 | 0.3064 | 0.4189 |
| `validation` | 2 | 3,158 | 441 | 0.1000 | 0.3391 | 0.1049 | 0.7732 | 0.1808 | 0.4671 | 0.1446 | 0.4282 |
| `validation` | 3 | 3,184 | 457 | 0.1110 | 0.3043 | 0.1103 | 0.7637 | 0.1841 | 0.4686 | 0.1403 | 0.4301 |

## Calibrator Files

- h1: `models/mifal/observable_calibrators/current_chla_pipe_grud_validation/observable_current_chla_h1_bloom_h_calibrator.json` (isotonic)
- h2: `models/mifal/observable_calibrators/current_chla_pipe_grud_validation/observable_current_chla_h2_bloom_h_calibrator.json` (isotonic)
- h3: `models/mifal/observable_calibrators/current_chla_pipe_grud_validation/observable_current_chla_h3_bloom_h_calibrator.json` (isotonic)

## Outputs

- Thresholds: `reports/mifal/mifal_observable_current_chla_pipe_grud_validation_calibration_thresholds.csv`
- Metrics: `reports/mifal/mifal_observable_current_chla_pipe_grud_validation_calibration_metrics.csv`
- Calibrated predictions: `reports/mifal/mifal_observable_current_chla_pipe_grud_validation_calibration_calibrated_predictions.csv`
- Manifest: `reports/mifal/mifal_observable_current_chla_pipe_grud_validation_calibration_manifest.json`
