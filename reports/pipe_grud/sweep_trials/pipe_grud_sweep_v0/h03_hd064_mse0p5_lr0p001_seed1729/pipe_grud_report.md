# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:23:22.286138+00:00`
Started at UTC: `2026-05-17T01:21:13.852612+00:00`
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
- Selection objective: `0.7794`
- Validation loss: `-3.0954`
- Validation RMSE all: `0.1202`
- Validation MAE all: `0.0640`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 1,065,877 | 0.1118 | 0.0578 | -2.6832 | 0.9420 | 0.2983 |
| `train` | `yN` | 1,065,877 | 0.0649 | 0.0179 | -3.8486 | 0.9800 | 0.1283 |
| `train` | `yF` | 1,065,877 | 0.1041 | 0.0441 | -2.7614 | 0.9503 | 0.2265 |
| `train` | `yT` | 1,065,877 | 0.2356 | 0.1543 | -1.0315 | 0.8936 | 0.7394 |
| `train` | `sigma_N` | 1,065,877 | 0.0616 | 0.0117 | -3.7593 | 0.9840 | 0.1303 |
| `train` | `sigma_F` | 1,065,877 | 0.0527 | 0.0178 | -3.0650 | 0.9650 | 0.1247 |
| `train` | `sigma_T` | 1,065,877 | 0.0843 | 0.0462 | -2.0463 | 0.8692 | 0.2419 |
| `train` | `delta_yN` | 1,065,877 | 0.0666 | 0.0201 | -3.8189 | 0.9807 | 0.1287 |
| `train` | `delta_yF` | 1,065,877 | 0.1051 | 0.0466 | -2.7717 | 0.9511 | 0.2251 |
| `train` | `delta_yT` | 1,065,877 | 0.2314 | 0.1620 | -1.0465 | 0.9039 | 0.7402 |
| `validation` | `all` | 116,097 | 0.1202 | 0.0640 | -2.5900 | 0.9421 | 0.3485 |
| `validation` | `yN` | 116,097 | 0.0785 | 0.0308 | -3.4181 | 0.9676 | 0.2010 |
| `validation` | `yF` | 116,097 | 0.1040 | 0.0456 | -3.1217 | 0.9685 | 0.2980 |
| `validation` | `yT` | 116,097 | 0.2355 | 0.1571 | -1.0017 | 0.8913 | 0.7544 |
| `validation` | `sigma_N` | 116,097 | 0.0874 | 0.0230 | -3.0642 | 0.9693 | 0.2011 |
| `validation` | `sigma_F` | 116,097 | 0.0570 | 0.0191 | -3.2613 | 0.9723 | 0.1583 |
| `validation` | `sigma_T` | 116,097 | 0.1011 | 0.0534 | -1.9309 | 0.8708 | 0.2775 |
| `validation` | `delta_yN` | 116,097 | 0.0797 | 0.0332 | -3.3865 | 0.9685 | 0.2009 |
| `validation` | `delta_yF` | 116,097 | 0.1066 | 0.0485 | -3.1115 | 0.9686 | 0.2911 |
| `validation` | `delta_yT` | 116,097 | 0.2321 | 0.1652 | -1.0142 | 0.9017 | 0.7539 |
| `test` | `all` | 86,069 | 0.1267 | 0.0685 | -2.3981 | 0.9407 | 0.3884 |
| `test` | `yN` | 86,069 | 0.0974 | 0.0422 | -2.9777 | 0.9517 | 0.2523 |
| `test` | `yF` | 86,069 | 0.1138 | 0.0542 | -2.8716 | 0.9659 | 0.3630 |
| `test` | `yT` | 86,069 | 0.2234 | 0.1501 | -1.0163 | 0.9015 | 0.7657 |
| `test` | `sigma_N` | 86,069 | 0.1098 | 0.0344 | -2.7864 | 0.9517 | 0.2512 |
| `test` | `sigma_F` | 86,069 | 0.0632 | 0.0227 | -3.1378 | 0.9703 | 0.1900 |
| `test` | `sigma_T` | 86,069 | 0.0944 | 0.0501 | -1.9482 | 0.8959 | 0.3014 |
| `test` | `delta_yN` | 86,069 | 0.0990 | 0.0451 | -2.9609 | 0.9537 | 0.2525 |
| `test` | `delta_yF` | 86,069 | 0.1173 | 0.0579 | -2.8604 | 0.9649 | 0.3530 |
| `test` | `delta_yT` | 86,069 | 0.2219 | 0.1596 | -1.0235 | 0.9109 | 0.7660 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.5000 | 0.0308 | 0.0785 | 1.0223 |
| `yF` | 0.6500 | 0.0456 | 0.1040 | 1.0146 |
| `yT` | 0.6500 | 0.1571 | 0.2355 | 1.0257 |
| `sigma_N` | 0.0000 | 0.0230 | 0.0874 | 1.0054 |
| `sigma_F` | 0.0000 | 0.0191 | 0.0570 | 1.0092 |
| `sigma_T` | 0.2000 | 0.0534 | 0.1011 | 1.0298 |
| `delta_yN` | 0.9000 | 0.0332 | 0.0797 | 1.0059 |
| `delta_yF` | 1.0000 | 0.0485 | 0.1066 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1652 | 0.2321 | 1.0065 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1267 | 0.1679 | 0.2453 | 0.0685 | 0.0827 | 0.1719 |
| `train` | `all` | 0.1118 | 0.1514 | 0.2616 | 0.0578 | 0.0706 | 0.1810 |
| `validation` | `all` | 0.1202 | 0.1613 | 0.2549 | 0.0640 | 0.0786 | 0.1864 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p5_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p5_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p5_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p5_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p5_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p5_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p5_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h03_hd064_mse0p5_lr0p001_seed1729/pipe_grud_manifest.json`
