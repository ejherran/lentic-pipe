# PIPE/GRU-D Rollout Alert Policy Frontier Report

Generated at UTC: `2026-06-12T18:51:47.740106+00:00`

## Scope

This report compares automatic threshold-selection objectives on the validation split and evaluates them on held-out test rows.
It does not adopt a final operational policy; it characterizes the decision frontier between precision and recall.

## Configuration

- Calibrated rows: `reports/pipe_grud/no_current_chla/pipe_rollout_calibrated_backtest_rows_smoke.parquet`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Selection objectives: `['fixed', 'fbeta', 'f1', 'mcc', 'balanced_accuracy', 'gmean_pr', 'closest_pr']`
- F-beta beta: `2.0`
- Minimum recall constraint: `None`
- Minimum precision constraint: `None`

## Test Frontier

| event | horizon | policy | threshold | rows | base rate | recall | precision | alert rate | F1 | F2 | MCC | balanced accuracy |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | 1 | `balanced_accuracy` | 0.1382 | 461 | 0.1302 | 0.7667 | 0.1581 | 0.6312 | 0.2621 | 0.4331 | 0.1086 | 0.5778 |
| `bloom_h` | 1 | `closest_pr` | 0.0941 | 461 | 0.1302 | 0.8500 | 0.1461 | 0.7570 | 0.2494 | 0.4329 | 0.0838 | 0.5534 |
| `bloom_h` | 1 | `f1` | 0.1382 | 461 | 0.1302 | 0.7667 | 0.1581 | 0.6312 | 0.2621 | 0.4331 | 0.1086 | 0.5778 |
| `bloom_h` | 1 | `fbeta` | 0.0941 | 461 | 0.1302 | 0.8500 | 0.1461 | 0.7570 | 0.2494 | 0.4329 | 0.0838 | 0.5534 |
| `bloom_h` | 1 | `gmean_pr` | 0.0811 | 461 | 0.1302 | 0.9833 | 0.1302 | 0.9826 | 0.2300 | 0.4257 | 0.0020 | 0.5004 |
| `bloom_h` | 1 | `mcc` | 0.1382 | 461 | 0.1302 | 0.7667 | 0.1581 | 0.6312 | 0.2621 | 0.4331 | 0.1086 | 0.5778 |
| `bloom_h` | 2 | `balanced_accuracy` | 0.1591 | 460 | 0.1348 | 0.5161 | 0.2051 | 0.3391 | 0.2936 | 0.3960 | 0.1476 | 0.6023 |
| `bloom_h` | 2 | `closest_pr` | 0.1355 | 460 | 0.1348 | 0.9355 | 0.1408 | 0.8957 | 0.2447 | 0.4394 | 0.0514 | 0.5230 |
| `bloom_h` | 2 | `f1` | 0.1355 | 460 | 0.1348 | 0.9355 | 0.1408 | 0.8957 | 0.2447 | 0.4394 | 0.0514 | 0.5230 |
| `bloom_h` | 2 | `fbeta` | 0.1355 | 460 | 0.1348 | 0.9355 | 0.1408 | 0.8957 | 0.2447 | 0.4394 | 0.0514 | 0.5230 |
| `bloom_h` | 2 | `gmean_pr` | 0.1355 | 460 | 0.1348 | 0.9355 | 0.1408 | 0.8957 | 0.2447 | 0.4394 | 0.0514 | 0.5230 |
| `bloom_h` | 2 | `mcc` | 0.1355 | 460 | 0.1348 | 0.9355 | 0.1408 | 0.8957 | 0.2447 | 0.4394 | 0.0514 | 0.5230 |
| `bloom_h` | 3 | `balanced_accuracy` | 0.1770 | 467 | 0.1328 | 0.8226 | 0.1619 | 0.6745 | 0.2706 | 0.4529 | 0.1236 | 0.5854 |
| `bloom_h` | 3 | `closest_pr` | 0.1770 | 467 | 0.1328 | 0.8226 | 0.1619 | 0.6745 | 0.2706 | 0.4529 | 0.1236 | 0.5854 |
| `bloom_h` | 3 | `f1` | 0.1770 | 467 | 0.1328 | 0.8226 | 0.1619 | 0.6745 | 0.2706 | 0.4529 | 0.1236 | 0.5854 |
| `bloom_h` | 3 | `fbeta` | 0.1770 | 467 | 0.1328 | 0.8226 | 0.1619 | 0.6745 | 0.2706 | 0.4529 | 0.1236 | 0.5854 |
| `bloom_h` | 3 | `gmean_pr` | 0.1770 | 467 | 0.1328 | 0.8226 | 0.1619 | 0.6745 | 0.2706 | 0.4529 | 0.1236 | 0.5854 |
| `bloom_h` | 3 | `mcc` | 0.1770 | 467 | 0.1328 | 0.8226 | 0.1619 | 0.6745 | 0.2706 | 0.4529 | 0.1236 | 0.5854 |
| `irc_alert` | 1 | `balanced_accuracy` | 1.0000 | 512 | 0.3379 | 0.3295 | 0.6264 | 0.1777 | 0.4318 | 0.3640 | 0.2836 | 0.6146 |
| `irc_alert` | 1 | `closest_pr` | 0.0000 | 512 | 0.3379 | 1.0000 | 0.3379 | 1.0000 | 0.5051 | 0.7184 | NA | 0.5000 |
| `irc_alert` | 1 | `f1` | 0.0000 | 512 | 0.3379 | 1.0000 | 0.3379 | 1.0000 | 0.5051 | 0.7184 | NA | 0.5000 |
| `irc_alert` | 1 | `fbeta` | 0.0000 | 512 | 0.3379 | 1.0000 | 0.3379 | 1.0000 | 0.5051 | 0.7184 | NA | 0.5000 |
| `irc_alert` | 1 | `fixed` | 0.5000 | 512 | 0.3379 | 0.3295 | 0.6264 | 0.1777 | 0.4318 | 0.3640 | 0.2836 | 0.6146 |
| `irc_alert` | 1 | `gmean_pr` | 0.0000 | 512 | 0.3379 | 1.0000 | 0.3379 | 1.0000 | 0.5051 | 0.7184 | NA | 0.5000 |
| `irc_alert` | 1 | `mcc` | 1.0000 | 512 | 0.3379 | 0.3295 | 0.6264 | 0.1777 | 0.4318 | 0.3640 | 0.2836 | 0.6146 |
| `irc_alert` | 2 | `balanced_accuracy` | 1.0000 | 512 | 0.3477 | 0.2303 | 0.6613 | 0.1211 | 0.3417 | 0.2649 | 0.2445 | 0.5837 |
| `irc_alert` | 2 | `closest_pr` | 0.0000 | 512 | 0.3477 | 1.0000 | 0.3477 | 1.0000 | 0.5159 | 0.7271 | NA | 0.5000 |
| `irc_alert` | 2 | `f1` | 0.0000 | 512 | 0.3477 | 1.0000 | 0.3477 | 1.0000 | 0.5159 | 0.7271 | NA | 0.5000 |
| `irc_alert` | 2 | `fbeta` | 0.0000 | 512 | 0.3477 | 1.0000 | 0.3477 | 1.0000 | 0.5159 | 0.7271 | NA | 0.5000 |
| `irc_alert` | 2 | `fixed` | 0.5000 | 512 | 0.3477 | 0.2303 | 0.6613 | 0.1211 | 0.3417 | 0.2649 | 0.2445 | 0.5837 |
| `irc_alert` | 2 | `gmean_pr` | 0.0000 | 512 | 0.3477 | 1.0000 | 0.3477 | 1.0000 | 0.5159 | 0.7271 | NA | 0.5000 |
| `irc_alert` | 2 | `mcc` | 1.0000 | 512 | 0.3477 | 0.2303 | 0.6613 | 0.1211 | 0.3417 | 0.2649 | 0.2445 | 0.5837 |
| `irc_alert` | 3 | `balanced_accuracy` | 1.0000 | 512 | 0.3535 | 0.1492 | 0.8182 | 0.0645 | 0.2523 | 0.1783 | 0.2551 | 0.5655 |
| `irc_alert` | 3 | `closest_pr` | 0.0000 | 512 | 0.3535 | 1.0000 | 0.3535 | 1.0000 | 0.5224 | 0.7322 | NA | 0.5000 |
| `irc_alert` | 3 | `f1` | 0.0000 | 512 | 0.3535 | 1.0000 | 0.3535 | 1.0000 | 0.5224 | 0.7322 | NA | 0.5000 |
| `irc_alert` | 3 | `fbeta` | 0.0000 | 512 | 0.3535 | 1.0000 | 0.3535 | 1.0000 | 0.5224 | 0.7322 | NA | 0.5000 |
| `irc_alert` | 3 | `fixed` | 0.5000 | 512 | 0.3535 | 0.1492 | 0.8182 | 0.0645 | 0.2523 | 0.1783 | 0.2551 | 0.5655 |
| `irc_alert` | 3 | `gmean_pr` | 0.0000 | 512 | 0.3535 | 1.0000 | 0.3535 | 1.0000 | 0.5224 | 0.7322 | NA | 0.5000 |
| `irc_alert` | 3 | `mcc` | 1.0000 | 512 | 0.3535 | 0.1492 | 0.8182 | 0.0645 | 0.2523 | 0.1783 | 0.2551 | 0.5655 |

## Objective Meanings

- `fixed`: the pre-existing fixed threshold policy.
- `fbeta`: recall-weighted F-beta selection; with beta 2.0 this is the sensitive early-warning policy.
- `f1`: harmonic mean of precision and recall.
- `mcc`: Matthews correlation coefficient, using all confusion-matrix cells.
- `balanced_accuracy`: mean of recall and specificity.
- `gmean_pr`: geometric mean of precision and recall.
- `closest_pr`: smallest Euclidean distance to the ideal precision-recall point `(1, 1)`.

## Interpretation Guardrails

- All non-fixed thresholds are selected on validation rows only.
- Test rows are used for evaluation only.
- These policies compare alert decisions; they do not retrain PIPE/GRU-D.
- A balanced objective is a modeling choice, not an objective truth; it should be defended by the decision context.

## Outputs

- Thresholds: `reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_thresholds_smoke.csv`
- Metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_metrics_smoke.csv`
- Manifest: `reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_manifest_smoke.json`