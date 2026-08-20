# FINAL CLOSURE REPORT — Closure V1

## 1. Freeze, commit and environment

Closure source commit: `ea8ddce7f8edb9a61db97e29178e52603fa371b1`.

Sealed topology: `ea8ddce -> H-SYN (exact9A+2M) -> P-SYN (exact2A) -> R-SYN (exact24)`.
E10 environment sealed and validated in T12: Python 3.14.7, FastAPI 0.138.1, and DVC 3.67.1.
The synthesis uses exactly 83 structured CSV/JSON/YAML inputs and identity-only DVC pointers, and it produces 24 manifest-last artifacts.
It does not read Parquet, `data/targets/`, raw outcomes, or `private/FULL.md`; it does not run refitting, rescoring, recalibration, DVC add/push, or E0-U/E1-E10.

## 2. Primary surface and holdout

Internal pseudoprospective WQP surface: 88 held-out locations, 4,488 origins, and 13,464 origin-horizon attempts.
The funnel retains failures and unavailable predictions in the intent-to-predict denominator. The five seeds are algorithmic slots, not ecological replicates.
P0, P1, and A2 remain `model_unavailable` without substitution. This is an internal WQP surface, not external validation.

## 3. Results E1–E10

### E1

Internal benchmark: observation-weighted Brier h1=B2:mean=0.1554:success_rate=0.184269:evaluable_rate=0.184269|h2=B2:mean=0.1597:success_rate=0.191176:evaluable_rate=0.191176|h3=B2:mean=0.1659:success_rate=0.182487:evaluable_rate=0.182487 with denominators h1:attempted=22440:successful=4135:evaluable=4135|h2:attempted=22440:successful=4290:evaluable=4290|h3:attempted=22440:successful=4095:evaluable=4095; PR-AUC observation-weighted h1=A1:mean=0.6105:success_rate=0.141488:evaluable_rate=0.141488|h2=B2:mean=0.6287:success_rate=0.191176:evaluable_rate=0.191176|h3=B2:mean=0.6024:success_rate=0.182487:evaluable_rate=0.182487 with denominators h1:attempted=22440:successful=3175:evaluable=3175|h2:attempted=22440:successful=4290:evaluable=4290|h3:attempted=22440:successful=4095:evaluable=4095. In the paired F1-F0 contrast, the absolute-loss difference was positive in 15/15; these results are descriptive, and the observation_weighted and site_weighted estimands remain separate.

### E2

Internal legacy-to-holdout transfer: 0/1050 estimable cells. The sealed reason is `legacy_evaluation_surface_not_frozen_before_e0_u`; this is not evidence of a zero gap or external geographic validation.

### E3

Preserved descriptive sensitivity for thresholds 25;30;33;50 micrograms/L, with prevalence, support, and Kendall statistics by horizon; no threshold was recalibrated after E0-U.

### E4

Ordinal/trophic B2-B1 comparison: a direction favorable to B2 in 15/15 reference-by-horizon summaries for macro-F1, quadratic kappa, ordinal MAE, and severe error. This is internal auxiliary proxy/derived-reference evidence; it does not validate the ANFIS branch, and NLA does not transfer monthly WQP targets.

### E5

Complete inferential ledger: A3;B78;C1;D9;E1 (92 cells). Every registered cell remains in Holm even when its estimate, confidence interval, and p-value are not estimable.

### E6

Controlled M0-P1 degradation: 0/78 estimable cells because P1 remained model_unavailable. No reconstruction, substitution, or new read occurred.

### E7

A1-A0 ablation on exact common rows: 3/3;3/3;2/3. Learning-curve and membership-stability diagnostics completed 0/4; no saturation or parameter-stability claim is authorized.

### E8

Paired raw-Gaussian versus locked-conformal comparison at nominal 0.90: raw_within=30/30;locked_within=26/30;locked_closer=5/30;locked_wider=30/30;mean_abs_error_raw=0.015565;median_abs_error_raw=0.013386;mean_abs_error_locked=0.032271;median_abs_error_locked=0.030872. Raw was within the absolute 0.05 margin in 30/30 groups and locked in 26/30; locked was closer in 5/30 and wider in 30/30, and its mean/median absolute errors were 0.032271/0.030872 versus 0.015565/0.013386 for raw. Therefore, `conformal always improves` is prohibited. This is descriptive diagnostics; the confirmatory comparison that depends on P1 remains non-estimable, and no recalibration occurred.

