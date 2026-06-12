# PIPE/GRU-D Rollout Alert Policy Frontier Report

Generated at UTC: `2026-06-12T15:38:43.609680+00:00`

## Scope

This report compares automatic threshold-selection objectives on the validation split and evaluates them on held-out test rows.
It does not adopt a final operational policy; it characterizes the decision frontier between precision and recall.

## Configuration

- Calibrated rows: `reports/pipe_grud/pipe_rollout_calibrated_backtest_rows.parquet`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Selection objectives: `['fixed', 'fbeta', 'f1', 'mcc', 'balanced_accuracy', 'gmean_pr', 'closest_pr']`
- F-beta beta: `2.0`
- Minimum recall constraint: `None`
- Minimum precision constraint: `None`

## Test Frontier

| event | horizon | policy | threshold | rows | base rate | recall | precision | alert rate | F1 | F2 | MCC | balanced accuracy |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | 1 | `balanced_accuracy` | 0.1538 | 11,852 | 0.1243 | 0.8242 | 0.4678 | 0.2190 | 0.5969 | 0.7152 | 0.5513 | 0.8456 |
| `bloom_h` | 1 | `closest_pr` | 0.2927 | 11,852 | 0.1243 | 0.6782 | 0.6088 | 0.1385 | 0.6416 | 0.6631 | 0.5887 | 0.8082 |
| `bloom_h` | 1 | `f1` | 0.3490 | 11,852 | 0.1243 | 0.6735 | 0.6120 | 0.1368 | 0.6412 | 0.6602 | 0.5884 | 0.8064 |
| `bloom_h` | 1 | `fbeta` | 0.1538 | 11,852 | 0.1243 | 0.8242 | 0.4678 | 0.2190 | 0.5969 | 0.7152 | 0.5513 | 0.8456 |
| `bloom_h` | 1 | `fixed` | 0.3000 | 11,852 | 0.1243 | 0.6083 | 0.6752 | 0.1120 | 0.6400 | 0.6206 | 0.5930 | 0.7834 |
| `bloom_h` | 1 | `gmean_pr` | 0.2927 | 11,852 | 0.1243 | 0.6782 | 0.6088 | 0.1385 | 0.6416 | 0.6631 | 0.5887 | 0.8082 |
| `bloom_h` | 1 | `mcc` | 0.3490 | 11,852 | 0.1243 | 0.6735 | 0.6120 | 0.1368 | 0.6412 | 0.6602 | 0.5884 | 0.8064 |
| `bloom_h` | 2 | `balanced_accuracy` | 0.1649 | 11,891 | 0.1298 | 0.8569 | 0.4204 | 0.2647 | 0.5641 | 0.7095 | 0.5186 | 0.8403 |
| `bloom_h` | 2 | `closest_pr` | 0.2632 | 11,891 | 0.1298 | 0.7137 | 0.5357 | 0.1730 | 0.6121 | 0.6693 | 0.5523 | 0.8107 |
| `bloom_h` | 2 | `f1` | 0.2836 | 11,891 | 0.1298 | 0.6885 | 0.5542 | 0.1613 | 0.6141 | 0.6567 | 0.5537 | 0.8029 |
| `bloom_h` | 2 | `fbeta` | 0.1649 | 11,891 | 0.1298 | 0.8569 | 0.4204 | 0.2647 | 0.5641 | 0.7095 | 0.5186 | 0.8403 |
| `bloom_h` | 2 | `fixed` | 0.3180 | 11,891 | 0.1298 | 0.3543 | 0.7503 | 0.0613 | 0.4813 | 0.3961 | 0.4718 | 0.6683 |
| `bloom_h` | 2 | `gmean_pr` | 0.2632 | 11,891 | 0.1298 | 0.7137 | 0.5357 | 0.1730 | 0.6121 | 0.6693 | 0.5523 | 0.8107 |
| `bloom_h` | 2 | `mcc` | 0.3333 | 11,891 | 0.1298 | 0.5738 | 0.6347 | 0.1174 | 0.6027 | 0.5851 | 0.5477 | 0.7623 |
| `bloom_h` | 3 | `balanced_accuracy` | 0.1436 | 11,939 | 0.1335 | 0.8601 | 0.3832 | 0.2997 | 0.5302 | 0.6887 | 0.4802 | 0.8234 |
| `bloom_h` | 3 | `closest_pr` | 0.2714 | 11,939 | 0.1335 | 0.7183 | 0.5037 | 0.1904 | 0.5922 | 0.6619 | 0.5278 | 0.8046 |
| `bloom_h` | 3 | `f1` | 0.2714 | 11,939 | 0.1335 | 0.7183 | 0.5037 | 0.1904 | 0.5922 | 0.6619 | 0.5278 | 0.8046 |
| `bloom_h` | 3 | `fbeta` | 0.1300 | 11,939 | 0.1335 | 0.8902 | 0.3615 | 0.3288 | 0.5142 | 0.6888 | 0.4692 | 0.8240 |
| `bloom_h` | 3 | `fixed` | 0.3000 | 11,939 | 0.1335 | 0.2880 | 0.7403 | 0.0519 | 0.4146 | 0.3280 | 0.4175 | 0.6362 |
| `bloom_h` | 3 | `gmean_pr` | 0.2308 | 11,939 | 0.1335 | 0.7604 | 0.4783 | 0.2122 | 0.5872 | 0.6801 | 0.5262 | 0.8163 |
| `bloom_h` | 3 | `mcc` | 0.2714 | 11,939 | 0.1335 | 0.7183 | 0.5037 | 0.1904 | 0.5922 | 0.6619 | 0.5278 | 0.8046 |
| `irc_alert` | 1 | `balanced_accuracy` | 0.3125 | 13,327 | 0.3335 | 0.8679 | 0.7552 | 0.3832 | 0.8077 | 0.8428 | 0.7052 | 0.8636 |
| `irc_alert` | 1 | `closest_pr` | 0.3594 | 13,327 | 0.3335 | 0.8499 | 0.7788 | 0.3639 | 0.8128 | 0.8347 | 0.7145 | 0.8646 |
| `irc_alert` | 1 | `f1` | 0.3359 | 13,327 | 0.3335 | 0.8594 | 0.7667 | 0.3738 | 0.8104 | 0.8391 | 0.7100 | 0.8643 |
| `irc_alert` | 1 | `fbeta` | 0.1172 | 13,327 | 0.3335 | 0.9386 | 0.6262 | 0.4998 | 0.7512 | 0.8534 | 0.6207 | 0.8291 |
| `irc_alert` | 1 | `fixed` | 0.5000 | 13,327 | 0.3335 | 0.7826 | 0.8337 | 0.3130 | 0.8073 | 0.7923 | 0.7162 | 0.8523 |
| `irc_alert` | 1 | `gmean_pr` | 0.3125 | 13,327 | 0.3335 | 0.8679 | 0.7552 | 0.3832 | 0.8077 | 0.8428 | 0.7052 | 0.8636 |
| `irc_alert` | 1 | `mcc` | 0.4688 | 13,327 | 0.3335 | 0.8006 | 0.8223 | 0.3247 | 0.8113 | 0.8049 | 0.7189 | 0.8570 |
| `irc_alert` | 2 | `balanced_accuracy` | 0.2812 | 13,327 | 0.3464 | 0.8741 | 0.7021 | 0.4312 | 0.7787 | 0.8333 | 0.6510 | 0.8388 |
| `irc_alert` | 2 | `closest_pr` | 0.3594 | 13,327 | 0.3464 | 0.8250 | 0.7622 | 0.3749 | 0.7923 | 0.8116 | 0.6768 | 0.8443 |
| `irc_alert` | 2 | `f1` | 0.2812 | 13,327 | 0.3464 | 0.8741 | 0.7021 | 0.4312 | 0.7787 | 0.8333 | 0.6510 | 0.8388 |
| `irc_alert` | 2 | `fbeta` | 0.1250 | 13,327 | 0.3464 | 0.9565 | 0.5776 | 0.5736 | 0.7202 | 0.8455 | 0.5636 | 0.7929 |
| `irc_alert` | 2 | `fixed` | 0.5000 | 13,327 | 0.3464 | 0.7244 | 0.8379 | 0.2995 | 0.7770 | 0.7446 | 0.6754 | 0.8251 |
| `irc_alert` | 2 | `gmean_pr` | 0.2734 | 13,327 | 0.3464 | 0.8787 | 0.6977 | 0.4362 | 0.7778 | 0.8354 | 0.6495 | 0.8385 |
| `irc_alert` | 2 | `mcc` | 0.4062 | 13,327 | 0.3464 | 0.7955 | 0.7895 | 0.3490 | 0.7925 | 0.7943 | 0.6819 | 0.8416 |
| `irc_alert` | 3 | `balanced_accuracy` | 0.3281 | 13,327 | 0.3564 | 0.8539 | 0.7305 | 0.4166 | 0.7874 | 0.8260 | 0.6601 | 0.8397 |
| `irc_alert` | 3 | `closest_pr` | 0.3281 | 13,327 | 0.3564 | 0.8539 | 0.7305 | 0.4166 | 0.7874 | 0.8260 | 0.6601 | 0.8397 |
| `irc_alert` | 3 | `f1` | 0.3281 | 13,327 | 0.3564 | 0.8539 | 0.7305 | 0.4166 | 0.7874 | 0.8260 | 0.6601 | 0.8397 |
| `irc_alert` | 3 | `fbeta` | 0.1641 | 13,327 | 0.3564 | 0.9423 | 0.5964 | 0.5631 | 0.7305 | 0.8444 | 0.5689 | 0.7946 |
| `irc_alert` | 3 | `fixed` | 0.5000 | 13,327 | 0.3564 | 0.6853 | 0.8468 | 0.2884 | 0.7575 | 0.7124 | 0.6518 | 0.8083 |
| `irc_alert` | 3 | `gmean_pr` | 0.2969 | 13,327 | 0.3564 | 0.8745 | 0.7077 | 0.4405 | 0.7823 | 0.8351 | 0.6507 | 0.8372 |
| `irc_alert` | 3 | `mcc` | 0.3281 | 13,327 | 0.3564 | 0.8539 | 0.7305 | 0.4166 | 0.7874 | 0.8260 | 0.6601 | 0.8397 |

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

- Thresholds: `reports/pipe_grud/pipe_rollout_policy_2b_thresholds.csv`
- Metrics: `reports/pipe_grud/pipe_rollout_policy_2b_metrics.csv`
- Manifest: `reports/pipe_grud/pipe_rollout_policy_2b_manifest.json`