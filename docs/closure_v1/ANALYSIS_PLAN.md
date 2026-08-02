# Closure V1 Analysis Plan

## Document status

| Field | Value |
|---|---|
| Experiment | `closure_v1` |
| Plan version | `1.1` |
| Protocol gate | `E0-P` |
| Status | `ready_to_lock` |
| Alignment base commit | `dba134a3f3759cf20651e2b8a08c658c3641d793` |
| Registration class | Internal Git-locked pseudoprospective analysis plan |

This document defines the analysis before the closure cohort is assigned and
before any post-2021 outcome is opened for closure evaluation. The plan is not
yet locked. Locking requires a clean repository commit and a separate lock
manifest containing the commit and SHA-256 hashes of every protocol component.

This is not an external preregistration, an independently timed prospective
study, or external validation. Outcomes from 2022 onward already exist in the
repository, so the strongest accurate description is an **internal,
Git-locked, pseudoprospective evaluation**.

The machine-readable authority for this document is
`configs/closure_v1/analysis_plan.yaml`. The amendment rationale is recorded in
`docs/closure_v1/PROTOCOL_AMENDMENT_V1_1.md`.

## Purpose and evidence boundary

Closure V1 consolidates existing thesis evidence onto one common experimental
surface and addresses the remaining gaps without introducing another model
family. It is designed to answer whether the final architecture:

1. adds predictive value over persistence and a strong raw-feature baseline;
2. remains useful at WQP monitoring locations withheld from every fitting
   stage;
3. is robust to reasonable bloom thresholds;
4. supports a direct, explicitly limited trophic-state analysis;
5. produces paired, site-clustered uncertainty statements; and
6. exposes failures and missing predictions instead of silently dropping them.

The primary transfer claim is limited to monitoring locations in the frozen
WQP cohort. The repository has no accepted crosswalk from WQP site identifiers
to audited waterbody identities. Consequently:

- the holdout unit is `wqp_monitoring_location`;
- the group key is `source_id + site_id`;
- `site_id` is source-scoped and is not interpreted as a lake identity;
- no claim about unseen waterbodies is authorized;
- no claim of external or field-prospective validation is authorized.

## Protocol gates

Closure V1 separates protocol definition, assignment, development, model
locking, and outcome access:

| Gate | Purpose | Outcome access |
|---|---|---|
| E0-R | Verify the aligned repository and provenance limitations | No closure evaluation |
| E0-P | Fix this plan, schema, surfaces, models, hypotheses, and decision rules | No post-2021 closure outcomes |
| E0-G | Resolve the grouping unit as WQP monitoring location | No post-2021 closure outcomes |
| E0-C | Assign the location holdout using information through 2021-12 only | No post-2021 closure outcomes |
| E0-D | Fit and select using non-holdout locations and development roles | No post-2021 closure outcomes |
| E0-M | Lock models, preprocessors, calibrators, thresholds, cutpoints, code, and batch command | Access log must remain empty |
| E0-U | Authorize one sealed evaluation batch | One authorized opening |

Creating these E0-P files does not create a holdout assignment, score a model,
or authorize E0-U.

## Experimental surfaces

### Primary surface: strict early warning

The primary surface is `closure_v1_wqp_adaptive_no_current_chla`:

- source: WQP only;
- history: 12 consecutive monthly input states;
- forecast horizons: 1, 2, and 3 months;
- complete-horizon cohort: all three horizons are required for the primary
  paired benchmark;
- input contract: no observed chlorophyll-a value or derivative at any input
  lag;
- target contract: future chlorophyll-a, bloom, risk, and operational trophic
  labels may be used only as outcomes;
- state contract: adaptive nutrient and functional state plus the explicitly
  no-Chl-a trophic state and their uncertainty/change channels;
- seasonal sine/cosine channels are permitted;
- optional sequence context derived from observed chlorophyll-a is forbidden,
  even when the current model implementation does not consume that column.

The strict prohibition includes raw chlorophyll-a values, transforms, lags,
persistence values, `risk_chla`, counts, missingness flags, QC rates, standard
deviations, adaptive outputs trained with chlorophyll-a, and combined scores
that include chlorophyll-a. Feature lineage must be audited before model lock.

The currently available MIFAL `observable_no_current_chla` adapter is not
eligible while it retains `Chl_prev`. MIFAL model `M0` becomes eligible only
after a strict adapter removes both `Chl` and `Chl_prev` and passes the same
lineage audit as PIPE.

