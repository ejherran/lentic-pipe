# Recomputed PIPE/GRU-D State Degradation Report

Generated at UTC: `2026-06-12T17:22:13.976550+00:00`
Started at UTC: `2026-06-12T17:20:33.683431+00:00`

## Scope

This report recomputes PIPE/GRU-D rollout scores after controlled degradation of PIPE sequence inputs.
It does not degrade raw panel predictors directly; raw-predictor degradation requires rebuilding fuzzy states and sequence datasets upstream.

## Configuration

- Config: `configs/degradation_scenarios.yaml`
- Scenario set: `pipe_state_recompute_smoke`
- Selected origins: `13,327`
- History length: `12`
- Rollout horizon: `3` month(s)
- Samples per origin: `128`
- Deterministic mode: `False`
- Max origins cap: `None`
- Calibrated bloom horizons available: `[1, 2, 3]`
- Rollout bloom calibrator horizons available: `[1, 2, 3]`
- Policies: `['closest_pr', 'fixed', 'fbeta']`
- Requested policy evaluation splits: `['test']`
- Observed policy metric splits: `['test']`
- Default downstream policy context: `closest_pr`

## Future Availability

| horizon | eligible origins | origins with observed future | selected origins | policy |
|---:|---:|---:|---:|---|
| 1 | 17,420 | 17,420 | 13,327 | `complete_horizons` |
| 2 | 17,420 | 15,268 | 13,327 | `complete_horizons` |
| 3 | 17,420 | 13,685 | 13,327 | `complete_horizons` |

## Scenario Summary

| scenario | status | seed | affected frame rows | affected frame cells | affected selected-window rows | affected selected-window cells | rollout rows | policy metric rows |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `ablate_pipe_state_level` | `evaluated` | NA | 2,068,291 | 5,460,016 | 33,105 | 84,420 | 39,981 | 72 |
| `control_observed` | `evaluated` | NA | 0 | 0 | 0 | 0 | 39,981 | 72 |
| `random_pipe_state_dropout_25` | `evaluated` | 20260612 | 1,745,390 | 3,434,413 | 27,981 | 55,757 | 39,981 | 72 |
| `random_pipe_state_dropout_25` | `evaluated` | 20260613 | 1,744,753 | 3,435,221 | 27,946 | 56,071 | 39,981 | 72 |
| `random_pipe_state_dropout_25` | `evaluated` | 20260614 | 1,744,751 | 3,433,142 | 27,923 | 55,755 | 39,981 | 72 |
| `temporal_pipe_state_blocks_3m_rate_10` | `evaluated` | 20260612 | 23,490 | 156,569 | 423 | 2,793 | 39,981 | 72 |
| `temporal_pipe_state_blocks_3m_rate_10` | `evaluated` | 20260613 | 22,935 | 153,028 | 400 | 2,662 | 39,981 | 72 |
| `temporal_pipe_state_blocks_3m_rate_10` | `evaluated` | 20260614 | 23,512 | 156,292 | 401 | 2,647 | 39,981 | 72 |

## State Metrics

