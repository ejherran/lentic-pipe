# E0-MZE — ANFIS-ablation DVC registration reproducibility patch

## Purpose and boundary

E0-MZE is an additive governance overlay for the single reproducibility
failure in the published E0-MZD registration runtime.  R-E0-MZD completed all
eleven canonical `dvc add --no-relink` commands, staged its exact `10A+1M`
scope, and passed the registration-specific scientific audit.  The unchanged
generic manifest validator then compared a historically correct trainer
record in A0/seed 1729 with today's superseding trainer bytes and emitted
exactly two expected `FAIL` findings: byte count and SHA-256.

This patch changes no model, checkpoint, prediction, metric, report,
preprocessor, training curve, manifest, DVC target, command order, fit,
calibration, evaluation, E0-M, E0-U, or outcome boundary.  It does not rewrite
the historical manifest and it does not weaken, skip, or special-case the
generic validator.  It adds an R-only closed provenance adapter which first
validates all ten manifest-to-trainer Git records and may adopt only the exact
two known findings for the one historical record.

The blocked R-E0-MZD attempt is historical evidence, not successful
registration.  Its one-shot authorization was consumed.  No retry is allowed
until H-E0-MZE and P-E0-MZE are independently reviewed, published, and
effective, followed by a new explicit R authorization.

## Published base and exact incident

The validator reconstructs this linear history:

```text
21ea7cb6978d93e356fa50c963c739337cbfd2d6  H-E0-MZD, exact 8M+5A
    |
    +-- 33b84bc8aa7a9968947f4b670dbd0aae10fbfa74  P-E0-MZD, exact 2A
            |
            +-- H-E0-MZE, exact 9M+5A
```

The failed registration report is local forensic evidence at
`tmp/pre_commit_artifacts_20260810T111555Z.md`: 8,434 bytes and SHA-256
`3d530563699f6bb11bf7b7d47a59a1b5aa47e6236bc52bb3648a6a46f550f080`.
It records 11/11 successful DVC add commands, an exact staged registration
scope, a clean DVC status after staging, no DVC push, and a successful
registration-specific reproducibility finding.  The generic manifest section
contains the exact two-item `FAIL` multiset and no adopted warning:

- trainer bytes: manifest `107577`, current `112554`;
- trainer SHA-256: manifest
  `608786d9da2c263cbae5010dd19d6a6acc61df25d4c370c1e1312526693eca7e`,
  current
  `738bf8a5dd4fba09e4238d2b9a2f436081410e4ab998fc4b8b822ff9c402e0a9`.

Rollback restored all versionable state: zero prediction pointers, baseline
109-byte `models.dvc` with SHA-256
`fcb93f78cc3e60c1c7f5bcc94a1765080358e0a5176880f1efa6245fa5365e5d`,
a clean index, no transaction guard/backup/config namespace, and unchanged
family80.  The `models.dvc` bytes and owned inode were restored; local
mtime/ctime are forensic metadata and are not authority.  Local DVC cache may
contain objects or metadata touches from the completed add commands.  Cache
is never authority, absence is not required, and cleanup is not authorized.

## Closed ten-manifest provenance map

The ten manifests are ordered A0/A1 within each base seed `1729`, `20260612`,
`20260613`, `20260614`, and `314159`.  Each manifest must contain one trainer
`source_code` record whose script path is exactly
`src/experiments/train_closure_anfis_ablation.py`; the matching generic
`script` record must remain semantically identical.

Only `reports/closure_v1/02_models/A0/seed_1729_manifest.json` is historical.
Its trainer record is reconstructed from ancestor
`3fff3f272eb6f6ba8e644dd49436bc39ecbed1f8`, Git blob
`f80a80fe89538da3c87707496dfa828053f77d77`, mode `100644`, 107,577 bytes,
and SHA-256
`608786d9da2c263cbae5010dd19d6a6acc61df25d4c370c1e1312526693eca7e`.

The other nine manifests bind the current trainer record reconstructed from
ancestor `8b4452bdca930a7b1ac1a7094f0c2b36e7d5d559`, Git blob
`f76ad4990c2838632b5806a3dcf193c5d1177da5`, mode `100644`, 112,554 bytes,
and SHA-256
`738bf8a5dd4fba09e4238d2b9a2f436081410e4ab998fc4b8b822ff9c402e0a9`.

The mapping is exact and closed: ten unique canonical manifest paths, ten
unique slots in canonical order, one historical record and nine current
records.  Commit, ancestry, Git blob OID, mode, byte count, SHA-256, role,
script path, source-code equality, model id, base seed, path order, and exact
types are authority.  Missing, extra, duplicate, swapped, reordered,
non-ancestor, unavailable, boolean-as-integer, or otherwise drifted records
fail closed.

## Generic findings remain generic

The generic manifest validation entry point and its ordinary call sites remain
unchanged.  It still reports the historical A0/1729 current-worktree mismatch
as two `FAIL` findings.  The MZE adapter is reachable only from the exact
R-E0-MZE staged scope after the ten-record Git map is validated.

The adapter accepts exactly the unordered two-item multiset above, with exact
severity, manifest path, script path, field, historical value, current value,
and message dialect.  It removes neither arbitrary failures nor warnings.  A
missing finding, duplicate, third finding, altered path/value/message, any
warning, or any unrelated failure aborts registration.  On success it replaces
only that exact pair with one explicit `OK` provenance-adoption record.  The
original generic findings remain available as evidence; the adapter never
pretends that the generic validator itself passed.

The replacement record is exact: check
`anfis_ablation_manifest_provenance`, path
`reports/closure_v1/02_models/A0/seed_1729_manifest.json`, and message
`Validated exact one historical and nine current trainer Git blobs.`.  The H
authority, schema, and R helper must encode that same four-field finding.

