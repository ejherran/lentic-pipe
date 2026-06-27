# PIPE Neural ODE v2 direct Rollout Alert Calibration Report

Generated at UTC: `2026-06-27T15:34:19.723492+00:00`

## Scope

This report selects horizon-specific rollout alert thresholds on the calibration split and evaluates them on requested splits.
Bloom probabilities are fitted from rollout-derived IRC scores to observed `bloom_h`; test rows are evaluation-only.

## Configuration

- Backtest rows: `['reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_backtest_rows_matched_grud_validation.parquet', 'reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_backtest_rows_matched_grud_test.parquet']`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Bloom score column: `irc_mean`
- Selection objective: `fbeta`
- F-beta beta: `2.0`
- Minimum recall: `None`
- Minimum precision: `None`
- Calibrator directory: `models/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/direct_alert_calibrators`

## Selected Thresholds

| event | horizon | score | threshold | rows | positives | recall | precision | F-beta | constraint |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| `bloom_h` | 1 | `rollout_probability_bloom_calibrated` | 0.1406 | 3,049 | 410 | 0.8561 | 0.3762 | 0.6821 | `True` |
| `bloom_h` | 2 | `rollout_probability_bloom_calibrated` | 0.1414 | 3,158 | 441 | 0.8367 | 0.3429 | 0.6496 | `True` |
| `bloom_h` | 3 | `rollout_probability_bloom_calibrated` | 0.1260 | 3,184 | 457 | 0.8140 | 0.3292 | 0.6288 | `True` |
| `irc_alert` | 1 | `alert_probability_irc` | 0.2422 | 5,069 | 2,232 | 0.9556 | 0.7086 | 0.8934 | `True` |
| `irc_alert` | 2 | `alert_probability_irc` | 0.1875 | 5,069 | 2,267 | 0.9629 | 0.6662 | 0.8842 | `True` |
| `irc_alert` | 3 | `alert_probability_irc` | 0.2344 | 5,069 | 2,270 | 0.9441 | 0.6844 | 0.8775 | `True` |

## Evaluation Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | precision | F-beta |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.2992 | 0.6599 | 0.0927 | 0.8369 | 0.5100 | 0.7418 |
| `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.3539 | 0.6409 | 0.0935 | 0.8783 | 0.4547 | 0.7404 |
| `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.3746 | 0.6254 | 0.0952 | 0.8822 | 0.4371 | 0.7330 |
| `bloom_h` | `validation` | 1 | 3,049 | 0.1345 | 0.3060 | 0.6077 | 0.0750 | 0.8561 | 0.3762 | 0.6821 |
| `bloom_h` | `validation` | 2 | 3,158 | 0.1396 | 0.3407 | 0.5790 | 0.0793 | 0.8367 | 0.3429 | 0.6496 |
| `bloom_h` | `validation` | 3 | 3,184 | 0.1435 | 0.3549 | 0.5484 | 0.0860 | 0.8140 | 0.3292 | 0.6288 |
| `irc_alert` | `test` | 1 | 6,145 | 0.4148 | 0.5456 | 0.9298 | 0.0896 | 0.9478 | 0.7205 | 0.8916 |
| `irc_alert` | `test` | 2 | 6,145 | 0.4330 | 0.6099 | 0.9218 | 0.0978 | 0.9590 | 0.6809 | 0.8866 |
| `irc_alert` | `test` | 3 | 6,145 | 0.4448 | 0.6174 | 0.9292 | 0.0976 | 0.9572 | 0.6895 | 0.8882 |
| `irc_alert` | `validation` | 1 | 5,069 | 0.4403 | 0.5938 | 0.9084 | 0.1038 | 0.9556 | 0.7086 | 0.8934 |
| `irc_alert` | `validation` | 2 | 5,069 | 0.4472 | 0.6465 | 0.8926 | 0.1133 | 0.9629 | 0.6662 | 0.8842 |
| `irc_alert` | `validation` | 3 | 5,069 | 0.4478 | 0.6177 | 0.8785 | 0.1199 | 0.9441 | 0.6844 | 0.8775 |

## Interpretation Guardrails

- Thresholds are selected on validation/calibration rows only.
- Test metrics must be read as held-out evaluation, not threshold tuning evidence.
- If a horizon has insufficient bloom positives, its calibrator is omitted.
- These outputs refine alert decisions; they do not retrain PIPE Neural ODE v2 direct.

## Outputs

- Thresholds: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_alert_calibration_thresholds.csv`
- Metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_alert_calibration_metrics.csv`
- Calibrated rows: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_calibrated_backtest_rows.parquet`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_alert_calibration_manifest.json`

## Calibrators

- `models/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/direct_alert_calibrators/rollout_bloom_h1_irc_mean_isotonic.joblib`
- `models/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/direct_alert_calibrators/rollout_bloom_h2_irc_mean_isotonic.joblib`
- `models/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/direct_alert_calibrators/rollout_bloom_h3_irc_mean_isotonic.joblib`