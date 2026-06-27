# MIFAL Controlled Degradation Report

Generated at UTC: `2026-06-27T17:41:48.610613+00:00`

## Scope

This report recomputes MIFAL-ED/T2 after controlled degradation of observable panel evidence.
Labels, temporal splits, calibrators, and thresholds remain fixed.

## Configuration

- Config: `configs/degradation_scenarios.yaml`
- Surface: `observable_no_current_chla`
- Panel: `data/panel/panel_monthly_v0.parquet`
- Splits: `data/splits/monthly_model_splits_v0.parquet`
- Reference rows: `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibrated_backtest_rows.parquet`
- Thresholds: `reports/mifal/mifal_observable_no_current_chla_pipe_grud_holdout_calibration_thresholds.csv`
- Scenario set: `mifal_observable_smoke`
- Output name: `mifal_controlled_degradation_no_current_chla_smoke`
- Evaluation splits: `validation, test`
- Include VOI: `False`

## Scenario Summary

| scenario | seed | rows | retained | affected rows | affected cells | metrics rows |
|---|---:|---:|---:|---:|---:|---:|
| `ablate_light` | NA | 180 | 1.0000 | 180 | 747 | 12 |
| `ablate_nutrients` | NA | 180 | 1.0000 | 175 | 935 | 12 |
| `control_observed` | NA | 180 | 1.0000 | 0 | 0 | 12 |
| `random_dropout_mcar_25` | 20260612 | 180 | 1.0000 | 131 | 674 | 12 |
| `random_dropout_mcar_25` | 20260613 | 180 | 1.0000 | 119 | 619 | 12 |
| `random_dropout_mcar_25` | 20260614 | 180 | 1.0000 | 127 | 733 | 12 |
| `temporal_blocks_3m_rate_10` | 20260612 | 180 | 1.0000 | 19 | 290 | 12 |
| `temporal_blocks_3m_rate_10` | 20260613 | 180 | 1.0000 | 15 | 239 | 12 |
| `temporal_blocks_3m_rate_10` | 20260614 | 180 | 1.0000 | 21 | 376 | 12 |

## Test Metrics

