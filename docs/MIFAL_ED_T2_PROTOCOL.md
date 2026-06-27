# MIFAL-ED/T2 Protocol

MIFAL-ED/T2 is the project parallel eco-fuzzy comparator for algal bloom risk
under sparse, stale, heterogeneous, or degraded observations. It does not
replace PIPE, adaptive ANFIS, GRU-D, or Neural ODE. Its value must be evaluated
empirically on a shared surface and reported even when it does not outperform
the learned models.

## Scientific Role

MIFAL-ED/T2 tests a different hypothesis from PIPE:

- learned temporal models should dominate when the data surface is rich enough;
- an interval type-2 fuzzy model may be less overconfident when observations are
  missing, old, indirect, or uncertain;
- its main possible contribution is robust uncertainty, interpretable ecological
  indices, and value-of-information guidance, not automatic global superiority.

The first empirical question is therefore not "does MIFAL beat PIPE?", but:

> On which data-quality regimes, if any, does MIFAL provide better calibrated or
> more useful risk under controlled degradation?

## Implementation Boundary

The public reference implementation lives in `src/mifal/ed_t2.py`.

It includes:

- interval type-2 membership footprints;
- reliability-aware fusion of multiple observations;
- bounded latent algal state dynamics;
- analysis-time assimilation of current biological observations;
- conservative risk, interval uncertainty, confidence, ecological indices, and
  value of information;
- interval metrics helpers for coverage and Winkler score.

The default parameters are ecological priors. They are not fitted constants and
must not be treated as calibrated model evidence.

## Current Panel Mapping

The current frozen monthly panel can populate only part of the MIFAL vocabulary:

| MIFAL variable | panel source | status | policy |
|---|---|---|---|
| `Tw` | `mean_temperature_C` | observable | direct |
| `TP` | `mean_TP_ugL` | observable | direct |
| `TN` | `mean_TN_ugL` | observable | divide by 1000 to mg/L |
| `Secchi` | `mean_secchi_depth_m` | observable | direct |
| `Turb` | `mean_turbidity_NTU` | observable | direct light support |
| `DOb` | `mean_DO_mgL` | qualified observable | not guaranteed bottom oxygen |
| `Chl` | `mean_chlorophyll_a_ugL` | observable | analysis observation |
| `Chl_prev` | previous-month `mean_chlorophyll_a_ugL` | constructible | one-month biological memory lag |
| `Wind` | none | unavailable | prior plus low reliability |
| `Residence` | none | unavailable | prior plus low reliability |
| `Flushing` | none | unavailable | prior plus low reliability |
| `Strat` | none | unavailable | prior plus low reliability |
| `Phyco` | none | unavailable | future extension |
| `Sat` | none | unavailable | future extension |
| `Visual` | none | unavailable | future extension |
| `Rain` | none | unavailable | future extension |
| `LandLoad` | none | unavailable | future extension |

Unavailable variables must enter as priors with zero or low reliability. They
must not be fabricated from unrelated columns.

Adapter observations are also filtered through the same physical bounds used by
the MIFAL core. Values outside those bounds are treated as unavailable
observations rather than clipped or allowed to abort large evaluations.

## Gate Sequence

### Gate 0: Input Availability Audit

Run `src/experiments/audit_mifal_inputs.py` against the frozen panel and
leakage-safe splits. This gate writes:

- `reports/mifal/mifal_input_audit_summary.csv`;
- `reports/mifal/mifal_input_audit_by_split.csv`;
- `reports/mifal/mifal_input_audit_by_source.csv`;
- `reports/mifal/mifal_input_audit_report.md`;
- `reports/mifal/mifal_input_audit_manifest.json`.

The audit determines whether a defensible observable MIFAL surface exists.

### Gate 1: Observable Adapter Smoke

Build a panel-to-MIFAL adapter that emits `Observation` payloads from origin
months only. The first version should support:

