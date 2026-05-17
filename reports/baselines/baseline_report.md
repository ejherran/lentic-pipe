# Baseline Report

Generated at UTC: `2026-05-16T20:54:55.240631+00:00`
Splits: `data/splits/monthly_model_splits_v0.parquet`
Panel: `data/panel/panel_monthly_v0.parquet`
Rows evaluated in metrics table: `27,665,862`
Models requested: `constant, source_month, site_month, persistence, logistic_sgd, ridge_sgd`
Threshold for confusion matrices: `0.5`

## Scope

Baselines are trained only on the train split for each horizon and evaluated on train, validation, and test.
Feature columns come from the origin month panel only; target and future columns are not used as features.

## Best Validation/Test Rows By PR-AUC

| horizon | split | model | task | rows | PR-AUC | ROC-AUC | Brier | recall | macro-F1 | RMSE risk | MAE risk |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `test` | `logistic_sgd` | `classification` | 121,540 | 0.7030 | 0.9237 | 0.0856 | 0.6655 | 0.8102 | NA | NA |
| 1 | `test` | `persistence` | `classification_and_risk` | 121,540 | 0.6175 | 0.9078 | 0.1416 | 0.8731 | 0.7176 | 0.2558 | 0.1450 |
| 1 | `test` | `site_month` | `classification_and_risk` | 121,540 | 0.4000 | 0.7627 | 0.1068 | 0.0187 | 0.4819 | 0.3603 | 0.3230 |
| 1 | `test` | `source_month` | `classification_and_risk` | 121,540 | 0.1719 | 0.5870 | 0.1183 | 0.0000 | 0.4630 | 0.3846 | 0.3470 |
| 1 | `test` | `constant` | `classification_and_risk` | 121,540 | 0.1377 | 0.5000 | 0.1192 | 0.0000 | 0.4630 | 0.3883 | 0.3511 |
| 1 | `test` | `ridge_sgd` | `risk` | 121,540 | 0.1377 | 0.5000 | 0.8623 | 0.9999 | 0.1211 | 0.7770 | 0.6737 |
| 1 | `validation` | `logistic_sgd` | `classification` | 163,110 | 0.6586 | 0.9134 | 0.0876 | 0.6348 | 0.7921 | NA | NA |
| 1 | `validation` | `persistence` | `classification_and_risk` | 163,110 | 0.5695 | 0.8988 | 0.1441 | 0.8540 | 0.7029 | 0.2704 | 0.1569 |
| 1 | `validation` | `site_month` | `classification_and_risk` | 163,110 | 0.4159 | 0.7859 | 0.0982 | 0.0222 | 0.4887 | 0.3510 | 0.3138 |
| 1 | `validation` | `source_month` | `classification_and_risk` | 163,110 | 0.1564 | 0.5850 | 0.1102 | 0.0000 | 0.4665 | 0.3781 | 0.3395 |
| 1 | `validation` | `constant` | `classification_and_risk` | 163,110 | 0.1257 | 0.5000 | 0.1110 | 0.0000 | 0.4665 | 0.3822 | 0.3452 |
| 1 | `validation` | `ridge_sgd` | `risk` | 163,110 | 0.1257 | 0.5000 | 0.8742 | 0.9998 | 0.1118 | 0.7840 | 0.6859 |
| 2 | `test` | `persistence` | `classification_and_risk` | 115,691 | 0.5493 | 0.8730 | 0.1519 | 0.8082 | 0.7047 | 0.2946 | 0.1743 |
| 2 | `test` | `logistic_sgd` | `classification` | 115,691 | 0.4397 | 0.8649 | 0.3021 | 0.9155 | 0.6241 | NA | NA |
| 2 | `test` | `site_month` | `classification_and_risk` | 115,691 | 0.3991 | 0.7513 | 0.1120 | 0.0157 | 0.4769 | 0.3649 | 0.3274 |
| 2 | `test` | `source_month` | `classification_and_risk` | 115,691 | 0.1772 | 0.5869 | 0.1231 | 0.0000 | 0.4609 | 0.3872 | 0.3496 |
| 2 | `test` | `constant` | `classification_and_risk` | 115,691 | 0.1449 | 0.5000 | 0.1241 | 0.0000 | 0.4609 | 0.3915 | 0.3538 |
| 2 | `test` | `ridge_sgd` | `risk` | 115,691 | 0.1442 | 0.4971 | 0.8527 | 0.9897 | 0.1304 | 0.7702 | 0.6636 |
| 2 | `validation` | `persistence` | `classification_and_risk` | 154,216 | 0.4885 | 0.8587 | 0.1520 | 0.7774 | 0.6868 | 0.3076 | 0.1855 |
| 2 | `validation` | `site_month` | `classification_and_risk` | 154,216 | 0.4136 | 0.7811 | 0.0998 | 0.0202 | 0.4861 | 0.3534 | 0.3167 |
| 2 | `validation` | `logistic_sgd` | `classification` | 154,216 | 0.3983 | 0.8568 | 0.3087 | 0.8997 | 0.6031 | NA | NA |
| 2 | `validation` | `source_month` | `classification_and_risk` | 154,216 | 0.1593 | 0.5872 | 0.1115 | 0.0000 | 0.4659 | 0.3788 | 0.3404 |
| 2 | `validation` | `constant` | `classification_and_risk` | 154,216 | 0.1277 | 0.5000 | 0.1124 | 0.0000 | 0.4659 | 0.3836 | 0.3470 |
| 2 | `validation` | `ridge_sgd` | `risk` | 154,216 | 0.1274 | 0.4985 | 0.8705 | 0.9942 | 0.1158 | 0.7829 | 0.6836 |
| 3 | `test` | `logistic_sgd` | `classification` | 99,670 | 0.6155 | 0.8818 | 0.1166 | 0.2710 | 0.6673 | NA | NA |
| 3 | `test` | `persistence` | `classification_and_risk` | 99,670 | 0.5131 | 0.8538 | 0.1589 | 0.7778 | 0.6942 | 0.3172 | 0.1933 |
| 3 | `test` | `site_month` | `classification_and_risk` | 99,670 | 0.3900 | 0.7418 | 0.1145 | 0.0122 | 0.4727 | 0.3697 | 0.3327 |
| 3 | `test` | `source_month` | `classification_and_risk` | 99,670 | 0.1842 | 0.5946 | 0.1243 | 0.0000 | 0.4604 | 0.3881 | 0.3509 |
| 3 | `test` | `ridge_sgd` | `risk` | 99,670 | 0.1469 | 0.5001 | 0.8526 | 0.9997 | 0.1287 | 0.7659 | 0.6575 |
| 3 | `test` | `constant` | `classification_and_risk` | 99,670 | 0.1469 | 0.5000 | 0.1255 | 0.0000 | 0.4604 | 0.3931 | 0.3556 |
| 3 | `validation` | `logistic_sgd` | `classification` | 136,038 | 0.5410 | 0.8668 | 0.1079 | 0.2208 | 0.6393 | NA | NA |
| 3 | `validation` | `persistence` | `classification_and_risk` | 136,038 | 0.4496 | 0.8374 | 0.1572 | 0.7394 | 0.6761 | 0.3288 | 0.2032 |
| 3 | `validation` | `site_month` | `classification_and_risk` | 136,038 | 0.4139 | 0.7780 | 0.1006 | 0.0168 | 0.4828 | 0.3565 | 0.3205 |
| 3 | `validation` | `source_month` | `classification_and_risk` | 136,038 | 0.1640 | 0.5952 | 0.1114 | 0.0000 | 0.4659 | 0.3787 | 0.3404 |
| 3 | `validation` | `ridge_sgd` | `risk` | 136,038 | 0.1278 | 0.5003 | 0.8712 | 0.9992 | 0.1147 | 0.7813 | 0.6814 |
| 3 | `validation` | `constant` | `classification_and_risk` | 136,038 | 0.1277 | 0.5000 | 0.1124 | 0.0000 | 0.4659 | 0.3844 | 0.3482 |

