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

Implementation path:

- builder: `src/experiments/build_adaptive_anfis_state.py`;
- tests: `tests/test_adaptive_anfis_real_smoke.py`;
- default adaptive state:
  `data/fuzzy/adaptive_state_vector_v0.parquet`;
- default checkpoints: `models/anfis/adaptive/`;
- default report: `reports/anfis/adaptive_anfis_state_report.md`;
- default manifest: `reports/anfis/adaptive_anfis_state_manifest.json`;
- default module metrics:
  `reports/anfis/adaptive_anfis_state_module_metrics.csv`;
- default target metrics:
  `reports/anfis/adaptive_anfis_state_target_metrics.csv`;
- default coverage diagnostics:
  `reports/anfis/adaptive_anfis_state_coverage.csv`;
- default memberships:
  `reports/anfis/adaptive_anfis_memberships_initial.csv` and
  `reports/anfis/adaptive_anfis_memberships_final.csv`.

The Gate 3 builder adds two refinements motivated by Gate 2:

- coverage-aware training through `--max-train-missing-fraction`;
- unit-constrained ordered centers through `--center-constraint unit`.

Initial WQP-focused diagnostic command:

```bash
poetry run python src/experiments/build_adaptive_anfis_state.py \
  --source-ids wqp \
  --train-rows-per-module 4096 \
  --max-export-rows 50000 \
  --epochs 60 \
  --center-constraint unit \
  --max-train-missing-fraction 0.5
```

This command is still a bounded diagnostic. A full Gate 3 export should remove
`--max-export-rows` only after reviewing the bounded WQP-focused report and
deciding whether the missingness and target metrics are stable enough.

## Gate 3 WQP-Focused Bounded Diagnostic Snapshot

The first bounded Gate 3 WQP-focused diagnostic completed successfully on
2026-06-15.

Command:

```bash
poetry run python src/experiments/build_adaptive_anfis_state.py \
  --source-ids wqp \
  --train-rows-per-module 4096 \
  --max-export-rows 50000 \
  --epochs 60 \
  --center-constraint unit \
  --max-train-missing-fraction 0.5
```

Artifacts:

- adaptive state:
  `data/fuzzy/adaptive_state_vector_v0.parquet`;
- checkpoints: `models/anfis/adaptive/`;
- report:
  `reports/anfis/adaptive_anfis_state_report.md`;
- manifest:
  `reports/anfis/adaptive_anfis_state_manifest.json`;
- module metrics:
  `reports/anfis/adaptive_anfis_state_module_metrics.csv`;
- target metrics:
  `reports/anfis/adaptive_anfis_state_target_metrics.csv`;
- coverage diagnostics:
  `reports/anfis/adaptive_anfis_state_coverage.csv`;
- memberships:
  `reports/anfis/adaptive_anfis_memberships_initial.csv` and
  `reports/anfis/adaptive_anfis_memberships_final.csv`.

Configuration and alignment:

- source: `wqp`;
- source state rows: `1,626,672`;
- panel matched rows: `1,626,672`;
- panel missing rows: `0`;
- exported adaptive rows: `50,000`;
- evaluation matched rows: `45,435`;
- evaluation missing rows: `1,441,389`.

The large number of evaluation missing rows is expected for this diagnostic
because `--max-export-rows 50000` exports only a bounded sample of the WQP
state. These target metrics should therefore be read as sample diagnostics, not
as full Gate 3 validation.

Training module metrics:

| module | final loss | anchor MAE | Spearman | output std | missing fraction |
|---|---:|---:|---:|---:|---:|
| `ANFIS-N` | 0.0036 | 0.0682 | 0.9907 | 0.1315 | 0.7901 |
| `ANFIS-F` | 0.0019 | 0.0971 | 0.9339 | 0.2107 | 0.5100 |
| `ANFIS-T` | 0.0120 | 0.0925 | 0.9481 | 0.3099 | 0.2710 |
| `ANFIS-T-no-current` | 0.0151 | 0.0610 | 0.9976 | 0.2413 | 0.4608 |

Export anchor metrics:

| module | rows | anchor MAE | anchor RMSE | Spearman | output std |
|---|---:|---:|---:|---:|---:|
| `ANFIS-N` | 50,000 | 0.0587 | 0.0966 | 0.9869 | 0.1262 |
| `ANFIS-F` | 50,000 | 0.1049 | 0.1447 | 0.8993 | 0.2048 |
| `ANFIS-T` | 50,000 | 0.0921 | 0.1111 | 0.9632 | 0.2616 |
| `ANFIS-T-no-current` | 50,000 | 0.0607 | 0.0914 | 0.9974 | 0.2379 |

Validation diagnostic metrics:

