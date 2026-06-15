# Raw-Predictor Recomputed PIPE/GRU-D Degradation Report

Generated at UTC: `2026-06-15T14:04:54.442298+00:00`
Started at UTC: `2026-06-15T13:53:32.043511+00:00`

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
- Selected origins: `6,145`
- History length: `12`
- Rollout horizon: `3` month(s)
- Samples per origin: `128`
- Deterministic mode: `False`
- Max origins cap: `None`
- Policies: `['closest_pr', 'fixed', 'fbeta']`
- Requested policy evaluation splits: `['test']`
- Default downstream policy context: `closest_pr`
- Calibrated bloom horizons available: `[1, 2, 3]`
- Rollout bloom calibrator horizons available: `[1, 2, 3]`

## Evaluation Surface Diagnostics

| source | panel rows | panel sites | canonical sequence rows | selected origins | panel rows without sequence origin |
|---|---:|---:|---:|---:|---:|
| `wqp` | 1,626,672 | 106,719 | 986,674 | 6,145 | 639,998 |

## Control Rebuild Drift

| canonical sequence rows | rebuilt state rows | rebuilt sequence rows | alignment missing rows | sequence cells changed | selected-window cells changed |
|---:|---:|---:|---:|---:|---:|
| 986,674 | 1,626,672 | 986,674 | 0 | 0 | 0 |

## Selected-Window Input Changes

