# PIPE Neural ODE v1 Rollout Alert Policy Frontier Report

Generated at UTC: `2026-06-15T21:07:58.290705+00:00`

## Scope

This report compares automatic threshold-selection objectives on the validation split and evaluates them on held-out test rows.
It does not adopt a final operational policy; it characterizes the decision frontier between precision and recall.

## Configuration

- Calibrated rows: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_calibrated_backtest_rows.parquet`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Selection objectives: `['fixed', 'fbeta', 'f1', 'mcc', 'balanced_accuracy', 'gmean_pr', 'closest_pr']`
- F-beta beta: `2.0`
- Minimum recall constraint: `None`
- Minimum precision constraint: `None`

## Test Frontier

| event | horizon | policy | threshold | rows | base rate | recall | precision | alert rate | F1 | F2 | MCC | balanced accuracy |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | 1 | `balanced_accuracy` | 0.1429 | 4,673 | 0.1823 | 0.8474 | 0.4797 | 0.3221 | 0.6126 | 0.7348 | 0.5309 | 0.8212 |
| `bloom_h` | 1 | `closest_pr` | 0.4074 | 4,673 | 0.1823 | 0.5939 | 0.6894 | 0.1571 | 0.6381 | 0.6108 | 0.5669 | 0.7671 |
| `bloom_h` | 1 | `f1` | 0.4074 | 4,673 | 0.1823 | 0.5939 | 0.6894 | 0.1571 | 0.6381 | 0.6108 | 0.5669 | 0.7671 |
| `bloom_h` | 1 | `fbeta` | 0.1429 | 4,673 | 0.1823 | 0.8474 | 0.4797 | 0.3221 | 0.6126 | 0.7348 | 0.5309 | 0.8212 |
| `bloom_h` | 1 | `fixed` | 0.3000 | 4,673 | 0.1823 | 0.4472 | 0.7355 | 0.1108 | 0.5562 | 0.4852 | 0.5059 | 0.7057 |
| `bloom_h` | 1 | `gmean_pr` | 0.4074 | 4,673 | 0.1823 | 0.5939 | 0.6894 | 0.1571 | 0.6381 | 0.6108 | 0.5669 | 0.7671 |
| `bloom_h` | 1 | `mcc` | 0.4074 | 4,673 | 0.1823 | 0.5939 | 0.6894 | 0.1571 | 0.6381 | 0.6108 | 0.5669 | 0.7671 |
| `bloom_h` | 2 | `balanced_accuracy` | 0.1429 | 4,710 | 0.1832 | 0.8111 | 0.5236 | 0.2839 | 0.6364 | 0.7308 | 0.5539 | 0.8228 |
| `bloom_h` | 2 | `closest_pr` | 0.3649 | 4,710 | 0.1832 | 0.6246 | 0.6153 | 0.1860 | 0.6199 | 0.6227 | 0.5339 | 0.7685 |
| `bloom_h` | 2 | `f1` | 0.3649 | 4,710 | 0.1832 | 0.6246 | 0.6153 | 0.1860 | 0.6199 | 0.6227 | 0.5339 | 0.7685 |
| `bloom_h` | 2 | `fbeta` | 0.1429 | 4,710 | 0.1832 | 0.8111 | 0.5236 | 0.2839 | 0.6364 | 0.7308 | 0.5539 | 0.8228 |
| `bloom_h` | 2 | `fixed` | 0.3180 | 4,710 | 0.1832 | 0.3244 | 0.7235 | 0.0822 | 0.4480 | 0.3647 | 0.4179 | 0.6483 |
| `bloom_h` | 2 | `gmean_pr` | 0.3649 | 4,710 | 0.1832 | 0.6246 | 0.6153 | 0.1860 | 0.6199 | 0.6227 | 0.5339 | 0.7685 |
| `bloom_h` | 2 | `mcc` | 0.3649 | 4,710 | 0.1832 | 0.6246 | 0.6153 | 0.1860 | 0.6199 | 0.6227 | 0.5339 | 0.7685 |
| `bloom_h` | 3 | `balanced_accuracy` | 0.1508 | 4,757 | 0.1856 | 0.8890 | 0.4465 | 0.3696 | 0.5945 | 0.7420 | 0.5138 | 0.8189 |
| `bloom_h` | 3 | `closest_pr` | 0.2982 | 4,757 | 0.1856 | 0.6840 | 0.5933 | 0.2140 | 0.6355 | 0.6637 | 0.5472 | 0.7886 |
| `bloom_h` | 3 | `f1` | 0.2982 | 4,757 | 0.1856 | 0.6840 | 0.5933 | 0.2140 | 0.6355 | 0.6637 | 0.5472 | 0.7886 |
| `bloom_h` | 3 | `fbeta` | 0.1373 | 4,757 | 0.1856 | 0.9083 | 0.4277 | 0.3942 | 0.5816 | 0.7416 | 0.5023 | 0.8156 |
| `bloom_h` | 3 | `fixed` | 0.3000 | 4,757 | 0.1856 | 0.3262 | 0.6809 | 0.0889 | 0.4410 | 0.3641 | 0.3979 | 0.6457 |
| `bloom_h` | 3 | `gmean_pr` | 0.2982 | 4,757 | 0.1856 | 0.6840 | 0.5933 | 0.2140 | 0.6355 | 0.6637 | 0.5472 | 0.7886 |
| `bloom_h` | 3 | `mcc` | 0.3913 | 4,757 | 0.1856 | 0.6138 | 0.6208 | 0.1835 | 0.6173 | 0.6152 | 0.5307 | 0.7642 |
| `irc_alert` | 1 | `balanced_accuracy` | 0.4141 | 6,145 | 0.4148 | 0.9023 | 0.8065 | 0.4641 | 0.8517 | 0.8814 | 0.7398 | 0.8744 |
| `irc_alert` | 1 | `closest_pr` | 0.4453 | 6,145 | 0.4148 | 0.8905 | 0.8228 | 0.4490 | 0.8553 | 0.8761 | 0.7474 | 0.8773 |
| `irc_alert` | 1 | `f1` | 0.4141 | 6,145 | 0.4148 | 0.9023 | 0.8065 | 0.4641 | 0.8517 | 0.8814 | 0.7398 | 0.8744 |
| `irc_alert` | 1 | `fbeta` | 0.2734 | 6,145 | 0.4148 | 0.9447 | 0.7446 | 0.5263 | 0.8328 | 0.8965 | 0.7055 | 0.8575 |
| `irc_alert` | 1 | `fixed` | 0.5000 | 6,145 | 0.4148 | 0.8694 | 0.8413 | 0.4286 | 0.8551 | 0.8636 | 0.7498 | 0.8766 |
| `irc_alert` | 1 | `gmean_pr` | 0.4141 | 6,145 | 0.4148 | 0.9023 | 0.8065 | 0.4641 | 0.8517 | 0.8814 | 0.7398 | 0.8744 |
| `irc_alert` | 1 | `mcc` | 0.4141 | 6,145 | 0.4148 | 0.9023 | 0.8065 | 0.4641 | 0.8517 | 0.8814 | 0.7398 | 0.8744 |
| `irc_alert` | 2 | `balanced_accuracy` | 0.4531 | 6,145 | 0.4330 | 0.8876 | 0.8081 | 0.4757 | 0.8460 | 0.8705 | 0.7209 | 0.8633 |
| `irc_alert` | 2 | `closest_pr` | 0.4531 | 6,145 | 0.4330 | 0.8876 | 0.8081 | 0.4757 | 0.8460 | 0.8705 | 0.7209 | 0.8633 |
| `irc_alert` | 2 | `f1` | 0.4531 | 6,145 | 0.4330 | 0.8876 | 0.8081 | 0.4757 | 0.8460 | 0.8705 | 0.7209 | 0.8633 |
| `irc_alert` | 2 | `fbeta` | 0.3438 | 6,145 | 0.4330 | 0.9346 | 0.7460 | 0.5426 | 0.8297 | 0.8896 | 0.6878 | 0.8457 |
| `irc_alert` | 2 | `fixed` | 0.5000 | 6,145 | 0.4330 | 0.8598 | 0.8335 | 0.4467 | 0.8465 | 0.8544 | 0.7262 | 0.8643 |
| `irc_alert` | 2 | `gmean_pr` | 0.3984 | 6,145 | 0.4330 | 0.9113 | 0.7802 | 0.5058 | 0.8407 | 0.8817 | 0.7089 | 0.8576 |
| `irc_alert` | 2 | `mcc` | 0.4531 | 6,145 | 0.4330 | 0.8876 | 0.8081 | 0.4757 | 0.8460 | 0.8705 | 0.7209 | 0.8633 |
| `irc_alert` | 3 | `balanced_accuracy` | 0.4844 | 6,145 | 0.4448 | 0.8818 | 0.8194 | 0.4786 | 0.8495 | 0.8686 | 0.7224 | 0.8631 |
| `irc_alert` | 3 | `closest_pr` | 0.4844 | 6,145 | 0.4448 | 0.8818 | 0.8194 | 0.4786 | 0.8495 | 0.8686 | 0.7224 | 0.8631 |
| `irc_alert` | 3 | `f1` | 0.4844 | 6,145 | 0.4448 | 0.8818 | 0.8194 | 0.4786 | 0.8495 | 0.8686 | 0.7224 | 0.8631 |
| `irc_alert` | 3 | `fbeta` | 0.3125 | 6,145 | 0.4448 | 0.9583 | 0.7027 | 0.6065 | 0.8108 | 0.8933 | 0.6445 | 0.8168 |
| `irc_alert` | 3 | `fixed` | 0.5000 | 6,145 | 0.4448 | 0.8745 | 0.8313 | 0.4679 | 0.8524 | 0.8655 | 0.7294 | 0.8662 |
| `irc_alert` | 3 | `gmean_pr` | 0.4531 | 6,145 | 0.4448 | 0.9005 | 0.7995 | 0.5009 | 0.8470 | 0.8783 | 0.7152 | 0.8598 |
| `irc_alert` | 3 | `mcc` | 0.4844 | 6,145 | 0.4448 | 0.8818 | 0.8194 | 0.4786 | 0.8495 | 0.8686 | 0.7224 | 0.8631 |

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
- These policies compare alert decisions; they do not retrain PIPE Neural ODE v1.
- A balanced objective is a modeling choice, not an objective truth; it should be defended by the decision context.

## Outputs

- Thresholds: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_policy_2b_thresholds.csv`
- Metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_policy_2b_metrics.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_policy_2b_manifest.json`