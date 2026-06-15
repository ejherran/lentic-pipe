# Adaptive ANFIS v0 Audit And Protocol

Updated: 2026-06-15

This document starts the transition from the lightweight PIPE baseline to the
robust/adaptive PIPE layer. It audits the current fuzzy/ANFIS-labeled code
path and defines the first adaptive ANFIS protocol before any adaptive training
is implemented.

This is a protocol and gap analysis, not an adaptive ANFIS result report.

## Current Layer Audit

The repository already has a reproducible expert/refined fuzzy layer that acts
as PIPE Layer 1 for the lightweight comparison block.

Implemented components:

| Component | Evidence | Status |
|---|---|---|
| Expert membership functions | `src/fuzzy/expert.py`, `reports/anfis/memberships.csv` | deterministic expert rules |
| Modular substate outputs | `yN`, `yF`, `yT`, `sigma_N`, `sigma_F`, `sigma_T`, deltas in `data/fuzzy/state_vector_v0.parquet` | implemented |
| No-current-Chl-a variant | `yT_no_chla`, `sigma_T_no_chla`, `irc1_no_chla` | implemented for strict early-warning surfaces |
| IRC score | `compute_irc1`, `reports/anfis/irc1_metrics.csv` | implemented |
| Train-only IRC weight search | `reports/anfis/anfis_report.md`, `reports/anfis/irc1_weight_search.csv` | implemented for alpha/beta/gamma only |
| Isotonic calibration | `models/anfis/calibrators/`, `reports/anfis/irc1_calibrated_metrics.csv` | validation-calibrated |
| Refined fuzzy ensemble | `src/experiments/refine_expert_fuzzy.py`, `reports/anfis/refined_fuzzy_report.md` | validation-selected comparison layer |
| Frozen current model | `reports/anfis/current_model_report.md`, `reports/anfis/current_model_audit.md` | implemented |
| Operational scoring | `src/experiments/score_current_model.py`, `reports/anfis/operational_scores_report.md` | implemented |

What the current layer is:

- a deterministic expert fuzzy state builder;
- an empirical IRC-weight and calibration layer;
- a validation-selected refined score ensemble;
- a reproducible baseline for PIPE lightweight.

What the current layer is not:

- it does not learn membership-function parameters;
- it does not learn ANFIS consequents per rule;
- it does not optimize module-level `ANFIS-N`, `ANFIS-F`, or `ANFIS-T`;
- it does not produce an adaptive `S(t)` separate from the expert/refined
  state;
- it does not support a claim that adaptive ANFIS has been implemented.

## Gap To Adaptive ANFIS

The project specification requires a modular adaptive ANFIS layer with:

- `ANFIS-N` for nutrient pressure;
- `ANFIS-F` for physicochemical condition;
- `ANFIS-T` for thermal/biological favorability;
- propagated uncertainty and trend features;
- an adaptive state vector `S_adaptive(t)`;
- comparison against the expert/refined fuzzy state;
- downstream PIPE/GRU-D evaluation over the adaptive state.

The missing technical pieces are:

| Gap | Required artifact |
|---|---|
| Trainable memberships | membership parameter tables and model checkpoints |
| Rule consequents | learned per-rule linear or constant Sugeno consequents |
| Pseudo-label protocol | generated labels from expert substates, current risk, and future targets |
| Ecological constraints | monotonic/order penalties and post-training violation reports |
| Module losses | per-module supervised/anchor losses plus downstream bloom/IRC loss |
| Adaptive uncertainty | sigma outputs or uncertainty proxies tied to membership ambiguity, missingness, and residuals |
| Adaptive state export | `S_adaptive(t)` parquet, manifest, and report |
| Baseline comparison | expert/refined vs adaptive metrics on validation/test |
| PIPE integration | sequence build and PIPE/GRU-D retraining over adaptive state |

## Module Contracts

The first adaptive implementation should keep the same ecological semantics as
the expert state so downstream PIPE code can compare surfaces fairly.

