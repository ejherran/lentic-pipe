# Data Licenses

This file summarizes license and redistribution status for the current sources.
The exact source registry remains `configs/sources.yaml`.

| source_id | License field | Redistribution stance |
|---|---|---|
| `lakebed_us_cse` | `cc-by-4.0` | Cite the original dataset. Keep the local mirror under DVC/GCS for reproducibility. |
| `wqp` | `public_download_multi_provider_with_terms_and_disclaimer` | Official WQP/EPA pages describe the data as publicly available for download/retrieval, but WQP aggregates many provider organizations and does not provide a single blanket raw redistribution license. Keep the full raw mirror in authorized DVC/GCS storage, not as public Git blobs; publish scripts, filters, hashes, manifests, and documentation. |
| `aquamatch_chla` | `cc0-1.0` | Metadata declares Creative Commons CC0 1.0 "No Rights Reserved". Keep the raw mirror under DVC/GCS; publish citation and hashes. |
| `nla` | `epa_public_data_with_recommended_citation` | EPA publishes NARS/NLA CSV files with companion metadata and recommended citation guidance. Keep the local raw mirror under DVC/GCS; publish citations, source metadata, hashes, DVC pointers, and derived summaries. |

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

## NLA Citation And Use Review

Reviewed on `2026-05-18` against official EPA National Aquatic Resource Surveys
documentation:

- `https://www.epa.gov/national-aquatic-resource-surveys/data-national-aquatic-resource-surveys`
- `https://www.epa.gov/national-aquatic-resource-surveys/frequent-questions-about-data-national-aquatic-resource-surveys`
- `https://www.epa.gov/national-aquatic-resource-surveys/what-data-are-available-download-national-aquatic-resource`

EPA's NARS data page provides data as CSV files with companion metadata. EPA's
FAQ recommends citing the data by EPA, survey report year, survey name/year,
the NARS data page URL, and access date. The report years recorded for NLA are:

| Survey | Report year |
|---|---:|
| National Lakes Assessment 2007 | 2010 |
| National Lakes Assessment 2012 | 2016 |
| National Lakes Assessment 2017 | 2022 |
| National Lakes Assessment 2022 | 2024 |

Citation template:

```text
U.S. Environmental Protection Agency. [survey report year]. National Aquatic
Resource Surveys. National Lakes Assessment [survey year] (data and metadata
files). Available from U.S. EPA web page:
https://www.epa.gov/national-aquatic-resource-surveys/data-national-aquatic-resource-surveys.
Date accessed: 2026-05-18.
```

## Publication Rule

GitHub may contain code, configs, reports, manifests, hashes, and DVC pointer
files. It must not contain full raw datasets, private bucket names, credentials,
or large derived artifacts.
