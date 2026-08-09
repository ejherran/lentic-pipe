# E0-MX: ANFIS-ablation model publication adoption patch 1

## Purpose and scientific boundary

E0-MX is an additive, implementation-only overlay over the published
lightweight A0 report commit
`5b24549f2d4791f6500e661f9ee404c0dc7a0866`. That commit is the direct child
of published H-E0-MW
`68107147c1a67c30ecfa64c862dd39531e574a9a` and adds exactly the five
pre-existing A0/1729 lightweight reports without changing their bytes.

E0-MX adopts that Git publication without treating it as a new fit, a replay,
or a scientific result. It changes no split, target, denominator,
preprocessing statistic, architecture, optimizer, seed, epoch, selection
rule, model output, or ordered-slot policy. The immutable A0/1729 one-shot
must never be rerun, rewritten, normalized, moved, touched, or replaced.
Calibration, evaluation, E0-M, E0-U, holdout and post-2020 target access,
outcome access, DVC registration, batch slot execution, and scientific network
egress remain closed.

## Why P-E0-MW is superseded

H-E0-MW required its five lightweight A0 files to remain untracked while its
future P commit was the direct child of H-E0-MW. Commit `5b24549` instead made
those exact five files tracked and became the child of H-E0-MW. The files are
valid and byte-exact, but live P-E0-MW topology and status predicates can no
longer pass. No P-E0-MW lock or companion exists, and neither path may be
generated, published, retried, or treated as authority on the new history.

E0-MX reconstructs both published commits and makes the tracked state
explicit. H-E0-MW remains immutable historical Git authority. The five report
blobs at `5b24549` are independently bound to publication commit, HEAD, index,
and worktree. The three heavyweight A0 finals remain outside Git.

## Exact lightweight publication

Commit `5b24549` has the single parent `6810714` and exactly five `100644`
additions:

| Path | Git blob | SHA-256 |
| --- | --- | --- |
| `reports/closure_v1/02_models/A0/seed_1729_manifest.json` | `9d554bc0b560b2a4e817f2eb8d07ef48424dd51a` | `406bf44de3ecdc49ff3d5797cbca1ec0c11ebfbdc70ba262130b85a2e58e31e2` |
| `reports/closure_v1/02_models/A0/seed_1729_preprocessor.json` | `b59088160da3c8d36efb984260f021959d52dddb` | `ebffd11d392c62e68e2afbd3ee05febfd05a7411fc83ca18563c7773a51faa62` |
| `reports/closure_v1/02_models/A0/seed_1729_report.md` | `740ef989b27bcbb44c22b81d4d90f9722d8f55b3` | `6e12b1d2fc0a1fce8baf7c1f81edbeb1bdd3d013d4365d606d21cc20399d123e` |
| `reports/closure_v1/02_models/A0/seed_1729_selection_metrics.csv` | `90ee68a227fd02d5554b6a256f8bde6927ec36a6` | `f6444a2047d2032334580f1322c4f61637a9028fd0aab27815a6c7386cf860eb` |
| `reports/closure_v1/02_models/A0/seed_1729_training_curve.csv` | `6b0a676116a34a41d36956696ba945c9632abecd` | `edfb193302b0fe21708e1ff1556dcdcdf817948a8bd35cef2f90b16be9cc0ec0` |

The other three exact finals remain the two ignored model files and the
ignored selection-predictions Parquet. All eight retain mode `0644`, one hard
link, exact byte counts and SHA-256 values, manifest-last physical ordering,
and absent temporary, guard, and DVC-pointer paths.

## H/P topology and exact scope

H-E0-MX must be the direct, non-merge child of `5b24549`. Its exact scope is
`6M+5A`.

Exactly these six paths are modified:

```text
src/data/prepare_commit_artifacts.py
src/experiments/audit_closure_anfis_ablation_model_bundle.py
src/experiments/train_closure_anfis_ablation.py
tests/test_audit_closure_anfis_ablation_model_bundle.py
tests/test_closure_anfis_ablation_model_publication_patch.py
tests/test_train_closure_anfis_ablation.py
```

Exactly these five paths are added:

```text
configs/closure_v1/anfis_ablation_model_publication_adoption_patch_lock.schema.json
docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_PUBLICATION_ADOPTION_PATCH_1.md
src/experiments/closure_anfis_ablation_model_publication_adoption_patch.py
src/experiments/lock_closure_anfis_ablation_model_publication_adoption_patch.py
tests/test_closure_anfis_ablation_model_publication_adoption_patch.py
```

The helper remains Git mode `100755`; the other ten H components are
`100644`. P-E0-MX must be the direct, non-merge child of H-E0-MX and add only
these two `100644` JSON files:

```text
reports/closure_v1/00_protocol/anfis_ablation_model_publication_adoption_patch_lock.json
reports/closure_v1/00_protocol/anfis_ablation_model_publication_adoption_patch_lock_manifest.json
```

