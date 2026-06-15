# Adaptive ANFIS Real-Data Smoke Report

Generated at UTC: `2026-06-15T15:04:13.547617+00:00`

Status: `completed`

## Scope

This Gate 2 smoke trains bounded adaptive ANFIS modules on a sampled
real-data slice using expert fuzzy substates as pseudo-label anchors.
It does not produce the full adaptive state vector and must not be used
as a thesis-scale adaptive PIPE result.

## Configuration

- sampled rows per split/horizon: `256`
- train rows per module: `256`
- memberships per input: `3`
- epochs: `40`
- learning rate: `0.03`
- random seed: `1729`

## Alignment

- sampled split rows: `2,304`
- state matched rows: `2,304`
- panel matched rows: `2,304`
- state missing rows: `0`
- panel missing rows: `0`

## Module Anchor Metrics

| module | status | train rows | eval rows | final loss | anchor MAE | anchor RMSE | Spearman | output std | ordered |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `ANFIS-N` | `passed` | 256 | 2,304 | 0.0007 | 0.0316 | 0.0674 | 0.8830 | 0.1475 | `True` |
| `ANFIS-F` | `passed` | 256 | 2,304 | 0.0014 | 0.0250 | 0.0571 | 0.9598 | 0.1880 | `True` |
| `ANFIS-T` | `passed` | 256 | 2,304 | 0.0183 | 0.1170 | 0.1353 | 0.9564 | 0.2889 | `True` |
| `ANFIS-T-no-current` | `passed` | 256 | 2,304 | 0.0049 | 0.0246 | 0.0663 | 0.9996 | 0.1262 | `True` |

## Validation Target Metrics

| score | horizon | rows | PR-AUC | ROC-AUC | Brier | recall | macro-F1 | risk RMSE | risk MAE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `irc1_adaptive` | 1 | 256 | 0.3504 | 0.7979 | 0.1884 | 0.7407 | 0.6555 | 0.3234 | 0.2915 |
| `irc1_adaptive` | 2 | 256 | 0.4493 | 0.8852 | 0.1899 | 0.8929 | 0.6742 | 0.3360 | 0.3064 |
| `irc1_adaptive` | 3 | 256 | 0.4494 | 0.7983 | 0.1874 | 0.6667 | 0.6884 | 0.3557 | 0.3222 |
| `irc1_no_chla_adaptive` | 1 | 256 | 0.2662 | 0.6791 | 0.2365 | 0.3704 | 0.5964 | 0.3850 | 0.3500 |
| `irc1_no_chla_adaptive` | 2 | 256 | 0.1726 | 0.6067 | 0.2391 | 0.2500 | 0.5596 | 0.4022 | 0.3680 |
| `irc1_no_chla_adaptive` | 3 | 256 | 0.2270 | 0.5626 | 0.2391 | 0.2222 | 0.5714 | 0.4117 | 0.3782 |

## Gate Checks

- split/state/panel alignment: `True`
- adaptive outputs are non-constant: `True`
- expert-anchor metrics written: `True`
- validation target metrics written: `True`
- full and no-current surfaces separated: `True`

## Outputs

- Module metrics: `reports/anfis/adaptive_anfis_real_smoke_module_metrics.csv`
- Target metrics: `reports/anfis/adaptive_anfis_real_smoke_target_metrics.csv`
- Prediction sample: `reports/anfis/adaptive_anfis_real_smoke_predictions.csv`
- Initial memberships: `reports/anfis/adaptive_anfis_real_smoke_memberships_initial.csv`
- Final memberships: `reports/anfis/adaptive_anfis_real_smoke_memberships_final.csv`
- Manifest: `reports/anfis/adaptive_anfis_real_smoke_manifest.json`
