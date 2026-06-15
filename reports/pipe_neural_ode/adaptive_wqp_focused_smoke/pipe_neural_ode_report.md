# PIPE Neural ODE Training Report v0

Generated at UTC: `2026-06-15T17:47:23.540015+00:00`
Started at UTC: `2026-06-15T17:47:20.197552+00:00`
Status: `completed`

## Scope

This step trains a probabilistic Neural ODE variant over the frozen PIPE sequence schema.
It models the monthly transition with a learned continuous-time derivative `dS/dt = f_theta(S, season, t)`.
The v0 runner is one-step only; recursive rollouts and alert calibration are downstream gates.
Synthetic smoke mode: `False`.

## Configuration

- Hidden dimension: `64`
- Dynamics depth: `2`
- Dropout: `0.0`
- Derivative scale: `0.25`
- Integration time: `1.0`
- ODE method: `rk4`
- ODE step size: `0.25`
- Auxiliary MSE weight: `0.5`
- Checkpoint selection metric: `balanced`
- Output blend selection metric: `balanced`
- Epochs requested: `3`
- Batch size: `2048`
- Learning rate: `0.001`
- Device: `auto`

## Transitions

| split | available | sampled/used |
|---|---:|---:|
| `train` | 808,970 | 50,000 |
| `validation` | 91,226 | 20,000 |
| `test` | 86,478 | 20,000 |

## Best Epoch

- Epoch: `3`
- Selection metric: `balanced`
- Selection objective: `0.9828`
- Validation loss: `-1.1771`
- Validation RMSE all: `0.1500`
- Validation MAE all: `0.0855`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 50,000 | 0.1329 | 0.0692 | -0.9983 | 0.9804 | 1.1199 |
| `train` | `yN` | 50,000 | 0.0641 | 0.0234 | -1.1915 | 0.9990 | 1.0245 |
| `train` | `yF` | 50,000 | 0.1371 | 0.0739 | -1.0223 | 0.9897 | 1.1117 |
| `train` | `yT` | 50,000 | 0.1959 | 0.0995 | -0.9431 | 0.9676 | 1.1115 |
| `train` | `sigma_N` | 50,000 | 0.0643 | 0.0183 | -1.0822 | 0.9984 | 1.1265 |
| `train` | `sigma_F` | 50,000 | 0.0425 | 0.0183 | -1.0667 | 1.0000 | 1.1498 |
| `train` | `sigma_T` | 50,000 | 0.0730 | 0.0338 | -1.0214 | 0.9998 | 1.1896 |
| `train` | `delta_yN` | 50,000 | 0.1092 | 0.0427 | -1.0691 | 0.9926 | 1.1079 |
| `train` | `delta_yF` | 50,000 | 0.2269 | 0.1352 | -0.8506 | 0.9560 | 1.1356 |
| `train` | `delta_yT` | 50,000 | 0.2834 | 0.1778 | -0.7381 | 0.9209 | 1.1221 |
| `validation` | `all` | 20,000 | 0.1500 | 0.0855 | -0.9370 | 0.9777 | 1.1751 |
| `validation` | `yN` | 20,000 | 0.0863 | 0.0443 | -1.1275 | 0.9978 | 1.0812 |
| `validation` | `yF` | 20,000 | 0.1393 | 0.0773 | -0.9816 | 0.9899 | 1.1620 |
| `validation` | `yT` | 20,000 | 0.2082 | 0.1170 | -0.8829 | 0.9665 | 1.1644 |
| `validation` | `sigma_N` | 20,000 | 0.0991 | 0.0404 | -1.0149 | 0.9952 | 1.1855 |
| `validation` | `sigma_F` | 20,000 | 0.0468 | 0.0204 | -1.0249 | 1.0000 | 1.2030 |
| `validation` | `sigma_T` | 20,000 | 0.0859 | 0.0446 | -0.9712 | 0.9998 | 1.2466 |
| `validation` | `delta_yN` | 20,000 | 0.1469 | 0.0798 | -0.9839 | 0.9882 | 1.1651 |
| `validation` | `delta_yF` | 20,000 | 0.2349 | 0.1427 | -0.7952 | 0.9490 | 1.1873 |
| `validation` | `delta_yT` | 20,000 | 0.3025 | 0.2030 | -0.6505 | 0.9131 | 1.1811 |
| `test` | `all` | 20,000 | 0.1550 | 0.0894 | -0.9398 | 0.9760 | 1.1535 |
| `test` | `yN` | 20,000 | 0.0935 | 0.0498 | -1.1374 | 0.9970 | 1.0529 |
| `test` | `yF` | 20,000 | 0.1410 | 0.0779 | -0.9945 | 0.9880 | 1.1348 |
| `test` | `yT` | 20,000 | 0.2067 | 0.1170 | -0.8884 | 0.9682 | 1.1513 |
| `test` | `sigma_N` | 20,000 | 0.1118 | 0.0481 | -1.0128 | 0.9952 | 1.1714 |
| `test` | `sigma_F` | 20,000 | 0.0491 | 0.0214 | -1.0337 | 1.0000 | 1.1866 |
| `test` | `sigma_T` | 20,000 | 0.0837 | 0.0441 | -0.9906 | 0.9999 | 1.2178 |
| `test` | `delta_yN` | 20,000 | 0.1606 | 0.0909 | -0.9757 | 0.9842 | 1.1404 |
| `test` | `delta_yF` | 20,000 | 0.2385 | 0.1450 | -0.7979 | 0.9482 | 1.1640 |
| `test` | `delta_yT` | 20,000 | 0.3102 | 0.2106 | -0.6277 | 0.9029 | 1.1626 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure Neural ODE prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.0000 | 0.0443 | 0.0863 | 1.0000 |
| `yF` | 0.0000 | 0.0773 | 0.1393 | 1.0000 |
| `yT` | 0.1000 | 0.1170 | 0.2082 | 1.0358 |
| `sigma_N` | 0.0000 | 0.0404 | 0.0991 | 1.0000 |
| `sigma_F` | 0.0000 | 0.0204 | 0.0468 | 1.0000 |
| `sigma_T` | 0.0000 | 0.0446 | 0.0859 | 1.0000 |
| `delta_yN` | 0.0000 | 0.0798 | 0.1469 | 1.0009 |
| `delta_yF` | 0.2000 | 0.1427 | 0.2349 | 1.0117 |
| `delta_yT` | 1.0000 | 0.2030 | 0.3025 | 1.0000 |

## Persistence Comparison

Positive relative improvement means PIPE Neural ODE beats the one-step persistence baseline.

| split | target | Neural ODE RMSE | persistence RMSE | RMSE rel improvement | Neural ODE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1550 | 0.1603 | 0.0326 | 0.0894 | 0.0899 | 0.0047 |
| `train` | `all` | 0.1329 | 0.1374 | 0.0324 | 0.0692 | 0.0684 | -0.0111 |
| `validation` | `all` | 0.1500 | 0.1548 | 0.0314 | 0.0855 | 0.0857 | 0.0029 |

## Outputs

- Model: `models/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_model_v0.pt`
- Checkpoint: `models/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_checkpoint_v0.pt`
- Metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_metrics.csv`
- Persistence metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_persistence_comparison.csv`
- Output blend weights: `reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_output_blend_weights.csv`
- Output blend search: `reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_output_blend_search.csv`
- Training curve: `reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_training_curve.csv`
- Prediction examples: `reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_prediction_examples.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_smoke/pipe_neural_ode_manifest.json`
