# Expert Fuzzy / ANFIS Fallback Report v0

Generated at UTC: `2026-05-16T21:36:54.706380+00:00`

## Scope

This is `expert_fuzzy_v0`: a deterministic expert fuzzy fallback for PIPE Layer 1.
It produces pseudo-labels and S(t), but it is not an adaptive ANFIS training result.

## IRC1 Weights

- alpha/yN: `0.5`
- beta/(1-yF): `0.5`
- gamma/yT: `2.0`
- mode: `train-grid`

## State Vector

- rows: `3,386,676`
- sites: `248,284`
- output: `data/fuzzy/state_vector_v0.parquet`

## Module Evidence

| source | rows | evidence N | evidence F | evidence T | evidence T no Chl-a | high sigma N | high sigma F | high sigma T |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `aquamatch_chla` | 1,755,072 | 0.0000 | 0.0000 | 0.5500 | 0.0000 | 1.0000 | 1.0000 | 0.0000 |
| `lakebed_us_cse` | 4,932 | 0.7851 | 0.4717 | 0.8943 | 0.9856 | 0.1721 | 0.0193 | 0.0063 |
| `wqp` | 1,626,672 | 0.2347 | 0.4507 | 0.5189 | 0.5215 | 0.6181 | 0.0796 | 0.2588 |

## Current-Month Scores vs Current Chl-a Risk

| score | source | rows | Pearson | Spearman | RMSE | MAE |
|---|---|---:|---:|---:|---:|---:|
| `irc1` | `all` | 2,599,588 | 0.9640 | 0.9365 | 0.1625 | 0.1400 |
| `irc1` | `aquamatch_chla` | 1,755,072 | 1.0000 | 1.0000 | 0.1411 | 0.1312 |
| `irc1` | `lakebed_us_cse` | 4,042 | 0.8653 | 0.8182 | 0.1989 | 0.1450 |
| `irc1` | `wqp` | 840,474 | 0.9029 | 0.8821 | 0.1996 | 0.1583 |
| `irc1_no_chla` | `all` | 2,599,588 | 0.2114 | 0.2375 | 0.4202 | 0.3796 |
| `irc1_no_chla` | `aquamatch_chla` | 1,755,072 | NA | NA | 0.4234 | 0.3936 |
| `irc1_no_chla` | `lakebed_us_cse` | 4,042 | 0.4287 | 0.5093 | 0.3398 | 0.2343 |
| `irc1_no_chla` | `wqp` | 840,474 | 0.3431 | 0.3811 | 0.4137 | 0.3508 |

## Raw Target Metrics By Horizon, Split, And Source

