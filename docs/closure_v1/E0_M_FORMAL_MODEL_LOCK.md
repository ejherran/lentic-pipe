# E0-M: formal model lock before unblinding

## Purpose

E0-M closes the development phase before any Closure V1 post-2021 outcome is
opened. It records the final model-availability decisions, calibration
authority, registered hypotheses, and the one future batch command, and it
creates the outcome-access log in its required present-but-empty state.

E0-M is a protocol lock. It does not fit, refit, calibrate, score, evaluate,
unblind, inspect target availability, count future outcomes, or execute the
sealed batch. It does not authorize E0-U. Models that are unavailable at this
boundary remain explicitly unavailable; the lock never creates placeholder
models, substitutes historical implementations, drops failed origins, or
changes denominators after development.

## Published predecessor authorities

H-E0-M is based on the published Closure V1 state at
`53947df3b826ee10be8cf3b137bae913bc73d2bb`. The formal lock must require,
among all other frozen predecessors, both of the following independently:

- the exact published final-calibration R8 authority and all eight immutable
  final-calibration records, with digest
  `524928813b26bed6de9feee34eff1e946f9fc214521c3a39171ed905b3faf7a2`;
- the exact published locked-evaluation R10 authority and all ten live input
  records, with strict digest
  `2b1e89ffa6816ad3bbaa8e1e8c5122b6b0b014dfc4645886443ffabe84036c17`.

R8 is calibration evidence and R10 is outcome-free evaluation input. Neither
bundle is an E0-M output. H, P, and R must preserve every predecessor byte,
path, type, mode, DVC identity, Git identity, manifest binding, and scientific
relationship. E0-M must not rewrite, restage, re-register, push, move,
quarantine, or otherwise adopt either predecessor bundle.

The gate also reconstructs the published P0 and P1 development authorities,
the five registered seeds, all declared model availability, exact
intent-to-predict denominators, feature-lineage audits, zero holdout-fit
overlap, the analysis plan, and the model benchmark. A missing, partial,
foreign, stale, unpublished, dirty, or remote-divergent predecessor fails
closed.

## Additive H/P/R topology

The unique gate is `E0-M` and the module stem is
`closure_formal_model_lock`.

H-E0-M is the direct non-merge child of the published base above and has exact
scope `1M+6A`. The sole modification is:

- `src/data/prepare_commit_artifacts.py`.

The six additions are:

- `configs/closure_v1/formal_model_lock.schema.json`;
- this document;
- `src/experiments/closure_formal_model_lock.py`;
- `src/experiments/lock_closure_formal_model_lock.py`;
- `src/experiments/run_closure_benchmark.py`;
- `tests/test_closure_formal_model_lock.py`.

P-E0-M is the direct non-merge child of H and contains exactly two regular
`100644` additions, in this publication order:

1. `configs/closure_v1/formal_model_lock_authority.json`;
2. `configs/closure_v1/formal_model_lock_authority_manifest.json`, last.

The P companion is canonical JSON. It binds the authority as its sole output,
binds every current physical input needed to rebuild the authority, and keeps
superseded Git blobs in an explicit `historical_inputs` collection instead of
misrepresenting them as current files. Its script is
`src/experiments/lock_closure_formal_model_lock.py`. The core fixes the exact
counts, sorted path sets, modes, byte counts, SHA-256 values, Git blobs,
commits, roles, and aggregate digests; duplicate, omitted, additional, or
reordered records fail closed.

P publication is necessary but not sufficient to create the formal model
lock. The effective P authority must be published, clean, remotely aligned,
and reloaded successfully. A separate explicit user authorization then permits
one one-shot R-E0-M transaction. R-E0-M contains exactly five additions and no
modifications or deletions, in this immutable physical publication order:

