# Closure V2 Analysis Plan

## Status and purpose

This document preregisters Closure V2 as an additive experiment. Closure V1,
its annotated tag `thesis-closure-v1`, its reports, manifests, models, data and
claims remain immutable. V2 addresses the V1 all-or-nothing temporal-fit rule;
it does not reinterpret V1 as having trained P0 or P1.

The primary objective is to fit and compare P0 and P1 on an exact shared
complete-case population while retaining every intended row and its failure
reason. A technically valid negative result is an acceptable completion.

## Surface and roles

The strict surface is `closure_v2_wqp_adaptive_no_current_chla`, with twelve
calendar months of history and horizons 1–3. Observed Chl-a and any direct or
renamed derivative are forbidden at every input lag. The temporal state has
nine state, uncertainty and change channels; four deterministic seasonal
channels complete the 13-dimensional input.

Development roles remain training through 2018-12, model selection during
2019-01–2020-12, and calibration/threshold fitting during 2021. Origin and
target must share a role. All 88 V1 holdout locations are excluded from every
development operation.

## Eligibility and shared fit

A fit row is eligible only when it is a development training/model-selection
row, its sequence status is `success`, all 13 input lists and nine targets are
finite, origin and target share a role, and no forbidden lineage or evaluation
overlap exists. Incomplete rows stay in the ledger, never enter the loss, are
never zero-filled and are never silently dropped.

Fit authorization requires at least 90% overall eligibility, 5,000 training
rows, 500 model-selection rows, 200 calibration rows and 200/50/30 distinct
locations in those roles. The primary P0/P1 fit uses the exact intersection of
successful keys by seed. Model-specific complete cases and masked loss are
secondary sensitivities only.

Eligibility bias is audited by role, site, time, climate season, input
coverage, state values, uncertainties, deltas and development-only bloom
frequency. Absolute SMD above 0.20 is flagged. It does not authorize changing
the cohort; claims are then limited to the eligible subpopulation and the
registered sensitivity is reported.

## Models, profiles and seeds

P0 and P1 are residual probabilistic GRUs, not canonical GRU-D models. They
share architecture, seeds, optimization budget, eligibility, calibration and
failure policy. Seeds are 1729, 20260612, 20260613, 20260614 and 314159 and are
not ecological replicates or replaceable slots.

Both the V2 profile (batch 512, 60 epochs, patience 10) and legacy diagnostic
profile (batch 2048, 20 epochs, patience 5) are evaluated using development
model-selection loss only. Lower probabilistic validation loss wins; an exact
tie selects the V2 profile. Evaluation data cannot influence this choice.

## Calibration and endpoints

Calibration uses 2021 only. Identity, Platt logistic and isotonic regression
are selected by Brier with ECE secondary; alert thresholds maximize F2; and
conformal quantiles are fixed for 0.80, 0.90 and 0.95. No recalibration follows
evaluation.

The primary endpoint is `bloom_h` at 30 µg/L. Thresholds 25, 33 and 50 are
predeclared sensitivities. Continuous state, ordinal trophic state, interval
quality, operational availability and planning deltas are secondary.

## Evaluation layers

`legacy_posthoc` reuses the 88 opened V1 locations only as retrospective
complementary evidence. It can never support a new confirmatory claim.

`fresh_primary` follows the deterministic hierarchy in
`configs/closure_v2/evaluation_cohorts.yaml`. The input-only feasibility audit
supports the first route: WQP locations absent from all 441 V1 locations. The
primary deterministic subset also requires origins from 2022 onward, twelve
consecutive eligible input months, and complete h1–h3 calendar geometry within
the site's input-observation window. Candidate identities are reconstructed
and frozen only after the V2 model lock. Target values and target availability
cannot affect assignment or replacement.

## Metrics and inference

Every result reports attempted, input-eligible, prediction-successful,
target-available, metric-evaluable and shared-success denominators.
Observation-weighted and site-weighted estimands, and legacy and fresh layers,
remain separate.

Primary family prediction is the mean probability across the five registered
seeds. Inference uses 2,000 paired bootstrap replicates resampling locations.
Seeds are never treated as independent ecological observations. PR-AUC
replicates with one class are non-estimable and at least 95% valid replicates
are required for an interval. Holm families A–E remain complete when a
contrast is unavailable.

## Degradation, planning and claims

M0–P1 degradation uses identical deterministic masks and frozen models with no
scenario refit. Planning compares all nine actions against `no_action` on
common keys, with location bootstrap and the complete nine-action Holm family.
Neither block authorizes field causality, official recommendations or universal
optimality.

Fresh WQP locations support, at most, internal evaluation on unused WQP
monitoring locations. They do not by themselves establish external validation
or unseen waterbody transfer. Every claim must map to cohort, estimand,
denominator, artifact, metric, uncertainty, authority commit and limitation.

## Stop conditions

Execution stops on V1 drift, outcome access before model lock, outcome-driven
cohort selection, post-evaluation tuning, silent row deletion, different P0/P1
primary keys, seed substitution, reduced Holm universes, mixed layers or
estimands, missing hashes, unpublished DVC pointers, missing denominators,
nonreproducible figures or credentials in the repository.
