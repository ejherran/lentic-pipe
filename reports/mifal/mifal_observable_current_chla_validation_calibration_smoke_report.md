# MIFAL-ED/T2 Validation Calibration Report v0

Generated at UTC: `2026-06-27T17:19:12.275366+00:00`
Surface: `observable_current_chla`
Predictions: `reports/mifal/mifal_observable_current_chla_smoke_predictions.csv`
Calibration split: `validation`
Evaluation splits: `validation`

Thresholds and calibrators are selected only on the calibration split. Do not read this report as held-out test evidence unless `test` is explicitly included as an evaluation split in a later run.

## Thresholds

| horizon | score | threshold | rows | positives | recall | precision | F-beta | method |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | `mifal_probability_bloom_calibrated` | 0.2500 | 100 | 15 | 0.6667 | 0.3448 | 0.5618 | `isotonic` |
| 2 | `mifal_probability_bloom_calibrated` | 0.2000 | 100 | 11 | 0.9091 | 0.2941 | 0.6410 | `isotonic` |
| 3 | `mifal_probability_bloom_calibrated` | 0.1333 | 100 | 16 | 1.0000 | 0.2051 | 0.5634 | `isotonic` |

## Metrics

| split | horizon | rows | positives | threshold | PR-AUC | Brier | recall | precision | F-beta | MCC | risk RMSE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `validation` | 1 | 100 | 15 | 0.2500 | 0.3986 | 0.1013 | 0.6667 | 0.3448 | 0.5618 | 0.3487 | 0.3711 |
| `validation` | 2 | 100 | 11 | 0.2000 | 0.2927 | 0.0799 | 0.9091 | 0.2941 | 0.6410 | 0.4223 | 0.4287 |
| `validation` | 3 | 100 | 16 | 0.1333 | 0.4291 | 0.1052 | 1.0000 | 0.2051 | 0.5634 | 0.2318 | 0.4023 |

## Calibrator Files

- h1: `models/mifal/observable_calibrators/current_chla_smoke/observable_current_chla_h1_bloom_h_calibrator.json` (isotonic)
- h2: `models/mifal/observable_calibrators/current_chla_smoke/observable_current_chla_h2_bloom_h_calibrator.json` (isotonic)
- h3: `models/mifal/observable_calibrators/current_chla_smoke/observable_current_chla_h3_bloom_h_calibrator.json` (isotonic)

## Outputs

- Thresholds: `reports/mifal/mifal_observable_current_chla_validation_calibration_smoke_thresholds.csv`
- Metrics: `reports/mifal/mifal_observable_current_chla_validation_calibration_smoke_metrics.csv`
- Calibrated predictions: `reports/mifal/mifal_observable_current_chla_validation_calibration_smoke_calibrated_predictions.csv`
- Manifest: `reports/mifal/mifal_observable_current_chla_validation_calibration_smoke_manifest.json`
