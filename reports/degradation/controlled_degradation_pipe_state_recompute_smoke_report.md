# Recomputed PIPE/GRU-D State Degradation Report

Generated at UTC: `2026-06-12T17:14:13.966579+00:00`
Started at UTC: `2026-06-12T17:13:29.699476+00:00`

## Scope

This report recomputes PIPE/GRU-D rollout scores after controlled degradation of PIPE sequence inputs.
It does not degrade raw panel predictors directly; raw-predictor degradation requires rebuilding fuzzy states and sequence datasets upstream.

## Configuration

- Config: `configs/degradation_scenarios.yaml`
- Scenario set: `pipe_state_recompute_smoke`
- Selected origins: `512`
- History length: `12`
- Rollout horizon: `3` month(s)
- Samples per origin: `1`
- Deterministic mode: `True`
- Max origins cap: `512`
- Calibrated bloom horizons available: `[1, 2, 3]`
- Rollout bloom calibrator horizons available: `[1, 2, 3]`
- Policies: `['closest_pr', 'fixed', 'fbeta']`
- Requested policy evaluation splits: `['test']`
- Observed policy metric splits: `['test']`
- Default downstream policy context: `closest_pr`

## Future Availability

| horizon | eligible origins | origins with observed future | selected origins | policy |
|---:|---:|---:|---:|---|
| 1 | 17,420 | 17,420 | 512 | `complete_horizons` |
| 2 | 17,420 | 15,268 | 512 | `complete_horizons` |
| 3 | 17,420 | 13,685 | 512 | `complete_horizons` |

## Scenario Summary

| scenario | status | seed | affected frame rows | affected frame cells | affected selected-window rows | affected selected-window cells | rollout rows | policy metric rows |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `ablate_pipe_state_level` | `evaluated` | NA | 2,068,291 | 5,460,016 | 5,490 | 14,223 | 1,536 | 72 |
| `control_observed` | `evaluated` | NA | 0 | 0 | 0 | 0 | 1,536 | 72 |
| `random_pipe_state_dropout_25` | `evaluated` | 20260612 | 1,745,390 | 3,434,413 | 4,695 | 9,540 | 1,536 | 72 |
| `random_pipe_state_dropout_25` | `evaluated` | 20260613 | 1,744,753 | 3,435,221 | 4,694 | 9,655 | 1,536 | 72 |
| `random_pipe_state_dropout_25` | `evaluated` | 20260614 | 1,744,751 | 3,433,142 | 4,633 | 9,397 | 1,536 | 72 |
| `temporal_pipe_state_blocks_3m_rate_10` | `evaluated` | 20260612 | 23,490 | 156,569 | 56 | 389 | 1,536 | 72 |
| `temporal_pipe_state_blocks_3m_rate_10` | `evaluated` | 20260613 | 22,935 | 153,028 | 75 | 496 | 1,536 | 72 |
| `temporal_pipe_state_blocks_3m_rate_10` | `evaluated` | 20260614 | 23,512 | 156,292 | 79 | 527 | 1,536 | 72 |

## State Metrics

