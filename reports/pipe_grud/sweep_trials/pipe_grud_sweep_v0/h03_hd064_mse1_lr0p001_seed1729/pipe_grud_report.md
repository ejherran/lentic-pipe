# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:25:34.673294+00:00`
Started at UTC: `2026-05-17T01:23:24.540265+00:00`
Status: `completed`

## Scope

This step trains the minimal probabilistic temporal model over the frozen PIPE sequence dataset.
It predicts the next 9-dimensional fuzzy state vector and estimates diagonal Gaussian uncertainty.
Checkpoint selection evaluates the same blended output used by the final model.

## Configuration

- History length: `3`
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
| `train` | 1,065,877 | 1,065,877 |
| `validation` | 116,097 | 116,097 |
| `test` | 86,069 | 86,069 |

## Best Epoch

- Epoch: `19`
- Selection metric: `balanced`
- Selection objective: `0.7778`
- Validation loss: `-3.0890`
- Validation RMSE all: `0.1199`
- Validation MAE all: `0.0639`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 1,065,877 | 0.1114 | 0.0577 | -2.7075 | 0.9455 | 0.3026 |
| `train` | `yN` | 1,065,877 | 0.0639 | 0.0173 | -3.8669 | 0.9814 | 0.1313 |
| `train` | `yF` | 1,065,877 | 0.1040 | 0.0444 | -2.7971 | 0.9505 | 0.2281 |
| `train` | `yT` | 1,065,877 | 0.2357 | 0.1536 | -1.0449 | 0.8952 | 0.7343 |
| `train` | `sigma_N` | 1,065,877 | 0.0616 | 0.0117 | -3.7589 | 0.9845 | 0.1378 |
| `train` | `sigma_F` | 1,065,877 | 0.0527 | 0.0178 | -3.0933 | 0.9697 | 0.1404 |
| `train` | `sigma_T` | 1,065,877 | 0.0828 | 0.0467 | -2.0919 | 0.8882 | 0.2522 |
| `train` | `delta_yN` | 1,065,877 | 0.0651 | 0.0187 | -3.8649 | 0.9817 | 0.1307 |
| `train` | `delta_yF` | 1,065,877 | 0.1050 | 0.0478 | -2.7911 | 0.9538 | 0.2336 |
| `train` | `delta_yT` | 1,065,877 | 0.2317 | 0.1613 | -1.0584 | 0.9048 | 0.7352 |
| `validation` | `all` | 116,097 | 0.1199 | 0.0639 | -2.5815 | 0.9453 | 0.3549 |
| `validation` | `yN` | 116,097 | 0.0776 | 0.0304 | -3.4417 | 0.9703 | 0.2071 |
| `validation` | `yF` | 116,097 | 0.1039 | 0.0459 | -3.0724 | 0.9681 | 0.3001 |
| `validation` | `yT` | 116,097 | 0.2356 | 0.1565 | -1.0086 | 0.8933 | 0.7521 |
| `validation` | `sigma_N` | 116,097 | 0.0874 | 0.0230 | -3.1152 | 0.9699 | 0.2126 |
| `validation` | `sigma_F` | 116,097 | 0.0570 | 0.0191 | -3.1567 | 0.9756 | 0.1747 |
| `validation` | `sigma_T` | 116,097 | 0.0997 | 0.0541 | -1.9705 | 0.8882 | 0.2897 |
| `validation` | `delta_yN` | 116,097 | 0.0787 | 0.0323 | -3.4386 | 0.9701 | 0.2053 |
| `validation` | `delta_yF` | 116,097 | 0.1064 | 0.0495 | -3.0102 | 0.9696 | 0.3012 |
| `validation` | `delta_yT` | 116,097 | 0.2326 | 0.1644 | -1.0195 | 0.9028 | 0.7517 |
| `test` | `all` | 86,069 | 0.1262 | 0.0684 | -2.3884 | 0.9438 | 0.3952 |
| `test` | `yN` | 86,069 | 0.0960 | 0.0420 | -3.0089 | 0.9553 | 0.2594 |
| `test` | `yF` | 86,069 | 0.1136 | 0.0544 | -2.8239 | 0.9654 | 0.3647 |
| `test` | `yT` | 86,069 | 0.2235 | 0.1494 | -1.0236 | 0.9031 | 0.7635 |
| `test` | `sigma_N` | 86,069 | 0.1098 | 0.0344 | -2.8466 | 0.9528 | 0.2637 |
| `test` | `sigma_F` | 86,069 | 0.0632 | 0.0227 | -3.0029 | 0.9730 | 0.2077 |
| `test` | `sigma_T` | 86,069 | 0.0931 | 0.0509 | -1.9755 | 0.9102 | 0.3138 |
| `test` | `delta_yN` | 86,069 | 0.0970 | 0.0442 | -3.0167 | 0.9564 | 0.2569 |
| `test` | `delta_yF` | 86,069 | 0.1169 | 0.0587 | -2.7667 | 0.9665 | 0.3642 |
| `test` | `delta_yT` | 86,069 | 0.2223 | 0.1589 | -1.0305 | 0.9119 | 0.7631 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.6500 | 0.0304 | 0.0776 | 1.0147 |
| `yF` | 0.6500 | 0.0459 | 0.1039 | 1.0172 |
| `yT` | 0.6500 | 0.1565 | 0.2356 | 1.0237 |
| `sigma_N` | 0.0000 | 0.0230 | 0.0874 | 1.0054 |
| `sigma_F` | 0.0000 | 0.0191 | 0.0570 | 1.0054 |
| `sigma_T` | 0.3500 | 0.0541 | 0.0997 | 1.0283 |
| `delta_yN` | 1.0000 | 0.0323 | 0.0787 | 1.0054 |
| `delta_yF` | 1.0000 | 0.0495 | 0.1064 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1644 | 0.2326 | 1.0060 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1262 | 0.1679 | 0.2485 | 0.0684 | 0.0827 | 0.1727 |
| `train` | `all` | 0.1114 | 0.1514 | 0.2644 | 0.0577 | 0.0706 | 0.1827 |
| `validation` | `all` | 0.1199 | 0.1613 | 0.2571 | 0.0639 | 0.0786 | 0.1873 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse1_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse1_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse1_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse1_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse1_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse1_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse1_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse1_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse1_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse1_lr0p001_seed1729/pipe_grud_manifest.json`
