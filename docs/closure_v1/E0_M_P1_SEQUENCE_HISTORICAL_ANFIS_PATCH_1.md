# Closure V1 E0-MC P1 Historical ANFIS Patch 1

## Purpose

E0-MC is an additive, development-only recovery gate for the first P1
sequence slot. It does not change a scientific decision, a state mapping, a
denominator, or an ANFIS artifact. It authorizes one replacement attempt for
exactly `model_id=P1`, `base_seed=1729` after the first E0-MB authorization
was consumed by a fail-closed provenance incompatibility.

The E0-MB effective loader completed successfully. Sequence construction then
stopped while validating the frozen seed-1729 ANFIS manifest. The historical
E0-DLP consumer helper attempted to treat the current sequence builder as if
it still had its E0-DLP Git-at-H bytes and raised:

```text
DevelopmentRuntimePatchError: patched base component differs from Git-at-H:
src/experiments/build_closure_pipe_sequences.py
```

The builder exposed that exception as:

```text
ClosurePipeSequenceError: ANFIS historical dependency lacks valid published
E0-DLP authority
```

This is a provenance-representation conflict. The builder was intentionally
superseded by the published E0-DLS, E0-DLT, E0-DLTV, E0-DLTVM, and E0-MB
chain. The failure occurred before sequence publication. All 28 paths in the
P1 seed-1729 execution namespace, all 140 registered P1 paths, all E0-M
outputs, and the outcome-access log remained absent. No DVC command ran. The
first one-shot authorization is nevertheless consumed and is never reused.

## Fixed Topology and Scope

H-E0-MC must be a direct, non-merge child of the published P-E0-MB commit:

```text
34c0b4e3203eca32bee69732a823519f2b0e61eb
```

Its Git diff is exactly two modifications and five additions.

Modified:

- `src/experiments/build_closure_pipe_sequences.py`;
- `tests/test_build_closure_pipe_sequences.py`.

Added:

- `configs/closure_v1/p1_sequence_historical_anfis_patch_lock.schema.json`;
- `docs/closure_v1/E0_M_P1_SEQUENCE_HISTORICAL_ANFIS_PATCH_1.md`;
- `src/experiments/closure_p1_sequence_historical_anfis_patch.py`;
- `src/experiments/lock_closure_p1_sequence_historical_anfis_patch.py`;
- `tests/test_closure_p1_sequence_historical_anfis_patch.py`.

P-E0-MC must be the direct, non-merge child of H-E0-MC and add exactly two
regular mode-`100644` JSON files:

- `reports/closure_v1/00_protocol/p1_sequence_historical_anfis_patch_lock.json`;
- `reports/closure_v1/00_protocol/p1_sequence_historical_anfis_patch_lock_manifest.json`.

No later commit may touch those files while using P-E0-MC as an effective
authority.

## Historical Authority

E0-MC preserves P-E0-MB as an immutable historical authority. It reconstructs
its H/P topology, canonical lock and companion, Git records, and the nested
E0-DLS -> E0-DLT -> E0-DLTV -> E0-DLTVM chain. That reconstruction proves the
published E0-DLP adoption of the frozen ANFIS seed-1729 bundle without calling
the obsolete effective E0-DLP loader against current builder bytes.

The compatibility adapter accepts only the exact frozen seed-1729 manifest,
including its byte count, SHA-256, historical generating-script record,
historical strict-adapter record, historical runtime-validator record, and
uppercase artifact paths. It rejects another seed, a similar manifest, a
duplicate historical record, a changed artifact, or a current-path fallback.

E0-DLP, E0-DLS, E0-DLT, E0-DLTV, E0-DLTVM, E0-MA, and E0-MB artifacts remain
unchanged. Historical records for superseded paths belong in the companion's
`historical_inputs[]`; they are never compared to current physical bytes by a
generic manifest consumer.

## Authorizations and Seals

The lock payload and companion contain only false execution flags. They cannot
self-authorize. Before publication they require:

```text
p1_sequence_retry_authorized=false
effective_in_payload=false
publication_required=true
prior_one_shot_authorization_consumed=true
```

Only the effective loader at the exact published P-E0-MC commit may return:

```text
p1_sequence_retry_authorized=true
authorized_model_id=P1
authorized_base_seed=1729
publication_required=false
```