| Module | Inputs | Output | High output means | Notes |
|---|---|---|---|---|
| `ANFIS-N` | `TP_ugL`, `TN_ugL`, `TN_TP_ratio` | `yN_adaptive`, `sigma_N_adaptive` | high nutrient pressure | preserve monotonic pressure for TP/TN except documented ratio regimes |
| `ANFIS-F` | `DO_mgL`, `pH`, `turbidity_NTU`, `secchi_depth_m` | `yF_adaptive`, `sigma_F_adaptive` | good physicochemical condition | IRC uses `1 - yF_adaptive` as risk contribution |
| `ANFIS-T` full | `temperature_C`, current Chl-a pressure | `yT_adaptive`, `sigma_T_adaptive` | high thermal/biological favorability | monitoring/nowcasting surface |
| `ANFIS-T` no-current | `temperature_C` plus optional season/evidence features | `yT_no_chla_adaptive`, `sigma_T_no_chla_adaptive` | favorability without current Chl-a | strict early-warning surface |

The adaptive state must retain the current PIPE interface:

```text
S_adaptive(t) =
[
  yN_adaptive,
  yF_adaptive,
  yT_adaptive,
  sigma_N_adaptive,
  sigma_F_adaptive,
  sigma_T_adaptive,
  delta_yN_adaptive,
  delta_yF_adaptive,
  delta_yT_adaptive
]
```

No-current exports must also provide adaptive counterparts for
`yT_no_chla`, `sigma_T_no_chla`, and `delta_yT_no_chla`.

## Initialization

Adaptive ANFIS should start conservatively from the expert fuzzy layer:

1. Use existing expert membership specifications from
   `reports/anfis/memberships.csv` as the default initialization.
2. Add optional fuzzy c-means initialization only after the expert-initialized
   smoke is stable.
3. Keep membership centers ordered after every update.
4. Keep widths positive with a softplus or lower-bound parameterization.
5. Clamp or transform outputs to `[0, 1]`.
6. Record initial and final membership tables for every run.

The first implementation should prefer small, auditable Gaussian or triangular
memberships over a large unconstrained rule base.

## Supervision

The adaptive layer should use three supervision sources, with train-only fitting
and validation-only selection:

| Supervision source | Use |
|---|---|
| Expert substates | pseudo-label anchors for `yN`, `yF`, `yT`, and no-current `yT` |
| Current Chl-a risk | direct monitoring signal for the full `ANFIS-T` and current IRC behavior |
| Future bloom/risk targets | downstream validation of whether adaptive `S(t)` improves forecast usefulness |

The first loss should be explicit and simple:

```text
L =
  lambda_anchor * MSE(y_module_adaptive, y_module_expert)
+ lambda_bloom  * BCE(bloom_h, bloom_probability_from_IRC_adaptive)
+ lambda_risk   * MSE(target_risk_chla_h, IRC_adaptive)
+ lambda_smooth * temporal_smoothness_penalty
+ lambda_order  * membership_order_penalty
+ lambda_prior  * parameter_drift_from_expert_initialization
```

The initial smoke can set `lambda_anchor` high so the model cannot drift far
from the interpretable expert baseline before the training loop is proven
stable.

## Validation Rules

The adaptive ANFIS protocol must preserve the repository's existing evaluation
discipline:

- train split fits membership and consequent parameters;
- validation split selects hyperparameters, thresholds, and accepted run;
- test split is report-only;
- no test metrics may influence architecture choice after the run;
- failures must be reported as `FAIL`, unstable, or no improvement rather than
  hidden.

## Evaluation Gates

Implement the adaptive layer in gates.

### Gate 0 - Static Audit

Deliverables:

- this protocol;
- inventory of current expert/refined artifacts;
- task updates marking only the protocol as complete.

### Gate 1 - Synthetic Smoke

Purpose: prove the adaptive implementation can learn a simple monotonic fuzzy
mapping without full data.

Required checks:

- finite loss;
- no NaN outputs;
- outputs in `[0, 1]`;
- ordered memberships after training;
- gradients update at least one membership or consequent parameter;
- deterministic run under a fixed seed.

### Gate 2 - Real Bounded Smoke

Purpose: run on a bounded real sample without claiming thesis-scale results.

