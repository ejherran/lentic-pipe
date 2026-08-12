# E0-MCALM — Final-calibration R8 post-publication authority patch 1

## Status and authority

This document defines the additive `E0-MCALM` authority that closes the
post-publication lifecycle defect found after the successful R-E0-MCALL
publication. It does not change any published E0-MCALL lock, companion,
namespace rule, manifest adapter, scientific contract, or R8 output byte.

The exact published base is R-E0-MCALL commit
`09309c2d16820f5d93fe9fd38dadef92377fd005`. Its direct parent is the
published P-E0-MCALL commit
`c798d2ec2041baa011237fd26fc7f55d7596f300`, whose direct parent is the
published H-E0-MCALL commit
`fc82108e9f45a28ef1a0543d7fae956ca642aca3`. H-E0-MCALM must be a direct,
non-merge child of the R base. E0-MCALM supersedes only MCALL's effective
post-R publication-state interpretation. E0-MCALL remains the historical
authority for its exact coordination namespace, immutable R8 bundle, generic
manifest adoption, and H/P/R publication history.

No calibration, E7, scientific rerun, outcome, holdout, post-2021, E0-M,
E0-U, DVC, staging, commit, or push authority is created by this overlay.

## Root cause and failure boundary

R-E0-MCALL was published successfully as the exact eight additions authorized
by P-E0-MCALL. The repository, index, refs, P lock bundle, R8 files, and closed
coordination namespace are terminal and clean. The MCALL effective loader
nevertheless calls its P-publication validator with a pre-R repository-state
dialect. That validator requires the workspace path set to equal the exact R8
set, with every entry either untracked or staged, and then treats current
`HEAD` as P by requiring its parent to be H and the H-to-HEAD scope to be the
exact P lock pair.

At the legitimate terminal R commit the workspace and index are empty,
`HEAD` is R, R's parent is P, and P's parent is H. The loader therefore fails
closed with `E0-MCALL published P worktree is not exact R8` before it can
recognize the published state. If that first predicate were merely removed,
the following H-to-HEAD comparison would still misclassify the exact R scope
as P. The same loader also reports
`both_bundles_completed_unpublished`, `r_outputs_ready_for_staging=true`, and
`r8_staging_authorized=true`; those fields are valid only before R publication
and are false at terminal R.

This is a repository lifecycle-dialect defect, not scientific, calibration,
E7, manifest, namespace, history, data, Git-object, or filesystem corruption.
The exact eight R outputs are already published and must not be regenerated,
copied, moved, normalized, touched, staged again, or rewritten.

The existing phase-specific MCALL checks remain narrow. Its H checkpoint may
require untracked P and R files, its unpublished-P validator may require the
two P files untracked or staged while R remains untracked, and its R adoption
validator may require exact R8 staging. E0-MCALM does not broaden any of those
predicates. It adds a separate terminal-publication predicate and uses it only
for post-R reconstruction and the future effective MCALM loader.

## Exact terminal topology and scopes

The historical chain reconstructed by E0-MCALM is exact:

- H-E0-MCALL `fc82108e...` has exact scope `1M+5A` over H-E0-MCALK;
- P-E0-MCALL `c798d2ec...` is its direct child with exact scope `2A`;
- R-E0-MCALL `09309c2d...` is P's direct child with exact scope `8A`;
- all three commits are non-merge commits and their frozen component modes,
  blobs, hashes, and semantic bindings must match their published contracts.

H-E0-MCALM has exact scope `1M+5A` as a direct child of R-E0-MCALL. The sole
modification is:

- `src/data/prepare_commit_artifacts.py`.

The five additions are:

- `configs/closure_v1/final_calibration_r8_post_publication_authority_patch_lock.schema.json`;
- this document;
- `src/experiments/closure_final_calibration_r8_post_publication_authority_patch.py`;
- `src/experiments/lock_closure_final_calibration_r8_post_publication_authority_patch.py`;
- `tests/test_closure_final_calibration_r8_post_publication_authority_patch.py`.