1. `reports/closure_v1/00_protocol/calibration_lock.yaml`;
2. `reports/closure_v1/00_protocol/hypothesis_registry.csv`;
3. `reports/closure_v1/00_protocol/locked_batch_command.txt`;
4. `reports/closure_v1/00_protocol/outcome_access_log.jsonl`, empty;
5. `reports/closure_v1/00_protocol/model_lock.yaml`, the logical manifest and
   publication sentinel, last.

The user-only Git commit and Git push barriers remain outside the H/P/R
publishers.

## Exact formal-lock outputs

### Model lock

`model_lock.yaml` records the closed model universe, the five registered
seeds, horizons 1/2/3, exact manifests and code/config identities, feature
lineage, origin denominators, zero holdout-fit overlap, and each slot's final
availability decision. Available slots bind their real model, checkpoint,
preprocessor, metrics, and seed records. Unavailable slots bind their real
report and manifest plus the declared failure/unavailability reason, and must
not invent a model, checkpoint, preprocessor, metric, calibrator, threshold,
or replacement.

The model universe is exactly `B0`, `B1`, `B2`, `F0`, `F1`, `P0`, `P1`,
`M0`, `A0`, `A1`, and `A2`. The terminal-status vocabulary is sealed by the
core and runner. Every intended origin remains represented by a terminal
status; silent deletion and survivor-only denominators are forbidden.

### Calibration lock

`calibration_lock.yaml` binds the immutable R8 authority and records the final
calibrator specifications, calibration metrics, alert thresholds, ordinal
cutpoints, model availability, ANFIS learning-curve evidence, and their
manifest relationships. Calibration fields are conditional on model
availability. An unavailable model remains unavailable rather than receiving
a fabricated calibrator, threshold, or cutpoint.

### Hypothesis registry

`hypothesis_registry.csv` is a deterministic projection of the already
published analysis plan. It fixes every registered comparison, estimand,
metric family, direction, cohort, horizon, multiplicity universe, and
availability condition before outcomes. A comparison that is not estimable
because a model is unavailable remains registered with the prescribed
not-estimable policy; it is not removed from the Holm universe and receives no
invented effect, confidence interval, or p-value. The registry contains no
observed result or future-outcome-derived field.

### Sealed batch command

`locked_batch_command.txt` contains exactly one newline-terminated command:

```text
.venv/bin/python -I -B src/experiments/run_closure_benchmark.py --execute-sealed-batch
```

Its exact argv is:

```text
[".venv/bin/python", "-I", "-B", "src/experiments/run_closure_benchmark.py", "--execute-sealed-batch"]
```

There is no shell, glob, interpolation, redirection, pipeline, optional flag,
environment-dependent path, extra argument, or alternative entrypoint. E0-M
binds the runner's path, bytes, SHA-256, mode, and Git blob. The runner must
load the future published E0-U authority as its first gate. Under E0-M alone,
`--check-only` may validate the outcome-free contract, but
`--execute-sealed-batch` must fail before any outcome path or evaluation I/O.

The sealed batch is a single evaluation transaction, not a training command.
Its stage ordering is fixed for the Closure V1 E1--E10 analysis, and it may
consume only the locked model/calibration/hypothesis/R10 authorities. It may
not refit, tune, replace unavailable models, alter thresholds, alter
cutpoints, change hypotheses, silently delete failures, or run a second
evaluation batch.

### Empty outcome-access log

`outcome_access_log.jsonl` is a regular `0644` file with link count one and
exact byte size zero. It has no BOM, whitespace, newline, JSON value, or
record. Its SHA-256 is therefore the SHA-256 of the empty byte string:
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Creating this empty file records the E0-M transition from absent to
present-empty. It does not authorize outcome access. Any nonzero size, record,
replacement inode, pre-existing file, early publication, or write after the
final barrier fails closed. The file is published immediately before
`model_lock.yaml`; the model lock is the manifest-like sentinel published last
only after the empty log and the other three companion outputs are durable and
revalidated.

## H/P locker behavior

### Current implementation-readiness barrier

