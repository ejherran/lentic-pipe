# E0-MCALL — Final-calibration R8 coordination-namespace revalidation patch 1

## Status and authority

This document defines the additive `E0-MCALL` authority that closes the
post-release and effective-loader coordination-namespace race found during
P-E0-MCALK readiness review. It does not change the published E0-MCALK
manifest adapter, either R8 manifest dialect, or any scientific output byte.

The published base is H-E0-MCALK commit
`6f078da52c5dd699ea312df209bfef5a8d120d00`, whose direct parent is the
published P-E0-MCALJ commit
`97f12b00b952829474a2937dccba6add783df074`. H-E0-MCALL must be a direct,
non-merge child of that H-E0-MCALK base. E0-MCALL supersedes only MCALK's
coordination-namespace publication and loading boundary; MCALK remains the
historical authority for the exact generic-manifest compatibility adapter,
the immutable R8 contract, and its failed-precommit containment.

No calibration, E7, outcome, holdout, post-2021, DVC, retry, commit, or push
authority is created by this overlay.

## Root cause and failure boundary

The MCALK publisher validated its complete namespace while its own publication
guard was held. After publishing lock first and companion last, it released
that guard and performed two ownership-transfer passes over physical inputs,
Git/ref/remote state, and the two owned outputs. Those passes did not repeat
the complete coordination-namespace check. A historical locker guard could
therefore appear after release without changing Git status or any sealed
physical input.

The MCALK effective loader also checked its own guard, its two output
temporaries, and the calibration/E7 run guards, but omitted at least the
historical MCALJ locker guard and did not recapture the complete namespace at
the end of loading. An ignored coordination entry could consequently survive
the publisher boundary or appear during loading even though all scientific
bytes and Git bindings remained valid.

This is a coordination-observability defect, not scientific, R8, manifest,
history, or data corruption. The exact eight R outputs remain immutable and
must not be regenerated, copied, moved, normalized, touched, or rewritten.

An authorized MCALK `--check-only` attempt was interrupted during a read-only
rehash of the historical scientific inventory, last observed at
`data/fuzzy/state_vector_v0.parquet`. It had not started publication, created
a guard, written a file, consumed the lock authorization, changed R8, invoked
DVC, or opened outcomes. E0-MCALL seals that attempt as superseded and does not
repeat it. Historical P-E0-MCALJ validation for this coordination overlay is
Git-only: it parses canonical Git and physical lock/companion bytes, validates
their closed schema, verification, authorization, topology, modes, OIDs,
hashes, and mutual bindings, but it does not rebuild or rehash the historical
scientific input inventory. The lock records
`historical_scientific_inputs_rehashed=false`.

## Complete closed namespace contract

E0-MCALL defines one explicit, deduplicated, lexicographically ordered
coordination namespace. It must not inherit a partial predecessor tuple by
accident. The contract distinguishes valid published historical finals from
coordination entries that must always be absent.

The following 18 published historical lock finals are required, regular,
Git-bound, and immutable: lock plus companion for each of E0-MCALP,
E0-MCALC, E0-MCALD, E0-MCALE, E0-MCALF, E0-MCALG, E0-MCALH, E0-MCALI, and
E0-MCALJ. They are authority inputs and are never classified as forbidden
coordination entries.

The base E0-MCAL lock and companion were never published and must remain
absent. The E0-MCALK lock and companion were also never published and must
remain absent. Before MCALL lock publication, the new MCALL lock and companion
must be absent; after publication, only those two owned finals may be present.

The closed forbidden coordination set contains:

- the lock and companion temporary path for E0-MCAL, E0-MCALP,
  E0-MCALC, E0-MCALD, E0-MCALE, E0-MCALF, E0-MCALG, E0-MCALH,
  E0-MCALI, E0-MCALJ, E0-MCALK, and E0-MCALL;
- one locker guard for each of those same twelve gates;
- all eight R-output temporary paths;
- the calibration run guard and the E7 run guard.

That is exactly 46 unique coordination paths: 24 lock temporaries, 12 locker
guards, eight R temporaries, and two scientific run guards. Every member must
be absent at prelock, at the publication baseline, while the owned MCALL guard
is held except for that exact owned guard, after guard release, in each
ownership-transfer pass, and twice during effective loading. An absent path
must remain absent; a regular file, symlink, directory, FIFO, socket, stale
temporary, foreign guard, or any other filesystem entry at a forbidden name
fails closed.

The outcome-access log and final E0-M/E0-U namespaces remain absent and are
outside the set of valid historical lock finals.

## Additive topology and immutable R8

H-E0-MCALL has exact scope `1M+5A`.

The sole modification is:

- `src/data/prepare_commit_artifacts.py`.

The five additions are:

- `configs/closure_v1/final_calibration_r8_coordination_namespace_revalidation_patch_lock.schema.json`;
- this document;
- `src/experiments/closure_final_calibration_r8_coordination_namespace_revalidation_patch.py`;
- `src/experiments/lock_closure_final_calibration_r8_coordination_namespace_revalidation_patch.py`;
- `tests/test_closure_final_calibration_r8_coordination_namespace_revalidation_patch.py`.

