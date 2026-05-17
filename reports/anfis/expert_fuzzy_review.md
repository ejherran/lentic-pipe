# Expert Fuzzy Review

Generated at UTC: `2026-05-16T21:43:20.301747+00:00`

## Calibrated Test Comparison Vs Selected Baselines

| score | horizon | baseline | IRC PR-AUC | baseline PR-AUC | d PR-AUC | IRC Brier | baseline Brier | d Brier | IRC macro-F1 | baseline macro-F1 | d macro-F1 |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc1` | 1 | `logistic_sgd` | 0.6386 | 0.6924 | -0.0538 | 0.0697 | 0.0651 | 0.0047 | 0.8007 | 0.8122 | -0.0115 |
| `irc1` | 2 | `persistence` | 0.5712 | 0.5461 | 0.0252 | 0.0836 | 0.0819 | 0.0017 | 0.7595 | 0.7723 | -0.0128 |
| `irc1` | 3 | `logistic_sgd` | 0.5331 | 0.5980 | -0.0649 | 0.0899 | 0.0854 | 0.0046 | 0.7390 | 0.7625 | -0.0236 |
| `irc1_no_chla` | 1 | `logistic_sgd` | 0.2728 | 0.6924 | -0.4196 | 0.1094 | 0.0651 | 0.0443 | 0.6084 | 0.8122 | -0.2038 |
| `irc1_no_chla` | 2 | `persistence` | 0.2558 | 0.5461 | -0.2903 | 0.1163 | 0.0819 | 0.0343 | 0.6068 | 0.7723 | -0.1655 |
| `irc1_no_chla` | 3 | `logistic_sgd` | 0.2411 | 0.5980 | -0.3568 | 0.1191 | 0.0854 | 0.0337 | 0.5977 | 0.7625 | -0.1648 |

## Source-Level Test Summary

| score | source | horizon | rows | raw PR-AUC | raw Brier | calibrated Brier | raw macro-F1 | calibrated macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `irc1` | `aquamatch_chla` | 1 | 66,226 | 0.5805 | 0.1323 | 0.0618 | 0.7078 | 0.8017 |
| `irc1` | `lakebed_us_cse` | 1 | 163 | 0.3404 | 0.1591 | 0.1146 | 0.6528 | 0.5495 |
| `irc1` | `wqp` | 1 | 55,151 | 0.6944 | 0.1671 | 0.0792 | 0.6895 | 0.7991 |
| `irc1` | `aquamatch_chla` | 2 | 65,117 | 0.4999 | 0.1385 | 0.0726 | 0.6917 | 0.7589 |
| `irc1` | `lakebed_us_cse` | 2 | 151 | 0.3098 | 0.1604 | 0.1116 | 0.6453 | 0.5232 |
| `irc1` | `wqp` | 2 | 50,423 | 0.6337 | 0.1727 | 0.0978 | 0.6842 | 0.7586 |
| `irc1` | `aquamatch_chla` | 3 | 55,831 | 0.4586 | 0.1430 | 0.0773 | 0.6792 | 0.7374 |
| `irc1` | `lakebed_us_cse` | 3 | 143 | 0.3125 | 0.1485 | 0.1024 | 0.6308 | 0.4542 |
| `irc1` | `wqp` | 3 | 43,696 | 0.5984 | 0.1788 | 0.1060 | 0.6741 | 0.7386 |
| `irc1_no_chla` | `aquamatch_chla` | 1 | 66,226 | 0.1175 | 0.2500 | 0.1037 | 0.1052 | 0.4688 |
| `irc1_no_chla` | `lakebed_us_cse` | 1 | 163 | 0.1312 | 0.2550 | 0.1324 | 0.3933 | 0.4673 |
| `irc1_no_chla` | `wqp` | 1 | 55,151 | 0.3853 | 0.2668 | 0.1161 | 0.5395 | 0.5987 |
| `irc1_no_chla` | `aquamatch_chla` | 2 | 65,117 | 0.1196 | 0.2500 | 0.1054 | 0.1068 | 0.4682 |
| `irc1_no_chla` | `lakebed_us_cse` | 2 | 151 | 0.1215 | 0.2504 | 0.1233 | 0.3863 | 0.4551 |
| `irc1_no_chla` | `wqp` | 2 | 50,423 | 0.3568 | 0.2635 | 0.1303 | 0.5443 | 0.5991 |
| `irc1_no_chla` | `aquamatch_chla` | 3 | 55,831 | 0.1198 | 0.2500 | 0.1055 | 0.1070 | 0.4681 |
| `irc1_no_chla` | `lakebed_us_cse` | 3 | 143 | 0.1087 | 0.2328 | 0.1171 | 0.3822 | 0.4418 |
| `irc1_no_chla` | `wqp` | 3 | 43,696 | 0.3276 | 0.2674 | 0.1364 | 0.5327 | 0.5859 |

## Output Files

- Comparison CSV: `reports/anfis/expert_fuzzy_test_comparison.csv`
- Source summary CSV: `reports/anfis/expert_fuzzy_source_summary.csv`
- Review manifest: `reports/anfis/expert_fuzzy_review_manifest.json`