The H slice may publish the formal-lock infrastructure and the fail-closed
runner contract, but its runner is intentionally incomplete at this revision.
Its source-only runner result is `status=sealed_batch_runner_incomplete`; the
formal prelock/check-only result is
`status=formal_model_lock_infrastructure_incomplete`, with
`missing_component_count=11`, `formal_model_lock_ready=false`,
`evaluator_available=false`, and `sealed_batch_execution_ready=false`. The
declared E1 scientific executor and the required external component APIs are
not yet a complete executable batch. Target access, outcome access, future
outcome access, writes, E0-M authorization, E0-U authorization, and evaluation
authorization all remain false.

Consequently this H revision is infrastructure-only: P-E0-M and R-E0-M are
not eligible to run or publish from it. `--check-only` must expose the barrier,
and `--execute-lock`, the effective authority path, and the one-shot R builder
must fail closed before P/R publication. A later, separately reviewed H
overlay must supply all missing components, produce and seal a new runner
source/contract hash, restore exact zero missing components, and pass the full
outcome-free audit before P may be generated. Publishing the current
incomplete runner as effective formal-model authority would be a protocol
error, not an accepted deferred E0-U implementation detail.

`src/experiments/lock_closure_formal_model_lock.py --check-only` performs
schema preflight and captures the complete outcome-free prelock state twice.
It requires exact H scope, direct topology, clean worktree/index outside the
authorized H slice, aligned local/tracking/live-remote refs, closed namespace,
absent P and R outputs, absent guards and temporaries, exact companion inputs,
and effective predecessor authorities including R8 and R10. Both captures
must be equal. Check-only writes nothing and runs no verification, DVC,
staging, formal-output builder, batch, evaluation, target, or outcome command.

`--execute-lock` starts from the same prelock and brackets the frozen H
verification commands with fresh schema, repository, namespace, predecessor,
R8, R10, and companion captures. Verification may run only the exact commands
sealed by the core. A command failure, wrong test count, skipped/deselected or
warning/failure dialect, output-marker drift, source drift, ref drift, remote
drift, or namespace drift stops before publication.

The P publisher uses an exclusive no-follow guard, anchored parent-directory
walks, private same-filesystem temporaries, no-clobber publication, fsync
barriers, authority-first/companion-last ordering, and rollback restricted to
still-owned inodes. It revalidates the full state under the guard, after each
publication, after companion publication, and at guard release. It never
creates or opens an E0-M R output and never touches R8 or R10.

`--check-effective` loads only a wholly published P authority. The effective
loader is fresh-clone capable and requires the exact H/P Git topology and
scope, canonical P pair, companion reconstruction, live remote, clean
namespace, unchanged predecessors, and either wholly absent R5 or a complete
strictly valid R5. A partial R namespace always fails. Before R exists it
reports the formal-output transaction as not performed. It never infers a
one-shot authorization from publication alone.

## One-shot R transaction

The one-shot formal-output builder may run only after P publication and a new,
explicit user authorization. Before opening any source needed to build R, it
must acquire its own exclusive no-follow guard and recapture the effective P
authority, refs, remote, index/worktree, namespace, R8, R10, configs, source
identities, and all input hashes. The five R finals and every R temporary must
be absent.

All five outputs are built from outcome-free inputs into private temporaries,
strictly parsed, semantically rebuilt, byte-hashed, metadata-checked, and
cross-bound before any final appears. Publication is no-clobber and follows
the exact five-record order above. Every step is bracketed by full-state
recapture. The empty log is published fourth and verified at exact zero bytes;
the cross-binding `model_lock.yaml` is published fifth and last. A later
failure rolls back only owned final inodes in reverse order. Foreign or
ambiguous state is retained for audit and produces STOP rather than
destructive cleanup.

After publication, the builder validates all five named and retained-FD
identities, exact bytes, semantic relationships, output order, empty-log
state, P authority, R8, R10, repository, remote, namespace, and guard before
emitting a success result. It performs no DVC add/push and no Git add/commit/
push. The authorization is consumed by the single attempted transaction; a
failure is not retried without audit and a new explicit authorization.

