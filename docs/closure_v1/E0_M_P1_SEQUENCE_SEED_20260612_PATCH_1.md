# E0-MH — P1 seed 20260612 sequence authority

## Purpose

E0-MH is an additive, fail-closed overlay that authorizes exactly one future
Closure V1 sequence-builder invocation for `model_id=P1` and
`base_seed=20260612`. It does not change the scientific sequence contract, the
state mapping, denominators, or seed order.

The authority follows the publication and audit of the completed P1/1729
slot. It neither rewrites nor reactivates E0-MC or E0-MG: both are
reconstructed from their historical Git blobs and remain immutable.

## Closed topology

- H-E0-MH base:
  `5d8bbef0fe58e57cd2180570bd6aef5f07923781`.
- H-E0-MH must be its direct non-merge child and contain exactly `2M+5A`.
- The future P-E0-MH must be the direct child of H-E0-MH and add only
  lock+companion `2A`.
- Authorization does not become effective until P-E0-MH is published and its
  strict loader verifies aligned `HEAD`, `main`, `origin/main`, `origin/HEAD`,
  and live remote state.

## Historical authorities

The lock reconstructs the following authorities without invoking their
one-shot effective loaders:

- H/P-E0-MC: `5bdac0f` / `d76f35b`;
- P1/1729 sequence bundle: `82c0bc1`;
- H/P-E0-MG: `fb0280f` / `730cd7d`;
- P1/1729 consumer: `5d8bbef`, exactly report+manifest with
  `model_unavailable/not_attempted/sequence_fit_rows_unavailable`;
- ANFIS state for seed 20260612: `b16b27d`, 1,214,885 bytes with SHA-256
  `99b4bc37de88d76068c044423071046cb6b0341056024c4de41cd1af51d09d26`.

E0-MC retains five physical components; only the builder and its test are
superseded by H-E0-MH. All seven H-E0-MG components and both published lock
bundles remain physically unchanged.

## Progression prelock

Before P-E0-MH can be created, all of these predicates must hold:

- P1/1729 contains exactly its six published artifacts: sequence, DVC pointer,
  summary, sequence manifest, consumer report, and consumer manifest;
- its other 22 registered paths are absent;
- all 28 registered P1/20260612 paths are absent;
- all 84 paths for P1/20260613, P1/20260614, and P1/314159 are absent;
- all four E0-M outputs are absent;
- `outcome_access_log.jsonl` is absent;
- no temporary files or guards exist for pending slots.

The gate runs immediately after argument parsing and before reading runtime,
manifests, states, or Parquets, before resolving outputs, and before creating
a guard.

## Future effective authorization

After P-E0-MH is published, the only newly true permission is:

```text
p1_sequence_builder_authorized=true
authorized_model_id=P1
authorized_base_seed=20260612
authorization_effective=true
```

Batch, retry, consumer, fit, DVC, E0-M, evaluation, E0-U, and outcome access
remain false. A failed invocation consumes its operational authorization and
does not enable an implicit retry.

## Locker transaction

The locker is implemented but is not executed as part of H-E0-MH. It provides:

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

H-E0-MH does not execute the locker, build the sequence, register or push DVC,
consume the temporal model, open E0-M/E0-U, or read outcomes. Those actions
require later independent gates and authorizations.
