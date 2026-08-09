# E0-MY: ANFIS-ablation DVC registration patch 1

## Purpose and scientific boundary

E0-MY is the implementation-only registration overlay that follows published
P-E0-MX at commit
`c73b8ebe11d942631d24e43b0eac2f4b2e72e400`. The ten ordered A0/A1 fits are
already complete. E0-MY does not fit, replay, select, normalize, touch, move,
or replace a model-family final. It only seals the complete local family and
authorizes a later, separately prepared DVC/Git registration transaction.

Calibration, evaluation, E0-M, E0-U, holdout and post-2020 targets, future
outcomes, seed selection, seed pooling, and scientific interpretation remain
closed. The ten manifests continue to report `device: cpu`; DVC registration
does not change that scientific record. Neither the H nor P gate invokes DVC
or any scientific-network command.

## Complete family sealed before registration

The family is an exact ordered set of ten slots:

```text
A0/1729, A1/1729,
A0/20260612, A1/20260612,
A0/20260613, A1/20260613,
A0/20260614, A1/20260614,
A0/314159, A1/314159
```

Each slot has exactly eight immutable finals in this role order:

```text
model, checkpoint, preprocessor, training_curve,
selection_predictions, selection_metrics, report, manifest
```

The pre-registration namespace therefore contains exactly `80` regular
single-link `0644` files: `20` model/checkpoint files, `10` prediction
Parquets, and `50` lightweight report files. Their total is `3,790,938` bytes.
The SHA-256 of the ordered list of records containing only
`role/path/bytes/sha256`, encoded as compact JSON with sorted object keys and
no final newline, is
`e625add8f8af1746f7deda9ff13a84a4d4f4c27b47e3b6312922db419508dd8e`.

All ten manifests are completion markers written last and bind the other
seven finals by exact path, byte count, and SHA-256. Before registration, all
ten prediction-pointer paths, all eighty temporary siblings, all ten guards,
and all ten pointer-temporary siblings must be absent. The existing
`models.dvc` remains the exact baseline file of `109` bytes with SHA-256
`fcb93f78cc3e60c1c7f5bcc94a1765080358e0a5176880f1efa6245fa5365e5d`.

## Dedicated DVC inventory

`configs/closure_v1/dvc_artifacts_post_lock.yaml` retains its general
top-level `artifacts` inventory at exactly `23` records. E0-MY adds a separate
top-level `anfis_ablation_registration_artifacts` inventory with exactly `10`
records, one for each ordered selection-prediction Parquet. Mixing these ten
records into the general inventory, changing the order, duplicating a path or
artifact id, or adding model/checkpoint files individually fails closed.

The model/checkpoint files are registered through the already declared
directory target `models`, which produces one modified `models.dvc`. The ten
prediction Parquets are file targets and each produces its own new `.dvc`
pointer.

## H/P/R topology and exact scopes

H-E0-MY must be the direct, non-merge child of P-E0-MX. Its exact scope is
`4M+5A`.

Exactly these four paths are modified:

```text
configs/closure_v1/dvc_artifacts_post_lock.yaml
src/data/prepare_commit_artifacts.py
tests/test_closure_anfis_ablation_model_publication_patch.py
tests/test_closure_anfis_ablation_model_publication_adoption_patch.py
```

Exactly these five paths are added:

```text
configs/closure_v1/anfis_ablation_dvc_registration_patch_lock.schema.json
docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_PATCH_1.md
src/experiments/closure_anfis_ablation_dvc_registration_patch.py
src/experiments/lock_closure_anfis_ablation_dvc_registration_patch.py
tests/test_closure_anfis_ablation_dvc_registration_patch.py
```

The helper remains Git mode `100755`; the other eight H components are
`100644`.

P-E0-MY must be the direct, non-merge child of H-E0-MY and add only these two
`100644` JSON files:

```text
reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_patch_lock.json
reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_patch_lock_manifest.json
```

The companion binds exactly `11` current physical inputs and `4` historical
Git inputs. The eighty family finals are bound by the lock's dedicated family
section and are deliberately not duplicated in the companion.

Only after P-E0-MY is committed and published may the registration transaction
R-E0-MY run. Its exact Git scope is `55A+1M` (`56` paths):

- `45A`: every still-untracked lightweight family output; the five published
  A0/1729 lightweight outputs are preserved and must not be restaged;
- `10A`: one selection-prediction `.parquet.dvc` pointer for every ordered
  model/seed slot;
- `1M`: the existing `models.dvc`, updated once for all twenty
  model/checkpoint files.