The following remain false in the payload, unpublished loader, effective
loader, effective preflight, and sequence output:

```text
batch_seed_execution_authorized
p1_fit_authorized
e0_m_authorized
evaluation_authorized
e0_u_authorized
future_outcomes_accessed
```

E0-MC does not authorize another P1 seed, a batch, training, calibration,
evaluation, E0-M, E0-U, holdout access, or post-2021 outcome access.

## Closed Verification Set

The future `--execute-lock` runs this fixed command family:

```text
.venv/bin/ty check
.venv/bin/pytest tests/test_closure_p1_sequence_historical_anfis_patch.py tests/test_closure_p1_sequence_builder_patch.py tests/test_build_closure_pipe_sequences.py -q
poetry check
scripts/check_repo_publication_ready.sh
git diff --check
```

The exact focused-test count is 116 and is fixed in source and schema. The
accepted pytest summary contains exactly that number of passes as its final
non-empty line and contains no warning, skip, deselection, xfail, xpass,
error, or failure term.

The verification set contains no DVC, cloud, experiment, evaluation, or
outcome command.

## Lock Transaction

The locker reserves both final names through independent exclusive guards in:

```text
tmp/closure_v1_e0_mc_locker
```

It holds both guards during prelock collection, verification, repeated
authority collection, serialization, publication, and unpublished
validation. The transaction:

1. rejects any final, temporary, guard, symlink, or broken-symlink collision;
2. uses repository-anchored, no-follow parent walks;
3. creates exclusive regular temporary inodes;
4. publishes by hard link without overwriting an existing name;
5. writes the lock first and the companion completion marker last;
6. synchronizes parent directories;
7. verifies output ownership and rehashes owned bytes;
8. validates the unpublished canonical bundle and all closed namespaces;
9. releases each guard only after verifying its owned inode;
10. rolls back owned finals in reverse order on any failure.

Rollback removes only the inodes created by the transaction. A foreign
replacement is preserved. Losing or replacing a guard during cleanup converts
an otherwise successful transaction into a fail-closed rollback. Tests that
exercise nested locker behavior use an isolated ignored temporary namespace
and never reacquire the live production guards.

## Three Separately Authorized CLI Modes

### Prelock check

After H-E0-MC is published, a separately authorized read-only check runs:

```bash
poetry run python \
  src/experiments/lock_closure_p1_sequence_historical_anfis_patch.py \
  --check-only
```

It verifies H topology, the live Git remote, historical authorities, the
frozen ANFIS manifest, and the pristine P1/E0-M/outcome namespaces. It writes
nothing and runs no verification, DVC, or outcome command.

### Lock execution

`--execute-lock` is a different authorization:

```bash
poetry run python \
  src/experiments/lock_closure_p1_sequence_historical_anfis_patch.py \
  --execute-lock
```

It runs the closed verification set and may publish only the two untracked
JSON files through the lock transaction. It returns
`locked_unpublished`; retry authorization remains false until publication.

Precommit without push is another authorization. It may stage exactly the two
P-E0-MC additions and must report DVC `{}`, no DVC add, no cloud status, no
DVC push, successful publication/manifest/freeze checks, and no warning or
`FAIL`. The user then publishes exactly P-E0-MC `2A`.

### Effective preflight

After publication, a separately authorized read-only preflight runs:

```bash
poetry run python \
  src/experiments/lock_closure_p1_sequence_historical_anfis_patch.py \
  --check-effective
```

Unlike `--check-only`, this mode requires the two final lock files and rejects
their temporaries or guards. It verifies exact P topology, `main`, local refs,
the live remote, a clean tree, canonical bundle bytes, historical authorities,
the frozen manifest, and the pristine execution namespace. It writes no file,
runs no DVC or outcome command, and does not consume the replacement one-shot
authorization.

## Replacement One-Shot

Only after `--check-effective` passes may the user separately authorize one
replacement invocation:

```bash
poetry run python src/experiments/build_closure_pipe_sequences.py \
  --model-id P1 \
  --base-seed 1729
```

That authorization is consumed even if execution fails. A further attempt is
forbidden without a new side-effect audit and a new locked authorization. On
success, the sequence Parquet, summary CSV, and manifest JSON are audited
before any DVC action. DVC registration, DVC push, precommit, Git publication,
consumer hardening, and P1 fit remain separate later gates.
