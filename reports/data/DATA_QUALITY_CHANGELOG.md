# Data Quality Changelog

## 2026-05-16 - WQP Date Parsing And Blank pH Units

### Scope

This entry documents a data-quality correction applied after rebuilding the WQP canonical observations and the monthly panel v0.

Affected files:

- `src/data/adapters/wqp_streaming.py`
- `src/data/adapters/common.py`
- `data/interim/observations/wqp/`
- `data/panel/monthly_long_v0.parquet`
- `data/panel/panel_monthly_v0.parquet`
- `reports/data/PANEL_REPORT_v0.md`

Raw WQP reference files remain unchanged. The relevant raw fingerprints are recorded in `reports/data/source_inventory.md`, including:

| raw file | sha256 |
|---|---|
| `data/raw/wqp/wqp_results.csv` | `58829372d440f6a3f15bc55b88346af2429747f96e2c9572194d2f9eb7dde904` |
| `data/raw/wqp/wqp_activity.csv` | `c34e206954c50be2577510d03f60f838e73ecdb47c07be46c1e70fba418546ff` |
| `data/raw/wqp/wqp_stations.csv` | `c6af182de050628a12a029ece427771c06f69e4b0b56298e7ae76cb5357b60a9` |

### Issue 1: Mixed WQP Date Formats

WQP `Activity_StartDate` and `Activity_StartTime` can appear as both date-only and date-time strings within the same chunk:

```text
1970-05-09 12:45:00
1970-01-01
1970-04-14
```

The previous parser used `pd.to_datetime(..., errors="coerce", utc=True)` on the mixed series. With current pandas behavior, format inference could parse the date-time values while coercing valid date-only rows to `NaT`.

Correction:

```python
pd.to_datetime(combined, errors="coerce", utc=True, format="mixed")
```

Current verification:

| metric | value |
|---|---:|
| WQP canonical rows | 23,808,301 |
| WQP rows missing `sample_datetime` | 0 |
| WQP rows missing `year_month` | 0 |
| WQP panelable rows | 23,808,301 |
| WQP excluded missing month rows | 0 |

### Issue 2: Blank pH Units

WQP contains many `pH` records with an empty raw unit. Because pH is dimensionless, an empty unit is accepted only for canonical variable `pH`.

Correction policy:

- `pH` + blank unit is converted with identity.
- The conversion trace is not plain `identity`; it is recorded as `assume_blank_unit_dimensionless`.
- The value must still pass the configured plausible range `0 <= pH <= 14`.
- Blank units for non-pH variables remain unsupported.

Current verification:

| metric | value |
|---|---:|
| WQP blank-unit pH accepted as OK | 3,726,056 |
| WQP blank-unit pH still bad | 60,147 |
| WQP blank-unit pH outside plausible range | 42,690 |
| WQP blank-unit pH non-numeric or missing | 17,457 |
| WQP non-pH blank-unit unsupported rows | 16,686 |

### Current WQP QC State

After rebuilding WQP canonical observations:

| metric | value |
|---|---:|
| WQP canonical rows | 23,808,301 |
| WQP OK observations | 23,040,870 |
| WQP bad observations | 767,431 |

Top QC flags from the post-correction scan:

| qc_flag | rows |
|---|---:|
| `ok` | 23,040,870 |
| `non_numeric_or_missing` | 308,215 |
| `unsupported_unit:RFU` | 59,362 |
| `outside_plausible_range` | 58,470 |
| `unsupported_unit:mV` | 53,985 |
| `unsupported_unit:volts` | 50,266 |
| `unsupported_unit:%` | 38,287 |
| `impossible_negative` | 32,892 |
| `unsupported_unit:cm` | 31,251 |
| `unsupported_unit:NTRU` | 30,861 |

### Current Monthly Panel State

After rebuilding the monthly panel v0:

| output | rows |
|---|---:|
| `data/panel/monthly_long_v0.parquet` | 7,420,800 |
| `data/panel/panel_monthly_v0.parquet` | 3,386,676 |

Input coverage is complete:

| source_id | canonical observations | panelable observations | excluded rows |
|---|---:|---:|---:|
| `aquamatch_chla` | 3,393,022 | 3,393,022 | 0 |
| `lakebed_us_cse` | 432,748,526 | 432,748,526 | 0 |
| `wqp` | 23,808,301 | 23,808,301 | 0 |

### Commands Used For Verification

```bash
.venv/bin/python src/data/summarize_observations.py \
  --source wqp \
  --scan

.venv/bin/python -c "import pyarrow.dataset as ds; d=ds.dataset('data/interim/observations/wqp', format='parquet', ignore_prefixes=['_','.']); print('missing_year_month', d.count_rows(filter=ds.field('year_month').is_null())); print('missing_sample_datetime', d.count_rows(filter=ds.field('sample_datetime').is_null())); print('blank_pH_ok', d.count_rows(filter=(ds.field('variable_canonical') == 'pH') & ds.field('unit_raw').is_null() & (ds.field('qc_flag') == 'ok')))"

sed -n '1,220p' reports/data/PANEL_REPORT_v0.md
```

### Downstream Implication

This correction must be considered part of the data preparation baseline before target construction, data freeze, splits, and any model training. Baselines, PIPE, or MIFAL runs based on the previous WQP canonical outputs should be treated as invalidated and regenerated.
