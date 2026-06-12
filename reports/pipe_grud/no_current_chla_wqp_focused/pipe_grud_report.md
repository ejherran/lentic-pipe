# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-06-12T22:46:01.317935+00:00`
Started at UTC: `2026-06-12T22:45:46.395166+00:00`
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
| `train` | 112,470 | 112,470 |
| `validation` | 7,079 | 7,079 |
| `test` | 7,582 | 7,582 |

## Best Epoch

- Epoch: `6`
- Selection metric: `balanced`
- Selection objective: `0.7449`
- Validation loss: `-0.9998`
- Validation RMSE all: `0.1632`
- Validation MAE all: `0.1116`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 112,470 | 0.1401 | 0.0913 | -1.7268 | 0.9283 | 0.4479 |
| `train` | `yN` | 112,470 | 0.0715 | 0.0258 | -2.5413 | 0.9449 | 0.1792 |
| `train` | `yF` | 112,470 | 0.1480 | 0.0962 | -1.4197 | 0.9004 | 0.4873 |
| `train` | `yT` | 112,470 | 0.3023 | 0.2534 | -0.6958 | 0.9100 | 0.9891 |
| `train` | `sigma_N` | 112,470 | 0.0748 | 0.0174 | -2.5436 | 0.9645 | 0.1832 |
| `train` | `sigma_F` | 112,470 | 0.0808 | 0.0439 | -1.9567 | 0.9446 | 0.2913 |
| `train` | `sigma_T` | 112,470 | 0.1333 | 0.1006 | -1.5122 | 0.9427 | 0.4539 |
| `train` | `delta_yN` | 112,470 | 0.0723 | 0.0316 | -2.4889 | 0.9452 | 0.1877 |
| `train` | `delta_yF` | 112,470 | 0.1471 | 0.1009 | -1.4221 | 0.9046 | 0.4886 |
| `train` | `delta_yT` | 112,470 | 0.2308 | 0.1519 | -0.9605 | 0.8980 | 0.7711 |
| `validation` | `all` | 7,079 | 0.1632 | 0.1116 | -0.7551 | 0.8678 | 0.4801 |
| `validation` | `yN` | 7,079 | 0.1151 | 0.0729 | -0.4309 | 0.7276 | 0.2106 |
| `validation` | `yF` | 7,079 | 0.1435 | 0.1000 | -1.4319 | 0.9198 | 0.5165 |
| `validation` | `yT` | 7,079 | 0.2979 | 0.2440 | -0.7088 | 0.9168 | 1.0165 |
| `validation` | `sigma_N` | 7,079 | 0.1459 | 0.0587 | 1.6105 | 0.8976 | 0.2157 |
| `validation` | `sigma_F` | 7,079 | 0.0822 | 0.0447 | -1.9481 | 0.9664 | 0.3171 |
| `validation` | `sigma_T` | 7,079 | 0.1752 | 0.1327 | -1.0662 | 0.8551 | 0.4861 |
| `validation` | `delta_yN` | 7,079 | 0.1180 | 0.0775 | -0.5131 | 0.7334 | 0.2200 |
| `validation` | `delta_yF` | 7,079 | 0.1432 | 0.1025 | -1.4270 | 0.9226 | 0.5231 |
| `validation` | `delta_yT` | 7,079 | 0.2475 | 0.1711 | -0.8804 | 0.8706 | 0.8155 |
| `test` | `all` | 7,582 | 0.1525 | 0.1046 | -0.9010 | 0.8857 | 0.4914 |
| `test` | `yN` | 7,582 | 0.1244 | 0.0817 | -0.3798 | 0.7367 | 0.2253 |
| `test` | `yF` | 7,582 | 0.1365 | 0.0938 | -1.4589 | 0.9257 | 0.5257 |
| `test` | `yT` | 7,582 | 0.2808 | 0.2247 | -0.7593 | 0.9284 | 1.0187 |
| `test` | `sigma_N` | 7,582 | 0.1451 | 0.0634 | 0.8786 | 0.8726 | 0.2291 |
| `test` | `sigma_F` | 7,582 | 0.0748 | 0.0405 | -1.9707 | 0.9755 | 0.3263 |
| `test` | `sigma_T` | 7,582 | 0.1335 | 0.1059 | -1.4775 | 0.9395 | 0.4956 |
| `test` | `delta_yN` | 7,582 | 0.1271 | 0.0867 | -0.4827 | 0.7352 | 0.2340 |
| `test` | `delta_yF` | 7,582 | 0.1371 | 0.0974 | -1.4452 | 0.9319 | 0.5353 |
| `test` | `delta_yT` | 7,582 | 0.2129 | 0.1472 | -1.0135 | 0.9259 | 0.8330 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.6500 | 0.0729 | 0.1151 | 1.0085 |
| `yF` | 0.8000 | 0.1000 | 0.1435 | 1.0042 |
| `yT` | 0.8000 | 0.2440 | 0.2979 | 1.0000 |
| `sigma_N` | 0.0000 | 0.0587 | 0.1459 | 1.0007 |
| `sigma_F` | 0.8000 | 0.0447 | 0.0822 | 1.0076 |
| `sigma_T` | 0.9000 | 0.1327 | 0.1752 | 1.0121 |
| `delta_yN` | 1.0000 | 0.0775 | 0.1180 | 1.0043 |
| `delta_yF` | 1.0000 | 0.1025 | 0.1432 | 1.0031 |
| `delta_yT` | 1.0000 | 0.1711 | 0.2475 | 1.0000 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1525 | 0.2236 | 0.3182 | 0.1046 | 0.1512 | 0.3085 |
| `train` | `all` | 0.1401 | 0.2082 | 0.3271 | 0.0913 | 0.1327 | 0.3121 |
| `validation` | `all` | 0.1632 | 0.2230 | 0.2684 | 0.1116 | 0.1471 | 0.2419 |

## Outputs

- Model: `models/pipe_grud/no_current_chla_wqp_focused/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/no_current_chla_wqp_focused/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/no_current_chla_wqp_focused/pipe_grud_manifest.json`
