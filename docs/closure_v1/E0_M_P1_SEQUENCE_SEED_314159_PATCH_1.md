# E0-MN — P1 seed 314159 sequence authority

## Purpose

E0-MN is an additive, fail-closed overlay that authorizes exactly one future
Closure V1 sequence-builder invocation for `model_id=P1` and
`base_seed=314159`. It does not change the scientific sequence contract, the
state mapping, denominators, or seed order.

The authority follows the publication and audit of the completed P1/20260614
slot. It neither rewrites nor reactivates E0-ML or E0-MM: both are
reconstructed from their historical Git blobs and remain immutable.

## Closed topology

- H-E0-MN base:
  `46daf1e2dd97a3d7e36ad187d4ae1510dfc14fc2`.
- H-E0-MN must be its direct non-merge child and contain exactly `2M+5A`.
- The future P-E0-MN must be the direct child of H-E0-MN and add only
  lock+companion `2A`.
- Authorization does not become effective until P-E0-MN is published and its
  strict loader verifies aligned `HEAD`, `main`, `origin/main`, `origin/HEAD`,
  and live remote state.

## Historical authorities

The lock reconstructs the following authorities without invoking their
one-shot effective loaders:

- H/P-E0-ML: `b30bf68` / `fa18ac0`;
- H/P-E0-MM: `f6cd0bf` / `e216bf4`;
- P1/1729 sequence+consumer bundles remain intact;
- P1/20260612 sequence bundle: `b448e1f`;
- P1/20260612 consumer: `5b2c5d6`, exactly report+manifest with
  `model_unavailable/not_attempted/sequence_fit_rows_unavailable`;
- P1/20260613 sequence bundle: `a25863c`;
- P1/20260613 consumer: `fea057b`, exactly report+manifest with
  `model_unavailable/not_attempted/sequence_fit_rows_unavailable`;
- P1/20260614 sequence bundle: `9b40b2b`;
- P1/20260614 consumer: `46daf1e`, exactly report+manifest with
  `model_unavailable/not_attempted/sequence_fit_rows_unavailable`;
- P1/1729 consumer: `5d8bbef`, exactly report+manifest with
  `model_unavailable/not_attempted/sequence_fit_rows_unavailable`;
- ANFIS state for seed 314159: `45705d6`, 1,214,293 bytes with SHA-256
  `53e71211cf0f58f78bb473869dcac7e15b578c39d6722eba02954c13a86101f0`;
  its 116-byte pointer has SHA-256
  `1c91d9c32feb0fbafe427e1d1f8c9e6252cb37570e0ae819ba54f587a6d4c181`
  and its 20,821-byte manifest has SHA-256
  `dedcc82dd998499fa5f3f8049554431b1e97dcf6dff32645e7e6bf4e5240f2f4`.

E0-ML retains five physical components; only the builder and its test are
superseded by H-E0-MN. All seven H-E0-MM components and both published lock
bundles remain physically unchanged.

## Progression prelock

Before P-E0-MN can be created, all of these predicates must hold:

- P1/1729 contains exactly its six published artifacts: sequence, DVC pointer,
  summary, sequence manifest, consumer report, and consumer manifest;
- P1/20260612 also contains exactly those six artifact classes;
- P1/20260613 also contains exactly those six artifact classes;
- P1/20260614 also contains exactly those six artifact classes;
- the 88 residual registered paths for the four completed seeds are absent;
- all 28 registered P1/314159 paths are absent;
- there are no later P1 seed paths after the final 314159 slot;
- the registered P1 namespace is exactly 24 present and 116 absent paths;
- all four E0-M outputs are absent;
- `outcome_access_log.jsonl` is absent;
- no temporary files or guards exist for pending slots.

The gate runs immediately after argument parsing and before reading runtime,
manifests, states, or Parquets, before resolving outputs, and before creating
a guard.

## Future effective authorization

After P-E0-MN is published, the only newly true permission is:

```text
p1_sequence_builder_authorized=true
authorized_model_id=P1
authorized_base_seed=314159
authorization_effective=true
```

Batch, retry, consumer, fit, DVC, E0-M, evaluation, E0-U, and outcome access
remain false. A failed invocation consumes its operational authorization and
does not enable an implicit retry.

## Locker transaction

The locker is implemented but is not executed as part of H-E0-MN. It provides:

- mutually exclusive `--check-only`, `--execute-lock`, and `--check-effective`
  modes;
- a supported-schema preflight before guards, remote checks, or commands;
- closed paths and no-follow parent traversal;
- exclusive guards under `tmp/`;
- hardlink no-clobber publication;
- lock-first and companion manifest-last ordering;
- rollback limited to owned inodes;
- prelock revalidation before publication;
- a companion with exactly 34 physical inputs and two historical Git-blob
  inputs for the superseded E0-ML builder and test;
- no DVC commands and no outcome access.

## Out of scope

H-E0-MN does not execute the locker, build the sequence, register or push DVC,
consume the temporal model, open E0-M/E0-U, or read outcomes. Those actions
require later independent gates and authorizations.
