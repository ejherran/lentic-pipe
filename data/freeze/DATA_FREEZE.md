# DATA_FREEZE v0

Generated at UTC: `2026-05-19T01:08:49.234972+00:00`
Repository commit: `9f538e35ec07e8326daeec258a9814d82e6a6eeb`
Worktree status: `dirty_at_generation`
Python constraint: `>=3.14,<3.15`

Publication note: this freeze was generated while the NLA integration commit was still staged in the local worktree. The current publication audit should use `git status --short` and `scripts/check_repo_publication_ready.sh`; the full historical dirty-file list is omitted here because it no longer describes the repository state after commit.

## Scope

This freeze captures the current raw fingerprints, canonical observations, monthly panel, target tables, and diagnostics used before temporal splits and baselines.

Downstream experiments must reference this freeze. If raw files, canonicalization logic, panel logic, target logic, or diagnostics change, regenerate this freeze before trusting new results.

## Raw Sources

Raw manifest: `data/catalog/raw_file_manifest.csv`
Raw source catalog: `data/catalog/source_catalog.json`
Raw files: `140`
Raw total size: `58.4 GB`

| source_id | files | size | license | provenance_status | raw_path |
|---|---:|---:|---|---|---|
| `aquamatch_chla` | 4 | 777.7 MB | cc0-1.0 | documented | `data/raw/aquamatch/chla_harmonized_final.csv` |
| `lakebed_us_cse` | 66 | 1.1 GB | cc-by-4.0 | documented | `data/raw/LakeBeD-US-CSE` |
| `nla` | 64 | 42.0 MB | epa_public_data_with_recommended_citation | documented_manual_download_initial_adapter | `data/raw/nla` |
| `wqp` | 6 | 56.5 GB | public_download_multi_provider_with_terms_and_disclaimer | documented_terms_reviewed_conservative_private_mirror | `data/raw/wqp` |

## Canonical Observations

| source_id | adapter | status | chunks | rows | output_dir |
|---|---|---|---:|---:|---|
| `aquamatch_chla` | `aquamatch_chla` | completed | 15 | 3,393,022 | `data/interim/observations/aquamatch_chla` |
| `lakebed_us_cse` | `lakebed_us_cse` | completed | 489 | 432,748,526 | `data/interim/observations/lakebed_us_cse` |
| `nla` | `nla_survey` | completed | 1 | 16,208 | `data/interim/observations/nla` |
| `wqp` | `wqp_streaming` | completed | 238 | 23,808,301 | `data/interim/observations/wqp` |

## Source-Site-Month Coverage

| source_id | site-month rows | sites | start | end |
|---|---:|---:|---|---|
| `aquamatch_chla` | 1,755,072 | 141,544 | `1970-01` | `2024-06` |
| `lakebed_us_cse` | 4,932 | 21 | `1981-04` | `2024-04` |
| `nla` | 4,052 | 2,902 | `2007-05` | `2022-09` |
| `wqp` | 1,626,672 | 106,719 | `1970-01` | `2026-05` |

## Panel And Targets

| artifact | rows | path |
|---|---:|---|
| monthly long panel | 7,437,008 | `data/panel/monthly_long_v0.parquet` |
| monthly wide panel | 3,390,728 | `data/panel/panel_monthly_v0.parquet` |
| target candidates | 10,172,184 | `data/targets/monthly_targets_long_v0.parquet` |
| model targets | 4,649,182 | `data/targets/monthly_targets_model_v0.parquet` |
| panel with targets | 3,390,728 | `data/targets/panel_monthly_with_targets_v0.parquet` |

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
| `canonical_observations` | 750 | 5.8 GB |
| `catalog` | 2 | 107.2 KB |
| `config` | 4 | 30.1 KB |
| `diagnostics` | 10 | 272.8 MB |
| `documentation` | 9 | 35.9 KB |
| `environment` | 4 | 439.1 KB |
| `interim` | 2 | 49.1 MB |
| `panel` | 3 | 184.8 MB |
| `repo_audit` | 1 | 3.9 KB |
| `repo_script` | 7 | 26.0 KB |
| `reports` | 14 | 54.1 KB |
| `script` | 21 | 272.9 KB |
| `source_download_script` | 6 | 16.2 KB |
| `targets` | 4 | 238.4 MB |

### Key Derived SHA-256

| path | sha256 |
|---|---|
| `data/panel/monthly_long_v0.parquet` | `0c3bc9d99cb4d30abd3e094ac760865348bd6b6a5b10c29db03a931cf3874101` |
| `data/panel/panel_monthly_v0.parquet` | `8aedc531b9e024bd8f73e66f917932b8301f79309d4596618c5a839e3b70dc62` |
| `data/targets/monthly_targets_long_v0.parquet` | `91df12130bff70552aa0a5536c51e80afc0711ddb24dccbbe605c6deca86be9b` |
| `data/targets/monthly_targets_model_v0.parquet` | `c93ee8dbf424828c8dc11bc5da236d5c505e5f6ba7478eb689cca12a88c7e799` |
| `data/targets/panel_monthly_with_targets_v0.parquet` | `ccbfe6545f72bcfcbdc800fca6b02ce5d3e99c140adbb310f12313a4357395f2` |
| `data/diagnostics/diagnostic_manifest_v0.json` | `aa6b172f28d3a19db54e45f3621b7065d0495b0f9a2b17bbca8e145fc37e4572` |

## Exact Generation Commands

```bash
.venv/bin/python src/data/validate_sources.py
.venv/bin/python src/data/raw_manifest.py --reuse-existing
.venv/bin/python src/data/build_observations.py --source lakebed_us_cse --chunksize 250000 --overwrite
.venv/bin/python src/data/build_observations.py --source aquamatch_chla --chunksize 250000 --overwrite
.venv/bin/python src/data/build_observations.py --source nla --chunksize 250000 --overwrite
.venv/bin/python src/data/build_observations.py --source wqp --chunksize 250000 --overwrite
.venv/bin/python src/data/report_observations.py
.venv/bin/python src/data/site_registry.py
.venv/bin/python src/data/build_waterbody_crosswalk.py
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
