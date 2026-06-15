# PIPE Neural ODE History Training Report v1

Generated at UTC: `2026-06-15T20:29:55.551914+00:00`
Started at UTC: `2026-06-15T20:29:33.107201+00:00`
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
- Epochs requested: `20`
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

- Epoch: `20`
- Selection metric: `balanced`
- Selection objective: `0.8086`
- Validation loss: `-2.0732`
- Validation RMSE all: `0.1187`
- Validation MAE all: `0.0731`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 112,470 | 0.0943 | 0.0498 | -2.6095 | 0.9126 | 0.2458 |
| `train` | `yN` | 112,470 | 0.0423 | 0.0139 | -3.9850 | 0.9677 | 0.0787 |
| `train` | `yF` | 112,470 | 0.1104 | 0.0642 | -1.8996 | 0.8780 | 0.2973 |
| `train` | `yT` | 112,470 | 0.1930 | 0.1041 | -1.1641 | 0.8547 | 0.5296 |
| `train` | `sigma_N` | 112,470 | 0.0537 | 0.0111 | -3.8769 | 0.9766 | 0.0883 |
| `train` | `sigma_F` | 112,470 | 0.0376 | 0.0171 | -2.8900 | 0.9117 | 0.1107 |
| `train` | `sigma_T` | 112,470 | 0.0576 | 0.0276 | -2.5482 | 0.8739 | 0.1507 |
| `train` | `delta_yN` | 112,470 | 0.0441 | 0.0154 | -3.9528 | 0.9684 | 0.0806 |
| `train` | `delta_yF` | 112,470 | 0.1143 | 0.0698 | -1.9104 | 0.8932 | 0.3125 |
| `train` | `delta_yT` | 112,470 | 0.1951 | 0.1256 | -1.2590 | 0.8888 | 0.5640 |
| `validation` | `all` | 7,079 | 0.1187 | 0.0731 | -1.7549 | 0.9120 | 0.4240 |
| `validation` | `yN` | 7,079 | 0.0867 | 0.0524 | -2.0650 | 0.9400 | 0.3699 |
| `validation` | `yF` | 7,079 | 0.1134 | 0.0719 | -1.5740 | 0.9469 | 0.5273 |
| `validation` | `yT` | 7,079 | 0.1989 | 0.1203 | -1.0988 | 0.8282 | 0.5604 |
| `validation` | `sigma_N` | 7,079 | 0.1194 | 0.0524 | -1.8120 | 0.9401 | 0.4204 |
| `validation` | `sigma_F` | 7,079 | 0.0496 | 0.0223 | -2.5501 | 0.9164 | 0.1672 |
| `validation` | `sigma_T` | 7,079 | 0.0795 | 0.0422 | -2.0142 | 0.8664 | 0.2611 |
| `validation` | `delta_yN` | 7,079 | 0.0935 | 0.0598 | -2.0233 | 0.9408 | 0.3824 |
| `validation` | `delta_yF` | 7,079 | 0.1181 | 0.0803 | -1.5584 | 0.9541 | 0.5395 |
| `validation` | `delta_yT` | 7,079 | 0.2092 | 0.1567 | -1.0983 | 0.8751 | 0.5879 |
| `test` | `all` | 7,582 | 0.1148 | 0.0710 | -1.5463 | 0.9173 | 0.4344 |
| `test` | `yN` | 7,582 | 0.0871 | 0.0551 | -1.4630 | 0.9185 | 0.3840 |
| `test` | `yF` | 7,582 | 0.1111 | 0.0705 | -1.5729 | 0.9561 | 0.5403 |
| `test` | `yT` | 7,582 | 0.1860 | 0.1092 | -1.1866 | 0.8630 | 0.5654 |
| `test` | `sigma_N` | 7,582 | 0.1382 | 0.0634 | -0.6779 | 0.8995 | 0.4388 |
| `test` | `sigma_F` | 7,582 | 0.0394 | 0.0203 | -2.6491 | 0.9143 | 0.1716 |
| `test` | `sigma_T` | 7,582 | 0.0699 | 0.0366 | -2.1139 | 0.9189 | 0.2694 |
| `test` | `delta_yN` | 7,582 | 0.0938 | 0.0639 | -1.4907 | 0.9247 | 0.4013 |
| `test` | `delta_yF` | 7,582 | 0.1157 | 0.0797 | -1.5582 | 0.9644 | 0.5511 |
| `test` | `delta_yT` | 7,582 | 0.1921 | 0.1406 | -1.2043 | 0.8962 | 0.5878 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure Neural ODE v1 prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.8000 | 0.0524 | 0.0867 | 1.0064 |
| `yF` | 0.6500 | 0.0719 | 0.1134 | 1.0151 |
| `yT` | 0.2000 | 0.1203 | 0.1989 | 1.0455 |
| `sigma_N` | 0.0000 | 0.0524 | 0.1194 | 1.0012 |
| `sigma_F` | 0.1000 | 0.0223 | 0.0496 | 1.0066 |
| `sigma_T` | 0.1000 | 0.0422 | 0.0795 | 1.0172 |
| `delta_yN` | 1.0000 | 0.0598 | 0.0935 | 1.0013 |
| `delta_yF` | 1.0000 | 0.0803 | 0.1181 | 1.0059 |
| `delta_yT` | 1.0000 | 0.1567 | 0.2092 | 1.0034 |

## Persistence Comparison

Positive relative improvement means PIPE Neural ODE v1 beats the one-step persistence baseline.

| split | target | Neural ODE v1 RMSE | persistence RMSE | RMSE rel improvement | Neural ODE v1 MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1148 | 0.1475 | 0.2216 | 0.0710 | 0.0841 | 0.1550 |
| `train` | `all` | 0.0943 | 0.1248 | 0.2447 | 0.0498 | 0.0612 | 0.1857 |
| `validation` | `all` | 0.1187 | 0.1529 | 0.2234 | 0.0731 | 0.0870 | 0.1595 |

## Outputs

- Model: `models/pipe_neural_ode/adaptive_wqp_focused_history_v1_extended/pipe_neural_ode_history_model_v1.pt`
- Checkpoint: `models/pipe_neural_ode/adaptive_wqp_focused_history_v1_extended/pipe_neural_ode_history_checkpoint_v1.pt`
- Metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_extended/pipe_neural_ode_history_metrics.csv`
- Persistence metrics: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_extended/pipe_neural_ode_history_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_extended/pipe_neural_ode_history_persistence_comparison.csv`
- Output blend weights: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_extended/pipe_neural_ode_history_output_blend_weights.csv`
- Output blend search: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_extended/pipe_neural_ode_history_output_blend_search.csv`
- Training curve: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_extended/pipe_neural_ode_history_training_curve.csv`
- Prediction examples: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_extended/pipe_neural_ode_history_prediction_examples.csv`
- Manifest: `reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_extended/pipe_neural_ode_history_manifest.json`
