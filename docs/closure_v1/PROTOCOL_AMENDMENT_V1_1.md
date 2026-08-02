# Closure V1 Protocol Amendment 1.1

## Status

This amendment is **ready to lock**, not locked. It is anchored to repository
alignment commit `dba134a3f3759cf20651e2b8a08c658c3641d793` and takes effect
only when the protocol lock is created from a clean later commit.

No Closure V1 holdout assignment, semantic decoding or inspection of post-2021
holdout outcomes, model score, or evaluation metric is authorized by this
document.

## Why the amendment was required

The original closure concept used stronger language than the repository could
support. Three facts require a narrower and more auditable design:

1. The existing temporal test has already been inspected during prior
   development, so it is legacy descriptive evidence rather than untouched
   confirmation.
2. Outcomes from 2022 onward are already present in the repository. A new
   analysis can be locked before those outcomes are opened for Closure V1, but
   it cannot be described as an externally timed prospective study.
3. `configs/site_resolution.yaml` contains no accepted waterbody crosswalk.
   WQP `site_id` values are source-scoped monitoring-location identifiers, not
   audited identities of distinct lakes or waterbodies.

The historical freeze also records that it was generated from a dirty Git
tree. Amendment 1.1 preserves that provenance limitation and does not rewrite
the historical freeze as if it had been produced under the new lock.

## Semantic changes

Version 1.1 replaces the earlier strong language with the following exact
terms:

| Earlier implication | Version 1.1 term |
|---|---|
| External preregistration | Internal plan locked by Git commit and SHA-256 manifest |
| Prospective validation | Pseudoprospective evaluation with a 2021-12 information cutoff |
| Unseen waterbodies | Held-out WQP monitoring locations |
| Independent external validation | Internal evaluation within the same WQP source and freeze |
| Geographic generalization | Transfer between retained monitoring locations within the frozen cohort |

The grouping unit is fixed as:

```yaml
unit_type: wqp_monitoring_location
key_columns: [source_id, site_id]
waterbody_claim_authorized: false
external_validation_claim_authorized: false
```

A later waterbody-level claim would require a new protocol version, an accepted
and audited waterbody grouping artifact built without post-cutoff outcomes, and
a new assignment before any evaluation access.

## Strict primary input amendment

“No current chlorophyll-a” is strengthened to **no observed chlorophyll-a at
any input lag**. The primary surface forbids:

- observed chlorophyll-a values and transforms;
- present or lagged `risk_chla` and persistence derived from it;
- chlorophyll-a counts, standard deviations, QC, missingness, or provenance
  channels;
- adaptive state outputs fitted with chlorophyll-a;
- optional context scores that combine chlorophyll-a with other evidence; and
- any differently named feature with observed chlorophyll-a lineage.

Future chlorophyll-a remains permitted only as an outcome. The primary
persistence comparator must persist a Chl-a-free state/risk. The historical
MIFAL no-current adapter is blocked for the primary surface while it retains
`Chl_prev`.

The historical `PIPE/GRU-D` label is retained only as an artifact alias. The
closure model is described as a residual probabilistic GRU over
engineered/imputed states, not canonical GRU-D, unless masks and elapsed-time
decay are implemented and separately verified.

## Temporal-role amendment

The former validation interval is split into two non-overlapping roles:

```text
training:          origin and target through 2018-12
model selection:   origin and target from 2019-01 through 2020-12
calibration:       origin and target from 2021-01 through 2021-12
locked evaluation: target from 2022-01 onward
```

Rows crossing a boundary are excluded from that role. Held-out locations are
excluded from every fit, selection, and calibration step, including ANFIS,
preprocessors, calibrators, alert thresholds, and ordinal cutpoints.

## Outcome-blind cohort amendment

Holdout assignment uses information no later than `2021-12`. Eligibility and
stratification use only WQP keys, no-Chl-a input history, permitted precursor
coverage, and historical targets ending by the cutoff. They do not use
post-cutoff target values or target availability.

The deterministic assignment count is
`floor(N eligible locations × 0.20)`, with seed `20260802`,
largest-remainder stratum quotas, lexicographic `stratum_id` ties, and SHA-256
within-stratum rank. Locations are never replaced because they lack a future
target or because a model fails.

If the floor rule produces zero selected locations, E0-C fails with a minimum
requirement of one location. A successful E0-C writes five artifacts and writes
the manifest last, after assignment, summary, cohort-flow, and leakage-audit
outputs exist.

The site registry is not an eligible selection input. Its counts, date ranges,
coordinates, names, HUC fields, and variable summaries may reflect data beyond
the information cutoff and do not establish waterbody identity.

## Cohort and failure amendment

Version 1.1 freezes four denominators:

1. assigned locations;
2. origins intended for prediction based on assignment and input history;
3. origins with an evaluable observed target; and
4. origins on which every model in a declared paired comparison succeeds.

