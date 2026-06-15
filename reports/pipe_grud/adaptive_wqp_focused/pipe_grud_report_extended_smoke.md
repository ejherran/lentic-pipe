# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-06-15T16:46:13.589852+00:00`
Started at UTC: `2026-06-15T16:46:09.811310+00:00`
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
- Epochs requested: `8`
- Batch size: `2048`
- Learning rate: `0.001`
- Device: `auto`

## Windows

| split | available | sampled/used |
|---|---:|---:|
| `train` | 112,470 | 50,000 |
| `validation` | 7,079 | 7,079 |
| `test` | 7,582 | 7,582 |

## Best Epoch

- Epoch: `8`
- Selection metric: `balanced`
- Selection objective: `0.9157`
- Validation loss: `-1.4812`
- Validation RMSE all: `0.1371`
- Validation MAE all: `0.0813`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 50,000 | 0.1111 | 0.0594 | -1.9233 | 0.9101 | 0.3686 |
| `train` | `yN` | 50,000 | 0.0436 | 0.0182 | -2.6354 | 0.9377 | 0.1438 |
| `train` | `yF` | 50,000 | 0.1192 | 0.0648 | -1.6268 | 0.8969 | 0.3928 |
| `train` | `yT` | 50,000 | 0.1941 | 0.1098 | -1.1389 | 0.8704 | 0.6119 |
| `train` | `sigma_N` | 50,000 | 0.0529 | 0.0109 | -2.4444 | 0.9638 | 0.1791 |
| `train` | `sigma_F` | 50,000 | 0.0374 | 0.0169 | -2.7851 | 0.9034 | 0.1297 |
| `train` | `sigma_T` | 50,000 | 0.0577 | 0.0274 | -2.3536 | 0.8860 | 0.1892 |
| `train` | `delta_yN` | 50,000 | 0.0684 | 0.0250 | -2.1873 | 0.9364 | 0.2299 |
| `train` | `delta_yF` | 50,000 | 0.1652 | 0.0952 | -1.2996 | 0.9053 | 0.5611 |
| `train` | `delta_yT` | 50,000 | 0.2617 | 0.1668 | -0.8385 | 0.8908 | 0.8801 |
| `validation` | `all` | 7,079 | 0.1371 | 0.0813 | -1.2858 | 0.8438 | 0.3691 |
| `validation` | `yN` | 7,079 | 0.0886 | 0.0535 | -1.0871 | 0.7551 | 0.1442 |
| `validation` | `yF` | 7,079 | 0.1226 | 0.0733 | -1.5980 | 0.8856 | 0.3923 |
| `validation` | `yT` | 7,079 | 0.1987 | 0.1207 | -1.1130 | 0.8648 | 0.6122 |
| `validation` | `sigma_N` | 7,079 | 0.1194 | 0.0524 | -0.5400 | 0.8505 | 0.1799 |
| `validation` | `sigma_F` | 7,079 | 0.0496 | 0.0223 | -2.4492 | 0.8880 | 0.1303 |
| `validation` | `sigma_T` | 7,079 | 0.0798 | 0.0420 | -1.8956 | 0.8070 | 0.1896 |
| `validation` | `delta_yN` | 7,079 | 0.1356 | 0.0812 | -0.8071 | 0.7645 | 0.2315 |
| `validation` | `delta_yF` | 7,079 | 0.1705 | 0.1068 | -1.2689 | 0.8926 | 0.5615 |
| `validation` | `delta_yT` | 7,079 | 0.2689 | 0.1797 | -0.8129 | 0.8860 | 0.8800 |
| `test` | `all` | 7,582 | 0.1322 | 0.0785 | -1.2724 | 0.8487 | 0.3693 |
| `test` | `yN` | 7,582 | 0.0888 | 0.0561 | -1.0810 | 0.7360 | 0.1445 |
| `test` | `yF` | 7,582 | 0.1191 | 0.0706 | -1.6282 | 0.8913 | 0.3920 |
| `test` | `yT` | 7,582 | 0.1865 | 0.1106 | -1.1791 | 0.8841 | 0.6129 |
| `test` | `sigma_N` | 7,582 | 0.1382 | 0.0634 | 0.2827 | 0.8325 | 0.1802 |
| `test` | `sigma_F` | 7,582 | 0.0394 | 0.0203 | -2.7335 | 0.8818 | 0.1303 |
| `test` | `sigma_T` | 7,582 | 0.0702 | 0.0364 | -2.1102 | 0.8537 | 0.1890 |
| `test` | `delta_yN` | 7,582 | 0.1348 | 0.0839 | -0.8085 | 0.7490 | 0.2313 |
| `test` | `delta_yF` | 7,582 | 0.1632 | 0.1010 | -1.3107 | 0.9050 | 0.5615 |
| `test` | `delta_yT` | 7,582 | 0.2493 | 0.1645 | -0.8828 | 0.9053 | 0.8817 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 1.0000 | 0.0535 | 0.0886 | 1.0062 |
| `yF` | 0.6500 | 0.0733 | 0.1226 | 1.0099 |
| `yT` | 0.3500 | 0.1207 | 0.1987 | 1.0422 |
| `sigma_N` | 0.0000 | 0.0524 | 0.1194 | 1.0015 |
| `sigma_F` | 0.1000 | 0.0223 | 0.0496 | 1.0053 |
| `sigma_T` | 0.0000 | 0.0420 | 0.0798 | 1.0035 |
| `delta_yN` | 1.0000 | 0.0812 | 0.1356 | 1.0000 |
| `delta_yF` | 1.0000 | 0.1068 | 0.1705 | 1.0000 |
| `delta_yT` | 1.0000 | 0.1797 | 0.2689 | 1.0000 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1322 | 0.1475 | 0.1040 | 0.0785 | 0.0841 | 0.0659 |
| `train` | `all` | 0.1111 | 0.1248 | 0.1099 | 0.0594 | 0.0612 | 0.0293 |
| `validation` | `all` | 0.1371 | 0.1529 | 0.1032 | 0.0813 | 0.0870 | 0.0654 |

## Outputs

- Model: `models/pipe_grud/adaptive_wqp_focused/pipe_grud_model_extended_smoke.pt`
- Checkpoint: `models/pipe_grud/adaptive_wqp_focused/pipe_grud_checkpoint_extended_smoke.pt`
- Metrics: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_metrics_extended_smoke.csv`
- Persistence metrics: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_persistence_metrics_extended_smoke.csv`
- Persistence comparison: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_persistence_comparison_extended_smoke.csv`
- Output blend weights: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_output_blend_weights_extended_smoke.csv`
- Output blend search: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_output_blend_search_extended_smoke.csv`
- Training curve: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_training_curve_extended_smoke.csv`
- Prediction examples: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_prediction_examples_extended_smoke.csv`
- Manifest: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_manifest_extended_smoke.json`
