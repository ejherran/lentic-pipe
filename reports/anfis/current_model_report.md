# Current Model Application Report v0

Generated at UTC: `2026-05-16T22:21:38.769296+00:00`

## Scope

This report applies the selected refined fuzzy score per horizon and freezes current model predictions.
The selected scores were chosen upstream on `validation`; this script only applies that frozen selection.

## Applied Scores

| horizon | score | rows | threshold |
|---:|---|---:|---:|
| 1 | `blend_irc1_w0p25` | 284,650 | 0.4000 |
| 2 | `source_selector` | 269,907 | 0.2676 |
| 3 | `blend_irc1_w0p25` | 235,708 | 0.3134 |

## Test Metrics

| horizon | rows | PR-AUC | ROC-AUC | Brier | recall | macro-F1 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 121,540 | 0.7117 | 0.9207 | 0.0643 | 0.6674 | 0.8136 |
| 2 | 115,691 | 0.5978 | 0.8804 | 0.0817 | 0.6405 | 0.7715 |
| 3 | 99,670 | 0.6115 | 0.8672 | 0.0841 | 0.6272 | 0.7645 |

## Outputs

- Predictions: `data/fuzzy/current_model_predictions_v0.parquet`
- Metrics: `reports/anfis/current_model_metrics.csv`
- Registry: `models/anfis/current_model_registry_v0.json`
- Manifest: `reports/anfis/current_model_manifest.json`
