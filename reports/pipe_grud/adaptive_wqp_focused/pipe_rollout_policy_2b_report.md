# PIPE/GRU-D Rollout Alert Policy Frontier Report

Generated at UTC: `2026-06-15T17:07:12.008672+00:00`

## Scope

This report compares automatic threshold-selection objectives on the validation split and evaluates them on held-out test rows.
It does not adopt a final operational policy; it characterizes the decision frontier between precision and recall.

## Configuration

- Calibrated rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibrated_backtest_rows.parquet`
- Calibration split: `validation`
- Evaluation splits: `['validation', 'test']`
- Selection objectives: `['fixed', 'fbeta', 'f1', 'mcc', 'balanced_accuracy', 'gmean_pr', 'closest_pr']`
- F-beta beta: `2.0`
- Minimum recall constraint: `None`
- Minimum precision constraint: `None`

## Test Frontier

| event | horizon | policy | threshold | rows | base rate | recall | precision | alert rate | F1 | F2 | MCC | balanced accuracy |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `bloom_h` | 1 | `balanced_accuracy` | 0.1571 | 4,673 | 0.1823 | 0.7758 | 0.5188 | 0.2726 | 0.6218 | 0.7059 | 0.5336 | 0.8077 |
| `bloom_h` | 1 | `closest_pr` | 0.3673 | 4,673 | 0.1823 | 0.6221 | 0.6479 | 0.1750 | 0.6347 | 0.6271 | 0.5555 | 0.7733 |
| `bloom_h` | 1 | `f1` | 0.3673 | 4,673 | 0.1823 | 0.6221 | 0.6479 | 0.1750 | 0.6347 | 0.6271 | 0.5555 | 0.7733 |
| `bloom_h` | 1 | `fbeta` | 0.1571 | 4,673 | 0.1823 | 0.7758 | 0.5188 | 0.2726 | 0.6218 | 0.7059 | 0.5336 | 0.8077 |
| `bloom_h` | 1 | `fixed` | 0.3000 | 4,673 | 0.1823 | 0.5282 | 0.6955 | 0.1385 | 0.6004 | 0.5549 | 0.5328 | 0.7383 |
| `bloom_h` | 1 | `gmean_pr` | 0.2931 | 4,673 | 0.1823 | 0.6573 | 0.6278 | 0.1909 | 0.6422 | 0.6512 | 0.5604 | 0.7852 |
| `bloom_h` | 1 | `mcc` | 0.3673 | 4,673 | 0.1823 | 0.6221 | 0.6479 | 0.1750 | 0.6347 | 0.6271 | 0.5555 | 0.7733 |
| `bloom_h` | 2 | `balanced_accuracy` | 0.1448 | 4,710 | 0.1832 | 0.8714 | 0.4349 | 0.3671 | 0.5802 | 0.7257 | 0.4955 | 0.8087 |
| `bloom_h` | 2 | `closest_pr` | 0.2812 | 4,710 | 0.1832 | 0.6315 | 0.5943 | 0.1947 | 0.6124 | 0.6237 | 0.5225 | 0.7674 |
| `bloom_h` | 2 | `f1` | 0.3115 | 4,710 | 0.1832 | 0.6083 | 0.6112 | 0.1824 | 0.6098 | 0.6089 | 0.5225 | 0.7608 |
| `bloom_h` | 2 | `fbeta` | 0.1448 | 4,710 | 0.1832 | 0.8714 | 0.4349 | 0.3671 | 0.5802 | 0.7257 | 0.4955 | 0.8087 |
| `bloom_h` | 2 | `fixed` | 0.3180 | 4,710 | 0.1832 | 0.2990 | 0.6935 | 0.0790 | 0.4178 | 0.3373 | 0.3863 | 0.6347 |
| `bloom_h` | 2 | `gmean_pr` | 0.2812 | 4,710 | 0.1832 | 0.6315 | 0.5943 | 0.1947 | 0.6124 | 0.6237 | 0.5225 | 0.7674 |
| `bloom_h` | 2 | `mcc` | 0.4623 | 4,710 | 0.1832 | 0.5655 | 0.6209 | 0.1669 | 0.5919 | 0.5757 | 0.5063 | 0.7440 |
| `bloom_h` | 3 | `balanced_accuracy` | 0.1500 | 4,757 | 0.1856 | 0.8641 | 0.4316 | 0.3717 | 0.5756 | 0.7198 | 0.4865 | 0.8023 |
| `bloom_h` | 3 | `closest_pr` | 0.3556 | 4,757 | 0.1856 | 0.5651 | 0.5857 | 0.1791 | 0.5752 | 0.5691 | 0.4806 | 0.7370 |
| `bloom_h` | 3 | `f1` | 0.3556 | 4,757 | 0.1856 | 0.5651 | 0.5857 | 0.1791 | 0.5752 | 0.5691 | 0.4806 | 0.7370 |
| `bloom_h` | 3 | `fbeta` | 0.1406 | 4,757 | 0.1856 | 0.8777 | 0.4212 | 0.3868 | 0.5692 | 0.7213 | 0.4812 | 0.8014 |
| `bloom_h` | 3 | `fixed` | 0.3000 | 4,757 | 0.1856 | 0.2503 | 0.6863 | 0.0677 | 0.3668 | 0.2867 | 0.3470 | 0.6121 |
| `bloom_h` | 3 | `gmean_pr` | 0.3556 | 4,757 | 0.1856 | 0.5651 | 0.5857 | 0.1791 | 0.5752 | 0.5691 | 0.4806 | 0.7370 |
| `bloom_h` | 3 | `mcc` | 0.3556 | 4,757 | 0.1856 | 0.5651 | 0.5857 | 0.1791 | 0.5752 | 0.5691 | 0.4806 | 0.7370 |
| `irc_alert` | 1 | `balanced_accuracy` | 0.4297 | 6,145 | 0.4148 | 0.8482 | 0.8146 | 0.4319 | 0.8311 | 0.8412 | 0.7075 | 0.8557 |
| `irc_alert` | 1 | `closest_pr` | 0.4062 | 6,145 | 0.4148 | 0.8568 | 0.8083 | 0.4397 | 0.8318 | 0.8466 | 0.7075 | 0.8564 |
| `irc_alert` | 1 | `f1` | 0.4062 | 6,145 | 0.4148 | 0.8568 | 0.8083 | 0.4397 | 0.8318 | 0.8466 | 0.7075 | 0.8564 |
| `irc_alert` | 1 | `fbeta` | 0.1094 | 6,145 | 0.4148 | 0.9521 | 0.6410 | 0.6161 | 0.7662 | 0.8679 | 0.5817 | 0.7871 |
| `irc_alert` | 1 | `fixed` | 0.5000 | 6,145 | 0.4148 | 0.8215 | 0.8313 | 0.4099 | 0.8264 | 0.8234 | 0.7046 | 0.8517 |
| `irc_alert` | 1 | `gmean_pr` | 0.4062 | 6,145 | 0.4148 | 0.8568 | 0.8083 | 0.4397 | 0.8318 | 0.8466 | 0.7075 | 0.8564 |
| `irc_alert` | 1 | `mcc` | 0.5000 | 6,145 | 0.4148 | 0.8215 | 0.8313 | 0.4099 | 0.8264 | 0.8234 | 0.7046 | 0.8517 |
| `irc_alert` | 2 | `balanced_accuracy` | 0.4375 | 6,145 | 0.4330 | 0.7896 | 0.7790 | 0.4389 | 0.7842 | 0.7874 | 0.6175 | 0.8092 |
| `irc_alert` | 2 | `closest_pr` | 0.3828 | 6,145 | 0.4330 | 0.8159 | 0.7583 | 0.4659 | 0.7860 | 0.8037 | 0.6131 | 0.8086 |
| `irc_alert` | 2 | `f1` | 0.3828 | 6,145 | 0.4330 | 0.8159 | 0.7583 | 0.4659 | 0.7860 | 0.8037 | 0.6131 | 0.8086 |
| `irc_alert` | 2 | `fbeta` | 0.1250 | 6,145 | 0.4330 | 0.9688 | 0.5773 | 0.7268 | 0.7234 | 0.8531 | 0.4747 | 0.7135 |
| `irc_alert` | 2 | `fixed` | 0.5000 | 6,145 | 0.4330 | 0.7554 | 0.7992 | 0.4093 | 0.7767 | 0.7637 | 0.6151 | 0.8052 |
| `irc_alert` | 2 | `gmean_pr` | 0.3516 | 6,145 | 0.4330 | 0.8335 | 0.7488 | 0.4820 | 0.7889 | 0.8151 | 0.6148 | 0.8100 |
| `irc_alert` | 2 | `mcc` | 0.4375 | 6,145 | 0.4330 | 0.7896 | 0.7790 | 0.4389 | 0.7842 | 0.7874 | 0.6175 | 0.8092 |
| `irc_alert` | 3 | `balanced_accuracy` | 0.4609 | 6,145 | 0.4448 | 0.7552 | 0.7815 | 0.4298 | 0.7681 | 0.7603 | 0.5883 | 0.7931 |
| `irc_alert` | 3 | `closest_pr` | 0.3750 | 6,145 | 0.4448 | 0.8053 | 0.7369 | 0.4861 | 0.7696 | 0.7906 | 0.5717 | 0.7875 |
| `irc_alert` | 3 | `f1` | 0.3750 | 6,145 | 0.4448 | 0.8053 | 0.7369 | 0.4861 | 0.7696 | 0.7906 | 0.5717 | 0.7875 |
| `irc_alert` | 3 | `fbeta` | 0.1641 | 6,145 | 0.4448 | 0.9755 | 0.5741 | 0.7557 | 0.7228 | 0.8558 | 0.4577 | 0.6979 |
| `irc_alert` | 3 | `fixed` | 0.5000 | 6,145 | 0.4448 | 0.7278 | 0.7978 | 0.4057 | 0.7612 | 0.7408 | 0.5870 | 0.7900 |
| `irc_alert` | 3 | `gmean_pr` | 0.2109 | 6,145 | 0.4448 | 0.9426 | 0.6174 | 0.6789 | 0.7461 | 0.8528 | 0.5054 | 0.7374 |
| `irc_alert` | 3 | `mcc` | 0.4609 | 6,145 | 0.4448 | 0.7552 | 0.7815 | 0.4298 | 0.7681 | 0.7603 | 0.5883 | 0.7931 |

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

- Thresholds: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_policy_2b_thresholds.csv`
- Metrics: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_policy_2b_metrics.csv`
- Manifest: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_policy_2b_manifest.json`