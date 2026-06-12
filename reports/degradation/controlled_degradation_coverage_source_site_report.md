# Controlled Degradation Report

Generated at UTC: `2026-06-12T16:44:25.265059+00:00`

## Scope

This report evaluates controlled-degradation scenarios on precomputed alert score rows.
Scenarios that modify predictor evidence are skipped unless passthrough-score evaluation is explicitly enabled.

## Configuration

- Config: `configs/degradation_scenarios.yaml`
- Scored rows: `reports/pipe_grud/pipe_rollout_calibrated_backtest_rows.parquet`
- Thresholds: `reports/pipe_grud/pipe_rollout_policy_2b_thresholds.csv`
- Scenario set: `coverage_source_site`
- Output name: `coverage_source_site`
- Policies: `['closest_pr', 'fixed', 'fbeta']`
- Evaluation splits: `['validation', 'test']`
- Default policy: `closest_pr`
- Passthrough precomputed scores: `False`

## Scenario Summary

| scenario | status | seed | output rows | retained | metrics rows | reason |
|---|---|---:|---:|---:|---:|---|
| `control_observed` | `evaluated` | NA | 88,761 | 1.0000 | 144 |  |
| `site_retention_25` | `evaluated` | 20260612 | 21,153 | 0.2383 | 144 |  |
| `site_retention_25` | `evaluated` | 20260613 | 21,483 | 0.2420 | 144 |  |
| `site_retention_25` | `evaluated` | 20260614 | 22,737 | 0.2562 | 144 |  |
| `site_retention_50` | `evaluated` | 20260612 | 44,601 | 0.5025 | 144 |  |
| `site_retention_50` | `evaluated` | 20260613 | 43,383 | 0.4888 | 144 |  |
| `site_retention_50` | `evaluated` | 20260614 | 44,841 | 0.5052 | 144 |  |
| `site_retention_75` | `evaluated` | 20260612 | 66,870 | 0.7534 | 144 |  |
| `site_retention_75` | `evaluated` | 20260613 | 67,326 | 0.7585 | 144 |  |
| `site_retention_75` | `evaluated` | 20260614 | 67,365 | 0.7589 | 144 |  |
| `source_scope_aquamatch_chla_only` | `evaluated` | NA | 54,552 | 0.6146 | 72 |  |
| `source_scope_lakebed_us_cse_only` | `evaluated` | NA | 567 | 0.0064 | 72 |  |
| `source_scope_no_wqp` | `evaluated` | NA | 55,119 | 0.6210 | 108 |  |
| `source_scope_wqp_only` | `evaluated` | NA | 33,642 | 0.3790 | 72 |  |

## Default-Policy Test Metrics

