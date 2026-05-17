# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:21:11.769382+00:00`
Started at UTC: `2026-05-17T01:19:05.956280+00:00`
Status: `completed`

## Scope

This step trains the minimal probabilistic temporal model over the frozen PIPE sequence dataset.
It predicts the next 9-dimensional fuzzy state vector and estimates diagonal Gaussian uncertainty.
Checkpoint selection evaluates the same blended output used by the final model.

## Configuration

- History length: `3`
- Hidden dimension: `64`
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

- Epoch: `17`
- Selection metric: `balanced`
- Selection objective: `0.7792`
- Validation loss: `-3.0541`
- Validation RMSE all: `0.1202`
- Validation MAE all: `0.0639`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 1,065,877 | 0.1118 | 0.0578 | -2.6887 | 0.9432 | 0.3050 |
| `train` | `yN` | 1,065,877 | 0.0649 | 0.0178 | -3.8294 | 0.9798 | 0.1305 |
| `train` | `yF` | 1,065,877 | 0.1042 | 0.0439 | -2.8010 | 0.9486 | 0.2325 |
| `train` | `yT` | 1,065,877 | 0.2358 | 0.1542 | -1.0127 | 0.8922 | 0.7466 |
| `train` | `sigma_N` | 1,065,877 | 0.0616 | 0.0117 | -3.7452 | 0.9838 | 0.1328 |
| `train` | `sigma_F` | 1,065,877 | 0.0527 | 0.0178 | -3.0788 | 0.9671 | 0.1349 |
| `train` | `sigma_T` | 1,065,877 | 0.0830 | 0.0464 | -2.0692 | 0.8819 | 0.2515 |
| `train` | `delta_yN` | 1,065,877 | 0.0667 | 0.0194 | -3.8355 | 0.9796 | 0.1275 |
| `train` | `delta_yF` | 1,065,877 | 0.1056 | 0.0471 | -2.7996 | 0.9532 | 0.2398 |
| `train` | `delta_yT` | 1,065,877 | 0.2317 | 0.1618 | -1.0271 | 0.9025 | 0.7486 |
| `validation` | `all` | 116,097 | 0.1202 | 0.0639 | -2.5576 | 0.9436 | 0.3579 |
| `validation` | `yN` | 116,097 | 0.0785 | 0.0308 | -3.4090 | 0.9675 | 0.2044 |
| `validation` | `yF` | 116,097 | 0.1041 | 0.0454 | -2.9787 | 0.9691 | 0.3129 |
| `validation` | `yT` | 116,097 | 0.2357 | 0.1568 | -0.9913 | 0.8904 | 0.7603 |
| `validation` | `sigma_N` | 116,097 | 0.0874 | 0.0230 | -3.1124 | 0.9692 | 0.2040 |
| `validation` | `sigma_F` | 116,097 | 0.0570 | 0.0191 | -3.1764 | 0.9745 | 0.1737 |
| `validation` | `sigma_T` | 116,097 | 0.0998 | 0.0537 | -1.9592 | 0.8824 | 0.2897 |
| `validation` | `delta_yN` | 116,097 | 0.0800 | 0.0328 | -3.4113 | 0.9668 | 0.1990 |
| `validation` | `delta_yF` | 116,097 | 0.1071 | 0.0490 | -2.9769 | 0.9720 | 0.3173 |
| `validation` | `delta_yT` | 116,097 | 0.2326 | 0.1648 | -1.0036 | 0.9008 | 0.7598 |
| `test` | `all` | 86,069 | 0.1268 | 0.0685 | -2.3596 | 0.9420 | 0.3981 |
| `test` | `yN` | 86,069 | 0.0975 | 0.0423 | -2.9639 | 0.9511 | 0.2539 |
| `test` | `yF` | 86,069 | 0.1139 | 0.0541 | -2.7410 | 0.9663 | 0.3804 |
| `test` | `yT` | 86,069 | 0.2236 | 0.1499 | -1.0088 | 0.9011 | 0.7716 |
| `test` | `sigma_N` | 86,069 | 0.1098 | 0.0344 | -2.8140 | 0.9511 | 0.2523 |
| `test` | `sigma_F` | 86,069 | 0.0632 | 0.0227 | -3.0263 | 0.9722 | 0.2075 |
| `test` | `sigma_T` | 86,069 | 0.0933 | 0.0506 | -1.9590 | 0.9056 | 0.3140 |
| `test` | `delta_yN` | 86,069 | 0.0992 | 0.0448 | -2.9718 | 0.9505 | 0.2474 |
| `test` | `delta_yF` | 86,069 | 0.1178 | 0.0584 | -2.7367 | 0.9693 | 0.3844 |
| `test` | `delta_yT` | 86,069 | 0.2225 | 0.1596 | -1.0152 | 0.9109 | 0.7719 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.5000 | 0.0308 | 0.0785 | 1.0217 |
| `yF` | 0.6500 | 0.0454 | 0.1041 | 1.0131 |
| `yT` | 0.6500 | 0.1568 | 0.2357 | 1.0245 |
| `sigma_N` | 0.0000 | 0.0230 | 0.0874 | 1.0056 |
| `sigma_F` | 0.0000 | 0.0191 | 0.0570 | 1.0060 |
| `sigma_T` | 0.3500 | 0.0537 | 0.0998 | 1.0250 |
| `delta_yN` | 0.9000 | 0.0328 | 0.0800 | 1.0050 |
| `delta_yF` | 1.0000 | 0.0490 | 0.1071 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1648 | 0.2326 | 1.0063 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1268 | 0.1679 | 0.2450 | 0.0685 | 0.0827 | 0.1715 |
| `train` | `all` | 0.1118 | 0.1514 | 0.2617 | 0.0578 | 0.0706 | 0.1818 |
| `validation` | `all` | 0.1202 | 0.1613 | 0.2548 | 0.0639 | 0.0786 | 0.1869 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p25_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p25_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p25_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p25_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p25_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p25_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p25_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p25_lr0p001_seed1729/pipe_grud_manifest.json`
