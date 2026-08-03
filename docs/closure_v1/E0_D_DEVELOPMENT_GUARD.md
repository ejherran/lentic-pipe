# Closure V1 E0-D Development Guard

Status: implementation contract derived from a read-only audit at commit
`0c283af`. This document does not amend the locked protocol.

## Purpose

E0-D builds the common Closure V1 development surfaces, fits the registered
models on non-holdout locations, selects bounded choices, and fixes calibration
artifacts without opening the locked evaluation outcomes. It must leave E0-U
sealed and produce the inputs required for the E0-M model lock.

The audit that produced this guard inspected versioned source code, command-line
defaults, locked Closure V1 configuration, protocol manifests, and Git history.
It did not execute a data builder or model, read panel, target, sequence, or
prediction rows, inspect post-2021 outcome availability, or emit metrics.

The authoritative contract remains:

- `reports/closure_v1/00_protocol/protocol_lock.json` and the hashes it records;
- `configs/closure_v1/analysis_plan.yaml`;
- `configs/closure_v1/location_holdout.yaml`;
- `configs/closure_v1/surface_primary.yaml` and
  `configs/closure_v1/surface_secondary.yaml`;
- `configs/closure_v1/model_benchmark.yaml` and
  `configs/closure_v1/experimental_matrix.yaml`; and
- `data/closure_v1/closure_holdout_assignment.csv` plus its E0-C manifest and
  leakage audit.

If this implementation note conflicts with a locked artifact, the locked
artifact wins and execution must stop.

## Published starting point

The E0-D implementation starts from the following immutable chain:

- E0-P protocol and cutoff-safe selector: `ead7d13`;
- external protocol lock and lock-manifest validation: `31230a2`; and
- E0-C outcome-blind assignment: `0c283af`.

The assignment contains 441 WQP monitoring locations: 88 assigned to
`internal_holdout` and 353 assigned to `development`. It records 8,903 eligible
historical origins determined through the information cutoff. The unit is the
source-scoped key `(source_id, site_id)` and is not an audited waterbody.

These counts describe the locked assignment, not an evaluation cohort. The
assignment cannot be rebalanced, replaced, or revised because of future target
availability or model failure.

## Fail-closed runtime contract

Every E0-D builder, preprocessor, trainer, selector, and calibrator must use one
shared guard. A command is not Closure V1-safe merely because an operator passes
different dates or omits an output flag. The guard must be mandatory and must
terminate before fitting or writing artifacts when any invariant fails.

### 1. Verify the protocol and assignment

Before reading modeling data, the runtime must:

1. verify the locked protocol and assignment artifacts against their manifests;
2. require exactly the source-scoped key `(source_id, site_id)` and reject null,
   duplicate, or conflicting assignment rows;
3. accept only `wqp`, `development`, and `internal_holdout` values in their
   registered fields;
4. verify the assignment summary against the E0-C manifest, including 441 total,
   88 holdout, and 353 development locations; and
5. construct the immutable development-key set from `assignment_role ==
   "development"`.

Every input row used by E0-D must match that development-key set. An unmatched
row, a holdout match, or a source other than WQP is a hard failure. The
zero-overlap count must be recorded in every model/preprocessor manifest and
must equal zero.

### 2. Enforce semantic outcome sealing

Before E0-U, post-2021 outcomes must not be decoded, inspected, aggregated,
availability-tested, or used analytically. Target reads must project only the
required columns and apply a storage-level row filter with
`target_year_month <= "2021-12"` before rows reach adapter logic. Equivalent
cutoff filters must be applied to any outcome-bearing source.

The development assignment must be joined immediately after the projected,
cutoff-filtered read and before feature/target joins, summaries, preprocessing,
fitting, selection, calibration, or row-availability statistics. No holdout
target column may reach a model-facing frame.

