# E0-MS — Closure V1 ANFIS-ablation input-sequence authority

## Status and exact scope

`H-E0-MS` is an additive, development-only, input-sequence authority over
`0a323b0b4c73384558b7782f63512b342a5411c5`, the published strict M0 bundle.
Its direct parent must be that commit and its scope is exactly ten additions:

- `configs/closure_v1/anfis_ablation_sequence_development_patch_lock.schema.json`;
- `configs/closure_v1/anfis_ablation_sequence_development_runtime.yaml`;
- this document;
- `src/experiments/audit_closure_anfis_ablation_sequence_bundle.py`;
- `src/experiments/build_closure_anfis_ablation_sequences.py`;
- `src/experiments/closure_anfis_ablation_sequence_development_patch.py`;
- `src/experiments/lock_closure_anfis_ablation_sequence_development_patch.py`;
- `tests/test_audit_closure_anfis_ablation_sequence_bundle.py`;
- `tests/test_build_closure_anfis_ablation_sequences.py`;
- `tests/test_closure_anfis_ablation_sequence_development_patch.py`.

The protocol, primary surface, common-origin bundle, baseline bundle, M0
bundle, five ANFIS state slots and every P0/P1 sequence and consumer artifact
remain immutable. H-E0-MS does not amend their scientific meaning or reopen a
consumed one-shot.

A future `P-E0-MS` is a direct, non-merge child of the published H commit and
contains exactly two additions:

- `reports/closure_v1/00_protocol/anfis_ablation_sequence_development_patch_lock.json`;
- `reports/closure_v1/00_protocol/anfis_ablation_sequence_development_patch_lock_manifest.json`.

Until that exact P commit is published and accepted by the effective loader,
both A0 and A1 builders remain unauthorized. Model fitting, target access,
calibration, metrics, rollout, DVC, E0-M, E0-U, evaluation and outcome access
remain false even after P is effective.

## Input-only scientific boundary

E0-MS may construct inputs only. Its source surface contains the exact 29,196
common-origin rows for 9,732 intent origins, 353 development locations and the
globally declared horizons 1, 2 and 3. Each of the six sequence bundles has
exactly one row per intent origin: horizons are manifest-level metadata, not a
row dimension or identity field. The three frozen time roles retain 8,352
training, 1,061 model-selection and 319 calibration-threshold origins. Each
logical input has 12 months ordered from the oldest calendar month through the
origin month. Holdout locations, unknown assignments, targets and post-2021
outcomes are forbidden.

No `target_year_month`, `evaluation_unit_id`, horizon-expanded row or other
target identity is serialized. No target artifact or target column may be
opened, projected or used to decide availability. The sequence builder may not
fit a model, preprocessor, calibrator or threshold and may not calculate a
metric. A sequence bundle is not a trained ablation result.

All serialized tensors use one nullable `FixedSizeList<float32>[12]` per
channel. A successful row contains finite child values. A terminal failure
retains its identity, status and reason, while every channel parent list is
null; fabricated vectors and partial tensors are forbidden.

## A0 — exact 18-channel raw no-current input

A0 is one deterministic shared bundle. Its channel order is exact:

1. `x_mean_TP_ugL`;
2. `x_mean_TN_ugL`;
3. `x_mean_DO_mgL`;
4. `x_mean_pH`;
5. `x_mean_turbidity_NTU`;
6. `x_mean_secchi_depth_m`;
7. `x_mean_temperature_C`;
8. `mask_mean_TP_ugL`;
9. `mask_mean_TN_ugL`;
10. `mask_mean_DO_mgL`;
11. `mask_mean_pH`;
12. `mask_mean_turbidity_NTU`;
13. `mask_mean_secchi_depth_m`;
14. `mask_mean_temperature_C`;
15. `season_sin_annual`;
16. `season_cos_annual`;
17. `season_sin_semiannual`;
18. `season_cos_semiannual`.

For each raw variable and month, its mask is exactly one only when the
corresponding mean is finite and the corresponding `n_obs` is finite and
strictly greater than zero; otherwise it is zero. A missing mean is serialized
as structural float32 zero together with mask zero. This storage convention is
not a scientific imputation and must never be interpreted without its mask.
Any future preprocessing must be fit on training data only and preserve the
mask semantics.

Seasonality is computed solely from the calendar month using
`2*pi*(month-1)/12`, in float64 before serialization to float32. No observed
chlorophyll-a value, lag, count, QC field, standard deviation, transform,
chlorophyll-derived missingness signal or derived state may enter A0. The seven
declared raw-variable masks are required inputs, not chlorophyll lineage.

## A1 — exact 27-channel raw-plus-adaptive input

A1 contains the exact 18 A0 channels in the same order followed by these nine
adaptive no-current ANFIS channels:

1. `x_yN` from `yN_adaptive`;
2. `x_yF` from `yF_adaptive`;
3. `x_yT` from `yT_no_chla_adaptive`;
4. `x_sigma_N` from `sigma_N_adaptive`;
5. `x_sigma_F` from `sigma_F_adaptive`;
6. `x_sigma_T` from `sigma_T_no_chla_adaptive`;
7. `x_delta_yN` from `delta_yN_adaptive`;
8. `x_delta_yF` from `delta_yF_adaptive`;
9. `x_delta_yT` from `delta_yT_no_chla_adaptive`.

