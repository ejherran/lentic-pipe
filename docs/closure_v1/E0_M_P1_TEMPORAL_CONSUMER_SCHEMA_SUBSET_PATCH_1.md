# Closure V1 E0-MG P1 Temporal Consumer Schema-Subset Patch 1

## Status

This document defines an additive, outcome-free compatibility gate for the
single `P1` temporal consumer slot with `base_seed=1729` on CPU. It supersedes
the two runtime-routing components of H-E0-MF while preserving the other five
H-E0-MF components byte for byte. It does not authorize the consumer until a
future P-E0-MG lock and companion have been published as an exact two-file
commit.

## Scope

H-E0-MG must be the direct, non-merge child of
`ba5d42f391af1c9574a6c27a711083dd56b30147`. Its public diff is closed to two
modifications and five additions:

- modified: `src/experiments/train_closure_pipe.py`;
- modified: `tests/test_train_closure_pipe.py`;
- added: `configs/closure_v1/p1_temporal_consumer_schema_subset_patch_lock.schema.json`;
- added: `docs/closure_v1/E0_M_P1_TEMPORAL_CONSUMER_SCHEMA_SUBSET_PATCH_1.md`;
- added: `src/experiments/closure_p1_temporal_consumer_schema_subset_patch.py`;
- added: `src/experiments/lock_closure_p1_temporal_consumer_schema_subset_patch.py`;
- added: `tests/test_closure_p1_temporal_consumer_schema_subset_patch.py`.

The following H-E0-MF components are historical inputs whose current bytes
must remain identical to their Git blobs at `ba5d42f`:

- the H-E0-MF schema;
- the H-E0-MF public protocol;
- the H-E0-MF validator;
- the H-E0-MF locker;
- the H-E0-MF test module.

The trainer and its test are the only superseded H-E0-MF components. The
historical authority is reconstructed from Git. The effective H-E0-MF loader
must never be called, and the two P-E0-MF output paths must be absent both
lexically and from all Git history.

## Failed P-E0-MF execution

The authorized P-E0-MF execute-lock process completed its prelock, acquired
both guards, and completed the full type check, the closed 262-test command,
the pytest-summary parser, Poetry validation, publication guard, diff check,
the fixed in-process P1/1729 auditor, and both targeted DVC pushes. The second
push passed the idempotence predicate. The consumer namespace and repeated
prelock remained unchanged, and the payload was built.

The process then loaded the H-E0-MF schema and failed before inspecting the
payload instance. The exact preserved exception was:

```text
_JsonSchemaDefinitionError: Unsupported JSON Schema keyword(s) at #/$defs/fileRecord/properties/bytes: ['minimum']
```

The H-E0-MF schema contains ten `minimum` keywords. It also contains one
`format` keyword, which would be rejected later by the same closed validator
subset. The failure was a schema-definition compatibility defect, not a
scientific, data, parser, audit, DVC, or model-availability failure.

No command-evidence payload was published. Therefore H-E0-MG records only the
facts implied by successful control-flow completion. It must not invent or
claim an exact first-push terminal, pytest summary line, duration, stdout hash,
or stderr hash from the failed process. No lock, companion, consumer artifact,
model, checkpoint, preprocessor, metric, blend, E0-M output, or outcome-access
record was written. Transaction cleanup released both guards.

## Closed schema subset

`src/experiments/closure_contract.py` intentionally implements a closed
Draft 2020-12 subset. It is an immutable historical protocol component and a
physically pinned support source of the P1 auditor. H-E0-MG does not modify it.

The MG schema uses only keywords accepted by that closed implementation. It
contains neither `minimum` nor `format`. Removing those keywords does not
weaken the effective contract because their assertions are performed by the
MG semantic validator:

- physical file sizes and schema bytes are positive or non-negative as
  appropriate;
- record bundles and component counts are reconstructed and compared exactly;
- command stdout and stderr line counts are non-negative integers, with
  booleans rejected;
- the focused test count is the exact closed count and skipped/deselected
  counts are zero;
- canonical auditor result bytes are strictly positive;
- `created_at_utc` must parse as an ISO timestamp with an explicit timezone;
- generated Git and filesystem records remain exact, including byte counts and
  SHA-256 hashes.

## Early schema preflight

The validator exposes
`preflight_p1_temporal_consumer_schema_subset_patch_schema()`. It reads only the
closed physical schema path, requires a regular non-empty JSON file, rejects
any `minimum` or `format` occurrence, runs the same closed schema-definition
validator used for the final payload, and returns exactly:

- `gate`;
- `schema_path`;
- `schema_bytes`;
- `schema_sha256`;
- `supported_subset_verified`;
- `minimum_keyword_absent`;
- `format_keyword_absent`.

Check-only and execute-lock must invoke this preflight before acquiring output
guards or running full type checks, pytest, audits, DVC, or any other external
command. The returned evidence is sealed as
`verification.schema_subset_preflight` and must still equal the live physical
schema when the final payload is validated.

## Verification order

After the early schema preflight, a future authorized execute-lock must retain
the following order:

1. acquire the two E0-MG guards and prove the output namespace empty;
2. collect the clean, published H-E0-MG prelock and historical authorities;
3. run the complete type check;
4. run the exact closed focused test command and parse one terminal summary;
5. run `poetry check`, the publication guard, and `git diff --check`;
6. call the fixed P1/1729 auditor in process and validate canonical evidence;
7. only after the audit passes, run the first targeted DVC push;
8. repeat the identical targeted push and require exact idempotence;
9. prove the consumer namespace and prelock remain unchanged;
10. build and validate the complete MG payload against the physical schema and
    all semantic checks;
11. publish the lock without clobbering an existing path;
12. publish the companion last as the completion marker;
13. reload and physically re-audit the unpublished bundle;
14. release both guards only after the transaction is complete.

Any failure must roll back only files owned by the current transaction, using
their anchored parent and `(device, inode)` identity. Foreign replacements,
symlinks, partial outputs, stale guards, and non-regular files fail closed.

## Future publication topology

P-E0-MG is a future exact two-addition commit whose parent must be the exact
published H-E0-MG commit:

```text
reports/closure_v1/00_protocol/p1_temporal_consumer_schema_subset_patch_lock.json
reports/closure_v1/00_protocol/p1_temporal_consumer_schema_subset_patch_lock_manifest.json
```

The companion contains only current physical inputs in `inputs[]`; the two
superseded H-E0-MF records belong in `historical_inputs[]` with their Git
commit. Historical inputs are never compared against superseding current
paths.

## Authorization boundary

Before P-E0-MG publication, every effective authorization remains false. A
published, physically and remotely verified P-E0-MG may authorize only the
`P1`, seed `1729`, CPU consumer. It preserves the existing unavailable-model
result:

```text
model_unavailable / not_attempted / sequence_fit_rows_unavailable
```

The expected consumer remains report plus manifest only. No model,
checkpoint, preprocessor, calibration artifact, metric, blend, fallback,
replacement, batch-seed execution, retry, E0-M, evaluation, E0-U, holdout, or
post-2021 outcome access is authorized by this patch.
