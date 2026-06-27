# MIFAL Controlled Degradation Report

Generated at UTC: `2026-06-27T17:47:43.909178+00:00`

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
- Output name: `mifal_controlled_degradation_no_current_chla_smoke_full`
- Evaluation splits: `validation, test`
- Include VOI: `False`

## Scenario Summary

| scenario | seed | rows | retained | affected rows | affected cells | metrics rows |
|---|---:|---:|---:|---:|---:|---:|
| `ablate_light` | NA | 23,531 | 1.0000 | 23,322 | 101,226 | 12 |
| `ablate_nutrients` | NA | 23,531 | 1.0000 | 22,718 | 116,041 | 12 |
| `control_observed` | NA | 23,531 | 1.0000 | 0 | 0 | 12 |
| `random_dropout_mcar_25` | 20260612 | 23,531 | 1.0000 | 17,317 | 93,630 | 12 |
| `random_dropout_mcar_25` | 20260613 | 23,531 | 1.0000 | 17,190 | 92,381 | 12 |
| `random_dropout_mcar_25` | 20260614 | 23,531 | 1.0000 | 17,368 | 93,455 | 12 |
| `temporal_blocks_3m_rate_10` | 20260612 | 23,531 | 1.0000 | 751 | 11,288 | 12 |
| `temporal_blocks_3m_rate_10` | 20260613 | 23,531 | 1.0000 | 580 | 8,147 | 12 |
| `temporal_blocks_3m_rate_10` | 20260614 | 23,531 | 1.0000 | 677 | 10,230 | 12 |

## Test Metrics

