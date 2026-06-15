# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-06-15T16:48:44.673383+00:00`
Started at UTC: `2026-06-15T16:48:30.455123+00:00`
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

- Epoch: `19`
- Selection metric: `balanced`
- Selection objective: `0.7709`
- Validation loss: `-1.5606`
- Validation RMSE all: `0.1130`
- Validation MAE all: `0.0698`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 112,470 | 0.0903 | 0.0506 | -2.2207 | 0.9086 | 0.2719 |
| `train` | `yN` | 112,470 | 0.0413 | 0.0139 | -2.9850 | 0.9361 | 0.1052 |
| `train` | `yF` | 112,470 | 0.1078 | 0.0646 | -1.8120 | 0.8947 | 0.3259 |
| `train` | `yT` | 112,470 | 0.1846 | 0.1100 | -1.1970 | 0.8747 | 0.5776 |
| `train` | `sigma_N` | 112,470 | 0.0534 | 0.0119 | -2.7611 | 0.9635 | 0.1288 |
| `train` | `sigma_F` | 112,470 | 0.0376 | 0.0171 | -2.8686 | 0.9047 | 0.1151 |
| `train` | `sigma_T` | 112,470 | 0.0579 | 0.0275 | -2.4493 | 0.8797 | 0.1704 |
| `train` | `delta_yN` | 112,470 | 0.0437 | 0.0252 | -2.8826 | 0.9372 | 0.1104 |
| `train` | `delta_yF` | 112,470 | 0.1067 | 0.0671 | -1.8128 | 0.8997 | 0.3295 |
| `train` | `delta_yT` | 112,470 | 0.1800 | 0.1183 | -1.2177 | 0.8872 | 0.5839 |
| `validation` | `all` | 7,079 | 0.1130 | 0.0698 | -1.2705 | 0.8410 | 0.3031 |
| `validation` | `yN` | 7,079 | 0.0844 | 0.0534 | -0.8202 | 0.7216 | 0.1268 |
| `validation` | `yF` | 7,079 | 0.1114 | 0.0717 | -1.7370 | 0.9021 | 0.3697 |
| `validation` | `yT` | 7,079 | 0.1901 | 0.1226 | -1.1641 | 0.8753 | 0.6128 |
| `validation` | `sigma_N` | 7,079 | 0.1189 | 0.0526 | 0.6502 | 0.8272 | 0.1564 |
| `validation` | `sigma_F` | 7,079 | 0.0495 | 0.0223 | -2.5632 | 0.9049 | 0.1368 |
| `validation` | `sigma_T` | 7,079 | 0.0798 | 0.0420 | -1.8996 | 0.8152 | 0.1949 |
| `validation` | `delta_yN` | 7,079 | 0.0850 | 0.0576 | -0.9912 | 0.7237 | 0.1341 |
| `validation` | `delta_yF` | 7,079 | 0.1120 | 0.0751 | -1.7268 | 0.9041 | 0.3724 |
| `validation` | `delta_yT` | 7,079 | 0.1860 | 0.1310 | -1.1829 | 0.8945 | 0.6238 |
| `test` | `all` | 7,582 | 0.1097 | 0.0677 | -1.3052 | 0.8529 | 0.3122 |
| `test` | `yN` | 7,582 | 0.0856 | 0.0572 | -0.9559 | 0.7114 | 0.1340 |
| `test` | `yF` | 7,582 | 0.1094 | 0.0710 | -1.7412 | 0.9115 | 0.3821 |
| `test` | `yT` | 7,582 | 0.1774 | 0.1103 | -1.2281 | 0.9000 | 0.6216 |
| `test` | `sigma_N` | 7,582 | 0.1376 | 0.0635 | 1.2225 | 0.8271 | 0.1656 |
| `test` | `sigma_F` | 7,582 | 0.0394 | 0.0204 | -2.7445 | 0.9023 | 0.1436 |
| `test` | `sigma_T` | 7,582 | 0.0702 | 0.0364 | -2.1779 | 0.8718 | 0.2013 |
| `test` | `delta_yN` | 7,582 | 0.0852 | 0.0593 | -1.1501 | 0.7238 | 0.1419 |
| `test` | `delta_yF` | 7,582 | 0.1113 | 0.0754 | -1.7222 | 0.9137 | 0.3831 |
| `test` | `delta_yT` | 7,582 | 0.1717 | 0.1154 | -1.2489 | 0.9148 | 0.6365 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.6500 | 0.0534 | 0.0844 | 1.0188 |
| `yF` | 0.8000 | 0.0717 | 0.1114 | 1.0113 |
| `yT` | 0.5000 | 0.1226 | 0.1901 | 1.0447 |
| `sigma_N` | 0.2000 | 0.0526 | 0.1189 | 1.0072 |
| `sigma_F` | 0.1000 | 0.0223 | 0.0495 | 1.0065 |
| `sigma_T` | 0.0000 | 0.0420 | 0.0798 | 1.0141 |
| `delta_yN` | 0.9000 | 0.0576 | 0.0850 | 1.0073 |
| `delta_yF` | 1.0000 | 0.0751 | 0.1120 | 1.0047 |
| `delta_yT` | 0.9000 | 0.1310 | 0.1860 | 1.0099 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1097 | 0.1475 | 0.2560 | 0.0677 | 0.0841 | 0.1952 |
| `train` | `all` | 0.0903 | 0.1248 | 0.2761 | 0.0506 | 0.0612 | 0.1731 |
| `validation` | `all` | 0.1130 | 0.1529 | 0.2607 | 0.0698 | 0.0870 | 0.1975 |

## Outputs

- Model: `models/pipe_grud/adaptive_wqp_focused/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/adaptive_wqp_focused/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_manifest.json`