## Output Files

- Metrics: `reports/baselines/baseline_metrics.csv`
- Manifest: `reports/baselines/baseline_manifest.json`
- Confusion matrices: `reports/baselines/confusion_matrices`
- Calibration tables: `reports/baselines/calibration`
- Model artifacts: `models/baselines`

## Model Artifacts

| model | horizon | path |
|---|---:|---|
| `source_month` | 1 | `models/baselines/source_month_h1.joblib` |
| `site_month` | 1 | `models/baselines/site_month_h1.joblib` |
| `logistic_sgd` | 1 | `models/baselines/logistic_sgd_h1.joblib` |
| `ridge_sgd` | 1 | `models/baselines/ridge_sgd_h1.joblib` |
| `source_month` | 2 | `models/baselines/source_month_h2.joblib` |
| `site_month` | 2 | `models/baselines/site_month_h2.joblib` |
| `logistic_sgd` | 2 | `models/baselines/logistic_sgd_h2.joblib` |
| `ridge_sgd` | 2 | `models/baselines/ridge_sgd_h2.joblib` |
| `source_month` | 3 | `models/baselines/source_month_h3.joblib` |
| `site_month` | 3 | `models/baselines/site_month_h3.joblib` |
| `logistic_sgd` | 3 | `models/baselines/logistic_sgd_h3.joblib` |
| `ridge_sgd` | 3 | `models/baselines/ridge_sgd_h3.joblib` |
