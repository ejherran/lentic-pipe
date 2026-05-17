# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:54:38.740369+00:00`
Started at UTC: `2026-05-17T01:53:49.236751+00:00`
Status: `completed`

## Scope

This step trains the minimal probabilistic temporal model over the frozen PIPE sequence dataset.
It predicts the next 9-dimensional fuzzy state vector and estimates diagonal Gaussian uncertainty.
Checkpoint selection evaluates the same blended output used by the final model.

## Configuration

- History length: `12`
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
| `train` | 378,557 | 378,557 |
| `validation` | 22,087 | 22,087 |
| `test` | 17,420 | 17,420 |

## Best Epoch

- Epoch: `19`
- Selection metric: `balanced`
- Selection objective: `0.7835`
- Validation loss: `-3.2654`
- Validation RMSE all: `0.1177`
- Validation MAE all: `0.0637`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 378,557 | 0.0993 | 0.0534 | -3.0284 | 0.9503 | 0.2932 |
| `train` | `yN` | 378,557 | 0.0400 | 0.0087 | -4.3925 | 0.9879 | 0.0630 |
| `train` | `yF` | 378,557 | 0.0853 | 0.0293 | -3.2863 | 0.9708 | 0.2311 |
| `train` | `yT` | 378,557 | 0.2470 | 0.1624 | -0.9101 | 0.8881 | 0.7974 |
| `train` | `sigma_N` | 378,557 | 0.0412 | 0.0052 | -4.3654 | 0.9925 | 0.0749 |
| `train` | `sigma_F` | 378,557 | 0.0459 | 0.0127 | -3.4594 | 0.9850 | 0.1571 |
| `train` | `sigma_T` | 378,557 | 0.0720 | 0.0429 | -2.1284 | 0.8719 | 0.2490 |
| `train` | `delta_yN` | 378,557 | 0.0400 | 0.0100 | -4.3461 | 0.9888 | 0.0649 |
| `train` | `delta_yF` | 378,557 | 0.0827 | 0.0326 | -3.4310 | 0.9688 | 0.2120 |
| `train` | `delta_yT` | 378,557 | 0.2400 | 0.1769 | -0.9363 | 0.8991 | 0.7894 |
| `validation` | `all` | 22,087 | 0.1177 | 0.0637 | -2.7491 | 0.9454 | 0.3890 |
| `validation` | `yN` | 22,087 | 0.0661 | 0.0248 | -3.8349 | 0.9556 | 0.1256 |
| `validation` | `yF` | 22,087 | 0.0880 | 0.0347 | -3.1471 | 0.9952 | 0.4340 |
| `validation` | `yT` | 22,087 | 0.2605 | 0.1728 | -0.8444 | 0.8805 | 0.8377 |
| `validation` | `sigma_N` | 22,087 | 0.0853 | 0.0197 | -3.6237 | 0.9749 | 0.1460 |
| `validation` | `sigma_F` | 22,087 | 0.0489 | 0.0146 | -3.3696 | 0.9947 | 0.2831 |
| `validation` | `sigma_T` | 22,087 | 0.0974 | 0.0514 | -1.9188 | 0.8633 | 0.3054 |
| `validation` | `delta_yN` | 22,087 | 0.0660 | 0.0270 | -3.7990 | 0.9583 | 0.1318 |
| `validation` | `delta_yF` | 22,087 | 0.0917 | 0.0404 | -3.3336 | 0.9955 | 0.4106 |
| `validation` | `delta_yT` | 22,087 | 0.2554 | 0.1880 | -0.8707 | 0.8906 | 0.8266 |
| `test` | `all` | 17,420 | 0.1133 | 0.0621 | -2.4928 | 0.9532 | 0.4544 |
| `test` | `yN` | 17,420 | 0.0831 | 0.0363 | -3.2753 | 0.9312 | 0.1675 |
| `test` | `yF` | 17,420 | 0.0952 | 0.0416 | -2.7538 | 0.9962 | 0.5903 |
| `test` | `yT` | 17,420 | 0.2208 | 0.1463 | -0.9888 | 0.9212 | 0.8492 |
| `test` | `sigma_N` | 17,420 | 0.0962 | 0.0278 | -3.1996 | 0.9602 | 0.1962 |
| `test` | `sigma_F` | 17,420 | 0.0515 | 0.0175 | -3.0217 | 0.9932 | 0.3787 |
| `test` | `sigma_T` | 17,420 | 0.0765 | 0.0426 | -2.0119 | 0.9146 | 0.3404 |
| `test` | `delta_yN` | 17,420 | 0.0829 | 0.0392 | -3.2581 | 0.9364 | 0.1769 |
| `test` | `delta_yF` | 17,420 | 0.0965 | 0.0469 | -2.9173 | 0.9961 | 0.5582 |
| `test` | `delta_yT` | 17,420 | 0.2170 | 0.1607 | -1.0091 | 0.9299 | 0.8321 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.5000 | 0.0248 | 0.0661 | 1.0315 |
| `yF` | 0.3500 | 0.0347 | 0.0880 | 1.0144 |
| `yT` | 0.6500 | 0.1728 | 0.2605 | 1.0274 |
| `sigma_N` | 0.0000 | 0.0197 | 0.0853 | 1.0005 |
| `sigma_F` | 0.0000 | 0.0146 | 0.0489 | 1.0001 |
| `sigma_T` | 0.0000 | 0.0514 | 0.0974 | 1.0102 |
| `delta_yN` | 0.9000 | 0.0270 | 0.0660 | 1.0075 |
| `delta_yF` | 1.0000 | 0.0404 | 0.0917 | 1.0034 |
| `delta_yT` | 1.0000 | 0.1880 | 0.2554 | 1.0056 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1133 | 0.1502 | 0.2457 | 0.0621 | 0.0737 | 0.1575 |
| `train` | `all` | 0.0993 | 0.1355 | 0.2670 | 0.0534 | 0.0645 | 0.1720 |
| `validation` | `all` | 0.1177 | 0.1575 | 0.2526 | 0.0637 | 0.0777 | 0.1804 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse1_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse1_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse1_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse1_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse1_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse1_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse1_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse1_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse1_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse1_lr0p001_seed1729/pipe_grud_manifest.json`
