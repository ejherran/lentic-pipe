# PIPE Neural ODE Continuous-Time Training Report v2

Generated at UTC: `2026-06-27T14:56:40.975751+00:00`
Started at UTC: `2026-06-27T14:55:59.804304+00:00`
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
- Epochs requested: `20`
- Batch size: `2048`
- Learning rate: `0.001`
- Device: `auto`

## Examples

| split | available | sampled/used |
|---|---:|---:|
| `train` | 319,652 | 50,000 |
| `validation` | 18,186 | 18,186 |
| `test` | 20,553 | 20,553 |

## Best Epoch

- Epoch: `12`
- Selection objective: `0.8700`
- Validation loss: `-1.6320`
- Validation RMSE all horizons: `0.1352`
- Validation MAE all horizons: `0.0837`

## Metrics

`horizon_months = 0` is the aggregate over all requested direct horizons.

| split | horizon | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `test` | 0 | `all` | 20,553 | 0.1285 | 0.0799 | -1.2872 | 0.9420 | 0.7495 |
| `test` | 0 | `delta_yF` | 20,553 | 0.1384 | 0.0858 | -1.1396 | 0.9667 | 0.9327 |
| `test` | 0 | `delta_yN` | 20,553 | 0.1176 | 0.0736 | -1.3233 | 0.8805 | 0.4987 |
| `test` | 0 | `delta_yT` | 20,553 | 0.2138 | 0.1399 | -0.8454 | 0.9661 | 1.1889 |
| `test` | 0 | `sigma_F` | 20,553 | 0.0424 | 0.0225 | -1.8084 | 0.9835 | 0.5601 |
| `test` | 0 | `sigma_N` | 20,553 | 0.1437 | 0.0692 | -1.2524 | 0.9011 | 0.5494 |
| `test` | 0 | `sigma_T` | 20,553 | 0.0779 | 0.0424 | -1.5583 | 0.9553 | 0.6260 |
| `test` | 0 | `yF` | 20,553 | 0.1265 | 0.0808 | -1.2056 | 0.9690 | 0.8740 |
| `test` | 0 | `yN` | 20,553 | 0.0956 | 0.0615 | -1.5138 | 0.8918 | 0.4657 |
| `test` | 0 | `yT` | 20,553 | 0.2003 | 0.1439 | -0.9383 | 0.9642 | 1.0497 |
| `test` | 1 | `all` | 7,582 | 0.1296 | 0.0765 | -1.2183 | 0.9468 | 0.8361 |
| `test` | 1 | `delta_yF` | 7,582 | 0.1557 | 0.0936 | -1.0032 | 0.9662 | 1.0749 |
| `test` | 1 | `delta_yN` | 7,582 | 0.1373 | 0.0849 | -1.0420 | 0.8653 | 0.5838 |
| `test` | 1 | `delta_yT` | 7,582 | 0.2394 | 0.1491 | -0.7158 | 0.9669 | 1.3545 |
| `test` | 1 | `sigma_F` | 7,582 | 0.0395 | 0.0203 | -1.7359 | 0.9858 | 0.6307 |
| `test` | 1 | `sigma_N` | 7,582 | 0.1382 | 0.0634 | -1.3062 | 0.9148 | 0.6192 |
| `test` | 1 | `sigma_T` | 7,582 | 0.0702 | 0.0364 | -1.5145 | 0.9720 | 0.7111 |
| `test` | 1 | `yF` | 7,582 | 0.1160 | 0.0697 | -1.1787 | 0.9752 | 0.9464 |
| `test` | 1 | `yN` | 7,582 | 0.0910 | 0.0557 | -1.5076 | 0.9045 | 0.5175 |
| `test` | 1 | `yT` | 7,582 | 0.1788 | 0.1158 | -0.9609 | 0.9703 | 1.0863 |
| `test` | 2 | `all` | 6,826 | 0.1254 | 0.0789 | -1.3017 | 0.9398 | 0.7260 |
| `test` | 2 | `delta_yF` | 6,826 | 0.1240 | 0.0768 | -1.1879 | 0.9728 | 0.9045 |
| `test` | 2 | `delta_yN` | 6,826 | 0.1078 | 0.0694 | -1.4190 | 0.8878 | 0.4751 |
| `test` | 2 | `delta_yT` | 6,826 | 0.1926 | 0.1264 | -0.8919 | 0.9720 | 1.1608 |
| `test` | 2 | `sigma_F` | 6,826 | 0.0430 | 0.0227 | -1.8324 | 0.9824 | 0.5374 |
| `test` | 2 | `sigma_N` | 6,826 | 0.1490 | 0.0732 | -1.1676 | 0.8888 | 0.5268 |
| `test` | 2 | `sigma_T` | 6,826 | 0.0801 | 0.0439 | -1.5730 | 0.9521 | 0.6026 |
| `test` | 2 | `yF` | 6,826 | 0.1293 | 0.0832 | -1.2129 | 0.9654 | 0.8512 |
| `test` | 2 | `yN` | 6,826 | 0.0968 | 0.0628 | -1.4947 | 0.8822 | 0.4449 |
| `test` | 2 | `yT` | 6,826 | 0.2059 | 0.1517 | -0.9362 | 0.9550 | 1.0308 |
| `test` | 3 | `all` | 6,145 | 0.1290 | 0.0853 | -1.3562 | 0.9386 | 0.6687 |
| `test` | 3 | `delta_yF` | 6,145 | 0.1306 | 0.0859 | -1.2543 | 0.9605 | 0.7887 |
| `test` | 3 | `delta_yN` | 6,145 | 0.1006 | 0.0642 | -1.5640 | 0.8910 | 0.4198 |
| `test` | 3 | `delta_yT` | 6,145 | 0.2026 | 0.1435 | -0.9537 | 0.9585 | 1.0158 |
| `test` | 3 | `sigma_F` | 6,145 | 0.0450 | 0.0249 | -1.8712 | 0.9819 | 0.4982 |
| `test` | 3 | `sigma_N` | 6,145 | 0.1443 | 0.0720 | -1.2802 | 0.8978 | 0.4884 |
| `test` | 3 | `sigma_T` | 6,145 | 0.0843 | 0.0480 | -1.5961 | 0.9383 | 0.5471 |
| `test` | 3 | `yF` | 6,145 | 0.1355 | 0.0918 | -1.2306 | 0.9653 | 0.8099 |
| `test` | 3 | `yN` | 6,145 | 0.0999 | 0.0673 | -1.5427 | 0.8867 | 0.4247 |
| `test` | 3 | `yT` | 6,145 | 0.2183 | 0.1700 | -0.9127 | 0.9670 | 1.0255 |
| `train` | 0 | `all` | 50,000 | 0.1057 | 0.0584 | -2.3198 | 0.9167 | 0.3265 |
| `train` | 0 | `delta_yF` | 50,000 | 0.1373 | 0.0782 | -1.6596 | 0.8868 | 0.3968 |
| `train` | 0 | `delta_yN` | 50,000 | 0.0569 | 0.0185 | -3.4228 | 0.9498 | 0.1086 |
| `train` | 0 | `delta_yT` | 50,000 | 0.2207 | 0.1342 | -1.0094 | 0.8997 | 0.7553 |
| `train` | 0 | `sigma_F` | 50,000 | 0.0399 | 0.0188 | -2.7686 | 0.9257 | 0.1585 |
| `train` | 0 | `sigma_N` | 50,000 | 0.0553 | 0.0120 | -3.1956 | 0.9733 | 0.1475 |
| `train` | 0 | `sigma_T` | 50,000 | 0.0626 | 0.0309 | -2.4363 | 0.8832 | 0.2001 |
| `train` | 0 | `yF` | 50,000 | 0.1248 | 0.0731 | -1.7388 | 0.8864 | 0.3767 |
| `train` | 0 | `yN` | 50,000 | 0.0467 | 0.0149 | -3.5652 | 0.9526 | 0.0983 |
| `train` | 0 | `yT` | 50,000 | 0.2071 | 0.1450 | -1.0819 | 0.8928 | 0.6966 |
| `train` | 1 | `all` | 17,487 | 0.1088 | 0.0560 | -2.3204 | 0.9196 | 0.3404 |
| `train` | 1 | `delta_yF` | 17,487 | 0.1595 | 0.0882 | -1.5020 | 0.8757 | 0.4400 |
| `train` | 1 | `delta_yN` | 17,487 | 0.0674 | 0.0213 | -3.3105 | 0.9438 | 0.1174 |
| `train` | 1 | `delta_yT` | 17,487 | 0.2516 | 0.1456 | -0.8676 | 0.8931 | 0.8437 |
| `train` | 1 | `sigma_F` | 17,487 | 0.0388 | 0.0174 | -2.7879 | 0.9301 | 0.1602 |
| `train` | 1 | `sigma_N` | 17,487 | 0.0542 | 0.0113 | -3.2498 | 0.9760 | 0.1502 |
| `train` | 1 | `sigma_T` | 17,487 | 0.0590 | 0.0279 | -2.5040 | 0.9002 | 0.2102 |
| `train` | 1 | `yF` | 17,487 | 0.1180 | 0.0650 | -1.8060 | 0.8964 | 0.3756 |
| `train` | 1 | `yN` | 17,487 | 0.0446 | 0.0133 | -3.6803 | 0.9567 | 0.0978 |
| `train` | 1 | `yT` | 17,487 | 0.1856 | 0.1141 | -1.1758 | 0.9046 | 0.6680 |
| `train` | 2 | `all` | 16,759 | 0.1019 | 0.0571 | -2.3435 | 0.9171 | 0.3223 |
| `train` | 2 | `delta_yF` | 16,759 | 0.1220 | 0.0692 | -1.7670 | 0.9023 | 0.3913 |
| `train` | 2 | `delta_yN` | 16,759 | 0.0517 | 0.0176 | -3.4921 | 0.9510 | 0.1057 |
| `train` | 2 | `delta_yT` | 16,759 | 0.2014 | 0.1231 | -1.0872 | 0.9108 | 0.7468 |
| `train` | 2 | `sigma_F` | 16,759 | 0.0403 | 0.0191 | -2.7588 | 0.9225 | 0.1553 |
| `train` | 2 | `sigma_N` | 16,759 | 0.0546 | 0.0119 | -3.2093 | 0.9734 | 0.1444 |
| `train` | 2 | `sigma_T` | 16,759 | 0.0628 | 0.0317 | -2.4232 | 0.8788 | 0.1966 |
| `train` | 2 | `yF` | 16,759 | 0.1260 | 0.0747 | -1.7266 | 0.8824 | 0.3727 |
| `train` | 2 | `yN` | 16,759 | 0.0461 | 0.0148 | -3.5652 | 0.9509 | 0.0955 |
| `train` | 2 | `yT` | 16,759 | 0.2119 | 0.1514 | -1.0616 | 0.8815 | 0.6927 |
| `train` | 3 | `all` | 15,754 | 0.1051 | 0.0625 | -2.2939 | 0.9131 | 0.3156 |
| `train` | 3 | `delta_yF` | 15,754 | 0.1254 | 0.0767 | -1.7201 | 0.8824 | 0.3549 |
| `train` | 3 | `delta_yN` | 15,754 | 0.0488 | 0.0165 | -3.4736 | 0.9553 | 0.1018 |
| `train` | 3 | `delta_yT` | 15,754 | 0.2030 | 0.1334 | -1.0839 | 0.8953 | 0.6662 |
| `train` | 3 | `sigma_F` | 15,754 | 0.0408 | 0.0198 | -2.7577 | 0.9243 | 0.1600 |
| `train` | 3 | `sigma_N` | 15,754 | 0.0572 | 0.0129 | -3.1210 | 0.9702 | 0.1479 |
| `train` | 3 | `sigma_T` | 15,754 | 0.0662 | 0.0335 | -2.3751 | 0.8690 | 0.1925 |
| `train` | 3 | `yF` | 15,754 | 0.1306 | 0.0805 | -1.6772 | 0.8795 | 0.3822 |
| `train` | 3 | `yN` | 15,754 | 0.0495 | 0.0169 | -3.4374 | 0.9499 | 0.1019 |
| `train` | 3 | `yT` | 15,754 | 0.2240 | 0.1725 | -0.9993 | 0.8918 | 0.7326 |
| `validation` | 0 | `all` | 18,186 | 0.1352 | 0.0837 | -1.3833 | 0.9424 | 0.7034 |
| `validation` | 0 | `delta_yF` | 18,186 | 0.1441 | 0.0900 | -1.1637 | 0.9605 | 0.8851 |
| `validation` | 0 | `delta_yN` | 18,186 | 0.1167 | 0.0697 | -1.5935 | 0.9027 | 0.4460 |
| `validation` | 0 | `delta_yT` | 18,186 | 0.2334 | 0.1568 | -0.8248 | 0.9508 | 1.1511 |
| `validation` | 0 | `sigma_F` | 18,186 | 0.0554 | 0.0255 | -1.8696 | 0.9762 | 0.5113 |
| `validation` | 0 | `sigma_N` | 18,186 | 0.1359 | 0.0621 | -1.5406 | 0.9251 | 0.5015 |
| `validation` | 0 | `sigma_T` | 18,186 | 0.0930 | 0.0526 | -1.5835 | 0.9418 | 0.5807 |
| `validation` | 0 | `yF` | 18,186 | 0.1282 | 0.0824 | -1.2428 | 0.9655 | 0.8267 |
| `validation` | 0 | `yN` | 18,186 | 0.0961 | 0.0587 | -1.7076 | 0.9084 | 0.4151 |
| `validation` | 0 | `yT` | 18,186 | 0.2137 | 0.1558 | -0.9237 | 0.9508 | 1.0127 |
| `validation` | 1 | `all` | 7,079 | 0.1344 | 0.0795 | -1.3397 | 0.9500 | 0.7761 |
| `validation` | 1 | `delta_yF` | 7,079 | 0.1622 | 0.0986 | -1.0258 | 0.9593 | 1.0102 |
| `validation` | 1 | `delta_yN` | 7,079 | 0.1378 | 0.0818 | -1.3671 | 0.8921 | 0.5157 |
| `validation` | 1 | `delta_yT` | 7,079 | 0.2589 | 0.1667 | -0.7060 | 0.9528 | 1.3021 |
| `validation` | 1 | `sigma_F` | 7,079 | 0.0497 | 0.0222 | -1.8146 | 0.9797 | 0.5676 |
| `validation` | 1 | `sigma_N` | 7,079 | 0.1194 | 0.0524 | -1.6286 | 0.9448 | 0.5570 |
| `validation` | 1 | `sigma_T` | 7,079 | 0.0798 | 0.0420 | -1.5758 | 0.9685 | 0.6522 |
| `validation` | 1 | `yF` | 7,079 | 0.1193 | 0.0716 | -1.2198 | 0.9689 | 0.8850 |
| `validation` | 1 | `yN` | 7,079 | 0.0904 | 0.0524 | -1.7603 | 0.9246 | 0.4545 |
| `validation` | 1 | `yT` | 7,079 | 0.1922 | 0.1280 | -0.9587 | 0.9596 | 1.0407 |
| `validation` | 2 | `all` | 6,038 | 0.1321 | 0.0831 | -1.4013 | 0.9402 | 0.6796 |
| `validation` | 2 | `delta_yF` | 6,038 | 0.1270 | 0.0793 | -1.2269 | 0.9675 | 0.8540 |
| `validation` | 2 | `delta_yN` | 6,038 | 0.1059 | 0.0657 | -1.6754 | 0.9086 | 0.4229 |
| `validation` | 2 | `delta_yT` | 6,038 | 0.2107 | 0.1433 | -0.8810 | 0.9611 | 1.1181 |
| `validation` | 2 | `sigma_F` | 6,038 | 0.0556 | 0.0257 | -1.8918 | 0.9735 | 0.4894 |
| `validation` | 2 | `sigma_N` | 6,038 | 0.1428 | 0.0659 | -1.5026 | 0.9167 | 0.4798 |
| `validation` | 2 | `sigma_T` | 6,038 | 0.0979 | 0.0572 | -1.5846 | 0.9342 | 0.5569 |
| `validation` | 2 | `yF` | 6,038 | 0.1301 | 0.0843 | -1.2552 | 0.9644 | 0.8044 |
| `validation` | 2 | `yN` | 6,038 | 0.0986 | 0.0609 | -1.6783 | 0.8975 | 0.3961 |
| `validation` | 2 | `yT` | 6,038 | 0.2199 | 0.1653 | -0.9156 | 0.9387 | 0.9943 |
| `validation` | 3 | `all` | 5,069 | 0.1376 | 0.0904 | -1.4229 | 0.9345 | 0.6301 |
| `validation` | 3 | `delta_yF` | 5,069 | 0.1360 | 0.0908 | -1.2808 | 0.9538 | 0.7474 |
| `validation` | 3 | `delta_yN` | 5,069 | 0.0948 | 0.0577 | -1.8122 | 0.9106 | 0.3763 |
| `validation` | 3 | `delta_yT` | 5,069 | 0.2212 | 0.1589 | -0.9237 | 0.9359 | 0.9796 |
| `validation` | 3 | `sigma_F` | 5,069 | 0.0624 | 0.0297 | -1.9197 | 0.9747 | 0.4589 |
| `validation` | 3 | `sigma_N` | 5,069 | 0.1486 | 0.0712 | -1.4631 | 0.9075 | 0.4499 |
| `validation` | 3 | `sigma_T` | 5,069 | 0.1034 | 0.0620 | -1.5929 | 0.9136 | 0.5090 |
| `validation` | 3 | `yF` | 5,069 | 0.1374 | 0.0951 | -1.2602 | 0.9621 | 0.7720 |
| `validation` | 3 | `yN` | 5,069 | 0.1008 | 0.0650 | -1.6689 | 0.8990 | 0.3825 |
| `validation` | 3 | `yT` | 5,069 | 0.2337 | 0.1834 | -0.8843 | 0.9529 | 0.9954 |

