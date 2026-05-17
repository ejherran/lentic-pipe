# Operational Site Review v0

Generated at UTC: `2026-05-16T23:54:27.496765+00:00`
Started at UTC: `2026-05-16T23:48:16.412873+00:00`

## Scope

This review aggregates frozen operational scores by source-scoped site. It does not refit or change the model.
Recent window: last `24` months.

## Horizon Summary

| horizon | sites | active recent sites | recent predicted sites | mean recent latest probability | sustained risk sites |
|---:|---:|---:|---:|---:|---:|
| 1 | 248,284 | 9,905 | 1,159 | 0.1537 | 539 |
| 2 | 248,284 | 9,905 | 1,316 | 0.1363 | 620 |
| 3 | 248,284 | 9,905 | 1,308 | 0.1441 | 659 |

## Recent Top Source Counts

| horizon | source | top sites |
|---:|---|---:|
| 1 | `wqp` | 989 |
| 1 | `aquamatch_chla` | 11 |
| 2 | `wqp` | 991 |
| 2 | `aquamatch_chla` | 9 |
| 3 | `wqp` | 990 |
| 3 | `aquamatch_chla` | 10 |

## Outputs

- Site summary: `reports/anfis/operational_site_review_summary.csv`
- Site summary parquet: `reports/anfis/operational_site_review_summary.parquet`
- Recent site risk: `reports/anfis/operational_site_review_recent_site_risk.csv`
- Top-site trajectories: `reports/anfis/operational_site_review_top_site_trajectories.csv`
- Sustained risk: `reports/anfis/operational_site_review_sustained_risk.csv`
- Low-evidence high-risk: `reports/anfis/operational_site_review_low_evidence_high_risk.csv`
- Manifest: `reports/anfis/operational_site_review_manifest.json`

Site summary rows: `744,852`
Recent site-risk rows: `3,000`
Trajectory rows: `12,401`
Sustained risk rows: `1,818`
Low-evidence high-risk rows: `851`