### Secondary surface: monitoring diagnostic

The secondary surface is `closure_v1_wqp_adaptive_current_chla`. It may use
observed chlorophyll-a and exists only to quantify the information advantage of
monitoring/nowcasting. Its results cannot support the primary early-warning
claim and cannot replace a failed primary analysis.

## Unit of analysis and common keys

The row-level prediction key is:

```text
source_id × site_id × origin_year_month × target_year_month × horizon_months
```

Every prediction also carries:

```text
evaluation_unit_id
holdout_group_id
assignment_role
input_eligible
target_evaluable
model_available
failure_code
```

Paired model comparisons use exact key intersections. The resampling and
equal-weight unit is `holdout_group_id`, which in v1.1 is the source-scoped WQP
monitoring location.

## Temporal roles

Both the origin and target month must remain within the assigned role. A row
that crosses a role boundary is excluded from that role.

| Role | Interval | Permitted use |
|---|---|---|
| Training | Through `2018-12` | Fit weights, memberships, preprocessors, and model parameters |
| Model selection | `2019-01` through `2020-12` | Choose bounded architecture, hyperparameters, baseline family, and calibration method |
| Calibration | `2021-01` through `2021-12` | Fit the selected calibrator and choose alert thresholds and ordinal cutpoints |
| Locked evaluation | Target month from `2022-01` onward | Score once after E0-M and E0-U; never tune |

Previously inspected temporal test results are legacy descriptive evidence and
are not independent confirmation. Holdout locations are excluded from all
three development roles, including ANFIS fitting and calibrator/threshold
selection.

## Outcome-blind location holdout

The cohort procedure is fixed in
`configs/closure_v1/location_holdout.yaml`. Its key rules are:

1. Use only `source_id == wqp` and source-native `site_id`.
2. Project only keys, permitted no-Chl-a precursor evidence, temporal fields,
   and outcomes whose target month is no later than `2021-12`.
3. Do not use site-registry row counts, date ranges, variable counts, names,
   coordinates, HUC fields, or cross-source candidates because those artifacts
   include information beyond the cutoff and do not establish waterbody
   identity.
4. Require 12 consecutive input months; adjacent retained months must be
   exactly one calendar month apart.
5. Require at least one complete historical origin for horizons 1-3. The last
   eligible historical origin is `2021-09`, and its targets end by `2021-12`.
6. Stratify by historical bloom presence, no-Chl-a precursor coverage band,
   and series-length band, using information through `2021-12` only.
7. Set the global holdout count to `floor(N eligible locations × 0.20)`, use
   seed `20260802`, allocate stratum quotas by largest remainder with
   lexicographic `stratum_id` ties, and rank locations within strata by SHA-256
   independently of input row order.
8. Assign all rows of a selected location to the holdout. Never reassign or
   replace a selected location because it lacks future outcomes or a model
   fails.
9. Evaluate assigned locations only after E0-M, E0-U, and the sealed batch.

The E0-C gate fails if the fixed floor rule would select fewer than one
location; it does not emit an empty assignment. A successful assignment writes
exactly five artifacts in this order: assignment, pre-cutoff summary,
pre-outcome cohort flow, leakage audit, and manifest. The manifest is written
last so it cannot declare an incomplete bundle complete.

Historical bloom presence may be used only for stratification and is computed
from unique target months no later than `2021-12`; repeated horizon rows are
deduplicated. No post-cutoff outcome value or availability flag may affect
eligibility, strata, ranking, quotas, or assignment.

Grouped five-fold evaluation (E2B) is predeclared as a complementary analysis.
It is not activated or modified based on the support or performance observed in
the primary location holdout (E2A).

## Frozen denominators

Four denominators are reported separately:

1. `assigned_units`: all WQP monitoring locations selected for holdout.
2. `intent_to_predict_origins`: origins defined from group assignment and input
   history alone, before inspecting target availability or model success.
3. `metric_evaluable_origins`: intent-to-predict origins with the required
   observed target.
4. `shared_success_origins`: metric-evaluable origins for which every model in
   a declared paired comparison produced a valid prediction.

Prediction availability and failures are reported on
`intent_to_predict_origins`. Paired quality metrics use
`shared_success_origins`. An individual model may also be summarized on
`metric_evaluable_origins`, but that result must be labeled unpaired. No model
may improve its apparent score by silently deleting failures.

## Models and seeds

The benchmark is fixed in `configs/closure_v1/model_benchmark.yaml`:

