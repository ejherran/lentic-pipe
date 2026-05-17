# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T02:00:23.352934+00:00`
Started at UTC: `2026-05-17T01:59:25.730474+00:00`
Status: `completed`

## Scope

This step trains the minimal probabilistic temporal model over the frozen PIPE sequence dataset.
It predicts the next 9-dimensional fuzzy state vector and estimates diagonal Gaussian uncertainty.
Checkpoint selection evaluates the same blended output used by the final model.

## Configuration

- History length: `12`
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
| `train` | 378,557 | 378,557 |
| `validation` | 22,087 | 22,087 |
| `test` | 17,420 | 17,420 |

## Best Epoch

- Epoch: `2`
- Selection metric: `balanced`
- Selection objective: `0.7619`
- Validation loss: `-1.9750`
- Validation RMSE all: `0.1149`
- Validation MAE all: `0.0617`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 378,557 | 0.0975 | 0.0519 | -2.1055 | 0.9337 | 0.3174 |
| `train` | `yN` | 378,557 | 0.0435 | 0.0067 | -2.7265 | 0.9710 | 0.1214 |
| `train` | `yF` | 378,557 | 0.0871 | 0.0297 | -1.9869 | 0.9307 | 0.2663 |
| `train` | `yT` | 378,557 | 0.2333 | 0.1569 | -0.9569 | 0.8936 | 0.7740 |
| `train` | `sigma_N` | 378,557 | 0.0412 | 0.0052 | -2.7727 | 0.9833 | 0.1319 |
| `train` | `sigma_F` | 378,557 | 0.0459 | 0.0127 | -2.6025 | 0.9547 | 0.1555 |
| `train` | `sigma_T` | 378,557 | 0.0720 | 0.0429 | -2.1347 | 0.8694 | 0.2332 |
| `train` | `delta_yN` | 378,557 | 0.0413 | 0.0157 | -2.7784 | 0.9717 | 0.1341 |
| `train` | `delta_yF` | 378,557 | 0.0829 | 0.0362 | -2.0207 | 0.9312 | 0.2724 |
| `train` | `delta_yT` | 378,557 | 0.2304 | 0.1615 | -0.9699 | 0.8980 | 0.7675 |
| `validation` | `all` | 22,087 | 0.1149 | 0.0617 | -1.6689 | 0.9007 | 0.3188 |
| `validation` | `yN` | 22,087 | 0.0719 | 0.0241 | -1.6933 | 0.8814 | 0.1231 |
| `validation` | `yF` | 22,087 | 0.0892 | 0.0347 | -1.9740 | 0.9161 | 0.2684 |
| `validation` | `yT` | 22,087 | 0.2447 | 0.1670 | -0.9077 | 0.8796 | 0.7739 |
| `validation` | `sigma_N` | 22,087 | 0.0853 | 0.0197 | -1.2305 | 0.9541 | 0.1334 |
| `validation` | `sigma_F` | 22,087 | 0.0489 | 0.0146 | -2.5569 | 0.9519 | 0.1566 |
| `validation` | `sigma_T` | 22,087 | 0.0974 | 0.0514 | -1.7351 | 0.8418 | 0.2346 |
| `validation` | `delta_yN` | 22,087 | 0.0686 | 0.0316 | -2.0119 | 0.8828 | 0.1358 |
| `validation` | `delta_yF` | 22,087 | 0.0860 | 0.0402 | -1.9931 | 0.9161 | 0.2745 |
| `validation` | `delta_yT` | 22,087 | 0.2426 | 0.1721 | -0.9174 | 0.8823 | 0.7693 |
| `test` | `all` | 17,420 | 0.1116 | 0.0600 | -1.4943 | 0.8956 | 0.3219 |
| `test` | `yN` | 17,420 | 0.0907 | 0.0364 | -0.7892 | 0.8272 | 0.1250 |
| `test` | `yF` | 17,420 | 0.0968 | 0.0414 | -1.8787 | 0.9075 | 0.2727 |
| `test` | `yT` | 17,420 | 0.2069 | 0.1386 | -1.0595 | 0.9201 | 0.7774 |
| `test` | `sigma_N` | 17,420 | 0.0962 | 0.0278 | -0.7646 | 0.9251 | 0.1361 |
| `test` | `sigma_F` | 17,420 | 0.0515 | 0.0175 | -2.4996 | 0.9416 | 0.1590 |
| `test` | `sigma_T` | 17,420 | 0.0765 | 0.0426 | -2.0773 | 0.8815 | 0.2378 |
| `test` | `delta_yN` | 17,420 | 0.0854 | 0.0435 | -1.4037 | 0.8261 | 0.1381 |
| `test` | `delta_yF` | 17,420 | 0.0923 | 0.0464 | -1.9174 | 0.9081 | 0.2774 |
| `test` | `delta_yT` | 17,420 | 0.2081 | 0.1459 | -1.0584 | 0.9234 | 0.7736 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.0000 | 0.0241 | 0.0719 | 1.0357 |
| `yF` | 0.2000 | 0.0347 | 0.0892 | 1.0327 |
| `yT` | 0.9000 | 0.1670 | 0.2447 | 1.0107 |
| `sigma_N` | 0.0000 | 0.0197 | 0.0853 | 1.0000 |
| `sigma_F` | 0.0000 | 0.0146 | 0.0489 | 1.0011 |
| `sigma_T` | 0.0000 | 0.0514 | 0.0974 | 1.0106 |
| `delta_yN` | 1.0000 | 0.0316 | 0.0686 | 1.0144 |
| `delta_yF` | 1.0000 | 0.0402 | 0.0860 | 1.0058 |
| `delta_yT` | 1.0000 | 0.1721 | 0.2426 | 1.0063 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1116 | 0.1502 | 0.2570 | 0.0600 | 0.0737 | 0.1857 |
| `train` | `all` | 0.0975 | 0.1355 | 0.2806 | 0.0519 | 0.0645 | 0.1950 |
| `validation` | `all` | 0.1149 | 0.1575 | 0.2701 | 0.0617 | 0.0777 | 0.2062 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse1_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse1_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse1_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse1_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse1_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse1_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse1_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse1_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse1_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse1_lr0p001_seed1729/pipe_grud_manifest.json`
