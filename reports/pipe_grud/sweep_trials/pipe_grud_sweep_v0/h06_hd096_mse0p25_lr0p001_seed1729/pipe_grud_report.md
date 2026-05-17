# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:45:11.837344+00:00`
Started at UTC: `2026-05-17T01:43:50.681804+00:00`
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
| `train` | 602,390 | 602,390 |
| `validation` | 54,637 | 54,637 |
| `test` | 40,606 | 40,606 |

## Best Epoch

- Epoch: `20`
- Selection metric: `balanced`
- Selection objective: `0.7746`
- Validation loss: `-3.2567`
- Validation RMSE all: `0.1135`
- Validation MAE all: `0.0611`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 602,390 | 0.1038 | 0.0549 | -2.9518 | 0.9480 | 0.3089 |
| `train` | `yN` | 602,390 | 0.0477 | 0.0111 | -4.2960 | 0.9875 | 0.0809 |
| `train` | `yF` | 602,390 | 0.0894 | 0.0323 | -3.2096 | 0.9642 | 0.2687 |
| `train` | `yT` | 602,390 | 0.2494 | 0.1633 | -0.9043 | 0.8860 | 0.7985 |
| `train` | `sigma_N` | 602,390 | 0.0488 | 0.0072 | -4.2675 | 0.9903 | 0.0899 |
| `train` | `sigma_F` | 602,390 | 0.0483 | 0.0140 | -3.3219 | 0.9801 | 0.1634 |
| `train` | `sigma_T` | 602,390 | 0.0736 | 0.0447 | -2.1454 | 0.8715 | 0.2394 |
| `train` | `delta_yN` | 602,390 | 0.0486 | 0.0118 | -4.2926 | 0.9872 | 0.0785 |
| `train` | `delta_yF` | 602,390 | 0.0884 | 0.0348 | -3.1934 | 0.9626 | 0.2568 |
| `train` | `delta_yT` | 602,390 | 0.2403 | 0.1746 | -0.9354 | 0.9025 | 0.8038 |
| `validation` | `all` | 54,637 | 0.1135 | 0.0611 | -2.7483 | 0.9548 | 0.4313 |
| `validation` | `yN` | 54,637 | 0.0652 | 0.0252 | -3.7446 | 0.9746 | 0.1744 |
| `validation` | `yF` | 54,637 | 0.0874 | 0.0347 | -3.2516 | 0.9949 | 0.5337 |
| `validation` | `yT` | 54,637 | 0.2495 | 0.1642 | -0.8934 | 0.8944 | 0.8397 |
| `validation` | `sigma_N` | 54,637 | 0.0804 | 0.0187 | -3.5695 | 0.9777 | 0.1888 |
| `validation` | `sigma_F` | 54,637 | 0.0459 | 0.0142 | -3.3783 | 0.9949 | 0.3162 |
| `validation` | `sigma_T` | 54,637 | 0.0960 | 0.0524 | -1.9835 | 0.8759 | 0.2995 |
| `validation` | `delta_yN` | 54,637 | 0.0650 | 0.0261 | -3.7504 | 0.9753 | 0.1681 |
| `validation` | `delta_yF` | 54,637 | 0.0891 | 0.0380 | -3.2477 | 0.9948 | 0.5089 |
| `validation` | `delta_yT` | 54,637 | 0.2428 | 0.1767 | -0.9156 | 0.9108 | 0.8528 |
| `test` | `all` | 40,606 | 0.1155 | 0.0620 | -2.5741 | 0.9584 | 0.4811 |
| `test` | `yN` | 40,606 | 0.0815 | 0.0340 | -3.3895 | 0.9611 | 0.2084 |
| `test` | `yF` | 40,606 | 0.0976 | 0.0423 | -2.9613 | 0.9957 | 0.6567 |
| `test` | `yT` | 40,606 | 0.2297 | 0.1499 | -0.9592 | 0.9124 | 0.8458 |
| `test` | `sigma_N` | 40,606 | 0.0950 | 0.0265 | -3.2937 | 0.9676 | 0.2273 |
| `test` | `sigma_F` | 40,606 | 0.0547 | 0.0180 | -3.1819 | 0.9934 | 0.3857 |
| `test` | `sigma_T` | 40,606 | 0.0777 | 0.0449 | -2.0428 | 0.9090 | 0.3187 |
| `test` | `delta_yN` | 40,606 | 0.0818 | 0.0350 | -3.3988 | 0.9625 | 0.2013 |
| `test` | `delta_yF` | 40,606 | 0.0980 | 0.0451 | -2.9648 | 0.9957 | 0.6251 |
| `test` | `delta_yT` | 40,606 | 0.2236 | 0.1624 | -0.9749 | 0.9282 | 0.8610 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.5000 | 0.0252 | 0.0652 | 1.0254 |
| `yF` | 0.5000 | 0.0347 | 0.0874 | 1.0096 |
| `yT` | 0.5000 | 0.1642 | 0.2495 | 1.0346 |
| `sigma_N` | 0.0000 | 0.0187 | 0.0804 | 1.0000 |
| `sigma_F` | 0.0000 | 0.0142 | 0.0459 | 1.0012 |
| `sigma_T` | 0.3500 | 0.0524 | 0.0960 | 1.0222 |
| `delta_yN` | 0.9000 | 0.0261 | 0.0650 | 1.0035 |
| `delta_yF` | 1.0000 | 0.0380 | 0.0891 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1767 | 0.2428 | 1.0061 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1155 | 0.1547 | 0.2536 | 0.0620 | 0.0753 | 0.1766 |
| `train` | `all` | 0.1038 | 0.1422 | 0.2698 | 0.0549 | 0.0673 | 0.1848 |
| `validation` | `all` | 0.1135 | 0.1537 | 0.2616 | 0.0611 | 0.0754 | 0.1892 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p25_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p25_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p25_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p25_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p25_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p25_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p25_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p25_lr0p001_seed1729/pipe_grud_manifest.json`
