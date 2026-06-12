# PIPE/GRU-D Rollout Alert Policy Frontier Report

Generated at UTC: `2026-06-12T22:57:27.821900+00:00`

## Scope

This report compares automatic threshold-selection objectives on the validation split and evaluates them on held-out test rows.
It does not adopt a final operational policy; it characterizes the decision frontier between precision and recall.

## Configuration

- Calibrated rows: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_calibrated_backtest_rows.parquet`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Selection objectives: `['fixed', 'fbeta', 'f1', 'mcc', 'balanced_accuracy', 'gmean_pr', 'closest_pr']`
- F-beta beta: `2.0`
- Minimum recall constraint: `None`
- Minimum precision constraint: `None`

## Test Frontier

| event | horizon | policy | threshold | rows | base rate | recall | precision | alert rate | F1 | F2 | MCC | balanced accuracy |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | 1 | `balanced_accuracy` | 0.1353 | 4,673 | 0.1823 | 0.6033 | 0.4262 | 0.2581 | 0.4995 | 0.5570 | 0.3725 | 0.7111 |
| `bloom_h` | 1 | `closest_pr` | 0.1957 | 4,673 | 0.1823 | 0.5153 | 0.4675 | 0.2009 | 0.4902 | 0.5049 | 0.3704 | 0.6922 |
| `bloom_h` | 1 | `f1` | 0.2500 | 4,673 | 0.1823 | 0.4789 | 0.4945 | 0.1765 | 0.4866 | 0.4819 | 0.3744 | 0.6849 |
| `bloom_h` | 1 | `fbeta` | 0.1333 | 4,673 | 0.1823 | 0.6702 | 0.3941 | 0.3101 | 0.4963 | 0.5878 | 0.3676 | 0.7202 |
| `bloom_h` | 1 | `gmean_pr` | 0.1957 | 4,673 | 0.1823 | 0.5153 | 0.4675 | 0.2009 | 0.4902 | 0.5049 | 0.3704 | 0.6922 |
| `bloom_h` | 1 | `mcc` | 0.2500 | 4,673 | 0.1823 | 0.4789 | 0.4945 | 0.1765 | 0.4866 | 0.4819 | 0.3744 | 0.6849 |
| `bloom_h` | 2 | `balanced_accuracy` | 0.1875 | 4,710 | 0.1832 | 0.5875 | 0.4149 | 0.2594 | 0.4863 | 0.5424 | 0.3545 | 0.7008 |
| `bloom_h` | 2 | `closest_pr` | 0.2326 | 4,710 | 0.1832 | 0.4983 | 0.4335 | 0.2106 | 0.4636 | 0.4838 | 0.3341 | 0.6761 |
| `bloom_h` | 2 | `f1` | 0.2821 | 4,710 | 0.1832 | 0.4380 | 0.4340 | 0.1849 | 0.4360 | 0.4372 | 0.3088 | 0.6549 |
| `bloom_h` | 2 | `fbeta` | 0.1383 | 4,710 | 0.1832 | 0.6280 | 0.4036 | 0.2851 | 0.4914 | 0.5652 | 0.3597 | 0.7099 |
| `bloom_h` | 2 | `gmean_pr` | 0.2326 | 4,710 | 0.1832 | 0.4983 | 0.4335 | 0.2106 | 0.4636 | 0.4838 | 0.3341 | 0.6761 |
| `bloom_h` | 2 | `mcc` | 0.2821 | 4,710 | 0.1832 | 0.4380 | 0.4340 | 0.1849 | 0.4360 | 0.4372 | 0.3088 | 0.6549 |
| `bloom_h` | 3 | `balanced_accuracy` | 0.1456 | 4,757 | 0.1856 | 0.6988 | 0.3739 | 0.3469 | 0.4872 | 0.5953 | 0.3530 | 0.7161 |
| `bloom_h` | 3 | `closest_pr` | 0.1456 | 4,757 | 0.1856 | 0.6988 | 0.3739 | 0.3469 | 0.4872 | 0.5953 | 0.3530 | 0.7161 |
| `bloom_h` | 3 | `f1` | 0.2500 | 4,757 | 0.1856 | 0.4666 | 0.4063 | 0.2132 | 0.4344 | 0.4531 | 0.2954 | 0.6556 |
| `bloom_h` | 3 | `fbeta` | 0.1302 | 4,757 | 0.1856 | 0.7395 | 0.3596 | 0.3818 | 0.4839 | 0.6105 | 0.3516 | 0.7197 |
| `bloom_h` | 3 | `gmean_pr` | 0.2041 | 4,757 | 0.1856 | 0.5549 | 0.3968 | 0.2596 | 0.4627 | 0.5140 | 0.3216 | 0.6813 |
| `bloom_h` | 3 | `mcc` | 0.2500 | 4,757 | 0.1856 | 0.4666 | 0.4063 | 0.2132 | 0.4344 | 0.4531 | 0.2954 | 0.6556 |
| `irc_alert` | 1 | `balanced_accuracy` | 0.5312 | 6,145 | 0.4544 | 0.7350 | 0.7155 | 0.4667 | 0.7251 | 0.7310 | 0.4906 | 0.7458 |
| `irc_alert` | 1 | `closest_pr` | 0.4922 | 6,145 | 0.4544 | 0.7636 | 0.6976 | 0.4973 | 0.7291 | 0.7494 | 0.4860 | 0.7440 |
| `irc_alert` | 1 | `f1` | 0.3438 | 6,145 | 0.4544 | 0.8696 | 0.6482 | 0.6096 | 0.7427 | 0.8140 | 0.4864 | 0.7383 |
| `irc_alert` | 1 | `fbeta` | 0.1562 | 6,145 | 0.4544 | 0.9620 | 0.5671 | 0.7707 | 0.7136 | 0.8444 | 0.4153 | 0.6753 |
| `irc_alert` | 1 | `fixed` | 0.5000 | 6,145 | 0.4544 | 0.7579 | 0.7007 | 0.4915 | 0.7281 | 0.7457 | 0.4863 | 0.7441 |
| `irc_alert` | 1 | `gmean_pr` | 0.3438 | 6,145 | 0.4544 | 0.8696 | 0.6482 | 0.6096 | 0.7427 | 0.8140 | 0.4864 | 0.7383 |
| `irc_alert` | 1 | `mcc` | 0.5312 | 6,145 | 0.4544 | 0.7350 | 0.7155 | 0.4667 | 0.7251 | 0.7310 | 0.4906 | 0.7458 |
| `irc_alert` | 2 | `balanced_accuracy` | 0.4531 | 6,145 | 0.4692 | 0.7461 | 0.7324 | 0.4779 | 0.7392 | 0.7433 | 0.5047 | 0.7526 |
| `irc_alert` | 2 | `closest_pr` | 0.3672 | 6,145 | 0.4692 | 0.8287 | 0.6903 | 0.5632 | 0.7532 | 0.7967 | 0.5031 | 0.7500 |
| `irc_alert` | 2 | `f1` | 0.3516 | 6,145 | 0.4692 | 0.8425 | 0.6819 | 0.5797 | 0.7538 | 0.8046 | 0.5006 | 0.7476 |
| `irc_alert` | 2 | `fbeta` | 0.0547 | 6,145 | 0.4692 | 0.9941 | 0.5227 | 0.8923 | 0.6852 | 0.8422 | 0.3088 | 0.5959 |
| `irc_alert` | 2 | `fixed` | 0.5000 | 6,145 | 0.4692 | 0.6903 | 0.7456 | 0.4343 | 0.7169 | 0.7007 | 0.4854 | 0.7410 |
| `irc_alert` | 2 | `gmean_pr` | 0.2422 | 6,145 | 0.4692 | 0.9261 | 0.6183 | 0.7027 | 0.7416 | 0.8423 | 0.4596 | 0.7105 |
| `irc_alert` | 2 | `mcc` | 0.3672 | 6,145 | 0.4692 | 0.8287 | 0.6903 | 0.5632 | 0.7532 | 0.7967 | 0.5031 | 0.7500 |
| `irc_alert` | 3 | `balanced_accuracy` | 0.3828 | 6,145 | 0.4781 | 0.7941 | 0.7148 | 0.5312 | 0.7523 | 0.7768 | 0.5043 | 0.7519 |
| `irc_alert` | 3 | `closest_pr` | 0.2656 | 6,145 | 0.4781 | 0.8907 | 0.6478 | 0.6574 | 0.7501 | 0.8286 | 0.4705 | 0.7235 |
| `irc_alert` | 3 | `f1` | 0.2578 | 6,145 | 0.4781 | 0.8975 | 0.6444 | 0.6659 | 0.7502 | 0.8322 | 0.4701 | 0.7219 |
| `irc_alert` | 3 | `fbeta` | 0.0625 | 6,145 | 0.4781 | 0.9894 | 0.5383 | 0.8788 | 0.6973 | 0.8474 | 0.3246 | 0.6060 |
| `irc_alert` | 3 | `fixed` | 0.5000 | 6,145 | 0.4781 | 0.6283 | 0.7441 | 0.4037 | 0.6813 | 0.6485 | 0.4381 | 0.7152 |
| `irc_alert` | 3 | `gmean_pr` | 0.2031 | 6,145 | 0.4781 | 0.9391 | 0.6135 | 0.7318 | 0.7422 | 0.8490 | 0.4478 | 0.6986 |
| `irc_alert` | 3 | `mcc` | 0.2656 | 6,145 | 0.4781 | 0.8907 | 0.6478 | 0.6574 | 0.7501 | 0.8286 | 0.4705 | 0.7235 |

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

- Thresholds: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_policy_2b_thresholds.csv`
- Metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_policy_2b_metrics.csv`
- Manifest: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_policy_2b_manifest.json`