Required checks:

- state rows align with the source panel/split sample;
- adaptive outputs are not constant;
- expert-anchor metrics are reported;
- bloom/risk validation metrics are computed;
- no-current and full surfaces are separated.

### Gate 3 - Full Adaptive State

Purpose: produce `S_adaptive(t)` as a new surface.

Required artifacts:

- adaptive state parquet, DVC pointer if heavy;
- adaptive model checkpoint(s), DVC pointer if binary;
- membership initial/final tables;
- module metrics;
- validation/test comparison against expert/refined fuzzy;
- manifest with code hashes, inputs, outputs, and random seed.

### Gate 4 - PIPE Re-evaluation

Purpose: compare PIPE lightweight against PIPE adaptive.

Required artifacts:

- sequence dataset built from `S_adaptive(t)`;
- PIPE/GRU-D training report over adaptive state;
- rollout backtests and 2B policy comparison;
- degradation protocol extension for adaptive state.

## Metrics

Module-level metrics:

- MSE/MAE versus expert pseudo-labels;
- Spearman correlation against expert substates;
- distribution shift of `yN`, `yF`, `yT`, and sigmas;
- monotonic/order violation counts;
- membership drift from initialization;
- source-level coverage and missingness bands.

Target-level metrics:

- PR-AUC, ROC-AUC, Brier, recall, macro-F1 for `bloom_h`;
- MAE/RMSE for `target_risk_chla_h`;
- calibration bins and top-decile lift;
- comparison against selected baselines and current refined fuzzy scores.

Downstream PIPE metrics:

- one-step state RMSE/MAE against persistence;
- rollout state RMSE/MAE by horizon;
- `bloom_h` and `irc_alert` PR-AUC, Brier, recall, precision, F2, MCC;
- policy-frontier behavior for fixed, F2, balanced, and `closest_pr` profiles.

## Recommended Artifact Names

Avoid overwriting the existing expert/refined fuzzy artifacts.

Suggested new paths:

| Artifact | Path |
|---|---|
| adaptive state | `data/fuzzy/adaptive_state_vector_v0.parquet` |
| adaptive report | `reports/anfis/adaptive_anfis_report.md` |
| adaptive manifest | `reports/anfis/adaptive_anfis_manifest.json` |
| adaptive module metrics | `reports/anfis/adaptive_anfis_module_metrics.csv` |
| adaptive target metrics | `reports/anfis/adaptive_anfis_target_metrics.csv` |
| initial memberships | `reports/anfis/adaptive_anfis_memberships_initial.csv` |
| final memberships | `reports/anfis/adaptive_anfis_memberships_final.csv` |
| model checkpoints | `models/anfis/adaptive/` |
| synthetic smoke report | `reports/anfis/adaptive_anfis_synthetic_smoke_report.md` |

If any adaptive state, checkpoint, or row-level output is large, it must be
managed through DVC pointers rather than committed as a Git blob.

## First Implementation Slice

The first code slice should be deliberately small:

1. add a lightweight adaptive ANFIS module with trainable Gaussian membership
   centers, positive widths, normalized firing strengths, and Sugeno-style
   consequents;
2. add synthetic tests for monotonic learning, output ranges, membership order,
   and deterministic seed behavior;
3. add a synthetic smoke runner that writes report and manifest artifacts;
4. only after that smoke passes, add bounded real-data training.

This sequence keeps adaptive ANFIS from contaminating the already closed PIPE
lightweight baseline.

## Claims Allowed After This Protocol

- The repository contains a documented expert/refined fuzzy baseline for PIPE
  Layer 1.
- The adaptive ANFIS implementation gap is now explicitly mapped.
- The next implementation can proceed through synthetic and real bounded
  gates without overwriting existing PIPE lightweight artifacts.

## Claims Not Allowed Yet

- Do not claim adaptive ANFIS has been implemented.
- Do not claim learned memberships or learned consequents exist.
- Do not claim adaptive ANFIS improves PIPE until validation/test comparisons
  and downstream PIPE re-evaluation exist.
- Do not claim ANFIS failure or success before the required gates are run.
