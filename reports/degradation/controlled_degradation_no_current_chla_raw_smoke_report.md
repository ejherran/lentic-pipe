# Raw-Predictor Recomputed PIPE/GRU-D Degradation Report

Generated at UTC: `2026-06-15T13:25:57.467915+00:00`
Started at UTC: `2026-06-15T13:17:45.813506+00:00`

## Scope

This report degrades raw monthly panel predictors, rebuilds the deterministic fuzzy state, rebuilds PIPE sequence inputs, and recomputes frozen PIPE/GRU-D rollouts.
Observed labels and future states remain fixed from the undegraded canonical sequence/split surfaces.
Fuzzy IRC weights are frozen; no fuzzy weights, PIPE weights, calibrators, or alert thresholds are refit.

## Configuration

- Config: `configs/degradation_scenarios.yaml`
- Panel: `data/panel/panel_monthly_v0.parquet`
- Canonical sequences/labels: `data/pipe_grud/pipe_sequence_dataset_no_current_chla_v0.parquet`
- Rebuilt input surface: `no_current_chla`
- Rebuilt source filter: `all`
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
| `aquamatch_chla` | 1,755,072 | 141,544 | 1,078,238 | 290 | 676,834 |
| `lakebed_us_cse` | 4,932 | 21 | 4,112 | 1 | 820 |
| `nla` | 4,052 | 2,902 | 0 | 0 | 4,052 |
| `wqp` | 1,626,672 | 106,719 | 986,674 | 221 | 639,998 |

## Control Rebuild Drift

| canonical sequence rows | rebuilt state rows | rebuilt sequence rows | alignment missing rows | sequence cells changed | selected-window cells changed |
|---:|---:|---:|---:|---:|---:|
| 2,069,024 | 3,390,728 | 2,069,024 | 0 | 0 | 0 |

## Selected-Window Input Changes

| scenario | input | rows | changed rows | mean before | mean after | mean delta | mean absolute delta |
|---|---|---:|---:|---:|---:|---:|---:|
| `ablate_light` | `x_irc_basis` | 5,490 | 2,227 | 0.5256 | 0.5177 | -0.0079 | 0.0143 |
| `ablate_light` | `x_yF` | 5,490 | 2,227 | 0.5443 | 0.5916 | 0.0473 | 0.0857 |
| `ablate_light` | `x_yN` | 5,490 | 0 | 0.5017 | 0.5017 | 0.0000 | 0.0000 |
| `ablate_light` | `x_yT` | 5,490 | 0 | 0.5490 | 0.5490 | 0.0000 | 0.0000 |
| `ablate_nutrients` | `x_irc_basis` | 5,490 | 2,097 | 0.5256 | 0.5253 | -0.0003 | 0.0180 |
| `ablate_nutrients` | `x_yF` | 5,490 | 0 | 0.5443 | 0.5443 | 0.0000 | 0.0000 |
| `ablate_nutrients` | `x_yN` | 5,490 | 2,097 | 0.5017 | 0.5000 | -0.0017 | 0.1078 |
| `ablate_nutrients` | `x_yT` | 5,490 | 0 | 0.5490 | 0.5490 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_irc_basis` | 5,490 | 0 | 0.5256 | 0.5256 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_yF` | 5,490 | 0 | 0.5443 | 0.5443 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_yN` | 5,490 | 0 | 0.5017 | 0.5017 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_yT` | 5,490 | 0 | 0.5490 | 0.5490 | 0.0000 | 0.0000 |
| `random_dropout_mcar_25` | `x_irc_basis` | 5,490 | 1,734 | 0.5256 | 0.5151 | -0.0105 | 0.0262 |
| `random_dropout_mcar_25` | `x_irc_basis` | 5,490 | 1,759 | 0.5256 | 0.5171 | -0.0085 | 0.0269 |
| `random_dropout_mcar_25` | `x_irc_basis` | 5,490 | 1,733 | 0.5256 | 0.5138 | -0.0118 | 0.0263 |
| `random_dropout_mcar_25` | `x_yF` | 5,490 | 1,093 | 0.5443 | 0.5472 | 0.0029 | 0.0354 |
| `random_dropout_mcar_25` | `x_yF` | 5,490 | 1,134 | 0.5443 | 0.5475 | 0.0032 | 0.0348 |
| `random_dropout_mcar_25` | `x_yF` | 5,490 | 1,130 | 0.5443 | 0.5491 | 0.0048 | 0.0345 |
| `random_dropout_mcar_25` | `x_yN` | 5,490 | 925 | 0.5017 | 0.4952 | -0.0066 | 0.0229 |
| `random_dropout_mcar_25` | `x_yN` | 5,490 | 907 | 0.5017 | 0.4932 | -0.0085 | 0.0227 |
| `random_dropout_mcar_25` | `x_yN` | 5,490 | 914 | 0.5017 | 0.4947 | -0.0070 | 0.0231 |
| `random_dropout_mcar_25` | `x_yT` | 5,490 | 394 | 0.5490 | 0.5356 | -0.0134 | 0.0285 |
| `random_dropout_mcar_25` | `x_yT` | 5,490 | 399 | 0.5490 | 0.5392 | -0.0098 | 0.0299 |
| `random_dropout_mcar_25` | `x_yT` | 5,490 | 387 | 0.5490 | 0.5343 | -0.0148 | 0.0284 |
| `temporal_blocks_3m_rate_10` | `x_irc_basis` | 5,490 | 4 | 0.5256 | 0.5258 | 0.0002 | 0.0002 |
| `temporal_blocks_3m_rate_10` | `x_irc_basis` | 5,490 | 11 | 0.5256 | 0.5257 | 0.0001 | 0.0004 |
| `temporal_blocks_3m_rate_10` | `x_irc_basis` | 5,490 | 12 | 0.5256 | 0.5253 | -0.0003 | 0.0003 |
| `temporal_blocks_3m_rate_10` | `x_yF` | 5,490 | 4 | 0.5443 | 0.5440 | -0.0002 | 0.0002 |
| `temporal_blocks_3m_rate_10` | `x_yF` | 5,490 | 11 | 0.5443 | 0.5440 | -0.0003 | 0.0006 |
| `temporal_blocks_3m_rate_10` | `x_yF` | 5,490 | 12 | 0.5443 | 0.5439 | -0.0004 | 0.0008 |
| `temporal_blocks_3m_rate_10` | `x_yN` | 5,490 | 4 | 0.5017 | 0.5020 | 0.0003 | 0.0003 |
| `temporal_blocks_3m_rate_10` | `x_yN` | 5,490 | 8 | 0.5017 | 0.5019 | 0.0002 | 0.0004 |
| `temporal_blocks_3m_rate_10` | `x_yN` | 5,490 | 12 | 0.5017 | 0.5022 | 0.0005 | 0.0007 |
| `temporal_blocks_3m_rate_10` | `x_yT` | 5,490 | 3 | 0.5490 | 0.5492 | 0.0002 | 0.0002 |
| `temporal_blocks_3m_rate_10` | `x_yT` | 5,490 | 9 | 0.5490 | 0.5491 | 0.0000 | 0.0005 |
| `temporal_blocks_3m_rate_10` | `x_yT` | 5,490 | 9 | 0.5490 | 0.5484 | -0.0006 | 0.0006 |