### E9

Planning: 0/9 actions with an estimable effect, confidence interval, or p-value (`model_unavailable`). The registered endpoint is `delta_objective_vs_no_action`; net benefit, causality, optimality, and official recommendations are not authorized.

### E10

Recovery-2 software evidence: 338 pass;9 skip;3 E2E;69 paths;83 operations;38 documented;Python 3.14.7;FastAPI 0.138.1;DVC 3.67.1. This verification establishes artifact reproducibility, not scientific efficacy or prospective field validation.


## 4. Comparisons and non-estimability

Exact census of 130 rows: 93 `model_unavailable`, 9 `not_applicable`, 5 `insufficient_support`, and 23 `descriptive_available`.
The 92 Holm contrasts retain A=3, B=78, C=1, D=9, and E=1. In a non-estimable row, `estimate` and `uncertainty` are empty by contract: they never represent zero, equivalence, or negative evidence.
Comparisons requiring P0/P1/A2 lack an estimate, confidence interval, and p-value because the required model was unavailable; E2 lacks a gap because no comparable frozen legacy surface exists; E6 lacks an M0-P1 intersection; E9 lacks both an action effect and a registered net-benefit endpoint.
Available A1-A0 deltas are descriptive, with no invented inferential interval:

`A1_vs_A0:h1 delta_brier=-0.0056 (n=3175); A1_vs_A0:h1 delta_mae=-0.0044 (n=3175); A1_vs_A0:h1 delta_pr_auc=0.0074 (n=3175); A1_vs_A0:h2 delta_brier=-0.0003 (n=3125); A1_vs_A0:h2 delta_mae=0.0002 (n=3125); A1_vs_A0:h2 delta_pr_auc=0.0072 (n=3125); A1_vs_A0:h3 delta_brier=-0.0111 (n=3045); A1_vs_A0:h3 delta_mae=-0.0020 (n=3045); A1_vs_A0:h3 delta_pr_auc=0.0202 (n=3045)`

E8 reports raw and locked coverage/width/Winkler diagnostics for 30 exact pairs: raw was within the margin in 30/30 and locked in 26/30, locked was closer in 5/30 and wider in 30/30, and mean/median absolute errors were 0.015565/0.013386 for raw and 0.032271/0.030872 for locked. This prohibits claiming that `conformal always improves` and provides neither global confirmation nor permission to recalibrate.

## 5. Verdict H1–H5

- H1: `limited_descriptive_support` — Interpretable and usable ANFIS; decisive experiments `E7;E4`; states `{"descriptive_available":22,"insufficient_support":4,"model_unavailable":2}`; limitation `NO_SATURATION_OR_MEMBERSHIP_STABILITY_EVIDENCE`.
- H2: `not_estimable_primary_architecture` — PIPE temporal signal; decisive experiments `E1;E2`; states `{"insufficient_support":1,"model_unavailable":2}`; limitation `P0_P1_MODEL_UNAVAILABLE`.
- H3: `partial_descriptive_only` — Uncertainty and degradation; decisive experiments `E8;E6`; states `{"descriptive_available":1,"model_unavailable":2}`; limitation `CONFIRMATORY_P1_AND_E6_NOT_ESTIMABLE`.
- H4: `not_estimable` — MIFAL as a robustness contrast; decisive experiments `E6`; states `{"model_unavailable":78}`; limitation `NO_M0_P1_SHARED_SUCCESS`.
- H5a: `not_confirmed_scientifically` — Planning capability; decisive experiments `E9`; states `{"model_unavailable":9}`; limitation `NO_SHARED_SUCCESS_OR_ESTIMABLE_RANKING`.
- H5b: `not_estimable` — Net planning benefit; decisive experiments `E9`; states `{"not_applicable":9}`; limitation `NET_BENEFIT_ENDPOINT_NOT_REGISTERED`.