| scenario | seed | horizon | source | event | rows | recall | precision | alert rate | F2 | delta F2 |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| `control_observed` | NA | 1 | `all` | `bloom_h` | 11,852 | 0.6782 | 0.6088 | 0.1385 | 0.6631 | 0.0000 |
| `control_observed` | NA | 1 | `all` | `irc_alert` | 13,327 | 0.8499 | 0.7788 | 0.3639 | 0.8347 | 0.0000 |
| `control_observed` | NA | 2 | `all` | `bloom_h` | 11,891 | 0.7137 | 0.5357 | 0.1730 | 0.6693 | 0.0000 |
| `control_observed` | NA | 2 | `all` | `irc_alert` | 13,327 | 0.8250 | 0.7622 | 0.3749 | 0.8116 | 0.0000 |
| `control_observed` | NA | 3 | `all` | `bloom_h` | 11,939 | 0.7183 | 0.5037 | 0.1904 | 0.6619 | 0.0000 |
| `control_observed` | NA | 3 | `all` | `irc_alert` | 13,327 | 0.8539 | 0.7305 | 0.4166 | 0.8260 | 0.0000 |
| `site_retention_25` | 20260612 | 1 | `all` | `bloom_h` | 2,931 | 0.6519 | 0.6005 | 0.1341 | 0.6410 | -0.0221 |
| `site_retention_25` | 20260612 | 1 | `all` | `irc_alert` | 3,257 | 0.8537 | 0.7876 | 0.3571 | 0.8396 | 0.0049 |
| `site_retention_25` | 20260612 | 2 | `all` | `bloom_h` | 2,943 | 0.7214 | 0.5700 | 0.1651 | 0.6850 | 0.0157 |
| `site_retention_25` | 20260612 | 2 | `all` | `irc_alert` | 3,257 | 0.8324 | 0.7920 | 0.3601 | 0.8240 | 0.0124 |
| `site_retention_25` | 20260612 | 3 | `all` | `bloom_h` | 2,956 | 0.7252 | 0.5539 | 0.1790 | 0.6830 | 0.0211 |
| `site_retention_25` | 20260612 | 3 | `all` | `irc_alert` | 3,257 | 0.8472 | 0.7481 | 0.3961 | 0.8254 | -0.0007 |
| `site_retention_25` | 20260613 | 1 | `all` | `bloom_h` | 2,944 | 0.6658 | 0.6403 | 0.1416 | 0.6606 | -0.0025 |
| `site_retention_25` | 20260613 | 1 | `all` | `irc_alert` | 3,281 | 0.8578 | 0.7705 | 0.3746 | 0.8388 | 0.0041 |
| `site_retention_25` | 20260613 | 2 | `all` | `bloom_h` | 2,949 | 0.7053 | 0.5489 | 0.1804 | 0.6673 | -0.0020 |
| `site_retention_25` | 20260613 | 2 | `all` | `irc_alert` | 3,281 | 0.8313 | 0.7432 | 0.3941 | 0.8121 | 0.0005 |
| `site_retention_25` | 20260613 | 3 | `all` | `bloom_h` | 2,959 | 0.6983 | 0.5017 | 0.1980 | 0.6476 | -0.0143 |
| `site_retention_25` | 20260613 | 3 | `all` | `irc_alert` | 3,281 | 0.8585 | 0.7178 | 0.4352 | 0.8261 | 0.0001 |
| `site_retention_25` | 20260614 | 1 | `all` | `bloom_h` | 2,944 | 0.6824 | 0.5193 | 0.1321 | 0.6421 | -0.0210 |
| `site_retention_25` | 20260614 | 1 | `all` | `irc_alert` | 3,334 | 0.8456 | 0.7694 | 0.3629 | 0.8292 | -0.0055 |
| `site_retention_25` | 20260614 | 2 | `all` | `bloom_h` | 2,949 | 0.7115 | 0.4568 | 0.1611 | 0.6401 | -0.0291 |
| `site_retention_25` | 20260614 | 2 | `all` | `irc_alert` | 3,334 | 0.8192 | 0.7427 | 0.3788 | 0.8027 | -0.0089 |
| `site_retention_25` | 20260614 | 3 | `all` | `bloom_h` | 2,958 | 0.7264 | 0.4160 | 0.1812 | 0.6321 | -0.0298 |
| `site_retention_25` | 20260614 | 3 | `all` | `irc_alert` | 3,334 | 0.8526 | 0.7247 | 0.4118 | 0.8235 | -0.0025 |
| `site_retention_50` | 20260612 | 1 | `all` | `bloom_h` | 5,936 | 0.6634 | 0.5692 | 0.1388 | 0.6421 | -0.0210 |
| `site_retention_50` | 20260612 | 1 | `all` | `irc_alert` | 6,723 | 0.8546 | 0.7876 | 0.3684 | 0.8403 | 0.0056 |
| `site_retention_50` | 20260612 | 2 | `all` | `bloom_h` | 5,958 | 0.7179 | 0.5214 | 0.1729 | 0.6676 | -0.0017 |
| `site_retention_50` | 20260612 | 2 | `all` | `irc_alert` | 6,723 | 0.8247 | 0.7690 | 0.3786 | 0.8129 | 0.0013 |
| `site_retention_50` | 20260612 | 3 | `all` | `bloom_h` | 5,982 | 0.7299 | 0.4735 | 0.1956 | 0.6586 | -0.0033 |
| `site_retention_50` | 20260612 | 3 | `all` | `irc_alert` | 6,723 | 0.8561 | 0.7353 | 0.4248 | 0.8289 | 0.0029 |
| `site_retention_50` | 20260613 | 1 | `all` | `bloom_h` | 5,687 | 0.6738 | 0.6157 | 0.1528 | 0.6613 | -0.0018 |
| `site_retention_50` | 20260613 | 1 | `all` | `irc_alert` | 6,434 | 0.8489 | 0.7899 | 0.3847 | 0.8364 | 0.0017 |
| `site_retention_50` | 20260613 | 2 | `all` | `bloom_h` | 5,706 | 0.7096 | 0.5433 | 0.1884 | 0.6687 | -0.0006 |
| `site_retention_50` | 20260613 | 2 | `all` | `irc_alert` | 6,434 | 0.8270 | 0.7731 | 0.3959 | 0.8156 | 0.0040 |
| `site_retention_50` | 20260613 | 3 | `all` | `bloom_h` | 5,730 | 0.7160 | 0.5178 | 0.2056 | 0.6651 | 0.0031 |
| `site_retention_50` | 20260613 | 3 | `all` | `irc_alert` | 6,434 | 0.8528 | 0.7386 | 0.4388 | 0.8272 | 0.0012 |
| `site_retention_50` | 20260614 | 1 | `all` | `bloom_h` | 5,949 | 0.6456 | 0.6166 | 0.1197 | 0.6396 | -0.0235 |
| `site_retention_50` | 20260614 | 1 | `all` | `irc_alert` | 6,709 | 0.8413 | 0.7642 | 0.3464 | 0.8247 | -0.0100 |
| `site_retention_50` | 20260614 | 2 | `all` | `bloom_h` | 5,967 | 0.6918 | 0.5288 | 0.1572 | 0.6516 | -0.0177 |
| `site_retention_50` | 20260614 | 2 | `all` | `irc_alert` | 6,709 | 0.8125 | 0.7520 | 0.3582 | 0.7996 | -0.0120 |
| `site_retention_50` | 20260614 | 3 | `all` | `bloom_h` | 5,992 | 0.7007 | 0.4971 | 0.1752 | 0.6476 | -0.0143 |
| `site_retention_50` | 20260614 | 3 | `all` | `irc_alert` | 6,709 | 0.8413 | 0.7226 | 0.4014 | 0.8146 | -0.0114 |
| `site_retention_75` | 20260612 | 1 | `all` | `bloom_h` | 8,989 | 0.6693 | 0.6154 | 0.1368 | 0.6578 | -0.0053 |
| `site_retention_75` | 20260612 | 1 | `all` | `irc_alert` | 10,074 | 0.8458 | 0.7717 | 0.3661 | 0.8298 | -0.0048 |
| `site_retention_75` | 20260612 | 2 | `all` | `bloom_h` | 9,019 | 0.7060 | 0.5389 | 0.1710 | 0.6648 | -0.0045 |
| `site_retention_75` | 20260612 | 2 | `all` | `irc_alert` | 10,074 | 0.8224 | 0.7587 | 0.3773 | 0.8088 | -0.0028 |
| `site_retention_75` | 20260612 | 3 | `all` | `bloom_h` | 9,058 | 0.7178 | 0.5040 | 0.1917 | 0.6617 | -0.0003 |
| `site_retention_75` | 20260612 | 3 | `all` | `irc_alert` | 10,074 | 0.8525 | 0.7289 | 0.4189 | 0.8246 | -0.0014 |
| `site_retention_75` | 20260613 | 1 | `all` | `bloom_h` | 8,898 | 0.6917 | 0.6129 | 0.1399 | 0.6744 | 0.0113 |
| `site_retention_75` | 20260613 | 1 | `all` | `irc_alert` | 10,048 | 0.8491 | 0.7785 | 0.3662 | 0.8340 | -0.0006 |
| `site_retention_75` | 20260613 | 2 | `all` | `bloom_h` | 8,933 | 0.7101 | 0.5358 | 0.1719 | 0.6667 | -0.0025 |
| `site_retention_75` | 20260613 | 2 | `all` | `irc_alert` | 10,048 | 0.8220 | 0.7613 | 0.3778 | 0.8091 | -0.0025 |
| `site_retention_75` | 20260613 | 3 | `all` | `bloom_h` | 8,972 | 0.7207 | 0.5026 | 0.1912 | 0.6632 | 0.0013 |
| `site_retention_75` | 20260613 | 3 | `all` | `irc_alert` | 10,048 | 0.8495 | 0.7324 | 0.4195 | 0.8232 | -0.0028 |
| `site_retention_75` | 20260614 | 1 | `all` | `bloom_h` | 8,981 | 0.6695 | 0.6198 | 0.1409 | 0.6589 | -0.0041 |
| `site_retention_75` | 20260614 | 1 | `all` | `irc_alert` | 10,135 | 0.8510 | 0.7838 | 0.3724 | 0.8366 | 0.0020 |
| `site_retention_75` | 20260614 | 2 | `all` | `bloom_h` | 9,005 | 0.7006 | 0.5453 | 0.1753 | 0.6628 | -0.0064 |
| `site_retention_75` | 20260614 | 2 | `all` | `irc_alert` | 10,135 | 0.8247 | 0.7667 | 0.3831 | 0.8124 | 0.0008 |
| `site_retention_75` | 20260614 | 3 | `all` | `bloom_h` | 9,043 | 0.7067 | 0.5085 | 0.1944 | 0.6556 | -0.0063 |
| `site_retention_75` | 20260614 | 3 | `all` | `irc_alert` | 10,135 | 0.8526 | 0.7371 | 0.4242 | 0.8267 | 0.0007 |
| `source_scope_aquamatch_chla_only` | NA | 1 | `all` | `bloom_h` | 7,154 | 0.6860 | 0.5892 | 0.1011 | 0.6642 | 0.0011 |
| `source_scope_aquamatch_chla_only` | NA | 1 | `all` | `irc_alert` | 7,154 | 0.7705 | 0.7293 | 0.2432 | 0.7619 | -0.0728 |
| `source_scope_aquamatch_chla_only` | NA | 2 | `all` | `bloom_h` | 7,154 | 0.7074 | 0.5211 | 0.1290 | 0.6602 | -0.0091 |
| `source_scope_aquamatch_chla_only` | NA | 2 | `all` | `irc_alert` | 7,154 | 0.7284 | 0.7234 | 0.2431 | 0.7274 | -0.0842 |
| `source_scope_aquamatch_chla_only` | NA | 3 | `all` | `bloom_h` | 7,154 | 0.7246 | 0.4790 | 0.1497 | 0.6572 | -0.0047 |
| `source_scope_aquamatch_chla_only` | NA | 3 | `all` | `irc_alert` | 7,154 | 0.7435 | 0.7086 | 0.2647 | 0.7362 | -0.0898 |
| `source_scope_lakebed_us_cse_only` | NA | 1 | `all` | `bloom_h` | 25 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.6631 |
| `source_scope_lakebed_us_cse_only` | NA | 1 | `all` | `irc_alert` | 28 | 0.4000 | 0.4000 | 0.1786 | 0.4000 | -0.4347 |
| `source_scope_lakebed_us_cse_only` | NA | 2 | `all` | `bloom_h` | 27 | 0.0000 | 0.0000 | 0.0741 | 0.0000 | -0.6693 |
| `source_scope_lakebed_us_cse_only` | NA | 2 | `all` | `irc_alert` | 28 | 0.6667 | 0.6667 | 0.2143 | 0.6667 | -0.1449 |
| `source_scope_lakebed_us_cse_only` | NA | 3 | `all` | `bloom_h` | 28 | 0.0000 | 0.0000 | 0.1071 | 0.0000 | -0.6619 |
| `source_scope_lakebed_us_cse_only` | NA | 3 | `all` | `irc_alert` | 28 | 0.7143 | 0.5556 | 0.3214 | 0.6757 | -0.1503 |
| `source_scope_no_wqp` | NA | 1 | `all` | `bloom_h` | 7,179 | 0.6860 | 0.5892 | 0.1007 | 0.6642 | 0.0011 |
| `source_scope_no_wqp` | NA | 1 | `all` | `irc_alert` | 7,182 | 0.7694 | 0.7284 | 0.2430 | 0.7608 | -0.0739 |
| `source_scope_no_wqp` | NA | 2 | `all` | `bloom_h` | 7,181 | 0.7063 | 0.5200 | 0.1288 | 0.6591 | -0.0102 |
| `source_scope_no_wqp` | NA | 2 | `all` | `irc_alert` | 7,182 | 0.7282 | 0.7232 | 0.2430 | 0.7272 | -0.0844 |
| `source_scope_no_wqp` | NA | 3 | `all` | `bloom_h` | 7,182 | 0.7215 | 0.4777 | 0.1495 | 0.6547 | -0.0073 |
| `source_scope_no_wqp` | NA | 3 | `all` | `irc_alert` | 7,182 | 0.7434 | 0.7078 | 0.2650 | 0.7360 | -0.0900 |
| `source_scope_wqp_only` | NA | 1 | `all` | `bloom_h` | 4,673 | 0.6725 | 0.6242 | 0.1964 | 0.6623 | -0.0008 |
| `source_scope_wqp_only` | NA | 1 | `all` | `irc_alert` | 6,145 | 0.8976 | 0.8071 | 0.5053 | 0.8779 | 0.0432 |
| `source_scope_wqp_only` | NA | 2 | `all` | `bloom_h` | 4,710 | 0.7196 | 0.5486 | 0.2403 | 0.6774 | 0.0081 |
| `source_scope_wqp_only` | NA | 2 | `all` | `irc_alert` | 6,145 | 0.8831 | 0.7831 | 0.5290 | 0.8611 | 0.0495 |
| `source_scope_wqp_only` | NA | 3 | `all` | `bloom_h` | 4,757 | 0.7157 | 0.5271 | 0.2520 | 0.6679 | 0.0060 |
| `source_scope_wqp_only` | NA | 3 | `all` | `irc_alert` | 6,145 | 0.9221 | 0.7424 | 0.5938 | 0.8795 | 0.0535 |

## Guardrails

- Labels are not modified by this evaluator.
- Source-scoped site identity is preserved.
- Ranking metrics are reported as NA for groups with only one observed class.
- Predictor-degradation scenarios require model recomputation for scientific performance claims.
- Degraded outputs are stress-test evidence, not official environmental alerts.

## Outputs

- Metrics: `reports/degradation/controlled_degradation_coverage_source_site_metrics.csv`
- Summary: `reports/degradation/controlled_degradation_coverage_source_site_summary.csv`
- Manifest: `reports/degradation/controlled_degradation_coverage_source_site_manifest.json`