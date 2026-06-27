# MIFAL Controlled Degradation Report

Generated at UTC: `2026-06-27T17:45:53.601250+00:00`

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
- Output name: `mifal_controlled_degradation_current_chla_smoke_full`
- Evaluation splits: `validation, test`
- Include VOI: `False`

## Scenario Summary

| scenario | seed | rows | retained | affected rows | affected cells | metrics rows |
|---|---:|---:|---:|---:|---:|---:|
| `ablate_light` | NA | 23,531 | 1.0000 | 23,322 | 101,226 | 12 |
| `ablate_nutrients` | NA | 23,531 | 1.0000 | 22,718 | 116,041 | 12 |
| `control_observed` | NA | 23,531 | 1.0000 | 0 | 0 | 12 |
| `random_dropout_mcar_25` | 20260612 | 23,531 | 1.0000 | 18,617 | 112,711 | 12 |
| `random_dropout_mcar_25` | 20260613 | 23,531 | 1.0000 | 18,656 | 112,335 | 12 |
| `random_dropout_mcar_25` | 20260614 | 23,531 | 1.0000 | 18,769 | 113,470 | 12 |
| `temporal_blocks_3m_rate_10` | 20260612 | 23,531 | 1.0000 | 751 | 13,814 | 12 |
| `temporal_blocks_3m_rate_10` | 20260613 | 23,531 | 1.0000 | 580 | 10,186 | 12 |
| `temporal_blocks_3m_rate_10` | 20260614 | 23,531 | 1.0000 | 677 | 12,611 | 12 |

## Test Metrics