| score | source | horizon | split | rows | PR-AUC | ROC-AUC | Brier | recall | macro-F1 | MAE risk |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `irc1` | `all` | 1 | `test` | 121,540 | 0.6487 | 0.9093 | 0.1481 | 0.8893 | 0.7009 | 0.2057 |
| `irc1` | `aquamatch_chla` | 1 | `test` | 66,226 | 0.5805 | 0.9076 | 0.1323 | 0.8694 | 0.7078 | 0.2081 |
| `irc1` | `lakebed_us_cse` | 1 | `test` | 163 | 0.3404 | 0.8009 | 0.1591 | 0.5909 | 0.6528 | 0.2295 |
| `irc1` | `wqp` | 1 | `test` | 55,151 | 0.6944 | 0.9078 | 0.1671 | 0.9073 | 0.6895 | 0.2027 |
| `irc1` | `all` | 1 | `train` | 1,336,605 | 0.6285 | 0.8975 | 0.1560 | 0.8844 | 0.7056 | 0.2177 |
| `irc1` | `all` | 1 | `validation` | 163,110 | 0.5807 | 0.8965 | 0.1504 | 0.8697 | 0.6871 | 0.2164 |
| `irc1` | `aquamatch_chla` | 1 | `validation` | 110,443 | 0.5384 | 0.8975 | 0.1381 | 0.8527 | 0.6911 | 0.2147 |
| `irc1` | `lakebed_us_cse` | 1 | `validation` | 445 | 0.2449 | 0.7582 | 0.1650 | 0.5636 | 0.6074 | 0.2364 |
| `irc1` | `wqp` | 1 | `validation` | 52,222 | 0.6383 | 0.8923 | 0.1763 | 0.8980 | 0.6748 | 0.2196 |
| `irc1` | `all` | 2 | `test` | 115,691 | 0.5802 | 0.8729 | 0.1534 | 0.8216 | 0.6909 | 0.2240 |
| `irc1` | `aquamatch_chla` | 2 | `test` | 65,117 | 0.4999 | 0.8738 | 0.1385 | 0.8049 | 0.6917 | 0.2258 |
| `irc1` | `lakebed_us_cse` | 2 | `test` | 151 | 0.3098 | 0.7783 | 0.1604 | 0.5789 | 0.6453 | 0.2464 |
| `irc1` | `wqp` | 2 | `test` | 50,423 | 0.6337 | 0.8654 | 0.1727 | 0.8366 | 0.6842 | 0.2216 |
| `irc1` | `all` | 2 | `train` | 1,294,854 | 0.5524 | 0.8592 | 0.1628 | 0.8189 | 0.6881 | 0.2397 |
| `irc1` | `all` | 2 | `validation` | 154,216 | 0.5039 | 0.8575 | 0.1547 | 0.7972 | 0.6720 | 0.2344 |
| `irc1` | `aquamatch_chla` | 2 | `validation` | 106,736 | 0.4543 | 0.8584 | 0.1432 | 0.7817 | 0.6741 | 0.2325 |
| `irc1` | `lakebed_us_cse` | 2 | `validation` | 430 | 0.1994 | 0.6884 | 0.1831 | 0.4545 | 0.5653 | 0.2708 |
| `irc1` | `wqp` | 2 | `validation` | 47,050 | 0.5689 | 0.8492 | 0.1803 | 0.8241 | 0.6619 | 0.2381 |
| `irc1` | `all` | 3 | `test` | 99,670 | 0.5430 | 0.8496 | 0.1587 | 0.7851 | 0.6796 | 0.2382 |
| `irc1` | `aquamatch_chla` | 3 | `test` | 55,831 | 0.4586 | 0.8532 | 0.1430 | 0.7725 | 0.6792 | 0.2381 |
| `irc1` | `lakebed_us_cse` | 3 | `test` | 143 | 0.3125 | 0.7969 | 0.1485 | 0.5294 | 0.6308 | 0.2532 |
| `irc1` | `wqp` | 3 | `test` | 43,696 | 0.5984 | 0.8397 | 0.1788 | 0.7963 | 0.6741 | 0.2384 |
| `irc1` | `all` | 3 | `train` | 1,189,253 | 0.5052 | 0.8316 | 0.1702 | 0.7782 | 0.6720 | 0.2553 |
| `irc1` | `all` | 3 | `validation` | 136,038 | 0.4652 | 0.8341 | 0.1574 | 0.7567 | 0.6623 | 0.2466 |
| `irc1` | `aquamatch_chla` | 3 | `validation` | 94,463 | 0.4109 | 0.8365 | 0.1463 | 0.7441 | 0.6616 | 0.2443 |
| `irc1` | `lakebed_us_cse` | 3 | `validation` | 421 | 0.1658 | 0.6686 | 0.1739 | 0.2745 | 0.5156 | 0.2722 |
| `irc1` | `wqp` | 3 | `validation` | 41,154 | 0.5356 | 0.8220 | 0.1827 | 0.7794 | 0.6568 | 0.2518 |
| `irc1_no_chla` | `all` | 1 | `test` | 121,540 | 0.2768 | 0.6687 | 0.2576 | 0.9231 | 0.3252 | 0.3724 |
| `irc1_no_chla` | `aquamatch_chla` | 1 | `test` | 66,226 | 0.1175 | 0.5000 | 0.2500 | 1.0000 | 0.1052 | 0.4008 |
| `irc1_no_chla` | `lakebed_us_cse` | 1 | `test` | 163 | 0.1312 | 0.4152 | 0.2550 | 0.1364 | 0.3933 | 0.3546 |
| `irc1_no_chla` | `wqp` | 1 | `test` | 55,151 | 0.3853 | 0.7384 | 0.2668 | 0.8581 | 0.5395 | 0.3383 |
| `irc1_no_chla` | `all` | 1 | `train` | 1,336,605 | 0.2544 | 0.6272 | 0.2545 | 0.9392 | 0.2725 | 0.3739 |
| `irc1_no_chla` | `all` | 1 | `validation` | 163,110 | 0.2233 | 0.6179 | 0.2597 | 0.9378 | 0.2504 | 0.3804 |
| `irc1_no_chla` | `aquamatch_chla` | 1 | `validation` | 110,443 | 0.1121 | 0.5000 | 0.2500 | 1.0000 | 0.1008 | 0.3959 |
| `irc1_no_chla` | `lakebed_us_cse` | 1 | `validation` | 445 | 0.1350 | 0.5407 | 0.2152 | 0.2545 | 0.4904 | 0.3085 |
| `irc1_no_chla` | `wqp` | 1 | `validation` | 52,222 | 0.3660 | 0.7198 | 0.2807 | 0.8471 | 0.5012 | 0.3482 |
| `irc1_no_chla` | `all` | 2 | `test` | 115,691 | 0.2598 | 0.6428 | 0.2559 | 0.8864 | 0.3210 | 0.3750 |
| `irc1_no_chla` | `aquamatch_chla` | 2 | `test` | 65,117 | 0.1196 | 0.5000 | 0.2500 | 1.0000 | 0.1068 | 0.4005 |
| `irc1_no_chla` | `lakebed_us_cse` | 2 | `test` | 151 | 0.1215 | 0.3975 | 0.2504 | 0.1053 | 0.3863 | 0.3548 |
| `irc1_no_chla` | `wqp` | 2 | `test` | 50,423 | 0.3568 | 0.6987 | 0.2635 | 0.7893 | 0.5443 | 0.3423 |
| `irc1_no_chla` | `all` | 2 | `train` | 1,294,854 | 0.2402 | 0.6108 | 0.2538 | 0.9195 | 0.2654 | 0.3773 |
| `irc1_no_chla` | `all` | 2 | `validation` | 154,216 | 0.2050 | 0.6029 | 0.2578 | 0.9191 | 0.2475 | 0.3826 |
| `irc1_no_chla` | `aquamatch_chla` | 2 | `validation` | 106,736 | 0.1125 | 0.5000 | 0.2500 | 1.0000 | 0.1012 | 0.3978 |
| `irc1_no_chla` | `lakebed_us_cse` | 2 | `validation` | 430 | 0.1238 | 0.5068 | 0.2293 | 0.2000 | 0.4651 | 0.3269 |
| `irc1_no_chla` | `wqp` | 2 | `validation` | 47,050 | 0.3272 | 0.6902 | 0.2757 | 0.7968 | 0.5085 | 0.3486 |
| `irc1_no_chla` | `all` | 3 | `test` | 99,670 | 0.2431 | 0.6204 | 0.2576 | 0.8586 | 0.3177 | 0.3794 |
| `irc1_no_chla` | `aquamatch_chla` | 3 | `test` | 55,831 | 0.1198 | 0.5000 | 0.2500 | 1.0000 | 0.1070 | 0.4003 |
| `irc1_no_chla` | `lakebed_us_cse` | 3 | `test` | 143 | 0.1087 | 0.4255 | 0.2328 | 0.0588 | 0.3822 | 0.3481 |
| `irc1_no_chla` | `wqp` | 3 | `test` | 43,696 | 0.3276 | 0.6626 | 0.2674 | 0.7411 | 0.5327 | 0.3528 |
| `irc1_no_chla` | `all` | 3 | `train` | 1,189,253 | 0.2237 | 0.5942 | 0.2550 | 0.9003 | 0.2607 | 0.3802 |
| `irc1_no_chla` | `all` | 3 | `validation` | 136,038 | 0.1967 | 0.5883 | 0.2570 | 0.8950 | 0.2465 | 0.3849 |
| `irc1_no_chla` | `aquamatch_chla` | 3 | `validation` | 94,463 | 0.1106 | 0.5000 | 0.2500 | 1.0000 | 0.0996 | 0.3984 |
| `irc1_no_chla` | `lakebed_us_cse` | 3 | `validation` | 421 | 0.1169 | 0.5088 | 0.2161 | 0.0784 | 0.4325 | 0.3297 |
| `irc1_no_chla` | `wqp` | 3 | `validation` | 41,154 | 0.3106 | 0.6585 | 0.2734 | 0.7414 | 0.5085 | 0.3545 |