| score | horizon | PR-AUC | ROC-AUC | Brier | recall | macro-F1 | risk RMSE |
|---|---:|---:|---:|---:|---:|---:|---:|
| `irc1_adaptive` | 1 | 0.5624 | 0.8661 | 0.1816 | 0.8543 | 0.6842 | 0.3121 |
| `irc1_adaptive` | 2 | 0.5234 | 0.8313 | 0.1843 | 0.8008 | 0.6834 | 0.3271 |
| `irc1_adaptive` | 3 | 0.5378 | 0.8326 | 0.1776 | 0.7489 | 0.6885 | 0.3353 |
| `irc1_no_chla_adaptive` | 1 | 0.4227 | 0.7777 | 0.2214 | 0.7953 | 0.5810 | 0.3654 |
| `irc1_no_chla_adaptive` | 2 | 0.3778 | 0.7324 | 0.2245 | 0.7415 | 0.5770 | 0.3766 |
| `irc1_no_chla_adaptive` | 3 | 0.4201 | 0.7526 | 0.2133 | 0.7265 | 0.6030 | 0.3767 |

Interpretation:

- Gate 3 bounded WQP-focused execution is mechanically healthy.
- Unit-constrained centers kept all final centers within `[0, 1]`.
- Full `irc1_adaptive` has mixed target behavior against expert `irc1`: lower
  PR-AUC/risk RMSE than expert IRC in this bounded sample, but stronger
  macro-F1.
- No-current `irc1_no_chla_adaptive` improves over expert `irc1_no_chla` on
  validation PR-AUC, ROC-AUC, Brier, macro-F1, and risk error in this bounded
  sample.
- A full WQP export without `--max-export-rows` is the next required step
  before accepting `S_adaptive(t)` as a retained Gate 3 artifact.

## Gate 3 WQP-Focused Full Export Snapshot

The full WQP-focused Gate 3 export completed successfully on 2026-06-15.

Command:

```bash
poetry run python src/experiments/build_adaptive_anfis_state.py \
  --source-ids wqp \
  --train-rows-per-module 4096 \
  --epochs 60 \
  --center-constraint unit \
  --max-train-missing-fraction 0.5
```

Configuration and alignment:

- source: `wqp`;
- source state rows: `1,626,672`;
- panel matched rows: `1,626,672`;
- panel missing rows: `0`;
- exported adaptive rows: `1,626,672`;
- evaluation matched rows: `1,486,824`;
- evaluation missing rows: `0`;
- adaptive state size: about `49 MB`;
- checkpoints directory size: about `20 KB`.

Export anchor metrics:

| module | rows | anchor MAE | anchor RMSE | Spearman | output std |
|---|---:|---:|---:|---:|---:|
| `ANFIS-N` | 1,626,672 | 0.0587 | 0.0966 | 0.9880 | 0.1272 |
| `ANFIS-F` | 1,626,672 | 0.1052 | 0.1449 | 0.8975 | 0.2048 |
| `ANFIS-T` | 1,626,672 | 0.0917 | 0.1107 | 0.9631 | 0.2618 |
| `ANFIS-T-no-current` | 1,626,672 | 0.0607 | 0.0915 | 0.9974 | 0.2382 |

Validation target metrics for full adaptive IRC:

| score | horizon | PR-AUC | ROC-AUC | Brier | recall | macro-F1 | risk RMSE |
|---|---:|---:|---:|---:|---:|---:|---:|
| `irc1_adaptive` | 1 | 0.5797 | 0.8773 | 0.1754 | 0.8524 | 0.6956 | 0.3130 |
| `irc1_adaptive` | 2 | 0.5238 | 0.8363 | 0.1787 | 0.7726 | 0.6810 | 0.3267 |
| `irc1_adaptive` | 3 | 0.4983 | 0.8119 | 0.1797 | 0.7180 | 0.6709 | 0.3353 |

Validation target metrics for adaptive no-current IRC:

| score | horizon | PR-AUC | ROC-AUC | Brier | recall | macro-F1 | risk RMSE |
|---|---:|---:|---:|---:|---:|---:|---:|
| `irc1_no_chla_adaptive` | 1 | 0.4212 | 0.7966 | 0.2175 | 0.8277 | 0.6027 | 0.3674 |
| `irc1_no_chla_adaptive` | 2 | 0.3789 | 0.7581 | 0.2174 | 0.7621 | 0.5975 | 0.3718 |
| `irc1_no_chla_adaptive` | 3 | 0.3594 | 0.7254 | 0.2165 | 0.7036 | 0.5946 | 0.3761 |

Interpretation:

- Gate 3 WQP-focused full export is accepted as a retained adaptive-state
  surface for the next PIPE-adaptive step.
- The no-current adaptive IRC improves over expert `irc1_no_chla` on
  validation PR-AUC, ROC-AUC, Brier, macro-F1, and risk RMSE/MAE.
- The full Chl-a-aware adaptive IRC remains mixed against expert `irc1`: it
  improves macro-F1 and slightly improves Brier in validation, but loses
  PR-AUC and risk RMSE/MAE. It should therefore be treated as an adaptive
  comparison surface, not as a replacement for the expert full surface.
