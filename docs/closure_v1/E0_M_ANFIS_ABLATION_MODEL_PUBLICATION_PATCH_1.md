# E0-MW: ANFIS-ablation model publication patch 1

## Purpose and scientific boundary

E0-MW is an additive, implementation-only overlay over published H-E0-MV
`455f593fc276dc0b74565e34aea4a09342badb30`. It corrects only the protocol
lock filename and publication dialect. It changes no split, target,
denominator, preprocessing statistic, architecture, optimizer, seed, epoch,
selection rule, model output, or ordered-slot policy.

The immutable `A0/1729` one-shot remains the sole completed slot. It must
never be rerun, rewritten, normalized, moved, touched, replaced, or copied
back through a temporary location. Calibration, evaluation, E0-M, E0-U,
holdout and post-2020 target access, outcome access, DVC registration, batch
slot execution, and scientific network egress remain closed.

## Blocked P-E0-MV attempt

The unpublished P-E0-MV lock was scientifically and structurally valid, but
the generic artifact assistant classified both staged JSON files as experiment
manifests. Its filename predicate accepts every JSON under `reports/` whose
basename contains `manifest`. The protocol lock therefore entered the generic
experiment-manifest branch even though its sealed dialect correctly used
`status=locked_unpublished` and did not expose a top-level `outputs` list.

The assistant failed closed with exactly these two findings against the lock:

```text
Experiment manifest status is `locked_unpublished`, expected `completed`.
Experiment manifest must contain a non-empty `outputs` list.
```

No DVC add or push ran. The before/after A0 inode, mtime, byte, hash, and mode
snapshots were identical. The two blocked JSON files and their failed report
are retained only as ignored local incident evidence:

| Record | Bytes | SHA-256 |
| --- | ---: | --- |
| blocked lock | 28403 | `0704ad83b0cf9c4f2de17c948e32eec889c435164268f815b9a99b05c6fd2b07` |
| blocked companion | 17033 | `25fbd11373d420db3127718c6808f57c2e96d05630371956035d69d0ac3d2966` |
| failed precommit report | 7451 | `3146b15569758cd4048e2f649147a0ff90c25b1d9b9d67e905f5fe51b2b4ab77` |

The local archive is
`tmp/p_e0_mv_blocked_20260808T195750Z/`; the report is
`tmp/pre_commit_artifacts_20260808T195750Z.md`. Neither path is an authority,
an input, a fresh-clone dependency, or a publication candidate. The original
P-E0-MV output paths must remain absent. The blocked bundle must never be
published, retried, copied back, or treated as an effective lock.

Rewriting the blocked lock to mimic an experiment manifest, weakening the
generic assistant, staging only one file, bypassing its failure, or amending
published H-E0-MV is forbidden.

## Closed filename correction

E0-MW follows the established E0-DLTVM publication-dialect precedent. The
generic assistant remains unchanged. The future protocol lock basename does
not contain `manifest`; only its generic completed companion does:

```text
reports/closure_v1/00_protocol/anfis_ablation_model_publication_patch_lock.json
reports/closure_v1/00_protocol/anfis_ablation_model_publication_patch_lock_manifest.json
```

Consequently, a P-E0-MW precommit must classify exactly one experiment
manifest, one covered output record, and one staged report artifact. The lock
retains its strict `locked_unpublished` protocol dialect. The companion retains
`status=completed`, lists the lock as its sole output, and is written last.

## H/P topology and exact scope

H-E0-MW must be the direct, non-merge child of H-E0-MV. Its exact scope is
`5M+5A`.

Exactly these five paths are modified:

```text
src/data/prepare_commit_artifacts.py
src/experiments/audit_closure_anfis_ablation_model_bundle.py
src/experiments/train_closure_anfis_ablation.py
tests/test_audit_closure_anfis_ablation_model_bundle.py
tests/test_train_closure_anfis_ablation.py
```

Exactly these five paths are added:

```text
configs/closure_v1/anfis_ablation_model_publication_patch_lock.schema.json
docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_PUBLICATION_PATCH_1.md
src/experiments/closure_anfis_ablation_model_publication_patch.py
src/experiments/lock_closure_anfis_ablation_model_publication_patch.py
tests/test_closure_anfis_ablation_model_publication_patch.py
```

The helper modification closes its only mutating deferred-DVC boundary to the
exact H-E0-MW `5M+5A` and P-E0-MW `2A` scopes. Read-only pure validators retain
the H/P-E0-MV maps solely to reconstruct and test the published historical
protocol; those maps cannot enter the staging path. It does not change the
generic manifest classifier, artifact semantics, unmanaged-heavy policy, or
DVC truth reporting. The trainer and auditor route to E0-MW before model,
target, or output I/O. Their tests prove the new fail-closed authority path.

