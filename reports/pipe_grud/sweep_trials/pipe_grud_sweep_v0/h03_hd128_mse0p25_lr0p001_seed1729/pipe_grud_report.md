# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:34:52.372687+00:00`
Started at UTC: `2026-05-17T01:32:29.501216+00:00`
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
- Auxiliary MSE weight: `0.25`
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
- Selection objective: `0.7700`
- Validation loss: `-3.1405`
- Validation RMSE all: `0.1189`
- Validation MAE all: `0.0632`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 1,065,877 | 0.1107 | 0.0571 | -2.7280 | 0.9402 | 0.2702 |
| `train` | `yN` | 1,065,877 | 0.0654 | 0.0176 | -3.8612 | 0.9776 | 0.1161 |
| `train` | `yF` | 1,065,877 | 0.1028 | 0.0442 | -2.7694 | 0.9430 | 0.2053 |
| `train` | `yT` | 1,065,877 | 0.2353 | 0.1524 | -1.1227 | 0.8962 | 0.6751 |
| `train` | `sigma_N` | 1,065,877 | 0.0616 | 0.0117 | -3.7822 | 0.9831 | 0.1170 |
| `train` | `sigma_F` | 1,065,877 | 0.0527 | 0.0178 | -3.0600 | 0.9562 | 0.1093 |
| `train` | `sigma_T` | 1,065,877 | 0.0789 | 0.0461 | -2.1834 | 0.8761 | 0.2091 |
| `train` | `delta_yN` | 1,065,877 | 0.0652 | 0.0180 | -3.8858 | 0.9787 | 0.1158 |
| `train` | `delta_yF` | 1,065,877 | 0.1033 | 0.0466 | -2.7505 | 0.9450 | 0.2077 |
| `train` | `delta_yT` | 1,065,877 | 0.2310 | 0.1592 | -1.1372 | 0.9061 | 0.6769 |
| `validation` | `all` | 116,097 | 0.1189 | 0.0632 | -2.6299 | 0.9369 | 0.3050 |
| `validation` | `yN` | 116,097 | 0.0790 | 0.0307 | -3.4015 | 0.9616 | 0.1814 |
| `validation` | `yF` | 116,097 | 0.1025 | 0.0454 | -3.2174 | 0.9550 | 0.2342 |
| `validation` | `yT` | 116,097 | 0.2350 | 0.1553 | -1.0287 | 0.8893 | 0.6839 |
| `validation` | `sigma_N` | 116,097 | 0.0874 | 0.0230 | -3.0232 | 0.9674 | 0.1756 |
| `validation` | `sigma_F` | 116,097 | 0.0570 | 0.0191 | -3.3165 | 0.9621 | 0.1247 |
| `validation` | `sigma_T` | 116,097 | 0.0959 | 0.0538 | -2.0198 | 0.8774 | 0.2422 |
| `validation` | `delta_yN` | 116,097 | 0.0783 | 0.0312 | -3.4209 | 0.9633 | 0.1808 |
| `validation` | `delta_yF` | 116,097 | 0.1039 | 0.0480 | -3.1937 | 0.9562 | 0.2359 |
| `validation` | `delta_yT` | 116,097 | 0.2308 | 0.1620 | -1.0469 | 0.9001 | 0.6865 |
| `test` | `all` | 86,069 | 0.1251 | 0.0676 | -2.4426 | 0.9339 | 0.3366 |
| `test` | `yN` | 86,069 | 0.0983 | 0.0422 | -2.9661 | 0.9439 | 0.2279 |
| `test` | `yF` | 86,069 | 0.1120 | 0.0542 | -2.9699 | 0.9483 | 0.2783 |
| `test` | `yT` | 86,069 | 0.2227 | 0.1480 | -1.0713 | 0.9019 | 0.6934 |
| `test` | `sigma_N` | 86,069 | 0.1098 | 0.0344 | -2.7038 | 0.9484 | 0.2184 |
| `test` | `sigma_F` | 86,069 | 0.0632 | 0.0227 | -3.1881 | 0.9578 | 0.1467 |
| `test` | `sigma_T` | 86,069 | 0.0888 | 0.0504 | -2.0692 | 0.8978 | 0.2598 |
| `test` | `delta_yN` | 86,069 | 0.0972 | 0.0430 | -2.9910 | 0.9472 | 0.2273 |
| `test` | `delta_yF` | 86,069 | 0.1137 | 0.0569 | -2.9470 | 0.9497 | 0.2809 |
| `test` | `delta_yT` | 86,069 | 0.2203 | 0.1562 | -1.0767 | 0.9105 | 0.6966 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.5000 | 0.0307 | 0.0790 | 1.0222 |
| `yF` | 0.8000 | 0.0454 | 0.1025 | 1.0126 |
| `yT` | 0.6500 | 0.1553 | 0.2350 | 1.0215 |
| `sigma_N` | 0.0000 | 0.0230 | 0.0874 | 1.0046 |
| `sigma_F` | 0.0000 | 0.0191 | 0.0570 | 1.0167 |
| `sigma_T` | 0.5000 | 0.0538 | 0.0959 | 1.0254 |
| `delta_yN` | 1.0000 | 0.0312 | 0.0783 | 1.0018 |
| `delta_yF` | 1.0000 | 0.0480 | 0.1039 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1620 | 0.2308 | 1.0066 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1251 | 0.1679 | 0.2548 | 0.0676 | 0.0827 | 0.1831 |
| `train` | `all` | 0.1107 | 0.1514 | 0.2691 | 0.0571 | 0.0706 | 0.1918 |
| `validation` | `all` | 0.1189 | 0.1613 | 0.2633 | 0.0632 | 0.0786 | 0.1968 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p25_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p25_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p25_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p25_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p25_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p25_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p25_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p25_lr0p001_seed1729/pipe_grud_manifest.json`