| scenario | seed | horizon | source | rows | PR-AUC | Brier | F-beta | delta F-beta | interval width | confidence | calibration bias |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `ablate_light` | NA | 1 | `all` | 4,673 | 0.6062 | 0.1017 | 0.6196 | -0.0142 | 0.6725 | 0.1706 | -0.0226 |
| `ablate_light` | NA | 2 | `all` | 4,710 | 0.5320 | 0.1130 | 0.5283 | -0.0017 | 0.6761 | 0.1687 | -0.0209 |
| `ablate_light` | NA | 3 | `all` | 4,757 | 0.4788 | 0.1206 | 0.5184 | -0.0033 | 0.6758 | 0.1689 | -0.0203 |
| `ablate_nutrients` | NA | 1 | `all` | 4,673 | 0.4900 | 0.1287 | 0.4720 | -0.1618 | 0.6537 | 0.1769 | -0.0865 |
| `ablate_nutrients` | NA | 2 | `all` | 4,710 | 0.4422 | 0.1364 | 0.4823 | -0.0478 | 0.6561 | 0.1756 | -0.0780 |
| `ablate_nutrients` | NA | 3 | `all` | 4,757 | 0.4071 | 0.1388 | 0.4490 | -0.0728 | 0.6554 | 0.1759 | -0.0745 |
| `control_observed` | NA | 1 | `all` | 4,673 | 0.6147 | 0.1005 | 0.6338 | 0.0000 | 0.6753 | 0.1717 | -0.0207 |
| `control_observed` | NA | 2 | `all` | 4,710 | 0.5416 | 0.1118 | 0.5300 | 0.0000 | 0.6790 | 0.1698 | -0.0187 |
| `control_observed` | NA | 3 | `all` | 4,757 | 0.4872 | 0.1195 | 0.5218 | 0.0000 | 0.6789 | 0.1699 | -0.0179 |
| `random_dropout_mcar_25` | 20260612 | 1 | `all` | 4,673 | 0.4220 | 0.1330 | 0.4951 | -0.1387 | 0.6744 | 0.1705 | -0.0011 |
| `random_dropout_mcar_25` | 20260612 | 2 | `all` | 4,710 | 0.3717 | 0.1393 | 0.4514 | -0.0787 | 0.6778 | 0.1688 | 0.0030 |
| `random_dropout_mcar_25` | 20260612 | 3 | `all` | 4,757 | 0.3460 | 0.1404 | 0.4402 | -0.0816 | 0.6780 | 0.1686 | -0.0052 |
| `random_dropout_mcar_25` | 20260613 | 1 | `all` | 4,673 | 0.3878 | 0.1377 | 0.4892 | -0.1446 | 0.6751 | 0.1702 | 0.0040 |
| `random_dropout_mcar_25` | 20260613 | 2 | `all` | 4,710 | 0.3478 | 0.1438 | 0.4306 | -0.0995 | 0.6784 | 0.1684 | -0.0016 |
| `random_dropout_mcar_25` | 20260613 | 3 | `all` | 4,757 | 0.3439 | 0.1405 | 0.4384 | -0.0834 | 0.6779 | 0.1687 | -0.0071 |
| `random_dropout_mcar_25` | 20260614 | 1 | `all` | 4,673 | 0.4239 | 0.1315 | 0.5077 | -0.1261 | 0.6745 | 0.1705 | 0.0004 |
| `random_dropout_mcar_25` | 20260614 | 2 | `all` | 4,710 | 0.3748 | 0.1387 | 0.4446 | -0.0855 | 0.6785 | 0.1684 | 0.0020 |
| `random_dropout_mcar_25` | 20260614 | 3 | `all` | 4,757 | 0.3423 | 0.1423 | 0.4387 | -0.0831 | 0.6780 | 0.1686 | -0.0021 |
| `temporal_blocks_3m_rate_10` | 20260612 | 1 | `all` | 4,673 | 0.6018 | 0.1024 | 0.6245 | -0.0093 | 0.6743 | 0.1720 | -0.0236 |
| `temporal_blocks_3m_rate_10` | 20260612 | 2 | `all` | 4,710 | 0.5284 | 0.1136 | 0.5243 | -0.0057 | 0.6780 | 0.1700 | -0.0214 |
| `temporal_blocks_3m_rate_10` | 20260612 | 3 | `all` | 4,757 | 0.4787 | 0.1206 | 0.5174 | -0.0044 | 0.6779 | 0.1701 | -0.0204 |
| `temporal_blocks_3m_rate_10` | 20260613 | 1 | `all` | 4,673 | 0.6046 | 0.1020 | 0.6265 | -0.0073 | 0.6746 | 0.1719 | -0.0228 |
| `temporal_blocks_3m_rate_10` | 20260613 | 2 | `all` | 4,710 | 0.5325 | 0.1130 | 0.5263 | -0.0038 | 0.6783 | 0.1699 | -0.0205 |
| `temporal_blocks_3m_rate_10` | 20260613 | 3 | `all` | 4,757 | 0.4792 | 0.1206 | 0.5180 | -0.0037 | 0.6782 | 0.1700 | -0.0198 |
| `temporal_blocks_3m_rate_10` | 20260614 | 1 | `all` | 4,673 | 0.5939 | 0.1035 | 0.6163 | -0.0175 | 0.6745 | 0.1719 | -0.0246 |
| `temporal_blocks_3m_rate_10` | 20260614 | 2 | `all` | 4,710 | 0.5243 | 0.1142 | 0.5180 | -0.0120 | 0.6782 | 0.1699 | -0.0222 |
| `temporal_blocks_3m_rate_10` | 20260614 | 3 | `all` | 4,757 | 0.4730 | 0.1215 | 0.5112 | -0.0105 | 0.6781 | 0.1700 | -0.0212 |

## Guardrails

- This is a stress test, not an official environmental alert.
- Calibration and threshold selection are not repeated under degraded evidence.
- Better interval coverage with poor discrimination is a partial result, not a win.
- MIFAL is evaluated only for `bloom_h`; it does not emit `irc_alert`.

## Outputs

- Metrics: `reports/degradation/mifal_controlled_degradation_current_chla_smoke_full_metrics.csv`
- Summary: `reports/degradation/mifal_controlled_degradation_current_chla_smoke_full_summary.csv`
- Availability: `reports/degradation/mifal_controlled_degradation_current_chla_smoke_full_availability.csv`
- Examples: `reports/degradation/mifal_controlled_degradation_current_chla_smoke_full_examples.csv`
- Manifest: `reports/degradation/mifal_controlled_degradation_current_chla_smoke_full_manifest.json`
