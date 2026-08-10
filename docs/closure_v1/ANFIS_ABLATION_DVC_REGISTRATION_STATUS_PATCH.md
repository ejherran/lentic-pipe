# E0-MZD — ANFIS-ablation DVC registration status-order patch

## Purpose and boundary

E0-MZD is an additive governance overlay for one deterministic failure in the
published E0-MZC registration runtime.  The scientific ANFIS-ablation family
was complete and unchanged, P-E0-MZC was effective, and all eleven canonical
`dvc add --no-relink` commands ran.  The transaction then rejected its own
valid final Git status because it compared the raw line order emitted by Git
with a globally path-sorted list.

This patch changes no model, checkpoint, prediction, metric, report,
preprocessor, training curve, manifest, DVC target, target order, fit,
calibration, evaluation, E0-M, E0-U, or outcome boundary.  It only makes the
closed status-scope validators insensitive to record order while remaining
strict about the exact status-to-path mapping and every malformed record.

The blocked R-E0-MZC attempt is historical evidence, not successful
registration.  Its one-shot authorization was consumed.  No retry is allowed
until H-E0-MZD and P-E0-MZD are separately reviewed, published, and effective,
followed by a new explicit R authorization.

## Published base and exact incident

The validator reconstructs this linear history:

```text
15478da7ecc8ae1baf064744b57d984cbaad6a28  H-E0-MZC, exact 8M+5A
    |
    +-- 3e1d319cb909c89eabdc1a1429294cef12ac481c  P-E0-MZC, exact 2A
            |
            +-- H-E0-MZD, exact 8M+5A
```

At the final in-progress check, the valid porcelain-v1 short status was
grouped by Git with the tracked modification first:

```text
 M models.dvc
?? data/closure_v1/development/anfis_ablation/A0/seed_1729_selection_predictions.parquet.dvc
?? data/closure_v1/development/anfis_ablation/A0/seed_20260612_selection_predictions.parquet.dvc
?? data/closure_v1/development/anfis_ablation/A0/seed_20260613_selection_predictions.parquet.dvc
?? data/closure_v1/development/anfis_ablation/A0/seed_20260614_selection_predictions.parquet.dvc
?? data/closure_v1/development/anfis_ablation/A0/seed_314159_selection_predictions.parquet.dvc
?? data/closure_v1/development/anfis_ablation/A1/seed_1729_selection_predictions.parquet.dvc
?? data/closure_v1/development/anfis_ablation/A1/seed_20260612_selection_predictions.parquet.dvc
?? data/closure_v1/development/anfis_ablation/A1/seed_20260613_selection_predictions.parquet.dvc
?? data/closure_v1/development/anfis_ablation/A1/seed_20260614_selection_predictions.parquet.dvc
?? data/closure_v1/development/anfis_ablation/A1/seed_314159_selection_predictions.parquet.dvc
```

The helper instead globally sorted the combined expected mapping, placing the
ten `data/...` records before `models.dvc`.  Both sequences represented the
same exact mapping, but raw `splitlines()` equality failed with
`registration progress scope drifted`.  A synthetic Git repository reproduces
the tracked-first/untracked-second grouping without DVC.

The first ten progress checks had only the canonical untracked pointer prefix
and therefore passed.  The eleventh models command completed before the
mismatch.  Forensic evidence is consistent and closed: `models.dvc` returned
to its 109-byte baseline, SHA-256
`fcb93f78cc3e60c1c7f5bcc94a1765080358e0a5176880f1efa6245fa5365e5d`,
Git blob `906e884546d8e2316a95b5e0a1378150639ed36e`, mode `0644`, one link,
and the same local inode `76416708`; its restoration changed local
mtime/ctime to `1786321073687619570`.  The expected models cache tree object
remained MD5 `6b8d7c0a8efcd8de2888d684a0cb285b`, SHA-256
`5d84e2efabbacb8ea06bd5abd3c44bc1e7affb46999ceb94266c0b52067ec1b1`,
mode `0444`, one link, and local inode `76683934`; its ctime changed to
`1786321073212611189` while content and mtime remained unchanged.

Rollback removed all ten owned pointers, index entries, guards, independent
bytes backup, hardlink anchor, temporary files, and isolated config
directories.  Git status and index are clean.  `.gitignore` remains the exact
6,630-byte adopted postimage with SHA-256
`406c174a073b9b41d610e1c434e94f4ab37b601dedd02b61cb8542bcc0eb7f52`,
Git blob `8a9ff4adac268b770f93ab7333beaf3029745429`, mode `0644`, and one
link.  Family80 remains byte- and identity-exact with records digest
`e625add8f8af1746f7deda9ff13a84a4d4f4c27b47e3b6312922db419508dd8e`.

## Exact porcelain mapping contract

Git porcelain record order is not authority.  Each validation boundary parses
the complete output into a closed mapping and compares that mapping exactly:

- progress `N=0..10`: the first `N` canonical pointers map to `??`;
- `models.dvc` may map to ` M` only at the final `N=10` models boundary;
- final pre-stage scope is exactly ten pointer `??` records plus
  `models.dvc -> " M"`;
- final staged scope is exactly ten pointer `A ` records plus
  `models.dvc -> "M "` and must match the exact `10A+1M` index;
- the canonical DVC command order remains alternating A0/A1 within each seed,
  with `models` eleventh and last; status discovery never selects commands.

The parser fails closed before mapping comparison.  Every non-empty record
must have an exact two-character status, one separator, and one non-empty
canonical path.  A duplicate path, conflicting duplicate, missing or extra
path, wrong status, rename, copy, deletion, unmerged state, ignored state,
quoted/composite rename record, short line, missing separator, empty path, or
trailing malformed record is rejected.  Reordering otherwise exact records is
accepted.  Malformed lines are never skipped.

