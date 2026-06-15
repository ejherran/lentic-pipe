# PIPE Neural ODE History Training Report v1

Generated at UTC: `2026-06-15T20:24:41.187890+00:00`
Started at UTC: `2026-06-15T20:24:39.739866+00:00`
Status: `completed`

## Scope

This step trains a history-encoded Neural ODE variant over the frozen PIPE sequence schema.
A GRU encoder summarizes the recent PIPE history, initializes a latent ODE, and decodes the next fuzzy state.
The v1 runner is one-step; recursive rollout support is a downstream gate after one-step validation.
Synthetic smoke mode: `True`.

## Configuration

- History length: `6`
- History hidden dimension: `64`
- History layers: `1`
- Latent dimension: `48`
- Dynamics hidden dimension: `64`
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
- Epochs requested: `10`
- Batch size: `128`
- Learning rate: `0.001`
- Device: `auto`

## Windows

| split | available | sampled/used |
|---|---:|---:|
| `train` | 304 | 304 |
| `validation` | 304 | 304 |
| `test` | 304 | 304 |

## Best Epoch

- Epoch: `7`
- Selection metric: `balanced`
- Selection objective: `0.4414`
- Validation loss: `-1.0480`
- Validation RMSE all: `0.0054`
- Validation MAE all: `0.0041`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 304 | 0.0052 | 0.0041 | -0.6966 | 1.0000 | 1.7154 |
| `train` | `yN` | 304 | 0.0069 | 0.0058 | -0.5869 | 1.0000 | 1.8320 |
| `train` | `yF` | 304 | 0.0050 | 0.0040 | -0.8453 | 1.0000 | 1.4187 |
| `train` | `yT` | 304 | 0.0095 | 0.0063 | -1.4435 | 1.0000 | 0.7866 |
| `train` | `sigma_N` | 304 | 0.0010 | 0.0009 | -0.2667 | 1.0000 | 2.5216 |
| `train` | `sigma_F` | 304 | 0.0012 | 0.0011 | -0.5764 | 1.0000 | 1.8528 |
| `train` | `sigma_T` | 304 | 0.0012 | 0.0010 | -0.5536 | 1.0000 | 1.8951 |
| `train` | `delta_yN` | 304 | 0.0059 | 0.0046 | -0.8273 | 1.0000 | 1.4435 |
| `train` | `delta_yF` | 304 | 0.0067 | 0.0052 | -0.6799 | 1.0000 | 1.6708 |
| `train` | `delta_yT` | 304 | 0.0095 | 0.0078 | -0.4895 | 1.0000 | 2.0179 |
| `validation` | `all` | 304 | 0.0054 | 0.0041 | -0.7048 | 1.0000 | 1.7029 |
| `validation` | `yN` | 304 | 0.0070 | 0.0056 | -0.5942 | 1.0000 | 1.8185 |
| `validation` | `yF` | 304 | 0.0054 | 0.0043 | -0.8546 | 1.0000 | 1.4054 |
| `validation` | `yT` | 304 | 0.0093 | 0.0057 | -1.4615 | 1.0000 | 0.7723 |
| `validation` | `sigma_N` | 304 | 0.0012 | 0.0011 | -0.2703 | 1.0000 | 2.5125 |
| `validation` | `sigma_F` | 304 | 0.0013 | 0.0010 | -0.5843 | 1.0000 | 1.8380 |
| `validation` | `sigma_T` | 304 | 0.0013 | 0.0011 | -0.5593 | 1.0000 | 1.8841 |
| `validation` | `delta_yN` | 304 | 0.0050 | 0.0038 | -0.8376 | 1.0000 | 1.4285 |
| `validation` | `delta_yF` | 304 | 0.0073 | 0.0057 | -0.6876 | 1.0000 | 1.6578 |
| `validation` | `delta_yT` | 304 | 0.0104 | 0.0085 | -0.4937 | 1.0000 | 2.0092 |
| `test` | `all` | 304 | 0.0051 | 0.0039 | -0.6973 | 1.0000 | 1.7141 |
| `test` | `yN` | 304 | 0.0067 | 0.0058 | -0.5883 | 1.0000 | 1.8295 |
| `test` | `yF` | 304 | 0.0053 | 0.0041 | -0.8440 | 1.0000 | 1.4203 |
| `test` | `yT` | 304 | 0.0086 | 0.0052 | -1.4459 | 1.0000 | 0.7844 |
| `test` | `sigma_N` | 304 | 0.0011 | 0.0009 | -0.2670 | 1.0000 | 2.5208 |
| `test` | `sigma_F` | 304 | 0.0011 | 0.0009 | -0.5772 | 1.0000 | 1.8512 |
| `test` | `sigma_T` | 304 | 0.0011 | 0.0009 | -0.5531 | 1.0000 | 1.8959 |
| `test` | `delta_yN` | 304 | 0.0061 | 0.0049 | -0.8285 | 1.0000 | 1.4415 |
| `test` | `delta_yF` | 304 | 0.0077 | 0.0060 | -0.6808 | 1.0000 | 1.6691 |
| `test` | `delta_yT` | 304 | 0.0082 | 0.0068 | -0.4914 | 1.0000 | 2.0141 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure Neural ODE v1 prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 1.0000 | 0.0056 | 0.0070 | 1.0000 |
| `yF` | 0.5000 | 0.0043 | 0.0054 | 1.0023 |
| `yT` | 1.0000 | 0.0057 | 0.0093 | 1.0000 |
| `sigma_N` | 0.0000 | 0.0011 | 0.0012 | 1.0000 |
| `sigma_F` | 0.0000 | 0.0010 | 0.0013 | 1.0000 |
| `sigma_T` | 0.0000 | 0.0011 | 0.0013 | 1.0000 |
| `delta_yN` | 1.0000 | 0.0038 | 0.0050 | 1.0000 |
| `delta_yF` | 0.0000 | 0.0057 | 0.0073 | 1.0000 |
| `delta_yT` | 0.9000 | 0.0085 | 0.0104 | 1.0000 |

## Persistence Comparison

Positive relative improvement means PIPE Neural ODE v1 beats the one-step persistence baseline.

| split | target | Neural ODE v1 RMSE | persistence RMSE | RMSE rel improvement | Neural ODE v1 MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.0051 | 0.0117 | 0.5665 | 0.0039 | 0.0090 | 0.5604 |
| `train` | `all` | 0.0052 | 0.0118 | 0.5579 | 0.0041 | 0.0089 | 0.5437 |
| `validation` | `all` | 0.0054 | 0.0121 | 0.5576 | 0.0041 | 0.0093 | 0.5595 |

## Outputs

- Model: `models/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_model_v1.pt`
- Checkpoint: `models/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_checkpoint_v1.pt`
- Metrics: `reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_metrics.csv`
- Persistence metrics: `reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_persistence_comparison.csv`
- Output blend weights: `reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_output_blend_weights.csv`
- Output blend search: `reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_output_blend_search.csv`
- Training curve: `reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_training_curve.csv`
- Prediction examples: `reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_prediction_examples.csv`
- Manifest: `reports/pipe_neural_ode/history_v1_synthetic_smoke/pipe_neural_ode_history_manifest.json`
