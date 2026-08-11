# E0-MCALP — final-calibration publication-guard patch 1

## Status and exact scope

`H-E0-MCALP` is a corrective authority over
`5d096e8ca560a592a65ab231ae173c4d3b5a4ff6`. Its direct parent must be that
published `H-E0-MCAL` commit. The H scope is exactly `4M+5A`:

- modified: `src/experiments/calibrate_closure_final_models.py`,
  `src/experiments/run_closure_anfis_learning_curve.py`,
  `tests/test_calibrate_closure_final_models.py` and
  `tests/test_closure_anfis_learning_curve.py`;
- added:
  `configs/closure_v1/final_calibration_publication_guard_patch_lock.schema.json`,
  this document,
  `src/experiments/closure_final_calibration_publication_guard_patch.py`,
  `src/experiments/lock_closure_final_calibration_publication_guard_patch.py`
  and `tests/test_closure_final_calibration_publication_guard_patch.py`.

The twelve original H-E0-MCAL components are reconstructed as eight preserved
physical inputs and four superseded Git blobs. The nine current H-E0-MCALP
components are physical inputs. The sets are disjoint by role and path.

The interrupted old `P-E0-MCAL` never existed and is not authority. Its lock,
companion, temporaries and guard remain absent. A future `P-E0-MCALP` is one
direct, non-merge child of H-E0-MCALP and contains exactly two additions:

- `reports/closure_v1/00_protocol/final_calibration_publication_guard_patch_lock.json`;
- `reports/closure_v1/00_protocol/final_calibration_publication_guard_patch_lock_manifest.json`.

The future R scope remains the exact eight lightweight E0-MCAL outputs: six
calibration files followed by two E7 files. No `.dvc`, Parquet, model,
checkpoint or outcome-log path belongs to H, P or R.

## Incident and correction boundary

An authorized old P-E0-MCAL launch was interrupted with `Ctrl-C`. The precise
verification phase reached by that process is indeterminate and no success
evidence from it is adopted. The subsequent audit found a clean worktree and
index and found every old P lock, companion, temporary, publication guard and
all eight R outputs absent. The invocation is consumed and must not be
retried on the old authority.

The audit also found a fail-closed violation in the inherited no-clobber
publisher. After linking its owned temporary inode to the final name, it read
the final name again and stored whatever identity was then observed. If an
adversary replaced the final name in that interval, cleanup treated the
foreign identity as owned and could unlink the foreign replacement.

E0-MCALP changes only publication governance:

1. the temporary inode identity, captured from its open descriptor, is the
   sole deletion authority;
2. after the exclusive hardlink, the final name must resolve to that exact
   temporary identity;
3. rollback may unlink the temporary or final name only while the name still
   resolves to that exact owned identity;
4. a missing, replaced, aliased, multiply linked, malformed or foreign entry
   fails closed, and every foreign replacement survives;
5. the completion companion remains the last publication and the only
   completion marker;
6. closing a temporary descriptor is part of publication, so a close failure
   before ownership transfer rolls back all owned names without leaking that
   descriptor; after the joint two-name linearization point, parent-descriptor
   cleanup is best-effort and cannot turn durable success into a failed call
   with an orphaned P bundle.

No model formula, seed, split, date boundary, denominator, target universe,
calibrator, threshold, cutpoint, E7 sample or terminal status changes. The
scientific boundary remains development-only through 2021-12. Holdout,
post-2021, E0-M, E0-U, outcome, DVC and scientific-network authorizations
remain false.

## Historical reconstruction and maximal companion

The strict validator reconstructs H-E0-MCAL from Git at `5d096e8…` without
calling its effective loader. The four superseded records are bound to that
commit, mode, byte count and SHA-256 and appear only in
`historical_inputs`. Their current physical successors must not be confused
with those historical blobs.

The P-E0-MCALP companion has one exact dialect:

- 17 unique physical `inputs`: eight preserved MCAL records plus all nine
  current MCALP components;
- four Git-bound `historical_inputs`: the superseded calibration/E7 runners
  and their two original focused-test modules;
- one top-level `script`: the current MCALP locker, also present exactly once
  in `inputs`;
- one `outputs` record: the MCALP lock;
- `manifest_written_last=true` and no scientific, DVC or outcome execution.

Omission, duplication, relocation, a role or mode change, a digest change,
or mixing a historical record into physical inputs invalidates the bundle.
Manifest-last is a logical, content-bound property: the exact canonical
companion records the exact lock and carries `manifest_written_last=true`.
It is deliberately not inferred from relative mtimes, which Git does not
preserve. Consequently an exact P bundle and exact Git-bound R bundle remain
valid after a fresh clone or recheckout with equal or inverted mtimes, while
any companion blob, record, hash or completion-marker drift fails closed.

## Gates and workflow

1. Publish exact H-E0-MCALP as `4M+5A` over `5d096e8…`.
2. Run the new locker with `--check-only`. Schema validation is first; it
   verifies exact parent/scope/blobs, the eight-preserved/four-superseded
   reconstruction, all scientific authorities, empty old/new P and R
   namespaces, clean refs and live `origin/main`. It writes nothing and runs
   no tests, DVC, calibration, E7 or outcomes.
3. Under a separate authorization, run `--execute-lock`. It may run only the
   full type check, the exact focused suite, `poetry check`, the repository
   publication guard and `git diff --check`. Git remote observation is gate
   network evidence, not scientific-network authorization.
4. Revalidate the complete prelock, then publish lock followed by companion
   through anchored no-follow directory descriptors, exclusive guard and
   temporaries, hardlink no-clobber, `temp_identity`-only cleanup and
   owned-inode rollback. Two joint identity passes and a final combined
   checkpoint precede ownership transfer, so substitution of the already
   validated lock while the companion is checked is detected.
5. Audit and publish exact P-E0-MCALP as `2A`, then require
   `--check-effective` before either runner can open scientific inputs.
6. Execute calibration once, audit it, then execute E7 once. Prepare and
   publish the unchanged exact `8A` R bundle only after both manifests pass
   strict manifest-last loading.

Each transition requires a separate authorization. A failure consumes only
that invocation and requires a new audit. H/P never execute calibration, E7,
DVC or outcomes; R never authorizes final E0-M or E0-U.

## Acceptance criteria

- exact H `4M+5A`, P `2A` and R `8A`, with zero overlap;
- original H reconstruction `8 preserved + 4 superseded`;
- maximal companion `17 physical + 4 historical + 1 output`, with the locker
  as top-level script and completion manifest written last;
- deterministic regression interposes the post-link substitution and proves
  the foreign final survives while every owned name is rolled back;
- deterministic regressions cover close failure before publication, foreign
  substitution between joint validation and ownership transfer, and a
  non-fatal parent-descriptor close failure after durable commit;
- existing finals, symlinks, hardlink aliases, occupied temporaries and
  identity drift fail closed without clobber;
- effective loading accepts exact P and Git-bound R bytes after fresh-clone
  timestamp normalization, recognizes only R lifecycle `0 -> 6 -> 8`, and
  rejects partial bundles, temporaries and active guards;
- schema, topology, strict loaders and both runners adopt only effective
  P-E0-MCALP;
- the interrupted phase remains indeterminate, old P remains absent and its
  invocation is never reused;
- all calibration/E7 scientific semantics and all downstream authorization
  boundaries remain unchanged.
