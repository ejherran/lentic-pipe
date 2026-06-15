# PIPE Neural ODE Training Report v0

Generated at UTC: `2026-06-15T19:23:45.171020+00:00`
Started at UTC: `2026-06-15T19:21:33.022856+00:00`
Status: `completed`

## Scope

This step trains a probabilistic Neural ODE variant over the frozen PIPE sequence schema.
It models the monthly transition with a learned continuous-time derivative `dS/dt = f_theta(S, season, t)`.
The v0 runner is one-step only; recursive rollouts and alert calibration are downstream gates.
Synthetic smoke mode: `False`.

## Configuration

- Hidden dimension: `96`
- Dynamics depth: `2`
- Dropout: `0.0`
- Derivative scale: `0.5`
- Integration time: `1.0`
- ODE method: `rk4`
- ODE step size: `0.25`
- Auxiliary MSE weight: `0.5`
- Checkpoint selection metric: `balanced`
- Output blend selection metric: `balanced`
- Epochs requested: `20`
- Batch size: `2048`
- Learning rate: `0.001`
- Device: `auto`

## Transitions

| split | available | sampled/used |
|---|---:|---:|
| `train` | 808,970 | 808,970 |
| `validation` | 91,226 | 91,226 |
| `test` | 86,478 | 86,478 |

## Best Epoch

- Epoch: `15`
- Selection metric: `balanced`
- Selection objective: `0.7794`
- Validation loss: `-1.9450`
- Validation RMSE all: `0.1169`
- Validation MAE all: `0.0673`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 808,970 | 0.1038 | 0.0549 | -2.1855 | 0.9313 | 0.3402 |
| `train` | `yN` | 808,970 | 0.0605 | 0.0238 | -2.9080 | 0.9483 | 0.1562 |
| `train` | `yF` | 808,970 | 0.1280 | 0.0745 | -1.6780 | 0.8854 | 0.3833 |
| `train` | `yT` | 808,970 | 0.1774 | 0.1009 | -1.5263 | 0.9058 | 0.5140 |
| `train` | `sigma_N` | 808,970 | 0.0644 | 0.0183 | -2.7183 | 0.9710 | 0.1980 |
| `train` | `sigma_F` | 808,970 | 0.0423 | 0.0182 | -2.8329 | 0.9314 | 0.1362 |
| `train` | `sigma_T` | 808,970 | 0.0737 | 0.0339 | -1.9484 | 0.9811 | 0.5493 |
| `train` | `delta_yN` | 808,970 | 0.0634 | 0.0254 | -2.8943 | 0.9504 | 0.1649 |
| `train` | `delta_yF` | 808,970 | 0.1314 | 0.0822 | -1.6713 | 0.8932 | 0.3990 |
| `train` | `delta_yT` | 808,970 | 0.1934 | 0.1167 | -1.4919 | 0.9148 | 0.5608 |
| `validation` | `all` | 91,226 | 0.1169 | 0.0673 | -1.5877 | 0.9250 | 0.4646 |
| `validation` | `yN` | 91,226 | 0.0812 | 0.0445 | -1.6011 | 0.9250 | 0.3174 |
| `validation` | `yF` | 91,226 | 0.1302 | 0.0787 | -1.6042 | 0.9008 | 0.4352 |
| `validation` | `yT` | 91,226 | 0.1869 | 0.1167 | -1.3519 | 0.8920 | 0.5848 |
| `validation` | `sigma_N` | 91,226 | 0.0985 | 0.0402 | -1.1687 | 0.9430 | 0.3915 |
| `validation` | `sigma_F` | 91,226 | 0.0466 | 0.0203 | -2.6278 | 0.9379 | 0.1688 |
| `validation` | `sigma_T` | 91,226 | 0.0854 | 0.0440 | -1.4825 | 0.9864 | 0.8351 |
| `validation` | `delta_yN` | 91,226 | 0.0851 | 0.0461 | -1.5695 | 0.9286 | 0.3454 |
| `validation` | `delta_yF` | 91,226 | 0.1350 | 0.0863 | -1.5821 | 0.9072 | 0.4558 |
| `validation` | `delta_yT` | 91,226 | 0.2029 | 0.1293 | -1.3014 | 0.9042 | 0.6472 |
| `test` | `all` | 86,478 | 0.1209 | 0.0708 | -1.5055 | 0.9167 | 0.4869 |
| `test` | `yN` | 86,478 | 0.0885 | 0.0504 | -1.5002 | 0.9048 | 0.3296 |
| `test` | `yF` | 86,478 | 0.1328 | 0.0806 | -1.5843 | 0.9024 | 0.4504 |
| `test` | `yT` | 86,478 | 0.1871 | 0.1194 | -1.1917 | 0.8876 | 0.6175 |
| `test` | `sigma_N` | 86,478 | 0.1119 | 0.0485 | -1.2281 | 0.9193 | 0.4041 |
| `test` | `sigma_F` | 86,478 | 0.0480 | 0.0212 | -2.5487 | 0.9332 | 0.1767 |
| `test` | `sigma_T` | 86,478 | 0.0832 | 0.0439 | -1.3407 | 0.9864 | 0.8858 |
| `test` | `delta_yN` | 86,478 | 0.0935 | 0.0523 | -1.4639 | 0.9076 | 0.3578 |
| `test` | `delta_yF` | 86,478 | 0.1385 | 0.0884 | -1.5593 | 0.9091 | 0.4733 |
| `test` | `delta_yT` | 86,478 | 0.2045 | 0.1326 | -1.1325 | 0.8999 | 0.6865 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure Neural ODE prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.3500 | 0.0445 | 0.0812 | 1.0166 |
| `yF` | 0.3500 | 0.0787 | 0.1302 | 1.0275 |
| `yT` | 0.5000 | 0.1167 | 0.1869 | 1.0338 |
| `sigma_N` | 0.0000 | 0.0402 | 0.0985 | 1.0117 |
| `sigma_F` | 0.0000 | 0.0203 | 0.0466 | 1.0056 |
| `sigma_T` | 0.0000 | 0.0440 | 0.0854 | 1.0000 |
| `delta_yN` | 1.0000 | 0.0461 | 0.0851 | 1.0000 |
| `delta_yF` | 1.0000 | 0.0863 | 0.1350 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1293 | 0.2029 | 1.0000 |

## Persistence Comparison

Positive relative improvement means PIPE Neural ODE beats the one-step persistence baseline.

| split | target | Neural ODE RMSE | persistence RMSE | RMSE rel improvement | Neural ODE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1209 | 0.1597 | 0.2428 | 0.0708 | 0.0897 | 0.2110 |
| `train` | `all` | 0.1038 | 0.1369 | 0.2413 | 0.0549 | 0.0681 | 0.1942 |
| `validation` | `all` | 0.1169 | 0.1533 | 0.2376 | 0.0673 | 0.0845 | 0.2035 |

## Outputs

- Model: `models/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_model_v0.pt`
- Checkpoint: `models/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_checkpoint_v0.pt`
- Metrics: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_metrics.csv`
- Persistence metrics: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_persistence_comparison.csv`
- Output blend weights: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_output_blend_weights.csv`
- Output blend search: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_output_blend_search.csv`
- Training curve: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_training_curve.csv`
- Prediction examples: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_prediction_examples.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_manifest.json`
