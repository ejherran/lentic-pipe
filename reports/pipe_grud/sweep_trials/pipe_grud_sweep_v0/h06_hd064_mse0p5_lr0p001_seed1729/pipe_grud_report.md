# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:42:29.321816+00:00`
Started at UTC: `2026-05-17T01:41:09.765398+00:00`
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
| `train` | 602,390 | 602,390 |
| `validation` | 54,637 | 54,637 |
| `test` | 40,606 | 40,606 |

## Best Epoch

- Epoch: `18`
- Selection metric: `balanced`
- Selection objective: `0.7796`
- Validation loss: `-3.2620`
- Validation RMSE all: `0.1142`
- Validation MAE all: `0.0615`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 602,390 | 0.1041 | 0.0552 | -2.9030 | 0.9463 | 0.3020 |
| `train` | `yN` | 602,390 | 0.0480 | 0.0111 | -4.3060 | 0.9869 | 0.0802 |
| `train` | `yF` | 602,390 | 0.0898 | 0.0329 | -3.1504 | 0.9605 | 0.2405 |
| `train` | `yT` | 602,390 | 0.2463 | 0.1649 | -0.9075 | 0.8890 | 0.8019 |
| `train` | `sigma_N` | 602,390 | 0.0488 | 0.0072 | -4.2544 | 0.9898 | 0.0867 |
| `train` | `sigma_F` | 602,390 | 0.0483 | 0.0140 | -3.3004 | 0.9795 | 0.1494 |
| `train` | `sigma_T` | 602,390 | 0.0759 | 0.0441 | -2.1039 | 0.8654 | 0.2431 |
| `train` | `delta_yN` | 602,390 | 0.0500 | 0.0151 | -4.0667 | 0.9875 | 0.0827 |
| `train` | `delta_yF` | 602,390 | 0.0884 | 0.0367 | -3.1134 | 0.9617 | 0.2348 |
| `train` | `delta_yT` | 602,390 | 0.2416 | 0.1709 | -0.9240 | 0.8968 | 0.7991 |
| `validation` | `all` | 54,637 | 0.1142 | 0.0615 | -2.7616 | 0.9524 | 0.4082 |
| `validation` | `yN` | 54,637 | 0.0653 | 0.0251 | -3.7665 | 0.9718 | 0.1660 |
| `validation` | `yF` | 54,637 | 0.0872 | 0.0351 | -3.3865 | 0.9938 | 0.4673 |
| `validation` | `yT` | 54,637 | 0.2465 | 0.1656 | -0.8953 | 0.8954 | 0.8411 |
| `validation` | `sigma_N` | 54,637 | 0.0804 | 0.0187 | -3.5922 | 0.9773 | 0.1701 |
| `validation` | `sigma_F` | 54,637 | 0.0459 | 0.0142 | -3.4859 | 0.9940 | 0.2772 |
| `validation` | `sigma_T` | 54,637 | 0.0987 | 0.0512 | -1.9309 | 0.8685 | 0.2946 |
| `validation` | `delta_yN` | 54,637 | 0.0675 | 0.0298 | -3.5543 | 0.9741 | 0.1710 |
| `validation` | `delta_yF` | 54,637 | 0.0923 | 0.0418 | -3.3350 | 0.9943 | 0.4487 |
| `validation` | `delta_yT` | 54,637 | 0.2440 | 0.1722 | -0.9079 | 0.9024 | 0.8375 |
| `test` | `all` | 40,606 | 0.1159 | 0.0624 | -2.5992 | 0.9560 | 0.4531 |
| `test` | `yN` | 40,606 | 0.0820 | 0.0341 | -3.4258 | 0.9576 | 0.2014 |
| `test` | `yF` | 40,606 | 0.0965 | 0.0424 | -3.0951 | 0.9943 | 0.5750 |
| `test` | `yT` | 40,606 | 0.2273 | 0.1523 | -0.9612 | 0.9141 | 0.8454 |
| `test` | `sigma_N` | 40,606 | 0.0950 | 0.0265 | -3.3304 | 0.9655 | 0.2060 |
| `test` | `sigma_F` | 40,606 | 0.0547 | 0.0180 | -3.2818 | 0.9922 | 0.3365 |
| `test` | `sigma_T` | 40,606 | 0.0798 | 0.0439 | -2.0168 | 0.9036 | 0.3126 |
| `test` | `delta_yN` | 40,606 | 0.0848 | 0.0390 | -3.2522 | 0.9604 | 0.2085 |
| `test` | `delta_yF` | 40,606 | 0.0988 | 0.0476 | -3.0559 | 0.9954 | 0.5484 |
| `test` | `delta_yT` | 40,606 | 0.2243 | 0.1580 | -0.9736 | 0.9213 | 0.8440 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.5000 | 0.0251 | 0.0653 | 1.0242 |
| `yF` | 0.5000 | 0.0351 | 0.0872 | 1.0130 |
| `yT` | 0.6500 | 0.1656 | 0.2465 | 1.0314 |
| `sigma_N` | 0.0000 | 0.0187 | 0.0804 | 1.0005 |
| `sigma_F` | 0.0000 | 0.0142 | 0.0459 | 1.0018 |
| `sigma_T` | 0.0000 | 0.0512 | 0.0987 | 1.0155 |
| `delta_yN` | 0.8000 | 0.0298 | 0.0675 | 1.0061 |
| `delta_yF` | 1.0000 | 0.0418 | 0.0923 | 1.0039 |
| `delta_yT` | 1.0000 | 0.1722 | 0.2440 | 1.0042 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1159 | 0.1547 | 0.2509 | 0.0624 | 0.0753 | 0.1712 |
| `train` | `all` | 0.1041 | 0.1422 | 0.2678 | 0.0552 | 0.0673 | 0.1795 |
| `validation` | `all` | 0.1142 | 0.1537 | 0.2568 | 0.0615 | 0.0754 | 0.1840 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p5_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p5_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p5_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p5_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p5_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p5_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p5_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd064_mse0p5_lr0p001_seed1729/pipe_grud_manifest.json`