The helper remains Git mode `100755`; the other nine H components are
`100644`. P-E0-MW must be the direct, non-merge child of H-E0-MW and add only
the two `100644` JSON files above.

## Historical reconstruction and companion dialect

H-E0-MV is immutable Git authority. E0-MW reconstructs all ten H-E0-MV
components at `455f593fc276dc0b74565e34aea4a09342badb30`.

The five H-E0-MV blobs superseded by H-E0-MW are the helper, trainer, auditor,
trainer test, and auditor test. They appear only in `historical_inputs`, with
their exact Git commit, byte count, and SHA-256. Current physical bytes are
never required to match those historical blobs. The other five H-E0-MV
components remain current physical inputs.

The P-E0-MW companion is maximal and exact:

- `77` unique current physical `inputs`;
- `5` Git-bound `historical_inputs` for the superseded H-E0-MV paths;
- the current E0-MW locker exactly once as top-level `script` and in `inputs`;
- the E0-MW lock as the sole `outputs` record.

The four older H-E0-MU historical records remain transitively governed by
published P-E0-MU and H-E0-MV reconstruction; they are not duplicated. The
blocked P-E0-MV files and all eight A0 artifacts are excluded from companion
`inputs` and `historical_inputs`. The strict E0-MW loader independently checks
the immutable A0 records.

## Slot authority and progression

Before P-E0-MW publication, all build, audit, DVC, calibration, evaluation,
E0-M, E0-U, and outcome authorizations remain false. The unpublished payload
is never effective.

After exact publication, the target-aware loader may authorize only:

- read-only audit of adopted `A0/1729` using its historical P-E0-MU binding;
- construction of the next ordered slot, `A1/1729`, using published P-E0-MW
  and the H-E0-MW trainer source record.

It must continue to revalidate the complete ordered prefix, all completed-slot
bytes, absence of holes, temporary files and guards, and the no-pointer policy.
A0 replay or replacement remains forbidden. DVC registration remains closed
until all ten A0/A1 slots are complete.

## Gates

The schema-first, non-writing preflight is:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_model_publication_patch.py \
  --check-only
```

It validates live H-E0-MW topology, exact H-E0-MV reconstruction, `77+5`
companion topology, the adopted A0 bundle, empty future namespaces, and absent
P-E0-MW outputs. It runs no verification, trainer, auditor, model-fit, DVC, or
scientific-network command and writes nothing.

The separately authorized lock execution is:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_model_publication_patch.py \
  --execute-lock
```

It runs only the verification commands frozen in the E0-MW validator and the
non-recursive historical A0 semantic audit. Publication is guarded,
descriptor-anchored, no-follow, no-clobber, lock-first and companion-last,
with rollback limited to owned inodes. It invokes neither the trainer nor the
public auditor entrypoint, performs no fit, runs no DVC command, and reads no
calibration, holdout, post-2020, or future outcome.

After P-E0-MW is separately committed and published, target-aware checks are:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_model_publication_patch.py \
  --check-effective --model-id A0 --base-seed 1729 \
  --audit-current-unpublished

poetry run python \
  src/experiments/lock_closure_anfis_ablation_model_publication_patch.py \
  --check-effective --model-id A1 --base-seed 1729
```

## Deferred-DVC precommit procedure

The eight A0 finals remain byte-exact in place while `models.dvc` truthfully
reports the unregistered model-directory delta. H-E0-MW and P-E0-MW therefore
use the same closed deferred-DVC mechanism introduced by H-E0-MV, with a new
exclusive absolute `0600`, single-link exclude file containing exactly the
five rooted lightweight A0 report paths.

Create `/tmp/e0_mw_a0_1729_exact_excludes` exclusively as a regular `0600`,
single-link file containing these five rooted lines in bytewise order:

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
GIT_CONFIG_VALUE_0=/tmp/e0_mw_a0_1729_exact_excludes \
DVC_NO_ANALYTICS=1 \
scripts/prepare_commit_artifacts.sh \
  --allow-unmanaged --no-push --defer-dvc-target models
```

Reject every unmanaged-heavy prompt. The helper must run no DVC add, cloud
status, or push. Its exclusive `0600` report must record the exact real DVC
status before and after staging, identical eight-file A0 snapshots, all
rejected unmanaged paths, a passing publication check, and no failing
reproducibility finding.

H preparation must stage exactly `5M+5A`. P preparation must stage exactly the
new lock and companion, and the manifest check must report `1/1/1`. Neither
preparation may stage an A0 final or `models.dvc`. The five lightweight A0
files remain untracked after the temporary exclude file is removed. Any drift
fails closed before publication.
