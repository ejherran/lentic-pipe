# PIPE Neural ODE Continuous-Time Training Report v2

Generated at UTC: `2026-06-27T14:46:51.595453+00:00`
Started at UTC: `2026-06-27T14:46:49.073738+00:00`
Status: `completed`

## Scope

This step trains a structurally separate continuous-time Neural ODE v2.
It encodes PIPE history once, then trains direct h-month targets by integrating the latent ODE for the requested `dt`.
Seasonal forcing is evaluated as a continuous function of integration time rather than fixed to one monthly step.
Synthetic smoke mode: `True`.

## Configuration

- History length: `6`
- Forecast horizons: `[1, 2, 3]`
- Context columns: `none`
- History hidden dimension: `32`
- History layers: `1`
- Latent dimension: `24`
- Dynamics hidden dimension: `32`
- Dynamics depth: `2`
- Dropout: `0.0`
- Derivative scale: `0.5`
- State delta scale per month: `0.35`
- ODE method: `rk4`
- ODE step size: `0.5`
- Auxiliary MSE weight: `0.5`
- Auxiliary IRC loss weight: `0.0`
- Checkpoint selection metric: `balanced`
- Output blend selection metric: `balanced`
- Epochs requested: `5`
- Batch size: `32`
- Learning rate: `0.001`
- Device: `auto`

## Examples

| split | available | sampled/used |
|---|---:|---:|
| `train` | 144 | 144 |
| `validation` | 144 | 144 |
| `test` | 144 | 144 |

## Best Epoch

- Epoch: `5`
- Selection objective: `0.6350`
- Validation loss: `-0.4973`
- Validation RMSE all horizons: `0.0137`
- Validation MAE all horizons: `0.0106`

## Metrics

`horizon_months = 0` is the aggregate over all requested direct horizons.

