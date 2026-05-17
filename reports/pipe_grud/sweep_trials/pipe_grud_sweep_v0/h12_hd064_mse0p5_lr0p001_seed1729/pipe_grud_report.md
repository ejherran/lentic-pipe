# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:53:47.078441+00:00`
Started at UTC: `2026-05-17T01:52:57.849862+00:00`
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
| `train` | 378,557 | 378,557 |
| `validation` | 22,087 | 22,087 |
| `test` | 17,420 | 17,420 |

## Best Epoch

- Epoch: `18`
- Selection metric: `balanced`
- Selection objective: `0.7733`
- Validation loss: `-3.3078`
- Validation RMSE all: `0.1175`
- Validation MAE all: `0.0622`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 378,557 | 0.0995 | 0.0523 | -3.0546 | 0.9484 | 0.2865 |
| `train` | `yN` | 378,557 | 0.0399 | 0.0090 | -4.3582 | 0.9861 | 0.0601 |
| `train` | `yF` | 378,557 | 0.0869 | 0.0295 | -3.4390 | 0.9598 | 0.1904 |
| `train` | `yT` | 378,557 | 0.2466 | 0.1611 | -0.9090 | 0.8891 | 0.8031 |
| `train` | `sigma_N` | 378,557 | 0.0412 | 0.0052 | -4.3652 | 0.9918 | 0.0705 |
| `train` | `sigma_F` | 378,557 | 0.0459 | 0.0127 | -3.5243 | 0.9833 | 0.1395 |
| `train` | `sigma_T` | 378,557 | 0.0720 | 0.0429 | -2.1251 | 0.8696 | 0.2465 |
| `train` | `delta_yN` | 378,557 | 0.0398 | 0.0080 | -4.4153 | 0.9872 | 0.0621 |
| `train` | `delta_yF` | 378,557 | 0.0821 | 0.0323 | -3.4251 | 0.9703 | 0.2066 |
| `train` | `delta_yT` | 378,557 | 0.2407 | 0.1699 | -0.9300 | 0.8983 | 0.7994 |
| `validation` | `all` | 22,087 | 0.1175 | 0.0622 | -2.7954 | 0.9423 | 0.3679 |
| `validation` | `yN` | 22,087 | 0.0660 | 0.0251 | -3.7921 | 0.9476 | 0.1127 |
| `validation` | `yF` | 22,087 | 0.0890 | 0.0348 | -3.4604 | 0.9910 | 0.3597 |
| `validation` | `yT` | 22,087 | 0.2601 | 0.1712 | -0.8472 | 0.8790 | 0.8358 |
| `validation` | `sigma_N` | 22,087 | 0.0853 | 0.0197 | -3.5667 | 0.9744 | 0.1305 |
| `validation` | `sigma_F` | 22,087 | 0.0489 | 0.0146 | -3.5045 | 0.9937 | 0.2454 |
| `validation` | `sigma_T` | 22,087 | 0.0974 | 0.0514 | -1.9094 | 0.8606 | 0.2955 |
| `validation` | `delta_yN` | 22,087 | 0.0662 | 0.0253 | -3.8546 | 0.9502 | 0.1184 |
| `validation` | `delta_yF` | 22,087 | 0.0905 | 0.0399 | -3.3480 | 0.9950 | 0.3819 |
| `validation` | `delta_yT` | 22,087 | 0.2542 | 0.1779 | -0.8754 | 0.8896 | 0.8309 |
| `test` | `all` | 17,420 | 0.1130 | 0.0604 | -2.5370 | 0.9492 | 0.4247 |
| `test` | `yN` | 17,420 | 0.0830 | 0.0365 | -3.2100 | 0.9204 | 0.1488 |
| `test` | `yF` | 17,420 | 0.0964 | 0.0414 | -3.0592 | 0.9910 | 0.4902 |
| `test` | `yT` | 17,420 | 0.2206 | 0.1443 | -0.9897 | 0.9205 | 0.8457 |
| `test` | `sigma_N` | 17,420 | 0.0962 | 0.0278 | -3.1263 | 0.9579 | 0.1737 |
| `test` | `sigma_F` | 17,420 | 0.0515 | 0.0175 | -3.1716 | 0.9925 | 0.3268 |
| `test` | `sigma_T` | 17,420 | 0.0765 | 0.0426 | -2.0213 | 0.9118 | 0.3277 |
| `test` | `delta_yN` | 17,420 | 0.0831 | 0.0379 | -3.2761 | 0.9228 | 0.1573 |
| `test` | `delta_yF` | 17,420 | 0.0952 | 0.0461 | -2.9651 | 0.9958 | 0.5156 |
| `test` | `delta_yT` | 17,420 | 0.2148 | 0.1490 | -1.0141 | 0.9299 | 0.8361 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.5000 | 0.0251 | 0.0660 | 1.0375 |
| `yF` | 0.2000 | 0.0348 | 0.0890 | 1.0223 |
| `yT` | 0.6500 | 0.1712 | 0.2601 | 1.0229 |
| `sigma_N` | 0.0000 | 0.0197 | 0.0853 | 1.0012 |
| `sigma_F` | 0.0000 | 0.0146 | 0.0489 | 1.0000 |
| `sigma_T` | 0.0000 | 0.0514 | 0.0974 | 1.0130 |
| `delta_yN` | 0.9000 | 0.0253 | 0.0662 | 1.0053 |
| `delta_yF` | 1.0000 | 0.0399 | 0.0905 | 1.0038 |
| `delta_yT` | 1.0000 | 0.1779 | 0.2542 | 1.0040 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1130 | 0.1502 | 0.2474 | 0.0604 | 0.0737 | 0.1811 |
| `train` | `all` | 0.0995 | 0.1355 | 0.2663 | 0.0523 | 0.0645 | 0.1895 |
| `validation` | `all` | 0.1175 | 0.1575 | 0.2538 | 0.0622 | 0.0777 | 0.1996 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p5_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p5_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p5_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p5_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p5_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p5_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p5_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p5_lr0p001_seed1729/pipe_grud_manifest.json`