- The adaptive state parquet and checkpoints must be promoted through DVC
  rather than committed as Git blobs.

### Gate 4 - PIPE Re-evaluation

Purpose: compare PIPE lightweight against PIPE adaptive.

Required artifacts:

- sequence dataset built from `S_adaptive(t)`;
- PIPE/GRU-D training report over adaptive state;
- rollout backtests and 2B policy comparison;
- degradation protocol extension for adaptive state.

Implementation path:

- sequence builder: `src/experiments/build_pipe_sequences.py`;
- input surfaces:
  - `adaptive` maps trained ANFIS columns such as `yN_adaptive`,
    `sigma_N_adaptive`, and `delta_yN_adaptive` into the canonical PIPE
    sequence schema;
  - `adaptive_no_current_chla` uses adaptive no-current thermal inputs while
    keeping full adaptive next-state targets;
- tests: `tests/test_build_pipe_sequences.py`.

Initial WQP-focused adaptive sequence command:

```bash
poetry run python src/experiments/build_pipe_sequences.py \
  --state data/fuzzy/adaptive_state_vector_v0.parquet \
  --input-surface adaptive \
  --source-ids wqp \
  --sequences data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet \
  --summary reports/pipe_grud/adaptive_wqp_focused/pipe_sequence_summary.csv \
  --discarded reports/pipe_grud/adaptive_wqp_focused/pipe_sequence_discarded_summary.csv \
  --report reports/pipe_grud/adaptive_wqp_focused/pipe_sequence_report.md \
  --manifest reports/pipe_grud/adaptive_wqp_focused/pipe_sequence_manifest.json
```

This command should be reviewed before training. The expected first decision is
whether the adaptive sequence row counts match the WQP-focused expert/no-current
sequence geometry closely enough to support a fair PIPE-GRU-D comparison.

### Gate 4 WQP-Focused Adaptive Sequence Snapshot

The WQP-focused adaptive sequence build completed successfully on 2026-06-15.

Artifacts:

- sequence dataset:
  `data/pipe_grud/pipe_sequence_dataset_adaptive_wqp_focused_v0.parquet`;
- report:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_sequence_report.md`;
- manifest:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_sequence_manifest.json`;
- summary:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_sequence_summary.csv`;
- discarded summary:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_sequence_discarded_summary.csv`.

Geometry:

- candidate state rows: `1,626,672`;
- kept sequence rows: `986,674`;
- discarded candidate rows: `639,998`;
- source-scoped sites kept: `43,715`;
- train rows/sites: `808,970` / `38,508`;
- validation rows/sites: `91,226` / `11,283`;
- test rows/sites: `86,478` / `10,366`.

Interpretation:

- The sequence geometry matches the WQP-focused lightweight/no-current surface.
- This supports a fair first PIPE-GRU-D adaptive smoke comparison over the same
  source, split geometry, adjacent-month target gap, and site-domain scale.
- The sequence parquet should be promoted through DVC if retained after the
  adaptive PIPE smoke is reviewed.

### Gate 4 WQP-Focused Adaptive Training Smoke Snapshot

The first WQP-focused adaptive PIPE/GRU-D training smoke completed on
2026-06-15.

Artifacts:

- model:
  `models/pipe_grud/adaptive_wqp_focused/pipe_grud_model_smoke.pt`;
- checkpoint:
  `models/pipe_grud/adaptive_wqp_focused/pipe_grud_checkpoint_smoke.pt`;
- report:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_report_smoke.md`;
- manifest:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_manifest_smoke.json`;
- metrics:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_metrics_smoke.csv`;
- persistence comparison:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_persistence_comparison_smoke.csv`.

Configuration:

- history length: `12`;
- hidden dimension: `96`;
- epochs: `2`;
- train windows used: `50,000` of `112,470`;
- validation windows used: `7,079`;
- test windows used: `7,582`.

Smoke result:

- status: `completed`;
- best epoch: `2`;
- validation all-state RMSE: `0.1507`;
- validation all-state RMSE improvement over persistence: `1.40%`;
- test all-state RMSE: `0.1453`;
- test all-state RMSE improvement over persistence: `1.48%`;
- test `yT` RMSE improvement over persistence: `2.06%`;
- test `delta_yT` RMSE improvement over persistence: `2.69%`.

Interpretation:

- The adaptive temporal smoke is mechanically healthy and does not collapse.
- The adaptive state is smoother than the no-current lightweight state, so the
  persistence baseline is stronger and the relative GRU-D gain is smaller.
- The best checkpoint occurs at the final smoke epoch, so a longer bounded
  training probe is required before deciding whether to scale to full training
  or treat the adaptive temporal variant as persistence-dominated.

### Gate 4 WQP-Focused Adaptive Extended Smoke Snapshot

The extended WQP-focused adaptive PIPE/GRU-D training smoke completed on
2026-06-15.

