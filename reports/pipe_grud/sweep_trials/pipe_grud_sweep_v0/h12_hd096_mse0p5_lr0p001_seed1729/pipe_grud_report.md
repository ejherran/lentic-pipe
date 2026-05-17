# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:56:24.867056+00:00`
Started at UTC: `2026-05-17T01:55:33.131985+00:00`
Status: `completed`

## Scope

This step trains the minimal probabilistic temporal model over the frozen PIPE sequence dataset.
It predicts the next 9-dimensional fuzzy state vector and estimates diagonal Gaussian uncertainty.
Checkpoint selection evaluates the same blended output used by the final model.

## Configuration

- History length: `12`
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
| `train` | 378,557 | 378,557 |
| `validation` | 22,087 | 22,087 |
| `test` | 17,420 | 17,420 |

## Best Epoch

- Epoch: `3`
- Selection metric: `balanced`
- Selection objective: `0.7460`
- Validation loss: `-2.0283`
- Validation RMSE all: `0.1121`
- Validation MAE all: `0.0607`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 378,557 | 0.0953 | 0.0511 | -2.1581 | 0.9320 | 0.2995 |
| `train` | `yN` | 378,557 | 0.0409 | 0.0083 | -2.8635 | 0.9714 | 0.1116 |
| `train` | `yF` | 378,557 | 0.0850 | 0.0302 | -2.0282 | 0.9275 | 0.2504 |
| `train` | `yT` | 378,557 | 0.2264 | 0.1541 | -0.9885 | 0.8929 | 0.7409 |
| `train` | `sigma_N` | 378,557 | 0.0412 | 0.0052 | -2.8547 | 0.9828 | 0.1161 |
| `train` | `sigma_F` | 378,557 | 0.0459 | 0.0127 | -2.6208 | 0.9523 | 0.1460 |
| `train` | `sigma_T` | 378,557 | 0.0708 | 0.0436 | -2.1626 | 0.8689 | 0.2270 |
| `train` | `delta_yN` | 378,557 | 0.0417 | 0.0147 | -2.8400 | 0.9719 | 0.1188 |
| `train` | `delta_yF` | 378,557 | 0.0821 | 0.0365 | -2.0675 | 0.9284 | 0.2505 |
| `train` | `delta_yT` | 378,557 | 0.2239 | 0.1543 | -0.9974 | 0.8921 | 0.7344 |
| `validation` | `all` | 22,087 | 0.1121 | 0.0607 | -1.6857 | 0.9011 | 0.3031 |
| `validation` | `yN` | 22,087 | 0.0678 | 0.0249 | -1.8738 | 0.8803 | 0.1140 |
| `validation` | `yF` | 22,087 | 0.0871 | 0.0351 | -2.0244 | 0.9136 | 0.2538 |
| `validation` | `yT` | 22,087 | 0.2374 | 0.1642 | -0.9381 | 0.8834 | 0.7465 |
| `validation` | `sigma_N` | 22,087 | 0.0853 | 0.0197 | -1.0008 | 0.9514 | 0.1187 |
| `validation` | `sigma_F` | 22,087 | 0.0489 | 0.0146 | -2.5867 | 0.9516 | 0.1485 |
| `validation` | `sigma_T` | 22,087 | 0.0957 | 0.0522 | -1.7779 | 0.8449 | 0.2303 |
| `validation` | `delta_yN` | 22,087 | 0.0686 | 0.0306 | -1.9608 | 0.8815 | 0.1215 |
| `validation` | `delta_yF` | 22,087 | 0.0845 | 0.0409 | -2.0567 | 0.9157 | 0.2543 |
| `validation` | `delta_yT` | 22,087 | 0.2336 | 0.1637 | -0.9524 | 0.8873 | 0.7406 |
| `test` | `all` | 17,420 | 0.1084 | 0.0582 | -1.5079 | 0.8966 | 0.3074 |
| `test` | `yN` | 17,420 | 0.0853 | 0.0365 | -1.0602 | 0.8284 | 0.1166 |
| `test` | `yF` | 17,420 | 0.0943 | 0.0418 | -1.9271 | 0.9054 | 0.2579 |
| `test` | `yT` | 17,420 | 0.1999 | 0.1344 | -1.0947 | 0.9240 | 0.7536 |
| `test` | `sigma_N` | 17,420 | 0.0962 | 0.0278 | -0.5237 | 0.9230 | 0.1219 |
| `test` | `sigma_F` | 17,420 | 0.0515 | 0.0175 | -2.5297 | 0.9417 | 0.1511 |
| `test` | `sigma_T` | 17,420 | 0.0753 | 0.0434 | -2.1165 | 0.8849 | 0.2331 |
| `test` | `delta_yN` | 17,420 | 0.0856 | 0.0423 | -1.2448 | 0.8262 | 0.1244 |
| `test` | `delta_yF` | 17,420 | 0.0917 | 0.0479 | -1.9672 | 0.9087 | 0.2583 |
| `test` | `delta_yT` | 17,420 | 0.1960 | 0.1325 | -1.1078 | 0.9270 | 0.7499 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.3500 | 0.0249 | 0.0678 | 1.0353 |
| `yF` | 0.3500 | 0.0351 | 0.0871 | 1.0327 |
| `yT` | 0.9000 | 0.1642 | 0.2374 | 1.0094 |
| `sigma_N` | 0.0000 | 0.0197 | 0.0853 | 1.0019 |
| `sigma_F` | 0.0000 | 0.0146 | 0.0489 | 1.0082 |
| `sigma_T` | 0.3500 | 0.0522 | 0.0957 | 1.0201 |
| `delta_yN` | 0.8000 | 0.0306 | 0.0686 | 1.0125 |
| `delta_yF` | 0.9000 | 0.0409 | 0.0845 | 1.0076 |
| `delta_yT` | 1.0000 | 0.1637 | 0.2336 | 1.0050 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1084 | 0.1502 | 0.2781 | 0.0582 | 0.0737 | 0.2098 |
| `train` | `all` | 0.0953 | 0.1355 | 0.2968 | 0.0511 | 0.0645 | 0.2085 |
| `validation` | `all` | 0.1121 | 0.1575 | 0.2882 | 0.0607 | 0.0777 | 0.2198 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p5_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p5_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p5_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p5_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p5_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p5_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p5_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p5_lr0p001_seed1729/pipe_grud_manifest.json`
