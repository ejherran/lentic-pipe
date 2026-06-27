# MIFAL-ED/T2 Validation Calibration Report v0

Generated at UTC: `2026-06-27T17:23:07.739274+00:00`
Surface: `observable_no_current_chla`
Predictions: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_validation_predictions.csv`
Calibration split: `validation`
Evaluation splits: `validation`

Thresholds and calibrators are selected only on the calibration split. Do not read this report as held-out test evidence unless `test` is explicitly included as an evaluation split in a later run.

## Thresholds

| horizon | score | threshold | rows | positives | recall | precision | F-beta | method |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | `mifal_probability_bloom_calibrated` | 0.1497 | 3,049 | 410 | 0.7195 | 0.2574 | 0.5294 | `isotonic` |
| 2 | `mifal_probability_bloom_calibrated` | 0.1111 | 3,158 | 441 | 0.6961 | 0.2340 | 0.4990 | `isotonic` |
| 3 | `mifal_probability_bloom_calibrated` | 0.1356 | 3,184 | 457 | 0.7024 | 0.2464 | 0.5126 | `isotonic` |

## Metrics

| split | horizon | rows | positives | threshold | PR-AUC | Brier | recall | precision | F-beta | MCC | risk RMSE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | 3,049 | 410 | 0.1497 | 0.2371 | 0.1066 | 0.7195 | 0.2574 | 0.5294 | 0.2797 | 0.4156 |
| `validation` | 2 | 3,158 | 441 | 0.1111 | 0.2199 | 0.1132 | 0.6961 | 0.2340 | 0.4990 | 0.2295 | 0.4249 |
| `validation` | 3 | 3,184 | 457 | 0.1356 | 0.2233 | 0.1153 | 0.7024 | 0.2464 | 0.5126 | 0.2441 | 0.4251 |

## Calibrator Files

- h1: `models/mifal/observable_calibrators/no_current_chla_pipe_grud_validation/observable_no_current_chla_h1_bloom_h_calibrator.json` (isotonic)
- h2: `models/mifal/observable_calibrators/no_current_chla_pipe_grud_validation/observable_no_current_chla_h2_bloom_h_calibrator.json` (isotonic)
- h3: `models/mifal/observable_calibrators/no_current_chla_pipe_grud_validation/observable_no_current_chla_h3_bloom_h_calibrator.json` (isotonic)

## Outputs

- Thresholds: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_validation_calibration_thresholds.csv`
- Metrics: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_validation_calibration_metrics.csv`
- Calibrated predictions: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_validation_calibration_calibrated_predictions.csv`
- Manifest: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_validation_calibration_manifest.json`
