# Closure V1 E0-ME P1 Temporal Consumer Verification Patch 1

## Purpose

E0-ME is an additive, development-only authority for the single
`P1`/`1729`/`cpu` temporal-consumer invocation. It repairs only the transport
used to verify the already-published P1 sequence bundle. The failed E0-MD
lock authorization was consumed and its process reached prelock, acquired the
two output guards, then rejected the normal virtual-environment interpreter
symlink. The owned guards were rolled back before any verification command,
DVC command, lock output, consumer, or outcome access. E0-ME invokes the
versioned read-only auditor as a fixed
in-process callable and never relaxes the regular-file policy of
`_require_fixed_venv_executable`.

This patch does not change scientific rows, mappings, denominators, runtime,
availability semantics, or output policy. The only permitted future consumer
result remains:

```text
slot_status=model_unavailable
fit_status=not_attempted
failure_reason=sequence_fit_rows_unavailable
replacement_used=false
```

## Closed topology and scope

H-E0-ME must be the direct non-merge child of H-E0-MD:

```text
95cc19318e359e650843949f810b92c5fd5d2009
```

Its exact diff is `2M+5A`.

Modified:

```text
src/experiments/train_closure_pipe.py
tests/test_train_closure_pipe.py
```

Added:

```text
configs/closure_v1/p1_temporal_consumer_verification_patch_lock.schema.json
docs/closure_v1/E0_M_P1_TEMPORAL_CONSUMER_VERIFICATION_PATCH_1.md
src/experiments/closure_p1_temporal_consumer_verification_patch.py
src/experiments/lock_closure_p1_temporal_consumer_verification_patch.py
tests/test_closure_p1_temporal_consumer_verification_patch.py
```

P-E0-ME must be the direct non-merge child of H-E0-ME and add exactly:

```text
reports/closure_v1/00_protocol/p1_temporal_consumer_verification_patch_lock.json
reports/closure_v1/00_protocol/p1_temporal_consumer_verification_patch_lock_manifest.json
```

Both outputs are immutable after publication.

## Historical E0-MD authority

E0-ME reconstructs H-E0-MD from Git. Its parent, cumulative `2M+5A` diff,
seven component records, and exact commit identity are required. Only the
trainer and its test may be superseded by H-E0-ME. The other five E0-MD
components must remain byte-identical both in Git and in the physical
worktree. E0-ME also reconstructs the historical E0-DLTVM authority required
by H-E0-MD while keeping its effective loader uncalled. Neither the E0-MD
effective loader nor its locker is called.

P-E0-MD never existed. Both historical E0-MD lock paths must remain absent as
Git additions and as lexical filesystem entries. E0-ME does not synthesize a
P-E0-MD authority.

## In-process auditor evidence

The auditor identity is fixed to:

```text
src.experiments.audit_closure_p1_sequence_bundle:audit_p1_sequence_bundle
```

Before calling it, E0-ME verifies its module, name, qualified name, source
path, code filename, and the source record against both the physical file and
the Git blob published in the P1 bundle commit. No Python subprocess, wrapper,
shell, or dynamic callable is accepted.

The full returned mapping is encoded as canonical JSON with sorted keys,
compact separators, UTF-8, and `allow_nan=false`. Its byte count and SHA-256
are locked. Closed evidence additionally requires:

```text
intent origins                 9,732
successful origins             9,227
failed origins                   505
fit successes                  8,925
fit unavailable                  488
calibration unavailable           17
fit failure reason      missing_target_state
```

The result must state `status=validated`, read-only execution, no consumer,
no fitting/model construction, no DVC operation, and no future-outcome access.

## Ordering

The effective loader has two phases:

1. validate schema, fixed metadata, historical Git authorities, H/P topology,
   clean worktree, local refs, and live `origin/main` without opening the P1
   Parquet;
2. only after P-E0-ME publication is effective, invoke the physical auditor
   in process and require exact equality with the locked audit evidence.

An unpublished lock is never an effective authority. Lock creation may run
the auditor only under a separate execute-lock authorization.

## Verification and egress

The future execute-lock verification keeps full `ty`, the exact focused
pytest collection, `poetry check`, publication guard, and `git diff --check`.
It also keeps two identical DVC pushes directed solely at the existing
P1/1729 pointer; the second must return exact idempotence. Only ty, pytest,
and DVC use the inherited fixed regular-executable check. The P1 auditor is
not a subprocess command.

## Transaction and prohibitions

The locker owns a unique ignored E0-ME guard namespace. It publishes lock
then companion using exclusive guards, regular-file no-clobber hard links,
manifest-last ordering, directory synchronization, and rollback limited to
owned inodes. A failed transaction must leave no lock, companion, temporary,
or guard file.

E0-ME does not authorize another sequence build, another seed, a retry under
an earlier authority, fitting unavailable rows, replacement, E0-M, E0-U,
evaluation, holdout/outcome access, DVC add, Git commit, or Git push. Consumer
execution remains a later explicit one-shot decision.
