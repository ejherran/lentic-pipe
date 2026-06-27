# PIPE Neural ODE v2 direct Rollout Alert Policy Frontier Report

Generated at UTC: `2026-06-27T15:38:23.046121+00:00`

## Scope

This report compares automatic threshold-selection objectives on the validation split and evaluates them on held-out test rows.
It does not adopt a final operational policy; it characterizes the decision frontier between precision and recall.

## Configuration

- Calibrated rows: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_calibrated_backtest_rows.parquet`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Selection objectives: `['fixed', 'fbeta', 'f1', 'mcc', 'balanced_accuracy', 'gmean_pr', 'closest_pr']`
- F-beta beta: `2.0`
- Minimum recall constraint: `None`
- Minimum precision constraint: `None`

## Test Frontier

| event | horizon | policy | threshold | rows | base rate | recall | precision | alert rate | F1 | F2 | MCC | balanced accuracy |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | 1 | `balanced_accuracy` | 0.1406 | 4,673 | 0.1823 | 0.8369 | 0.5100 | 0.2992 | 0.6338 | 0.7418 | 0.5545 | 0.8288 |
| `bloom_h` | 1 | `closest_pr` | 0.3485 | 4,673 | 0.1823 | 0.6502 | 0.6580 | 0.1802 | 0.6541 | 0.6518 | 0.5775 | 0.7874 |
| `bloom_h` | 1 | `f1` | 0.3485 | 4,673 | 0.1823 | 0.6502 | 0.6580 | 0.1802 | 0.6541 | 0.6518 | 0.5775 | 0.7874 |
| `bloom_h` | 1 | `fbeta` | 0.1406 | 4,673 | 0.1823 | 0.8369 | 0.5100 | 0.2992 | 0.6338 | 0.7418 | 0.5545 | 0.8288 |
| `bloom_h` | 1 | `gmean_pr` | 0.2353 | 4,673 | 0.1823 | 0.7559 | 0.5576 | 0.2472 | 0.6418 | 0.7057 | 0.5569 | 0.8111 |
| `bloom_h` | 1 | `mcc` | 0.3485 | 4,673 | 0.1823 | 0.6502 | 0.6580 | 0.1802 | 0.6541 | 0.6518 | 0.5775 | 0.7874 |
| `bloom_h` | 2 | `balanced_accuracy` | 0.1414 | 4,710 | 0.1832 | 0.8783 | 0.4547 | 0.3539 | 0.5992 | 0.7404 | 0.5194 | 0.8210 |
| `bloom_h` | 2 | `closest_pr` | 0.3038 | 4,710 | 0.1832 | 0.6605 | 0.6278 | 0.1928 | 0.6437 | 0.6537 | 0.5616 | 0.7863 |
| `bloom_h` | 2 | `f1` | 0.3038 | 4,710 | 0.1832 | 0.6605 | 0.6278 | 0.1928 | 0.6437 | 0.6537 | 0.5616 | 0.7863 |
| `bloom_h` | 2 | `fbeta` | 0.1414 | 4,710 | 0.1832 | 0.8783 | 0.4547 | 0.3539 | 0.5992 | 0.7404 | 0.5194 | 0.8210 |
| `bloom_h` | 2 | `gmean_pr` | 0.3038 | 4,710 | 0.1832 | 0.6605 | 0.6278 | 0.1928 | 0.6437 | 0.6537 | 0.5616 | 0.7863 |
| `bloom_h` | 2 | `mcc` | 0.4000 | 4,710 | 0.1832 | 0.6049 | 0.6501 | 0.1705 | 0.6267 | 0.6134 | 0.5471 | 0.7659 |
| `bloom_h` | 3 | `balanced_accuracy` | 0.1441 | 4,757 | 0.1856 | 0.8550 | 0.4618 | 0.3437 | 0.5997 | 0.7306 | 0.5140 | 0.8139 |
| `bloom_h` | 3 | `closest_pr` | 0.3000 | 4,757 | 0.1856 | 0.7089 | 0.5934 | 0.2218 | 0.6460 | 0.6824 | 0.5598 | 0.7991 |
| `bloom_h` | 3 | `f1` | 0.3000 | 4,757 | 0.1856 | 0.7089 | 0.5934 | 0.2218 | 0.6460 | 0.6824 | 0.5598 | 0.7991 |
| `bloom_h` | 3 | `fbeta` | 0.1260 | 4,757 | 0.1856 | 0.8822 | 0.4371 | 0.3746 | 0.5846 | 0.7330 | 0.5007 | 0.8117 |
| `bloom_h` | 3 | `gmean_pr` | 0.3000 | 4,757 | 0.1856 | 0.7089 | 0.5934 | 0.2218 | 0.6460 | 0.6824 | 0.5598 | 0.7991 |
| `bloom_h` | 3 | `mcc` | 0.3000 | 4,757 | 0.1856 | 0.7089 | 0.5934 | 0.2218 | 0.6460 | 0.6824 | 0.5598 | 0.7991 |
| `irc_alert` | 1 | `balanced_accuracy` | 0.4609 | 6,145 | 0.4148 | 0.8894 | 0.8196 | 0.4501 | 0.8531 | 0.8745 | 0.7433 | 0.8753 |
| `irc_alert` | 1 | `closest_pr` | 0.4766 | 6,145 | 0.4148 | 0.8823 | 0.8284 | 0.4418 | 0.8545 | 0.8710 | 0.7468 | 0.8764 |
| `irc_alert` | 1 | `f1` | 0.4609 | 6,145 | 0.4148 | 0.8894 | 0.8196 | 0.4501 | 0.8531 | 0.8745 | 0.7433 | 0.8753 |
| `irc_alert` | 1 | `fbeta` | 0.2422 | 6,145 | 0.4148 | 0.9478 | 0.7205 | 0.5456 | 0.8187 | 0.8916 | 0.6800 | 0.8436 |
| `irc_alert` | 1 | `fixed` | 0.5000 | 6,145 | 0.4148 | 0.8721 | 0.8382 | 0.4316 | 0.8548 | 0.8651 | 0.7488 | 0.8764 |
| `irc_alert` | 1 | `gmean_pr` | 0.4609 | 6,145 | 0.4148 | 0.8894 | 0.8196 | 0.4501 | 0.8531 | 0.8745 | 0.7433 | 0.8753 |
| `irc_alert` | 1 | `mcc` | 0.5469 | 6,145 | 0.4148 | 0.8482 | 0.8559 | 0.4111 | 0.8520 | 0.8497 | 0.7480 | 0.8735 |
| `irc_alert` | 2 | `balanced_accuracy` | 0.4766 | 6,145 | 0.4330 | 0.8790 | 0.8187 | 0.4649 | 0.8478 | 0.8662 | 0.7255 | 0.8652 |
| `irc_alert` | 2 | `closest_pr` | 0.4766 | 6,145 | 0.4330 | 0.8790 | 0.8187 | 0.4649 | 0.8478 | 0.8662 | 0.7255 | 0.8652 |
| `irc_alert` | 2 | `f1` | 0.4297 | 6,145 | 0.4330 | 0.8993 | 0.8014 | 0.4859 | 0.8475 | 0.8778 | 0.7228 | 0.8645 |
| `irc_alert` | 2 | `fbeta` | 0.1875 | 6,145 | 0.4330 | 0.9590 | 0.6809 | 0.6099 | 0.7964 | 0.8866 | 0.6255 | 0.8079 |
| `irc_alert` | 2 | `fixed` | 0.5000 | 6,145 | 0.4330 | 0.8715 | 0.8297 | 0.4548 | 0.8501 | 0.8628 | 0.7312 | 0.8674 |
| `irc_alert` | 2 | `gmean_pr` | 0.4297 | 6,145 | 0.4330 | 0.8993 | 0.8014 | 0.4859 | 0.8475 | 0.8778 | 0.7228 | 0.8645 |
| `irc_alert` | 2 | `mcc` | 0.4766 | 6,145 | 0.4330 | 0.8790 | 0.8187 | 0.4649 | 0.8478 | 0.8662 | 0.7255 | 0.8652 |
| `irc_alert` | 3 | `balanced_accuracy` | 0.3906 | 6,145 | 0.4448 | 0.9184 | 0.7678 | 0.5320 | 0.8364 | 0.8837 | 0.6931 | 0.8480 |
| `irc_alert` | 3 | `closest_pr` | 0.3984 | 6,145 | 0.4448 | 0.9166 | 0.7729 | 0.5274 | 0.8386 | 0.8837 | 0.6976 | 0.8504 |
| `irc_alert` | 3 | `f1` | 0.3906 | 6,145 | 0.4448 | 0.9184 | 0.7678 | 0.5320 | 0.8364 | 0.8837 | 0.6931 | 0.8480 |
| `irc_alert` | 3 | `fbeta` | 0.2344 | 6,145 | 0.4448 | 0.9572 | 0.6895 | 0.6174 | 0.8016 | 0.8882 | 0.6257 | 0.8060 |
| `irc_alert` | 3 | `fixed` | 0.5000 | 6,145 | 0.4448 | 0.8771 | 0.8271 | 0.4716 | 0.8514 | 0.8666 | 0.7269 | 0.8651 |
| `irc_alert` | 3 | `gmean_pr` | 0.3906 | 6,145 | 0.4448 | 0.9184 | 0.7678 | 0.5320 | 0.8364 | 0.8837 | 0.6931 | 0.8480 |
| `irc_alert` | 3 | `mcc` | 0.3906 | 6,145 | 0.4448 | 0.9184 | 0.7678 | 0.5320 | 0.8364 | 0.8837 | 0.6931 | 0.8480 |

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
- These policies compare alert decisions; they do not retrain PIPE Neural ODE v2 direct.
- A balanced objective is a modeling choice, not an objective truth; it should be defended by the decision context.

## Outputs

- Thresholds: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_alert_policy_2b_thresholds.csv`
- Metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_alert_policy_2b_metrics.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_alert_policy_2b_manifest.json`