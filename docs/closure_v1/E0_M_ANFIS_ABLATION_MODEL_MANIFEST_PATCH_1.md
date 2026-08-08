# E0-MV: A0/A1 model-manifest authority patch 1

## Purpose and immutable evidence

E0-MV is an implementation-only overlay over published P-E0-MU
`404983e3dfc511d982b2641aa4aea769dcbc6beb`.  It changes no split, target,
denominator, preprocessing statistic, architecture, optimization rule, seed,
selection rule, or output schema.  Calibration, evaluation, E0-M, E0-U,
holdout targets, post-2020 targets outside the sealed development projection,
DVC registration, and scientific network egress remain closed.

The first one-shot, `A0/1729`, completed and published its eight local finals
atomically.  The writer and the semantic auditor agree on the JSON dialect:
UTF-8, `ensure_ascii=False`, `allow_nan=False`, two-space indentation, insertion
order preserved, and one terminal newline.  The public audit entrypoint then
stopped before acquiring audit authority because the older E0-MT progression
adapter required a different byte dialect: compact JSON with sorted keys.  The
failure is representational, not scientific.  The non-recursive semantic audit
passes the existing bundle with exact schemas and hash bindings and reports no
calibration, DVC, future-outcome, or write side effect.

The following A0 records are immutable adoption evidence.  E0-MV must never
rewrite, normalize, move, touch, replace, or replay them:

| Role | Bytes | SHA-256 |
| --- | ---: | --- |
| model | 142911 | `1e5c2c21b9cb69a4dfa9139fcd6058e57afd4922a19bd1b3cd071a6608897fef` |
| checkpoint | 142911 | `0991ff130f694b69ae30bd37416d3ba2d63f67874b3d895976efb9e28c6ce277` |
| preprocessor | 2472 | `ebffd11d392c62e68e2afbd3ee05febfd05a7411fc83ca18563c7773a51faa62` |
| training curve | 2588 | `edfb193302b0fe21708e1ff1556dcdcdf817948a8bd35cef2f90b16be9cc0ec0` |
| selection predictions | 64842 | `6ca58207a32ba345fc4611c73a879e0546a608d7d076baf8f8da057373a3a4ae` |
| selection metrics | 914 | `f6444a2047d2032334580f1322c4f61637a9028fd0aab27815a6c7386cf860eb` |
| report | 320 | `6e12b1d2fc0a1fce8baf7c1f81edbeb1bdd3d013d4365d606d21cc20399d123e` |
| manifest | 11231 | `406bf44de3ecdc49ff3d5797cbca1ec0c11ebfbdc70ba262130b85a2e58e31e2` |

The manifest remains physically newer than the other seven finals.  It retains
its exact historical E0-MU authority binding, its three physical E0-MU
authority records, and the H-E0-MU trainer source record.  The five lightweight
report files remain untracked and the model, checkpoint, and prediction
Parquet remain ignored until the ten-slot registration gate.

## H/P topology and exact scope

H-E0-MV is a direct, non-merge child of P-E0-MU.  Its exact scope is `5M+5A`.
Only these five existing paths are modified:

```text
src/data/prepare_commit_artifacts.py
src/experiments/audit_closure_anfis_ablation_model_bundle.py
src/experiments/train_closure_anfis_ablation.py
tests/test_audit_closure_anfis_ablation_model_bundle.py
tests/test_train_closure_anfis_ablation.py
```

Exactly these five authority paths are added:

```text
configs/closure_v1/anfis_ablation_model_manifest_patch_lock.schema.json
docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_MANIFEST_PATCH_1.md
src/experiments/closure_anfis_ablation_model_manifest_patch.py
src/experiments/lock_closure_anfis_ablation_model_manifest_patch.py
tests/test_closure_anfis_ablation_model_manifest_patch.py
```

The H commit preserves the repository's executable contract: the precommit
assistant `src/data/prepare_commit_artifacts.py` is exactly Git mode `100755`;
the other nine H components are exactly `100644`.  The lock records the full
ten-path mode map.  A chmod or normalization of the helper is forbidden.

No other E0-MT or E0-MU source, lock, companion, runtime, sequence, target,
model output, DVC pointer, benchmark, or analysis-plan path is modified.  The
four E0-MU source/test blobs superseded here remain reconstructible from Git.

