# PIPE/GRU-D Rollout Alert Calibration Report

Generated at UTC: `2026-06-12T19:11:36.627784+00:00`

## Scope

This report selects horizon-specific rollout alert thresholds on the calibration split and evaluates them on requested splits.
Bloom probabilities are fitted from rollout-derived IRC scores to observed `bloom_h`; test rows are evaluation-only.

## Configuration

- Backtest rows: `['reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_validation.parquet', 'reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_test.parquet']`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Bloom score column: `irc_mean`
- Selection objective: `fbeta`
- F-beta beta: `2.0`
- Minimum recall: `0.5`
- Minimum precision: `None`
- Calibrator directory: `models/pipe_grud/no_current_chla/rollout_calibrators`

## Selected Thresholds

| event | horizon | score | threshold | rows | positives | recall | precision | F-beta | constraint |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| `bloom_h` | 1 | `rollout_probability_bloom_calibrated` | 0.0909 | 14,212 | 1,841 | 0.9120 | 0.1426 | 0.4386 | `True` |
| `bloom_h` | 2 | `rollout_probability_bloom_calibrated` | 0.0897 | 14,325 | 1,892 | 0.9223 | 0.1431 | 0.4416 | `True` |
| `bloom_h` | 3 | `rollout_probability_bloom_calibrated` | 0.0902 | 14,352 | 1,898 | 0.9531 | 0.1393 | 0.4395 | `True` |
| `irc_alert` | 1 | `alert_probability_irc` | 0.1875 | 16,260 | 5,860 | 0.9860 | 0.3792 | 0.7469 | `True` |
| `irc_alert` | 2 | `alert_probability_irc` | 0.1016 | 16,260 | 5,873 | 0.9980 | 0.3656 | 0.7415 | `True` |
| `irc_alert` | 3 | `alert_probability_irc` | 0.0547 | 16,260 | 5,817 | 0.9995 | 0.3596 | 0.7371 | `True` |

## Evaluation Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | precision | F-beta |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `test` | 1 | 11,852 | 0.1243 | 0.7616 | 0.2913 | 0.1008 | 0.8805 | 0.1437 | 0.4347 |
| `bloom_h` | `test` | 2 | 11,891 | 0.1298 | 0.8186 | 0.2672 | 0.1049 | 0.9469 | 0.1502 | 0.4595 |
| `bloom_h` | `test` | 3 | 11,939 | 0.1335 | 0.8982 | 0.2561 | 0.1093 | 0.9787 | 0.1455 | 0.4561 |
| `bloom_h` | `validation` | 1 | 14,212 | 0.1295 | 0.8285 | 0.1892 | 0.1097 | 0.9120 | 0.1426 | 0.4386 |
| `bloom_h` | `validation` | 2 | 14,325 | 0.1321 | 0.8510 | 0.1991 | 0.1109 | 0.9223 | 0.1431 | 0.4416 |
| `bloom_h` | `validation` | 3 | 14,352 | 0.1322 | 0.9051 | 0.1972 | 0.1111 | 0.9531 | 0.1393 | 0.4395 |
| `irc_alert` | `test` | 1 | 13,327 | 0.3335 | 0.8956 | 0.6532 | 0.1805 | 0.9620 | 0.3582 | 0.7194 |
| `irc_alert` | `test` | 2 | 13,327 | 0.3464 | 0.9753 | 0.6346 | 0.1852 | 0.9976 | 0.3543 | 0.7318 |
| `irc_alert` | `test` | 3 | 13,327 | 0.3564 | 0.9923 | 0.6147 | 0.1967 | 1.0000 | 0.3592 | 0.7370 |
| `irc_alert` | `validation` | 1 | 16,260 | 0.3604 | 0.9372 | 0.6027 | 0.1981 | 0.9860 | 0.3792 | 0.7469 |
| `irc_alert` | `validation` | 2 | 16,260 | 0.3612 | 0.9859 | 0.5790 | 0.2085 | 0.9980 | 0.3656 | 0.7415 |
| `irc_alert` | `validation` | 3 | 16,260 | 0.3577 | 0.9945 | 0.5642 | 0.2179 | 0.9995 | 0.3596 | 0.7371 |

## Interpretation Guardrails

- Thresholds are selected on validation/calibration rows only.
- Test metrics must be read as held-out evaluation, not threshold tuning evidence.
- If a horizon has insufficient bloom positives, its calibrator is omitted.
- These outputs refine alert decisions; they do not retrain PIPE/GRU-D.

## Outputs

- Thresholds: `reports/pipe_grud/no_current_chla/pipe_rollout_calibration_thresholds.csv`
- Metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_calibration_metrics.csv`
- Calibrated rows: `reports/pipe_grud/no_current_chla/pipe_rollout_calibrated_backtest_rows.parquet`
- Manifest: `reports/pipe_grud/no_current_chla/pipe_rollout_calibration_manifest.json`

## Calibrators

- `models/pipe_grud/no_current_chla/rollout_calibrators/rollout_bloom_h1_irc_mean_isotonic.joblib`
- `models/pipe_grud/no_current_chla/rollout_calibrators/rollout_bloom_h2_irc_mean_isotonic.joblib`
- `models/pipe_grud/no_current_chla/rollout_calibrators/rollout_bloom_h3_irc_mean_isotonic.joblib`