| scenario | seed | split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE |
|---|---:|---|---:|---|---:|---:|---:|---:|---:|
| `ablate_pipe_state_level` | NA | `test` | 1 | `all` | 119,943 | 0.3062 | 0.3549 | 0.1371 | 0.1973 |
| `ablate_pipe_state_level` | NA | `test` | 1 | `irc1` | 13,327 | 0.3171 | 0.3539 | 0.1039 | 0.2371 |
| `ablate_pipe_state_level` | NA | `test` | 2 | `all` | 119,943 | 0.2923 | 0.3516 | 0.1687 | 0.1910 |
| `ablate_pipe_state_level` | NA | `test` | 2 | `irc1` | 13,327 | 0.3090 | 0.3621 | 0.1466 | 0.2400 |
| `ablate_pipe_state_level` | NA | `test` | 3 | `all` | 119,943 | 0.2851 | 0.3535 | 0.1934 | 0.1887 |
| `ablate_pipe_state_level` | NA | `test` | 3 | `irc1` | 13,327 | 0.3054 | 0.3678 | 0.1697 | 0.2416 |
| `control_observed` | NA | `test` | 1 | `all` | 119,943 | 0.1341 | 0.1792 | 0.2518 | 0.0730 |
| `control_observed` | NA | `test` | 1 | `irc1` | 13,327 | 0.1415 | 0.1627 | 0.1304 | 0.1084 |
| `control_observed` | NA | `test` | 2 | `all` | 119,943 | 0.1475 | 0.1796 | 0.1788 | 0.0825 |
| `control_observed` | NA | `test` | 2 | `irc1` | 13,327 | 0.1624 | 0.1992 | 0.1849 | 0.1316 |
| `control_observed` | NA | `test` | 3 | `all` | 119,943 | 0.1543 | 0.1886 | 0.1821 | 0.0881 |
| `control_observed` | NA | `test` | 3 | `irc1` | 13,327 | 0.1717 | 0.2237 | 0.2326 | 0.1412 |
| `random_pipe_state_dropout_25` | 20260612 | `test` | 1 | `all` | 119,943 | 0.2403 | 0.2745 | 0.1245 | 0.1388 |
| `random_pipe_state_dropout_25` | 20260612 | `test` | 1 | `irc1` | 13,327 | 0.2001 | 0.2316 | 0.1360 | 0.1441 |
| `random_pipe_state_dropout_25` | 20260612 | `test` | 2 | `all` | 119,943 | 0.2377 | 0.2753 | 0.1368 | 0.1412 |
| `random_pipe_state_dropout_25` | 20260612 | `test` | 2 | `irc1` | 13,327 | 0.2081 | 0.2548 | 0.1832 | 0.1611 |
| `random_pipe_state_dropout_25` | 20260612 | `test` | 3 | `all` | 119,943 | 0.2360 | 0.2801 | 0.1575 | 0.1428 |
| `random_pipe_state_dropout_25` | 20260612 | `test` | 3 | `irc1` | 13,327 | 0.2131 | 0.2707 | 0.2128 | 0.1703 |
| `random_pipe_state_dropout_25` | 20260613 | `test` | 1 | `all` | 119,943 | 0.2416 | 0.2757 | 0.1238 | 0.1394 |
| `random_pipe_state_dropout_25` | 20260613 | `test` | 1 | `irc1` | 13,327 | 0.2006 | 0.2318 | 0.1346 | 0.1445 |
| `random_pipe_state_dropout_25` | 20260613 | `test` | 2 | `all` | 119,943 | 0.2389 | 0.2764 | 0.1356 | 0.1418 |
| `random_pipe_state_dropout_25` | 20260613 | `test` | 2 | `irc1` | 13,327 | 0.2090 | 0.2553 | 0.1813 | 0.1615 |
| `random_pipe_state_dropout_25` | 20260613 | `test` | 3 | `all` | 119,943 | 0.2373 | 0.2818 | 0.1579 | 0.1434 |
| `random_pipe_state_dropout_25` | 20260613 | `test` | 3 | `irc1` | 13,327 | 0.2149 | 0.2723 | 0.2111 | 0.1706 |
| `random_pipe_state_dropout_25` | 20260614 | `test` | 1 | `all` | 119,943 | 0.2393 | 0.2739 | 0.1265 | 0.1381 |
| `random_pipe_state_dropout_25` | 20260614 | `test` | 1 | `irc1` | 13,327 | 0.1993 | 0.2308 | 0.1369 | 0.1445 |
| `random_pipe_state_dropout_25` | 20260614 | `test` | 2 | `all` | 119,943 | 0.2367 | 0.2749 | 0.1391 | 0.1404 |
| `random_pipe_state_dropout_25` | 20260614 | `test` | 2 | `irc1` | 13,327 | 0.2079 | 0.2555 | 0.1862 | 0.1617 |
| `random_pipe_state_dropout_25` | 20260614 | `test` | 3 | `all` | 119,943 | 0.2350 | 0.2797 | 0.1598 | 0.1421 |
| `random_pipe_state_dropout_25` | 20260614 | `test` | 3 | `irc1` | 13,327 | 0.2130 | 0.2713 | 0.2147 | 0.1701 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `test` | 1 | `all` | 119,943 | 0.1419 | 0.1855 | 0.2354 | 0.0764 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `test` | 1 | `irc1` | 13,327 | 0.1454 | 0.1678 | 0.1336 | 0.1103 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `test` | 2 | `all` | 119,943 | 0.1537 | 0.1859 | 0.1731 | 0.0856 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `test` | 2 | `irc1` | 13,327 | 0.1650 | 0.2031 | 0.1875 | 0.1331 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `test` | 3 | `all` | 119,943 | 0.1597 | 0.1945 | 0.1791 | 0.0910 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `test` | 3 | `irc1` | 13,327 | 0.1737 | 0.2268 | 0.2342 | 0.1425 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `test` | 1 | `all` | 119,943 | 0.1397 | 0.1836 | 0.2391 | 0.0755 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `test` | 1 | `irc1` | 13,327 | 0.1433 | 0.1648 | 0.1306 | 0.1092 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `test` | 2 | `all` | 119,943 | 0.1522 | 0.1842 | 0.1736 | 0.0849 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `test` | 2 | `irc1` | 13,327 | 0.1637 | 0.2005 | 0.1837 | 0.1323 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `test` | 3 | `all` | 119,943 | 0.1585 | 0.1927 | 0.1774 | 0.0904 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `test` | 3 | `irc1` | 13,327 | 0.1729 | 0.2245 | 0.2299 | 0.1420 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `test` | 1 | `all` | 119,943 | 0.1420 | 0.1856 | 0.2350 | 0.0765 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `test` | 1 | `irc1` | 13,327 | 0.1443 | 0.1660 | 0.1310 | 0.1097 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `test` | 2 | `all` | 119,943 | 0.1539 | 0.1861 | 0.1728 | 0.0857 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `test` | 2 | `irc1` | 13,327 | 0.1645 | 0.2019 | 0.1854 | 0.1326 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `test` | 3 | `all` | 119,943 | 0.1600 | 0.1947 | 0.1779 | 0.0911 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `test` | 3 | `irc1` | 13,327 | 0.1735 | 0.2257 | 0.2313 | 0.1423 |

