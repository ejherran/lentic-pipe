# Data Sources

This project is source-scoped. Downstream tables must preserve `source_id` and
`site_id`; no pipeline step may assume that sites from different raw sources are
the same water body unless an explicit source-matching table is created. The
candidate-generation policy for that matching layer is documented in
`docs/SITE_RESOLUTION.md` and configured in `configs/site_resolution.yaml`.

The authoritative machine-readable source registry is
`configs/sources.yaml`.

## Current Sources

| source_id | Source | Local raw path | Acquisition | Status |
|---|---|---|---|---|
| `lakebed_us_cse` | LakeBeD-US: Computer Science Edition | `data/raw/LakeBeD-US-CSE` | `data/scripts/download_lakebed_us_cse.py` via Hugging Face dataset snapshot | documented |
| `wqp` | Water Quality Portal WQX3 lake/reservoir/impoundment export | `data/raw/wqp` | project WQX3 scripts using the recorded WQP query filters | acquisition and terms reviewed; full raw mirror remains in authorized DVC/GCS storage, not public Git blobs |
| `aquamatch_chla` | AquaMatch Chlorophyll a Data from Water Quality Portal: ~1970-2024 | `data/raw/aquamatch` | manual authenticated browser download from EDI Data Portal by the project owner | documented |
| `nla` | EPA National Lakes Assessment survey data | `data/raw/nla` | manual browser download from the EPA National Aquatic Resource Surveys data page | documented raw snapshot; initial adapter uses the combined NLA 2007-2022 population-estimate file |

## WQP Query

The browser query used to define the WQP extraction was:

```text
https://www.waterqualitydata.us/beta/#countrycode=US&siteType=Lake%2C%20Reservoir%2C%20Impoundment&sampleMedia=Water&startDateLo=01-01-1970&startDateHi=05-11-2026&mimeType=csv&dataProfile=fullPhysChem&providers=NWIS&providers=STORET
```

The local scripts use equivalent WQX3 endpoints so the download is chunked and
resumable:

| File | Endpoint role |
|---|---|
| `data/scripts/download_wqp_results.py` | `Result/search` with `dataProfile=fullPhysChem`; writes `data/raw/wqp/wqp_results.csv` |
| `data/scripts/download_wqp_stations.py` | `Station/search`; writes `data/raw/wqp/wqp_stations.csv` |
| `data/scripts/download_wqp_activity.py` | `Activity/search`; writes `data/raw/wqp/wqp_activity.csv` |

WQP download chunks are resumable working files under
`data/cache/downloads/wqp/`; they are intentionally not raw source files and are
not included in the DVC raw artifact plan.

Official WQP/EPA documentation describes WQP data as publicly available for
download/retrieval, but the portal aggregates USGS data and WQX submissions from
many provider organizations. This project therefore does not publish the full
raw WQP mirror as a Git blob. Public artifacts are limited to acquisition
scripts, query filters, metadata, SHA-256 hashes, and derived summaries.

## LakeBeD Snapshot Notes

LakeBeD is acquired with the project script from the public Hugging Face dataset
snapshot into `data/raw/LakeBeD-US-CSE`. Local Hugging Face cache files under
`.cache/` are excluded from the raw SHA-256 manifest and from DVC. The canonical
raw artifact is the dataset content needed by the adapter, not local download
cache metadata.

## AquaMatch Package

AquaMatch was downloaded directly from EDI Data Portal after login. No third
party mirror was used.

| Field | Value |
|---|---|
| Package ID | `edi.1756.2` |
| DOI | `https://doi.org/10.6073/pasta/2f750544112e5408928dd9a61e6ace30` |
| Data entity | `chla_harmonized_final` |
| Main file | `data/raw/aquamatch/chla_harmonized_final.csv` |
| Metadata files | `metadata.xml`, `README.pdf`, `Data_Package_Quality_Report.mhtml` |
| Publication date | `2024-11-20` |

## EPA National Lakes Assessment

The `nla` source contains manually downloaded EPA National Aquatic Resource
Surveys National Lakes Assessment files under `data/raw/nla/`. The local raw
snapshot is organized by survey year directories:

| Survey folder | Local files | Notes |
|---|---:|---|
| `2007` | 48 | Site information, water quality, Secchi, profile, habitat, plankton, condition estimates, metadata, and final data notes. |
| `2012` | 4 | Key variables and condition categories with metadata. |
| `2017` | 6 | Population-estimate, condition-estimate, and landscape metrics files with metadata. |
| `2022` | 6 | Combined 2007-2022 population-estimate table, condition estimates, and 2022 sample grid with metadata. |

EPA's NARS data page publishes survey data as CSV files with companion metadata
files and recommends reviewing technical reports, manuals, survey reports, and
metadata before analysis. EPA also provides recommended citation text for each
survey. The project records the citation template and report years in
`configs/sources.yaml`.

The initial canonical adapter uses:

```text
data/raw/nla/2022/nla2007-2022_data_forpopestimates_indexvisits_probsites_0.csv
```

That file includes survey cycles 2007, 2012, 2017, and 2022. It contributes
survey-level `CHLA_RESULT`, `NTL_RESULT`, `PTL_RESULT`, and `DO_SURF` values to
canonical variables. The combined table records survey cycle but not a row-level
sample date, so the adapter joins exact `DATE_COL` values from available
survey-year files when possible. The current exact-date joins use:

| Survey cycle | Date source |
|---:|---|
| 2007 | `data/raw/nla/2007/NLA2007_SampledLakeInformation_20091113.csv`; exact date coverage 1,028/1,028 combined rows |
| 2022 | `data/raw/nla/2022/nla2022_sample_grid.csv`; exact date coverage 981/981 combined rows |

Rows without a joined exact date use a documented nominal July month for the
survey year and record `sample_date_policy=survey_year_nominal_month` in
`flags_json`.

Do not interpret NLA nominal months as monthly monitoring frequency. If
year-specific site/date files are added later, the adapter should be revised to
join exact sample dates before rebuilding the panel and targets.

The NLA adapter also joins 2007 `SampledLakeInformation` metadata when
available. `LAKENAME`/`NHDNAME` are used to populate canonical `site_name`, and
`HUC_8`, `REACHCODE`, and `COM_ID` are retained in `flags_json` as review
evidence for cross-source site resolution. Later NLA combined population files
do not expose the same lake-name fields in the current raw snapshot, so missing
NLA names remain expected for those survey cycles.

## Adding Future Sources

1. Add a stable `source_id` entry to `configs/sources.yaml`.
2. Store untouched raw files under `data/raw/<source_id>/`.
3. Record source type, access policy, acquisition route, URL, license, filters,
   and redistribution policy.
4. Add raw paths to `raw_manifest_paths` when the source includes metadata files
   outside the adapter's `raw_path`.
5. Add the heavy raw and derived paths to `configs/dvc_artifacts.yaml`.
6. Regenerate raw SHA-256 manifests before harmonization or model training.