Artifacts:

- model:
  `models/pipe_grud/adaptive_wqp_focused/pipe_grud_model_extended_smoke.pt`;
- checkpoint:
  `models/pipe_grud/adaptive_wqp_focused/pipe_grud_checkpoint_extended_smoke.pt`;
- report:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_report_extended_smoke.md`;
- manifest:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_manifest_extended_smoke.json`;
- metrics:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_metrics_extended_smoke.csv`;
- persistence comparison:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_persistence_comparison_extended_smoke.csv`.

Configuration:

- history length: `12`;
- hidden dimension: `96`;
- epochs: `8`;
- train windows used: `50,000` of `112,470`;
- validation windows used: `7,079`;
- test windows used: `7,582`.

Extended smoke result:

- status: `completed`;
- best epoch: `8`;
- validation all-state RMSE: `0.1371`;
- validation all-state RMSE improvement over persistence: `10.32%`;
- test all-state RMSE: `0.1322`;
- test all-state RMSE improvement over persistence: `10.40%`;
- test all-state MAE improvement over persistence: `6.59%`;
- test `delta_yN`, `delta_yF`, and `delta_yT` RMSE improvements:
  `14.41%`, `18.72%`, and `18.94%`.

Interpretation:

- The extended smoke shows non-trivial temporal signal over the adaptive state.
- The strongest gains are in change/delta channels, while sigma channels remain
  persistence-dominated.
- Because the best checkpoint occurs at the final extended-smoke epoch, the next
  step is a full WQP-focused adaptive PIPE/GRU-D training run using all
  available windows before rollout/backtest evaluation.

### Gate 4 WQP-Focused Adaptive Full Training Snapshot

The full WQP-focused adaptive PIPE/GRU-D training run completed on 2026-06-15.

Artifacts:

