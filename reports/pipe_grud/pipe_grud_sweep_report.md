# PIPE/GRU-D Hyperparameter Sweep

Generated at UTC: `2026-05-17T02:00:24.294842+00:00`
Started at UTC: `2026-05-17T01:19:04.468028+00:00`
Sweep id: `pipe_grud_sweep_v0`

## Scope

This sweep compares PIPE/GRU-D hyperparameter configurations without overwriting the frozen model artifact.
Ranking is selected on validation only; test metrics are included for audit after selection.

## Grid

- History lengths: `3,6,12`
- Hidden dimensions: `64,96,128`
- MSE weights: `0.25,0.5,1.0`
- Learning rates: `0.001`
- Epochs: `20`
- Max train windows: `0`
- Max eval windows: `0`

## Best Validation Selection

- Trial: `h12_hd096_mse1_lr0p001_seed1729`
- History length: `12`
- Hidden dimension: `96`
- MSE weight: `1.0000`
- Learning rate: `0.001`
- Best epoch: `20`
- Validation objective: `0.7450`
- Validation RMSE all: `0.1128`
- Validation MAE all: `0.0601`
- Test RMSE all: `0.1091`
- Test MAE all: `0.0580`
- Test RMSE improvement vs persistence: `0.2735`
- Test MAE improvement vs persistence: `0.2128`
- Trial report: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0/h12_hd096_mse1_lr0p001_seed1729/pipe_grud_report.md`

## Ranked Trials

| rank | trial | status | h | hidden | mse | lr | best epoch | validation objective | validation RMSE | validation MAE | test RMSE | test MAE |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `h12_hd096_mse1_lr0p001_seed1729` | `completed` | 12 | 96 | 1.0000 | 0.001 | 20 | 0.7450 | 0.1128 | 0.0601 | 0.1091 | 0.0580 |
| 2 | `h12_hd096_mse0p5_lr0p001_seed1729` | `completed` | 12 | 96 | 0.5000 | 0.001 | 3 | 0.7460 | 0.1121 | 0.0607 | 0.1084 | 0.0582 |
| 3 | `h12_hd128_mse0p25_lr0p001_seed1729` | `completed` | 12 | 128 | 0.2500 | 0.001 | 20 | 0.7508 | 0.1128 | 0.0610 | 0.1097 | 0.0595 |
| 4 | `h12_hd096_mse0p25_lr0p001_seed1729` | `completed` | 12 | 96 | 0.2500 | 0.001 | 3 | 0.7568 | 0.1125 | 0.0621 | 0.1091 | 0.0596 |
| 5 | `h12_hd128_mse1_lr0p001_seed1729` | `completed` | 12 | 128 | 1.0000 | 0.001 | 2 | 0.7619 | 0.1149 | 0.0617 | 0.1116 | 0.0600 |
| 6 | `h12_hd128_mse0p5_lr0p001_seed1729` | `completed` | 12 | 128 | 0.5000 | 0.001 | 16 | 0.7646 | 0.1144 | 0.0624 | 0.1109 | 0.0611 |
| 7 | `h06_hd128_mse0p25_lr0p001_seed1729` | `completed` | 6 | 128 | 0.2500 | 0.001 | 15 | 0.7666 | 0.1122 | 0.0605 | 0.1144 | 0.0614 |
| 8 | `h06_hd128_mse0p5_lr0p001_seed1729` | `completed` | 6 | 128 | 0.5000 | 0.001 | 18 | 0.7673 | 0.1125 | 0.0605 | 0.1147 | 0.0613 |
| 9 | `h06_hd128_mse1_lr0p001_seed1729` | `completed` | 6 | 128 | 1.0000 | 0.001 | 20 | 0.7691 | 0.1121 | 0.0610 | 0.1143 | 0.0618 |
| 10 | `h03_hd128_mse0p25_lr0p001_seed1729` | `completed` | 3 | 128 | 0.2500 | 0.001 | 19 | 0.7700 | 0.1189 | 0.0632 | 0.1251 | 0.0676 |
| 11 | `h03_hd128_mse1_lr0p001_seed1729` | `completed` | 3 | 128 | 1.0000 | 0.001 | 19 | 0.7703 | 0.1187 | 0.0633 | 0.1249 | 0.0677 |
| 12 | `h03_hd128_mse0p5_lr0p001_seed1729` | `completed` | 3 | 128 | 0.5000 | 0.001 | 19 | 0.7704 | 0.1188 | 0.0633 | 0.1250 | 0.0676 |
| 13 | `h12_hd064_mse0p5_lr0p001_seed1729` | `completed` | 12 | 64 | 0.5000 | 0.001 | 18 | 0.7733 | 0.1175 | 0.0622 | 0.1130 | 0.0604 |
| 14 | `h06_hd096_mse0p25_lr0p001_seed1729` | `completed` | 6 | 96 | 0.2500 | 0.001 | 20 | 0.7746 | 0.1135 | 0.0611 | 0.1155 | 0.0620 |
| 15 | `h03_hd096_mse1_lr0p001_seed1729` | `completed` | 3 | 96 | 1.0000 | 0.001 | 20 | 0.7750 | 0.1191 | 0.0639 | 0.1253 | 0.0681 |
| 16 | `h06_hd096_mse1_lr0p001_seed1729` | `completed` | 6 | 96 | 1.0000 | 0.001 | 20 | 0.7754 | 0.1137 | 0.0612 | 0.1157 | 0.0620 |
| 17 | `h03_hd096_mse0p5_lr0p001_seed1729` | `completed` | 3 | 96 | 0.5000 | 0.001 | 19 | 0.7758 | 0.1194 | 0.0638 | 0.1257 | 0.0681 |
| 18 | `h03_hd096_mse0p25_lr0p001_seed1729` | `completed` | 3 | 96 | 0.2500 | 0.001 | 18 | 0.7762 | 0.1195 | 0.0638 | 0.1259 | 0.0682 |
| 19 | `h06_hd064_mse1_lr0p001_seed1729` | `completed` | 6 | 64 | 1.0000 | 0.001 | 20 | 0.7773 | 0.1138 | 0.0614 | 0.1157 | 0.0624 |
| 20 | `h06_hd096_mse0p5_lr0p001_seed1729` | `completed` | 6 | 96 | 0.5000 | 0.001 | 16 | 0.7777 | 0.1137 | 0.0615 | 0.1157 | 0.0624 |
| 21 | `h03_hd064_mse1_lr0p001_seed1729` | `completed` | 3 | 64 | 1.0000 | 0.001 | 19 | 0.7778 | 0.1199 | 0.0639 | 0.1262 | 0.0684 |
| 22 | `h12_hd064_mse0p25_lr0p001_seed1729` | `completed` | 12 | 64 | 0.2500 | 0.001 | 18 | 0.7784 | 0.1179 | 0.0628 | 0.1135 | 0.0610 |
| 23 | `h06_hd064_mse0p25_lr0p001_seed1729` | `completed` | 6 | 64 | 0.2500 | 0.001 | 18 | 0.7786 | 0.1141 | 0.0614 | 0.1158 | 0.0625 |
| 24 | `h03_hd064_mse0p25_lr0p001_seed1729` | `completed` | 3 | 64 | 0.2500 | 0.001 | 17 | 0.7792 | 0.1202 | 0.0639 | 0.1268 | 0.0685 |
| 25 | `h03_hd064_mse0p5_lr0p001_seed1729` | `completed` | 3 | 64 | 0.5000 | 0.001 | 19 | 0.7794 | 0.1202 | 0.0640 | 0.1267 | 0.0685 |
| 26 | `h06_hd064_mse0p5_lr0p001_seed1729` | `completed` | 6 | 64 | 0.5000 | 0.001 | 18 | 0.7796 | 0.1142 | 0.0615 | 0.1159 | 0.0624 |
| 27 | `h12_hd064_mse1_lr0p001_seed1729` | `completed` | 12 | 64 | 1.0000 | 0.001 | 19 | 0.7835 | 0.1177 | 0.0637 | 0.1133 | 0.0621 |

## Outputs

- Summary CSV: `reports/pipe_grud/pipe_grud_sweep_summary.csv`
- Manifest: `reports/pipe_grud/pipe_grud_sweep_manifest.json`
- Trial reports root: `reports/pipe_grud/sweep_trials/pipe_grud_sweep_v0`
- Trial models root: `models/pipe_grud/sweep_trials/pipe_grud_sweep_v0`
