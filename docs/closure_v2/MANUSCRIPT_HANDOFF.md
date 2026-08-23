# Closure V2 manuscript handoff

## 1. Purpose

This document is the canonical post-certification handoff for the person or
agent updating the final LaTeX thesis. It makes the editorial work executable
without reopening raw outcomes, recalculating metrics, selecting favorable
results, or inferring scientific wording from plots.

The Closure V2 experiment and software certification are complete. This
handoff is additive documentation created after the certified tag. It does not
change any scientific result, denominator, claim boundary, model, data file,
or certification predicate.

## 2. Frozen authorities

| Authority | Commit or digest | Function |
|---|---|---|
| Closure V1 terminal tag | `eb07598aa54a0944d1a87fe46d62415d0a4454aa` | Immutable historical evidence |
| Closure V2 protocol tag | `5ebc8c632a0f55eda38da9f14e30942b0a1ed12f` | Pre-outcome protocol |
| Closure V2 development tag | `23449e5b781dd15b46b4eed7ddd4e6f7d6d37ea8` | Development freeze |
| Closure V2 model-lock tag | `8388d29f9e962ae13e2f2510f3c57ae3bac0a944` | Frozen model selection and calibration authority |
| Closure V2 result authority | `e85990193ce2c97cbf7b2f200e8320fa05bbe5ac` | P16 scientific result inputs |
| Closure V2 synthesis commit | `60e799f416dd6db2474c4aeeb7c542d84e8d3759` | Tables, figures, claims, and final synthesis |
| Closure V2 terminal tag | `dafb115ce67aa7c9c910ef6f83a17123e5bf4e7e` | Certified thesis evidence |
| Synthesis manifest SHA-256 | `699c6f37530de3f5ea447e1605a7a552add820d1a267ab3a9af53c173bb6a608` | Binds the P17 package |
| Certification manifest SHA-256 | `c812e1c7c3e171341101fe8e0d0192af976d64ef9bfad6979b0e7e819e75e64c` | Binds the P18 package |

The terminal tag name is `thesis-closure-v2`. Do not move or recreate that
tag. A future handoff commit may be a descendant of the tag, but the certified
evidence directories must remain byte-identical to the tagged versions.

Before editing the thesis, verify:

```bash
git rev-parse thesis-closure-v2^{}
git merge-base --is-ancestor thesis-closure-v2 HEAD
git diff --exit-code thesis-closure-v2 -- \
  reports/closure_v2/08_synthesis \
  reports/closure_v2/09_certification
```

The first command must print
`dafb115ce67aa7c9c910ef6f83a17123e5bf4e7e`; the other commands must exit
successfully.

## 3. Required reading order

Read these files in order before changing LaTeX:

1. `reports/closure_v2/08_synthesis/FINAL_CLOSURE_REPORT.md`
2. `reports/closure_v2/08_synthesis/MANUSCRIPT_CHANGE_MAP.md`
3. `reports/closure_v2/08_synthesis/THESIS_CLAIM_EVIDENCE_MATRIX.csv`
4. `reports/closure_v2/08_synthesis/FINAL_CLOSURE_MATRIX.csv`
5. `reports/closure_v2/08_synthesis/THESIS_TABLES/T14_hypothesis_adjudication.csv`
6. `reports/closure_v2/09_certification/FINAL_CERTIFICATION_REPORT.md`
7. `docs/closure_v2/CLAIM_BOUNDARIES.md`
8. `docs/closure_v2/ANALYSIS_PLAN.md`

The claim matrix is the authority for claim-level cohort, estimand,
denominator, source artifact, limitation, allowed wording, and forbidden
wording. The final report is the narrative authority. If prose drafted for the
thesis conflicts with either file, revise the prose rather than the evidence.

## 4. Evidence layers that must remain separate

### 4.1 Development

- 9,732 total intent origins.
- 9,413 fit-intent origins in training and model selection.
- 8,925 complete-case shared-fit rows.
- 488 fit-intent rows were retained in the ledger but excluded from model
  loss because they were incomplete.
- Five registered P0 slots and five registered P1 slots were trained and
  calibrated without replacement.
- Seeds are algorithmic slots, not ecological replications.

