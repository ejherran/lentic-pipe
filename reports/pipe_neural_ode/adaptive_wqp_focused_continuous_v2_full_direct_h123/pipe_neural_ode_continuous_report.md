# PIPE Neural ODE Continuous-Time Training Report v2

Generated at UTC: `2026-06-27T15:13:55.961336+00:00`
Started at UTC: `2026-06-27T15:10:09.246423+00:00`
Status: `completed`

## Scope

This step trains a structurally separate continuous-time Neural ODE v2.
It encodes PIPE history once, then trains direct h-month targets by integrating the latent ODE for the requested `dt`.
Seasonal forcing is evaluated as a continuous function of integration time rather than fixed to one monthly step.
Synthetic smoke mode: `False`.

## Configuration

- History length: `12`
- Forecast horizons: `[1, 2, 3]`
- Context columns: `none`
- History hidden dimension: `128`
- History layers: `1`
- Latent dimension: `96`
- Dynamics hidden dimension: `128`
- Dynamics depth: `3`
- Dropout: `0.0`
- Derivative scale: `0.5`
- State delta scale per month: `0.35`
- ODE method: `rk4`
- ODE step size: `0.25`
- Auxiliary MSE weight: `0.5`
- Auxiliary IRC loss weight: `0.0`
- Checkpoint selection metric: `balanced`
- Output blend selection metric: `balanced`
- Epochs requested: `40`
- Batch size: `2048`
- Learning rate: `0.001`
- Device: `auto`

## Examples

| split | available | sampled/used |
|---|---:|---:|
| `train` | 319,652 | 319,652 |
| `validation` | 18,186 | 18,186 |
| `test` | 20,553 | 20,553 |

## Best Epoch

- Epoch: `40`
- Selection objective: `0.7690`
- Validation loss: `-1.6211`
- Validation RMSE all horizons: `0.1189`
- Validation MAE all horizons: `0.0743`

## Metrics

`horizon_months = 0` is the aggregate over all requested direct horizons.