| scenario | seed | split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE |
|---|---:|---|---:|---|---:|---:|---:|---:|---:|
| `ablate_pipe_state_level` | NA | `test` | 1 | `all` | 4,608 | 0.3247 | 0.3533 | 0.0808 | 0.1965 |
| `ablate_pipe_state_level` | NA | `test` | 1 | `irc1` | 512 | 0.3340 | 0.3520 | 0.0511 | 0.2414 |
| `ablate_pipe_state_level` | NA | `test` | 2 | `all` | 4,608 | 0.3227 | 0.3477 | 0.0719 | 0.1957 |
| `ablate_pipe_state_level` | NA | `test` | 2 | `irc1` | 512 | 0.3280 | 0.3579 | 0.0834 | 0.2415 |
| `ablate_pipe_state_level` | NA | `test` | 3 | `all` | 4,608 | 0.3210 | 0.3514 | 0.0866 | 0.1977 |
| `ablate_pipe_state_level` | NA | `test` | 3 | `irc1` | 512 | 0.3252 | 0.3627 | 0.1035 | 0.2438 |
| `control_observed` | NA | `test` | 1 | `all` | 4,608 | 0.1281 | 0.1838 | 0.3027 | 0.0589 |
| `control_observed` | NA | `test` | 1 | `irc1` | 512 | 0.1453 | 0.1686 | 0.1381 | 0.0962 |
| `control_observed` | NA | `test` | 2 | `all` | 4,608 | 0.1392 | 0.1795 | 0.2248 | 0.0658 |
| `control_observed` | NA | `test` | 2 | `irc1` | 512 | 0.1648 | 0.2035 | 0.1904 | 0.1166 |
| `control_observed` | NA | `test` | 3 | `all` | 4,608 | 0.1444 | 0.1898 | 0.2392 | 0.0712 |
| `control_observed` | NA | `test` | 3 | `irc1` | 512 | 0.1647 | 0.2184 | 0.2459 | 0.1199 |
| `random_pipe_state_dropout_25` | 20260612 | `test` | 1 | `all` | 4,608 | 0.2545 | 0.2818 | 0.0970 | 0.1341 |
| `random_pipe_state_dropout_25` | 20260612 | `test` | 1 | `irc1` | 512 | 0.2231 | 0.2479 | 0.0998 | 0.1504 |
| `random_pipe_state_dropout_25` | 20260612 | `test` | 2 | `all` | 4,608 | 0.2560 | 0.2774 | 0.0774 | 0.1376 |
| `random_pipe_state_dropout_25` | 20260612 | `test` | 2 | `irc1` | 512 | 0.2190 | 0.2577 | 0.1503 | 0.1547 |
| `random_pipe_state_dropout_25` | 20260612 | `test` | 3 | `all` | 4,608 | 0.2555 | 0.2842 | 0.1009 | 0.1408 |
| `random_pipe_state_dropout_25` | 20260612 | `test` | 3 | `irc1` | 512 | 0.2162 | 0.2717 | 0.2041 | 0.1586 |
| `random_pipe_state_dropout_25` | 20260613 | `test` | 1 | `all` | 4,608 | 0.2556 | 0.2823 | 0.0948 | 0.1360 |
| `random_pipe_state_dropout_25` | 20260613 | `test` | 1 | `irc1` | 512 | 0.2031 | 0.2270 | 0.1053 | 0.1417 |
| `random_pipe_state_dropout_25` | 20260613 | `test` | 2 | `all` | 4,608 | 0.2562 | 0.2785 | 0.0801 | 0.1382 |
| `random_pipe_state_dropout_25` | 20260613 | `test` | 2 | `irc1` | 512 | 0.2118 | 0.2519 | 0.1590 | 0.1536 |
| `random_pipe_state_dropout_25` | 20260613 | `test` | 3 | `all` | 4,608 | 0.2588 | 0.2845 | 0.0906 | 0.1437 |
| `random_pipe_state_dropout_25` | 20260613 | `test` | 3 | `irc1` | 512 | 0.2120 | 0.2596 | 0.1831 | 0.1565 |
| `random_pipe_state_dropout_25` | 20260614 | `test` | 1 | `all` | 4,608 | 0.2488 | 0.2745 | 0.0937 | 0.1310 |
| `random_pipe_state_dropout_25` | 20260614 | `test` | 1 | `irc1` | 512 | 0.2136 | 0.2343 | 0.0885 | 0.1441 |
| `random_pipe_state_dropout_25` | 20260614 | `test` | 2 | `all` | 4,608 | 0.2503 | 0.2737 | 0.0855 | 0.1343 |
| `random_pipe_state_dropout_25` | 20260614 | `test` | 2 | `irc1` | 512 | 0.2175 | 0.2568 | 0.1531 | 0.1569 |
| `random_pipe_state_dropout_25` | 20260614 | `test` | 3 | `all` | 4,608 | 0.2514 | 0.2763 | 0.0903 | 0.1381 |
| `random_pipe_state_dropout_25` | 20260614 | `test` | 3 | `irc1` | 512 | 0.2164 | 0.2628 | 0.1766 | 0.1606 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `test` | 1 | `all` | 4,608 | 0.1356 | 0.1890 | 0.2826 | 0.0616 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `test` | 1 | `irc1` | 512 | 0.1507 | 0.1754 | 0.1411 | 0.0992 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `test` | 2 | `all` | 4,608 | 0.1453 | 0.1849 | 0.2141 | 0.0683 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `test` | 2 | `irc1` | 512 | 0.1681 | 0.2088 | 0.1952 | 0.1190 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `test` | 3 | `all` | 4,608 | 0.1490 | 0.1938 | 0.2307 | 0.0733 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `test` | 3 | `irc1` | 512 | 0.1678 | 0.2227 | 0.2464 | 0.1221 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `test` | 1 | `all` | 4,608 | 0.1365 | 0.1892 | 0.2789 | 0.0624 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `test` | 1 | `irc1` | 512 | 0.1472 | 0.1705 | 0.1370 | 0.0966 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `test` | 2 | `all` | 4,608 | 0.1462 | 0.1853 | 0.2110 | 0.0691 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `test` | 2 | `irc1` | 512 | 0.1645 | 0.2047 | 0.1967 | 0.1165 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `test` | 3 | `all` | 4,608 | 0.1515 | 0.1953 | 0.2240 | 0.0747 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `test` | 3 | `irc1` | 512 | 0.1651 | 0.2198 | 0.2491 | 0.1202 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `test` | 1 | `all` | 4,608 | 0.1431 | 0.1950 | 0.2660 | 0.0653 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `test` | 1 | `irc1` | 512 | 0.1544 | 0.1797 | 0.1409 | 0.1010 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `test` | 2 | `all` | 4,608 | 0.1524 | 0.1909 | 0.2017 | 0.0716 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `test` | 2 | `irc1` | 512 | 0.1707 | 0.2121 | 0.1955 | 0.1196 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `test` | 3 | `all` | 4,608 | 0.1565 | 0.2002 | 0.2184 | 0.0768 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `test` | 3 | `irc1` | 512 | 0.1678 | 0.2241 | 0.2511 | 0.1218 |