## Namespace and outcome protections

The formal gate owns only its exact P pair, exact R5, exact guards, and exact
temporaries. Every H/P/R entrypoint rejects symlinks, FIFOs, devices,
directories in file positions, hardlink aliases, unexpected files, legacy
formal-lock names, active predecessor guards, incomplete P/R states, and
coordination artifacts from an incompatible gate.

Outcome-sensitive paths remain unopened throughout H, P, and R. Byte hashing
of the already locked outcome-free R10 bundle is permitted; decoding or
inspecting future targets, target availability, predictions, metrics, or
post-2021 outcomes is not. At successful E0-M completion:

- `evaluation_authorized=false`;
- `e0_u_authorized=false`;
- `outcome_access_authorized=false`;
- `future_outcomes_accessed=false`;
- `evaluation_run=false`;
- `sealed_batch_run=false`;
- `outcome_access_log_records=0`.

Only a later clean, published E0-U authority plus separate explicit user
authorization may permit the runner to open outcomes and append the first
access record.

## Publication-assistant dialect

The R5 mixes YAML, CSV, TXT, and an empty JSONL file. Generic manifest
discovery must not be treated as authority for this heterogeneous protocol
bundle: YAML may not be classified as a manifest, CSV/TXT coverage may appear
uncovered, and an empty JSONL file may be ignored by content-based discovery.

The H adapter may adopt generic findings only for the exact R-E0-M five-file
staged scope, only after the strict formal-lock validator has accepted the
complete P authority and all five exact R bytes and semantics. The accepted
finding multiset is frozen by the core/tests. Any missing, additional,
duplicate, changed, downgraded, or reordered-as-duplicate finding remains a
failure. The adapter must not rewrite an R file, add a fake generic manifest,
invent an `outputs` field, weaken generic behavior globally, or suppress an
unrelated manifest, DVC, freeze, coverage, scope, authority, or namespace
finding.

Precommit may stage only exact R-E0-M `5A`, must select no DVC path, and must
run no DVC add, DVC push, evaluation, batch, outcome, commit, or push command.
The strict validator runs before and after generic inspection and again after
staging. The report must contain no non-adopted warning or failure.

## Acceptance sequence

1. Publish H-E0-M `1M+6A` as the direct child of `53947df3b...`; do not create
   P or R.
2. Under separate authorization run `--check-only`; require equal captures,
   absent P/R, no writes, no verification, no outcome access, and the explicit
   current `sealed_batch_runner_incomplete`/missing-11 result.
3. Stop. Do not run `--execute-lock` and do not generate P or R from this H.
4. In a future reviewed H overlay, implement all missing batch components and
   seal the new runner hash; repeat the full outcome-free check until missing
   count is exactly zero and formal-lock readiness is true.
5. Only then, under a new authorization, run `--execute-lock`; publish only P
   authority then companion and audit them before precommit.
6. Publish exact P-E0-M `2A`, verify clean local/tracking/live-remote refs, and
   reload the effective authority independently.
7. Under a new explicit one-shot authorization, create exact R-E0-M `5A` in
   calibration/hypothesis/batch/empty-log/model-lock-last order.
8. Strictly audit R, then run precommit under separate authorization; require
   exact dialect adoption, exact five staged additions, no DVC selection or
   command, and no other warning or failure.
9. Leave Git commit and Git push to the user. E0-U and the sealed evaluation
   batch remain separately authorized future barriers.

Acceptance requires exact H `1M+6A`, P `2A`, R `5A`, authority-first and
manifest-last P publication, exact five-output R order with a zero-byte log
fourth and `model_lock.yaml` last, immutable R8/R10, exact runner command and
source identity, complete
companion reconstruction, atomic no-clobber publication, inode-owned rollback,
closed namespace, strict heterogeneous-dialect adoption, zero DVC work, zero
evaluation/outcome access, and every authority outside its named gate false.
