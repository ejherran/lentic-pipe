# Raw-Predictor Recomputed PIPE/GRU-D Degradation Report

Generated at UTC: `2026-06-15T13:35:22.331323+00:00`
Started at UTC: `2026-06-15T13:31:25.731325+00:00`

## Scope

This report degrades raw monthly panel predictors, rebuilds the deterministic fuzzy state, rebuilds PIPE sequence inputs, and recomputes frozen PIPE/GRU-D rollouts.
Observed labels and future states remain fixed from the undegraded canonical sequence/split surfaces.
Fuzzy IRC weights are frozen; no fuzzy weights, PIPE weights, calibrators, or alert thresholds are refit.

## Configuration

- Config: `configs/degradation_scenarios.yaml`
- Panel: `data/panel/panel_monthly_v0.parquet`
- Canonical sequences/labels: `data/pipe_grud/pipe_sequence_dataset_no_current_chla_wqp_focused_v0.parquet`
- Rebuilt input surface: `no_current_chla`
- Rebuilt source filter: `['wqp']`
- Fuzzy manifest for frozen weights: `reports/anfis/fuzzy_manifest.json`
- Fuzzy weight source: `fuzzy_manifest`
- Scenario set: `no_current_raw_smoke`
- Selected origins: `512`
- History length: `12`
- Rollout horizon: `3` month(s)
- Samples per origin: `1`
- Deterministic mode: `True`
- Max origins cap: `512`
- Policies: `['closest_pr', 'fixed', 'fbeta']`
- Requested policy evaluation splits: `['test']`
- Default downstream policy context: `closest_pr`
- Calibrated bloom horizons available: `[1, 2, 3]`
- Rollout bloom calibrator horizons available: `[1, 2, 3]`

## Evaluation Surface Diagnostics

| source | panel rows | panel sites | canonical sequence rows | selected origins | panel rows without sequence origin |
|---|---:|---:|---:|---:|---:|
| `wqp` | 1,626,672 | 106,719 | 986,674 | 512 | 639,998 |

## Control Rebuild Drift

| canonical sequence rows | rebuilt state rows | rebuilt sequence rows | alignment missing rows | sequence cells changed | selected-window cells changed |
|---:|---:|---:|---:|---:|---:|
| 986,674 | 1,626,672 | 986,674 | 0 | 0 | 0 |

## Selected-Window Input Changes

