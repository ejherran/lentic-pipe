# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:27:54.663207+00:00`
Started at UTC: `2026-05-17T01:25:36.755441+00:00`
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
| `train` | 1,065,877 | 1,065,877 |
| `validation` | 116,097 | 116,097 |
| `test` | 86,069 | 86,069 |

## Best Epoch

- Epoch: `18`
- Selection metric: `balanced`
- Selection objective: `0.7762`
- Validation loss: `-3.0370`
- Validation RMSE all: `0.1195`
- Validation MAE all: `0.0638`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 1,065,877 | 0.1112 | 0.0578 | -2.7019 | 0.9484 | 0.3108 |
| `train` | `yN` | 1,065,877 | 0.0650 | 0.0179 | -3.8092 | 0.9797 | 0.1285 |
| `train` | `yF` | 1,065,877 | 0.1035 | 0.0444 | -2.8009 | 0.9576 | 0.2565 |
| `train` | `yT` | 1,065,877 | 0.2358 | 0.1543 | -1.0709 | 0.9070 | 0.7634 |
| `train` | `sigma_N` | 1,065,877 | 0.0616 | 0.0117 | -3.7296 | 0.9840 | 0.1305 |
| `train` | `sigma_F` | 1,065,877 | 0.0527 | 0.0178 | -3.0716 | 0.9662 | 0.1362 |
| `train` | `sigma_T` | 1,065,877 | 0.0801 | 0.0465 | -2.1404 | 0.8884 | 0.2424 |
| `train` | `delta_yN` | 1,065,877 | 0.0648 | 0.0186 | -3.8186 | 0.9809 | 0.1296 |
| `train` | `delta_yF` | 1,065,877 | 0.1050 | 0.0467 | -2.7926 | 0.9536 | 0.2425 |
| `train` | `delta_yT` | 1,065,877 | 0.2318 | 0.1622 | -1.0836 | 0.9183 | 0.7679 |
| `validation` | `all` | 116,097 | 0.1195 | 0.0638 | -2.5511 | 0.9464 | 0.3578 |
| `validation` | `yN` | 116,097 | 0.0787 | 0.0308 | -3.3465 | 0.9665 | 0.2050 |
| `validation` | `yF` | 116,097 | 0.1033 | 0.0456 | -2.9590 | 0.9722 | 0.3128 |
| `validation` | `yT` | 116,097 | 0.2357 | 0.1573 | -1.0010 | 0.9005 | 0.7736 |
| `validation` | `sigma_N` | 116,097 | 0.0874 | 0.0230 | -3.0837 | 0.9688 | 0.2026 |
| `validation` | `sigma_F` | 116,097 | 0.0570 | 0.0191 | -3.2208 | 0.9734 | 0.1674 |
| `validation` | `sigma_T` | 116,097 | 0.0970 | 0.0538 | -1.9971 | 0.8865 | 0.2767 |
| `validation` | `delta_yN` | 116,097 | 0.0781 | 0.0316 | -3.3582 | 0.9689 | 0.2077 |
| `validation` | `delta_yF` | 116,097 | 0.1065 | 0.0484 | -2.9819 | 0.9692 | 0.2956 |
| `validation` | `delta_yT` | 116,097 | 0.2318 | 0.1650 | -1.0115 | 0.9116 | 0.7788 |
| `test` | `all` | 86,069 | 0.1259 | 0.0682 | -2.3353 | 0.9455 | 0.4011 |
| `test` | `yN` | 86,069 | 0.0978 | 0.0423 | -2.8750 | 0.9501 | 0.2575 |
| `test` | `yF` | 86,069 | 0.1132 | 0.0542 | -2.7184 | 0.9689 | 0.3738 |
| `test` | `yT` | 86,069 | 0.2237 | 0.1501 | -1.0227 | 0.9131 | 0.8002 |
| `test` | `sigma_N` | 86,069 | 0.1098 | 0.0344 | -2.6684 | 0.9517 | 0.2523 |
| `test` | `sigma_F` | 86,069 | 0.0632 | 0.0227 | -3.0514 | 0.9724 | 0.1992 |
| `test` | `sigma_T` | 86,069 | 0.0903 | 0.0505 | -2.0140 | 0.9088 | 0.3044 |
| `test` | `delta_yN` | 86,069 | 0.0963 | 0.0431 | -2.9018 | 0.9556 | 0.2608 |
| `test` | `delta_yF` | 86,069 | 0.1168 | 0.0577 | -2.7378 | 0.9650 | 0.3543 |
| `test` | `delta_yT` | 86,069 | 0.2215 | 0.1590 | -1.0280 | 0.9238 | 0.8071 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.5000 | 0.0308 | 0.0787 | 1.0242 |
| `yF` | 0.8000 | 0.0456 | 0.1033 | 1.0131 |
| `yT` | 0.6500 | 0.1573 | 0.2357 | 1.0269 |
| `sigma_N` | 0.0000 | 0.0230 | 0.0874 | 1.0043 |
| `sigma_F` | 0.0000 | 0.0191 | 0.0570 | 1.0109 |
| `sigma_T` | 0.5000 | 0.0538 | 0.0970 | 1.0253 |
| `delta_yN` | 1.0000 | 0.0316 | 0.0781 | 1.0040 |
| `delta_yF` | 1.0000 | 0.0484 | 0.1065 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1650 | 0.2318 | 1.0065 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1259 | 0.1679 | 0.2504 | 0.0682 | 0.0827 | 0.1748 |
| `train` | `all` | 0.1112 | 0.1514 | 0.2660 | 0.0578 | 0.0706 | 0.1819 |
| `validation` | `all` | 0.1195 | 0.1613 | 0.2594 | 0.0638 | 0.0786 | 0.1882 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p25_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p25_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p25_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p25_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p25_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p25_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p25_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p25_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd096_mse0p25_lr0p001_seed1729/pipe_grud_manifest.json`