## Future Availability

| horizon | eligible origins | origins with observed future | selected origins | policy |
|---:|---:|---:|---:|---|
| 1 | 17,420 | 17,420 | 512 | `complete_horizons` |
| 2 | 17,420 | 15,268 | 512 | `complete_horizons` |
| 3 | 17,420 | 13,685 | 512 | `complete_horizons` |

## Scenario Summary

| scenario | status | seed | raw cells | sequence cells | selected-window cells | rollout rows | policy metric rows |
|---|---|---:|---:|---:|---:|---:|---:|
| `ablate_light` | `evaluated` | NA | 10,220,097 | 2,309,107 | 6,512 | 1,536 | 60 |
| `ablate_nutrients` | `evaluated` | NA | 6,503,188 | 1,049,437 | 6,230 | 1,536 | 60 |
| `control_observed` | `evaluated` | NA | 0 | 0 | 0 | 1,536 | 60 |
| `random_dropout_mcar_25` | `evaluated` | 20260612 | 13,378,058 | 2,283,399 | 9,232 | 1,536 | 60 |
| `random_dropout_mcar_25` | `evaluated` | 20260613 | 13,370,716 | 2,282,024 | 9,316 | 1,536 | 60 |
| `random_dropout_mcar_25` | `evaluated` | 20260614 | 13,376,697 | 2,281,573 | 9,298 | 1,536 | 60 |
| `temporal_blocks_3m_rate_10` | `evaluated` | 20260612 | 540,648 | 30,864 | 39 | 1,536 | 60 |
| `temporal_blocks_3m_rate_10` | `evaluated` | 20260613 | 547,847 | 31,502 | 91 | 1,536 | 60 |
| `temporal_blocks_3m_rate_10` | `evaluated` | 20260614 | 539,433 | 30,611 | 107 | 1,536 | 60 |

## State Metrics

