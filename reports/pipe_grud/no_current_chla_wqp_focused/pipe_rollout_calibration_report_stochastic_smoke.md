# PIPE/GRU-D Rollout Alert Calibration Report

Generated at UTC: `2026-06-12T22:38:41.374400+00:00`

## Scope

This report selects horizon-specific rollout alert thresholds on the calibration split and evaluates them on requested splits.
Bloom probabilities are fitted from rollout-derived IRC scores to observed `bloom_h`; test rows are evaluation-only.

## Configuration

- Backtest rows: `['reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_rows_validation_stochastic_smoke.parquet', 'reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_rows_test_stochastic_smoke.parquet']`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Bloom score column: `irc_mean`
- Selection objective: `fbeta`
- F-beta beta: `2.0`
- Minimum recall: `None`
- Minimum precision: `None`
- Calibrator directory: `models/pipe_grud/no_current_chla_wqp_focused/rollout_calibrators_stochastic_smoke`

## Selected Thresholds

| event | horizon | score | threshold | rows | positives | recall | precision | F-beta | constraint |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| `bloom_h` | 1 | `rollout_probability_bloom_calibrated` | 0.1481 | 301 | 34 | 0.8824 | 0.1987 | 0.5226 | `True` |
| `bloom_h` | 2 | `rollout_probability_bloom_calibrated` | 0.1282 | 327 | 41 | 0.6829 | 0.1818 | 0.4403 | `True` |
| `bloom_h` | 3 | `rollout_probability_bloom_calibrated` | 0.2073 | 342 | 40 | 0.6500 | 0.2600 | 0.5000 | `True` |
| `irc_alert` | 1 | `alert_probability_irc` | 0.3438 | 512 | 241 | 0.9378 | 0.6175 | 0.8496 | `True` |
| `irc_alert` | 2 | `alert_probability_irc` | 0.0859 | 512 | 240 | 1.0000 | 0.4697 | 0.8158 | `True` |
| `irc_alert` | 3 | `alert_probability_irc` | 0.1328 | 512 | 241 | 1.0000 | 0.4707 | 0.8164 | `True` |

## Evaluation Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | precision | F-beta |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.5000 | 0.2874 | 0.1428 | 0.7059 | 0.2400 | 0.5085 |
| `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.4809 | 0.4107 | 0.1374 | 0.7500 | 0.2857 | 0.5660 |
| `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.3407 | 0.2735 | 0.1387 | 0.5362 | 0.2662 | 0.4458 |
| `bloom_h` | `validation` | 1 | 301 | 0.1130 | 0.5017 | 0.3821 | 0.0788 | 0.8824 | 0.1987 | 0.5226 |
| `bloom_h` | `validation` | 2 | 327 | 0.1254 | 0.4709 | 0.2736 | 0.0996 | 0.6829 | 0.1818 | 0.4403 |
| `bloom_h` | `validation` | 3 | 342 | 0.1170 | 0.2924 | 0.3174 | 0.0887 | 0.6500 | 0.2600 | 0.5000 |
| `irc_alert` | `test` | 1 | 512 | 0.4316 | 0.6699 | 0.7281 | 0.2071 | 0.8869 | 0.5714 | 0.7987 |
| `irc_alert` | `test` | 2 | 512 | 0.4395 | 0.9941 | 0.6596 | 0.2207 | 1.0000 | 0.4420 | 0.7984 |
| `irc_alert` | `test` | 3 | 512 | 0.4492 | 0.9980 | 0.5967 | 0.2412 | 0.9957 | 0.4481 | 0.8001 |
| `irc_alert` | `validation` | 1 | 512 | 0.4707 | 0.7148 | 0.7650 | 0.1868 | 0.9378 | 0.6175 | 0.8496 |
| `irc_alert` | `validation` | 2 | 512 | 0.4688 | 0.9980 | 0.6963 | 0.2159 | 1.0000 | 0.4697 | 0.8158 |
| `irc_alert` | `validation` | 3 | 512 | 0.4707 | 1.0000 | 0.6133 | 0.2388 | 1.0000 | 0.4707 | 0.8164 |

## Interpretation Guardrails

- Thresholds are selected on validation/calibration rows only.
- Test metrics must be read as held-out evaluation, not threshold tuning evidence.
- If a horizon has insufficient bloom positives, its calibrator is omitted.
- These outputs refine alert decisions; they do not retrain PIPE/GRU-D.

## Outputs

- Thresholds: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_calibration_thresholds_stochastic_smoke.csv`
- Metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_calibration_metrics_stochastic_smoke.csv`
- Calibrated rows: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_calibrated_backtest_rows_stochastic_smoke.parquet`
- Manifest: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_calibration_manifest_stochastic_smoke.json`

## Calibrators

- `models/pipe_grud/no_current_chla_wqp_focused/rollout_calibrators_stochastic_smoke/rollout_bloom_h1_irc_mean_isotonic.joblib`
- `models/pipe_grud/no_current_chla_wqp_focused/rollout_calibrators_stochastic_smoke/rollout_bloom_h2_irc_mean_isotonic.joblib`
- `models/pipe_grud/no_current_chla_wqp_focused/rollout_calibrators_stochastic_smoke/rollout_bloom_h3_irc_mean_isotonic.joblib`