Any other added, modified, deleted, renamed, copied, or staged path rejects the
transaction.

## Gates

The schema-first, non-writing H preflight is:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_dvc_registration_patch.py \
  --check-only
```

It validates the live H topology, P-E0-MX ancestry, the two inventories, the
complete 80-final family, the baseline `models.dvc`, the absent pointer/temp/
guard namespace, and absent P-E0-MY outputs. It performs no verification
command and writes nothing.

The separately authorized lock publication is:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_dvc_registration_patch.py \
  --execute-lock
```

It runs only the frozen verification commands, snapshots the full family
before and after every command, and publishes only lock then companion.
Publication is exclusive, descriptor-anchored, no-follow and no-clobber, with
temporary siblings, companion-last completion, and rollback restricted to
inodes owned by the transaction. It runs the closed read-only semantic family
audit in process, but never runs the trainer or public model-auditor entrypoint,
DVC, calibration, evaluation, or an outcome reader.

After P-E0-MY is separately published, the effective-authority check is:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_dvc_registration_patch.py \
  --check-effective
```

An unpublished P bundle is not effective and cannot authorize registration.

## R-E0-MY registration transaction

With P-E0-MY effective and the exact pre-registration namespace intact, run
the helper only under separate authorization:

```bash
DVC_NO_ANALYTICS=1 \
scripts/prepare_commit_artifacts.sh \
  --register-anfis-ablation-model-family --no-push
```

This mode admits no custom manifest, DVC binary, report, jobs, Git-state
redirection, extra target, unmanaged-path choice, dry run, or push. It must
run exactly one `dvc add --no-relink <target>` command for each of the ten
ordered prediction Parquets and then `dvc add --no-relink models`,
then stage exactly the `55A+1M` registration scope. It must re-audit all
eighty finals, both inventory sections, generated pointer structures, DVC
status, Git scope, and scientific boundaries before returning success. It
must not run `dvc push`, `git commit`, or `git push`.

The transaction seals repository `.dvc/config` as 43 bytes/SHA-256
`cb08c869a906d07c5b1ccf593299a0f253e0ce03303c43070b6a68124b27fda0`
with cache type `reflink,hardlink,copy`, and `.dvc/config.local` as 211
bytes/SHA-256
`a912c374690215c7753070f68d7dfdaff8c1224b01c336aa887d6731a3bb2287`.
Incoming DVC/XDG overrides, local cache/autostage overrides, and implicit
relinking are forbidden. Each DVC subprocess receives transaction-owned,
empty global and system config directories; both are removed with the other
durable coordination paths only after the effective post-registration audit.

The resulting registration commit is a separate publication barrier. The
ten lightweight manifests remain the only completion markers; DVC pointer
files are registration metadata, not new experimental results.

## External storage barrier

Cloud egress is outside H, P, and the no-push R helper. After R is prepared
and audited, but before its Git commit and publication, two separately visible
DVC pushes are required under explicit external-egress authorization:

1. push the updated `models.dvc` target;
2. push the ten ordered selection-prediction pointer targets together.

The two commands are distinct and ordered:

```bash
DVC_NO_ANALYTICS=1 .venv/bin/dvc push models.dvc

DVC_NO_ANALYTICS=1 .venv/bin/dvc push \
  data/closure_v1/development/anfis_ablation/A0/seed_1729_selection_predictions.parquet.dvc \
  data/closure_v1/development/anfis_ablation/A1/seed_1729_selection_predictions.parquet.dvc \
  data/closure_v1/development/anfis_ablation/A0/seed_20260612_selection_predictions.parquet.dvc \
  data/closure_v1/development/anfis_ablation/A1/seed_20260612_selection_predictions.parquet.dvc \
  data/closure_v1/development/anfis_ablation/A0/seed_20260613_selection_predictions.parquet.dvc \
  data/closure_v1/development/anfis_ablation/A1/seed_20260613_selection_predictions.parquet.dvc \
  data/closure_v1/development/anfis_ablation/A0/seed_20260614_selection_predictions.parquet.dvc \
  data/closure_v1/development/anfis_ablation/A1/seed_20260614_selection_predictions.parquet.dvc \
  data/closure_v1/development/anfis_ablation/A0/seed_314159_selection_predictions.parquet.dvc \
  data/closure_v1/development/anfis_ablation/A1/seed_314159_selection_predictions.parquet.dvc
```

Each push must be repeated idempotently and report that storage is already up
to date before Git publication. No command in this document authorizes a Git
commit or Git push; those remain manual publication barriers.