| scenario | input | rows | changed rows | mean before | mean after | mean delta | mean absolute delta |
|---|---|---:|---:|---:|---:|---:|---:|
| `ablate_light` | `x_irc_basis` | 4,692 | 4,383 | 0.5510 | 0.5366 | -0.0143 | 0.0362 |
| `ablate_light` | `x_yF` | 4,692 | 4,383 | 0.6012 | 0.6873 | 0.0861 | 0.2171 |
| `ablate_light` | `x_yN` | 4,692 | 0 | 0.4928 | 0.4928 | 0.0000 | 0.0000 |
| `ablate_light` | `x_yT` | 4,692 | 0 | 0.6036 | 0.6036 | 0.0000 | 0.0000 |
| `ablate_nutrients` | `x_irc_basis` | 4,692 | 4,254 | 0.5510 | 0.5522 | 0.0012 | 0.0425 |
| `ablate_nutrients` | `x_yF` | 4,692 | 0 | 0.6012 | 0.6012 | 0.0000 | 0.0000 |
| `ablate_nutrients` | `x_yN` | 4,692 | 4,254 | 0.4928 | 0.5000 | 0.0072 | 0.2548 |
| `ablate_nutrients` | `x_yT` | 4,692 | 0 | 0.6036 | 0.6036 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_irc_basis` | 4,692 | 0 | 0.5510 | 0.5510 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_yF` | 4,692 | 0 | 0.6012 | 0.6012 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_yN` | 4,692 | 0 | 0.4928 | 0.4928 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_yT` | 4,692 | 0 | 0.6036 | 0.6036 | 0.0000 | 0.0000 |
| `random_dropout_mcar_25` | `x_irc_basis` | 4,692 | 3,427 | 0.5510 | 0.5313 | -0.0197 | 0.0558 |
| `random_dropout_mcar_25` | `x_irc_basis` | 4,692 | 3,414 | 0.5510 | 0.5292 | -0.0218 | 0.0563 |
| `random_dropout_mcar_25` | `x_irc_basis` | 4,692 | 3,449 | 0.5510 | 0.5290 | -0.0220 | 0.0587 |
| `random_dropout_mcar_25` | `x_yF` | 4,692 | 2,128 | 0.6012 | 0.6091 | 0.0079 | 0.0862 |
| `random_dropout_mcar_25` | `x_yF` | 4,692 | 2,126 | 0.6012 | 0.6094 | 0.0082 | 0.0859 |
| `random_dropout_mcar_25` | `x_yF` | 4,692 | 2,083 | 0.6012 | 0.6059 | 0.0047 | 0.0838 |
| `random_dropout_mcar_25` | `x_yN` | 4,692 | 1,956 | 0.4928 | 0.4763 | -0.0164 | 0.0537 |
| `random_dropout_mcar_25` | `x_yN` | 4,692 | 1,907 | 0.4928 | 0.4745 | -0.0183 | 0.0546 |
| `random_dropout_mcar_25` | `x_yN` | 4,692 | 2,003 | 0.4928 | 0.4734 | -0.0193 | 0.0585 |
| `random_dropout_mcar_25` | `x_yT` | 4,692 | 661 | 0.6036 | 0.5802 | -0.0234 | 0.0567 |
| `random_dropout_mcar_25` | `x_yT` | 4,692 | 667 | 0.6036 | 0.5776 | -0.0260 | 0.0572 |
| `random_dropout_mcar_25` | `x_yT` | 4,692 | 692 | 0.6036 | 0.5766 | -0.0270 | 0.0602 |
| `temporal_blocks_3m_rate_10` | `x_irc_basis` | 4,692 | 20 | 0.5510 | 0.5508 | -0.0002 | 0.0006 |
| `temporal_blocks_3m_rate_10` | `x_irc_basis` | 4,692 | 13 | 0.5510 | 0.5506 | -0.0004 | 0.0006 |
| `temporal_blocks_3m_rate_10` | `x_irc_basis` | 4,692 | 11 | 0.5510 | 0.5509 | -0.0001 | 0.0003 |
| `temporal_blocks_3m_rate_10` | `x_yF` | 4,692 | 20 | 0.6012 | 0.6007 | -0.0005 | 0.0010 |
| `temporal_blocks_3m_rate_10` | `x_yF` | 4,692 | 13 | 0.6012 | 0.6012 | -0.0000 | 0.0008 |
| `temporal_blocks_3m_rate_10` | `x_yF` | 4,692 | 11 | 0.6012 | 0.6008 | -0.0004 | 0.0008 |
| `temporal_blocks_3m_rate_10` | `x_yN` | 4,692 | 19 | 0.4928 | 0.4933 | 0.0005 | 0.0009 |
| `temporal_blocks_3m_rate_10` | `x_yN` | 4,692 | 12 | 0.4928 | 0.4929 | 0.0001 | 0.0010 |
| `temporal_blocks_3m_rate_10` | `x_yN` | 4,692 | 11 | 0.4928 | 0.4931 | 0.0003 | 0.0009 |
| `temporal_blocks_3m_rate_10` | `x_yT` | 4,692 | 11 | 0.6036 | 0.6031 | -0.0005 | 0.0007 |
| `temporal_blocks_3m_rate_10` | `x_yT` | 4,692 | 6 | 0.6036 | 0.6030 | -0.0006 | 0.0006 |
| `temporal_blocks_3m_rate_10` | `x_yT` | 4,692 | 5 | 0.6036 | 0.6032 | -0.0004 | 0.0004 |

## Future Availability

| horizon | eligible origins | origins with observed future | selected origins | policy |
|---:|---:|---:|---:|---|
| 1 | 7,582 | 7,582 | 512 | `complete_horizons` |
| 2 | 7,582 | 6,826 | 512 | `complete_horizons` |
| 3 | 7,582 | 6,345 | 512 | `complete_horizons` |

## Scenario Summary

| scenario | status | seed | raw cells | sequence cells | selected-window cells | rollout rows | policy metric rows |
|---|---|---:|---:|---:|---:|---:|---:|
| `ablate_light` | `evaluated` | NA | 10,190,837 | 2,300,449 | 12,727 | 1,536 | 30 |
| `ablate_nutrients` | `evaluated` | NA | 6,377,245 | 1,039,421 | 12,664 | 1,536 | 30 |
| `control_observed` | `evaluated` | NA | 0 | 0 | 0 | 1,536 | 30 |
| `random_dropout_mcar_25` | `evaluated` | 20260612 | 9,650,241 | 2,269,705 | 18,006 | 1,536 | 30 |
| `random_dropout_mcar_25` | `evaluated` | 20260613 | 9,646,358 | 2,267,308 | 17,942 | 1,536 | 30 |
| `random_dropout_mcar_25` | `evaluated` | 20260614 | 9,649,621 | 2,267,290 | 18,143 | 1,536 | 30 |
| `temporal_blocks_3m_rate_10` | `evaluated` | 20260612 | 365,277 | 30,361 | 165 | 1,536 | 30 |
| `temporal_blocks_3m_rate_10` | `evaluated` | 20260613 | 359,217 | 29,707 | 99 | 1,536 | 30 |
| `temporal_blocks_3m_rate_10` | `evaluated` | 20260614 | 370,507 | 30,950 | 89 | 1,536 | 30 |