## Alert Metrics

| scenario | seed | event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| `ablate_pipe_state_level` | NA | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0000 | 0.1211 | 0.1246 | 0.0000 |
| `ablate_pipe_state_level` | NA | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0000 | 0.1119 | 0.1257 | 0.0000 |
| `ablate_pipe_state_level` | NA | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0000 | 0.1260 | 0.1216 | 0.0000 |
| `ablate_pipe_state_level` | NA | `irc_alert` | `test` | 1 | 512 | 0.3379 | 0.0000 | 0.3379 | 0.3379 | 0.0000 |
| `ablate_pipe_state_level` | NA | `irc_alert` | `test` | 2 | 512 | 0.3477 | 0.0000 | 0.3477 | 0.3477 | 0.0000 |
| `ablate_pipe_state_level` | NA | `irc_alert` | `test` | 3 | 512 | 0.3535 | 0.0000 | 0.3535 | 0.3535 | 0.0000 |
| `control_observed` | NA | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0824 | 0.7159 | 0.0701 | 0.4667 |
| `control_observed` | NA | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0565 | 0.6988 | 0.0811 | 0.3548 |
| `control_observed` | NA | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0493 | 0.6033 | 0.0844 | 0.2742 |
| `control_observed` | NA | `irc_alert` | `test` | 1 | 512 | 0.3379 | 0.2871 | 0.7003 | 0.1406 | 0.7168 |
| `control_observed` | NA | `irc_alert` | `test` | 2 | 512 | 0.3477 | 0.2637 | 0.6658 | 0.1660 | 0.6404 |
| `control_observed` | NA | `irc_alert` | `test` | 3 | 512 | 0.3535 | 0.2559 | 0.6417 | 0.1836 | 0.6022 |
| `random_pipe_state_dropout_25` | 20260612 | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0477 | 0.4738 | 0.0933 | 0.2667 |
| `random_pipe_state_dropout_25` | 20260612 | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0283 | 0.5545 | 0.0969 | 0.1613 |
| `random_pipe_state_dropout_25` | 20260612 | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0150 | 0.4539 | 0.1020 | 0.0645 |
| `random_pipe_state_dropout_25` | 20260612 | `irc_alert` | `test` | 1 | 512 | 0.3379 | 0.2227 | 0.5874 | 0.2012 | 0.5318 |
| `random_pipe_state_dropout_25` | 20260612 | `irc_alert` | `test` | 2 | 512 | 0.3477 | 0.1914 | 0.5656 | 0.2227 | 0.4551 |
| `random_pipe_state_dropout_25` | 20260612 | `irc_alert` | `test` | 3 | 512 | 0.3535 | 0.1816 | 0.5928 | 0.2148 | 0.4530 |
| `random_pipe_state_dropout_25` | 20260613 | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0369 | 0.6556 | 0.0850 | 0.2500 |
| `random_pipe_state_dropout_25` | 20260613 | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0217 | 0.5758 | 0.0987 | 0.1613 |
| `random_pipe_state_dropout_25` | 20260613 | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0150 | 0.4662 | 0.1011 | 0.0806 |
| `random_pipe_state_dropout_25` | 20260613 | `irc_alert` | `test` | 1 | 512 | 0.3379 | 0.2168 | 0.6303 | 0.1797 | 0.5549 |
| `random_pipe_state_dropout_25` | 20260613 | `irc_alert` | `test` | 2 | 512 | 0.3477 | 0.1836 | 0.5894 | 0.2109 | 0.4607 |
| `random_pipe_state_dropout_25` | 20260613 | `irc_alert` | `test` | 3 | 512 | 0.3535 | 0.1660 | 0.5573 | 0.2344 | 0.4033 |
| `random_pipe_state_dropout_25` | 20260614 | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0412 | 0.5158 | 0.0912 | 0.2500 |
| `random_pipe_state_dropout_25` | 20260614 | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0261 | 0.5272 | 0.0997 | 0.1452 |
| `random_pipe_state_dropout_25` | 20260614 | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0193 | 0.4510 | 0.1018 | 0.0968 |
| `random_pipe_state_dropout_25` | 20260614 | `irc_alert` | `test` | 1 | 512 | 0.3379 | 0.2148 | 0.5953 | 0.1973 | 0.5260 |
| `random_pipe_state_dropout_25` | 20260614 | `irc_alert` | `test` | 2 | 512 | 0.3477 | 0.1914 | 0.5656 | 0.2227 | 0.4551 |
| `random_pipe_state_dropout_25` | 20260614 | `irc_alert` | `test` | 3 | 512 | 0.3535 | 0.1699 | 0.5719 | 0.2266 | 0.4199 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0824 | 0.7014 | 0.0713 | 0.4667 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0565 | 0.6950 | 0.0815 | 0.3548 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0493 | 0.5933 | 0.0853 | 0.2742 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `irc_alert` | `test` | 1 | 512 | 0.3379 | 0.2773 | 0.6897 | 0.1465 | 0.6936 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `irc_alert` | `test` | 2 | 512 | 0.3477 | 0.2578 | 0.6552 | 0.1719 | 0.6236 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `irc_alert` | `test` | 3 | 512 | 0.3535 | 0.2461 | 0.6247 | 0.1934 | 0.5746 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0824 | 0.7095 | 0.0707 | 0.4667 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0565 | 0.7004 | 0.0810 | 0.3548 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0493 | 0.5954 | 0.0850 | 0.2742 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `irc_alert` | `test` | 1 | 512 | 0.3379 | 0.2852 | 0.6966 | 0.1426 | 0.7110 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `irc_alert` | `test` | 2 | 512 | 0.3477 | 0.2637 | 0.6658 | 0.1660 | 0.6404 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `irc_alert` | `test` | 3 | 512 | 0.3535 | 0.2578 | 0.6379 | 0.1855 | 0.6022 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0781 | 0.6840 | 0.0731 | 0.4333 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0543 | 0.6636 | 0.0836 | 0.3226 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0471 | 0.5744 | 0.0864 | 0.2581 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `irc_alert` | `test` | 1 | 512 | 0.3379 | 0.2793 | 0.6856 | 0.1484 | 0.6936 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `irc_alert` | `test` | 2 | 512 | 0.3477 | 0.2559 | 0.6592 | 0.1699 | 0.6236 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `irc_alert` | `test` | 3 | 512 | 0.3535 | 0.2480 | 0.6353 | 0.1875 | 0.5856 |

