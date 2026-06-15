# Adaptive ANFIS State Report

Generated at UTC: `2026-06-15T15:36:32.801358+00:00`

Status: `completed`

## Scope

This Gate 3 builder trains adaptive ANFIS modules and exports an
`S_adaptive(t)` state surface. The exported parquet and checkpoints are
heavy/model artifacts and should be promoted through DVC after review.

## Configuration

- source ids: `wqp`
- max train rows per module: `4096`
- max export rows: `all`
- max train missing fraction: `0.5`
- center constraint: `unit`
- memberships per input: `3`
- epochs: `60`
- learning rate: `0.03`
- random seed: `1729`

## Alignment

- source state rows: `1,626,672`
- panel matched rows: `1,626,672`
- panel missing rows: `0`
- exported adaptive rows: `1,626,672`
- evaluation matched rows: `1,486,824`
- evaluation missing rows: `0`

## Training Module Metrics

| module | status | train rows | final loss | anchor MAE | Spearman | output std | missing fraction |
|---|---|---:|---:|---:|---:|---:|---:|
| `ANFIS-N` | `passed` | 4,096 | 0.0036 | 0.0682 | 0.9907 | 0.1315 | 0.7901 |
| `ANFIS-F` | `passed` | 4,096 | 0.0019 | 0.0971 | 0.9339 | 0.2107 | 0.5100 |
| `ANFIS-T` | `passed` | 4,096 | 0.0120 | 0.0925 | 0.9481 | 0.3099 | 0.2710 |
| `ANFIS-T-no-current` | `passed` | 4,096 | 0.0151 | 0.0610 | 0.9976 | 0.2413 | 0.4608 |

## Export Anchor Metrics

| module | rows | anchor MAE | anchor RMSE | Spearman | output std |
|---|---:|---:|---:|---:|---:|
| `ANFIS-N` | 1,626,672 | 0.0587 | 0.0966 | 0.9880 | 0.1272 |
| `ANFIS-F` | 1,626,672 | 0.1052 | 0.1449 | 0.8975 | 0.2048 |
| `ANFIS-T` | 1,626,672 | 0.0917 | 0.1107 | 0.9631 | 0.2618 |
| `ANFIS-T-no-current` | 1,626,672 | 0.0607 | 0.0915 | 0.9974 | 0.2382 |

## Validation Target Metrics

| score | horizon | rows | PR-AUC | ROC-AUC | Brier | recall | macro-F1 | risk RMSE | risk MAE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc1_adaptive` | 1 | 52,222 | 0.5797 | 0.8773 | 0.1754 | 0.8524 | 0.6956 | 0.3130 | 0.2782 |
| `irc1_adaptive` | 2 | 47,050 | 0.5238 | 0.8363 | 0.1787 | 0.7726 | 0.6810 | 0.3267 | 0.2883 |
| `irc1_adaptive` | 3 | 41,154 | 0.4983 | 0.8119 | 0.1797 | 0.7180 | 0.6709 | 0.3353 | 0.2948 |
| `irc1_no_chla_adaptive` | 1 | 52,222 | 0.4212 | 0.7966 | 0.2175 | 0.8277 | 0.6027 | 0.3674 | 0.3311 |
| `irc1_no_chla_adaptive` | 2 | 47,050 | 0.3789 | 0.7581 | 0.2174 | 0.7621 | 0.5975 | 0.3718 | 0.3337 |
| `irc1_no_chla_adaptive` | 3 | 41,154 | 0.3594 | 0.7254 | 0.2165 | 0.7036 | 0.5946 | 0.3761 | 0.3367 |

## Outputs

- Adaptive state: `data/fuzzy/adaptive_state_vector_v0.parquet`
- Model checkpoints: `models/anfis/adaptive`
- Module metrics: `reports/anfis/adaptive_anfis_state_module_metrics.csv`
- Target metrics: `reports/anfis/adaptive_anfis_state_target_metrics.csv`
- Coverage metrics: `reports/anfis/adaptive_anfis_state_coverage.csv`
- Initial memberships: `reports/anfis/adaptive_anfis_memberships_initial.csv`
- Final memberships: `reports/anfis/adaptive_anfis_memberships_final.csv`
- Manifest: `reports/anfis/adaptive_anfis_state_manifest.json`