| scenario | seed | split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE |
|---|---:|---|---:|---|---:|---:|---:|---:|---:|
| `ablate_light` | NA | `test` | 1 | `all` | 4,608 | 0.1492 | 0.1811 | 0.1760 | 0.0827 |
| `ablate_light` | NA | `test` | 1 | `irc1` | 512 | 0.1630 | 0.1731 | 0.0587 | 0.1183 |
| `ablate_light` | NA | `test` | 2 | `all` | 4,608 | 0.2167 | 0.1852 | -0.1696 | 0.1231 |
| `ablate_light` | NA | `test` | 2 | `irc1` | 512 | 0.2282 | 0.1989 | -0.1471 | 0.1813 |
| `ablate_light` | NA | `test` | 3 | `all` | 4,608 | 0.2339 | 0.2082 | -0.1236 | 0.1371 |
| `ablate_light` | NA | `test` | 3 | `irc1` | 512 | 0.2822 | 0.2383 | -0.1843 | 0.2348 |
| `ablate_nutrients` | NA | `test` | 1 | `all` | 4,608 | 0.1796 | 0.1993 | 0.0988 | 0.0988 |
| `ablate_nutrients` | NA | `test` | 1 | `irc1` | 512 | 0.1529 | 0.1754 | 0.1284 | 0.1122 |
| `ablate_nutrients` | NA | `test` | 2 | `all` | 4,608 | 0.2385 | 0.2042 | -0.1678 | 0.1375 |
| `ablate_nutrients` | NA | `test` | 2 | `irc1` | 512 | 0.2134 | 0.2020 | -0.0562 | 0.1689 |
| `ablate_nutrients` | NA | `test` | 3 | `all` | 4,608 | 0.2478 | 0.2240 | -0.1060 | 0.1466 |
| `ablate_nutrients` | NA | `test` | 3 | `irc1` | 512 | 0.2578 | 0.2405 | -0.0721 | 0.2115 |
| `control_observed` | NA | `test` | 1 | `all` | 4,608 | 0.1292 | 0.1644 | 0.2137 | 0.0684 |
| `control_observed` | NA | `test` | 1 | `irc1` | 512 | 0.1458 | 0.1676 | 0.1299 | 0.1044 |
| `control_observed` | NA | `test` | 2 | `all` | 4,608 | 0.1962 | 0.1692 | -0.1592 | 0.1048 |
| `control_observed` | NA | `test` | 2 | `irc1` | 512 | 0.2074 | 0.1948 | -0.0647 | 0.1637 |
| `control_observed` | NA | `test` | 3 | `all` | 4,608 | 0.2124 | 0.1945 | -0.0917 | 0.1184 |
| `control_observed` | NA | `test` | 3 | `irc1` | 512 | 0.2498 | 0.2328 | -0.0733 | 0.2031 |
| `random_dropout_mcar_25` | 20260612 | `test` | 1 | `all` | 4,608 | 0.1475 | 0.1852 | 0.2038 | 0.0825 |
| `random_dropout_mcar_25` | 20260612 | `test` | 1 | `irc1` | 512 | 0.1531 | 0.1716 | 0.1080 | 0.1124 |
| `random_dropout_mcar_25` | 20260612 | `test` | 2 | `all` | 4,608 | 0.2079 | 0.1901 | -0.0933 | 0.1163 |
| `random_dropout_mcar_25` | 20260612 | `test` | 2 | `irc1` | 512 | 0.2131 | 0.1951 | -0.0920 | 0.1702 |
| `random_dropout_mcar_25` | 20260612 | `test` | 3 | `all` | 4,608 | 0.2221 | 0.2114 | -0.0507 | 0.1280 |
| `random_dropout_mcar_25` | 20260612 | `test` | 3 | `irc1` | 512 | 0.2534 | 0.2265 | -0.1185 | 0.2084 |
| `random_dropout_mcar_25` | 20260613 | `test` | 1 | `all` | 4,608 | 0.1514 | 0.1887 | 0.1975 | 0.0846 |
| `random_dropout_mcar_25` | 20260613 | `test` | 1 | `irc1` | 512 | 0.1578 | 0.1741 | 0.0940 | 0.1146 |
| `random_dropout_mcar_25` | 20260613 | `test` | 2 | `all` | 4,608 | 0.2102 | 0.1938 | -0.0849 | 0.1187 |
| `random_dropout_mcar_25` | 20260613 | `test` | 2 | `irc1` | 512 | 0.2155 | 0.1942 | -0.1100 | 0.1713 |
| `random_dropout_mcar_25` | 20260613 | `test` | 3 | `all` | 4,608 | 0.2243 | 0.2141 | -0.0476 | 0.1301 |
| `random_dropout_mcar_25` | 20260613 | `test` | 3 | `irc1` | 512 | 0.2578 | 0.2293 | -0.1242 | 0.2113 |
| `random_dropout_mcar_25` | 20260614 | `test` | 1 | `all` | 4,608 | 0.1496 | 0.1881 | 0.2046 | 0.0842 |
| `random_dropout_mcar_25` | 20260614 | `test` | 1 | `irc1` | 512 | 0.1558 | 0.1725 | 0.0967 | 0.1133 |
| `random_dropout_mcar_25` | 20260614 | `test` | 2 | `all` | 4,608 | 0.2077 | 0.1859 | -0.1172 | 0.1172 |
| `random_dropout_mcar_25` | 20260614 | `test` | 2 | `irc1` | 512 | 0.2096 | 0.1879 | -0.1150 | 0.1666 |
| `random_dropout_mcar_25` | 20260614 | `test` | 3 | `all` | 4,608 | 0.2223 | 0.2091 | -0.0630 | 0.1287 |
| `random_dropout_mcar_25` | 20260614 | `test` | 3 | `irc1` | 512 | 0.2549 | 0.2220 | -0.1483 | 0.2096 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 1 | `all` | 4,608 | 0.1293 | 0.1644 | 0.2133 | 0.0684 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 1 | `irc1` | 512 | 0.1459 | 0.1676 | 0.1294 | 0.1045 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 2 | `all` | 4,608 | 0.1962 | 0.1692 | -0.1593 | 0.1048 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 2 | `irc1` | 512 | 0.2075 | 0.1948 | -0.0655 | 0.1639 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 3 | `all` | 4,608 | 0.2123 | 0.1945 | -0.0916 | 0.1183 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 3 | `irc1` | 512 | 0.2500 | 0.2328 | -0.0741 | 0.2032 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 1 | `all` | 4,608 | 0.1296 | 0.1649 | 0.2141 | 0.0686 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 1 | `irc1` | 512 | 0.1458 | 0.1675 | 0.1300 | 0.1043 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 2 | `all` | 4,608 | 0.1964 | 0.1702 | -0.1536 | 0.1050 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 2 | `irc1` | 512 | 0.2074 | 0.1948 | -0.0649 | 0.1638 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 3 | `all` | 4,608 | 0.2122 | 0.1948 | -0.0894 | 0.1182 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 3 | `irc1` | 512 | 0.2499 | 0.2328 | -0.0736 | 0.2031 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 1 | `all` | 4,608 | 0.1302 | 0.1649 | 0.2103 | 0.0688 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 1 | `irc1` | 512 | 0.1457 | 0.1675 | 0.1300 | 0.1044 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 2 | `all` | 4,608 | 0.1968 | 0.1698 | -0.1589 | 0.1052 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 2 | `irc1` | 512 | 0.2077 | 0.1944 | -0.0680 | 0.1641 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 3 | `all` | 4,608 | 0.2129 | 0.1949 | -0.0924 | 0.1187 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 3 | `irc1` | 512 | 0.2502 | 0.2325 | -0.0760 | 0.2036 |

