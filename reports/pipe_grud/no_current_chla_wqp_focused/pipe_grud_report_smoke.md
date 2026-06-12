# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-06-12T22:20:43.232915+00:00`
Started at UTC: `2026-06-12T22:20:41.065833+00:00`
Status: `completed`

## Scope

This step trains the minimal probabilistic temporal model over the frozen PIPE sequence dataset.
It predicts the next 9-dimensional fuzzy state vector and estimates diagonal Gaussian uncertainty.
Checkpoint selection evaluates the same blended output used by the final model.

## Configuration

- History length: `12`
- Hidden dimension: `96`
- GRU layers: `1`
- Residual mode: `add_last`
- Auxiliary MSE weight: `1.0`
- Checkpoint selection metric: `balanced`
- Output blend selection metric: `balanced`
- Epochs requested: `2`
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

- Epoch: `1`
- Selection metric: `balanced`
- Selection objective: `0.9801`
- Validation loss: `-0.9049`
- Validation RMSE all: `0.2144`
- Validation MAE all: `0.1470`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 50,000 | 0.1983 | 0.1303 | -0.6889 | 0.9772 | 1.4191 |
| `train` | `yN` | 50,000 | 0.0790 | 0.0221 | -1.0243 | 0.9991 | 1.1537 |
| `train` | `yF` | 50,000 | 0.1631 | 0.0952 | -0.7343 | 0.9972 | 1.4776 |
| `train` | `yT` | 50,000 | 0.3695 | 0.3065 | -0.4836 | 0.9108 | 1.1084 |
| `train` | `sigma_N` | 50,000 | 0.0751 | 0.0174 | -0.6002 | 1.0000 | 1.7892 |
| `train` | `sigma_F` | 50,000 | 0.0832 | 0.0423 | -0.4675 | 1.0000 | 2.0430 |
| `train` | `sigma_T` | 50,000 | 0.3171 | 0.2903 | -0.5669 | 0.9985 | 1.4247 |
| `train` | `delta_yN` | 50,000 | 0.1326 | 0.0477 | -1.0304 | 0.9864 | 1.0891 |
| `train` | `delta_yF` | 50,000 | 0.2568 | 0.1615 | -0.6405 | 0.9772 | 1.4699 |
| `train` | `delta_yT` | 50,000 | 0.3088 | 0.1894 | -0.6527 | 0.9259 | 1.2162 |
| `validation` | `all` | 7,079 | 0.2144 | 0.1470 | -0.6693 | 0.9771 | 1.4457 |
| `validation` | `yN` | 7,079 | 0.1258 | 0.0737 | -0.9619 | 0.9972 | 1.1831 |
| `validation` | `yF` | 7,079 | 0.1577 | 0.1026 | -0.7288 | 0.9997 | 1.4952 |
| `validation` | `yT` | 7,079 | 0.3291 | 0.2612 | -0.6116 | 0.9256 | 1.1365 |
| `validation` | `sigma_N` | 7,079 | 0.1459 | 0.0587 | -0.5573 | 1.0000 | 1.8201 |
| `validation` | `sigma_F` | 7,079 | 0.0856 | 0.0444 | -0.4561 | 1.0000 | 2.0661 |
| `validation` | `sigma_T` | 7,079 | 0.2886 | 0.2603 | -0.6055 | 0.9989 | 1.4520 |
| `validation` | `delta_yN` | 7,079 | 0.2060 | 0.1282 | -0.8947 | 0.9723 | 1.1213 |
| `validation` | `delta_yF` | 7,079 | 0.2497 | 0.1712 | -0.6379 | 0.9849 | 1.4958 |
| `validation` | `delta_yT` | 7,079 | 0.3414 | 0.2227 | -0.5696 | 0.9152 | 1.2408 |
| `test` | `all` | 7,582 | 0.2135 | 0.1482 | -0.6669 | 0.9793 | 1.4459 |
| `test` | `yN` | 7,582 | 0.1373 | 0.0835 | -0.9473 | 0.9964 | 1.1870 |
| `test` | `yF` | 7,582 | 0.1493 | 0.0929 | -0.7345 | 0.9987 | 1.4955 |
| `test` | `yT` | 7,582 | 0.3474 | 0.2879 | -0.5573 | 0.9323 | 1.1358 |
| `test` | `sigma_N` | 7,582 | 0.1451 | 0.0634 | -0.5593 | 1.0000 | 1.8170 |
| `test` | `sigma_F` | 7,582 | 0.0778 | 0.0399 | -0.4563 | 1.0000 | 2.0688 |
| `test` | `sigma_T` | 7,582 | 0.2938 | 0.2654 | -0.5972 | 0.9988 | 1.4486 |
| `test` | `delta_yN` | 7,582 | 0.2224 | 0.1407 | -0.8627 | 0.9694 | 1.1218 |
| `test` | `delta_yF` | 7,582 | 0.2357 | 0.1539 | -0.6543 | 0.9831 | 1.4942 |
| `test` | `delta_yT` | 7,582 | 0.3130 | 0.2058 | -0.6334 | 0.9351 | 1.2442 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.0000 | 0.0737 | 0.1258 | 1.0070 |
| `yF` | 0.0000 | 0.1026 | 0.1577 | 1.0007 |
| `yT` | 1.0000 | 0.2612 | 0.3291 | 1.0000 |
| `sigma_N` | 0.0000 | 0.0587 | 0.1459 | 1.0000 |
| `sigma_F` | 0.0000 | 0.0444 | 0.0856 | 1.0000 |
| `sigma_T` | 0.5000 | 0.2603 | 0.2886 | 1.0256 |
| `delta_yN` | 1.0000 | 0.1282 | 0.2060 | 1.0048 |
| `delta_yF` | 1.0000 | 0.1712 | 0.2497 | 1.0000 |
| `delta_yT` | 0.8000 | 0.2227 | 0.3414 | 1.0069 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.2135 | 0.2236 | 0.0452 | 0.1482 | 0.1512 | 0.0204 |
| `train` | `all` | 0.1983 | 0.2082 | 0.0475 | 0.1303 | 0.1326 | 0.0180 |
| `validation` | `all` | 0.2144 | 0.2230 | 0.0387 | 0.1470 | 0.1471 | 0.0011 |

## Outputs

- Model: `models/pipe_grud/no_current_chla_wqp_focused/pipe_grud_model_smoke.pt`
- Checkpoint: `models/pipe_grud/no_current_chla_wqp_focused/pipe_grud_checkpoint_smoke.pt`
- Metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_metrics_smoke.csv`
- Persistence metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_persistence_metrics_smoke.csv`
- Persistence comparison: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_persistence_comparison_smoke.csv`
- Output blend weights: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_output_blend_weights_smoke.csv`
- Output blend search: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_output_blend_search_smoke.csv`
- Training curve: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_training_curve_smoke.csv`
- Prediction examples: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_prediction_examples_smoke.csv`
- Manifest: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_manifest_smoke.json`
