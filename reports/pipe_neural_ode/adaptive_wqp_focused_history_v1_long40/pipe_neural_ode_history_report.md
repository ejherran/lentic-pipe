# PIPE Neural ODE History Training Report v1

Generated at UTC: `2026-06-15T20:35:48.607363+00:00`
Started at UTC: `2026-06-15T20:35:05.549678+00:00`
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
- Epochs requested: `40`
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

- Epoch: `40`
- Selection metric: `balanced`
- Selection objective: `0.7703`
- Validation loss: `-2.2480`
- Validation RMSE all: `0.1128`
- Validation MAE all: `0.0698`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 112,470 | 0.0900 | 0.0478 | -2.8372 | 0.9424 | 0.2496 |
| `train` | `yN` | 112,470 | 0.0420 | 0.0129 | -4.2004 | 0.9804 | 0.0818 |
| `train` | `yF` | 112,470 | 0.1079 | 0.0633 | -2.0815 | 0.9179 | 0.3364 |
| `train` | `yT` | 112,470 | 0.1669 | 0.1017 | -1.5416 | 0.9230 | 0.4876 |
| `train` | `sigma_N` | 112,470 | 0.0537 | 0.0111 | -4.1159 | 0.9830 | 0.0915 |
| `train` | `sigma_F` | 112,470 | 0.0375 | 0.0170 | -2.9987 | 0.9210 | 0.1179 |
| `train` | `sigma_T` | 112,470 | 0.0559 | 0.0278 | -2.8290 | 0.9158 | 0.1607 |
| `train` | `delta_yN` | 112,470 | 0.0427 | 0.0135 | -4.1981 | 0.9823 | 0.0839 |
| `train` | `delta_yF` | 112,470 | 0.1134 | 0.0683 | -2.0732 | 0.9287 | 0.3559 |
| `train` | `delta_yT` | 112,470 | 0.1900 | 0.1144 | -1.4966 | 0.9291 | 0.5306 |
| `validation` | `all` | 7,079 | 0.1128 | 0.0698 | -1.8714 | 0.9216 | 0.3699 |
| `validation` | `yN` | 7,079 | 0.0860 | 0.0522 | -2.2086 | 0.9335 | 0.2930 |
| `validation` | `yF` | 7,079 | 0.1115 | 0.0713 | -1.8055 | 0.9513 | 0.4405 |
| `validation` | `yT` | 7,079 | 0.1734 | 0.1207 | -1.2243 | 0.8781 | 0.5079 |
| `validation` | `sigma_N` | 7,079 | 0.1194 | 0.0524 | -1.8088 | 0.9378 | 0.3529 |
| `validation` | `sigma_F` | 7,079 | 0.0495 | 0.0223 | -2.6851 | 0.9247 | 0.1578 |
| `validation` | `sigma_T` | 7,079 | 0.0770 | 0.0431 | -1.9643 | 0.8859 | 0.2489 |
| `validation` | `delta_yN` | 7,079 | 0.0899 | 0.0565 | -2.2045 | 0.9376 | 0.3008 |
| `validation` | `delta_yF` | 7,079 | 0.1157 | 0.0772 | -1.7626 | 0.9631 | 0.4779 |
| `validation` | `delta_yT` | 7,079 | 0.1928 | 0.1331 | -1.1795 | 0.8828 | 0.5493 |
| `test` | `all` | 7,582 | 0.1093 | 0.0677 | -1.7746 | 0.9282 | 0.3748 |
| `test` | `yN` | 7,582 | 0.0866 | 0.0552 | -1.8359 | 0.9283 | 0.3082 |
| `test` | `yF` | 7,582 | 0.1093 | 0.0700 | -1.7883 | 0.9563 | 0.4579 |
| `test` | `yT` | 7,582 | 0.1606 | 0.1076 | -1.4658 | 0.9044 | 0.4895 |
| `test` | `sigma_N` | 7,582 | 0.1382 | 0.0634 | -0.8291 | 0.8973 | 0.3605 |
| `test` | `sigma_F` | 7,582 | 0.0393 | 0.0203 | -2.7634 | 0.9306 | 0.1627 |
| `test` | `sigma_T` | 7,582 | 0.0679 | 0.0369 | -2.3132 | 0.9318 | 0.2505 |
| `test` | `delta_yN` | 7,582 | 0.0900 | 0.0599 | -1.8407 | 0.9339 | 0.3175 |
| `test` | `delta_yF` | 7,582 | 0.1137 | 0.0765 | -1.7369 | 0.9643 | 0.4954 |
| `test` | `delta_yT` | 7,582 | 0.1779 | 0.1192 | -1.3987 | 0.9066 | 0.5306 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure Neural ODE v1 prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.6500 | 0.0522 | 0.0860 | 1.0091 |
| `yF` | 0.6500 | 0.0713 | 0.1115 | 1.0156 |
| `yT` | 0.8000 | 0.1207 | 0.1734 | 1.0284 |
| `sigma_N` | 0.0000 | 0.0524 | 0.1194 | 1.0000 |
| `sigma_F` | 0.1000 | 0.0223 | 0.0495 | 1.0120 |
| `sigma_T` | 0.5000 | 0.0431 | 0.0770 | 1.0265 |
| `delta_yN` | 1.0000 | 0.0565 | 0.0899 | 1.0036 |
| `delta_yF` | 1.0000 | 0.0772 | 0.1157 | 1.0009 |
| `delta_yT` | 1.0000 | 0.1331 | 0.1928 | 1.0000 |

## Persistence Comparison

Positive relative improvement means PIPE Neural ODE v1 beats the one-step persistence baseline.

| split | target | Neural ODE v1 RMSE | persistence RMSE | RMSE rel improvement | Neural ODE v1 MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1093 | 0.1475 | 0.2593 | 0.0677 | 0.0841 | 0.1952 |
| `train` | `all` | 0.0900 | 0.1248 | 0.2788 | 0.0478 | 0.0612 | 0.2195 |
| `validation` | `all` | 0.1128 | 0.1529 | 0.2621 | 0.0698 | 0.0870 | 0.1972 |

## Outputs

- Model: `models/pipe_neural_ode/adaptive_wqp_focused_history_v1_long40/pipe_neural_ode_history_model_v1.pt`
- Checkpoint: `models/pipe_neural_ode/adaptive_wqp_focused_history_v1_long40/pipe_neural_ode_history_checkpoint_v1.pt`
- Metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long40/pipe_neural_ode_history_metrics.csv`
- Persistence metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long40/pipe_neural_ode_history_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long40/pipe_neural_ode_history_persistence_comparison.csv`
- Output blend weights: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long40/pipe_neural_ode_history_output_blend_weights.csv`
- Output blend search: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long40/pipe_neural_ode_history_output_blend_search.csv`
- Training curve: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long40/pipe_neural_ode_history_training_curve.csv`
- Prediction examples: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long40/pipe_neural_ode_history_prediction_examples.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long40/pipe_neural_ode_history_manifest.json`
