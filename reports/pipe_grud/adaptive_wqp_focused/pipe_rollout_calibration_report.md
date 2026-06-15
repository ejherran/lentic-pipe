# PIPE/GRU-D Rollout Alert Calibration Report

Generated at UTC: `2026-06-15T17:03:27.097813+00:00`

## Scope

This report selects horizon-specific rollout alert thresholds on the calibration split and evaluates them on requested splits.
Bloom probabilities are fitted from rollout-derived IRC scores to observed `bloom_h`; test rows are evaluation-only.

## Configuration

- Backtest rows: `['reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_validation.parquet', 'reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_test.parquet']`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Bloom score column: `irc_mean`
- Selection objective: `fbeta`
- F-beta beta: `2.0`
- Minimum recall: `None`
- Minimum precision: `None`
- Calibrator directory: `models/pipe_grud/adaptive_wqp_focused/rollout_calibrators`

## Selected Thresholds

| event | horizon | score | threshold | rows | positives | recall | precision | F-beta | constraint |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| `bloom_h` | 1 | `rollout_probability_bloom_calibrated` | 0.1571 | 3,049 | 410 | 0.8098 | 0.4079 | 0.6764 | `True` |
| `bloom_h` | 2 | `rollout_probability_bloom_calibrated` | 0.1448 | 3,158 | 441 | 0.8617 | 0.3299 | 0.6516 | `True` |
| `bloom_h` | 3 | `rollout_probability_bloom_calibrated` | 0.1406 | 3,184 | 457 | 0.8665 | 0.3281 | 0.6524 | `True` |
| `irc_alert` | 1 | `alert_probability_irc` | 0.1094 | 5,069 | 2,232 | 0.9503 | 0.6284 | 0.8620 | `True` |
| `irc_alert` | 2 | `alert_probability_irc` | 0.1250 | 5,069 | 2,267 | 0.9629 | 0.5625 | 0.8429 | `True` |
| `irc_alert` | 3 | `alert_probability_irc` | 0.1641 | 5,069 | 2,270 | 0.9678 | 0.5452 | 0.8379 | `True` |

## Evaluation Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | precision | F-beta |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.2726 | 0.6405 | 0.0946 | 0.7758 | 0.5188 | 0.7059 |
| `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.3671 | 0.5879 | 0.1016 | 0.8714 | 0.4349 | 0.7257 |
| `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.3868 | 0.5593 | 0.1056 | 0.8777 | 0.4212 | 0.7213 |
| `bloom_h` | `validation` | 1 | 3,049 | 0.1345 | 0.2670 | 0.5735 | 0.0749 | 0.8098 | 0.4079 | 0.6764 |
| `bloom_h` | `validation` | 2 | 3,158 | 0.1396 | 0.3648 | 0.5466 | 0.0818 | 0.8617 | 0.3299 | 0.6516 |
| `bloom_h` | `validation` | 3 | 3,184 | 0.1435 | 0.3791 | 0.5053 | 0.0882 | 0.8665 | 0.3281 | 0.6524 |
| `irc_alert` | `test` | 1 | 6,145 | 0.4148 | 0.6161 | 0.9013 | 0.1059 | 0.9521 | 0.6410 | 0.8679 |
| `irc_alert` | `test` | 2 | 6,145 | 0.4330 | 0.7268 | 0.8630 | 0.1329 | 0.9688 | 0.5773 | 0.8531 |
| `irc_alert` | `test` | 3 | 6,145 | 0.4448 | 0.7557 | 0.8547 | 0.1424 | 0.9755 | 0.5741 | 0.8558 |
| `irc_alert` | `validation` | 1 | 5,069 | 0.4403 | 0.6658 | 0.8703 | 0.1216 | 0.9503 | 0.6284 | 0.8620 |
| `irc_alert` | `validation` | 2 | 5,069 | 0.4472 | 0.7656 | 0.8217 | 0.1507 | 0.9629 | 0.5625 | 0.8429 |
| `irc_alert` | `validation` | 3 | 5,069 | 0.4478 | 0.7950 | 0.7910 | 0.1682 | 0.9678 | 0.5452 | 0.8379 |

## Interpretation Guardrails

- Thresholds are selected on validation/calibration rows only.
- Test metrics must be read as held-out evaluation, not threshold tuning evidence.
- If a horizon has insufficient bloom positives, its calibrator is omitted.
- These outputs refine alert decisions; they do not retrain PIPE/GRU-D.

## Outputs

- Thresholds: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibration_thresholds.csv`
- Metrics: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibration_metrics.csv`
- Calibrated rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibrated_backtest_rows.parquet`
- Manifest: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibration_manifest.json`

## Calibrators

- `models/pipe_grud/adaptive_wqp_focused/rollout_calibrators/rollout_bloom_h1_irc_mean_isotonic.joblib`
- `models/pipe_grud/adaptive_wqp_focused/rollout_calibrators/rollout_bloom_h2_irc_mean_isotonic.joblib`
- `models/pipe_grud/adaptive_wqp_focused/rollout_calibrators/rollout_bloom_h3_irc_mean_isotonic.joblib`