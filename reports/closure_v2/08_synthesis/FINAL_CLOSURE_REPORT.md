# FINAL CLOSURE REPORT — Closure V2

## 1. Authority and evidence boundary

Closure V2 synthesis authority is `e85990193ce2c97cbf7b2f200e8320fa05bbe5ac`. Closure V1 remains immutable at its published authorities; V2 is additive and does not retroactively change V1 model availability or claims. This synthesis consumed only 41 allowlisted structured Git inputs. It did not read raw targets, Parquet, or `private/FULL.md`, and did not refit, rescore, recalibrate, or pool cohorts/estimands.

## 2. Eligibility and model availability

All five P0 and five P1 slots were trained and calibrated without replacement on the same 8,925 complete-case shared-fit rows from 9,413 fit-intent rows. The 505 incomplete origins remain visible in the ledger. Seeds are algorithmic slots, not ecological replicates.

## 3. Evaluation surfaces

`fresh_primary` contains 2,286 origins from 137 WQP monitoring locations unused by V1 and is the maximum internal evidence layer. `legacy_posthoc` contains 4,488 origins from the 88 previously opened V1 locations and is retrospective complementary evidence. They are never pooled.

## 4. Primary inferential result

On fresh-primary observation-weighted common rows, P1 versus B2 was `{'inferior': 6}` across Brier and PR-AUC at h1-h3. P1 versus P0 was `{'inconclusive': 3, 'inferior': 3}`. Thus V2 resolves the V1 structural non-estimability, but the registered fresh-primary evidence does not support superiority of the adaptive P1 branch. The favorable P1-P0 result in legacy-posthoc remains retrospective and cannot overturn the fresh-primary result.

## 5. Uncertainty, degradation and planning

Uncertainty diagnostics are reported by model, cohort and horizon without a global calibration claim. Degradation uses identical deterministic masks and frozen models; it supports only robustness statements under simulated missingness. No universal M0-P1 crossover was found.

All 9 fresh-primary planning actions had negative objective estimates after the registered cost, support and uncertainty terms; Holm rejected none. This is valid negative model-behavior evidence, not evidence that interventions fail in the field, and not an official recommendation.

## 6. H1-H5b adjudication

| hypothesis_id   | v1_verdict                         | v2_verdict                     | cohort         | evidence_summary                                                                                                             | denominator                                   | limitation                                                                                                    | decisive_artifact                                                                                                                                                 | authority_commit                         |
|:----------------|:-----------------------------------|:-------------------------------|:---------------|:-----------------------------------------------------------------------------------------------------------------------------|:----------------------------------------------|:--------------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------|
| H1              | limited_descriptive_support        | not_supported_on_fresh_primary | fresh_primary  | Adaptive ANFIS state did not improve P1 over P0: Brier was inconclusive and PR-AUC inferior at h1-h3.                        | 966;933;885 shared rows                       | V2 tests predictive utility of the adaptive state, not interpretability, membership stability, or saturation. | reports/closure_v2/05_inference/pairwise_effects.csv;reports/closure_v2/06_degradation/pairwise_effects.csv;reports/closure_v2/07_planning/planning_bootstrap.csv | e85990193ce2c97cbf7b2f200e8320fa05bbe5ac |
| H2              | not_estimable_primary_architecture | estimable_negative_result      | fresh_primary  | P1 was inferior to B2 for observation-weighted Brier and PR-AUC at h1-h3.                                                    | 966;933;885 shared rows                       | Internal evaluation on unused WQP monitoring locations; no external validation.                               | reports/closure_v2/05_inference/pairwise_effects.csv;reports/closure_v2/06_degradation/pairwise_effects.csv;reports/closure_v2/07_planning/planning_bootstrap.csv | e85990193ce2c97cbf7b2f200e8320fa05bbe5ac |
| H3              | partial_descriptive_only           | partial_descriptive_support    | fresh_primary  | Uncertainty and simulated degradation became estimable, with model/scenario-specific results rather than a global guarantee. | published rows by model, horizon and scenario | Simulated missingness is not field robustness and intervals are not universal calibration.                    | reports/closure_v2/05_inference/pairwise_effects.csv;reports/closure_v2/06_degradation/pairwise_effects.csv;reports/closure_v2/07_planning/planning_bootstrap.csv | e85990193ce2c97cbf7b2f200e8320fa05bbe5ac |
| H4              | not_estimable                      | estimable_descriptive_contrast | fresh_primary  | M0-P1 degradation contrasts were estimated on identical masks; no universal crossover was found.                             | registered family rows                        | M0 is a robustness comparator, not a causal mechanism or field intervention.                                  | reports/closure_v2/05_inference/pairwise_effects.csv;reports/closure_v2/06_degradation/pairwise_effects.csv;reports/closure_v2/07_planning/planning_bootstrap.csv | e85990193ce2c97cbf7b2f200e8320fa05bbe5ac |
| H5a             | not_confirmed_scientifically       | not_supported                  | fresh_primary  | All nine planning objectives had negative clustered estimates versus no_action after registered cost/support penalties.      | 9 actions; 6,858 intended rows each           | Raw-proxy simulation does not authorize causality, official recommendations, or universal optima.             | reports/closure_v2/05_inference/pairwise_effects.csv;reports/closure_v2/06_degradation/pairwise_effects.csv;reports/closure_v2/07_planning/planning_bootstrap.csv | e85990193ce2c97cbf7b2f200e8320fa05bbe5ac |
| H5b             | not_estimable                      | not_estimable_registered_scope | not_applicable | A separate field net-benefit endpoint was not registered or observed.                                                        | 9-action planning family                      | delta_objective_vs_no_action is a simulated objective, not observed net benefit.                              | reports/closure_v2/05_inference/pairwise_effects.csv;reports/closure_v2/06_degradation/pairwise_effects.csv;reports/closure_v2/07_planning/planning_bootstrap.csv | e85990193ce2c97cbf7b2f200e8320fa05bbe5ac |

## 7. Global verdict

Closure V2 provides a completed, reproducible and refutable temporal experiment. It converts the unavailable V1 P0/P1 question into an estimable negative result: on the internal fresh-primary surface, the adaptive P1 branch did not outperform the registered comparators and was inferior on the primary P1-B2 contrasts. This does not establish external invalidity, universal model inferiority, field causality, or lack of management value.

## 8. Thesis package

The package contains 162 final evidence rows, 17 claim mappings, 14 deterministic tables and 10 deterministic SVG figures. Every claim provides cohort, estimand, denominator, artifact, authority and wording boundaries. `MANUSCRIPT_CHANGE_MAP.md` is a handoff only; this phase does not modify LaTeX.
