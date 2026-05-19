# Site Resolution

The project preserves source-scoped site identity by default. A row from WQP,
AquaMatch, LakeBeD, or NLA is not treated as the same waterbody as a row from
another source unless an explicit, versioned crosswalk says so.

## Current Policy

- `source_id` and `site_id` remain authoritative in canonical observations,
  panels, targets, splits, and model inputs.
- Cross-source matching starts as an auditable candidate table, not an automatic
  merge.
- Accepted waterbody IDs are not generated from raw candidate pairs. They must
  be reviewed, documented, and versioned before downstream workflows use them.
- Modeling splits must be re-checked after any accepted crosswalk is introduced,
  because the same waterbody can otherwise appear in different splits through
  different source-specific IDs.

The machine-readable policy and candidate thresholds live in
`configs/site_resolution.yaml`.

## WQP Backbone Policy

WQP is the operational backbone for broad panel construction because it has the
widest source coverage and longest monitoring history. Other sources remain
source-scoped and are used as review, enrichment, validation, or benchmark
layers until an explicit accepted crosswalk is created.

Some WQP stations carry provider-prefixed identifiers that echo another source.
For example, WQP can expose NARS/NLA stations as `NARS_WQX-NLA_ME-10063`, while
the NLA source records the same survey site as `NLA_ME-10063`. Candidate
generation normalizes configured provider prefixes before comparing
`site_id_source`, so these cases are classified as identifier evidence instead
of coordinate-only evidence.

When source identifiers do not match but coordinates are identical within the
configured tolerance, the candidate remains `strong` but uses the explicit
method `same_coordinates_different_identifier`. This means the pair is likely
the same sampling point, while still requiring provenance review before it is
used as an accepted merge.

## Focused NLA-WQP Review

The first focused NLA-WQP candidate review is recorded in
`reports/data/nla_wqp_crosswalk_review.md`. It keeps the review separate from
accepted site identity because the project has not promoted any cross-source
waterbody IDs yet.

The enriched focused run produced 5,466 NLA-WQP candidate pairs:

| review_tier | count | Default action |
|---:|---:|---|
| `1` | 2,001 | Review as WQP records carrying NLA/NARS identifier evidence. |
| `2` | 13 | Review as same-coordinate, different-identifier evidence. |
| `3` | 435 | Review as likely same-waterbody or nearby-station candidates. |
| `4` | 3,017 | Keep exploratory by default. |

The prioritized review set is tiers 1-3, with 2,449 candidate pairs. Tier 4 is
kept in the full artifact for audits but is too noisy for immediate promotion
work.

The candidate table also includes `distance_review_band` and `review_action`.
These columns separate identifier evidence from spatial precision. For example,
a WQP `NARS_WQX-*` alias can be valid provenance evidence while still needing
coordinate-offset review if the reported WQP coordinate is hundreds of meters
from the NLA coordinate.

## Candidate Generation

Build candidate pairs from the source-scoped site registry:

```bash
poetry run python src/data/site_registry.py
poetry run python src/data/build_waterbody_crosswalk.py
```

The candidate builder writes:

```text
data/interim/waterbody_crosswalk_candidates_v0.parquet
data/interim/waterbody_crosswalk_candidates_v0.csv
reports/data/waterbody_crosswalk_candidates_report.md
reports/data/waterbody_crosswalk_candidates_manifest.json
```

The `data/interim/` outputs are DVC-managed artifacts. The report and manifest
are small review artifacts kept in Git.

## Confidence Labels

| confidence | Meaning | Downstream use |
|---|---|---|
| `exact` | Source-native site identifiers match literally, or match after configured provider-prefix normalization, and coordinates are compatible. | High-priority review item; still not an accepted merge by itself. |
| `strong` | Coordinates are identical with different identifiers, coordinates are very close, or coordinates are close and normalized names are similar. | Review before promotion. |
| `candidate` | Coordinates are within the search radius but evidence is limited. | Manual review only. |

## Review Tiers

The candidate table includes `review_tier` so a complete candidate artifact can
still be reviewed in priority order.

| review_tier | Meaning |
|---:|---|
| `1` | Identifiers match literally or after configured provider-prefix normalization. |
| `2` | Coordinates are identical within tolerance, but identifiers differ. |
| `3` | Strong spatial candidate: coordinates are very close, or close with normalized-name support. |
| `4` | Nearby coordinate candidate inside the broad search radius. |

Candidate rows are pairwise. A future accepted crosswalk should resolve groups
or clusters explicitly instead of assuming pairwise candidate IDs are durable
waterbody IDs.

## Distance Review Bands

| distance_review_band | Meaning |
|---|---|
| `same_coordinate` | Distance is within the configured same-coordinate tolerance. |
| `near_exact_<=1m` | Coordinates are effectively identical for review purposes. |
| `very_near_<=10m` | Coordinates are separated by at most 10 m. |
| `very_close_<=50m` | Coordinates are inside the current very-close threshold. |
| `close_<=250m` | Coordinates are inside the current strong-distance threshold. |
| `offset_<=500m` | Identifier evidence may still be useful, but coordinate offset needs review. |
| `offset_>500m` | Treat as an identifier/provenance match with substantial coordinate-offset review. |

## Review Evidence

Before promoting a candidate, record the evidence used for the decision. Useful
evidence includes:

- source-native identifiers and agency/provider context
- coordinates and distance
- source names after normalization
- hydrologic identifiers such as COMID or HUC when available
- temporal overlap and sampling context
- manual inspection notes for ambiguous reservoirs, lake complexes, or nearby
  monitoring stations

Promotion should create a new accepted crosswalk artifact and update the panel,
targets, splits, diagnostics, and data freeze in the same data-governance cycle.
