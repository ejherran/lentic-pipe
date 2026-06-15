# PIPE Neural ODE Training Report v0

Generated at UTC: `2026-06-15T19:18:54.205559+00:00`
Started at UTC: `2026-06-15T19:18:14.121958+00:00`
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
| `train` | 808,970 | 200,000 |
| `validation` | 91,226 | 50,000 |
| `test` | 86,478 | 50,000 |

## Best Epoch

- Epoch: `11`
- Selection metric: `balanced`
- Selection objective: `0.7837`
- Validation loss: `-1.9822`
- Validation RMSE all: `0.1177`
- Validation MAE all: `0.0678`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 200,000 | 0.1045 | 0.0555 | -2.0652 | 0.9153 | 0.3257 |
| `train` | `yN` | 200,000 | 0.0618 | 0.0236 | -2.6639 | 0.9307 | 0.1646 |
| `train` | `yF` | 200,000 | 0.1318 | 0.0739 | -1.6056 | 0.8782 | 0.3896 |
| `train` | `yT` | 200,000 | 0.1785 | 0.1024 | -1.3342 | 0.8842 | 0.5420 |
| `train` | `sigma_N` | 200,000 | 0.0642 | 0.0183 | -2.5581 | 0.9578 | 0.1914 |
| `train` | `sigma_F` | 200,000 | 0.0423 | 0.0182 | -2.7443 | 0.9265 | 0.1443 |
| `train` | `sigma_T` | 200,000 | 0.0739 | 0.0341 | -2.1028 | 0.9405 | 0.3295 |
| `train` | `delta_yN` | 200,000 | 0.0627 | 0.0266 | -2.6614 | 0.9339 | 0.1720 |
| `train` | `delta_yF` | 200,000 | 0.1326 | 0.0837 | -1.6156 | 0.8909 | 0.4081 |
| `train` | `delta_yT` | 200,000 | 0.1927 | 0.1190 | -1.3006 | 0.8946 | 0.5899 |
| `validation` | `all` | 50,000 | 0.1177 | 0.0678 | -1.6351 | 0.9109 | 0.4282 |
| `validation` | `yN` | 50,000 | 0.0830 | 0.0442 | -1.8690 | 0.8968 | 0.2624 |
| `validation` | `yF` | 50,000 | 0.1338 | 0.0772 | -1.4913 | 0.8978 | 0.4807 |
| `validation` | `yT` | 50,000 | 0.1900 | 0.1181 | -1.2031 | 0.8864 | 0.6489 |
| `validation` | `sigma_N` | 50,000 | 0.0978 | 0.0399 | -1.3728 | 0.9251 | 0.2918 |
| `validation` | `sigma_F` | 50,000 | 0.0462 | 0.0202 | -2.4694 | 0.9403 | 0.2047 |
| `validation` | `sigma_T` | 50,000 | 0.0855 | 0.0441 | -1.7832 | 0.9412 | 0.4621 |
| `validation` | `delta_yN` | 50,000 | 0.0851 | 0.0484 | -1.8707 | 0.9020 | 0.2744 |
| `validation` | `delta_yF` | 50,000 | 0.1345 | 0.0855 | -1.4941 | 0.9097 | 0.5054 |
| `validation` | `delta_yT` | 50,000 | 0.2032 | 0.1329 | -1.1620 | 0.8985 | 0.7230 |
| `test` | `all` | 50,000 | 0.1213 | 0.0709 | -1.5124 | 0.9001 | 0.4486 |
| `test` | `yN` | 50,000 | 0.0906 | 0.0500 | -1.5783 | 0.8730 | 0.2811 |
| `test` | `yF` | 50,000 | 0.1359 | 0.0784 | -1.4837 | 0.9014 | 0.4980 |
| `test` | `yT` | 50,000 | 0.1888 | 0.1193 | -1.1205 | 0.8794 | 0.6707 |
| `test` | `sigma_N` | 50,000 | 0.1111 | 0.0480 | -1.1912 | 0.8969 | 0.3096 |
| `test` | `sigma_F` | 50,000 | 0.0477 | 0.0210 | -2.4102 | 0.9336 | 0.2150 |
| `test` | `sigma_T` | 50,000 | 0.0831 | 0.0438 | -1.6990 | 0.9346 | 0.4901 |
| `test` | `delta_yN` | 50,000 | 0.0929 | 0.0545 | -1.5848 | 0.8780 | 0.2943 |
| `test` | `delta_yF` | 50,000 | 0.1378 | 0.0874 | -1.4771 | 0.9131 | 0.5259 |
| `test` | `delta_yT` | 50,000 | 0.2042 | 0.1354 | -1.0672 | 0.8911 | 0.7530 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure Neural ODE prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.2000 | 0.0442 | 0.0830 | 1.0177 |
| `yF` | 0.2000 | 0.0772 | 0.1338 | 1.0292 |
| `yT` | 0.5000 | 0.1181 | 0.1900 | 1.0358 |
| `sigma_N` | 0.0000 | 0.0399 | 0.0978 | 1.0000 |
| `sigma_F` | 0.0000 | 0.0202 | 0.0462 | 1.0018 |
| `sigma_T` | 0.0000 | 0.0441 | 0.0855 | 1.0000 |
| `delta_yN` | 1.0000 | 0.0484 | 0.0851 | 1.0000 |
| `delta_yF` | 1.0000 | 0.0855 | 0.1345 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1329 | 0.2032 | 1.0000 |

## Persistence Comparison

Positive relative improvement means PIPE Neural ODE beats the one-step persistence baseline.

| split | target | Neural ODE RMSE | persistence RMSE | RMSE rel improvement | Neural ODE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1213 | 0.1591 | 0.2374 | 0.0709 | 0.0893 | 0.2061 |
| `train` | `all` | 0.1045 | 0.1369 | 0.2367 | 0.0555 | 0.0683 | 0.1865 |
| `validation` | `all` | 0.1177 | 0.1534 | 0.2331 | 0.0678 | 0.0847 | 0.1995 |

## Outputs

- Model: `models/pipe_neural_ode/adaptive_wqp_focused_extended_smoke/pipe_neural_ode_model_v0.pt`
- Checkpoint: `models/pipe_neural_ode/adaptive_wqp_focused_extended_smoke/pipe_neural_ode_checkpoint_v0.pt`
- Metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_extended_smoke/pipe_neural_ode_metrics.csv`
- Persistence metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_extended_smoke/pipe_neural_ode_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_neural_ode/adaptive_wqp_focused_extended_smoke/pipe_neural_ode_persistence_comparison.csv`
- Output blend weights: `reports/pipe_neural_ode/adaptive_wqp_focused_extended_smoke/pipe_neural_ode_output_blend_weights.csv`
- Output blend search: `reports/pipe_neural_ode/adaptive_wqp_focused_extended_smoke/pipe_neural_ode_output_blend_search.csv`
- Training curve: `reports/pipe_neural_ode/adaptive_wqp_focused_extended_smoke/pipe_neural_ode_training_curve.csv`
- Prediction examples: `reports/pipe_neural_ode/adaptive_wqp_focused_extended_smoke/pipe_neural_ode_prediction_examples.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_extended_smoke/pipe_neural_ode_manifest.json`