Global verdict: **Closure V1 did not produce conclusive predictive corroboration; it did preserve a reproducible methodological and engineering contribution.**

## 6. Authorized claims

- `C01_holdout_population` [descriptive_available]: Closure V1 evaluated 88 held-out WQP locations, 4,488 origins and 13,464 origin-horizon attempts. (value/state `88;4488;13464`; denominator `13464`).
- `C02_intent_to_predict` [descriptive_available]: Failures and unavailable predictions remained in the intent-to-predict denominator. (value/state `retained`; denominator `13464`).
- `C03_primary_models_unavailable` [model_unavailable]: P0, P1 and A2 were unavailable and were not substituted. (value/state `model_unavailable`; denominator `3 models`).
- `C04_brier_observation_weighted` [descriptive_available]: B2 had the lowest observation-weighted Brier score at horizons 1, 2 and 3 among estimable branches; each rank is accompanied by its exact attempted, successful and metric-evaluable denominators and rates. (value/state `h1=B2:mean=0.1554:success_rate=0.184269:evaluable_rate=0.184269|h2=B2:mean=0.1597:success_rate=0.191176:evaluable_rate=0.191176|h3=B2:mean=0.1659:success_rate=0.182487:evaluable_rate=0.182487`; denominator `h1:attempted=22440:successful=4135:evaluable=4135|h2:attempted=22440:successful=4290:evaluable=4290|h3:attempted=22440:successful=4095:evaluable=4095`).
- `C05_pr_auc_observation_weighted` [descriptive_available]: A1 had the highest observation-weighted PR-AUC at horizon 1, while B2 had it at horizons 2 and 3 among estimable branches; each rank is accompanied by its exact attempted, successful and metric-evaluable denominators and rates. (value/state `h1=A1:mean=0.6105:success_rate=0.141488:evaluable_rate=0.141488|h2=B2:mean=0.6287:success_rate=0.191176:evaluable_rate=0.191176|h3=B2:mean=0.6024:success_rate=0.182487:evaluable_rate=0.182487`; denominator `h1:attempted=22440:successful=3175:evaluable=3175|h2:attempted=22440:successful=4290:evaluable=4290|h3:attempted=22440:successful=4095:evaluable=4095`).
- `C06_f1_vs_f0_absolute_error` [descriptive_available]: F1 had higher absolute error than F0 in all 15 estimated exact-shared-row seed-horizon comparisons. (value/state `positive in 15/15`; denominator `15`).
- `C07_anfis_ablation` [descriptive_available]: Relative to A0 on exact common rows, A1 had higher PR-AUC at three horizons, lower Brier at three, and lower MAE at two of three. (value/state `3/3;3/3;2/3`; denominator `3175;3125;3045 common rows`).
- `C08_anfis_missing_diagnostics` [insufficient_support]: The three prespecified learning-curve sizes and the membership-stability analysis remained unavailable. (value/state `0/4`; denominator `4`).
- `C09_site_transfer` [insufficient_support]: None of the 1,050 registered legacy-to-holdout site-transfer cells was estimable because the legacy evaluation surface was not frozen before E0-U. (value/state `0`; denominator `1050`).
- `C10_thresholds` [descriptive_available]: Threshold sensitivity is reported for 25, 30, 33 and 50 micrograms per litre. (value/state `25;30;33;50`; denominator `reported per cutoff`).
- `C11_trophic_b2_vs_b1` [descriptive_available]: B2 improved on B1 in all four ordinal metrics in each of 15 proxy/reference-by-horizon summaries. (value/state `15/15`; denominator `15 reference-horizon cells`).
- `C12_degradation` [model_unavailable]: All 78 registered M0-versus-P1 degradation cells were unavailable because P1 was unavailable. (value/state `0`; denominator `78`).
- `C13_uncertainty` [descriptive_available]: Raw Gaussian was within the sealed 0.05 coverage margin in 30 of 30 primary A0/A1 groups, versus 26 of 30 for locked conformal; locked conformal was closer in 5 of 30 paired groups and wider in all 30. (value/state `raw_within=30/30;locked_within=26/30;locked_closer=5/30;locked_wider=30/30;mean_abs_error_raw=0.015565;median_abs_error_raw=0.013386;mean_abs_error_locked=0.032271;median_abs_error_locked=0.030872`; denominator `30 paired primary groups`).
- `C14_multiplicity` [descriptive_available]: Holm universes A=3, B=78, C=1, D=9 and E=1 were retained despite non-estimability. (value/state `A3;B78;C1;D9;E1`; denominator `92 cells`).
- `C15_planning` [model_unavailable]: All nine preregistered planning actions were non-estimable. (value/state `model_unavailable`; denominator `9 actions`).
- `C16_software` [descriptive_available]: E10 verified 338 passing public tests with 9 justified skips, three passing end-to-end tests, a valid 69-path/83-operation OpenAPI contract, and the sealed Python 3.14.7, FastAPI 0.138.1 and DVC 3.67.1 environment. (value/state `338 pass;9 skip;3 E2E;69 paths;83 operations;38 documented;Python 3.14.7;FastAPI 0.138.1;DVC 3.67.1`; denominator `6 source artifacts`).
- `C17_global_verdict_discussion` [insufficient_support]: Closure V1 provides no conclusive predictive corroboration, while preserving a reproducible engineering and methodological contribution. (value/state `no_conclusive_predictive_corroboration`; denominator `92 Holm cells plus 38 descriptive/limitation rows`).
- `C18_summary_boundary` [insufficient_support]: The summary may report descriptive available results and explicit non-estimability, but not replace unavailable P0, P1 or A2. (value/state `no substitution`; denominator `130 adjudication rows`).
- `C19_abstract_boundary` [insufficient_support]: The abstract may state the internal pseudoprospective scope and non-conclusive verdict, without claiming external validation or causal planning. (value/state `internal;non-conclusive;non-causal`; denominator `130 adjudication rows`).
- `C20_conclusion_boundary` [insufficient_support]: The conclusion may claim reproducibility and methodological traceability, not universal superiority, field causality or official management recommendations. (value/state `reproducible_methodological_contribution`; denominator `130 adjudication rows`).

