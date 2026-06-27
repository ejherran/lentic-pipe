# MIFAL-ED/T2 Validation Calibration Report v0

Generated at UTC: `2026-06-27T17:19:12.275204+00:00`
Surface: `observable_no_current_chla`
Predictions: `reports/mifal/mifal_observable_no_current_chla_smoke_predictions.csv`
Calibration split: `validation`
Evaluation splits: `validation`

Thresholds and calibrators are selected only on the calibration split. Do not read this report as held-out test evidence unless `test` is explicitly included as an evaluation split in a later run.

## Thresholds

| horizon | score | threshold | rows | positives | recall | precision | F-beta | method |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | `mifal_probability_bloom_calibrated` | 0.1250 | 100 | 15 | 0.9333 | 0.2414 | 0.5932 | `isotonic` |
| 2 | `mifal_probability_bloom_calibrated` | 0.1111 | 100 | 11 | 1.0000 | 0.1618 | 0.4911 | `isotonic` |
| 3 | `mifal_probability_bloom_calibrated` | 0.1591 | 100 | 16 | 0.8750 | 0.2090 | 0.5344 | `isotonic` |

## Metrics

| split | horizon | rows | positives | threshold | PR-AUC | Brier | recall | precision | F-beta | MCC | risk RMSE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | 100 | 15 | 0.1250 | 0.3601 | 0.1046 | 0.9333 | 0.2414 | 0.5932 | 0.3007 | 0.3624 |
| `validation` | 2 | 100 | 11 | 0.1111 | 0.1810 | 0.0916 | 1.0000 | 0.1618 | 0.4911 | 0.2412 | 0.4210 |
| `validation` | 3 | 100 | 16 | 0.1591 | 0.2494 | 0.1259 | 0.8750 | 0.2090 | 0.5344 | 0.1903 | 0.4147 |

## Calibrator Files

- h1: `models/mifal/observable_calibrators/no_current_chla_smoke/observable_no_current_chla_h1_bloom_h_calibrator.json` (isotonic)
- h2: `models/mifal/observable_calibrators/no_current_chla_smoke/observable_no_current_chla_h2_bloom_h_calibrator.json` (isotonic)
- h3: `models/mifal/observable_calibrators/no_current_chla_smoke/observable_no_current_chla_h3_bloom_h_calibrator.json` (isotonic)

## Outputs

- Thresholds: `reports/mifal/mifal_observable_no_current_chla_validation_calibration_smoke_thresholds.csv`
- Metrics: `reports/mifal/mifal_observable_no_current_chla_validation_calibration_smoke_metrics.csv`
- Calibrated predictions: `reports/mifal/mifal_observable_no_current_chla_validation_calibration_smoke_calibrated_predictions.csv`
- Manifest: `reports/mifal/mifal_observable_no_current_chla_validation_calibration_smoke_manifest.json`
