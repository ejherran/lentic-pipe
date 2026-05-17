# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:47:54.507001+00:00`
Started at UTC: `2026-05-17T01:46:35.356449+00:00`
Status: `completed`

## Scope

This step trains the minimal probabilistic temporal model over the frozen PIPE sequence dataset.
It predicts the next 9-dimensional fuzzy state vector and estimates diagonal Gaussian uncertainty.
Checkpoint selection evaluates the same blended output used by the final model.

## Configuration

- History length: `6`
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
| `train` | 602,390 | 602,390 |
| `validation` | 54,637 | 54,637 |
| `test` | 40,606 | 40,606 |

## Best Epoch

- Epoch: `20`
- Selection metric: `balanced`
- Selection objective: `0.7754`
- Validation loss: `-3.2241`
- Validation RMSE all: `0.1137`
- Validation MAE all: `0.0612`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 602,390 | 0.1040 | 0.0550 | -2.9254 | 0.9467 | 0.3108 |
| `train` | `yN` | 602,390 | 0.0480 | 0.0112 | -4.2952 | 0.9883 | 0.0863 |
| `train` | `yF` | 602,390 | 0.0903 | 0.0323 | -3.1638 | 0.9619 | 0.2730 |
| `train` | `yT` | 602,390 | 0.2483 | 0.1632 | -0.9108 | 0.8843 | 0.7852 |
| `train` | `sigma_N` | 602,390 | 0.0488 | 0.0072 | -4.2730 | 0.9906 | 0.0919 |
| `train` | `sigma_F` | 602,390 | 0.0483 | 0.0140 | -3.3174 | 0.9792 | 0.1639 |
| `train` | `sigma_T` | 602,390 | 0.0743 | 0.0445 | -2.1326 | 0.8657 | 0.2371 |
| `train` | `delta_yN` | 602,390 | 0.0494 | 0.0143 | -4.1130 | 0.9876 | 0.0825 |
| `train` | `delta_yF` | 602,390 | 0.0887 | 0.0338 | -3.1818 | 0.9625 | 0.2865 |
| `train` | `delta_yT` | 602,390 | 0.2398 | 0.1743 | -0.9406 | 0.9006 | 0.7907 |
| `validation` | `all` | 54,637 | 0.1137 | 0.0612 | -2.7252 | 0.9531 | 0.4307 |
| `validation` | `yN` | 54,637 | 0.0655 | 0.0253 | -3.7445 | 0.9757 | 0.1822 |
| `validation` | `yF` | 54,637 | 0.0885 | 0.0349 | -3.1685 | 0.9942 | 0.5210 |
| `validation` | `yT` | 54,637 | 0.2487 | 0.1641 | -0.9012 | 0.8905 | 0.8192 |
| `validation` | `sigma_N` | 54,637 | 0.0804 | 0.0187 | -3.5730 | 0.9777 | 0.1882 |
| `validation` | `sigma_F` | 54,637 | 0.0459 | 0.0142 | -3.4136 | 0.9946 | 0.3097 |
| `validation` | `sigma_T` | 54,637 | 0.0970 | 0.0519 | -1.9761 | 0.8680 | 0.2943 |
| `validation` | `delta_yN` | 54,637 | 0.0654 | 0.0279 | -3.5916 | 0.9754 | 0.1722 |
| `validation` | `delta_yF` | 54,637 | 0.0887 | 0.0367 | -3.2371 | 0.9951 | 0.5581 |
| `validation` | `delta_yT` | 54,637 | 0.2431 | 0.1767 | -0.9212 | 0.9063 | 0.8318 |
| `test` | `all` | 40,606 | 0.1157 | 0.0620 | -2.5519 | 0.9568 | 0.4791 |
| `test` | `yN` | 40,606 | 0.0819 | 0.0342 | -3.3779 | 0.9616 | 0.2157 |
| `test` | `yF` | 40,606 | 0.0986 | 0.0423 | -2.8918 | 0.9950 | 0.6376 |
| `test` | `yT` | 40,606 | 0.2287 | 0.1496 | -0.9712 | 0.9088 | 0.8221 |
| `test` | `sigma_N` | 40,606 | 0.0950 | 0.0265 | -3.3029 | 0.9678 | 0.2245 |
| `test` | `sigma_F` | 40,606 | 0.0547 | 0.0180 | -3.1974 | 0.9931 | 0.3748 |
| `test` | `sigma_T` | 40,606 | 0.0784 | 0.0444 | -2.0416 | 0.9021 | 0.3102 |
| `test` | `delta_yN` | 40,606 | 0.0826 | 0.0367 | -3.2537 | 0.9618 | 0.2046 |
| `test` | `delta_yF` | 40,606 | 0.0980 | 0.0441 | -2.9453 | 0.9964 | 0.6862 |
| `test` | `delta_yT` | 40,606 | 0.2234 | 0.1622 | -0.9856 | 0.9242 | 0.8363 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.5000 | 0.0253 | 0.0655 | 1.0279 |
| `yF` | 0.5000 | 0.0349 | 0.0885 | 1.0097 |
| `yT` | 0.5000 | 0.1641 | 0.2487 | 1.0341 |
| `sigma_N` | 0.0000 | 0.0187 | 0.0804 | 1.0000 |
| `sigma_F` | 0.0000 | 0.0142 | 0.0459 | 1.0025 |
| `sigma_T` | 0.2000 | 0.0519 | 0.0970 | 1.0219 |
| `delta_yN` | 0.9000 | 0.0279 | 0.0654 | 1.0047 |
| `delta_yF` | 1.0000 | 0.0367 | 0.0887 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1767 | 0.2431 | 1.0054 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1157 | 0.1547 | 0.2522 | 0.0620 | 0.0753 | 0.1770 |
| `train` | `all` | 0.1040 | 0.1422 | 0.2687 | 0.0550 | 0.0673 | 0.1832 |
| `validation` | `all` | 0.1137 | 0.1537 | 0.2603 | 0.0612 | 0.0754 | 0.1888 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse1_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse1_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse1_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse1_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse1_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse1_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse1_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse1_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse1_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse1_lr0p001_seed1729/pipe_grud_manifest.json`
