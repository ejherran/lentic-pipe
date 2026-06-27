# MIFAL Controlled Degradation Report

Generated at UTC: `2026-06-27T17:41:47.931861+00:00`

## Scope

This report recomputes MIFAL-ED/T2 after controlled degradation of observable panel evidence.
Labels, temporal splits, calibrators, and thresholds remain fixed.

## Configuration

- Config: `configs/degradation_scenarios.yaml`
- Surface: `observable_current_chla`
- Panel: `data/panel/panel_monthly_v0.parquet`
- Splits: `data/splits/monthly_model_splits_v0.parquet`
- Reference rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibrated_backtest_rows.parquet`
- Thresholds: `reports/mifal/mifal_observable_current_chla_pipe_grud_holdout_calibration_thresholds.csv`
- Scenario set: `mifal_observable_smoke`
- Output name: `mifal_controlled_degradation_current_chla_smoke`
- Evaluation splits: `validation, test`
- Include VOI: `False`

## Scenario Summary

| scenario | seed | rows | retained | affected rows | affected cells | metrics rows |
|---|---:|---:|---:|---:|---:|---:|
| `ablate_light` | NA | 180 | 1.0000 | 180 | 747 | 12 |
| `ablate_nutrients` | NA | 180 | 1.0000 | 175 | 935 | 12 |
| `control_observed` | NA | 180 | 1.0000 | 0 | 0 | 12 |
| `random_dropout_mcar_25` | 20260612 | 180 | 1.0000 | 144 | 800 | 12 |
| `random_dropout_mcar_25` | 20260613 | 180 | 1.0000 | 133 | 805 | 12 |
| `random_dropout_mcar_25` | 20260614 | 180 | 1.0000 | 139 | 851 | 12 |
| `temporal_blocks_3m_rate_10` | 20260612 | 180 | 1.0000 | 19 | 350 | 12 |
| `temporal_blocks_3m_rate_10` | 20260613 | 180 | 1.0000 | 15 | 296 | 12 |
| `temporal_blocks_3m_rate_10` | 20260614 | 180 | 1.0000 | 21 | 438 | 12 |

## Test Metrics

| scenario | seed | horizon | source | rows | PR-AUC | Brier | F-beta | delta F-beta | interval width | confidence | calibration bias |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `ablate_light` | NA | 1 | `all` | 30 | 0.7500 | 0.0285 | 0.7143 | 0.0000 | 0.6614 | 0.1765 | 0.0632 |
| `ablate_light` | NA | 2 | `all` | 30 | 0.5615 | 0.1585 | 0.6250 | 0.0000 | 0.6840 | 0.1654 | -0.0737 |
| `ablate_light` | NA | 3 | `all` | 30 | 0.6935 | 0.0970 | 0.5405 | -0.1174 | 0.6760 | 0.1687 | -0.0209 |
| `ablate_nutrients` | NA | 1 | `all` | 30 | 1.0000 | 0.0313 | 1.0000 | 0.2857 | 0.6463 | 0.1805 | 0.0169 |
| `ablate_nutrients` | NA | 2 | `all` | 30 | 0.4271 | 0.2251 | 0.4054 | -0.2196 | 0.6541 | 0.1765 | -0.1496 |
| `ablate_nutrients` | NA | 3 | `all` | 30 | 0.5154 | 0.1196 | 0.4167 | -0.2412 | 0.6637 | 0.1717 | -0.0621 |
| `control_observed` | NA | 1 | `all` | 30 | 0.7500 | 0.0286 | 0.7143 | 0.0000 | 0.6645 | 0.1774 | 0.0637 |
| `control_observed` | NA | 2 | `all` | 30 | 0.5615 | 0.1586 | 0.6250 | 0.0000 | 0.6853 | 0.1672 | -0.0729 |
| `control_observed` | NA | 3 | `all` | 30 | 0.6944 | 0.0963 | 0.6579 | 0.0000 | 0.6787 | 0.1700 | -0.0178 |
| `random_dropout_mcar_25` | 20260612 | 1 | `all` | 30 | 0.1650 | 0.0634 | 0.3125 | -0.4018 | 0.6674 | 0.1744 | 0.0537 |
| `random_dropout_mcar_25` | 20260612 | 2 | `all` | 30 | 0.4005 | 0.2028 | 0.4082 | -0.2168 | 0.6809 | 0.1677 | -0.0641 |
| `random_dropout_mcar_25` | 20260612 | 3 | `all` | 30 | 0.5292 | 0.1080 | 0.6944 | 0.0365 | 0.6770 | 0.1696 | 0.0241 |
| `random_dropout_mcar_25` | 20260613 | 1 | `all` | 30 | 1.0000 | 0.0435 | 0.5882 | -0.1261 | 0.6660 | 0.1753 | 0.1281 |
| `random_dropout_mcar_25` | 20260613 | 2 | `all` | 30 | 0.4699 | 0.1731 | 0.5102 | -0.1148 | 0.6776 | 0.1693 | -0.0650 |
| `random_dropout_mcar_25` | 20260613 | 3 | `all` | 30 | 0.7274 | 0.0855 | 0.5405 | -0.1174 | 0.6800 | 0.1681 | 0.0094 |
| `random_dropout_mcar_25` | 20260614 | 1 | `all` | 30 | 0.6111 | 0.0750 | 0.4762 | -0.2381 | 0.6737 | 0.1711 | 0.1432 |
| `random_dropout_mcar_25` | 20260614 | 2 | `all` | 30 | 0.3483 | 0.2196 | 0.2128 | -0.4122 | 0.6761 | 0.1701 | -0.0860 |
| `random_dropout_mcar_25` | 20260614 | 3 | `all` | 30 | 0.3556 | 0.1262 | 0.6579 | 0.0000 | 0.6800 | 0.1681 | 0.0094 |
| `temporal_blocks_3m_rate_10` | 20260612 | 1 | `all` | 30 | 0.7500 | 0.0284 | 0.7143 | 0.0000 | 0.6627 | 0.1777 | 0.0625 |
| `temporal_blocks_3m_rate_10` | 20260612 | 2 | `all` | 30 | 0.5615 | 0.1586 | 0.6250 | 0.0000 | 0.6853 | 0.1672 | -0.0729 |
| `temporal_blocks_3m_rate_10` | 20260612 | 3 | `all` | 30 | 0.5690 | 0.1180 | 0.5556 | -0.1023 | 0.6751 | 0.1708 | -0.0462 |
| `temporal_blocks_3m_rate_10` | 20260613 | 1 | `all` | 30 | 0.7500 | 0.0286 | 0.7143 | 0.0000 | 0.6681 | 0.1750 | 0.0637 |
| `temporal_blocks_3m_rate_10` | 20260613 | 2 | `all` | 30 | 0.5242 | 0.1629 | 0.5556 | -0.0694 | 0.6825 | 0.1676 | -0.0766 |
| `temporal_blocks_3m_rate_10` | 20260613 | 3 | `all` | 30 | 0.7588 | 0.0928 | 0.6757 | 0.0178 | 0.6764 | 0.1705 | -0.0265 |
| `temporal_blocks_3m_rate_10` | 20260614 | 1 | `all` | 30 | 0.7500 | 0.0281 | 0.7143 | 0.0000 | 0.6644 | 0.1761 | 0.0606 |
| `temporal_blocks_3m_rate_10` | 20260614 | 2 | `all` | 30 | 0.5615 | 0.1586 | 0.6250 | 0.0000 | 0.6843 | 0.1668 | -0.0733 |
| `temporal_blocks_3m_rate_10` | 20260614 | 3 | `all` | 30 | 0.3638 | 0.1228 | 0.4286 | -0.2293 | 0.6727 | 0.1717 | -0.0362 |

## Guardrails

- This is a stress test, not an official environmental alert.
- Calibration and threshold selection are not repeated under degraded evidence.
- Better interval coverage with poor discrimination is a partial result, not a win.
- MIFAL is evaluated only for `bloom_h`; it does not emit `irc_alert`.

## Outputs

- Metrics: `reports/degradation/mifal_controlled_degradation_current_chla_smoke_metrics.csv`
- Summary: `reports/degradation/mifal_controlled_degradation_current_chla_smoke_summary.csv`
- Availability: `reports/degradation/mifal_controlled_degradation_current_chla_smoke_availability.csv`
- Examples: `reports/degradation/mifal_controlled_degradation_current_chla_smoke_examples.csv`
- Manifest: `reports/degradation/mifal_controlled_degradation_current_chla_smoke_manifest.json`