## Alert Metrics

| scenario | seed | event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| `ablate_light` | NA | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0108 | 0.2191 | 0.1169 | 0.0167 |
| `ablate_light` | NA | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0087 | 0.2688 | 0.1176 | 0.0323 |
| `ablate_light` | NA | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0021 | 0.2566 | 0.1178 | 0.0161 |
| `ablate_light` | NA | `irc_alert` | `test` | 1 | 512 | 0.3828 | 0.1484 | 0.5533 | 0.2695 | 0.3418 |
| `ablate_light` | NA | `irc_alert` | `test` | 2 | 512 | 0.3926 | 0.0938 | 0.4622 | 0.3418 | 0.1841 |
| `ablate_light` | NA | `irc_alert` | `test` | 3 | 512 | 0.3672 | 0.0488 | 0.4200 | 0.3340 | 0.1117 |
| `ablate_nutrients` | NA | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0065 | 0.2075 | 0.1126 | 0.0167 |
| `ablate_nutrients` | NA | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0000 | 0.2489 | 0.1160 | 0.0000 |
| `ablate_nutrients` | NA | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0000 | 0.2569 | 0.1150 | 0.0000 |
| `ablate_nutrients` | NA | `irc_alert` | `test` | 1 | 512 | 0.3828 | 0.2324 | 0.6032 | 0.2324 | 0.5000 |
| `ablate_nutrients` | NA | `irc_alert` | `test` | 2 | 512 | 0.3926 | 0.1797 | 0.5265 | 0.2949 | 0.3532 |
| `ablate_nutrients` | NA | `irc_alert` | `test` | 3 | 512 | 0.3672 | 0.1328 | 0.4834 | 0.2930 | 0.2819 |
| `control_observed` | NA | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0195 | 0.2961 | 0.1106 | 0.0167 |
| `control_observed` | NA | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0130 | 0.3065 | 0.1123 | 0.0645 |
| `control_observed` | NA | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0193 | 0.3113 | 0.1100 | 0.0806 |
| `control_observed` | NA | `irc_alert` | `test` | 1 | 512 | 0.3828 | 0.2109 | 0.5963 | 0.2383 | 0.4643 |
| `control_observed` | NA | `irc_alert` | `test` | 2 | 512 | 0.3926 | 0.1699 | 0.5301 | 0.2930 | 0.3433 |
| `control_observed` | NA | `irc_alert` | `test` | 3 | 512 | 0.3672 | 0.1426 | 0.5192 | 0.2715 | 0.3245 |
| `random_dropout_mcar_25` | 20260612 | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0217 | 0.2631 | 0.1118 | 0.0667 |
| `random_dropout_mcar_25` | 20260612 | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0261 | 0.2998 | 0.1129 | 0.0806 |
| `random_dropout_mcar_25` | 20260612 | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0257 | 0.3439 | 0.1080 | 0.1290 |
| `random_dropout_mcar_25` | 20260612 | `irc_alert` | `test` | 1 | 512 | 0.3828 | 0.1934 | 0.5824 | 0.2480 | 0.4286 |
| `random_dropout_mcar_25` | 20260612 | `irc_alert` | `test` | 2 | 512 | 0.3926 | 0.1562 | 0.5223 | 0.2988 | 0.3184 |
| `random_dropout_mcar_25` | 20260612 | `irc_alert` | `test` | 3 | 512 | 0.3672 | 0.1270 | 0.5144 | 0.2754 | 0.2979 |
| `random_dropout_mcar_25` | 20260613 | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0152 | 0.2590 | 0.1125 | 0.0167 |
| `random_dropout_mcar_25` | 20260613 | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0109 | 0.2767 | 0.1154 | 0.0323 |
| `random_dropout_mcar_25` | 20260613 | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0193 | 0.2666 | 0.1138 | 0.0645 |
| `random_dropout_mcar_25` | 20260613 | `irc_alert` | `test` | 1 | 512 | 0.3828 | 0.1777 | 0.5453 | 0.2715 | 0.3776 |
| `random_dropout_mcar_25` | 20260613 | `irc_alert` | `test` | 2 | 512 | 0.3926 | 0.1387 | 0.5029 | 0.3125 | 0.2786 |
| `random_dropout_mcar_25` | 20260613 | `irc_alert` | `test` | 3 | 512 | 0.3672 | 0.1152 | 0.4949 | 0.2871 | 0.2660 |
| `random_dropout_mcar_25` | 20260614 | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0130 | 0.2421 | 0.1141 | 0.0333 |
| `random_dropout_mcar_25` | 20260614 | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0174 | 0.2913 | 0.1141 | 0.0645 |
| `random_dropout_mcar_25` | 20260614 | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0150 | 0.2647 | 0.1138 | 0.0323 |
| `random_dropout_mcar_25` | 20260614 | `irc_alert` | `test` | 1 | 512 | 0.3828 | 0.1875 | 0.5667 | 0.2578 | 0.4082 |
| `random_dropout_mcar_25` | 20260614 | `irc_alert` | `test` | 2 | 512 | 0.3926 | 0.1582 | 0.5438 | 0.2852 | 0.3383 |
| `random_dropout_mcar_25` | 20260614 | `irc_alert` | `test` | 3 | 512 | 0.3672 | 0.1328 | 0.5316 | 0.2656 | 0.3191 |
| `temporal_blocks_3m_rate_10` | 20260612 | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0195 | 0.2961 | 0.1106 | 0.0167 |
| `temporal_blocks_3m_rate_10` | 20260612 | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0130 | 0.3067 | 0.1122 | 0.0645 |
| `temporal_blocks_3m_rate_10` | 20260612 | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0193 | 0.3114 | 0.1100 | 0.0806 |
| `temporal_blocks_3m_rate_10` | 20260612 | `irc_alert` | `test` | 1 | 512 | 0.3828 | 0.2109 | 0.5963 | 0.2383 | 0.4643 |
| `temporal_blocks_3m_rate_10` | 20260612 | `irc_alert` | `test` | 2 | 512 | 0.3926 | 0.1699 | 0.5301 | 0.2930 | 0.3433 |
| `temporal_blocks_3m_rate_10` | 20260612 | `irc_alert` | `test` | 3 | 512 | 0.3672 | 0.1426 | 0.5192 | 0.2715 | 0.3245 |
| `temporal_blocks_3m_rate_10` | 20260613 | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0195 | 0.2961 | 0.1106 | 0.0167 |
| `temporal_blocks_3m_rate_10` | 20260613 | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0130 | 0.3065 | 0.1122 | 0.0645 |
| `temporal_blocks_3m_rate_10` | 20260613 | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0193 | 0.3116 | 0.1100 | 0.0806 |
| `temporal_blocks_3m_rate_10` | 20260613 | `irc_alert` | `test` | 1 | 512 | 0.3828 | 0.2109 | 0.5963 | 0.2383 | 0.4643 |
| `temporal_blocks_3m_rate_10` | 20260613 | `irc_alert` | `test` | 2 | 512 | 0.3926 | 0.1699 | 0.5301 | 0.2930 | 0.3433 |
| `temporal_blocks_3m_rate_10` | 20260613 | `irc_alert` | `test` | 3 | 512 | 0.3672 | 0.1406 | 0.5229 | 0.2695 | 0.3245 |
| `temporal_blocks_3m_rate_10` | 20260614 | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0195 | 0.2961 | 0.1106 | 0.0167 |
| `temporal_blocks_3m_rate_10` | 20260614 | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0130 | 0.3052 | 0.1123 | 0.0645 |
| `temporal_blocks_3m_rate_10` | 20260614 | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0193 | 0.3098 | 0.1102 | 0.0806 |
| `temporal_blocks_3m_rate_10` | 20260614 | `irc_alert` | `test` | 1 | 512 | 0.3828 | 0.2109 | 0.5963 | 0.2383 | 0.4643 |
| `temporal_blocks_3m_rate_10` | 20260614 | `irc_alert` | `test` | 2 | 512 | 0.3926 | 0.1680 | 0.5273 | 0.2949 | 0.3383 |
| `temporal_blocks_3m_rate_10` | 20260614 | `irc_alert` | `test` | 3 | 512 | 0.3672 | 0.1445 | 0.5155 | 0.2734 | 0.3245 |

