# Monthly Panel Report v0

Long panel rows: `7,420,800`
Wide panel rows: `3,386,676`

## By Source

| source_id | monthly variable rows | unique sites | panelable observations | ok observations | bad observations |
|---|---:|---:|---:|---:|---:|
| `aquamatch_chla` | 1,755,072 | 141,544 | 3,393,022 | 3,393,022 | 0 |
| `lakebed_us_cse` | 25,932 | 21 | 432,748,526 | 432,730,536 | 17,990 |
| `wqp` | 5,639,796 | 106,719 | 23,808,301 | 23,040,870 | 767,431 |

## Input Coverage

| source_id | canonical observations | panelable observations | excluded rows | excluded missing month | excluded missing variable |
|---|---:|---:|---:|---:|---:|
| `aquamatch_chla` | 3,393,022 | 3,393,022 | 0 | 0 | 0 |
| `lakebed_us_cse` | 432,748,526 | 432,748,526 | 0 | 0 | 0 |
| `wqp` | 23,808,301 | 23,808,301 | 0 | 0 | 0 |

## OK Observations By Variable

| variable | ok observations |
|---|---:|
| `DO_mgL` | 29,582,910 |
| `TN_ugL` | 416,147 |
| `TP_ugL` | 1,117,968 |
| `chlorophyll_a_ugL` | 7,255,350 |
| `pH` | 4,414,429 |
| `secchi_depth_m` | 2,081,981 |
| `temperature_C` | 413,354,257 |
| `turbidity_NTU` | 941,386 |

## Aggregation Policy

- Monthly values use `qc_flag == ok` and non-null `value_canonical`.
- Bad or unsupported observations are retained only as counts (`n_obs_bad`, `qc_ok_rate`).
- Observations without `year_month` are excluded from monthly aggregation and counted in Input Coverage.
- `value_mean`, `value_std`, `value_min`, and `value_max` are exact over OK observations.
- Exact monthly medians are intentionally not computed in v0 because high-frequency sources contain hundreds of millions of observations.
