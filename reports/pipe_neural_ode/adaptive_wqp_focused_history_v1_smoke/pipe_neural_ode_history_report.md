# PIPE Neural ODE History Training Report v1

Generated at UTC: `2026-06-15T20:26:49.386572+00:00`
Started at UTC: `2026-06-15T20:26:46.403921+00:00`
Status: `completed`

## Scope

This step trains a history-encoded Neural ODE variant over the frozen PIPE sequence schema.
A GRU encoder summarizes the recent PIPE history, initializes a latent ODE, and decodes the next fuzzy state.
The v1 runner is one-step; recursive rollout support is a downstream gate after one-step validation.
Synthetic smoke mode: `False`.

## Configuration

- History length: `12`
- History hidden dimension: `96`
- History layers: `1`
- Latent dimension: `64`
- Dynamics hidden dimension: `96`
- Dynamics depth: `2`
- Dropout: `0.0`
- Derivative scale: `0.5`
- State delta scale: `0.5`
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

## Windows

| split | available | sampled/used |
|---|---:|---:|
| `train` | 112,470 | 50,000 |
| `validation` | 7,079 | 7,079 |
| `test` | 7,582 | 7,582 |

## Best Epoch

- Epoch: `3`
- Selection metric: `balanced`
- Selection objective: `0.9273`
- Validation loss: `-1.4372`
- Validation RMSE all: `0.1389`
- Validation MAE all: `0.0823`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 50,000 | 0.1122 | 0.0606 | -1.9321 | 0.9086 | 0.3591 |
| `train` | `yN` | 50,000 | 0.0455 | 0.0184 | -2.6445 | 0.9364 | 0.1367 |
| `train` | `yF` | 50,000 | 0.1177 | 0.0674 | -1.6563 | 0.8998 | 0.3896 |
| `train` | `yT` | 50,000 | 0.1950 | 0.1094 | -1.1265 | 0.8593 | 0.5696 |
| `train` | `sigma_N` | 50,000 | 0.0529 | 0.0109 | -2.4981 | 0.9629 | 0.1565 |
| `train` | `sigma_F` | 50,000 | 0.0374 | 0.0168 | -2.8051 | 0.9036 | 0.1243 |
| `train` | `sigma_T` | 50,000 | 0.0577 | 0.0274 | -2.3762 | 0.8781 | 0.1761 |
| `train` | `delta_yN` | 50,000 | 0.0751 | 0.0311 | -2.1450 | 0.9342 | 0.2328 |
| `train` | `delta_yF` | 50,000 | 0.1755 | 0.1008 | -1.2616 | 0.9055 | 0.5796 |
| `train` | `delta_yT` | 50,000 | 0.2528 | 0.1628 | -0.8754 | 0.8978 | 0.8670 |
| `validation` | `all` | 7,079 | 0.1389 | 0.0823 | -1.2464 | 0.8450 | 0.3789 |
| `validation` | `yN` | 7,079 | 0.0916 | 0.0539 | -1.0531 | 0.7621 | 0.1490 |
| `validation` | `yF` | 7,079 | 0.1207 | 0.0736 | -1.6138 | 0.8969 | 0.4106 |
| `validation` | `yT` | 7,079 | 0.1998 | 0.1211 | -1.0983 | 0.8453 | 0.5985 |
| `validation` | `sigma_N` | 7,079 | 0.1194 | 0.0524 | -0.3033 | 0.8484 | 0.1702 |
| `validation` | `sigma_F` | 7,079 | 0.0497 | 0.0222 | -2.5108 | 0.8918 | 0.1378 |
| `validation` | `sigma_T` | 7,079 | 0.0798 | 0.0420 | -1.8956 | 0.8063 | 0.1916 |
| `validation` | `delta_yN` | 7,079 | 0.1485 | 0.0894 | -0.6869 | 0.7587 | 0.2512 |
| `validation` | `delta_yF` | 7,079 | 0.1816 | 0.1125 | -1.2110 | 0.8979 | 0.6064 |
| `validation` | `delta_yT` | 7,079 | 0.2594 | 0.1734 | -0.8447 | 0.8974 | 0.8949 |
| `test` | `all` | 7,582 | 0.1343 | 0.0796 | -1.2141 | 0.8528 | 0.3827 |
| `test` | `yN` | 7,582 | 0.0925 | 0.0567 | -1.0231 | 0.7440 | 0.1514 |
| `test` | `yF` | 7,582 | 0.1176 | 0.0705 | -1.6356 | 0.9035 | 0.4138 |
| `test` | `yT` | 7,582 | 0.1874 | 0.1110 | -1.1682 | 0.8793 | 0.6044 |
| `test` | `sigma_N` | 7,582 | 0.1382 | 0.0634 | 0.5590 | 0.8322 | 0.1727 |
| `test` | `sigma_F` | 7,582 | 0.0395 | 0.0203 | -2.7042 | 0.8874 | 0.1399 |
| `test` | `sigma_T` | 7,582 | 0.0702 | 0.0364 | -2.0924 | 0.8552 | 0.1942 |
| `test` | `delta_yN` | 7,582 | 0.1476 | 0.0916 | -0.7090 | 0.7440 | 0.2549 |
| `test` | `delta_yF` | 7,582 | 0.1743 | 0.1060 | -1.2488 | 0.9126 | 0.6116 |
| `test` | `delta_yT` | 7,582 | 0.2413 | 0.1600 | -0.9042 | 0.9172 | 0.9018 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure Neural ODE v1 prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.8000 | 0.0539 | 0.0916 | 1.0106 |
| `yF` | 0.8000 | 0.0736 | 0.1207 | 1.0115 |
| `yT` | 0.3500 | 0.1211 | 0.1998 | 1.0391 |
| `sigma_N` | 0.0000 | 0.0524 | 0.1194 | 1.0012 |
| `sigma_F` | 0.0000 | 0.0222 | 0.0497 | 1.0001 |
| `sigma_T` | 0.0000 | 0.0420 | 0.0798 | 1.0071 |
| `delta_yN` | 1.0000 | 0.0894 | 0.1485 | 1.0000 |
| `delta_yF` | 1.0000 | 0.1125 | 0.1816 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1734 | 0.2594 | 1.0000 |