| split | horizon | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `test` | 0 | `all` | 20,553 | 0.1135 | 0.0702 | -1.4203 | 0.9115 | 0.3661 |
| `test` | 0 | `delta_yF` | 20,553 | 0.1226 | 0.0753 | -1.5196 | 0.8696 | 0.3561 |
| `test` | 0 | `delta_yN` | 20,553 | 0.0975 | 0.0601 | -1.6110 | 0.9337 | 0.3755 |
| `test` | 0 | `delta_yT` | 20,553 | 0.1874 | 0.1167 | -0.2787 | 0.9123 | 0.5965 |
| `test` | 0 | `sigma_F` | 20,553 | 0.0403 | 0.0226 | -2.8272 | 0.9121 | 0.1357 |
| `test` | 0 | `sigma_N` | 20,553 | 0.1436 | 0.0692 | -0.5899 | 0.8925 | 0.3924 |
| `test` | 0 | `sigma_T` | 20,553 | 0.0665 | 0.0435 | -2.2575 | 0.9418 | 0.2619 |
| `test` | 0 | `yF` | 20,553 | 0.1145 | 0.0757 | -1.6349 | 0.8784 | 0.3251 |
| `test` | 0 | `yN` | 20,553 | 0.0860 | 0.0587 | -1.6805 | 0.9373 | 0.3246 |
| `test` | 0 | `yT` | 20,553 | 0.1635 | 0.1105 | -0.3829 | 0.9260 | 0.5269 |
| `test` | 1 | `all` | 7,582 | 0.1110 | 0.0676 | -1.6024 | 0.9194 | 0.3595 |
| `test` | 1 | `delta_yF` | 7,582 | 0.1214 | 0.0760 | -1.6000 | 0.8740 | 0.3376 |
| `test` | 1 | `delta_yN` | 7,582 | 0.0979 | 0.0602 | -1.7752 | 0.9484 | 0.3770 |
| `test` | 1 | `delta_yT` | 7,582 | 0.1944 | 0.1217 | -0.8017 | 0.9192 | 0.5728 |
| `test` | 1 | `sigma_F` | 7,582 | 0.0383 | 0.0205 | -2.8671 | 0.9176 | 0.1343 |
| `test` | 1 | `sigma_N` | 7,582 | 0.1381 | 0.0634 | -0.7830 | 0.9085 | 0.4091 |
| `test` | 1 | `sigma_T` | 7,582 | 0.0631 | 0.0386 | -2.3260 | 0.9465 | 0.2581 |
| `test` | 1 | `yF` | 7,582 | 0.1062 | 0.0693 | -1.7468 | 0.8920 | 0.3116 |
| `test` | 1 | `yN` | 7,582 | 0.0827 | 0.0554 | -1.8677 | 0.9459 | 0.3293 |
| `test` | 1 | `yT` | 7,582 | 0.1569 | 0.1038 | -0.6537 | 0.9230 | 0.5054 |
| `test` | 2 | `all` | 6,826 | 0.1143 | 0.0707 | -1.3162 | 0.9072 | 0.3662 |
| `test` | 2 | `delta_yF` | 6,826 | 0.1225 | 0.0741 | -1.4916 | 0.8654 | 0.3610 |
| `test` | 2 | `delta_yN` | 6,826 | 0.0967 | 0.0599 | -1.6419 | 0.9270 | 0.3776 |
| `test` | 2 | `delta_yT` | 6,826 | 0.1824 | 0.1124 | 0.3434 | 0.9049 | 0.5982 |
| `test` | 2 | `sigma_F` | 6,826 | 0.0409 | 0.0228 | -2.8280 | 0.9099 | 0.1346 |
| `test` | 2 | `sigma_N` | 6,826 | 0.1489 | 0.0731 | -0.4585 | 0.8822 | 0.3843 |
| `test` | 2 | `sigma_T` | 6,826 | 0.0671 | 0.0443 | -2.2586 | 0.9398 | 0.2600 |
| `test` | 2 | `yF` | 6,826 | 0.1168 | 0.0772 | -1.6256 | 0.8739 | 0.3277 |
| `test` | 2 | `yN` | 6,826 | 0.0868 | 0.0594 | -1.5882 | 0.9351 | 0.3208 |
| `test` | 2 | `yT` | 6,826 | 0.1671 | 0.1130 | -0.2971 | 0.9268 | 0.5319 |
| `test` | 3 | `all` | 6,145 | 0.1155 | 0.0729 | -1.3111 | 0.9065 | 0.3741 |
| `test` | 3 | `delta_yF` | 6,145 | 0.1241 | 0.0757 | -1.4514 | 0.8688 | 0.3734 |
| `test` | 3 | `delta_yN` | 6,145 | 0.0978 | 0.0602 | -1.3741 | 0.9230 | 0.3714 |
| `test` | 3 | `delta_yT` | 6,145 | 0.1839 | 0.1152 | -0.3245 | 0.9120 | 0.6240 |
| `test` | 3 | `sigma_F` | 6,145 | 0.0419 | 0.0248 | -2.7771 | 0.9077 | 0.1387 |
| `test` | 3 | `sigma_N` | 6,145 | 0.1442 | 0.0719 | -0.4974 | 0.8843 | 0.3810 |
| `test` | 3 | `sigma_T` | 6,145 | 0.0700 | 0.0487 | -2.1718 | 0.9382 | 0.2685 |
| `test` | 3 | `yF` | 6,145 | 0.1216 | 0.0821 | -1.5072 | 0.8667 | 0.3390 |
| `test` | 3 | `yN` | 6,145 | 0.0889 | 0.0619 | -1.5521 | 0.9290 | 0.3230 |
| `test` | 3 | `yT` | 6,145 | 0.1675 | 0.1160 | -0.1442 | 0.9289 | 0.5480 |
| `train` | 0 | `all` | 319,652 | 0.0914 | 0.0486 | -2.9474 | 0.9434 | 0.2417 |
| `train` | 0 | `delta_yF` | 319,652 | 0.1216 | 0.0677 | -2.0888 | 0.9123 | 0.3294 |
| `train` | 0 | `delta_yN` | 319,652 | 0.0468 | 0.0143 | -4.3112 | 0.9836 | 0.0912 |
| `train` | 0 | `delta_yT` | 319,652 | 0.1955 | 0.1112 | -1.5824 | 0.9181 | 0.5337 |
| `train` | 0 | `sigma_F` | 319,652 | 0.0377 | 0.0187 | -3.0912 | 0.9167 | 0.1099 |
| `train` | 0 | `sigma_N` | 319,652 | 0.0548 | 0.0119 | -4.3145 | 0.9827 | 0.0959 |
| `train` | 0 | `sigma_T` | 319,652 | 0.0527 | 0.0301 | -2.9487 | 0.9307 | 0.1521 |
| `train` | 0 | `yF` | 319,652 | 0.1071 | 0.0670 | -2.1511 | 0.9243 | 0.3003 |
| `train` | 0 | `yN` | 319,652 | 0.0412 | 0.0134 | -4.3355 | 0.9839 | 0.0819 |
| `train` | 0 | `yT` | 319,652 | 0.1651 | 0.1033 | -1.7029 | 0.9383 | 0.4805 |
| `train` | 1 | `all` | 112,470 | 0.0911 | 0.0478 | -3.0145 | 0.9508 | 0.2409 |
| `train` | 1 | `delta_yF` | 112,470 | 0.1218 | 0.0687 | -2.1873 | 0.9256 | 0.3173 |
| `train` | 1 | `delta_yN` | 112,470 | 0.0465 | 0.0139 | -4.3424 | 0.9877 | 0.0918 |
| `train` | 1 | `delta_yT` | 112,470 | 0.2075 | 0.1198 | -1.7018 | 0.9389 | 0.5451 |
| `train` | 1 | `sigma_F` | 112,470 | 0.0366 | 0.0171 | -3.1388 | 0.9254 | 0.1107 |
| `train` | 1 | `sigma_N` | 112,470 | 0.0537 | 0.0112 | -4.3425 | 0.9863 | 0.1004 |
| `train` | 1 | `sigma_T` | 112,470 | 0.0517 | 0.0276 | -3.0160 | 0.9350 | 0.1547 |
| `train` | 1 | `yF` | 112,470 | 0.1027 | 0.0621 | -2.2294 | 0.9264 | 0.2879 |
| `train` | 1 | `yN` | 112,470 | 0.0396 | 0.0125 | -4.3629 | 0.9871 | 0.0832 |
| `train` | 1 | `yT` | 112,470 | 0.1596 | 0.0972 | -1.8088 | 0.9450 | 0.4769 |
| `train` | 2 | `all` | 106,375 | 0.0910 | 0.0485 | -2.9367 | 0.9400 | 0.2402 |
| `train` | 2 | `delta_yF` | 106,375 | 0.1215 | 0.0673 | -2.0490 | 0.9037 | 0.3322 |
| `train` | 2 | `delta_yN` | 106,375 | 0.0470 | 0.0144 | -4.3098 | 0.9823 | 0.0915 |
| `train` | 2 | `delta_yT` | 106,375 | 0.1888 | 0.1071 | -1.5474 | 0.9063 | 0.5228 |
| `train` | 2 | `sigma_F` | 106,375 | 0.0381 | 0.0191 | -3.0805 | 0.9132 | 0.1089 |
| `train` | 2 | `sigma_N` | 106,375 | 0.0549 | 0.0120 | -4.3219 | 0.9820 | 0.0940 |
| `train` | 2 | `sigma_T` | 106,375 | 0.0529 | 0.0305 | -2.9469 | 0.9301 | 0.1509 |
| `train` | 2 | `yF` | 106,375 | 0.1084 | 0.0679 | -2.1377 | 0.9223 | 0.3009 |
| `train` | 2 | `yN` | 106,375 | 0.0414 | 0.0134 | -4.3409 | 0.9834 | 0.0810 |
| `train` | 2 | `yT` | 106,375 | 0.1661 | 0.1044 | -1.6964 | 0.9371 | 0.4798 |
| `train` | 3 | `all` | 100,807 | 0.0919 | 0.0497 | -2.8838 | 0.9386 | 0.2440 |
| `train` | 3 | `delta_yF` | 100,807 | 0.1213 | 0.0671 | -2.0209 | 0.9066 | 0.3400 |
| `train` | 3 | `delta_yN` | 100,807 | 0.0469 | 0.0147 | -4.2779 | 0.9803 | 0.0901 |
| `train` | 3 | `delta_yT` | 100,807 | 0.1884 | 0.1059 | -1.4860 | 0.9072 | 0.5326 |
| `train` | 3 | `sigma_F` | 100,807 | 0.0384 | 0.0201 | -3.0495 | 0.9107 | 0.1100 |
| `train` | 3 | `sigma_N` | 100,807 | 0.0557 | 0.0126 | -4.2754 | 0.9795 | 0.0929 |
| `train` | 3 | `sigma_T` | 100,807 | 0.0535 | 0.0324 | -2.8756 | 0.9265 | 0.1504 |
| `train` | 3 | `yF` | 100,807 | 0.1106 | 0.0714 | -2.0779 | 0.9241 | 0.3135 |
| `train` | 3 | `yN` | 100,807 | 0.0427 | 0.0144 | -4.2992 | 0.9809 | 0.0814 |
| `train` | 3 | `yT` | 100,807 | 0.1699 | 0.1089 | -1.5917 | 0.9320 | 0.4853 |
| `validation` | 0 | `all` | 18,186 | 0.1189 | 0.0743 | -1.4933 | 0.9052 | 0.3705 |
| `validation` | 0 | `delta_yF` | 18,186 | 0.1254 | 0.0779 | -1.6795 | 0.8712 | 0.3609 |
| `validation` | 0 | `delta_yN` | 18,186 | 0.0945 | 0.0559 | -1.9671 | 0.9436 | 0.3614 |
| `validation` | 0 | `delta_yT` | 18,186 | 0.2066 | 0.1352 | -0.2647 | 0.8843 | 0.6241 |
| `validation` | 0 | `sigma_F` | 18,186 | 0.0533 | 0.0256 | -2.6191 | 0.9033 | 0.1300 |
| `validation` | 0 | `sigma_N` | 18,186 | 0.1358 | 0.0621 | -1.2506 | 0.9268 | 0.4119 |
| `validation` | 0 | `sigma_T` | 18,186 | 0.0780 | 0.0522 | -1.7962 | 0.8893 | 0.2533 |
| `validation` | 0 | `yF` | 18,186 | 0.1119 | 0.0753 | -1.7592 | 0.8863 | 0.3299 |
| `validation` | 0 | `yN` | 18,186 | 0.0859 | 0.0568 | -2.0323 | 0.9442 | 0.3125 |
| `validation` | 0 | `yT` | 18,186 | 0.1789 | 0.1280 | -0.0708 | 0.8972 | 0.5509 |
| `validation` | 1 | `all` | 7,079 | 0.1146 | 0.0704 | -1.6731 | 0.9153 | 0.3673 |
| `validation` | 1 | `delta_yF` | 7,079 | 0.1232 | 0.0775 | -1.7239 | 0.8713 | 0.3401 |
| `validation` | 1 | `delta_yN` | 7,079 | 0.0986 | 0.0576 | -2.1438 | 0.9568 | 0.3698 |
| `validation` | 1 | `delta_yT` | 7,079 | 0.2121 | 0.1394 | -0.4441 | 0.8980 | 0.6114 |
| `validation` | 1 | `sigma_F` | 7,079 | 0.0486 | 0.0224 | -2.7765 | 0.9131 | 0.1287 |
| `validation` | 1 | `sigma_N` | 7,079 | 0.1194 | 0.0525 | -1.6303 | 0.9472 | 0.4291 |
| `validation` | 1 | `sigma_T` | 7,079 | 0.0714 | 0.0446 | -1.8320 | 0.9056 | 0.2534 |
| `validation` | 1 | `yF` | 7,079 | 0.1060 | 0.0694 | -1.8827 | 0.8878 | 0.3121 |
| `validation` | 1 | `yN` | 7,079 | 0.0822 | 0.0529 | -2.2239 | 0.9551 | 0.3222 |
| `validation` | 1 | `yT` | 7,079 | 0.1700 | 0.1172 | -0.4003 | 0.9031 | 0.5386 |
| `validation` | 2 | `all` | 6,038 | 0.1199 | 0.0751 | -1.3883 | 0.8990 | 0.3680 |
| `validation` | 2 | `delta_yF` | 6,038 | 0.1256 | 0.0768 | -1.6753 | 0.8715 | 0.3638 |
| `validation` | 2 | `delta_yN` | 6,038 | 0.0922 | 0.0553 | -1.8360 | 0.9377 | 0.3597 |
| `validation` | 2 | `delta_yT` | 6,038 | 0.2012 | 0.1306 | -0.2503 | 0.8720 | 0.6184 |
| `validation` | 2 | `sigma_F` | 6,038 | 0.0536 | 0.0259 | -2.5796 | 0.8985 | 0.1286 |
| `validation` | 2 | `sigma_N` | 6,038 | 0.1427 | 0.0659 | -1.0450 | 0.9198 | 0.4025 |
| `validation` | 2 | `sigma_T` | 6,038 | 0.0813 | 0.0556 | -1.7050 | 0.8736 | 0.2503 |
| `validation` | 2 | `yF` | 6,038 | 0.1134 | 0.0763 | -1.7150 | 0.8854 | 0.3323 |
| `validation` | 2 | `yN` | 6,038 | 0.0871 | 0.0581 | -1.9504 | 0.9399 | 0.3063 |
| `validation` | 2 | `yT` | 6,038 | 0.1819 | 0.1313 | 0.2619 | 0.8925 | 0.5499 |
| `validation` | 3 | `all` | 5,069 | 0.1233 | 0.0789 | -1.3673 | 0.8983 | 0.3782 |
| `validation` | 3 | `delta_yF` | 5,069 | 0.1283 | 0.0798 | -1.6224 | 0.8708 | 0.3864 |
| `validation` | 3 | `delta_yN` | 5,069 | 0.0914 | 0.0542 | -1.8764 | 0.9323 | 0.3516 |
| `validation` | 3 | `delta_yT` | 5,069 | 0.2050 | 0.1346 | -0.0315 | 0.8797 | 0.6486 |
| `validation` | 3 | `sigma_F` | 5,069 | 0.0590 | 0.0296 | -2.4463 | 0.8954 | 0.1337 |
| `validation` | 3 | `sigma_N` | 5,069 | 0.1484 | 0.0711 | -0.9652 | 0.9067 | 0.3990 |
| `validation` | 3 | `sigma_T` | 5,069 | 0.0826 | 0.0588 | -1.8547 | 0.8852 | 0.2569 |
| `validation` | 3 | `yF` | 5,069 | 0.1178 | 0.0824 | -1.6395 | 0.8854 | 0.3520 |
| `validation` | 3 | `yN` | 5,069 | 0.0895 | 0.0608 | -1.8624 | 0.9343 | 0.3063 |
| `validation` | 3 | `yT` | 5,069 | 0.1874 | 0.1392 | -0.0070 | 0.8947 | 0.5693 |

## Persistence Comparison

| split | horizon | target | Neural ODE v2 RMSE | persistence RMSE | RMSE rel improvement | Neural ODE v2 MAE | persistence MAE | MAE rel improvement |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `test` | 0 | `all` | 0.1135 | 0.1524 | 0.2549 | 0.0702 | 0.0901 | 0.2206 |
| `train` | 0 | `all` | 0.0914 | 0.1275 | 0.2837 | 0.0486 | 0.0654 | 0.2564 |
| `validation` | 0 | `all` | 0.1189 | 0.1590 | 0.2522 | 0.0743 | 0.0941 | 0.2098 |

## Outputs

- Model: `models/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_model_v2.pt`
- Checkpoint: `models/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_checkpoint_v2.pt`
- Metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_metrics.csv`
- Persistence metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_persistence_comparison.csv`
- Output blend weights: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_output_blend_weights.csv`
- Output blend search: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_output_blend_search.csv`
- Training curve: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_training_curve.csv`
- Prediction examples: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_prediction_examples.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_manifest.json`
