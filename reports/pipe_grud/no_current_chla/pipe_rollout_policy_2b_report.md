# PIPE/GRU-D Rollout Alert Policy Frontier Report

Generated at UTC: `2026-06-12T19:12:05.761969+00:00`

## Scope

This report compares automatic threshold-selection objectives on the validation split and evaluates them on held-out test rows.
It does not adopt a final operational policy; it characterizes the decision frontier between precision and recall.

## Configuration

- Calibrated rows: `reports/pipe_grud/no_current_chla/pipe_rollout_calibrated_backtest_rows.parquet`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Selection objectives: `['fixed', 'fbeta', 'f1', 'mcc', 'balanced_accuracy', 'gmean_pr', 'closest_pr']`
- F-beta beta: `2.0`
- Minimum recall constraint: `None`
- Minimum precision constraint: `None`

## Test Frontier

| event | horizon | policy | threshold | rows | base rate | recall | precision | alert rate | F1 | F2 | MCC | balanced accuracy |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | 1 | `balanced_accuracy` | 0.1332 | 11,852 | 0.1243 | 0.7576 | 0.1736 | 0.5423 | 0.2825 | 0.4530 | 0.1629 | 0.6230 |
| `bloom_h` | 1 | `closest_pr` | 0.0909 | 11,852 | 0.1243 | 0.8805 | 0.1437 | 0.7616 | 0.2471 | 0.4347 | 0.1052 | 0.5679 |
| `bloom_h` | 1 | `f1` | 0.1332 | 11,852 | 0.1243 | 0.7576 | 0.1736 | 0.5423 | 0.2825 | 0.4530 | 0.1629 | 0.6230 |
| `bloom_h` | 1 | `fbeta` | 0.0909 | 11,852 | 0.1243 | 0.8805 | 0.1437 | 0.7616 | 0.2471 | 0.4347 | 0.1052 | 0.5679 |
| `bloom_h` | 1 | `gmean_pr` | 0.0714 | 11,852 | 0.1243 | 0.9423 | 0.1319 | 0.8879 | 0.2314 | 0.4228 | 0.0650 | 0.5311 |
| `bloom_h` | 1 | `mcc` | 0.2679 | 11,852 | 0.1243 | 0.2179 | 0.4961 | 0.0546 | 0.3028 | 0.2455 | 0.2709 | 0.5933 |
| `bloom_h` | 2 | `balanced_accuracy` | 0.1362 | 11,891 | 0.1298 | 0.8174 | 0.1791 | 0.5927 | 0.2938 | 0.4772 | 0.1766 | 0.6291 |
| `bloom_h` | 2 | `closest_pr` | 0.0897 | 11,891 | 0.1298 | 0.9469 | 0.1502 | 0.8186 | 0.2593 | 0.4595 | 0.1286 | 0.5737 |
| `bloom_h` | 2 | `f1` | 0.1287 | 11,891 | 0.1298 | 0.8420 | 0.1737 | 0.6296 | 0.2879 | 0.4758 | 0.1699 | 0.6221 |
| `bloom_h` | 2 | `fbeta` | 0.0897 | 11,891 | 0.1298 | 0.9469 | 0.1502 | 0.8186 | 0.2593 | 0.4595 | 0.1286 | 0.5737 |
| `bloom_h` | 2 | `gmean_pr` | 0.0769 | 11,891 | 0.1298 | 0.9780 | 0.1423 | 0.8924 | 0.2485 | 0.4498 | 0.1067 | 0.5492 |
| `bloom_h` | 2 | `mcc` | 0.3956 | 11,891 | 0.1298 | 0.1289 | 0.4877 | 0.0343 | 0.2039 | 0.1511 | 0.2007 | 0.5543 |
| `bloom_h` | 3 | `balanced_accuracy` | 0.1333 | 11,939 | 0.1335 | 0.7673 | 0.1856 | 0.5519 | 0.2989 | 0.4717 | 0.1700 | 0.6243 |
| `bloom_h` | 3 | `closest_pr` | 0.0906 | 11,939 | 0.1335 | 0.9630 | 0.1477 | 0.8707 | 0.2561 | 0.4576 | 0.1080 | 0.5533 |
| `bloom_h` | 3 | `f1` | 0.1308 | 11,939 | 0.1335 | 0.8030 | 0.1776 | 0.6038 | 0.2908 | 0.4711 | 0.1599 | 0.6149 |
| `bloom_h` | 3 | `fbeta` | 0.0902 | 11,939 | 0.1335 | 0.9787 | 0.1455 | 0.8982 | 0.2533 | 0.4561 | 0.1044 | 0.5464 |
| `bloom_h` | 3 | `gmean_pr` | 0.0762 | 11,939 | 0.1335 | 0.9937 | 0.1402 | 0.9461 | 0.2458 | 0.4482 | 0.0827 | 0.5275 |
| `bloom_h` | 3 | `mcc` | 0.2903 | 11,939 | 0.1335 | 0.2171 | 0.3477 | 0.0833 | 0.2673 | 0.2347 | 0.1899 | 0.5772 |
| `irc_alert` | 1 | `balanced_accuracy` | 0.4297 | 13,327 | 0.3335 | 0.5225 | 0.6325 | 0.2755 | 0.5723 | 0.5413 | 0.3911 | 0.6853 |
| `irc_alert` | 1 | `closest_pr` | 0.2891 | 13,327 | 0.3335 | 0.8240 | 0.4262 | 0.6447 | 0.5618 | 0.6944 | 0.2650 | 0.6345 |
| `irc_alert` | 1 | `f1` | 0.3047 | 13,327 | 0.3335 | 0.7858 | 0.4440 | 0.5902 | 0.5674 | 0.6809 | 0.2813 | 0.6467 |
| `irc_alert` | 1 | `fbeta` | 0.1875 | 13,327 | 0.3335 | 0.9620 | 0.3582 | 0.8956 | 0.5220 | 0.7194 | 0.1536 | 0.5498 |
| `irc_alert` | 1 | `fixed` | 0.5000 | 13,327 | 0.3335 | 0.4777 | 0.6768 | 0.2354 | 0.5601 | 0.5076 | 0.4040 | 0.6818 |
| `irc_alert` | 1 | `gmean_pr` | 0.1875 | 13,327 | 0.3335 | 0.9620 | 0.3582 | 0.8956 | 0.5220 | 0.7194 | 0.1536 | 0.5498 |
| `irc_alert` | 1 | `mcc` | 0.5078 | 13,327 | 0.3335 | 0.4741 | 0.6812 | 0.2321 | 0.5591 | 0.5048 | 0.4055 | 0.6816 |
| `irc_alert` | 2 | `balanced_accuracy` | 0.3594 | 13,327 | 0.3464 | 0.5329 | 0.6229 | 0.2963 | 0.5744 | 0.5488 | 0.3772 | 0.6810 |
| `irc_alert` | 2 | `closest_pr` | 0.2109 | 13,327 | 0.3464 | 0.8705 | 0.4199 | 0.7181 | 0.5665 | 0.7166 | 0.2465 | 0.6165 |
| `irc_alert` | 2 | `f1` | 0.2344 | 13,327 | 0.3464 | 0.8143 | 0.4417 | 0.6386 | 0.5727 | 0.6968 | 0.2663 | 0.6344 |
| `irc_alert` | 2 | `fbeta` | 0.1016 | 13,327 | 0.3464 | 0.9976 | 0.3543 | 0.9753 | 0.5229 | 0.7318 | 0.1046 | 0.5171 |
| `irc_alert` | 2 | `fixed` | 0.5000 | 13,327 | 0.3464 | 0.3724 | 0.7296 | 0.1768 | 0.4931 | 0.4128 | 0.3733 | 0.6496 |
| `irc_alert` | 2 | `gmean_pr` | 0.1406 | 13,327 | 0.3464 | 0.9831 | 0.3667 | 0.9285 | 0.5342 | 0.7358 | 0.1543 | 0.5418 |
| `irc_alert` | 2 | `mcc` | 0.4141 | 13,327 | 0.3464 | 0.4686 | 0.6707 | 0.2420 | 0.5517 | 0.4986 | 0.3851 | 0.6733 |
| `irc_alert` | 3 | `balanced_accuracy` | 0.2891 | 13,327 | 0.3564 | 0.5815 | 0.5855 | 0.3539 | 0.5835 | 0.5823 | 0.3541 | 0.6768 |
| `irc_alert` | 3 | `closest_pr` | 0.1719 | 13,327 | 0.3564 | 0.8747 | 0.4184 | 0.7451 | 0.5661 | 0.7181 | 0.2214 | 0.6007 |
| `irc_alert` | 3 | `f1` | 0.1719 | 13,327 | 0.3564 | 0.8747 | 0.4184 | 0.7451 | 0.5661 | 0.7181 | 0.2214 | 0.6007 |
| `irc_alert` | 3 | `fbeta` | 0.0547 | 13,327 | 0.3564 | 1.0000 | 0.3592 | 0.9923 | 0.5285 | 0.7370 | 0.0654 | 0.5059 |
| `irc_alert` | 3 | `fixed` | 0.5000 | 13,327 | 0.3564 | 0.2931 | 0.7573 | 0.1379 | 0.4226 | 0.3340 | 0.3348 | 0.6205 |
| `irc_alert` | 3 | `gmean_pr` | 0.1016 | 13,327 | 0.3564 | 0.9893 | 0.3678 | 0.9586 | 0.5363 | 0.7394 | 0.1146 | 0.5238 |
| `irc_alert` | 3 | `mcc` | 0.3516 | 13,327 | 0.3564 | 0.4878 | 0.6612 | 0.2629 | 0.5614 | 0.5148 | 0.3801 | 0.6747 |

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

- Thresholds: `reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_thresholds.csv`
- Metrics: `reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_metrics.csv`
- Manifest: `reports/pipe_grud/no_current_chla/pipe_rollout_policy_2b_manifest.json`