### 4.2 Fresh primary evaluation

- Evidence label: `fresh_primary`.
- 2,286 origins from 137 WQP monitoring locations unused by Closure V1.
- This is the strongest internal Closure V2 evidence layer.
- It is not external validation and does not establish performance on unseen
  waterbody populations.

### 4.3 Legacy post hoc evaluation

- Evidence label: `legacy_posthoc`.
- 4,488 origins from the 88 previously opened Closure V1 locations.
- It is retrospective complementary evidence.
- It cannot overturn or be pooled with the fresh-primary result.

Every reported metric must retain its cohort and estimand. Never pool
`fresh_primary` with `legacy_posthoc`, and never pool observation-weighted
with site-weighted estimates.

## 5. Scientific result that the thesis must preserve

Closure V2 resolved the previous structural non-estimability: P0 and P1 were
successfully fitted, calibrated, and evaluated. The result was negative for
the adaptive P1 branch on the registered fresh-primary comparisons.

- P1 versus B2 was inferior for observation-weighted Brier and PR-AUC at
  horizons h1, h2, and h3.
- P1 versus P0 had inconclusive Brier differences and inferior PR-AUC at h1,
  h2, and h3.
- The shared fresh-primary denominators by horizon were 966, 933, and 885.
- P1 was descriptively favorable to P0 in all 12 registered legacy-posthoc
  rows, but that evidence is retrospective and complementary.
- Uncertainty results are model-, cohort-, and horizon-specific; there is no
  global calibration guarantee.
- Degradation was evaluated under identical deterministic simulated masks;
  no universal M0-P1 crossover was found.
- None of the nine registered fresh-primary planning actions exceeded
  `no_action` after the registered cost, support, and uncertainty penalties;
  Holm rejected none.

The thesis may state that P1 became estimable but did not demonstrate an
advantage on the fresh-primary surface. It must not state that P1 is
universally inferior, that Closure V2 is external validation, or that the
planning simulation demonstrates field causality.

## 6. Hypothesis adjudication

| Hypothesis | Closure V2 verdict | Required interpretation |
|---|---|---|
| H1 | `not_supported_on_fresh_primary` | The adaptive state did not improve predictive utility over P0; this is not an interpretability test. |
| H2 | `estimable_negative_result` | P1 was inferior to B2 on the registered fresh-primary contrasts. |
| H3 | `partial_descriptive_support` | Uncertainty and simulated degradation are estimable only at their published model/scenario granularity. |
| H4 | `estimable_descriptive_contrast` | M0-P1 robustness contrasts exist, without a universal crossover or causal claim. |
| H5a | `not_supported` | No registered simulated action improved the penalized objective; this is not a field recommendation. |
| H5b | `not_estimable_registered_scope` | A separate observed field net-benefit endpoint was not registered. |

Use `T14_hypothesis_adjudication.csv` for the complete V1/V2 comparison,
denominators, limitations, and decisive artifacts.

## 7. Section-by-section editing plan

| Thesis target | Claims | Primary tables | Primary figures | Required message |
|---|---|---|---|---|
| Resumen | C04, C05, C06, C14, C15 | T01, T06, T07, T14 | F05, F10 | P0/P1 became estimable; fresh-primary did not support adaptive P1 superiority. |
| Abstract | C01, C05, C06, C16 | T04, T06, T07 | F04, F05 | Internal evaluation on WQP monitoring locations unused by V1 produced a bounded negative result. |
| Chapter III | C01-C04 | T01, T02, T03, T12 | F01, F02, F09 | Describe complete-case shared fit, retained attrition, registered slots, and separate evidence layers. |
| Chapter IV | C05-C11 | T04-T11, T14 | F03-F08, F10 | Present fresh-primary first, legacy-posthoc separately, and retain negative and non-estimable results. |
| Chapter V | C12-C14, C17 | T12-T14 | F09, F10 | Distinguish reproducibility from efficacy and V2 additive evidence from frozen V1 evidence. |
| Appendices | C01-C17 | T01-T14 | F01-F10 | Preserve hashes, provenance, row filters, denominators, captions, and claim boundaries. |