| ID | Role |
|---|---|
| B0 | Horizon-specific prevalence estimated on non-holdout training locations; no recalibration |
| B1 | Persistence of the last Chl-a-free state/risk |
| B2 | Strong tabular raw-feature baseline with a strict no-Chl-a allowlist |
| F0 | Expert fuzzy no-current state |
| F1 | Adaptive ANFIS no-current state |
| P0 | Residual probabilistic GRU on the expert no-current state |
| P1 | Residual probabilistic GRU on the adaptive no-current state; primary candidate |
| M0 | Strict MIFAL-ED/T2 comparator, blocked until `Chl_prev` is removed |

The historical `pipe_grud` name is retained only as an artifact alias. P0 and
P1 are residual probabilistic GRUs over engineered/imputed state sequences;
they are not described as canonical GRU-D because the implementation does not
contain the canonical mask and elapsed-time decay mechanism.

All stochastic components use exactly these five seeds:

```text
1729, 20260612, 20260613, 20260614, 314159
```

Deterministic components record `1729` as their technical seed. Seeds are
analyzed as repeated fits, not pooled as independent observational rows.

## Selection, calibration, and threshold rules

Model and baseline configurations are selected only in the model-selection
role. Bloom calibration follows this fixed staged rule:

1. compare identity, Platt logistic, and isotonic calibration by forward
   validation within the model-selection role, using 2019 for fitting and 2020
   for scoring;
2. retain candidates within `0.001` Brier of the lowest Brier score, then choose
   the lowest expected calibration error computed with 10 equal-width bins;
3. break any remaining tie by the fixed simplicity order identity, Platt
   logistic, then isotonic;
4. refit the chosen method in the `calibration_threshold` role;
5. select an alert threshold in `calibration_threshold` by maximum F2;
6. break F2 ties by higher recall, then higher precision, then the lower
   numeric threshold;
7. lock each model/horizon calibrator and threshold before E0-U.

Ordinal cutpoints are selected in `calibration_threshold` by maximum macro-F1,
then lower ordinal MAE, then lexicographically smaller ordered cutpoints. The
cutpoints must be monotone and are locked before evaluation.

The primary bloom definition is `30 µg/L`. Sensitivity thresholds are fixed at
`25`, `30`, `33`, and `50 µg/L`. The same continuous predictions and common
origins are used at every threshold; calibrators and decision thresholds are
fit only in their permitted development roles.

## Locked experimental matrix for E6-E9

`configs/closure_v1/experimental_matrix.yaml` is the authoritative matrix for
the experiments that depend on fixed scenario universes or sensitivity grids.

- E6 compares M0 and P1 under one control and exactly 12 degraded scenarios:
  MCAR 10/25/50%, temporal blocks 1 month at 10%, 3 months at 10%, and 6 months
  at 25%, four deterministic precursor-family ablations, and two fixed combined
  scenarios. `combined_moderate` is MCAR 25% plus the 3-month/10% block;
  `combined_severe` is MCAR 50% plus the 6-month/25% block plus nutrient
  ablation. Random scenarios use all five seeds. One raw mask is generated
  before model-specific transforms and shared exactly by M0 and P1. The mask
  universe is the unique finite cells of the seven declared raw predictors,
  keyed by source, location, month, and variable; repeated appearances of a
  cell in different origins or horizons reuse its mask value.

  MCAR values are generated by serializing the ordered tuple declared in the
  matrix as a compact ASCII-escaped JSON array, hashing its UTF-8 bytes with
  SHA-256, interpreting the first eight digest bytes as an unsigned big-endian
  integer, and dividing by `2^64`. A cell is masked exactly when that value is
  strictly below the scenario fraction. Text is NFC-normalized first; the seed
  is a JSON integer and every other tuple element is a JSON string. Two locked
  payload/digest test vectors make the byte serialization executable rather
  than interpretive. Temporal-block starts use the analogous
  tuple with a block-start month. Within each location-variable series, full
  candidate blocks are sorted by digest and then month; overlapping candidates
  are skipped until the fixed, round-half-up block count is reached or the
  candidates are exhausted. Blocks are never truncated, resampled, or tuned to
  force the realized fraction. Combined scenarios are the union of their named
  component masks for the same seed, not a fresh draw. Planned and realized
  fractions are both reported. Deterministic ablations set their declared raw
  cells to missing after the random-mask union and before model-specific
  transforms. Every direct or transitive derived feature of an ablated raw
  variable is invalidated before model-specific imputation; pre-degradation
  derived values cannot be reused, and an unlisted dependent feature fails the
  lineage audit.

  Family B uses five ordered replicate slots. P1 model seed and stochastic
  degradation seed are paired one-to-one by slot; their 5x5 cross-product is
  forbidden. Deterministic M0 output at technical seed 1729 is reused in the
  five comparison slots, while control/deterministic scenarios use one
  technical degradation mask. Every exact row must succeed for both models in
  all five slots. Within each location bootstrap replicate, PR-AUC or Brier is
  computed separately per model and slot, M0-minus-P1 deltas are formed, and
  the five deltas are averaged before deriving one two-sided p-value. Seeds are
  not inference units. Holm family B contains the 13 scenarios,
  horizons 1-3, and PR-AUC/Brier only (78 confirmatory p-values).
