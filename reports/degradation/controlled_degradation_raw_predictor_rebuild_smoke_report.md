# Raw-Predictor Recomputed PIPE/GRU-D Degradation Report

Generated at UTC: `2026-06-12T18:14:18.830876+00:00`
Started at UTC: `2026-06-12T18:11:48.058316+00:00`

## Scope

This report degrades raw monthly panel predictors, rebuilds the deterministic fuzzy state, rebuilds PIPE sequence inputs, and recomputes frozen PIPE/GRU-D rollouts.
Observed labels and future states remain fixed from the undegraded canonical sequence/split surfaces.
Fuzzy IRC weights are frozen; no fuzzy weights, PIPE weights, calibrators, or alert thresholds are refit.

## Configuration

- Config: `configs/degradation_scenarios.yaml`
- Panel: `data/panel/panel_monthly_v0.parquet`
- Canonical sequences/labels: `data/pipe_grud/pipe_sequence_dataset_v0.parquet`
- Fuzzy manifest for frozen weights: `reports/anfis/fuzzy_manifest.json`
- Fuzzy weight source: `fuzzy_manifest`
- Scenario set: `raw_predictor_rebuild_smoke`
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
| `ablate_chlorophyll_memory` | `x_irc_basis` | 5,490 | 4,857 | 0.4024 | 0.5256 | 0.1232 | 0.2236 |
| `ablate_chlorophyll_memory` | `x_yF` | 5,490 | 0 | 0.5443 | 0.5443 | 0.0000 | 0.0000 |
| `ablate_chlorophyll_memory` | `x_yN` | 5,490 | 0 | 0.5017 | 0.5017 | 0.0000 | 0.0000 |
| `ablate_chlorophyll_memory` | `x_yT` | 5,490 | 4,857 | 0.3642 | 0.5490 | 0.1848 | 0.3354 |
| `ablate_nutrients` | `x_irc_basis` | 5,490 | 2,097 | 0.4024 | 0.4021 | -0.0003 | 0.0180 |
| `ablate_nutrients` | `x_yF` | 5,490 | 0 | 0.5443 | 0.5443 | 0.0000 | 0.0000 |
| `ablate_nutrients` | `x_yN` | 5,490 | 2,097 | 0.5017 | 0.5000 | -0.0017 | 0.1078 |
| `ablate_nutrients` | `x_yT` | 5,490 | 0 | 0.3642 | 0.3642 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_irc_basis` | 5,490 | 0 | 0.4024 | 0.4024 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_yF` | 5,490 | 0 | 0.5443 | 0.5443 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_yN` | 5,490 | 0 | 0.5017 | 0.5017 | 0.0000 | 0.0000 |
| `control_rebuild` | `x_yT` | 5,490 | 0 | 0.3642 | 0.3642 | 0.0000 | 0.0000 |

## Future Availability

| horizon | eligible origins | origins with observed future | selected origins | policy |
|---:|---:|---:|---:|---|
| 1 | 17,420 | 17,420 | 512 | `complete_horizons` |
| 2 | 17,420 | 15,268 | 512 | `complete_horizons` |
| 3 | 17,420 | 13,685 | 512 | `complete_horizons` |

## Scenario Summary

| scenario | status | seed | raw cells | sequence cells | selected-window cells | rollout rows | policy metric rows |
|---|---|---:|---:|---:|---:|---:|---:|
| `ablate_chlorophyll_memory` | `evaluated` | NA | 21,795,816 | 4,186,753 | 12,955 | 1,536 | 72 |
| `ablate_nutrients` | `evaluated` | NA | 6,503,188 | 1,049,437 | 6,230 | 1,536 | 72 |
| `control_observed` | `evaluated` | NA | 0 | 0 | 0 | 1,536 | 72 |

## State Metrics

| scenario | seed | split | horizon | target | rows | RMSE | persistence RMSE | RMSE improvement | MAE |
|---|---:|---|---:|---|---:|---:|---:|---:|---:|
| `ablate_chlorophyll_memory` | NA | `test` | 1 | `all` | 4,608 | 0.2133 | 0.2380 | 0.1039 | 0.1167 |
| `ablate_chlorophyll_memory` | NA | `test` | 1 | `irc1` | 512 | 0.2586 | 0.2770 | 0.0664 | 0.2293 |
| `ablate_chlorophyll_memory` | NA | `test` | 2 | `all` | 4,608 | 0.2133 | 0.2401 | 0.1118 | 0.1189 |
| `ablate_chlorophyll_memory` | NA | `test` | 2 | `irc1` | 512 | 0.2554 | 0.2891 | 0.1165 | 0.2286 |
| `ablate_chlorophyll_memory` | NA | `test` | 3 | `all` | 4,608 | 0.2134 | 0.2476 | 0.1381 | 0.1219 |
| `ablate_chlorophyll_memory` | NA | `test` | 3 | `irc1` | 512 | 0.2528 | 0.3003 | 0.1581 | 0.2238 |
| `ablate_nutrients` | NA | `test` | 1 | `all` | 4,608 | 0.1763 | 0.2156 | 0.1824 | 0.0864 |
| `ablate_nutrients` | NA | `test` | 1 | `irc1` | 512 | 0.1455 | 0.1692 | 0.1405 | 0.0994 |
| `ablate_nutrients` | NA | `test` | 2 | `all` | 4,608 | 0.1824 | 0.2128 | 0.1429 | 0.0915 |
| `ablate_nutrients` | NA | `test` | 2 | `irc1` | 512 | 0.1650 | 0.2046 | 0.1932 | 0.1183 |
| `ablate_nutrients` | NA | `test` | 3 | `all` | 4,608 | 0.1829 | 0.2199 | 0.1685 | 0.0937 |
| `ablate_nutrients` | NA | `test` | 3 | `irc1` | 512 | 0.1615 | 0.2200 | 0.2663 | 0.1178 |
| `control_observed` | NA | `test` | 1 | `all` | 4,608 | 0.1281 | 0.1838 | 0.3027 | 0.0589 |
| `control_observed` | NA | `test` | 1 | `irc1` | 512 | 0.1453 | 0.1686 | 0.1381 | 0.0962 |
| `control_observed` | NA | `test` | 2 | `all` | 4,608 | 0.1392 | 0.1795 | 0.2248 | 0.0658 |
| `control_observed` | NA | `test` | 2 | `irc1` | 512 | 0.1648 | 0.2035 | 0.1904 | 0.1166 |
| `control_observed` | NA | `test` | 3 | `all` | 4,608 | 0.1444 | 0.1898 | 0.2392 | 0.0712 |
| `control_observed` | NA | `test` | 3 | `irc1` | 512 | 0.1647 | 0.2184 | 0.2459 | 0.1199 |

## Alert Metrics

| scenario | seed | event | split | horizon | rows | positive rate | predicted positive rate | PR-AUC | Brier | recall |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| `ablate_chlorophyll_memory` | NA | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0304 | 0.2444 | 0.1112 | 0.0833 |
| `ablate_chlorophyll_memory` | NA | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0174 | 0.2773 | 0.1110 | 0.0645 |
| `ablate_chlorophyll_memory` | NA | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0086 | 0.2624 | 0.1094 | 0.0323 |
| `ablate_chlorophyll_memory` | NA | `irc_alert` | `test` | 1 | 512 | 0.3379 | 0.3203 | 0.4306 | 0.3223 | 0.4971 |
| `ablate_chlorophyll_memory` | NA | `irc_alert` | `test` | 2 | 512 | 0.3477 | 0.2266 | 0.4790 | 0.2773 | 0.4270 |
| `ablate_chlorophyll_memory` | NA | `irc_alert` | `test` | 3 | 512 | 0.3535 | 0.2188 | 0.5013 | 0.2676 | 0.4309 |
| `ablate_nutrients` | NA | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0694 | 0.7348 | 0.0704 | 0.4167 |
| `ablate_nutrients` | NA | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0609 | 0.6783 | 0.0819 | 0.3548 |
| `ablate_nutrients` | NA | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0535 | 0.6265 | 0.0832 | 0.3387 |
| `ablate_nutrients` | NA | `irc_alert` | `test` | 1 | 512 | 0.3379 | 0.2969 | 0.7110 | 0.1348 | 0.7399 |
| `ablate_nutrients` | NA | `irc_alert` | `test` | 2 | 512 | 0.3477 | 0.2910 | 0.6492 | 0.1738 | 0.6685 |
| `ablate_nutrients` | NA | `irc_alert` | `test` | 3 | 512 | 0.3535 | 0.2910 | 0.6671 | 0.1680 | 0.6740 |
| `control_observed` | NA | `bloom_h` | `test` | 1 | 461 | 0.1302 | 0.0824 | 0.7159 | 0.0701 | 0.4667 |
| `control_observed` | NA | `bloom_h` | `test` | 2 | 460 | 0.1348 | 0.0565 | 0.6988 | 0.0811 | 0.3548 |
| `control_observed` | NA | `bloom_h` | `test` | 3 | 467 | 0.1328 | 0.0493 | 0.6033 | 0.0844 | 0.2742 |
| `control_observed` | NA | `irc_alert` | `test` | 1 | 512 | 0.3379 | 0.2871 | 0.7003 | 0.1406 | 0.7168 |
| `control_observed` | NA | `irc_alert` | `test` | 2 | 512 | 0.3477 | 0.2637 | 0.6658 | 0.1660 | 0.6404 |
| `control_observed` | NA | `irc_alert` | `test` | 3 | 512 | 0.3535 | 0.2559 | 0.6417 | 0.1836 | 0.6022 |

## Policy Metrics

| scenario | seed | policy | event | split | horizon | rows | recall | precision | alert rate | F2 | delta F2 |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `ablate_chlorophyll_memory` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.1667 | 0.3448 | 0.0629 | 0.1859 | -0.5004 |
| `ablate_chlorophyll_memory` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.2903 | 0.4000 | 0.0978 | 0.3072 | -0.4028 |
| `ablate_chlorophyll_memory` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.2903 | 0.3103 | 0.1242 | 0.2941 | -0.3784 |
| `ablate_chlorophyll_memory` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.4971 | 0.5244 | 0.3203 | 0.5023 | -0.2366 |
| `ablate_chlorophyll_memory` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.4270 | 0.6552 | 0.2266 | 0.4589 | -0.2140 |
| `ablate_chlorophyll_memory` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.4309 | 0.6964 | 0.2188 | 0.4665 | -0.1709 |
| `ablate_chlorophyll_memory` | NA | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.3500 | 0.2877 | 0.1584 | 0.3355 | -0.4204 |
| `ablate_chlorophyll_memory` | NA | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.4677 | 0.3152 | 0.2000 | 0.4265 | -0.2819 |
| `ablate_chlorophyll_memory` | NA | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.8871 | 0.1682 | 0.7002 | 0.4783 | -0.2215 |
| `ablate_chlorophyll_memory` | NA | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.4971 | 0.5244 | 0.3203 | 0.5023 | -0.2366 |
| `ablate_chlorophyll_memory` | NA | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.4270 | 0.6552 | 0.2266 | 0.4589 | -0.2140 |
| `ablate_chlorophyll_memory` | NA | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.4309 | 0.6964 | 0.2188 | 0.4665 | -0.1709 |
| `ablate_chlorophyll_memory` | NA | `fixed` | `bloom_h` | `test` | 1 | 461 | 0.0833 | 0.3571 | 0.0304 | 0.0984 | -0.4052 |
| `ablate_chlorophyll_memory` | NA | `fixed` | `bloom_h` | `test` | 2 | 460 | 0.0645 | 0.5000 | 0.0174 | 0.0781 | -0.3233 |
| `ablate_chlorophyll_memory` | NA | `fixed` | `bloom_h` | `test` | 3 | 467 | 0.0323 | 0.5000 | 0.0086 | 0.0397 | -0.2740 |
| `ablate_chlorophyll_memory` | NA | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.4971 | 0.5244 | 0.3203 | 0.5023 | -0.2366 |
| `ablate_chlorophyll_memory` | NA | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.4270 | 0.6552 | 0.2266 | 0.4589 | -0.2140 |
| `ablate_chlorophyll_memory` | NA | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.4309 | 0.6964 | 0.2188 | 0.4665 | -0.1709 |
| `ablate_nutrients` | NA | `closest_pr` | `bloom_h` | `test` | 1 | 461 | 0.6833 | 0.6212 | 0.1432 | 0.6699 | -0.0163 |
| `ablate_nutrients` | NA | `closest_pr` | `bloom_h` | `test` | 2 | 460 | 0.7903 | 0.5568 | 0.1913 | 0.7292 | 0.0192 |
| `ablate_nutrients` | NA | `closest_pr` | `bloom_h` | `test` | 3 | 467 | 0.7581 | 0.4700 | 0.2141 | 0.6753 | 0.0028 |
| `ablate_nutrients` | NA | `closest_pr` | `irc_alert` | `test` | 1 | 512 | 0.7399 | 0.8421 | 0.2969 | 0.7583 | 0.0193 |
| `ablate_nutrients` | NA | `closest_pr` | `irc_alert` | `test` | 2 | 512 | 0.6685 | 0.7987 | 0.2910 | 0.6911 | 0.0181 |
| `ablate_nutrients` | NA | `closest_pr` | `irc_alert` | `test` | 3 | 512 | 0.6740 | 0.8188 | 0.2910 | 0.6987 | 0.0613 |
| `ablate_nutrients` | NA | `fbeta` | `bloom_h` | `test` | 1 | 461 | 0.8500 | 0.4904 | 0.2256 | 0.7413 | -0.0145 |
| `ablate_nutrients` | NA | `fbeta` | `bloom_h` | `test` | 2 | 460 | 0.8387 | 0.4160 | 0.2717 | 0.6971 | -0.0113 |
| `ablate_nutrients` | NA | `fbeta` | `bloom_h` | `test` | 3 | 467 | 0.9194 | 0.3476 | 0.3512 | 0.6917 | -0.0080 |
| `ablate_nutrients` | NA | `fbeta` | `irc_alert` | `test` | 1 | 512 | 0.7399 | 0.8421 | 0.2969 | 0.7583 | 0.0193 |
| `ablate_nutrients` | NA | `fbeta` | `irc_alert` | `test` | 2 | 512 | 0.6685 | 0.7987 | 0.2910 | 0.6911 | 0.0181 |
| `ablate_nutrients` | NA | `fbeta` | `irc_alert` | `test` | 3 | 512 | 0.6740 | 0.8188 | 0.2910 | 0.6987 | 0.0613 |
| `ablate_nutrients` | NA | `fixed` | `bloom_h` | `test` | 1 | 461 | 0.4167 | 0.7812 | 0.0694 | 0.4596 | -0.0440 |
| `ablate_nutrients` | NA | `fixed` | `bloom_h` | `test` | 2 | 460 | 0.3548 | 0.7857 | 0.0609 | 0.3986 | -0.0029 |
| `ablate_nutrients` | NA | `fixed` | `bloom_h` | `test` | 3 | 467 | 0.3387 | 0.8400 | 0.0535 | 0.3846 | 0.0710 |
| `ablate_nutrients` | NA | `fixed` | `irc_alert` | `test` | 1 | 512 | 0.7399 | 0.8421 | 0.2969 | 0.7583 | 0.0193 |
| `ablate_nutrients` | NA | `fixed` | `irc_alert` | `test` | 2 | 512 | 0.6685 | 0.7987 | 0.2910 | 0.6911 | 0.0181 |
| `ablate_nutrients` | NA | `fixed` | `irc_alert` | `test` | 3 | 512 | 0.6740 | 0.8188 | 0.2910 | 0.6987 | 0.0613 |
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

## Guardrails

- Labels and observed future fuzzy states come from the undegraded canonical sequence/split artifacts.
- Raw predictor degradation is propagated only through the fuzzy state and PIPE input sequence rebuild.
- This experiment measures operational dependence of the current pipeline, not ecological causal importance.
- Chl-a memory is a target-proximal predictor; early-warning claims require a no-current-Chl-a evaluation surface.
- Fuzzy IRC weights are frozen from the current fuzzy manifest, not re-optimized under degradation.
- PIPE/GRU-D model weights, calibrators, and policy thresholds are frozen.
- Degraded outputs are stress-test evidence, not official environmental alerts.

## Outputs

- State metrics: `reports/degradation/controlled_degradation_raw_predictor_rebuild_smoke_state_metrics.csv`
- Alert metrics: `reports/degradation/controlled_degradation_raw_predictor_rebuild_smoke_alert_metrics.csv`
- Policy metrics: `reports/degradation/controlled_degradation_raw_predictor_rebuild_smoke_policy_metrics.csv`
- Summary: `reports/degradation/controlled_degradation_raw_predictor_rebuild_smoke_summary.csv`
- Examples: `reports/degradation/controlled_degradation_raw_predictor_rebuild_smoke_examples.csv`
- Diagnostics: `reports/degradation/controlled_degradation_raw_predictor_rebuild_smoke_diagnostics.csv`
- Backtest rows: `None`
- Manifest: `reports/degradation/controlled_degradation_raw_predictor_rebuild_smoke_manifest.json`
