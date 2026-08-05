# Closure V1 E0-MB P1 Sequence-Builder Patch 1

## Purpose

E0-MB is an additive, development-only gate between the published P0 model
availability registry and the first P1 sequence build. It fixes two execution
risks without changing the scientific sequence contract:

1. the sequence builder previously validated E0-DLTVM but did not enforce the
   published E0-MA registry in its own process;
2. Parquet, summary, and manifest were individually no-clobber but were not a
   rollback-capable bundle.

E0-MB authorizes exactly `model_id=P1`, `base_seed=1729`, and sequence
materialization. It does not authorize P1 fitting, another seed, batch seed
execution, calibration, E0-M, evaluation, E0-U, holdout access, or post-2021
outcome access.

## Additive Topology

The H-E0-MB commit must be a direct non-merge child of the published E0-MA
registry commit:

```text
9851211 E0-MA registry (historical authority)
  -> H-E0-MB exact 2M+5A
    -> P-E0-MB exact lock+companion 2A
```

H-E0-MB modifies only the sequence builder and its existing test file. It adds
this protocol, the lock schema, validator, locker, and focused validator tests.
The two modified DLTVM paths are recorded as superseded historical components;
the other nine H-DLTVM components must remain byte-identical.

P-E0-MB adds only:

- `reports/closure_v1/00_protocol/p1_sequence_builder_patch_lock.json`;
- `reports/closure_v1/00_protocol/p1_sequence_builder_patch_lock_manifest.json`.

The lock payload and companion both record
`p1_sequence_builder_authorized=false`, `effective_in_payload=false`, and
`publication_required=true`; neither can self-authorize. The effective loader
has no unpublished or no-remote mode. It requires the exact P commit, branch
`main`, a clean worktree and index, lock and companion bytes equal to their Git
blobs and canonical JSON, aligned `HEAD`, `main`, `origin/main`, and
`origin/HEAD`, plus the same live remote main commit.

## Historical Authorities

The original E0-MA loader deliberately requires `HEAD` at its exact registry
commit, and the E0-DLTVM loader deliberately requires its historical builder
bytes. Neither condition can hold after a legitimate builder hardening commit.
E0-MB therefore reconstructs both authorities rather than weakening either
loader.

For E0-MA it verifies:

- the immutable H five-addition commit and registry two-addition commit;
- canonical registry and companion bytes bound to their Git blobs;
- the five terminal P0 slots and fixed per-slot denominator;
- registry reconstruction against the closed physical policy;
- P1 fit, E0-M, evaluation, E0-U, and future outcomes remain false.

For E0-DLTVM it verifies:

- the immutable H and P commits and exact lock/companion bytes;
- the original schema, fixed lock fields, verification evidence, and companion;
- P0, H-DLTV, and H-DLTVM builder provenance from their historical Git blobs;
- two superseded builder/test records and nine physically preserved components.

Historical P1 absence is reconstructed as registry-time evidence. Current P1
absence is a separate physical predicate checked immediately before the build.
The historical E0-MB loader remains non-authorizing and reconstructs the two
superseded H components from their Git blobs, so later hardening does not erase
this evidence.

## Current Namespace

Before seed 1729 is authorized, E0-MB requires all 140 registered P1 paths for
the five fixed seeds to be absent, along with every E0-M output and the outcome
access log. The seed-1729 execution namespace contains 28 paths:

- sequence Parquet, CSV summary, JSON manifest;
- their temporary paths, DVC pointer and pointer temporary, and exclusive
  sequence-builder guard;
- the 19 downstream P1 temporal-consumer final, temporary, and guard paths.

Broken symlinks count as present. The builder repeats its own nine-path
preflight while holding the exclusive seed guard.

## Bundle Transaction

The hardened builder retains the existing fixed schema, mappings, canonical
order, compression, counts, and manifest dialect. Only publication behavior
changes.

The transaction:

1. holds ownership of every final inode until bundle commit;
2. creates each temporary as an exclusive regular inode under a no-follow,
   repository-anchored parent walk;
3. publishes through a hard link that cannot overwrite an existing final;
4. writes Parquet, then summary, then the manifest completion marker last;
5. verifies DVC-pointer absence at preflight, before the manifest, after the
   manifest, and both before and after output rehash/dependency validation at
   transaction commit;
6. releases and validates the exclusive slot guard before committing outputs;
7. rehashes every owned final, including the manifest, and revalidates all
   inode and parent identities before commit;
8. revalidates every dependency, including both E0-MB authority files, after
   serialization and before commit;
9. on a controlled failure, rolls back owned inodes in reverse order and
   synchronizes their parent directories;
10. never removes a foreign replacement.

The sequence manifest includes the exact E0-MB lock and companion as ordinary
three-field input records (`path`, `bytes`, `sha256`). Their roles are checked
by the gate but omitted from sequence-manifest inputs to preserve the closed
consumer dialect.

The currently published temporal consumer does not yet collect these two
E0-MB records and still binds the older DLTVM builder authority. Therefore the
new sequence bundle is intentionally not fit-consumer compatible yet. This
lock keeps `p1_fit_authorized=false`; a later, separately locked consumer
hardening must adopt both authority inputs and the H-E0-MB builder before any
P1 fit can run.

The repeated pointer checks close the controlled workflow, in which DVC
registration begins only after the builder exits and its bundle is audited.
They cannot make an unrelated process that ignores the slot guard mutually
exclusive; such an uncoordinated writer remains forbidden operationally.

No multi-directory userspace protocol can make a `SIGKILL` or power loss
between distinct directory operations fully atomic. Such a partial remains
fail-closed because the manifest is the last completion marker and the next
preflight rejects every residual final or temporary for explicit review.

## Lock Workflow

After publishing H-E0-MB, the following command is a separately authorized,
read-only preflight. It performs live Git remote verification but no DVC or
outcome commands and writes no files:

```bash
poetry run python src/experiments/lock_closure_p1_sequence_builder_patch.py \
  --check-only
```

`--execute-lock` is a different authorization. It runs the closed full type
check, focused test set, package check, publication guard, and diff check. It
then publishes only the lock and companion through two exclusive guards,
lock first and companion last, with owned-inode rollback. It does not run DVC
commands or open outcome paths.

The companion keeps current physical files in `inputs[]` and the two
superseded H-DLTVM builder/test records in `historical_inputs[]`; generic
precommit validation must never compare those historical records against the
current paths.

After `--execute-lock` passes, precommit is another explicit authorization and
must run without push. It may stage exactly the two new JSON files and must not
run DVC add, cloud status, DVC push, or any outcome command. Publication is
allowed only after that precommit report passes without warnings or `FAIL` and
the staged diff is exactly 2A. Guard loss or replacement during locker cleanup
fails closed and rolls back owned lock outputs while preserving a foreign
replacement.

After auditing and publishing the exact two-addition P bundle, the effective
loader—not the payload—is allowed to return:

```text
p1_sequence_builder_authorized=true
authorized_model_id=P1
authorized_base_seed=1729
p1_fit_authorized=false
e0_m_authorized=false
evaluation_authorized=false
e0_u_authorized=false
future_outcomes_accessed=false
```

Only then may a separately authorized one-shot invocation run:

```bash
poetry run python src/experiments/build_closure_pipe_sequences.py \
  --model-id P1 \
  --base-seed 1729
```

The resulting three-file sequence bundle must be audited, registered in DVC,
pushed, and published before any P1 trainer or later seed is considered.
