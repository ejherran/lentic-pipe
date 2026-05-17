# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:57:20.458444+00:00`
Started at UTC: `2026-05-17T01:56:27.139417+00:00`
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
- Epochs requested: `20`
- Batch size: `2048`
- Learning rate: `0.001`
- Device: `auto`

## Windows

| split | available | sampled/used |
|---|---:|---:|
| `train` | 378,557 | 378,557 |
| `validation` | 22,087 | 22,087 |
| `test` | 17,420 | 17,420 |

## Best Epoch

- Epoch: `20`
- Selection metric: `balanced`
- Selection objective: `0.7450`
- Validation loss: `-3.0956`
- Validation RMSE all: `0.1128`
- Validation MAE all: `0.0601`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 378,557 | 0.0957 | 0.0504 | -2.8573 | 0.9459 | 0.2872 |
| `train` | `yN` | 378,557 | 0.0407 | 0.0090 | -4.3778 | 0.9881 | 0.0633 |
| `train` | `yF` | 378,557 | 0.0880 | 0.0291 | -2.6326 | 0.9828 | 0.3488 |
| `train` | `yT` | 378,557 | 0.2286 | 0.1530 | -0.9759 | 0.8750 | 0.6897 |
| `train` | `sigma_N` | 378,557 | 0.0412 | 0.0052 | -4.1431 | 0.9924 | 0.0805 |
| `train` | `sigma_F` | 378,557 | 0.0459 | 0.0127 | -3.1485 | 0.9845 | 0.1720 |
| `train` | `sigma_T` | 378,557 | 0.0711 | 0.0434 | -2.1484 | 0.8544 | 0.2249 |
| `train` | `delta_yN` | 378,557 | 0.0383 | 0.0077 | -4.3846 | 0.9892 | 0.0665 |
| `train` | `delta_yF` | 378,557 | 0.0805 | 0.0363 | -2.9262 | 0.9721 | 0.2483 |
| `train` | `delta_yT` | 378,557 | 0.2275 | 0.1570 | -0.9784 | 0.8743 | 0.6903 |
| `validation` | `all` | 22,087 | 0.1128 | 0.0601 | -2.5674 | 0.9402 | 0.3727 |
| `validation` | `yN` | 22,087 | 0.0673 | 0.0252 | -3.7846 | 0.9540 | 0.1205 |
| `validation` | `yF` | 22,087 | 0.0902 | 0.0345 | -2.4410 | 0.9979 | 0.5710 |
| `validation` | `yT` | 22,087 | 0.2411 | 0.1636 | -0.9118 | 0.8686 | 0.7157 |
| `validation` | `sigma_N` | 22,087 | 0.0853 | 0.0197 | -3.4065 | 0.9747 | 0.1412 |
| `validation` | `sigma_F` | 22,087 | 0.0489 | 0.0146 | -3.0503 | 0.9943 | 0.2785 |
| `validation` | `sigma_T` | 22,087 | 0.0961 | 0.0519 | -1.9267 | 0.8473 | 0.2601 |
| `validation` | `delta_yN` | 22,087 | 0.0628 | 0.0239 | -3.8838 | 0.9590 | 0.1213 |
| `validation` | `delta_yF` | 22,087 | 0.0844 | 0.0411 | -2.7823 | 0.9963 | 0.4273 |
| `validation` | `delta_yT` | 22,087 | 0.2395 | 0.1666 | -0.9200 | 0.8701 | 0.7188 |
| `test` | `all` | 17,420 | 0.1091 | 0.0580 | -2.3577 | 0.9479 | 0.4335 |
| `test` | `yN` | 17,420 | 0.0847 | 0.0367 | -3.1963 | 0.9269 | 0.1591 |
| `test` | `yF` | 17,420 | 0.0979 | 0.0412 | -2.1458 | 0.9986 | 0.7416 |
| `test` | `yT` | 17,420 | 0.2037 | 0.1354 | -1.0842 | 0.9111 | 0.7248 |
| `test` | `sigma_N` | 17,420 | 0.0962 | 0.0278 | -3.0054 | 0.9591 | 0.1853 |
| `test` | `sigma_F` | 17,420 | 0.0515 | 0.0175 | -2.7796 | 0.9927 | 0.3589 |
| `test` | `sigma_T` | 17,420 | 0.0758 | 0.0432 | -2.0855 | 0.8975 | 0.2816 |
| `test` | `delta_yN` | 17,420 | 0.0786 | 0.0348 | -3.3583 | 0.9365 | 0.1602 |
| `test` | `delta_yF` | 17,420 | 0.0911 | 0.0474 | -2.4783 | 0.9967 | 0.5597 |
| `test` | `delta_yT` | 17,420 | 0.2027 | 0.1382 | -1.0862 | 0.9125 | 0.7304 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.3500 | 0.0252 | 0.0673 | 1.0467 |
| `yF` | 0.1000 | 0.0345 | 0.0902 | 1.0234 |
| `yT` | 0.8000 | 0.1636 | 0.2411 | 1.0096 |
| `sigma_N` | 0.0000 | 0.0197 | 0.0853 | 1.0003 |
| `sigma_F` | 0.0000 | 0.0146 | 0.0489 | 1.0035 |
| `sigma_T` | 0.2000 | 0.0519 | 0.0961 | 1.0199 |
| `delta_yN` | 1.0000 | 0.0239 | 0.0628 | 1.0052 |
| `delta_yF` | 1.0000 | 0.0411 | 0.0844 | 1.0073 |
| `delta_yT` | 1.0000 | 0.1666 | 0.2395 | 1.0034 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1091 | 0.1502 | 0.2735 | 0.0580 | 0.0737 | 0.2128 |
| `train` | `all` | 0.0957 | 0.1355 | 0.2937 | 0.0504 | 0.0645 | 0.2191 |
| `validation` | `all` | 0.1128 | 0.1575 | 0.2835 | 0.0601 | 0.0777 | 0.2266 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse1_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse1_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse1_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse1_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse1_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse1_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse1_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse1_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse1_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse1_lr0p001_seed1729/pipe_grud_manifest.json`
