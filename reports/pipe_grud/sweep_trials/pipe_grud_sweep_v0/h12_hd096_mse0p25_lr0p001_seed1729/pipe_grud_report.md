# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:55:30.919809+00:00`
Started at UTC: `2026-05-17T01:54:40.895567+00:00`
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
| `train` | 378,557 | 378,557 |
| `validation` | 22,087 | 22,087 |
| `test` | 17,420 | 17,420 |

## Best Epoch

- Epoch: `3`
- Selection metric: `balanced`
- Selection objective: `0.7568`
- Validation loss: `-2.1009`
- Validation RMSE all: `0.1125`
- Validation MAE all: `0.0621`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 378,557 | 0.0960 | 0.0526 | -2.1916 | 0.9331 | 0.2984 |
| `train` | `yN` | 378,557 | 0.0408 | 0.0084 | -2.9706 | 0.9726 | 0.1071 |
| `train` | `yF` | 378,557 | 0.0850 | 0.0305 | -2.0694 | 0.9290 | 0.2466 |
| `train` | `yT` | 378,557 | 0.2258 | 0.1545 | -0.9910 | 0.8935 | 0.7385 |
| `train` | `sigma_N` | 378,557 | 0.0412 | 0.0052 | -2.9397 | 0.9841 | 0.1145 |
| `train` | `sigma_F` | 378,557 | 0.0459 | 0.0127 | -2.6373 | 0.9560 | 0.1492 |
| `train` | `sigma_T` | 378,557 | 0.0704 | 0.0438 | -2.1719 | 0.8691 | 0.2271 |
| `train` | `delta_yN` | 378,557 | 0.0423 | 0.0179 | -2.9099 | 0.9726 | 0.1127 |
| `train` | `delta_yF` | 378,557 | 0.0868 | 0.0440 | -2.0440 | 0.9289 | 0.2477 |
| `train` | `delta_yT` | 378,557 | 0.2256 | 0.1563 | -0.9905 | 0.8925 | 0.7420 |
| `validation` | `all` | 22,087 | 0.1125 | 0.0621 | -1.7503 | 0.9045 | 0.3041 |
| `validation` | `yN` | 22,087 | 0.0676 | 0.0249 | -2.0248 | 0.8826 | 0.1109 |
| `validation` | `yF` | 22,087 | 0.0870 | 0.0353 | -2.0802 | 0.9182 | 0.2525 |
| `validation` | `yT` | 22,087 | 0.2369 | 0.1652 | -0.9390 | 0.8855 | 0.7473 |
| `validation` | `sigma_N` | 22,087 | 0.0853 | 0.0197 | -1.1885 | 0.9555 | 0.1188 |
| `validation` | `sigma_F` | 22,087 | 0.0489 | 0.0146 | -2.6229 | 0.9566 | 0.1532 |
| `validation` | `sigma_T` | 22,087 | 0.0945 | 0.0526 | -1.8202 | 0.8504 | 0.2322 |
| `validation` | `delta_yN` | 22,087 | 0.0687 | 0.0327 | -2.0687 | 0.8858 | 0.1169 |
| `validation` | `delta_yF` | 22,087 | 0.0882 | 0.0477 | -2.0631 | 0.9176 | 0.2541 |
| `validation` | `delta_yT` | 22,087 | 0.2355 | 0.1664 | -0.9449 | 0.8878 | 0.7509 |
| `test` | `all` | 17,420 | 0.1091 | 0.0596 | -1.6054 | 0.9020 | 0.3116 |
| `test` | `yN` | 17,420 | 0.0851 | 0.0367 | -1.3225 | 0.8351 | 0.1160 |
| `test` | `yF` | 17,420 | 0.0942 | 0.0420 | -1.9876 | 0.9113 | 0.2600 |
| `test` | `yT` | 17,420 | 0.2002 | 0.1358 | -1.0917 | 0.9268 | 0.7591 |
| `test` | `sigma_N` | 17,420 | 0.0962 | 0.0278 | -0.8224 | 0.9285 | 0.1243 |
| `test` | `sigma_F` | 17,420 | 0.0515 | 0.0175 | -2.5696 | 0.9486 | 0.1576 |
| `test` | `sigma_T` | 17,420 | 0.0748 | 0.0433 | -2.1334 | 0.8896 | 0.2374 |
| `test` | `delta_yN` | 17,420 | 0.0853 | 0.0439 | -1.4526 | 0.8371 | 0.1224 |
| `test` | `delta_yF` | 17,420 | 0.0950 | 0.0531 | -1.9787 | 0.9130 | 0.2620 |
| `test` | `delta_yT` | 17,420 | 0.1994 | 0.1361 | -1.0906 | 0.9277 | 0.7652 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.3500 | 0.0249 | 0.0676 | 1.0348 |
| `yF` | 0.3500 | 0.0353 | 0.0870 | 1.0360 |
| `yT` | 0.9000 | 0.1652 | 0.2369 | 1.0112 |
| `sigma_N` | 0.0000 | 0.0197 | 0.0853 | 1.0011 |
| `sigma_F` | 0.0000 | 0.0146 | 0.0489 | 1.0089 |
| `sigma_T` | 0.5000 | 0.0526 | 0.0945 | 1.0211 |
| `delta_yN` | 0.8000 | 0.0327 | 0.0687 | 1.0164 |
| `delta_yF` | 0.8000 | 0.0477 | 0.0882 | 1.0151 |
| `delta_yT` | 1.0000 | 0.1664 | 0.2355 | 1.0054 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1091 | 0.1502 | 0.2738 | 0.0596 | 0.0737 | 0.1915 |
| `train` | `all` | 0.0960 | 0.1355 | 0.2920 | 0.0526 | 0.0645 | 0.1849 |
| `validation` | `all` | 0.1125 | 0.1575 | 0.2855 | 0.0621 | 0.0777 | 0.2008 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p25_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p25_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p25_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p25_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p25_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p25_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p25_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse0p25_lr0p001_seed1729/pipe_grud_manifest.json`