- model: `models/pipe_grud/adaptive_wqp_focused/pipe_grud_model.pt`;
- checkpoint: `models/pipe_grud/adaptive_wqp_focused/pipe_grud_checkpoint.pt`;
- report: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_report.md`;
- manifest: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_manifest.json`;
- metrics: `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_metrics.csv`;
- persistence comparison:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_grud_persistence_comparison.csv`.

Configuration:

- history length: `12`;
- hidden dimension: `96`;
- epochs: `20`;
- train windows used: `112,470`;
- validation windows used: `7,079`;
- test windows used: `7,582`.

Full training result:

- status: `completed`;
- best epoch: `19`;
- validation all-state RMSE: `0.1130`;
- validation all-state RMSE improvement over persistence: `26.07%`;
- test all-state RMSE: `0.1097`;
- test all-state RMSE improvement over persistence: `25.60%`;
- test all-state MAE improvement over persistence: `19.52%`;
- test `delta_yN`, `delta_yF`, and `delta_yT` RMSE improvements:
  `45.88%`, `44.58%`, and `44.18%`.

Interpretation:

- Full adaptive PIPE/GRU-D training shows strong one-step temporal signal over
  the adaptive WQP-focused state.
- The strongest gains remain in change/delta channels.
- `sigma_T` remains effectively persistence-dominated.
- The next required step is recursive rollout backtesting on validation and
  test before any claim about adaptive PIPE alert performance is allowed.

### Gate 4 WQP-Focused Adaptive Validation Rollout Snapshot

The validation recursive rollout backtest completed on 2026-06-15.

Artifacts:

- report:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_report_validation.md`;
- manifest:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_manifest_validation.json`;
- state metrics:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_metrics_validation.csv`;
- alert metrics:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_alert_metrics_validation.csv`;
- diagnostic examples:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_examples_validation.csv`;
- row-level backtest export:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_validation.parquet`.

Configuration:

- split: `validation`;
- selected origins: `5,069`;
- evaluated rollout rows: `15,207`;
- observed state source: `target`;
- samples per origin: `128`;
- rollout horizon: `3`;
- horizon policy: complete horizons.

Validation state metrics:

| horizon | all-state RMSE | persistence RMSE | RMSE improvement | IRC RMSE | IRC RMSE improvement | IRC coverage |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.1273 | 0.1726 | 26.27% | 0.1265 | 9.06% | 0.8627 |
| 2 | 0.1422 | 0.1761 | 19.29% | 0.1490 | 15.17% | 0.8980 |
| 3 | 0.1476 | 0.1842 | 19.87% | 0.1611 | 19.90% | 0.9292 |

Validation alert metrics:

| event | horizon | PR-AUC | Brier | recall | macro-F1 |
|---|---:|---:|---:|---:|---:|
| `irc_alert` | 1 | 0.8703 | 0.1216 | 0.7997 | 0.8414 |
| `irc_alert` | 2 | 0.8217 | 0.1507 | 0.7225 | 0.7817 |
| `irc_alert` | 3 | 0.7910 | 0.1682 | 0.6656 | 0.7479 |
| `bloom_h` | 1 | 0.5814 | 0.0854 | 0.5244 | 0.7510 |
| `bloom_h` | 2 | 0.5531 | 0.0951 | 0.2993 | 0.6765 |
| `bloom_h` | 3 | 0.5115 | 0.1021 | 0.1729 | 0.5991 |

Interpretation:

- Validation rollouts remain better than persistence for all-state RMSE and
  IRC RMSE across horizons 1-3.
- The adaptive validation IRC alert surface is stronger than the lightweight
  WQP-focused no-current validation run in PR-AUC and Brier, while using the
  same selected-origin geometry.
- Bloom alert recall weakens materially by horizon 3 and should remain a
  limitation until calibrated policy comparisons are run.
- This validation snapshot is a gate check; final adaptive policy claims still
  require the held-out test split and policy calibration.

### Gate 4 WQP-Focused Adaptive Test Rollout Snapshot

The held-out test recursive rollout backtest completed on 2026-06-15.

Artifacts:

- report:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_report_test.md`;
- manifest:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_manifest_test.json`;
- state metrics:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_metrics_test.csv`;
- alert metrics:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_alert_metrics_test.csv`;
- diagnostic examples:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_examples_test.csv`;
- row-level backtest export:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_backtest_rows_test.parquet`.

Configuration:

- split: `test`;
- selected origins: `6,145`;
- evaluated rollout rows: `18,435`;
- observed state source: `target`;
- samples per origin: `128`;
- rollout horizon: `3`;
- horizon policy: complete horizons.

Test state metrics:

| horizon | all-state RMSE | persistence RMSE | RMSE improvement | IRC RMSE | IRC RMSE improvement | IRC coverage |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.1233 | 0.1645 | 25.03% | 0.1236 | 9.58% | 0.8871 |
| 2 | 0.1342 | 0.1691 | 20.66% | 0.1461 | 15.86% | 0.9120 |
| 3 | 0.1394 | 0.1749 | 20.31% | 0.1553 | 19.71% | 0.9390 |

Test alert metrics:

| event | horizon | PR-AUC | Brier | recall | macro-F1 |
|---|---:|---:|---:|---:|---:|
| `irc_alert` | 1 | 0.9013 | 0.1059 | 0.8215 | 0.8523 |
| `irc_alert` | 2 | 0.8630 | 0.1329 | 0.7554 | 0.8071 |
| `irc_alert` | 3 | 0.8547 | 0.1424 | 0.7278 | 0.7923 |
| `bloom_h` | 1 | 0.6559 | 0.1086 | 0.5282 | 0.7620 |
| `bloom_h` | 2 | 0.6131 | 0.1169 | 0.2990 | 0.6650 |
| `bloom_h` | 3 | 0.5983 | 0.1236 | 0.2503 | 0.6375 |

Interpretation:

- Held-out test confirms that recursive adaptive rollouts improve persistence
  for all-state RMSE and IRC RMSE across horizons 1-3.
- The adaptive test `irc_alert` surface is stronger than the lightweight
  WQP-focused no-current test run in PR-AUC, Brier, recall, and macro-F1 under
  the same selected-origin geometry.
- `bloom_h` is stronger on test than validation in ranking terms, but fixed
  recall remains low for horizons 2-3; it remains a secondary diagnostic.
- Validation and test are now healthy enough to run adaptive rollout
  calibration and 2B policy-frontier comparison.

### Gate 4 WQP-Focused Adaptive Calibration Snapshot

The validation-to-test adaptive rollout calibration completed on 2026-06-15.

Artifacts:

- report:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibration_report.md`;
- manifest:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibration_manifest.json`;
- thresholds:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibration_thresholds.csv`;
- metrics:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibration_metrics.csv`;
- calibrated rows:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_calibrated_backtest_rows.parquet`;
- bloom calibrators:
  `models/pipe_grud/adaptive_wqp_focused/rollout_calibrators/`.

Configuration:

- calibration split: `validation`;
- evaluation splits: `validation`, `test`;
- backtest rows: `33,642`;
- threshold rows: `6`;
- metric rows: `12`;
- selection objective: `fbeta`;
- F-beta beta: `2.0`;
- bloom score column: `irc_mean`;
- fitted bloom calibrators: `3`.

F2-selected thresholds:

| event | horizon | threshold | validation recall | validation precision | validation F2 |
|---|---:|---:|---:|---:|---:|
| `irc_alert` | 1 | 0.1094 | 0.9503 | 0.6284 | 0.8620 |
| `irc_alert` | 2 | 0.1250 | 0.9629 | 0.5625 | 0.8429 |
| `irc_alert` | 3 | 0.1641 | 0.9678 | 0.5452 | 0.8379 |
| `bloom_h` | 1 | 0.1571 | 0.8098 | 0.4079 | 0.6764 |
| `bloom_h` | 2 | 0.1448 | 0.8617 | 0.3299 | 0.6516 |
| `bloom_h` | 3 | 0.1406 | 0.8665 | 0.3281 | 0.6524 |