| split | horizon | target | rows | RMSE | MAE | NLL | 90% coverage | 90% mean width |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `test` | 0 | `all` | 144 | 0.0147 | 0.0114 | -0.3613 | 1.0000 | 2.3391 |
| `test` | 0 | `delta_yF` | 144 | 0.0198 | 0.0152 | -0.3862 | 1.0000 | 2.2449 |
| `test` | 0 | `delta_yN` | 144 | 0.0203 | 0.0152 | -0.3306 | 1.0000 | 2.3672 |
| `test` | 0 | `delta_yT` | 144 | 0.0277 | 0.0206 | -0.7124 | 1.0000 | 1.6190 |
| `test` | 0 | `sigma_F` | 144 | 0.0022 | 0.0014 | -0.4050 | 1.0000 | 2.1998 |
| `test` | 0 | `sigma_N` | 144 | 0.0028 | 0.0024 | -0.4057 | 1.0000 | 2.2002 |
| `test` | 0 | `sigma_T` | 144 | 0.0030 | 0.0023 | 0.0715 | 1.0000 | 3.5341 |
| `test` | 0 | `yF` | 144 | 0.0161 | 0.0133 | -0.3637 | 1.0000 | 2.2880 |
| `test` | 0 | `yN` | 144 | 0.0160 | 0.0141 | -0.3675 | 1.0000 | 2.2845 |
| `test` | 0 | `yT` | 144 | 0.0243 | 0.0185 | -0.3519 | 1.0000 | 2.3146 |
| `test` | 1 | `all` | 56 | 0.0105 | 0.0084 | -0.3064 | 1.0000 | 2.4552 |
| `test` | 1 | `delta_yF` | 56 | 0.0118 | 0.0091 | -0.3251 | 1.0000 | 2.3796 |
| `test` | 1 | `delta_yN` | 56 | 0.0134 | 0.0111 | -0.2697 | 1.0000 | 2.5124 |
| `test` | 1 | `delta_yT` | 56 | 0.0228 | 0.0157 | -0.6159 | 1.0000 | 1.7765 |
| `test` | 1 | `sigma_F` | 56 | 0.0011 | 0.0008 | -0.3334 | 1.0000 | 2.3587 |
| `test` | 1 | `sigma_N` | 56 | 0.0014 | 0.0013 | -0.3272 | 1.0000 | 2.3730 |
| `test` | 1 | `sigma_T` | 56 | 0.0014 | 0.0012 | 0.0610 | 1.0000 | 3.4969 |
| `test` | 1 | `yF` | 56 | 0.0128 | 0.0110 | -0.3230 | 1.0000 | 2.3817 |
| `test` | 1 | `yN` | 56 | 0.0159 | 0.0147 | -0.3115 | 1.0000 | 2.4122 |
| `test` | 1 | `yT` | 56 | 0.0140 | 0.0109 | -0.3128 | 1.0000 | 2.4062 |
| `test` | 2 | `all` | 48 | 0.0141 | 0.0113 | -0.3671 | 1.0000 | 2.3239 |
| `test` | 2 | `delta_yF` | 48 | 0.0193 | 0.0155 | -0.3876 | 1.0000 | 2.2393 |
| `test` | 2 | `delta_yN` | 48 | 0.0143 | 0.0116 | -0.3368 | 1.0000 | 2.3495 |
| `test` | 2 | `delta_yT` | 48 | 0.0287 | 0.0215 | -0.7235 | 1.0000 | 1.5948 |
| `test` | 2 | `sigma_F` | 48 | 0.0022 | 0.0015 | -0.4155 | 1.0000 | 2.1723 |
| `test` | 2 | `sigma_N` | 48 | 0.0027 | 0.0025 | -0.4134 | 1.0000 | 2.1775 |
| `test` | 2 | `sigma_T` | 48 | 0.0029 | 0.0024 | 0.0721 | 1.0000 | 3.5362 |
| `test` | 2 | `yF` | 48 | 0.0154 | 0.0121 | -0.3698 | 1.0000 | 2.2725 |
| `test` | 2 | `yN` | 48 | 0.0171 | 0.0151 | -0.3739 | 1.0000 | 2.2677 |
| `test` | 2 | `yT` | 48 | 0.0242 | 0.0198 | -0.3554 | 1.0000 | 2.3051 |
| `test` | 3 | `all` | 40 | 0.0191 | 0.0158 | -0.4311 | 1.0000 | 2.1950 |
| `test` | 3 | `delta_yF` | 40 | 0.0277 | 0.0235 | -0.4700 | 1.0000 | 2.0632 |
| `test` | 3 | `delta_yN` | 40 | 0.0313 | 0.0252 | -0.4084 | 1.0000 | 2.1851 |
| `test` | 3 | `delta_yT` | 40 | 0.0324 | 0.0262 | -0.8342 | 1.0000 | 1.4275 |
| `test` | 3 | `sigma_F` | 40 | 0.0032 | 0.0023 | -0.4926 | 1.0000 | 2.0105 |
| `test` | 3 | `sigma_N` | 40 | 0.0041 | 0.0038 | -0.5062 | 1.0000 | 1.9856 |
| `test` | 3 | `sigma_T` | 40 | 0.0043 | 0.0036 | 0.0855 | 1.0000 | 3.5838 |
| `test` | 3 | `yF` | 40 | 0.0204 | 0.0179 | -0.4134 | 1.0000 | 2.1754 |
| `test` | 3 | `yN` | 40 | 0.0148 | 0.0123 | -0.4383 | 1.0000 | 2.1259 |
| `test` | 3 | `yT` | 40 | 0.0338 | 0.0275 | -0.4024 | 1.0000 | 2.1977 |
| `train` | 0 | `all` | 144 | 0.0131 | 0.0100 | -0.3549 | 1.0000 | 2.3525 |
| `train` | 0 | `delta_yF` | 144 | 0.0152 | 0.0121 | -0.3760 | 1.0000 | 2.2683 |
| `train` | 0 | `delta_yN` | 144 | 0.0203 | 0.0162 | -0.3238 | 1.0000 | 2.3832 |
| `train` | 0 | `delta_yT` | 144 | 0.0226 | 0.0158 | -0.6991 | 1.0000 | 1.6417 |
| `train` | 0 | `sigma_F` | 144 | 0.0032 | 0.0027 | -0.3989 | 1.0000 | 2.2131 |
| `train` | 0 | `sigma_N` | 144 | 0.0027 | 0.0020 | -0.3974 | 1.0000 | 2.2186 |
| `train` | 0 | `sigma_T` | 144 | 0.0022 | 0.0015 | 0.0673 | 1.0000 | 3.5195 |
| `train` | 0 | `yF` | 144 | 0.0150 | 0.0113 | -0.3556 | 1.0000 | 2.3067 |
| `train` | 0 | `yN` | 144 | 0.0163 | 0.0139 | -0.3618 | 1.0000 | 2.2976 |
| `train` | 0 | `yT` | 144 | 0.0204 | 0.0141 | -0.3483 | 1.0000 | 2.3234 |
| `train` | 1 | `all` | 56 | 0.0099 | 0.0079 | -0.3003 | 1.0000 | 2.4687 |
| `train` | 1 | `delta_yF` | 56 | 0.0108 | 0.0091 | -0.3157 | 1.0000 | 2.4021 |
| `train` | 1 | `delta_yN` | 56 | 0.0178 | 0.0153 | -0.2635 | 1.0000 | 2.5280 |
| `train` | 1 | `delta_yT` | 56 | 0.0218 | 0.0151 | -0.6031 | 1.0000 | 1.7997 |
| `train` | 1 | `sigma_F` | 56 | 0.0015 | 0.0014 | -0.3276 | 1.0000 | 2.3725 |
| `train` | 1 | `sigma_N` | 56 | 0.0013 | 0.0011 | -0.3196 | 1.0000 | 2.3912 |
| `train` | 1 | `sigma_T` | 56 | 0.0011 | 0.0008 | 0.0572 | 1.0000 | 3.4840 |
| `train` | 1 | `yF` | 56 | 0.0081 | 0.0064 | -0.3152 | 1.0000 | 2.4005 |
| `train` | 1 | `yN` | 56 | 0.0136 | 0.0125 | -0.3060 | 1.0000 | 2.4256 |
| `train` | 1 | `yT` | 56 | 0.0128 | 0.0091 | -0.3092 | 1.0000 | 2.4149 |
| `train` | 2 | `all` | 48 | 0.0125 | 0.0098 | -0.3606 | 1.0000 | 2.3372 |
| `train` | 2 | `delta_yF` | 48 | 0.0155 | 0.0127 | -0.3774 | 1.0000 | 2.2627 |
| `train` | 2 | `delta_yN` | 48 | 0.0192 | 0.0161 | -0.3298 | 1.0000 | 2.3656 |
| `train` | 2 | `delta_yT` | 48 | 0.0248 | 0.0174 | -0.7099 | 1.0000 | 1.6175 |
| `train` | 2 | `sigma_F` | 48 | 0.0031 | 0.0028 | -0.4094 | 1.0000 | 2.1856 |
| `train` | 2 | `sigma_N` | 48 | 0.0026 | 0.0022 | -0.4051 | 1.0000 | 2.1959 |
| `train` | 2 | `sigma_T` | 48 | 0.0021 | 0.0016 | 0.0679 | 1.0000 | 3.5213 |
| `train` | 2 | `yF` | 48 | 0.0100 | 0.0083 | -0.3617 | 1.0000 | 2.2912 |
| `train` | 2 | `yN` | 48 | 0.0142 | 0.0115 | -0.3684 | 1.0000 | 2.2806 |
| `train` | 2 | `yT` | 48 | 0.0209 | 0.0152 | -0.3517 | 1.0000 | 2.3140 |
| `train` | 3 | `all` | 40 | 0.0166 | 0.0132 | -0.4243 | 1.0000 | 2.2080 |
| `train` | 3 | `delta_yF` | 40 | 0.0193 | 0.0157 | -0.4589 | 1.0000 | 2.0876 |
| `train` | 3 | `delta_yN` | 40 | 0.0245 | 0.0178 | -0.4013 | 1.0000 | 2.2017 |
| `train` | 3 | `delta_yT` | 40 | 0.0209 | 0.0149 | -0.8206 | 1.0000 | 1.4496 |
| `train` | 3 | `sigma_F` | 40 | 0.0046 | 0.0042 | -0.4863 | 1.0000 | 2.0232 |
| `train` | 3 | `sigma_N` | 40 | 0.0039 | 0.0032 | -0.4969 | 1.0000 | 2.0043 |
| `train` | 3 | `sigma_T` | 40 | 0.0032 | 0.0025 | 0.0807 | 1.0000 | 3.5669 |
| `train` | 3 | `yF` | 40 | 0.0244 | 0.0219 | -0.4047 | 1.0000 | 2.1938 |
| `train` | 3 | `yN` | 40 | 0.0213 | 0.0186 | -0.4321 | 1.0000 | 2.1386 |
| `train` | 3 | `yT` | 40 | 0.0273 | 0.0197 | -0.3988 | 1.0000 | 2.2066 |
| `validation` | 0 | `all` | 144 | 0.0137 | 0.0106 | -0.3600 | 1.0000 | 2.3419 |
| `validation` | 0 | `delta_yF` | 144 | 0.0174 | 0.0132 | -0.3859 | 1.0000 | 2.2454 |
| `validation` | 0 | `delta_yN` | 144 | 0.0217 | 0.0162 | -0.3286 | 1.0000 | 2.3715 |
| `validation` | 0 | `delta_yT` | 144 | 0.0232 | 0.0166 | -0.7097 | 1.0000 | 1.6239 |
| `validation` | 0 | `sigma_F` | 144 | 0.0028 | 0.0023 | -0.4038 | 1.0000 | 2.2023 |
| `validation` | 0 | `sigma_N` | 144 | 0.0023 | 0.0019 | -0.4021 | 1.0000 | 2.2078 |
| `validation` | 0 | `sigma_T` | 144 | 0.0035 | 0.0028 | 0.0713 | 1.0000 | 3.5335 |
| `validation` | 0 | `yF` | 144 | 0.0136 | 0.0119 | -0.3631 | 1.0000 | 2.2894 |
| `validation` | 0 | `yN` | 144 | 0.0169 | 0.0149 | -0.3663 | 1.0000 | 2.2872 |
| `validation` | 0 | `yT` | 144 | 0.0218 | 0.0161 | -0.3513 | 1.0000 | 2.3162 |
| `validation` | 1 | `all` | 56 | 0.0102 | 0.0083 | -0.3051 | 1.0000 | 2.4582 |
| `validation` | 1 | `delta_yF` | 56 | 0.0104 | 0.0077 | -0.3248 | 1.0000 | 2.3801 |
| `validation` | 1 | `delta_yN` | 56 | 0.0135 | 0.0112 | -0.2679 | 1.0000 | 2.5170 |
| `validation` | 1 | `delta_yT` | 56 | 0.0220 | 0.0152 | -0.6129 | 1.0000 | 1.7818 |
| `validation` | 1 | `sigma_F` | 56 | 0.0014 | 0.0012 | -0.3322 | 1.0000 | 2.3614 |
| `validation` | 1 | `sigma_N` | 56 | 0.0011 | 0.0010 | -0.3238 | 1.0000 | 2.3809 |
| `validation` | 1 | `sigma_T` | 56 | 0.0017 | 0.0015 | 0.0608 | 1.0000 | 3.4964 |
| `validation` | 1 | `yF` | 56 | 0.0127 | 0.0118 | -0.3223 | 1.0000 | 2.3832 |
| `validation` | 1 | `yN` | 56 | 0.0164 | 0.0151 | -0.3103 | 1.0000 | 2.4150 |
| `validation` | 1 | `yT` | 56 | 0.0130 | 0.0101 | -0.3121 | 1.0000 | 2.4079 |
| `validation` | 2 | `all` | 48 | 0.0133 | 0.0107 | -0.3657 | 1.0000 | 2.3266 |
| `validation` | 2 | `delta_yF` | 48 | 0.0167 | 0.0130 | -0.3874 | 1.0000 | 2.2397 |
| `validation` | 2 | `delta_yN` | 48 | 0.0157 | 0.0129 | -0.3348 | 1.0000 | 2.3538 |
| `validation` | 2 | `delta_yT` | 48 | 0.0252 | 0.0178 | -0.7206 | 1.0000 | 1.5998 |
| `validation` | 2 | `sigma_F` | 48 | 0.0027 | 0.0024 | -0.4143 | 1.0000 | 2.1748 |
| `validation` | 2 | `sigma_N` | 48 | 0.0022 | 0.0020 | -0.4099 | 1.0000 | 2.1851 |
| `validation` | 2 | `sigma_T` | 48 | 0.0034 | 0.0030 | 0.0719 | 1.0000 | 3.5355 |
| `validation` | 2 | `yF` | 48 | 0.0136 | 0.0118 | -0.3692 | 1.0000 | 2.2739 |
| `validation` | 2 | `yN` | 48 | 0.0183 | 0.0159 | -0.3727 | 1.0000 | 2.2704 |
| `validation` | 2 | `yT` | 48 | 0.0218 | 0.0173 | -0.3547 | 1.0000 | 2.3068 |
| `validation` | 3 | `all` | 40 | 0.0171 | 0.0139 | -0.4299 | 1.0000 | 2.1975 |
| `validation` | 3 | `delta_yF` | 40 | 0.0247 | 0.0212 | -0.4698 | 1.0000 | 2.0636 |
| `validation` | 3 | `delta_yN` | 40 | 0.0339 | 0.0273 | -0.4063 | 1.0000 | 2.1891 |
| `validation` | 3 | `delta_yT` | 40 | 0.0224 | 0.0170 | -0.8323 | 1.0000 | 1.4320 |
| `validation` | 3 | `sigma_F` | 40 | 0.0041 | 0.0036 | -0.4914 | 1.0000 | 2.0127 |
| `validation` | 3 | `sigma_N` | 40 | 0.0033 | 0.0030 | -0.5025 | 1.0000 | 1.9928 |
| `validation` | 3 | `sigma_T` | 40 | 0.0051 | 0.0045 | 0.0852 | 1.0000 | 3.5829 |
| `validation` | 3 | `yF` | 40 | 0.0146 | 0.0120 | -0.4130 | 1.0000 | 2.1766 |
| `validation` | 3 | `yN` | 40 | 0.0157 | 0.0132 | -0.4371 | 1.0000 | 2.1284 |
| `validation` | 3 | `yT` | 40 | 0.0301 | 0.0231 | -0.4019 | 1.0000 | 2.1992 |

