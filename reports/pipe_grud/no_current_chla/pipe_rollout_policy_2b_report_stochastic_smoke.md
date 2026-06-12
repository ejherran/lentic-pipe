# PIPE/GRU-D Rollout Alert Policy Frontier Report

Generated at UTC: `2026-06-12T19:00:04.042223+00:00`

## Scope

This report compares automatic threshold-selection objectives on the validation split and evaluates them on held-out test rows.
It does not adopt a final operational policy; it characterizes the decision frontier between precision and recall.

## Configuration

- Calibrated rows: `reports/pipe_grud/no_current_chla/pipe_rollout_calibrated_backtest_rows_stochastic_smoke.parquet`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Selection objectives: `['fixed', 'fbeta', 'f1', 'mcc', 'balanced_accuracy', 'gmean_pr', 'closest_pr']`
- F-beta beta: `2.0`
- Minimum recall constraint: `None`
- Minimum precision constraint: `None`

## Test Frontier

| event | horizon | policy | threshold | rows | base rate | recall | precision | alert rate | F1 | F2 | MCC | balanced accuracy |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | 1 | `balanced_accuracy` | 0.1604 | 461 | 0.1302 | 0.4833 | 0.2000 | 0.3145 | 0.2829 | 0.3766 | 0.1406 | 0.5970 |
| `bloom_h` | 1 | `closest_pr` | 0.1077 | 461 | 0.1302 | 0.9333 | 0.1308 | 0.9284 | 0.2295 | 0.4192 | 0.0074 | 0.5028 |
| `bloom_h` | 1 | `f1` | 0.1172 | 461 | 0.1302 | 0.8333 | 0.1340 | 0.8091 | 0.2309 | 0.4078 | 0.0238 | 0.5139 |
| `bloom_h` | 1 | `fbeta` | 0.1000 | 461 | 0.1302 | 0.9667 | 0.1278 | 0.9848 | 0.2257 | 0.4179 | -0.0574 | 0.4896 |
| `bloom_h` | 1 | `gmean_pr` | 0.1000 | 461 | 0.1302 | 0.9667 | 0.1278 | 0.9848 | 0.2257 | 0.4179 | -0.0574 | 0.4896 |
| `bloom_h` | 1 | `mcc` | 0.1604 | 461 | 0.1302 | 0.4833 | 0.2000 | 0.3145 | 0.2829 | 0.3766 | 0.1406 | 0.5970 |
| `bloom_h` | 2 | `balanced_accuracy` | 0.1792 | 460 | 0.1348 | 0.5968 | 0.1689 | 0.4761 | 0.2633 | 0.3961 | 0.0954 | 0.5697 |
| `bloom_h` | 2 | `closest_pr` | 0.1084 | 460 | 0.1348 | 1.0000 | 0.1369 | 0.9848 | 0.2408 | 0.4422 | 0.0491 | 0.5088 |
| `bloom_h` | 2 | `f1` | 0.1792 | 460 | 0.1348 | 0.5968 | 0.1689 | 0.4761 | 0.2633 | 0.3961 | 0.0954 | 0.5697 |
| `bloom_h` | 2 | `fbeta` | 0.1084 | 460 | 0.1348 | 1.0000 | 0.1369 | 0.9848 | 0.2408 | 0.4422 | 0.0491 | 0.5088 |
| `bloom_h` | 2 | `gmean_pr` | 0.1084 | 460 | 0.1348 | 1.0000 | 0.1369 | 0.9848 | 0.2408 | 0.4422 | 0.0491 | 0.5088 |
| `bloom_h` | 2 | `mcc` | 0.1792 | 460 | 0.1348 | 0.5968 | 0.1689 | 0.4761 | 0.2633 | 0.3961 | 0.0954 | 0.5697 |
| `bloom_h` | 3 | `balanced_accuracy` | 0.1592 | 467 | 0.1328 | 0.7581 | 0.1416 | 0.7109 | 0.2386 | 0.4052 | 0.0407 | 0.5272 |
| `bloom_h` | 3 | `closest_pr` | 0.1592 | 467 | 0.1328 | 0.7581 | 0.1416 | 0.7109 | 0.2386 | 0.4052 | 0.0407 | 0.5272 |
| `bloom_h` | 3 | `f1` | 0.1592 | 467 | 0.1328 | 0.7581 | 0.1416 | 0.7109 | 0.2386 | 0.4052 | 0.0407 | 0.5272 |
| `bloom_h` | 3 | `fbeta` | 0.1592 | 467 | 0.1328 | 0.7581 | 0.1416 | 0.7109 | 0.2386 | 0.4052 | 0.0407 | 0.5272 |
| `bloom_h` | 3 | `gmean_pr` | 0.0927 | 467 | 0.1328 | 1.0000 | 0.1345 | 0.9872 | 0.2371 | 0.4372 | 0.0446 | 0.5074 |
| `bloom_h` | 3 | `mcc` | 0.1592 | 467 | 0.1328 | 0.7581 | 0.1416 | 0.7109 | 0.2386 | 0.4052 | 0.0407 | 0.5272 |
| `irc_alert` | 1 | `balanced_accuracy` | 0.4531 | 512 | 0.3379 | 0.3584 | 0.5586 | 0.2168 | 0.4366 | 0.3861 | 0.2455 | 0.6069 |
| `irc_alert` | 1 | `closest_pr` | 0.3203 | 512 | 0.3379 | 0.8382 | 0.3699 | 0.7656 | 0.5133 | 0.6688 | 0.1223 | 0.5548 |
| `irc_alert` | 1 | `f1` | 0.2891 | 512 | 0.3379 | 0.8960 | 0.3563 | 0.8496 | 0.5099 | 0.6877 | 0.0926 | 0.5350 |
| `irc_alert` | 1 | `fbeta` | 0.0469 | 512 | 0.3379 | 0.9827 | 0.3373 | 0.9844 | 0.5022 | 0.7107 | -0.0099 | 0.4987 |
| `irc_alert` | 1 | `fixed` | 0.5000 | 512 | 0.3379 | 0.3006 | 0.5977 | 0.1699 | 0.4000 | 0.3338 | 0.2485 | 0.5987 |
| `irc_alert` | 1 | `gmean_pr` | 0.0469 | 512 | 0.3379 | 0.9827 | 0.3373 | 0.9844 | 0.5022 | 0.7107 | -0.0099 | 0.4987 |
| `irc_alert` | 1 | `mcc` | 0.5234 | 512 | 0.3379 | 0.2775 | 0.6076 | 0.1543 | 0.3810 | 0.3113 | 0.2436 | 0.5930 |
| `irc_alert` | 2 | `balanced_accuracy` | 0.3281 | 512 | 0.3477 | 0.5169 | 0.4144 | 0.4336 | 0.4600 | 0.4925 | 0.1227 | 0.5638 |
| `irc_alert` | 2 | `closest_pr` | 0.2656 | 512 | 0.3477 | 0.7978 | 0.3568 | 0.7773 | 0.4931 | 0.6396 | 0.0358 | 0.5156 |
| `irc_alert` | 2 | `f1` | 0.2656 | 512 | 0.3477 | 0.7978 | 0.3568 | 0.7773 | 0.4931 | 0.6396 | 0.0358 | 0.5156 |
| `irc_alert` | 2 | `fbeta` | 0.0938 | 512 | 0.3477 | 0.9888 | 0.3478 | 0.9883 | 0.5146 | 0.7225 | 0.0033 | 0.5004 |
| `irc_alert` | 2 | `fixed` | 0.5000 | 512 | 0.3477 | 0.2303 | 0.6508 | 0.1230 | 0.3402 | 0.2645 | 0.2384 | 0.5822 |
| `irc_alert` | 2 | `gmean_pr` | 0.0938 | 512 | 0.3477 | 0.9888 | 0.3478 | 0.9883 | 0.5146 | 0.7225 | 0.0033 | 0.5004 |
| `irc_alert` | 2 | `mcc` | 0.6094 | 512 | 0.3477 | 0.1461 | 0.8966 | 0.0566 | 0.2512 | 0.1754 | 0.2824 | 0.5685 |
| `irc_alert` | 3 | `balanced_accuracy` | 0.3203 | 512 | 0.3535 | 0.3757 | 0.4857 | 0.2734 | 0.4237 | 0.3935 | 0.1696 | 0.5791 |
| `irc_alert` | 3 | `closest_pr` | 0.2188 | 512 | 0.3535 | 0.8343 | 0.3561 | 0.8281 | 0.4992 | 0.6577 | 0.0120 | 0.5047 |
| `irc_alert` | 3 | `f1` | 0.1328 | 512 | 0.3535 | 0.9890 | 0.3538 | 0.9883 | 0.5211 | 0.7276 | 0.0046 | 0.5005 |
| `irc_alert` | 3 | `fbeta` | 0.1328 | 512 | 0.3535 | 0.9890 | 0.3538 | 0.9883 | 0.5211 | 0.7276 | 0.0046 | 0.5005 |
| `irc_alert` | 3 | `fixed` | 0.5000 | 512 | 0.3535 | 0.1160 | 0.8077 | 0.0508 | 0.2029 | 0.1400 | 0.2197 | 0.5505 |
| `irc_alert` | 3 | `gmean_pr` | 0.1328 | 512 | 0.3535 | 0.9890 | 0.3538 | 0.9883 | 0.5211 | 0.7276 | 0.0046 | 0.5005 |
| `irc_alert` | 3 | `mcc` | 0.4297 | 512 | 0.3535 | 0.1768 | 0.6667 | 0.0938 | 0.2795 | 0.2073 | 0.2107 | 0.5642 |

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

- Thresholds: `reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_thresholds_stochastic_smoke.csv`
- Metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_metrics_stochastic_smoke.csv`
- Manifest: `reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_manifest_stochastic_smoke.json`