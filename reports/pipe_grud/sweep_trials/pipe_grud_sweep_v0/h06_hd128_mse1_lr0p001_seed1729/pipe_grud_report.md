# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:52:04.443643+00:00`
Started at UTC: `2026-05-17T01:50:42.435489+00:00`
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
| `train` | 602,390 | 602,390 |
| `validation` | 54,637 | 54,637 |
| `test` | 40,606 | 40,606 |

## Best Epoch

- Epoch: `20`
- Selection metric: `balanced`
- Selection objective: `0.7691`
- Validation loss: `-3.1781`
- Validation RMSE all: `0.1121`
- Validation MAE all: `0.0610`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 602,390 | 0.1028 | 0.0552 | -2.8741 | 0.9467 | 0.2999 |
| `train` | `yN` | 602,390 | 0.0471 | 0.0095 | -4.3538 | 0.9865 | 0.0759 |
| `train` | `yF` | 602,390 | 0.0883 | 0.0332 | -3.0854 | 0.9714 | 0.2889 |
| `train` | `yT` | 602,390 | 0.2428 | 0.1635 | -0.9425 | 0.8871 | 0.7643 |
| `train` | `sigma_N` | 602,390 | 0.0488 | 0.0072 | -4.0396 | 0.9904 | 0.1006 |
| `train` | `sigma_F` | 602,390 | 0.0483 | 0.0140 | -3.3158 | 0.9784 | 0.1460 |
| `train` | `sigma_T` | 602,390 | 0.0724 | 0.0452 | -2.1697 | 0.8591 | 0.2202 |
| `train` | `delta_yN` | 602,390 | 0.0502 | 0.0156 | -3.9393 | 0.9874 | 0.0803 |
| `train` | `delta_yF` | 602,390 | 0.0892 | 0.0378 | -3.0588 | 0.9606 | 0.2551 |
| `train` | `delta_yT` | 602,390 | 0.2382 | 0.1707 | -0.9620 | 0.8990 | 0.7678 |
| `validation` | `all` | 54,637 | 0.1121 | 0.0610 | -2.6727 | 0.9523 | 0.4101 |
| `validation` | `yN` | 54,637 | 0.0646 | 0.0240 | -3.8236 | 0.9730 | 0.1602 |
| `validation` | `yF` | 54,637 | 0.0860 | 0.0350 | -2.9516 | 0.9961 | 0.5285 |
| `validation` | `yT` | 54,637 | 0.2434 | 0.1640 | -0.9307 | 0.8944 | 0.8021 |
| `validation` | `sigma_N` | 54,637 | 0.0804 | 0.0187 | -3.4878 | 0.9780 | 0.1962 |
| `validation` | `sigma_F` | 54,637 | 0.0459 | 0.0142 | -3.3342 | 0.9932 | 0.2664 |
| `validation` | `sigma_T` | 54,637 | 0.0943 | 0.0528 | -2.0237 | 0.8616 | 0.2786 |
| `validation` | `delta_yN` | 54,637 | 0.0661 | 0.0289 | -3.4781 | 0.9767 | 0.1690 |
| `validation` | `delta_yF` | 54,637 | 0.0884 | 0.0395 | -3.0744 | 0.9933 | 0.4873 |
| `validation` | `delta_yT` | 54,637 | 0.2396 | 0.1716 | -0.9505 | 0.9047 | 0.8024 |
| `test` | `all` | 40,606 | 0.1143 | 0.0618 | -2.5111 | 0.9563 | 0.4573 |
| `test` | `yN` | 40,606 | 0.0805 | 0.0330 | -3.4653 | 0.9589 | 0.1917 |
| `test` | `yF` | 40,606 | 0.0957 | 0.0423 | -2.6910 | 0.9963 | 0.6511 |
| `test` | `yT` | 40,606 | 0.2237 | 0.1495 | -1.0002 | 0.9126 | 0.8065 |
| `test` | `sigma_N` | 40,606 | 0.0950 | 0.0265 | -3.2236 | 0.9683 | 0.2343 |
| `test` | `sigma_F` | 40,606 | 0.0547 | 0.0180 | -3.1351 | 0.9912 | 0.3226 |
| `test` | `sigma_T` | 40,606 | 0.0765 | 0.0450 | -2.0794 | 0.8981 | 0.2958 |
| `test` | `delta_yN` | 40,606 | 0.0839 | 0.0377 | -3.1752 | 0.9643 | 0.2023 |
| `test` | `delta_yF` | 40,606 | 0.0977 | 0.0464 | -2.8156 | 0.9942 | 0.6035 |
| `test` | `delta_yT` | 40,606 | 0.2208 | 0.1577 | -1.0146 | 0.9223 | 0.8077 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.6500 | 0.0240 | 0.0646 | 1.0086 |
| `yF` | 0.6500 | 0.0350 | 0.0860 | 1.0145 |
| `yT` | 0.6500 | 0.1640 | 0.2434 | 1.0261 |
| `sigma_N` | 0.0000 | 0.0187 | 0.0804 | 1.0006 |
| `sigma_F` | 0.0000 | 0.0142 | 0.0459 | 1.0023 |
| `sigma_T` | 0.3500 | 0.0528 | 0.0943 | 1.0328 |
| `delta_yN` | 0.9000 | 0.0289 | 0.0661 | 1.0094 |
| `delta_yF` | 1.0000 | 0.0395 | 0.0884 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1716 | 0.2396 | 1.0056 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1143 | 0.1547 | 0.2615 | 0.0618 | 0.0753 | 0.1794 |
| `train` | `all` | 0.1028 | 0.1422 | 0.2770 | 0.0552 | 0.0673 | 0.1800 |
| `validation` | `all` | 0.1121 | 0.1537 | 0.2707 | 0.0610 | 0.0754 | 0.1912 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse1_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse1_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse1_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse1_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse1_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse1_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse1_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse1_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse1_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd128_mse1_lr0p001_seed1729/pipe_grud_manifest.json`
