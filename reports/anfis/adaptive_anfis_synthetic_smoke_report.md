# Adaptive ANFIS Synthetic Smoke Report

Generated at UTC: `2026-06-15T14:50:03.564404+00:00`

Status: `completed`

## Scope

This Gate 1 smoke uses synthetic data only. It checks that a small
trainable Gaussian-membership Sugeno ANFIS can learn bounded module
mappings before any real-data adaptive ANFIS claim is made.

## Configuration

- rows per module: `128`
- memberships per input: `3`
- epochs: `80`
- learning rate: `0.05`
- random seed: `1729`

## Module Metrics

| module | status | rows | input dim | rules | initial loss | final loss | relative improvement | output range | centers ordered | max parameter delta |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|
| `ANFIS-N` | `passed` | 128 | 3 | 27 | 0.0349 | 0.0003 | 0.9905 | `0.1556-0.8714` | `True` | 1.8301 |
| `ANFIS-F` | `passed` | 128 | 4 | 81 | 0.0263 | 0.0002 | 0.9924 | `0.1753-0.8323` | `True` | 1.6325 |
| `ANFIS-T` | `passed` | 128 | 2 | 9 | 0.0338 | 0.0004 | 0.9887 | `0.1658-0.8483` | `True` | 1.7140 |

## Gate Checks

- finite loss: `True`
- outputs in `[0, 1]`: `True`
- ordered centers: `True`
- parameter update observed: `True`
- loss improved: `True`

## Outputs

- Metrics: `reports/anfis/adaptive_anfis_synthetic_smoke_metrics.csv`
- Manifest: `reports/anfis/adaptive_anfis_synthetic_smoke_manifest.json`
