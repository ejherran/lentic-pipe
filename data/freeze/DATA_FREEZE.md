# DATA_FREEZE v0

Generated at UTC: `2026-05-18T14:41:22.026802+00:00`
Repository commit: `e38be702e2cf10fe1f8341895a96863a108dfb9f`
Worktree status: `M data/catalog/raw_file_manifest.csv
 M data/catalog/source_catalog.json
 M data/freeze/DATA_FREEZE.md
 M data/freeze/data_freeze_manifest_v0.json
 M data/freeze/derived_file_manifest_v0.csv
 M reports/data/source_inventory.md`
Python constraint: `>=3.14,<3.15`

## Scope

This freeze captures the current raw fingerprints, canonical observations, monthly panel, target tables, and diagnostics used before temporal splits and baselines.

Downstream experiments must reference this freeze. If raw files, canonicalization logic, panel logic, target logic, or diagnostics change, regenerate this freeze before trusting new results.

## Raw Sources

Raw manifest: `data/catalog/raw_file_manifest.csv`
Raw source catalog: `data/catalog/source_catalog.json`
Raw files: `76`
Raw total size: `58.3 GB`

| source_id | files | size | license | provenance_status | raw_path |
|---|---:|---:|---|---|---|
| `aquamatch_chla` | 4 | 777.7 MB | cc0-1.0 | documented | `data/raw/aquamatch/chla_harmonized_final.csv` |
| `lakebed_us_cse` | 66 | 1.1 GB | cc-by-4.0 | documented | `data/raw/LakeBeD-US-CSE` |
| `wqp` | 6 | 56.5 GB | public_download_multi_provider_with_terms_and_disclaimer | documented_terms_reviewed_conservative_private_mirror | `data/raw/wqp` |

## Canonical Observations

| source_id | adapter | status | chunks | rows | output_dir |
|---|---|---|---:|---:|---|
| `aquamatch_chla` | `aquamatch_chla` | completed | 15 | 3,393,022 | `data/interim/observations/aquamatch_chla` |
| `lakebed_us_cse` | `lakebed_us_cse` | completed | 489 | 432,748,526 | `data/interim/observations/lakebed_us_cse` |
| `wqp` | `wqp_streaming` | completed | 238 | 23,808,301 | `data/interim/observations/wqp` |

## Source-Site-Month Coverage

| source_id | site-month rows | sites | start | end |
|---|---:|---:|---|---|
| `aquamatch_chla` | 1,755,072 | 141,544 | `1970-01` | `2024-06` |
| `lakebed_us_cse` | 4,932 | 21 | `1981-04` | `2024-04` |
| `wqp` | 1,626,672 | 106,719 | `1970-01` | `2026-05` |

## Panel And Targets

| artifact | rows | path |
|---|---:|---|
| monthly long panel | 7,420,800 | `data/panel/monthly_long_v0.parquet` |
| monthly wide panel | 3,386,676 | `data/panel/panel_monthly_v0.parquet` |
| target candidates | 10,160,028 | `data/targets/monthly_targets_long_v0.parquet` |
| model targets | 4,649,182 | `data/targets/monthly_targets_model_v0.parquet` |
| panel with targets | 3,386,676 | `data/targets/panel_monthly_with_targets_v0.parquet` |

## Target Policy

- Horizons: `[1, 2, 3]` months.
- Bloom threshold: `30.0 ug/L`.
- Risk policy: `{'epsilon': 0.1, 'low_chla_ugL': 5.0, 'bloom_chla_ugL': 30.0}`.
- Trophic state proxy: `{'oligotrophic_max': 2.6, 'mesotrophic_max': 7.3, 'eutrophic_max': 56.0}`.
- Targets are source-scoped by `source_id` and `site_id`; no cross-source site equivalence is assumed.

## Diagnostics

Diagnostic report: `reports/data/DATA_DIAGNOSTIC_REPORT_v0.md`
Rows with target: `4,649,182`
Bloom-positive target rows across all horizons: `716,509`

## Derived Artifact Hashes

Derived manifest: `data/freeze/derived_file_manifest_v0.csv`

| category | files | size |
|---|---:|---:|
| `canonical_observations` | 747 | 5.8 GB |
| `catalog` | 2 | 56.3 KB |
| `config` | 3 | 21.8 KB |
| `diagnostics` | 10 | 270.5 MB |
| `documentation` | 7 | 17.1 KB |
| `environment` | 4 | 437.5 KB |
| `interim` | 2 | 48.5 MB |
| `panel` | 3 | 184.3 MB |
| `repo_audit` | 1 | 3.9 KB |
| `repo_script` | 5 | 18.2 KB |
| `reports` | 11 | 36.2 KB |
| `script` | 18 | 184.4 KB |
| `source_download_script` | 6 | 16.2 KB |
| `targets` | 4 | 238.0 MB |

### Key Derived SHA-256

| path | sha256 |
|---|---|
| `data/panel/monthly_long_v0.parquet` | `80fd83aa10ffe4028e344c8e9b31822d1241e7a0da9e0a9e727fecda3a0cff76` |
| `data/panel/panel_monthly_v0.parquet` | `03cc633578cc1b842a6646ab77209aa5ced7c0fc48e2c24fc5a9debc25c8e883` |
| `data/targets/monthly_targets_long_v0.parquet` | `3ffa54d57e6cf8dfbefa56a55a10c9cc0fe19a979c91bb04306f2d2b444e7450` |
| `data/targets/monthly_targets_model_v0.parquet` | `49815a11fc3fe70c292e4aa011ac1617ba4865aca718371055f44b3d9569437e` |
| `data/targets/panel_monthly_with_targets_v0.parquet` | `651e7c6fb3d1d800dbd910b0170f4730b8e926fc068f545e115ee60b4992caab` |
| `data/diagnostics/diagnostic_manifest_v0.json` | `a62c68676905037d9dfee68adff451d74eb8cb7347bb24c9b48c58e032e2b0f0` |

## Exact Generation Commands

```bash
.venv/bin/python src/data/validate_sources.py
.venv/bin/python src/data/raw_manifest.py --reuse-existing
.venv/bin/python src/data/build_observations.py --source lakebed_us_cse --chunksize 250000 --overwrite
.venv/bin/python src/data/build_observations.py --source aquamatch_chla --chunksize 250000 --overwrite
.venv/bin/python src/data/build_observations.py --source wqp --chunksize 250000 --overwrite
.venv/bin/python src/data/report_observations.py
.venv/bin/python src/data/site_registry.py
.venv/bin/python src/data/build_panel.py --overwrite --progress-every-parts 25
.venv/bin/python src/data/build_targets.py --overwrite
.venv/bin/python src/data/diagnose_panel_targets.py --overwrite
.venv/bin/python src/data/freeze.py --overwrite
```

## Inclusion And Exclusion Criteria

- Include only declared sources from `configs/sources.yaml`.
- Preserve raw files unchanged under `data/raw` and trust only files recorded in `data/catalog/raw_file_manifest.csv`.
- Canonical observations include mapped variables from `configs/variables.yaml` after unit conversion and QC flagging.
- Monthly panel values use only `qc_flag == ok` and non-null canonical values.
- Bad observations are retained as counts but do not contribute to monthly means.
- WQP date parsing uses mixed date formats; pH blank units are accepted as assumed dimensionless with trace `assume_blank_unit_dimensionless`.
- Targets require future monthly mean Chl-a for the same source-scoped site.

## Integrity Rule

Do not train baselines, PIPE, or MIFAL against data that differs from this freeze. Any change to raw files, canonical adapters, panel construction, target construction, or diagnostics requires a new freeze.
