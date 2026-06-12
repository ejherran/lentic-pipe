# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-06-12T18:43:34.493427+00:00`
Started at UTC: `2026-06-12T18:43:28.186723+00:00`
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
- Auxiliary MSE weight: `1.0`
- Checkpoint selection metric: `balanced`
- Output blend selection metric: `balanced`
- Epochs requested: `2`
- Batch size: `2048`
- Learning rate: `0.001`
- Device: `auto`

## Windows

| split | available | sampled/used |
|---|---:|---:|
| `train` | 378,557 | 50,000 |
| `validation` | 22,087 | 20,000 |
| `test` | 17,420 | 17,420 |

## Best Epoch

- Epoch: `1`
- Selection metric: `balanced`
- Selection objective: `0.8219`
- Validation loss: `-0.9304`
- Validation RMSE all: `0.1665`
- Validation MAE all: `0.0983`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 50,000 | 0.1467 | 0.0853 | -0.7323 | 0.9715 | 1.4069 |
| `train` | `yN` | 50,000 | 0.0441 | 0.0067 | -0.9976 | 0.9998 | 1.2062 |
| `train` | `yF` | 50,000 | 0.0890 | 0.0284 | -0.6909 | 0.9998 | 1.6233 |
| `train` | `yT` | 50,000 | 0.3812 | 0.3358 | -0.4478 | 0.8419 | 1.1119 |
| `train` | `sigma_N` | 50,000 | 0.0427 | 0.0055 | -0.6407 | 1.0000 | 1.7291 |
| `train` | `sigma_F` | 50,000 | 0.0453 | 0.0126 | -0.5187 | 1.0000 | 1.9532 |
| `train` | `sigma_T` | 50,000 | 0.2056 | 0.1466 | -0.7964 | 0.9947 | 1.3122 |
| `train` | `delta_yN` | 50,000 | 0.0733 | 0.0117 | -0.9964 | 0.9968 | 1.1939 |
| `train` | `delta_yF` | 50,000 | 0.1455 | 0.0490 | -0.7915 | 0.9919 | 1.4126 |
| `train` | `delta_yT` | 50,000 | 0.2936 | 0.1711 | -0.7109 | 0.9182 | 1.1199 |
| `validation` | `all` | 20,000 | 0.1665 | 0.0983 | -0.7116 | 0.9733 | 1.4215 |
| `validation` | `yN` | 20,000 | 0.0720 | 0.0241 | -0.9752 | 0.9995 | 1.2211 |
| `validation` | `yF` | 20,000 | 0.0917 | 0.0341 | -0.6846 | 0.9999 | 1.6334 |
| `validation` | `yT` | 20,000 | 0.3673 | 0.3246 | -0.4904 | 0.8767 | 1.1278 |
| `validation` | `sigma_N` | 20,000 | 0.0854 | 0.0197 | -0.6223 | 1.0000 | 1.7456 |
| `validation` | `sigma_F` | 20,000 | 0.0490 | 0.0147 | -0.5118 | 1.0000 | 1.9663 |
| `validation` | `sigma_T` | 20,000 | 0.2470 | 0.1799 | -0.7345 | 0.9927 | 1.3277 |
| `validation` | `delta_yN` | 20,000 | 0.1197 | 0.0415 | -0.9539 | 0.9935 | 1.2095 |
| `validation` | `delta_yF` | 20,000 | 0.1504 | 0.0583 | -0.7808 | 0.9935 | 1.4274 |
| `validation` | `delta_yT` | 20,000 | 0.3163 | 0.1880 | -0.6507 | 0.9041 | 1.1345 |
| `test` | `all` | 17,420 | 0.1741 | 0.1044 | -0.7065 | 0.9770 | 1.4321 |
| `test` | `yN` | 17,420 | 0.0907 | 0.0364 | -0.9549 | 0.9987 | 1.2343 |
| `test` | `yF` | 17,420 | 0.0991 | 0.0407 | -0.6761 | 0.9997 | 1.6427 |
| `test` | `yT` | 17,420 | 0.3668 | 0.3240 | -0.4943 | 0.8909 | 1.1367 |
| `test` | `sigma_N` | 17,420 | 0.0962 | 0.0278 | -0.6131 | 1.0000 | 1.7562 |
| `test` | `sigma_F` | 17,420 | 0.0515 | 0.0175 | -0.5045 | 1.0000 | 1.9802 |
| `test` | `sigma_T` | 17,420 | 0.2658 | 0.1966 | -0.7022 | 0.9901 | 1.3358 |
| `test` | `delta_yN` | 17,420 | 0.1494 | 0.0614 | -0.9186 | 0.9898 | 1.2200 |
| `test` | `delta_yF` | 17,420 | 0.1631 | 0.0690 | -0.7647 | 0.9917 | 1.4358 |
| `test` | `delta_yT` | 17,420 | 0.2844 | 0.1660 | -0.7301 | 0.9323 | 1.1473 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.0000 | 0.0241 | 0.0720 | 1.0069 |
| `yF` | 0.0000 | 0.0341 | 0.0917 | 1.0001 |
| `yT` | 1.0000 | 0.3246 | 0.3673 | 1.0000 |
| `sigma_N` | 0.0000 | 0.0197 | 0.0854 | 1.0000 |
| `sigma_F` | 0.0000 | 0.0147 | 0.0490 | 1.0000 |
| `sigma_T` | 0.5000 | 0.1799 | 0.2470 | 1.0598 |
| `delta_yN` | 0.0000 | 0.0415 | 0.1197 | 1.0035 |
| `delta_yF` | 0.0000 | 0.0583 | 0.1504 | 1.0154 |
| `delta_yT` | 0.0000 | 0.1880 | 0.3163 | 1.0018 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1741 | 0.1963 | 0.1131 | 0.1044 | 0.1299 | 0.1961 |
| `train` | `all` | 0.1467 | 0.1767 | 0.1697 | 0.0853 | 0.1196 | 0.2868 |
| `validation` | `all` | 0.1665 | 0.1917 | 0.1314 | 0.0983 | 0.1268 | 0.2248 |

## Outputs

- Model: `models/pipe_grud/no_current_chla/pipe_grud_model_smoke.pt`
- Checkpoint: `models/pipe_grud/no_current_chla/pipe_grud_checkpoint_smoke.pt`
- Metrics: `reports/pipe_grud/no_current_chla/pipe_grud_metrics_smoke.csv`
- Persistence metrics: `reports/pipe_grud/no_current_chla/pipe_grud_persistence_metrics_smoke.csv`
- Persistence comparison: `reports/pipe_grud/no_current_chla/pipe_grud_persistence_comparison_smoke.csv`
- Output blend weights: `reports/pipe_grud/no_current_chla/pipe_grud_output_blend_weights_smoke.csv`
- Output blend search: `reports/pipe_grud/no_current_chla/pipe_grud_output_blend_search_smoke.csv`
- Training curve: `reports/pipe_grud/no_current_chla/pipe_grud_training_curve_smoke.csv`
- Prediction examples: `reports/pipe_grud/no_current_chla/pipe_grud_prediction_examples_smoke.csv`
- Manifest: `reports/pipe_grud/no_current_chla/pipe_grud_manifest_smoke.json`
