# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:58:21.597024+00:00`
Started at UTC: `2026-05-17T01:57:22.786626+00:00`
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

- Epoch: `20`
- Selection metric: `balanced`
- Selection objective: `0.7508`
- Validation loss: `-3.0763`
- Validation RMSE all: `0.1128`
- Validation MAE all: `0.0610`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 378,557 | 0.0951 | 0.0505 | -2.8171 | 0.9502 | 0.2924 |
| `train` | `yN` | 378,557 | 0.0426 | 0.0076 | -4.4159 | 0.9877 | 0.0661 |
| `train` | `yF` | 378,557 | 0.0817 | 0.0296 | -2.9440 | 0.9596 | 0.2221 |
| `train` | `yT` | 378,557 | 0.2307 | 0.1567 | -0.9763 | 0.8918 | 0.7480 |
| `train` | `sigma_N` | 378,557 | 0.0412 | 0.0052 | -3.5645 | 0.9950 | 0.1331 |
| `train` | `sigma_F` | 378,557 | 0.0459 | 0.0127 | -3.1794 | 0.9813 | 0.1579 |
| `train` | `sigma_T` | 378,557 | 0.0674 | 0.0439 | -2.2157 | 0.8818 | 0.2289 |
| `train` | `delta_yN` | 378,557 | 0.0392 | 0.0079 | -4.1870 | 0.9899 | 0.0763 |
| `train` | `delta_yF` | 378,557 | 0.0807 | 0.0317 | -2.8776 | 0.9710 | 0.2623 |
| `train` | `delta_yT` | 378,557 | 0.2268 | 0.1592 | -0.9938 | 0.8934 | 0.7365 |
| `validation` | `all` | 22,087 | 0.1128 | 0.0610 | -2.5581 | 0.9443 | 0.3715 |
| `validation` | `yN` | 22,087 | 0.0704 | 0.0246 | -3.7202 | 0.9456 | 0.1260 |
| `validation` | `yF` | 22,087 | 0.0844 | 0.0345 | -2.8637 | 0.9912 | 0.3774 |
| `validation` | `yT` | 22,087 | 0.2440 | 0.1683 | -0.9129 | 0.8809 | 0.7698 |
| `validation` | `sigma_N` | 22,087 | 0.0853 | 0.0197 | -3.0586 | 0.9761 | 0.2183 |
| `validation` | `sigma_F` | 22,087 | 0.0489 | 0.0146 | -3.1211 | 0.9935 | 0.2535 |
| `validation` | `sigma_T` | 22,087 | 0.0891 | 0.0527 | -2.0096 | 0.8721 | 0.2579 |
| `validation` | `delta_yN` | 22,087 | 0.0641 | 0.0242 | -3.6840 | 0.9597 | 0.1342 |
| `validation` | `delta_yF` | 22,087 | 0.0870 | 0.0381 | -2.7265 | 0.9957 | 0.4471 |
| `validation` | `delta_yT` | 22,087 | 0.2419 | 0.1727 | -0.9264 | 0.8841 | 0.7591 |
| `test` | `all` | 17,420 | 0.1097 | 0.0595 | -2.3532 | 0.9510 | 0.4256 |
| `test` | `yN` | 17,420 | 0.0888 | 0.0366 | -3.0563 | 0.9158 | 0.1649 |
| `test` | `yF` | 17,420 | 0.0910 | 0.0410 | -2.5812 | 0.9890 | 0.4851 |
| `test` | `yT` | 17,420 | 0.2069 | 0.1414 | -1.0609 | 0.9234 | 0.7802 |
| `test` | `sigma_N` | 17,420 | 0.0962 | 0.0278 | -2.7663 | 0.9667 | 0.2780 |
| `test` | `sigma_F` | 17,420 | 0.0515 | 0.0175 | -2.8701 | 0.9922 | 0.3212 |
| `test` | `sigma_T` | 17,420 | 0.0713 | 0.0437 | -2.1465 | 0.9151 | 0.2783 |
| `test` | `delta_yN` | 17,420 | 0.0805 | 0.0356 | -3.1918 | 0.9362 | 0.1739 |
| `test` | `delta_yF` | 17,420 | 0.0934 | 0.0451 | -2.4424 | 0.9944 | 0.5760 |
| `test` | `delta_yT` | 17,420 | 0.2078 | 0.1472 | -1.0635 | 0.9262 | 0.7724 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.1000 | 0.0246 | 0.0704 | 1.0550 |
| `yF` | 0.6500 | 0.0345 | 0.0844 | 1.0137 |
| `yT` | 0.8000 | 0.1683 | 0.2440 | 1.0159 |
| `sigma_N` | 0.0000 | 0.0197 | 0.0853 | 1.0000 |
| `sigma_F` | 0.0000 | 0.0146 | 0.0489 | 1.0005 |
| `sigma_T` | 1.0000 | 0.0527 | 0.0891 | 1.0129 |
| `delta_yN` | 0.9000 | 0.0242 | 0.0641 | 1.0050 |
| `delta_yF` | 1.0000 | 0.0381 | 0.0870 | 1.0025 |
| `delta_yT` | 1.0000 | 0.1727 | 0.2419 | 1.0062 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1097 | 0.1502 | 0.2696 | 0.0595 | 0.0737 | 0.1922 |
| `train` | `all` | 0.0951 | 0.1355 | 0.2981 | 0.0505 | 0.0645 | 0.2172 |
| `validation` | `all` | 0.1128 | 0.1575 | 0.2836 | 0.0610 | 0.0777 | 0.2148 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p25_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p25_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p25_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p25_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p25_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p25_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p25_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p25_lr0p001_seed1729/pipe_grud_manifest.json`
