# E0-MCAL: final development calibration

## Status and purpose

| Field | Value |
|---|---|
| Gate | `E0-MCAL` |
| Base commit | `2f46d3e258195315e2473be6cf7d62db22c55bcf` |
| This H slice | `ready_to_lock` |
| H scope | exactly `12A` |
| P scope | exactly `2A` |
| R scope | exactly `8A`, all light and non-DVC |
| Post-2021 outcome access | forbidden |
| E0-U authorization | `false` |

E0-MCAL closes the final development-only calibration protocol and the
terminal ANFIS E7 learning curve before any evaluation input can be opened. It
is not E0-M, does not create an evaluation batch, does not authorize E0-U, and
does not turn development evidence into holdout evidence. Every scientific
operation is restricted to non-holdout sites and temporal roles ending at
`2021-12`.

Effective authority exists only after P-E0-MCAL has been published. A local,
unpublished lock has status `locked_unpublished`; every public consumer must
reject it.

## H/P/R boundary

H-E0-MCAL is additive. It contains exactly the following twelve new paths,
all with Git mode `100644`, as registered by
`FINAL_CALIBRATION_H_STAGED_SCOPE`:

```text
configs/closure_v1/final_calibration_runtime.yaml
configs/closure_v1/final_calibration_runtime.schema.json
configs/closure_v1/final_calibration_lock.schema.json
docs/closure_v1/E0_M_FINAL_CALIBRATION.md
src/experiments/calibrate_closure_final_models.py
src/experiments/closure_final_calibration.py
src/experiments/lock_closure_final_calibration.py
src/experiments/run_closure_anfis_learning_curve.py
tests/test_calibrate_closure_final_models.py
tests/test_closure_anfis_learning_curve.py
tests/test_closure_final_calibration.py
tests/test_lock_closure_final_calibration.py
```

No heavy path, Parquet file, model, checkpoint, prediction, or outcome belongs
to H. P publishes exactly these two files with Git mode `100644`:

```text
reports/closure_v1/00_protocol/final_calibration_lock.json
reports/closure_v1/00_protocol/final_calibration_lock_manifest.json
```

The manifest is published last. R publishes exactly eight light artifacts:

```text
reports/closure_v1/03_calibration/calibrator_specs.json
reports/closure_v1/03_calibration/calibration_metrics.csv
reports/closure_v1/03_calibration/alert_thresholds.csv
reports/closure_v1/03_calibration/ordinal_cutpoints.csv
reports/closure_v1/03_calibration/model_availability.csv
reports/closure_v1/03_calibration/final_calibration_manifest.json
reports/closure_v1/07_anfis_ablation/anfis_learning_curve.csv
reports/closure_v1/07_anfis_ablation/anfis_learning_curve_manifest.json
```

The six calibration files are one bundle and the two E7 files are another.
Each manifest is published last and binds every preceding member. H, P, and R
have zero overlap. Neither P nor R may include `.dvc`, Parquet, model, or
checkpoint files.

R is sequential and one-shot. The six-file calibration bundle is built and
published first. E7 may start only after that bundle is complete and
canonical, and then publishes its two files. If any output or private guard
for a runner is already present, whether partial or complete, that runner
stops immediately after its gate and before loading inputs, calibrating, or
fitting. A second invocation never recalibrates or repeats the 15 E7 fits.

## Closed scientific input inventory

Although P contains only two light JSON files, its lock closes all scientific
inputs needed by R. The inventory contains 66 Git-bound authority records and
94 physical payload bindings. Its closed partitions contain 97 calibration
inputs and 15 E7 inputs. The P0/P1 unavailable-model namespace contains 190
registered paths: exactly 20 present reports/manifests and 170 required
absences.

The inventory covers targets and common-origin records; B0/B1/B2 and M0
manifests, pointers, and Git/DVC bindings; and A0/A1 predictions, sequences,
models, preprocessors, and checkpoints. Each record binds its path, bytes,
digest, mode, and relevant physical identity. A runner reopens every input
through one parent-anchored `O_NOFOLLOW` descriptor and checks the same
snapshot before and after publication. An output manifest is evidence only;
it cannot create, complete, or replace P authority after the fact.

`data/targets/target_manifest_v0.json` is inside a DVC-owned tree and is not
misrepresented as a Git root. The closed chain uses the Git-bound
`data/targets.dvc` pointer and `protocol_lock.json`; the latter binds both the
physical manifest and `monthly_targets_model_v0.parquet` by byte count and
SHA-256. The inventory also retains all five exact `model_unavailable`
manifests and reports for each of P0 and P1, requires their model/checkpoint/
preprocessor namespaces to be absent, and keeps A2 absent without a
substitute.

Two physical payload classes are accepted. Ordinary payloads must be regular
`0644`, single-link files. A DVC-managed payload may be regular `0444` with
exactly two links only when the other name is the expected cache object for
an authorized pointer and both names resolve to the same device, inode,
bytes, and digest. A third link, a writable cache-linked payload, a wrong
cache object, or any alias drift fails closed.

## Availability matrix

