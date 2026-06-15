# PIPE Neural ODE Rollout Alert Calibration Report

Generated at UTC: `2026-06-15T19:54:07.957233+00:00`

## Scope

This report selects horizon-specific rollout alert thresholds on the calibration split and evaluates them on requested splits.
Bloom probabilities are fitted from rollout-derived IRC scores to observed `bloom_h`; test rows are evaluation-only.

## Configuration

- Backtest rows: `['reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_rows_matched_grud_validation.parquet', 'reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_rows_matched_grud_test.parquet']`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Bloom score column: `irc_mean`
- Selection objective: `fbeta`
- F-beta beta: `2.0`
- Minimum recall: `None`
- Minimum precision: `None`
- Calibrator directory: `models/pipe_neural_ode/adaptive_wqp_focused/rollout_calibrators`

## Selected Thresholds

| event | horizon | score | threshold | rows | positives | recall | precision | F-beta | constraint |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| `bloom_h` | 1 | `rollout_probability_bloom_calibrated` | 0.1409 | 3,049 | 410 | 0.8610 | 0.3555 | 0.6703 | `True` |
| `bloom_h` | 2 | `rollout_probability_bloom_calibrated` | 0.1429 | 3,158 | 441 | 0.7800 | 0.3652 | 0.6356 | `True` |
| `bloom_h` | 3 | `rollout_probability_bloom_calibrated` | 0.1304 | 3,184 | 457 | 0.7987 | 0.3242 | 0.6178 | `True` |
| `irc_alert` | 1 | `alert_probability_irc` | 0.1797 | 5,069 | 2,232 | 0.9391 | 0.6684 | 0.8687 | `True` |
| `irc_alert` | 2 | `alert_probability_irc` | 0.1953 | 5,069 | 2,267 | 0.9352 | 0.6002 | 0.8413 | `True` |
| `irc_alert` | 3 | `alert_probability_irc` | 0.1719 | 5,069 | 2,270 | 0.9727 | 0.5320 | 0.8345 | `True` |

## Evaluation Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | precision | F-beta |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.3109 | 0.5979 | 0.1004 | 0.7981 | 0.4680 | 0.6994 |
| `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.3036 | 0.5538 | 0.1080 | 0.7822 | 0.4720 | 0.6913 |
| `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.3797 | 0.5517 | 0.1102 | 0.8505 | 0.4158 | 0.7034 |
| `bloom_h` | `validation` | 1 | 3,049 | 0.1345 | 0.3257 | 0.5281 | 0.0802 | 0.8610 | 0.3555 | 0.6703 |
| `bloom_h` | `validation` | 2 | 3,158 | 0.1396 | 0.2983 | 0.4744 | 0.0904 | 0.7800 | 0.3652 | 0.6356 |
| `bloom_h` | `validation` | 3 | 3,184 | 0.1435 | 0.3536 | 0.4314 | 0.0980 | 0.7987 | 0.3242 | 0.6178 |
| `irc_alert` | `test` | 1 | 6,145 | 0.4148 | 0.5803 | 0.8952 | 0.1046 | 0.9372 | 0.6699 | 0.8680 |
| `irc_alert` | `test` | 2 | 6,145 | 0.4330 | 0.6680 | 0.8549 | 0.1322 | 0.9402 | 0.6095 | 0.8482 |
| `irc_alert` | `test` | 3 | 6,145 | 0.4448 | 0.7867 | 0.8529 | 0.1424 | 0.9759 | 0.5517 | 0.8458 |
| `irc_alert` | `validation` | 1 | 5,069 | 0.4403 | 0.6187 | 0.8632 | 0.1191 | 0.9391 | 0.6684 | 0.8687 |
| `irc_alert` | `validation` | 2 | 5,069 | 0.4472 | 0.6968 | 0.8214 | 0.1509 | 0.9352 | 0.6002 | 0.8413 |
| `irc_alert` | `validation` | 3 | 5,069 | 0.4478 | 0.8187 | 0.7907 | 0.1686 | 0.9727 | 0.5320 | 0.8345 |

## Interpretation Guardrails

- Thresholds are selected on validation/calibration rows only.
- Test metrics must be read as held-out evaluation, not threshold tuning evidence.
- If a horizon has insufficient bloom positives, its calibrator is omitted.
- These outputs refine alert decisions; they do not retrain PIPE Neural ODE.

## Outputs

- Thresholds: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_calibration_thresholds.csv`
- Metrics: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_calibration_metrics.csv`
- Calibrated rows: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_calibrated_backtest_rows.parquet`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_calibration_manifest.json`

## Calibrators

- `models/pipe_neural_ode/adaptive_wqp_focused/rollout_calibrators/rollout_bloom_h1_irc_mean_isotonic.joblib`
- `models/pipe_neural_ode/adaptive_wqp_focused/rollout_calibrators/rollout_bloom_h2_irc_mean_isotonic.joblib`
- `models/pipe_neural_ode/adaptive_wqp_focused/rollout_calibrators/rollout_bloom_h3_irc_mean_isotonic.joblib`