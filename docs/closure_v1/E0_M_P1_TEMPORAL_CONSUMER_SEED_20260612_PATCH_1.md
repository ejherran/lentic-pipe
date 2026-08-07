# E0-MI — P1 seed 20260612 temporal-consumer authority

## Purpose

E0-MI is an additive, fail-closed authority for exactly one future temporal
consumer invocation: `model_id=P1`, `base_seed=20260612`, `device=cpu`. It is
the ordered successor to the published P1/20260612 sequence bundle. It does
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

- H-E0-MI base: `b448e1fb0ee75b6135da11f0ea9a8877d89e0ee1`.
- H-E0-MI must be its direct non-merge child and contain exactly `2M+5A`.
- The modified paths are only the temporal trainer and its test module.
- The five additions are this document, schema, validator, locker, and focused
  patch test.
- Future P-E0-MI must be the direct child of H-E0-MI and add only lock plus
  companion manifest.
- Authorization is ineffective until P-E0-MI is published and its strict
  loader verifies local refs and live `origin/main`.

## Historical authorities

The validator reconstructs, but never calls the effective loaders of:

- H/P-E0-MG at `fb0280f` / `730cd7d`;
- H/P-E0-MH at `16662cd` / `f8a1589`.

For E0-MG, the trainer and trainer test are explicitly superseded Git blobs;
its other five components remain physically identical. All seven E0-MH
components remain physically identical. The two published lock bundles are
verified against their introducing commits, exact two-addition topology, and
current bytes. This avoids reactivating the seed-1729 consumer or the already
consumed seed-20260612 builder authority.

## Published sequence evidence

E0-MI binds the `b448e1f` publication and its immutable physical payload:

- Parquet: 1,379,747 bytes, SHA-256
  `7c12fe31cece86ecc6a67d86337159a55757bec21b60f7a45d6911e8487a8f6b`;
- DVC pointer: 104 bytes, SHA-256
  `e219bf384487f5f063afbb1933dd4315a99553fe5c6b230a6544588759b2c4c7`;
- summary: 356 bytes, SHA-256
  `a6c6c837a82c13a9321233de03b588c60b7a4198b77dcf31b3c7a62027752c3e`;
- manifest: 6,541 bytes, SHA-256
  `617b1acc27b90c90229c07fc7a91009e2d978d28d3f26a2c6d513e74cba87003`;
- read-only auditor source and its focused test as introduced by the same
  exact five-addition commit.

The auditor is only bound statically during H-E0-MI. It is reserved for the
future authorized lock execution because it reconstructs the sequence builder
in process even though it never calls the builder CLI or writes outputs.

## Progression and namespace

At lock time the following must hold simultaneously:

- P1/1729 retains exactly sequence, pointer, summary, sequence manifest,
  unavailable report, and unavailable model manifest;
- the other 22 registered P1/1729 paths are absent;
- P1/20260612 retains exactly sequence, pointer, summary, and sequence manifest;
- all 19 consumer final/temp/guard paths for P1/20260612 are absent;
- all five P1/20260612 sequence temporary/guard paths are absent;
- all 84 registered paths for the three later seeds are absent;
- all four E0-M paths and the outcome-access log are absent.

The prelock compares the complete 140-path registered P1 universe against the
exact ten-path present set; it does not infer closure from only the required
files.

The gate runs immediately after argument parsing and before seed validation,
path resolution, guards, Parquet/schema reads, runtime setup, or output I/O.
The trainer must use the seed-20260612 pointer, auditor, and E0-MH lock inputs;
the historical seed-1729 pointer and E0-MC input dialect are not valid for this
slot.

## Transaction and future lock

The existing trainer transaction remains authoritative: exclusive slot guard,
no-follow parent checks, temporary regular files, hardlink no-clobber,
report-first/manifest-last publication, and rollback only of owned inodes.

The locker is implemented by H-E0-MI but is not executed by that change. A
future separately authorized execution may run full `ty`, the closed focused
suite, lightweight repository checks, the auditor in-process, and two targeted
DVC pushes for `seed_20260612.parquet.dvc`; the second push must be idempotent.
It may then publish locally only lock plus companion. Check-only performs none
of those commands, audits, writes, DVC operations, or outcome access.

## Explicit non-authorizations

H-E0-MI itself does not execute the locker, builder, consumer, auditor, DVC,
E0-M, E0-U, evaluation, holdout/test reads, or outcomes. The eventual effective
authority permits only the one consumer invocation and still records
`p1_fit_authorized=false`, `fit_attempt_authorized=false`, and
`sequence_fit_available=false`.
