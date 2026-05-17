# Baseline Selection And Calibration Report

Generated at UTC: `2026-05-16T21:03:55.419034+00:00`
Baseline metrics: `reports/baselines/baseline_metrics.csv`
Baseline manifest: `reports/baselines/baseline_manifest.json`

## Selection Policy

- Bloom classification: choose per horizon on `validation` by max PR-AUC, then min Brier, then max macro-F1.
- Risk regression: choose per horizon on `validation` by min MAE, then min RMSE.
- Calibration: fit isotonic calibration on `validation` for the selected bloom baseline only.
- Threshold: choose on `validation` after calibration by max macro-F1.
- `test` is used only for final reporting.

## Selected Baselines

| task | horizon | model | validation PR-AUC | validation Brier | validation MAE risk | policy |
|---|---:|---|---:|---:|---:|---|
| `bloom` | 1 | `logistic_sgd` | 0.6586 | 0.0876 | NA | validation max PR-AUC; tie min Brier; tie max macro-F1 |
| `bloom` | 2 | `persistence` | 0.4885 | 0.1520 | 0.1855 | validation max PR-AUC; tie min Brier; tie max macro-F1 |
| `bloom` | 3 | `logistic_sgd` | 0.5410 | 0.1079 | NA | validation max PR-AUC; tie min Brier; tie max macro-F1 |
| `risk` | 1 | `persistence` | 0.5695 | 0.1441 | 0.1569 | validation min MAE risk; tie min RMSE risk |
| `risk` | 2 | `persistence` | 0.4885 | 0.1520 | 0.1855 | validation min MAE risk; tie min RMSE risk |
| `risk` | 3 | `persistence` | 0.4496 | 0.1572 | 0.2032 | validation min MAE risk; tie min RMSE risk |

## Calibrated Bloom Metrics

| horizon | split | model | phase | rows | threshold | PR-AUC | ROC-AUC | Brier | recall | macro-F1 |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | `test` | `logistic_sgd` | `isotonic_calibrated` | 121,540 | 0.3500 | 0.6924 | 0.9169 | 0.0651 | 0.6901 | 0.8122 |
| 1 | `test` | `logistic_sgd` | `uncalibrated_selected` | 121,540 | 0.5000 | 0.7030 | 0.9237 | 0.0856 | 0.6655 | 0.8102 |
| 1 | `validation` | `logistic_sgd` | `isotonic_calibrated` | 163,110 | 0.3500 | 0.6482 | 0.9055 | 0.0650 | 0.6599 | 0.7937 |
| 1 | `validation` | `logistic_sgd` | `uncalibrated_selected` | 163,110 | 0.5000 | 0.6586 | 0.9134 | 0.0876 | 0.6348 | 0.7921 |
| 2 | `test` | `persistence` | `isotonic_calibrated` | 115,691 | 0.3000 | 0.5461 | 0.8734 | 0.0819 | 0.6246 | 0.7723 |
| 2 | `test` | `persistence` | `uncalibrated_selected` | 115,691 | 0.5000 | 0.5493 | 0.8730 | 0.1519 | 0.8082 | 0.7047 |
| 2 | `validation` | `persistence` | `isotonic_calibrated` | 154,216 | 0.3000 | 0.4854 | 0.8592 | 0.0788 | 0.5818 | 0.7503 |
| 2 | `validation` | `persistence` | `uncalibrated_selected` | 154,216 | 0.5000 | 0.4885 | 0.8587 | 0.1520 | 0.7774 | 0.6868 |
| 3 | `test` | `logistic_sgd` | `isotonic_calibrated` | 99,670 | 0.3000 | 0.5980 | 0.8645 | 0.0854 | 0.6347 | 0.7625 |
| 3 | `test` | `logistic_sgd` | `uncalibrated_selected` | 99,670 | 0.5000 | 0.6155 | 0.8818 | 0.1166 | 0.2710 | 0.6673 |
| 3 | `validation` | `logistic_sgd` | `isotonic_calibrated` | 136,038 | 0.3000 | 0.5247 | 0.8468 | 0.0820 | 0.5774 | 0.7358 |
| 3 | `validation` | `logistic_sgd` | `uncalibrated_selected` | 136,038 | 0.5000 | 0.5410 | 0.8668 | 0.1079 | 0.2208 | 0.6393 |

## Selected Risk Metrics

| horizon | split | model | rows | RMSE risk | MAE risk |
|---:|---|---|---:|---:|---:|
| 1 | `test` | `persistence` | 121,540 | 0.2558 | 0.1450 |
| 1 | `validation` | `persistence` | 163,110 | 0.2704 | 0.1569 |
| 2 | `test` | `persistence` | 115,691 | 0.2946 | 0.1743 |
| 2 | `validation` | `persistence` | 154,216 | 0.3076 | 0.1855 |
| 3 | `test` | `persistence` | 99,670 | 0.3172 | 0.1933 |
| 3 | `validation` | `persistence` | 136,038 | 0.3288 | 0.2032 |

## Outputs

- Selection CSV: `reports/baselines/baseline_selection.csv`
- Calibrated metrics CSV: `reports/baselines/baseline_calibrated_metrics.csv`
- Manifest: `reports/baselines/baseline_selection_manifest.json`
- Calibrators: `models/baselines/calibrators`

## Calibrator Artifacts

| model | horizon | calibration | path | sha256 |
|---|---:|---|---|---|
| `logistic_sgd` | 1 | `isotonic` | `models/baselines/calibrators/logistic_sgd_h1_isotonic.joblib` | `3583210df75f9ee85ee05e74c80e16ff41ddde38785bc4be84d17e455e88e88a` |
| `persistence` | 2 | `isotonic` | `models/baselines/calibrators/persistence_h2_isotonic.joblib` | `f6354b5ca68e342bd87307647ae15771dc4d4bcf5b94d1c4252426ffc5c25481` |
| `logistic_sgd` | 3 | `isotonic` | `models/baselines/calibrators/logistic_sgd_h3_isotonic.joblib` | `48eeff7f24125e381722d949bb458d2a46c4b6dd25c67b94bdcf255751529804` |