- E7 must attempt ANFIS module sizes 4,096, 16,384, and 65,536 rows with the five
  fixed seeds. Resource limits do not permit silent omission: the limitation
  and completed sizes are retained, and no saturation claim is authorized if
  the curve is incomplete.
- E8 evaluates nominal coverage 0.80, 0.90, and 0.95, with 0.90 primary. For a
  model output with finite mean `mu` and positive scale `sigma`, the before
  interval is the native central Gaussian interval using factors
  `1.2815515655446004`, `1.6448536269514722`, and
  `1.959963984540054`, respectively. The after interval is
  `mu +/- q_c * sigma`. For each model, surface, endpoint, horizon, and model
  seed separately, scores `abs(y - mu) / max(sigma, 1e-6)` are formed on
  non-holdout WQP rows in the 2021 calibration-threshold role. With `n` finite
  scores, `q_c` is the order statistic at one-based index
  `min(n, ceil((n + 1) * c))`, with no interpolation. At least 30 rows are
  required; groups below that count remain explicitly unavailable and are not
  pooled. Every `q_c` is locked before E0-U and the before/after comparison uses
  identical locked-evaluation rows. Evaluation-time adjustment is forbidden.
  Coverage, absolute coverage error, interval width, and Winkler score are
  always reported together.

  Conditional coverage is diagnostic and never creates stratum-specific
  `q` values. The required breakdowns are global, horizon, 2021-locked
  nutrient-evidence and input-missingness quartiles, fixed predicted-risk bands
  `[0,.25)`, `[.25,.5)`, `[.5,.75)`, `[.75,1]`, pre-cutoff location-input
  frequency, development-seen versus heldout-unseen location status, and the
  exact E6 scenario. Sparse strata retain row/location counts and an
  insufficient-support status instead of being pooled or deleted.

  Confirmatory family E is one predeclared test: P1 on the strict primary
  surface, core endpoints `yN`, `yF`, and `yT`, horizons 1-3, and nominal 90%
  coverage. Its row loss is the 90% Winkler score, its paired delta is after
  minus before, and its primary estimand is the observation-weighted mean with
  equal endpoint/horizon weight and location-clustered inference. The paired
  row loss is averaged across the five locked model seeds before ecological
  inference; every exact paired row must contain all five seeds, otherwise it
  remains outside shared success and its failure is reported on the
  intent-to-predict denominator. Aggregation first averages seeds within a row,
  then rows within each endpoint/horizon, and finally gives equal weight to the
  nine endpoint/horizon cells. Seeds are not sampling units. The one-sided
  alternative is a
  negative delta and family E contains exactly one p-value. Levels 80%/95%,
  the other six state/change endpoints, other models, location-balanced
  summaries, and all conditional breakdowns are descriptive. Independently of
  that test, a 90% interval is called calibrated only when its absolute
  coverage error is at most 0.05.
- E9 duplicates the ten raw-proxy planning scenarios, operations, and relative
  costs from the legacy catalog. The closure matrix is authoritative and does
  not reuse the catalog's legacy `selection_split`, `heldout_split`, planning
  modes, or cost budgets. All nine actions are evaluated. At each common
  origin-horizon, let `Delta_IRC = IRC_no_action - IRC_scenario`,
  `Delta_bloom = P_no_action - P_scenario`, and
  `Delta_U = U_scenario - U_no_action`. The locked objective is

  `O_s = 0.60*Delta_IRC + 0.40*Delta_bloom
         - 0.05*m_cost*relative_cost
         - 0.10*max(0, Delta_U)
         - 0.05*m_support*support_violation`.

  `O_no_action` is exactly zero and the confirmatory endpoint is
  `O_s - O_no_action`. `IRC`, the bloom proxy, uncertainty, support envelopes,
  and missing-component policy are defined in the closure matrix, so the
  objective does not depend on defaults in legacy executable code. Holm family
  D contains the nine actions versus `no_action` only at cost/support
  multipliers 1.0/1.0. P1 on the strict primary surface is the locked planning
  model and is not refit. For each exact row, action-minus-no-action objective
  deltas are computed within each of the five model seeds, all five are
  required, and their equal-weight mean is formed before pooling common rows
  observation-weighted across horizons 1-3 and clustering by holdout location.
  Seeds are not inference units. The 3x3 grid over
  0.5/1.0/2.0 multipliers is descriptive sensitivity and cannot redefine the
  confirmatory family or select favorable weights post hoc.

