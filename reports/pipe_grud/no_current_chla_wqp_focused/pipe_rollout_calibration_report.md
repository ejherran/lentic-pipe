# PIPE/GRU-D Rollout Alert Calibration Report

Generated at UTC: `2026-06-12T22:55:52.775871+00:00`

## Scope

This report selects horizon-specific rollout alert thresholds on the calibration split and evaluates them on requested splits.
Bloom probabilities are fitted from rollout-derived IRC scores to observed `bloom_h`; test rows are evaluation-only.

## Configuration

- Backtest rows: `['reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_rows_validation.parquet', 'reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_rows_test.parquet']`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Bloom score column: `irc_mean`
- Selection objective: `fbeta`
- F-beta beta: `2.0`
- Minimum recall: `None`
- Minimum precision: `None`
- Calibrator directory: `models/pipe_grud/no_current_chla_wqp_focused/rollout_calibrators`

## Selected Thresholds

| event | horizon | score | threshold | rows | positives | recall | precision | F-beta | constraint |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| `bloom_h` | 1 | `rollout_probability_bloom_calibrated` | 0.1333 | 3,049 | 410 | 0.7537 | 0.2628 | 0.5487 | `True` |
| `bloom_h` | 2 | `rollout_probability_bloom_calibrated` | 0.1383 | 3,158 | 441 | 0.6735 | 0.3341 | 0.5597 | `True` |
| `bloom_h` | 3 | `rollout_probability_bloom_calibrated` | 0.1302 | 3,184 | 457 | 0.7462 | 0.2617 | 0.5446 | `True` |
| `irc_alert` | 1 | `alert_probability_irc` | 0.1562 | 5,069 | 2,486 | 0.9807 | 0.5932 | 0.8674 | `True` |
| `irc_alert` | 2 | `alert_probability_irc` | 0.0547 | 5,069 | 2,489 | 0.9940 | 0.5357 | 0.8488 | `True` |
| `irc_alert` | 3 | `alert_probability_irc` | 0.0625 | 5,069 | 2,480 | 0.9891 | 0.5389 | 0.8475 | `True` |

## Evaluation Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | precision | F-beta |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.3101 | 0.4277 | 0.1288 | 0.6702 | 0.3941 | 0.5878 |
| `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.2851 | 0.3931 | 0.1349 | 0.6280 | 0.4036 | 0.5652 |
| `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.3818 | 0.3713 | 0.1371 | 0.7395 | 0.3596 | 0.6105 |
| `bloom_h` | `validation` | 1 | 3,049 | 0.1345 | 0.3857 | 0.3712 | 0.0979 | 0.7537 | 0.2628 | 0.5487 |
| `bloom_h` | `validation` | 2 | 3,158 | 0.1396 | 0.2815 | 0.3966 | 0.0987 | 0.6735 | 0.3341 | 0.5597 |
| `bloom_h` | `validation` | 3 | 3,184 | 0.1435 | 0.4092 | 0.3555 | 0.1054 | 0.7462 | 0.2617 | 0.5446 |
| `irc_alert` | `test` | 1 | 6,145 | 0.4544 | 0.7707 | 0.7963 | 0.1684 | 0.9620 | 0.5671 | 0.8444 |
| `irc_alert` | `test` | 2 | 6,145 | 0.4692 | 0.8923 | 0.7456 | 0.1754 | 0.9941 | 0.5227 | 0.8422 |
| `irc_alert` | `test` | 3 | 6,145 | 0.4781 | 0.8788 | 0.7276 | 0.1857 | 0.9894 | 0.5383 | 0.8474 |
| `irc_alert` | `validation` | 1 | 5,069 | 0.4904 | 0.8108 | 0.8003 | 0.1669 | 0.9807 | 0.5932 | 0.8674 |
| `irc_alert` | `validation` | 2 | 5,069 | 0.4910 | 0.9110 | 0.7585 | 0.1908 | 0.9940 | 0.5357 | 0.8488 |
| `irc_alert` | `validation` | 3 | 5,069 | 0.4892 | 0.8980 | 0.7272 | 0.2057 | 0.9891 | 0.5389 | 0.8475 |

## Interpretation Guardrails

- Thresholds are selected on validation/calibration rows only.
- Test metrics must be read as held-out evaluation, not threshold tuning evidence.
- If a horizon has insufficient bloom positives, its calibrator is omitted.
- These outputs refine alert decisions; they do not retrain PIPE/GRU-D.

## Outputs

- Thresholds: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_calibration_thresholds.csv`
- Metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_calibration_metrics.csv`
- Calibrated rows: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_calibrated_backtest_rows.parquet`
- Manifest: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_calibration_manifest.json`

## Calibrators

- `models/pipe_grud/no_current_chla_wqp_focused/rollout_calibrators/rollout_bloom_h1_irc_mean_isotonic.joblib`
- `models/pipe_grud/no_current_chla_wqp_focused/rollout_calibrators/rollout_bloom_h2_irc_mean_isotonic.joblib`
- `models/pipe_grud/no_current_chla_wqp_focused/rollout_calibrators/rollout_bloom_h3_irc_mean_isotonic.joblib`