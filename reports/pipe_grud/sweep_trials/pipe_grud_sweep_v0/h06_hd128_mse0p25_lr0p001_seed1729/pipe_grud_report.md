# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:49:17.194776+00:00`
Started at UTC: `2026-05-17T01:47:56.649262+00:00`
Status: `completed`

## Scope

This step trains the minimal probabilistic temporal model over the frozen PIPE sequence dataset.
It predicts the next 9-dimensional fuzzy state vector and estimates diagonal Gaussian uncertainty.
Checkpoint selection evaluates the same blended output used by the final model.

## Configuration

- History length: `6`
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
| `train` | 602,390 | 602,390 |
| `validation` | 54,637 | 54,637 |
| `test` | 40,606 | 40,606 |

## Best Epoch

- Epoch: `15`
- Selection metric: `balanced`
- Selection objective: `0.7666`
- Validation loss: `-3.2166`
- Validation RMSE all: `0.1122`
- Validation MAE all: `0.0605`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 602,390 | 0.1028 | 0.0547 | -2.8640 | 0.9435 | 0.3023 |
| `train` | `yN` | 602,390 | 0.0492 | 0.0112 | -4.2455 | 0.9842 | 0.0756 |
| `train` | `yF` | 602,390 | 0.0861 | 0.0326 | -3.0226 | 0.9498 | 0.2450 |
| `train` | `yT` | 602,390 | 0.2439 | 0.1639 | -0.9152 | 0.8911 | 0.7985 |
| `train` | `sigma_N` | 602,390 | 0.0488 | 0.0072 | -4.0653 | 0.9906 | 0.1027 |
| `train` | `sigma_F` | 602,390 | 0.0483 | 0.0140 | -3.1544 | 0.9755 | 0.1501 |
| `train` | `sigma_T` | 602,390 | 0.0723 | 0.0451 | -2.1530 | 0.8690 | 0.2382 |
| `train` | `delta_yN` | 602,390 | 0.0491 | 0.0106 | -4.2968 | 0.9845 | 0.0756 |
| `train` | `delta_yF` | 602,390 | 0.0886 | 0.0364 | -2.9887 | 0.9474 | 0.2381 |
| `train` | `delta_yT` | 602,390 | 0.2393 | 0.1711 | -0.9348 | 0.8997 | 0.7970 |
| `validation` | `all` | 54,637 | 0.1122 | 0.0605 | -2.7029 | 0.9500 | 0.3983 |
| `validation` | `yN` | 54,637 | 0.0667 | 0.0253 | -3.7017 | 0.9615 | 0.1459 |
| `validation` | `yF` | 54,637 | 0.0839 | 0.0338 | -3.1552 | 0.9908 | 0.4417 |
| `validation` | `yT` | 54,637 | 0.2442 | 0.1640 | -0.8991 | 0.8985 | 0.8429 |
| `validation` | `sigma_N` | 54,637 | 0.0804 | 0.0187 | -3.4805 | 0.9778 | 0.1904 |
| `validation` | `sigma_F` | 54,637 | 0.0459 | 0.0142 | -3.2306 | 0.9924 | 0.2531 |
| `validation` | `sigma_T` | 54,637 | 0.0939 | 0.0529 | -2.0012 | 0.8677 | 0.2984 |
| `validation` | `delta_yN` | 54,637 | 0.0653 | 0.0249 | -3.7923 | 0.9651 | 0.1450 |
| `validation` | `delta_yF` | 54,637 | 0.0886 | 0.0387 | -3.1480 | 0.9903 | 0.4293 |
| `validation` | `delta_yT` | 54,637 | 0.2413 | 0.1721 | -0.9175 | 0.9059 | 0.8379 |
| `test` | `all` | 40,606 | 0.1144 | 0.0614 | -2.5197 | 0.9523 | 0.4404 |
| `test` | `yN` | 40,606 | 0.0838 | 0.0343 | -3.2582 | 0.9417 | 0.1731 |
| `test` | `yF` | 40,606 | 0.0933 | 0.0413 | -2.8978 | 0.9912 | 0.5456 |
| `test` | `yT` | 40,606 | 0.2240 | 0.1493 | -0.9657 | 0.9167 | 0.8500 |
| `test` | `sigma_N` | 40,606 | 0.0950 | 0.0265 | -3.2074 | 0.9672 | 0.2270 |
| `test` | `sigma_F` | 40,606 | 0.0547 | 0.0180 | -3.0407 | 0.9898 | 0.3018 |
| `test` | `sigma_T` | 40,606 | 0.0761 | 0.0451 | -2.0487 | 0.9027 | 0.3192 |
| `test` | `delta_yN` | 40,606 | 0.0825 | 0.0340 | -3.3835 | 0.9469 | 0.1716 |
| `test` | `delta_yF` | 40,606 | 0.0980 | 0.0462 | -2.8959 | 0.9908 | 0.5304 |
| `test` | `delta_yT` | 40,606 | 0.2218 | 0.1580 | -0.9798 | 0.9239 | 0.8446 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.3500 | 0.0253 | 0.0667 | 1.0364 |
| `yF` | 0.9000 | 0.0338 | 0.0839 | 1.0050 |
| `yT` | 0.6500 | 0.1640 | 0.2442 | 1.0264 |
| `sigma_N` | 0.0000 | 0.0187 | 0.0804 | 1.0004 |
| `sigma_F` | 0.0000 | 0.0142 | 0.0459 | 1.0020 |
| `sigma_T` | 0.5000 | 0.0529 | 0.0939 | 1.0266 |
| `delta_yN` | 0.9000 | 0.0249 | 0.0653 | 1.0032 |
| `delta_yF` | 1.0000 | 0.0387 | 0.0886 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1721 | 0.2413 | 1.0049 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1144 | 0.1547 | 0.2610 | 0.0614 | 0.0753 | 0.1848 |
| `train` | `all` | 0.1028 | 0.1422 | 0.2768 | 0.0547 | 0.0673 | 0.1875 |
| `validation` | `all` | 0.1122 | 0.1537 | 0.2696 | 0.0605 | 0.0754 | 0.1973 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p25_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p25_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p25_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p25_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p25_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p25_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p25_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p25_lr0p001_seed1729/pipe_grud_manifest.json`
