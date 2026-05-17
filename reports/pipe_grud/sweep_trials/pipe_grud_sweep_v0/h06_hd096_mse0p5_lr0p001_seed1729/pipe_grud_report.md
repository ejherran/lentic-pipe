# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:46:33.103334+00:00`
Started at UTC: `2026-05-17T01:45:14.112380+00:00`
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

- Epoch: `16`
- Selection metric: `balanced`
- Selection objective: `0.7777`
- Validation loss: `-3.1697`
- Validation RMSE all: `0.1137`
- Validation MAE all: `0.0615`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 602,390 | 0.1039 | 0.0553 | -2.8606 | 0.9452 | 0.3114 |
| `train` | `yN` | 602,390 | 0.0479 | 0.0110 | -4.2838 | 0.9881 | 0.0879 |
| `train` | `yF` | 602,390 | 0.0915 | 0.0327 | -3.0464 | 0.9555 | 0.2632 |
| `train` | `yT` | 602,390 | 0.2451 | 0.1649 | -0.9081 | 0.8889 | 0.7991 |
| `train` | `sigma_N` | 602,390 | 0.0488 | 0.0072 | -4.2593 | 0.9909 | 0.0983 |
| `train` | `sigma_F` | 602,390 | 0.0483 | 0.0140 | -3.2111 | 0.9780 | 0.1642 |
| `train` | `sigma_T` | 602,390 | 0.0747 | 0.0446 | -2.1123 | 0.8644 | 0.2448 |
| `train` | `delta_yN` | 602,390 | 0.0492 | 0.0155 | -3.9466 | 0.9879 | 0.0867 |
| `train` | `delta_yF` | 602,390 | 0.0882 | 0.0343 | -3.0584 | 0.9546 | 0.2535 |
| `train` | `delta_yT` | 602,390 | 0.2415 | 0.1738 | -0.9199 | 0.8982 | 0.8049 |
| `validation` | `all` | 54,637 | 0.1137 | 0.0615 | -2.6780 | 0.9531 | 0.4280 |
| `validation` | `yN` | 54,637 | 0.0655 | 0.0251 | -3.7460 | 0.9744 | 0.1816 |
| `validation` | `yF` | 54,637 | 0.0894 | 0.0351 | -3.1414 | 0.9929 | 0.5006 |
| `validation` | `yT` | 54,637 | 0.2456 | 0.1659 | -0.8926 | 0.8971 | 0.8456 |
| `validation` | `sigma_N` | 54,637 | 0.0804 | 0.0187 | -3.5718 | 0.9780 | 0.1991 |
| `validation` | `sigma_F` | 54,637 | 0.0459 | 0.0142 | -3.3004 | 0.9941 | 0.3001 |
| `validation` | `sigma_T` | 54,637 | 0.0973 | 0.0519 | -1.9481 | 0.8667 | 0.3090 |
| `validation` | `delta_yN` | 54,637 | 0.0653 | 0.0291 | -3.4665 | 0.9751 | 0.1773 |
| `validation` | `delta_yF` | 54,637 | 0.0887 | 0.0377 | -3.1384 | 0.9933 | 0.4808 |
| `validation` | `delta_yT` | 54,637 | 0.2449 | 0.1758 | -0.8966 | 0.9068 | 0.8583 |
| `test` | `all` | 40,606 | 0.1157 | 0.0624 | -2.5064 | 0.9569 | 0.4755 |
| `test` | `yN` | 40,606 | 0.0818 | 0.0340 | -3.3578 | 0.9601 | 0.2159 |
| `test` | `yF` | 40,606 | 0.0993 | 0.0423 | -2.8759 | 0.9934 | 0.6121 |
| `test` | `yT` | 40,606 | 0.2260 | 0.1518 | -0.9565 | 0.9159 | 0.8545 |
| `test` | `sigma_N` | 40,606 | 0.0950 | 0.0265 | -3.3031 | 0.9681 | 0.2383 |
| `test` | `sigma_F` | 40,606 | 0.0547 | 0.0180 | -3.0863 | 0.9923 | 0.3611 |
| `test` | `sigma_T` | 40,606 | 0.0788 | 0.0446 | -2.0061 | 0.9017 | 0.3302 |
| `test` | `delta_yN` | 40,606 | 0.0822 | 0.0378 | -3.1370 | 0.9623 | 0.2112 |
| `test` | `delta_yF` | 40,606 | 0.0978 | 0.0449 | -2.8786 | 0.9941 | 0.5864 |
| `test` | `delta_yT` | 40,606 | 0.2254 | 0.1617 | -0.9560 | 0.9240 | 0.8698 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.5000 | 0.0251 | 0.0655 | 1.0244 |
| `yF` | 0.3500 | 0.0351 | 0.0894 | 1.0163 |
| `yT` | 0.6500 | 0.1659 | 0.2456 | 1.0305 |
| `sigma_N` | 0.0000 | 0.0187 | 0.0804 | 1.0000 |
| `sigma_F` | 0.0000 | 0.0142 | 0.0459 | 1.0014 |
| `sigma_T` | 0.2000 | 0.0519 | 0.0973 | 1.0220 |
| `delta_yN` | 0.9000 | 0.0291 | 0.0653 | 1.0067 |
| `delta_yF` | 1.0000 | 0.0377 | 0.0887 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1758 | 0.2449 | 1.0048 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1157 | 0.1547 | 0.2526 | 0.0624 | 0.0753 | 0.1716 |
| `train` | `all` | 0.1039 | 0.1422 | 0.2693 | 0.0553 | 0.0673 | 0.1778 |
| `validation` | `all` | 0.1137 | 0.1537 | 0.2604 | 0.0615 | 0.0754 | 0.1842 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p5_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p5_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p5_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p5_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p5_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p5_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p5_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h06_hd096_mse0p5_lr0p001_seed1729/pipe_grud_manifest.json`
