# PIPE Neural ODE History Training Report v1

Generated at UTC: `2026-06-15T20:40:40.713050+00:00`
Started at UTC: `2026-06-15T20:39:15.604602+00:00`
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
- Epochs requested: `80`
- Batch size: `2048`
- Learning rate: `0.001`
- Device: `auto`

## Windows

| split | available | sampled/used |
|---|---:|---:|
| `train` | 112,470 | 112,470 |
| `validation` | 7,079 | 7,079 |
| `test` | 7,582 | 7,582 |

## Best Epoch

- Epoch: `77`
- Selection metric: `balanced`
- Selection objective: `0.7495`
- Validation loss: `-2.2439`
- Validation RMSE all: `0.1102`
- Validation MAE all: `0.0677`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 112,470 | 0.0873 | 0.0467 | -2.9532 | 0.9464 | 0.2350 |
| `train` | `yN` | 112,470 | 0.0411 | 0.0124 | -4.3046 | 0.9758 | 0.0711 |
| `train` | `yF` | 112,470 | 0.1034 | 0.0617 | -2.1994 | 0.9284 | 0.3028 |
| `train` | `yT` | 112,470 | 0.1595 | 0.0984 | -1.7167 | 0.9433 | 0.4803 |
| `train` | `sigma_N` | 112,470 | 0.0537 | 0.0111 | -4.2890 | 0.9795 | 0.0800 |
| `train` | `sigma_F` | 112,470 | 0.0368 | 0.0173 | -3.0777 | 0.9249 | 0.1171 |
| `train` | `sigma_T` | 112,470 | 0.0533 | 0.0296 | -2.8573 | 0.9088 | 0.1441 |
| `train` | `delta_yN` | 112,470 | 0.0417 | 0.0131 | -4.3009 | 0.9773 | 0.0722 |
| `train` | `delta_yF` | 112,470 | 0.1108 | 0.0656 | -2.1872 | 0.9353 | 0.3187 |
| `train` | `delta_yT` | 112,470 | 0.1851 | 0.1110 | -1.6463 | 0.9447 | 0.5282 |
| `validation` | `all` | 7,079 | 0.1102 | 0.0677 | -1.8640 | 0.9062 | 0.3215 |
| `validation` | `yN` | 7,079 | 0.0844 | 0.0519 | -2.2187 | 0.9102 | 0.2444 |
| `validation` | `yF` | 7,079 | 0.1070 | 0.0691 | -1.9608 | 0.9031 | 0.3194 |
| `validation` | `yT` | 7,079 | 0.1679 | 0.1153 | -1.1401 | 0.9020 | 0.5240 |
| `validation` | `sigma_N` | 7,079 | 0.1194 | 0.0524 | -1.4158 | 0.9227 | 0.3148 |
| `validation` | `sigma_F` | 7,079 | 0.0486 | 0.0224 | -2.8096 | 0.9185 | 0.1331 |
| `validation` | `sigma_T` | 7,079 | 0.0729 | 0.0437 | -2.0127 | 0.8823 | 0.2265 |
| `validation` | `delta_yN` | 7,079 | 0.0885 | 0.0550 | -2.2196 | 0.9143 | 0.2499 |
| `validation` | `delta_yF` | 7,079 | 0.1125 | 0.0730 | -1.9431 | 0.9083 | 0.3366 |
| `validation` | `delta_yT` | 7,079 | 0.1904 | 0.1266 | -1.0556 | 0.8945 | 0.5448 |
| `test` | `all` | 7,582 | 0.1064 | 0.0648 | -1.7932 | 0.9119 | 0.3130 |
| `test` | `yN` | 7,582 | 0.0849 | 0.0546 | -1.8512 | 0.8996 | 0.2530 |
| `test` | `yF` | 7,582 | 0.1056 | 0.0675 | -1.9396 | 0.9095 | 0.3192 |
| `test` | `yT` | 7,582 | 0.1540 | 0.1011 | -1.3935 | 0.9280 | 0.4836 |
| `test` | `sigma_N` | 7,582 | 0.1382 | 0.0634 | -0.5559 | 0.8812 | 0.3062 |
| `test` | `sigma_F` | 7,582 | 0.0386 | 0.0206 | -2.9035 | 0.9156 | 0.1337 |
| `test` | `sigma_T` | 7,582 | 0.0640 | 0.0372 | -2.3758 | 0.9300 | 0.2264 |
| `test` | `delta_yN` | 7,582 | 0.0881 | 0.0576 | -1.8473 | 0.9036 | 0.2581 |
| `test` | `delta_yF` | 7,582 | 0.1111 | 0.0719 | -1.9158 | 0.9168 | 0.3345 |
| `test` | `delta_yT` | 7,582 | 0.1731 | 0.1096 | -1.3561 | 0.9230 | 0.5023 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure Neural ODE v1 prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.6500 | 0.0519 | 0.0844 | 1.0115 |
| `yF` | 0.8000 | 0.0691 | 0.1070 | 1.0079 |
| `yT` | 0.9000 | 0.1153 | 0.1679 | 1.0113 |
| `sigma_N` | 0.0000 | 0.0524 | 0.1194 | 1.0009 |
| `sigma_F` | 0.3500 | 0.0224 | 0.0486 | 1.0142 |
| `sigma_T` | 0.8000 | 0.0437 | 0.0729 | 1.0274 |
| `delta_yN` | 1.0000 | 0.0550 | 0.0885 | 1.0017 |
| `delta_yF` | 1.0000 | 0.0730 | 0.1125 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1266 | 0.1904 | 1.0000 |

## Persistence Comparison

Positive relative improvement means PIPE Neural ODE v1 beats the one-step persistence baseline.

| split | target | Neural ODE v1 RMSE | persistence RMSE | RMSE rel improvement | Neural ODE v1 MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1064 | 0.1475 | 0.2786 | 0.0648 | 0.0841 | 0.2289 |
| `train` | `all` | 0.0873 | 0.1248 | 0.3008 | 0.0467 | 0.0612 | 0.2375 |
| `validation` | `all` | 0.1102 | 0.1529 | 0.2792 | 0.0677 | 0.0870 | 0.2218 |

## Outputs

- Model: `models/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_model_v1.pt`
- Checkpoint: `models/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_checkpoint_v1.pt`
- Metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_metrics.csv`
- Persistence metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_persistence_comparison.csv`
- Output blend weights: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_output_blend_weights.csv`
- Output blend search: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_output_blend_search.csv`
- Training curve: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_training_curve.csv`
- Prediction examples: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_prediction_examples.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_manifest.json`
