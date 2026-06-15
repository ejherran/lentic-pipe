# PIPE Neural ODE Training Report v0

Generated at UTC: `2026-06-15T17:36:34.589854+00:00`
Started at UTC: `2026-06-15T17:36:32.679723+00:00`
Status: `completed`

## Scope

This step trains a probabilistic Neural ODE variant over the frozen PIPE sequence schema.
It models the monthly transition with a learned continuous-time derivative `dS/dt = f_theta(S, season, t)`.
The v0 runner is one-step only; recursive rollouts and alert calibration are downstream gates.
Synthetic smoke mode: `True`.

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
- Epochs requested: `20`
- Batch size: `128`
- Learning rate: `0.001`
- Device: `auto`

## Transitions

| split | available | sampled/used |
|---|---:|---:|
| `train` | 384 | 384 |
| `validation` | 384 | 384 |
| `test` | 384 | 384 |

## Best Epoch

- Epoch: `10`
- Selection metric: `balanced`
- Selection objective: `0.7168`
- Validation loss: `-0.2238`
- Validation RMSE all: `0.0111`
- Validation MAE all: `0.0087`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 384 | 0.0109 | 0.0086 | -0.1662 | 1.0000 | 2.7907 |
| `train` | `yN` | 384 | 0.0117 | 0.0094 | -0.2095 | 1.0000 | 2.6727 |
| `train` | `yF` | 384 | 0.0077 | 0.0059 | -0.2381 | 1.0000 | 2.5966 |
| `train` | `yT` | 384 | 0.0211 | 0.0156 | -0.2060 | 1.0000 | 2.6784 |
| `train` | `sigma_N` | 384 | 0.0011 | 0.0010 | -0.1181 | 1.0000 | 2.9242 |
| `train` | `sigma_F` | 384 | 0.0014 | 0.0012 | -0.1343 | 1.0000 | 2.8769 |
| `train` | `sigma_T` | 384 | 0.0013 | 0.0011 | -0.1917 | 1.0000 | 2.7210 |
| `train` | `delta_yN` | 384 | 0.0193 | 0.0171 | -0.1014 | 1.0000 | 2.9741 |
| `train` | `delta_yF` | 384 | 0.0077 | 0.0059 | -0.1598 | 1.0000 | 2.8057 |
| `train` | `delta_yT` | 384 | 0.0264 | 0.0205 | -0.1373 | 1.0000 | 2.8669 |
| `validation` | `all` | 384 | 0.0111 | 0.0087 | -0.1680 | 1.0000 | 2.7857 |
| `validation` | `yN` | 384 | 0.0104 | 0.0086 | -0.2115 | 1.0000 | 2.6676 |
| `validation` | `yF` | 384 | 0.0083 | 0.0064 | -0.2418 | 1.0000 | 2.5868 |
| `validation` | `yT` | 384 | 0.0212 | 0.0148 | -0.2071 | 1.0000 | 2.6755 |
| `validation` | `sigma_N` | 384 | 0.0013 | 0.0012 | -0.1194 | 1.0000 | 2.9205 |
| `validation` | `sigma_F` | 384 | 0.0014 | 0.0011 | -0.1361 | 1.0000 | 2.8719 |
| `validation` | `sigma_T` | 384 | 0.0014 | 0.0012 | -0.1909 | 1.0000 | 2.7230 |
| `validation` | `delta_yN` | 384 | 0.0193 | 0.0174 | -0.1045 | 1.0000 | 2.9650 |
| `validation` | `delta_yF` | 384 | 0.0083 | 0.0064 | -0.1624 | 1.0000 | 2.7984 |
| `validation` | `delta_yT` | 384 | 0.0281 | 0.0216 | -0.1387 | 1.0000 | 2.8626 |
| `test` | `all` | 384 | 0.0104 | 0.0084 | -0.1661 | 1.0000 | 2.7911 |
| `test` | `yN` | 384 | 0.0103 | 0.0085 | -0.2080 | 1.0000 | 2.6767 |
| `test` | `yF` | 384 | 0.0091 | 0.0069 | -0.2413 | 1.0000 | 2.5880 |
| `test` | `yT` | 384 | 0.0176 | 0.0127 | -0.2061 | 1.0000 | 2.6784 |
| `test` | `sigma_N` | 384 | 0.0012 | 0.0010 | -0.1183 | 1.0000 | 2.9237 |
| `test` | `sigma_F` | 384 | 0.0012 | 0.0010 | -0.1330 | 1.0000 | 2.8806 |
| `test` | `sigma_T` | 384 | 0.0012 | 0.0010 | -0.1858 | 1.0000 | 2.7369 |
| `test` | `delta_yN` | 384 | 0.0194 | 0.0176 | -0.1041 | 1.0000 | 2.9660 |
| `test` | `delta_yF` | 384 | 0.0091 | 0.0069 | -0.1602 | 1.0000 | 2.8043 |
| `test` | `delta_yT` | 384 | 0.0249 | 0.0200 | -0.1380 | 1.0000 | 2.8649 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure Neural ODE prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 1.0000 | 0.0086 | 0.0104 | 1.0000 |
| `yF` | 0.0000 | 0.0064 | 0.0083 | 1.0000 |
| `yT` | 0.3500 | 0.0148 | 0.0212 | 1.0000 |
| `sigma_N` | 0.0000 | 0.0012 | 0.0013 | 1.0000 |
| `sigma_F` | 0.0000 | 0.0011 | 0.0014 | 1.0000 |
| `sigma_T` | 0.0000 | 0.0012 | 0.0014 | 1.0000 |
| `delta_yN` | 0.5000 | 0.0174 | 0.0193 | 1.0000 |
| `delta_yF` | 0.0000 | 0.0064 | 0.0083 | 1.0000 |
| `delta_yT` | 0.2000 | 0.0216 | 0.0281 | 1.0066 |

## Persistence Comparison

Positive relative improvement means PIPE Neural ODE beats the one-step persistence baseline.

| split | target | Neural ODE RMSE | persistence RMSE | RMSE rel improvement | Neural ODE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.0104 | 0.0152 | 0.3157 | 0.0084 | 0.0116 | 0.2780 |
| `train` | `all` | 0.0109 | 0.0155 | 0.2989 | 0.0086 | 0.0116 | 0.2580 |
| `validation` | `all` | 0.0111 | 0.0158 | 0.2968 | 0.0087 | 0.0119 | 0.2695 |

## Outputs

- Model: `models/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_model_v0.pt`
- Checkpoint: `models/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_checkpoint_v0.pt`
- Metrics: `reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_metrics.csv`
- Persistence metrics: `reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_persistence_comparison.csv`
- Output blend weights: `reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_output_blend_weights.csv`
- Output blend search: `reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_output_blend_search.csv`
- Training curve: `reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_training_curve.csv`
- Prediction examples: `reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_prediction_examples.csv`
- Manifest: `reports/pipe_neural_ode/synthetic_smoke/pipe_neural_ode_manifest.json`
