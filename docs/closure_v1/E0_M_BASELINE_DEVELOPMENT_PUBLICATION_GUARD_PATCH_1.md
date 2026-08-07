# E0-MQ — Closure V1 baseline publication-guard authority

## Status and exact scope

`H-E0-MQ` is a corrective authority over
`7f4099644c53e0b56d6af1adf62a0d107ade4d3a`. Its direct parent must be that
published `H-E0-MP` commit and its scope is exactly seven paths: the baseline
runner and its test are modified, while this document, the E0-MQ schema,
validator, locker and focused test are added. The scientific runtime contract
in `configs/closure_v1/baseline_development_runtime.yaml` remains the immutable
E0-MP contract.

`P-E0-MP` never existed and is not an authority. Its lock, companion,
temporaries and guards must remain absent. A future `P-E0-MQ` is a direct,
non-merge child of H-E0-MQ and contains exactly two additions:

- `reports/closure_v1/00_protocol/baseline_development_publication_guard_patch_lock.json`;
- `reports/closure_v1/00_protocol/baseline_development_publication_guard_patch_lock_manifest.json`.

Until that exact P commit is published and passes `--check-effective`, every
execution authorization remains false.

## Correction boundary

E0-MQ corrects only two publication-governance defects discovered before any
baseline execution:

1. the E0-MP locker expected a publication-guard message that the repository
   command does not emit; E0-MQ accepts the single exact success marker
   `OK: tracked files look publication-ready.` and rejects missing, repeated,
   ambiguous or failure evidence;
2. the E0-MP companion omitted the top-level generating-script record required
   by the generic manifest verifier; E0-MQ includes the current locker as
   `script` while retaining the same record once in the physical input list.

No runtime formula, feature, seed, cutoff, denominator, output schema, fit
policy or selection rule changes. B0, B1 and B2 remain the development-only
batch defined in E0-MP: both origin and target cutoffs are at or before
2020-12; calibration, holdout evaluation, E0-M, E0-U and post-2021 outcomes
remain inaccessible. The one-shot namespace still reserves 69 potential
finals, 69 temporaries, three future raw-score DVC pointers and their three
temporaries. All must be absent at H/P lock time. DVC registration is a later,
separately authorized operation.

## Historical reconstruction and companion

The E0-MQ validator reconstructs H-E0-MP without invoking an effective E0-MP
loader. The six unchanged MP components are current physical inputs. The MP
runner and runner test are reconstructed from Git at `7f409964…` and appear
only in `historical_inputs`; current bytes are not required to match those two
superseded blobs.

The future companion is maximal and exact:

- 53 unique physical `inputs`: 40 runtime pins, six preserved MP components
  and all seven current H-E0-MQ components;
- two Git-bound `historical_inputs`: the superseded MP runner and runner test;
- one top-level `script`: the current E0-MQ locker record, also present once in
  `inputs`;
- one `outputs` record: the E0-MQ lock.

Relocating, omitting, duplicating or changing a role, commit, byte count or
digest in either input section is invalid. The companion is written last and
is the only completion marker.

## Gate and transaction workflow

1. Publish exact H-E0-MQ as `2M+5A` over H-E0-MP.
2. Run `--check-only`. Schema validation is the first gate. It verifies exact
   H topology, current and historical bindings, the 40 runtime pins, empty
   namespaces, clean refs and live `origin/main`; it writes nothing and runs
   no tests, DVC, auditor, baseline science or outcomes.
3. Under separate authorization, run `--execute-lock`. It may run only the
   full type check, the exact 69-test focused suite with zero skips or
   deselections, `poetry check`, the publication guard and
   `git diff --check`. Read-only Git remote verification is recorded as gate
   network evidence; scientific network authorization remains false.
4. The locker revalidates the prelock after those commands, publishes the lock
   and then the companion using no-follow directory descriptors, exclusive
   guards and temporaries, hardlink no-clobber and owned-inode rollback.
5. Audit and publish exact P-E0-MQ as `2A`, then run `--check-effective`.
6. Only an effective P-E0-MQ may enable the baseline one-shot and B0/B1/B2
   flags. Calibration, E0-M, evaluation, E0-U, DVC, scientific network,
   outcomes and every future authorization remain false.

A failed one-shot consumes its authorization and must be audited before any
new attempt. H/P themselves never execute the baseline, DVC, an auditor or an
outcome read.
