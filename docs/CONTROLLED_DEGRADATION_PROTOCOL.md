# Controlled Degradation Protocol

This document defines the first controlled-degradation protocol for
`lentic-pipe`. It is a protocol and scenario design only; it does not report
executed degradation results.

## Purpose

Controlled degradation tests whether the project remains useful when the
available environmental evidence becomes weaker. This is different from simply
optimizing model performance: the objective is to expose failure modes under
realistic data loss, sparse monitoring, and partial-variable settings.

The protocol supports the doctoral claim that the system is reproducible,
auditable, and honest about limits. Every degradation run must preserve the
frozen target labels, leakage-safe temporal splits, and source-scoped site
identity.

## Verified Basis

The scenario criteria are grounded in the repository and external source
definitions:

| Basis | Source | Design implication |
|---|---|---|
| The project models algal proliferation and trophic state in lentic water bodies using frozen data, temporal splits, fuzzy scoring, PIPE/GRU-D, and DVC-backed artifacts. | `README.md` | Degradation must be reproducible, split-safe, and artifact-tracked. |
| The freeze defines canonical panel, target, split, and hash surfaces. | `data/freeze/DATA_FREEZE.md` | Degradation must not silently change the freeze or target labels. |
| Temporal splits keep only rows where origin and target are in the same split and report zero leakage rows. | `data/splits/SPLIT_REPORT.md`, `data/splits/split_manifest.json` | Degradation must operate inside existing split boundaries. |
| Canonical variables include Chl-a, nutrients, dissolved oxygen, pH, turbidity, temperature, and Secchi depth with ecological roles. | `configs/variables.yaml` | Feature-family degradation should follow ecological roles, not arbitrary column order. |
| NLA is a statistical survey of U.S. lakes, ponds, and reservoirs. | EPA National Lakes Assessment: <https://www.epa.gov/national-aquatic-resource-surveys/nla> | NLA should remain validation/provenance/enrichment unless crosswalk acceptance changes. |
| WQP integrates publicly available water-quality data from USGS, EPA, and many other organizations. | Water Quality Portal: <https://www.waterqualitydata.us/> | Source and site coverage degradation should be explicit because provider coverage is heterogeneous. |
| GRU-D was designed for multivariate time series with missing values and uses masking/time-gap information. | Che et al., GRU-D: <https://arxiv.org/abs/1606.01865> | Temporal missingness and missing-pattern stress tests are relevant to PIPE/GRU-D. |
| Missingness mechanisms such as MCAR, MAR, MNAR, and structured missingness are distinct and can bias conclusions differently. | Missing-data review: <https://arxiv.org/abs/2404.04905> | The first protocol should separate random dropout, structured feature loss, and temporal blocks. |
| Iteration 2B selected `closest_pr` as the provisional downstream alert policy. | `docs/PIPE_ROLLOUT_ITERATION_2.md` | Degradation runs should use `closest_pr` as default and keep `fixed`/`fbeta` as comparisons. |

## Non-Goals

- Do not redefine the bloom threshold.
- Do not change target labels during evaluation.
- Do not accept cross-source site matches as truth.
- Do not use test rows for scenario selection.
- Do not present degraded alert outputs as official environmental alerts.
- Do not write heavy degraded row-level artifacts to Git.

## Default Alert Policy

The default downstream alert policy is:

```text
policy_version: pipe_grud_rollout_alert_policy_2b_v0
selection_objective: closest_pr
threshold_source: reports/pipe_grud/pipe_rollout_policy_2b_thresholds.csv
```

The `fixed` and `fbeta` policies remain comparison profiles. This lets later
work distinguish model robustness from alert-policy sensitivity.

## Evaluation Surface

The first degradation pass should evaluate the current frozen surface:

- panel and targets from `data/freeze/DATA_FREEZE.md`;
- temporal splits from `data/splits/split_manifest.json`;
- canonical variables from `configs/variables.yaml`;
- PIPE/GRU-D rollout evidence from Iterations 1, 2, and 2B;
- default alert policy `closest_pr`.

The first implementation should be evaluation-only where possible. Retraining
under degraded training data is a later phase because it is more expensive and
can obscure whether a failure comes from model learning or from operational
evidence loss.

## Recomputed Evaluation Modes

The protocol separates three evaluation modes:

- precomputed-score degradation: coverage/source/site scenarios that can be
  evaluated directly on existing scored backtest rows;
- PIPE state-input recomputation: controlled degradation of PIPE sequence input
  columns followed by frozen PIPE/GRU-D rollout recomputation;
