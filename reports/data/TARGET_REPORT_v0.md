# Target Report v0

Panel input rows: `3,390,728`
Target candidate rows: `10,172,184`
Rows with available Chl-a target: `4,649,182`

## By Horizon

| horizon_months | candidate rows | target month rows | target rows | missing target month | missing Chl-a in target month | bloom positives | bloom negatives | bloom rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3,390,728 | 2,075,709 | 1,627,391 | 1,315,019 | 448,318 | 249,413 | 1,377,978 | 0.1533 |
| 2 | 3,390,728 | 1,947,257 | 1,577,326 | 1,443,471 | 369,931 | 243,594 | 1,333,732 | 0.1544 |
| 3 | 3,390,728 | 1,729,279 | 1,444,465 | 1,661,449 | 284,814 | 223,502 | 1,220,963 | 0.1547 |

## By Source And Horizon

| source_id | horizon_months | target rows | sites with target | bloom positives | bloom rate | missing target month | missing Chl-a in target month |
|---|---:|---:|---:|---:|---:|---:|---:|
| `aquamatch_chla` | 1 | 1,082,865 | 49,459 | 144,059 | 0.1330 | 672,207 | 0 |
| `aquamatch_chla` | 2 | 1,073,870 | 53,305 | 141,668 | 0.1319 | 681,202 | 0 |
| `aquamatch_chla` | 3 | 986,698 | 50,214 | 129,231 | 0.1310 | 768,374 | 0 |
| `lakebed_us_cse` | 1 | 3,377 | 21 | 390 | 0.1155 | 801 | 754 |
| `lakebed_us_cse` | 2 | 3,382 | 21 | 383 | 0.1132 | 841 | 709 |
| `lakebed_us_cse` | 3 | 3,373 | 21 | 361 | 0.1070 | 870 | 689 |
| `nla` | 1 | 0 | 0 | 0 | NA | 4,052 | 0 |
| `nla` | 2 | 0 | 0 | 0 | NA | 4,052 | 0 |
| `nla` | 3 | 0 | 0 | 0 | NA | 4,052 | 0 |
| `wqp` | 1 | 541,149 | 26,201 | 104,964 | 0.1940 | 637,959 | 447,564 |
| `wqp` | 2 | 500,074 | 27,997 | 101,543 | 0.2031 | 757,376 | 369,222 |
| `wqp` | 3 | 454,394 | 26,999 | 93,910 | 0.2067 | 888,153 | 284,125 |

## Future Chl-a Distribution

| horizon_months | count | mean | median | p95 | max |
|---:|---:|---:|---:|---:|---:|
| 1 | 1,627,391 | 18.7967 | 6.9500 | 72.0000 | 10,000.0000 |
| 2 | 1,577,326 | 18.7824 | 6.9500 | 72.0000 | 10,000.0000 |
| 3 | 1,444,465 | 18.7760 | 7.0000 | 71.6080 | 9,900.0000 |

## Target Policy

- Horizons are exact calendar-month offsets: `1, 2, 3`.
- Targets are source-scoped by `source_id` and `site_id`; no cross-source site merge is assumed.
- `bloom_h = 1` when future monthly mean Chl-a is greater than `30 ug/L`.
- Continuous risk uses the project log normalization with epsilon `0.1`, low reference `5 ug/L`, and bloom reference `30 ug/L`.
- `target_trophic_state_h` is a crisp Chl-a proxy in v0: oligotrophic `<2.6`, mesotrophic `<7.3`, eutrophic `<56`, hypereutrophic `>=56` ug/L.
- The final fuzzy trophic state remains a later ANFIS/Mamdani output; this v0 target is only a supervised proxy.

## Outputs

- `data/targets/monthly_targets_long_v0.parquet`: all origin-month by horizon candidates, including missing targets.
- `data/targets/monthly_targets_model_v0.parquet`: only rows with available future Chl-a target.
- `data/targets/panel_monthly_with_targets_v0.parquet`: monthly panel with h1/h2/h3 target columns attached.
- `data/targets/target_manifest_v0.json`: machine-readable target build manifest.