## State Metrics

| scenario | seed | split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE |
|---|---:|---|---:|---|---:|---:|---:|---:|---:|
| `ablate_light` | NA | `test` | 1 | `all` | 4,608 | 0.1974 | 0.2391 | 0.1744 | 0.1343 |
| `ablate_light` | NA | `test` | 1 | `irc1` | 512 | 0.2072 | 0.2006 | -0.0327 | 0.1600 |
| `ablate_light` | NA | `test` | 2 | `all` | 4,608 | 0.2499 | 0.2490 | -0.0036 | 0.1743 |
| `ablate_light` | NA | `test` | 2 | `irc1` | 512 | 0.2982 | 0.2600 | -0.1468 | 0.2546 |
| `ablate_light` | NA | `test` | 3 | `all` | 4,608 | 0.2648 | 0.2637 | -0.0042 | 0.1876 |
| `ablate_light` | NA | `test` | 3 | `irc1` | 512 | 0.3282 | 0.3017 | -0.0878 | 0.2770 |
| `ablate_nutrients` | NA | `test` | 1 | `all` | 4,608 | 0.2435 | 0.2780 | 0.1241 | 0.1628 |
| `ablate_nutrients` | NA | `test` | 1 | `irc1` | 512 | 0.1656 | 0.2098 | 0.2103 | 0.1303 |
| `ablate_nutrients` | NA | `test` | 2 | `all` | 4,608 | 0.2725 | 0.2872 | 0.0510 | 0.1908 |
| `ablate_nutrients` | NA | `test` | 2 | `irc1` | 512 | 0.2103 | 0.2688 | 0.2175 | 0.1708 |
| `ablate_nutrients` | NA | `test` | 3 | `all` | 4,608 | 0.2807 | 0.3011 | 0.0675 | 0.2021 |
| `ablate_nutrients` | NA | `test` | 3 | `irc1` | 512 | 0.2307 | 0.3100 | 0.2558 | 0.1876 |
| `control_observed` | NA | `test` | 1 | `all` | 4,608 | 0.1495 | 0.2104 | 0.2895 | 0.0946 |
| `control_observed` | NA | `test` | 1 | `irc1` | 512 | 0.1510 | 0.1864 | 0.1899 | 0.1171 |
| `control_observed` | NA | `test` | 2 | `all` | 4,608 | 0.1951 | 0.2230 | 0.1248 | 0.1287 |
| `control_observed` | NA | `test` | 2 | `irc1` | 512 | 0.2022 | 0.2484 | 0.1858 | 0.1653 |
| `control_observed` | NA | `test` | 3 | `all` | 4,608 | 0.2160 | 0.2400 | 0.0998 | 0.1449 |
| `control_observed` | NA | `test` | 3 | `irc1` | 512 | 0.2256 | 0.2909 | 0.2245 | 0.1846 |
| `random_dropout_mcar_25` | 20260612 | `test` | 1 | `all` | 4,608 | 0.1836 | 0.2557 | 0.2822 | 0.1275 |
| `random_dropout_mcar_25` | 20260612 | `test` | 1 | `irc1` | 512 | 0.1757 | 0.1956 | 0.1019 | 0.1375 |
| `random_dropout_mcar_25` | 20260612 | `test` | 2 | `all` | 4,608 | 0.2195 | 0.2613 | 0.1600 | 0.1538 |
| `random_dropout_mcar_25` | 20260612 | `test` | 2 | `irc1` | 512 | 0.2325 | 0.2390 | 0.0270 | 0.1936 |
| `random_dropout_mcar_25` | 20260612 | `test` | 3 | `all` | 4,608 | 0.2327 | 0.2733 | 0.1487 | 0.1645 |
| `random_dropout_mcar_25` | 20260612 | `test` | 3 | `irc1` | 512 | 0.2599 | 0.2746 | 0.0537 | 0.2141 |
| `random_dropout_mcar_25` | 20260613 | `test` | 1 | `all` | 4,608 | 0.1820 | 0.2549 | 0.2861 | 0.1271 |
| `random_dropout_mcar_25` | 20260613 | `test` | 1 | `irc1` | 512 | 0.1759 | 0.1976 | 0.1097 | 0.1400 |
| `random_dropout_mcar_25` | 20260613 | `test` | 2 | `all` | 4,608 | 0.2199 | 0.2612 | 0.1580 | 0.1540 |
| `random_dropout_mcar_25` | 20260613 | `test` | 2 | `irc1` | 512 | 0.2359 | 0.2474 | 0.0464 | 0.1963 |
| `random_dropout_mcar_25` | 20260613 | `test` | 3 | `all` | 4,608 | 0.2346 | 0.2740 | 0.1438 | 0.1655 |
| `random_dropout_mcar_25` | 20260613 | `test` | 3 | `irc1` | 512 | 0.2654 | 0.2823 | 0.0599 | 0.2176 |
| `random_dropout_mcar_25` | 20260614 | `test` | 1 | `all` | 4,608 | 0.1805 | 0.2507 | 0.2802 | 0.1245 |
| `random_dropout_mcar_25` | 20260614 | `test` | 1 | `irc1` | 512 | 0.1768 | 0.1907 | 0.0727 | 0.1392 |
| `random_dropout_mcar_25` | 20260614 | `test` | 2 | `all` | 4,608 | 0.2178 | 0.2575 | 0.1543 | 0.1522 |
| `random_dropout_mcar_25` | 20260614 | `test` | 2 | `irc1` | 512 | 0.2332 | 0.2400 | 0.0286 | 0.1923 |
| `random_dropout_mcar_25` | 20260614 | `test` | 3 | `all` | 4,608 | 0.2325 | 0.2712 | 0.1427 | 0.1635 |
| `random_dropout_mcar_25` | 20260614 | `test` | 3 | `irc1` | 512 | 0.2626 | 0.2777 | 0.0543 | 0.2147 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 1 | `all` | 4,608 | 0.1504 | 0.2112 | 0.2879 | 0.0952 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 1 | `irc1` | 512 | 0.1509 | 0.1865 | 0.1908 | 0.1174 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 2 | `all` | 4,608 | 0.1959 | 0.2237 | 0.1241 | 0.1293 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 2 | `irc1` | 512 | 0.2024 | 0.2485 | 0.1853 | 0.1655 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 3 | `all` | 4,608 | 0.2169 | 0.2407 | 0.0990 | 0.1456 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 3 | `irc1` | 512 | 0.2263 | 0.2911 | 0.2227 | 0.1853 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 1 | `all` | 4,608 | 0.1501 | 0.2105 | 0.2871 | 0.0949 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 1 | `irc1` | 512 | 0.1516 | 0.1866 | 0.1875 | 0.1175 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 2 | `all` | 4,608 | 0.1957 | 0.2232 | 0.1234 | 0.1290 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 2 | `irc1` | 512 | 0.2028 | 0.2485 | 0.1840 | 0.1654 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 3 | `all` | 4,608 | 0.2165 | 0.2402 | 0.0989 | 0.1452 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 3 | `irc1` | 512 | 0.2264 | 0.2911 | 0.2224 | 0.1852 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 1 | `all` | 4,608 | 0.1507 | 0.2117 | 0.2884 | 0.0953 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 1 | `irc1` | 512 | 0.1507 | 0.1870 | 0.1939 | 0.1169 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 2 | `all` | 4,608 | 0.1955 | 0.2233 | 0.1245 | 0.1290 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 2 | `irc1` | 512 | 0.2018 | 0.2487 | 0.1886 | 0.1648 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 3 | `all` | 4,608 | 0.2167 | 0.2411 | 0.1011 | 0.1454 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 3 | `irc1` | 512 | 0.2249 | 0.2909 | 0.2267 | 0.1841 |

