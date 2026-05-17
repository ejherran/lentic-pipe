# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-05-17T01:59:23.272744+00:00`
Started at UTC: `2026-05-17T01:58:24.007697+00:00`
Status: `completed`

## Scope

This step trains the minimal probabilistic temporal model over the frozen PIPE sequence dataset.
It predicts the next 9-dimensional fuzzy state vector and estimates diagonal Gaussian uncertainty.
Checkpoint selection evaluates the same blended output used by the final model.

## Configuration

- History length: `12`
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
| `train` | 378,557 | 378,557 |
| `validation` | 22,087 | 22,087 |
| `test` | 17,420 | 17,420 |

## Best Epoch

- Epoch: `16`
- Selection metric: `balanced`
- Selection objective: `0.7646`
- Validation loss: `-3.1123`
- Validation RMSE all: `0.1144`
- Validation MAE all: `0.0624`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 378,557 | 0.0973 | 0.0525 | -2.7704 | 0.9479 | 0.3014 |
| `train` | `yN` | 378,557 | 0.0392 | 0.0081 | -4.3918 | 0.9881 | 0.0671 |
| `train` | `yF` | 378,557 | 0.0864 | 0.0299 | -3.0015 | 0.9599 | 0.2201 |
| `train` | `yT` | 378,557 | 0.2386 | 0.1643 | -0.9399 | 0.8919 | 0.7769 |
| `train` | `sigma_N` | 378,557 | 0.0412 | 0.0052 | -2.8634 | 0.9964 | 0.2316 |
| `train` | `sigma_F` | 378,557 | 0.0459 | 0.0127 | -3.2650 | 0.9770 | 0.1329 |
| `train` | `sigma_T` | 378,557 | 0.0676 | 0.0442 | -2.2120 | 0.8733 | 0.2232 |
| `train` | `delta_yN` | 378,557 | 0.0383 | 0.0082 | -4.2981 | 0.9895 | 0.0736 |
| `train` | `delta_yF` | 378,557 | 0.0807 | 0.0351 | -3.0192 | 0.9608 | 0.2096 |
| `train` | `delta_yT` | 378,557 | 0.2380 | 0.1648 | -0.9425 | 0.8941 | 0.7776 |
| `validation` | `all` | 22,087 | 0.1144 | 0.0624 | -2.5616 | 0.9417 | 0.3751 |
| `validation` | `yN` | 22,087 | 0.0654 | 0.0246 | -3.7628 | 0.9457 | 0.1231 |
| `validation` | `yF` | 22,087 | 0.0885 | 0.0349 | -2.9455 | 0.9905 | 0.3726 |
| `validation` | `yT` | 22,087 | 0.2513 | 0.1740 | -0.8810 | 0.8787 | 0.7937 |
| `validation` | `sigma_N` | 22,087 | 0.0853 | 0.0197 | -2.5598 | 0.9781 | 0.3292 |
| `validation` | `sigma_F` | 22,087 | 0.0489 | 0.0146 | -3.3140 | 0.9919 | 0.2148 |
| `validation` | `sigma_T` | 22,087 | 0.0895 | 0.0529 | -1.9871 | 0.8636 | 0.2517 |
| `validation` | `delta_yN` | 22,087 | 0.0633 | 0.0246 | -3.7705 | 0.9553 | 0.1316 |
| `validation` | `delta_yF` | 22,087 | 0.0840 | 0.0393 | -2.9595 | 0.9920 | 0.3597 |
| `validation` | `delta_yT` | 22,087 | 0.2539 | 0.1770 | -0.8745 | 0.8800 | 0.7999 |
| `test` | `all` | 17,420 | 0.1109 | 0.0611 | -2.3705 | 0.9502 | 0.4327 |
| `test` | `yN` | 17,420 | 0.0819 | 0.0362 | -3.1736 | 0.9200 | 0.1662 |
| `test` | `yF` | 17,420 | 0.0958 | 0.0413 | -2.6468 | 0.9880 | 0.4922 |
| `test` | `yT` | 17,420 | 0.2137 | 0.1484 | -1.0260 | 0.9224 | 0.8042 |
| `test` | `sigma_N` | 17,420 | 0.0962 | 0.0278 | -2.3488 | 0.9727 | 0.4080 |
| `test` | `sigma_F` | 17,420 | 0.0515 | 0.0175 | -3.0502 | 0.9914 | 0.2803 |
| `test` | `sigma_T` | 17,420 | 0.0715 | 0.0440 | -2.1444 | 0.9093 | 0.2737 |
| `test` | `delta_yN` | 17,420 | 0.0793 | 0.0357 | -3.2617 | 0.9331 | 0.1767 |
| `test` | `delta_yF` | 17,420 | 0.0904 | 0.0452 | -2.6717 | 0.9902 | 0.4776 |
| `test` | `delta_yT` | 17,420 | 0.2173 | 0.1535 | -1.0114 | 0.9246 | 0.8157 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.6500 | 0.0246 | 0.0654 | 1.0185 |
| `yF` | 0.2000 | 0.0349 | 0.0885 | 1.0423 |
| `yT` | 0.8000 | 0.1740 | 0.2513 | 1.0261 |
| `sigma_N` | 0.0000 | 0.0197 | 0.0853 | 1.0000 |
| `sigma_F` | 0.0000 | 0.0146 | 0.0489 | 1.0010 |
| `sigma_T` | 1.0000 | 0.0529 | 0.0895 | 1.0145 |
| `delta_yN` | 1.0000 | 0.0246 | 0.0633 | 1.0058 |
| `delta_yF` | 1.0000 | 0.0393 | 0.0840 | 1.0039 |
| `delta_yT` | 0.9000 | 0.1770 | 0.2539 | 1.0082 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1109 | 0.1502 | 0.2620 | 0.0611 | 0.0737 | 0.1717 |
| `train` | `all` | 0.0973 | 0.1355 | 0.2821 | 0.0525 | 0.0645 | 0.1863 |
| `validation` | `all` | 0.1144 | 0.1575 | 0.2733 | 0.0624 | 0.0777 | 0.1976 |

## Outputs

- Model: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p5_lr0p001_seed1729/pipe_grud_model.pt`
- Checkpoint: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p5_lr0p001_seed1729/pipe_grud_checkpoint.pt`
- Metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p5_lr0p001_seed1729/pipe_grud_metrics.csv`
- Persistence metrics: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p5_lr0p001_seed1729/pipe_grud_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p5_lr0p001_seed1729/pipe_grud_persistence_comparison.csv`
- Output blend weights: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_weights.csv`
- Output blend search: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p5_lr0p001_seed1729/pipe_grud_output_blend_search.csv`
- Training curve: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p5_lr0p001_seed1729/pipe_grud_training_curve.csv`
- Prediction examples: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p5_lr0p001_seed1729/pipe_grud_prediction_examples.csv`
- Manifest: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd128_mse0p5_lr0p001_seed1729/pipe_grud_manifest.json`
