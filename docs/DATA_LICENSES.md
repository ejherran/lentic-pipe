# Data Licenses

This file summarizes license and redistribution status for the current sources.
The exact source registry remains `configs/sources.yaml`.

| source_id | License field | Redistribution stance |
|---|---|---|
| `lakebed_us_cse` | `cc-by-4.0` | Cite the original dataset. Keep the local mirror under DVC/GCS for reproducibility. |
| `wqp` | `public_download_multi_provider_with_terms_and_disclaimer` | Official WQP/EPA pages describe the data as publicly available for download/retrieval, but WQP aggregates many provider organizations and does not provide a single blanket raw redistribution license. Keep the full raw mirror in authorized DVC/GCS storage, not as public Git blobs; publish scripts, filters, hashes, manifests, and documentation. |
| `aquamatch_chla` | `cc0-1.0` | Metadata declares Creative Commons CC0 1.0 "No Rights Reserved". Keep the raw mirror under DVC/GCS; publish citation and hashes. |

## AquaMatch Citation

Brousil, M.R., M.F. Meyer, K. Willi, B.G. Steele, J. De La Torre, and
M.R. Ross. 2024. AquaMatch Chlorophyll a Data from Water Quality Portal:
~1970-2024 ver 2. Environmental Data Initiative.
`https://doi.org/10.6073/pasta/2f750544112e5408928dd9a61e6ace30`

## WQP Terms Review

Reviewed on `2026-05-17` against official WQP/EPA documentation:

- `https://www.epa.gov/waterdata/water-quality-data`
- `https://www.epa.gov/waterdata/waters-terms-use-and-disclaimer`
- `https://www.epa.gov/waterdata/water-quality-portal-quick-reference-guide`
- `https://www.waterqualitydata.us/portal_userguide/`

The publication stance is conservative: WQP-derived raw files remain in
authorized DVC/GCS storage instead of public Git blobs. Git may contain
reproducible acquisition scripts, query filters, source metadata, hashes, DVC
pointers, and derived summaries. This preserves reproducibility for authorized
users while avoiding a broad public redistribution claim for the full raw export.

## Publication Rule

GitHub may contain code, configs, reports, manifests, hashes, and DVC pointer
files. It must not contain full raw datasets, private bucket names, credentials,
or large derived artifacts.
