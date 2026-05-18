# PIPE/GRU-D Rollout Iteration 1

This note freezes the first reproducible iteration of recursive PIPE/GRU-D
rollouts and alert backtesting.

## Scope

Iteration 1 adds two related but distinct outputs:

- an operational rollout artifact over the latest eligible source-scoped sites;
- a historical rollout backtest over observed test futures.

The operational artifact is useful for ranking simulated future alert states.
The backtest is the evidence-bearing result because it compares recursive
rollouts against observed future fuzzy states.

## Reproduction Commands

Operational rollout:

```bash
poetry run python src/experiments/rollout_pipe_grud.py --samples 64 --batch-size 256
```

Historical backtest:

```bash
poetry run python src/experiments/evaluate_pipe_grud_rollouts.py --split test --samples 128 --batch-size 256
```

The backtest manifest records:

- selected origins: 13,327;
- evaluated rollout rows: 39,981;
- history length: 12 months;
- rollout horizons: 1, 2, and 3 months;
- samples per origin: 128;
- random seed: 1729.

## Main Results

State rollout RMSE improved over persistence at all evaluated horizons.

| Horizon | PIPE RMSE | Persistence RMSE | Relative improvement |
|---:|---:|---:|---:|
| 1 | 0.1341 | 0.1792 | 0.2518 |
| 2 | 0.1475 | 0.1796 | 0.1788 |
| 3 | 0.1543 | 0.1886 | 0.1821 |

IRC rollout RMSE also improved over persistence.

| Horizon | PIPE IRC RMSE | Persistence IRC RMSE | Relative improvement |
|---:|---:|---:|---:|
| 1 | 0.1415 | 0.1627 | 0.1304 |
| 2 | 0.1624 | 0.1992 | 0.1849 |
| 3 | 0.1717 | 0.2237 | 0.2326 |

IRC alert discrimination remained strong across horizons.

| Horizon | PR-AUC | ROC-AUC | Recall | Macro-F1 |
|---:|---:|---:|---:|---:|
| 1 | 0.8894 | 0.9351 | 0.7826 | 0.8577 |
| 2 | 0.8769 | 0.9239 | 0.7244 | 0.8354 |
| 3 | 0.8702 | 0.9191 | 0.6853 | 0.8211 |

Bloom alert ranking retained useful signal, but the current binary thresholds
are too conservative for an early-warning use case.

| Horizon | Bloom positive rate | Predicted positive rate | Recall | PR-AUC | ROC-AUC |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.1243 | 0.1120 | 0.6083 | 0.6737 | 0.9297 |
| 2 | 0.1298 | 0.0613 | 0.3543 | 0.6366 | 0.9160 |
| 3 | 0.1335 | 0.0519 | 0.2880 | 0.6106 | 0.9066 |

## Interpretation

Iteration 1 supports the PIPE/GRU-D rollout as a useful probabilistic temporal
model for fuzzy state dynamics and IRC alert ranking. It should not yet be
presented as a final bloom alert system.

The key limitation is not absence of signal. The backtest shows high ROC-AUC
for bloom targets, especially at horizons 1 and 2. The current decision
thresholds, however, suppress positives too aggressively and reduce recall at
longer horizons.

## Known Limitations

- LakeBeD has too few test rows to support source-level conclusions.
- WQP is the most difficult source and drives much of the long-horizon alert
  degradation.
- The model tends to smooth abrupt future IRC jumps, producing some severe
  false negatives.
- The current bloom probabilities use existing IRC calibrators rather than a
  calibrator fitted specifically to rollout-derived IRC values.

## Iteration 2 Direction

The next iteration should improve alert decision quality before retraining the
PIPE/GRU-D model:

1. Select horizon-specific thresholds with explicit recall or F-beta targets.
2. Fit rollout-specific calibrators from simulated IRC to observed `bloom_h`.
3. Re-evaluate the calibrated rollout alerts on validation and test splits.
4. Only then decide whether a heavier PIPE/GRU-D retraining cycle is warranted.

## Artifacts

Git-tracked code and tests:

- `src/experiments/rollout_pipe_grud.py`
- `src/experiments/evaluate_pipe_grud_rollouts.py`
- `tests/test_rollout_pipe_grud.py`
- `tests/test_evaluate_pipe_grud_rollouts.py`

DVC-tracked heavy artifact:

- `data/pipe_grud/pipe_rollout_alerts_v0.parquet`
- `data/pipe_grud/pipe_rollout_alerts_v0.parquet.dvc`

Small reports kept in Git:

- `reports/pipe_grud/pipe_rollout_alert_report.md`
- `reports/pipe_grud/pipe_rollout_alert_summary.csv`
- `reports/pipe_grud/pipe_rollout_top_alerts.csv`
- `reports/pipe_grud/pipe_rollout_recent_top_alerts.csv`
- `reports/pipe_grud/pipe_rollout_alert_manifest.json`
- `reports/pipe_grud/pipe_rollout_backtest_report.md`
- `reports/pipe_grud/pipe_rollout_backtest_metrics.csv`
- `reports/pipe_grud/pipe_rollout_backtest_alert_metrics.csv`
- `reports/pipe_grud/pipe_rollout_backtest_examples.csv`
- `reports/pipe_grud/pipe_rollout_backtest_manifest.json`