## Endpoints and estimands

Primary bloom endpoints are PR-AUC and Brier score for horizons 1-3. Threshold
metrics (recall, precision, F2, macro-F1, and alert rate) are secondary because
they depend on a calibration-period decision threshold.

Continuous-state endpoints are RMSE and MAE, with NLL and calibrated interval
scores reported when a model supplies a compatible predictive distribution.
Operational trophic endpoints are macro-F1, quadratic weighted kappa, ordinal
MAE, severe-error rate, class recall, and confusion matrices.

Every principal comparison reports:

- an observation-weighted estimate with confidence intervals clustered by
  monitoring location;
- a location-balanced estimate, with each eligible location weighted equally;
- the median, interquartile range, and fraction of locations won;
- exact row, location, positive-event, failure, and availability counts.

PR-AUC at a single location is omitted when both classes are not present, and
the excluded count is shown. Brier score remains defined and is reported for
such locations.

## Hypotheses, comparisons, and interpretation margins

The primary benchmark comparisons are:

- P1 versus B1: added temporal value over Chl-a-free persistence;
- P1 versus B2: value beyond a strong raw-feature baseline;
- P1 versus P0: incremental value of adaptive ANFIS state;
- P1 versus M0: comparative discrimination and calibration when M0 is strict
  and available;
- F1 versus F0: incremental static value of adaptive ANFIS;
- A2 versus P1: information advantage from current chlorophyll-a, reported only
  as a secondary surface comparison.

The project-specific competitiveness margins are fixed before evaluation:

- PR-AUC absolute non-inferiority margin: `0.02`;
- Brier absolute non-inferiority margin: `0.01`;
- state RMSE/MAE versus persistence: improvement must be greater than zero.

These are analytical conventions for this closure and are not ecological
standards. A confidence interval that includes zero means that a difference was
not demonstrated; it does not establish equivalence. Statistical significance
without a useful effect is not presented as substantive superiority.

## Multiplicity and inference

Holm adjustment at family-wise alpha `0.05` is applied within, but not across,
the following predeclared families:

- A: P1 versus B1, B2, and P0;
- B: M0 versus P1 for the exact 13-scenario E6 matrix, horizons 1-3, and
  PR-AUC/Brier;
- C: A2 versus P1;
- D: the nine E9 actions versus no action at cost/support multipliers 1.0/1.0;
- E: one aggregate 90% Winkler-score comparison, after versus before, for P1
  on the strict primary surface and core endpoints `yN`/`yF`/`yT` across
  horizons 1-3.

Correction dimensions are family-specific. Family B has exactly 78 p-values
(13 scenarios × 3 horizons × 2 endpoints). Family D has exactly nine p-values
(one primary `delta_objective` comparison for each action at weights 1.0/1.0).
Secondary/descriptive metrics and the E9 3x3 sensitivity grid do not expand
either confirmatory family. Family E has exactly one p-value; it first averages
paired row loss across model seeds and never treats seeds as ecological units.

The primary uncertainty procedure is a paired hierarchical bootstrap with
5,000 replicates:

1. sample `holdout_group_id` values with replacement;
2. retain all paired rows for each sampled group;
3. compute both model estimates on the same rows;
4. store the paired difference;
5. form percentile 95% confidence intervals.

A 12-month within-location block bootstrap is secondary. Wilcoxon on
location-level losses and McNemar on paired decisions are complementary. Seeds
are summarized per fit and are not treated as extra environmental units.

## Failure policy

Every intent-to-predict row receives one terminal status: successful,
input-ineligible, target-unavailable, model-unavailable, numerical-failure, or
infrastructure-failure. Failure codes are fixed in the machine-readable plan.

