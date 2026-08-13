# E0-MID: locked-evaluation input-manifest dialect patch

## Purpose and authority boundary

E0-MID is an additive publication-assistant compatibility overlay over the
published P-E0-MIC commit
`707fbe92c7147d281c2a272178289e948a137b1b`. It changes no locked-evaluation
input, origin, feature, sequence, Arrow schema, row, pointer, summary, manifest,
target, outcome, model, metric, calibration output, or E7 output byte.

The sole purpose of E0-MID is to let the generic publication assistant adopt
three known manifest-dialect findings only after the strict MIC validator has
accepted the exact already-materialized historical R-E0-MI bundle. E0-MID does
not revive the consumed input-bundle producer authorization, authorize another
DVC add or push, authorize evaluation, E0-M, E0-U, outcome access, staging
outside the exact R scope, Git commit, or Git push.

## Consumed incident and fail-closed result

The one-shot R-E0-MI producer completed under published P-E0-MIC. Four
directed DVC registrations then completed with return code zero. The
publication assistant staged the exact four pointers, summary, and manifest;
its Git add and publication check returned zero, DVC status remained `{}`, and
no DVC push, Git commit, or Git push ran.

The assistant subsequently returned one and wrote:

```text
tmp/pre_commit_artifacts_20260813T143904Z.md
```

That report has SHA-256
`d843c34f2260f8f5a7a0745492099265a44a85c9240956589a8caf9b219d8aef`.
Its only non-OK findings are the following exact three records:

```text
FAIL manifest reports/closure_v1/01_surface/locked_evaluation_input_manifest.json
Experiment manifest status is `completed_unpublished`, expected `completed`.

FAIL manifest reports/closure_v1/01_surface/locked_evaluation_input_manifest.json
Experiment manifest must contain a non-empty `outputs` list.

FAIL manifest reports/closure_v1/01_surface/locked_evaluation_input_summary.json
Staged report artifact is not listed in any experiment manifest output.
```

The MIC transaction validator ran both before and after report generation. It
required the exact staged six-file scope, live remote authority, panel DVC
identity, four physical outputs, four pointers, summary, manifest,
manifest-last ordering, and a complete input-only semantic rebuild. Either
strict failure would have stopped with return code two. The observed return
code one therefore records a generic representation mismatch after strict
validation, not scientific, DVC, transactional, or byte drift.

## Root cause and exact adoption

The generic assistant accepts an experiment lifecycle status of `completed`
and discovers report coverage through a non-empty top-level `outputs` list.
The sealed input-bundle dialect intentionally uses:

- `status=completed_unpublished` while the R commit has not been published;
- `physical_outputs`, containing four exact Parquet records;
- `summary`, containing the exact path, byte count, and SHA-256 of the summary;
- `manifest_written_last=true`.

Those keys are required by the strict E0-MIC/E0-MIB contract. Changing the
status to `completed`, adding a duplicate generic `outputs` representation, or
rewriting either JSON would invalidate the one-shot bundle and its exact
semantic reconstruction.

E0-MID therefore leaves the generic validator unchanged. Its adapter may run
only for the exact adoption gate R-E0-MID six-addition scope under an effective
published P-E0-MID authority. It must first run the unchanged generic checks,
then require all of the following:

- the non-OK result is the exact three-finding multiset above, including
  severity, check kind, path, and complete message;
- there is no missing, additional, duplicate, reordered-as-duplicate, changed,
  downgraded, or newly introduced non-OK finding;
- the four pointer records and all generic DVC structure checks pass;
- index and worktree contain exactly the six authorized `100644` additions;
- all ten restored R files retain their sealed path, type, mode, link count,
  device, inode, size, bytes, hashes, and manifest relationships;
- the effective MID/MIC authority, live refs and remote, source identities,
  physical predecessor snapshot, strict R validation, summary binding,
  manifest-last contract, and input-only false flags all pass again.

Only after those predicates pass may the adapter remove the exact three known
generic failures and add one explicit E0-MID OK result. Any other finding or
state remains a failure. The adapter never suppresses an unrelated manifest,
DVC, freeze, output-coverage, scope, authority, namespace, or physical finding.

## Exact R10 containment

After the blocked assistant, the six staged entries were removed from the
index and all ten R files were archived by same-filesystem rename under the
ignored containment root
`tmp/r_e0_mi_manifest_dialect_blocked_20260813T143904Z/`. The live R namespace
is absent. Rename preserved every inode, byte, mode, link count, and mtime.
The producer is consumed and must never be rerun; the four DVC pointers are
already final and DVC add must never be repeated.

The strict R digest is
`2b1e89ffa6816ad3bbaa8e1e8c5122b6b0b014dfc4645886443ffabe84036c17`.
All ten records are regular `0644`, have link count one, and are on device
`2069`:

