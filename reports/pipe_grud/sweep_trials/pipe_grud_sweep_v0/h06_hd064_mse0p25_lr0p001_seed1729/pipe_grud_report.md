# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:41:07.514858+00:00`
Started at UTC: `2026-05-17T01:39:48.388936+00:00`
Status: `completed`

## Scope

This step trains the minimal probabilistic temporal model over the frozen PIPE sequence dataset.
It predicts the next 9-dimensional fuzzy state vector and estimates diagonal Gaussian uncertainty.
Checkpoint selection evaluates the same blended output used by the final model.

## Configuration

- History length: `6`
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
| `train` | 602,390 | 602,390 |
| `validation` | 54,637 | 54,637 |
| `test` | 40,606 | 40,606 |

## Best Epoch

- Epoch: `18`
- Selection metric: `balanced`
- Selection objective: `0.7786`
- Validation loss: `-3.2719`
- Validation RMSE all: `0.1141`
- Validation MAE all: `0.0614`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 602,390 | 0.1038 | 0.0550 | -2.9420 | 0.9471 | 0.3027 |
| `train` | `yN` | 602,390 | 0.0471 | 0.0097 | -4.3394 | 0.9862 | 0.0768 |
| `train` | `yF` | 602,390 | 0.0895 | 0.0328 | -3.2091 | 0.9615 | 0.2362 |
| `train` | `yT` | 602,390 | 0.2458 | 0.1652 | -0.9108 | 0.8879 | 0.7943 |
| `train` | `sigma_N` | 602,390 | 0.0488 | 0.0072 | -4.2454 | 0.9903 | 0.0940 |
| `train` | `sigma_F` | 602,390 | 0.0483 | 0.0140 | -3.3275 | 0.9836 | 0.1686 |
| `train` | `sigma_T` | 602,390 | 0.0759 | 0.0441 | -2.1051 | 0.8663 | 0.2431 |
| `train` | `delta_yN` | 602,390 | 0.0498 | 0.0137 | -4.1977 | 0.9865 | 0.0787 |
| `train` | `delta_yF` | 602,390 | 0.0884 | 0.0359 | -3.2151 | 0.9649 | 0.2377 |
| `train` | `delta_yT` | 602,390 | 0.2410 | 0.1722 | -0.9283 | 0.8971 | 0.7947 |
| `validation` | `all` | 54,637 | 0.1141 | 0.0614 | -2.7549 | 0.9520 | 0.4062 |
| `validation` | `yN` | 54,637 | 0.0645 | 0.0242 | -3.8078 | 0.9703 | 0.1563 |
| `validation` | `yF` | 54,637 | 0.0872 | 0.0351 | -3.3195 | 0.9933 | 0.4524 |
| `validation` | `yT` | 54,637 | 0.2460 | 0.1657 | -0.8997 | 0.8945 | 0.8333 |
| `validation` | `sigma_N` | 54,637 | 0.0804 | 0.0187 | -3.6568 | 0.9779 | 0.1832 |
| `validation` | `sigma_F` | 54,637 | 0.0459 | 0.0142 | -3.3001 | 0.9950 | 0.2994 |
| `validation` | `sigma_T` | 54,637 | 0.0987 | 0.0512 | -1.9305 | 0.8690 | 0.2923 |
| `validation` | `delta_yN` | 54,637 | 0.0674 | 0.0286 | -3.6757 | 0.9712 | 0.1602 |
| `validation` | `delta_yF` | 54,637 | 0.0931 | 0.0417 | -3.2911 | 0.9944 | 0.4460 |
| `validation` | `delta_yT` | 54,637 | 0.2433 | 0.1735 | -0.9127 | 0.9028 | 0.8330 |
| `test` | `all` | 40,606 | 0.1158 | 0.0625 | -2.5915 | 0.9556 | 0.4508 |
| `test` | `yN` | 40,606 | 0.0806 | 0.0334 | -3.4679 | 0.9557 | 0.1899 |
| `test` | `yF` | 40,606 | 0.0964 | 0.0423 | -3.0373 | 0.9938 | 0.5556 |
| `test` | `yT` | 40,606 | 0.2269 | 0.1525 | -0.9661 | 0.9131 | 0.8375 |
| `test` | `sigma_N` | 40,606 | 0.0950 | 0.0265 | -3.3827 | 0.9677 | 0.2228 |
| `test` | `sigma_F` | 40,606 | 0.0547 | 0.0180 | -3.0905 | 0.9935 | 0.3620 |
| `test` | `sigma_T` | 40,606 | 0.0798 | 0.0439 | -2.0209 | 0.9040 | 0.3097 |
| `test` | `delta_yN` | 40,606 | 0.0849 | 0.0382 | -3.3665 | 0.9561 | 0.1956 |
| `test` | `delta_yF` | 40,606 | 0.0996 | 0.0477 | -3.0144 | 0.9953 | 0.5445 |
| `test` | `delta_yT` | 40,606 | 0.2243 | 0.1597 | -0.9768 | 0.9212 | 0.8397 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.6500 | 0.0242 | 0.0645 | 1.0106 |
| `yF` | 0.5000 | 0.0351 | 0.0872 | 1.0120 |
| `yT` | 0.6500 | 0.1657 | 0.2460 | 1.0317 |
| `sigma_N` | 0.0000 | 0.0187 | 0.0804 | 1.0008 |
| `sigma_F` | 0.0000 | 0.0142 | 0.0459 | 1.0009 |
| `sigma_T` | 0.0000 | 0.0512 | 0.0987 | 1.0140 |
| `delta_yN` | 0.8000 | 0.0286 | 0.0674 | 1.0051 |
| `delta_yF` | 1.0000 | 0.0417 | 0.0931 | 1.0043 |
| `delta_yT` | 1.0000 | 0.1735 | 0.2433 | 1.0048 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1158 | 0.1547 | 0.2517 | 0.0625 | 0.0753 | 0.1707 |
| `train` | `all` | 0.1038 | 0.1422 | 0.2698 | 0.0550 | 0.0673 | 0.1834 |
| `validation` | `all` | 0.1141 | 0.1537 | 0.2578 | 0.0614 | 0.0754 | 0.1850 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p25_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p25_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p25_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p25_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p25_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p25_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p25_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p25_lr0p001_seed1729/pipe_grud_manifest.json`