## H/P/R topology and exact scopes

H-E0-MZE is the direct non-merge child of P-E0-MZD and has exact scope
`9M+5A`.

Modified paths:

```text
src/data/prepare_commit_artifacts.py
tests/test_closure_anfis_ablation_dvc_registration_patch.py
tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py
tests/test_closure_anfis_ablation_dvc_registration_order_patch.py
tests/test_closure_anfis_ablation_dvc_registration_namespace_patch.py
tests/test_closure_anfis_ablation_dvc_registration_gitignore_patch.py
tests/test_closure_anfis_ablation_dvc_registration_status_patch.py
tests/test_closure_anfis_ablation_model_publication_patch.py
tests/test_closure_anfis_ablation_model_publication_adoption_patch.py
```

Added paths:

```text
configs/closure_v1/anfis_ablation_dvc_registration_reproducibility_patch.schema.json
docs/closure_v1/ANFIS_ABLATION_DVC_REGISTRATION_REPRODUCIBILITY_PATCH.md
src/experiments/closure_anfis_ablation_dvc_registration_reproducibility_patch.py
src/experiments/lock_closure_anfis_ablation_dvc_registration_reproducibility_patch.py
tests/test_closure_anfis_ablation_dvc_registration_reproducibility_patch.py
```

P-E0-MZE is an atomic exact `2A` bundle:

```text
reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_reproducibility_patch_lock.json
reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_reproducibility_patch_lock_manifest.json
```

R-E0-MZE remains a separate exact `10A+1M` transaction: the ten canonical
selection-prediction `.parquet.dvc` pointers and modified `models.dvc`.
Discovery is an exact set; execution remains alternating A0/A1 within each
seed, with `models` eleventh and last.  H/P precommit defers `models` and runs
no DVC commands.  R uses its dedicated `--no-push` workflow.  DVC add, DVC
push, Git commit, and Git push remain separate authorization boundaries.

## Companion partition and historical authority

The future P-E0-MZE companion binds exactly 20 current physical inputs and 43
historical Git inputs.  Physical inputs are the two published P-E0-MZD JSON
authorities, four H-E0-MZD components preserved physically, and all fourteen
H-E0-MZE components.  Historical inputs are the 34 records inherited from
P-E0-MZD plus the nine H-E0-MZD blobs superseded by H-E0-MZE.  Family80 is
sealed in the lock and is not duplicated in companion inputs.  The companion
has exactly one output and is written last.

## Scientific, namespace, and cache invariants

The authority requires ten `completed` / `available` / `passed` slots and
exactly 80 regular single-link `0644` finals: 50 tracked lightweight files, 20
models/checkpoints, and ten selection-prediction Parquets.  At H and P, all
ten prediction pointers remain absent and baseline `models.dvc` remains the
only Git owner of `models/`.

The exact `/models` ignore entry remains present once, byte-for-byte and
Git-bound.  No registration guard, backup, anchor, temporary pointer,
isolated config directory, locker guard, or foreign namespace entry may exist
at H/P.  Foreign paths and cache objects are never rollback-owned.  No
training, replay, replacement, calibration, evaluation, E0-M, E0-U,
test/holdout access, post-2021 outcome access, or scientific network action is
authorized.

## Verification, publication, and runtime barriers

The non-writing H preflight is:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_dvc_registration_reproducibility_patch.py \
  --check-only
```

It validates schema first, exact topology/scopes/modes, P-E0-MZD, the 20/43
companion partition, the closed ten-manifest mapping, the exact two-finding
incident, inherited namespace/status/gitignore contracts, family80, baseline
`models.dvc`, runtime/configuration, cache non-authority, and absent P/R
coordination namespaces.  It performs no writes, DVC operation, model action,
outcome access, or scientific network action.

A separately authorized `--execute-lock` runs only the frozen read-only
verification commands and publishes canonical lock plus companion using
anchored no-follow/no-clobber writes, manifest last, exact owned-output
identity checks, repeated governance/Git/family snapshots, and best-effort
rollback of every owned output.  `--check-effective` is valid only after exact
P publication.  Public loaders expose no transaction-record argument; the
private R loader accepts only the active owned transaction record.

R uses repository `.venv/bin/dvc add --no-relink`, isolated DVC configuration,
sealed Git/Python/wrapper identities, and a closed environment.  Incoming
`GIT_*` including `GIT_PAGER`, `PYTHON*`, `LD_*`, and unsupported `DVC_*`
redirects are rejected or removed.  The immutable `.gitignore`, family80,
closed manifest map, and cache non-authority are revalidated across every
command.  `DVC push` is not part of registration.

Any failure before the commit-ready linearization point rolls back every
transaction-owned pointer, `models.dvc` bytes/inode ownership, exact partial
or autostaged index subset, temporary, guard, backup, anchor, and isolated
configuration node.  Foreign paths, family finals, `.gitignore`, and
`.dvc/cache` are never removed.  Registration remains false until exact R is
completed, separately committed, and published.

## Adversarial closure

E0-MZE fails closed for any map10 drift; any manifest/Git record type, path,
slot, order, role, commit, ancestor, blob OID, mode, byte, SHA-256, or
source-code drift; any missing, extra, duplicate, swapped, reordered, or
unavailable record; any generic finding multiset other than the exact two
known failures; any warning or third failure; any status, namespace, family,
Git, index, `.gitignore`, runtime, configuration, topology, history,
publisher, loader, transaction ownership, or rollback drift; cache treated as
authority; reordered canonical DVC commands; or any implicit DVC/network/
push/scientific permission.