Availability and failures are reported against the intent-to-predict cohort.
Paired quality comparisons use the exact shared-success intersection. Failed or
unavailable rows cannot disappear from reports, and no replacement sampling is
permitted.

## Development, lock, and opening amendment

Closure V1 now has separate gates:

- E0-P fixes the protocol and decision rules.
- E0-G fixes the grouping interpretation.
- E0-C creates the outcome-blind assignment.
- E0-D completes development without holdout outcomes.
- E0-M locks models, preprocessing, calibration, hypotheses, and one batch
  command after a zero-overlap audit.
- E0-U records explicit authorization and performs one sealed outcome opening.

The lock manifest is external to the files it hashes. This avoids embedding a
commit hash inside the same commit whose identity is being computed.

Outcome access means semantic decoding, inspection, aggregation, availability
testing, or analytical use of outcome rows. The locker reads complete source
artifact byte streams to compute SHA-256 hashes but does not decode target
rows. Cryptographic byte reading is provenance verification, not outcome
access under this protocol.

The E0-C reader projects declared columns and requests
`target_year_month <= 2021-12` through the Parquet API. The guarantee is that
post-cutoff target rows and availability flags are never materialized to the
Closure V1 selector. It is not a claim about unaudited internal page I/O or
decoding performed by the storage engine while satisfying that request; such
internal mechanics do not constitute semantic inspection or E0-U.

If a technical failure occurs before metrics are emitted, a documented patch
and complete rerun are permitted. Once metrics exist, any analytical change is
post-unblinding, preserves the original batch, and is labeled exploratory.

## Statistical amendment

The amendment predefines:

- five model seeds: `1729`, `20260612`, `20260613`, `20260614`, and `314159`;
- B0 prevalence estimated by horizon from non-holdout training rows, without
  evaluation-period refit or recalibration;
- primary bloom endpoints: PR-AUC and Brier at horizons 1-3;
- bloom-calibration candidates identity, Platt logistic, and isotonic, selected
  by Brier within `0.001`, then 10-bin equal-width ECE, then fixed simplicity;
- observation-weighted and location-balanced estimands;
- paired 5,000-replicate bootstrap by monitoring location;
- non-inferiority margins of `0.02` PR-AUC and `0.01` Brier;
- Holm correction within five scientific hypothesis families at alpha `0.05`;
- threshold sensitivity at 25, 30, 33, and 50 micrograms per liter; and
- explicit availability, failure, and model-unavailable reporting.

`configs/closure_v1/experimental_matrix.yaml` additionally freezes:

- the exact E6 control plus 12 degraded scenarios, shared-mask rule, five
  seeds, horizons 1-3, and PR-AUC/Brier Holm universe; the shared mask now has
  an exact canonical-JSON/SHA-256 digest-to-uniform algorithm, deterministic
  non-overlapping block selection, explicit overlap/fraction accounting,
  named-component union rules, raw/derived ablation semantics, and a
  one-to-one five-slot model/degradation seed aggregation contract;
- required E7 ANFIS sizes 4,096, 16,384, and 65,536, with no saturation claim
  if resource limits prevent completing the curve;
- E8 nominal levels 0.80, 0.90, and 0.95, with 0.90 primary; native Gaussian
  before intervals and 2021 non-holdout split-conformal after intervals are
  fixed per model/surface/endpoint/horizon/seed, including the finite-sample
  `q` rule and diagnostic conditional-coverage strata; and
- the ten E9 scenarios with exact operations/costs, a nine-action confirmatory
  family at multipliers 1.0/1.0, and a descriptive 3x3 sensitivity grid. The
  complete closure objective, component definitions, penalty constants,
  support contract, P1/five-seed aggregation, and action estimand are copied
  into the authoritative
  matrix; legacy planning modes, budgets, and executable defaults do not fill
  any confirmatory decision.

Uncertainty family E is limited to one aggregate P1/primary-surface comparison:
90% Winkler score after versus before recalibration for `yN`, `yF`, and `yT`
over horizons 1-3. Paired row loss is averaged over the five locked seeds before
location-clustered inference; all five seeds are required on each exact row,
and aggregation then gives equal weight to the nine endpoint/horizon cells.
Seeds are not inferential units. All other E8
levels, endpoints, models, and conditional strata are descriptive.

The legacy planning config is locked only as scenario-catalog provenance. Its
legacy validation/test roles do not apply to Closure V1; the closure matrix and
the temporal roles in the analysis plan take precedence.

Seeds are repeated fits, not independent ecological observations. Confidence
intervals and effect sizes take precedence over isolated p-values.

## Claim boundary after the amendment

Positive results may support a statement about temporal transfer to WQP
monitoring locations held out from fitting within this frozen cohort. They do
not establish transfer to unseen waterbodies, external geographic
generalization, prospective field performance, ecological causality, or an
official intervention recommendation.

The original scientific conclusion remains refutable. Baseline dominance,
weak transfer, insufficient target support, calibration failure, and negative
planning results must be retained and reported.
