# E0-MIC: locked-evaluation panel DVC identity patch

## Purpose and boundary

E0-MIC is an additive authority overlay over published P-E0-MIB commit
`ddd00ae96fa8cb589f368cb2f7b98d9e2561491d`.  It closes one representational
blocker discovered before R-E0-MI: the locked panel is a normal DVC cache
hardlink with mode `0444` and link count `2`, while the inherited generic
reader accepted only a private `0644`/single-link file.  The mismatch is not
scientific drift, data corruption, target access, or a consumed R attempt.

This overlay changes only the physical identity dialect used to read the
already sealed panel.  It does not rewrite the panel, its pointer, the
assignment, P-E0-MIB, calibration/E7 outputs, or any model.  It does not run
R-E0-MI, register DVC outputs, open outcomes, authorize E0-M/E0-U, stage,
commit, or push.

## Topology and exact scopes

The gate is `E0-MIC`.  Its module stem is
`closure_locked_evaluation_input_panel_dvc_identity_patch`.

H-E0-MIC is one direct child of P-E0-MIB and has exact scope `1M+5A`:

- modify `src/data/prepare_commit_artifacts.py`;
- add `configs/closure_v1/locked_evaluation_input_panel_dvc_identity_patch_lock.schema.json`;
- add this document;
- add `src/experiments/closure_locked_evaluation_input_panel_dvc_identity_patch.py`;
- add `src/experiments/lock_closure_locked_evaluation_input_panel_dvc_identity_patch.py`;
- add `tests/test_closure_locked_evaluation_input_panel_dvc_identity_patch.py`.

P-E0-MIC is a direct child of H and contains exactly two additions:

- `configs/closure_v1/locked_evaluation_input_panel_dvc_identity_patch_lock.json`;
- `configs/closure_v1/locked_evaluation_input_panel_dvc_identity_patch_lock_manifest.json`.

The later producer retains gate `R-E0-MI`, four physical Parquets, four DVC
pointers, one summary, one manifest, and exact tracked scope `6A`.  Its exact
command is:

```text
poetry run python src/experiments/closure_locked_evaluation_input_panel_dvc_identity_patch.py --execute-input-bundle
```

H and P never imply permission to run that command.  R requires separate,
informed, one-shot authorization after P-E0-MIC is published and audited.

## Closed physical identity contract

The assignment remains an anchored regular file with mode `0644`, link count
`1`, and its sealed SHA-256.  Every future R physical output remains a distinct
regular file with mode `0644` and link count `1`.

The panel contract is deliberately different and exact:

- panel path `data/panel/panel_monthly_v0.parquet`;
- pointer path `data/panel/panel_monthly_v0.parquet.dvc`;
- DVC cache object `.dvc/cache/files/md5/9a/eaac8466f16cae4ef4164980899059`;
- panel and cache are regular, mode `0444`, link count exactly `2`;
- panel and cache have the same device and inode and identical bytes;
- payload size is `103469973` bytes;
- payload MD5 is `9aeaac8466f16cae4ef4164980899059`;
- payload SHA-256 is
  `8aedc531b9e024bd8f73e66f917932b8301f79309d4596618c5a839e3b70dc62`;
- the pointer is regular `0644`/single-link and its only output seals
  `hash: md5`, the same MD5 and size, and path `panel_monthly_v0.parquet`.

The audited helper performs anchored no-follow traversal, binds the opened
descriptor to the named entry, validates the authorized pointer, verifies the
panel/cache inode and bytes, and repeats the capture at transaction
boundaries.  A symlink, missing or extra hardlink, mode change, inode change,
cache replacement, pointer dialect/hash/size/path change, payload mutation, or
unstable reread fails closed.  It never broadens `0444`/link-count `2` to the
assignment or R outputs.

H/P checks may open and hash only the assignment, panel pointer, panel, and
exact cache object as byte-level identity evidence.  They do not decode panel
rows or import the Arrow/scientific producer.  They never open target,
target-availability, outcome, state, prediction, metric, or E0-M paths.

## Input-only R contract preserved

E0-MIC inherits the complete E0-MIB scientific contract.  R reads only the
four assignment identifier columns and the explicit no-Chl-a panel projection.
The origin universe begins at `2022-01`; its upper bound is the last panel
month in that permitted input projection, never a target-derived boundary.
Horizons `{1,2,3}` remain deferred arithmetic for the future evaluator and are
not materialized as target months.

The four Parquets keep exact Arrow schemas, column order, nullability,
lexicographic order, unique keys, row relationships, and cross-table foreign
keys.  Terminal validation rebuilds the complete bundle from the permitted
assignment and panel projection and requires byte/semantic equality.  No
target, target availability, outcome, metric, model fit, prediction, E0-M, or
E0-U artifact is created or read.

