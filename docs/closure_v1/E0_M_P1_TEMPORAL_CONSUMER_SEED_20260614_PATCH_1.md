# E0-MM — P1 seed 20260614 temporal-consumer authority

## Purpose

E0-MM is an additive, fail-closed authority for exactly one future temporal
consumer invocation: `model_id=P1`, `base_seed=20260614`, `device=cpu`. It is
the ordered successor to the published P1/20260614 sequence bundle. It does
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

- H-E0-MM base: `9b40b2bea49084aab1ba37a1a5e4b87261a83fae`.
- H-E0-MM must be its direct non-merge child and contain exactly `2M+5A`.
- The modified paths are only the temporal trainer and its test module.
- The five additions are this document, schema, validator, locker, and focused
  patch test.
- Future P-E0-MM must be the direct child of H-E0-MM and add only lock plus
  companion manifest.
- Authorization is ineffective until P-E0-MM is published and its strict
  loader verifies local refs and live `origin/main`.

## Historical authorities

The validator reconstructs, but never calls the effective loaders of:

- H/P-E0-MK at `a718808` / `780c30f`;
- H/P-E0-ML at `b30bf68` / `fa18ac0`.

For E0-MK, the trainer and trainer test are explicitly superseded Git blobs;
its other five components remain physically identical. All seven E0-ML
components remain physically identical. The two published lock bundles are
verified against their introducing commits, exact two-addition topology, and
current bytes. This avoids reactivating the seed-1729 consumer or the already
consumed seed-20260614 builder authority.

## Published sequence evidence

E0-MM binds the `9b40b2b` publication and its immutable physical payload:

- Parquet: 1,380,317 bytes, SHA-256
  `4227d4e956303d16873401b1b52ab2a480dc6c1276eaff883d15d10b2a9d81cb`;
- DVC pointer: 104 bytes, SHA-256
  `29c8bdc33a97e399c84986c6b00a2d957ede94957f3d1a619529cf1f54db8ec2`;
- summary: 356 bytes, SHA-256
  `a6c6c837a82c13a9321233de03b588c60b7a4198b77dcf31b3c7a62027752c3e`;
- manifest: 6,541 bytes, SHA-256
  `e297f0d97b81c7d02bcee39dcb15f760620d3e62990313aba9c7589234ab277a`;
- read-only auditor source: 76,575 bytes, SHA-256
  `c76f79d8443d1a28462f90a383f33a6a8bb5301490b2b23681593a81c647a48b`;
- auditor test: 28,168 bytes, SHA-256
  `5a3ac249299ef560728fd407f09ae0df13325b0e4cca4459cf1d0059551304f2`.

The auditor is only bound statically during H-E0-MM. It is reserved for the
future authorized lock execution because it reconstructs the sequence builder
in process even though it never calls the builder CLI or writes outputs.

## Progression and namespace

At lock time the following must hold simultaneously:

- P1/1729 retains exactly sequence, pointer, summary, sequence manifest,
  unavailable report, and unavailable model manifest;
- P1/20260612 retains the same complete six-record sequence-plus-consumer slot;
- P1/20260613 retains the same complete six-record sequence-plus-consumer slot;
- the other 66 registered paths across the three completed prior seeds are
  absent;
- P1/20260614 retains exactly sequence, pointer, summary, and sequence manifest;
- all 19 consumer final/temp/guard paths for P1/20260614 are absent;
- all five P1/20260614 sequence temporary/guard paths are absent;
- all 28 registered paths for the later seed 314159 are absent;
- all four E0-M paths and the outcome-access log are absent.

The prelock compares the complete 140-path registered P1 universe against the
exact 22-path present set; it does not infer closure from only the required
files.

The gate runs immediately after argument parsing and before seed validation,
path resolution, guards, Parquet/schema reads, runtime setup, or output I/O.
The trainer must use the seed-20260614 pointer, auditor, and E0-ML lock inputs;
the historical seed-1729 pointer and E0-MC input dialect are not valid for this
slot.

## Transaction and future lock

The existing trainer transaction remains authoritative: exclusive slot guard,
no-follow parent checks, temporary regular files, hardlink no-clobber,
report-first/manifest-last publication, and rollback only of owned inodes.

The locker is implemented by H-E0-MM but is not executed by that change. A
future separately authorized execution may run full `ty`, the closed focused
suite, lightweight repository checks, the auditor in-process, and two targeted
DVC pushes for `seed_20260614.parquet.dvc`; the second push must be idempotent.
It may then publish locally only lock plus companion. The companion contains
24 physical inputs and the two superseded H-E0-MK trainer/test Git blobs as
historical inputs. Check-only performs none of those commands, audits, writes,
DVC operations, or outcome access.

## Explicit non-authorizations

H-E0-MM itself does not execute the locker, builder, consumer, auditor, DVC,
E0-M, E0-U, evaluation, holdout/test reads, or outcomes. The eventual effective
authority permits only the one consumer invocation and still records
`p1_fit_authorized=false`, `fit_attempt_authorized=false`, and
`sequence_fit_available=false`.
