# MIFAL-ED/T2 Synthesis

This document closes the current MIFAL-ED/T2 block as a reproducible,
structurally separate comparator for `lentic-pipe`.

MIFAL-ED/T2 does not become the operational default. Its final role in the
current project state is to provide an interpretable eco-fuzzy comparator,
uncertainty-aware diagnostics, and controlled-degradation evidence under sparse
or weakened observations.

## Decision

MIFAL-ED/T2 is scientifically useful, but not predictively superior to the
adaptive PIPE/GRU-D benchmark on the matched `bloom_h` surface.

The block is closed with a negative predictive result and a positive diagnostic
result:

- negative predictive result: PIPE/GRU-D remains stronger than MIFAL for
  `bloom_h` on the held-out matched test surface;
- positive diagnostic result: MIFAL provides a transparent robustness lens under
  observable-evidence degradation;
- boundary: MIFAL does not emit `irc_alert`, so it must not be compared against
  PIPE or Neural ODE on that target.

## Completed Scope

The implemented MIFAL block includes:

- a public protocol in `docs/MIFAL_ED_T2_PROTOCOL.md`;
- a separate core implementation in `src/mifal/ed_t2.py`;
- an observable panel adapter in `src/mifal/panel_adapter.py`;
- availability auditing, isolated evaluation, validation-only calibration,
  matched-surface evaluation, MIFAL-vs-PIPE comparison, and controlled
  degradation runners;
- DVC separation for row-level MIFAL artifacts and Git-tracked lightweight
  reports/manifests.

The main controlled-degradation runner is
`src/experiments/evaluate_mifal_controlled_degradation.py`.

## Held-Out Predictive Evidence

The final held-out comparison used the PIPE-compatible reference surface:

```text
reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibrated_backtest_rows.parquet
```

The matched-surface evaluation produced 23,531 matched keys and 47,062 long
MIFAL rows across validation and test. The test comparison is for `bloom_h`
only.

| MIFAL surface | h1 PR-AUC | h2 PR-AUC | h3 PR-AUC | h1 F2 | h2 F2 | h3 F2 |
|---|---:|---:|---:|---:|---:|---:|
| current Chl-a | 0.6147 | 0.5416 | 0.4872 | 0.6338 | 0.5300 | 0.5218 |
| no-current Chl-a | 0.3608 | 0.3307 | 0.3218 | 0.5949 | 0.5922 | 0.5693 |

Against adaptive PIPE/GRU-D on the same matched test rows, current-Chl-a MIFAL
remained weaker:

| Horizon | Delta PR-AUC | Delta Brier | Delta F2 |
|---:|---:|---:|---:|
| 1 | -0.0258 | +0.0059 | -0.0721 |
| 2 | -0.0464 | +0.0102 | -0.1957 |
| 3 | -0.0721 | +0.0139 | -0.1996 |

No-current-Chl-a MIFAL was further behind in PR-AUC and Brier. This supports
the closure decision: MIFAL is a comparator, not a replacement for the learned
temporal models.

Primary evidence:

- `reports/mifal/mifal_observable_current_vs_no_current_pipe_grud_holdout_matched_report.md`
- `reports/mifal/mifal_vs_pipe_grud_bloom_holdout_comparison_report.md`

## Controlled-Degradation Evidence

The final degradation pass used `mifal_observable_core` on both observable
surfaces with fixed validation calibrators and fixed thresholds. Each core run
used 23,531 rows, 32 evaluated scenario/seed runs, 384 metric rows, 1,536
availability rows, and 160 examples.

The strongest stressors were:

- current Chl-a surface: Chl-a memory removal caused the largest ranking loss,
  reducing test PR-AUC to 0.2059/0.2043/0.2030 by horizons 1/2/3;
- current Chl-a surface: nutrient ablation reduced test F2 by
  -0.1618/-0.0478/-0.0728;
- no-current Chl-a surface: nutrient ablation was the dominant failure mode,
  reducing test F2 by -0.3400/-0.3366/-0.3315;
- severe MCAR 50% dropout materially degraded both surfaces;
- temporal block scenarios were milder than nutrient ablation or severe random
  dropout;
- site-retention scenarios should be interpreted as cohort/subset diagnostics
  because row mix and event prevalence change.

Light ablation was small on both surfaces. Physicochemical ablation sometimes
improved current-Chl-a F2, so this result should be treated as noisy-channel or
cohort-mix sensitivity, not as evidence that physicochemical variables are
ecologically irrelevant.

Primary evidence:

- `reports/degradation/mifal_controlled_degradation_current_chla_core_full_report.md`
- `reports/degradation/mifal_controlled_degradation_no_current_chla_core_full_report.md`

## Interpretation

The empirical story is coherent:

- when current biological evidence is available, MIFAL ranking improves, but it
  still trails PIPE/GRU-D on held-out `bloom_h`;
- when current Chl-a is withheld, MIFAL depends much more strongly on nutrient
  evidence, which is plausible for an early-warning surface;
- MIFAL intervals and reliability signals are useful for documenting degraded
  evidence, but wide intervals and weak discrimination are limitations, not
  wins;
- MIFAL should be kept as a parallel interpretability and stress-test pipeline,
  not promoted as the production alert model.

## Reporting Boundary

Future reports should state:

- MIFAL produced a valid negative predictive comparison against adaptive
  PIPE/GRU-D for `bloom_h`;
- MIFAL did not evaluate `irc_alert`;
- the main diagnostic contribution is controlled-degradation sensitivity under
  weakened observable evidence;
- better interval behavior must not be reported as superiority unless decision
  utility also improves.

## Next Project Step

With MIFAL closed, the next major doctoral block is counterfactual planning:
define defensible intervenable proxies, constraints, costs, and a minimal
search strategy over already-established predictive surfaces.