The detailed allowed and forbidden wording for each target remains in
`MANUSCRIPT_CHANGE_MAP.md`. The row-level authority remains
`THESIS_CLAIM_EVIDENCE_MATRIX.csv`.

## 8. Table inventory

All tables are Git-tracked CSV files under
`reports/closure_v2/08_synthesis/THESIS_TABLES/`.

| ID | File | Editorial use |
|---|---|---|
| T01 | `T01_model_availability.csv` | Ten registered model slots and availability |
| T02 | `T02_fit_eligibility_attrition.csv` | Intent, fit-intent, eligible, and excluded denominators |
| T03 | `T03_eligibility_bias.csv` | Complete-case eligibility bias diagnostics |
| T04 | `T04_benchmark_observation_weighted.csv` | Observation-weighted benchmark metrics by cohort |
| T05 | `T05_benchmark_site_weighted.csv` | Site-weighted benchmark metrics by cohort |
| T06 | `T06_p1_vs_b2_inference.csv` | Registered P1-B2 effects and adjudication |
| T07 | `T07_p1_vs_p0_inference.csv` | Registered P1-P0 effects and adjudication |
| T08 | `T08_threshold_sensitivity.csv` | Predeclared threshold sensitivity |
| T09 | `T09_uncertainty.csv` | Coverage and interval diagnostics |
| T10 | `T10_degradation_m0_p1.csv` | Matched simulated-degradation evidence |
| T11 | `T11_planning.csv` | Penalized planning objective contrasts |
| T12 | `T12_v1_v2_evidence_boundary.csv` | Frozen V1 versus additive V2 provenance |
| T13 | `T13_software_evidence.csv` | Reproducibility and software evidence |
| T14 | `T14_hypothesis_adjudication.csv` | H1-H5b terminal verdicts |

Do not edit these CSV files for presentation. Transform them inside the LaTeX
project with a reproducible script or a table-generation layer. Preserve the
source filename and row filter in the table note or appendix traceability
ledger. Rounding for display must not replace the source values.

## 9. Figure inventory and caption boundaries

All figures are deterministic SVG files under
`reports/closure_v2/08_synthesis/THESIS_FIGURES/`.

| ID | File | Caption boundary |
|---|---|---|
| F01 | `F01_fit_eligibility_funnel.svg` | Complete-case attrition with all intent rows retained in the ledger |
| F02 | `F02_eligibility_bias.svg` | Descriptive eligibility imbalance, not a causal missingness model |
| F03 | `F03_training_curves.svg` | Algorithmic slots and training trajectories, not ecological replication |
| F04 | `F04_benchmark_metrics_availability.svg` | Metric availability on fresh-primary with explicit model/cohort/horizon |
| F05 | `F05_paired_effects.svg` | Registered paired effects; direction depends on the metric definition |
| F06 | `F06_calibration_uncertainty.svg` | Model/cohort/horizon-specific interval diagnostics |
| F07 | `F07_degradation_curves.svg` | Robustness under simulated deterministic missingness only |
| F08 | `F08_planning_effects.svg` | Penalized simulated objective contrasts, not causal interventions |
| F09 | `F09_v1_v2_provenance.svg` | V1 frozen evidence and V2 additive evidence must remain separate |
| F10 | `F10_hypothesis_verdicts.svg` | Terminal bounded H1-H5b adjudication |

If the LaTeX toolchain cannot include SVG directly, convert SVG to PDF in the
thesis repository. Keep the original SVG untouched, record the conversion
command and tool version, and visually compare the PDF with the source. Do not
redraw or simplify plots manually.

## 10. Model and terminology rules

- Call P0 and P1 residual probabilistic GRU models over engineered states.
- Do not call either branch canonical GRU-D. The implementation does not
  contain the explicit mask and learned temporal-decay mechanism required for
  that name.
- Call `fresh_primary` an internal evaluation on WQP monitoring locations
  unused by V1.
- Call `legacy_posthoc` retrospective complementary evidence.
- Call the degradation analysis simulated missingness robustness.
- Call planning a simulated penalized objective analysis.
- Call the P18 result a software/reproducibility certification, never an
  efficacy certification.

## 11. Prohibited transformations and claims

The thesis editor must not:

- reopen raw outcomes or recompute metrics;
- refit, rescore, recalibrate, or select a different seed;
- drop failed, unavailable, negative, or non-estimable rows;
- pool evaluation cohorts or estimands;
- replace denominators with a single global sample size;
- use seed variability as ecological replication;
- describe fresh-primary as external or prospective validation;
- describe threshold values as official ecological standards;
- infer field robustness from simulated missingness;
- infer causal management effects from planning rollouts;
- claim universal P1 inferiority, universal model superiority, or certified
  scientific efficacy;
- alter Closure V1 wording as if V2 retroactively corrected V1.

## 12. Recommended LaTeX workflow

1. Record the starting commit and a clean status in the thesis repository.
2. Create a dedicated thesis-update branch.
3. Copy or reference only the Git-tracked synthesis assets listed here.
4. Add stable LaTeX labels such as `tab:closure-v2-t06` and
   `fig:closure-v2-f05`; maintain an ID-to-label ledger.
5. Draft methods and evidence-layer definitions before results prose.
6. Insert fresh-primary results before legacy-posthoc results.
7. Add cohort, estimand, denominator, and limitation to every table or figure
   note.
8. Trace every new or revised sentence to a claim ID C01-C17.
9. Build the thesis from a clean auxiliary-file state using the project's
   existing reproducible build command.
10. Review the rendered PDF for clipped tables, unreadable legends, broken
    cross-references, missing citations, and altered mathematical signs.
11. Run the acceptance checklist below before requesting editorial review.

The thesis repository should record its own conversion scripts and generated
PDF/table wrappers. Those presentation artifacts do not belong in this
evidence repository unless a separate publication policy explicitly requires
them.

## 13. Traceability ledger required in the thesis project

Create a small ledger in the thesis project with at least these columns:

```text
thesis_section
latex_label
claim_id
source_artifact
row_filter
cohort
estimand
denominator
display_rounding
limitation
source_commit
```

Use `dafb115ce67aa7c9c910ef6f83a17123e5bf4e7e` as `source_commit` for the
certified handoff package. A sentence may cite multiple claims, but every
numerical assertion must resolve to a source artifact and row filter.

## 14. Acceptance checklist

### Authority and integrity

- [ ] `thesis-closure-v2^{}` resolves to the certified terminal commit.
- [ ] Synthesis and certification directories match the tagged blobs.
- [ ] The synthesis and certification manifest SHA-256 values match Section 2.
- [ ] No raw outcome or private file was used during manuscript editing.

### Scientific content

- [ ] Development, fresh-primary, and legacy-posthoc layers are distinct.
- [ ] Observation-weighted and site-weighted estimands are distinct.
- [ ] All denominators are copied from the claim matrix or source table.
- [ ] The 488 incomplete fit-intent rows remain visible in the narrative.
- [ ] Fresh-primary negative results precede retrospective favorable results.
- [ ] H1-H5b wording matches T14.
- [ ] Uncertainty, degradation, and planning limitations are explicit.
- [ ] No prohibited claim from Section 11 appears.

### LaTeX and presentation

- [ ] Every imported table and figure has a stable LaTeX label.
- [ ] Every caption names cohort, estimand, and limitation when applicable.
- [ ] Table rounding is documented and source values remain unchanged.
- [ ] SVG conversions are reproducible and visually verified.
- [ ] All references and citations resolve in the final PDF.
- [ ] The thesis build passes from a clean state.
- [ ] The thesis traceability ledger covers every revised numerical claim.

## 15. Completion receipt for the thesis editor

At handoff completion, report:

- thesis repository URL or identifier;
- starting and terminal thesis commits;
- changed LaTeX files;
- imported tables and figures by T/F ID;
- incorporated claims by C ID;
- thesis build command and exit status;
- rendered PDF hash;
- traceability-ledger path;
- unresolved editorial decisions or limitations.

Do not record credentials, private bucket URLs, local absolute paths, or raw
outcome paths in that receipt.

## 16. Handoff completion state

This repository-side handoff is complete when this document is reviewed and
published as a descendant of `thesis-closure-v2` without changing the tagged
synthesis or certification bundles. The actual LaTeX edits, PDF build, and
editorial approval belong to the thesis project and are intentionally outside
the Closure V2 evidence repository.