The lock retains every model slot, including models for which calibration is
not applicable or unavailable:

| State | Models | Rule |
|---|---|---|
| `calibratable` | `B0`, `B1`, `B2`, `M0`, `A0`, `A1` | Emit records for every applicable seed, surface, endpoint, and horizon |
| `not_applicable` | `F0`, `F1` | Do not invent calibrators or null artifacts |
| `unavailable` | `P0`, `P1`, `A2` | Retain the slot and reason without changing denominators |

The closed matrix has 66 bloom-calibration groups and 33 ordinal groups. The
30 B1/B2 ordinal groups complete. The three B0 ordinal groups retain
`not_available_degenerate_constant_score`, with null cutpoints rather than
invented thresholds for a constant score. `q_c` applies only to A0 and A1; it
is not filled for other models and unsupported groups are never pooled.

Every bloom group binds the same contractual universe of complete development
target keys. Counts by horizon for 2019/2020/2021 are respectively
`397/261/224`, `371/287/224`, and `344/314/224`: exactly 882 identities per
group. A missing, extra, or swapped identity fails before any calibrator is
fit.

## Temporal roles and method selection

Method selection occurs entirely inside the model-selection role:

1. fit candidates on non-holdout 2019 rows;
2. score the candidates on non-holdout 2020 rows;
3. compare `identity`, `platt`, and `isotonic` by Brier score;
4. retain candidates within `0.001` of the minimum Brier score;
5. break ties by lower ECE using ten equal-width bins;
6. break any remaining tie by simplicity: `identity`, `platt`, `isotonic`;
7. refit only the chosen method on the 2021 `calibration_threshold` role.

B0 is the explicit exception. It uses a fixed identity transform with
`fit_rows=0` and `refit_year=null`; no fit occurs in either 2019 or 2021. Its
metrics and alert threshold are still evaluated on 2021 without relabeling
that calculation as a refit.

Training, evaluation, holdout, post-2021, and holdout-site rows are invalid in
all these operations. PR-AUC is not a selection criterion, and a monotonic
transform cannot be reported as a ranking improvement.

## Alert thresholds and ordinal cutpoints

The 2021 alert threshold maximizes F2 with `beta=2`. Ties prefer higher recall,
then higher precision, then the numerically smaller threshold. Ordinal
cutpoints are strictly increasing and maximize macro-F1; ties prefer lower
ordinal MAE and then the lexicographically smaller cutpoint vector. The
implementation uses an exact dynamic program whose results and tie-breaking
must match exhaustive search on small reference cases; it must not enumerate
all `O(U^3)` triples for large real score universes.

No refit, selection, or threshold adjustment occurs during evaluation. The
thresholds and cutpoints are sealed before E0-U with the model, surface,
endpoint, horizon, and seed that produced them.

## Split-conformal scaling `q_c`

For each exact A0/A1 model, surface, endpoint, horizon, and seed combination,
2021 non-holdout WQP rows produce scores

```text
abs(y - mu) / max(sigma, 1e-6)
```

For each nominal coverage `c in {0.80, 0.90, 0.95}`, `q_c` is the order
statistic at one-based position `min(n, ceil((n + 1) * c))`, without
interpolation. At least 30 finite scores are required. An unsupported group is
explicitly `unavailable`; it is not pooled, interpolated, imputed, or given a
fallback. No evaluation row may adjust a sealed `q_c`.

## Terminal E7 learning curve

E7 attempts module training sizes `4096`, `16384`, and `65536`, in that
canonical order, for the five fixed seeds. Sampling is deterministic and
stratified by `holdout_group_id`, `temporal_period`, and
`expert_anchor_band`; holdout and post-2021 rows are always excluded.

Three historical blockers retain their exact bytes and Git bindings. The
development runtime remains `blocked_pending_sampling_strata_contract`; the
training and sequence runtimes remain `blocked_for_separate_gate`; and the
sequence runtime also retains `e7_learning_curve_sizes_authorized=false`.
E0-MCAL adopts all three exact records and supersedes them only for E7 through
a closed additive contract. It does not rewrite or reinterpret history.

After applying the same per-module eligibility filter as the production
sampler, the runner derives its strata internally and never trusts caller
columns:

- `holdout_group_id = source_id::site_id`, checked against the development
  assignment;
- `temporal_period` uses thirds of the sorted unique months in the eligible
  universe, with index `floor(3*i/n)` and labels `early`, `middle`, `late`;
- `expert_anchor_band` uses the module target and fixed intervals
  `[0,1/3)`, `[1/3,2/3)`, `[2/3,1]` with labels `low`, `middle`, `high`.

Evidence retains the month-to-period map and digest, each module's eligible
universe and digest, and every stratum assignment/count. Exact physical
eligible counts are `ANFIS-N=4757`, `ANFIS-F=35273`, and
`ANFIS-T-no-current=35419`.