The progress validator additionally requires the active owned guard, immutable
`.gitignore`, exact pointer-prefix ownership and identities, family80, and the
sealed `models.dvc` phase.  The pre-stage and staged validators preserve their
existing physical mode, single-link, index-stage-zero, and index-OID equals
worktree-OID checks.

## H/P/R topology and exact scopes

H-E0-MZD is the direct non-merge child of P-E0-MZC and has exact scope
`8M+5A`.

Modified paths:

```text
src/data/prepare_commit_artifacts.py
tests/test_closure_anfis_ablation_dvc_registration_gitignore_patch.py
tests/test_closure_anfis_ablation_dvc_registration_namespace_patch.py
tests/test_closure_anfis_ablation_dvc_registration_order_patch.py
tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py
tests/test_closure_anfis_ablation_dvc_registration_patch.py
tests/test_closure_anfis_ablation_model_publication_adoption_patch.py
tests/test_closure_anfis_ablation_model_publication_patch.py
```

Added paths:

```text
configs/closure_v1/anfis_ablation_dvc_registration_status_patch.schema.json
docs/closure_v1/ANFIS_ABLATION_DVC_REGISTRATION_STATUS_PATCH.md
src/experiments/closure_anfis_ablation_dvc_registration_status_patch.py
src/experiments/lock_closure_anfis_ablation_dvc_registration_status_patch.py
tests/test_closure_anfis_ablation_dvc_registration_status_patch.py
```

P-E0-MZD is an atomic exact `2A` bundle:

```text
reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_status_patch_lock.json
reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_status_patch_lock_manifest.json
```

R-E0-MZD remains a distinct exact `10A+1M` transaction: the ten canonical
selection-prediction `.parquet.dvc` pointers and modified `models.dvc`.
H/P precommit defers `models`; R uses its dedicated `--no-push` workflow.
DVC add, DVC push, Git commit, and Git push remain separate authorization
boundaries.

## Companion partition and historical authority

The future P-E0-MZD companion binds exactly 20 current physical inputs and 34
historical Git inputs.  Physical inputs are the two published P-E0-MZC JSON
authorities, the H-E0-MZC components preserved physically, and all thirteen
H-E0-MZD components.  Historical inputs are the 26 records inherited from
P-E0-MZC plus the eight H-E0-MZC blobs superseded by H-E0-MZD.  Family80 is
sealed in the lock and is not duplicated in companion inputs.  The companion
has exactly one output and is written last.

## Scientific, cache, and namespace invariants

The authority requires ten `completed` / `available` / `passed` slots and
exactly 80 regular single-link `0644` finals: 50 tracked lightweight files, 20
models/checkpoints, and ten selection-prediction Parquets.  At H and P, all
ten prediction pointers remain absent and baseline `models.dvc` remains the
only Git owner of `models/`.

Local `.dvc/cache` is forensic residue, never authority.  The ten prediction
objects, expected 268-entry models tree, and its 20 added model/checkpoint
objects may remain and may exhibit DVC metadata touches.  E0-MZD neither
deletes, stages, publishes, nor requires absence of local cache objects.  Cache
content cannot substitute for a pointer, `models.dvc`, family final, P lock,
or successful R report.

No registration guard, backup, anchor, temporary pointer, isolated config
directory, locker guard, or foreign namespace entry may exist at H/P.  No
training, replay, replacement, calibration, evaluation, E0-M, E0-U,
test/holdout access, post-2021 outcome access, or scientific network action is
authorized.

## Verification and publication gates

The non-writing H preflight is:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_dvc_registration_status_patch.py \
  --check-only
```

It validates schema first, exact topology/scopes/modes, P-E0-MZC, the 20/34
companion partition, the incident and porcelain mapping policy, family80,
baseline `models.dvc`, `.gitignore`, runtime/configuration, cache
non-authority, and absent P/R/coordination namespaces.  It performs no writes,
verification command, DVC operation, model action, outcome access, or network
action.

A separately authorized `--execute-lock` runs only the frozen read-only
verification commands and publishes canonical lock plus companion with
anchored no-follow/no-clobber writes, manifest last, exact owned-output
identity checks, repeated governance/Git/family snapshots, and best-effort
rollback of every owned output.  `--check-effective` is valid only after exact
P publication.  Public loaders expose no transaction-record argument; the
private R loader accepts only the active owned transaction record.

R uses repository `.venv/bin/dvc add --no-relink`, isolated DVC configuration,
sealed Git/Python/wrapper identities, and a closed environment.  Incoming
`GIT_*` (including `GIT_PAGER`), `PYTHON*`, `LD_*`, and unsupported `DVC_*`
redirects are rejected or removed.  The immutable `.gitignore`, family80, and
cache non-authority are revalidated across every command.

Any failure before the commit-ready linearization point rolls back every
transaction-owned pointer, `models.dvc` bytes/inode ownership, exact partial
or autostaged index subset, temporary, guard, backup, anchor, and isolated
configuration node.  Foreign paths, family finals, `.gitignore`, and
`.dvc/cache` are never removed.  Registration remains false until exact R is
completed, separately committed, and published.

## Adversarial closure

E0-MZD fails closed for missing, extra, duplicated, malformed, renamed,
deleted, copied, unmerged, wrong-status, wrong-phase, or foreign porcelain
records; noncanonical pointer prefixes; models appearing before the final
phase; reordered DVC commands; family, Git, index, `.gitignore`, runtime,
configuration, topology, history, publisher, loader, transaction ownership,
or rollback drift; cache treated as authority; or any implicit DVC/network/
push/scientific permission.  It accepts only order permutations of one exact
phase-specific status mapping.