Held-out test metrics under F2 thresholds:

| event | horizon | alert rate | PR-AUC | Brier | recall | precision | F2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `irc_alert` | 1 | 0.6161 | 0.9013 | 0.1059 | 0.9521 | 0.6410 | 0.8679 |
| `irc_alert` | 2 | 0.7268 | 0.8630 | 0.1329 | 0.9688 | 0.5773 | 0.8531 |
| `irc_alert` | 3 | 0.7557 | 0.8547 | 0.1424 | 0.9755 | 0.5741 | 0.8558 |
| `bloom_h` | 1 | 0.2726 | 0.6405 | 0.0946 | 0.7758 | 0.5188 | 0.7059 |
| `bloom_h` | 2 | 0.3671 | 0.5879 | 0.1016 | 0.8714 | 0.4349 | 0.7257 |
| `bloom_h` | 3 | 0.3868 | 0.5593 | 0.1056 | 0.8777 | 0.4212 | 0.7213 |

Interpretation:

- F2 calibration is technically healthy and selected thresholds on validation
  only.
- Adaptive F2 `irc_alert` keeps very high held-out recall with lower alert
  rates and higher precision than the lightweight WQP-focused no-current F2
  profile.
- Bloom calibration is materially stronger than the lightweight WQP-focused
  no-current bloom calibration, but it is still a secondary diagnostic.
- F2 remains a recall-first profile. A balanced/default adaptive policy still
  requires the 2B policy-frontier comparison.

### Gate 4 WQP-Focused Adaptive 2B Policy Frontier Snapshot

The adaptive 2B policy-frontier comparison completed on 2026-06-15.

Artifacts:

- report:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_policy_2b_report.md`;
- manifest:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_policy_2b_manifest.json`;
- thresholds:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_policy_2b_thresholds.csv`;
- metrics:
  `reports/pipe_grud/adaptive_wqp_focused/pipe_rollout_policy_2b_metrics.csv`.

Configuration:

- calibration split: `validation`;
- evaluation splits: `validation`, `test`;
- calibrated rows: `33,642`;
- threshold rows: `42`;
- metric rows: `84`;
- objectives: `fixed`, `fbeta`, `f1`, `mcc`, `balanced_accuracy`,
  `gmean_pr`, and `closest_pr`.

Held-out test `irc_alert` frontier:

| horizon | policy | threshold | recall | precision | alert rate | F2 | MCC | balanced accuracy |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | `closest_pr` | 0.4062 | 0.8568 | 0.8083 | 0.4397 | 0.8466 | 0.7075 | 0.8564 |
| 1 | `fbeta` | 0.1094 | 0.9521 | 0.6410 | 0.6161 | 0.8679 | 0.5817 | 0.7871 |
| 1 | `balanced_accuracy` | 0.4297 | 0.8482 | 0.8146 | 0.4319 | 0.8412 | 0.7075 | 0.8557 |
| 2 | `closest_pr` | 0.3828 | 0.8159 | 0.7583 | 0.4659 | 0.8037 | 0.6131 | 0.8086 |
| 2 | `fbeta` | 0.1250 | 0.9688 | 0.5773 | 0.7268 | 0.8531 | 0.4747 | 0.7135 |
| 2 | `balanced_accuracy` | 0.4375 | 0.7896 | 0.7790 | 0.4389 | 0.7874 | 0.6175 | 0.8092 |
| 3 | `closest_pr` | 0.3750 | 0.8053 | 0.7369 | 0.4861 | 0.7906 | 0.5717 | 0.7875 |
| 3 | `fbeta` | 0.1641 | 0.9755 | 0.5741 | 0.7557 | 0.8558 | 0.4577 | 0.6979 |
| 3 | `balanced_accuracy` | 0.4609 | 0.7552 | 0.7815 | 0.4298 | 0.7603 | 0.5883 | 0.7931 |

Held-out test `bloom_h` frontier:

| horizon | default comparison policy | recall | precision | alert rate | F2 | MCC |
|---:|---|---:|---:|---:|---:|---:|
| 1 | `closest_pr` | 0.6221 | 0.6479 | 0.1750 | 0.6271 | 0.5555 |
| 2 | `closest_pr` | 0.6315 | 0.5943 | 0.1947 | 0.6237 | 0.5225 |
| 3 | `closest_pr` | 0.5651 | 0.5857 | 0.1791 | 0.5691 | 0.4806 |

Interpretation:

- `closest_pr` remains a defensible default experimental profile for adaptive
  `irc_alert`: it keeps recall above `0.80` on all horizons while avoiding the
  high alert volume of F2.
- `fbeta`/F2 should be retained as the sensitive recall-first profile.
- `balanced_accuracy`/`mcc` provide a conservative alternative, especially at
  horizons 2-3 where they trade recall for precision and lower alert volume.
- The adaptive bloom frontier is strong enough to report, but `irc_alert`
  remains the primary operational target.

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
| real-data smoke report | `reports/anfis/adaptive_anfis_real_smoke_report.md` |

If any adaptive state, checkpoint, or row-level output is large, it must be
managed through DVC pointers rather than committed as a Git blob.

## First Implementation Slice

The first code slice is deliberately small:

1. add a lightweight adaptive ANFIS module with trainable Gaussian membership
   centers, positive widths, normalized firing strengths, and Sugeno-style
   consequents;
2. add synthetic tests for monotonic learning, output ranges, membership order,
   and deterministic seed behavior;
3. add a synthetic smoke runner that writes report and manifest artifacts;
4. only after that smoke passes, add bounded real-data training.

Implementation paths:

- module: `src/fuzzy/adaptive_anfis.py`;
- smoke runner:
  `src/experiments/run_adaptive_anfis_synthetic_smoke.py`;
- tests: `tests/test_adaptive_anfis.py`;
- default smoke report:
  `reports/anfis/adaptive_anfis_synthetic_smoke_report.md`;
- default smoke manifest:
  `reports/anfis/adaptive_anfis_synthetic_smoke_manifest.json`.

This sequence keeps adaptive ANFIS from contaminating the already closed PIPE
lightweight baseline.

## Gate 1 Synthetic Smoke Snapshot

The synthetic-only Gate 1 runner completed successfully on 2026-06-15.

Artifacts:

- report:
  `reports/anfis/adaptive_anfis_synthetic_smoke_report.md`;
- manifest:
  `reports/anfis/adaptive_anfis_synthetic_smoke_manifest.json`;
- metrics:
  `reports/anfis/adaptive_anfis_synthetic_smoke_metrics.csv`.

Smoke configuration:

- rows per module: `128`;
- memberships per input: `3`;
- epochs: `80`;
- learning rate: `0.05`;
- random seed: `1729`.

Gate checks passed for synthetic `ANFIS-N`, `ANFIS-F`, and `ANFIS-T`:

- finite final losses;
- outputs remained in `[0, 1]`;
- centers remained ordered;
- trainable parameters changed;
- losses improved by more than `98%` in all three synthetic modules.

This result validates only the minimal adaptive training mechanics. It does
not yet validate real-data ANFIS behavior or produce `S_adaptive(t)`.

## Gate 2 Real-Data Smoke Implementation

The bounded real-data smoke runner has been added as the next executable gate:

- runner: `src/experiments/run_adaptive_anfis_real_smoke.py`;
- tests: `tests/test_adaptive_anfis_real_smoke.py`;
- report:
  `reports/anfis/adaptive_anfis_real_smoke_report.md`;
- manifest:
  `reports/anfis/adaptive_anfis_real_smoke_manifest.json`;
- module metrics:
  `reports/anfis/adaptive_anfis_real_smoke_module_metrics.csv`;
- target metrics:
  `reports/anfis/adaptive_anfis_real_smoke_target_metrics.csv`;
- bounded prediction sample:
  `reports/anfis/adaptive_anfis_real_smoke_predictions.csv`;
- initial/final memberships:
  `reports/anfis/adaptive_anfis_real_smoke_memberships_initial.csv` and
  `reports/anfis/adaptive_anfis_real_smoke_memberships_final.csv`.

This runner trains `ANFIS-N`, `ANFIS-F`, `ANFIS-T`, and
`ANFIS-T-no-current` on sampled train rows only, using expert fuzzy substates
as pseudo-label anchors. It then evaluates anchor metrics and target metrics
on the sampled real-data slice, including separate full and no-current IRC
surfaces.

The default command is intentionally bounded:

```bash
poetry run python src/experiments/run_adaptive_anfis_real_smoke.py
```

The smoke is a readiness gate, not a final adaptive-state result. Passing it
justifies moving toward Gate 3 design, but it does not by itself prove that the
adaptive surface improves PIPE.

## Gate 2 Real-Data Smoke Snapshot

The bounded real-data Gate 2 smoke completed successfully on 2026-06-15.

Command:

```bash
poetry run python src/experiments/run_adaptive_anfis_real_smoke.py \
  --sample-rows-per-split-horizon 256 \
  --train-rows-per-module 256 \
  --epochs 40
