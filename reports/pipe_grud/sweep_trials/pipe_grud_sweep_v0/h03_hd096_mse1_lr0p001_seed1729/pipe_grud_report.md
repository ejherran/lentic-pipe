# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:32:27.344256+00:00`
Started at UTC: `2026-05-17T01:30:13.201191+00:00`
Status: `completed`

## Scope

This step trains the minimal probabilistic temporal model over the frozen PIPE sequence dataset.
It predicts the next 9-dimensional fuzzy state vector and estimates diagonal Gaussian uncertainty.
Checkpoint selection evaluates the same blended output used by the final model.

## Configuration

- History length: `3`
- Hidden dimension: `96`
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

- Epoch: `20`
- Selection metric: `balanced`
- Selection objective: `0.7750`
- Validation loss: `-3.0379`
- Validation RMSE all: `0.1191`
- Validation MAE all: `0.0639`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 1,065,877 | 0.1108 | 0.0577 | -2.7193 | 0.9395 | 0.2812 |
| `train` | `yN` | 1,065,877 | 0.0650 | 0.0177 | -3.8533 | 0.9784 | 0.1210 |
| `train` | `yF` | 1,065,877 | 0.1029 | 0.0445 | -2.8277 | 0.9472 | 0.2219 |
| `train` | `yT` | 1,065,877 | 0.2356 | 0.1542 | -1.0624 | 0.8820 | 0.6791 |
| `train` | `sigma_N` | 1,065,877 | 0.0616 | 0.0117 | -3.7637 | 0.9828 | 0.1158 |
| `train` | `sigma_F` | 1,065,877 | 0.0527 | 0.0178 | -3.0855 | 0.9593 | 0.1213 |
| `train` | `sigma_T` | 1,065,877 | 0.0798 | 0.0467 | -2.1361 | 0.8776 | 0.2271 |
| `train` | `delta_yN` | 1,065,877 | 0.0645 | 0.0187 | -3.8561 | 0.9793 | 0.1215 |
| `train` | `delta_yF` | 1,065,877 | 0.1038 | 0.0462 | -2.8079 | 0.9550 | 0.2429 |
| `train` | `delta_yT` | 1,065,877 | 0.2312 | 0.1618 | -1.0805 | 0.8941 | 0.6800 |
| `validation` | `all` | 116,097 | 0.1191 | 0.0639 | -2.5509 | 0.9365 | 0.3201 |
| `validation` | `yN` | 116,097 | 0.0787 | 0.0307 | -3.3846 | 0.9632 | 0.1910 |
| `validation` | `yF` | 116,097 | 0.1026 | 0.0455 | -3.0333 | 0.9618 | 0.2625 |
| `validation` | `yT` | 116,097 | 0.2354 | 0.1574 | -0.9867 | 0.8742 | 0.6862 |
| `validation` | `sigma_N` | 116,097 | 0.0874 | 0.0230 | -3.0372 | 0.9671 | 0.1764 |
| `validation` | `sigma_F` | 116,097 | 0.0570 | 0.0191 | -3.2258 | 0.9669 | 0.1446 |
| `validation` | `sigma_T` | 116,097 | 0.0970 | 0.0543 | -1.9954 | 0.8777 | 0.2590 |
| `validation` | `delta_yN` | 116,097 | 0.0777 | 0.0316 | -3.3896 | 0.9655 | 0.1928 |
| `validation` | `delta_yF` | 116,097 | 0.1048 | 0.0479 | -2.9039 | 0.9665 | 0.2812 |
| `validation` | `delta_yT` | 116,097 | 0.2312 | 0.1652 | -1.0018 | 0.8859 | 0.6870 |
| `test` | `all` | 86,069 | 0.1253 | 0.0681 | -2.3414 | 0.9345 | 0.3564 |
| `test` | `yN` | 86,069 | 0.0978 | 0.0422 | -2.9055 | 0.9454 | 0.2384 |
| `test` | `yF` | 86,069 | 0.1124 | 0.0542 | -2.7978 | 0.9560 | 0.3116 |
| `test` | `yT` | 86,069 | 0.2231 | 0.1498 | -1.0166 | 0.8876 | 0.7065 |
| `test` | `sigma_N` | 86,069 | 0.1098 | 0.0344 | -2.6364 | 0.9477 | 0.2184 |
| `test` | `sigma_F` | 86,069 | 0.0632 | 0.0227 | -3.0677 | 0.9647 | 0.1694 |
| `test` | `sigma_T` | 86,069 | 0.0902 | 0.0509 | -2.0199 | 0.8996 | 0.2818 |
| `test` | `delta_yN` | 86,069 | 0.0960 | 0.0430 | -2.9267 | 0.9497 | 0.2407 |
| `test` | `delta_yF` | 86,069 | 0.1147 | 0.0569 | -2.6762 | 0.9609 | 0.3323 |
| `test` | `delta_yT` | 86,069 | 0.2205 | 0.1587 | -1.0260 | 0.8987 | 0.7091 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.5000 | 0.0307 | 0.0787 | 1.0218 |
| `yF` | 0.8000 | 0.0455 | 0.1026 | 1.0138 |
| `yT` | 0.6500 | 0.1574 | 0.2354 | 1.0276 |
| `sigma_N` | 0.0000 | 0.0230 | 0.0874 | 1.0053 |
| `sigma_F` | 0.0000 | 0.0191 | 0.0570 | 1.0131 |
| `sigma_T` | 0.5000 | 0.0543 | 0.0970 | 1.0252 |
| `delta_yN` | 1.0000 | 0.0316 | 0.0777 | 1.0046 |
| `delta_yF` | 1.0000 | 0.0479 | 0.1048 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1652 | 0.2312 | 1.0065 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1253 | 0.1679 | 0.2537 | 0.0681 | 0.0827 | 0.1766 |
| `train` | `all` | 0.1108 | 0.1514 | 0.2685 | 0.0577 | 0.0706 | 0.1830 |
| `validation` | `all` | 0.1191 | 0.1613 | 0.2618 | 0.0639 | 0.0786 | 0.1881 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse1_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse1_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse1_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse1_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse1_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse1_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse1_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse1_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse1_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse1_lr0p001_seed1729/pipe_grud_manifest.json`
