# E0-MZ — ANFIS-ablation DVC registration adoption patch

## Purpose

E0-MZ is an additive governance overlay over
`2f0643ab6f634fdcce71f0ee0d847c448d2c61f5`. It adopts the already-published
45 lightweight ANFIS-ablation outputs without treating their publication as a
DVC registration, and restores a closed path to register only the 30 heavy
family outputs.

The overlay does not refit, recalibrate, evaluate, rewrite, or reinterpret any
scientific artifact. The ten completed A0/A1 slots and their 80 immutable
finals remain the scientific authority. E0-MZ changes only the publication and
registration topology that was invalidated when the 45 lightweight files were
committed before P-E0-MY and R-E0-MY.

## Adopted history

The validator reconstructs this exact linear history from Git:

```text
c73b8ebe11d942631d24e43b0eac2f4b2e72e400  P-E0-MX
    |
    +-- af233a89e22ce380f7b1f2094cdf4a92eb95b83d  H-E0-MY, exact 4M+5A
            |
            +-- 2f0643ab6f634fdcce71f0ee0d847c448d2c61f5
                exact 45A lightweight-family adoption
```

The second commit adds exactly the 45 paths that R-E0-MY expected to add. Its
bytes must equal the corresponding records in the immutable 80-final family.
It is material publication progress, but it is not P-E0-MY or R-E0-MY. The two
P-E0-MY JSON paths and all ten selection-prediction DVC pointers must remain
absent at the E0-MZ prelock.

## Scientific state preserved

The adopted family is exactly:

- model IDs `A0` and `A1`;
- base seeds `1729`, `20260612`, `20260613`, `20260614`, and `314159`;
- ten `completed` / `available` / `passed` slots;
- 80 regular `0644`, single-link finals;
- 50 lightweight Git files, all already tracked at the E0-MZ base;
- 20 model/checkpoint files and ten selection-prediction Parquets physically
  present but still ignored and unregistered;
- zero final or pointer temporaries, training guards, registration guards, or
  E0-MY/E0-MZ lock outputs.

Each slot retains 5,932 training origins/17,796 horizon rows, 658
model-selection origins/1,974 rows, and 224 calibration-metadata-only
origins/672 rows. Calibration target values, test, holdout, post-2020 targets,
E0-M, and E0-U remain unopened or unauthorized. This lock is not evidence of
calibration or evaluation performance.

## H/P/R topology and exact scopes

H-E0-MZ must be the direct, non-merge child of the exact 45A adoption commit
`2f0643ab6f634fdcce71f0ee0d847c448d2c61f5`. Its exact scope is `4M+5A`.

Exactly these four paths are modified:

```text
src/data/prepare_commit_artifacts.py
tests/test_closure_anfis_ablation_dvc_registration_patch.py
tests/test_closure_anfis_ablation_model_publication_adoption_patch.py
tests/test_closure_anfis_ablation_model_publication_patch.py
```

Exactly these five paths are added:

```text
configs/closure_v1/anfis_ablation_dvc_registration_adoption_patch_lock.schema.json
docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_ADOPTION_PATCH_1.md
src/experiments/closure_anfis_ablation_dvc_registration_adoption_patch.py
src/experiments/lock_closure_anfis_ablation_dvc_registration_adoption_patch.py
tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py
```

The helper remains Git mode `100755`; the other eight H components are
`100644`.

P-E0-MZ must be the direct, non-merge child of H-E0-MZ and add only these two
regular, single-link `100644` JSON files:

```text
reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_adoption_patch_lock.json
reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_adoption_patch_lock_manifest.json
```

Only after P-E0-MZ is committed and published may R-E0-MZ run. Its exact Git
scope is `10A+1M` (`11` paths):

- ten new `.parquet.dvc` pointers, one for every ordered A0/A1 seed slot;
- one modified `models.dvc`, registering all 20 model/checkpoint files through
  the already-owned `models` directory target.