## Persistence Comparison

| split | horizon | target | Neural ODE v2 RMSE | persistence RMSE | RMSE rel improvement | Neural ODE v2 MAE | persistence MAE | MAE rel improvement |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `test` | 0 | `all` | 0.0147 | 0.0215 | 0.3180 | 0.0114 | 0.0169 | 0.3210 |
| `train` | 0 | `all` | 0.0131 | 0.0176 | 0.2574 | 0.0100 | 0.0131 | 0.2392 |
| `validation` | 0 | `all` | 0.0137 | 0.0212 | 0.3544 | 0.0106 | 0.0170 | 0.3756 |

## Outputs

- Model: `models/pipe_neural_ode/continuous_v2_synthetic_smoke/pipe_neural_ode_continuous_model_v2.pt`
- Checkpoint: `models/pipe_neural_ode/continuous_v2_synthetic_smoke/pipe_neural_ode_continuous_checkpoint_v2.pt`
- Metrics: `reports/pipe_neural_ode/continuous_v2_synthetic_smoke/pipe_neural_ode_continuous_metrics.csv`
- Persistence metrics: `reports/pipe_neural_ode/continuous_v2_synthetic_smoke/pipe_neural_ode_continuous_persistence_metrics.csv`
- Persistence comparison: `reports/pipe_neural_ode/continuous_v2_synthetic_smoke/pipe_neural_ode_continuous_persistence_comparison.csv`
- Output blend weights: `reports/pipe_neural_ode/continuous_v2_synthetic_smoke/pipe_neural_ode_continuous_output_blend_weights.csv`
- Output blend search: `reports/pipe_neural_ode/continuous_v2_synthetic_smoke/pipe_neural_ode_continuous_output_blend_search.csv`
- Training curve: `reports/pipe_neural_ode/continuous_v2_synthetic_smoke/pipe_neural_ode_continuous_training_curve.csv`
- Prediction examples: `reports/pipe_neural_ode/continuous_v2_synthetic_smoke/pipe_neural_ode_continuous_prediction_examples.csv`
- Manifest: `reports/pipe_neural_ode/continuous_v2_synthetic_smoke/pipe_neural_ode_continuous_manifest.json`