```

Artifacts:

- report:
  `reports/anfis/adaptive_anfis_real_smoke_report.md`;
- manifest:
  `reports/anfis/adaptive_anfis_real_smoke_manifest.json`;
- module metrics:
  `reports/anfis/adaptive_anfis_real_smoke_module_metrics.csv`;
- target metrics:
  `reports/anfis/adaptive_anfis_real_smoke_target_metrics.csv`;
- prediction sample:
  `reports/anfis/adaptive_anfis_real_smoke_predictions.csv`;
- initial/final memberships:
  `reports/anfis/adaptive_anfis_real_smoke_memberships_initial.csv` and
  `reports/anfis/adaptive_anfis_real_smoke_memberships_final.csv`.

Smoke configuration:

- sampled rows per split/horizon: `256`;
- total sampled split rows: `2,304`;
- train rows per module: `256`;
- memberships per input: `3`;
- epochs: `40`;
- learning rate: `0.03`;
- random seed: `1729`.

Gate checks passed:

- split/state/panel alignment: `2,304 / 2,304` rows matched;
- state missing rows: `0`;
- panel missing rows: `0`;
- all four adaptive modules passed finite-loss, ordered-center,
  parameter-update, and non-constant-output checks;
- target metrics were produced for full and no-current adaptive IRC surfaces.

Module anchor summary:

| module | final loss | anchor MAE | anchor RMSE | Spearman | output std | mean missing fraction |
|---|---:|---:|---:|---:|---:|---:|
| `ANFIS-N` | 0.0007 | 0.0316 | 0.0674 | 0.8830 | 0.1475 | 0.8248 |
| `ANFIS-F` | 0.0014 | 0.0250 | 0.0571 | 0.9598 | 0.1880 | 0.8280 |
| `ANFIS-T` | 0.0183 | 0.1170 | 0.1353 | 0.9564 | 0.2889 | 0.4234 |
| `ANFIS-T-no-current` | 0.0049 | 0.0246 | 0.0663 | 0.9996 | 0.1262 | 0.8194 |

Validation target metrics for adaptive full IRC:

| score | horizon | PR-AUC | ROC-AUC | Brier | recall | macro-F1 | risk RMSE |
|---|---:|---:|---:|---:|---:|---:|---:|
| `irc1_adaptive` | 1 | 0.3504 | 0.7979 | 0.1884 | 0.7407 | 0.6555 | 0.3234 |
| `irc1_adaptive` | 2 | 0.4493 | 0.8852 | 0.1899 | 0.8929 | 0.6742 | 0.3360 |
| `irc1_adaptive` | 3 | 0.4494 | 0.7983 | 0.1874 | 0.6667 | 0.6884 | 0.3557 |

Validation target metrics for adaptive no-current IRC:

| score | horizon | PR-AUC | ROC-AUC | Brier | recall | macro-F1 | risk RMSE |
|---|---:|---:|---:|---:|---:|---:|---:|
| `irc1_no_chla_adaptive` | 1 | 0.2662 | 0.6791 | 0.2365 | 0.3704 | 0.5964 | 0.3850 |
| `irc1_no_chla_adaptive` | 2 | 0.1726 | 0.6067 | 0.2391 | 0.2500 | 0.5596 | 0.4022 |
| `irc1_no_chla_adaptive` | 3 | 0.2270 | 0.5626 | 0.2391 | 0.2222 | 0.5714 | 0.4117 |

Interpretation:

- Gate 2 is satisfied as a real-data training and reporting smoke.
- The adaptive modules can learn expert-substate anchors on sampled real rows
  while preserving ordered centers and bounded outputs.
- This run is not evidence of downstream PIPE improvement. The target metrics
  are diagnostic only and use an uncalibrated threshold of `0.5`.
- The all-source sample has high missingness for nutrient, physicochemical,
  and no-current thermal modules. Gate 3 should therefore add
  coverage-aware training and a source-focused diagnostic, especially for WQP,
  before exporting a full adaptive state.
- Final memberships are ordered but not constrained to remain inside the
  normalized `[0, 1]` feature interval. Gate 3 should decide whether to add
  bounded-center parameterization or an explicit prior/drift penalty.

## Claims Allowed After This Protocol

- The repository contains a documented expert/refined fuzzy baseline for PIPE
  Layer 1.
- The adaptive ANFIS implementation gap is now explicitly mapped.
- Synthetic adaptive ANFIS mechanics have passed Gate 1.
- The Gate 2 bounded real-data smoke completed on sampled real rows without
  overwriting existing PIPE lightweight artifacts.
- The Gate 3 WQP-focused full adaptive-state export completed and is retained
  as a comparison surface for the next PIPE-adaptive step.
- In validation, the WQP-focused no-current adaptive IRC improves over the
  expert no-current IRC across PR-AUC, ROC-AUC, Brier, macro-F1, and risk
  error.
- In validation, the WQP-focused full Chl-a-aware adaptive IRC is mixed against
  the expert full IRC and should not replace it without downstream PIPE
  re-evaluation.

## Claims Not Allowed Yet

- Do not claim adaptive ANFIS improves PIPE until validation/test comparisons
  and downstream PIPE re-evaluation exist.
- Do not claim the adaptive ANFIS layer is thesis-complete before full
  downstream PIPE re-evaluation, degradation analysis, and final comparison
  against PIPE lightweight, Neural ODE if stable, and MIFAL exist.
