# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:43:48.392975+00:00`
Started at UTC: `2026-05-17T01:42:31.583784+00:00`
Status: `completed`

## Scope

This step trains the minimal probabilistic temporal model over the frozen PIPE sequence dataset.
It predicts the next 9-dimensional fuzzy state vector and estimates diagonal Gaussian uncertainty.
Checkpoint selection evaluates the same blended output used by the final model.

## Configuration

- History length: `6`
- Hidden dimension: `64`
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
- Selection objective: `0.7773`
- Validation loss: `-3.2924`
- Validation RMSE all: `0.1138`
- Validation MAE all: `0.0614`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 602,390 | 0.1038 | 0.0550 | -2.9518 | 0.9471 | 0.3001 |
| `train` | `yN` | 602,390 | 0.0480 | 0.0102 | -4.3367 | 0.9866 | 0.0777 |
| `train` | `yF` | 602,390 | 0.0894 | 0.0325 | -3.2046 | 0.9631 | 0.2391 |
| `train` | `yT` | 602,390 | 0.2455 | 0.1647 | -0.9136 | 0.8888 | 0.7952 |
| `train` | `sigma_N` | 602,390 | 0.0488 | 0.0072 | -4.2659 | 0.9899 | 0.0862 |
| `train` | `sigma_F` | 602,390 | 0.0483 | 0.0140 | -3.3348 | 0.9809 | 0.1526 |
| `train` | `sigma_T` | 602,390 | 0.0759 | 0.0441 | -2.1067 | 0.8638 | 0.2406 |
| `train` | `delta_yN` | 602,390 | 0.0496 | 0.0132 | -4.2431 | 0.9873 | 0.0798 |
| `train` | `delta_yF` | 602,390 | 0.0882 | 0.0345 | -3.2292 | 0.9648 | 0.2357 |
| `train` | `delta_yT` | 602,390 | 0.2406 | 0.1741 | -0.9317 | 0.8988 | 0.7943 |
| `validation` | `all` | 54,637 | 0.1138 | 0.0614 | -2.7758 | 0.9521 | 0.4025 |
| `validation` | `yN` | 54,637 | 0.0653 | 0.0245 | -3.7915 | 0.9706 | 0.1602 |
| `validation` | `yF` | 54,637 | 0.0869 | 0.0348 | -3.3397 | 0.9939 | 0.4533 |
| `validation` | `yT` | 54,637 | 0.2457 | 0.1654 | -0.9026 | 0.8944 | 0.8330 |
| `validation` | `sigma_N` | 54,637 | 0.0804 | 0.0187 | -3.6068 | 0.9772 | 0.1700 |
| `validation` | `sigma_F` | 54,637 | 0.0459 | 0.0142 | -3.4309 | 0.9945 | 0.2797 |
| `validation` | `sigma_T` | 54,637 | 0.0987 | 0.0512 | -1.9330 | 0.8680 | 0.2919 |
| `validation` | `delta_yN` | 54,637 | 0.0671 | 0.0281 | -3.7071 | 0.9727 | 0.1641 |
| `validation` | `delta_yF` | 54,637 | 0.0910 | 0.0391 | -3.3564 | 0.9947 | 0.4404 |
| `validation` | `delta_yT` | 54,637 | 0.2434 | 0.1762 | -0.9145 | 0.9032 | 0.8300 |
| `test` | `all` | 40,606 | 0.1157 | 0.0624 | -2.6142 | 0.9559 | 0.4485 |
| `test` | `yN` | 40,606 | 0.0820 | 0.0336 | -3.4473 | 0.9567 | 0.1970 |
| `test` | `yF` | 40,606 | 0.0962 | 0.0420 | -3.0581 | 0.9941 | 0.5610 |
| `test` | `yT` | 40,606 | 0.2268 | 0.1522 | -0.9678 | 0.9135 | 0.8377 |
| `test` | `sigma_N` | 40,606 | 0.0950 | 0.0265 | -3.3270 | 0.9662 | 0.2086 |
| `test` | `sigma_F` | 40,606 | 0.0547 | 0.0180 | -3.2661 | 0.9929 | 0.3416 |
| `test` | `sigma_T` | 40,606 | 0.0798 | 0.0439 | -2.0209 | 0.9029 | 0.3104 |
| `test` | `delta_yN` | 40,606 | 0.0845 | 0.0376 | -3.3855 | 0.9589 | 0.2028 |
| `test` | `delta_yF` | 40,606 | 0.0980 | 0.0453 | -3.0761 | 0.9956 | 0.5415 |
| `test` | `delta_yT` | 40,606 | 0.2243 | 0.1622 | -0.9788 | 0.9219 | 0.8363 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.5000 | 0.0245 | 0.0653 | 1.0167 |
| `yF` | 0.5000 | 0.0348 | 0.0869 | 1.0111 |
| `yT` | 0.6500 | 0.1654 | 0.2457 | 1.0312 |
| `sigma_N` | 0.0000 | 0.0187 | 0.0804 | 1.0007 |
| `sigma_F` | 0.0000 | 0.0142 | 0.0459 | 1.0016 |
| `sigma_T` | 0.0000 | 0.0512 | 0.0987 | 1.0195 |
| `delta_yN` | 0.8000 | 0.0281 | 0.0671 | 1.0048 |
| `delta_yF` | 1.0000 | 0.0391 | 0.0910 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1762 | 0.2434 | 1.0060 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1157 | 0.1547 | 0.2522 | 0.0624 | 0.0753 | 0.1720 |
| `train` | `all` | 0.1038 | 0.1422 | 0.2700 | 0.0550 | 0.0673 | 0.1835 |
| `validation` | `all` | 0.1138 | 0.1537 | 0.2593 | 0.0614 | 0.0754 | 0.1861 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse1_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse1_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse1_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse1_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse1_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse1_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse1_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse1_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse1_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse1_lr0p001_seed1729/pipe_grud_manifest.json`