Code may read the locked assignment and input-history identifiers needed to
construct a future sealed batch. It may not probe whether a holdout target
exists after 2021. Absence, presence, row count, nullness, or file partition
metadata for those outcomes is itself sealed information.

### 3. Assign the exact temporal roles

Role assignment uses monthly origin and target values. Both values must fall
inside the same role; boundary-crossing rows are excluded with an explicit
reason and count.

| Role | Origin and target boundary | Permitted decisions |
|---|---|---|
| `training` | Through `2018-12` | Fit preprocessors, fuzzy memberships, ANFIS parameters, model parameters, and horizon prevalence |
| `model_selection` | `2019-01` through `2020-12` | Select bounded hyperparameters, model/baseline family, and calibration method |
| `calibration_threshold` | `2021-01` through `2021-12` | Fit the selected calibrator and select alert thresholds and ordinal cutpoints |
| `locked_evaluation` | Origin and target from `2022-01` | Forbidden in E0-D; one sealed batch only after E0-M and E0-U |

The calibration-method comparison further uses 2019 to fit each candidate and
2020 to score it. The selected method is then fit in the 2021
`calibration_threshold` role. Model weights, preprocessing parameters, and
fuzzy/ANFIS parameters remain fitted only on `training`; 2021 cannot be used to
revisit a model or hyperparameter choice.

Runtimes and manifests must preserve these role names. Collapsing 2019-2021
into a generic `validation` split is not allowed because it conflates model
selection with calibration. Labeling 2022+ rows as `test` does not authorize
their materialization.

### 4. Enforce the primary feature lineage

The primary surface is WQP-only, has 12 consecutive months of history, requires
complete horizons 1-3 on exact common keys, and forbids observed chlorophyll-a
at every input lag. The prohibition includes raw values, transformations,
persistence, `risk_chla`, counts, QC or missingness fields, metadata that
reveals observed chlorophyll-a, and any state fitted using those inputs.

The only PIPE sequence channels permitted on the primary surface are:

- `x_yN`, `x_yF`, and `x_yT`;
- `x_sigma_N`, `x_sigma_F`, and `x_sigma_T`;
- `x_delta_yN`, `x_delta_yF`, and `x_delta_yT`; and
- `season_sin_annual`, `season_cos_annual`, `season_sin_semiannual`, and
  `season_cos_semiannual`.

Future chlorophyll-a is permitted only as a target. The B2 adapter must use the
exact raw-feature allowlist in `model_benchmark.yaml`. B1 must persist only a
Chl-a-free state or risk. F0/F1/P0/P1 must pass an explicit feature-lineage
audit before E0-M. Secondary-surface artifacts must use a separate namespace
and cannot support the primary claim.

M0 remains unavailable while the historical adapter retains `Chl_prev`. It
must not be silently substituted, and failure to produce a strict adapter does
not authorize a replacement model.

### 5. Keep development outputs separate from evaluation

E0-D commands may write only development surfaces, fitted artifacts, selection
records, calibration/threshold records, lineage audits, and manifests. They
must not write holdout predictions, locked-evaluation predictions, test or
holdout metrics, or reports that fall back from an empty test set to a
development set.

All outputs must:

- use the `closure_v1` namespace and state their surface and temporal role;
- record input, code, preprocessor, checkpoint, calibrator, and output hashes
  where applicable;
- record the five fixed seeds `1729`, `20260612`, `20260613`, `20260614`, and
  `314159`, without treating seeds as independent observations;
- record assignment counts, input/output row counts, exclusions by reason,
  exact common-key coverage, and a zero holdout-overlap audit;
- preserve unavailable predictions and failures instead of silently deleting
  them; and
- leave the outcome-access log present and empty.

Model training, selection, and calibration commands must never share an output
path with the future sealed batch. E0-M must lock a separate batch command that
loads already-fitted artifacts and performs no refit, threshold adjustment, or
fallback selection.

## Legacy commands that are not E0-D-safe as written