All 45 module preflights are retained. Exactly 25 sample preflights succeed:
the 15 module samples at 4096 plus the ten ANFIS-F/ANFIS-T-no-current samples
at 16384. Exactly 20 preflights record an insufficient universe: the five
ANFIS-N samples at 16384 and all 15 module samples at 65536. A slot performs
fits only if all three module preflights succeeded, so the terminal table has
exactly 15 rows: five completed `4096×seed` slots with 15 new in-memory E7
fits, followed by ten `resource_failure_recorded` slots with zero fits.

`primary_fit_reuse_count=0` and `new_e7_fit_count=15`. Historical
`locked_hash_ranked_training_sample_4096` samples are not comparable and are
not reused; each new fit has the separate identity
`e7_stratified_training_sample_4096`. E7 writes no model, checkpoint, or
adaptive state. The physical family of 80 primary artifacts is snapshotted
before fitting and revalidated before, during, and after publication.

Each completed row retains per-module loss/fidelity, membership stability,
and a deterministic cost proxy. Downstream metrics remain
`not_estimable_without_separate_temporal_consumers` because P0/P1 are
unavailable. `saturation_claim_authorized=false`: no result may claim
saturation, replace a failed size, or masquerade as an existing primary slot.

A resource limitation does not permit silent omission or post-hoc
substitution. The failed size and diagnostic remain explicit, later sizes are
not fabricated, and the terminal limitation does not authorize opportunistic
retries.

## Outcome and evaluation-batch boundary

Throughout H, P, and R all of the following remain true:

- no post-2021 outcome decoding, aggregation, availability testing, or
  semantic inspection occurs;
- the outcome access log remains absent: H12/P2/R8 do not contain it and no
  MCAL runner creates, opens, or writes it;
- `outcome_access_authorized=false`, `e0_u_authorized=false`, and
  `evaluation_batch_authorized=false`;
- no evaluation prediction, holdout metric, evaluation denominator, or sealed
  evaluation batch exists;
- no evaluation Parquet is opened before effective P authority is verified.

The calibration and E7 entry points call
`require_final_calibration_authority` first. A gate failure occurs before
scientific input loading or creation of directories, temporary files, guards,
or final outputs. MCAL does not replace E0-M. Only the future five-path
P-E0-M bundle may introduce its zero-byte, present outcome-access log.

## Strict publication and loading

`--check-only` is read-only. `--execute-lock` requires exact base, scope,
modes, blobs, refs, model matrix, temporal roles, boundaries, and namespaces.
The publisher:

1. reserves an exclusive, regular, no-follow, single-link `0600` guard;
2. walks parents by dirfd and rejects symlinks, foreign hardlinks,
   non-regular entries, and existing destinations;
3. writes private temporary files, fsyncs file and directory, and publishes by
   an exclusive link/rename operation;
4. revalidates bytes, SHA-256, `0644`, `nlink=1`, and full identity;
5. publishes data members first and the manifest last;
6. before the linearization point, rolls back every owned inode and no foreign
   inode; after commitment, an output is either recognizable as complete or
   cleanup remains safely recoverable;
7. removes owned temporary files, empty owned directories in reverse order,
   and the guard without erasing foreign or nonempty directories.

Public loading requires published P and reconstructs its Git bindings. It
rejects `locked_unpublished` authority. Every file read is bound to one
regular `O_NOFOLLOW` descriptor, and all validated metadata belongs to that
descriptor. Byte, inode, mode, link-count, mtime/ctime, manifest, scope, ref,
or namespace drift fails closed. No public caller can forge the private
coordination record used during a transaction.

## Separate authorizations

Each transition requires a new, explicit authorization:

1. publish H-E0-MCAL;
2. execute the P lock once;
3. prepare and publish P-E0-MCAL;
4. execute the six-file calibration R bundle;
5. execute the two-file E7 R bundle;
6. prepare and publish R.

Neither H nor P authorizes an R runner. R does not authorize E0-M, E0-U,
outcome access, network access, DVC, push, commit, or overwrite. A failure
consumes only the invocation that was authorized and requires a stable audit
before any new overlay or authorization is considered.

## Acceptance criteria

- exact H `12A`, P `2A`, and R `8A` scopes with zero overlap;
- canonical JSON/CSV, manifest-last, `0644`, single-link, and no-clobber;
- exact `6 calibratable / 2 not_applicable / 3 unavailable` matrix;
- 66 bloom groups, 33 ordinal groups, and A0/A1-only `q_c`;
- 2019 fit, 2020 assessment, 2021 refit/threshold/cutpoint, zero holdout;
- exact target universes of 882 rows per group and strict target label/risk
  cross-binding;
- E7 exact 15 terminal rows (`5 completed`, `10 resource_failure`), 15 new E7
  fits, `primary_fit_reuse_count=0`, 45 module preflights partitioned into
  25 successful and 20 resource records, and eligible universes
  `4757/35273/35419`;
- no model/checkpoint overwrite, substitution, or saturation claim;
- loaders, publisher, and rollback fail closed on drift, aliases, malformed
  evidence, or TOCTOU;
- the outcome access log remains absent and all outcome/batch/E0-U
  authorizations remain `false`; MCAL does not substitute for the future
  five-path P-E0-M bundle;
- no DVC, network, staging, commit, or push belongs to this contract.