| scenario | seed | horizon | source | rows | PR-AUC | Brier | F-beta | delta F-beta | interval width | confidence | calibration bias |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `ablate_light` | NA | 1 | `all` | 30 | 0.6667 | 0.0475 | 0.7143 | 0.0000 | 0.6451 | 0.1841 | 0.0155 |
| `ablate_light` | NA | 2 | `all` | 30 | 0.5201 | 0.1949 | 0.6667 | 0.0000 | 0.6658 | 0.1742 | -0.1451 |
| `ablate_light` | NA | 3 | `all` | 30 | 0.4333 | 0.1198 | 0.7143 | 0.0000 | 0.6607 | 0.1759 | -0.0547 |
| `ablate_nutrients` | NA | 1 | `all` | 30 | 0.5333 | 0.0503 | 0.5556 | -0.1587 | 0.6299 | 0.1879 | -0.0005 |
| `ablate_nutrients` | NA | 2 | `all` | 30 | 0.2689 | 0.2360 | 0.0000 | -0.6667 | 0.6359 | 0.1850 | -0.1903 |
| `ablate_nutrients` | NA | 3 | `all` | 30 | 0.3333 | 0.1375 | 0.2381 | -0.4762 | 0.6485 | 0.1787 | -0.0883 |
| `control_observed` | NA | 1 | `all` | 30 | 0.5000 | 0.0445 | 0.7143 | 0.0000 | 0.6480 | 0.1852 | 0.0281 |
| `control_observed` | NA | 2 | `all` | 30 | 0.5129 | 0.1872 | 0.6667 | 0.0000 | 0.6670 | 0.1761 | -0.1320 |
| `control_observed` | NA | 3 | `all` | 30 | 0.4000 | 0.1196 | 0.7143 | 0.0000 | 0.6634 | 0.1773 | -0.0514 |
| `random_dropout_mcar_25` | 20260612 | 1 | `all` | 30 | 0.1625 | 0.0661 | 0.2941 | -0.4202 | 0.6460 | 0.1849 | 0.0539 |
| `random_dropout_mcar_25` | 20260612 | 2 | `all` | 30 | 0.3051 | 0.2103 | 0.5319 | -0.1348 | 0.6653 | 0.1753 | -0.1263 |
| `random_dropout_mcar_25` | 20260612 | 3 | `all` | 30 | 0.1750 | 0.1396 | 0.4545 | -0.2597 | 0.6679 | 0.1730 | -0.0190 |
| `random_dropout_mcar_25` | 20260613 | 1 | `all` | 30 | 0.2000 | 0.0594 | 0.4762 | -0.2381 | 0.6531 | 0.1817 | 0.0734 |
| `random_dropout_mcar_25` | 20260613 | 2 | `all` | 30 | 0.2964 | 0.2084 | 0.6122 | -0.0544 | 0.6708 | 0.1727 | -0.1151 |
| `random_dropout_mcar_25` | 20260613 | 3 | `all` | 30 | 0.2101 | 0.1349 | 0.4839 | -0.2304 | 0.6638 | 0.1757 | -0.0298 |
| `random_dropout_mcar_25` | 20260614 | 1 | `all` | 30 | 0.0833 | 0.0756 | 0.0000 | -0.7143 | 0.6613 | 0.1764 | 0.0534 |
| `random_dropout_mcar_25` | 20260614 | 2 | `all` | 30 | 0.3762 | 0.1942 | 0.6122 | -0.0544 | 0.6752 | 0.1699 | -0.1109 |
| `random_dropout_mcar_25` | 20260614 | 3 | `all` | 30 | 0.2565 | 0.1298 | 0.6452 | -0.0691 | 0.6602 | 0.1777 | -0.0354 |
| `temporal_blocks_3m_rate_10` | 20260612 | 1 | `all` | 30 | 0.5000 | 0.0445 | 0.7143 | 0.0000 | 0.6473 | 0.1851 | 0.0281 |
| `temporal_blocks_3m_rate_10` | 20260612 | 2 | `all` | 30 | 0.5129 | 0.1872 | 0.6667 | 0.0000 | 0.6670 | 0.1761 | -0.1320 |
| `temporal_blocks_3m_rate_10` | 20260612 | 3 | `all` | 30 | 0.3333 | 0.1262 | 0.5769 | -0.1374 | 0.6623 | 0.1769 | -0.0606 |
| `temporal_blocks_3m_rate_10` | 20260613 | 1 | `all` | 30 | 0.5000 | 0.0445 | 0.7143 | 0.0000 | 0.6522 | 0.1826 | 0.0281 |
| `temporal_blocks_3m_rate_10` | 20260613 | 2 | `all` | 30 | 0.4333 | 0.1974 | 0.5682 | -0.0985 | 0.6655 | 0.1759 | -0.1383 |
| `temporal_blocks_3m_rate_10` | 20260613 | 3 | `all` | 30 | 0.4286 | 0.1183 | 0.7407 | 0.0265 | 0.6624 | 0.1772 | -0.0560 |
| `temporal_blocks_3m_rate_10` | 20260614 | 1 | `all` | 30 | 0.5000 | 0.0445 | 0.7143 | 0.0000 | 0.6500 | 0.1830 | 0.0281 |
| `temporal_blocks_3m_rate_10` | 20260614 | 2 | `all` | 30 | 0.5141 | 0.1872 | 0.6667 | 0.0000 | 0.6667 | 0.1755 | -0.1322 |
| `temporal_blocks_3m_rate_10` | 20260614 | 3 | `all` | 30 | 0.2333 | 0.1378 | 0.3846 | -0.3297 | 0.6602 | 0.1777 | -0.0622 |

## Guardrails

- This is a stress test, not an official environmental alert.
- Calibration and threshold selection are not repeated under degraded evidence.
- Better interval coverage with poor discrimination is a partial result, not a win.
- MIFAL is evaluated only for `bloom_h`; it does not emit `irc_alert`.

## Outputs

- Metrics: `reports/degradation/mifal_controlled_degradation_no_current_chla_smoke_metrics.csv`
- Summary: `reports/degradation/mifal_controlled_degradation_no_current_chla_smoke_summary.csv`
- Availability: `reports/degradation/mifal_controlled_degradation_no_current_chla_smoke_availability.csv`
- Examples: `reports/degradation/mifal_controlled_degradation_no_current_chla_smoke_examples.csv`
- Manifest: `reports/degradation/mifal_controlled_degradation_no_current_chla_smoke_manifest.json`
