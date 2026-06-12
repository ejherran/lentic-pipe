# PIPE Sequence Dataset v0

Generated at UTC: `2026-06-12T18:40:56.901829+00:00`
Started at UTC: `2026-06-12T18:40:24.347378+00:00`

## Scope

This step builds a leakage-safe adjacent-month `S(t) -> S(t+1)` dataset for PIPE/GRU-D.
It does not train or tune a temporal model.
Input surface: `no_current_chla`.
Maximum allowed target gap: `1` month(s).
Input dimensionality for the minimal PIPE model: `13` = 9 state values + 4 seasonal values.

No-current-Chl-a mode replaces current thermal/biological input channels with no-Chl-a fuzzy variants:

| input channel | state source |
|---|---|
| `x_yT` | `yT_no_chla` |
| `x_sigma_T` | `sigma_T_no_chla` |
| `x_delta_yT` | `delta_yT_no_chla` |

Targets remain the full next-month fuzzy state, so observed future Chl-a-derived state can still be evaluated.

## Row Counts

- Candidate state rows: `3,386,676`
- Kept sequence rows: `2,069,024`
- Discarded candidate rows: `1,317,652`
- Source-scoped sites kept: `93,168`

## By Split

| split | rows | sites | origin range | target range |
|---|---:|---:|---|---|
| `test` | 152,958 | 19,216 | `2022-01..2026-04` | `2022-02..2026-05` |
| `train` | 1,713,848 | 81,817 | `1970-01..2018-11` | `1970-02..2018-12` |
| `validation` | 202,218 | 23,724 | `2019-01..2021-11` | `2019-02..2021-12` |

## By Source And Split

| source | split | rows | sites | origin range | target range | mean gap | max gap |
|---|---|---:|---:|---|---|---:|---:|
| `aquamatch_chla` | `test` | 66,226 | 8,829 | `2022-01..2024-05` | `2022-02..2024-06` | 1.0000 | 1 |
| `aquamatch_chla` | `train` | 901,569 | 43,288 | `1970-01..2018-11` | `1970-02..2018-12` | 1.0000 | 1 |
| `aquamatch_chla` | `validation` | 110,443 | 12,420 | `2019-01..2021-11` | `2019-02..2021-12` | 1.0000 | 1 |
| `lakebed_us_cse` | `test` | 254 | 21 | `2022-01..2024-03` | `2022-02..2024-04` | 1.0000 | 1 |
| `lakebed_us_cse` | `train` | 3,309 | 21 | `1981-04..2018-11` | `1981-05..2018-12` | 1.0000 | 1 |
| `lakebed_us_cse` | `validation` | 549 | 21 | `2019-01..2021-11` | `2019-02..2021-12` | 1.0000 | 1 |
| `wqp` | `test` | 86,478 | 10,366 | `2022-01..2026-04` | `2022-02..2026-05` | 1.0000 | 1 |
| `wqp` | `train` | 808,970 | 38,508 | `1970-01..2018-11` | `1970-02..2018-12` | 1.0000 | 1 |
| `wqp` | `validation` | 91,226 | 11,283 | `2019-01..2021-11` | `2019-02..2021-12` | 1.0000 | 1 |

## Discarded

| source | reason | rows | sites |
|---|---|---:|---:|
| `aquamatch_chla` | `crosses_split_boundary` | 26,142 | 17,569 |
| `aquamatch_chla` | `gap_too_large` | 509,148 | 60,610 |
| `aquamatch_chla` | `no_next_state` | 141,544 | 141,544 |
| `lakebed_us_cse` | `crosses_split_boundary` | 42 | 21 |
| `lakebed_us_cse` | `gap_too_large` | 757 | 21 |
| `lakebed_us_cse` | `no_next_state` | 21 | 21 |
| `wqp` | `crosses_split_boundary` | 24,745 | 16,536 |
| `wqp` | `gap_too_large` | 508,534 | 63,466 |
| `wqp` | `no_next_state` | 106,719 | 106,719 |

## Outputs

- Sequence dataset: `data/pipe_grud/pipe_sequence_dataset_no_current_chla_v0.parquet`
- Summary: `reports/pipe_grud/no_current_chla/pipe_sequence_summary.csv`
- Discarded summary: `reports/pipe_grud/no_current_chla/pipe_sequence_discarded_summary.csv`
- Manifest: `reports/pipe_grud/no_current_chla/pipe_sequence_manifest.json`
