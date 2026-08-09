# E0-MZB — ANFIS-ablation DVC registration namespace patch

## Purpose

E0-MZB is an additive governance overlay over published P-E0-MZA commit
`b1f346f7191349901635fa7fa52807ea7031c39c`. It repairs one fail-closed
namespace defect observed during the first R-E0-MZA DVC target. The first
canonical `dvc add --no-relink` created its pointer, and the subsequent family
audit rejected the otherwise valid prefix because its exact-tree comparison
still admitted only the ten prediction payloads.

The R transaction rolled back every repository-owned effect: all ten pointers
are absent, `models.dvc` has its published baseline bytes, the Git index is
clean, and all guards, backups, anchors, temporary files, and isolated DVC
configuration directories are absent. The immutable payload family is intact.
The one DVC cache object left by the completed command is local DVC-owned
cache, is not authority, is not required to be absent, and is deliberately
outside rollback ownership.

E0-MZB changes no scientific result and authorizes neither registration nor
push. It distinguishes the valid in-progress transaction namespace from the
closed public namespace without weakening either one.

## Published authority and recorded incident

The validator reconstructs this exact direct-parent chain:

```text
4265b0a958761e7dabc410957932828c771b8e4c  H-E0-MZA, exact 5M+5A
    |
    +-- b1f346f7191349901635fa7fa52807ea7031c39c  P-E0-MZA, exact 2A
            |
            +-- H-E0-MZB, exact 6M+5A
```

The incident record seals exactly one attempted and completed target, its
payload and pointer, failure with pointer count one during post-add family
namespace validation, complete rollback to pointer count zero, the published
`models.dvc` SHA-256, the exact family80 digest, a clean index, and no DVC
push. Local cache presence or absence cannot satisfy or invalidate authority.

## Exact namespace contract

The prediction root always contains the exact ten immutable selection
prediction payloads. During the private guarded R transaction, after exactly
`N` successful prediction-target commands, it may additionally contain only
the first `N` pointer paths in the canonical interleaved order:

```text
A0/1729, A1/1729,
A0/20260612, A1/20260612,
A0/20260613, A1/20260613,
A0/20260614, A1/20260614,
A0/314159, A1/314159
```

For `N=0..10`, the exact tree is therefore ten payloads plus the canonical
pointer prefix of length `N`. Each present pointer must have canonical bytes,
mode `0644`, link count one, and its expected payload relationship. A missing
prefix member, an out-of-prefix or extra entry, a payload hole, symlink at any
walk component, hardlink, noncanonical mode, or metadata/payload drift is
fatal.

The public family snapshot accepts only the stable endpoints `N=0` and
`N=10`. Counts `1..9` are accepted only by the private in-progress path with
the active, owned registration transaction. Counts and policy flags are exact
types; booleans are never integers. This exception is not available to a
public caller and cannot be used to bless an arbitrary partial namespace.

Discovery remains an exact set of ten unique missing payloads. Lexical
discovery order is accepted as observation only; execution remains derived
from the canonical interleaved constant, with `models` eleventh and last.

## Scientific state preserved

The authority still seals ten `completed` / `available` / `passed` slots.
It contains exactly 80 regular single-link `0644` finals, 50 tracked lightweight files, 20
model/checkpoint files, and ten selection-prediction Parquets. The exact
family-record digest is
`e625add8f8af1746f7deda9ff13a84a4d4f4c27b47e3b6312922db419508dd8e`.
The restored baseline `models.dvc` SHA-256 is
`fcb93f78cc3e60c1c7f5bcc94a1765080358e0a5176880f1efa6245fa5365e5d`.

Calibration targets, test/holdout data, post-2021 outcomes, E0-M, and E0-U
remain outside this authority. Cache existence is not scientific evidence.

## H/P/R topology and exact scopes

H-E0-MZB is the direct non-merge child of P-E0-MZA and has exact scope
`6M+5A`.

Modified paths:

```text
src/data/prepare_commit_artifacts.py
tests/test_closure_anfis_ablation_dvc_registration_patch.py
tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py
tests/test_closure_anfis_ablation_dvc_registration_order_patch.py
tests/test_closure_anfis_ablation_model_publication_adoption_patch.py
tests/test_closure_anfis_ablation_model_publication_patch.py
```