The 50 lightweight files are preserved and must not be staged by R-E0-MZ. Any
other added, modified, deleted, renamed, copied, untracked, or staged path
rejects the transaction.

## Companion partition

The P-E0-MZ companion binds exactly 16 current physical inputs and eight
historical Git inputs:

- current physical: two P-E0-MX authority files, five preserved H-E0-MY
  components, and nine H-E0-MZ components;
- historical: four inherited P-E0-MX blobs superseded by H-E0-MY and four
  H-E0-MY blobs superseded by H-E0-MZ.

The adopted 45 files are part of the complete family records sealed in the
lock. Neither those 45 nor the remaining 35 family finals are duplicated in
the companion input list. Historical inputs are reconstructed from their
exact commits and are never compared to superseding physical paths.

## Gates

The schema-first, non-writing H preflight is:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_dvc_registration_adoption_patch.py \
  --check-only
```

It validates the exact P-E0-MX -> H-E0-MY -> 45A adoption -> H-E0-MZ
topology, the 80-final family, Git/physical bindings, the baseline
`models.dvc`, both artifact inventories, and the absent P/R/temporary
namespace. Check-only performs no verification command and writes nothing.

The separately authorized lock publication is:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_dvc_registration_adoption_patch.py \
  --execute-lock
```

It runs only the frozen read-only verification commands and publishes lock
then companion through the exclusive, no-follow, no-clobber, manifest-last
publisher. A failure rolls back only transaction-owned inodes. It never runs a
trainer, optimizer, auditor, DVC command, cloud command, or scientific network
command.

After the exact two-file P publication, effective authority is checked with:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_dvc_registration_adoption_patch.py \
  --check-effective
```

## Registration boundary

R-E0-MZ reuses the hardened exact-family transaction in the public
pre-commit assistant. Its only accepted invocation remains the dedicated
family-registration mode with `--no-push`, default repository manifests and
binaries, `DVC_NO_ANALYTICS=1`, and no custom targets or reports.

The transaction:

1. requires effective, published P-E0-MZ authority before DVC inspection;
2. seals the 80-final family, baseline `models.dvc`, repository/local DVC
   configuration, DVC wrapper/interpreter, Git executable, and exact index;
3. isolates global/system DVC configuration and sanitizes Git/Python/loader
   environment redirects;
4. runs exactly ten prediction targets followed by `models`, each as
   `dvc add --no-relink`;
5. preserves finals byte-for-byte and captures every pointer plus
   `models.dvc` by inode, mode, links, size, digest, mtime, and ctime;
6. rolls back exact partial/autostaged index subsets, pointers, and either an
   in-place or atomic `models.dvc` mutation on any pre-commit failure;
7. stages only R-E0-MZ `10A+1M`, never pushes DVC, and keeps the durable
   coordination guard until the post-registration private loader succeeds;
8. linearizes complete R with the durable `commit_ready` guard before
   coordination cleanup, preserving foreign replacements.

The ten `dvc add` commands and the later DVC push are separate authorization
boundaries. P-E0-MZ authorizes neither. Git commit and Git push remain manual
publication barriers.

## Closed outcomes and risks

E0-MZ must fail closed if any of these conditions changes:

- either adopted historical commit, parent, scope, Git mode, or blob;
- any family final, manifest relationship, path inventory, hard-link count,
  or forbidden namespace path;
- either P-E0-MY path becoming present;
- any pre-existing selection pointer or non-baseline `models.dvc`;
- the 16/8 companion partition or H/P/R exact scopes;
- branch, tracking, live remote, worktree, or index alignment;
- any calibration, evaluation, E0-M, E0-U, future-outcome, DVC, or network
  authorization becoming true.

The already-published 45A commit is preserved, not rewritten. E0-MZ closes
the resulting governance gap without claiming that heavy artifacts are
registered until R-E0-MZ completes and is separately published.
