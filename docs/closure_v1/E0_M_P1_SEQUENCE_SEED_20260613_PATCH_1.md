# E0-MJ — P1 seed 20260613 sequence authority

## Purpose

E0-MJ is an additive, fail-closed overlay that authorizes exactly one future
Closure V1 sequence-builder invocation for `model_id=P1` and
`base_seed=20260613`. It does not change the scientific sequence contract, the
state mapping, denominators, or seed order.

The authority follows the publication and audit of the completed P1/20260612
slot. It neither rewrites nor reactivates E0-MH or E0-MI: both are
reconstructed from their historical Git blobs and remain immutable.

## Closed topology

- H-E0-MJ base:
  `5b2c5d6b4f4c296c9485d1cb22561086aeeb6b85`.
- H-E0-MJ must be its direct non-merge child and contain exactly `2M+5A`.
- The future P-E0-MJ must be the direct child of H-E0-MJ and add only
  lock+companion `2A`.
- Authorization does not become effective until P-E0-MJ is published and its
  strict loader verifies aligned `HEAD`, `main`, `origin/main`, `origin/HEAD`,
  and live remote state.

## Historical authorities

The lock reconstructs the following authorities without invoking their
one-shot effective loaders:

- H/P-E0-MH: `16662cd` / `f8a1589`;
- H/P-E0-MI: `e8efbf8` / `16ee69f`;
- P1/1729 sequence+consumer bundles remain intact;
- P1/20260612 sequence bundle: `b448e1f`;
- P1/20260612 consumer: `5b2c5d6`, exactly report+manifest with
  `model_unavailable/not_attempted/sequence_fit_rows_unavailable`;
- P1/1729 consumer: `5d8bbef`, exactly report+manifest with
  `model_unavailable/not_attempted/sequence_fit_rows_unavailable`;
- ANFIS state for seed 20260613: `f197780`, 1,215,359 bytes with SHA-256
  `53f9a733e660d1968f8cf45916b1947ffa902346c16fabe2f07df9d27c4618a2`.

E0-MH retains five physical components; only the builder and its test are
superseded by H-E0-MJ. All seven H-E0-MI components and both published lock
bundles remain physically unchanged.

## Progression prelock

Before P-E0-MJ can be created, all of these predicates must hold:

- P1/1729 contains exactly its six published artifacts: sequence, DVC pointer,
  summary, sequence manifest, consumer report, and consumer manifest;
- P1/20260612 also contains exactly those six artifact classes;
- the 44 residual registered paths for both completed seeds are absent;
- all 28 registered P1/20260613 paths are absent;
- all 56 paths for P1/20260614 and P1/314159 are absent;
- the registered P1 namespace is exactly 12 present and 128 absent paths;
- all four E0-M outputs are absent;
- `outcome_access_log.jsonl` is absent;
- no temporary files or guards exist for pending slots.

The gate runs immediately after argument parsing and before reading runtime,
manifests, states, or Parquets, before resolving outputs, and before creating
a guard.

## Future effective authorization

After P-E0-MJ is published, the only newly true permission is:

```text
p1_sequence_builder_authorized=true
authorized_model_id=P1
authorized_base_seed=20260613
authorization_effective=true
```

Batch, retry, consumer, fit, DVC, E0-M, evaluation, E0-U, and outcome access
remain false. A failed invocation consumes its operational authorization and
does not enable an implicit retry.

## Locker transaction

The locker is implemented but is not executed as part of H-E0-MJ. It provides:

- mutually exclusive `--check-only`, `--execute-lock`, and `--check-effective`
  modes;
- a supported-schema preflight before guards, remote checks, or commands;
- closed paths and no-follow parent traversal;
- exclusive guards under `tmp/`;
- hardlink no-clobber publication;
- lock-first and companion manifest-last ordering;
- rollback limited to owned inodes;
- prelock revalidation before publication;
- no DVC commands and no outcome access.

## Out of scope

H-E0-MJ does not execute the locker, build the sequence, register or push DVC,
consume the temporal model, open E0-M/E0-U, or read outcomes. Those actions
require later independent gates and authorizations.