- Input eligibility is determined before target access.
- Missing outcomes change `metric_evaluable_origins`, not assignment.
- A failed model remains in the availability denominator.
- No failed location or origin is replaced.
- The paired quality cohort is the declared shared-success intersection.
- Availability and failure rates accompany every quality table.
- An unresolved strict MIFAL adapter is reported as model unavailable; it does
  not permit using the Chl-a-memory adapter on the primary surface.

## Outcome access and sealed batch

For this protocol, **outcome access** means semantic decoding, inspection,
aggregation, availability testing, or analytical use of outcome rows. Before
E0-U, code operating on the holdout may access group identifiers and input
history but may not perform any of those operations on post-2021 outcomes. The
outcome access log must exist and remain empty at model lock.

The protocol locker reads the complete byte streams of declared source
artifacts to calculate SHA-256 hashes. It does not decode or inspect target
rows. Cryptographic byte reading is provenance verification and is explicitly
not classified as semantic outcome access.

For E0-C, the Parquet read API is called with a projected column list and a
`target_year_month <= 2021-12` filter. The sealed-state guarantee applies to
rows and values materialized to Closure V1 application logic: no post-cutoff
target row or availability flag may be exposed to the selector. The protocol
does not claim or audit whether a storage engine internally reads or decodes a
mixed physical page while satisfying that filtered request. Such internal I/O
is not semantic outcome inspection and is not an E0-U opening.

E0-U requires an explicit authorization recorded against a clean commit/tag
after model, calibration, hypothesis, and batch locks pass zero-overlap audits.
The authorized command runs one sealed batch that materializes predictions and
metrics together. Evaluation results are never written by training commands.

A technical failure before any metric is emitted may be corrected only by a
documented patch version followed by a complete rerun. Any analytical change
after metrics are emitted is post-unblinding, preserves the original batch, and
is labeled exploratory rather than locked confirmation.

## Change control and locking

While the status is `ready_to_lock`, a material change requires updating both
human-readable documents and all affected machine-readable configs. At lock:

- the repository must be clean;
- all required protocol components must exist;
- the schema and cross-file contract must pass;
- SHA-256 hashes are calculated for protocol, code, and source artifacts;
- the Git commit is written to an external lock manifest to avoid a circular
  self-hash;
- no holdout assignment is created and no post-2021 target row is decoded or
  inspected by the locking command.

After lock and before E0-U, any material change requires a new protocol version
and lock manifest. After E0-U, the original outputs are immutable; corrections
or extensions receive a new version and an explicit exploratory label.

## Operator sequence before cohort assignment

The protocol and cohort gates are intentionally separate. The safe sequence is:

1. Validate this draft without writing outputs:

   ```bash
   poetry run python src/experiments/lock_closure_protocol.py --check-only
   ```

2. Review and commit the E0-P documents, configs, selection code, and tests.
3. From that clean commit, create the external protocol lock bundle:

   ```bash
   poetry run python src/experiments/lock_closure_protocol.py
   ```

   This command hashes the complete byte streams of protocol and source
   artifacts. It does not create the cohort or semantically decode, inspect, or
   use post-2021 holdout outcomes.

4. Review and commit the generated lock bundle. The lock records the clean
   protocol commit; its committed descendant anchors the external manifest.
5. On the clean descendant commit, validate the cohort guard without reading
   the panel:

   ```bash
   poetry run python src/experiments/build_closure_holdout.py --dry-run
   ```

6. Only after explicit authorization, create the one-time pre-cutoff
   assignment:

   ```bash
   poetry run python src/experiments/build_closure_holdout.py \
     --execute-locked-selection
   ```

The assignment command projects only allowlisted WQP input fields and
historical `bloom_h` rows ending by `2021-12`. It does not authorize E0-U or
access to post-2021 holdout outcomes.

## Authorized and unauthorized statements

If results are positive, an authorized statement is:

> The locked analysis found evidence of temporal transfer to WQP monitoring
> locations withheld from fitting within the frozen cohort.

Statements not authorized by Closure V1 include:

- “validated on unseen waterbodies”;
- “external validation”;
- “prospective field validation”;
- “generalizes to any lake, region, country, or monitoring program”;
- “causal nutrient intervention effect”; and
- “official environmental recommendation.”

Negative and inconclusive results remain part of the thesis evidence. If a
baseline dominates, uncertainty remains poorly calibrated, or transfer fails,
the engineering and reproducibility contributions are reported without
inflating the predictive claim.