P-E0-MCALM is exactly two `100644` additions under
`reports/closure_v1/00_protocol/`, with stem
`final_calibration_r8_post_publication_authority_patch_lock`: the canonical
lock and its companion manifest. There is no E0-MCALM R transaction. The
published R8 remains tracked, byte-identical, inode-identical, and outside
both H and P scopes.

Before H-E0-MCALM is published, the new implementation may reconstruct only
the exact clean terminal R base. The published H check-only and lock publisher
then require exact H-over-R topology with the MCALM P pair absent. The future
effective loader requires a clean P-E0-MCALM `HEAD`, its direct H parent, the
exact R base immediately behind H, and the complete historical
H-E0-MCALL/P-E0-MCALL/R-E0-MCALL chain. It never substitutes workspace status
for commit topology.

## Closed namespace after R publication

E0-MCALM preserves and extends the explicit MCALL coordination namespace. It
distinguishes required published finals, never-published finals, the current
owned pair, and forbidden coordination entries.

Exactly 20 published historical finals are required, regular, Git-bound, and
immutable: lock plus companion for each of E0-MCALP, E0-MCALC, E0-MCALD,
E0-MCALE, E0-MCALF, E0-MCALG, E0-MCALH, E0-MCALI, E0-MCALJ, and E0-MCALL.
They are authority inputs and are never forbidden coordination entries.

Exactly four never-published finals must remain absent: the base E0-MCAL lock
and companion and the E0-MCALK lock and companion. Before MCALM publication,
the current MCALM lock and companion must also be absent. After publication,
only those exact two current owned finals may be present in addition to the
20 historical finals.

The forbidden coordination set contains exactly 49 unique paths:

- lock and companion temporary paths for E0-MCAL, E0-MCALP, E0-MCALC,
  E0-MCALD, E0-MCALE, E0-MCALF, E0-MCALG, E0-MCALH, E0-MCALI, E0-MCALJ,
  E0-MCALK, E0-MCALL, and E0-MCALM: 26 paths;
- one locker guard for each of those same 13 gates: 13 paths;
- all eight R-output temporary paths: eight paths;
- the calibration run guard and the E7 run guard: two paths.

Every forbidden name must be absent at terminal-R reconstruction, prelock,
the publication baseline, while the exact owned MCALM guard is held except
for that guard, after guard release, during every ownership-transfer pass,
and twice during effective loading. Any regular file, symlink, directory,
FIFO, socket, stale temporary, foreign guard, or other filesystem entry at a
forbidden name fails closed. Required historical lock finals are not included
in the forbidden set.

All four E0-M final paths and the outcome-access log remain absent and are
recaptured with repository, namespace, and physical snapshots. Their absence
does not authorize their creation. E0-M requires a later explicit gate.

## Immutable R8 and exact companion

The exact six calibration files and exact two E7 files at R-E0-MCALL are
required as regular, single-link `100644` files whose physical bytes,
SHA-256, size, device, inode, link count, mtime, ctime, Git mode, Git blob,
and manifest/output bindings match the frozen R contract. Validation is local
and science-free. It must not follow or rehash scientific inventories, load a
Parquet, import dataframe engines for data access, or reopen any model,
prediction, target, holdout, or outcome input.

The P-E0-MCALM companion contains exactly 16 unique current physical inputs:
the two published P-E0-MCALL records, the six current H-E0-MCALM components,
and the eight published R outputs. It additionally contains exactly six
historical Git inputs for the superseded H-E0-MCALL component bytes and
exactly one lock output. The current MCALM locker appears exactly once as
top-level `script` and exactly once among current inputs. The companion is
canonical JSON and is published last.

## Lock publisher and effective loader

The publisher validates frozen verification evidence, exact H-over-R
topology, clean index/worktree, local refs and live remote before acquiring an
exclusive no-follow guard. It publishes through anchored parent descriptors,
an exclusive temporary identity, and hardlink no-clobber, with lock first and
companion last. It repeatedly revalidates all 16 physical identities, exact
R8 Git bindings, all 20 historical finals, all four never-published absences,
the complete 49-path coordination set, E0-M/outcome absence, refs, remote,
and both owned output identities before and after guard release. Failure
rolls back only still-owned MCALM inodes and never removes or rewrites a
foreign name, historical final, or R8 output.

