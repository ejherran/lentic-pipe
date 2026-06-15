# PIPE/GRU-D Training Report v0

Generated at UTC: `2026-06-15T16:43:20.726671+00:00`
Started at UTC: `2026-06-15T16:43:18.097164+00:00`
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
- Epochs requested: `2`
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

- Epoch: `2`
- Selection metric: `balanced`
- Selection objective: `0.9923`
- Validation loss: `-1.5559`
- Validation RMSE all: `0.1507`
- Validation MAE all: `0.0869`

## Metrics

| split | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---|---:|---:|---:|---:|---:|---:|
| `train` | `all` | 50,000 | 0.1229 | 0.0622 | -1.6629 | 0.9309 | 0.4863 |
| `train` | `yN` | 50,000 | 0.0467 | 0.0128 | -2.3225 | 0.9677 | 0.2764 |
| `train` | `yF` | 50,000 | 0.1226 | 0.0640 | -1.5915 | 0.8877 | 0.3745 |
| `train` | `yT` | 50,000 | 0.2005 | 0.1071 | -1.1060 | 0.8805 | 0.6749 |
| `train` | `sigma_N` | 50,000 | 0.0529 | 0.0109 | -2.0484 | 0.9859 | 0.3828 |
| `train` | `sigma_F` | 50,000 | 0.0374 | 0.0168 | -1.9667 | 0.9975 | 0.4428 |
| `train` | `sigma_T` | 50,000 | 0.0577 | 0.0274 | -2.1232 | 0.9669 | 0.3352 |
| `train` | `delta_yN` | 50,000 | 0.0784 | 0.0276 | -2.0474 | 0.9325 | 0.2514 |
| `train` | `delta_yF` | 50,000 | 0.1978 | 0.1151 | -1.0987 | 0.8736 | 0.5659 |
| `train` | `delta_yT` | 50,000 | 0.3120 | 0.1784 | -0.6619 | 0.8858 | 1.0732 |
| `validation` | `all` | 7,079 | 0.1507 | 0.0869 | -1.3571 | 0.8862 | 0.4864 |
| `validation` | `yN` | 7,079 | 0.0948 | 0.0531 | -1.8397 | 0.8892 | 0.2768 |
| `validation` | `yF` | 7,079 | 0.1260 | 0.0726 | -1.5595 | 0.8720 | 0.3739 |
| `validation` | `yT` | 7,079 | 0.2053 | 0.1189 | -1.0832 | 0.8832 | 0.6743 |
| `validation` | `sigma_N` | 7,079 | 0.1194 | 0.0524 | -1.6269 | 0.9496 | 0.3831 |
| `validation` | `sigma_F` | 7,079 | 0.0497 | 0.0222 | -1.9365 | 0.9890 | 0.4433 |
| `validation` | `sigma_T` | 7,079 | 0.0798 | 0.0420 | -1.9773 | 0.9070 | 0.3350 |
| `validation` | `delta_yN` | 7,079 | 0.1562 | 0.0920 | -0.4980 | 0.7452 | 0.2521 |
| `validation` | `delta_yF` | 7,079 | 0.2039 | 0.1268 | -1.0574 | 0.8572 | 0.5662 |
| `validation` | `delta_yT` | 7,079 | 0.3213 | 0.2019 | -0.6350 | 0.8832 | 1.0726 |
| `test` | `all` | 7,582 | 0.1453 | 0.0839 | -1.3727 | 0.8918 | 0.4867 |
| `test` | `yN` | 7,582 | 0.0955 | 0.0567 | -1.8316 | 0.8771 | 0.2774 |
| `test` | `yF` | 7,582 | 0.1224 | 0.0697 | -1.5943 | 0.8812 | 0.3737 |
| `test` | `yT` | 7,582 | 0.1920 | 0.1092 | -1.1449 | 0.8975 | 0.6758 |
| `test` | `sigma_N` | 7,582 | 0.1382 | 0.0634 | -1.4488 | 0.9161 | 0.3837 |
| `test` | `sigma_F` | 7,582 | 0.0395 | 0.0203 | -1.9613 | 0.9989 | 0.4433 |
| `test` | `sigma_T` | 7,582 | 0.0702 | 0.0364 | -2.0476 | 0.9482 | 0.3345 |
| `test` | `delta_yN` | 7,582 | 0.1549 | 0.0949 | -0.5166 | 0.7350 | 0.2518 |
| `test` | `delta_yF` | 7,582 | 0.1959 | 0.1208 | -1.1112 | 0.8698 | 0.5662 |
| `test` | `delta_yT` | 7,582 | 0.2993 | 0.1840 | -0.6984 | 0.9020 | 1.0736 |

## Output Blend Weights

`blend_weight = 0` means pure persistence; `1` means pure neural prediction.
Weights are selected on validation `balanced` per target.

| target | blend weight | validation MAE | validation RMSE | objective |
|---|---:|---:|---:|---:|
| `yN` | 0.0000 | 0.0531 | 0.0948 | 1.0004 |
| `yF` | 0.0000 | 0.0726 | 0.1260 | 1.0000 |
| `yT` | 0.3500 | 0.1189 | 0.2053 | 1.0216 |
| `sigma_N` | 0.0000 | 0.0524 | 0.1194 | 1.0017 |
| `sigma_F` | 0.0000 | 0.0222 | 0.0497 | 1.0000 |
| `sigma_T` | 0.0000 | 0.0420 | 0.0798 | 1.0000 |
| `delta_yN` | 1.0000 | 0.0920 | 0.1562 | 1.0000 |
| `delta_yF` | 1.0000 | 0.1268 | 0.2039 | 1.0031 |
| `delta_yT` | 1.0000 | 0.2019 | 0.3213 | 1.0000 |

## Persistence Comparison

Positive relative improvement means PIPE/GRU-D beats the one-step persistence baseline.

| split | target | PIPE RMSE | persistence RMSE | RMSE rel improvement | PIPE MAE | persistence MAE | MAE rel improvement |
|---|---|---:|---:|---:|---:|---:|---:|
| `test` | `all` | 0.1453 | 0.1475 | 0.0148 | 0.0839 | 0.0841 | 0.0018 |
| `train` | `all` | 0.1229 | 0.1248 | 0.0157 | 0.0622 | 0.0612 | -0.0164 |
| `validation` | `all` | 0.1507 | 0.1529 | 0.0140 | 0.0869 | 0.0870 | 0.0013 |

## Outputs

- Model: `models/pipe_grud/adaptive_wqp_focused/pipe_grud_model_smoke.pt`
- Checkpoint: `models/pipe_grud/adaptive_wqp_focused/pipe_grud_checkpoint_smoke.pt`
- Metrics: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_metrics_smoke.csv`
- Persistence metrics: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_persistence_metrics_smoke.csv`
- Persistence comparison: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_persistence_comparison_smoke.csv`
- Output blend weights: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_output_blend_weights_smoke.csv`
- Output blend search: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_output_blend_search_smoke.csv`
- Training curve: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_training_curve_smoke.csv`
- Prediction examples: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_prediction_examples_smoke.csv`
- Manifest: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_manifest_smoke.json`
