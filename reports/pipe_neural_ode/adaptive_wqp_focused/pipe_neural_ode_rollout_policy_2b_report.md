# PIPE Neural ODE Rollout Alert Policy Frontier Report

Generated at UTC: `2026-06-15T19:56:26.312533+00:00`

## Scope

This report compares automatic threshold-selection objectives on the validation split and evaluates them on held-out test rows.
It does not adopt a final operational policy; it characterizes the decision frontier between precision and recall.

## Configuration

- Calibrated rows: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_calibrated_backtest_rows.parquet`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Selection objectives: `['fixed', 'fbeta', 'f1', 'mcc', 'balanced_accuracy', 'gmean_pr', 'closest_pr']`
- F-beta beta: `2.0`
- Minimum recall constraint: `None`
- Minimum precision constraint: `None`

## Test Frontier

| event | horizon | policy | threshold | rows | base rate | recall | precision | alert rate | F1 | F2 | MCC | balanced accuracy |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | 1 | `balanced_accuracy` | 0.1409 | 4,673 | 0.1823 | 0.7981 | 0.4680 | 0.3109 | 0.5900 | 0.6994 | 0.4970 | 0.7979 |
| `bloom_h` | 1 | `closest_pr` | 0.3008 | 4,673 | 0.1823 | 0.6725 | 0.5859 | 0.2093 | 0.6262 | 0.6532 | 0.5377 | 0.7833 |
| `bloom_h` | 1 | `f1` | 0.3008 | 4,673 | 0.1823 | 0.6725 | 0.5859 | 0.2093 | 0.6262 | 0.6532 | 0.5377 | 0.7833 |
| `bloom_h` | 1 | `fbeta` | 0.1409 | 4,673 | 0.1823 | 0.7981 | 0.4680 | 0.3109 | 0.5900 | 0.6994 | 0.4970 | 0.7979 |
| `bloom_h` | 1 | `fixed` | 0.3000 | 4,673 | 0.1823 | 0.4965 | 0.6736 | 0.1344 | 0.5716 | 0.5240 | 0.5013 | 0.7214 |
| `bloom_h` | 1 | `gmean_pr` | 0.2294 | 4,673 | 0.1823 | 0.7007 | 0.5637 | 0.2266 | 0.6248 | 0.6682 | 0.5347 | 0.7899 |
| `bloom_h` | 1 | `mcc` | 0.3008 | 4,673 | 0.1823 | 0.6725 | 0.5859 | 0.2093 | 0.6262 | 0.6532 | 0.5377 | 0.7833 |
| `bloom_h` | 2 | `balanced_accuracy` | 0.1429 | 4,710 | 0.1832 | 0.7822 | 0.4720 | 0.3036 | 0.5887 | 0.6913 | 0.4929 | 0.7929 |
| `bloom_h` | 2 | `closest_pr` | 0.2167 | 4,710 | 0.1832 | 0.7486 | 0.4846 | 0.2830 | 0.5883 | 0.6750 | 0.4895 | 0.7850 |
| `bloom_h` | 2 | `f1` | 0.2778 | 4,710 | 0.1832 | 0.7207 | 0.4968 | 0.2658 | 0.5882 | 0.6611 | 0.4877 | 0.7785 |
| `bloom_h` | 2 | `fbeta` | 0.1429 | 4,710 | 0.1832 | 0.7822 | 0.4720 | 0.3036 | 0.5887 | 0.6913 | 0.4929 | 0.7929 |
| `bloom_h` | 2 | `fixed` | 0.3180 | 4,710 | 0.1832 | 0.2665 | 0.7034 | 0.0694 | 0.3866 | 0.3043 | 0.3672 | 0.6206 |
| `bloom_h` | 2 | `gmean_pr` | 0.1923 | 4,710 | 0.1832 | 0.7694 | 0.4787 | 0.2945 | 0.5902 | 0.6861 | 0.4935 | 0.7907 |
| `bloom_h` | 2 | `mcc` | 0.2778 | 4,710 | 0.1832 | 0.7207 | 0.4968 | 0.2658 | 0.5882 | 0.6611 | 0.4877 | 0.7785 |
| `bloom_h` | 3 | `balanced_accuracy` | 0.1983 | 4,757 | 0.1856 | 0.8448 | 0.4229 | 0.3708 | 0.5637 | 0.7043 | 0.4685 | 0.7910 |
| `bloom_h` | 3 | `closest_pr` | 0.1983 | 4,757 | 0.1856 | 0.8448 | 0.4229 | 0.3708 | 0.5637 | 0.7043 | 0.4685 | 0.7910 |
| `bloom_h` | 3 | `f1` | 0.2481 | 4,757 | 0.1856 | 0.7984 | 0.4513 | 0.3284 | 0.5767 | 0.6920 | 0.4779 | 0.7886 |
| `bloom_h` | 3 | `fbeta` | 0.1304 | 4,757 | 0.1856 | 0.8505 | 0.4158 | 0.3797 | 0.5586 | 0.7034 | 0.4632 | 0.7891 |
| `bloom_h` | 3 | `fixed` | 0.3000 | 4,757 | 0.1856 | 0.2231 | 0.7164 | 0.0578 | 0.3402 | 0.2587 | 0.3381 | 0.6015 |
| `bloom_h` | 3 | `gmean_pr` | 0.1983 | 4,757 | 0.1856 | 0.8448 | 0.4229 | 0.3708 | 0.5637 | 0.7043 | 0.4685 | 0.7910 |
| `bloom_h` | 3 | `mcc` | 0.1983 | 4,757 | 0.1856 | 0.8448 | 0.4229 | 0.3708 | 0.5637 | 0.7043 | 0.4685 | 0.7910 |
| `irc_alert` | 1 | `balanced_accuracy` | 0.3672 | 6,145 | 0.4148 | 0.8737 | 0.7908 | 0.4583 | 0.8302 | 0.8557 | 0.7020 | 0.8549 |
| `irc_alert` | 1 | `closest_pr` | 0.3672 | 6,145 | 0.4148 | 0.8737 | 0.7908 | 0.4583 | 0.8302 | 0.8557 | 0.7020 | 0.8549 |
| `irc_alert` | 1 | `f1` | 0.3672 | 6,145 | 0.4148 | 0.8737 | 0.7908 | 0.4583 | 0.8302 | 0.8557 | 0.7020 | 0.8549 |
| `irc_alert` | 1 | `fbeta` | 0.1797 | 6,145 | 0.4148 | 0.9372 | 0.6699 | 0.5803 | 0.7814 | 0.8680 | 0.6089 | 0.8050 |
| `irc_alert` | 1 | `fixed` | 0.5000 | 6,145 | 0.4148 | 0.8223 | 0.8374 | 0.4073 | 0.8298 | 0.8253 | 0.7111 | 0.8546 |
| `irc_alert` | 1 | `gmean_pr` | 0.3672 | 6,145 | 0.4148 | 0.8737 | 0.7908 | 0.4583 | 0.8302 | 0.8557 | 0.7020 | 0.8549 |
| `irc_alert` | 1 | `mcc` | 0.3672 | 6,145 | 0.4148 | 0.8737 | 0.7908 | 0.4583 | 0.8302 | 0.8557 | 0.7020 | 0.8549 |
| `irc_alert` | 2 | `balanced_accuracy` | 0.4766 | 6,145 | 0.4330 | 0.7738 | 0.7910 | 0.4236 | 0.7823 | 0.7772 | 0.6193 | 0.8088 |
| `irc_alert` | 2 | `closest_pr` | 0.3516 | 6,145 | 0.4330 | 0.8497 | 0.7256 | 0.5071 | 0.7828 | 0.8216 | 0.5989 | 0.8021 |
| `irc_alert` | 2 | `f1` | 0.3203 | 6,145 | 0.4330 | 0.8670 | 0.7051 | 0.5325 | 0.7777 | 0.8289 | 0.5859 | 0.7950 |
| `irc_alert` | 2 | `fbeta` | 0.1953 | 6,145 | 0.4330 | 0.9402 | 0.6095 | 0.6680 | 0.7396 | 0.8482 | 0.5052 | 0.7401 |
| `irc_alert` | 2 | `fixed` | 0.5000 | 6,145 | 0.4330 | 0.7580 | 0.8020 | 0.4093 | 0.7794 | 0.7664 | 0.6198 | 0.8075 |
| `irc_alert` | 2 | `gmean_pr` | 0.3203 | 6,145 | 0.4330 | 0.8670 | 0.7051 | 0.5325 | 0.7777 | 0.8289 | 0.5859 | 0.7950 |
| `irc_alert` | 2 | `mcc` | 0.5391 | 6,145 | 0.4330 | 0.7336 | 0.8254 | 0.3849 | 0.7768 | 0.7502 | 0.6263 | 0.8075 |
| `irc_alert` | 3 | `balanced_accuracy` | 0.4609 | 6,145 | 0.4448 | 0.7622 | 0.7769 | 0.4363 | 0.7695 | 0.7651 | 0.5881 | 0.7935 |
| `irc_alert` | 3 | `closest_pr` | 0.3906 | 6,145 | 0.4448 | 0.8288 | 0.7143 | 0.5160 | 0.7673 | 0.8030 | 0.5601 | 0.7816 |
| `irc_alert` | 3 | `f1` | 0.2969 | 6,145 | 0.4448 | 0.9074 | 0.6462 | 0.6246 | 0.7548 | 0.8395 | 0.5228 | 0.7547 |
| `irc_alert` | 3 | `fbeta` | 0.1719 | 6,145 | 0.4448 | 0.9759 | 0.5517 | 0.7867 | 0.7049 | 0.8458 | 0.4133 | 0.6704 |
| `irc_alert` | 3 | `fixed` | 0.5000 | 6,145 | 0.4448 | 0.7186 | 0.8076 | 0.3958 | 0.7605 | 0.7348 | 0.5909 | 0.7907 |
| `irc_alert` | 3 | `gmean_pr` | 0.2656 | 6,145 | 0.4448 | 0.9323 | 0.6273 | 0.6610 | 0.7500 | 0.8497 | 0.5129 | 0.7443 |
| `irc_alert` | 3 | `mcc` | 0.4609 | 6,145 | 0.4448 | 0.7622 | 0.7769 | 0.4363 | 0.7695 | 0.7651 | 0.5881 | 0.7935 |

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
- These policies compare alert decisions; they do not retrain PIPE Neural ODE.
- A balanced objective is a modeling choice, not an objective truth; it should be defended by the decision context.

## Outputs

- Thresholds: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_policy_2b_thresholds.csv`
- Metrics: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_policy_2b_metrics.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_policy_2b_manifest.json`