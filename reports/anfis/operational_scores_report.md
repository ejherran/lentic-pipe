# Operational Current Model Scores v0

Generated at UTC: `2026-05-16T23:28:35.144238+00:00`
Started at UTC: `2026-05-16T23:26:17.056788+00:00`

## Scope

Scores every monthly panel row for each selected horizon using the frozen current refined fuzzy model.
These are operational probabilities, not validation/test metrics.

## Horizon Summary

| horizon | rows | sites | selected score | threshold | predicted blooms | predicted rate | mean probability | p95 probability | max probability |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | 3,386,676 | 248,284 | `blend_irc1_w0p25` | 0.4000 | 414,477 | 0.1224 | 0.1363 | 0.6561 | 0.8865 |
| 2 | 3,386,676 | 248,284 | `source_selector` | 0.2676 | 468,238 | 0.1383 | 0.1313 | 0.5664 | 0.6840 |
| 3 | 3,386,676 | 248,284 | `blend_irc1_w0p25` | 0.3134 | 464,448 | 0.1371 | 0.1325 | 0.5386 | 0.8691 |

## Selected Baselines

| horizon | baseline model |
|---:|---|
| 1 | `logistic_sgd` |
| 2 | `persistence` |
| 3 | `logistic_sgd` |

## Source Selector Fallback

Unknown future sources use the fallback score below until the refinement step is rerun with validation evidence for that source.

| horizon | fallback score |
|---:|---|
| 1 | `blend_irc1_w0p25` |
| 2 | `blend_irc1_w0p25` |
| 3 | `blend_irc1_w0p25` |

## Outputs

- Scores: `data/fuzzy/operational_scores_v0.parquet`
- Summary: `reports/anfis/operational_scores_summary.csv`
- Top risks: `reports/anfis/operational_top_risks.csv`
- Recent top risks: `reports/anfis/operational_recent_top_risks.csv`
- Latest-site top risks: `reports/anfis/operational_latest_site_top_risks.csv`
- Recent latest-site top risks: `reports/anfis/operational_recent_latest_site_top_risks.csv`
- Manifest: `reports/anfis/operational_scores_manifest.json`

Top-risk ranking rule: probability desc; threshold margin desc; evidence priority desc; full evidence desc; exogenous evidence desc; most recent month desc; source/site/date asc.

Recent top-risk window: last `24` months per horizon, anchored on each horizon's latest `origin_year_month`.
Recent top-risk rows written: `3,000`
Latest-site top-risk rows written: `3,000`
Recent latest-site top-risk rows written: `3,000`
Top-risk rows written: `3,000`