## Alert Metrics

| scenario | seed | event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| `ablate_pipe_state_level` | NA | `bloom_h` | `test` | 1 | 11,852 | 0.1243 | 0.0000 | 0.1137 | 0.1180 | 0.0000 |
| `ablate_pipe_state_level` | NA | `bloom_h` | `test` | 2 | 11,891 | 0.1298 | 0.0000 | 0.1235 | 0.1187 | 0.0000 |
| `ablate_pipe_state_level` | NA | `bloom_h` | `test` | 3 | 11,939 | 0.1335 | 0.0000 | 0.1298 | 0.1200 | 0.0000 |
| `ablate_pipe_state_level` | NA | `irc_alert` | `test` | 1 | 13,327 | 0.3335 | 0.0000 | 0.3443 | 0.3122 | 0.0000 |
| `ablate_pipe_state_level` | NA | `irc_alert` | `test` | 2 | 13,327 | 0.3464 | 0.0003 | 0.3637 | 0.2958 | 0.0006 |
| `ablate_pipe_state_level` | NA | `irc_alert` | `test` | 3 | 13,327 | 0.3564 | 0.0007 | 0.3779 | 0.2882 | 0.0011 |
| `control_observed` | NA | `bloom_h` | `test` | 1 | 11,852 | 0.1243 | 0.1120 | 0.6737 | 0.0711 | 0.6083 |
| `control_observed` | NA | `bloom_h` | `test` | 2 | 11,891 | 0.1298 | 0.0613 | 0.6366 | 0.0830 | 0.3543 |
| `control_observed` | NA | `bloom_h` | `test` | 3 | 11,939 | 0.1335 | 0.0519 | 0.6106 | 0.0899 | 0.2880 |
| `control_observed` | NA | `irc_alert` | `test` | 1 | 13,327 | 0.3335 | 0.3130 | 0.8894 | 0.0913 | 0.7826 |
| `control_observed` | NA | `irc_alert` | `test` | 2 | 13,327 | 0.3464 | 0.2995 | 0.8769 | 0.1038 | 0.7244 |
| `control_observed` | NA | `irc_alert` | `test` | 3 | 13,327 | 0.3564 | 0.2884 | 0.8702 | 0.1123 | 0.6853 |
| `random_pipe_state_dropout_25` | 20260612 | `bloom_h` | `test` | 1 | 11,852 | 0.1243 | 0.0614 | 0.4996 | 0.0874 | 0.3218 |
| `random_pipe_state_dropout_25` | 20260612 | `bloom_h` | `test` | 2 | 11,891 | 0.1298 | 0.0232 | 0.4770 | 0.0960 | 0.1205 |
| `random_pipe_state_dropout_25` | 20260612 | `bloom_h` | `test` | 3 | 11,939 | 0.1335 | 0.0148 | 0.4808 | 0.1008 | 0.0834 |
| `random_pipe_state_dropout_25` | 20260612 | `irc_alert` | `test` | 1 | 13,327 | 0.3335 | 0.2223 | 0.7768 | 0.1489 | 0.5569 |
| `random_pipe_state_dropout_25` | 20260612 | `irc_alert` | `test` | 2 | 13,327 | 0.3464 | 0.1913 | 0.7831 | 0.1529 | 0.4708 |
| `random_pipe_state_dropout_25` | 20260612 | `irc_alert` | `test` | 3 | 13,327 | 0.3564 | 0.1658 | 0.7868 | 0.1580 | 0.4048 |
| `random_pipe_state_dropout_25` | 20260613 | `bloom_h` | `test` | 1 | 11,852 | 0.1243 | 0.0599 | 0.5130 | 0.0872 | 0.3279 |
| `random_pipe_state_dropout_25` | 20260613 | `bloom_h` | `test` | 2 | 11,891 | 0.1298 | 0.0211 | 0.4982 | 0.0958 | 0.1218 |
| `random_pipe_state_dropout_25` | 20260613 | `bloom_h` | `test` | 3 | 11,939 | 0.1335 | 0.0137 | 0.4768 | 0.1014 | 0.0740 |
| `random_pipe_state_dropout_25` | 20260613 | `irc_alert` | `test` | 1 | 13,327 | 0.3335 | 0.2178 | 0.7807 | 0.1480 | 0.5500 |
| `random_pipe_state_dropout_25` | 20260613 | `irc_alert` | `test` | 2 | 13,327 | 0.3464 | 0.1854 | 0.7860 | 0.1528 | 0.4601 |
| `random_pipe_state_dropout_25` | 20260613 | `irc_alert` | `test` | 3 | 13,327 | 0.3564 | 0.1605 | 0.7879 | 0.1596 | 0.3975 |
| `random_pipe_state_dropout_25` | 20260614 | `bloom_h` | `test` | 1 | 11,852 | 0.1243 | 0.0619 | 0.5067 | 0.0869 | 0.3306 |
| `random_pipe_state_dropout_25` | 20260614 | `bloom_h` | `test` | 2 | 11,891 | 0.1298 | 0.0198 | 0.4960 | 0.0957 | 0.1166 |
| `random_pipe_state_dropout_25` | 20260614 | `bloom_h` | `test` | 3 | 11,939 | 0.1335 | 0.0125 | 0.4896 | 0.1008 | 0.0709 |
| `random_pipe_state_dropout_25` | 20260614 | `irc_alert` | `test` | 1 | 13,327 | 0.3335 | 0.2184 | 0.7848 | 0.1466 | 0.5565 |
| `random_pipe_state_dropout_25` | 20260614 | `irc_alert` | `test` | 2 | 13,327 | 0.3464 | 0.1894 | 0.7834 | 0.1528 | 0.4669 |
| `random_pipe_state_dropout_25` | 20260614 | `irc_alert` | `test` | 3 | 13,327 | 0.3564 | 0.1630 | 0.7918 | 0.1576 | 0.4015 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `bloom_h` | `test` | 1 | 11,852 | 0.1243 | 0.1099 | 0.6651 | 0.0719 | 0.5988 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `bloom_h` | `test` | 2 | 11,891 | 0.1298 | 0.0598 | 0.6298 | 0.0836 | 0.3465 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `bloom_h` | `test` | 3 | 11,939 | 0.1335 | 0.0507 | 0.6038 | 0.0904 | 0.2804 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `irc_alert` | `test` | 1 | 13,327 | 0.3335 | 0.3068 | 0.8827 | 0.0951 | 0.7667 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `irc_alert` | `test` | 2 | 13,327 | 0.3464 | 0.2927 | 0.8710 | 0.1069 | 0.7080 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `irc_alert` | `test` | 3 | 13,327 | 0.3564 | 0.2818 | 0.8663 | 0.1144 | 0.6705 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `bloom_h` | `test` | 1 | 11,852 | 0.1243 | 0.1099 | 0.6689 | 0.0716 | 0.5995 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `bloom_h` | `test` | 2 | 11,891 | 0.1298 | 0.0605 | 0.6307 | 0.0835 | 0.3491 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `bloom_h` | `test` | 3 | 11,939 | 0.1335 | 0.0511 | 0.6091 | 0.0903 | 0.2848 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `irc_alert` | `test` | 1 | 13,327 | 0.3335 | 0.3100 | 0.8867 | 0.0927 | 0.7754 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `irc_alert` | `test` | 2 | 13,327 | 0.3464 | 0.2960 | 0.8745 | 0.1050 | 0.7173 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `irc_alert` | `test` | 3 | 13,327 | 0.3564 | 0.2846 | 0.8680 | 0.1135 | 0.6771 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `bloom_h` | `test` | 1 | 11,852 | 0.1243 | 0.1099 | 0.6676 | 0.0717 | 0.5981 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `bloom_h` | `test` | 2 | 11,891 | 0.1298 | 0.0600 | 0.6298 | 0.0836 | 0.3452 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `bloom_h` | `test` | 3 | 11,939 | 0.1335 | 0.0503 | 0.6034 | 0.0905 | 0.2779 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `irc_alert` | `test` | 1 | 13,327 | 0.3335 | 0.3088 | 0.8846 | 0.0939 | 0.7727 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `irc_alert` | `test` | 2 | 13,327 | 0.3464 | 0.2947 | 0.8734 | 0.1058 | 0.7140 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `irc_alert` | `test` | 3 | 13,327 | 0.3564 | 0.2835 | 0.8671 | 0.1140 | 0.6743 |

