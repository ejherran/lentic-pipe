# PIPE/GRU-D Rollout Alert Calibration Report

Generated at UTC: `2026-06-12T14:38:31.740193+00:00`

## Scope

This report selects horizon-specific rollout alert thresholds on the calibration split and evaluates them on requested splits.
Bloom probabilities are fitted from rollout-derived IRC scores to observed `bloom_h`; test rows are evaluation-only.

## Configuration

- Backtest rows: `['reports/pipe_grud/pipe_rollout_backtest_rows_validation.parquet', 'reports/pipe_grud/pipe_rollout_backtest_rows_test.parquet']`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Bloom score column: `irc_mean`
- Selection objective: `fbeta`
- F-beta beta: `2.0`
- Minimum recall: `0.5`
- Minimum precision: `None`
- Calibrator directory: `models/pipe_grud/rollout_calibrators`

## Selected Thresholds

| event | horizon | score | threshold | rows | positives | recall | precision | F-beta | constraint |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| `bloom_h` | 1 | `rollout_probability_bloom_calibrated` | 0.1538 | 14,212 | 1,841 | 0.7936 | 0.4209 | 0.6742 | `True` |
| `bloom_h` | 2 | `rollout_probability_bloom_calibrated` | 0.1649 | 14,325 | 1,892 | 0.7960 | 0.3788 | 0.6523 | `True` |
| `bloom_h` | 3 | `rollout_probability_bloom_calibrated` | 0.1300 | 14,352 | 1,898 | 0.8303 | 0.3361 | 0.6416 | `True` |
| `irc_alert` | 1 | `alert_probability_irc` | 0.1172 | 16,260 | 5,860 | 0.9121 | 0.6159 | 0.8321 | `True` |
| `irc_alert` | 2 | `alert_probability_irc` | 0.1250 | 16,260 | 5,873 | 0.9350 | 0.5619 | 0.8253 | `True` |
| `irc_alert` | 3 | `alert_probability_irc` | 0.1641 | 16,260 | 5,817 | 0.9201 | 0.5744 | 0.8212 | `True` |

## Evaluation Metrics

| event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall | precision | F-beta |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | `test` | 1 | 11,852 | 0.1243 | 0.2190 | 0.6621 | 0.0619 | 0.8242 | 0.4678 | 0.7152 |
| `bloom_h` | `test` | 2 | 11,891 | 0.1298 | 0.2647 | 0.6262 | 0.0698 | 0.8569 | 0.4204 | 0.7095 |
| `bloom_h` | `test` | 3 | 11,939 | 0.1335 | 0.3288 | 0.5961 | 0.0752 | 0.8902 | 0.3615 | 0.6888 |
| `bloom_h` | `validation` | 1 | 14,212 | 0.1295 | 0.2442 | 0.6024 | 0.0718 | 0.7936 | 0.4209 | 0.6742 |
| `bloom_h` | `validation` | 2 | 14,325 | 0.1321 | 0.2776 | 0.5713 | 0.0775 | 0.7960 | 0.3788 | 0.6523 |
| `bloom_h` | `validation` | 3 | 14,352 | 0.1322 | 0.3267 | 0.5507 | 0.0800 | 0.8303 | 0.3361 | 0.6416 |
| `irc_alert` | `test` | 1 | 13,327 | 0.3335 | 0.4998 | 0.8894 | 0.0913 | 0.9386 | 0.6262 | 0.8534 |
| `irc_alert` | `test` | 2 | 13,327 | 0.3464 | 0.5736 | 0.8769 | 0.1038 | 0.9565 | 0.5776 | 0.8455 |
| `irc_alert` | `test` | 3 | 13,327 | 0.3564 | 0.5631 | 0.8702 | 0.1123 | 0.9423 | 0.5964 | 0.8444 |
| `irc_alert` | `validation` | 1 | 16,260 | 0.3604 | 0.5338 | 0.8354 | 0.1230 | 0.9121 | 0.6159 | 0.8321 |
| `irc_alert` | `validation` | 2 | 16,260 | 0.3612 | 0.6010 | 0.8100 | 0.1316 | 0.9350 | 0.5619 | 0.8253 |
| `irc_alert` | `validation` | 3 | 16,260 | 0.3577 | 0.5730 | 0.7945 | 0.1365 | 0.9201 | 0.5744 | 0.8212 |

## Interpretation Guardrails

- Thresholds are selected on validation/calibration rows only.
- Test metrics must be read as held-out evaluation, not threshold tuning evidence.
- If a horizon has insufficient bloom positives, its calibrator is omitted.
- These outputs refine alert decisions; they do not retrain PIPE/GRU-D.

## Outputs

- Thresholds: `reports/pipe_grud/pipe_rollout_calibration_thresholds.csv`
- Metrics: `reports/pipe_grud/pipe_rollout_calibration_metrics.csv`
- Calibrated rows: `reports/pipe_grud/pipe_rollout_calibrated_backtest_rows.parquet`
- Manifest: `reports/pipe_grud/pipe_rollout_calibration_manifest.json`

## Calibrators

- `models/pipe_grud/rollout_calibrators/rollout_bloom_h1_irc_mean_isotonic.joblib`
- `models/pipe_grud/rollout_calibrators/rollout_bloom_h2_irc_mean_isotonic.joblib`
- `models/pipe_grud/rollout_calibrators/rollout_bloom_h3_irc_mean_isotonic.joblib`