## Persistence Comparison

Positive relative improvement means PIPE Neural ODE v1 beats the one-step persistence baseline.

| split | target | Neural ODE v1 RMSE | persistence RMSE | RMSE rel improvement | Neural ODE v1 MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1343 | 0.1475 | 0.0896 | 0.0796 | 0.0841 | 0.0538 |
| `train` | `all` | 0.1122 | 0.1248 | 0.1014 | 0.0606 | 0.0612 | 0.0109 |
| `validation` | `all` | 0.1389 | 0.1529 | 0.0910 | 0.0823 | 0.0870 | 0.0545 |

## Outputs

- Model: `models/pipe_neural_ode/adaptive_wqp_focused_history_v1_smoke/pipe_neural_ode_history_model_v1.pt`
- Checkpoint: `models/pipe_neural_ode/adaptive_wqp_focused_history_v1_smoke/pipe_neural_ode_history_checkpoint_v1.pt`
- Metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_smoke/pipe_neural_ode_history_metrics.csv`
- Persistence metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_smoke/pipe_neural_ode_history_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_smoke/pipe_neural_ode_history_persistence_comparison.csv`
- Output blend weights: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_smoke/pipe_neural_ode_history_output_blend_weights.csv`
- Output blend search: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_smoke/pipe_neural_ode_history_output_blend_search.csv`
- Training curve: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_smoke/pipe_neural_ode_history_training_curve.csv`
- Prediction examples: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_smoke/pipe_neural_ode_history_prediction_examples.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_smoke/pipe_neural_ode_history_manifest.json`
