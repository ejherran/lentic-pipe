# Waterbody Crosswalk Candidates

Generated at UTC: `2026-05-19T00:01:05.590849+00:00`

## Purpose

This report lists cross-source site pairs that may represent the same waterbody. It is an audit layer only: it does not merge observations, change site IDs, or alter the monthly panel.

## Search Configuration

- Candidate maximum distance: `1000.0 m`
- Strong distance threshold: `250.0 m`
- Very close distance threshold: `50.0 m`
- Same-coordinate tolerance: `0.001 m`
- Exact ID maximum distance: `5000.0 m`
- Name similarity threshold: `0.75`
- Site ID prefix normalization: `{"wqp": ["NARS_WQX-"]}`

## Summary

- Source-scoped sites in input registry: `251,186`
- Candidate pairs: `410,563`

| review_tier | pairs |
|---:|---:|
| `1` | 35,022 |
| `2` | 2,531 |
| `3` | 24,265 |
| `4` | 348,745 |

| confidence | pairs |
|---|---:|
| `exact` | 35,022 |
| `strong` | 26,796 |
| `candidate` | 348,745 |

## By Source Pair

| source_pair | pairs | min_distance_m | median_distance_m |
|---|---:|---:|---:|
| `aquamatch_chla - lakebed_us_cse` | 42 | 4.5 | 228.0 |
| `aquamatch_chla - nla` | 5,648 | 0.0 | 76.6 |
| `aquamatch_chla - wqp` | 399,343 | 0.0 | 493.2 |
| `lakebed_us_cse - nla` | 2 | 85.6 | 441.7 |
| `lakebed_us_cse - wqp` | 62 | 4.5 | 448.9 |
| `nla - wqp` | 5,466 | 0.0 | 175.2 |

## By Match Method

| match_method | pairs |
|---|---:|
| `nearby_coordinates` | 348,745 |
| `shared_source_site_identifier` | 33,021 |
| `very_close_coordinates` | 24,129 |
| `same_coordinates_different_identifier` | 2,531 |
| `provider_prefix_normalized_site_identifier` | 2,001 |
| `close_coordinates_and_name` | 104 |
| `very_close_coordinates_and_name` | 32 |

## By Distance Review Band

| distance_review_band | pairs |
|---|---:|
| `same_coordinate` | 22,754 |
| `near_exact_<=1m` | 20,540 |
| `very_near_<=10m` | 7,638 |
| `very_close_<=50m` | 10,242 |
| `close_<=250m` | 57,255 |
| `offset_<=500m` | 92,089 |
| `offset_>500m` | 200,045 |

## Tier 1 Coordinate Offset

| distance_review_band | pairs |
|---|---:|
| `same_coordinate` | 20,223 |
| `near_exact_<=1m` | 11,981 |
| `very_near_<=10m` | 1,875 |
| `very_close_<=50m` | 403 |
| `close_<=250m` | 185 |
| `offset_<=500m` | 137 |
| `offset_>500m` | 218 |

## Top Candidates

| tier | confidence | method | distance_m | left | right |
|---:|---|---|---:|---|---|
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:NJDEP_BFBM-NJW04459-049-1` | `wqp:NJDEP_BFBM-NJW04459-049-1` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:21IOWA_WQX-22070002` | `wqp:21IOWA_WQX-22070002` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:MNPCA-56-0116-01-201` | `wqp:MNPCA-56-0116-01-201` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:11113300-CHASULD` | `wqp:11113300-CHASULD` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:21NDHDWQ_WQX-381200` | `wqp:21NDHDWQ_WQX-381200` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:21FLCEN_WQX-20010793` | `wqp:21FLCEN_WQX-20010793` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:WIDNR_WQX-603458` | `wqp:WIDNR_WQX-603458` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:MNPCA-10-0013-00-451` | `wqp:MNPCA-10-0013-00-451` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:COEOMAHA_WQX-OCRLKML1` | `wqp:COEOMAHA_WQX-OCRLKML1` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:21OHIO_WQX-301988` | `wqp:21OHIO_WQX-301988` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:21FLCEN_WQX-20020639` | `wqp:21FLCEN_WQX-20020639` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:21KAN001_WQX-LM017601` | `wqp:21KAN001_WQX-LM017601` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:NJDEP_BFBM-NJW04459-118-2` | `wqp:NJDEP_BFBM-NJW04459-118-2` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:LEECHLAK_WQX-Steamboat Bay` | `wqp:LEECHLAK_WQX-Steamboat Bay` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:21NC03WQ-CPFLH2` | `wqp:21NC03WQ-CPFLH2` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:MNPCA-08-0073-00-201` | `wqp:MNPCA-08-0073-00-201` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:MNPCA-18-0386-00-101` | `wqp:MNPCA-18-0386-00-101` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:NARS_WQX-NLA_SD-10010` | `wqp:NARS_WQX-NLA_SD-10010` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:MNPCA-15-0023-00-201` | `wqp:MNPCA-15-0023-00-201` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:MNPCA-11-0361-00-100` | `wqp:MNPCA-11-0361-00-100` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:MNPCA-31-0464-00-201` | `wqp:MNPCA-31-0464-00-201` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:21VASWCB-9-NEW132.86` | `wqp:21VASWCB-9-NEW132.86` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:MNPCA-27-0133-15-108` | `wqp:MNPCA-27-0133-15-108` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:UTAHDWQ_WQX-5932240` | `wqp:UTAHDWQ_WQX-5932240` |
| `1` | `exact` | `shared_source_site_identifier` | 0.0 | `aquamatch_chla:21FLORAN_WQX-SC13` | `wqp:21FLORAN_WQX-SC13` |

## Rules

- Preserve `source_id` and source-scoped `site_id` in all downstream tables.
- Treat `candidate` rows as review items, not accepted merges.
- Promote a candidate to an accepted waterbody crosswalk only after documenting the match evidence.
- Re-check temporal splits before using linked waterbodies in modeling, because cross-source links can create leakage if the same waterbody appears in different splits through different sources.
