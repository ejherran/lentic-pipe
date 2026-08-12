# E0-MCALK — Final-calibration R8 manifest reproducibility patch 1

## Status and authority

This document defines the additive `E0-MCALK` authority for the publication
assistant's interpretation of the already materialized Closure V1 R8
manifests. It changes no scientific input, target, prediction, calibrator,
selected method, coefficient, intercept, metric, threshold, cutpoint,
availability decision, ANFIS fit, E7 terminal record, CSV value, or R output
byte.

The published base is P-E0-MCALJ commit
`97f12b00b952829474a2937dccba6add783df074`. Its direct historical H authority
is `05e846cfc3804a35f7550d6a2de9687b4450568d`, whose parent is
`fbbb9ebb8260c43146ce6407d6629c20ce8cf4d9`. E0-MCALK is a new gate. It does
not revive the consumed R8 precommit invocation and does not authorize a
calibration or E7 rerun.

## Consumed precommit incident and containment

The R8 science run completed once under published P-E0-MCALJ and produced the
exact six-file calibration bundle followed by the exact two-file E7 bundle.
Both strict MCALJ output-group validators accepted the canonical files and
their scientific semantics. The subsequent publication assistant invocation
at report `tmp/pre_commit_artifacts_20260812T180346Z.md` stopped fail-closed
after `git add -A` because its generic experiment-manifest dialect rejected
the two sealed lifecycle statuses.

The report records these two failures:

```text
Experiment manifest status is `completed_unpublished`, expected `completed`.
Experiment manifest status is `terminal`, expected `completed`.
```

It also records one generating-script warning for each manifest. The
publication guard passed; all six pre-manifest output records were covered;
their byte counts and SHA-256 bindings passed; DVC status was empty; no DVC
add, DVC push, Git commit, or Git push ran. Containment restores the exact
eight R files to the unpublished R8 namespace. They remain ordinary
untracked publication candidates with their original bytes and inodes. They
must not be regenerated, normalized, copied, moved, touched, or staged before
the separately authorized E0-MCALK publication workflow reaches its R gate.

## Root cause: generic dialect, not bundle drift

`src/data/prepare_commit_artifacts.py` classifies any JSON below `reports/`
whose basename contains `manifest` as an experiment manifest, except for a
small closed set of special cases. Both R8 manifests therefore enter the
generic branch. That branch accepts only an absent status or
`status=completed` and warns when a top-level `script` record is absent.

The two R8 manifests intentionally use different exact contracts:

- `reports/closure_v1/03_calibration/final_calibration_manifest.json` uses
  schema `closure_final_calibration_manifest_v1`, experiment
  `closure_v1`, gate `E0-MCALJ`, status `completed_unpublished`, exactly 97
  input records, exactly five pre-manifest output records, and no top-level
  `script`;
- `reports/closure_v1/07_anfis_ablation/anfis_learning_curve_manifest.json`
  uses schema `closure_anfis_learning_curve_manifest_v1`, experiment `E7`,
  gate `E0-MCALJ`, status `terminal`, exactly 15 input records, exactly one
  pre-manifest output record, and no top-level `script`.

Both bind the same effective MCALJ authority SHA-256. Their exact output
paths, order, record keys, canonical JSON, scientific boundary, counts,
execution policy, sample evidence, CSV semantics, and physical hashes are
already required by the sealed MCALJ strict output-group validator. Changing
either status to `completed`, adding a `script` field, or otherwise rewriting
either manifest would violate that public contract. The failed precommit is
therefore a representation mismatch in the generic assistant, not evidence
of R8 scientific, transactional, or byte drift.

## Exact compatibility adapter

E0-MCALK adds one fail-closed compatibility adapter at the generic
publication boundary. The generic classifier, ordinary `completed` dialect,
unmanaged-heavy policy, DVC behavior, and all unrelated manifest handling
remain unchanged.

Adoption is permitted only when all of the following are true:

- the exact published P-E0-MCALK authority is effective;
- the staged name-status scope is exactly the eight R8 additions and has no
  extra, missing, modified, deleted, renamed, or copied path;
- both canonical manifests occupy their exact paths and retain their exact
  schema, experiment, gate, lifecycle status, key set, input and output
  record dialect, cardinality, order, scientific boundary, and common
  authority binding;
- all eight physical outputs are regular, safe, unchanged, and match the
  bytes and SHA-256 values fixed by the manifests and the P prelock;
- the underlying generic validator emits only the exact two known status
  failures and exact two known missing-script warnings, while all output
  coverage and physical binding checks pass.

Only that exact four-finding multiset may be adopted. A missing finding,
duplicate, changed severity, changed path, changed status, unexpected warning,
additional failure, output drift, alternate manifest path, or non-exact R8
scope fails closed. A successful adoption replaces only those four known
generic findings with one explicit MCALK reproducibility result; it does not
pretend that the generic dialect itself changed and does not suppress any
unrelated finding.

The absence of top-level `script` is not missing provenance. The published
MCALJ authority, exact runner components, manifest input inventories, and the
new MCALK historical/current Git bindings close the provenance chain without
mutating the caller or either R8 manifest.

