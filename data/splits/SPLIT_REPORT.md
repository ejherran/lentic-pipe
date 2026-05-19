# Split Report v0

Generated at UTC: `2026-05-19T00:31:02.324495+00:00`
Target model rows input: `4,649,182`
Rows kept: `4,610,977`
Rows discarded: `38,205`
Leakage rows after filtering: `0`

## Freeze References

- Freeze manifest: `data/freeze/data_freeze_manifest_v0.json`
- Target model table: `data/targets/monthly_targets_model_v0.parquet`
- Target model SHA-256: `c93ee8dbf424828c8dc11bc5da236d5c505e5f6ba7478eb689cca12a88c7e799`
- Panel with targets SHA-256: `ccbfe6545f72bcfcbdc800fca6b02ce5d3e99c140adbb310f12313a4357395f2`

## Temporal Boundaries

| split | origin/target month rule |
|---|---|
| train | `<= 2018-12` |
| validation | `2019-01` through `2021-12` |
| test | `>= 2022-01` |

Rows are kept only when `origin_split == target_split`.

## Overall By Split And Horizon

| split | horizon | rows | sites | bloom positives | bloom negatives | bloom rate | origin range | target range |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `test` | 1 | 121,540 | 15,608 | 16,737 | 104,803 | 0.1377 | `2022-01..2026-03` | `2022-02..2026-04` |
| `test` | 2 | 115,691 | 17,536 | 16,765 | 98,926 | 0.1449 | `2022-01..2026-02` | `2022-03..2026-04` |
| `test` | 3 | 99,670 | 16,316 | 14,639 | 85,031 | 0.1469 | `2022-01..2025-11` | `2022-04..2026-02` |
| `train` | 1 | 1,336,605 | 65,617 | 211,603 | 1,125,002 | 0.1583 | `1970-01..2018-11` | `1970-02..2018-12` |
| `train` | 2 | 1,294,854 | 70,268 | 206,069 | 1,088,785 | 0.1591 | `1970-01..2018-10` | `1970-03..2018-12` |
| `train` | 3 | 1,189,253 | 66,960 | 189,990 | 999,263 | 0.1598 | `1970-01..2018-09` | `1970-04..2018-12` |
| `validation` | 1 | 163,110 | 19,348 | 20,506 | 142,604 | 0.1257 | `2019-01..2021-11` | `2019-02..2021-12` |
| `validation` | 2 | 154,216 | 21,045 | 19,697 | 134,519 | 0.1277 | `2019-01..2021-10` | `2019-03..2021-12` |
| `validation` | 3 | 136,038 | 20,202 | 17,377 | 118,661 | 0.1277 | `2019-01..2021-09` | `2019-04..2021-12` |

## By Source, Horizon, And Split