Added paths:

```text
configs/closure_v1/anfis_ablation_dvc_registration_namespace_patch_lock.schema.json
docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_NAMESPACE_PATCH_1.md
src/experiments/closure_anfis_ablation_dvc_registration_namespace_patch.py
src/experiments/lock_closure_anfis_ablation_dvc_registration_namespace_patch.py
tests/test_closure_anfis_ablation_dvc_registration_namespace_patch.py
```

The helper remains Git mode `100755`; every other H component is `100644`.
P-E0-MZB adds only lock and companion as regular, single-link canonical JSON
files with mode `100644`:

```text
reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_namespace_patch_lock.json
reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_namespace_patch_lock_manifest.json
```

Only published P-E0-MZB may authorize R-E0-MZB. Its exact Git scope is
`10A+1M`: ten added
prediction `.parquet.dvc` pointers and one modified `models.dvc`. The canonical
target order is the ten interleaved prediction payloads followed by `models`.
H/P precommit defers `models`; R is a separate `--no-push` workflow.

## Companion partition

The P-E0-MZB companion binds exactly 17 current physical inputs and 19
historical Git inputs. Current physical inputs are the two P-E0-MZA authority
files, four H-E0-MZA components preserved physically, and all eleven H-E0-MZB
components. Historical inputs are the 13 records inherited from P-E0-MZA plus
the six H-E0-MZA blobs superseded by H-E0-MZB. Historical blobs are rebuilt
from their exact commits and are never substituted by current worktree bytes.
Family80 is sealed in the lock rather than duplicated in companion inputs.

## Gates

The schema-first, non-writing H preflight is:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_dvc_registration_namespace_patch.py \
  --check-only
```

It verifies topology, exact scopes and modes, P-E0-MZA, the 17/19 companion
partition, family80, baseline `models.dvc`, inventories, the namespace repair,
runtime/config contracts, and absent P/R/temporary coordination. It performs
no verification command, write, DVC operation, fit, audit, or scientific
network access.

Separately authorized lock publication uses `--execute-lock`. It runs only the
frozen read-only verification commands, then creates lock and companion with
no-follow/no-clobber publication, companion last, and best-effort rollback of
every transaction-owned output. `--check-effective` is valid only after exact
P publication. Public loaders accept no caller transaction record; the private
R loader accepts only the active owned record and revalidates authority before
linearization.

## Registration and rollback boundary

R uses only repository `.venv/bin/dvc add --no-relink`, isolated configuration,
canonical runtime identities, and a closed environment. `GIT_PAGER`, all other
incoming `GIT_*`, `PYTHON*`, `LD_*`, and unsupported `DVC_*` redirects are
rejected or removed. Each successful target is followed by the exact private
prefix audit. Final family, pointer, `models.dvc`, Git scope/index, report, and
authority checks remain mandatory before the `commit_ready` linearization
marker.

Any pre-linearization failure rolls back all transaction-owned pointers,
`models.dvc` bytes/inode state, exact partial or autostaged index subset,
temporaries, guards, backups, anchors, and isolated config nodes. Rollback is
best-effort across every owned node and never touches foreign replacements,
pre-existing paths, payload finals, or `.dvc/cache`. Cache bytes do not count
as completion, authority, or a recoverable repository mutation.

The eleven DVC adds, later DVC push, Git commit, and Git push remain separate
authorization boundaries. H/P/R never imply DVC push.

## Adversarial closure

E0-MZB fails closed for any malformed count or policy type; missing, duplicate,
extra, holed, renamed, or non-prefix namespace member; symlink, hardlink, mode,
payload, inode, or transient metadata drift; cache treated as authority; scope,
index, topology, history, publisher, loader, runtime, environment, or config
drift; incomplete rollback; caller-forged coordination; training, calibration,
evaluation, future-outcome access; or any implicit DVC/network/push permission.

E0-MZB repairs only the in-progress exact-tree contract. Registration remains
false until separately authorized exact R completes, is committed, and is
published.