- raw-predictor recomputation: degradation of monthly panel predictors followed
  by deterministic fuzzy-state rebuild, PIPE sequence rebuild, and frozen
  PIPE/GRU-D rollout recomputation.

The raw-predictor mode must preserve labels by construction. Degraded raw
predictors are allowed to change only the reconstructed input sequence consumed
by PIPE/GRU-D. Observed future fuzzy states, bloom labels, split membership,
model weights, calibrators, and alert thresholds remain fixed from the
undegraded canonical artifacts. Fuzzy IRC weights are loaded from the current
fuzzy manifest and are not re-optimized under degradation.

Raw-predictor degradation measures operational dependence of the current
pipeline. It must not be interpreted as ecological causal importance. In
particular, if a frozen model remains accurate after nutrient ablation while
using current Chl-a memory, the correct interpretation is that the current
model/alert surface can rely on a target-proximal Chl-a signal. It does not
mean nutrients are ecologically irrelevant to algal proliferation.

For early-warning claims, the project must distinguish two surfaces:

- monitoring/nowcasting: may use current Chl-a because it is an observed state
  indicator;
- no-current-Chl-a early warning: must estimate future Chl-a or bloom risk from
  upstream evidence such as nutrients, physicochemical conditions, light, and
  seasonality, using observed Chl-a only as the evaluation target.

When canonical variables are expanded onto the monthly panel, raw-family
ablations remove both direct monthly aggregates and their uncertainty/provenance
signals where they influence the fuzzy layer. For example, `TP_ugL` maps to
`mean_TP_ugL`, available aggregate/QC columns such as `qc_ok_rate_TP_ugL`, and
derived nutrient columns such as `log_TP` and `TN_TP_ratio`.

## Scenario Families

### 1. Control

The control scenario is the current, undegraded freeze-derived evaluation
surface. Every reported metric must include an absolute value and a delta
against this control.

### 2. Feature-Family Ablation

Feature-family ablations remove semantically related predictor families while
preserving labels. They answer: which ecological evidence family carries the
system?

Core families:

- `chlorophyll_memory`: `chlorophyll_a_ugL`, `log_chlorophyll_a`, `risk_chla`.
- `nutrients`: `TP_ugL`, `TN_ugL`, `TN_TP_ratio`, `log_TP`, `log_TN`.
- `light`: `secchi_depth_m`, `turbidity_NTU`.
- `physicochemical`: `temperature_C`, `DO_mgL`, `pH`.

These are core because they match the repository's canonical variable roles:
target/memory, nutrient pressure, light availability, and physicochemical
condition.

### 3. Random Value Dropout

Random dropout simulates generic loss of measurements. It should be applied to
predictors only and never to held-out labels. The core rates are:

- mild: 10%;
- moderate: 25%;
- severe: 50%.

Use deterministic seeds and report results per seed. The first implementation
should use MCAR-style random dropout only; MAR/MNAR-like mechanisms can be added
later after the first reproducible baseline exists.

### 4. Temporal Block Missingness

Temporal block missingness simulates gaps in monitoring. It removes contiguous
origin-month predictor evidence within source-scoped site histories while
leaving target labels fixed for evaluation.

Core block lengths:

- 1 month: missed visit;
- 3 months: seasonal or quarterly gap;
- 6 months: extended monitoring interruption.

Temporal blocks are especially important for PIPE/GRU-D because missing
patterns and time gaps are part of the modeling premise.

### 5. Site Retention

Site retention simulates reduced spatial monitoring coverage. It retains a
deterministic stratified sample of source-scoped sites and reports metrics on
the retained rows.

Core retention levels:

- 75% retained: mild contraction;
- 50% retained: moderate contraction;
- 25% retained: severe contraction.

Sampling must be stratified by `source_id` and split where possible so source
coverage changes are reported rather than hidden.

### 6. Source-Scope Diagnostics

Source-scope scenarios are diagnostic, not primary adoption criteria. They help
answer whether conclusions are driven by one source.

Core diagnostics:

- `wqp_only`: WQP is the current multivariable backbone.
- `no_wqp`: stress test for dependence on WQP.
- `aquamatch_chla_only`: Chl-a auxiliary coverage stress.
- `lakebed_us_cse_only`: small-source cautionary diagnostic.

NLA is not a direct target-transfer source under the current conservative
policy and should not be used as a monthly predictive target source unless a
reviewed crosswalk is promoted.

### 7. Combined Operational Stress

Combined scenarios approximate realistic failure regimes:

- `ops_moderate`: 25% random dropout, 3-month blocks at 10%, and 75% site
  retention.
