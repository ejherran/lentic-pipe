# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:37:20.676925+00:00`
Started at UTC: `2026-05-17T01:34:54.582032+00:00`
Status: `completed`

## Scope

This step trains the minimal probabilistic temporal model over the frozen PIPE sequence dataset.
It predicts the next 9-dimensional fuzzy state vector and estimates diagonal Gaussian uncertainty.
Checkpoint selection evaluates the same blended output used by the final model.

## Configuration

- History length: `3`
- Hidden dimension: `128`
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
| `train` | 1,065,877 | 1,065,877 |
| `validation` | 116,097 | 116,097 |
| `test` | 86,069 | 86,069 |

## Best Epoch

- Epoch: `19`
- Selection metric: `balanced`
- Selection objective: `0.7704`
- Validation loss: `-3.1164`
- Validation RMSE all: `0.1188`
- Validation MAE all: `0.0633`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 1,065,877 | 0.1106 | 0.0572 | -2.6877 | 0.9353 | 0.2604 |
| `train` | `yN` | 1,065,877 | 0.0653 | 0.0182 | -3.8450 | 0.9775 | 0.1143 |
| `train` | `yF` | 1,065,877 | 0.1028 | 0.0443 | -2.5645 | 0.9298 | 0.1818 |
| `train` | `yT` | 1,065,877 | 0.2354 | 0.1520 | -1.1154 | 0.8907 | 0.6600 |
| `train` | `sigma_N` | 1,065,877 | 0.0616 | 0.0117 | -3.7641 | 0.9827 | 0.1126 |
| `train` | `sigma_F` | 1,065,877 | 0.0523 | 0.0179 | -3.0521 | 0.9532 | 0.1051 |
| `train` | `sigma_T` | 1,065,877 | 0.0789 | 0.0459 | -2.1681 | 0.8683 | 0.2032 |
| `train` | `delta_yN` | 1,065,877 | 0.0650 | 0.0200 | -3.8203 | 0.9784 | 0.1137 |
| `train` | `delta_yF` | 1,065,877 | 0.1035 | 0.0463 | -2.7285 | 0.9370 | 0.1936 |
| `train` | `delta_yT` | 1,065,877 | 0.2308 | 0.1586 | -1.1317 | 0.9002 | 0.6598 |
| `validation` | `all` | 116,097 | 0.1188 | 0.0633 | -2.6107 | 0.9321 | 0.2936 |
| `validation` | `yN` | 116,097 | 0.0790 | 0.0310 | -3.3674 | 0.9614 | 0.1792 |
| `validation` | `yF` | 116,097 | 0.1025 | 0.0455 | -3.2532 | 0.9445 | 0.2087 |
| `validation` | `yT` | 116,097 | 0.2351 | 0.1549 | -1.0208 | 0.8828 | 0.6666 |
| `validation` | `sigma_N` | 116,097 | 0.0874 | 0.0230 | -2.9799 | 0.9667 | 0.1698 |
| `validation` | `sigma_F` | 116,097 | 0.0567 | 0.0192 | -3.2945 | 0.9597 | 0.1198 |
| `validation` | `sigma_T` | 116,097 | 0.0959 | 0.0537 | -2.0014 | 0.8690 | 0.2347 |
| `validation` | `delta_yN` | 116,097 | 0.0781 | 0.0328 | -3.3453 | 0.9627 | 0.1776 |
| `validation` | `delta_yF` | 116,097 | 0.1042 | 0.0478 | -3.1906 | 0.9480 | 0.2180 |
| `validation` | `delta_yT` | 116,097 | 0.2307 | 0.1615 | -1.0436 | 0.8936 | 0.6682 |
| `test` | `all` | 86,069 | 0.1250 | 0.0676 | -2.4287 | 0.9289 | 0.3237 |
| `test` | `yN` | 86,069 | 0.0982 | 0.0424 | -2.9468 | 0.9438 | 0.2248 |
| `test` | `yF` | 86,069 | 0.1120 | 0.0543 | -3.0132 | 0.9363 | 0.2479 |
| `test` | `yT` | 86,069 | 0.2227 | 0.1475 | -1.0665 | 0.8963 | 0.6757 |
| `test` | `sigma_N` | 86,069 | 0.1098 | 0.0344 | -2.6453 | 0.9471 | 0.2110 |
| `test` | `sigma_F` | 86,069 | 0.0629 | 0.0228 | -3.1690 | 0.9549 | 0.1403 |
| `test` | `sigma_T` | 86,069 | 0.0888 | 0.0502 | -2.0563 | 0.8906 | 0.2527 |
| `test` | `delta_yN` | 86,069 | 0.0969 | 0.0444 | -2.9410 | 0.9461 | 0.2230 |
| `test` | `delta_yF` | 86,069 | 0.1139 | 0.0566 | -2.9436 | 0.9400 | 0.2589 |
| `test` | `delta_yT` | 86,069 | 0.2200 | 0.1554 | -1.0764 | 0.9049 | 0.6787 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.5000 | 0.0310 | 0.0790 | 1.0279 |
| `yF` | 0.8000 | 0.0455 | 0.1025 | 1.0133 |
| `yT` | 0.6500 | 0.1549 | 0.2351 | 1.0206 |
| `sigma_N` | 0.0000 | 0.0230 | 0.0874 | 1.0050 |
| `sigma_F` | 0.1000 | 0.0192 | 0.0567 | 1.0159 |
| `sigma_T` | 0.5000 | 0.0537 | 0.0959 | 1.0237 |
| `delta_yN` | 1.0000 | 0.0328 | 0.0781 | 1.0046 |
| `delta_yF` | 1.0000 | 0.0478 | 0.1042 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1615 | 0.2307 | 1.0062 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1250 | 0.1679 | 0.2554 | 0.0676 | 0.0827 | 0.1829 |
| `train` | `all` | 0.1106 | 0.1514 | 0.2695 | 0.0572 | 0.0706 | 0.1900 |
| `validation` | `all` | 0.1188 | 0.1613 | 0.2635 | 0.0633 | 0.0786 | 0.1957 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p5_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p5_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p5_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p5_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p5_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p5_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p5_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd128_mse0p5_lr0p001_seed1729/pipe_grud_manifest.json`