## Persistence Comparison

| split | horizon | target | Neural ODE v2 RMSE | persistence RMSE | RMSE rel improvement | Neural ODE v2 MAE | persistence MAE | MAE rel improvement |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `test` | 0 | `all` | 0.1285 | 0.1524 | 0.1569 | 0.0799 | 0.0901 | 0.1129 |
| `train` | 0 | `all` | 0.1057 | 0.1279 | 0.1735 | 0.0584 | 0.0656 | 0.1091 |
| `validation` | 0 | `all` | 0.1352 | 0.1590 | 0.1501 | 0.0837 | 0.0941 | 0.1099 |

## Outputs

- Model: `models/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_smoke/pipe_neural_ode_continuous_model_v2.pt`
- Checkpoint: `models/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_smoke/pipe_neural_ode_continuous_checkpoint_v2.pt`
- Metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_smoke/pipe_neural_ode_continuous_metrics.csv`
- Persistence metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_smoke/pipe_neural_ode_continuous_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_smoke/pipe_neural_ode_continuous_persistence_comparison.csv`
- Output blend weights: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_smoke/pipe_neural_ode_continuous_output_blend_weights.csv`
- Output blend search: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_smoke/pipe_neural_ode_continuous_output_blend_search.csv`
- Training curve: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_smoke/pipe_neural_ode_continuous_training_curve.csv`
- Prediction examples: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_smoke/pipe_neural_ode_continuous_prediction_examples.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_smoke/pipe_neural_ode_continuous_manifest.json`