The effective loader requires canonical lock and companion, exact
`16/6/1` bindings, P-E0-MCALM as clean current `HEAD`, H as its direct parent,
and R-E0-MCALL as H's exact direct parent. It separately reconstructs the
historical MCALL H/P/R chain and terminal R publication rather than invoking
a pre-R staging predicate. It snapshots and recaptures every physical input,
Git/ref/remote state, current owned output, namespace entry, E0-M path, and
outcome path before returning.

The effective terminal result must state that both bundles are completed and
published, that all eight R outputs are published, and that they are neither
ready nor authorized for staging. It may expose effective MCALM authority for
downstream validation, but it keeps scientific rerun, calibration, E7,
holdout, post-2021, outcome, E0-M, E0-U, DVC, staging, commit, and push
authorization false. The scientific run-namespace entrypoint remains
terminal and fail-closed.

## Check-only and verification

`--check-only` performs schema preflight and two read-only, science-free
captures of the exact H-over-R prelock state, the 16 physical inputs, the
published/absent/current namespace partitions, all 49 forbidden entries,
E0-M/outcome absence, refs, and live remote. It compares both captures and
writes nothing. It runs no type check, focused test, Poetry check, publication
guard, diff check, scientific inventory rebuild or rehash, DVC, staging,
commit, push, or scientific-network command.

`--execute-lock` captures the same prelock and physical state before running
only:

- the full `poetry run ty check`;
- the frozen MCALM governance and publication-assistant suite;
- `poetry check`;
- `scripts/check_repo_publication_ready.sh` with its exact success output;
- `git diff --check` with empty output.

The focused command is exactly:

```text
poetry run pytest -q tests/test_prepare_commit_artifacts.py tests/test_closure_final_calibration_r8_post_publication_authority_patch.py
```

The focused suite contains exactly 48 passing tests, with zero skipped and
zero deselected. The locker removes `PYTEST_ADDOPTS`, disables plugin
autoload, requires one exact terminal summary, and rejects warnings, skips,
deselections, xfails, xpasses, errors, and failures. Governance covers exact
R/H/P topology, the absence of any new R transaction, terminal loader state,
clean worktree/index, exact `16/6/1`, namespace `20/4/2/49`, R8 physical and
Git identity, no-clobber/rollback, lock-first/manifest-last, loader and
post-release races, and science/DVC/outcome/E0-M/staging/commit/push
tripwires.

After verification the locker requires schema, prelock, namespace, outcome,
all 16 physical identities, and all eight R identities to equal their first
captures. Only then may it build, validate, and publish the two P JSON files.
It never stages any path.

## Publication sequence and acceptance

1. Publish H-E0-MCALM `1M+5A` as a direct child of R-E0-MCALL
   `09309c2d16820f5d93fe9fd38dadef92377fd005`; no R file is included.
2. Under separate authorization, run `--check-only`; require
   `ready_to_lock`, exact terminal reconstruction, empty current pair, empty
   forbidden namespace, and zero writes or verification commands.
3. Under a new authorization, run `--execute-lock`; publish only lock first
   and companion last, leaving every R8 inode and byte unchanged.
4. Audit and publish exact P-E0-MCALM `2A`; require a clean repository, the
   public effective loader, and the still-empty 49-path forbidden namespace.
5. Stop at the manual barrier. E0-M remains unauthorized until a distinct
   explicit closure gate is designed, audited, and approved.

Acceptance requires exact base `09309c2...`, H `1M+5A`, P `2A`, no new R,
companion `16/6/1`, 20 published historical finals intact, four
never-published finals absent, the current pair absent-before/present-after,
all 49 coordination entries absent at every sealed checkpoint, E0-M and
outcome paths absent, R8 physical/Git identity unchanged, lock-first and
companion-last publication, science-free validation, and every scientific,
DVC, outcome, E0-M, staging, commit, and push authorization false.