## Calibrated Target Metrics

| score | horizon | split | rows | threshold | PR-AUC | ROC-AUC | Brier | recall | macro-F1 |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `irc1` | 1 | `test` | 121,540 | 0.3000 | 0.6386 | 0.9096 | 0.0697 | 0.6788 | 0.8007 |
| `irc1` | 1 | `validation` | 163,110 | 0.3000 | 0.5737 | 0.8973 | 0.0699 | 0.6436 | 0.7792 |
| `irc1` | 2 | `test` | 115,691 | 0.3180 | 0.5712 | 0.8734 | 0.0836 | 0.5935 | 0.7595 |
| `irc1` | 2 | `validation` | 154,216 | 0.3180 | 0.4976 | 0.8583 | 0.0803 | 0.5587 | 0.7396 |
| `irc1` | 3 | `test` | 99,670 | 0.3000 | 0.5331 | 0.8506 | 0.0899 | 0.5523 | 0.7390 |
| `irc1` | 3 | `validation` | 136,038 | 0.3000 | 0.4585 | 0.8356 | 0.0848 | 0.5087 | 0.7174 |
| `irc1_no_chla` | 1 | `test` | 121,540 | 0.2000 | 0.2728 | 0.6757 | 0.1094 | 0.4089 | 0.6084 |
| `irc1_no_chla` | 1 | `validation` | 163,110 | 0.2000 | 0.2200 | 0.6234 | 0.1042 | 0.2984 | 0.5862 |
| `irc1_no_chla` | 2 | `test` | 115,691 | 0.2000 | 0.2558 | 0.6486 | 0.1163 | 0.3752 | 0.6068 |
| `irc1_no_chla` | 2 | `validation` | 154,216 | 0.2000 | 0.2022 | 0.6069 | 0.1069 | 0.2745 | 0.5842 |
| `irc1_no_chla` | 3 | `test` | 99,670 | 0.2000 | 0.2411 | 0.6267 | 0.1191 | 0.3542 | 0.5977 |
| `irc1_no_chla` | 3 | `validation` | 136,038 | 0.2000 | 0.1940 | 0.5923 | 0.1075 | 0.2578 | 0.5800 |

