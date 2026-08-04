# E0-DLT: Closure V1 Temporal-Consumer Atomicity Patch 1

## Status and scope

E0-DLT is an additive implementation-hardening overlay over the immutable
E0-DL, E0-DLP, and E0-DLS authorities. It binds the already published P0
sequence bundle before any temporal consumer may run. It changes no scientific
decision, mapping, denominator, split, seed, or model-unavailable semantics.
Evaluation, E0-U, holdout outcomes, and post-2021 outcomes remain sealed.

The trigger was the audit of the first P0 sequence bundle. P0 contains 9,732
intended origins, of which 9,227 are valid and 505 retain an unavailable
autoregressive target. The 488 unavailable origins that belong to fit roles
must produce a failed temporal-model slot with:

```text
status=model_unavailable
fit_status=not_attempted
failure_reason=sequence_fit_rows_unavailable
```

No checkpoint may be produced for that failed slot and no denominator may be
silently reduced. This behavior was already closed by E0-DLS. E0-DLT only
hardens the temporal consumer's one-shot publication transaction so a crash or
concurrent process cannot leave a partial slot that looks complete.

## Closed implementation correction

Every P0 seed slot uses one exclusive guard under ignored `tmp/`:

```text
tmp/closure_v1_temporal_consumer/P0_seed_<base_seed>.guard
```

The guard is acquired before checking any final or temporary output and is
held through publication. The consumer then applies these rules:

- broken symlinks count as existing evidence;
- every temporary file is created exclusively;
- a final is published with a no-clobber atomic operation;
- the completion manifest is published last;
- rollback removes only inodes created and still owned by that invocation;
- a failed `model_unavailable` slot never replaces a prior slot;
- P0's five registered seeds remain `1729`, `20260612`, `20260613`,
  `20260614`, and `314159`;
- CPU-only development execution remains mandatory.

These rules do not authorize a temporal fit by themselves. The runtime loader
fails closed until P-DLT is committed and published.

## Historical authority and closed topology

The authority chain is strictly additive:

```text
P-DLS 92a9fb1ba17a61cb91c0b89782f2dd4bf956b5e1
-> P0 bundle b075d4f1606aa35c1b86493604c18845f2d28a2f
-> H-DLT
-> P-DLT
```

H-DLT must be a direct, non-merge child of the published P0 bundle. Its Git
diff contains exactly six modifications and five additions.

The six E0-DLS components explicitly superseded by H-DLT are:

```text
src/experiments/build_closure_pipe_sequences.py
src/experiments/rollout_closure_pipe.py
src/experiments/train_closure_pipe.py
tests/test_build_closure_pipe_sequences.py
tests/test_rollout_closure_pipe.py
tests/test_train_closure_pipe.py
```

The five E0-DLS components preserved byte-for-byte are:

```text
configs/closure_v1/development_runtime_sequence_patch_lock.schema.json
docs/closure_v1/E0_D_RUNTIME_SEQUENCE_PATCH_1.md
src/experiments/closure_development_runtime_sequence_patch.py
src/experiments/lock_closure_development_runtime_sequence_patch.py
tests/test_closure_development_runtime_sequence_patch.py
```

The five additions in H-DLT are:

```text
configs/closure_v1/development_runtime_temporal_consumer_patch_lock.schema.json
docs/closure_v1/E0_D_RUNTIME_TEMPORAL_CONSUMER_PATCH_1.md
src/experiments/closure_development_runtime_temporal_consumer_patch.py
src/experiments/lock_closure_development_runtime_temporal_consumer_patch.py
tests/test_closure_development_runtime_temporal_consumer_patch.py
```

The H-DLT lock binds the published P-DLS lock and companion, all 40 components
preserved by the nested P-DLS base authority, the exact 6+5 E0-DLS component
partition, and the P0 Git/DVC bundle. The latter includes the
explicit pointer, the 1,377,124-byte Parquet with SHA-256
`a10fbe5054d795b44dac1da2853a387b4dbead3e04dd7d9d942313b2aa5318fd`,
and its completion manifest. It does not reinterpret or open outcomes.
Authority readers and locker output parents walk from the repository root by
directory file descriptor and reject every symlinked ancestor. Verification
removes inherited Python/virtualenv overrides, replaces executable search with
a closed path, and resolves fixed `.venv/bin` tools through the same no-follow
walk.

## Lock procedure

After H-DLT is committed, pushed, clean, and identical to live `origin/main`,
the non-writing preflight is:

```bash
poetry run python src/experiments/lock_closure_development_runtime_temporal_consumer_patch.py \
  --check-only
```

The real lock requires a separate explicit authorization:

```bash
poetry run python src/experiments/lock_closure_development_runtime_temporal_consumer_patch.py \
  --execute-lock
```

The locker revalidates the historical authorities and physical P0 payload,
proves that all 95 final, temporary, and guard paths for the five P0 seeds are
absent, and runs the full type check, the closed focused suite with exactly 156
passing tests and no skip/deselection, `poetry check`,
the publication guard, and `git diff --check`. It also runs two identical,
targeted DVC pushes for the P0 pointer; each must terminate exactly with
`Everything is up to date.`. It does not run a sequence builder, temporal
consumer, rollout, evaluation, E0-M, E0-U, or outcome reader.

The two lock outputs are reserved for the entire gate and published without
clobbering. P-DLT must be the direct, non-merge child of H-DLT and add exactly:

```text
reports/closure_v1/00_protocol/development_runtime_temporal_consumer_patch_lock.json
reports/closure_v1/00_protocol/development_runtime_temporal_consumer_patch_lock_manifest.json
```

The companion is written last and binds the P-DLS lock and companion, the new
schema and validator, and the published P0 pointer and manifest. The lock's
future publication commit is discovered from Git history, avoiding a circular
hash.

## Authorization after publication

Only after P-DLT is committed, pushed, clean, unchanged, and aligned with live
`origin/main` does
`require_development_fit_authorized_with_temporal_consumer_patch()` return an
effective CPU development-fit authorization. Before that publication it fails
closed. Every temporal fit still requires a separate one-shot user
authorization.

P-DLT does not authorize evaluation or E0-U, does not replace E0-M, and does
not authorize access to holdout or post-2021 outcomes.