| Original path | Bytes | SHA-256 | Inode |
| --- | ---: | --- | ---: |
| `data/closure_v1/locked_evaluation/input_history.parquet` | 480855 | `70b25305b861467a0c253abc9bb44f5038120341dfe77a8143560dc05eb391c0` | 77866321 |
| `data/closure_v1/locked_evaluation/intent_origins.parquet` | 171047 | `de6be0c7a8eefa282f7db25510373801d0839249fbbbb8c6c62188b80ce2d578` | 77866322 |
| `data/closure_v1/locked_evaluation/origin_features.parquet` | 238955 | `8099942097f5544d35ecee9640e68ec2be79dbf0f17483b3c5c64b963d252d6d` | 77866323 |
| `data/closure_v1/locked_evaluation/sequence_features.parquet` | 436677 | `b5f37c326ef19852a96ebf970970e4be60006a0dc0d21a3181b918e7a3a2f1a7` | 77866324 |
| `data/closure_v1/locked_evaluation/input_history.parquet.dvc` | 103 | `a479daefc0a3ba596dbd06350eefd991eeeda00857d8ea423a535547f1632077` | 77866327 |
| `data/closure_v1/locked_evaluation/intent_origins.parquet.dvc` | 104 | `943900d54a0f99fef5c72c6341edb28c8dffd5831fcc2c2b34ae4527888e27ff` | 77866329 |
| `data/closure_v1/locked_evaluation/origin_features.parquet.dvc` | 105 | `5cc90a4cb90796a6c96f57a745e9a72fb325ecd92816a1314c0321ef69fee851` | 77866330 |
| `data/closure_v1/locked_evaluation/sequence_features.parquet.dvc` | 107 | `ad5b266d68098365350f3d8532a3f4bba1b12a85b3a90dda93a6205f83f0c46b` | 77866331 |
| `reports/closure_v1/01_surface/locked_evaluation_input_summary.json` | 443 | `217b495f811517a0c3f94cc6f98910175f54c4b017dc4fd81efd7691326b9ea0` | 77072772 |
| `reports/closure_v1/01_surface/locked_evaluation_input_manifest.json` | 20049 | `c8d7b4f0f207f217eb0289cbc3563877c0ffd592dc41120559d7a24ddd6a03df` | 77072773 |

The four pointers retain the exact registered MD5/size pairs
`d02d1b0b94f740ce990d06a7a949b09c/480855`,
`b9bad06b799f342f9bf54eb0a2cbec7a/171047`,
`da118c0515bdbd9705539bce1305bf11/238955`, and
`f858efff8a4c2e25f4c5b287258f0176/436677`, in frozen physical-output order.

The ignored archive is containment evidence, not a second scientific bundle
or a Git input. H/P code must not copy, normalize, relink, chmod, touch, stage,
or decode it. Before P publication it may compare only the sealed archive
metadata needed to prove that live R is absent and the same ten owned entries
remain contained. Archive content validation occurs only at the separately
authorized restoration boundary.

## Additive topology and exact scopes

The gate is `E0-MID`; its module stem is
`closure_locked_evaluation_input_manifest_dialect_patch`.

H-E0-MID is the direct non-merge child of P-E0-MIC and has exact scope
`1M+5A`.

The sole modification is:

- `src/data/prepare_commit_artifacts.py`.

The five additions are:

- `configs/closure_v1/locked_evaluation_input_manifest_dialect_patch_lock.schema.json`;
- this document;
- `src/experiments/closure_locked_evaluation_input_manifest_dialect_patch.py`;
- `src/experiments/lock_closure_locked_evaluation_input_manifest_dialect_patch.py`;
- `tests/test_closure_locked_evaluation_input_manifest_dialect_patch.py`.

P-E0-MID is the direct non-merge child of H and contains exactly two `100644`
additions:

- `configs/closure_v1/locked_evaluation_input_manifest_dialect_patch_lock.json`;
- `configs/closure_v1/locked_evaluation_input_manifest_dialect_patch_lock_manifest.json`.

The restored publication uses the new gate `R-E0-MID` and exact tracked scope
`6A`:

- four `.parquet.dvc` pointers in frozen physical-output order;
- `reports/closure_v1/01_surface/locked_evaluation_input_summary.json`;
- `reports/closure_v1/01_surface/locked_evaluation_input_manifest.json`, last.

This R is adoption-only. It consists solely of the restored archived bytes; it
is not a new producer run, DVC registration, transformation, normalization, or
scientific result.

## Companion and historical preservation

The P companion is canonical JSON with exact cardinality `16/6/1`:

- 16 current physical inputs: published P-E0-MIC's two JSON files, H-E0-MID's
  six components, and the eight immutable final-calibration/E7 outputs;
- six historical Git inputs: H-E0-MIC's exact superseded component blobs;
- one output: the E0-MID lock JSON.

Each set is sorted and duplicate-free. Current inputs bind exact path, mode,
SHA-256, size, and Git identity where applicable; historical inputs are rebuilt
from their published Git objects. The MID locker appears once as companion
`script` and once among current inputs. The companion is published last and
records no scientific execution, R touch, R restoration, DVC command, outcome
access, staging, commit, or push.

## H/P locker behavior

