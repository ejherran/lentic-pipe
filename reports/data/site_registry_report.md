# Site Registry Report

Total source-scoped sites: `248,284`
Total canonical observations represented: `459,949,849`

## By Source

| source_id | sites | rows |
|---|---:|---:|
| `aquamatch_chla` | 141,544 | 3,393,022 |
| `lakebed_us_cse` | 21 | 432,748,526 |
| `wqp` | 106,719 | 23,808,301 |

## Notes

- `site_id` is source-scoped and does not imply cross-source equivalence.
- Cross-source merges must be declared later in `configs/site_resolution.yaml`.
- LakeBeD date ranges are left empty here because the registry is built from manifests to avoid scanning 432M rows.
