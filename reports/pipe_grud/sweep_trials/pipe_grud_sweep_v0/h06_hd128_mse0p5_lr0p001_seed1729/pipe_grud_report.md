# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:50:40.211641+00:00`
Started at UTC: `2026-05-17T01:49:19.319366+00:00`
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
| `train` | 602,390 | 602,390 |
| `validation` | 54,637 | 54,637 |
| `test` | 40,606 | 40,606 |

## Best Epoch

- Epoch: `18`
- Selection metric: `balanced`
- Selection objective: `0.7673`
- Validation loss: `-3.2176`
- Validation RMSE all: `0.1125`
- Validation MAE all: `0.0605`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 602,390 | 0.1032 | 0.0546 | -2.8393 | 0.9394 | 0.2843 |
| `train` | `yN` | 602,390 | 0.0491 | 0.0114 | -4.2687 | 0.9828 | 0.0681 |
| `train` | `yF` | 602,390 | 0.0915 | 0.0341 | -2.8872 | 0.9308 | 0.1866 |
| `train` | `yT` | 602,390 | 0.2431 | 0.1644 | -0.9316 | 0.8899 | 0.7828 |
| `train` | `sigma_N` | 602,390 | 0.0488 | 0.0072 | -3.9475 | 0.9898 | 0.0978 |
| `train` | `sigma_F` | 602,390 | 0.0483 | 0.0140 | -3.1613 | 0.9652 | 0.1185 |
| `train` | `sigma_T` | 602,390 | 0.0721 | 0.0444 | -2.1665 | 0.8611 | 0.2208 |
| `train` | `delta_yN` | 602,390 | 0.0488 | 0.0105 | -4.2458 | 0.9880 | 0.0844 |
| `train` | `delta_yF` | 602,390 | 0.0888 | 0.0356 | -2.9956 | 0.9494 | 0.2243 |
| `train` | `delta_yT` | 602,390 | 0.2388 | 0.1701 | -0.9495 | 0.8975 | 0.7757 |
| `validation` | `all` | 54,637 | 0.1125 | 0.0605 | -2.7123 | 0.9487 | 0.3745 |
| `validation` | `yN` | 54,637 | 0.0665 | 0.0254 | -3.6906 | 0.9603 | 0.1382 |
| `validation` | `yF` | 54,637 | 0.0889 | 0.0360 | -3.2694 | 0.9826 | 0.3571 |
| `validation` | `yT` | 54,637 | 0.2435 | 0.1649 | -0.9182 | 0.8959 | 0.8205 |
| `validation` | `sigma_N` | 54,637 | 0.0804 | 0.0187 | -3.3728 | 0.9776 | 0.1826 |
| `validation` | `sigma_F` | 54,637 | 0.0459 | 0.0142 | -3.3924 | 0.9889 | 0.2112 |
| `validation` | `sigma_T` | 54,637 | 0.0936 | 0.0521 | -2.0212 | 0.8633 | 0.2745 |
| `validation` | `delta_yN` | 54,637 | 0.0651 | 0.0247 | -3.7946 | 0.9772 | 0.1671 |
| `validation` | `delta_yF` | 54,637 | 0.0882 | 0.0378 | -3.0159 | 0.9893 | 0.4072 |
| `validation` | `delta_yT` | 54,637 | 0.2402 | 0.1709 | -0.9355 | 0.9031 | 0.8120 |
| `test` | `all` | 40,606 | 0.1147 | 0.0613 | -2.5499 | 0.9520 | 0.4141 |
| `test` | `yN` | 40,606 | 0.0836 | 0.0343 | -3.2981 | 0.9419 | 0.1671 |
| `test` | `yF` | 40,606 | 0.0986 | 0.0430 | -3.0137 | 0.9826 | 0.4439 |
| `test` | `yT` | 40,606 | 0.2237 | 0.1502 | -0.9849 | 0.9143 | 0.8265 |
| `test` | `sigma_N` | 40,606 | 0.0950 | 0.0265 | -3.1174 | 0.9670 | 0.2189 |
| `test` | `sigma_F` | 40,606 | 0.0547 | 0.0180 | -3.1918 | 0.9849 | 0.2548 |
| `test` | `sigma_T` | 40,606 | 0.0760 | 0.0442 | -2.0805 | 0.8991 | 0.2925 |
| `test` | `delta_yN` | 40,606 | 0.0823 | 0.0338 | -3.4858 | 0.9661 | 0.2014 |
| `test` | `delta_yF` | 40,606 | 0.0976 | 0.0450 | -2.7778 | 0.9899 | 0.5019 |
| `test` | `delta_yT` | 40,606 | 0.2209 | 0.1566 | -0.9995 | 0.9222 | 0.8201 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.3500 | 0.0254 | 0.0665 | 1.0398 |
| `yF` | 0.3500 | 0.0360 | 0.0889 | 1.0399 |
| `yT` | 0.6500 | 0.1649 | 0.2435 | 1.0291 |
| `sigma_N` | 0.0000 | 0.0187 | 0.0804 | 1.0005 |
| `sigma_F` | 0.0000 | 0.0142 | 0.0459 | 1.0015 |
| `sigma_T` | 0.5000 | 0.0521 | 0.0936 | 1.0175 |
| `delta_yN` | 0.9000 | 0.0247 | 0.0651 | 1.0038 |
| `delta_yF` | 1.0000 | 0.0378 | 0.0882 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1709 | 0.2402 | 1.0059 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1147 | 0.1547 | 0.2588 | 0.0613 | 0.0753 | 0.1863 |
| `train` | `all` | 0.1032 | 0.1422 | 0.2740 | 0.0546 | 0.0673 | 0.1883 |
| `validation` | `all` | 0.1125 | 0.1537 | 0.2680 | 0.0605 | 0.0754 | 0.1974 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p5_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p5_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p5_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p5_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p5_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p5_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p5_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse0p5_lr0p001_seed1729/pipe_grud_manifest.json`
