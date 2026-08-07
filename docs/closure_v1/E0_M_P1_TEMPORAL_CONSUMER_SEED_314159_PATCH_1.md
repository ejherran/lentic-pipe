# E0-MO — P1 seed 314159 temporal-consumer authority

## Purpose

E0-MO is an additive, fail-closed authority for exactly one future temporal
consumer invocation: `model_id=P1`, `base_seed=314159`, `device=cpu`. It is
the ordered successor to the published P1/314159 sequence bundle. It does
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

- H-E0-MO base: `2d69cc82f2611aaebef245bbffd38b4fed0c82a9`.
- H-E0-MO must be its direct non-merge child and contain exactly `2M+5A`.
- The modified paths are only the temporal trainer and its test module.
- The five additions are this document, schema, validator, locker, and focused
  patch test.
- Future P-E0-MO must be the direct child of H-E0-MO and add only lock plus
  companion manifest.
- Authorization is ineffective until P-E0-MO is published and its strict
  loader verifies local refs and live `origin/main`.

## Historical authorities

The validator reconstructs, but never calls the effective loaders of:

- H/P-E0-MM at `f6cd0bf` / `e216bf4`;
- H/P-E0-MN at `99ac7af` / `7f3a4e1`.

For E0-MM, the trainer and trainer test are explicitly superseded Git blobs;
its other five components remain physically identical. All seven E0-MN
components remain physically identical. The two published lock bundles are
verified against their introducing commits, exact two-addition topology, and
current bytes. This avoids reactivating the seed-1729 consumer or the already
consumed seed-314159 builder authority.

## Published sequence evidence

E0-MO binds the `2d69cc8` publication and its immutable physical payload:

- Parquet: 1,380,649 bytes, SHA-256
  `c156afcd96c27a20619948fd90962f1d8f688a18d20aadb1d5ec313bbc3afbba`;
- DVC pointer: 102 bytes, SHA-256
  `308c0d9e3ace6cd5cebca850463a1d038e0aec467d1d3c1a28e8efd520293348`;
- summary: 356 bytes, SHA-256
  `a6c6c837a82c13a9321233de03b588c60b7a4198b77dcf31b3c7a62027752c3e`;
- manifest: 6,528 bytes, SHA-256
  `72a04d7edc024b1070164c11e3ab1e34cdd0ceb6edab369c9b7f57eff3af92c6`;
- read-only auditor source: 79,444 bytes, SHA-256
  `2260af70b584ab8b48db087d7425211916ffb573292f93a019c98a995867c4db`;
- auditor test: 28,741 bytes, SHA-256
  `b842f5de592c2d33e78c35c0ccd3c809c09d064c397d13aeb6314b70b14559d6`.

The auditor is only bound statically during H-E0-MO. It is reserved for the
future authorized lock execution because it reconstructs the sequence builder
in process even though it never calls the builder CLI or writes outputs.

## Progression and namespace

At lock time the following must hold simultaneously:

- P1/1729 retains exactly sequence, pointer, summary, sequence manifest,
  unavailable report, and unavailable model manifest;
- P1/20260612 retains the same complete six-record sequence-plus-consumer slot;
- P1/20260613 retains the same complete six-record sequence-plus-consumer slot;
- P1/20260614 retains the same complete six-record sequence-plus-consumer slot;
- the other 88 registered paths across the four completed prior seeds are
  absent;
- P1/314159 retains exactly sequence, pointer, summary, and sequence manifest;
- all 19 consumer final/temp/guard paths for P1/314159 are absent;
- all five P1/314159 sequence temporary/guard paths are absent;
- no later registered seed namespace remains;
- all four E0-M paths and the outcome-access log are absent.

The prelock compares the complete 140-path registered P1 universe against the
exact 28-path present set; it does not infer closure from only the required
files.

The gate runs immediately after argument parsing and before seed validation,
path resolution, guards, Parquet/schema reads, runtime setup, or output I/O.
The trainer must use the seed-314159 pointer, auditor, and E0-MN lock inputs;
the historical seed-1729 pointer and E0-MC input dialect are not valid for this
slot.

## Transaction and future lock

The existing trainer transaction remains authoritative: exclusive slot guard,
no-follow parent checks, temporary regular files, hardlink no-clobber,
report-first/manifest-last publication, and rollback only of owned inodes.

The locker is implemented by H-E0-MO but is not executed by that change. A
future separately authorized execution may run full `ty`, the closed focused
suite, lightweight repository checks, the auditor in-process, and two targeted
DVC pushes for `seed_314159.parquet.dvc`; the second push must be idempotent.
It may then publish locally only lock plus companion. The companion contains
24 physical inputs and the two superseded H-E0-MM trainer/test Git blobs as
historical inputs. Check-only performs none of those commands, audits, writes,
DVC operations, or outcome access.

## Explicit non-authorizations

H-E0-MO itself does not execute the locker, builder, consumer, auditor, DVC,
E0-M, E0-U, evaluation, holdout/test reads, or outcomes. The eventual effective
authority permits only the one consumer invocation and still records
`p1_fit_authorized=false`, `fit_attempt_authorized=false`, and
`sequence_fit_available=false`.
