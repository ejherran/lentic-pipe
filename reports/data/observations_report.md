# Canonical Observations Report

Sources: `3`
Total canonical observations: `459,949,849`

## Source Summary

| source_id | status | chunks | rows | output_dir |
|---|---|---:|---:|---|
| `aquamatch_chla` | completed | 15 | 3,393,022 | `data/interim/observations/aquamatch_chla` |
| `lakebed_us_cse` | completed | 489 | 432,748,526 | `data/interim/observations/lakebed_us_cse` |
| `wqp` | completed | 238 | 23,808,301 | `data/interim/observations/wqp` |

## Variable Counts

### aquamatch_chla

| variable_canonical | rows |
|---|---:|
| `chlorophyll_a_ugL` | 3,393,022 |

### lakebed_us_cse

| variable_canonical | rows |
|---|---:|
| `DO_mgL` | 24,110,502 |
| `TN_ugL` | 17,821 |
| `TP_ugL` | 21,074 |
| `chlorophyll_a_ugL` | 1,880,447 |
| `secchi_depth_m` | 7,743 |
| `temperature_C` | 406,710,939 |

### wqp

| variable_canonical | rows |
|---|---:|
| `DO_mgL` | 5,576,205 |
| `TN_ugL` | 449,615 |
| `TP_ugL` | 1,203,710 |
| `chlorophyll_a_ugL` | 2,188,154 |
| `pH` | 4,544,701 |
| `secchi_depth_m` | 2,124,283 |
| `temperature_C` | 6,675,107 |
| `turbidity_NTU` | 1,046,526 |

## Integrity Note

This report is derived from per-source `_manifest.json` files generated during canonicalization. Use `src/data/summarize_observations.py --scan` to verify physical parquet row counts against manifests.
