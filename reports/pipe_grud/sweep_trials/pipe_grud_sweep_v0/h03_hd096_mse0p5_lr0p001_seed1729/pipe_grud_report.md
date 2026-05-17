# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:30:11.125699+00:00`
Started at UTC: `2026-05-17T01:27:56.823017+00:00`
Status: `completed`

## Scope

This step trains the minimal probabilistic temporal model over the frozen PIPE sequence dataset.
It predicts the next 9-dimensional fuzzy state vector and estimates diagonal Gaussian uncertainty.
Checkpoint selection evaluates the same blended output used by the final model.

## Configuration

- History length: `3`
- Hidden dimension: `96`
- GRU layers: `1`
- Residual mode: `add_last`
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
| `train` | 1,065,877 | 1,065,877 |
| `validation` | 116,097 | 116,097 |
| `test` | 86,069 | 86,069 |

## Best Epoch

- Epoch: `19`
- Selection metric: `balanced`
- Selection objective: `0.7758`
- Validation loss: `-3.0924`
- Validation RMSE all: `0.1194`
- Validation MAE all: `0.0638`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 1,065,877 | 0.1111 | 0.0578 | -2.6873 | 0.9395 | 0.2869 |
| `train` | `yN` | 1,065,877 | 0.0651 | 0.0181 | -3.8457 | 0.9799 | 0.1281 |
| `train` | `yF` | 1,065,877 | 0.1033 | 0.0443 | -2.7505 | 0.9462 | 0.2224 |
| `train` | `yT` | 1,065,877 | 0.2355 | 0.1539 | -1.0501 | 0.8847 | 0.7007 |
| `train` | `sigma_N` | 1,065,877 | 0.0616 | 0.0117 | -3.7687 | 0.9840 | 0.1289 |
| `train` | `sigma_F` | 1,065,877 | 0.0527 | 0.0178 | -3.0433 | 0.9619 | 0.1224 |
| `train` | `sigma_T` | 1,065,877 | 0.0802 | 0.0468 | -2.1247 | 0.8755 | 0.2281 |
| `train` | `delta_yN` | 1,065,877 | 0.0649 | 0.0202 | -3.7730 | 0.9809 | 0.1292 |
| `train` | `delta_yF` | 1,065,877 | 0.1051 | 0.0459 | -2.7611 | 0.9463 | 0.2215 |
| `train` | `delta_yT` | 1,065,877 | 0.2313 | 0.1612 | -1.0685 | 0.8957 | 0.7010 |
| `validation` | `all` | 116,097 | 0.1194 | 0.0638 | -2.5971 | 0.9388 | 0.3314 |
| `validation` | `yN` | 116,097 | 0.0788 | 0.0309 | -3.3947 | 0.9663 | 0.2012 |
| `validation` | `yF` | 116,097 | 0.1031 | 0.0454 | -3.1599 | 0.9657 | 0.2750 |
| `validation` | `yT` | 116,097 | 0.2354 | 0.1568 | -0.9946 | 0.8783 | 0.7085 |
| `validation` | `sigma_N` | 116,097 | 0.0874 | 0.0230 | -3.0336 | 0.9688 | 0.1969 |
| `validation` | `sigma_F` | 116,097 | 0.0570 | 0.0191 | -3.3185 | 0.9706 | 0.1525 |
| `validation` | `sigma_T` | 116,097 | 0.0972 | 0.0542 | -1.9888 | 0.8761 | 0.2625 |
| `validation` | `delta_yN` | 116,097 | 0.0782 | 0.0330 | -3.3285 | 0.9688 | 0.2039 |
| `validation` | `delta_yF` | 116,097 | 0.1067 | 0.0477 | -3.1439 | 0.9651 | 0.2731 |
| `validation` | `delta_yT` | 116,097 | 0.2312 | 0.1641 | -1.0111 | 0.8894 | 0.7088 |
| `test` | `all` | 86,069 | 0.1257 | 0.0681 | -2.3995 | 0.9379 | 0.3725 |
| `test` | `yN` | 86,069 | 0.0979 | 0.0423 | -2.9318 | 0.9506 | 0.2550 |
| `test` | `yF` | 86,069 | 0.1130 | 0.0541 | -2.9057 | 0.9613 | 0.3317 |
| `test` | `yT` | 86,069 | 0.2231 | 0.1494 | -1.0153 | 0.8914 | 0.7300 |
| `test` | `sigma_N` | 86,069 | 0.1098 | 0.0344 | -2.7632 | 0.9513 | 0.2469 |
| `test` | `sigma_F` | 86,069 | 0.0632 | 0.0227 | -3.1685 | 0.9694 | 0.1824 |
| `test` | `sigma_T` | 86,069 | 0.0904 | 0.0509 | -2.0095 | 0.9000 | 0.2870 |
| `test` | `delta_yN` | 86,069 | 0.0965 | 0.0443 | -2.8876 | 0.9555 | 0.2586 |
| `test` | `delta_yF` | 86,069 | 0.1170 | 0.0570 | -2.8883 | 0.9607 | 0.3293 |
| `test` | `delta_yT` | 86,069 | 0.2206 | 0.1580 | -1.0256 | 0.9011 | 0.7319 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.5000 | 0.0309 | 0.0788 | 1.0262 |
| `yF` | 0.8000 | 0.0454 | 0.1031 | 1.0122 |
| `yT` | 0.6500 | 0.1568 | 0.2354 | 1.0254 |
| `sigma_N` | 0.0000 | 0.0230 | 0.0874 | 1.0049 |
| `sigma_F` | 0.0000 | 0.0191 | 0.0570 | 1.0142 |
| `sigma_T` | 0.5000 | 0.0542 | 0.0972 | 1.0266 |
| `delta_yN` | 1.0000 | 0.0330 | 0.0782 | 1.0060 |
| `delta_yF` | 1.0000 | 0.0477 | 0.1067 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1641 | 0.2312 | 1.0061 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1257 | 0.1679 | 0.2512 | 0.0681 | 0.0827 | 0.1761 |
| `train` | `all` | 0.1111 | 0.1514 | 0.2665 | 0.0578 | 0.0706 | 0.1821 |
| `validation` | `all` | 0.1194 | 0.1613 | 0.2598 | 0.0638 | 0.0786 | 0.1887 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p5_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p5_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p5_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p5_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p5_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p5_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p5_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p5_lr0p001_seed1729/pipe_grud_manifest.json`