## Companion and predecessor preservation

The P companion is canonical JSON and exact `16/6/1`:

- 16 current physical inputs: published P-E0-MIB's two JSON files, H-E0-MIC's
  six components, and the eight immutable calibration/E7 outputs;
- six historical Git inputs: H-E0-MIB's exact superseded component blobs;
- one output: the E0-MIC lock JSON.

Every set is sorted, duplicate-free, mode/hash/size bound, and reconstructed.
The companion names the MIC locker as its script and is published last.  The
predecessor physical snapshot is revalidated before and after every publication
boundary.  Historical blobs are read from their sealed commits and are not
confused with their superseding worktree files.

## Locker behavior

`--check-only` performs schema preflight, captures the exact four source
identities, captures the immutable physical16, collects the full remote-aware
prelock state twice, and then recaptures physical16 and the four source
identities.  Each collect independently validates the exact assignment,
pointer, panel, and cache identity.  Both state captures, both physical
snapshots, and both exact4 source snapshots must be equal.  The source
snapshots truthfully seal `panel_bytes_opened=true` and
`assignment_bytes_opened=true`, while `panel_rows_decoded=false` and
`assignment_rows_decoded=false`.  Check-only writes nothing and runs no type
check, pytest, Poetry check, publication guard, diff check, scientific row
decoder, DVC command, staging, commit, or push.

`--execute-lock` first captures prelock state and physical16, then runs exactly:

```text
poetry run ty check
poetry run pytest -q tests/test_prepare_commit_artifacts.py tests/test_closure_locked_evaluation_input_panel_dvc_identity_patch.py
poetry check
scripts/check_repo_publication_ready.sh
git diff --check
```

The focused suite must report exactly `48 passed`, zero skipped, and zero
deselected, with no warning/failure dialect.  The exact4 source identity
snapshot brackets the full verification interval.  After verification the
locker recaptures physical16 and the full prelock state, reconstructs the
schema-closed payload, and validates it with live-remote policy before
publication.  Any source device, inode, mode, link-count, size, timestamp, or
byte-hash change across that interval fails before publication.

The publisher acquires one exclusive guard, rejects any pre-existing final or
temporary, publishes lock first and companion manifest last through hardlink
no-clobber, validates exact bytes and owned identities, and revalidates Git,
remote, namespace, panel identity, and physical16 at every boundary.  Failure
rolls back only outputs whose owned inode still matches; a foreign replacement
or incomplete rollback remains visible and requires audit.  The guard is
released before two final ownership-transfer passes, both of which repeat all
identity and authority checks.

## Namespace and authorization barriers

Before P publication, both MIC P outputs, both MIC temporaries, the MIC locker
guard, and every inherited R output/temp/run guard are absent.  Published
historical locks remain present and intact; never-published legacy finals stay
absent.  P publication may create only the exact MIC pair.  R and all formal
E0-M paths, including the outcome access log, remain absent.

Every H/P payload and loader result keeps evaluation, training, calibration,
DVC add/push, Git commit/push, E0-M, E0-U, outcome access, holdout outcome
access, and post-2021 outcome access false.  Before R exists, effective MIC
authority may authorize only the exact input-bundle producer command.  Once R
exists, that one-shot authority is consumed and the terminal loader performs
the inherited deep input-only rebuild without granting evaluation authority.

## Acceptance and manual barriers

Acceptance requires all of the following:

1. H is the exact `1M+5A` child of `ddd00ae96f...`, with frozen modes and
   hashes, aligned refs, and no extra workspace paths.
2. Schema preflight rejects duplicate keys and every open object dialect.
3. Assignment `0644/1` and panel/cache `0444/2` identities, pointer binding,
   bytes, inode, and stable rereads pass; every stated drift fails closed.
4. Check-only returns `ready_to_lock`, two equal prelock captures, immutable16,
   two equal exact4 source-identity captures, byte-open/row-decode flags that
   match reality, zero writes, and zero verification/scientific-row/DVC
   commands.
5. Execute-lock seals exact verification `48/0/0` and publishes only P2,
   lock-first/manifest-last, with companion `16/6/1` and rollback guarantees.
6. P is published and independently audited before any R authorization.
7. R, E0-M, E0-U, outcomes, targets, predictions, metrics, DVC operations,
   staging, commit, and push remain absent unless separately authorized at
   their own manual boundary.

Stop for an independent read-only audit after H precommit/publication, after
check-only, after P lock publication/precommit/publication, after the one-shot
R producer, after directed DVC registration, and after R precommit/publication.
