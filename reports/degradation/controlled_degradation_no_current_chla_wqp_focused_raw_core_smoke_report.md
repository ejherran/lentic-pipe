# Raw-Predictor Recomputed PIPE/GRU-D Degradation Report

Generated at UTC: `2026-06-15T13:49:20.768147+00:00`
Started at UTC: `2026-06-15T13:39:13.491212+00:00`

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
- Scenario set: `no_current_raw_core`
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
| `ablate_physicochemical` | `x_irc_basis` | 4,692 | 2,666 | 0.5510 | 0.4958 | -0.0551 | 0.1476 |
| `ablate_physicochemical` | `x_yF` | 4,692 | 2,484 | 0.6012 | 0.5177 | -0.0835 | 0.1310 |
| `ablate_physicochemical` | `x_yN` | 4,692 | 0 | 0.4928 | 0.4928 | 0.0000 | 0.0000 |
| `ablate_physicochemical` | `x_yT` | 4,692 | 2,647 | 0.6036 | 0.5000 | -0.1036 | 0.2288 |
| `control_rebuild` | `x_irc_basis` | 4,692 | 0 | 0.5510 | 0.5510 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_yF` | 4,692 | 0 | 0.6012 | 0.6012 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_yN` | 4,692 | 0 | 0.4928 | 0.4928 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_yT` | 4,692 | 0 | 0.6036 | 0.6036 | 0.0000 | 0.0000 |
| `random_dropout_mcar_10` | `x_irc_basis` | 4,692 | 1,849 | 0.5510 | 0.5417 | -0.0092 | 0.0235 |
| `random_dropout_mcar_10` | `x_irc_basis` | 4,692 | 1,845 | 0.5510 | 0.5421 | -0.0089 | 0.0234 |
| `random_dropout_mcar_10` | `x_irc_basis` | 4,692 | 1,940 | 0.5510 | 0.5425 | -0.0085 | 0.0246 |
| `random_dropout_mcar_10` | `x_yF` | 4,692 | 994 | 0.6012 | 0.6056 | 0.0043 | 0.0351 |
| `random_dropout_mcar_10` | `x_yF` | 4,692 | 952 | 0.6012 | 0.6055 | 0.0042 | 0.0327 |
| `random_dropout_mcar_10` | `x_yF` | 4,692 | 1,010 | 0.6012 | 0.6034 | 0.0022 | 0.0353 |
| `random_dropout_mcar_10` | `x_yN` | 4,692 | 876 | 0.4928 | 0.4866 | -0.0062 | 0.0198 |
| `random_dropout_mcar_10` | `x_yN` | 4,692 | 897 | 0.4928 | 0.4845 | -0.0083 | 0.0224 |
| `random_dropout_mcar_10` | `x_yN` | 4,692 | 972 | 0.4928 | 0.4845 | -0.0083 | 0.0245 |
| `random_dropout_mcar_10` | `x_yT` | 4,692 | 275 | 0.6036 | 0.5924 | -0.0112 | 0.0232 |
| `random_dropout_mcar_10` | `x_yT` | 4,692 | 266 | 0.6036 | 0.5933 | -0.0103 | 0.0228 |
| `random_dropout_mcar_10` | `x_yT` | 4,692 | 279 | 0.6036 | 0.5935 | -0.0101 | 0.0235 |
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
| `random_dropout_mcar_50` | `x_irc_basis` | 4,692 | 4,379 | 0.5510 | 0.5124 | -0.0386 | 0.1045 |
| `random_dropout_mcar_50` | `x_irc_basis` | 4,692 | 4,381 | 0.5510 | 0.5130 | -0.0380 | 0.1064 |
| `random_dropout_mcar_50` | `x_irc_basis` | 4,692 | 4,397 | 0.5510 | 0.5107 | -0.0403 | 0.1070 |
| `random_dropout_mcar_50` | `x_yF` | 4,692 | 3,279 | 0.6012 | 0.6011 | -0.0001 | 0.1661 |
| `random_dropout_mcar_50` | `x_yF` | 4,692 | 3,245 | 0.6012 | 0.6014 | 0.0002 | 0.1666 |
| `random_dropout_mcar_50` | `x_yF` | 4,692 | 3,272 | 0.6012 | 0.6002 | -0.0010 | 0.1678 |
| `random_dropout_mcar_50` | `x_yN` | 4,692 | 3,112 | 0.4928 | 0.4640 | -0.0287 | 0.1152 |
| `random_dropout_mcar_50` | `x_yN` | 4,692 | 3,087 | 0.4928 | 0.4638 | -0.0290 | 0.1151 |
| `random_dropout_mcar_50` | `x_yN` | 4,692 | 3,122 | 0.4928 | 0.4622 | -0.0305 | 0.1177 |
| `random_dropout_mcar_50` | `x_yT` | 4,692 | 1,324 | 0.6036 | 0.5528 | -0.0508 | 0.1140 |
| `random_dropout_mcar_50` | `x_yT` | 4,692 | 1,352 | 0.6036 | 0.5539 | -0.0497 | 0.1169 |
| `random_dropout_mcar_50` | `x_yT` | 4,692 | 1,338 | 0.6036 | 0.5505 | -0.0531 | 0.1164 |
| `temporal_blocks_1m_rate_10` | `x_irc_basis` | 4,692 | 7 | 0.5510 | 0.5509 | -0.0001 | 0.0002 |
| `temporal_blocks_1m_rate_10` | `x_irc_basis` | 4,692 | 5 | 0.5510 | 0.5509 | -0.0001 | 0.0002 |
| `temporal_blocks_1m_rate_10` | `x_irc_basis` | 4,692 | 2 | 0.5510 | 0.5510 | 0.0000 | 0.0000 |
| `temporal_blocks_1m_rate_10` | `x_yF` | 4,692 | 7 | 0.6012 | 0.6010 | -0.0002 | 0.0005 |
| `temporal_blocks_1m_rate_10` | `x_yF` | 4,692 | 5 | 0.6012 | 0.6012 | -0.0001 | 0.0003 |
| `temporal_blocks_1m_rate_10` | `x_yF` | 4,692 | 2 | 0.6012 | 0.6010 | -0.0002 | 0.0002 |
| `temporal_blocks_1m_rate_10` | `x_yN` | 4,692 | 7 | 0.4928 | 0.4930 | 0.0002 | 0.0003 |
| `temporal_blocks_1m_rate_10` | `x_yN` | 4,692 | 5 | 0.4928 | 0.4928 | 0.0000 | 0.0004 |
| `temporal_blocks_1m_rate_10` | `x_yN` | 4,692 | 2 | 0.4928 | 0.4930 | 0.0002 | 0.0002 |
| `temporal_blocks_1m_rate_10` | `x_yT` | 4,692 | 3 | 0.6036 | 0.6033 | -0.0003 | 0.0003 |
| `temporal_blocks_1m_rate_10` | `x_yT` | 4,692 | 2 | 0.6036 | 0.6034 | -0.0002 | 0.0002 |
| `temporal_blocks_1m_rate_10` | `x_yT` | 4,692 | 1 | 0.6036 | 0.6036 | -0.0000 | 0.0000 |
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
| `temporal_blocks_6m_rate_25` | `x_irc_basis` | 4,692 | 51 | 0.5510 | 0.5506 | -0.0004 | 0.0014 |
| `temporal_blocks_6m_rate_25` | `x_irc_basis` | 4,692 | 94 | 0.5510 | 0.5507 | -0.0003 | 0.0033 |
| `temporal_blocks_6m_rate_25` | `x_irc_basis` | 4,692 | 170 | 0.5510 | 0.5480 | -0.0030 | 0.0078 |
| `temporal_blocks_6m_rate_25` | `x_yF` | 4,692 | 46 | 0.6012 | 0.6003 | -0.0010 | 0.0031 |
| `temporal_blocks_6m_rate_25` | `x_yF` | 4,692 | 87 | 0.6012 | 0.5997 | -0.0016 | 0.0066 |
| `temporal_blocks_6m_rate_25` | `x_yF` | 4,692 | 167 | 0.6012 | 0.5989 | -0.0023 | 0.0109 |
| `temporal_blocks_6m_rate_25` | `x_yN` | 4,692 | 50 | 0.4928 | 0.4927 | -0.0001 | 0.0033 |
| `temporal_blocks_6m_rate_25` | `x_yN` | 4,692 | 86 | 0.4928 | 0.4945 | 0.0017 | 0.0050 |
| `temporal_blocks_6m_rate_25` | `x_yN` | 4,692 | 160 | 0.4928 | 0.4914 | -0.0014 | 0.0106 |
| `temporal_blocks_6m_rate_25` | `x_yT` | 4,692 | 16 | 0.6036 | 0.6027 | -0.0009 | 0.0012 |
| `temporal_blocks_6m_rate_25` | `x_yT` | 4,692 | 38 | 0.6036 | 0.6023 | -0.0013 | 0.0033 |
| `temporal_blocks_6m_rate_25` | `x_yT` | 4,692 | 108 | 0.6036 | 0.5989 | -0.0047 | 0.0095 |

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
| `ablate_physicochemical` | `evaluated` | NA | 14,895,330 | 2,346,452 | 14,537 | 1,536 | 30 |
| `control_observed` | `evaluated` | NA | 0 | 0 | 0 | 1,536 | 30 |
| `random_dropout_mcar_10` | `evaluated` | 20260612 | 3,860,596 | 1,049,325 | 8,780 | 1,536 | 30 |
| `random_dropout_mcar_10` | `evaluated` | 20260613 | 3,861,306 | 1,048,047 | 8,640 | 1,536 | 30 |
| `random_dropout_mcar_10` | `evaluated` | 20260614 | 3,862,117 | 1,048,662 | 9,222 | 1,536 | 30 |
| `random_dropout_mcar_25` | `evaluated` | 20260612 | 9,650,241 | 2,269,705 | 18,006 | 1,536 | 30 |
| `random_dropout_mcar_25` | `evaluated` | 20260613 | 9,646,358 | 2,267,308 | 17,942 | 1,536 | 30 |
| `random_dropout_mcar_25` | `evaluated` | 20260614 | 9,649,621 | 2,267,290 | 18,143 | 1,536 | 30 |
| `random_dropout_mcar_50` | `evaluated` | 20260612 | 19,295,589 | 3,641,286 | 26,855 | 1,536 | 30 |
| `random_dropout_mcar_50` | `evaluated` | 20260613 | 19,291,455 | 3,643,603 | 26,762 | 1,536 | 30 |
| `random_dropout_mcar_50` | `evaluated` | 20260614 | 19,296,402 | 3,641,390 | 26,824 | 1,536 | 30 |
| `temporal_blocks_1m_rate_10` | `evaluated` | 20260612 | 252,105 | 17,166 | 69 | 1,536 | 30 |
| `temporal_blocks_1m_rate_10` | `evaluated` | 20260613 | 247,721 | 16,568 | 46 | 1,536 | 30 |
| `temporal_blocks_1m_rate_10` | `evaluated` | 20260614 | 254,097 | 17,438 | 25 | 1,536 | 30 |
| `temporal_blocks_3m_rate_10` | `evaluated` | 20260612 | 365,277 | 30,361 | 165 | 1,536 | 30 |
| `temporal_blocks_3m_rate_10` | `evaluated` | 20260613 | 359,217 | 29,707 | 99 | 1,536 | 30 |
| `temporal_blocks_3m_rate_10` | `evaluated` | 20260614 | 370,507 | 30,950 | 89 | 1,536 | 30 |
| `temporal_blocks_6m_rate_25` | `evaluated` | 20260612 | 1,175,335 | 98,982 | 333 | 1,536 | 30 |
| `temporal_blocks_6m_rate_25` | `evaluated` | 20260613 | 1,174,824 | 101,206 | 647 | 1,536 | 30 |
| `temporal_blocks_6m_rate_25` | `evaluated` | 20260614 | 1,184,566 | 101,580 | 1,301 | 1,536 | 30 |

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
| `ablate_physicochemical` | NA | `test` | 1 | `all` | 4,608 | 0.2054 | 0.2581 | 0.2042 | 0.1377 |
| `ablate_physicochemical` | NA | `test` | 1 | `irc1` | 512 | 0.2334 | 0.1976 | -0.1810 | 0.1907 |
| `ablate_physicochemical` | NA | `test` | 2 | `all` | 4,608 | 0.2397 | 0.2547 | 0.0590 | 0.1594 |
| `ablate_physicochemical` | NA | `test` | 2 | `irc1` | 512 | 0.2934 | 0.1974 | -0.4867 | 0.2359 |
| `ablate_physicochemical` | NA | `test` | 3 | `all` | 4,608 | 0.2582 | 0.2607 | 0.0095 | 0.1757 |
| `ablate_physicochemical` | NA | `test` | 3 | `irc1` | 512 | 0.3150 | 0.2058 | -0.5311 | 0.2552 |
| `control_observed` | NA | `test` | 1 | `all` | 4,608 | 0.1495 | 0.2104 | 0.2895 | 0.0946 |
| `control_observed` | NA | `test` | 1 | `irc1` | 512 | 0.1510 | 0.1864 | 0.1899 | 0.1171 |
| `control_observed` | NA | `test` | 2 | `all` | 4,608 | 0.1951 | 0.2230 | 0.1248 | 0.1287 |
| `control_observed` | NA | `test` | 2 | `irc1` | 512 | 0.2022 | 0.2484 | 0.1858 | 0.1653 |
| `control_observed` | NA | `test` | 3 | `all` | 4,608 | 0.2160 | 0.2400 | 0.0998 | 0.1449 |
| `control_observed` | NA | `test` | 3 | `irc1` | 512 | 0.2256 | 0.2909 | 0.2245 | 0.1846 |
| `random_dropout_mcar_10` | 20260612 | `test` | 1 | `all` | 4,608 | 0.1609 | 0.2290 | 0.2976 | 0.1056 |
| `random_dropout_mcar_10` | 20260612 | `test` | 1 | `irc1` | 512 | 0.1570 | 0.1880 | 0.1651 | 0.1218 |
| `random_dropout_mcar_10` | 20260612 | `test` | 2 | `all` | 4,608 | 0.2028 | 0.2365 | 0.1426 | 0.1369 |
| `random_dropout_mcar_10` | 20260612 | `test` | 2 | `irc1` | 512 | 0.2114 | 0.2443 | 0.1346 | 0.1744 |
| `random_dropout_mcar_10` | 20260612 | `test` | 3 | `all` | 4,608 | 0.2204 | 0.2538 | 0.1315 | 0.1510 |
| `random_dropout_mcar_10` | 20260612 | `test` | 3 | `irc1` | 512 | 0.2369 | 0.2857 | 0.1707 | 0.1952 |
| `random_dropout_mcar_10` | 20260613 | `test` | 1 | `all` | 4,608 | 0.1642 | 0.2306 | 0.2879 | 0.1085 |
| `random_dropout_mcar_10` | 20260613 | `test` | 1 | `irc1` | 512 | 0.1640 | 0.1930 | 0.1503 | 0.1298 |
| `random_dropout_mcar_10` | 20260613 | `test` | 2 | `all` | 4,608 | 0.2046 | 0.2389 | 0.1437 | 0.1382 |
| `random_dropout_mcar_10` | 20260613 | `test` | 2 | `irc1` | 512 | 0.2151 | 0.2476 | 0.1313 | 0.1787 |
| `random_dropout_mcar_10` | 20260613 | `test` | 3 | `all` | 4,608 | 0.2219 | 0.2540 | 0.1263 | 0.1522 |
| `random_dropout_mcar_10` | 20260613 | `test` | 3 | `irc1` | 512 | 0.2393 | 0.2864 | 0.1644 | 0.1961 |
| `random_dropout_mcar_10` | 20260614 | `test` | 1 | `all` | 4,608 | 0.1609 | 0.2273 | 0.2925 | 0.1058 |
| `random_dropout_mcar_10` | 20260614 | `test` | 1 | `irc1` | 512 | 0.1553 | 0.1829 | 0.1508 | 0.1226 |
| `random_dropout_mcar_10` | 20260614 | `test` | 2 | `all` | 4,608 | 0.2031 | 0.2377 | 0.1452 | 0.1372 |
| `random_dropout_mcar_10` | 20260614 | `test` | 2 | `irc1` | 512 | 0.2113 | 0.2428 | 0.1298 | 0.1733 |
| `random_dropout_mcar_10` | 20260614 | `test` | 3 | `all` | 4,608 | 0.2211 | 0.2555 | 0.1346 | 0.1515 |
| `random_dropout_mcar_10` | 20260614 | `test` | 3 | `irc1` | 512 | 0.2368 | 0.2843 | 0.1668 | 0.1939 |
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
| `random_dropout_mcar_50` | 20260612 | `test` | 1 | `all` | 4,608 | 0.2206 | 0.2985 | 0.2609 | 0.1632 |
| `random_dropout_mcar_50` | 20260612 | `test` | 1 | `irc1` | 512 | 0.2134 | 0.2095 | -0.0189 | 0.1680 |
| `random_dropout_mcar_50` | 20260612 | `test` | 2 | `all` | 4,608 | 0.2554 | 0.3007 | 0.1505 | 0.1875 |
| `random_dropout_mcar_50` | 20260612 | `test` | 2 | `irc1` | 512 | 0.2859 | 0.2392 | -0.1952 | 0.2388 |
| `random_dropout_mcar_50` | 20260612 | `test` | 3 | `all` | 4,608 | 0.2687 | 0.3080 | 0.1278 | 0.1982 |
| `random_dropout_mcar_50` | 20260612 | `test` | 3 | `irc1` | 512 | 0.3185 | 0.2628 | -0.2121 | 0.2631 |
| `random_dropout_mcar_50` | 20260613 | `test` | 1 | `all` | 4,608 | 0.2180 | 0.2947 | 0.2601 | 0.1623 |
| `random_dropout_mcar_50` | 20260613 | `test` | 1 | `irc1` | 512 | 0.2064 | 0.1987 | -0.0389 | 0.1650 |
| `random_dropout_mcar_50` | 20260613 | `test` | 2 | `all` | 4,608 | 0.2532 | 0.2983 | 0.1511 | 0.1858 |
| `random_dropout_mcar_50` | 20260613 | `test` | 2 | `irc1` | 512 | 0.2797 | 0.2310 | -0.2106 | 0.2328 |
| `random_dropout_mcar_50` | 20260613 | `test` | 3 | `all` | 4,608 | 0.2669 | 0.3070 | 0.1308 | 0.1962 |
| `random_dropout_mcar_50` | 20260613 | `test` | 3 | `irc1` | 512 | 0.3118 | 0.2561 | -0.2176 | 0.2559 |
| `random_dropout_mcar_50` | 20260614 | `test` | 1 | `all` | 4,608 | 0.2188 | 0.2948 | 0.2578 | 0.1609 |
| `random_dropout_mcar_50` | 20260614 | `test` | 1 | `irc1` | 512 | 0.2132 | 0.2055 | -0.0373 | 0.1696 |
| `random_dropout_mcar_50` | 20260614 | `test` | 2 | `all` | 4,608 | 0.2527 | 0.2988 | 0.1545 | 0.1844 |
| `random_dropout_mcar_50` | 20260614 | `test` | 2 | `irc1` | 512 | 0.2800 | 0.2364 | -0.1846 | 0.2319 |
| `random_dropout_mcar_50` | 20260614 | `test` | 3 | `all` | 4,608 | 0.2673 | 0.3081 | 0.1325 | 0.1965 |
| `random_dropout_mcar_50` | 20260614 | `test` | 3 | `irc1` | 512 | 0.3141 | 0.2652 | -0.1845 | 0.2565 |
| `temporal_blocks_1m_rate_10` | 20260612 | `test` | 1 | `all` | 4,608 | 0.1499 | 0.2109 | 0.2892 | 0.0949 |
| `temporal_blocks_1m_rate_10` | 20260612 | `test` | 1 | `irc1` | 512 | 0.1510 | 0.1865 | 0.1908 | 0.1173 |
| `temporal_blocks_1m_rate_10` | 20260612 | `test` | 2 | `all` | 4,608 | 0.1955 | 0.2233 | 0.1247 | 0.1289 |
| `temporal_blocks_1m_rate_10` | 20260612 | `test` | 2 | `irc1` | 512 | 0.2022 | 0.2485 | 0.1864 | 0.1652 |
| `temporal_blocks_1m_rate_10` | 20260612 | `test` | 3 | `all` | 4,608 | 0.2164 | 0.2403 | 0.0998 | 0.1452 |
| `temporal_blocks_1m_rate_10` | 20260612 | `test` | 3 | `irc1` | 512 | 0.2259 | 0.2912 | 0.2243 | 0.1849 |
| `temporal_blocks_1m_rate_10` | 20260613 | `test` | 1 | `all` | 4,608 | 0.1499 | 0.2109 | 0.2893 | 0.0948 |
| `temporal_blocks_1m_rate_10` | 20260613 | `test` | 1 | `irc1` | 512 | 0.1511 | 0.1866 | 0.1903 | 0.1173 |
| `temporal_blocks_1m_rate_10` | 20260613 | `test` | 2 | `all` | 4,608 | 0.1955 | 0.2233 | 0.1248 | 0.1289 |
| `temporal_blocks_1m_rate_10` | 20260613 | `test` | 2 | `irc1` | 512 | 0.2022 | 0.2485 | 0.1864 | 0.1651 |
| `temporal_blocks_1m_rate_10` | 20260613 | `test` | 3 | `all` | 4,608 | 0.2163 | 0.2403 | 0.0999 | 0.1452 |
| `temporal_blocks_1m_rate_10` | 20260613 | `test` | 3 | `irc1` | 512 | 0.2257 | 0.2911 | 0.2247 | 0.1848 |
| `temporal_blocks_1m_rate_10` | 20260614 | `test` | 1 | `all` | 4,608 | 0.1503 | 0.2117 | 0.2899 | 0.0951 |
| `temporal_blocks_1m_rate_10` | 20260614 | `test` | 1 | `irc1` | 512 | 0.1509 | 0.1863 | 0.1902 | 0.1170 |
| `temporal_blocks_1m_rate_10` | 20260614 | `test` | 2 | `all` | 4,608 | 0.1954 | 0.2239 | 0.1272 | 0.1289 |
| `temporal_blocks_1m_rate_10` | 20260614 | `test` | 2 | `irc1` | 512 | 0.2022 | 0.2484 | 0.1860 | 0.1653 |
| `temporal_blocks_1m_rate_10` | 20260614 | `test` | 3 | `all` | 4,608 | 0.2163 | 0.2410 | 0.1025 | 0.1450 |
| `temporal_blocks_1m_rate_10` | 20260614 | `test` | 3 | `irc1` | 512 | 0.2255 | 0.2909 | 0.2250 | 0.1843 |
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
| `temporal_blocks_6m_rate_25` | 20260612 | `test` | 1 | `all` | 4,608 | 0.1551 | 0.2142 | 0.2761 | 0.0979 |
| `temporal_blocks_6m_rate_25` | 20260612 | `test` | 1 | `irc1` | 512 | 0.1542 | 0.1870 | 0.1753 | 0.1191 |
| `temporal_blocks_6m_rate_25` | 20260612 | `test` | 2 | `all` | 4,608 | 0.1994 | 0.2258 | 0.1171 | 0.1317 |
| `temporal_blocks_6m_rate_25` | 20260612 | `test` | 2 | `irc1` | 512 | 0.2059 | 0.2483 | 0.1705 | 0.1675 |
| `temporal_blocks_6m_rate_25` | 20260612 | `test` | 3 | `all` | 4,608 | 0.2200 | 0.2428 | 0.0938 | 0.1480 |
| `temporal_blocks_6m_rate_25` | 20260612 | `test` | 3 | `irc1` | 512 | 0.2309 | 0.2908 | 0.2062 | 0.1883 |
| `temporal_blocks_6m_rate_25` | 20260613 | `test` | 1 | `all` | 4,608 | 0.1566 | 0.2146 | 0.2702 | 0.0988 |
| `temporal_blocks_6m_rate_25` | 20260613 | `test` | 1 | `irc1` | 512 | 0.1538 | 0.1886 | 0.1846 | 0.1191 |
| `temporal_blocks_6m_rate_25` | 20260613 | `test` | 2 | `all` | 4,608 | 0.2002 | 0.2262 | 0.1151 | 0.1323 |
| `temporal_blocks_6m_rate_25` | 20260613 | `test` | 2 | `irc1` | 512 | 0.2043 | 0.2488 | 0.1789 | 0.1666 |
| `temporal_blocks_6m_rate_25` | 20260613 | `test` | 3 | `all` | 4,608 | 0.2211 | 0.2438 | 0.0932 | 0.1488 |
| `temporal_blocks_6m_rate_25` | 20260613 | `test` | 3 | `irc1` | 512 | 0.2291 | 0.2910 | 0.2128 | 0.1869 |
| `temporal_blocks_6m_rate_25` | 20260614 | `test` | 1 | `all` | 4,608 | 0.1594 | 0.2168 | 0.2647 | 0.1008 |
| `temporal_blocks_6m_rate_25` | 20260614 | `test` | 1 | `irc1` | 512 | 0.1527 | 0.1866 | 0.1815 | 0.1177 |
| `temporal_blocks_6m_rate_25` | 20260614 | `test` | 2 | `all` | 4,608 | 0.2025 | 0.2292 | 0.1163 | 0.1341 |
| `temporal_blocks_6m_rate_25` | 20260614 | `test` | 2 | `irc1` | 512 | 0.2070 | 0.2472 | 0.1627 | 0.1687 |
| `temporal_blocks_6m_rate_25` | 20260614 | `test` | 3 | `all` | 4,608 | 0.2224 | 0.2453 | 0.0934 | 0.1500 |
| `temporal_blocks_6m_rate_25` | 20260614 | `test` | 3 | `irc1` | 512 | 0.2318 | 0.2896 | 0.1997 | 0.1883 |

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
| `ablate_physicochemical` | NA | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0125 | 0.3653 | 0.1370 | 0.0147 |
| `ablate_physicochemical` | NA | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.0891 | 0.3941 | 0.1400 | 0.2222 |
| `ablate_physicochemical` | NA | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.1152 | 0.3239 | 0.1393 | 0.2464 |
| `ablate_physicochemical` | NA | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.3047 | 0.6019 | 0.3711 | 0.4346 |
| `ablate_physicochemical` | NA | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.2793 | 0.5911 | 0.3828 | 0.3977 |
| `ablate_physicochemical` | NA | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.2715 | 0.5604 | 0.4062 | 0.3647 |
| `control_observed` | NA | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0525 | 0.3747 | 0.1300 | 0.1471 |
| `control_observed` | NA | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.1094 | 0.4663 | 0.1248 | 0.3194 |
| `control_observed` | NA | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.1324 | 0.3466 | 0.1297 | 0.2899 |
| `control_observed` | NA | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.5020 | 0.7576 | 0.1895 | 0.8077 |
| `control_observed` | NA | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.4180 | 0.6669 | 0.2871 | 0.6293 |
| `control_observed` | NA | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.4062 | 0.6112 | 0.3379 | 0.5686 |
| `random_dropout_mcar_10` | 20260612 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0475 | 0.3645 | 0.1309 | 0.1324 |
| `random_dropout_mcar_10` | 20260612 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.0738 | 0.4416 | 0.1295 | 0.2083 |
| `random_dropout_mcar_10` | 20260612 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.1078 | 0.3373 | 0.1305 | 0.2319 |
| `random_dropout_mcar_10` | 20260612 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.4590 | 0.7405 | 0.2129 | 0.7423 |
| `random_dropout_mcar_10` | 20260612 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.3809 | 0.6505 | 0.3086 | 0.5714 |
| `random_dropout_mcar_10` | 20260612 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.3633 | 0.6005 | 0.3535 | 0.5098 |
| `random_dropout_mcar_10` | 20260613 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0400 | 0.3503 | 0.1329 | 0.1029 |
| `random_dropout_mcar_10` | 20260613 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.0789 | 0.4308 | 0.1319 | 0.2083 |
| `random_dropout_mcar_10` | 20260613 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.1005 | 0.3416 | 0.1308 | 0.2174 |
| `random_dropout_mcar_10` | 20260613 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.4375 | 0.7168 | 0.2383 | 0.6962 |
| `random_dropout_mcar_10` | 20260613 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.3652 | 0.6488 | 0.3125 | 0.5521 |
| `random_dropout_mcar_10` | 20260613 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.3477 | 0.6053 | 0.3496 | 0.4980 |
| `random_dropout_mcar_10` | 20260614 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0375 | 0.3480 | 0.1306 | 0.1176 |
| `random_dropout_mcar_10` | 20260614 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.0814 | 0.4278 | 0.1322 | 0.2083 |
| `random_dropout_mcar_10` | 20260614 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.1029 | 0.3324 | 0.1336 | 0.2029 |
| `random_dropout_mcar_10` | 20260614 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.4531 | 0.7440 | 0.2109 | 0.7385 |
| `random_dropout_mcar_10` | 20260614 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.3809 | 0.6584 | 0.3008 | 0.5792 |
| `random_dropout_mcar_10` | 20260614 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.3477 | 0.6127 | 0.3418 | 0.5059 |
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
| `random_dropout_mcar_50` | 20260612 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0050 | 0.3103 | 0.1445 | 0.0000 |
| `random_dropout_mcar_50` | 20260612 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.0229 | 0.4108 | 0.1483 | 0.0556 |
| `random_dropout_mcar_50` | 20260612 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.0343 | 0.3283 | 0.1412 | 0.0725 |
| `random_dropout_mcar_50` | 20260612 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.2539 | 0.6697 | 0.3164 | 0.4385 |
| `random_dropout_mcar_50` | 20260612 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.1855 | 0.5683 | 0.4180 | 0.2703 |
| `random_dropout_mcar_50` | 20260612 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.1777 | 0.5393 | 0.4375 | 0.2392 |
| `random_dropout_mcar_50` | 20260613 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0075 | 0.3088 | 0.1449 | 0.0147 |
| `random_dropout_mcar_50` | 20260613 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.0127 | 0.3791 | 0.1510 | 0.0278 |
| `random_dropout_mcar_50` | 20260613 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.0196 | 0.3055 | 0.1424 | 0.0435 |
| `random_dropout_mcar_50` | 20260613 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.2676 | 0.6327 | 0.3457 | 0.4231 |
| `random_dropout_mcar_50` | 20260613 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.1836 | 0.5742 | 0.4121 | 0.2741 |
| `random_dropout_mcar_50` | 20260613 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.1699 | 0.5695 | 0.4062 | 0.2627 |
| `random_dropout_mcar_50` | 20260614 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0125 | 0.3157 | 0.1450 | 0.0147 |
| `random_dropout_mcar_50` | 20260614 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.0254 | 0.4333 | 0.1453 | 0.0972 |
| `random_dropout_mcar_50` | 20260614 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.0441 | 0.3083 | 0.1425 | 0.0725 |
| `random_dropout_mcar_50` | 20260614 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.2754 | 0.6440 | 0.3340 | 0.4423 |
| `random_dropout_mcar_50` | 20260614 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.1719 | 0.5720 | 0.4160 | 0.2587 |
| `random_dropout_mcar_50` | 20260614 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.1562 | 0.5424 | 0.4355 | 0.2196 |
| `temporal_blocks_1m_rate_10` | 20260612 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0525 | 0.3748 | 0.1300 | 0.1471 |
| `temporal_blocks_1m_rate_10` | 20260612 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.1094 | 0.4658 | 0.1248 | 0.3194 |
| `temporal_blocks_1m_rate_10` | 20260612 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.1324 | 0.3465 | 0.1297 | 0.2899 |
| `temporal_blocks_1m_rate_10` | 20260612 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.5020 | 0.7576 | 0.1895 | 0.8077 |
| `temporal_blocks_1m_rate_10` | 20260612 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.4180 | 0.6669 | 0.2871 | 0.6293 |
| `temporal_blocks_1m_rate_10` | 20260612 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.4062 | 0.6112 | 0.3379 | 0.5686 |
| `temporal_blocks_1m_rate_10` | 20260613 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0525 | 0.3747 | 0.1300 | 0.1471 |
| `temporal_blocks_1m_rate_10` | 20260613 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.1094 | 0.4662 | 0.1249 | 0.3194 |
| `temporal_blocks_1m_rate_10` | 20260613 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.1324 | 0.3462 | 0.1298 | 0.2899 |
| `temporal_blocks_1m_rate_10` | 20260613 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.5020 | 0.7576 | 0.1895 | 0.8077 |
| `temporal_blocks_1m_rate_10` | 20260613 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.4180 | 0.6669 | 0.2871 | 0.6293 |
| `temporal_blocks_1m_rate_10` | 20260613 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.4062 | 0.6112 | 0.3379 | 0.5686 |
| `temporal_blocks_1m_rate_10` | 20260614 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0525 | 0.3746 | 0.1301 | 0.1471 |
| `temporal_blocks_1m_rate_10` | 20260614 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.1094 | 0.4659 | 0.1248 | 0.3194 |
| `temporal_blocks_1m_rate_10` | 20260614 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.1324 | 0.3465 | 0.1297 | 0.2899 |
| `temporal_blocks_1m_rate_10` | 20260614 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.5020 | 0.7576 | 0.1895 | 0.8077 |
| `temporal_blocks_1m_rate_10` | 20260614 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.4180 | 0.6669 | 0.2871 | 0.6293 |
| `temporal_blocks_1m_rate_10` | 20260614 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.4062 | 0.6112 | 0.3379 | 0.5686 |
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
| `temporal_blocks_6m_rate_25` | 20260612 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0525 | 0.3699 | 0.1308 | 0.1471 |
| `temporal_blocks_6m_rate_25` | 20260612 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.1069 | 0.4583 | 0.1259 | 0.3194 |
| `temporal_blocks_6m_rate_25` | 20260612 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.1275 | 0.3439 | 0.1303 | 0.2754 |
| `temporal_blocks_6m_rate_25` | 20260612 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.4980 | 0.7541 | 0.1934 | 0.8000 |
| `temporal_blocks_6m_rate_25` | 20260612 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.4141 | 0.6674 | 0.2871 | 0.6255 |
| `temporal_blocks_6m_rate_25` | 20260612 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.4004 | 0.6099 | 0.3398 | 0.5608 |
| `temporal_blocks_6m_rate_25` | 20260613 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0525 | 0.3579 | 0.1321 | 0.1471 |
| `temporal_blocks_6m_rate_25` | 20260613 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.1069 | 0.4537 | 0.1272 | 0.3194 |
| `temporal_blocks_6m_rate_25` | 20260613 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.1225 | 0.3451 | 0.1296 | 0.2754 |
| `temporal_blocks_6m_rate_25` | 20260613 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.4902 | 0.7514 | 0.1973 | 0.7885 |
| `temporal_blocks_6m_rate_25` | 20260613 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.4082 | 0.6584 | 0.2969 | 0.6100 |
| `temporal_blocks_6m_rate_25` | 20260613 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.3945 | 0.6017 | 0.3496 | 0.5451 |
| `temporal_blocks_6m_rate_25` | 20260614 | `bloom_h` | `test` | 1 | 400 | 0.1700 | 0.0525 | 0.3670 | 0.1310 | 0.1471 |
| `temporal_blocks_6m_rate_25` | 20260614 | `bloom_h` | `test` | 2 | 393 | 0.1832 | 0.0967 | 0.4609 | 0.1265 | 0.2917 |
| `temporal_blocks_6m_rate_25` | 20260614 | `bloom_h` | `test` | 3 | 408 | 0.1691 | 0.1225 | 0.3407 | 0.1300 | 0.2754 |
| `temporal_blocks_6m_rate_25` | 20260614 | `irc_alert` | `test` | 1 | 512 | 0.5078 | 0.4707 | 0.7645 | 0.1895 | 0.7769 |
| `temporal_blocks_6m_rate_25` | 20260614 | `irc_alert` | `test` | 2 | 512 | 0.5059 | 0.3945 | 0.6704 | 0.2871 | 0.6062 |
| `temporal_blocks_6m_rate_25` | 20260614 | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.3848 | 0.6112 | 0.3398 | 0.5451 |

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
| `ablate_physicochemical` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.2794 | 0.4130 | 0.1150 | 0.2987 | -0.1820 |
| `ablate_physicochemical` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.3750 | 0.4091 | 0.1679 | 0.3814 | -0.1956 |
| `ablate_physicochemical` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.4928 | 0.3469 | 0.2402 | 0.4545 | -0.1206 |
| `ablate_physicochemical` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.4346 | 0.7244 | 0.3047 | 0.4724 | -0.3372 |
| `ablate_physicochemical` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.3977 | 0.7203 | 0.2793 | 0.4368 | -0.2152 |
| `ablate_physicochemical` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.3647 | 0.6691 | 0.2715 | 0.4012 | -0.1892 |
| `ablate_physicochemical` | NA | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.4265 | 0.4143 | 0.1750 | 0.4240 | -0.1206 |
| `ablate_physicochemical` | NA | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.4306 | 0.3875 | 0.2036 | 0.4212 | -0.1599 |
| `ablate_physicochemical` | NA | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.4928 | 0.3333 | 0.2500 | 0.4497 | -0.1338 |
| `ablate_physicochemical` | NA | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.4346 | 0.7244 | 0.3047 | 0.4724 | -0.3372 |
| `ablate_physicochemical` | NA | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.3977 | 0.7203 | 0.2793 | 0.4368 | -0.2152 |
| `ablate_physicochemical` | NA | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.3647 | 0.6691 | 0.2715 | 0.4012 | -0.1892 |
| `ablate_physicochemical` | NA | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.4346 | 0.7244 | 0.3047 | 0.4724 | -0.3372 |
| `ablate_physicochemical` | NA | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.3977 | 0.7203 | 0.2793 | 0.4368 | -0.2152 |
| `ablate_physicochemical` | NA | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.3647 | 0.6691 | 0.2715 | 0.4012 | -0.1892 |
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
| `random_dropout_mcar_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.4118 | 0.3784 | 0.1850 | 0.4046 | -0.0761 |
| `random_dropout_mcar_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.5694 | 0.4713 | 0.2214 | 0.5467 | -0.0303 |
| `random_dropout_mcar_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.6522 | 0.3409 | 0.3235 | 0.5515 | -0.0236 |
| `random_dropout_mcar_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.7423 | 0.8213 | 0.4590 | 0.7569 | -0.0527 |
| `random_dropout_mcar_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.5714 | 0.7590 | 0.3809 | 0.6011 | -0.0509 |
| `random_dropout_mcar_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.5098 | 0.6989 | 0.3633 | 0.5390 | -0.0514 |
| `random_dropout_mcar_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.5588 | 0.3304 | 0.2875 | 0.4910 | -0.0536 |
| `random_dropout_mcar_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.6250 | 0.4245 | 0.2697 | 0.5711 | -0.0100 |
| `random_dropout_mcar_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.7101 | 0.3403 | 0.3529 | 0.5833 | -0.0002 |
| `random_dropout_mcar_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.7423 | 0.8213 | 0.4590 | 0.7569 | -0.0527 |
| `random_dropout_mcar_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.5714 | 0.7590 | 0.3809 | 0.6011 | -0.0509 |
| `random_dropout_mcar_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.5098 | 0.6989 | 0.3633 | 0.5390 | -0.0514 |
| `random_dropout_mcar_10` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.7423 | 0.8213 | 0.4590 | 0.7569 | -0.0527 |
| `random_dropout_mcar_10` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.5714 | 0.7590 | 0.3809 | 0.6011 | -0.0509 |
| `random_dropout_mcar_10` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.5098 | 0.6989 | 0.3633 | 0.5390 | -0.0514 |
| `random_dropout_mcar_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.3971 | 0.3649 | 0.1850 | 0.3902 | -0.0906 |
| `random_dropout_mcar_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.5417 | 0.4535 | 0.2188 | 0.5214 | -0.0555 |
| `random_dropout_mcar_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.6377 | 0.3385 | 0.3186 | 0.5419 | -0.0332 |
| `random_dropout_mcar_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.6962 | 0.8080 | 0.4375 | 0.7160 | -0.0936 |
| `random_dropout_mcar_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.5521 | 0.7647 | 0.3652 | 0.5846 | -0.0674 |
| `random_dropout_mcar_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.7135 | 0.3477 | 0.5301 | -0.0603 |
| `random_dropout_mcar_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.5735 | 0.3421 | 0.2850 | 0.5052 | -0.0394 |
| `random_dropout_mcar_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.5972 | 0.4019 | 0.2723 | 0.5443 | -0.0368 |
| `random_dropout_mcar_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.6522 | 0.3214 | 0.3431 | 0.5409 | -0.0427 |
| `random_dropout_mcar_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.6962 | 0.8080 | 0.4375 | 0.7160 | -0.0936 |
| `random_dropout_mcar_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.5521 | 0.7647 | 0.3652 | 0.5846 | -0.0674 |
| `random_dropout_mcar_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.7135 | 0.3477 | 0.5301 | -0.0603 |
| `random_dropout_mcar_10` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.6962 | 0.8080 | 0.4375 | 0.7160 | -0.0936 |
| `random_dropout_mcar_10` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.5521 | 0.7647 | 0.3652 | 0.5846 | -0.0674 |
| `random_dropout_mcar_10` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.4980 | 0.7135 | 0.3477 | 0.5301 | -0.0603 |
| `random_dropout_mcar_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.4265 | 0.3766 | 0.1925 | 0.4155 | -0.0653 |
| `random_dropout_mcar_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.5278 | 0.4634 | 0.2087 | 0.5135 | -0.0634 |
| `random_dropout_mcar_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.6087 | 0.3360 | 0.3064 | 0.5237 | -0.0514 |
| `random_dropout_mcar_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.7385 | 0.8276 | 0.4531 | 0.7547 | -0.0548 |
| `random_dropout_mcar_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.5792 | 0.7692 | 0.3809 | 0.6093 | -0.0427 |
| `random_dropout_mcar_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.5059 | 0.7247 | 0.3477 | 0.5384 | -0.0520 |
| `random_dropout_mcar_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.5735 | 0.3333 | 0.2925 | 0.5013 | -0.0433 |
| `random_dropout_mcar_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.5833 | 0.4078 | 0.2621 | 0.5371 | -0.0440 |
| `random_dropout_mcar_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.6812 | 0.3431 | 0.3358 | 0.5690 | -0.0145 |
| `random_dropout_mcar_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.7385 | 0.8276 | 0.4531 | 0.7547 | -0.0548 |
| `random_dropout_mcar_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.5792 | 0.7692 | 0.3809 | 0.6093 | -0.0427 |
| `random_dropout_mcar_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.5059 | 0.7247 | 0.3477 | 0.5384 | -0.0520 |
| `random_dropout_mcar_10` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.7385 | 0.8276 | 0.4531 | 0.7547 | -0.0548 |
| `random_dropout_mcar_10` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.5792 | 0.7692 | 0.3809 | 0.6093 | -0.0427 |
| `random_dropout_mcar_10` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.5059 | 0.7247 | 0.3477 | 0.5384 | -0.0520 |
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
| `random_dropout_mcar_50` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.1324 | 0.4091 | 0.0550 | 0.1531 | -0.3277 |
| `random_dropout_mcar_50` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.1944 | 0.4516 | 0.0789 | 0.2194 | -0.3575 |
| `random_dropout_mcar_50` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.2464 | 0.2931 | 0.1422 | 0.2545 | -0.3206 |
| `random_dropout_mcar_50` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.4385 | 0.8769 | 0.2539 | 0.4872 | -0.3224 |
| `random_dropout_mcar_50` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.2703 | 0.7368 | 0.1855 | 0.3095 | -0.3425 |
| `random_dropout_mcar_50` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.2392 | 0.6703 | 0.1777 | 0.2745 | -0.3159 |
| `random_dropout_mcar_50` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.2794 | 0.4043 | 0.1175 | 0.2978 | -0.2467 |
| `random_dropout_mcar_50` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.2778 | 0.4545 | 0.1120 | 0.3012 | -0.2799 |
| `random_dropout_mcar_50` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.2609 | 0.2769 | 0.1593 | 0.2639 | -0.3196 |
| `random_dropout_mcar_50` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.4385 | 0.8769 | 0.2539 | 0.4872 | -0.3224 |
| `random_dropout_mcar_50` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.2703 | 0.7368 | 0.1855 | 0.3095 | -0.3425 |
| `random_dropout_mcar_50` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.2392 | 0.6703 | 0.1777 | 0.2745 | -0.3159 |
| `random_dropout_mcar_50` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.4385 | 0.8769 | 0.2539 | 0.4872 | -0.3224 |
| `random_dropout_mcar_50` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.2703 | 0.7368 | 0.1855 | 0.3095 | -0.3425 |
| `random_dropout_mcar_50` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.2392 | 0.6703 | 0.1777 | 0.2745 | -0.3159 |
| `random_dropout_mcar_50` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.0882 | 0.3529 | 0.0425 | 0.1038 | -0.3770 |
| `random_dropout_mcar_50` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.1389 | 0.4000 | 0.0636 | 0.1597 | -0.4172 |
| `random_dropout_mcar_50` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.2899 | 0.3571 | 0.1373 | 0.3012 | -0.2739 |
| `random_dropout_mcar_50` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.4231 | 0.8029 | 0.2676 | 0.4673 | -0.3423 |
| `random_dropout_mcar_50` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.2741 | 0.7553 | 0.1836 | 0.3142 | -0.3378 |
| `random_dropout_mcar_50` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.2627 | 0.7701 | 0.1699 | 0.3026 | -0.2878 |
| `random_dropout_mcar_50` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.2059 | 0.3256 | 0.1075 | 0.2222 | -0.3223 |
| `random_dropout_mcar_50` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.1944 | 0.3889 | 0.0916 | 0.2160 | -0.3651 |
| `random_dropout_mcar_50` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.3188 | 0.3548 | 0.1520 | 0.3254 | -0.2581 |
| `random_dropout_mcar_50` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.4231 | 0.8029 | 0.2676 | 0.4673 | -0.3423 |
| `random_dropout_mcar_50` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.2741 | 0.7553 | 0.1836 | 0.3142 | -0.3378 |
| `random_dropout_mcar_50` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.2627 | 0.7701 | 0.1699 | 0.3026 | -0.2878 |
| `random_dropout_mcar_50` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.4231 | 0.8029 | 0.2676 | 0.4673 | -0.3423 |
| `random_dropout_mcar_50` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.2741 | 0.7553 | 0.1836 | 0.3142 | -0.3378 |
| `random_dropout_mcar_50` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.2627 | 0.7701 | 0.1699 | 0.3026 | -0.2878 |
| `random_dropout_mcar_50` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.1029 | 0.3500 | 0.0500 | 0.1199 | -0.3609 |
| `random_dropout_mcar_50` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.2083 | 0.4054 | 0.0941 | 0.2308 | -0.3462 |
| `random_dropout_mcar_50` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.2609 | 0.3273 | 0.1348 | 0.2719 | -0.3032 |
| `random_dropout_mcar_50` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.4423 | 0.8156 | 0.2754 | 0.4869 | -0.3227 |
| `random_dropout_mcar_50` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.2587 | 0.7614 | 0.1719 | 0.2980 | -0.3540 |
| `random_dropout_mcar_50` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.2196 | 0.7000 | 0.1562 | 0.2545 | -0.3358 |
| `random_dropout_mcar_50` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.2353 | 0.3333 | 0.1200 | 0.2500 | -0.2946 |
| `random_dropout_mcar_50` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.2500 | 0.4186 | 0.1094 | 0.2719 | -0.3092 |
| `random_dropout_mcar_50` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.3043 | 0.3387 | 0.1520 | 0.3107 | -0.2729 |
| `random_dropout_mcar_50` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.4423 | 0.8156 | 0.2754 | 0.4869 | -0.3227 |
| `random_dropout_mcar_50` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.2587 | 0.7614 | 0.1719 | 0.2980 | -0.3540 |
| `random_dropout_mcar_50` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.2196 | 0.7000 | 0.1562 | 0.2545 | -0.3358 |
| `random_dropout_mcar_50` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.4423 | 0.8156 | 0.2754 | 0.4869 | -0.3227 |
| `random_dropout_mcar_50` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.2587 | 0.7614 | 0.1719 | 0.2980 | -0.3540 |
| `random_dropout_mcar_50` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.2196 | 0.7000 | 0.1562 | 0.2545 | -0.3358 |
| `temporal_blocks_1m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.5147 | 0.3804 | 0.2300 | 0.4808 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.6250 | 0.4412 | 0.2595 | 0.5769 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.7101 | 0.3267 | 0.3676 | 0.5751 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.8077 | 0.8171 | 0.5020 | 0.8096 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.6471 | 0.3333 | 0.3300 | 0.5446 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.6667 | 0.3840 | 0.3181 | 0.5811 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.7391 | 0.3168 | 0.3946 | 0.5835 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.8077 | 0.8171 | 0.5020 | 0.8096 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.8077 | 0.8171 | 0.5020 | 0.8096 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.5147 | 0.3804 | 0.2300 | 0.4808 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.6250 | 0.4412 | 0.2595 | 0.5769 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.6957 | 0.3221 | 0.3652 | 0.5647 | -0.0104 |
| `temporal_blocks_1m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.8077 | 0.8171 | 0.5020 | 0.8096 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.6324 | 0.3282 | 0.3275 | 0.5335 | -0.0111 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.6667 | 0.3840 | 0.3181 | 0.5811 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.7391 | 0.3168 | 0.3946 | 0.5835 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.8077 | 0.8171 | 0.5020 | 0.8096 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.8077 | 0.8171 | 0.5020 | 0.8096 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.5147 | 0.3804 | 0.2300 | 0.4808 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.6250 | 0.4412 | 0.2595 | 0.5769 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.7101 | 0.3267 | 0.3676 | 0.5751 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.8077 | 0.8171 | 0.5020 | 0.8096 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.6471 | 0.3333 | 0.3300 | 0.5446 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.6667 | 0.3840 | 0.3181 | 0.5811 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.7391 | 0.3168 | 0.3946 | 0.5835 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.8077 | 0.8171 | 0.5020 | 0.8096 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.8077 | 0.8171 | 0.5020 | 0.8096 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.6293 | 0.7617 | 0.4180 | 0.6520 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.5686 | 0.6971 | 0.4062 | 0.5904 | 0.0000 |
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
| `temporal_blocks_6m_rate_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.4853 | 0.3708 | 0.2225 | 0.4571 | -0.0237 |
| `temporal_blocks_6m_rate_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.5972 | 0.4343 | 0.2519 | 0.5556 | -0.0214 |
| `temporal_blocks_6m_rate_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.6957 | 0.3243 | 0.3627 | 0.5660 | -0.0091 |
| `temporal_blocks_6m_rate_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.8000 | 0.8157 | 0.4980 | 0.8031 | -0.0065 |
| `temporal_blocks_6m_rate_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.6255 | 0.7642 | 0.4141 | 0.6490 | -0.0030 |
| `temporal_blocks_6m_rate_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.5608 | 0.6976 | 0.4004 | 0.5837 | -0.0067 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.6324 | 0.3308 | 0.3250 | 0.5348 | -0.0097 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.6528 | 0.3821 | 0.3130 | 0.5718 | -0.0093 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.7246 | 0.3145 | 0.3897 | 0.5747 | -0.0088 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.8000 | 0.8157 | 0.4980 | 0.8031 | -0.0065 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.6255 | 0.7642 | 0.4141 | 0.6490 | -0.0030 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.5608 | 0.6976 | 0.4004 | 0.5837 | -0.0067 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.8000 | 0.8157 | 0.4980 | 0.8031 | -0.0065 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.6255 | 0.7642 | 0.4141 | 0.6490 | -0.0030 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.5608 | 0.6976 | 0.4004 | 0.5837 | -0.0067 |
| `temporal_blocks_6m_rate_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.4706 | 0.3721 | 0.2150 | 0.4469 | -0.0338 |
| `temporal_blocks_6m_rate_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.5833 | 0.4286 | 0.2494 | 0.5440 | -0.0329 |
| `temporal_blocks_6m_rate_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.6667 | 0.3194 | 0.3529 | 0.5476 | -0.0275 |
| `temporal_blocks_6m_rate_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.7885 | 0.8167 | 0.4902 | 0.7940 | -0.0156 |
| `temporal_blocks_6m_rate_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.6100 | 0.7560 | 0.4082 | 0.6345 | -0.0175 |
| `temporal_blocks_6m_rate_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.5451 | 0.6881 | 0.3945 | 0.5687 | -0.0217 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.6029 | 0.3203 | 0.3200 | 0.5125 | -0.0321 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.6111 | 0.3697 | 0.3028 | 0.5405 | -0.0406 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.6957 | 0.3097 | 0.3799 | 0.5568 | -0.0267 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.7885 | 0.8167 | 0.4902 | 0.7940 | -0.0156 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.6100 | 0.7560 | 0.4082 | 0.6345 | -0.0175 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.5451 | 0.6881 | 0.3945 | 0.5687 | -0.0217 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.7885 | 0.8167 | 0.4902 | 0.7940 | -0.0156 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.6100 | 0.7560 | 0.4082 | 0.6345 | -0.0175 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.5451 | 0.6881 | 0.3945 | 0.5687 | -0.0217 |
| `temporal_blocks_6m_rate_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 400 | 0.4853 | 0.3793 | 0.2175 | 0.4596 | -0.0212 |
| `temporal_blocks_6m_rate_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 393 | 0.6111 | 0.4536 | 0.2468 | 0.5714 | -0.0055 |
| `temporal_blocks_6m_rate_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 408 | 0.6667 | 0.3239 | 0.3480 | 0.5502 | -0.0249 |
| `temporal_blocks_6m_rate_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.7769 | 0.8382 | 0.4707 | 0.7884 | -0.0211 |
| `temporal_blocks_6m_rate_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.6062 | 0.7772 | 0.3945 | 0.6341 | -0.0179 |
| `temporal_blocks_6m_rate_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.5451 | 0.7056 | 0.3848 | 0.5711 | -0.0193 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 400 | 0.6029 | 0.3306 | 0.3100 | 0.5177 | -0.0269 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 393 | 0.6667 | 0.4068 | 0.3003 | 0.5911 | 0.0100 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 408 | 0.7101 | 0.3182 | 0.3775 | 0.5698 | -0.0138 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.7769 | 0.8382 | 0.4707 | 0.7884 | -0.0211 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.6062 | 0.7772 | 0.3945 | 0.6341 | -0.0179 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.5451 | 0.7056 | 0.3848 | 0.5711 | -0.0193 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.7769 | 0.8382 | 0.4707 | 0.7884 | -0.0211 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.6062 | 0.7772 | 0.3945 | 0.6341 | -0.0179 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.5451 | 0.7056 | 0.3848 | 0.5711 | -0.0193 |

## Guardrails

- Labels and observed future fuzzy states come from the undegraded canonical sequence/split artifacts.
- Raw predictor degradation is propagated only through the fuzzy state and PIPE input sequence rebuild.
- This experiment measures operational dependence of the current pipeline, not ecological causal importance.
- Chl-a memory is a target-proximal predictor; early-warning claims require a no-current-Chl-a evaluation surface.
- Fuzzy IRC weights are frozen from the current fuzzy manifest, not re-optimized under degradation.
- PIPE/GRU-D model weights, calibrators, and policy thresholds are frozen.
- Degraded outputs are stress-test evidence, not official environmental alerts.

## Outputs

- State metrics: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_smoke_state_metrics.csv`
- Alert metrics: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_smoke_alert_metrics.csv`
- Policy metrics: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_smoke_policy_metrics.csv`
- Summary: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_smoke_summary.csv`
- Examples: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_smoke_examples.csv`
- Diagnostics: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_smoke_diagnostics.csv`
- Backtest rows: `None`
- Manifest: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_smoke_manifest.json`