`--check-only` performs schema preflight, exact base/H topology, clean Git
scope, aligned local/tracking/live-remote refs, namespace closure, predecessor
`16/6/1` reconstruction, and immutable final-calibration/E7 snapshot checks.
It captures the prelock state twice and compares both captures. For R it is
strictly metadata-only: live R10 must be absent, the exact archive entries must
remain contained, and no archived Parquet, pointer, summary, or manifest byte
may be opened or decoded. Check-only writes nothing and runs no type check,
pytest, Poetry check, publication guard, diff check, producer, strict R rebuild,
DVC, staging, commit, push, or scientific-network command.

`--execute-lock` begins from the same metadata-only state and brackets all
verification with repeated prelock, namespace, archive-metadata, and immutable
physical-input captures. It may run only:

```text
poetry run ty check
poetry run pytest -q tests/test_prepare_commit_artifacts.py tests/test_closure_locked_evaluation_input_manifest_dialect_patch.py
poetry check
scripts/check_repo_publication_ready.sh
git diff --check
```

The focused command is frozen at exactly `48 passed`, zero skipped, zero
deselected, and no warning, xfail, xpass, error, or failure dialect. The locker
removes `PYTEST_ADDOPTS`, disables third-party pytest plugin autoload, and
requires one exact terminal summary. Governance tripwires forbid producer,
Parquet decoder, target, outcome, evaluation, DVC, restoration, staging,
commit, push, and scientific-network calls.

After verification, any prelock, ref, namespace, archive metadata, schema, or
physical predecessor drift fails before publication. The publisher acquires
an exclusive no-follow guard, rejects every pre-existing final or temporary,
publishes lock first and companion manifest last through hardlink no-clobber,
revalidates at every publication and release boundary, and rolls back only
still-owned P inodes. It may create only the exact P pair. It never restores,
opens, stages, or rewrites an R file.

## Effective authority and restoration barrier

The effective loader requires published P-E0-MID as clean HEAD, exact direct
H/P topology and scopes, canonical lock and companion, exact `16/6/1`, aligned
live remote, no active guard or temporary, and unchanged predecessor outputs.
It accepts only a wholly absent or exact complete live R10 namespace. It keeps
evaluation, E0-M, E0-U, outcome access, producer execution, DVC add/push, Git
commit, and Git push false. While live R is absent it keeps R adoption false.
The effective loader is fresh-clone capable and does not inspect ignored local
containment; it exposes no restoration authorization flag.

Restoration is a separate manual mutation requiring explicit authorization
from the user after P publication and an independent local archive audit. It
is not implied or authorized by the loader. It must use same-filesystem renames
from the exact archive records back to their original paths; publish the
manifest last; preserve every inode, byte, mode, link count, device, and mtime;
and leave exactly the four physical ignored files plus six untracked
publication candidates. It must not copy, touch, chmod, relink, regenerate,
run the producer, run DVC add, or run DVC push. An incomplete, foreign, or
drifted namespace fails closed for audit and is never silently repaired.

After restoration, strict MID/MIC validation may open the permitted
assignment/panel sources and restored input-only R bundle to reconstruct it
exactly. It still may not open any target, target-availability, outcome,
prediction, metric, E0-M, or E0-U path. The publication assistant may then
stage only exact R-E0-MID `6A`, run no DVC add, and adopt only the exact three
generic findings. Commit and push remain manual user-only barriers. The old
R-E0-MI route is not eligible because it owns the already-consumed producer
and directed-DVC-registration transaction. Only after the exact restored R10
is present and the strict loader accepts its complete state may effective MID
authority report R-E0-MID adoption true.

## Acceptance sequence

1. Publish H-E0-MID `1M+5A` as the direct child of `707fbe92c...`; do not
   include or restore any R path.
2. Run `--check-only` under separate authorization. It must return
   `ready_to_lock`, equal metadata-only captures, live R absent, and zero
   writes or verification/scientific/DVC commands.
3. Under a new authorization, run `--execute-lock`; require the frozen
   verification result and exact lock-first/manifest-last P2 publication.
4. Audit, precommit, publish, and independently reload exact P-E0-MID before
   touching the archive.
5. Under a new explicit authorization, restore the exact R10 by manifest-last
   same-filesystem rename. Do not rerun the producer or DVC add.
6. Audit the restored identities and strict semantics. Under another explicit
   authorization, run the publication assistant for exact R-E0-MID `6A`;
   require the exact-three adoption and no other finding.
7. Keep Git commit and Git push as separate manual user actions. E0-M, E0-U,
   evaluation, and outcome access remain unauthorized after R publication.

Acceptance requires exact base `707fbe92c...`, H `1M+5A`, P `2A`, adoption-only
R `6A`, companion `16/6/1`, report and R10 seals above, generic behavior
unchanged outside exact R, metadata-only H/P, no-clobber P publication,
manifest-last restoration and R publication, strict semantic reconstruction,
and every producer-rerun, DVC, outcome, E0-M/E0-U, evaluation, commit, and push
authorization false unless separately granted at its named manual barrier.