| scenario | input | rows | changed rows | mean before | mean after | mean delta | mean absolute delta |
|---|---|---:|---:|---:|---:|---:|---:|
| `ablate_light` | `x_irc_basis` | 12,998 | 11,989 | 0.5413 | 0.5271 | -0.0142 | 0.0349 |
| `ablate_light` | `x_yF` | 12,998 | 11,989 | 0.6008 | 0.6860 | 0.0852 | 0.2092 |
| `ablate_light` | `x_yN` | 12,998 | 0 | 0.4984 | 0.4984 | 0.0000 | 0.0000 |
| `ablate_light` | `x_yT` | 12,998 | 0 | 0.5876 | 0.5876 | 0.0000 | 0.0000 |
| `ablate_nutrients` | `x_irc_basis` | 12,998 | 11,487 | 0.5413 | 0.5416 | 0.0003 | 0.0410 |
| `ablate_nutrients` | `x_yF` | 12,998 | 0 | 0.6008 | 0.6008 | 0.0000 | 0.0000 |
| `ablate_nutrients` | `x_yN` | 12,998 | 11,487 | 0.4984 | 0.5000 | 0.0016 | 0.2461 |
| `ablate_nutrients` | `x_yT` | 12,998 | 0 | 0.5876 | 0.5876 | 0.0000 | 0.0000 |
| `ablate_physicochemical` | `x_irc_basis` | 12,998 | 7,184 | 0.5413 | 0.4960 | -0.0453 | 0.1455 |
| `ablate_physicochemical` | `x_yF` | 12,998 | 6,582 | 0.6008 | 0.5221 | -0.0787 | 0.1232 |
| `ablate_physicochemical` | `x_yN` | 12,998 | 0 | 0.4984 | 0.4984 | 0.0000 | 0.0000 |
| `ablate_physicochemical` | `x_yT` | 12,998 | 7,141 | 0.5876 | 0.5000 | -0.0876 | 0.2237 |
| `control_rebuild` | `x_irc_basis` | 12,998 | 0 | 0.5413 | 0.5413 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_yF` | 12,998 | 0 | 0.6008 | 0.6008 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_yN` | 12,998 | 0 | 0.4984 | 0.4984 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_yT` | 12,998 | 0 | 0.5876 | 0.5876 | 0.0000 | 0.0000 |
| `random_dropout_mcar_10` | `x_irc_basis` | 12,998 | 5,083 | 0.5413 | 0.5339 | -0.0074 | 0.0229 |
| `random_dropout_mcar_10` | `x_irc_basis` | 12,998 | 5,078 | 0.5413 | 0.5338 | -0.0076 | 0.0232 |
| `random_dropout_mcar_10` | `x_irc_basis` | 12,998 | 5,136 | 0.5413 | 0.5338 | -0.0076 | 0.0236 |
| `random_dropout_mcar_10` | `x_yF` | 12,998 | 2,702 | 0.6008 | 0.6052 | 0.0044 | 0.0331 |
| `random_dropout_mcar_10` | `x_yF` | 12,998 | 2,589 | 0.6008 | 0.6035 | 0.0027 | 0.0317 |
| `random_dropout_mcar_10` | `x_yF` | 12,998 | 2,707 | 0.6008 | 0.6041 | 0.0033 | 0.0342 |
| `random_dropout_mcar_10` | `x_yN` | 12,998 | 2,406 | 0.4984 | 0.4921 | -0.0063 | 0.0208 |
| `random_dropout_mcar_10` | `x_yN` | 12,998 | 2,475 | 0.4984 | 0.4909 | -0.0075 | 0.0225 |
| `random_dropout_mcar_10` | `x_yN` | 12,998 | 2,473 | 0.4984 | 0.4915 | -0.0069 | 0.0226 |
| `random_dropout_mcar_10` | `x_yT` | 12,998 | 715 | 0.5876 | 0.5791 | -0.0085 | 0.0223 |
| `random_dropout_mcar_10` | `x_yT` | 12,998 | 716 | 0.5876 | 0.5788 | -0.0088 | 0.0227 |
| `random_dropout_mcar_10` | `x_yT` | 12,998 | 722 | 0.5876 | 0.5788 | -0.0088 | 0.0226 |
| `random_dropout_mcar_25` | `x_irc_basis` | 12,998 | 9,379 | 0.5413 | 0.5230 | -0.0183 | 0.0544 |
| `random_dropout_mcar_25` | `x_irc_basis` | 12,998 | 9,362 | 0.5413 | 0.5236 | -0.0178 | 0.0548 |
| `random_dropout_mcar_25` | `x_irc_basis` | 12,998 | 9,429 | 0.5413 | 0.5231 | -0.0183 | 0.0569 |
| `random_dropout_mcar_25` | `x_yF` | 12,998 | 5,675 | 0.6008 | 0.6089 | 0.0081 | 0.0805 |
| `random_dropout_mcar_25` | `x_yF` | 12,998 | 5,594 | 0.6008 | 0.6065 | 0.0057 | 0.0803 |
| `random_dropout_mcar_25` | `x_yF` | 12,998 | 5,654 | 0.6008 | 0.6069 | 0.0061 | 0.0807 |
| `random_dropout_mcar_25` | `x_yN` | 12,998 | 5,330 | 0.4984 | 0.4830 | -0.0154 | 0.0548 |
| `random_dropout_mcar_25` | `x_yN` | 12,998 | 5,335 | 0.4984 | 0.4816 | -0.0168 | 0.0558 |
| `random_dropout_mcar_25` | `x_yN` | 12,998 | 5,364 | 0.4984 | 0.4827 | -0.0157 | 0.0565 |
| `random_dropout_mcar_25` | `x_yT` | 12,998 | 1,735 | 0.5876 | 0.5660 | -0.0216 | 0.0549 |
| `random_dropout_mcar_25` | `x_yT` | 12,998 | 1,768 | 0.5876 | 0.5666 | -0.0210 | 0.0555 |
| `random_dropout_mcar_25` | `x_yT` | 12,998 | 1,847 | 0.5876 | 0.5657 | -0.0219 | 0.0582 |
| `random_dropout_mcar_50` | `x_irc_basis` | 12,998 | 12,088 | 0.5413 | 0.5078 | -0.0335 | 0.1026 |
| `random_dropout_mcar_50` | `x_irc_basis` | 12,998 | 12,046 | 0.5413 | 0.5090 | -0.0324 | 0.1029 |
| `random_dropout_mcar_50` | `x_irc_basis` | 12,998 | 12,103 | 0.5413 | 0.5076 | -0.0338 | 0.1042 |
| `random_dropout_mcar_50` | `x_yF` | 12,998 | 8,874 | 0.6008 | 0.6016 | 0.0008 | 0.1606 |
| `random_dropout_mcar_50` | `x_yF` | 12,998 | 8,787 | 0.6008 | 0.6015 | 0.0007 | 0.1599 |
| `random_dropout_mcar_50` | `x_yF` | 12,998 | 8,881 | 0.6008 | 0.6035 | 0.0027 | 0.1594 |
| `random_dropout_mcar_50` | `x_yN` | 12,998 | 8,499 | 0.4984 | 0.4711 | -0.0273 | 0.1151 |
| `random_dropout_mcar_50` | `x_yN` | 12,998 | 8,434 | 0.4984 | 0.4723 | -0.0262 | 0.1141 |
| `random_dropout_mcar_50` | `x_yN` | 12,998 | 8,476 | 0.4984 | 0.4725 | -0.0259 | 0.1153 |
| `random_dropout_mcar_50` | `x_yT` | 12,998 | 3,513 | 0.5876 | 0.5443 | -0.0433 | 0.1108 |
| `random_dropout_mcar_50` | `x_yT` | 12,998 | 3,571 | 0.5876 | 0.5458 | -0.0418 | 0.1119 |
| `random_dropout_mcar_50` | `x_yT` | 12,998 | 3,624 | 0.5876 | 0.5441 | -0.0435 | 0.1137 |
| `temporal_blocks_1m_rate_10` | `x_irc_basis` | 12,998 | 16 | 0.5413 | 0.5413 | -0.0000 | 0.0002 |
| `temporal_blocks_1m_rate_10` | `x_irc_basis` | 12,998 | 17 | 0.5413 | 0.5412 | -0.0001 | 0.0003 |
| `temporal_blocks_1m_rate_10` | `x_irc_basis` | 12,998 | 15 | 0.5413 | 0.5413 | -0.0000 | 0.0002 |
| `temporal_blocks_1m_rate_10` | `x_yF` | 12,998 | 16 | 0.6008 | 0.6007 | -0.0001 | 0.0004 |
| `temporal_blocks_1m_rate_10` | `x_yF` | 12,998 | 17 | 0.6008 | 0.6007 | -0.0001 | 0.0004 |
| `temporal_blocks_1m_rate_10` | `x_yF` | 12,998 | 14 | 0.6008 | 0.6006 | -0.0002 | 0.0003 |
| `temporal_blocks_1m_rate_10` | `x_yN` | 12,998 | 14 | 0.4984 | 0.4985 | 0.0001 | 0.0003 |
| `temporal_blocks_1m_rate_10` | `x_yN` | 12,998 | 17 | 0.4984 | 0.4985 | 0.0000 | 0.0005 |
| `temporal_blocks_1m_rate_10` | `x_yN` | 12,998 | 12 | 0.4984 | 0.4984 | -0.0000 | 0.0003 |
| `temporal_blocks_1m_rate_10` | `x_yT` | 12,998 | 7 | 0.5876 | 0.5875 | -0.0001 | 0.0002 |
| `temporal_blocks_1m_rate_10` | `x_yT` | 12,998 | 7 | 0.5876 | 0.5874 | -0.0002 | 0.0003 |
| `temporal_blocks_1m_rate_10` | `x_yT` | 12,998 | 9 | 0.5876 | 0.5875 | -0.0001 | 0.0002 |
| `temporal_blocks_3m_rate_10` | `x_irc_basis` | 12,998 | 47 | 0.5413 | 0.5413 | -0.0001 | 0.0006 |
| `temporal_blocks_3m_rate_10` | `x_irc_basis` | 12,998 | 48 | 0.5413 | 0.5410 | -0.0003 | 0.0008 |
| `temporal_blocks_3m_rate_10` | `x_irc_basis` | 12,998 | 45 | 0.5413 | 0.5411 | -0.0002 | 0.0006 |
| `temporal_blocks_3m_rate_10` | `x_yF` | 12,998 | 47 | 0.6008 | 0.6007 | -0.0001 | 0.0011 |
| `temporal_blocks_3m_rate_10` | `x_yF` | 12,998 | 48 | 0.6008 | 0.6006 | -0.0002 | 0.0012 |
| `temporal_blocks_3m_rate_10` | `x_yF` | 12,998 | 42 | 0.6008 | 0.6003 | -0.0005 | 0.0010 |
| `temporal_blocks_3m_rate_10` | `x_yN` | 12,998 | 40 | 0.4984 | 0.4986 | 0.0002 | 0.0006 |
| `temporal_blocks_3m_rate_10` | `x_yN` | 12,998 | 47 | 0.4984 | 0.4986 | 0.0002 | 0.0013 |
| `temporal_blocks_3m_rate_10` | `x_yN` | 12,998 | 40 | 0.4984 | 0.4983 | -0.0001 | 0.0010 |
| `temporal_blocks_3m_rate_10` | `x_yT` | 12,998 | 22 | 0.5876 | 0.5874 | -0.0002 | 0.0006 |
| `temporal_blocks_3m_rate_10` | `x_yT` | 12,998 | 23 | 0.5876 | 0.5870 | -0.0006 | 0.0008 |
| `temporal_blocks_3m_rate_10` | `x_yT` | 12,998 | 24 | 0.5876 | 0.5871 | -0.0005 | 0.0007 |
| `temporal_blocks_6m_rate_25` | `x_irc_basis` | 12,998 | 237 | 0.5413 | 0.5406 | -0.0007 | 0.0030 |
| `temporal_blocks_6m_rate_25` | `x_irc_basis` | 12,998 | 374 | 0.5413 | 0.5400 | -0.0014 | 0.0045 |
| `temporal_blocks_6m_rate_25` | `x_irc_basis` | 12,998 | 352 | 0.5413 | 0.5401 | -0.0012 | 0.0048 |
| `temporal_blocks_6m_rate_25` | `x_yF` | 12,998 | 225 | 0.6008 | 0.5989 | -0.0019 | 0.0053 |
| `temporal_blocks_6m_rate_25` | `x_yF` | 12,998 | 358 | 0.6008 | 0.5989 | -0.0019 | 0.0086 |
| `temporal_blocks_6m_rate_25` | `x_yF` | 12,998 | 348 | 0.6008 | 0.5992 | -0.0016 | 0.0078 |
| `temporal_blocks_6m_rate_25` | `x_yN` | 12,998 | 217 | 0.4984 | 0.4985 | 0.0001 | 0.0046 |
| `temporal_blocks_6m_rate_25` | `x_yN` | 12,998 | 332 | 0.4984 | 0.4993 | 0.0009 | 0.0071 |
| `temporal_blocks_6m_rate_25` | `x_yN` | 12,998 | 329 | 0.4984 | 0.4988 | 0.0004 | 0.0077 |
| `temporal_blocks_6m_rate_25` | `x_yT` | 12,998 | 109 | 0.5876 | 0.5860 | -0.0016 | 0.0033 |
| `temporal_blocks_6m_rate_25` | `x_yT` | 12,998 | 146 | 0.5876 | 0.5848 | -0.0028 | 0.0046 |
| `temporal_blocks_6m_rate_25` | `x_yT` | 12,998 | 178 | 0.5876 | 0.5852 | -0.0024 | 0.0056 |

## Future Availability

| horizon | eligible origins | origins with observed future | selected origins | policy |
|---:|---:|---:|---:|---|
| 1 | 7,582 | 7,582 | 6,145 | `complete_horizons` |
| 2 | 7,582 | 6,826 | 6,145 | `complete_horizons` |
| 3 | 7,582 | 6,345 | 6,145 | `complete_horizons` |

## Scenario Summary

| scenario | status | seed | raw cells | sequence cells | selected-window cells | rollout rows | policy metric rows |
|---|---|---:|---:|---:|---:|---:|---:|
| `ablate_light` | `evaluated` | NA | 10,190,837 | 2,300,449 | 35,005 | 18,435 | 30 |
| `ablate_nutrients` | `evaluated` | NA | 6,377,245 | 1,039,421 | 34,277 | 18,435 | 30 |
| `ablate_physicochemical` | `evaluated` | NA | 14,895,330 | 2,346,452 | 38,906 | 18,435 | 30 |
| `control_observed` | `evaluated` | NA | 0 | 0 | 0 | 18,435 | 30 |
| `random_dropout_mcar_10` | `evaluated` | 20260612 | 3,860,596 | 1,049,325 | 23,789 | 18,435 | 30 |
| `random_dropout_mcar_10` | `evaluated` | 20260613 | 3,861,306 | 1,048,047 | 23,609 | 18,435 | 30 |
| `random_dropout_mcar_10` | `evaluated` | 20260614 | 3,862,117 | 1,048,662 | 24,224 | 18,435 | 30 |
| `random_dropout_mcar_25` | `evaluated` | 20260612 | 9,650,241 | 2,269,705 | 48,652 | 18,435 | 30 |
| `random_dropout_mcar_25` | `evaluated` | 20260613 | 9,646,358 | 2,267,308 | 48,494 | 18,435 | 30 |
| `random_dropout_mcar_25` | `evaluated` | 20260614 | 9,649,621 | 2,267,290 | 49,029 | 18,435 | 30 |
| `random_dropout_mcar_50` | `evaluated` | 20260612 | 19,295,589 | 3,641,286 | 72,798 | 18,435 | 30 |
| `random_dropout_mcar_50` | `evaluated` | 20260613 | 19,291,455 | 3,643,603 | 72,671 | 18,435 | 30 |
| `random_dropout_mcar_50` | `evaluated` | 20260614 | 19,296,402 | 3,641,390 | 73,008 | 18,435 | 30 |
| `temporal_blocks_1m_rate_10` | `evaluated` | 20260612 | 252,105 | 17,166 | 149 | 18,435 | 30 |
| `temporal_blocks_1m_rate_10` | `evaluated` | 20260613 | 247,721 | 16,568 | 165 | 18,435 | 30 |
| `temporal_blocks_1m_rate_10` | `evaluated` | 20260614 | 254,097 | 17,438 | 139 | 18,435 | 30 |
| `temporal_blocks_3m_rate_10` | `evaluated` | 20260612 | 365,277 | 30,361 | 363 | 18,435 | 30 |
| `temporal_blocks_3m_rate_10` | `evaluated` | 20260613 | 359,217 | 29,707 | 369 | 18,435 | 30 |
| `temporal_blocks_3m_rate_10` | `evaluated` | 20260614 | 370,507 | 30,950 | 334 | 18,435 | 30 |
| `temporal_blocks_6m_rate_25` | `evaluated` | 20260612 | 1,175,335 | 98,982 | 1,669 | 18,435 | 30 |
| `temporal_blocks_6m_rate_25` | `evaluated` | 20260613 | 1,174,824 | 101,206 | 2,541 | 18,435 | 30 |
| `temporal_blocks_6m_rate_25` | `evaluated` | 20260614 | 1,184,566 | 101,580 | 2,591 | 18,435 | 30 |

## State Metrics

| scenario | seed | split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE |
|---|---:|---|---:|---|---:|---:|---:|---:|---:|
| `ablate_light` | NA | `test` | 1 | `all` | 55,305 | 0.1944 | 0.2312 | 0.1592 | 0.1386 |
| `ablate_light` | NA | `test` | 1 | `irc1` | 6,145 | 0.1991 | 0.1971 | -0.0103 | 0.1585 |
| `ablate_light` | NA | `test` | 2 | `all` | 55,305 | 0.2394 | 0.2446 | 0.0213 | 0.1738 |
| `ablate_light` | NA | `test` | 2 | `irc1` | 6,145 | 0.2623 | 0.2489 | -0.0537 | 0.2197 |
| `ablate_light` | NA | `test` | 3 | `all` | 55,305 | 0.2552 | 0.2591 | 0.0149 | 0.1862 |
| `ablate_light` | NA | `test` | 3 | `irc1` | 6,145 | 0.2872 | 0.2905 | 0.0114 | 0.2416 |
| `ablate_nutrients` | NA | `test` | 1 | `all` | 55,305 | 0.2450 | 0.2717 | 0.0986 | 0.1706 |
| `ablate_nutrients` | NA | `test` | 1 | `irc1` | 6,145 | 0.1664 | 0.2046 | 0.1871 | 0.1358 |
| `ablate_nutrients` | NA | `test` | 2 | `all` | 55,305 | 0.2711 | 0.2825 | 0.0404 | 0.1979 |
| `ablate_nutrients` | NA | `test` | 2 | `irc1` | 6,145 | 0.2009 | 0.2546 | 0.2109 | 0.1641 |
| `ablate_nutrients` | NA | `test` | 3 | `all` | 55,305 | 0.2806 | 0.2955 | 0.0503 | 0.2085 |
| `ablate_nutrients` | NA | `test` | 3 | `irc1` | 6,145 | 0.2197 | 0.2957 | 0.2568 | 0.1797 |
| `ablate_physicochemical` | NA | `test` | 1 | `all` | 55,305 | 0.2062 | 0.2623 | 0.2140 | 0.1439 |
| `ablate_physicochemical` | NA | `test` | 1 | `irc1` | 6,145 | 0.2236 | 0.2045 | -0.0932 | 0.1796 |
| `ablate_physicochemical` | NA | `test` | 2 | `all` | 55,305 | 0.2298 | 0.2609 | 0.1190 | 0.1597 |
| `ablate_physicochemical` | NA | `test` | 2 | `irc1` | 6,145 | 0.2577 | 0.2042 | -0.2624 | 0.2055 |
| `ablate_physicochemical` | NA | `test` | 3 | `all` | 55,305 | 0.2457 | 0.2650 | 0.0730 | 0.1747 |
| `ablate_physicochemical` | NA | `test` | 3 | `irc1` | 6,145 | 0.2659 | 0.2076 | -0.2808 | 0.2119 |
| `control_observed` | NA | `test` | 1 | `all` | 55,305 | 0.1537 | 0.2037 | 0.2455 | 0.1044 |
| `control_observed` | NA | `test` | 1 | `irc1` | 6,145 | 0.1502 | 0.1849 | 0.1877 | 0.1199 |
| `control_observed` | NA | `test` | 2 | `all` | 55,305 | 0.1957 | 0.2177 | 0.1014 | 0.1377 |
| `control_observed` | NA | `test` | 2 | `irc1` | 6,145 | 0.1916 | 0.2383 | 0.1959 | 0.1597 |
| `control_observed` | NA | `test` | 3 | `all` | 55,305 | 0.2153 | 0.2354 | 0.0856 | 0.1532 |
| `control_observed` | NA | `test` | 3 | `irc1` | 6,145 | 0.2078 | 0.2799 | 0.2573 | 0.1737 |
| `random_dropout_mcar_10` | 20260612 | `test` | 1 | `all` | 55,305 | 0.1651 | 0.2221 | 0.2568 | 0.1147 |
| `random_dropout_mcar_10` | 20260612 | `test` | 1 | `irc1` | 6,145 | 0.1599 | 0.1903 | 0.1598 | 0.1275 |
| `random_dropout_mcar_10` | 20260612 | `test` | 2 | `all` | 55,305 | 0.2023 | 0.2330 | 0.1316 | 0.1446 |
| `random_dropout_mcar_10` | 20260612 | `test` | 2 | `irc1` | 6,145 | 0.2002 | 0.2374 | 0.1570 | 0.1664 |
| `random_dropout_mcar_10` | 20260612 | `test` | 3 | `all` | 55,305 | 0.2193 | 0.2487 | 0.1182 | 0.1582 |
| `random_dropout_mcar_10` | 20260612 | `test` | 3 | `irc1` | 6,145 | 0.2175 | 0.2765 | 0.2132 | 0.1812 |
| `random_dropout_mcar_10` | 20260613 | `test` | 1 | `all` | 55,305 | 0.1651 | 0.2200 | 0.2497 | 0.1149 |
| `random_dropout_mcar_10` | 20260613 | `test` | 1 | `irc1` | 6,145 | 0.1590 | 0.1878 | 0.1534 | 0.1272 |
| `random_dropout_mcar_10` | 20260613 | `test` | 2 | `all` | 55,305 | 0.2025 | 0.2327 | 0.1296 | 0.1448 |
| `random_dropout_mcar_10` | 20260613 | `test` | 2 | `irc1` | 6,145 | 0.2005 | 0.2362 | 0.1511 | 0.1671 |
| `random_dropout_mcar_10` | 20260613 | `test` | 3 | `all` | 55,305 | 0.2194 | 0.2481 | 0.1155 | 0.1583 |
| `random_dropout_mcar_10` | 20260613 | `test` | 3 | `irc1` | 6,145 | 0.2173 | 0.2754 | 0.2109 | 0.1813 |
| `random_dropout_mcar_10` | 20260614 | `test` | 1 | `all` | 55,305 | 0.1652 | 0.2220 | 0.2555 | 0.1147 |
| `random_dropout_mcar_10` | 20260614 | `test` | 1 | `irc1` | 6,145 | 0.1593 | 0.1891 | 0.1573 | 0.1270 |
| `random_dropout_mcar_10` | 20260614 | `test` | 2 | `all` | 55,305 | 0.2026 | 0.2339 | 0.1339 | 0.1447 |
| `random_dropout_mcar_10` | 20260614 | `test` | 2 | `irc1` | 6,145 | 0.2007 | 0.2375 | 0.1550 | 0.1667 |
| `random_dropout_mcar_10` | 20260614 | `test` | 3 | `all` | 55,305 | 0.2197 | 0.2496 | 0.1199 | 0.1585 |
| `random_dropout_mcar_10` | 20260614 | `test` | 3 | `irc1` | 6,145 | 0.2174 | 0.2756 | 0.2111 | 0.1810 |
| `random_dropout_mcar_25` | 20260612 | `test` | 1 | `all` | 55,305 | 0.1835 | 0.2481 | 0.2604 | 0.1322 |
| `random_dropout_mcar_25` | 20260612 | `test` | 1 | `irc1` | 6,145 | 0.1761 | 0.1973 | 0.1075 | 0.1402 |
| `random_dropout_mcar_25` | 20260612 | `test` | 2 | `all` | 55,305 | 0.2153 | 0.2568 | 0.1616 | 0.1577 |
| `random_dropout_mcar_25` | 20260612 | `test` | 2 | `irc1` | 6,145 | 0.2167 | 0.2360 | 0.0817 | 0.1794 |
| `random_dropout_mcar_25` | 20260612 | `test` | 3 | `all` | 55,305 | 0.2292 | 0.2687 | 0.1472 | 0.1685 |
| `random_dropout_mcar_25` | 20260612 | `test` | 3 | `irc1` | 6,145 | 0.2348 | 0.2692 | 0.1277 | 0.1943 |
| `random_dropout_mcar_25` | 20260613 | `test` | 1 | `all` | 55,305 | 0.1838 | 0.2482 | 0.2595 | 0.1323 |
| `random_dropout_mcar_25` | 20260613 | `test` | 1 | `irc1` | 6,145 | 0.1762 | 0.1969 | 0.1051 | 0.1406 |
| `random_dropout_mcar_25` | 20260613 | `test` | 2 | `all` | 55,305 | 0.2157 | 0.2572 | 0.1613 | 0.1577 |
| `random_dropout_mcar_25` | 20260613 | `test` | 2 | `irc1` | 6,145 | 0.2191 | 0.2378 | 0.0785 | 0.1810 |
| `random_dropout_mcar_25` | 20260613 | `test` | 3 | `all` | 55,305 | 0.2297 | 0.2702 | 0.1497 | 0.1688 |
| `random_dropout_mcar_25` | 20260613 | `test` | 3 | `irc1` | 6,145 | 0.2370 | 0.2726 | 0.1307 | 0.1969 |
| `random_dropout_mcar_25` | 20260614 | `test` | 1 | `all` | 55,305 | 0.1841 | 0.2482 | 0.2582 | 0.1323 |
| `random_dropout_mcar_25` | 20260614 | `test` | 1 | `irc1` | 6,145 | 0.1782 | 0.1966 | 0.0935 | 0.1417 |
| `random_dropout_mcar_25` | 20260614 | `test` | 2 | `all` | 55,305 | 0.2159 | 0.2572 | 0.1605 | 0.1578 |
| `random_dropout_mcar_25` | 20260614 | `test` | 2 | `irc1` | 6,145 | 0.2201 | 0.2365 | 0.0695 | 0.1819 |
| `random_dropout_mcar_25` | 20260614 | `test` | 3 | `all` | 55,305 | 0.2300 | 0.2693 | 0.1460 | 0.1689 |
| `random_dropout_mcar_25` | 20260614 | `test` | 3 | `irc1` | 6,145 | 0.2376 | 0.2691 | 0.1170 | 0.1967 |
| `random_dropout_mcar_50` | 20260612 | `test` | 1 | `all` | 55,305 | 0.2192 | 0.2939 | 0.2539 | 0.1660 |
| `random_dropout_mcar_50` | 20260612 | `test` | 1 | `irc1` | 6,145 | 0.2077 | 0.2107 | 0.0138 | 0.1657 |
| `random_dropout_mcar_50` | 20260612 | `test` | 2 | `all` | 55,305 | 0.2455 | 0.2982 | 0.1766 | 0.1855 |
| `random_dropout_mcar_50` | 20260612 | `test` | 2 | `irc1` | 6,145 | 0.2525 | 0.2370 | -0.0654 | 0.2062 |
| `random_dropout_mcar_50` | 20260612 | `test` | 3 | `all` | 55,305 | 0.2575 | 0.3070 | 0.1611 | 0.1950 |
| `random_dropout_mcar_50` | 20260612 | `test` | 3 | `irc1` | 6,145 | 0.2723 | 0.2625 | -0.0376 | 0.2237 |
| `random_dropout_mcar_50` | 20260613 | `test` | 1 | `all` | 55,305 | 0.2187 | 0.2928 | 0.2530 | 0.1654 |
| `random_dropout_mcar_50` | 20260613 | `test` | 1 | `irc1` | 6,145 | 0.2090 | 0.2094 | 0.0018 | 0.1669 |
| `random_dropout_mcar_50` | 20260613 | `test` | 2 | `all` | 55,305 | 0.2459 | 0.2981 | 0.1751 | 0.1855 |
| `random_dropout_mcar_50` | 20260613 | `test` | 2 | `irc1` | 6,145 | 0.2561 | 0.2372 | -0.0798 | 0.2086 |
| `random_dropout_mcar_50` | 20260613 | `test` | 3 | `all` | 55,305 | 0.2579 | 0.3054 | 0.1554 | 0.1949 |
| `random_dropout_mcar_50` | 20260613 | `test` | 3 | `irc1` | 6,145 | 0.2761 | 0.2629 | -0.0502 | 0.2260 |
| `random_dropout_mcar_50` | 20260614 | `test` | 1 | `all` | 55,305 | 0.2196 | 0.2931 | 0.2509 | 0.1662 |
| `random_dropout_mcar_50` | 20260614 | `test` | 1 | `irc1` | 6,145 | 0.2123 | 0.2119 | -0.0023 | 0.1702 |
| `random_dropout_mcar_50` | 20260614 | `test` | 2 | `all` | 55,305 | 0.2462 | 0.2973 | 0.1721 | 0.1856 |
| `random_dropout_mcar_50` | 20260614 | `test` | 2 | `irc1` | 6,145 | 0.2582 | 0.2365 | -0.0917 | 0.2106 |
| `random_dropout_mcar_50` | 20260614 | `test` | 3 | `all` | 55,305 | 0.2584 | 0.3055 | 0.1540 | 0.1953 |
| `random_dropout_mcar_50` | 20260614 | `test` | 3 | `irc1` | 6,145 | 0.2780 | 0.2615 | -0.0631 | 0.2279 |
| `temporal_blocks_1m_rate_10` | 20260612 | `test` | 1 | `all` | 55,305 | 0.1538 | 0.2038 | 0.2454 | 0.1044 |
| `temporal_blocks_1m_rate_10` | 20260612 | `test` | 1 | `irc1` | 6,145 | 0.1503 | 0.1850 | 0.1879 | 0.1199 |
| `temporal_blocks_1m_rate_10` | 20260612 | `test` | 2 | `all` | 55,305 | 0.1957 | 0.2178 | 0.1015 | 0.1377 |
| `temporal_blocks_1m_rate_10` | 20260612 | `test` | 2 | `irc1` | 6,145 | 0.1916 | 0.2384 | 0.1960 | 0.1597 |
| `temporal_blocks_1m_rate_10` | 20260612 | `test` | 3 | `all` | 55,305 | 0.2153 | 0.2355 | 0.0857 | 0.1533 |
| `temporal_blocks_1m_rate_10` | 20260612 | `test` | 3 | `irc1` | 6,145 | 0.2079 | 0.2799 | 0.2574 | 0.1738 |
| `temporal_blocks_1m_rate_10` | 20260613 | `test` | 1 | `all` | 55,305 | 0.1540 | 0.2042 | 0.2457 | 0.1046 |
| `temporal_blocks_1m_rate_10` | 20260613 | `test` | 1 | `irc1` | 6,145 | 0.1504 | 0.1850 | 0.1874 | 0.1200 |
| `temporal_blocks_1m_rate_10` | 20260613 | `test` | 2 | `all` | 55,305 | 0.1958 | 0.2181 | 0.1021 | 0.1378 |
| `temporal_blocks_1m_rate_10` | 20260613 | `test` | 2 | `irc1` | 6,145 | 0.1916 | 0.2383 | 0.1958 | 0.1597 |
| `temporal_blocks_1m_rate_10` | 20260613 | `test` | 3 | `all` | 55,305 | 0.2154 | 0.2358 | 0.0862 | 0.1534 |
| `temporal_blocks_1m_rate_10` | 20260613 | `test` | 3 | `irc1` | 6,145 | 0.2079 | 0.2798 | 0.2569 | 0.1739 |
| `temporal_blocks_1m_rate_10` | 20260614 | `test` | 1 | `all` | 55,305 | 0.1540 | 0.2042 | 0.2458 | 0.1046 |
| `temporal_blocks_1m_rate_10` | 20260614 | `test` | 1 | `irc1` | 6,145 | 0.1503 | 0.1850 | 0.1875 | 0.1200 |
| `temporal_blocks_1m_rate_10` | 20260614 | `test` | 2 | `all` | 55,305 | 0.1958 | 0.2182 | 0.1024 | 0.1378 |
| `temporal_blocks_1m_rate_10` | 20260614 | `test` | 2 | `irc1` | 6,145 | 0.1917 | 0.2383 | 0.1955 | 0.1597 |
| `temporal_blocks_1m_rate_10` | 20260614 | `test` | 3 | `all` | 55,305 | 0.2154 | 0.2358 | 0.0865 | 0.1533 |
| `temporal_blocks_1m_rate_10` | 20260614 | `test` | 3 | `irc1` | 6,145 | 0.2079 | 0.2798 | 0.2570 | 0.1738 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 1 | `all` | 55,305 | 0.1541 | 0.2040 | 0.2449 | 0.1046 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 1 | `irc1` | 6,145 | 0.1504 | 0.1851 | 0.1879 | 0.1201 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 2 | `all` | 55,305 | 0.1960 | 0.2181 | 0.1015 | 0.1379 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 2 | `irc1` | 6,145 | 0.1918 | 0.2385 | 0.1957 | 0.1598 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 3 | `all` | 55,305 | 0.2156 | 0.2358 | 0.0858 | 0.1534 |
| `temporal_blocks_3m_rate_10` | 20260612 | `test` | 3 | `irc1` | 6,145 | 0.2080 | 0.2800 | 0.2570 | 0.1739 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 1 | `all` | 55,305 | 0.1546 | 0.2045 | 0.2442 | 0.1049 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 1 | `irc1` | 6,145 | 0.1507 | 0.1852 | 0.1863 | 0.1203 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 2 | `all` | 55,305 | 0.1962 | 0.2183 | 0.1010 | 0.1381 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 2 | `irc1` | 6,145 | 0.1919 | 0.2383 | 0.1946 | 0.1600 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 3 | `all` | 55,305 | 0.2158 | 0.2360 | 0.0857 | 0.1537 |
| `temporal_blocks_3m_rate_10` | 20260613 | `test` | 3 | `irc1` | 6,145 | 0.2083 | 0.2799 | 0.2558 | 0.1741 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 1 | `all` | 55,305 | 0.1547 | 0.2047 | 0.2443 | 0.1050 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 1 | `irc1` | 6,145 | 0.1506 | 0.1851 | 0.1862 | 0.1203 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 2 | `all` | 55,305 | 0.1963 | 0.2185 | 0.1018 | 0.1381 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 2 | `irc1` | 6,145 | 0.1920 | 0.2383 | 0.1943 | 0.1599 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 3 | `all` | 55,305 | 0.2158 | 0.2361 | 0.0862 | 0.1536 |
| `temporal_blocks_3m_rate_10` | 20260614 | `test` | 3 | `irc1` | 6,145 | 0.2083 | 0.2799 | 0.2558 | 0.1741 |
| `temporal_blocks_6m_rate_25` | 20260612 | `test` | 1 | `all` | 55,305 | 0.1576 | 0.2067 | 0.2376 | 0.1067 |
| `temporal_blocks_6m_rate_25` | 20260612 | `test` | 1 | `irc1` | 6,145 | 0.1524 | 0.1860 | 0.1803 | 0.1215 |
| `temporal_blocks_6m_rate_25` | 20260612 | `test` | 2 | `all` | 55,305 | 0.1988 | 0.2204 | 0.0978 | 0.1399 |
| `temporal_blocks_6m_rate_25` | 20260612 | `test` | 2 | `irc1` | 6,145 | 0.1943 | 0.2386 | 0.1858 | 0.1612 |
| `temporal_blocks_6m_rate_25` | 20260612 | `test` | 3 | `all` | 55,305 | 0.2180 | 0.2377 | 0.0829 | 0.1553 |
| `temporal_blocks_6m_rate_25` | 20260612 | `test` | 3 | `irc1` | 6,145 | 0.2107 | 0.2799 | 0.2473 | 0.1755 |
| `temporal_blocks_6m_rate_25` | 20260613 | `test` | 1 | `all` | 55,305 | 0.1611 | 0.2093 | 0.2304 | 0.1089 |
| `temporal_blocks_6m_rate_25` | 20260613 | `test` | 1 | `irc1` | 6,145 | 0.1545 | 0.1871 | 0.1745 | 0.1231 |
| `temporal_blocks_6m_rate_25` | 20260613 | `test` | 2 | `all` | 55,305 | 0.2017 | 0.2232 | 0.0965 | 0.1419 |
| `temporal_blocks_6m_rate_25` | 20260613 | `test` | 2 | `irc1` | 6,145 | 0.1959 | 0.2394 | 0.1816 | 0.1627 |
| `temporal_blocks_6m_rate_25` | 20260613 | `test` | 3 | `all` | 55,305 | 0.2205 | 0.2401 | 0.0817 | 0.1572 |
| `temporal_blocks_6m_rate_25` | 20260613 | `test` | 3 | `irc1` | 6,145 | 0.2122 | 0.2802 | 0.2426 | 0.1767 |
| `temporal_blocks_6m_rate_25` | 20260614 | `test` | 1 | `all` | 55,305 | 0.1620 | 0.2102 | 0.2295 | 0.1094 |
| `temporal_blocks_6m_rate_25` | 20260614 | `test` | 1 | `irc1` | 6,145 | 0.1541 | 0.1868 | 0.1749 | 0.1226 |
| `temporal_blocks_6m_rate_25` | 20260614 | `test` | 2 | `all` | 55,305 | 0.2020 | 0.2238 | 0.0976 | 0.1421 |
| `temporal_blocks_6m_rate_25` | 20260614 | `test` | 2 | `irc1` | 6,145 | 0.1956 | 0.2383 | 0.1792 | 0.1626 |
| `temporal_blocks_6m_rate_25` | 20260614 | `test` | 3 | `all` | 55,305 | 0.2208 | 0.2406 | 0.0825 | 0.1575 |
| `temporal_blocks_6m_rate_25` | 20260614 | `test` | 3 | `irc1` | 6,145 | 0.2121 | 0.2792 | 0.2403 | 0.1768 |

## Alert Metrics

| scenario | seed | event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| `ablate_light` | NA | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.0505 | 0.3690 | 0.1438 | 0.1561 |
| `ablate_light` | NA | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.0231 | 0.3719 | 0.1458 | 0.0556 |
| `ablate_light` | NA | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.0240 | 0.3712 | 0.1486 | 0.0374 |
| `ablate_light` | NA | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.2885 | 0.8641 | 0.1964 | 0.5044 |
| `ablate_light` | NA | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.1627 | 0.7831 | 0.2827 | 0.2587 |
| `ablate_light` | NA | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.1037 | 0.7610 | 0.3125 | 0.1546 |
| `ablate_nutrients` | NA | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.0445 | 0.3452 | 0.1390 | 0.1162 |
| `ablate_nutrients` | NA | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.0431 | 0.3122 | 0.1392 | 0.0765 |
| `ablate_nutrients` | NA | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.0820 | 0.3060 | 0.1415 | 0.1484 |
| `ablate_nutrients` | NA | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.5284 | 0.8281 | 0.1587 | 0.7961 |
| `ablate_nutrients` | NA | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.4472 | 0.7374 | 0.2026 | 0.6232 |
| `ablate_nutrients` | NA | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.3930 | 0.7061 | 0.2221 | 0.5229 |
| `ablate_physicochemical` | NA | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.0895 | 0.4023 | 0.1343 | 0.2394 |
| `ablate_physicochemical` | NA | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.1178 | 0.3798 | 0.1351 | 0.2816 |
| `ablate_physicochemical` | NA | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.1354 | 0.3730 | 0.1377 | 0.2978 |
| `ablate_physicochemical` | NA | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.3221 | 0.7211 | 0.2533 | 0.4567 |
| `ablate_physicochemical` | NA | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.2885 | 0.7302 | 0.2863 | 0.4018 |
| `ablate_physicochemical` | NA | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.2779 | 0.7406 | 0.2923 | 0.3879 |
| `control_observed` | NA | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.1554 | 0.4493 | 0.1250 | 0.4296 |
| `control_observed` | NA | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.1335 | 0.4047 | 0.1272 | 0.3244 |
| `control_observed` | NA | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.1532 | 0.3857 | 0.1308 | 0.3364 |
| `control_observed` | NA | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.4915 | 0.8572 | 0.1467 | 0.7794 |
| `control_observed` | NA | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.4343 | 0.7759 | 0.1936 | 0.6322 |
| `control_observed` | NA | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.4037 | 0.7553 | 0.2098 | 0.5743 |
| `random_dropout_mcar_10` | 20260612 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.1175 | 0.4344 | 0.1280 | 0.3263 |
| `random_dropout_mcar_10` | 20260612 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.1032 | 0.3977 | 0.1293 | 0.2549 |
| `random_dropout_mcar_10` | 20260612 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.1223 | 0.3813 | 0.1325 | 0.2718 |
| `random_dropout_mcar_10` | 20260612 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.4592 | 0.8448 | 0.1576 | 0.7279 |
| `random_dropout_mcar_10` | 20260612 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.3897 | 0.7757 | 0.2039 | 0.5762 |
| `random_dropout_mcar_10` | 20260612 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.3587 | 0.7583 | 0.2207 | 0.5199 |
| `random_dropout_mcar_10` | 20260613 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.1213 | 0.4377 | 0.1276 | 0.3462 |
| `random_dropout_mcar_10` | 20260613 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.1042 | 0.3993 | 0.1292 | 0.2607 |
| `random_dropout_mcar_10` | 20260613 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.1234 | 0.3841 | 0.1322 | 0.2820 |
| `random_dropout_mcar_10` | 20260613 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.4576 | 0.8495 | 0.1565 | 0.7228 |
| `random_dropout_mcar_10` | 20260613 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.3896 | 0.7758 | 0.2055 | 0.5708 |
| `random_dropout_mcar_10` | 20260613 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.3554 | 0.7571 | 0.2221 | 0.5125 |
| `random_dropout_mcar_10` | 20260614 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.1226 | 0.4308 | 0.1275 | 0.3427 |
| `random_dropout_mcar_10` | 20260614 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.1081 | 0.4023 | 0.1291 | 0.2607 |
| `random_dropout_mcar_10` | 20260614 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.1270 | 0.3827 | 0.1325 | 0.2707 |
| `random_dropout_mcar_10` | 20260614 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.4563 | 0.8466 | 0.1568 | 0.7241 |
| `random_dropout_mcar_10` | 20260614 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.3909 | 0.7737 | 0.2049 | 0.5705 |
| `random_dropout_mcar_10` | 20260614 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.3585 | 0.7540 | 0.2217 | 0.5172 |
| `random_dropout_mcar_25` | 20260612 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.0775 | 0.4240 | 0.1320 | 0.2207 |
| `random_dropout_mcar_25` | 20260612 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.0688 | 0.3941 | 0.1331 | 0.1727 |
| `random_dropout_mcar_25` | 20260612 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.0856 | 0.3845 | 0.1356 | 0.2016 |
| `random_dropout_mcar_25` | 20260612 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.3963 | 0.8281 | 0.1767 | 0.6318 |
| `random_dropout_mcar_25` | 20260612 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.3178 | 0.7747 | 0.2251 | 0.4750 |
| `random_dropout_mcar_25` | 20260612 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.2853 | 0.7622 | 0.2433 | 0.4162 |
| `random_dropout_mcar_25` | 20260613 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.0794 | 0.4014 | 0.1335 | 0.2195 |
| `random_dropout_mcar_25` | 20260613 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.0707 | 0.3785 | 0.1343 | 0.1669 |
| `random_dropout_mcar_25` | 20260613 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.0847 | 0.3718 | 0.1364 | 0.1891 |
| `random_dropout_mcar_25` | 20260613 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.3976 | 0.8285 | 0.1760 | 0.6315 |
| `random_dropout_mcar_25` | 20260613 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.3178 | 0.7641 | 0.2298 | 0.4699 |
| `random_dropout_mcar_25` | 20260613 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.2802 | 0.7494 | 0.2479 | 0.4046 |
| `random_dropout_mcar_25` | 20260614 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.0832 | 0.4015 | 0.1332 | 0.2230 |
| `random_dropout_mcar_25` | 20260614 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.0724 | 0.3744 | 0.1342 | 0.1750 |
| `random_dropout_mcar_25` | 20260614 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.0898 | 0.3597 | 0.1372 | 0.1880 |
| `random_dropout_mcar_25` | 20260614 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.3925 | 0.8206 | 0.1784 | 0.6210 |
| `random_dropout_mcar_25` | 20260614 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.3225 | 0.7601 | 0.2294 | 0.4732 |
| `random_dropout_mcar_25` | 20260614 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.2838 | 0.7456 | 0.2478 | 0.4084 |
| `random_dropout_mcar_50` | 20260612 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.0396 | 0.3900 | 0.1409 | 0.1045 |
| `random_dropout_mcar_50` | 20260612 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.0350 | 0.3668 | 0.1421 | 0.0857 |
| `random_dropout_mcar_50` | 20260612 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.0448 | 0.3667 | 0.1438 | 0.1042 |
| `random_dropout_mcar_50` | 20260612 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.2823 | 0.7922 | 0.2190 | 0.4466 |
| `random_dropout_mcar_50` | 20260612 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.1998 | 0.7563 | 0.2761 | 0.2931 |
| `random_dropout_mcar_50` | 20260612 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.1723 | 0.7502 | 0.2957 | 0.2446 |
| `random_dropout_mcar_50` | 20260613 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.0357 | 0.3887 | 0.1413 | 0.1009 |
| `random_dropout_mcar_50` | 20260613 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.0270 | 0.3707 | 0.1422 | 0.0672 |
| `random_dropout_mcar_50` | 20260613 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.0395 | 0.3579 | 0.1446 | 0.0951 |
| `random_dropout_mcar_50` | 20260613 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.2812 | 0.7881 | 0.2206 | 0.4460 |
| `random_dropout_mcar_50` | 20260613 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.1958 | 0.7466 | 0.2813 | 0.2867 |
| `random_dropout_mcar_50` | 20260613 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.1635 | 0.7379 | 0.3021 | 0.2354 |
| `random_dropout_mcar_50` | 20260614 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.0357 | 0.3917 | 0.1408 | 0.0986 |
| `random_dropout_mcar_50` | 20260614 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.0346 | 0.3698 | 0.1416 | 0.0776 |
| `random_dropout_mcar_50` | 20260614 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.0494 | 0.3555 | 0.1443 | 0.1042 |
| `random_dropout_mcar_50` | 20260614 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.2744 | 0.7807 | 0.2242 | 0.4317 |
| `random_dropout_mcar_50` | 20260614 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.1915 | 0.7460 | 0.2825 | 0.2834 |
| `random_dropout_mcar_50` | 20260614 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.1665 | 0.7366 | 0.3037 | 0.2363 |
| `temporal_blocks_1m_rate_10` | 20260612 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.1554 | 0.4493 | 0.1250 | 0.4296 |
| `temporal_blocks_1m_rate_10` | 20260612 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.1333 | 0.4047 | 0.1272 | 0.3233 |
| `temporal_blocks_1m_rate_10` | 20260612 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.1530 | 0.3856 | 0.1308 | 0.3352 |
| `temporal_blocks_1m_rate_10` | 20260612 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.4911 | 0.8571 | 0.1467 | 0.7788 |
| `temporal_blocks_1m_rate_10` | 20260612 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.4343 | 0.7759 | 0.1937 | 0.6322 |
| `temporal_blocks_1m_rate_10` | 20260612 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.4037 | 0.7553 | 0.2098 | 0.5743 |
| `temporal_blocks_1m_rate_10` | 20260613 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.1547 | 0.4482 | 0.1251 | 0.4272 |
| `temporal_blocks_1m_rate_10` | 20260613 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.1329 | 0.4034 | 0.1273 | 0.3221 |
| `temporal_blocks_1m_rate_10` | 20260613 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.1526 | 0.3843 | 0.1309 | 0.3341 |
| `temporal_blocks_1m_rate_10` | 20260613 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.4916 | 0.8568 | 0.1468 | 0.7794 |
| `temporal_blocks_1m_rate_10` | 20260613 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.4342 | 0.7754 | 0.1937 | 0.6319 |
| `temporal_blocks_1m_rate_10` | 20260613 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.4031 | 0.7547 | 0.2100 | 0.5731 |
| `temporal_blocks_1m_rate_10` | 20260614 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.1549 | 0.4480 | 0.1251 | 0.4272 |
| `temporal_blocks_1m_rate_10` | 20260614 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.1331 | 0.4029 | 0.1274 | 0.3233 |
| `temporal_blocks_1m_rate_10` | 20260614 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.1530 | 0.3838 | 0.1309 | 0.3352 |
| `temporal_blocks_1m_rate_10` | 20260614 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.4915 | 0.8569 | 0.1468 | 0.7791 |
| `temporal_blocks_1m_rate_10` | 20260614 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.4340 | 0.7754 | 0.1938 | 0.6316 |
| `temporal_blocks_1m_rate_10` | 20260614 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.4036 | 0.7548 | 0.2099 | 0.5740 |
| `temporal_blocks_3m_rate_10` | 20260612 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.1551 | 0.4491 | 0.1250 | 0.4284 |
| `temporal_blocks_3m_rate_10` | 20260612 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.1333 | 0.4045 | 0.1273 | 0.3233 |
| `temporal_blocks_3m_rate_10` | 20260612 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.1526 | 0.3854 | 0.1309 | 0.3341 |
| `temporal_blocks_3m_rate_10` | 20260612 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.4908 | 0.8570 | 0.1468 | 0.7781 |
| `temporal_blocks_3m_rate_10` | 20260612 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.4342 | 0.7758 | 0.1938 | 0.6319 |
| `temporal_blocks_3m_rate_10` | 20260612 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.4036 | 0.7552 | 0.2100 | 0.5740 |
| `temporal_blocks_3m_rate_10` | 20260613 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.1543 | 0.4464 | 0.1253 | 0.4249 |
| `temporal_blocks_3m_rate_10` | 20260613 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.1325 | 0.4012 | 0.1276 | 0.3198 |
| `temporal_blocks_3m_rate_10` | 20260613 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.1522 | 0.3820 | 0.1312 | 0.3318 |
| `temporal_blocks_3m_rate_10` | 20260613 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.4903 | 0.8562 | 0.1471 | 0.7772 |
| `temporal_blocks_3m_rate_10` | 20260613 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.4330 | 0.7746 | 0.1942 | 0.6298 |
| `temporal_blocks_3m_rate_10` | 20260613 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.4020 | 0.7539 | 0.2105 | 0.5710 |
| `temporal_blocks_3m_rate_10` | 20260614 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.1543 | 0.4466 | 0.1253 | 0.4249 |
| `temporal_blocks_3m_rate_10` | 20260614 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.1327 | 0.4008 | 0.1276 | 0.3210 |
| `temporal_blocks_3m_rate_10` | 20260614 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.1526 | 0.3819 | 0.1311 | 0.3330 |
| `temporal_blocks_3m_rate_10` | 20260614 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.4903 | 0.8563 | 0.1472 | 0.7772 |
| `temporal_blocks_3m_rate_10` | 20260614 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.4329 | 0.7745 | 0.1942 | 0.6292 |
| `temporal_blocks_3m_rate_10` | 20260614 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.4021 | 0.7540 | 0.2104 | 0.5713 |
| `temporal_blocks_6m_rate_25` | 20260612 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.1515 | 0.4405 | 0.1258 | 0.4178 |
| `temporal_blocks_6m_rate_25` | 20260612 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.1299 | 0.4013 | 0.1277 | 0.3163 |
| `temporal_blocks_6m_rate_25` | 20260612 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.1488 | 0.3811 | 0.1314 | 0.3262 |
| `temporal_blocks_6m_rate_25` | 20260612 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.4836 | 0.8548 | 0.1487 | 0.7677 |
| `temporal_blocks_6m_rate_25` | 20260612 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.4252 | 0.7738 | 0.1963 | 0.6193 |
| `temporal_blocks_6m_rate_25` | 20260612 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.3954 | 0.7533 | 0.2131 | 0.5630 |
| `temporal_blocks_6m_rate_25` | 20260613 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.1494 | 0.4455 | 0.1259 | 0.4190 |
| `temporal_blocks_6m_rate_25` | 20260613 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.1272 | 0.4031 | 0.1279 | 0.3094 |
| `temporal_blocks_6m_rate_25` | 20260613 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.1453 | 0.3851 | 0.1313 | 0.3228 |
| `temporal_blocks_6m_rate_25` | 20260613 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.4771 | 0.8516 | 0.1518 | 0.7557 |
| `temporal_blocks_6m_rate_25` | 20260613 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.4221 | 0.7696 | 0.1998 | 0.6136 |
| `temporal_blocks_6m_rate_25` | 20260613 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.3924 | 0.7494 | 0.2160 | 0.5568 |
| `temporal_blocks_6m_rate_25` | 20260614 | `bloom_h` | `test` | 1 | 4,673 | 0.1823 | 0.1464 | 0.4433 | 0.1259 | 0.4038 |
| `temporal_blocks_6m_rate_25` | 20260614 | `bloom_h` | `test` | 2 | 4,710 | 0.1832 | 0.1259 | 0.4034 | 0.1278 | 0.3094 |
| `temporal_blocks_6m_rate_25` | 20260614 | `bloom_h` | `test` | 3 | 4,757 | 0.1856 | 0.1453 | 0.3841 | 0.1314 | 0.3194 |
| `temporal_blocks_6m_rate_25` | 20260614 | `irc_alert` | `test` | 1 | 6,145 | 0.5149 | 0.4747 | 0.8535 | 0.1502 | 0.7570 |
| `temporal_blocks_6m_rate_25` | 20260614 | `irc_alert` | `test` | 2 | 6,145 | 0.5403 | 0.4182 | 0.7740 | 0.1984 | 0.6108 |
| `temporal_blocks_6m_rate_25` | 20260614 | `irc_alert` | `test` | 3 | 6,145 | 0.5474 | 0.3886 | 0.7532 | 0.2154 | 0.5547 |

## Policy Metrics

| scenario | seed | policy | event | split | horizon | rows | recall | precision | alert rate | F2 | delta F2 |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `ablate_light` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.1995 | 0.5247 | 0.0693 | 0.2278 | -0.2772 |
| `ablate_light` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.1043 | 0.4500 | 0.0425 | 0.1232 | -0.3606 |
| `ablate_light` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.1812 | 0.4444 | 0.0757 | 0.2055 | -0.3898 |
| `ablate_light` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.5088 | 0.8974 | 0.2919 | 0.5571 | -0.2347 |
| `ablate_light` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.4286 | 0.8371 | 0.2766 | 0.4750 | -0.2965 |
| `ablate_light` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.5190 | 0.7940 | 0.3579 | 0.5576 | -0.2545 |
| `ablate_light` | NA | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.3005 | 0.4288 | 0.1278 | 0.3196 | -0.2682 |
| `ablate_light` | NA | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.1738 | 0.4559 | 0.0699 | 0.1984 | -0.3668 |
| `ablate_light` | NA | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.2310 | 0.4636 | 0.0925 | 0.2568 | -0.3537 |
| `ablate_light` | NA | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.8752 | 0.7458 | 0.6042 | 0.8458 | -0.0365 |
| `ablate_light` | NA | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9563 | 0.6337 | 0.8153 | 0.8680 | -0.0101 |
| `ablate_light` | NA | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9180 | 0.6766 | 0.7427 | 0.8568 | -0.0243 |
| `ablate_light` | NA | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.5044 | 0.9002 | 0.2885 | 0.5531 | -0.2335 |
| `ablate_light` | NA | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.2587 | 0.8590 | 0.1627 | 0.3008 | -0.3573 |
| `ablate_light` | NA | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.1546 | 0.8163 | 0.1037 | 0.1845 | -0.4216 |
| `ablate_nutrients` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.2547 | 0.3931 | 0.1181 | 0.2740 | -0.2310 |
| `ablate_nutrients` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.2897 | 0.3487 | 0.1522 | 0.2998 | -0.1840 |
| `ablate_nutrients` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.5764 | 0.3125 | 0.3424 | 0.4931 | -0.1022 |
| `ablate_nutrients` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.8028 | 0.7739 | 0.5341 | 0.7968 | 0.0051 |
| `ablate_nutrients` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.8226 | 0.7151 | 0.6215 | 0.7986 | 0.0271 |
| `ablate_nutrients` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.9028 | 0.6750 | 0.7321 | 0.8457 | 0.0335 |
| `ablate_nutrients` | NA | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.5798 | 0.3229 | 0.3274 | 0.5002 | -0.0876 |
| `ablate_nutrients` | NA | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.4948 | 0.3514 | 0.2580 | 0.4575 | -0.1077 |
| `ablate_nutrients` | NA | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.6308 | 0.3008 | 0.3893 | 0.5173 | -0.0932 |
| `ablate_nutrients` | NA | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9716 | 0.6271 | 0.7977 | 0.8754 | -0.0069 |
| `ablate_nutrients` | NA | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9970 | 0.5839 | 0.9225 | 0.8734 | -0.0047 |
| `ablate_nutrients` | NA | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9902 | 0.5964 | 0.9089 | 0.8747 | -0.0065 |
| `ablate_nutrients` | NA | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.7961 | 0.7758 | 0.5284 | 0.7920 | 0.0054 |
| `ablate_nutrients` | NA | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.6232 | 0.7529 | 0.4472 | 0.6454 | -0.0126 |
| `ablate_nutrients` | NA | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.5229 | 0.7284 | 0.3930 | 0.5542 | -0.0520 |
| `ablate_physicochemical` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.2817 | 0.4607 | 0.1115 | 0.3054 | -0.1995 |
| `ablate_physicochemical` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.3499 | 0.4131 | 0.1552 | 0.3610 | -0.1228 |
| `ablate_physicochemical` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.4530 | 0.3600 | 0.2336 | 0.4308 | -0.1646 |
| `ablate_physicochemical` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.4649 | 0.7289 | 0.3284 | 0.5012 | -0.2905 |
| `ablate_physicochemical` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.4991 | 0.7322 | 0.3683 | 0.5330 | -0.2384 |
| `ablate_physicochemical` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.5773 | 0.7214 | 0.4381 | 0.6013 | -0.2109 |
| `ablate_physicochemical` | NA | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.4178 | 0.4294 | 0.1774 | 0.4201 | -0.1677 |
| `ablate_physicochemical` | NA | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.4090 | 0.3875 | 0.1934 | 0.4045 | -0.1606 |
| `ablate_physicochemical` | NA | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.4757 | 0.3503 | 0.2520 | 0.4439 | -0.1666 |
| `ablate_physicochemical` | NA | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.7832 | 0.6280 | 0.6421 | 0.7463 | -0.1360 |
| `ablate_physicochemical` | NA | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.8419 | 0.6229 | 0.7302 | 0.7866 | -0.0915 |
| `ablate_physicochemical` | NA | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.8127 | 0.6412 | 0.6939 | 0.7714 | -0.1097 |
| `ablate_physicochemical` | NA | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.4567 | 0.7302 | 0.3221 | 0.4937 | -0.2929 |
| `ablate_physicochemical` | NA | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.4018 | 0.7524 | 0.2885 | 0.4431 | -0.2149 |
| `ablate_physicochemical` | NA | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.3879 | 0.7641 | 0.2779 | 0.4303 | -0.1758 |
| `control_observed` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.5153 | 0.4675 | 0.2009 | 0.5049 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.4983 | 0.4335 | 0.2106 | 0.4838 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.6988 | 0.3739 | 0.3469 | 0.5953 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.7863 | 0.8141 | 0.4973 | 0.7918 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.7780 | 0.7463 | 0.5632 | 0.7715 | 0.0000 |
| `control_observed` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.8448 | 0.7035 | 0.6574 | 0.8122 | 0.0000 |
| `control_observed` | NA | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.6702 | 0.3941 | 0.3101 | 0.5878 | 0.0000 |
| `control_observed` | NA | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.6280 | 0.4036 | 0.2851 | 0.5652 | 0.0000 |
| `control_observed` | NA | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.7395 | 0.3596 | 0.3818 | 0.6105 | 0.0000 |
| `control_observed` | NA | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9700 | 0.6480 | 0.7707 | 0.8823 | 0.0000 |
| `control_observed` | NA | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9925 | 0.6009 | 0.8923 | 0.8781 | 0.0000 |
| `control_observed` | NA | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9878 | 0.6154 | 0.8788 | 0.8812 | 0.0000 |
| `control_observed` | NA | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.7794 | 0.8166 | 0.4915 | 0.7866 | 0.0000 |
| `control_observed` | NA | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.6322 | 0.7864 | 0.4343 | 0.6580 | 0.0000 |
| `control_observed` | NA | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.5743 | 0.7787 | 0.4037 | 0.6061 | 0.0000 |
| `random_dropout_mcar_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.4085 | 0.4703 | 0.1584 | 0.4195 | -0.0855 |
| `random_dropout_mcar_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.4171 | 0.4343 | 0.1760 | 0.4205 | -0.0633 |
| `random_dropout_mcar_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.6342 | 0.3851 | 0.3057 | 0.5616 | -0.0338 |
| `random_dropout_mcar_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.7342 | 0.8137 | 0.4646 | 0.7488 | -0.0429 |
| `random_dropout_mcar_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.7328 | 0.7575 | 0.5227 | 0.7376 | -0.0338 |
| `random_dropout_mcar_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.8062 | 0.7207 | 0.6124 | 0.7875 | -0.0247 |
| `random_dropout_mcar_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.5974 | 0.4046 | 0.2692 | 0.5454 | -0.0424 |
| `random_dropout_mcar_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.5377 | 0.4106 | 0.2399 | 0.5063 | -0.0588 |
| `random_dropout_mcar_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.6806 | 0.3740 | 0.3378 | 0.5847 | -0.0258 |
| `random_dropout_mcar_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9564 | 0.6520 | 0.7552 | 0.8747 | -0.0076 |
| `random_dropout_mcar_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9886 | 0.6028 | 0.8861 | 0.8764 | -0.0017 |
| `random_dropout_mcar_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9842 | 0.6195 | 0.8698 | 0.8805 | -0.0006 |
| `random_dropout_mcar_10` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.7279 | 0.8161 | 0.4592 | 0.7440 | -0.0426 |
| `random_dropout_mcar_10` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.5762 | 0.7987 | 0.3897 | 0.6102 | -0.0478 |
| `random_dropout_mcar_10` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.5199 | 0.7936 | 0.3587 | 0.5584 | -0.0477 |
| `random_dropout_mcar_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.4155 | 0.4896 | 0.1547 | 0.4285 | -0.0765 |
| `random_dropout_mcar_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.4253 | 0.4481 | 0.1739 | 0.4296 | -0.0542 |
| `random_dropout_mcar_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.6274 | 0.3874 | 0.3006 | 0.5582 | -0.0371 |
| `random_dropout_mcar_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.7295 | 0.8101 | 0.4636 | 0.7443 | -0.0475 |
| `random_dropout_mcar_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.7214 | 0.7517 | 0.5185 | 0.7273 | -0.0442 |
| `random_dropout_mcar_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.8050 | 0.7168 | 0.6148 | 0.7857 | -0.0265 |
| `random_dropout_mcar_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.6068 | 0.4146 | 0.2669 | 0.5553 | -0.0325 |
| `random_dropout_mcar_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.5504 | 0.4222 | 0.2389 | 0.5189 | -0.0463 |
| `random_dropout_mcar_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.6693 | 0.3710 | 0.3349 | 0.5766 | -0.0339 |
| `random_dropout_mcar_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9602 | 0.6562 | 0.7535 | 0.8787 | -0.0036 |
| `random_dropout_mcar_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9895 | 0.6031 | 0.8864 | 0.8771 | -0.0010 |
| `random_dropout_mcar_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9857 | 0.6197 | 0.8708 | 0.8816 | 0.0004 |
| `random_dropout_mcar_10` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.7228 | 0.8133 | 0.4576 | 0.7393 | -0.0473 |
| `random_dropout_mcar_10` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.5708 | 0.7916 | 0.3896 | 0.6045 | -0.0535 |
| `random_dropout_mcar_10` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.5125 | 0.7894 | 0.3554 | 0.5512 | -0.0550 |
| `random_dropout_mcar_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.4390 | 0.4876 | 0.1641 | 0.4479 | -0.0570 |
| `random_dropout_mcar_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.4125 | 0.4315 | 0.1752 | 0.4162 | -0.0676 |
| `random_dropout_mcar_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.6206 | 0.3785 | 0.3044 | 0.5502 | -0.0451 |
| `random_dropout_mcar_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.7307 | 0.8155 | 0.4614 | 0.7462 | -0.0455 |
| `random_dropout_mcar_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.7223 | 0.7555 | 0.5165 | 0.7287 | -0.0428 |
| `random_dropout_mcar_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.8047 | 0.7211 | 0.6109 | 0.7865 | -0.0257 |
| `random_dropout_mcar_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.6033 | 0.4122 | 0.2669 | 0.5521 | -0.0357 |
| `random_dropout_mcar_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.5492 | 0.4129 | 0.2437 | 0.5152 | -0.0500 |
| `random_dropout_mcar_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.6693 | 0.3673 | 0.3382 | 0.5748 | -0.0357 |
| `random_dropout_mcar_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9608 | 0.6525 | 0.7582 | 0.8779 | -0.0045 |
| `random_dropout_mcar_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9898 | 0.6048 | 0.8841 | 0.8780 | -0.0001 |
| `random_dropout_mcar_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9854 | 0.6203 | 0.8697 | 0.8816 | 0.0005 |
| `random_dropout_mcar_10` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.7241 | 0.8170 | 0.4563 | 0.7409 | -0.0456 |
| `random_dropout_mcar_10` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.5705 | 0.7885 | 0.3909 | 0.6039 | -0.0542 |
| `random_dropout_mcar_10` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.5172 | 0.7898 | 0.3585 | 0.5556 | -0.0505 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.2934 | 0.4941 | 0.1083 | 0.3194 | -0.1856 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.3013 | 0.4514 | 0.1223 | 0.3227 | -0.1611 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.4983 | 0.4074 | 0.2270 | 0.4770 | -0.1183 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.6372 | 0.8198 | 0.4002 | 0.6669 | -0.1249 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.6446 | 0.7759 | 0.4488 | 0.6672 | -0.1043 |
| `random_dropout_mcar_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.7304 | 0.7398 | 0.5404 | 0.7323 | -0.0799 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.4812 | 0.4266 | 0.2056 | 0.4692 | -0.1186 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.4090 | 0.4315 | 0.1737 | 0.4133 | -0.1518 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.5481 | 0.3897 | 0.2611 | 0.5069 | -0.1036 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9387 | 0.6594 | 0.7330 | 0.8654 | -0.0169 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9804 | 0.6074 | 0.8721 | 0.8732 | -0.0049 |
| `random_dropout_mcar_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9724 | 0.6246 | 0.8522 | 0.8749 | -0.0062 |
| `random_dropout_mcar_25` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.6318 | 0.8209 | 0.3963 | 0.6623 | -0.1242 |
| `random_dropout_mcar_25` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.4750 | 0.8075 | 0.3178 | 0.5176 | -0.1404 |
| `random_dropout_mcar_25` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.4162 | 0.7986 | 0.2853 | 0.4603 | -0.1459 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.2817 | 0.4734 | 0.1085 | 0.3065 | -0.1984 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.3071 | 0.4492 | 0.1253 | 0.3278 | -0.1560 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.5006 | 0.4000 | 0.2323 | 0.4766 | -0.1187 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.6387 | 0.8146 | 0.4037 | 0.6676 | -0.1242 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.6413 | 0.7625 | 0.4544 | 0.6623 | -0.1091 |
| `random_dropout_mcar_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.7241 | 0.7331 | 0.5408 | 0.7259 | -0.0863 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.4636 | 0.4136 | 0.2044 | 0.4527 | -0.1351 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.4067 | 0.4234 | 0.1760 | 0.4100 | -0.1552 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.5504 | 0.3894 | 0.2624 | 0.5084 | -0.1021 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9415 | 0.6657 | 0.7282 | 0.8695 | -0.0128 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9819 | 0.6066 | 0.8745 | 0.8738 | -0.0043 |
| `random_dropout_mcar_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9712 | 0.6236 | 0.8526 | 0.8738 | -0.0074 |
| `random_dropout_mcar_25` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.6315 | 0.8178 | 0.3976 | 0.6616 | -0.1249 |
| `random_dropout_mcar_25` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.4699 | 0.7988 | 0.3178 | 0.5120 | -0.1460 |
| `random_dropout_mcar_25` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.4046 | 0.7904 | 0.2802 | 0.4483 | -0.1578 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.2969 | 0.4774 | 0.1134 | 0.3212 | -0.1837 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.2932 | 0.4217 | 0.1274 | 0.3122 | -0.1716 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.4915 | 0.3872 | 0.2357 | 0.4664 | -0.1290 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.6327 | 0.8135 | 0.4005 | 0.6622 | -0.1296 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.6340 | 0.7655 | 0.4475 | 0.6566 | -0.1149 |
| `random_dropout_mcar_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.7197 | 0.7354 | 0.5357 | 0.7228 | -0.0894 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.4800 | 0.4115 | 0.2127 | 0.4646 | -0.1232 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.4079 | 0.4131 | 0.1809 | 0.4089 | -0.1563 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.5447 | 0.3781 | 0.2674 | 0.5006 | -0.1099 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9384 | 0.6595 | 0.7326 | 0.8652 | -0.0171 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9837 | 0.6079 | 0.8744 | 0.8755 | -0.0026 |
| `random_dropout_mcar_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9724 | 0.6239 | 0.8532 | 0.8746 | -0.0065 |
| `random_dropout_mcar_25` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.6210 | 0.8147 | 0.3925 | 0.6520 | -0.1345 |
| `random_dropout_mcar_25` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.4732 | 0.7926 | 0.3225 | 0.5147 | -0.1434 |
| `random_dropout_mcar_25` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.4084 | 0.7878 | 0.2838 | 0.4520 | -0.1542 |
| `random_dropout_mcar_50` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.1397 | 0.4818 | 0.0529 | 0.1628 | -0.3422 |
| `random_dropout_mcar_50` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.1495 | 0.4230 | 0.0648 | 0.1717 | -0.3121 |
| `random_dropout_mcar_50` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.2831 | 0.3925 | 0.1339 | 0.2998 | -0.2955 |
| `random_dropout_mcar_50` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.4611 | 0.8165 | 0.2908 | 0.5051 | -0.2867 |
| `random_dropout_mcar_50` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.4512 | 0.7802 | 0.3124 | 0.4928 | -0.2787 |
| `random_dropout_mcar_50` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.5505 | 0.7656 | 0.3937 | 0.5833 | -0.2289 |
| `random_dropout_mcar_50` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.2782 | 0.4447 | 0.1141 | 0.3007 | -0.2871 |
| `random_dropout_mcar_50` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.2144 | 0.4139 | 0.0949 | 0.2372 | -0.3279 |
| `random_dropout_mcar_50` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.3103 | 0.3759 | 0.1532 | 0.3215 | -0.2890 |
| `random_dropout_mcar_50` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.8821 | 0.6570 | 0.6913 | 0.8255 | -0.0568 |
| `random_dropout_mcar_50` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9542 | 0.6095 | 0.8459 | 0.8572 | -0.0208 |
| `random_dropout_mcar_50` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9293 | 0.6343 | 0.8020 | 0.8502 | -0.0310 |
| `random_dropout_mcar_50` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.4466 | 0.8144 | 0.2823 | 0.4909 | -0.2956 |
| `random_dropout_mcar_50` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.2931 | 0.7923 | 0.1998 | 0.3353 | -0.3227 |
| `random_dropout_mcar_50` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.2446 | 0.7771 | 0.1723 | 0.2835 | -0.3226 |
| `random_dropout_mcar_50` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.1244 | 0.4977 | 0.0456 | 0.1464 | -0.3586 |
| `random_dropout_mcar_50` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.1414 | 0.4469 | 0.0580 | 0.1638 | -0.3200 |
| `random_dropout_mcar_50` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.2741 | 0.3954 | 0.1287 | 0.2920 | -0.3033 |
| `random_dropout_mcar_50` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.4548 | 0.8135 | 0.2879 | 0.4988 | -0.2930 |
| `random_dropout_mcar_50` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.4434 | 0.7751 | 0.3090 | 0.4849 | -0.2866 |
| `random_dropout_mcar_50` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.5351 | 0.7544 | 0.3883 | 0.5681 | -0.2441 |
| `random_dropout_mcar_50` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.2793 | 0.4449 | 0.1145 | 0.3018 | -0.2860 |
| `random_dropout_mcar_50` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.2155 | 0.4366 | 0.0904 | 0.2398 | -0.3254 |
| `random_dropout_mcar_50` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.3137 | 0.3946 | 0.1476 | 0.3271 | -0.2834 |
| `random_dropout_mcar_50` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.8752 | 0.6623 | 0.6804 | 0.8223 | -0.0600 |
| `random_dropout_mcar_50` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9464 | 0.6076 | 0.8415 | 0.8514 | -0.0266 |
| `random_dropout_mcar_50` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9191 | 0.6321 | 0.7961 | 0.8426 | -0.0386 |
| `random_dropout_mcar_50` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.4460 | 0.8166 | 0.2812 | 0.4905 | -0.2961 |
| `random_dropout_mcar_50` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.2867 | 0.7914 | 0.1958 | 0.3287 | -0.3294 |
| `random_dropout_mcar_50` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.2354 | 0.7881 | 0.1635 | 0.2738 | -0.3323 |
| `random_dropout_mcar_50` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.1455 | 0.5254 | 0.0505 | 0.1701 | -0.3348 |
| `random_dropout_mcar_50` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.1634 | 0.4312 | 0.0694 | 0.1866 | -0.2972 |
| `random_dropout_mcar_50` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.2888 | 0.3953 | 0.1356 | 0.3052 | -0.2901 |
| `random_dropout_mcar_50` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.4387 | 0.8051 | 0.2806 | 0.4826 | -0.3091 |
| `random_dropout_mcar_50` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.4386 | 0.7749 | 0.3058 | 0.4802 | -0.2912 |
| `random_dropout_mcar_50` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.5294 | 0.7627 | 0.3800 | 0.5639 | -0.2483 |
| `random_dropout_mcar_50` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.2758 | 0.4401 | 0.1143 | 0.2981 | -0.2897 |
| `random_dropout_mcar_50` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.2317 | 0.4141 | 0.1025 | 0.2541 | -0.3110 |
| `random_dropout_mcar_50` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.3239 | 0.3923 | 0.1532 | 0.3356 | -0.2749 |
| `random_dropout_mcar_50` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.8758 | 0.6628 | 0.6804 | 0.8229 | -0.0594 |
| `random_dropout_mcar_50` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9524 | 0.6111 | 0.8420 | 0.8567 | -0.0213 |
| `random_dropout_mcar_50` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9191 | 0.6332 | 0.7946 | 0.8430 | -0.0381 |
| `random_dropout_mcar_50` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.4317 | 0.8102 | 0.2744 | 0.4762 | -0.3103 |
| `random_dropout_mcar_50` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.2834 | 0.7995 | 0.1915 | 0.3254 | -0.3326 |
| `random_dropout_mcar_50` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.2363 | 0.7771 | 0.1665 | 0.2745 | -0.3316 |
| `temporal_blocks_1m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.5141 | 0.4670 | 0.2007 | 0.5039 | -0.0010 |
| `temporal_blocks_1m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.4983 | 0.4335 | 0.2106 | 0.4838 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.6988 | 0.3739 | 0.3469 | 0.5953 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.7857 | 0.8140 | 0.4970 | 0.7912 | -0.0005 |
| `temporal_blocks_1m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.7771 | 0.7463 | 0.5626 | 0.7707 | -0.0007 |
| `temporal_blocks_1m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.8448 | 0.7036 | 0.6573 | 0.8122 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.6702 | 0.3941 | 0.3101 | 0.5878 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.6280 | 0.4036 | 0.2851 | 0.5652 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.7395 | 0.3596 | 0.3818 | 0.6105 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9700 | 0.6477 | 0.7710 | 0.8822 | -0.0001 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9925 | 0.6008 | 0.8924 | 0.8780 | -0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9881 | 0.6153 | 0.8791 | 0.8813 | 0.0002 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.7788 | 0.8164 | 0.4911 | 0.7860 | -0.0005 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.6322 | 0.7864 | 0.4343 | 0.6580 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.5743 | 0.7787 | 0.4037 | 0.6061 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.5117 | 0.4663 | 0.2001 | 0.5020 | -0.0030 |
| `temporal_blocks_1m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.4971 | 0.4333 | 0.2102 | 0.4829 | -0.0009 |
| `temporal_blocks_1m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.6965 | 0.3736 | 0.3460 | 0.5939 | -0.0015 |
| `temporal_blocks_1m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.7860 | 0.8138 | 0.4973 | 0.7914 | -0.0003 |
| `temporal_blocks_1m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.7783 | 0.7464 | 0.5634 | 0.7717 | 0.0003 |
| `temporal_blocks_1m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.8448 | 0.7033 | 0.6576 | 0.8121 | -0.0000 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.6690 | 0.3939 | 0.3097 | 0.5870 | -0.0008 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.6269 | 0.4034 | 0.2847 | 0.5644 | -0.0008 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.7384 | 0.3598 | 0.3809 | 0.6100 | -0.0005 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9700 | 0.6479 | 0.7709 | 0.8823 | -0.0001 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9925 | 0.6007 | 0.8926 | 0.8780 | -0.0001 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9878 | 0.6153 | 0.8789 | 0.8811 | -0.0000 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.7794 | 0.8163 | 0.4916 | 0.7865 | -0.0001 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.6319 | 0.7864 | 0.4342 | 0.6578 | -0.0003 |
| `temporal_blocks_1m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.5731 | 0.7784 | 0.4031 | 0.6050 | -0.0011 |
| `temporal_blocks_1m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.5141 | 0.4670 | 0.2007 | 0.5039 | -0.0010 |
| `temporal_blocks_1m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.4971 | 0.4329 | 0.2104 | 0.4828 | -0.0010 |
| `temporal_blocks_1m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.6976 | 0.3740 | 0.3462 | 0.5947 | -0.0006 |
| `temporal_blocks_1m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.7860 | 0.8138 | 0.4973 | 0.7914 | -0.0003 |
| `temporal_blocks_1m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.7777 | 0.7460 | 0.5632 | 0.7712 | -0.0003 |
| `temporal_blocks_1m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.8448 | 0.7031 | 0.6578 | 0.8121 | -0.0001 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.6690 | 0.3939 | 0.3097 | 0.5870 | -0.0008 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.6269 | 0.4037 | 0.2845 | 0.5645 | -0.0007 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.7384 | 0.3594 | 0.3813 | 0.6098 | -0.0007 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9700 | 0.6480 | 0.7707 | 0.8823 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9925 | 0.6008 | 0.8924 | 0.8780 | -0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9878 | 0.6154 | 0.8788 | 0.8812 | 0.0000 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.7791 | 0.8162 | 0.4915 | 0.7862 | -0.0003 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.6316 | 0.7863 | 0.4340 | 0.6575 | -0.0005 |
| `temporal_blocks_1m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.5740 | 0.7786 | 0.4036 | 0.6059 | -0.0003 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.5153 | 0.4675 | 0.2009 | 0.5049 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.4971 | 0.4329 | 0.2104 | 0.4828 | -0.0010 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.6988 | 0.3739 | 0.3469 | 0.5953 | 0.0000 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.7851 | 0.8139 | 0.4967 | 0.7907 | -0.0011 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.7768 | 0.7462 | 0.5624 | 0.7705 | -0.0010 |
| `temporal_blocks_3m_rate_10` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.8439 | 0.7043 | 0.6560 | 0.8117 | -0.0004 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.6690 | 0.3942 | 0.3094 | 0.5871 | -0.0007 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.6269 | 0.4040 | 0.2843 | 0.5646 | -0.0006 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.7407 | 0.3599 | 0.3820 | 0.6113 | 0.0008 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9703 | 0.6477 | 0.7714 | 0.8824 | 0.0001 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9925 | 0.6007 | 0.8926 | 0.8780 | -0.0001 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9884 | 0.6154 | 0.8793 | 0.8815 | 0.0004 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.7781 | 0.8163 | 0.4908 | 0.7855 | -0.0011 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.6319 | 0.7864 | 0.4342 | 0.6578 | -0.0003 |
| `temporal_blocks_3m_rate_10` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.5740 | 0.7786 | 0.4036 | 0.6059 | -0.0003 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.5094 | 0.4652 | 0.1997 | 0.4999 | -0.0051 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.4936 | 0.4316 | 0.2096 | 0.4798 | -0.0040 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.6942 | 0.3729 | 0.3456 | 0.5922 | -0.0032 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.7838 | 0.8136 | 0.4960 | 0.7896 | -0.0021 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.7768 | 0.7458 | 0.5627 | 0.7704 | -0.0011 |
| `temporal_blocks_3m_rate_10` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.8439 | 0.7027 | 0.6574 | 0.8113 | -0.0009 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.6643 | 0.3922 | 0.3088 | 0.5834 | -0.0044 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.6246 | 0.4025 | 0.2843 | 0.5625 | -0.0027 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.7350 | 0.3590 | 0.3801 | 0.6077 | -0.0028 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9700 | 0.6476 | 0.7712 | 0.8822 | -0.0002 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9925 | 0.6004 | 0.8931 | 0.8778 | -0.0002 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9878 | 0.6150 | 0.8793 | 0.8810 | -0.0001 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.7772 | 0.8161 | 0.4903 | 0.7847 | -0.0019 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.6298 | 0.7858 | 0.4330 | 0.6559 | -0.0022 |
| `temporal_blocks_3m_rate_10` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.5710 | 0.7777 | 0.4020 | 0.6031 | -0.0030 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.5106 | 0.4662 | 0.1997 | 0.5010 | -0.0039 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.4936 | 0.4320 | 0.2093 | 0.4799 | -0.0039 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.6954 | 0.3742 | 0.3450 | 0.5935 | -0.0019 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.7841 | 0.8137 | 0.4962 | 0.7899 | -0.0019 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.7762 | 0.7454 | 0.5626 | 0.7699 | -0.0016 |
| `temporal_blocks_3m_rate_10` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.8451 | 0.7034 | 0.6578 | 0.8124 | 0.0002 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.6655 | 0.3929 | 0.3088 | 0.5844 | -0.0034 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.6234 | 0.4027 | 0.2837 | 0.5618 | -0.0034 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.7361 | 0.3599 | 0.3797 | 0.6088 | -0.0017 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9700 | 0.6477 | 0.7710 | 0.8822 | -0.0001 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9928 | 0.6007 | 0.8929 | 0.8781 | 0.0001 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9881 | 0.6156 | 0.8788 | 0.8814 | 0.0003 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.7772 | 0.8161 | 0.4903 | 0.7847 | -0.0019 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.6292 | 0.7853 | 0.4329 | 0.6553 | -0.0028 |
| `temporal_blocks_3m_rate_10` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.5713 | 0.7778 | 0.4021 | 0.6034 | -0.0028 |
| `temporal_blocks_6m_rate_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.5035 | 0.4658 | 0.1971 | 0.4955 | -0.0095 |
| `temporal_blocks_6m_rate_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.4844 | 0.4327 | 0.2051 | 0.4731 | -0.0107 |
| `temporal_blocks_6m_rate_25` | 20260612 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.6852 | 0.3735 | 0.3406 | 0.5872 | -0.0082 |
| `temporal_blocks_6m_rate_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.7750 | 0.8154 | 0.4893 | 0.7827 | -0.0090 |
| `temporal_blocks_6m_rate_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.7663 | 0.7471 | 0.5541 | 0.7624 | -0.0091 |
| `temporal_blocks_6m_rate_25` | 20260612 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.8338 | 0.7037 | 0.6487 | 0.8041 | -0.0081 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.6585 | 0.3937 | 0.3049 | 0.5804 | -0.0074 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.6130 | 0.4035 | 0.2783 | 0.5553 | -0.0098 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.7293 | 0.3602 | 0.3759 | 0.6053 | -0.0052 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9700 | 0.6465 | 0.7725 | 0.8817 | -0.0006 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9925 | 0.5990 | 0.8952 | 0.8772 | -0.0008 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9875 | 0.6143 | 0.8801 | 0.8805 | -0.0006 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.7677 | 0.8173 | 0.4836 | 0.7771 | -0.0094 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.6193 | 0.7868 | 0.4252 | 0.6468 | -0.0112 |
| `temporal_blocks_6m_rate_25` | 20260612 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.5630 | 0.7794 | 0.3954 | 0.5961 | -0.0100 |
| `temporal_blocks_6m_rate_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.5012 | 0.4750 | 0.1924 | 0.4957 | -0.0092 |
| `temporal_blocks_6m_rate_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.4797 | 0.4386 | 0.2004 | 0.4709 | -0.0129 |
| `temporal_blocks_6m_rate_25` | 20260613 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.6829 | 0.3785 | 0.3349 | 0.5883 | -0.0070 |
| `temporal_blocks_6m_rate_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.7630 | 0.8131 | 0.4832 | 0.7725 | -0.0193 |
| `temporal_blocks_6m_rate_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.7590 | 0.7447 | 0.5507 | 0.7561 | -0.0153 |
| `temporal_blocks_6m_rate_25` | 20260613 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.8243 | 0.7029 | 0.6420 | 0.7968 | -0.0154 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.6467 | 0.3975 | 0.2966 | 0.5747 | -0.0131 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.6060 | 0.4073 | 0.2726 | 0.5522 | -0.0130 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.7237 | 0.3645 | 0.3685 | 0.6045 | -0.0060 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9684 | 0.6451 | 0.7730 | 0.8802 | -0.0021 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9916 | 0.5984 | 0.8952 | 0.8764 | -0.0016 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9857 | 0.6142 | 0.8786 | 0.8793 | -0.0018 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.7557 | 0.8155 | 0.4771 | 0.7669 | -0.0196 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.6136 | 0.7853 | 0.4221 | 0.6416 | -0.0164 |
| `temporal_blocks_6m_rate_25` | 20260613 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.5568 | 0.7769 | 0.3924 | 0.5902 | -0.0159 |
| `temporal_blocks_6m_rate_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 1 | 4,673 | 0.4965 | 0.4721 | 0.1917 | 0.4914 | -0.0135 |
| `temporal_blocks_6m_rate_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 2 | 4,710 | 0.4809 | 0.4341 | 0.2030 | 0.4707 | -0.0131 |
| `temporal_blocks_6m_rate_25` | 20260614 | `closest_pr` | `bloom_h` | `test` | 3 | 4,757 | 0.6840 | 0.3787 | 0.3353 | 0.5890 | -0.0063 |
| `temporal_blocks_6m_rate_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 1 | 6,145 | 0.7630 | 0.8183 | 0.4801 | 0.7734 | -0.0183 |
| `temporal_blocks_6m_rate_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 2 | 6,145 | 0.7551 | 0.7486 | 0.5450 | 0.7538 | -0.0177 |
| `temporal_blocks_6m_rate_25` | 20260614 | `closest_pr` | `irc_alert` | `test` | 3 | 6,145 | 0.8231 | 0.7064 | 0.6379 | 0.7968 | -0.0154 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 1 | 4,673 | 0.6514 | 0.3956 | 0.3002 | 0.5768 | -0.0110 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 2 | 4,710 | 0.6118 | 0.4080 | 0.2747 | 0.5563 | -0.0089 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fbeta` | `bloom_h` | `test` | 3 | 4,757 | 0.7214 | 0.3630 | 0.3689 | 0.6024 | -0.0081 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 1 | 6,145 | 0.9684 | 0.6455 | 0.7725 | 0.8803 | -0.0020 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 2 | 6,145 | 0.9904 | 0.6003 | 0.8913 | 0.8765 | -0.0016 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fbeta` | `irc_alert` | `test` | 3 | 6,145 | 0.9834 | 0.6140 | 0.8768 | 0.8777 | -0.0034 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fixed` | `irc_alert` | `test` | 1 | 6,145 | 0.7570 | 0.8210 | 0.4747 | 0.7690 | -0.0176 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fixed` | `irc_alert` | `test` | 2 | 6,145 | 0.6108 | 0.7891 | 0.4182 | 0.6397 | -0.0183 |
| `temporal_blocks_6m_rate_25` | 20260614 | `fixed` | `irc_alert` | `test` | 3 | 6,145 | 0.5547 | 0.7814 | 0.3886 | 0.5889 | -0.0173 |

## Guardrails

- Labels and observed future fuzzy states come from the undegraded canonical sequence/split artifacts.
- Raw predictor degradation is propagated only through the fuzzy state and PIPE input sequence rebuild.
- This experiment measures operational dependence of the current pipeline, not ecological causal importance.
- Chl-a memory is a target-proximal predictor; early-warning claims require a no-current-Chl-a evaluation surface.
- Fuzzy IRC weights are frozen from the current fuzzy manifest, not re-optimized under degradation.
- PIPE/GRU-D model weights, calibrators, and policy thresholds are frozen.
- Degraded outputs are stress-test evidence, not official environmental alerts.

## Outputs

- State metrics: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_full_state_metrics.csv`
- Alert metrics: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_full_alert_metrics.csv`
- Policy metrics: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_full_policy_metrics.csv`
- Summary: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_full_summary.csv`
- Examples: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_full_examples.csv`
- Diagnostics: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_full_diagnostics.csv`
- Backtest rows: `None`
- Manifest: `reports/degradation/controlled_degradation_no_current_chla_wqp_focused_raw_core_full_manifest.json`
