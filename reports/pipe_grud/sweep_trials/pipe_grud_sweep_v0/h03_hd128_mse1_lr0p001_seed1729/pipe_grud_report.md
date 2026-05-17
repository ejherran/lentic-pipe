# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:39:46.227440+00:00`
Started at UTC: `2026-05-17T01:37:22.907155+00:00`
Status: `completed`

## Scope

This step trains the minimal probabilistic temporal model over the frozen PIPE sequence dataset.
It predicts the next 9-dimensional fuzzy state vector and estimates diagonal Gaussian uncertainty.
Checkpoint selection evaluates the same blended output used by the final model.

## Configuration

- History length: `3`
- Hidden dimension: `128`
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
| `train` | 1,065,877 | 1,065,877 |
| `validation` | 116,097 | 116,097 |
| `test` | 86,069 | 86,069 |

## Best Epoch

- Epoch: `19`
- Selection metric: `balanced`
- Selection objective: `0.7703`
- Validation loss: `-3.1340`
- Validation RMSE all: `0.1187`
- Validation MAE all: `0.0633`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 1,065,877 | 0.1104 | 0.0572 | -2.7287 | 0.9397 | 0.2713 |
| `train` | `yN` | 1,065,877 | 0.0653 | 0.0181 | -3.8626 | 0.9773 | 0.1123 |
| `train` | `yF` | 1,065,877 | 0.1029 | 0.0442 | -2.7751 | 0.9442 | 0.2093 |
| `train` | `yT` | 1,065,877 | 0.2347 | 0.1524 | -1.1106 | 0.8934 | 0.6785 |
| `train` | `sigma_N` | 1,065,877 | 0.0616 | 0.0117 | -3.7954 | 0.9830 | 0.1156 |
| `train` | `sigma_F` | 1,065,877 | 0.0523 | 0.0179 | -3.0801 | 0.9579 | 0.1122 |
| `train` | `sigma_T` | 1,065,877 | 0.0788 | 0.0460 | -2.1702 | 0.8734 | 0.2094 |
| `train` | `delta_yN` | 1,065,877 | 0.0646 | 0.0179 | -3.8929 | 0.9787 | 0.1126 |
| `train` | `delta_yF` | 1,065,877 | 0.1034 | 0.0468 | -2.7457 | 0.9459 | 0.2121 |
| `train` | `delta_yT` | 1,065,877 | 0.2303 | 0.1596 | -1.1253 | 0.9035 | 0.6797 |
| `validation` | `all` | 116,097 | 0.1187 | 0.0633 | -2.6254 | 0.9364 | 0.3061 |
| `validation` | `yN` | 116,097 | 0.0790 | 0.0310 | -3.4092 | 0.9624 | 0.1786 |
| `validation` | `yF` | 116,097 | 0.1026 | 0.0454 | -3.1942 | 0.9558 | 0.2361 |
| `validation` | `yT` | 116,097 | 0.2345 | 0.1555 | -1.0245 | 0.8861 | 0.6885 |
| `validation` | `sigma_N` | 116,097 | 0.0874 | 0.0230 | -3.0639 | 0.9675 | 0.1761 |
| `validation` | `sigma_F` | 116,097 | 0.0567 | 0.0192 | -3.2920 | 0.9634 | 0.1274 |
| `validation` | `sigma_T` | 116,097 | 0.0959 | 0.0537 | -2.0137 | 0.8740 | 0.2416 |
| `validation` | `delta_yN` | 116,097 | 0.0778 | 0.0310 | -3.4371 | 0.9646 | 0.1789 |
| `validation` | `delta_yF` | 116,097 | 0.1039 | 0.0481 | -3.1538 | 0.9570 | 0.2379 |
| `validation` | `delta_yT` | 116,097 | 0.2305 | 0.1629 | -1.0404 | 0.8966 | 0.6900 |
| `test` | `all` | 86,069 | 0.1249 | 0.0677 | -2.4370 | 0.9334 | 0.3376 |
| `test` | `yN` | 86,069 | 0.0982 | 0.0424 | -2.9731 | 0.9447 | 0.2212 |
| `test` | `yF` | 86,069 | 0.1122 | 0.0542 | -2.9481 | 0.9490 | 0.2805 |
| `test` | `yT` | 86,069 | 0.2221 | 0.1482 | -1.0571 | 0.8984 | 0.7024 |
| `test` | `sigma_N` | 86,069 | 0.1098 | 0.0344 | -2.7493 | 0.9485 | 0.2171 |
| `test` | `sigma_F` | 86,069 | 0.0629 | 0.0228 | -3.1673 | 0.9595 | 0.1494 |
| `test` | `sigma_T` | 86,069 | 0.0887 | 0.0503 | -2.0570 | 0.8952 | 0.2588 |
| `test` | `delta_yN` | 86,069 | 0.0964 | 0.0427 | -3.0058 | 0.9486 | 0.2221 |
| `test` | `delta_yF` | 86,069 | 0.1136 | 0.0569 | -2.9136 | 0.9501 | 0.2833 |
| `test` | `delta_yT` | 86,069 | 0.2202 | 0.1574 | -1.0616 | 0.9062 | 0.7041 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.5000 | 0.0310 | 0.0790 | 1.0281 |
| `yF` | 0.8000 | 0.0454 | 0.1026 | 1.0128 |
| `yT` | 0.6500 | 0.1555 | 0.2345 | 1.0215 |
| `sigma_N` | 0.0000 | 0.0230 | 0.0874 | 1.0053 |
| `sigma_F` | 0.1000 | 0.0192 | 0.0567 | 1.0159 |
| `sigma_T` | 0.5000 | 0.0537 | 0.0959 | 1.0219 |
| `delta_yN` | 1.0000 | 0.0310 | 0.0778 | 1.0028 |
| `delta_yF` | 1.0000 | 0.0481 | 0.1039 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1629 | 0.2305 | 1.0072 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1249 | 0.1679 | 0.2561 | 0.0677 | 0.0827 | 0.1812 |
| `train` | `all` | 0.1104 | 0.1514 | 0.2707 | 0.0572 | 0.0706 | 0.1903 |
| `validation` | `all` | 0.1187 | 0.1613 | 0.2643 | 0.0633 | 0.0786 | 0.1952 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse1_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse1_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse1_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse1_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse1_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse1_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse1_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse1_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse1_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse1_lr0p001_seed1729/pipe_grud_manifest.json`