## 7. Withdrawn or limited claims

Claims of external validation, a universal winner, confirmatory B2/A1 superiority, ANFIS saturation or stability, canonical GRU-D, direct monthly NLA-to-WQP transfer, E6 robustness, global calibration, E9 causality/net benefit/optimality, and official recommendations remain withdrawn or limited.
It is also prohibited to interpret `not_estimable` as a zero effect, equivalence, failure, or negative evidence, or to present E10 verification as scientific efficacy.

## 8. Replacement tables and figures

T01-T12 and F01-F08 replace earlier Closure V1 results and are deterministic descendants of published structured artifacts. Their sealed captions are:

- **T01** — T01. Model and experiment availability in the internal WQP holdout; weighting not applicable; horizons of 1, 2, and 3 months; intent_to_predict and successful denominators as recorded; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: P0, P1, and A2 remain model_unavailable without substitution.
- **T02** — T02. Intent-to-predict funnel for the internal WQP holdout; weighting preserved by estimand; horizons of 1, 2, and 3 months; attempted and successful denominators published in E1; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: failures remain in the denominator and no complete-case filtering is applied.
- **T03** — T03. Dual benchmark in the internal WQP holdout; observation_weighted and site_weighted estimands kept separate; horizons of 1, 2, and 3 months; metric_evaluable_origins denominators published by row; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: no universal winner is inferred and unavailable models are not substituted.
- **T04** — T04. Paired descriptive F1-F0 and A1-A0 deltas in the internal WQP holdout; weighting preserved by contrast; horizons of 1, 2, and 3 months; exact_shared_success_intersection or common_row_count denominator as applicable to each row; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: no intervals or confirmatory significance are invented.
- **T05** — T05. Transfer across locations within the internal WQP holdout; weighting preserved for each estimand; horizons of 1, 2, and 3 months; per-location and per-origin denominators declared in E2; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: internal WQP transfer, not external geographic validation.
- **T06** — T06. Threshold sensitivity in the internal WQP holdout; E3 weighting preserved; horizons of 1, 2, and 3 months; metric_evaluable_origins denominator for each threshold; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: project thresholds, not official ecological standards.
- **T07** — T07. Trophic performance by proxy and reference in the internal WQP holdout; E4 weighting preserved; horizons of 1, 2, and 3 months when applicable; denominator published for each reference and proxy; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: NLA provides semantic provenance, not direct monthly transfer of WQP targets.
- **T08** — T08. Multiplicity ledger for the internal WQP holdout; weighting defined by each registered estimand; horizons of 1, 2, and 3 months; Holm universes A=3, B=78, C=1, D=9, and E=1 without reduction; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: not_estimable does not mean zero effect or equivalence.
- **T09** — T09. ANFIS ablation in the locked WQP cohort; weighting and per-seed summary preserved from E7; horizons of 1, 2, and 3 months when applicable; denominators published by module and seed; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: descriptive evidence does not replace unavailable confirmatory comparisons.
- **T10** — T10. Calibration and uncertainty in the internal WQP holdout; equal_weight_endpoints_and_horizons weighting for the registered contrast and published weights for diagnostics; horizons of 1, 2, and 3 months; exact_shared_rows denominator; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: the confirmatory contrast requiring P1 is not_estimable without additional recalibration.
- **T11** — T11. E6/E9 unavailability in the internal WQP holdout; registered paired-degradation and planning estimands; horizons of 1, 2, and 3 months; published intended_prediction_row_count and row_count denominators; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: E6 is completed_unavailable and nine E9 actions are model_unavailable, without reconstruction or field causality.
- **T12** — T12. Software reproducibility evidence for Closure V1; weighting and horizon not applicable; test and contract counts declared in the recovery_2 manifest; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: certification of the published artifact, not prospective field validation.
- **F01** — F01. Cohort flow and availability for the locked internal WQP holdout; weighting not applicable; horizons of 1, 2, and 3 months; registered cohort and availability denominators; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: P0, P1, and A2 are shown as unavailable, never as zero.
- **F02** — F02. Primary performance in the internal WQP holdout; separate panels for observation_weighted and site_weighted; horizons of 1, 2, and 3 months; denominator published by metric; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: estimands are not mixed and unavailable models are labeled N/A.
- **F03** — F03. Paired descriptive deltas in the internal WQP holdout; weighting preserved by contrast; horizons of 1, 2, and 3 months; common denominators published by E1/E7; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: descriptive points without invented intervals or a universal conclusion.
- **F04** — F04. Metric sensitivity to thresholds in the internal WQP holdout; E3 weighting preserved; horizons of 1, 2, and 3 months; metric_evaluable_origins denominator by threshold; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: project thresholds, not official ecological standards.
- **F05** — F05. Semantic and proxy-based trophic evidence for WQP and the declared references; E4 weighting preserved; horizons of 1, 2, and 3 months when applicable; denominator published by reference; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: NLA does not directly validate monthly WQP targets.
- **F06** — F06. Raw and locked uncertainty coverage in the internal WQP holdout; published weights and the equal_weight_endpoints_and_horizons contrast; horizons of 1, 2, and 3 months; denominator by group and exact_shared_rows when applicable; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: no recalibration is performed and the contrast requiring P1 remains N/A.
- **F07** — F07. H1-H5b verdicts for the internal WQP holdout; weighting defined by each estimand; horizons of 1, 2, and 3 months; registered denominators and Holm universes without substitution; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: for H1, direct ANFIS evidence is separated from auxiliary B1/B2 context, descriptive support is not elevated to confirmation, and not_estimable remains explicit.
- **F08** — F08. Closure V1 provenance R-H1/P1/U1-H2/P2/U2-H3/P3/U3-H4-F; weighting and horizon not applicable; component and artifact denominators declared by each freeze; authority ea8ddce7f8edb9a61db97e29178e52603fa371b1; limitation: reproducible traceability does not demonstrate scientific effectiveness or field causality.