There are five A1 bundles, for seeds 1729, 20260612, 20260613, 20260614 and
314159. Every A1 slot must use the ANFIS state from the same seed; cross-seed
substitution, best-seed selection, averaging and replacement are forbidden.
The serialized `base_seed` and `upstream_state_seed` are both that same seed.
Both fields are null for deterministic shared A0. Full/current-Chl-a ANFIS
channels are forbidden.

The row-status vocabulary is closed to `success`,
`input_history_unavailable` and `model_slot_unavailable`. Missing or duplicate
history, missing paired state, key disagreement, nonfinite state, forbidden
lineage, authority drift or namespace collision is handled by the registered
status when the runtime permits retention, or aborts the entire transaction
when integrity cannot be established. A failed slot is not replaced by a
different seed, P0/P1 tensor or historical sequence.

## Six bundles and closed output namespace

Future separately authorized sequence invocations may cumulatively produce
exactly six independently atomic bundles: one A0 bundle and five same-seed A1
bundles. One invocation consumes one declared bundle slot; it may not batch or
replace another slot. The progression order is exact: A0 first, then A1 seeds
1729, 20260612, 20260613, 20260614 and 314159. HEAD remains the exact published
P commit during all six invocations. The effective loader accepts only an exact
untracked prefix of completed three-file bundles, binds the requested next slot
and rejects a hole, future slot, replay, out-of-order invocation, changed prior
bundle or unrelated path. All six pointer paths remain absent. Each bundle
contains Parquet, summary and manifest, with the manifest written last. The 18
final paths are:

- A0 `data/closure_v1/development/sequences/A0/raw_no_current.parquet`,
  `reports/closure_v1/01_surface/sequences/A0/raw_no_current_summary.csv` and
  `reports/closure_v1/01_surface/sequences/A0/raw_no_current_manifest.json`;
- for each frozen seed, A1
  `data/closure_v1/development/sequences/A1/seed_{seed}.parquet`,
  `reports/closure_v1/01_surface/sequences/A1/seed_{seed}_summary.csv` and
  `reports/closure_v1/01_surface/sequences/A1/seed_{seed}_manifest.json`.

The six `.dvc` pointer paths are future, separately authorized records and must
be absent throughout H/P and sequence construction. All 18 sibling temporary
paths and six exclusive guards must also be absent before and after a complete
transaction. H/P may not run the builder or auditor and may not invoke DVC.

Publication walks parents through directory descriptors with no-follow,
creates guards and temporaries with `O_EXCL`, publishes finals by no-clobber
hardlink, verifies retained file descriptors and rolls back only an inode
owned by the transaction. A foreign replacement is preserved and causes a
fail-closed error. Each bundle manifest is the last record published.

## What this does not establish for E7

All ten P0/P1 temporal consumers are presently
`model_unavailable/not_attempted/sequence_fit_rows_unavailable`: 8,925 fit-role
sequence origins are available and 488 are unavailable. E0-MS neither changes
those denominators nor authorizes a replacement. Therefore the A0/P0/P1/A1 E7
comparison remains non-estimable until separately locked temporal fits exist.
No predictive, calibration or ANFIS-incremental-value claim may be derived
from these input bundles alone.

The E7 ANFIS training-size sensitivity at 4,096, 16,384 and 65,536 rows per
module is outside this gate. E0-MS records it as blocked for a separate
sampling-strata authority. It does not authorize new ANFIS fits or a saturation
claim.

## H/P workflow and companion topology

1. Publish exact H-E0-MS as `10A` over the M0 bundle.
2. Run `--check-only`. Schema validation is the first operation. It verifies
   the exact H topology, all 44 physical pins, the closed 18-final/6-pointer
   namespace, clean refs and the live tracking ref. It writes nothing and runs
   no type check, tests, builder, auditor, DVC, data or outcome command.
3. Under separate authorization, run `--execute-lock`. Its only commands are
   the full type check, the exact focused H suite of 63 tests with zero skips or
   deselections, `poetry check`, the publication guard with its exact success
   output and `git diff --check`.
4. Recollect the prelock after verification and publish only lock followed by
   companion. The companion binds exactly 54 unique physical inputs: the 44
   frozen pins plus all ten H components. `historical_inputs` is exactly empty,
   `physical_inputs_only=true`, the locker appears once in `inputs` and is also
   the generating `script`, and the sole companion output is the lock record.
5. Audit and publish exact P-E0-MS as `2A`; then run `--check-effective`.
6. Only the effective P authority may permit a separately authorized
   single-bundle one-shot. Every additional slot requires its own explicit
   authorization and must preserve and revalidate the exact untracked prefix.
   After all six triples are complete, read-only audit, DVC registration,
   precommit and Git publication occur jointly under later decisions. Fitting,
   calibration and E0-M remain separate.

H/P may perform read-only live Git alignment. They may not use scientific
network egress, open targets or outcomes, execute A0/A1, invoke DVC, or create
data, models, metrics, E0-M or E0-U artifacts.