- `ops_sparse_network`: nutrient family removed, 3-month blocks at 25%, and
  50% site retention.
- `ops_no_chla_memory`: Chl-a memory removed plus 3-month blocks at 10%.
- `ops_severe`: 50% random dropout, 6-month blocks at 25%, and 25% site
  retention.

Combined scenarios must be interpreted as stress tests, not estimates of a
specific real monitoring program.

## Metrics

Required metrics:

- rows retained;
- positive rate;
- PR-AUC;
- ROC-AUC;
- Brier score;
- precision;
- recall;
- specificity;
- F1;
- F2;
- MCC;
- balanced accuracy;
- alert rate;
- delta versus control for all performance metrics.

Report metrics by:

- scenario;
- split;
- horizon;
- source_id;
- event family where applicable (`bloom_h`, `irc_alert`);
- policy profile where applicable (`closest_pr`, `fixed`, `fbeta`).

## Artifact Plan

Configuration:

- `configs/degradation_scenarios.yaml`

Implemented evaluator:

- `src/experiments/evaluate_controlled_degradation.py`
- `src/experiments/evaluate_degraded_pipe_grud_rollouts.py`

Current evaluator scope:

- control, source-scope, and site-retention scenarios can be evaluated directly
  on precomputed rollout score rows;
- predictor-evidence degradation scenarios are recorded as
  `skipped_requires_model_recompute` by default, because scientific performance
  claims require recomputing model scores after the degraded predictors are
  applied;
- `--evaluate-passthrough-scores` exists only for diagnostics and must not be
  interpreted as degraded-model performance.

Recomputed PIPE/GRU-D evaluator scope:

- `evaluate_degraded_pipe_grud_rollouts.py` recomputes PIPE/GRU-D rollout
  scores after degrading PIPE sequence input columns;
- this is a state-level recomputation path, not a raw-predictor ablation path;
- it also evaluates the configured downstream alert-policy thresholds on the
  recomputed scores;
- the default state recomputation smoke set is
  `pipe_state_recompute_smoke`;
- raw-variable family ablations such as nutrients, light, and Chl-a memory
  still require an upstream rebuild of fuzzy states and sequence datasets.

Expected future small Git artifacts:

- `reports/degradation/controlled_degradation_metrics.csv`
- `reports/degradation/controlled_degradation_summary.csv`
- `reports/degradation/controlled_degradation_report.md`
- `reports/degradation/controlled_degradation_manifest.json`
- `reports/degradation/controlled_degradation_pipe_recomputed_state_metrics.csv`
- `reports/degradation/controlled_degradation_pipe_recomputed_alert_metrics.csv`
- `reports/degradation/controlled_degradation_pipe_recomputed_policy_metrics.csv`
- `reports/degradation/controlled_degradation_pipe_recomputed_summary.csv`
- `reports/degradation/controlled_degradation_pipe_recomputed_examples.csv`
- `reports/degradation/controlled_degradation_pipe_recomputed_report.md`
- `reports/degradation/controlled_degradation_pipe_recomputed_manifest.json`

Expected future DVC artifacts, only if row-level degraded tables are materialized:

- `data/degradation/controlled_degradation_rows.parquet`
- `reports/degradation/controlled_degradation_rows.parquet`
- `reports/degradation/controlled_degradation_pipe_recomputed_backtest_rows.parquet`

## Reproducibility Rules

1. Keep labels fixed for evaluation-only degradation.
2. Apply degradation to predictors only unless a training-scarcity phase is
   explicitly declared.
3. Use deterministic seeds from the config.
4. Report row counts before and after degradation.
5. Preserve source-scoped site identity.
6. Do not tune scenarios on test results.
7. Keep small reports in Git and heavy row-level outputs in DVC.
8. Record input/output/script SHA-256 hashes in the manifest.
9. Report failures and empty scenarios; do not silently drop them.
10. Treat degraded outputs as stress-test evidence, not operational alerts.
11. Report ranking metrics as `NA` when a group has only one observed class.

## Phased Execution Plan

Phase 0, completed by this protocol:

- define scenario criteria;
- create machine-readable config;
- document source rationale.

Phase 1, completed smoke step:

- run the implemented evaluator as a smoke test and inspect its summary;
- use control, source-scope, and site-retention metrics as valid
  precomputed-score degradation evidence;
- treat feature-family ablations, random dropout, temporal blocks, and combined
  predictor-degradation scenarios as queued until a model-score recomputation
  path is added;