## Policy Metrics

| scenario | seed | policy | event | split | horizon | rows | recall | precision | alert rate | F2 | delta F2 |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `ablate_light` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.6833 | 0.1608 | 0.5531 | 0.4141 | -0.0001 |
| `ablate_light` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.6129 | 0.2123 | 0.3891 | 0.4450 | -0.0328 |
| `ablate_light` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.4677 | 0.2959 | 0.2099 | 0.4191 | -0.0796 |
| `ablate_light` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.3418 | 0.8816 | 0.1484 | 0.3895 | -0.1206 |
| `ablate_light` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.1841 | 0.7708 | 0.0938 | 0.2171 | -0.1701 |
| `ablate_light` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.1117 | 0.8400 | 0.0488 | 0.1351 | -0.2346 |
| `ablate_light` | NA | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.6833 | 0.1608 | 0.5531 | 0.4141 | -0.0001 |
| `ablate_light` | NA | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.6129 | 0.2123 | 0.3891 | 0.4450 | -0.0328 |
| `ablate_light` | NA | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.4839 | 0.2970 | 0.2163 | 0.4298 | -0.0663 |
| `ablate_light` | NA | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.3418 | 0.8816 | 0.1484 | 0.3895 | -0.1206 |
| `ablate_light` | NA | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.1841 | 0.7708 | 0.0938 | 0.2171 | -0.1701 |
| `ablate_light` | NA | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.1117 | 0.8400 | 0.0488 | 0.1351 | -0.2346 |
| `ablate_light` | NA | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.3418 | 0.8816 | 0.1484 | 0.3895 | -0.1206 |
| `ablate_light` | NA | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.1841 | 0.7708 | 0.0938 | 0.2171 | -0.1701 |
| `ablate_light` | NA | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.1117 | 0.8400 | 0.0488 | 0.1351 | -0.2346 |
| `ablate_nutrients` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.7000 | 0.1538 | 0.5922 | 0.4094 | -0.0048 |
| `ablate_nutrients` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.6452 | 0.1923 | 0.4522 | 0.4386 | -0.0392 |
| `ablate_nutrients` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.5645 | 0.2448 | 0.3062 | 0.4476 | -0.0511 |
| `ablate_nutrients` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.5000 | 0.8235 | 0.2324 | 0.5426 | 0.0325 |
| `ablate_nutrients` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.3532 | 0.7717 | 0.1797 | 0.3962 | 0.0090 |
| `ablate_nutrients` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.2819 | 0.7794 | 0.1328 | 0.3232 | -0.0465 |
| `ablate_nutrients` | NA | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.7000 | 0.1538 | 0.5922 | 0.4094 | -0.0048 |
| `ablate_nutrients` | NA | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.6452 | 0.1923 | 0.4522 | 0.4386 | -0.0392 |
| `ablate_nutrients` | NA | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.5645 | 0.2414 | 0.3105 | 0.4453 | -0.0508 |
| `ablate_nutrients` | NA | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.5000 | 0.8235 | 0.2324 | 0.5426 | 0.0325 |
| `ablate_nutrients` | NA | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.3532 | 0.7717 | 0.1797 | 0.3962 | 0.0090 |
| `ablate_nutrients` | NA | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.2819 | 0.7794 | 0.1328 | 0.3232 | -0.0465 |
| `ablate_nutrients` | NA | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.5000 | 0.8235 | 0.2324 | 0.5426 | 0.0325 |
| `ablate_nutrients` | NA | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.3532 | 0.7717 | 0.1797 | 0.3962 | 0.0090 |
| `ablate_nutrients` | NA | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.2819 | 0.7794 | 0.1328 | 0.3232 | -0.0465 |
| `control_observed` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.7000 | 0.1573 | 0.5792 | 0.4142 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.6935 | 0.2129 | 0.4391 | 0.4778 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.6129 | 0.2857 | 0.2848 | 0.4987 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.4643 | 0.8426 | 0.2109 | 0.5101 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.3433 | 0.7931 | 0.1699 | 0.3872 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.3245 | 0.8356 | 0.1426 | 0.3697 | 0.0000 |
| `control_observed` | NA | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.7000 | 0.1573 | 0.5792 | 0.4142 | 0.0000 |
| `control_observed` | NA | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.6935 | 0.2129 | 0.4391 | 0.4778 | 0.0000 |
| `control_observed` | NA | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.6129 | 0.2815 | 0.2891 | 0.4961 | 0.0000 |
| `control_observed` | NA | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.4643 | 0.8426 | 0.2109 | 0.5101 | 0.0000 |
| `control_observed` | NA | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.3433 | 0.7931 | 0.1699 | 0.3872 | 0.0000 |
| `control_observed` | NA | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.3245 | 0.8356 | 0.1426 | 0.3697 | 0.0000 |
| `control_observed` | NA | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.4643 | 0.8426 | 0.2109 | 0.5101 | 0.0000 |
| `control_observed` | NA | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.3433 | 0.7931 | 0.1699 | 0.3872 | 0.0000 |
| `control_observed` | NA | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.3245 | 0.8356 | 0.1426 | 0.3697 | 0.0000 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.7167 | 0.1575 | 0.5922 | 0.4191 | 0.0049 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.6613 | 0.2020 | 0.4413 | 0.4545 | -0.0232 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.5968 | 0.2741 | 0.2891 | 0.4830 | -0.0157 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.4286 | 0.8485 | 0.1934 | 0.4757 | -0.0344 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.3184 | 0.8000 | 0.1562 | 0.3620 | -0.0252 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.2979 | 0.8615 | 0.1270 | 0.3427 | -0.0270 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.7167 | 0.1575 | 0.5922 | 0.4191 | 0.0049 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.6613 | 0.2020 | 0.4413 | 0.4545 | -0.0232 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.5968 | 0.2721 | 0.2912 | 0.4818 | -0.0143 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.4286 | 0.8485 | 0.1934 | 0.4757 | -0.0344 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.3184 | 0.8000 | 0.1562 | 0.3620 | -0.0252 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.2979 | 0.8615 | 0.1270 | 0.3427 | -0.0270 |
| `random_dropout_mcar_25` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.4286 | 0.8485 | 0.1934 | 0.4757 | -0.0344 |
| `random_dropout_mcar_25` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.3184 | 0.8000 | 0.1562 | 0.3620 | -0.0252 |
| `random_dropout_mcar_25` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.2979 | 0.8615 | 0.1270 | 0.3427 | -0.0270 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.7333 | 0.1648 | 0.5792 | 0.4339 | 0.0197 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.6774 | 0.2121 | 0.4304 | 0.4709 | -0.0069 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.5484 | 0.2720 | 0.2677 | 0.4558 | -0.0429 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.3776 | 0.8132 | 0.1777 | 0.4229 | -0.0872 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.2786 | 0.7887 | 0.1387 | 0.3200 | -0.0672 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.2660 | 0.8475 | 0.1152 | 0.3083 | -0.0614 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.7333 | 0.1648 | 0.5792 | 0.4339 | 0.0197 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.6774 | 0.2121 | 0.4304 | 0.4709 | -0.0069 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.5484 | 0.2677 | 0.2719 | 0.4533 | -0.0428 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.3776 | 0.8132 | 0.1777 | 0.4229 | -0.0872 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.2786 | 0.7887 | 0.1387 | 0.3200 | -0.0672 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.2660 | 0.8475 | 0.1152 | 0.3083 | -0.0614 |
| `random_dropout_mcar_25` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.3776 | 0.8132 | 0.1777 | 0.4229 | -0.0872 |
| `random_dropout_mcar_25` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.2786 | 0.7887 | 0.1387 | 0.3200 | -0.0672 |
| `random_dropout_mcar_25` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.2660 | 0.8475 | 0.1152 | 0.3083 | -0.0614 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.7000 | 0.1609 | 0.5662 | 0.4192 | 0.0050 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.6452 | 0.2062 | 0.4217 | 0.4525 | -0.0253 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.5484 | 0.2720 | 0.2677 | 0.4558 | -0.0429 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.4082 | 0.8333 | 0.1875 | 0.4545 | -0.0555 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.3383 | 0.8395 | 0.1582 | 0.3842 | -0.0030 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.3191 | 0.8824 | 0.1328 | 0.3659 | -0.0038 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.7000 | 0.1609 | 0.5662 | 0.4192 | 0.0050 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.6452 | 0.2062 | 0.4217 | 0.4525 | -0.0253 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.5484 | 0.2677 | 0.2719 | 0.4533 | -0.0428 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.4082 | 0.8333 | 0.1875 | 0.4545 | -0.0555 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.3383 | 0.8395 | 0.1582 | 0.3842 | -0.0030 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.3191 | 0.8824 | 0.1328 | 0.3659 | -0.0038 |
| `random_dropout_mcar_25` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.4082 | 0.8333 | 0.1875 | 0.4545 | -0.0555 |
| `random_dropout_mcar_25` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.3383 | 0.8395 | 0.1582 | 0.3842 | -0.0030 |
| `random_dropout_mcar_25` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.3191 | 0.8824 | 0.1328 | 0.3659 | -0.0038 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.7000 | 0.1573 | 0.5792 | 0.4142 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.6935 | 0.2139 | 0.4370 | 0.4788 | 0.0011 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.6129 | 0.2857 | 0.2848 | 0.4987 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.4643 | 0.8426 | 0.2109 | 0.5101 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.3433 | 0.7931 | 0.1699 | 0.3872 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.3245 | 0.8356 | 0.1426 | 0.3697 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.7000 | 0.1573 | 0.5792 | 0.4142 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.6935 | 0.2139 | 0.4370 | 0.4788 | 0.0011 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.6129 | 0.2815 | 0.2891 | 0.4961 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.4643 | 0.8426 | 0.2109 | 0.5101 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.3433 | 0.7931 | 0.1699 | 0.3872 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.3245 | 0.8356 | 0.1426 | 0.3697 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.4643 | 0.8426 | 0.2109 | 0.5101 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.3433 | 0.7931 | 0.1699 | 0.3872 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.3245 | 0.8356 | 0.1426 | 0.3697 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.7000 | 0.1573 | 0.5792 | 0.4142 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.6935 | 0.2129 | 0.4391 | 0.4778 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.6129 | 0.2857 | 0.2848 | 0.4987 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.4643 | 0.8426 | 0.2109 | 0.5101 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.3433 | 0.7931 | 0.1699 | 0.3872 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.3245 | 0.8472 | 0.1406 | 0.3701 | 0.0004 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.7000 | 0.1573 | 0.5792 | 0.4142 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.6935 | 0.2129 | 0.4391 | 0.4778 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.6129 | 0.2815 | 0.2891 | 0.4961 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.4643 | 0.8426 | 0.2109 | 0.5101 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.3433 | 0.7931 | 0.1699 | 0.3872 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.3245 | 0.8472 | 0.1406 | 0.3701 | 0.0004 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.4643 | 0.8426 | 0.2109 | 0.5101 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.3433 | 0.7931 | 0.1699 | 0.3872 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.3245 | 0.8472 | 0.1406 | 0.3701 | 0.0004 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.7000 | 0.1573 | 0.5792 | 0.4142 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.6935 | 0.2129 | 0.4391 | 0.4778 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.6129 | 0.2857 | 0.2848 | 0.4987 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.4643 | 0.8426 | 0.2109 | 0.5101 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.3383 | 0.7907 | 0.1680 | 0.3820 | -0.0052 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.3245 | 0.8243 | 0.1445 | 0.3692 | -0.0004 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.7000 | 0.1573 | 0.5792 | 0.4142 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.6935 | 0.2129 | 0.4391 | 0.4778 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.6129 | 0.2815 | 0.2891 | 0.4961 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.4643 | 0.8426 | 0.2109 | 0.5101 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.3383 | 0.7907 | 0.1680 | 0.3820 | -0.0052 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.3245 | 0.8243 | 0.1445 | 0.3692 | -0.0004 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.4643 | 0.8426 | 0.2109 | 0.5101 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.3383 | 0.7907 | 0.1680 | 0.3820 | -0.0052 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.3245 | 0.8243 | 0.1445 | 0.3692 | -0.0004 |

