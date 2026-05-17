# Data Sources

This project is source-scoped. Downstream tables must preserve `source_id` and
`site_id`; no pipeline step may assume that sites from different raw sources are
the same water body unless an explicit source-matching table is created.

The authoritative machine-readable source registry is
`configs/sources.yaml`.

## Current Sources

| source_id | Source | Local raw path | Acquisition | Status |
|---|---|---|---|---|
| `lakebed_us_cse` | LakeBeD-US: Computer Science Edition | `data/raw/LakeBeD-US-CSE` | `data/scripts/download_lakebed_us_cse.py` via Hugging Face dataset snapshot | documented |
| `wqp` | Water Quality Portal WQX3 lake/reservoir/impoundment export | `data/raw/wqp` | project WQX3 scripts using the recorded WQP query filters | acquisition and terms reviewed; full raw mirror remains in authorized DVC/GCS storage, not public Git blobs |
| `aquamatch_chla` | AquaMatch Chlorophyll a Data from Water Quality Portal: ~1970-2024 | `data/raw/aquamatch` | manual authenticated browser download from EDI Data Portal by the project owner | documented |

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

## Adding Future Sources

1. Add a stable `source_id` entry to `configs/sources.yaml`.
2. Store untouched raw files under `data/raw/<source_id>/`.
3. Record source type, access policy, acquisition route, URL, license, filters,
   and redistribution policy.
4. Add raw paths to `raw_manifest_paths` when the source includes metadata files
   outside the adapter's `raw_path`.
5. Add the heavy raw and derived paths to `configs/dvc_artifacts.yaml`.
6. Regenerate raw SHA-256 manifests before harmonization or model training.
