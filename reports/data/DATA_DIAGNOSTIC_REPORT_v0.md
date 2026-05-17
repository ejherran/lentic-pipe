# Data Diagnostic Report v0

Panel rows: `3,386,676`
Target candidate rows: `10,160,028`
Rows with target: `4,649,182`
Bloom positives across all horizons: `716,509`

## Source Coverage

| source_id | site-month rows | sites | start | end |
|---|---:|---:|---|---|
| `aquamatch_chla` | 1,755,072 | 141,544 | `1970-01` | `2024-06` |
| `lakebed_us_cse` | 4,932 | 21 | `1981-04` | `2024-04` |
| `wqp` | 1,626,672 | 106,719 | `1970-01` | `2026-05` |

## Variable Coverage

| variable | months with value | coverage rate | sites with value | OK observations | bad observations | mean monthly QC OK rate |
|---|---:|---:|---:|---:|---:|---:|
| `DO_mgL` | 706,059 | 0.2085 | 58,858 | 29,582,910 | 103,797 | 0.9970 |
| `TN_ugL` | 237,568 | 0.0701 | 21,188 | 416,147 | 51,289 | 0.9878 |
| `TP_ugL` | 584,659 | 0.1726 | 45,835 | 1,117,968 | 106,816 | 0.9837 |
| `chlorophyll_a_ugL` | 2,599,588 | 0.7676 | 193,068 | 7,255,350 | 206,273 | 0.9971 |
| `pH` | 688,852 | 0.2034 | 64,956 | 4,414,429 | 130,272 | 0.9954 |
| `secchi_depth_m` | 1,213,390 | 0.3583 | 70,080 | 2,081,981 | 50,045 | 0.9996 |
| `temperature_C` | 853,189 | 0.2519 | 70,026 | 413,354,257 | 31,789 | 0.9994 |
| `turbidity_NTU` | 371,850 | 0.1098 | 32,944 | 941,386 | 105,140 | 0.9940 |

## Target Coverage By Source And Horizon

| source_id | horizon | target rows | target coverage rate | bloom positives | bloom rate | missing target month | missing Chl-a in target month |
|---|---:|---:|---:|---:|---:|---:|---:|
| `aquamatch_chla` | 1 | 1,082,865 | 0.6170 | 144,059 | 0.1330 | 672,207 | 0 |
| `aquamatch_chla` | 2 | 1,073,870 | 0.6119 | 141,668 | 0.1319 | 681,202 | 0 |
| `aquamatch_chla` | 3 | 986,698 | 0.5622 | 129,231 | 0.1310 | 768,374 | 0 |
| `lakebed_us_cse` | 1 | 3,377 | 0.6847 | 390 | 0.1155 | 801 | 754 |
| `lakebed_us_cse` | 2 | 3,382 | 0.6857 | 383 | 0.1132 | 841 | 709 |
| `lakebed_us_cse` | 3 | 3,373 | 0.6839 | 361 | 0.1070 | 870 | 689 |
| `wqp` | 1 | 541,149 | 0.3327 | 104,964 | 0.1940 | 637,959 | 447,564 |
| `wqp` | 2 | 500,074 | 0.3074 | 101,543 | 0.2031 | 757,376 | 369,222 |
| `wqp` | 3 | 454,394 | 0.2793 | 93,910 | 0.2067 | 888,153 | 284,125 |

## Bloom Site Counts

| horizon | sites with target | sites with >=1 bloom | sites with 0 blooms |
|---:|---:|---:|---:|
| 1 | 75,681 | 28,061 | 47,620 |
| 2 | 81,323 | 29,362 | 51,961 |
| 3 | 77,234 | 28,020 | 49,214 |

## Future Chl-a By Source And Horizon

| source_id | horizon | count | mean | median | p05 | p95 | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| `aquamatch_chla` | 1 | 1,082,865 | 16.2507 | 6.2105 | 0.8000 | 64.0000 | 1,000.0000 |
| `aquamatch_chla` | 2 | 1,073,870 | 16.0561 | 6.0750 | 0.7300 | 63.0000 | 1,000.0000 |
| `aquamatch_chla` | 3 | 986,698 | 15.9704 | 6.0800 | 0.7500 | 62.5000 | 1,000.0000 |
| `lakebed_us_cse` | 1 | 3,377 | 14.5457 | 5.6437 | 0.9841 | 57.8800 | 508.6255 |
| `lakebed_us_cse` | 2 | 3,382 | 14.2683 | 5.6061 | 1.0000 | 57.5117 | 361.7833 |
| `lakebed_us_cse` | 3 | 3,373 | 13.7406 | 5.5000 | 0.8170 | 53.9680 | 361.7833 |
| `wqp` | 1 | 541,149 | 23.9179 | 8.0000 | 1.0667 | 87.0000 | 10,000.0000 |
| `wqp` | 2 | 500,074 | 24.6674 | 8.6000 | 1.0500 | 89.0000 | 10,000.0000 |
| `wqp` | 3 | 454,394 | 24.9054 | 9.0000 | 1.0400 | 89.0000 | 9,900.0000 |

## Absence Interpretation

- Missing target month means the source-site has no row at the future calendar month.
- Missing Chl-a in target month means the source-site-month exists, but no OK Chl-a monthly mean is available.
- These missingness classes are operational/data-coverage missingness. They should be treated as MAR/MNAR risk until split-level diagnostics are complete; do not assume MCAR.
- Targets are source-scoped; cross-source site equivalence is not assumed.

## Figures

- `variable_coverage`: `reports/data/figures/variable_coverage.svg`
- `source_variable_coverage`: `reports/data/figures/source_variable_coverage.svg`
- `target_coverage`: `reports/data/figures/target_coverage_by_source_horizon.svg`
- `future_chla_p95`: `reports/data/figures/future_chla_p95_by_source_horizon.svg`

## Output Tables

- `coverage_by_source`: `data/diagnostics/coverage_by_source.csv`
- `coverage_by_site`: `data/diagnostics/coverage_by_site.csv`
- `coverage_by_variable`: `data/diagnostics/coverage_by_variable.csv`
- `coverage_by_site_variable`: `data/diagnostics/coverage_by_site_variable.csv`
- `coverage_by_source_variable`: `data/diagnostics/coverage_by_source_variable.csv`
- `bloom_counts_by_site_horizon`: `data/diagnostics/bloom_counts_by_site_horizon.csv`
- `target_coverage_by_source_horizon`: `data/diagnostics/target_coverage_by_source_horizon.csv`
- `feature_missingness`: `data/diagnostics/feature_missingness.csv`
- `chla_distribution_by_source_horizon`: `data/diagnostics/chla_distribution_by_source_horizon.csv`