## Additive topology and immutable R8

H-E0-MCALK is the direct non-merge child of P-E0-MCALJ and has exact scope
`1M+5A`.

The sole modification is:

- `src/data/prepare_commit_artifacts.py`.

The five additions are:

- `configs/closure_v1/final_calibration_r8_manifest_reproducibility_patch_lock.schema.json`;
- this document;
- `src/experiments/closure_final_calibration_r8_manifest_reproducibility_patch.py`;
- `src/experiments/lock_closure_final_calibration_r8_manifest_reproducibility_patch.py`;
- `tests/test_closure_final_calibration_r8_manifest_reproducibility_patch.py`.

P-E0-MCALK is exactly two `100644` additions under
`reports/closure_v1/00_protocol/`, with stem
`final_calibration_r8_manifest_reproducibility_patch_lock`: the canonical
lock and its companion manifest.

R remains exactly eight `100644` additions in its fixed order: six
calibration paths, manifest last within that group, followed by the E7 CSV and
its manifest last. H and P must accept those eight files as an exact untracked
R8 snapshot. Check-only, verification, lock construction, validation, and
publication must compare their byte, SHA-256, mode, device, inode, link-count,
and path identities. None may stage, move, rewrite, chmod, relink, or touch an
R8 file.

## Lock, companion, publisher, and loader

The P companion contains exactly 16 unique current physical inputs, one
historical Git input for the superseded publication-assistant bytes, and one
lock output. The current MCALK locker appears exactly once as top-level
`script` and exactly once in `inputs`. The companion is canonical JSON and
requires `manifest_written_last=true`, `scientific_execution_run=false`,
`r8_files_touched=false`, `r8_files_staged=false`, `dvc_commands_run=false`,
and `outcome_paths_opened=false`.

The locker inherits the established exclusive no-follow guard, anchored
directory descriptors, regular-file and link-count checks, hardlink
no-clobber publication, lock-first/manifest-last ordering, inode-owned
rollback, schema preflight, repeated Git/ref/remote reconstruction, and
post-verification snapshot equality. Publication may create only the two P
JSON files. Failure rolls back only owned P inodes and leaves all eight R8
inodes untouched.

Before publication the authority remains false. The public loader requires
the exact published P commit, direct H/P topology, exact scopes and modes,
canonical lock and companion, exact `16/1/1` bindings, no active guard, and
the still-identical eight-file R8 snapshot. It authorizes only the exact R8
publication-assistant adoption. It never authorizes science, a runner, a
retry, DVC, outcome access, Git staging, Git commit, or Git push.

## Check-only and verification

`--check-only` performs schema, topology, namespace, authority, and immutable
R8 snapshot validation only. Its read-only authority reconstruction may run
Git topology, tracking-ref, and live-remote-ref checks. It writes nothing and
runs no type-check, focused-test, Poetry, publication-guard, Git-diff
verification, science, DVC, or scientific-network command.

`--execute-lock` first captures the full P prelock and eight-file R8 identity
snapshot. It may then run only:

- the full `poetry run ty check`;
- the frozen focused MCALK governance and publication-assistant adapter suite;
- `poetry check`;
- `scripts/check_repo_publication_ready.sh` with its exact success output;
- `git diff --check` with empty output.

The focused command is exactly:

```text
poetry run pytest -q tests/test_prepare_commit_artifacts.py tests/test_closure_final_calibration_r8_manifest_reproducibility_patch.py
```

The focused pytest environment removes `PYTEST_ADDOPTS`, disables plugin
autoload, requires one exact `48 passed` terminal summary, and rejects skipped,
deselected, xfailed, xpassed, warning, error, or failed summaries. Governance
tripwires forbid invocation of calibration, E7, Parquet, target, outcome, DVC,
scientific network, staging, commit, or push code. The prelock and all R8
physical identities must be identical before and after verification and again
at publication.

## Publication sequence and acceptance

1. Preserve the current exact R8 files and publish H-E0-MCALK `1M+5A` as a
   direct child of P-E0-MCALJ. Do not include any R8 path in H.
2. Run the MCALK locker `--check-only` under separate authorization. It must
   return `ready_to_lock` with zero writes and zero verification commands.
3. Under a new authorization run `--execute-lock`. It may execute only the
   frozen checks and publish lock first, companion last, without touching R8.
4. Audit and publish exact P-E0-MCALK `2A`; then require the public effective
   loader with no active guard.
5. Only under another explicit authorization may the publication assistant
   stage the already-existing exact R8 `8A`. It must not run calibration or
   E7, and Git commit and Git push remain manual user-only barriers.

Acceptance requires exact base `97f12b0...`, predecessor H `05e846c...`, H
`1M+5A`, P `2A`, R `8A`, companion `16/1/1`, exact two-manifest semantic and
physical validation, exact-four-finding adoption, unchanged generic behavior
outside that closed scope, immutable R8 bytes and inodes, lock-first and
manifest-last P publication, science-free verification, and every scientific,
DVC, outcome, commit, and push authorization false in P. The unpublished lock
payload keeps R8 staging false; only the exact published effective authority
may return the closed exact8A publication-assistant permission.
