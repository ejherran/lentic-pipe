# PIPE Sequence Dataset v0

Generated at UTC: `2026-06-15T16:39:41.148446+00:00`
Started at UTC: `2026-06-15T16:39:25.796427+00:00`

## Scope

This step builds a leakage-safe adjacent-month `S(t) -> S(t+1)` dataset for PIPE/GRU-D.
It does not train or tune a temporal model.
Input surface: `adaptive`.
Source filter: `wqp`.
Maximum allowed target gap: `1` month(s).
Input dimensionality for the minimal PIPE model: `13` = 9 state values + 4 seasonal values.

Adaptive mode reads trained ANFIS state columns and emits the same canonical PIPE feature
and target names used by the expert-state temporal model. This keeps downstream PIPE/GRU-D
scripts comparable while preserving the source-column mapping in the manifest.

| canonical target | state source |
|---|---|
| `yN` | `yN_adaptive` |
| `yF` | `yF_adaptive` |
| `yT` | `yT_adaptive` |
| `sigma_N` | `sigma_N_adaptive` |
| `sigma_F` | `sigma_F_adaptive` |
| `sigma_T` | `sigma_T_adaptive` |
| `delta_yN` | `delta_yN_adaptive` |
| `delta_yF` | `delta_yF_adaptive` |
| `delta_yT` | `delta_yT_adaptive` |

## Row Counts

- Candidate state rows: `1,626,672`
- Kept sequence rows: `986,674`
- Discarded candidate rows: `639,998`
- Source-scoped sites kept: `43,715`

## By Split

| split | rows | sites | origin range | target range |
|---|---:|---:|---|---|
| `test` | 86,478 | 10,366 | `2022-01..2026-04` | `2022-02..2026-05` |
| `train` | 808,970 | 38,508 | `1970-01..2018-11` | `1970-02..2018-12` |
| `validation` | 91,226 | 11,283 | `2019-01..2021-11` | `2019-02..2021-12` |

## By Source And Split

| source | split | rows | sites | origin range | target range | mean gap | max gap |
|---|---|---:|---:|---|---|---:|---:|
| `wqp` | `test` | 86,478 | 10,366 | `2022-01..2026-04` | `2022-02..2026-05` | 1.0000 | 1 |
| `wqp` | `train` | 808,970 | 38,508 | `1970-01..2018-11` | `1970-02..2018-12` | 1.0000 | 1 |
| `wqp` | `validation` | 91,226 | 11,283 | `2019-01..2021-11` | `2019-02..2021-12` | 1.0000 | 1 |

## Discarded

| source | reason | rows | sites |
|---|---|---:|---:|
| `wqp` | `crosses_split_boundary` | 24,745 | 16,536 |
| `wqp` | `gap_too_large` | 508,534 | 63,466 |
| `wqp` | `no_next_state` | 106,719 | 106,719 |

## Outputs

- Sequence dataset: `data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet`
- Summary: `reports/pipe_grud/adaptive_wqp_focused/pipe_sequence_summary.csv`
- Discarded summary: `reports/pipe_grud/adaptive_wqp_focused/pipe_sequence_discarded_summary.csv`
- Manifest: `reports/pipe_grud/adaptive_wqp_focused/pipe_sequence_manifest.json`