P-E0-MV must be the direct, non-merge child of H-E0-MV and add exactly two
regular `100644` files:

```text
reports/closure_v1/00_protocol/anfis_ablation_model_manifest_patch_lock.json
reports/closure_v1/00_protocol/anfis_ablation_model_manifest_patch_lock_manifest.json
```

The lock is published first and the companion last.  Publication is exclusive,
no-follow, no-clobber, descriptor-anchored, and rolls back only owned inodes.
Neither public publisher accepts caller-supplied verification or payloads.

## Historical reconstruction and companion dialect

P-E0-MU and its H parent are immutable Git authorities.  The four H-E0-MU
blobs superseded by H-E0-MV (trainer, auditor, and their two tests) are rebuilt
from Git and appear only in `historical_inputs`; current bytes are never
required to match them.  The older four historical H-E0-MT records remain
transitively sealed by the exact physical P-E0-MU companion and are not
duplicated in the new companion.

The E0-MV companion is maximal and exact for this overlay:

- `72` unique current physical `inputs`: sixty preserved P-E0-MU physical
  dependencies, the P-E0-MU lock and companion, and all ten H-E0-MV
  components;
- `4` Git-bound `historical_inputs`: the superseded H-E0-MU trainer, auditor,
  trainer test, and auditor test;
- the current E0-MV locker as the top-level `script`, also present exactly once
  in `inputs`;
- the E0-MV lock as the sole `outputs` record.

The eight A0 artifacts are sealed separately as the adopted scientific bundle
inside the lock.  They are deliberately not placed in companion `inputs`,
because that field is reserved for current governance dependencies consumed by
the generic artifact checker.  The strict E0-MV loader independently verifies
all eight records, their regular-file modes, manifest-last ordering, pretty
canonical JSON, historical authority/source bindings, and semantic audit.

## Slot-manifest authority

The effective loader is target-aware and returns an outer E0-MV authority plus
two slot-specific records:

- `slot_manifest_authority`: exactly the thirteen manifest authority-binding
  keys;
- `slot_source_record`: exactly `role`, `path`, `bytes`, and `sha256` for the
  trainer whose bytes created that slot.

For adopted `A0/1729` audit mode, those values are the historical E0-MU binding
and H-E0-MU trainer record already serialized in the immutable manifest.  For
future slots they bind published P-E0-MV and the current H-E0-MV trainer.  The
auditor accepts the historical branch only for adopted `A0/1729`; future slots
cannot claim it.  The trainer accepts only the next build slot and serializes
the current E0-MV binding and source record.

Before exact P-E0-MV publication, the loader authorizes neither audit nor
build.  After publication it may authorize read-only audit of adopted
`A0/1729` and, independently, the exact next build slot `A1/1729`.  A0 replay,
replacement, retry, or normalization remains forbidden.  Every subsequent
slot must form the existing ordered prefix:

```text
A0/1729, A1/1729, A0/20260612, A1/20260612, A0/20260613,
A1/20260613, A0/20260614, A1/20260614, A0/314159, A1/314159
```

Each authority load revalidates the byte-exact adopted A0 bundle, all completed
slots, the absence of holes, temporaries and guards, and the no-pointer policy
before the final ten-slot DVC gate.  All calibration, evaluation, E0-M, E0-U,
outcome, DVC, retry, replacement, batch, and scientific-network flags remain
false.

## Gates

The non-writing preflight is:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_model_manifest_patch.py \
  --check-only
```

It validates the schema first, exact H/P-MU reconstruction, H-E0-MV topology,
live Git alignment, the adopted A0 inventory, and the remaining empty
namespace.  It runs no verification command and writes nothing.

Under the already separated execution authorization, `--execute-lock` may run
only the frozen verification commands and the non-recursive A0 semantic audit,
then publish lock plus companion.  It never invokes the trainer or public
auditor entrypoint, performs no fit or optimization, and runs no DVC command.

After P-E0-MV publication, the target-aware checks are:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_model_manifest_patch.py \
  --check-effective --model-id A0 --base-seed 1729 \
  --audit-current-unpublished

poetry run python \
  src/experiments/lock_closure_anfis_ablation_model_manifest_patch.py \
  --check-effective --model-id A1 --base-seed 1729
```

