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

The superseding H-E0-MBATCH overlay is based on the published H-E0-M
prerequisite at `4bf1953660462b63115a47f97b1041e44d33d873`, itself the
direct child of `53947df3b826ee10be8cf3b137bae913bc73d2bb`. The formal lock must require,
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

H-E0-MBATCH is the direct non-merge child of the prerequisite above and has
exact scope `7M+10A`. It modifies the seven prerequisite paths (schema, this
document, precommit adapter, formal core, locker, runner, and governance test)
and adds exactly the ten E2--E10 component paths enumerated by the runner.
The runner contains E1 internally; no outcome data is read by H.

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
/usr/bin/env -i LANG=C LC_ALL=C .venv/bin/python -I -S -B src/experiments/run_closure_benchmark.py --execute-sealed-batch
```

Its exact external launch argv is:

```text
["/usr/bin/env", "-i", "LANG=C", "LC_ALL=C", ".venv/bin/python", "-I", "-S", "-B", "src/experiments/run_closure_benchmark.py", "--execute-sealed-batch"]
```

The inner Python `sys.orig_argv` is exactly
`[".venv/bin/python", "-I", "-S", "-B",
"src/experiments/run_closure_benchmark.py", "--execute-sealed-batch"]` and the
working directory is the repository root. There is no shell, glob,
interpolation, redirection, pipeline, optional flag, inherited environment,
extra argument, or alternative entrypoint. E0-M binds the runner's path,
bytes, SHA-256, mode, Git blob, complete startup contract, and exact external
and inner commands. Under E0-M alone, `--check-only` may validate the
outcome-free contract, but `--execute-sealed-batch` must fail before any
outcome path or evaluation I/O.

The executable performs an authenticated, outcome-free bootstrap before it
executes any future E0-U source. It requires exact isolated/no-site/no-bytecode
flags, exact `LANG=C`/`LC_ALL=C` as the entire environment, exact bootstrap
`sys.path`, import hooks, no trace/profile hook, and sealed identities for
`/usr/bin/env`, Python, `/usr/bin/git`, local Git config, and the HTTPS remote
helper. The future authority must already be a regular tracked `100644` file
whose physical bytes equal the index and a locally recomputed,
content-addressed HEAD commit/tree/blob chain. Local `main`, `origin/main`,
`origin/HEAD`, HEAD, and live `main` at the literal HTTPS repository URL must
all agree before those bytes are compiled. Missing E0-U stops at the local
anchored source lookup before the live-remote query.

The authenticated authority source permits only a module docstring, exact
future-annotations directive, literal constants, and undecorated function
definitions; classes, executable top-level imports or expressions, common
dynamic-loader/reflection primitives, and nonliteral defaults are forbidden.
Direct import statements inside functions are restricted to a closed stdlib
allowlist, and the authority runs with a restricted builtins mapping. The
content-addressed, live-remote Git binding remains the authority for the
behavior inside the authenticated `require` function; this contract does not
claim that arbitrary Python function behavior can be proven safe by a static
syntax filter alone. Its `require` API is the first
capability-bearing/outcome-bearing operation, not the first bootstrap check.
The compatibility field `authority_is_first_execute_operation=true` is
therefore defined narrowly as "first capability or outcome operation after the
authenticated outcome-free bootstrap"; it does not erase or mislabel those
preceding trust checks.
Only after that API returns may the runner activate the authority-bound
runtime: it validates exact wheel `RECORD` and recursive physical records for
the ten declared distributions and native-library roots, sets the structurally
non-creatable pycache prefix `/dev/null/closure_e0_u_pycache`, appends purelib
without `site` or `.pth`, and installs a closed origin-checking import guard.
The runner rejects preactivated scientific modules, seals existing importer
cache entries by object identity, accepts only exact loader types/origins, and
recaptures the exact process environment, module/import topology, runtime
records after callbacks, immediately before and after publication/audit, and
at the terminal boundary. The E0-U result has an exact public keyset; runner
callables and observed private records never enter component contexts.
Component diagnostics have exact, branch-aware keysets and
permit only finite JSON scalars, lists, and string-keyed maps; DataFrames,
arrays, bytes, paths, callables, tuples, and extra keys cannot travel through
the diagnostics channel.

The kernel, ELF loader, `/usr/bin/env`, Python executable and linked system
libraries, and Python frozen/stdlib bootstrap are an unavoidable external TCB
before Python can run its own checks. The sealed launcher minimizes that TCB
and the first Python boundary detects drift; it does not claim to
retroactively prevent side effects from a compromised pre-Python TCB.
The live-remote check likewise treats the sealed `git-remote-http` helper plus
the system libcurl/TLS/DNS/CA transport stack as an explicit external network
TCB; it does not claim a complete binary closure of that system stack.

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

### Superseding implementation-readiness barrier

The published prerequisite remains immutable evidence of the earlier
`missing_component_count=11` STOP. H-E0-MBATCH supersedes only that readiness
surface: it supplies E1 and all ten external component paths and requires
`status=sealed_batch_runner_ready_for_formal_lock`, exact zero missing
components, `formal_model_lock_ready=true`, `evaluator_available=true`, and
`sealed_batch_execution_ready=true`. This means the command and all component
APIs are sealable; it does not execute them and does not authorize E0-U.
Target access, outcome access, writes, E0-M authorization, E0-U authorization,
and evaluation authorization remain false throughout H and P.

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

All five output byte strings are first rebuilt in memory from outcome-free
inputs, strictly parsed, byte-hashed, metadata-checked, and cross-bound before
any final appears. Each output then passes through its own private temporary
and a no-clobber publication step in the exact five-record order above. Every
step is bracketed by full-state recapture. The empty log is published fourth
and verified at exact zero bytes; the cross-binding `model_lock.yaml` is
published fifth and last. A later failure rolls back only owned final inodes
in reverse order. Foreign or ambiguous state is retained for audit and
produces STOP rather than destructive cleanup.

The locker exposes this transaction only as
`--execute-formal-model-lock`; it is separate from `--execute-lock` (P).
After publication, the builder validates all five named owned-inode
identities, exact bytes, semantic relationships, output order, empty-log
state, P authority, R8, R10, repository, remote, namespace, and guard before
emitting a success result. The unpublished `model_lock.yaml` keeps
`e0_m_authorized=false` and records only that E0-M becomes effective after
publication; the strict loader is the sole source of the effective
authorization bit. The builder performs no DVC add/push and no Git add/commit/
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

1. Preserve published H-E0-M `1M+6A` as immutable prerequisite evidence.
2. Publish H-E0-MBATCH `7M+10A` as its direct child; do not create P or R.
3. Under separate authorization run `--check-only`; require equal captures,
   absent P/R, no writes, no verification, no outcome access, and exact
   `sealed_batch_runner_ready_for_formal_lock`/missing-zero readiness.
4. Under a new authorization run `--execute-lock`; publish only P
   authority then companion and audit them before precommit.
5. Publish exact P-E0-M `2A`, verify clean local/tracking/live-remote refs, and
   reload the effective authority independently.
6. Under a new explicit one-shot authorization, create exact R-E0-M `5A` in
   calibration/hypothesis/batch/empty-log/model-lock-last order.
7. Strictly audit R, then run precommit under separate authorization; require
   exact dialect adoption, exact five staged additions, no DVC selection or
   command, and no other warning or failure.
8. Leave Git commit and Git push to the user. E0-U and the sealed evaluation
   batch remain separately authorized future barriers.

Acceptance requires prerequisite H `1M+6A`, superseding H-E0-MBATCH
`7M+10A`, P `2A`, R `5A`, authority-first and
manifest-last P publication, exact five-output R order with a zero-byte log
fourth and `model_lock.yaml` last, immutable R8/R10, exact runner command and
source identity, complete
companion reconstruction, atomic no-clobber publication, inode-owned rollback,
closed namespace, strict heterogeneous-dialect adoption, zero DVC work, zero
evaluation/outcome access, and every authority outside its named gate false.