| scenario | seed | horizon | source | rows | PR-AUC | Brier | F-beta | delta F-beta | interval width | confidence | calibration bias |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `ablate_light` | NA | 1 | `all` | 4,673 | 0.3443 | 0.1393 | 0.5976 | 0.0028 | 0.6555 | 0.1787 | -0.0730 |
| `ablate_light` | NA | 2 | `all` | 4,710 | 0.3321 | 0.1415 | 0.5948 | 0.0026 | 0.6593 | 0.1767 | -0.0670 |
| `ablate_light` | NA | 3 | `all` | 4,757 | 0.3112 | 0.1413 | 0.5708 | 0.0015 | 0.6592 | 0.1768 | -0.0586 |
| `ablate_nutrients` | NA | 1 | `all` | 4,673 | 0.2567 | 0.1523 | 0.2548 | -0.3400 | 0.6365 | 0.1847 | -0.1056 |
| `ablate_nutrients` | NA | 2 | `all` | 4,710 | 0.3007 | 0.1518 | 0.2556 | -0.3366 | 0.6393 | 0.1833 | -0.0986 |
| `ablate_nutrients` | NA | 3 | `all` | 4,757 | 0.2519 | 0.1544 | 0.2379 | -0.3315 | 0.6387 | 0.1836 | -0.0989 |
| `control_observed` | NA | 1 | `all` | 4,673 | 0.3608 | 0.1344 | 0.5949 | 0.0000 | 0.6581 | 0.1800 | -0.0625 |
| `control_observed` | NA | 2 | `all` | 4,710 | 0.3307 | 0.1384 | 0.5922 | 0.0000 | 0.6621 | 0.1779 | -0.0577 |
| `control_observed` | NA | 3 | `all` | 4,757 | 0.3218 | 0.1398 | 0.5693 | 0.0000 | 0.6622 | 0.1780 | -0.0542 |
| `random_dropout_mcar_25` | 20260612 | 1 | `all` | 4,673 | 0.2431 | 0.1465 | 0.4981 | -0.0967 | 0.6613 | 0.1768 | -0.0424 |
| `random_dropout_mcar_25` | 20260612 | 2 | `all` | 4,710 | 0.2371 | 0.1471 | 0.5317 | -0.0605 | 0.6656 | 0.1746 | -0.0420 |
| `random_dropout_mcar_25` | 20260612 | 3 | `all` | 4,757 | 0.2244 | 0.1490 | 0.5170 | -0.0523 | 0.6658 | 0.1745 | -0.0345 |
| `random_dropout_mcar_25` | 20260613 | 1 | `all` | 4,673 | 0.2472 | 0.1456 | 0.4986 | -0.0963 | 0.6614 | 0.1767 | -0.0426 |
| `random_dropout_mcar_25` | 20260613 | 2 | `all` | 4,710 | 0.2447 | 0.1458 | 0.5438 | -0.0484 | 0.6655 | 0.1746 | -0.0412 |
| `random_dropout_mcar_25` | 20260613 | 3 | `all` | 4,757 | 0.2319 | 0.1477 | 0.5280 | -0.0413 | 0.6659 | 0.1744 | -0.0349 |
| `random_dropout_mcar_25` | 20260614 | 1 | `all` | 4,673 | 0.2486 | 0.1456 | 0.5085 | -0.0864 | 0.6614 | 0.1768 | -0.0426 |
| `random_dropout_mcar_25` | 20260614 | 2 | `all` | 4,710 | 0.2385 | 0.1466 | 0.5368 | -0.0554 | 0.6659 | 0.1744 | -0.0398 |
| `random_dropout_mcar_25` | 20260614 | 3 | `all` | 4,757 | 0.2365 | 0.1471 | 0.5373 | -0.0320 | 0.6663 | 0.1743 | -0.0341 |
| `temporal_blocks_3m_rate_10` | 20260612 | 1 | `all` | 4,673 | 0.3586 | 0.1350 | 0.5850 | -0.0099 | 0.6576 | 0.1800 | -0.0643 |
| `temporal_blocks_3m_rate_10` | 20260612 | 2 | `all` | 4,710 | 0.3288 | 0.1389 | 0.5814 | -0.0107 | 0.6616 | 0.1779 | -0.0593 |
| `temporal_blocks_3m_rate_10` | 20260612 | 3 | `all` | 4,757 | 0.3207 | 0.1403 | 0.5612 | -0.0081 | 0.6617 | 0.1779 | -0.0558 |
| `temporal_blocks_3m_rate_10` | 20260613 | 1 | `all` | 4,673 | 0.3578 | 0.1350 | 0.5874 | -0.0075 | 0.6578 | 0.1800 | -0.0638 |
| `temporal_blocks_3m_rate_10` | 20260613 | 2 | `all` | 4,710 | 0.3280 | 0.1389 | 0.5844 | -0.0078 | 0.6617 | 0.1780 | -0.0588 |
| `temporal_blocks_3m_rate_10` | 20260613 | 3 | `all` | 4,757 | 0.3190 | 0.1403 | 0.5616 | -0.0077 | 0.6618 | 0.1780 | -0.0555 |
| `temporal_blocks_3m_rate_10` | 20260614 | 1 | `all` | 4,673 | 0.3502 | 0.1358 | 0.5754 | -0.0194 | 0.6578 | 0.1799 | -0.0643 |
| `temporal_blocks_3m_rate_10` | 20260614 | 2 | `all` | 4,710 | 0.3218 | 0.1396 | 0.5745 | -0.0177 | 0.6617 | 0.1779 | -0.0593 |
| `temporal_blocks_3m_rate_10` | 20260614 | 3 | `all` | 4,757 | 0.3152 | 0.1409 | 0.5536 | -0.0157 | 0.6618 | 0.1779 | -0.0559 |

## Guardrails

- This is a stress test, not an official environmental alert.
- Calibration and threshold selection are not repeated under degraded evidence.
- Better interval coverage with poor discrimination is a partial result, not a win.
- MIFAL is evaluated only for `bloom_h`; it does not emit `irc_alert`.

## Outputs

- Metrics: `reports/degradation/mifal_controlled_degradation_no_current_chla_smoke_full_metrics.csv`
- Summary: `reports/degradation/mifal_controlled_degradation_no_current_chla_smoke_full_summary.csv`
- Availability: `reports/degradation/mifal_controlled_degradation_no_current_chla_smoke_full_availability.csv`
- Examples: `reports/degradation/mifal_controlled_degradation_no_current_chla_smoke_full_examples.csv`
- Manifest: `reports/degradation/mifal_controlled_degradation_no_current_chla_smoke_full_manifest.json`