- evaluate `closest_pr` as default and include `fixed`/`fbeta` comparisons.

Smoke execution, 2026-06-12:

- command: `poetry run python src/experiments/evaluate_controlled_degradation.py --scenario-set smoke`;
- regenerated after the ranking-metric guardrail was added;
- generated at UTC: `2026-06-12T16:47:25.964686+00:00`;
- input rows: 88,761;
- threshold rows: 42;
- metric rows: 648;
- summary rows: 8;
- evaluated runs: 5 across 3 unique scenarios;
- skipped runs: 3 across 3 unique scenarios;
- ranking metrics marked as `NA` for one-class groups: 21 rows;
- all input, output, and script SHA-256 hashes are recorded in
  `reports/degradation/controlled_degradation_manifest.json`;
- `score_recomputed` is false for this smoke run because the evaluator operates
  on precomputed rollout score rows.

Smoke interpretation:

- `site_retention_50` preserved approximately half of the rows and kept
  `closest_pr` test performance close to the undegraded control.
- `source_scope_wqp_only` changed both row mix and event prevalence, so its
  stronger IRC-alert recall/F2 should be treated as a source-scope diagnostic,
  not as evidence that WQP is intrinsically superior.
- Predictor-evidence degradation scenarios were intentionally skipped because
  they require recomputing model scores after degradation.

Phase 1, next technical step:

- run Iteration 1B, a source/site-coverage expansion that remains valid on
  precomputed score rows;
- keep Iteration 1B outputs separate from the smoke artifacts;
- after reviewing 1B, decide whether to implement the model-score recomputation
  path required for predictor-degradation scenarios.

Iteration 1B scenario set:

- `coverage_source_site`

Iteration 1B command:

```bash
poetry run python src/experiments/evaluate_controlled_degradation.py \
  --scenario-set coverage_source_site \
  --output-name coverage_source_site
```

Iteration 1B expected artifacts:

- `reports/degradation/controlled_degradation_coverage_source_site_metrics.csv`
- `reports/degradation/controlled_degradation_coverage_source_site_summary.csv`
- `reports/degradation/controlled_degradation_coverage_source_site_report.md`
- `reports/degradation/controlled_degradation_coverage_source_site_manifest.json`

Iteration 1B execution, 2026-06-12:

- generated at UTC: `2026-06-12T16:44:25.269542+00:00`;
- input rows: 88,761;
- threshold rows: 42;
- metric rows: 1,764;
- summary rows: 14;
- evaluated runs: 14 across 8 unique scenarios;
- skipped runs: 0;
- ranking metrics marked as `NA` for one-class groups: 72 rows;
- all input, output, and script SHA-256 hashes are recorded in
  `reports/degradation/controlled_degradation_coverage_source_site_manifest.json`;
- `score_recomputed` is false for this run because the evaluator operates on
  precomputed rollout score rows.

Iteration 1B interpretation:

- Site-retention scenarios at 75%, 50%, and 25% preserved `closest_pr`
  performance close to the control, with larger seed sensitivity for bloom than
  for IRC alert.
- `source_scope_wqp_only` increased IRC-alert recall/F2 but also changed event
  prevalence and alert rate, so it is a source-mix diagnostic rather than a
  claim that WQP is intrinsically superior.
- `source_scope_no_wqp` and `source_scope_aquamatch_chla_only` degraded
  IRC-alert performance, consistent with dependence on WQP-backed coverage for
  that alert surface.
- `source_scope_lakebed_us_cse_only` has too few rows for stable comparison and
  should be reported as insufficient-coverage evidence.

Phase 2:

- run a state-level PIPE/GRU-D recomputation smoke using
  `pipe_state_recompute_smoke`;
- inspect whether state-level degradation meaningfully changes rollout
  behavior before materializing row-level outputs;
- add combined operational stress scenarios;
- decide whether selected degraded row-level artifacts need DVC promotion.

State recomputation smoke command:

```bash
poetry run python src/experiments/evaluate_degraded_pipe_grud_rollouts.py \
  --scenario-set pipe_state_recompute_smoke \
  --output-name pipe_state_recompute_smoke \
  --deterministic \
  --max-origins 512
```

The smoke command is intentionally capped and deterministic. A full scientific
run should remove the cap, use the intended sampling configuration, and decide
explicitly whether to materialize `--backtest-rows` under DVC.

State recomputation smoke execution, 2026-06-12:

- generated at UTC: `2026-06-12T17:14:13.975172+00:00`;
- scenario set: `pipe_state_recompute_smoke`;
- split: `test`;
- selected origins: 512;
- rollout rows: 12,288 across 8 evaluated runs;
- state metric rows: 1,056;
- alert metric rows: 192;
- policy metric rows: 576;
- deterministic samples per origin: 1;
- calibrated bloom horizons: 1, 2, and 3;
- rollout bloom calibrator horizons: 1, 2, and 3;
- script hash:
  `54e56833a3e540d758f84e9d8dd3bde6d5b3b7cb64019d4d056667f389f22041`;
- all input, output, and script SHA-256 hashes are recorded in
  `reports/degradation/controlled_degradation_pipe_state_recompute_smoke_manifest.json`.

State recomputation smoke interpretation:

- `ablate_pipe_state_level` collapses the alert surface under the configured
  policies: test alert rate and recall are 0 for both `bloom_h` and
  `irc_alert` across horizons, confirming strong dependence on current fuzzy
  state levels.
- `random_pipe_state_dropout_25` degrades performance materially but does not
  collapse the system. Under `closest_pr`, mean F2 deltas across the three seeds
  are approximately -0.20 to -0.22 for `bloom_h` and -0.16 to -0.17 for
  `irc_alert`, depending on horizon.
- `temporal_pipe_state_blocks_3m_rate_10` is much less damaging in this capped
  smoke. Under `closest_pr`, mean F2 deltas are approximately -0.01 to -0.02
  for most horizons and events.
- These results should be treated as a capped technical smoke, not the final
  robustness result. A full run should remove the origin cap and decide whether
  row-level outputs need DVC tracking.

State recomputation full execution, 2026-06-12:

- generated at UTC: `2026-06-12T17:22:13.984884+00:00`;
- scenario set: `pipe_state_recompute_smoke`;
- output name: `pipe_state_recompute_full`;
- split: `test`;
- selected origins: 13,327;
- rollout rows: 319,848 across 8 evaluated runs;
- state metric rows: 1,056;
- alert metric rows: 192;
- policy metric rows: 576;
- stochastic samples per origin: 128;
- calibrated bloom horizons: 1, 2, and 3;
- rollout bloom calibrator horizons: 1, 2, and 3;
- script hash:
  `54e56833a3e540d758f84e9d8dd3bde6d5b3b7cb64019d4d056667f389f22041`;
- all input, output, and script SHA-256 hashes are recorded in
  `reports/degradation/controlled_degradation_pipe_state_recompute_full_manifest.json`;
- no row-level backtest table was materialized, so no new DVC artifact is
  required for this run.

State recomputation full interpretation:

- The full run preserves the smoke conclusion: current fuzzy state levels are
  essential for the PIPE/GRU-D alert surface.
- Under `closest_pr`, `ablate_pipe_state_level` nearly collapses performance.
  Mean delta F2 is about -0.66 for `bloom_h` and -0.82 for `irc_alert` across
  horizons.
- `random_pipe_state_dropout_25` is a material but non-collapsing degradation.
  Mean delta F2 is about -0.24 for `bloom_h` and -0.19 for `irc_alert` across
  horizons.
- `temporal_pipe_state_blocks_3m_rate_10` remains close to the control. Mean
  delta F2 is about -0.01 for `bloom_h` and -0.007 for `irc_alert`.
- The seed-to-seed variation is small for random and temporal scenarios in the
  full run, so the qualitative ordering is stable:
  state-level ablation is severe, random state dropout is moderate/severe, and
  moderate temporal blocks are mild.

Phase 3:

- repeat comparable scenarios for MIFAL once that pipeline exists;
- compare baseline, fuzzy, PIPE/GRU-D, and MIFAL on a shared degradation grid.
- define a formal no-current-Chl-a early-warning surface before making strong
  precursor claims from nutrient sensitivity. The raw-predictor factorial smoke
  showed target-proximal Chl-a-memory dominance on the current frozen
  monitoring surface, so early-warning evaluation must remove current Chl-a
  from model fitting, calibration, and threshold selection, not only from
  post-hoc degradation scenarios.

## Decisions Made

- Use `closest_pr` as the default alert policy for downstream degradation
  because it is a single validation-selected rule across event/horizon surfaces.
- Start with evaluation-only degradation before retraining under degraded
  training data.
- Prioritize feature-family, random dropout, temporal block, site-retention,
  source-scope, and combined operational-stress scenarios.
- Keep NLA as validation/provenance/enrichment unless the crosswalk policy
  changes.
- Treat nutrient-ablation robustness on a Chl-a-aware frozen surface as
  operational dependence evidence, not as evidence that nutrients are
  ecologically unimportant.