## Exact transient exclusion for H/P preparation

The generic artifact assistant ends with `git add -A`.  During H-E0-MV and
P-E0-MV preparation it must not capture the five lightweight adopted A0 files,
which contractually remain untracked until the ten-slot registration gate.
Archiving, renaming, copying back, rewriting, touching, or normalizing any A0
artifact is forbidden.

Instead, run the assistant with a command-scoped Git configuration environment.
Create one exclusive regular temporary exclude file at an absolute path
outside the publication scope, with mode `0600`, containing exactly these
rooted patterns and no others:

```text
/reports/closure_v1/02_models/A0/seed_1729_manifest.json
/reports/closure_v1/02_models/A0/seed_1729_preprocessor.json
/reports/closure_v1/02_models/A0/seed_1729_report.md
/reports/closure_v1/02_models/A0/seed_1729_selection_metrics.csv
/reports/closure_v1/02_models/A0/seed_1729_training_curve.csv
```

With no pre-existing `GIT_CONFIG*`, `GIT_INDEX_FILE`, `GIT_DIR`,
`GIT_WORK_TREE`, `GIT_COMMON_DIR`, object-directory override, or namespace
override, set for the assistant process only:

```text
GIT_CONFIG_COUNT=1
GIT_CONFIG_KEY_0=core.excludesFile
GIT_CONFIG_VALUE_0=<absolute exclusive temporary file>
```

These variables propagate to the assistant's child Git commands and vanish
with that process; repository and user Git configuration are not changed.

The helper rejects the deferral unless `GIT_CONFIG_COUNT=1`,
`GIT_CONFIG_KEY_0=core.excludesFile`, and `GIT_CONFIG_VALUE_0` names that exact
absolute, regular, exclusive `0600` file.  It also requires
`DVC_NO_ANALYTICS=1` exactly and rejects a custom `DVC_SITE_CACHE_DIR` (the
repository default is the only accepted explicit value).  The adopted A0 model and checkpoint
make the already tracked `models` DVC
directory truthfully appear modified even though registration remains closed
until all ten slots exist.  The assistant therefore accepts one narrowly
sealed deferral only for this phase.  It requires `--no-push`, accepts the
exact target `models` and no alias or second target, validates the immutable
A0/1729 eight-record inventory and exact one-slot prefix, and revalidates the
same evidence before staging, after staging, after reproducibility checks, and
after writing the report.  A custom `--dvc-bin`, `DVC_BIN`, `--manifest`, or
`--report` is forbidden; the repository `.venv/bin/dvc`, sealed default
inventory, and generated default report path are mandatory.  The report is
created once as regular mode `0600` with no-follow/exclusive semantics and
records both eight-file inode/mtime/byte/hash snapshots.  It removes `models`
only from the DVC-add target
set; the actual `dvc status --json` payload and the deferral are written to the
report.  In deferred mode, the helper resolves the exact pre-stage H or P
scope and invokes `git add -A --` with only those ten or two explicit paths;
it never uses a repository-wide pathspec.  At every post-staging checkpoint it
revalidates the exact global staged/unstaged status, all Git modes, and every
index blob against the raw worktree bytes.  It must run neither `dvc add
models` nor `dvc push`.  Any target, status, byte, prefix, pointer, worktree,
index, staged-scope, report, or post-staging drift fails closed.

With the command-scoped five-pattern exclude file above, run:

```bash
DVC_NO_ANALYTICS=1 scripts/prepare_commit_artifacts.sh \
  --allow-unmanaged --no-push --defer-dvc-target models
```

Reject every unmanaged heavy DVC prompt.  The temporary exclude file is then
removed.  Before and after the assistant, verify the same eight A0 byte counts
and SHA-256 values, regular modes, manifest-last mtimes, absent pointer,
temporary and guard paths, truthful deferred-DVC report, and exact Git scope.
Archiving, renaming, copying back, rewriting, touching, or normalizing any A0
artifact remains forbidden.  H preparation must leave only `5M+5A` staged; P
preparation must leave only the two lock files staged.  Any mismatch fails
closed before publication.  In particular, none of the eight A0 finals and no
`models.dvc` path may be staged after either preparation.