## Guardrails

- Labels and observed future fuzzy states come from the undegraded canonical sequence/split artifacts.
- Raw predictor degradation is propagated only through the fuzzy state and PIPE input sequence rebuild.
- This experiment measures operational dependence of the current pipeline, not ecological causal importance.
- Chl-a memory is a target-proximal predictor; early-warning claims require a no-current-Chl-a evaluation surface.
- Fuzzy IRC weights are frozen from the current fuzzy manifest, not re-optimized under degradation.
- PIPE/GRU-D model weights, calibrators, and policy thresholds are frozen.
- Degraded outputs are stress-test evidence, not official environmental alerts.

## Outputs

- State metrics: `reports/degradation/controlled_degradation_no_current_chla_raw_smoke_state_metrics.csv`
- Alert metrics: `reports/degradation/controlled_degradation_no_current_chla_raw_smoke_alert_metrics.csv`
- Policy metrics: `reports/degradation/controlled_degradation_no_current_chla_raw_smoke_policy_metrics.csv`
- Summary: `reports/degradation/controlled_degradation_no_current_chla_raw_smoke_summary.csv`
- Examples: `reports/degradation/controlled_degradation_no_current_chla_raw_smoke_examples.csv`
- Diagnostics: `reports/degradation/controlled_degradation_no_current_chla_raw_smoke_diagnostics.csv`
- Backtest rows: `None`
- Manifest: `reports/degradation/controlled_degradation_no_current_chla_raw_smoke_manifest.json`
