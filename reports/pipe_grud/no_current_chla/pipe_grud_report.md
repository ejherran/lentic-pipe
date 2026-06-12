# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-06-12T19:04:41.911337+00:00`
Started at UTC: `2026-06-12T19:03:56.604493+00:00`
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
- Epochs requested: `20`
- Batch size: `2048`
- Learning rate: `0.001`
- Device: `auto`

## Windows

| split | available | sampled/used |
|---|---:|---:|
| `train` | 378,557 | 378,557 |
| `validation` | 22,087 | 22,087 |
| `test` | 17,420 | 17,420 |

## Best Epoch

- Epoch: `19`
- Selection metric: `balanced`
- Selection objective: `0.6759`
- Validation loss: `-3.0306`
- Validation RMSE all: `0.1345`
- Validation MAE all: `0.0822`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 378,557 | 0.1190 | 0.0737 | -2.8906 | 0.9541 | 0.3530 |
| `train` | `yN` | 378,557 | 0.0400 | 0.0092 | -4.3416 | 0.9866 | 0.0606 |
| `train` | `yF` | 378,557 | 0.0816 | 0.0301 | -3.2459 | 0.9560 | 0.1759 |
| `train` | `yT` | 378,557 | 0.3639 | 0.3122 | -0.5132 | 0.9086 | 1.2238 |
| `train` | `sigma_N` | 378,557 | 0.0412 | 0.0052 | -4.3852 | 0.9910 | 0.0644 |
| `train` | `sigma_F` | 378,557 | 0.0459 | 0.0127 | -3.2624 | 0.9843 | 0.1557 |
| `train` | `sigma_T` | 378,557 | 0.1118 | 0.0833 | -1.9394 | 0.9154 | 0.3301 |
| `train` | `delta_yN` | 378,557 | 0.0391 | 0.0098 | -4.3088 | 0.9873 | 0.0640 |
| `train` | `delta_yF` | 378,557 | 0.0800 | 0.0334 | -3.1949 | 0.9630 | 0.2016 |
| `train` | `delta_yT` | 378,557 | 0.2677 | 0.1675 | -0.8239 | 0.8947 | 0.9005 |
| `validation` | `all` | 22,087 | 0.1345 | 0.0822 | -2.5689 | 0.9446 | 0.4037 |
| `validation` | `yN` | 22,087 | 0.0664 | 0.0252 | -3.5461 | 0.9257 | 0.0935 |
| `validation` | `yF` | 22,087 | 0.0841 | 0.0345 | -3.3375 | 0.9869 | 0.2688 |
| `validation` | `yT` | 22,087 | 0.3501 | 0.2993 | -0.5516 | 0.9223 | 1.2251 |
| `validation` | `sigma_N` | 22,087 | 0.0853 | 0.0197 | -2.9962 | 0.9704 | 0.0980 |
| `validation` | `sigma_F` | 22,087 | 0.0489 | 0.0146 | -3.2577 | 0.9942 | 0.2226 |
| `validation` | `sigma_T` | 22,087 | 0.1437 | 0.1029 | -1.8066 | 0.8969 | 0.4011 |
| `validation` | `delta_yN` | 22,087 | 0.0646 | 0.0259 | -3.6519 | 0.9330 | 0.0970 |
| `validation` | `delta_yF` | 22,087 | 0.0838 | 0.0380 | -3.2086 | 0.9931 | 0.3129 |
| `validation` | `delta_yT` | 22,087 | 0.2837 | 0.1795 | -0.7636 | 0.8792 | 0.9143 |
| `test` | `all` | 17,420 | 0.1359 | 0.0840 | -2.3102 | 0.9391 | 0.4512 |
| `test` | `yN` | 17,420 | 0.0834 | 0.0364 | -2.9881 | 0.8964 | 0.1261 |
| `test` | `yF` | 17,420 | 0.0910 | 0.0414 | -3.0058 | 0.9823 | 0.3594 |
| `test` | `yT` | 17,420 | 0.3354 | 0.2893 | -0.5855 | 0.9381 | 1.2136 |
| `test` | `sigma_N` | 17,420 | 0.0962 | 0.0278 | -2.6470 | 0.9492 | 0.1321 |
| `test` | `sigma_F` | 17,420 | 0.0515 | 0.0175 | -2.9902 | 0.9930 | 0.2903 |
| `test` | `sigma_T` | 17,420 | 0.1576 | 0.1135 | -1.6496 | 0.8742 | 0.4726 |
| `test` | `delta_yN` | 17,420 | 0.0814 | 0.0371 | -3.1301 | 0.9060 | 0.1306 |
| `test` | `delta_yF` | 17,420 | 0.0910 | 0.0459 | -2.8746 | 0.9896 | 0.4206 |
| `test` | `delta_yT` | 17,420 | 0.2359 | 0.1470 | -0.9210 | 0.9228 | 0.9158 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.5000 | 0.0252 | 0.0664 | 1.0389 |
| `yF` | 0.6500 | 0.0345 | 0.0841 | 1.0156 |
| `yT` | 1.0000 | 0.2993 | 0.3501 | 1.0000 |
| `sigma_N` | 0.0000 | 0.0197 | 0.0853 | 1.0004 |
| `sigma_F` | 0.0000 | 0.0146 | 0.0489 | 1.0094 |
| `sigma_T` | 1.0000 | 0.1029 | 0.1437 | 1.0000 |
| `delta_yN` | 0.9000 | 0.0259 | 0.0646 | 1.0060 |
| `delta_yF` | 1.0000 | 0.0380 | 0.0838 | 1.0052 |
| `delta_yT` | 1.0000 | 0.1795 | 0.2837 | 1.0013 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1359 | 0.1963 | 0.3075 | 0.0840 | 0.1299 | 0.3532 |
| `train` | `all` | 0.1190 | 0.1764 | 0.3252 | 0.0737 | 0.1193 | 0.3824 |
| `validation` | `all` | 0.1345 | 0.1915 | 0.2974 | 0.0822 | 0.1266 | 0.3508 |

## Outputs

- Model: `models/pipe_grud/no_current_chla/pipe_grud_model_v0.pt`
- Checkpoint: `models/pipe_grud/no_current_chla/pipe_grud_checkpoint_v0.pt`
- Metrics: `reports/pipe_grud/no_current_chla/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/no_current_chla/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/no_current_chla/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/no_current_chla/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/no_current_chla/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/no_current_chla/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/no_current_chla/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/no_current_chla/pipe_grud_manifest.json`