## Policy Metrics

| scenario | seed | policy | event | split | horizon | rows | recall | precision | alert rate | F2 | delta F2 |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `ablate_pipe_state_level` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 11,852 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.6631 |
| `ablate_pipe_state_level` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 11,891 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.6693 |
| `ablate_pipe_state_level` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 11,939 | 0.0006 | 1.0000 | 0.0001 | 0.0008 | -0.6611 |
| `ablate_pipe_state_level` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 13,327 | 0.0009 | 1.0000 | 0.0003 | 0.0011 | -0.8335 |
| `ablate_pipe_state_level` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 13,327 | 0.0052 | 0.6486 | 0.0028 | 0.0065 | -0.8051 |
| `ablate_pipe_state_level` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 13,327 | 0.0147 | 0.5645 | 0.0093 | 0.0183 | -0.8077 |
| `ablate_pipe_state_level` | NA | `fbeta` | `bloom_h` | `test` | 1 | 11,852 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.7152 |
| `ablate_pipe_state_level` | NA | `fbeta` | `bloom_h` | `test` | 2 | 11,891 | 0.0013 | 0.4000 | 0.0004 | 0.0016 | -0.7079 |
| `ablate_pipe_state_level` | NA | `fbeta` | `bloom_h` | `test` | 3 | 11,939 | 0.0031 | 0.2381 | 0.0018 | 0.0039 | -0.6849 |
| `ablate_pipe_state_level` | NA | `fbeta` | `irc_alert` | `test` | 1 | 13,327 | 0.0286 | 0.4320 | 0.0221 | 0.0351 | -0.8183 |
| `ablate_pipe_state_level` | NA | `fbeta` | `irc_alert` | `test` | 2 | 13,327 | 0.2071 | 0.3874 | 0.1852 | 0.2284 | -0.6172 |
| `ablate_pipe_state_level` | NA | `fbeta` | `irc_alert` | `test` | 3 | 13,327 | 0.2114 | 0.3983 | 0.1892 | 0.2333 | -0.6111 |
| `ablate_pipe_state_level` | NA | `fixed` | `bloom_h` | `test` | 1 | 11,852 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.6206 |
| `ablate_pipe_state_level` | NA | `fixed` | `bloom_h` | `test` | 2 | 11,891 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.3961 |
| `ablate_pipe_state_level` | NA | `fixed` | `bloom_h` | `test` | 3 | 11,939 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.3280 |
| `ablate_pipe_state_level` | NA | `fixed` | `irc_alert` | `test` | 1 | 13,327 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.7923 |
| `ablate_pipe_state_level` | NA | `fixed` | `irc_alert` | `test` | 2 | 13,327 | 0.0006 | 0.7500 | 0.0003 | 0.0008 | -0.7438 |
| `ablate_pipe_state_level` | NA | `fixed` | `irc_alert` | `test` | 3 | 13,327 | 0.0011 | 0.5556 | 0.0007 | 0.0013 | -0.7111 |
| `control_observed` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 11,852 | 0.6782 | 0.6088 | 0.1385 | 0.6631 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 11,891 | 0.7137 | 0.5357 | 0.1730 | 0.6693 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 11,939 | 0.7183 | 0.5037 | 0.1904 | 0.6619 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 13,327 | 0.8499 | 0.7788 | 0.3639 | 0.8347 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 13,327 | 0.8250 | 0.7622 | 0.3749 | 0.8116 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 13,327 | 0.8539 | 0.7305 | 0.4166 | 0.8260 | 0.0000 |
| `control_observed` | NA | `fbeta` | `bloom_h` | `test` | 1 | 11,852 | 0.8242 | 0.4678 | 0.2190 | 0.7152 | 0.0000 |
| `control_observed` | NA | `fbeta` | `bloom_h` | `test` | 2 | 11,891 | 0.8569 | 0.4204 | 0.2647 | 0.7095 | 0.0000 |
| `control_observed` | NA | `fbeta` | `bloom_h` | `test` | 3 | 11,939 | 0.8902 | 0.3615 | 0.3288 | 0.6888 | 0.0000 |
| `control_observed` | NA | `fbeta` | `irc_alert` | `test` | 1 | 13,327 | 0.9386 | 0.6262 | 0.4998 | 0.8534 | 0.0000 |
| `control_observed` | NA | `fbeta` | `irc_alert` | `test` | 2 | 13,327 | 0.9565 | 0.5776 | 0.5736 | 0.8455 | 0.0000 |
| `control_observed` | NA | `fbeta` | `irc_alert` | `test` | 3 | 13,327 | 0.9423 | 0.5964 | 0.5631 | 0.8444 | 0.0000 |
| `control_observed` | NA | `fixed` | `bloom_h` | `test` | 1 | 11,852 | 0.6083 | 0.6752 | 0.1120 | 0.6206 | 0.0000 |
| `control_observed` | NA | `fixed` | `bloom_h` | `test` | 2 | 11,891 | 0.3543 | 0.7503 | 0.0613 | 0.3961 | 0.0000 |
| `control_observed` | NA | `fixed` | `bloom_h` | `test` | 3 | 11,939 | 0.2880 | 0.7403 | 0.0519 | 0.3280 | 0.0000 |
| `control_observed` | NA | `fixed` | `irc_alert` | `test` | 1 | 13,327 | 0.7826 | 0.8337 | 0.3130 | 0.7923 | 0.0000 |
| `control_observed` | NA | `fixed` | `irc_alert` | `test` | 2 | 13,327 | 0.7244 | 0.8379 | 0.2995 | 0.7446 | 0.0000 |
| `control_observed` | NA | `fixed` | `irc_alert` | `test` | 3 | 13,327 | 0.6853 | 0.8468 | 0.2884 | 0.7124 | 0.0000 |
| `random_pipe_state_dropout_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 11,852 | 0.4033 | 0.6000 | 0.0835 | 0.4316 | -0.2315 |
| `random_pipe_state_dropout_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 11,891 | 0.3892 | 0.5454 | 0.0927 | 0.4129 | -0.2564 |
| `random_pipe_state_dropout_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 11,939 | 0.3758 | 0.5426 | 0.0925 | 0.4004 | -0.2615 |
| `random_pipe_state_dropout_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 13,327 | 0.6078 | 0.7755 | 0.2613 | 0.6353 | -0.1994 |
| `random_pipe_state_dropout_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 13,327 | 0.5873 | 0.7724 | 0.2634 | 0.6169 | -0.1947 |
| `random_pipe_state_dropout_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 13,327 | 0.6434 | 0.7611 | 0.3013 | 0.6639 | -0.1621 |
| `random_pipe_state_dropout_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 11,852 | 0.5764 | 0.4810 | 0.1489 | 0.5544 | -0.1608 |
| `random_pipe_state_dropout_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 11,891 | 0.5764 | 0.4475 | 0.1673 | 0.5450 | -0.1645 |
| `random_pipe_state_dropout_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 11,939 | 0.6468 | 0.4051 | 0.2132 | 0.5779 | -0.1109 |
| `random_pipe_state_dropout_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 13,327 | 0.7408 | 0.6315 | 0.3912 | 0.7160 | -0.1374 |
| `random_pipe_state_dropout_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 13,327 | 0.8490 | 0.5714 | 0.5146 | 0.7738 | -0.0717 |
| `random_pipe_state_dropout_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 13,327 | 0.8604 | 0.5872 | 0.5222 | 0.7872 | -0.0572 |
| `random_pipe_state_dropout_25` | 20260612 | `fixed` | `bloom_h` | `test` | 1 | 11,852 | 0.3218 | 0.6511 | 0.0614 | 0.3580 | -0.2626 |
| `random_pipe_state_dropout_25` | 20260612 | `fixed` | `bloom_h` | `test` | 2 | 11,891 | 0.1205 | 0.6739 | 0.0232 | 0.1441 | -0.2519 |
| `random_pipe_state_dropout_25` | 20260612 | `fixed` | `bloom_h` | `test` | 3 | 11,939 | 0.0834 | 0.7514 | 0.0148 | 0.1015 | -0.2266 |
| `random_pipe_state_dropout_25` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 13,327 | 0.5569 | 0.8353 | 0.2223 | 0.5967 | -0.1956 |
| `random_pipe_state_dropout_25` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 13,327 | 0.4708 | 0.8525 | 0.1913 | 0.5171 | -0.2275 |
| `random_pipe_state_dropout_25` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 13,327 | 0.4048 | 0.8701 | 0.1658 | 0.4533 | -0.2591 |
| `random_pipe_state_dropout_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 11,852 | 0.4053 | 0.6304 | 0.0799 | 0.4365 | -0.2266 |
| `random_pipe_state_dropout_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 11,891 | 0.4074 | 0.5835 | 0.0907 | 0.4336 | -0.2357 |
| `random_pipe_state_dropout_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 11,939 | 0.3745 | 0.5729 | 0.0873 | 0.4024 | -0.2595 |
| `random_pipe_state_dropout_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 13,327 | 0.6100 | 0.7815 | 0.2603 | 0.6380 | -0.1966 |
| `random_pipe_state_dropout_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 13,327 | 0.5888 | 0.7858 | 0.2595 | 0.6199 | -0.1917 |
| `random_pipe_state_dropout_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 13,327 | 0.6307 | 0.7606 | 0.2956 | 0.6530 | -0.1730 |
| `random_pipe_state_dropout_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 11,852 | 0.5804 | 0.4844 | 0.1489 | 0.5583 | -0.1569 |
| `random_pipe_state_dropout_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 11,891 | 0.5641 | 0.4518 | 0.1621 | 0.5374 | -0.1721 |
| `random_pipe_state_dropout_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 11,939 | 0.6317 | 0.4093 | 0.2060 | 0.5698 | -0.1189 |
| `random_pipe_state_dropout_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 13,327 | 0.7464 | 0.6340 | 0.3926 | 0.7208 | -0.1326 |
| `random_pipe_state_dropout_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 13,327 | 0.8484 | 0.5728 | 0.5129 | 0.7739 | -0.0716 |
| `random_pipe_state_dropout_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 13,327 | 0.8579 | 0.5917 | 0.5168 | 0.7871 | -0.0573 |
| `random_pipe_state_dropout_25` | 20260613 | `fixed` | `bloom_h` | `test` | 1 | 11,852 | 0.3279 | 0.6803 | 0.0599 | 0.3658 | -0.2548 |
| `random_pipe_state_dropout_25` | 20260613 | `fixed` | `bloom_h` | `test` | 2 | 11,891 | 0.1218 | 0.7490 | 0.0211 | 0.1463 | -0.2498 |
| `random_pipe_state_dropout_25` | 20260613 | `fixed` | `bloom_h` | `test` | 3 | 11,939 | 0.0740 | 0.7239 | 0.0137 | 0.0902 | -0.2378 |
| `random_pipe_state_dropout_25` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 13,327 | 0.5500 | 0.8419 | 0.2178 | 0.5909 | -0.2014 |
| `random_pipe_state_dropout_25` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 13,327 | 0.4601 | 0.8596 | 0.1854 | 0.5073 | -0.2373 |
| `random_pipe_state_dropout_25` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 13,327 | 0.3975 | 0.8827 | 0.1605 | 0.4466 | -0.2659 |
| `random_pipe_state_dropout_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 11,852 | 0.4209 | 0.6194 | 0.0845 | 0.4497 | -0.2134 |
| `random_pipe_state_dropout_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 11,891 | 0.4009 | 0.5700 | 0.0913 | 0.4262 | -0.2431 |
| `random_pipe_state_dropout_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 11,939 | 0.3858 | 0.5658 | 0.0910 | 0.4120 | -0.2499 |
| `random_pipe_state_dropout_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 13,327 | 0.6121 | 0.7814 | 0.2612 | 0.6398 | -0.1949 |
| `random_pipe_state_dropout_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 13,327 | 0.5906 | 0.7784 | 0.2628 | 0.6205 | -0.1911 |
| `random_pipe_state_dropout_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 13,327 | 0.6432 | 0.7615 | 0.3010 | 0.6638 | -0.1622 |
| `random_pipe_state_dropout_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 11,852 | 0.5927 | 0.4874 | 0.1511 | 0.5681 | -0.1471 |
| `random_pipe_state_dropout_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 11,891 | 0.5842 | 0.4600 | 0.1649 | 0.5543 | -0.1553 |
| `random_pipe_state_dropout_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 11,939 | 0.6512 | 0.4129 | 0.2106 | 0.5838 | -0.1050 |
| `random_pipe_state_dropout_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 13,327 | 0.7500 | 0.6352 | 0.3937 | 0.7238 | -0.1296 |
| `random_pipe_state_dropout_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 13,327 | 0.8536 | 0.5725 | 0.5164 | 0.7772 | -0.0683 |
| `random_pipe_state_dropout_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 13,327 | 0.8615 | 0.5868 | 0.5233 | 0.7877 | -0.0567 |
| `random_pipe_state_dropout_25` | 20260614 | `fixed` | `bloom_h` | `test` | 1 | 11,852 | 0.3306 | 0.6635 | 0.0619 | 0.3675 | -0.2531 |
| `random_pipe_state_dropout_25` | 20260614 | `fixed` | `bloom_h` | `test` | 2 | 11,891 | 0.1166 | 0.7660 | 0.0198 | 0.1404 | -0.2557 |
| `random_pipe_state_dropout_25` | 20260614 | `fixed` | `bloom_h` | `test` | 3 | 11,939 | 0.0709 | 0.7584 | 0.0125 | 0.0866 | -0.2415 |
| `random_pipe_state_dropout_25` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 13,327 | 0.5565 | 0.8498 | 0.2184 | 0.5977 | -0.1946 |
| `random_pipe_state_dropout_25` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 13,327 | 0.4669 | 0.8538 | 0.1894 | 0.5134 | -0.2312 |
| `random_pipe_state_dropout_25` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 13,327 | 0.4015 | 0.8780 | 0.1630 | 0.4504 | -0.2621 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 11,852 | 0.6673 | 0.6109 | 0.1358 | 0.6552 | -0.0078 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 11,891 | 0.6988 | 0.5371 | 0.1690 | 0.6591 | -0.0101 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 11,939 | 0.7008 | 0.5052 | 0.1852 | 0.6504 | -0.0115 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 13,327 | 0.8346 | 0.7774 | 0.3580 | 0.8225 | -0.0122 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 13,327 | 0.8107 | 0.7620 | 0.3685 | 0.8004 | -0.0112 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 13,327 | 0.8451 | 0.7323 | 0.4113 | 0.8198 | -0.0062 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 11,852 | 0.8058 | 0.4681 | 0.2140 | 0.7042 | -0.0110 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 11,891 | 0.8368 | 0.4211 | 0.2580 | 0.6988 | -0.0107 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 11,939 | 0.8789 | 0.3630 | 0.3233 | 0.6843 | -0.0044 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 13,327 | 0.9257 | 0.6258 | 0.4933 | 0.8448 | -0.0087 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 13,327 | 0.9502 | 0.5760 | 0.5713 | 0.8409 | -0.0046 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 13,327 | 0.9381 | 0.5946 | 0.5623 | 0.8409 | -0.0034 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fixed` | `bloom_h` | `test` | 1 | 11,852 | 0.5988 | 0.6769 | 0.1099 | 0.6129 | -0.0077 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fixed` | `bloom_h` | `test` | 2 | 11,891 | 0.3465 | 0.7525 | 0.0598 | 0.3884 | -0.0077 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fixed` | `bloom_h` | `test` | 3 | 11,939 | 0.2804 | 0.7388 | 0.0507 | 0.3202 | -0.0079 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 13,327 | 0.7667 | 0.8332 | 0.3068 | 0.7791 | -0.0132 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 13,327 | 0.7080 | 0.8377 | 0.2927 | 0.7306 | -0.0140 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 13,327 | 0.6705 | 0.8480 | 0.2818 | 0.6998 | -0.0126 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 11,852 | 0.6714 | 0.6090 | 0.1370 | 0.6579 | -0.0052 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 11,891 | 0.6988 | 0.5344 | 0.1698 | 0.6583 | -0.0109 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 11,939 | 0.7058 | 0.5054 | 0.1864 | 0.6539 | -0.0080 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 13,327 | 0.8436 | 0.7788 | 0.3612 | 0.8298 | -0.0049 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 13,327 | 0.8187 | 0.7628 | 0.3717 | 0.8069 | -0.0047 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 13,327 | 0.8507 | 0.7323 | 0.4140 | 0.8241 | -0.0019 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 11,852 | 0.8167 | 0.4694 | 0.2163 | 0.7114 | -0.0038 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 11,891 | 0.8478 | 0.4210 | 0.2615 | 0.7049 | -0.0046 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 11,939 | 0.8808 | 0.3608 | 0.3259 | 0.6837 | -0.0050 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 13,327 | 0.9320 | 0.6277 | 0.4952 | 0.8496 | -0.0038 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 13,327 | 0.9549 | 0.5786 | 0.5717 | 0.8450 | -0.0005 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 13,327 | 0.9408 | 0.5978 | 0.5610 | 0.8440 | -0.0004 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fixed` | `bloom_h` | `test` | 1 | 11,852 | 0.5995 | 0.6777 | 0.1099 | 0.6136 | -0.0070 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fixed` | `bloom_h` | `test` | 2 | 11,891 | 0.3491 | 0.7486 | 0.0605 | 0.3908 | -0.0053 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fixed` | `bloom_h` | `test` | 3 | 11,939 | 0.2848 | 0.7443 | 0.0511 | 0.3249 | -0.0031 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 13,327 | 0.7754 | 0.8342 | 0.3100 | 0.7865 | -0.0058 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 13,327 | 0.7173 | 0.8393 | 0.2960 | 0.7388 | -0.0058 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 13,327 | 0.6771 | 0.8479 | 0.2846 | 0.7055 | -0.0070 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 11,852 | 0.6653 | 0.6064 | 0.1363 | 0.6526 | -0.0104 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 11,891 | 0.7001 | 0.5346 | 0.1700 | 0.6593 | -0.0100 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 11,939 | 0.7026 | 0.5031 | 0.1864 | 0.6510 | -0.0109 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 13,327 | 0.8393 | 0.7795 | 0.3590 | 0.8266 | -0.0080 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 13,327 | 0.8150 | 0.7622 | 0.3704 | 0.8038 | -0.0077 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 13,327 | 0.8457 | 0.7314 | 0.4121 | 0.8201 | -0.0059 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 11,852 | 0.8133 | 0.4665 | 0.2167 | 0.7080 | -0.0072 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 11,891 | 0.8426 | 0.4199 | 0.2605 | 0.7014 | -0.0081 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 11,939 | 0.8777 | 0.3609 | 0.3247 | 0.6823 | -0.0065 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 13,327 | 0.9282 | 0.6267 | 0.4939 | 0.8467 | -0.0067 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 13,327 | 0.9517 | 0.5771 | 0.5712 | 0.8423 | -0.0032 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 13,327 | 0.9394 | 0.5953 | 0.5624 | 0.8420 | -0.0023 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fixed` | `bloom_h` | `test` | 1 | 11,852 | 0.5981 | 0.6767 | 0.1099 | 0.6123 | -0.0083 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fixed` | `bloom_h` | `test` | 2 | 11,891 | 0.3452 | 0.7475 | 0.0600 | 0.3868 | -0.0092 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fixed` | `bloom_h` | `test` | 3 | 11,939 | 0.2779 | 0.7371 | 0.0503 | 0.3175 | -0.0106 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 13,327 | 0.7727 | 0.8343 | 0.3088 | 0.7843 | -0.0080 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 13,327 | 0.7140 | 0.8391 | 0.2947 | 0.7360 | -0.0086 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 13,327 | 0.6743 | 0.8478 | 0.2835 | 0.7031 | -0.0094 |

## Guardrails

- Labels are fixed and come from the undegraded sequence/split surfaces.
- Only PIPE sequence input columns are degraded in this evaluator.
- Seasonality columns are preserved by the configured scenario set.
- Raw-predictor family ablations remain queued for an upstream fuzzy-state rebuild.
- Degraded outputs are stress-test evidence, not official environmental alerts.

## Outputs

- State metrics: `reports/degradation/controlled_degradation_pipe_state_recompute_full_state_metrics.csv`
- Alert metrics: `reports/degradation/controlled_degradation_pipe_state_recompute_full_alert_metrics.csv`
- Policy metrics: `reports/degradation/controlled_degradation_pipe_state_recompute_full_policy_metrics.csv`
- Summary: `reports/degradation/controlled_degradation_pipe_state_recompute_full_summary.csv`
- Examples: `reports/degradation/controlled_degradation_pipe_state_recompute_full_examples.csv`
- Backtest rows: `None`
- Manifest: `reports/degradation/controlled_degradation_pipe_state_recompute_full_manifest.json`