## Trophic Expert State Counts

| state | rows |
|---|---:|
| `oligotrophic` | 1,079,759 |
| `mesotrophic` | 815,894 |
| `unknown` | 787,088 |
| `eutrophic` | 532,661 |
| `hypereutrophic` | 171,274 |

## Top IRC1 Weight Candidates

| rank | alpha | beta | gamma | train rows | train PR-AUC | train Brier |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.5000 | 0.5000 | 2.0000 | 500,000 | 0.5619 | 0.1625 |
| 2 | 1.0000 | 0.5000 | 2.0000 | 500,000 | 0.5585 | 0.1655 |
| 3 | 0.5000 | 0.5000 | 1.0000 | 500,000 | 0.5573 | 0.1682 |
| 4 | 1.0000 | 1.0000 | 2.0000 | 500,000 | 0.5573 | 0.1682 |
| 5 | 0.5000 | 1.0000 | 2.0000 | 500,000 | 0.5554 | 0.1642 |
| 6 | 1.0000 | 0.5000 | 1.0000 | 500,000 | 0.5490 | 0.1771 |
| 7 | 2.0000 | 1.0000 | 2.0000 | 500,000 | 0.5490 | 0.1771 |
| 8 | 2.0000 | 0.5000 | 2.0000 | 500,000 | 0.5471 | 0.1747 |
| 9 | 0.5000 | 0.5000 | 0.5000 | 500,000 | 0.5422 | 0.1826 |
| 10 | 1.0000 | 1.0000 | 1.0000 | 500,000 | 0.5422 | 0.1826 |

## Outputs

- State vector: `data/fuzzy/state_vector_v0.parquet`
- Metrics: `reports/anfis/irc1_metrics.csv`
- Calibrated metrics: `reports/anfis/irc1_calibrated_metrics.csv`
- Rules: `reports/anfis/rules.csv`
- Memberships: `reports/anfis/memberships.csv`
- Trace examples: `reports/anfis/trace_examples.csv`
- Manifest: `reports/anfis/fuzzy_manifest.json`

## Calibration Artifacts

| score | horizon | calibration | path | sha256 |
|---|---:|---|---|---|
| `irc1` | 1 | `isotonic` | `models/anfis/calibrators/irc1_h1_isotonic.joblib` | `3b260cdb7dcb10fb4ffc72a96a13e387123631be512f777412361f7f3430dacc` |
| `irc1` | 2 | `isotonic` | `models/anfis/calibrators/irc1_h2_isotonic.joblib` | `04346fac63cf670b59bdff37fa0544c7bcfa3e590f7ff48627bea8a5fec7adff` |
| `irc1` | 3 | `isotonic` | `models/anfis/calibrators/irc1_h3_isotonic.joblib` | `389ca9ac472a25ae24fa7a7ed6c796d3b1a1da71da7d0693df131ffab4a39cee` |
| `irc1_no_chla` | 1 | `isotonic` | `models/anfis/calibrators/irc1_no_chla_h1_isotonic.joblib` | `e8974c80ca8f2f6399b9d70ffc8f8d00dc81a09705ccafebfaaed054e20830cd` |
| `irc1_no_chla` | 2 | `isotonic` | `models/anfis/calibrators/irc1_no_chla_h2_isotonic.joblib` | `84862f94b6b696f68f3015f5873499697e0fbeca85fc9da6b670d5c7b46ed13b` |
| `irc1_no_chla` | 3 | `isotonic` | `models/anfis/calibrators/irc1_no_chla_h3_isotonic.joblib` | `3a5f64a026289dc39c6cea30a0658ff32431d82b556468159e5af5b238aa3e0c` |
