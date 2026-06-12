# PIPE/GRU-D Rollout Alert Calibration Report

Generated at UTC: `2026-06-12T18:59:47.496708+00:00`

## Scope

This report selects horizon-specific rollout alert thresholds on the calibration split and evaluates them on requested splits.
Bloom probabilities are fitted from rollout-derived IRC scores to observed `bloom_h`; test rows are evaluation-only.

## Configuration

- Backtest rows: `['reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_validation_stochastic_smoke.parquet', 'reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_test_stochastic_smoke.parquet']`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Bloom score column: `irc_mean`
- Selection objective: `fbeta`
- F-beta beta: `2.0`
- Minimum recall: `None`
- Minimum precision: `None`
- Calibrator directory: `models/pipe_grud/no_current_chla/rollout_calibrators_stochastic_smoke`

## Selected Thresholds

| event | horizon | score | threshold | rows | positives | recall | precision | F-beta | constraint |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| `bloom_h` | 1 | `rollout_probability_bloom_calibrated` | 0.1000 | 445 | 57 | 1.0000 | 0.1287 | 0.4247 | `True` |
| `bloom_h` | 2 | `rollout_probability_bloom_calibrated` | 0.1084 | 451 | 66 | 1.0000 | 0.1470 | 0.4628 | `True` |
| `bloom_h` | 3 | `rollout_probability_bloom_calibrated` | 0.1592 | 460 | 68 | 0.7941 | 0.1765 | 0.4671 | `True` |
| `irc_alert` | 1 | `alert_probability_irc` | 0.0469 | 512 | 184 | 1.0000 | 0.3636 | 0.7407 | `True` |
| `irc_alert` | 2 | `alert_probability_irc` | 0.0938 | 512 | 179 | 1.0000 | 0.3538 | 0.7324 | `True` |
| `irc_alert` | 3 | `alert_probability_irc` | 0.1328 | 512 | 180 | 1.0000 | 0.3550 | 0.7335 | `True` |

## Evaluation Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | precision | F-beta |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.9848 | 0.1889 | 0.1128 | 0.9667 | 0.1278 | 0.4179 |
| `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.9848 | 0.2109 | 0.1147 | 1.0000 | 0.1369 | 0.4422 |
| `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.7109 | 0.1665 | 0.1147 | 0.7581 | 0.1416 | 0.4052 |
| `bloom_h` | `validation` | 1 | 445 | 0.1281 | 0.9955 | 0.1486 | 0.1109 | 1.0000 | 0.1287 | 0.4247 |
| `bloom_h` | `validation` | 2 | 451 | 0.1463 | 0.9956 | 0.1725 | 0.1237 | 1.0000 | 0.1470 | 0.4628 |
| `bloom_h` | `validation` | 3 | 460 | 0.1478 | 0.6652 | 0.1873 | 0.1237 | 0.7941 | 0.1765 | 0.4671 |
| `irc_alert` | `test` | 1 | 512 | 0.3379 | 0.9844 | 0.5311 | 0.2169 | 0.9827 | 0.3373 | 0.7107 |
| `irc_alert` | `test` | 2 | 512 | 0.3477 | 0.9883 | 0.5374 | 0.2128 | 0.9888 | 0.3478 | 0.7225 |
| `irc_alert` | `test` | 3 | 512 | 0.3535 | 0.9883 | 0.5008 | 0.2235 | 0.9890 | 0.3538 | 0.7276 |
| `irc_alert` | `validation` | 1 | 512 | 0.3594 | 0.9883 | 0.5465 | 0.2135 | 1.0000 | 0.3636 | 0.7407 |
| `irc_alert` | `validation` | 2 | 512 | 0.3496 | 0.9883 | 0.5313 | 0.2098 | 1.0000 | 0.3538 | 0.7324 |
| `irc_alert` | `validation` | 3 | 512 | 0.3516 | 0.9902 | 0.4707 | 0.2237 | 1.0000 | 0.3550 | 0.7335 |

## Interpretation Guardrails

- Thresholds are selected on validation/calibration rows only.
- Test metrics must be read as held-out evaluation, not threshold tuning evidence.
- If a horizon has insufficient bloom positives, its calibrator is omitted.
- These outputs refine alert decisions; they do not retrain PIPE/GRU-D.

## Outputs

- Thresholds: `reports/pipe_grud/no_current_chla/pipe_rollout_calibration_thresholds_stochastic_smoke.csv`
- Metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_calibration_metrics_stochastic_smoke.csv`
- Calibrated rows: `reports/pipe_grud/no_current_chla/pipe_rollout_calibrated_backtest_rows_stochastic_smoke.parquet`
- Manifest: `reports/pipe_grud/no_current_chla/pipe_rollout_calibration_manifest_stochastic_smoke.json`

## Calibrators

- `models/pipe_grud/no_current_chla/rollout_calibrators_stochastic_smoke/rollout_bloom_h1_irc_mean_isotonic.joblib`
- `models/pipe_grud/no_current_chla/rollout_calibrators_stochastic_smoke/rollout_bloom_h2_irc_mean_isotonic.joblib`
- `models/pipe_grud/no_current_chla/rollout_calibrators_stochastic_smoke/rollout_bloom_h3_irc_mean_isotonic.joblib`