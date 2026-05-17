# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:52:55.684714+00:00`
Started at UTC: `2026-05-17T01:52:06.565139+00:00`
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

- Epoch: `18`
- Selection metric: `balanced`
- Selection objective: `0.7784`
- Validation loss: `-3.2650`
- Validation RMSE all: `0.1179`
- Validation MAE all: `0.0628`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 378,557 | 0.0997 | 0.0526 | -3.0247 | 0.9474 | 0.2822 |
| `train` | `yN` | 378,557 | 0.0391 | 0.0074 | -4.4079 | 0.9860 | 0.0602 |
| `train` | `yF` | 378,557 | 0.0894 | 0.0285 | -3.4440 | 0.9575 | 0.1876 |
| `train` | `yT` | 378,557 | 0.2455 | 0.1603 | -0.9187 | 0.8873 | 0.7876 |
| `train` | `sigma_N` | 378,557 | 0.0412 | 0.0052 | -4.3392 | 0.9917 | 0.0714 |
| `train` | `sigma_F` | 378,557 | 0.0459 | 0.0127 | -3.5960 | 0.9813 | 0.1277 |
| `train` | `sigma_T` | 378,557 | 0.0720 | 0.0429 | -2.1203 | 0.8715 | 0.2505 |
| `train` | `delta_yN` | 378,557 | 0.0401 | 0.0097 | -4.3559 | 0.9870 | 0.0630 |
| `train` | `delta_yF` | 378,557 | 0.0844 | 0.0378 | -3.0994 | 0.9680 | 0.2091 |
| `train` | `delta_yT` | 378,557 | 0.2393 | 0.1688 | -0.9410 | 0.8960 | 0.7824 |
| `validation` | `all` | 22,087 | 0.1179 | 0.0628 | -2.7710 | 0.9410 | 0.3619 |
| `validation` | `yN` | 22,087 | 0.0649 | 0.0239 | -3.8490 | 0.9480 | 0.1126 |
| `validation` | `yF` | 22,087 | 0.0914 | 0.0340 | -3.4371 | 0.9886 | 0.3500 |
| `validation` | `yT` | 22,087 | 0.2592 | 0.1713 | -0.8556 | 0.8773 | 0.8203 |
| `validation` | `sigma_N` | 22,087 | 0.0853 | 0.0197 | -3.5597 | 0.9742 | 0.1299 |
| `validation` | `sigma_F` | 22,087 | 0.0489 | 0.0146 | -3.6123 | 0.9929 | 0.2273 |
| `validation` | `sigma_T` | 22,087 | 0.0974 | 0.0514 | -1.9129 | 0.8610 | 0.2996 |
| `validation` | `delta_yN` | 22,087 | 0.0668 | 0.0267 | -3.8108 | 0.9506 | 0.1201 |
| `validation` | `delta_yF` | 22,087 | 0.0927 | 0.0454 | -3.0200 | 0.9909 | 0.3844 |
| `validation` | `delta_yT` | 22,087 | 0.2543 | 0.1786 | -0.8816 | 0.8851 | 0.8130 |
| `test` | `all` | 17,420 | 0.1135 | 0.0610 | -2.5217 | 0.9482 | 0.4164 |
| `test` | `yN` | 17,420 | 0.0816 | 0.0354 | -3.2595 | 0.9189 | 0.1478 |
| `test` | `yF` | 17,420 | 0.0991 | 0.0407 | -3.0412 | 0.9894 | 0.4732 |
| `test` | `yT` | 17,420 | 0.2197 | 0.1444 | -1.0022 | 0.9187 | 0.8298 |
| `test` | `sigma_N` | 17,420 | 0.0962 | 0.0278 | -3.1186 | 0.9576 | 0.1716 |
| `test` | `sigma_F` | 17,420 | 0.0515 | 0.0175 | -3.2709 | 0.9921 | 0.3021 |
| `test` | `sigma_T` | 17,420 | 0.0765 | 0.0426 | -2.0169 | 0.9127 | 0.3317 |
| `test` | `delta_yN` | 17,420 | 0.0836 | 0.0391 | -3.2520 | 0.9229 | 0.1584 |
| `test` | `delta_yF` | 17,420 | 0.0981 | 0.0509 | -2.7089 | 0.9943 | 0.5158 |
| `test` | `delta_yT` | 17,420 | 0.2149 | 0.1503 | -1.0247 | 0.9272 | 0.8176 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.6500 | 0.0239 | 0.0649 | 1.0127 |
| `yF` | 0.0000 | 0.0340 | 0.0914 | 1.0296 |
| `yT` | 0.6500 | 0.1713 | 0.2592 | 1.0234 |
| `sigma_N` | 0.0000 | 0.0197 | 0.0853 | 1.0002 |
| `sigma_F` | 0.0000 | 0.0146 | 0.0489 | 1.0006 |
| `sigma_T` | 0.0000 | 0.0514 | 0.0974 | 1.0156 |
| `delta_yN` | 0.9000 | 0.0267 | 0.0668 | 1.0074 |
| `delta_yF` | 0.9000 | 0.0454 | 0.0927 | 1.0108 |
| `delta_yT` | 1.0000 | 0.1786 | 0.2543 | 1.0038 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1135 | 0.1502 | 0.2446 | 0.0610 | 0.0737 | 0.1727 |
| `train` | `all` | 0.0997 | 0.1355 | 0.2648 | 0.0526 | 0.0645 | 0.1849 |
| `validation` | `all` | 0.1179 | 0.1575 | 0.2515 | 0.0628 | 0.0777 | 0.1917 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p25_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p25_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p25_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p25_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p25_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p25_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p25_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd064_mse0p25_lr0p001_seed1729/pipe_grud_manifest.json`