- full observable surface, including current origin-month Chl-a;
- no-current-Chl-a surface, where biological memory is degraded or removed;
- explicit reliability from QC rate, observation count, age, and source policy.

The public adapter lives in `src/mifal/panel_adapter.py`, and the isolated smoke
runner lives in `src/experiments/evaluate_mifal_observable.py`.

The smoke gate should run on bounded rows and report examples, indices,
intervals, and value-of-information output. It is still not a final comparison.

Current smoke artifact naming:

- `reports/mifal/mifal_observable_current_chla_smoke_report.md`;
- `reports/mifal/mifal_observable_no_current_chla_smoke_report.md`;
- matching `*_predictions.csv`, `*_metrics.csv`, `*_availability.csv`,
  `*_examples.csv`, and `*_manifest.json`.

The first smoke showed the expected conservative behavior: wide intervals, low
mean data reliability, and high recall at threshold 0.5 with many false
positives. This should be treated as a diagnostic result that motivates
validation calibration, not as final performance evidence.

### Gate 2: Validation Calibration

Calibrate on validation only:

- risk-to-bloom calibration, preferably isotonic if enough positive examples
  exist;
- alert thresholds for `bloom_h` and, when aligned, `irc_alert`;
- optional MIFAL parameters only with strong regularization and documented
  priors.

Test data must not be used for model or threshold selection.

The first public calibration runner is
`src/experiments/calibrate_mifal_observable_alerts.py`. It consumes the
isolated MIFAL observable predictions, fits per-horizon validation calibrators
as JSON artifacts, selects validation thresholds, and writes calibrated
predictions, metrics, a report, and a manifest. The runner intentionally refuses
non-validation calibration splits.

Current validation-smoke artifacts:

- `reports/mifal/mifal_observable_current_chla_validation_calibration_smoke_report.md`;
- `reports/mifal/mifal_observable_no_current_chla_validation_calibration_smoke_report.md`;
- matching `*_thresholds.csv`, `*_metrics.csv`,
  `*_calibrated_predictions.csv`, and `*_manifest.json`;
- JSON calibrators under `models/mifal/observable_calibrators/`.

The bounded validation smoke used 100 validation rows per horizon from each
surface. On the current-Chl-a surface, calibrated F2 by horizon was
0.5618/0.6410/0.5634 with PR-AUC 0.3986/0.2927/0.4291. On the no-current-Chl-a
surface, calibrated F2 was 0.5932/0.4911/0.5344 with PR-AUC
0.3601/0.1810/0.2494. These numbers are diagnostic only; they confirm the
calibration path and reduce the uncalibrated over-alerting in some horizons, but
they are not held-out performance evidence.

### Gate 3: Matched-Surface Evaluation

Evaluate MIFAL on the same origin/horizon/split surface used by the relevant
PIPE and baseline comparisons. Report:

- PR-AUC, ROC-AUC, Brier, F2, precision, recall, MCC;
- RMSE/MAE for continuous risk when appropriate;
- interval coverage, mean width, and Winkler score;
- reliability and uncertainty distributions;
- examples of dominant factors and recommended sampling.

The first matched-surface utility is
`src/experiments/evaluate_mifal_matched_surface.py`. It does not fit
calibrators or select thresholds. It only intersects already-calibrated MIFAL
prediction files by `source_id`, `site_id`, `origin_year_month`,
`horizon_months`, and `split`, with an optional reference rows table such as a
PIPE backtest export.

Current validation-smoke artifacts:

- `reports/mifal/mifal_observable_current_vs_no_current_matched_validation_smoke_report.md`;
- `reports/mifal/mifal_observable_current_vs_no_current_matched_pipe_grud_validation_smoke_report.md`;
- matching `*_matched_rows.csv`, `*_metrics.csv`, `*_comparison.csv`, and
  `*_manifest.json`.