| source_id | horizon | split | rows | sites | bloom positives | bloom rate | origin range | target range |
|---|---:|---|---:|---:|---:|---:|---|---|
| `aquamatch_chla` | 1 | `test` | 66,226 | 8,829 | 7,782 | 0.1175 | `2022-01..2024-05` | `2022-02..2024-06` |
| `aquamatch_chla` | 1 | `train` | 901,569 | 43,288 | 123,570 | 0.1371 | `1970-01..2018-11` | `1970-02..2018-12` |
| `aquamatch_chla` | 1 | `validation` | 110,443 | 12,420 | 12,376 | 0.1121 | `2019-01..2021-11` | `2019-02..2021-12` |
| `aquamatch_chla` | 2 | `test` | 65,117 | 10,261 | 7,790 | 0.1196 | `2022-01..2024-04` | `2022-03..2024-06` |
| `aquamatch_chla` | 2 | `train` | 892,319 | 46,508 | 121,212 | 0.1358 | `1970-01..2018-10` | `1970-03..2018-12` |
| `aquamatch_chla` | 2 | `validation` | 106,736 | 13,687 | 12,013 | 0.1125 | `2019-01..2021-10` | `2019-03..2021-12` |
| `aquamatch_chla` | 3 | `test` | 55,831 | 9,332 | 6,689 | 0.1198 | `2022-01..2024-03` | `2022-04..2024-06` |
| `aquamatch_chla` | 3 | `train` | 821,392 | 43,855 | 111,147 | 0.1353 | `1970-01..2018-09` | `1970-04..2018-12` |
| `aquamatch_chla` | 3 | `validation` | 94,463 | 12,937 | 10,450 | 0.1106 | `2019-01..2021-09` | `2019-04..2021-12` |
| `lakebed_us_cse` | 1 | `test` | 163 | 14 | 22 | 0.1350 | `2022-01..2023-11` | `2022-02..2023-12` |
| `lakebed_us_cse` | 1 | `train` | 2,760 | 21 | 311 | 0.1127 | `1981-06..2018-11` | `1981-07..2018-12` |
| `lakebed_us_cse` | 1 | `validation` | 445 | 21 | 55 | 0.1236 | `2019-01..2021-11` | `2019-02..2021-12` |
| `lakebed_us_cse` | 2 | `test` | 151 | 14 | 19 | 0.1258 | `2022-01..2023-10` | `2022-03..2023-12` |
| `lakebed_us_cse` | 2 | `train` | 2,776 | 21 | 305 | 0.1099 | `1981-05..2018-10` | `1981-07..2018-12` |
| `lakebed_us_cse` | 2 | `validation` | 430 | 21 | 55 | 0.1279 | `2019-01..2021-10` | `2019-03..2021-12` |
| `lakebed_us_cse` | 3 | `test` | 143 | 14 | 17 | 0.1189 | `2022-01..2023-09` | `2022-04..2023-12` |
| `lakebed_us_cse` | 3 | `train` | 2,768 | 21 | 287 | 0.1037 | `1981-04..2018-09` | `1981-07..2018-12` |
| `lakebed_us_cse` | 3 | `validation` | 421 | 21 | 51 | 0.1211 | `2019-01..2021-09` | `2019-04..2021-12` |
| `wqp` | 1 | `test` | 55,151 | 6,765 | 8,933 | 0.1620 | `2022-01..2026-03` | `2022-02..2026-04` |
| `wqp` | 1 | `train` | 432,276 | 22,308 | 87,722 | 0.2029 | `1970-03..2018-11` | `1970-04..2018-12` |
| `wqp` | 1 | `validation` | 52,222 | 6,907 | 8,075 | 0.1546 | `2019-01..2021-11` | `2019-02..2021-12` |
| `wqp` | 2 | `test` | 50,423 | 7,261 | 8,956 | 0.1776 | `2022-01..2026-02` | `2022-03..2026-04` |
| `wqp` | 2 | `train` | 399,759 | 23,739 | 84,552 | 0.2115 | `1970-02..2018-10` | `1970-04..2018-12` |
| `wqp` | 2 | `validation` | 47,050 | 7,337 | 7,629 | 0.1621 | `2019-01..2021-10` | `2019-03..2021-12` |
| `wqp` | 3 | `test` | 43,696 | 6,970 | 7,933 | 0.1815 | `2022-01..2025-11` | `2022-04..2026-02` |
| `wqp` | 3 | `train` | 365,093 | 23,084 | 78,556 | 0.2152 | `1970-04..2018-09` | `1970-07..2018-12` |
| `wqp` | 3 | `validation` | 41,154 | 7,244 | 6,876 | 0.1671 | `2019-01..2021-09` | `2019-04..2021-12` |

## Discarded Rows

| source_id | horizon | reason | rows | bloom positives |
|---|---:|---|---:|---:|
| `aquamatch_chla` | 1 | `crosses_split_boundary` | 4,627 | 331 |
| `aquamatch_chla` | 2 | `crosses_split_boundary` | 9,698 | 653 |
| `aquamatch_chla` | 3 | `crosses_split_boundary` | 15,012 | 945 |
| `lakebed_us_cse` | 1 | `crosses_split_boundary` | 9 | 2 |
| `lakebed_us_cse` | 2 | `crosses_split_boundary` | 25 | 4 |
| `lakebed_us_cse` | 3 | `crosses_split_boundary` | 41 | 6 |
| `wqp` | 1 | `crosses_split_boundary` | 1,500 | 234 |
| `wqp` | 2 | `crosses_split_boundary` | 2,842 | 406 |
| `wqp` | 3 | `crosses_split_boundary` | 4,451 | 545 |

## Outputs

- Kept split rows: `data/splits/monthly_model_splits_v0.parquet`
- Discarded rows: `data/splits/monthly_model_splits_discarded_v0.parquet`
- Summary CSV: `data/splits/split_summary_by_source_horizon_v0.csv`
- Manifest: `data/splits/split_manifest.json`