P-E0-MCALL is exactly two `100644` additions under
`reports/closure_v1/00_protocol/`, with stem
`final_calibration_r8_coordination_namespace_revalidation_patch_lock`: the
canonical lock and its companion manifest.

R remains the same exact eight `100644` additions fixed by published MCALK:
six calibration outputs with their manifest last, followed by the E7 CSV and
its manifest last. H and P must leave all eight untracked. Every check,
verification step, publication checkpoint, loader checkpoint, and precommit
adapter revalidation compares their exact path, bytes, SHA-256, mode, device,
inode, link count, size, mtime, and ctime. E0-MCALL never stages or mutates an
R8 file.

The generic precommit validator still runs first. Only the exact MCALK
four-finding multiset —two known lifecycle-status failures and two known
missing-script warnings— may be adopted after strict output validation. No
other finding is suppressed.

## Lock, companion, publisher, and loader

The P companion contains exactly 16 unique current physical inputs: the two
published P-E0-MCALJ records, six current H-E0-MCALL components, and eight
immutable R8 outputs. It additionally contains exactly six historical Git
inputs for the superseded H-E0-MCALK component bytes and exactly one lock
output. The current MCALL locker appears exactly once as top-level `script`
and exactly once among current inputs. The companion is canonical JSON and is
published last.

The publisher validates the frozen verification evidence and exact H/remote
authority before acquiring an exclusive no-follow guard. It publishes through
anchored parent descriptors, one exclusive temporary identity, hardlink
no-clobber, lock first and companion last. It repeatedly revalidates all 16
physical identities, the full 46-path coordination contract, Git/ref/live
remote state, and both owned output identities before and after guard release.
Each ownership-transfer pass must include the namespace checkpoint. Failure
rolls back only still-owned MCALL inodes and never removes or rewrites a
foreign name or any R8 output.

The public loader requires canonical lock and companion, exact published H/P
topology and scopes, exact `16/6/1` bindings, all required historical finals,
the exact R8 bundle, and the complete coordination namespace. It snapshots
the absence contract before semantic reconstruction, recaptures all physical
and owned identities, then repeats the same absence contract and publication
validation before returning. A path appearing, disappearing, changing type,
or changing identity during loading fails closed.

Only the exact published P-E0-MCALL authority may authorize the existing R8
publication-assistant staging transaction. It authorizes no science, runner,
retry, DVC, outcome access, Git commit, or Git push.

## Check-only and verification

`--check-only` performs schema preflight and read-only reconstruction of the
published H base, historical finals, complete namespace, MCALK adapter
contract, R8 bundle, physical identities, local refs, and live remote. It runs
no type check, focused test, Poetry check, publication guard, diff check,
scientific inventory rebuild or rehash, DVC, staging, commit, push, or
scientific-network command, and it writes nothing.

`--execute-lock` first captures the complete prelock and exact 16-file
physical snapshot. It may then run only:

- the full `poetry run ty check`;
- the frozen MCALL governance and publication-assistant suite;
- `poetry check`;
- `scripts/check_repo_publication_ready.sh` with its exact success output;
- `git diff --check` with empty output.

The focused command is exactly:

```text
poetry run pytest -q tests/test_prepare_commit_artifacts.py tests/test_closure_final_calibration_r8_coordination_namespace_revalidation_patch.py
```

The focused suite contains exactly 48 passing tests, with zero skipped and
zero deselected. The locker removes `PYTEST_ADDOPTS`, disables plugin
autoload, requires one exact terminal summary, and rejects warnings, skips,
deselections, xfails, xpasses, errors, and failures. Governance includes exact
namespace cardinality/membership, valid historical-final preservation,
never-published-final absence, prelock and post-release race injection,
effective-loader race injection, no-clobber/rollback, exact `16/6/1`, R8
identity, H/P/R staging order, generic-first exact-four adoption, and all
science/DVC/outcome/commit/push tripwires.

After verification, the locker requires the schema, prelock, full namespace
snapshot, all 16 physical identities, and all eight R8 identities to equal
their pre-verification values. Only then may it build, validate, and publish
the two P JSON files.

## Publication sequence and acceptance

1. Publish H-E0-MCALL `1M+5A` as a direct child of H-E0-MCALK
   `6f078da52c5dd699ea312df209bfef5a8d120d00`; exclude R8.
2. Under separate authorization, run `--check-only`; require
   `ready_to_lock`, exact empty coordination namespace, and zero writes or
   verification commands.
3. Under a new authorization, run `--execute-lock`; publish only lock first
   and companion last, with R8 unchanged.
4. Audit and publish exact P-E0-MCALL `2A`; require the public effective
   loader and a still-empty 46-path coordination namespace.
5. Only under another explicit authorization may the publication assistant
   stage exact R8 `8A`. Commit and push remain manual user-only barriers.

Acceptance requires exact base `6f078da...`, H `1M+5A`, P `2A`, R `8A`,
companion `16/6/1`, all 18 historical finals present and intact, MCAL/MCALK
never-published finals absent, all 46 coordination entries absent at every
sealed checkpoint, R8 bytes and inodes unchanged, lock-first/manifest-last
publication, science-free verification, and every scientific, DVC, outcome,
commit, and push authorization false.
