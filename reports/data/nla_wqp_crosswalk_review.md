# NLA-WQP Crosswalk Review

Generated review date: `2026-05-18`

## Purpose

This review records the first focused cross-source site-resolution pass between
EPA NLA and WQP after adding NLA to the canonical workspace. It is a review
artifact only. It does not promote accepted waterbody IDs, merge observations,
or change the monthly panel.

## Strategy Decision

WQP is the operational backbone for broad panel construction because it has the
widest spatial and temporal coverage in the current workspace. NLA is treated
as a validation, provenance, and enrichment layer.

The crosswalk therefore distinguishes WQP records that already carry NLA/NARS
identity evidence from spatially close records reported by other WQP providers.
This keeps WQP-first modeling practical while avoiding silent duplicate or
leakage-prone merges.

## Reproduction Commands

The enriched focused review was generated from the source-scoped site registry
after rebuilding NLA with 2007 `LAKENAME`/`NHDNAME` site metadata:

```bash
poetry run python src/data/build_waterbody_crosswalk.py \
  --source-pair nla:wqp \
  --output-parquet tmp/crosswalk_nla_wqp_enriched.parquet \
  --output-csv tmp/crosswalk_nla_wqp_enriched.csv \
  --report tmp/crosswalk_nla_wqp_enriched_report.md \
  --manifest tmp/crosswalk_nla_wqp_enriched_manifest.json
```

The prioritized review view was generated with:

```bash
head -n 1 tmp/crosswalk_nla_wqp_enriched.csv > tmp/crosswalk_nla_wqp_enriched_review_priority.csv
awk -F, 'NR > 1 && $2 <= 3 {print}' tmp/crosswalk_nla_wqp_enriched.csv >> tmp/crosswalk_nla_wqp_enriched_review_priority.csv
```

## Results

| metric | count |
|---|---:|
| Source-scoped sites in registry | 251,186 |
| NLA-WQP candidate pairs | 5,466 |
| Prioritized review candidates, tiers 1-3 | 2,449 |
| Exploratory nearby candidates, tier 4 | 3,017 |
| NLA sites with names after 2007 metadata enrichment | 985 |

## Review Tiers

| review_tier | match_method | count | Interpretation |
|---:|---|---:|---|
| `1` | `provider_prefix_normalized_site_identifier` | 2,001 | WQP contains records whose source identifier matches NLA after configured provider-prefix normalization such as `NARS_WQX-NLA_ME-10063` to `NLA_ME-10063`. Treat as high-confidence provenance/duplication evidence, not as independent validation. |
| `2` | `same_coordinates_different_identifier` | 13 | Coordinates are identical within tolerance, but source identifiers differ. Treat as high-confidence same-point review items requiring provenance checks. |
| `3` | `very_close_coordinates` | 301 | Coordinates are within the very-close threshold, but name evidence is missing or weak. Treat as spatial review candidates. |
| `3` | `very_close_coordinates_and_name` | 32 | Coordinates are within the very-close threshold and normalized names are similar. Treat as high-priority manual review candidates. |
| `3` | `close_coordinates_and_name` | 102 | Coordinates are within the strong-distance threshold and normalized names are similar. Treat as high-priority manual review candidates. |
| `4` | `nearby_coordinates` | 3,017 | Coordinates are within the broad search radius only. Treat as exploratory and exclude from prioritized review by default. |

## Tier 1 Coordinate Offset Review

Tier 1 rows are identifier aliases, but spatial precision varies:

| distance_review_band | count |
|---|---:|
| `same_coordinate` | 813 |
| `near_exact_<=1m` | 778 |
| `very_near_<=10m` | 88 |
| `very_close_<=50m` | 79 |
| `close_<=250m` | 118 |
| `offset_<=500m` | 72 |
| `offset_>500m` | 53 |

The 243 tier 1 records above 50 m should be treated as alias/provenance
matches, not spatially exact station matches. The 53 records above 500 m are
the first tier 1 offset-review subset.

## Tier 2 Review

Tier 2 contains 13 same-coordinate, different-identifier candidates:

| provider group | count | Interpretation |
|---|---:|---|
| `OREGONDEQ` | 10 | Strong external-provider bridges for NLA-WQP review. |
| `MNPCA` | 1 | Strong external-provider bridge for NLA-WQP review. |
| `MNDA_PESTICIDE` | 1 | Strong external-provider bridge for NLA-WQP review. |
| `NARS_WQX` | 1 | Likely same-point NLA/NARS alias across NLA identifiers or cycles; do not treat as independent external validation. |

## Tier 3 Name-Supported Review

Tier 3 contains 435 spatial candidates across 337 NLA sites. Of these, 134 have
name support:

| subset | pairs | note |
|---|---:|---|
| Has tier 1 NARS/WQP alias | 132 | Useful as WQP enrichment around already-linked NLA sites. |
| No tier 1 NARS/WQP alias | 2 | Highest-priority possible new NLA-WQP links. |

The two name-supported tier 3 candidates without a tier 1 alias are:

| NLA site | NLA name | WQP site | WQP name | distance_m |
|---|---|---|---|---:|
| `NLA_MN-10054` | `Long Lake (Main Bay)` | `MNPCA-31-0266-01-203` | `LONG (MAIN BAY)` | 34.538 |
| `NLA_OR-10057` | `Emigrant Lake` | `OREGONDEQ-38859-ORDEQ` | `Emigrant Lake` | 187.556 |

## Observations

- The NLA-WQP focused run produced no literal `shared_source_site_identifier`
  matches, because WQP NARS/NLA station IDs are provider-prefixed.
- Prefix normalization moved 2,001 NLA-WQP pairs into review tier 1.
- Enriching NLA with 2007 site metadata raised tier 3 from 333 to 435 pairs by
  moving 102 previously broad spatial candidates into
  `close_coordinates_and_name`.
- Tier 1 pairs should still be separated by coordinate precision before
  promotion. In the first review CSV, many were exact-coordinate aliases, while
  a smaller set had substantial coordinate offsets despite matching NLA/NARS
  identifiers.
- Same-coordinate pairs with different identifiers are rare and informative:
  13 pairs. They are strong evidence of the same sampling point, but still need
  provider/provenance review before promotion.
- The `very_close_coordinates` set remains manageable at 301 pairs using the
  current 50 m threshold.
- Tier 4 is useful for exploratory audits but is too noisy for immediate
  promotion work.

## Current Policy

- Keep canonical observations source-scoped.
- Use WQP as the panel backbone.
- Use NLA to validate, annotate, or enrich WQP-backed sites after explicit
  review.
- Do not treat NLA-derived WQP records as independent evidence.
- Treat tier 1 records with large coordinate offsets as alias/provenance matches
  requiring coordinate review, not as spatially exact matches.
- Do not promote tier 2 or tier 3 candidates automatically.
- Re-check temporal and spatial splits before any accepted crosswalk affects
  modeling inputs.

## Next Review Step

Review tiers 1-3 before creating any accepted crosswalk artifact. If an
accepted crosswalk is introduced later, version it separately from the candidate
table and rebuild the panel, targets, splits, diagnostics, and data freeze in
the same governance cycle.