The lock basename deliberately does not contain `manifest`. Therefore the
generic artifact assistant classifies the lock as one staged report and only
the completed companion as an experiment manifest. P precommit must report
exactly one manifest, one covered output, and one staged report: `1/1/1`.

## Historical reconstruction and companion dialect

The helper preserves the published H/P-E0-MV and H/P-E0-MW scope and mode maps
only for read-only reconstruction. Its sole live mutating boundary admits
exact H/P-E0-MX scopes. Historical MV or MW scopes fail closed in a real
repository before DVC inspection or Git staging.

The P-E0-MX companion is maximal and exact:

- `87` unique current physical `inputs`;
- `11` Git-bound `historical_inputs` for superseded published components;
- the current E0-MX locker exactly once as top-level `script` and in `inputs`;
- the E0-MX lock as the sole `outputs` record.

All historical records are reconstructed from their named Git commits. No
blocked P-E0-MV file, absent P-E0-MW file, ignored local incident archive, or
future slot is an authority or fresh-clone dependency.

## Slot authority and progression

Before exact P-E0-MX publication, every build, audit, DVC, calibration,
evaluation, E0-M, E0-U, and outcome authorization remains false. An
unpublished lock is never effective.

After publication, the target-aware loader may authorize only:

- read-only audit of adopted A0/1729 against its historical E0-MU scientific
  authority and exact `5b24549` Git bindings;
- construction of the next ordered slot, A1/1729, through published P-E0-MX
  and the H-E0-MX trainer record.

A0 replay or replacement remains forbidden. DVC registration remains closed
until all ten A0/A1 slots are complete.

## Gates

The schema-first, non-writing preflight is:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_model_publication_adoption_patch.py \
  --check-only
```

It validates the live H-E0-MX topology, H-E0-MW and `5b24549`
reconstruction, the `87+11` companion topology, the adopted A0 bundle, empty
future namespaces, and absent P-E0-MX outputs. It runs no verification,
trainer, auditor, model-fit, DVC, or scientific-network command and writes
nothing.

The separately authorized lock execution is:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_model_publication_adoption_patch.py \
  --execute-lock
```

It runs only the verification commands frozen by E0-MX and the non-recursive
historical A0 semantic audit. Publication is exclusive, descriptor-anchored,
no-follow, no-clobber, lock-first and companion-last, with rollback limited to
owned inodes. It invokes neither trainer nor public auditor entrypoints,
performs no fit, runs no DVC command, and reads no calibration, holdout,
post-2020, or future outcome.

After P-E0-MX is separately committed and published, target-aware checks are:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_model_publication_adoption_patch.py \
  --check-effective --model-id A0 --base-seed 1729 \
  --audit-current-unpublished

poetry run python \
  src/experiments/lock_closure_anfis_ablation_model_publication_adoption_patch.py \
  --check-effective --model-id A1 --base-seed 1729
```

## Deferred-DVC precommit procedure

The committed lightweight reports do not change the model-directory delta.
`models.dvc` must remain byte-identical in HEAD, index, and worktree while
local DVC status truthfully reports only the modified `models` output. The
eight A0 finals are snapshotted before and after staging and no A0 final or
`models.dvc` may enter the index.

E0-MX retains the inherited five-line command-scoped exclude file to
neutralize ambient global excludes and keep the invocation deterministic. It
does not hide modifications or deletions of the now-tracked files; the helper
independently requires their exact publication-commit, HEAD, index, and
worktree bindings.

Create `/tmp/e0_mx_a0_1729_exact_excludes` exclusively as a regular `0600`,
single-link file containing exactly these rooted lines in bytewise order:

```text
/reports/closure_v1/02_models/A0/seed_1729_manifest.json
/reports/closure_v1/02_models/A0/seed_1729_preprocessor.json
/reports/closure_v1/02_models/A0/seed_1729_report.md
/reports/closure_v1/02_models/A0/seed_1729_selection_metrics.csv
/reports/closure_v1/02_models/A0/seed_1729_training_curve.csv
```

With no other `GIT_CONFIG*` or redirected Git-state variable, run exactly:

```bash
GIT_CONFIG_COUNT=1 \
GIT_CONFIG_KEY_0=core.excludesFile \
GIT_CONFIG_VALUE_0=/tmp/e0_mx_a0_1729_exact_excludes \
DVC_NO_ANALYTICS=1 \
scripts/prepare_commit_artifacts.sh \
  --allow-unmanaged --no-push --defer-dvc-target models
```

Reject every unmanaged-heavy prompt. The helper must run no DVC add, cloud
status, or push. Its exclusive `0600`, single-link report must record exact
real DVC status before and after staging, identical eight-file snapshots, all
rejected unmanaged paths, a passing publication check, and no failing
reproducibility finding.

H preparation must stage exactly `6M+5A`. P preparation must stage exactly
the new lock and companion and its manifest check must report `1/1/1`. Neither
preparation may stage an A0 final or `models.dvc`. Any byte, inode, mtime,
mode, Git-binding, scope, environment, or DVC-status drift fails closed.
