# PIPE Neural ODE v1 Rollout Alert Calibration Report

Generated at UTC: `2026-06-15T21:03:36.803879+00:00`

## Scope

This report selects horizon-specific rollout alert thresholds on the calibration split and evaluates them on requested splits.
Bloom probabilities are fitted from rollout-derived IRC scores to observed `bloom_h`; test rows are evaluation-only.

## Configuration

- Backtest rows: `['reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_rows_matched_grud_validation.parquet', 'reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_rows_matched_grud_test.parquet']`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Bloom score column: `irc_mean`
- Selection objective: `fbeta`
- F-beta beta: `2.0`
- Minimum recall: `None`
- Minimum precision: `None`
- Calibrator directory: `models/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/rollout_calibrators`

## Selected Thresholds

| event | horizon | score | threshold | rows | positives | recall | precision | F-beta | constraint |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| `bloom_h` | 1 | `rollout_probability_bloom_calibrated` | 0.1429 | 3,049 | 410 | 0.8927 | 0.3540 | 0.6844 | `True` |
| `bloom_h` | 2 | `rollout_probability_bloom_calibrated` | 0.1429 | 3,158 | 441 | 0.7800 | 0.4150 | 0.6633 | `True` |
| `bloom_h` | 3 | `rollout_probability_bloom_calibrated` | 0.1373 | 3,184 | 457 | 0.8687 | 0.3319 | 0.6564 | `True` |
| `irc_alert` | 1 | `alert_probability_irc` | 0.2734 | 5,069 | 2,232 | 0.9449 | 0.7348 | 0.8938 | `True` |
| `irc_alert` | 2 | `alert_probability_irc` | 0.3438 | 5,069 | 2,267 | 0.9290 | 0.7265 | 0.8799 | `True` |
| `irc_alert` | 3 | `alert_probability_irc` | 0.3125 | 5,069 | 2,270 | 0.9454 | 0.6830 | 0.8779 | `True` |

## Evaluation Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | precision | F-beta |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.3221 | 0.6518 | 0.0932 | 0.8474 | 0.4797 | 0.7348 |
| `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.2839 | 0.6280 | 0.0958 | 0.8111 | 0.5236 | 0.7308 |
| `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.3942 | 0.6382 | 0.0952 | 0.9083 | 0.4277 | 0.7416 |
| `bloom_h` | `validation` | 1 | 3,049 | 0.1345 | 0.3391 | 0.5983 | 0.0735 | 0.8927 | 0.3540 | 0.6844 |
| `bloom_h` | `validation` | 2 | 3,158 | 0.1396 | 0.2625 | 0.5683 | 0.0802 | 0.7800 | 0.4150 | 0.6633 |
| `bloom_h` | `validation` | 3 | 3,184 | 0.1435 | 0.3756 | 0.5514 | 0.0849 | 0.8687 | 0.3319 | 0.6564 |
| `irc_alert` | `test` | 1 | 6,145 | 0.4148 | 0.5263 | 0.9331 | 0.0869 | 0.9447 | 0.7446 | 0.8965 |
| `irc_alert` | `test` | 2 | 6,145 | 0.4330 | 0.5426 | 0.9208 | 0.0999 | 0.9346 | 0.7460 | 0.8896 |
| `irc_alert` | `test` | 3 | 6,145 | 0.4448 | 0.6065 | 0.9238 | 0.1048 | 0.9583 | 0.7027 | 0.8933 |
| `irc_alert` | `validation` | 1 | 5,069 | 0.4403 | 0.5662 | 0.9094 | 0.1017 | 0.9449 | 0.7348 | 0.8938 |
| `irc_alert` | `validation` | 2 | 5,069 | 0.4472 | 0.5719 | 0.8911 | 0.1176 | 0.9290 | 0.7265 | 0.8799 |
| `irc_alert` | `validation` | 3 | 5,069 | 0.4478 | 0.6198 | 0.8789 | 0.1265 | 0.9454 | 0.6830 | 0.8779 |

## Interpretation Guardrails

- Thresholds are selected on validation/calibration rows only.
- Test metrics must be read as held-out evaluation, not threshold tuning evidence.
- If a horizon has insufficient bloom positives, its calibrator is omitted.
- These outputs refine alert decisions; they do not retrain PIPE Neural ODE v1.

## Outputs

- Thresholds: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_calibration_thresholds.csv`
- Metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_calibration_metrics.csv`
- Calibrated rows: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_calibrated_backtest_rows.parquet`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_calibration_manifest.json`

## Calibrators

- `models/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/rollout_calibrators/rollout_bloom_h1_irc_mean_isotonic.joblib`
- `models/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/rollout_calibrators/rollout_bloom_h2_irc_mean_isotonic.joblib`
- `models/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/rollout_calibrators/rollout_bloom_h3_irc_mean_isotonic.joblib`