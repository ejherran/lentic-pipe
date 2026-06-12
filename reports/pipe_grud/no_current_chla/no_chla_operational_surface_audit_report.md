# No-Current-Chl-a Operational Surface Audit

Generated at UTC: `2026-06-12T22:04:00.174841+00:00`
Started at UTC: `2026-06-12T22:03:52.078847+00:00`
Audit version: `no_chla_operational_surface_audit_v0`

## Purpose

This audit checks whether target-bearing rows have non-Chl-a precursor evidence at the origin month.
It does not train, calibrate, or select thresholds.

Current Chl-a columns are treated as forbidden predictors for the operational early-warning contract.
They are counted only as a diagnostic reference.

## Headline Counts

- Target split rows audited: `4,610,977`
- Source-scoped sites audited: `93,310`
- Rows with any nutrient precursor: `0.1644`
- Rows with high precursor readiness: `0.1167`
- Rows with season-only non-Chl-a evidence: `0.6919`
- Rows where forbidden current Chl-a exists but must not be used: `0.9762`

## Evidence Band Rules

- `high`: nutrient evidence plus temperature plus either light proxy or physicochemical evidence.
- `medium`: nutrient evidence plus at least one nonseason companion group.
- `low`: at least one nonseason exogenous group, but not enough for `medium`.
- `season_only`: no nonseason exogenous group is present at the origin month.

## By Split And Horizon

| split | horizon | rows | sites | bloom rate | any nutrient | both nutrients | temperature | high | medium | low | season only |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `test` | 1 | 121,540 | 15,608 | 0.1377 | 0.3945 | 0.2070 | 0.2598 | 0.2171 | 0.1599 | 0.0745 | 0.5485 |
| `test` | 2 | 115,691 | 17,536 | 0.1449 | 0.3827 | 0.2095 | 0.2439 | 0.2056 | 0.1607 | 0.0678 | 0.5659 |
| `test` | 3 | 99,670 | 16,316 | 0.1469 | 0.3915 | 0.2263 | 0.2411 | 0.2061 | 0.1708 | 0.0605 | 0.5627 |
| `train` | 1 | 1,336,605 | 65,617 | 0.1583 | 0.1446 | 0.0325 | 0.1636 | 0.1125 | 0.0261 | 0.1671 | 0.6943 |
| `train` | 2 | 1,294,854 | 70,268 | 0.1591 | 0.1300 | 0.0295 | 0.1549 | 0.1034 | 0.0211 | 0.1672 | 0.7083 |
| `train` | 3 | 1,189,253 | 66,960 | 0.1598 | 0.1200 | 0.0264 | 0.1530 | 0.0978 | 0.0173 | 0.1751 | 0.7098 |
| `validation` | 1 | 163,110 | 19,348 | 0.1257 | 0.2770 | 0.1450 | 0.1872 | 0.1540 | 0.1132 | 0.0527 | 0.6800 |
| `validation` | 2 | 154,216 | 21,045 | 0.1277 | 0.2656 | 0.1451 | 0.1740 | 0.1443 | 0.1115 | 0.0495 | 0.6947 |
| `validation` | 3 | 136,038 | 20,202 | 0.1277 | 0.2683 | 0.1518 | 0.1680 | 0.1423 | 0.1168 | 0.0444 | 0.6965 |

## By Source