## Alert Metrics

| scenario | seed | event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| `ablate_light` | NA | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0450 | 0.2905 | 0.1466 | 0.1029 |
| `ablate_light` | NA | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.0331 | 0.3882 | 0.1526 | 0.0694 |
| `ablate_light` | NA | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.0294 | 0.3272 | 0.1446 | 0.0435 |
| `ablate_light` | NA | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.2656 | 0.7005 | 0.2891 | 0.4769 |
| `ablate_light` | NA | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.1348 | 0.5763 | 0.4180 | 0.2201 |
| `ablate_light` | NA | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.1055 | 0.5219 | 0.4629 | 0.1412 |
| `ablate_nutrients` | NA | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0500 | 0.2475 | 0.1421 | 0.0882 |
| `ablate_nutrients` | NA | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.0433 | 0.3251 | 0.1412 | 0.0972 |
| `ablate_nutrients` | NA | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.0858 | 0.2643 | 0.1361 | 0.1449 |
| `ablate_nutrients` | NA | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.5195 | 0.7271 | 0.2148 | 0.8000 |
| `ablate_nutrients` | NA | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.4668 | 0.6588 | 0.2891 | 0.6757 |
| `ablate_nutrients` | NA | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.4199 | 0.5638 | 0.3945 | 0.5255 |
| `control_observed` | NA | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0525 | 0.3747 | 0.1300 | 0.1471 |
| `control_observed` | NA | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.1094 | 0.4663 | 0.1248 | 0.3194 |
| `control_observed` | NA | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.1324 | 0.3466 | 0.1297 | 0.2899 |
| `control_observed` | NA | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.5020 | 0.7576 | 0.1895 | 0.8077 |
| `control_observed` | NA | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.4180 | 0.6669 | 0.2871 | 0.6293 |
| `control_observed` | NA | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.4062 | 0.6112 | 0.3379 | 0.5686 |
| `random_dropout_mcar_25` | 20260612 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0225 | 0.3439 | 0.1360 | 0.0588 |
| `random_dropout_mcar_25` | 20260612 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.0407 | 0.4633 | 0.1348 | 0.1250 |
| `random_dropout_mcar_25` | 20260612 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.0686 | 0.3438 | 0.1342 | 0.1449 |
| `random_dropout_mcar_25` | 20260612 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.3770 | 0.7055 | 0.2598 | 0.6154 |
| `random_dropout_mcar_25` | 20260612 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.3008 | 0.6167 | 0.3535 | 0.4479 |
| `random_dropout_mcar_25` | 20260612 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.2773 | 0.5974 | 0.3652 | 0.4118 |
| `random_dropout_mcar_25` | 20260613 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0225 | 0.3568 | 0.1347 | 0.0441 |
| `random_dropout_mcar_25` | 20260613 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.0331 | 0.4009 | 0.1407 | 0.0833 |
| `random_dropout_mcar_25` | 20260613 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.0588 | 0.3412 | 0.1324 | 0.1304 |
| `random_dropout_mcar_25` | 20260613 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.3789 | 0.6856 | 0.2773 | 0.6000 |
| `random_dropout_mcar_25` | 20260613 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.2910 | 0.6321 | 0.3398 | 0.4517 |
| `random_dropout_mcar_25` | 20260613 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.2598 | 0.5786 | 0.3867 | 0.3725 |
| `random_dropout_mcar_25` | 20260614 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0300 | 0.3466 | 0.1343 | 0.0882 |
| `random_dropout_mcar_25` | 20260614 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.0534 | 0.4152 | 0.1392 | 0.1389 |
| `random_dropout_mcar_25` | 20260614 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.0735 | 0.3158 | 0.1358 | 0.1304 |
| `random_dropout_mcar_25` | 20260614 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.3906 | 0.7091 | 0.2539 | 0.6346 |
| `random_dropout_mcar_25` | 20260614 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.3203 | 0.6296 | 0.3379 | 0.4826 |
| `random_dropout_mcar_25` | 20260614 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.2852 | 0.5818 | 0.3809 | 0.4039 |
| `temporal_blocks_3m_rate_10` | 20260612 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0525 | 0.3748 | 0.1300 | 0.1471 |
| `temporal_blocks_3m_rate_10` | 20260612 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.1094 | 0.4659 | 0.1248 | 0.3194 |
| `temporal_blocks_3m_rate_10` | 20260612 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.1324 | 0.3465 | 0.1297 | 0.2899 |
| `temporal_blocks_3m_rate_10` | 20260612 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.5000 | 0.7559 | 0.1914 | 0.8038 |
| `temporal_blocks_3m_rate_10` | 20260612 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.4180 | 0.6669 | 0.2871 | 0.6293 |
| `temporal_blocks_3m_rate_10` | 20260612 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.4062 | 0.6112 | 0.3379 | 0.5686 |
| `temporal_blocks_3m_rate_10` | 20260613 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0525 | 0.3731 | 0.1303 | 0.1471 |
| `temporal_blocks_3m_rate_10` | 20260613 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.1094 | 0.4638 | 0.1252 | 0.3194 |
| `temporal_blocks_3m_rate_10` | 20260613 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.1324 | 0.3443 | 0.1301 | 0.2899 |
| `temporal_blocks_3m_rate_10` | 20260613 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.5000 | 0.7559 | 0.1914 | 0.8038 |
| `temporal_blocks_3m_rate_10` | 20260613 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.4160 | 0.6652 | 0.2891 | 0.6255 |
| `temporal_blocks_3m_rate_10` | 20260613 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.4043 | 0.6096 | 0.3398 | 0.5647 |
| `temporal_blocks_3m_rate_10` | 20260614 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0525 | 0.3745 | 0.1301 | 0.1471 |
| `temporal_blocks_3m_rate_10` | 20260614 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.1094 | 0.4658 | 0.1248 | 0.3194 |
| `temporal_blocks_3m_rate_10` | 20260614 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.1324 | 0.3466 | 0.1297 | 0.2899 |
| `temporal_blocks_3m_rate_10` | 20260614 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.5020 | 0.7576 | 0.1895 | 0.8077 |
| `temporal_blocks_3m_rate_10` | 20260614 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.4180 | 0.6669 | 0.2871 | 0.6293 |
| `temporal_blocks_3m_rate_10` | 20260614 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.4062 | 0.6112 | 0.3379 | 0.5686 |

