# Closure V1 E0-MF P1 Temporal Consumer Pytest-Summary Patch 1

## Purpose

E0-MF is an additive, development-only authority for the single
`P1`/`1729`/`cpu` temporal-consumer invocation. It repairs only the closed
parser for pytest 9.0.3's duration suffix. The failed P-E0-ME execute-lock
authorization was consumed once. Its process completed prelock, acquired both
output guards, passed full `ty`, and ran the exact focused pytest collection
with return code zero. ME then rejected the terminal summary before reaching
`poetry check`, the publication guard, `git diff --check`, the in-process P1
auditor, DVC, payload construction, or output publication. The owned guards
were rolled back. The concrete stdout was not preserved, so MF does not invent
or seal a recovered terminal line.

Pytest 9.0.3 emits `N passed in S.SSs` below 60 seconds and appends
` (str(timedelta(seconds=int(duration))))` at or above 60 seconds. MF accepts
exactly those two forms, requires the closed test count, one unique final
summary line, exactly two duration decimals, and rejects warning, skipped,
deselected, xfail/xpass, error, or failure statuses. The scientific auditor
remains the same fixed in-process callable introduced by ME.

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

H-E0-MF must be the direct non-merge child of H-E0-ME:

```text
1b30cd658acc9e46779e907e3efb30511f646983
```

Its exact diff is `2M+5A`.

Modified:

```text
src/experiments/train_closure_pipe.py
tests/test_train_closure_pipe.py
```

Added:

```text
configs/closure_v1/p1_temporal_consumer_pytest_summary_patch_lock.schema.json
docs/closure_v1/E0_M_P1_TEMPORAL_CONSUMER_PYTEST_SUMMARY_PATCH_1.md
src/experiments/closure_p1_temporal_consumer_pytest_summary_patch.py
src/experiments/lock_closure_p1_temporal_consumer_pytest_summary_patch.py
tests/test_closure_p1_temporal_consumer_pytest_summary_patch.py
```

P-E0-MF must be the direct non-merge child of H-E0-MF and add exactly:

```text
reports/closure_v1/00_protocol/p1_temporal_consumer_pytest_summary_patch_lock.json
reports/closure_v1/00_protocol/p1_temporal_consumer_pytest_summary_patch_lock_manifest.json
```

Both outputs are immutable after publication.

## Historical E0-ME authority

E0-MF reconstructs H-E0-ME from Git. Its parent, cumulative `2M+5A` diff,
seven component records, and exact commit identity are required. Only the
trainer and its test may be superseded by H-E0-MF. The other five E0-ME
components must remain byte-identical both in Git and in the physical
worktree. Through ME's historical-only API, MF also reconstructs E0-MD and
E0-DLTVM without calling any ME effective loader. It never fabricates an
effective authority from historical metadata.

P-E0-ME never existed. Both historical E0-ME lock paths must remain absent as
Git additions and as lexical filesystem entries. E0-MF does not synthesize a
P-E0-ME authority.

## In-process auditor evidence

The auditor identity is fixed to:

```text
src.experiments.audit_closure_p1_sequence_bundle:audit_p1_sequence_bundle
```

Before calling it, E0-MF verifies its module, name, qualified name, source
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
2. only after P-E0-MF publication is effective, invoke the physical auditor
   in process and require exact equality with the locked audit evidence.

An unpublished lock is never an effective authority. Lock creation may run
the auditor only under a separate execute-lock authorization.

## Verification and egress

The future execute-lock verification keeps full `ty`, the exact focused
pytest collection, `poetry check`, publication guard, and `git diff --check`.
The focused parser accepts the short form only below 60 seconds and requires
the exact `timedelta` clock at or above 60 seconds; neither an absent clock nor
an inconsistent clock is permitted.
The in-process auditor runs after all local checks and strictly before either
DVC push; a parser or auditor failure therefore leaves both pushes unreachable.
It also keeps two identical DVC pushes directed solely at the existing
P1/1729 pointer; the second must return exact idempotence. Only ty, pytest,
and DVC use the inherited fixed regular-executable check. The P1 auditor is
not a subprocess command.

## Transaction and prohibitions

The locker owns a unique ignored E0-MF guard namespace. It publishes lock
then companion using exclusive guards, regular-file no-clobber hard links,
manifest-last ordering, directory synchronization, and rollback limited to
owned inodes. A failed transaction must leave no lock, companion, temporary,
or guard file.

E0-MF does not authorize another sequence build, another seed, a retry under
an earlier authority, fitting unavailable rows, replacement, E0-M, E0-U,
evaluation, holdout/outcome access, DVC add, Git commit, or Git push. Consumer
execution remains a later explicit one-shot decision.
