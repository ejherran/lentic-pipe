# Current Model Audit Report v0

Generated at UTC: `2026-05-16T22:31:30.184922+00:00`

## Scope

This audit reviews the frozen `current_refined_fuzzy_v0` predictions.
It does not retrain, reselect, or alter model outputs.

## Headline Test Metrics

| horizon | rows | PR-AUC | ROC-AUC | Brier | recall | macro-F1 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 121,540 | 0.7117 | 0.9207 | 0.0643 | 0.6674 | 0.8136 |
| 2 | 115,691 | 0.5978 | 0.8804 | 0.0817 | 0.6405 | 0.7715 |
| 3 | 99,670 | 0.6115 | 0.8672 | 0.0841 | 0.6272 | 0.7645 |

## Calibration Summary

| horizon | rows | expected blooms | observed blooms | weighted abs error | max bin abs error |
|---:|---:|---:|---:|---:|---:|
| 1 | 121,540 | 16,231.0960 | 16,737 | 0.0104 | 0.0729 |
| 2 | 115,691 | 15,578.4352 | 16,765 | 0.0104 | 0.1706 |
| 3 | 99,670 | 13,993.8884 | 14,639 | 0.0185 | 0.1299 |

## Top Decile Lift

| horizon | rows | bloom rate | base rate | lift | capture rate | min probability |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 12,154 | 0.7537 | 0.1377 | 5.4729 | 0.5473 | 0.5288 |
| 2 | 11,570 | 0.6625 | 0.1449 | 4.5717 | 0.4572 | 0.5664 |
| 3 | 9,967 | 0.6789 | 0.1469 | 4.6226 | 0.4623 | 0.4395 |

## Evidence Band Test Metrics

| evidence group | band | horizon | rows | PR-AUC | Brier | recall | macro-F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| `exogenous_evidence_band` | `high` | 1 | 23,469 | 0.7325 | 0.0911 | 0.6941 | 0.8065 |
| `exogenous_evidence_band` | `low` | 1 | 7,056 | 0.6792 | 0.0567 | 0.6323 | 0.8005 |
| `exogenous_evidence_band` | `medium` | 1 | 24,354 | 0.7913 | 0.0535 | 0.6779 | 0.8396 |
| `exogenous_evidence_band` | `missing` | 1 | 66,661 | 0.6681 | 0.0595 | 0.6500 | 0.8046 |
| `exogenous_evidence_band` | `high` | 2 | 21,923 | 0.6503 | 0.1211 | 0.6418 | 0.7641 |
| `exogenous_evidence_band` | `low` | 2 | 5,846 | 0.5926 | 0.0768 | 0.5542 | 0.7638 |
| `exogenous_evidence_band` | `medium` | 2 | 22,454 | 0.7156 | 0.0721 | 0.7179 | 0.8004 |
| `exogenous_evidence_band` | `missing` | 2 | 65,468 | 0.4981 | 0.0722 | 0.6161 | 0.7588 |
| `exogenous_evidence_band` | `high` | 3 | 19,918 | 0.6480 | 0.1161 | 0.6567 | 0.7601 |
| `exogenous_evidence_band` | `low` | 3 | 3,868 | 0.4931 | 0.0871 | 0.4889 | 0.7142 |
| `exogenous_evidence_band` | `medium` | 3 | 19,798 | 0.7143 | 0.0772 | 0.6832 | 0.8004 |
| `exogenous_evidence_band` | `missing` | 3 | 56,086 | 0.5373 | 0.0751 | 0.5925 | 0.7490 |
| `full_evidence_band` | `high` | 1 | 22,819 | 0.7360 | 0.0913 | 0.7047 | 0.8088 |
| `full_evidence_band` | `low` | 1 | 69,569 | 0.6656 | 0.0593 | 0.6421 | 0.8029 |
| `full_evidence_band` | `medium` | 1 | 29,106 | 0.7723 | 0.0549 | 0.6743 | 0.8335 |
| `full_evidence_band` | `missing` | 1 | 46 | 0.1578 | 0.0892 | 0.3333 | 0.5512 |
| `full_evidence_band` | `high` | 2 | 21,197 | 0.6594 | 0.1216 | 0.6597 | 0.7681 |
| `full_evidence_band` | `low` | 2 | 68,195 | 0.4978 | 0.0725 | 0.6064 | 0.7572 |
| `full_evidence_band` | `medium` | 2 | 26,238 | 0.6993 | 0.0736 | 0.6891 | 0.7935 |
| `full_evidence_band` | `missing` | 2 | 61 | 0.0000 | 0.0054 | 0.0000 | 1.0000 |
| `full_evidence_band` | `high` | 3 | 19,176 | 0.6626 | 0.1200 | 0.6758 | 0.7636 |
| `full_evidence_band` | `low` | 3 | 58,207 | 0.5342 | 0.0751 | 0.5821 | 0.7468 |
| `full_evidence_band` | `medium` | 3 | 22,214 | 0.6818 | 0.0768 | 0.6568 | 0.7883 |
| `full_evidence_band` | `missing` | 3 | 73 | 0.2167 | 0.0650 | 1.0000 | 0.6656 |

## Limitations

- LakeBeD test and validation support is small compared with AquaMatch and WQP; source-level metrics for LakeBeD are high variance.
- `source_selector` is selected from validation and should be re-audited after adding new data sources.
- Error examples are high-confidence false positives and low-confidence false negatives, not causal explanations.

## Outputs

- Calibration bins: `reports/anfis/current_model_calibration_bins.csv`
- Lift table: `reports/anfis/current_model_lift_table.csv`
- Confusion by group: `reports/anfis/current_model_confusion_by_group.csv`
- Error examples: `reports/anfis/current_model_error_examples.csv`
- Manifest: `reports/anfis/current_model_audit_manifest.json`
