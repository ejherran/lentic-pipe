# Refined Expert Fuzzy Ensemble Report v0

Generated at UTC: `2026-05-16T22:12:00.942533+00:00`

## Scope

This step does not rebuild the fuzzy state vector. It tests whether fuzzy scores improve the selected calibrated baseline.
All candidate selection is done on `validation`; `test` is report-only.
Selection policy: validation max PR-AUC among candidates with validation Brier <= baseline + 0.002; tie min Brier; tie max macro-F1; test report only.

## Selected Refined Scores

| horizon | selected score | threshold | validation PR-AUC | test PR-AUC | baseline test PR-AUC | d PR-AUC | test Brier | baseline test Brier | d Brier | test macro-F1 | d macro-F1 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `blend_irc1_w0p25` | 0.4000 | 0.6644 | 0.7117 | 0.6924 | 0.0193 | 0.0643 | 0.0651 | -0.0008 | 0.8136 | 0.0014 |
| 2 | `source_selector` | 0.2676 | 0.5176 | 0.5978 | 0.5461 | 0.0517 | 0.0817 | 0.0819 | -0.0002 | 0.7715 | -0.0008 |
| 3 | `blend_irc1_w0p25` | 0.3134 | 0.5369 | 0.6115 | 0.5980 | 0.0135 | 0.0841 | 0.0854 | -0.0012 | 0.7645 | 0.0019 |

## Baseline Test Reference

| horizon | rows | PR-AUC | ROC-AUC | Brier | recall | macro-F1 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 121,540 | 0.6924 | 0.9169 | 0.0651 | 0.6901 | 0.8122 |
| 2 | 115,691 | 0.5461 | 0.8734 | 0.0819 | 0.6246 | 0.7723 |
| 3 | 99,670 | 0.5980 | 0.8645 | 0.0854 | 0.6347 | 0.7625 |

## Source Selector Summary

| horizon | selected score | sources |
|---:|---|---:|
| 1 | `blend_irc1_w0p25` | 2 |
| 1 | `gate_trophic_irc1_w0p75` | 1 |
| 2 | `blend_irc1_w0p25` | 1 |
| 2 | `blend_irc1_w0p75` | 1 |
| 2 | `gate_full_irc1_w0p25` | 1 |
| 3 | `blend_irc1_w0p25` | 2 |
| 3 | `blend_irc1_w0p5` | 1 |

## Outputs

- Predictions: `data/fuzzy/refined_scores_v0.parquet`
- Metrics: `reports/anfis/refined_fuzzy_metrics.csv`
- Selection: `reports/anfis/refined_fuzzy_selection.csv`
- Source selection: `reports/anfis/refined_fuzzy_source_selection.csv`
- Manifest: `reports/anfis/refined_fuzzy_manifest.json`

## Model Artifacts

| model | horizon | path | sha256 |
|---|---:|---|---|
| `meta_logistic` | 1 | `models/anfis/refined/meta_logistic_h1.joblib` | `8111df8c932502e548185bef466d8631c3ead463cfc660dec8e7324e6d261d5d` |
| `meta_logistic` | 2 | `models/anfis/refined/meta_logistic_h2.joblib` | `7219aa2b90923515d08fdb2f98cf5a372b04b47b0a472a1a78e0cb3f728e8cab` |
| `meta_logistic` | 3 | `models/anfis/refined/meta_logistic_h3.joblib` | `a563cc87ed06c89053f03759b871e668a5967957d58f30b985e7cdffc544ce87` |