## Policy Metrics

| scenario | seed | policy | event | split | horizon | rows | recall | precision | alert rate | F2 | delta F2 |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `ablate_light` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.2206 | 0.4167 | 0.0900 | 0.2435 | -0.2373 |
| `ablate_light` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.2361 | 0.6071 | 0.0712 | 0.2690 | -0.3079 |
| `ablate_light` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.2464 | 0.4359 | 0.0956 | 0.2698 | -0.3053 |
| `ablate_light` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.4769 | 0.9118 | 0.2656 | 0.5272 | -0.2823 |
| `ablate_light` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.2201 | 0.8261 | 0.1348 | 0.2579 | -0.3941 |
| `ablate_light` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.1412 | 0.6667 | 0.1055 | 0.1676 | -0.4228 |
| `ablate_light` | NA | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.2941 | 0.3509 | 0.1425 | 0.3040 | -0.2406 |
| `ablate_light` | NA | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.2639 | 0.5758 | 0.0840 | 0.2960 | -0.2852 |
| `ablate_light` | NA | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.2464 | 0.4048 | 0.1029 | 0.2673 | -0.3162 |
| `ablate_light` | NA | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.4769 | 0.9118 | 0.2656 | 0.5272 | -0.2823 |
| `ablate_light` | NA | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.2201 | 0.8261 | 0.1348 | 0.2579 | -0.3941 |
| `ablate_light` | NA | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.1412 | 0.6667 | 0.1055 | 0.1676 | -0.4228 |
| `ablate_light` | NA | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.4769 | 0.9118 | 0.2656 | 0.5272 | -0.2823 |
| `ablate_light` | NA | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.2201 | 0.8261 | 0.1348 | 0.2579 | -0.3941 |
| `ablate_light` | NA | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.1412 | 0.6667 | 0.1055 | 0.1676 | -0.4228 |
| `ablate_nutrients` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.2941 | 0.2532 | 0.1975 | 0.2849 | -0.1959 |
| `ablate_nutrients` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.5000 | 0.3529 | 0.2595 | 0.4615 | -0.1154 |
| `ablate_nutrients` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.6377 | 0.2683 | 0.4020 | 0.5000 | -0.0751 |
| `ablate_nutrients` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.8000 | 0.7820 | 0.5195 | 0.7963 | -0.0132 |
| `ablate_nutrients` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.6757 | 0.7322 | 0.4668 | 0.6863 | 0.0343 |
| `ablate_nutrients` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.5255 | 0.6233 | 0.4199 | 0.5425 | -0.0479 |
| `ablate_nutrients` | NA | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.5735 | 0.2484 | 0.3925 | 0.4545 | -0.0900 |
| `ablate_nutrients` | NA | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.5972 | 0.3282 | 0.3333 | 0.5131 | -0.0680 |
| `ablate_nutrients` | NA | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.6522 | 0.2528 | 0.4363 | 0.4956 | -0.0879 |
| `ablate_nutrients` | NA | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.8000 | 0.7820 | 0.5195 | 0.7963 | -0.0132 |
| `ablate_nutrients` | NA | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.6757 | 0.7322 | 0.4668 | 0.6863 | 0.0343 |
| `ablate_nutrients` | NA | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.5255 | 0.6233 | 0.4199 | 0.5425 | -0.0479 |
| `ablate_nutrients` | NA | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.8000 | 0.7820 | 0.5195 | 0.7963 | -0.0132 |
| `ablate_nutrients` | NA | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.6757 | 0.7322 | 0.4668 | 0.6863 | 0.0343 |
| `ablate_nutrients` | NA | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.5255 | 0.6233 | 0.4199 | 0.5425 | -0.0479 |
| `control_observed` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.5147 | 0.3804 | 0.2300 | 0.4808 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.6250 | 0.4412 | 0.2595 | 0.5769 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.7101 | 0.3267 | 0.3676 | 0.5751 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.8077 | 0.8171 | 0.5020 | 0.8096 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
| `control_observed` | NA | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.6471 | 0.3333 | 0.3300 | 0.5446 | 0.0000 |
| `control_observed` | NA | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.6667 | 0.3840 | 0.3181 | 0.5811 | 0.0000 |
| `control_observed` | NA | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.7391 | 0.3168 | 0.3946 | 0.5835 | 0.0000 |
| `control_observed` | NA | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.8077 | 0.8171 | 0.5020 | 0.8096 | 0.0000 |
| `control_observed` | NA | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `control_observed` | NA | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
| `control_observed` | NA | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.8077 | 0.8171 | 0.5020 | 0.8096 | 0.0000 |
| `control_observed` | NA | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `control_observed` | NA | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.3382 | 0.5000 | 0.1150 | 0.3616 | -0.1191 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.4028 | 0.5179 | 0.1425 | 0.4215 | -0.1554 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.4493 | 0.3333 | 0.2279 | 0.4201 | -0.1551 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.6154 | 0.8290 | 0.3770 | 0.6488 | -0.1607 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.4479 | 0.7532 | 0.3008 | 0.4874 | -0.1646 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.4118 | 0.7394 | 0.2773 | 0.4518 | -0.1386 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.4706 | 0.3855 | 0.2075 | 0.4507 | -0.0939 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.5000 | 0.5000 | 0.1832 | 0.5000 | -0.0811 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.4783 | 0.3267 | 0.2475 | 0.4377 | -0.1459 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.6154 | 0.8290 | 0.3770 | 0.6488 | -0.1607 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.4479 | 0.7532 | 0.3008 | 0.4874 | -0.1646 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.4118 | 0.7394 | 0.2773 | 0.4518 | -0.1386 |
| `random_dropout_mcar_25` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.6154 | 0.8290 | 0.3770 | 0.6488 | -0.1607 |
| `random_dropout_mcar_25` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.4479 | 0.7532 | 0.3008 | 0.4874 | -0.1646 |
| `random_dropout_mcar_25` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.4118 | 0.7394 | 0.2773 | 0.4518 | -0.1386 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.2941 | 0.4000 | 0.1250 | 0.3106 | -0.1702 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.3750 | 0.4426 | 0.1552 | 0.3868 | -0.1901 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.5217 | 0.3636 | 0.2426 | 0.4800 | -0.0951 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.6000 | 0.8041 | 0.3789 | 0.6321 | -0.1775 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.4517 | 0.7852 | 0.2910 | 0.4937 | -0.1583 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.3725 | 0.7143 | 0.2598 | 0.4120 | -0.1784 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.4853 | 0.3750 | 0.2200 | 0.4583 | -0.0862 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.4583 | 0.4074 | 0.2061 | 0.4472 | -0.1340 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.5652 | 0.3611 | 0.2647 | 0.5078 | -0.0757 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.6000 | 0.8041 | 0.3789 | 0.6321 | -0.1775 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.4517 | 0.7852 | 0.2910 | 0.4937 | -0.1583 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.3725 | 0.7143 | 0.2598 | 0.4120 | -0.1784 |
| `random_dropout_mcar_25` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.6000 | 0.8041 | 0.3789 | 0.6321 | -0.1775 |
| `random_dropout_mcar_25` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.4517 | 0.7852 | 0.2910 | 0.4937 | -0.1583 |
| `random_dropout_mcar_25` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.3725 | 0.7143 | 0.2598 | 0.4120 | -0.1784 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.2941 | 0.4000 | 0.1250 | 0.3106 | -0.1702 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.3611 | 0.4194 | 0.1578 | 0.3714 | -0.2055 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.5652 | 0.3714 | 0.2574 | 0.5118 | -0.0633 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.6346 | 0.8250 | 0.3906 | 0.6653 | -0.1442 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.4826 | 0.7622 | 0.3203 | 0.5208 | -0.1312 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.4039 | 0.7055 | 0.2852 | 0.4417 | -0.1487 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.4853 | 0.3750 | 0.2200 | 0.4583 | -0.0862 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.4583 | 0.4125 | 0.2036 | 0.4484 | -0.1327 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.5797 | 0.3509 | 0.2794 | 0.5128 | -0.0707 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.6346 | 0.8250 | 0.3906 | 0.6653 | -0.1442 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.4826 | 0.7622 | 0.3203 | 0.5208 | -0.1312 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.4039 | 0.7055 | 0.2852 | 0.4417 | -0.1487 |
| `random_dropout_mcar_25` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.6346 | 0.8250 | 0.3906 | 0.6653 | -0.1442 |
| `random_dropout_mcar_25` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.4826 | 0.7622 | 0.3203 | 0.5208 | -0.1312 |
| `random_dropout_mcar_25` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.4039 | 0.7055 | 0.2852 | 0.4417 | -0.1487 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.5147 | 0.3804 | 0.2300 | 0.4808 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.6250 | 0.4412 | 0.2595 | 0.5769 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.7101 | 0.3267 | 0.3676 | 0.5751 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.8038 | 0.8164 | 0.5000 | 0.8063 | -0.0032 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.6471 | 0.3333 | 0.3300 | 0.5446 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.6667 | 0.3840 | 0.3181 | 0.5811 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.7391 | 0.3168 | 0.3946 | 0.5835 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.8038 | 0.8164 | 0.5000 | 0.8063 | -0.0032 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.8038 | 0.8164 | 0.5000 | 0.8063 | -0.0032 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.5147 | 0.3804 | 0.2300 | 0.4808 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.6250 | 0.4412 | 0.2595 | 0.5769 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.6957 | 0.3221 | 0.3652 | 0.5647 | -0.0104 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.8038 | 0.8164 | 0.5000 | 0.8063 | -0.0032 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.6255 | 0.7606 | 0.4160 | 0.6485 | -0.0035 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.5647 | 0.6957 | 0.4043 | 0.5868 | -0.0036 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.6324 | 0.3282 | 0.3275 | 0.5335 | -0.0111 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.6667 | 0.3840 | 0.3181 | 0.5811 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.7246 | 0.3125 | 0.3922 | 0.5734 | -0.0101 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.8038 | 0.8164 | 0.5000 | 0.8063 | -0.0032 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.6255 | 0.7606 | 0.4160 | 0.6485 | -0.0035 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.5647 | 0.6957 | 0.4043 | 0.5868 | -0.0036 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.8038 | 0.8164 | 0.5000 | 0.8063 | -0.0032 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.6255 | 0.7606 | 0.4160 | 0.6485 | -0.0035 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.5647 | 0.6957 | 0.4043 | 0.5868 | -0.0036 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.5147 | 0.3804 | 0.2300 | 0.4808 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.6250 | 0.4412 | 0.2595 | 0.5769 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.7101 | 0.3267 | 0.3676 | 0.5751 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.8077 | 0.8171 | 0.5020 | 0.8096 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.6471 | 0.3333 | 0.3300 | 0.5446 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.6667 | 0.3840 | 0.3181 | 0.5811 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.7391 | 0.3168 | 0.3946 | 0.5835 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.8077 | 0.8171 | 0.5020 | 0.8096 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.8077 | 0.8171 | 0.5020 | 0.8096 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |

## Guardrails

- Labels and observed future fuzzy states come from the undegraded canonical sequence/split artifacts.
- Raw predictor degradation is propagated only through the fuzzy state and PIPE input sequence rebuild.
- This experiment measures operational dependence of the current pipeline, not ecological causal importance.
- Chl-a memory is a target-proximal predictor; early-warning claims require a no-current-Chl-a evaluation surface.
- Fuzzy IRC weights are frozen from the current fuzzy manifest, not re-optimized under degradation.
- PIPE/GRU-D model weights, calibrators, and policy thresholds are frozen.
- Degraded outputs are stress-test evidence, not official environmental alerts.

## Outputs

- State metrics: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_smoke_state_metrics.csv`
- Alert metrics: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_smoke_alert_metrics.csv`
- Policy metrics: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_smoke_policy_metrics.csv`
- Summary: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_smoke_summary.csv`
- Examples: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_smoke_examples.csv`
- Diagnostics: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_smoke_diagnostics.csv`
- Backtest rows: `None`
- Manifest: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_smoke_manifest.json`