The reference-aware observable runner can also evaluate MIFAL directly on a
PIPE-compatible validation surface by passing `--reference-rows` to
`src/experiments/evaluate_mifal_observable.py`. The first such run used adaptive
PIPE-GRU-D validation backtest rows and produced 9,391 matched `bloom_h` rows
across horizons. Surface-specific validation calibrations were then fitted with
`src/experiments/calibrate_mifal_observable_alerts.py`.

Current PIPE-compatible validation artifacts:

- `reports/mifal/mifal_observable_current_chla_pipe_grud_validation_report.md`;
- `reports/mifal/mifal_observable_no_current_chla_pipe_grud_validation_report.md`;
- `reports/mifal/mifal_observable_current_chla_pipe_grud_validation_calibration_report.md`;
- `reports/mifal/mifal_observable_no_current_chla_pipe_grud_validation_calibration_report.md`;
- `reports/mifal/mifal_observable_current_vs_no_current_pipe_grud_validation_matched_report.md`;
- `reports/mifal/mifal_vs_pipe_grud_bloom_validation_comparison_report.md`.

Artifact policy: row-level prediction exports, calibrated prediction exports,
and matched-row exports are DVC pointer-only artifacts. Lightweight reports,
metrics, thresholds, manifests, examples, and availability summaries remain
Git-trackable evidence. MIFAL calibrator JSON files live under `models/` and
are covered by the project-level `models.dvc` pointer.

The current-vs-no-current validation smoke matched 300 keys and 600 long
prediction rows. Relative to the no-current-Chl-a surface, the current-Chl-a
surface improved PR-AUC by 0.0385/0.1117/0.1796 and Brier by
-0.0033/-0.0117/-0.0206 for horizons 1/2/3. F2 changed by
-0.0314/0.1500/0.0290, showing a mixed precision-recall trade-off rather than
a uniform win. A reference-filtered smoke against adaptive PIPE-GRU-D validation
rows matched only 7 keys, all negatives, so it is only a feasibility check for
the matching machinery and must not be interpreted as a PIPE comparison.

On the PIPE-compatible validation surface, current-Chl-a MIFAL improved PR-AUC
over no-current-Chl-a MIFAL but had lower F2. Against adaptive PIPE-GRU-D
`bloom_h` validation metrics on the same row counts, both MIFAL surfaces were
weaker in PR-AUC, Brier, and F2 for all horizons. This is a valid negative
comparison result for `bloom_h`; it does not evaluate `irc_alert`, which MIFAL
does not emit.

After the validation policy was fixed, the same workflow was run on a
validation/test holdout surface using
`reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibrated_backtest_rows.parquet`
as reference. This produced 23,531 matched keys and 47,062 long MIFAL rows.
Current-Chl-a MIFAL remained the stronger MIFAL ranking surface, but adaptive
PIPE-GRU-D remained stronger for `bloom_h` on held-out test. Test deltas for
current-Chl-a MIFAL versus PIPE-GRU-D by horizon 1/2/3 were PR-AUC
-0.0258/-0.0464/-0.0721, Brier +0.0059/+0.0102/+0.0139, and F2
-0.0721/-0.1957/-0.1996. No-current-Chl-a MIFAL was further behind in PR-AUC
and Brier. This closes MIFAL as a valid, interpretable comparator with a
negative predictive result on the current `bloom_h` surface, while preserving it
for controlled-degradation analysis.

### Gate 4: Controlled Degradation

Repeat comparable degradation scenarios for MIFAL and PIPE. The key outcomes
are degradation slope, overconfidence, interval coverage, and operational
failure modes, not only peak predictive performance.

## Reporting Rules

- Do not claim MIFAL is superior globally.
- Do not compare against PIPE unless the origin/horizon/split surface is
  matched or the mismatch is explicitly stated.
- Report wide intervals as a limitation when they reduce decision usefulness.
- Treat better coverage with poor discrimination as a partial result, not a
  win.
- Keep MIFAL structurally separate from PIPE so that either model can fail
  without contaminating the other.
