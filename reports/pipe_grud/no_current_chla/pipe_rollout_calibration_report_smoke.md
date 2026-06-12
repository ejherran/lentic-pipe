# PIPE/GRU-D Rollout Alert Calibration Report

Generated at UTC: `2026-06-12T18:50:03.898034+00:00`

## Scope

This report selects horizon-specific rollout alert thresholds on the calibration split and evaluates them on requested splits.
Bloom probabilities are fitted from rollout-derived IRC scores to observed `bloom_h`; test rows are evaluation-only.

## Configuration

- Backtest rows: `['reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_validation_smoke.parquet', 'reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_test_smoke.parquet']`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Bloom score column: `irc_mean`
- Selection objective: `fbeta`
- F-beta beta: `2.0`
- Minimum recall: `None`
- Minimum precision: `None`
- Calibrator directory: `models/pipe_grud/no_current_chla/rollout_calibrators_smoke`

## Selected Thresholds

| event | horizon | score | threshold | rows | positives | recall | precision | F-beta | constraint |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| `bloom_h` | 1 | `rollout_probability_bloom_calibrated` | 0.0941 | 445 | 57 | 0.8947 | 0.1382 | 0.4271 | `True` |
| `bloom_h` | 2 | `rollout_probability_bloom_calibrated` | 0.1355 | 451 | 66 | 0.9848 | 0.1548 | 0.4751 | `True` |
| `bloom_h` | 3 | `rollout_probability_bloom_calibrated` | 0.1770 | 460 | 68 | 0.8235 | 0.1911 | 0.4956 | `True` |
| `irc_alert` | 1 | `alert_probability_irc` | 0.0000 | 512 | 184 | 1.0000 | 0.3594 | 0.7372 | `True` |
| `irc_alert` | 2 | `alert_probability_irc` | 0.0000 | 512 | 179 | 1.0000 | 0.3496 | 0.7288 | `True` |
| `irc_alert` | 3 | `alert_probability_irc` | 0.0000 | 512 | 180 | 1.0000 | 0.3516 | 0.7305 | `True` |

## Evaluation Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | precision | F-beta |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.7570 | 0.2052 | 0.1111 | 0.8500 | 0.1461 | 0.4329 |
| `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.8957 | 0.2539 | 0.1124 | 0.9355 | 0.1408 | 0.4394 |
| `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.6745 | 0.1911 | 0.1130 | 0.8226 | 0.1619 | 0.4529 |
| `bloom_h` | `validation` | 1 | 445 | 0.1281 | 0.8292 | 0.1582 | 0.1103 | 0.8947 | 0.1382 | 0.4271 |
| `bloom_h` | `validation` | 2 | 451 | 0.1463 | 0.9313 | 0.1741 | 0.1232 | 0.9848 | 0.1548 | 0.4751 |
| `bloom_h` | `validation` | 3 | 460 | 0.1478 | 0.6370 | 0.1991 | 0.1219 | 0.8235 | 0.1911 | 0.4956 |
| `irc_alert` | `test` | 1 | 512 | 0.3379 | 1.0000 | 0.4329 | 0.2930 | 1.0000 | 0.3379 | 0.7184 |
| `irc_alert` | `test` | 2 | 512 | 0.3477 | 1.0000 | 0.4199 | 0.3086 | 1.0000 | 0.3477 | 0.7271 |
| `irc_alert` | `test` | 3 | 512 | 0.3535 | 1.0000 | 0.4228 | 0.3125 | 1.0000 | 0.3535 | 0.7322 |
| `irc_alert` | `validation` | 1 | 512 | 0.3594 | 1.0000 | 0.4708 | 0.2910 | 1.0000 | 0.3594 | 0.7372 |
| `irc_alert` | `validation` | 2 | 512 | 0.3496 | 1.0000 | 0.4109 | 0.3164 | 1.0000 | 0.3496 | 0.7288 |
| `irc_alert` | `validation` | 3 | 512 | 0.3516 | 1.0000 | 0.3813 | 0.3379 | 1.0000 | 0.3516 | 0.7305 |

## Interpretation Guardrails

- Thresholds are selected on validation/calibration rows only.
- Test metrics must be read as held-out evaluation, not threshold tuning evidence.
- If a horizon has insufficient bloom positives, its calibrator is omitted.
- These outputs refine alert decisions; they do not retrain PIPE/GRU-D.

## Outputs

- Thresholds: `reports/pipe_grud/no_current_chla/pipe_rollout_calibration_thresholds_smoke.csv`
- Metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_calibration_metrics_smoke.csv`
- Calibrated rows: `reports/pipe_grud/no_current_chla/pipe_rollout_calibrated_backtest_rows_smoke.parquet`
- Manifest: `reports/pipe_grud/no_current_chla/pipe_rollout_calibration_manifest_smoke.json`

## Calibrators

- `models/pipe_grud/no_current_chla/rollout_calibrators_smoke/rollout_bloom_h1_irc_mean_isotonic.joblib`
- `models/pipe_grud/no_current_chla/rollout_calibrators_smoke/rollout_bloom_h2_irc_mean_isotonic.joblib`
- `models/pipe_grud/no_current_chla/rollout_calibrators_smoke/rollout_bloom_h3_irc_mean_isotonic.joblib`