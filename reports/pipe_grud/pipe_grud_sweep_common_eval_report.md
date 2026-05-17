# PIPE/GRU-D Sweep Common-Window Evaluation

Generated at UTC: `2026-05-17T02:12:30.565076+00:00`
Started at UTC: `2026-05-17T02:11:40.162943+00:00`

## Scope

This evaluation compares sweep trials on the same end-window population.
It is required before promoting a trial when history length varies across the sweep.
Ranking is selected on common validation windows only; common test metrics are included for audit.

## Common Window

- Common history length: `12`
- Checkpoint selection metric: `balanced`

## Best Common Validation Selection

- Trial: `h12_hd096_mse1_lr0p001_seed1729`
- Original sweep rank: `1`
- History length: `12`
- Hidden dimension: `96`
- MSE weight: `1.0000`
- Common validation objective: `0.7450`
- Common validation RMSE all: `0.1128`
- Common validation MAE all: `0.0601`
- Common test RMSE all: `0.1091`
- Common test MAE all: `0.0580`
- Common test RMSE improvement vs persistence: `0.2735`
- Common test MAE improvement vs persistence: `0.2128`

## Ranked Common Evaluation

| rank | trial | original rank | h | hidden | mse | validation objective | validation RMSE | validation MAE | test RMSE | test MAE |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `h12_hd096_mse1_lr0p001_seed1729` | 1 | 12 | 96 | 1.0000 | 0.7450 | 0.1128 | 0.0601 | 0.1091 | 0.0580 |
| 2 | `h12_hd096_mse0p5_lr0p001_seed1729` | 2 | 12 | 96 | 0.5000 | 0.7460 | 0.1121 | 0.0607 | 0.1084 | 0.0582 |
| 3 | `h12_hd128_mse0p25_lr0p001_seed1729` | 3 | 12 | 128 | 0.2500 | 0.7508 | 0.1128 | 0.0610 | 0.1097 | 0.0595 |
| 4 | `h12_hd096_mse0p25_lr0p001_seed1729` | 4 | 12 | 96 | 0.2500 | 0.7568 | 0.1125 | 0.0621 | 0.1091 | 0.0596 |
| 5 | `h12_hd128_mse1_lr0p001_seed1729` | 5 | 12 | 128 | 1.0000 | 0.7619 | 0.1149 | 0.0617 | 0.1116 | 0.0600 |
| 6 | `h12_hd128_mse0p5_lr0p001_seed1729` | 6 | 12 | 128 | 0.5000 | 0.7646 | 0.1144 | 0.0624 | 0.1109 | 0.0611 |
| 7 | `h06_hd128_mse0p25_lr0p001_seed1729` | 7 | 6 | 128 | 0.2500 | 0.7679 | 0.1154 | 0.0624 | 0.1112 | 0.0604 |
| 8 | `h03_hd128_mse0p25_lr0p001_seed1729` | 10 | 3 | 128 | 0.2500 | 0.7681 | 0.1156 | 0.0624 | 0.1113 | 0.0605 |
| 9 | `h03_hd128_mse0p5_lr0p001_seed1729` | 12 | 3 | 128 | 0.5000 | 0.7681 | 0.1155 | 0.0624 | 0.1113 | 0.0605 |
| 10 | `h06_hd128_mse0p5_lr0p001_seed1729` | 8 | 6 | 128 | 0.5000 | 0.7686 | 0.1155 | 0.0625 | 0.1115 | 0.0603 |
| 11 | `h03_hd128_mse1_lr0p001_seed1729` | 11 | 3 | 128 | 1.0000 | 0.7688 | 0.1155 | 0.0625 | 0.1111 | 0.0607 |
| 12 | `h06_hd128_mse1_lr0p001_seed1729` | 9 | 6 | 128 | 1.0000 | 0.7706 | 0.1151 | 0.0630 | 0.1111 | 0.0609 |
| 13 | `h03_hd096_mse1_lr0p001_seed1729` | 15 | 3 | 96 | 1.0000 | 0.7731 | 0.1157 | 0.0631 | 0.1115 | 0.0612 |
| 14 | `h12_hd064_mse0p5_lr0p001_seed1729` | 13 | 12 | 64 | 0.5000 | 0.7733 | 0.1175 | 0.0622 | 0.1130 | 0.0604 |
| 15 | `h03_hd096_mse0p5_lr0p001_seed1729` | 17 | 3 | 96 | 0.5000 | 0.7738 | 0.1161 | 0.0630 | 0.1118 | 0.0611 |
| 16 | `h03_hd096_mse0p25_lr0p001_seed1729` | 18 | 3 | 96 | 0.2500 | 0.7740 | 0.1161 | 0.0630 | 0.1119 | 0.0612 |
| 17 | `h03_hd064_mse1_lr0p001_seed1729` | 21 | 3 | 64 | 1.0000 | 0.7748 | 0.1164 | 0.0630 | 0.1122 | 0.0614 |
| 18 | `h03_hd064_mse0p25_lr0p001_seed1729` | 24 | 3 | 64 | 0.2500 | 0.7751 | 0.1167 | 0.0629 | 0.1127 | 0.0614 |
| 19 | `h06_hd096_mse0p25_lr0p001_seed1729` | 14 | 6 | 96 | 0.2500 | 0.7762 | 0.1166 | 0.0631 | 0.1125 | 0.0614 |
| 20 | `h03_hd064_mse0p5_lr0p001_seed1729` | 25 | 3 | 64 | 0.5000 | 0.7762 | 0.1167 | 0.0631 | 0.1127 | 0.0616 |
| 21 | `h06_hd096_mse1_lr0p001_seed1729` | 16 | 6 | 96 | 1.0000 | 0.7769 | 0.1168 | 0.0631 | 0.1126 | 0.0612 |
| 22 | `h06_hd064_mse1_lr0p001_seed1729` | 19 | 6 | 64 | 1.0000 | 0.7781 | 0.1170 | 0.0632 | 0.1126 | 0.0617 |
| 23 | `h12_hd064_mse0p25_lr0p001_seed1729` | 22 | 12 | 64 | 0.2500 | 0.7784 | 0.1179 | 0.0628 | 0.1135 | 0.0610 |
| 24 | `h06_hd064_mse0p25_lr0p001_seed1729` | 23 | 6 | 64 | 0.2500 | 0.7794 | 0.1173 | 0.0633 | 0.1128 | 0.0617 |
| 25 | `h06_hd096_mse0p5_lr0p001_seed1729` | 20 | 6 | 96 | 0.5000 | 0.7796 | 0.1169 | 0.0635 | 0.1129 | 0.0617 |
| 26 | `h06_hd064_mse0p5_lr0p001_seed1729` | 26 | 6 | 64 | 0.5000 | 0.7802 | 0.1174 | 0.0633 | 0.1129 | 0.0616 |
| 27 | `h12_hd064_mse1_lr0p001_seed1729` | 27 | 12 | 64 | 1.0000 | 0.7835 | 0.1177 | 0.0637 | 0.1133 | 0.0621 |

## Outputs

- Common evaluation CSV: `reports/pipe_grud/pipe_grud_sweep_common_eval.csv`
- Manifest: `reports/pipe_grud/pipe_grud_sweep_common_eval_manifest.json`
