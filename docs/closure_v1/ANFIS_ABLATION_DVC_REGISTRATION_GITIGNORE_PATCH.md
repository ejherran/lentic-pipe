# E0-MZC — ANFIS-ablation DVC registration `.gitignore` patch

## Purpose

E0-MZC is an additive governance overlay over published P-E0-MZB commit
`d202dead382fb42f9388e2a280240eaf59030ced`. It records and repairs the
fail-closed R-E0-MZB incident in which all eleven canonical
`dvc add --no-relink` commands ran, but the final `models` command appended
the exact root-anchored line `/models` to `.gitignore`. The R transaction owned
only ten prediction pointers plus `models.dvc`; its final Git-scope check
therefore rejected the unowned `.gitignore` modification and returned
`registration rollback could not be completed safely`.

Rollback removed all ten pointers, restored the 109-byte baseline
`models.dvc`, returned the Git index to its clean baseline, and removed every
owned guard, backup, anchor, temporary file, and isolated DVC configuration
directory. It deliberately did not remove the foreign `.gitignore` mutation
or local DVC cache objects. The exact family of 80 scientific finals remained
physically unchanged.

E0-MZC adopts that single deterministic line as policy. It changes no
scientific result, does not declare the failed registration complete, and
authorizes neither DVC add, DVC push, Git commit, nor Git push. R remains
blocked until H-E0-MZC and P-E0-MZC are separately published and a new
one-shot authorization is granted.

## Published base and incident evidence

The validator reconstructs this exact history:

```text
233e9d4b89f8bcc58742c0d95c51ea2ec3e5049d  H-E0-MZB, exact 6M+5A
    |
    +-- d202dead382fb42f9388e2a280240eaf59030ced  P-E0-MZB, exact 2A
            |
            +-- H-E0-MZC, exact 8M+5A
```

The incident record distinguishes repository rollback from cache residue. It
seals eleven attempted DVC-add commands, ten completed prediction targets,
ten pointers present immediately before the final models-scope check, the
`models` target executed eleventh, and failure during post-add Git-scope
validation. Final repository evidence is: pointer count zero; baseline
`models.dvc` SHA-256
`fcb93f78cc3e60c1c7f5bcc94a1765080358e0a5176880f1efa6245fa5365e5d`;
clean Git index; absent transaction coordination; unchanged family digest
`e625add8f8af1746f7deda9ff13a84a4d4f4c27b47e3b6312922db419508dd8e`;
and exactly one worktree delta, `.gitignore`.

The `.gitignore` preimage is reconstructed from P-E0-MZB, not trusted from
the worktree: 6,622 bytes, Git blob
`04f1ec817111eb3bc617c5392380fcaa7f449d3d`, and SHA-256
`6deac139b03970cb324989e4f5879a051f557d976acc5e21387177043e31faaf`.
The adopted postimage is exactly that byte string followed by `/models\n`:
6,630 bytes, Git blob `8a9ff4adac268b770f93ab7333beaf3029745429`, and
SHA-256 `406c174a073b9b41d610e1c434e94f4ab37b601dedd02b61cb8542bcc0eb7f52`.

## Exact `.gitignore` contract

The adopted file is one regular, single-link `0644` file. Its bytes, Git
mode, Git blob, SHA-256, length, device/inode identity, and mtime/ctime are
read and bound from stable descriptors at each authority boundary. The
postimage has exactly one whole line equal to `/models`, terminated by LF,
with no CR, trailing whitespace, duplicate, escaped variant, or later
negation. It is the final effective rule for the root `models` directory.

This ordering is intentional. The installed `scmrepo` implementation checks
`is_ignored(path)` before it opens or appends to `.gitignore`. With the exact
final `/models` rule, `models` is already ignored and the method returns
without touching bytes, inode, link count, mode, mtime, or ctime. The helper
still revalidates the exact postimage and its full physical identity before
and after every DVC command, so a duplicate append, reorder, in-place write,
atomic replacement, hardlink, symlink, metadata-only touch, or concurrent
Git mutation fails closed.

The final rule supersedes the older allow-list block for descendants under
`models/`. This is safe only because the published contract has no Git-tracked
descendant of `models/`: the directory is the single DVC output represented
by root-level `models.dvc`. `models.dvc` itself is not ignored. Adding a
nested Git file or nested `.dvc` pointer, adding a later `!` rule, changing the
target spelling, or changing this ownership model requires a new overlay; it
must not be smuggled into R.

## Cache is forensic residue, not authority

The failed run populated local `.dvc/cache` while processing the ten
prediction payloads and `models`. Nine prediction objects were new during the
incident, one prediction object pre-existed, and the expected models tree
object plus its model/checkpoint objects were created before rollback.
Those objects are reproducible evidence that commands ran, but they are not repository state, scientific evidence, completion evidence, or authority.
They are outside transaction ownership, need not be absent, are never staged,
and must never substitute for pointers, `models.dvc`, family bytes, a
published P lock, or a successful R report. E0-MZC neither deletes nor
publishes cache content.

## H/P/R topology and exact scopes

H-E0-MZC is the direct non-merge child of P-E0-MZB and has exact scope
`8M+5A`.

Modified paths:

```text
.gitignore
src/data/prepare_commit_artifacts.py
tests/test_closure_anfis_ablation_dvc_registration_patch.py
tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py
tests/test_closure_anfis_ablation_dvc_registration_order_patch.py
tests/test_closure_anfis_ablation_dvc_registration_namespace_patch.py
tests/test_closure_anfis_ablation_model_publication_patch.py
tests/test_closure_anfis_ablation_model_publication_adoption_patch.py
```

Added paths:

```text
configs/closure_v1/anfis_ablation_dvc_registration_gitignore_patch.schema.json
docs/closure_v1/ANFIS_ABLATION_DVC_REGISTRATION_GITIGNORE_PATCH.md
src/experiments/closure_anfis_ablation_dvc_registration_gitignore_patch.py
src/experiments/lock_closure_anfis_ablation_dvc_registration_gitignore_patch.py
tests/test_closure_anfis_ablation_dvc_registration_gitignore_patch.py
```

The helper remains Git mode `100755`; all other H components are `100644`.
P-E0-MZC adds exactly two regular, single-link canonical JSON files with Git
mode `100644`, lock first and companion manifest last:

```text
reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_gitignore_patch_lock.json
reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_gitignore_patch_lock_manifest.json
```

Only published P-E0-MZC may authorize R-E0-MZC. R retains the exact
`10A+1M` Git scope: ten added selection-prediction `.parquet.dvc` pointers
plus modified `models.dvc`. The canonical execution order is interleaved
A0/A1 within each of the five seeds, followed by `models` eleventh and last.
The selected target list derives from the sealed canonical constant, never
from lexical discovery order. H/P precommit defers `models`; R is a separate
`--no-push` workflow.

## Companion partition

The future P-E0-MZC companion binds exactly 19 current physical inputs and 26
historical Git inputs. Current physical inputs are the two P-E0-MZB authority
files, four H-E0-MZB components preserved physically, and all thirteen
H-E0-MZC components. Historical inputs are the 19 records inherited from
P-E0-MZB plus the seven H-E0-MZB blobs superseded by H-E0-MZC. The
`.gitignore` preimage is sealed inside the incident correction and therefore
does not add a twenty-seventh historical companion input. Family80 remains
sealed in the lock rather than duplicated in companion inputs.

## Scientific and namespace state preserved

The authority still requires ten `completed` / `available` / `passed` slots
and exactly 80 regular single-link `0644` finals: 50 tracked lightweight files,
20 model/checkpoint files, and ten selection-prediction Parquets. At H
and P, all ten prediction pointers are absent and baseline `models.dvc`
remains unchanged. No registration guard, bytes backup, hardlink anchor,
temporary pointer, isolated config directory, locker guard, or foreign entry
may occupy its namespace.

Calibration targets, test/holdout data, post-2021 outcomes, E0-M, and E0-U
remain outside this authority. No training, replay, replacement, calibration,
evaluation, or outcome access is authorized.

## Gates and transactional boundary

The schema-first, non-writing H preflight is:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_dvc_registration_gitignore_patch.py \
  --check-only
```

It verifies topology, exact scopes and modes, P-E0-MZB, the 19/26 companion
partition, exact `.gitignore` preimage/postimage and no-touch behavior,
family80, baseline `models.dvc`, inventory, runtime/config contracts, cache
non-authority, and absent P/R/coordination namespaces. It performs no write,
verification command, DVC operation, fit, audit, or scientific network access.

Separately authorized `--execute-lock` runs only the frozen read-only
verification commands, then publishes lock plus companion with anchored
no-follow/no-clobber writes, canonical JSON, manifest last, repeated
governance/Git/family snapshots, exact owned-output byte/metadata checks, and
best-effort rollback of every owned output. `--check-effective` succeeds only
after exact P publication. Public loaders expose no transaction-record
argument; the private R loader accepts only the active owned record and
revalidates guard, coordination, P authority, `.gitignore`, family, Git, and
configuration state before linearization.

R uses only repository `.venv/bin/dvc add --no-relink`, the canonical eleven
targets, isolated configuration, sealed runtime identities, and a closed
environment. `GIT_PAGER`, every other incoming `GIT_*`, `PYTHON*`, `LD_*`,
and unsupported `DVC_*` redirects are rejected or removed. The adopted
`.gitignore` is immutable governance input during R, not transaction-owned
output. Any byte or identity drift aborts before the next command.

Any pre-linearization failure rolls back every transaction-owned pointer,
`models.dvc` byte/inode state, exact partial or autostaged index subset,
temporaries, guards, backups, anchors, and isolated config nodes. It never
touches foreign replacements, family finals, the adopted `.gitignore`, or
`.dvc/cache`. A rollback is reported complete only when exact initial scope,
including the immutable adopted `.gitignore`, is restored. The eleven DVC
adds, a later DVC push, Git commit, and Git push remain separate authorization
boundaries.

## Adversarial closure

E0-MZC fails closed for incorrect `.gitignore` bytes, OID, count, order,
newline, mode, link count, identity, timestamp, or effective Git-ignore
source; a duplicate or later negation; tracked descendants under `models/`;
DVC-induced metadata touch; malformed incident counts or types; cache treated
as authority; pointer prefix, payload, family80, `models.dvc`, scope, index,
topology, history, publisher, loader, runtime, environment, configuration, or
rollback drift; caller-forged coordination; training or future-outcome access;
or any implicit DVC/network/push permission.

E0-MZC repairs only the deterministic Git-ignore prerequisite. Registration
remains false until a separately authorized exact R completes, is committed,
and is published.
