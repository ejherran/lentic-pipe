# PIPE/GRU-D Rollout Alert Policy Frontier Report

Generated at UTC: `2026-06-12T22:40:32.280072+00:00`

## Scope

This report compares automatic threshold-selection objectives on the validation split and evaluates them on held-out test rows.
It does not adopt a final operational policy; it characterizes the decision frontier between precision and recall.

## Configuration

- Calibrated rows: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_calibrated_backtest_rows_stochastic_smoke.parquet`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Selection objectives: `['fixed', 'fbeta', 'f1', 'mcc', 'balanced_accuracy', 'gmean_pr', 'closest_pr']`
- F-beta beta: `2.0`
- Minimum recall constraint: `None`
- Minimum precision constraint: `None`

## Test Frontier

| event | horizon | policy | threshold | rows | base rate | recall | precision | alert rate | F1 | F2 | MCC | balanced accuracy |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | 1 | `balanced_accuracy` | 0.1481 | 400 | 0.1700 | 0.7059 | 0.2400 | 0.5000 | 0.3582 | 0.5085 | 0.1864 | 0.6240 |
| `bloom_h` | 1 | `closest_pr` | 0.1481 | 400 | 0.1700 | 0.7059 | 0.2400 | 0.5000 | 0.3582 | 0.5085 | 0.1864 | 0.6240 |
| `bloom_h` | 1 | `f1` | 0.2222 | 400 | 0.1700 | 0.2206 | 0.4545 | 0.0825 | 0.2970 | 0.2459 | 0.2271 | 0.5832 |
| `bloom_h` | 1 | `fbeta` | 0.1481 | 400 | 0.1700 | 0.7059 | 0.2400 | 0.5000 | 0.3582 | 0.5085 | 0.1864 | 0.6240 |
| `bloom_h` | 1 | `gmean_pr` | 1.0000 | 400 | 0.1700 | 0.0441 | 0.4286 | 0.0175 | 0.0800 | 0.0538 | 0.0919 | 0.5160 |
| `bloom_h` | 1 | `mcc` | 1.0000 | 400 | 0.1700 | 0.0441 | 0.4286 | 0.0175 | 0.0800 | 0.0538 | 0.0919 | 0.5160 |
| `bloom_h` | 2 | `balanced_accuracy` | 0.1282 | 393 | 0.1832 | 0.7500 | 0.2857 | 0.4809 | 0.4138 | 0.5660 | 0.2551 | 0.6647 |
| `bloom_h` | 2 | `closest_pr` | 0.0769 | 393 | 0.1832 | 0.8333 | 0.2553 | 0.5980 | 0.3909 | 0.5736 | 0.2273 | 0.6441 |
| `bloom_h` | 2 | `f1` | 0.1481 | 393 | 0.1832 | 0.6111 | 0.3099 | 0.3613 | 0.4112 | 0.5116 | 0.2463 | 0.6529 |
| `bloom_h` | 2 | `fbeta` | 0.1282 | 393 | 0.1832 | 0.7500 | 0.2857 | 0.4809 | 0.4138 | 0.5660 | 0.2551 | 0.6647 |
| `bloom_h` | 2 | `gmean_pr` | 0.0750 | 393 | 0.1832 | 1.0000 | 0.1851 | 0.9898 | 0.3124 | 0.5318 | 0.0480 | 0.5062 |
| `bloom_h` | 2 | `mcc` | 0.6667 | 393 | 0.1832 | 0.0556 | 0.8000 | 0.0127 | 0.1039 | 0.0683 | 0.1810 | 0.5262 |
| `bloom_h` | 3 | `balanced_accuracy` | 0.2073 | 408 | 0.1691 | 0.5362 | 0.2662 | 0.3407 | 0.3558 | 0.4458 | 0.1861 | 0.6177 |
| `bloom_h` | 3 | `closest_pr` | 0.2073 | 408 | 0.1691 | 0.5362 | 0.2662 | 0.3407 | 0.3558 | 0.4458 | 0.1861 | 0.6177 |
| `bloom_h` | 3 | `f1` | 0.2073 | 408 | 0.1691 | 0.5362 | 0.2662 | 0.3407 | 0.3558 | 0.4458 | 0.1861 | 0.6177 |
| `bloom_h` | 3 | `fbeta` | 0.2073 | 408 | 0.1691 | 0.5362 | 0.2662 | 0.3407 | 0.3558 | 0.4458 | 0.1861 | 0.6177 |
| `bloom_h` | 3 | `gmean_pr` | 0.2073 | 408 | 0.1691 | 0.5362 | 0.2662 | 0.3407 | 0.3558 | 0.4458 | 0.1861 | 0.6177 |
| `bloom_h` | 3 | `mcc` | 0.2073 | 408 | 0.1691 | 0.5362 | 0.2662 | 0.3407 | 0.3558 | 0.4458 | 0.1861 | 0.6177 |
| `irc_alert` | 1 | `balanced_accuracy` | 0.4453 | 512 | 0.4316 | 0.7602 | 0.5979 | 0.5488 | 0.6693 | 0.7210 | 0.3701 | 0.6859 |
| `irc_alert` | 1 | `closest_pr` | 0.4453 | 512 | 0.4316 | 0.7602 | 0.5979 | 0.5488 | 0.6693 | 0.7210 | 0.3701 | 0.6859 |
| `irc_alert` | 1 | `f1` | 0.4453 | 512 | 0.4316 | 0.7602 | 0.5979 | 0.5488 | 0.6693 | 0.7210 | 0.3701 | 0.6859 |
| `irc_alert` | 1 | `fbeta` | 0.3438 | 512 | 0.4316 | 0.8869 | 0.5714 | 0.6699 | 0.6950 | 0.7987 | 0.4021 | 0.6909 |
| `irc_alert` | 1 | `fixed` | 0.5000 | 512 | 0.4316 | 0.6923 | 0.6220 | 0.4805 | 0.6552 | 0.6770 | 0.3695 | 0.6864 |
| `irc_alert` | 1 | `gmean_pr` | 0.4453 | 512 | 0.4316 | 0.7602 | 0.5979 | 0.5488 | 0.6693 | 0.7210 | 0.3701 | 0.6859 |
| `irc_alert` | 1 | `mcc` | 0.4453 | 512 | 0.4316 | 0.7602 | 0.5979 | 0.5488 | 0.6693 | 0.7210 | 0.3701 | 0.6859 |
| `irc_alert` | 2 | `balanced_accuracy` | 0.4375 | 512 | 0.4395 | 0.6756 | 0.6032 | 0.4922 | 0.6373 | 0.6597 | 0.3248 | 0.6636 |
| `irc_alert` | 2 | `closest_pr` | 0.3906 | 512 | 0.4395 | 0.7333 | 0.5769 | 0.5586 | 0.6458 | 0.6956 | 0.3116 | 0.6559 |
| `irc_alert` | 2 | `f1` | 0.3906 | 512 | 0.4395 | 0.7333 | 0.5769 | 0.5586 | 0.6458 | 0.6956 | 0.3116 | 0.6559 |
| `irc_alert` | 2 | `fbeta` | 0.0859 | 512 | 0.4395 | 1.0000 | 0.4420 | 0.9941 | 0.6131 | 0.7984 | 0.0680 | 0.5052 |
| `irc_alert` | 2 | `fixed` | 0.5000 | 512 | 0.4395 | 0.5200 | 0.6000 | 0.3809 | 0.5571 | 0.5342 | 0.2537 | 0.6241 |
| `irc_alert` | 2 | `gmean_pr` | 0.3047 | 512 | 0.4395 | 0.8356 | 0.5067 | 0.7246 | 0.6309 | 0.7396 | 0.2199 | 0.5990 |
| `irc_alert` | 2 | `mcc` | 0.4375 | 512 | 0.4395 | 0.6756 | 0.6032 | 0.4922 | 0.6373 | 0.6597 | 0.3248 | 0.6636 |
| `irc_alert` | 3 | `balanced_accuracy` | 0.4531 | 512 | 0.4492 | 0.4391 | 0.5611 | 0.3516 | 0.4927 | 0.4591 | 0.1656 | 0.5795 |
| `irc_alert` | 3 | `closest_pr` | 0.2812 | 512 | 0.4492 | 0.8217 | 0.4644 | 0.7949 | 0.5934 | 0.7121 | 0.0600 | 0.5243 |
| `irc_alert` | 3 | `f1` | 0.2812 | 512 | 0.4492 | 0.8217 | 0.4644 | 0.7949 | 0.5934 | 0.7121 | 0.0600 | 0.5243 |
| `irc_alert` | 3 | `fbeta` | 0.1328 | 512 | 0.4492 | 0.9957 | 0.4481 | 0.9980 | 0.6181 | 0.8001 | -0.0490 | 0.4978 |
| `irc_alert` | 3 | `fixed` | 0.5000 | 512 | 0.4492 | 0.3391 | 0.6393 | 0.2383 | 0.4432 | 0.3743 | 0.2138 | 0.5916 |
| `irc_alert` | 3 | `gmean_pr` | 0.1328 | 512 | 0.4492 | 0.9957 | 0.4481 | 0.9980 | 0.6181 | 0.8001 | -0.0490 | 0.4978 |
| `irc_alert` | 3 | `mcc` | 0.4609 | 512 | 0.4492 | 0.4304 | 0.5928 | 0.3262 | 0.4987 | 0.4554 | 0.2008 | 0.5947 |

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

- Thresholds: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_policy_2b_thresholds_stochastic_smoke.csv`
- Metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_policy_2b_metrics_stochastic_smoke.csv`
- Manifest: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_policy_2b_manifest_stochastic_smoke.json`