## Policy Metrics

| scenario | seed | policy | event | split | horizon | rows | recall | precision | alert rate | F2 | delta F2 |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `ablate_pipe_state_level` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.6863 |
| `ablate_pipe_state_level` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.7100 |
| `ablate_pipe_state_level` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.6725 |
| `ablate_pipe_state_level` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.7390 |
| `ablate_pipe_state_level` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.6730 |
| `ablate_pipe_state_level` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.6374 |
| `ablate_pipe_state_level` | NA | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.7558 |
| `ablate_pipe_state_level` | NA | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.7083 |
| `ablate_pipe_state_level` | NA | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.6997 |
| `ablate_pipe_state_level` | NA | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.7390 |
| `ablate_pipe_state_level` | NA | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.6730 |
| `ablate_pipe_state_level` | NA | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.6374 |
| `ablate_pipe_state_level` | NA | `fixed` | `bloom_h` | `test` | 1 | 461 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.5036 |
| `ablate_pipe_state_level` | NA | `fixed` | `bloom_h` | `test` | 2 | 460 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.4015 |
| `ablate_pipe_state_level` | NA | `fixed` | `bloom_h` | `test` | 3 | 467 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.3137 |
| `ablate_pipe_state_level` | NA | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.7390 |
| `ablate_pipe_state_level` | NA | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.6730 |
| `ablate_pipe_state_level` | NA | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -0.6374 |
| `control_observed` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.7000 | 0.6364 | 0.1432 | 0.6863 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.7581 | 0.5663 | 0.1804 | 0.7100 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.7419 | 0.4894 | 0.2013 | 0.6725 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.7168 | 0.8435 | 0.2871 | 0.7390 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.6404 | 0.8444 | 0.2637 | 0.6730 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.6022 | 0.8321 | 0.2559 | 0.6374 | 0.0000 |
| `control_observed` | NA | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.8667 | 0.5000 | 0.2256 | 0.7558 | 0.0000 |
| `control_observed` | NA | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.8226 | 0.4554 | 0.2435 | 0.7083 | 0.0000 |
| `control_observed` | NA | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.8871 | 0.3793 | 0.3105 | 0.6997 | 0.0000 |
| `control_observed` | NA | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.7168 | 0.8435 | 0.2871 | 0.7390 | 0.0000 |
| `control_observed` | NA | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.6404 | 0.8444 | 0.2637 | 0.6730 | 0.0000 |
| `control_observed` | NA | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.6022 | 0.8321 | 0.2559 | 0.6374 | 0.0000 |
| `control_observed` | NA | `fixed` | `bloom_h` | `test` | 1 | 461 | 0.4667 | 0.7368 | 0.0824 | 0.5036 | 0.0000 |
| `control_observed` | NA | `fixed` | `bloom_h` | `test` | 2 | 460 | 0.3548 | 0.8462 | 0.0565 | 0.4015 | 0.0000 |
| `control_observed` | NA | `fixed` | `bloom_h` | `test` | 3 | 467 | 0.2742 | 0.7391 | 0.0493 | 0.3137 | 0.0000 |
| `control_observed` | NA | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.7168 | 0.8435 | 0.2871 | 0.7390 | 0.0000 |
| `control_observed` | NA | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.6404 | 0.8444 | 0.2637 | 0.6730 | 0.0000 |
| `control_observed` | NA | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.6022 | 0.8321 | 0.2559 | 0.6374 | 0.0000 |
| `random_pipe_state_dropout_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.4500 | 0.6136 | 0.0954 | 0.4754 | -0.2109 |
| `random_pipe_state_dropout_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.5000 | 0.5636 | 0.1196 | 0.5116 | -0.1984 |
| `random_pipe_state_dropout_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.4032 | 0.4630 | 0.1156 | 0.4139 | -0.2586 |
| `random_pipe_state_dropout_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.5318 | 0.8070 | 0.2227 | 0.5707 | -0.1683 |
| `random_pipe_state_dropout_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.4551 | 0.8265 | 0.1914 | 0.5000 | -0.1730 |
| `random_pipe_state_dropout_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.4530 | 0.8817 | 0.1816 | 0.5018 | -0.1356 |
| `random_pipe_state_dropout_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.5667 | 0.5152 | 0.1432 | 0.5556 | -0.2003 |
| `random_pipe_state_dropout_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.6129 | 0.4691 | 0.1761 | 0.5775 | -0.1308 |
| `random_pipe_state_dropout_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.6290 | 0.3824 | 0.2184 | 0.5571 | -0.1426 |
| `random_pipe_state_dropout_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.5318 | 0.8070 | 0.2227 | 0.5707 | -0.1683 |
| `random_pipe_state_dropout_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.4551 | 0.8265 | 0.1914 | 0.5000 | -0.1730 |
| `random_pipe_state_dropout_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.4530 | 0.8817 | 0.1816 | 0.5018 | -0.1356 |
| `random_pipe_state_dropout_25` | 20260612 | `fixed` | `bloom_h` | `test` | 1 | 461 | 0.2667 | 0.7273 | 0.0477 | 0.3053 | -0.1983 |
| `random_pipe_state_dropout_25` | 20260612 | `fixed` | `bloom_h` | `test` | 2 | 460 | 0.1613 | 0.7692 | 0.0283 | 0.1916 | -0.2099 |
| `random_pipe_state_dropout_25` | 20260612 | `fixed` | `bloom_h` | `test` | 3 | 467 | 0.0645 | 0.5714 | 0.0150 | 0.0784 | -0.2352 |
| `random_pipe_state_dropout_25` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.5318 | 0.8070 | 0.2227 | 0.5707 | -0.1683 |
| `random_pipe_state_dropout_25` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.4551 | 0.8265 | 0.1914 | 0.5000 | -0.1730 |
| `random_pipe_state_dropout_25` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.4530 | 0.8817 | 0.1816 | 0.5018 | -0.1356 |
| `random_pipe_state_dropout_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.5000 | 0.6977 | 0.0933 | 0.5300 | -0.1562 |
| `random_pipe_state_dropout_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.5000 | 0.6327 | 0.1065 | 0.5219 | -0.1881 |
| `random_pipe_state_dropout_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.4839 | 0.5455 | 0.1178 | 0.4950 | -0.1775 |
| `random_pipe_state_dropout_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.5549 | 0.8649 | 0.2168 | 0.5978 | -0.1412 |
| `random_pipe_state_dropout_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.4607 | 0.8723 | 0.1836 | 0.5087 | -0.1643 |
| `random_pipe_state_dropout_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.4033 | 0.8588 | 0.1660 | 0.4512 | -0.1863 |
| `random_pipe_state_dropout_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.7000 | 0.5753 | 0.1584 | 0.6709 | -0.0849 |
| `random_pipe_state_dropout_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.6452 | 0.5128 | 0.1696 | 0.6135 | -0.0948 |
| `random_pipe_state_dropout_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.6129 | 0.4270 | 0.1906 | 0.5638 | -0.1359 |
| `random_pipe_state_dropout_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.5549 | 0.8649 | 0.2168 | 0.5978 | -0.1412 |
| `random_pipe_state_dropout_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.4607 | 0.8723 | 0.1836 | 0.5087 | -0.1643 |
| `random_pipe_state_dropout_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.4033 | 0.8588 | 0.1660 | 0.4512 | -0.1863 |
| `random_pipe_state_dropout_25` | 20260613 | `fixed` | `bloom_h` | `test` | 1 | 461 | 0.2500 | 0.8824 | 0.0369 | 0.2918 | -0.2118 |
| `random_pipe_state_dropout_25` | 20260613 | `fixed` | `bloom_h` | `test` | 2 | 460 | 0.1613 | 1.0000 | 0.0217 | 0.1938 | -0.2077 |
| `random_pipe_state_dropout_25` | 20260613 | `fixed` | `bloom_h` | `test` | 3 | 467 | 0.0806 | 0.7143 | 0.0150 | 0.0980 | -0.2156 |
| `random_pipe_state_dropout_25` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.5549 | 0.8649 | 0.2168 | 0.5978 | -0.1412 |
| `random_pipe_state_dropout_25` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.4607 | 0.8723 | 0.1836 | 0.5087 | -0.1643 |
| `random_pipe_state_dropout_25` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.4033 | 0.8588 | 0.1660 | 0.4512 | -0.1863 |
| `random_pipe_state_dropout_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.4333 | 0.6190 | 0.0911 | 0.4610 | -0.2253 |
| `random_pipe_state_dropout_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.4839 | 0.5556 | 0.1174 | 0.4967 | -0.2133 |
| `random_pipe_state_dropout_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.4516 | 0.5091 | 0.1178 | 0.4620 | -0.2105 |
| `random_pipe_state_dropout_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.5260 | 0.8273 | 0.2148 | 0.5673 | -0.1716 |
| `random_pipe_state_dropout_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.4551 | 0.8265 | 0.1914 | 0.5000 | -0.1730 |
| `random_pipe_state_dropout_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.4199 | 0.8736 | 0.1699 | 0.4686 | -0.1689 |
| `random_pipe_state_dropout_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.5833 | 0.4730 | 0.1605 | 0.5573 | -0.1985 |
| `random_pipe_state_dropout_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.6129 | 0.4691 | 0.1761 | 0.5775 | -0.1308 |
| `random_pipe_state_dropout_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.6129 | 0.3762 | 0.2163 | 0.5444 | -0.1553 |
| `random_pipe_state_dropout_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.5260 | 0.8273 | 0.2148 | 0.5673 | -0.1716 |
| `random_pipe_state_dropout_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.4551 | 0.8265 | 0.1914 | 0.5000 | -0.1730 |
| `random_pipe_state_dropout_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.4199 | 0.8736 | 0.1699 | 0.4686 | -0.1689 |
| `random_pipe_state_dropout_25` | 20260614 | `fixed` | `bloom_h` | `test` | 1 | 461 | 0.2500 | 0.7895 | 0.0412 | 0.2896 | -0.2140 |
| `random_pipe_state_dropout_25` | 20260614 | `fixed` | `bloom_h` | `test` | 2 | 460 | 0.1452 | 0.7500 | 0.0261 | 0.1731 | -0.2284 |
| `random_pipe_state_dropout_25` | 20260614 | `fixed` | `bloom_h` | `test` | 3 | 467 | 0.0968 | 0.6667 | 0.0193 | 0.1167 | -0.1969 |
| `random_pipe_state_dropout_25` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.5260 | 0.8273 | 0.2148 | 0.5673 | -0.1716 |
| `random_pipe_state_dropout_25` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.4551 | 0.8265 | 0.1914 | 0.5000 | -0.1730 |
| `random_pipe_state_dropout_25` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.4199 | 0.8736 | 0.1699 | 0.4686 | -0.1689 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.6833 | 0.6308 | 0.1410 | 0.6721 | -0.0141 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.7419 | 0.5679 | 0.1761 | 0.6991 | -0.0109 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.7097 | 0.4944 | 0.1906 | 0.6528 | -0.0197 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.6936 | 0.8451 | 0.2773 | 0.7194 | -0.0196 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.6236 | 0.8409 | 0.2578 | 0.6576 | -0.0154 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.5746 | 0.8254 | 0.2461 | 0.6118 | -0.0257 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.8333 | 0.4902 | 0.2213 | 0.7310 | -0.0248 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.8065 | 0.4545 | 0.2391 | 0.6983 | -0.0100 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.8710 | 0.3750 | 0.3084 | 0.6888 | -0.0110 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.6936 | 0.8451 | 0.2773 | 0.7194 | -0.0196 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.6236 | 0.8409 | 0.2578 | 0.6576 | -0.0154 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.5746 | 0.8254 | 0.2461 | 0.6118 | -0.0257 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fixed` | `bloom_h` | `test` | 1 | 461 | 0.4667 | 0.7368 | 0.0824 | 0.5036 | 0.0000 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fixed` | `bloom_h` | `test` | 2 | 460 | 0.3548 | 0.8462 | 0.0565 | 0.4015 | 0.0000 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fixed` | `bloom_h` | `test` | 3 | 467 | 0.2742 | 0.7391 | 0.0493 | 0.3137 | 0.0000 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.6936 | 0.8451 | 0.2773 | 0.7194 | -0.0196 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.6236 | 0.8409 | 0.2578 | 0.6576 | -0.0154 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.5746 | 0.8254 | 0.2461 | 0.6118 | -0.0257 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.6833 | 0.6308 | 0.1410 | 0.6721 | -0.0141 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.7581 | 0.5732 | 0.1783 | 0.7121 | 0.0022 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.7258 | 0.4839 | 0.1991 | 0.6598 | -0.0127 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.7110 | 0.8425 | 0.2852 | 0.7339 | -0.0051 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.6404 | 0.8444 | 0.2637 | 0.6730 | 0.0000 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.6022 | 0.8258 | 0.2578 | 0.6367 | -0.0007 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.8500 | 0.5000 | 0.2213 | 0.7456 | -0.0102 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.8226 | 0.4554 | 0.2435 | 0.7083 | 0.0000 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.8710 | 0.3699 | 0.3126 | 0.6853 | -0.0145 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.7110 | 0.8425 | 0.2852 | 0.7339 | -0.0051 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.6404 | 0.8444 | 0.2637 | 0.6730 | 0.0000 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.6022 | 0.8258 | 0.2578 | 0.6367 | -0.0007 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fixed` | `bloom_h` | `test` | 1 | 461 | 0.4667 | 0.7368 | 0.0824 | 0.5036 | 0.0000 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fixed` | `bloom_h` | `test` | 2 | 460 | 0.3548 | 0.8462 | 0.0565 | 0.4015 | 0.0000 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fixed` | `bloom_h` | `test` | 3 | 467 | 0.2742 | 0.7391 | 0.0493 | 0.3137 | 0.0000 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.7110 | 0.8425 | 0.2852 | 0.7339 | -0.0051 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.6404 | 0.8444 | 0.2637 | 0.6730 | 0.0000 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.6022 | 0.8258 | 0.2578 | 0.6367 | -0.0007 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.6500 | 0.6190 | 0.1367 | 0.6436 | -0.0427 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.7097 | 0.5500 | 0.1739 | 0.6707 | -0.0392 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.6935 | 0.4778 | 0.1927 | 0.6361 | -0.0364 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.6936 | 0.8392 | 0.2793 | 0.7186 | -0.0204 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.6236 | 0.8473 | 0.2559 | 0.6584 | -0.0146 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.5856 | 0.8346 | 0.2480 | 0.6228 | -0.0146 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.8167 | 0.4851 | 0.2191 | 0.7185 | -0.0373 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.7742 | 0.4444 | 0.2348 | 0.6742 | -0.0342 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.8387 | 0.3741 | 0.2976 | 0.6718 | -0.0279 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.6936 | 0.8392 | 0.2793 | 0.7186 | -0.0204 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.6236 | 0.8473 | 0.2559 | 0.6584 | -0.0146 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.5856 | 0.8346 | 0.2480 | 0.6228 | -0.0146 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fixed` | `bloom_h` | `test` | 1 | 461 | 0.4333 | 0.7222 | 0.0781 | 0.4710 | -0.0326 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fixed` | `bloom_h` | `test` | 2 | 460 | 0.3226 | 0.8000 | 0.0543 | 0.3663 | -0.0352 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fixed` | `bloom_h` | `test` | 3 | 467 | 0.2581 | 0.7273 | 0.0471 | 0.2963 | -0.0174 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.6936 | 0.8392 | 0.2793 | 0.7186 | -0.0204 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.6236 | 0.8473 | 0.2559 | 0.6584 | -0.0146 |
| `temporal_pipe_state_blocks_3m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.5856 | 0.8346 | 0.2480 | 0.6228 | -0.0146 |

## Guardrails

- Labels are fixed and come from the undegraded sequence/split surfaces.
- Only PIPE sequence input columns are degraded in this evaluator.
- Seasonality columns are preserved by the configured scenario set.
- Raw-predictor family ablations remain queued for an upstream fuzzy-state rebuild.
- Degraded outputs are stress-test evidence, not official environmental alerts.

## Outputs

- State metrics: `reports/degradation/controlled_degradation_pipe_state_recompute_smoke_state_metrics.csv`
- Alert metrics: `reports/degradation/controlled_degradation_pipe_state_recompute_smoke_alert_metrics.csv`
- Policy metrics: `reports/degradation/controlled_degradation_pipe_state_recompute_smoke_policy_metrics.csv`
- Summary: `reports/degradation/controlled_degradation_pipe_state_recompute_smoke_summary.csv`
- Examples: `reports/degradation/controlled_degradation_pipe_state_recompute_smoke_examples.csv`
- Backtest rows: `None`
- Manifest: `reports/degradation/controlled_degradation_pipe_state_recompute_smoke_manifest.json`
