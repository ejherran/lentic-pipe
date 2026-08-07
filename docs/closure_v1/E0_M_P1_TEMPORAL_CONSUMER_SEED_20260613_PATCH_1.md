# E0-MK — P1 seed 20260613 temporal-consumer authority

## Purpose

E0-MK is an additive, fail-closed authority for exactly one future temporal
consumer invocation: `model_id=P1`, `base_seed=20260613`, `device=cpu`. It is
the ordered successor to the published P1/20260613 sequence bundle. It does
not authorize another sequence build, a model fit, a retry, batch execution,
DVC mutation, evaluation, E0-M, E0-U, or access to future outcomes.

The sealed sequence fit-role evidence contains 8,925 successful origins and
488 origins unavailable because `missing_target_state`; 17 additional failures
belong only to calibration. Consequently the only permitted consumer result is
an atomic report-plus-manifest bundle with:

```text
slot_status=model_unavailable
fit_status=not_attempted
failure_reason=sequence_fit_rows_unavailable
```

No model, checkpoint, preprocessor, metrics, curves, blend artifacts, fallback,
or replacement may be emitted.

## Closed topology

- H-E0-MK base: `a25863c05730d65d0fb3454a608243b2c9eca639`.
- H-E0-MK must be its direct non-merge child and contain exactly `2M+5A`.
- The modified paths are only the temporal trainer and its test module.
- The five additions are this document, schema, validator, locker, and focused
  patch test.
- Future P-E0-MK must be the direct child of H-E0-MK and add only lock plus
  companion manifest.
- Authorization is ineffective until P-E0-MK is published and its strict
  loader verifies local refs and live `origin/main`.

## Historical authorities

The validator reconstructs, but never calls the effective loaders of:

- H/P-E0-MI at `e8efbf8` / `16ee69f`;
- H/P-E0-MJ at `3b86b75` / `04b3420`.

For E0-MI, the trainer and trainer test are explicitly superseded Git blobs;
its other five components remain physically identical. All seven E0-MJ
components remain physically identical. The two published lock bundles are
verified against their introducing commits, exact two-addition topology, and
current bytes. This avoids reactivating the seed-1729 consumer or the already
consumed seed-20260613 builder authority.

## Published sequence evidence

E0-MK binds the `a25863c` publication and its immutable physical payload:

- Parquet: 1,379,656 bytes, SHA-256
  `4dfd3ec12e061d29730fbf005e2e4c7e24a922335da5d4512a9b8c5eb847171a`;
- DVC pointer: 104 bytes, SHA-256
  `a2b6f345ba7340abaf6791bf99d22ec8a989c940f91f3634456fa02bd9902962`;
- summary: 356 bytes, SHA-256
  `a6c6c837a82c13a9321233de03b588c60b7a4198b77dcf31b3c7a62027752c3e`;
- manifest: 6,541 bytes, SHA-256
  `d2ecb7b9b25b0b60a6534d64679db44d77e2484f6e3f269c7ae3db020bcfbac3`;
- read-only auditor source and its focused test as introduced by the same
  exact five-addition commit.

The auditor is only bound statically during H-E0-MK. It is reserved for the
future authorized lock execution because it reconstructs the sequence builder
in process even though it never calls the builder CLI or writes outputs.

## Progression and namespace

At lock time the following must hold simultaneously:

- P1/1729 retains exactly sequence, pointer, summary, sequence manifest,
  unavailable report, and unavailable model manifest;
- P1/20260612 retains the same complete six-record sequence-plus-consumer slot;
- the other 44 registered paths across both completed prior seeds are absent;
- P1/20260613 retains exactly sequence, pointer, summary, and sequence manifest;
- all 19 consumer final/temp/guard paths for P1/20260613 are absent;
- all five P1/20260613 sequence temporary/guard paths are absent;
- all 56 registered paths for the two later seeds are absent;
- all four E0-M paths and the outcome-access log are absent.

The prelock compares the complete 140-path registered P1 universe against the
exact sixteen-path present set; it does not infer closure from only the required
files.

The gate runs immediately after argument parsing and before seed validation,
path resolution, guards, Parquet/schema reads, runtime setup, or output I/O.
The trainer must use the seed-20260613 pointer, auditor, and E0-MJ lock inputs;
the historical seed-1729 pointer and E0-MC input dialect are not valid for this
slot.

## Transaction and future lock

The existing trainer transaction remains authoritative: exclusive slot guard,
no-follow parent checks, temporary regular files, hardlink no-clobber,
report-first/manifest-last publication, and rollback only of owned inodes.

The locker is implemented by H-E0-MK but is not executed by that change. A
future separately authorized execution may run full `ty`, the closed focused
suite, lightweight repository checks, the auditor in-process, and two targeted
DVC pushes for `seed_20260613.parquet.dvc`; the second push must be idempotent.
It may then publish locally only lock plus companion. Check-only performs none
of those commands, audits, writes, DVC operations, or outcome access.

## Explicit non-authorizations

H-E0-MK itself does not execute the locker, builder, consumer, auditor, DVC,
E0-M, E0-U, evaluation, holdout/test reads, or outcomes. The eventual effective
authority permits only the one consumer invocation and still records
`p1_fit_authorized=false`, `fit_attempt_authorized=false`, and
`sequence_fit_available=false`.