## 9. LaTeX sections to modify after approval

Target file, only after formal R-SYN approval: `private/mifal_ed_t2/mifal_ed_modelo_tesis_v5.tex`.

- Chapter III — `source_id + site_id` unit; cutoff-safe 353/88 split; 12-month history and h1/h2/h3; temporal roles; no-current surface; five seeds as slots; catalog/availability; intent-to-predict; E1-E10; separate estimands; Holm; recoveries; and manifest-last publication.
- Chapter IV — freeze/cohort; funnel; E1; E2; E3; E4; E5; E6; E7; E8; E9; separate E10; H1-H5b matrix, in that order.
- Chapter V — discussion, limitations, no substitution, internal WQP scope, refutability, and global conclusion.
- Summary and abstract — internal scope, bounded descriptive results, unavailable P0/P1/A2, and a non-conclusive verdict.
- Contribution list and general conclusion — separate reproducibility from predictive efficacy.
- Reproducibility appendix — topology, activations/receipts, exact52/exact53, DVC pointers, E10/OpenAPI, Holm, and guards, without turning inodes or local paths into scientific claims.

## 10. Claim → artifact → metric → limitation

| claim | destination | state | artifact | metric | value/state | denominator | limitation |
|---|---|---|---|---|---|---|---|
| C01_holdout_population | III | descriptive_available | reports/closure_v1/01_surface/locked_evaluation_input_summary.json | site/origin/attempt counts | 88;4488;13464 | 13464 | Internal pseudoprospective location holdout. |
| C02_intent_to_predict | III | descriptive_available | reports/closure_v1/01_benchmark/model_metrics_long.csv | attempted versus successful denominator | retained | 13464 | Availability is part of the estimand. |
| C03_primary_models_unavailable | IV | model_unavailable | reports/closure_v1/03_calibration/model_availability.csv | availability_state | model_unavailable | 3 models | No replacement or imputation is permitted. |
| C04_brier_observation_weighted | IV | descriptive_available | reports/closure_v1/01_benchmark/model_metrics_long.csv | five-seed mean Brier rank/value plus successful and evaluable rates | h1=B2:mean=0.1554:success_rate=0.184269:evaluable_rate=0.184269\|h2=B2:mean=0.1597:success_rate=0.191176:evaluable_rate=0.191176\|h3=B2:mean=0.1659:success_rate=0.182487:evaluable_rate=0.182487 | h1:attempted=22440:successful=4135:evaluable=4135\|h2:attempted=22440:successful=4290:evaluable=4290\|h3:attempted=22440:successful=4095:evaluable=4095 | The ranking is estimand-specific and descriptive. |
| C05_pr_auc_observation_weighted | IV | descriptive_available | reports/closure_v1/01_benchmark/model_metrics_long.csv | five-seed mean PR-AUC rank/value plus successful and evaluable rates | h1=A1:mean=0.6105:success_rate=0.141488:evaluable_rate=0.141488\|h2=B2:mean=0.6287:success_rate=0.191176:evaluable_rate=0.191176\|h3=B2:mean=0.6024:success_rate=0.182487:evaluable_rate=0.182487 | h1:attempted=22440:successful=3175:evaluable=3175\|h2:attempted=22440:successful=4290:evaluable=4290\|h3:attempted=22440:successful=4095:evaluable=4095 | The horizon-specific ranking is descriptive. |
| C06_f1_vs_f0_absolute_error | IV | descriptive_available | reports/closure_v1/01_benchmark/model_comparison_paired.csv | mean_loss_difference_F1_minus_F0 | positive in 15/15 | 15 | The comparison has no inferential interval and does not establish universal model superiority. |
| C07_anfis_ablation | IV | descriptive_available | reports/closure_v1/07_anfis_ablation_evaluation/ablation_pairwise.csv | delta PR-AUC/Brier/MAE directions | 3/3;3/3;2/3 | 3175;3125;3045 common rows | No interval, membership-stability or saturation claim is available. |
| C08_anfis_missing_diagnostics | IV | insufficient_support | reports/closure_v1/11_synthesis/THESIS_TABLES/T09_anfis_ablation.csv | completed diagnostics | 0/4 | 4 | The absence of these diagnostics blocks saturation and membership-stability claims. |
| C09_site_transfer | IV | insufficient_support | reports/closure_v1/02_site_transfer/generalization_gap.csv | estimable site-transfer cells | 0 | 1050 | This is internal WQP transfer and not external geographic validation. |
| C10_thresholds | IV | descriptive_available | reports/closure_v1/03_thresholds/threshold_prevalence.csv | prevalence/support/rank stability | 25;30;33;50 | reported per cutoff | The 50 threshold has sparse support. |
| C11_trophic_b2_vs_b1 | IV | descriptive_available | reports/closure_v1/11_synthesis/THESIS_TABLES/T07_trophic_performance.csv | macro-F1/kappa higher and ordinal-MAE/severe-error lower | 15/15 | 15 reference-horizon cells | These are internal proxy and derived-reference comparisons, not direct NLA target transfer. |
| C12_degradation | IV | model_unavailable | reports/closure_v1/06_degradation/failure_registry.csv | estimable degradation cells | 0 | 78 | Unavailable cells are not zero effects and were not reconstructed. |
| C13_uncertainty | IV | descriptive_available | reports/closure_v1/08_uncertainty/uncertainty_ledger.csv | paired coverage-margin, closeness, width and mean/median absolute-error diagnostics | raw_within=30/30;locked_within=26/30;locked_closer=5/30;locked_wider=30/30;mean_abs_error_raw=0.015565;median_abs_error_raw=0.013386;mean_abs_error_locked=0.032271;median_abs_error_locked=0.030872 | 30 paired primary groups | Locked conformal did not improve these diagnostics uniformly and this is not global calibration. |
| C14_multiplicity | IV | descriptive_available | reports/closure_v1/05_inference/multiplicity_report.csv | registered universe size | A3;B78;C1;D9;E1 | 92 cells | Non-estimability is not a zero effect. |
| C15_planning | IV | model_unavailable | reports/closure_v1/09_planning/planning_bootstrap.csv | delta_objective_vs_no_action/CI/p-value availability | model_unavailable | 9 actions | No causal, net-benefit or optimality claim is authorized. |
| C16_software | IV | descriptive_available | reports/closure_v1/11_synthesis/THESIS_TABLES/T12_software_evidence.csv | tests/OpenAPI/E2E/runtime state | 338 pass;9 skip;3 E2E;69 paths;83 operations;38 documented;Python 3.14.7;FastAPI 0.138.1;DVC 3.67.1 | 6 source artifacts | Software verification does not validate scientific utility. |
| C17_global_verdict_discussion | V | insufficient_support | reports/closure_v1/11_synthesis/FINAL_CLOSURE_MATRIX.csv | global thesis verdict | no_conclusive_predictive_corroboration | 92 Holm cells plus 38 descriptive/limitation rows | The engineering contribution is distinct from predictive corroboration. |
| C18_summary_boundary | Summary | insufficient_support | reports/closure_v1/11_synthesis/FINAL_CLOSURE_MATRIX.csv | authorized synthesis boundary | no substitution | 130 adjudication rows | Every unavailable result remains labelled and denominator-preserving. |
| C19_abstract_boundary | Abstract | insufficient_support | reports/closure_v1/11_synthesis/FINAL_CLOSURE_MATRIX.csv | authorized abstract boundary | internal;non-conclusive;non-causal | 130 adjudication rows | The scope is internal WQP and descriptive where available. |
| C20_conclusion_boundary | Conclusion | insufficient_support | reports/closure_v1/11_synthesis/FINAL_CLOSURE_MATRIX.csv | authorized conclusion boundary | reproducible_methodological_contribution | 130 adjudication rows | Reproducibility is not scientific efficacy. |

The machine-readable source for this section is `THESIS_CLAIM_EVIDENCE_MATRIX.csv`. The manuscript remains out of scope until the report, both matrices, and the published R-SYN bundle are approved.