The following scripts remain valid historical evidence generators, but their
current defaults and control flow do not satisfy the Closure V1 runtime
contract. They must not be executed against Closure V1 data until their strict
adapters and tests are in place.

| Script | Static audit finding | Required change |
|---|---|---|
| `src/experiments/build_adaptive_anfis_state.py` | Loads legacy split rows, trains from the generic `train` label, defaults to evaluating `train,validation,test`, and has no mandatory assignment join | Add development-key filtering, exact Closure roles, strict no-Chl-a module inputs, and development-only outputs |
| `src/experiments/baselines.py` | Its default feature list includes observed Chl-a lineage and its evaluation loop writes `train`, `validation`, and `test` results | Implement B0/B1/B2 from the locked allowlists and prevent any test/holdout output |
| `src/experiments/select_baselines.py` | Uses generic validation for selection, isotonic fitting, and threshold selection, then evaluates test | Separate 2019/2020 method selection from 2021 calibrator/threshold fitting and remove test access |
| `src/experiments/build_pipe_sequences.py` | Combines 2019-2021 as `validation`, labels 2022+ as `test`, permits optional context columns, and has no assignment guard | Emit the three development roles only, enforce the primary channel allowlist, and exclude holdout keys before serialization |
| `src/experiments/train_pipe_grud.py` | Materializes datasets for `train`, `validation`, and `test`, evaluates all three, and selects on the generic validation split | Add P0/P1 Closure adapters with exact roles, mandatory overlap checks, and no evaluation branch |
| `src/experiments/train_pipe_neural_ode.py`, `train_pipe_neural_ode_v1.py`, and `train_pipe_neural_ode_v2.py` | Historical trainers enumerate and evaluate test; some modes accept context derived from combined state | Keep them as iteration-specific evidence unless separately registered and adapted; they are not Closure V1-safe runners |
| `src/experiments/evaluate_mifal_observable.py` and related MIFAL calibration/evaluation scripts | The historical observable adapter retains `Chl_prev` and evaluation defaults can include test | Build and audit a strict no-`Chl`/no-`Chl_prev` adapter before model lock, or record M0 as unavailable |

This list is a static audit boundary, not a guarantee that unlisted scripts are
safe. Any downstream evaluator, rollout, calibration, comparison, or planning
command that can load `test`, `locked_evaluation`, or holdout targets is denied
by default during E0-D.

## Adapter sequence before execution

Implementation should proceed in this order:

1. Add a shared, synthetic-testable Closure development guard for assignment
   validation, cutoff-filtered reads, role assignment, overlap checks, feature
   allowlists, and development-only output assertions.
2. Build the primary state, sequence, and exact common-origin cohort through
   that guard. Record crossing rows and exclusions without reading post-2021
   outcomes.
3. Add B0/B1/B2 and F0/F1 adapters. Fit only on `training`; use
   `model_selection` only for registered choices.
4. Add P0/P1 adapters over the exact common primary surface and run all five
   fixed seeds. The historical `pipe_grud` name remains an alias for a residual
   probabilistic GRU, not canonical GRU-D.
5. Either implement a strict M0 adapter and pass the same common-key and lineage
   audits before model lock, or record `model_unavailable` without substitution.
6. Select the calibration method with the registered 2019/2020 subroles, fit
   the selected calibrator and thresholds/cutpoints on 2021, and hash every
   resulting artifact.
7. Run a zero-overlap and no-evaluation-output audit, then prepare E0-M with one
   separate sealed batch command and an empty outcome-access log.

Unit and integration tests for these adapters must use synthetic frames. Tests
must demonstrate rejection of a holdout key, a post-2021 target, a crossing
role row, a forbidden Chl-a lineage column, an unexpected source or role, an
unregistered seed, and any development command that attempts to emit test or
holdout output.

E0-D completion does not authorize E0-U. The holdout can be opened only once,
after a clean E0-M lock and explicit authorization recorded for the sealed
batch.