| source | split | horizon | rows | bloom rate | any nutrient | high | season only | forbidden Chl-a present |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `aquamatch_chla` | `test` | 1 | 66,226 | 0.1175 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| `aquamatch_chla` | `test` | 2 | 65,117 | 0.1196 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| `aquamatch_chla` | `test` | 3 | 55,831 | 0.1198 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| `aquamatch_chla` | `train` | 1 | 901,569 | 0.1371 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| `aquamatch_chla` | `train` | 2 | 892,319 | 0.1358 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| `aquamatch_chla` | `train` | 3 | 821,392 | 0.1353 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| `aquamatch_chla` | `validation` | 1 | 110,443 | 0.1121 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| `aquamatch_chla` | `validation` | 2 | 106,736 | 0.1125 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| `aquamatch_chla` | `validation` | 3 | 94,463 | 0.1106 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| `lakebed_us_cse` | `test` | 1 | 163 | 0.1350 | 0.3865 | 0.3865 | 0.1288 | 0.9571 |
| `lakebed_us_cse` | `test` | 2 | 151 | 0.1258 | 0.3974 | 0.3974 | 0.1258 | 0.9007 |
| `lakebed_us_cse` | `test` | 3 | 143 | 0.1189 | 0.4126 | 0.4126 | 0.1189 | 0.8531 |
| `lakebed_us_cse` | `train` | 1 | 2,760 | 0.1127 | 0.8848 | 0.8808 | 0.0011 | 0.9710 |
| `lakebed_us_cse` | `train` | 2 | 2,776 | 0.1099 | 0.8840 | 0.8829 | 0.0014 | 0.9640 |
| `lakebed_us_cse` | `train` | 3 | 2,768 | 0.1037 | 0.8801 | 0.8772 | 0.0011 | 0.9617 |
| `lakebed_us_cse` | `validation` | 1 | 445 | 0.1236 | 0.7416 | 0.7416 | 0.0022 | 0.9326 |
| `lakebed_us_cse` | `validation` | 2 | 430 | 0.1279 | 0.7395 | 0.7395 | 0.0023 | 0.9023 |
| `lakebed_us_cse` | `validation` | 3 | 421 | 0.1211 | 0.7387 | 0.7387 | 0.0000 | 0.8622 |
| `wqp` | `test` | 1 | 55,151 | 0.1620 | 0.8682 | 0.4772 | 0.0075 | 0.9292 |
| `wqp` | `test` | 2 | 50,423 | 0.1776 | 0.8770 | 0.4705 | 0.0066 | 0.9123 |
| `wqp` | `test` | 3 | 43,696 | 0.1815 | 0.8916 | 0.4687 | 0.0054 | 0.8957 |
| `wqp` | `train` | 1 | 432,276 | 0.2029 | 0.4413 | 0.3423 | 0.0613 | 0.9431 |
| `wqp` | `train` | 2 | 399,759 | 0.2115 | 0.4148 | 0.3288 | 0.0621 | 0.9302 |
| `wqp` | `train` | 3 | 365,093 | 0.2152 | 0.3843 | 0.3120 | 0.0624 | 0.9256 |
| `wqp` | `validation` | 1 | 52,222 | 0.1546 | 0.8589 | 0.4747 | 0.0091 | 0.9085 |
| `wqp` | `validation` | 2 | 47,050 | 0.1621 | 0.8638 | 0.4663 | 0.0083 | 0.8747 |
| `wqp` | `validation` | 3 | 41,154 | 0.1671 | 0.8793 | 0.4630 | 0.0068 | 0.8537 |

## Sequence Surface Check

| source | split | rows | mean evidence N | mean evidence F | mean evidence T no Chl-a | low nutrient evidence | changed IRC by Chl-a removal |
|---|---|---:|---:|---:|---:|---:|---:|
| `aquamatch_chla` | `test` | 66,226 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| `aquamatch_chla` | `train` | 901,569 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| `aquamatch_chla` | `validation` | 110,443 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| `lakebed_us_cse` | `test` | 254 | 0.4429 | 0.3972 | 0.9173 | 0.5433 | 0.5709 |
| `lakebed_us_cse` | `train` | 3,309 | 0.8241 | 0.4815 | 0.9909 | 0.1242 | 0.4956 |
| `lakebed_us_cse` | `validation` | 549 | 0.7300 | 0.4539 | 0.9945 | 0.2587 | 0.6284 |
| `wqp` | `test` | 86,478 | 0.4803 | 0.4826 | 0.6049 | 0.3363 | 0.5571 |
| `wqp` | `train` | 808,970 | 0.1675 | 0.4062 | 0.4551 | 0.7046 | 0.4708 |
| `wqp` | `validation` | 91,226 | 0.4625 | 0.4569 | 0.5325 | 0.3766 | 0.5006 |

## Interpretation Guardrails

- Low nutrient coverage is evidence about the available operational data surface, not evidence that nutrients are ecologically unimportant.
- Rows with current Chl-a present are still valid targets, but current Chl-a must remain excluded from operational predictors.
- Source-scoped targets do not assume that WQP nutrient rows and AquaMatch Chl-a rows refer to the same lake unless an accepted crosswalk is promoted later.

## Outputs

- `summary`: `reports/pipe_grud/no_current_chla/no_chla_operational_surface_audit_summary.csv`
- `by_source`: `reports/pipe_grud/no_current_chla/no_chla_operational_surface_audit_by_source_split_horizon.csv`
- `feature_coverage`: `reports/pipe_grud/no_current_chla/no_chla_operational_surface_audit_feature_coverage.csv`
- `sequence_coverage`: `reports/pipe_grud/no_current_chla/no_chla_operational_surface_audit_sequence_coverage.csv`
- `low_evidence_examples`: `reports/pipe_grud/no_current_chla/no_chla_operational_surface_audit_low_evidence_examples.csv`
- `report`: `reports/pipe_grud/no_current_chla/no_chla_operational_surface_audit_report.md`
