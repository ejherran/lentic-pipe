# E0-MCALF — Final-calibration raw-exclusion evidence patch 1

## Status and authority

This document defines the additive `E0-MCALF` authority that repairs the
raw-score exclusion evidence dialect without changing a scientific input,
model, prediction, calibration algorithm, E7 algorithm, or R output path.  It
is based on published P-E0-MCALE commit
`79e799343e06d718797b61e8eee44d4af42bb1ca`.  The historical H-E0-MCALE
commit is `068dd7622db30953a2b1c6bd1c21ebc60a22efa5`.

E0-MCALF is a new gate.  It does not restore the consumed E0-MCALE calibration
authorization, and the failed invocation must never be retried under
P-E0-MCALE.  Only a separately authorized run under a published, effective
P-E0-MCALF may start another one-shot calibration attempt.

## Consumed incident

The E0-MCALE one-shot passed authority and namespace gates, opened the sealed
development-only scientific inputs, and completed the ten A0/A1 inference
slots.  `build_final_calibration_bundle` then failed at its first pure check:

```text
E0-MCAL raw exclusion evidence drifted: B0
```

The failure preceded calibration-frame validation, fitting, output
serialization, guard acquisition, temporary creation, and publication.  The
repository remained at exact R0: six calibration finals, two E7 finals, all
R temporaries, and both runner guards were absent.  No holdout, post-2021,
outcome, E0-M, E0-U, DVC, Git, or scientific-network boundary was opened.
Scientific reads and A0/A1 inference did occur.  The authorization is
consumed and `retry_authorized=false`.

## Root cause

The producer is internally consistent.  For every raw-score source it filters
both development roles, `model_selection` and `calibration_threshold`, over
target months `2019-01..2021-12`, then projects those candidate rows onto the
2,646 complete target keys.  The one-seed B0/M0 candidate universe is 4,140
rows: 2,646 matched and 1,494 incomplete.  The five-seed B1/B2 universes are
the exact fivefold replication: 20,700 candidates, 13,230 matched, and 7,470
incomplete.

The predecessor validator instead froze `2931=2646+285` and its fivefold
form.  The value 285 is only the incomplete `calibration_threshold` partition
(`957=672+285`), while its matched value 2,646 includes both roles.  It omitted
the 1,209 incomplete `model_selection` rows (`3183=1974+1209`).  Thus the old
tuple mixed scopes; no physical data, score, or target identity drifted.

All 1,494 excluded rows are unique target keys with `input_eligible=true` and
`complete_targets_evaluable=false`.  The producer sorts their exact
`source_id|site_id|origin_year_month|target_year_month|horizon_months` strings
and hashes canonical JSON `{"keys":[...]}` with one terminal newline.  The
closed digest is:

```text
e56ce749c2787097b878fc7a44350797521d143cbb08322c9537cdd905c0dfd9
```

## Exact raw exclusion evidence dialect

The first `input_filter_evidence` record remains the exact 16-key target
scan/projection contract published by P-E0-MCALE, including
`8743=2646+6097`, 121 sites, the sealed site digest, month ranges, and zero
boundary/holdout counts.  E0-MCALF changes only the following four records.

Each raw record has exactly six keys and no others:

```text
model_id
source_path
candidate_row_count
matched_target_row_count
excluded_incomplete_target_row_count
excluded_target_keys_sha256
```

The records are ordered B0, B1, B2, M0 and have these exact values:

| model | candidate | matched | excluded | source |
| --- | ---: | ---: | ---: | --- |
| B0 | 4140 | 2646 | 1494 | `data/closure_v1/development/baselines/B0/raw_scores.parquet` |
| B1 | 20700 | 13230 | 7470 | `data/closure_v1/development/baselines/B1/raw_scores.parquet` |
| B2 | 20700 | 13230 | 7470 | `data/closure_v1/development/baselines/B2/raw_scores.parquet` |
| M0 | 4140 | 2646 | 1494 | `data/closure_v1/development/mifal/M0/raw_scores.parquet` |

Every record uses the exact digest above.  Identities, paths, and digest are
nonempty exact JSON strings.  Counts are exact non-boolean JSON integers and
must satisfy `candidate=matched+excluded`.  The digest is equality-bound, not
merely checked as 64 hexadecimal characters.  The old 2,931/285 and
14,655/1,425 tuples, a foreign well-formed digest, bool-as-int, reordered or
missing models, an added key, a changed path, and every arithmetic mismatch
fail closed.

## Additive topology

H-E0-MCALF is exactly `4M+5A` over P-E0-MCALE:

Modified historical successors:

- `src/experiments/calibrate_closure_final_models.py`;
- `src/experiments/run_closure_anfis_learning_curve.py`;
- `tests/test_calibrate_closure_final_models.py`;
- `tests/test_closure_anfis_learning_curve.py`.

Added overlay components:

- `configs/closure_v1/final_calibration_raw_exclusion_evidence_patch_lock.schema.json`;
- `docs/closure_v1/E0_M_FINAL_CALIBRATION_RAW_EXCLUSION_EVIDENCE_PATCH_1.md`;
- `src/experiments/closure_final_calibration_raw_exclusion_evidence_patch.py`;
- `src/experiments/lock_closure_final_calibration_raw_exclusion_evidence_patch.py`;
- `tests/test_closure_final_calibration_raw_exclusion_evidence_patch.py`.

P-E0-MCALF is exactly two additions:

- `reports/closure_v1/00_protocol/final_calibration_raw_exclusion_evidence_patch_lock.json`;
- `reports/closure_v1/00_protocol/final_calibration_raw_exclusion_evidence_patch_lock_manifest.json`.

R remains the unchanged ordered lifecycle `0 -> 6 -> 8`:

- `reports/closure_v1/03_calibration/calibrator_specs.json`;
- `reports/closure_v1/03_calibration/calibration_metrics.csv`;
- `reports/closure_v1/03_calibration/alert_thresholds.csv`;
- `reports/closure_v1/03_calibration/ordinal_cutpoints.csv`;
- `reports/closure_v1/03_calibration/model_availability.csv`;
- `reports/closure_v1/03_calibration/final_calibration_manifest.json`;
- `reports/closure_v1/07_anfis_ablation/anfis_learning_curve.csv`;
- `reports/closure_v1/07_anfis_ablation/anfis_learning_curve_manifest.json`.

The five non-runner H-E0-MCALE components are preserved physically.  Its four
runner/test components are retained as historical Git inputs and superseded
by the four current files.  Both P-E0-MCALE files remain physical inputs.

## Lock and companion

The P companion contains exactly:

- 16 unique physical inputs: five preserved H-E0-MCALE components, both
  P-E0-MCALE files, and all nine H-E0-MCALF components;
- four historical Git inputs: the superseded calibration/E7 runners and
  their two tests;
- one output record for the E0-MCALF lock;
- the current locker exactly once as top-level `script` and once in
  `inputs`;
- `manifest_written_last=true`, `scientific_execution_run=false`,
  `dvc_commands_run=false`, and `outcome_paths_opened=false`.

The lock remains canonical JSON and `locked_unpublished`.  Every unpublished
calibration, E7, holdout, post-2021, outcome, E0-M, E0-U, DVC, Git, and
scientific-network authorization remains false.

Publication inherits the frozen-payload semantic reconstruction, anchored
parent descriptors, no-follow exclusive guard, hardlink no-clobber,
`temp_identity`-only cleanup, lock-first/companion-last order, repeated
branch/HEAD/tracking/live-remote and physical snapshots, joint output
metadata/identity checkpoints, foreign-preserving rollback, and non-fatal
post-commit descriptor close.  There is no fallible operation after the
declared ownership-transfer linearization that may turn a valid P2 into an
orphaned failure result.

Effective loading inherits canonical/schema/semantic reconstruction,
fresh-clone-safe Git bindings, the transitive predecessor authority, exact
static absence boundaries, repeated R lifecycle and repository checkpoints,
live-remote checks, and full P metadata linearization.  It validates the new
four-record raw evidence contract locally, preserves the predecessor 16-key
target contract, never mutates a historical module global, and never delegates
the incorrect predecessor raw-count literals.

## Runner ordering and boundaries

Both runners import only the effective E0-MCALF authority.  Calibration must
call `require_final_calibration_authority` and then
`require_final_calibration_run_namespace` before configuring the runtime,
opening any scientific payload, performing inference, or resolving an output
parent.  E7 follows the same gate order and is unavailable until the exact
six-file calibration bundle exists.

The calibration producer preserves the physical scanner audit and exact target
projection, computes the four raw exclusion records from the same membership
mask used for the target join, and validates target plus raw evidence before
calibration-frame validation or fitting.  The old 2,931/285 and
14,655/1,425 records are rejected by the producer, builder, P authority,
effective loader, and R loader.

Partial output groups, any temporary, any runner/locker guard, legacy P,
outcome log, or E0-M output fail closed before scientific I/O.  No gate in
this overlay authorizes DVC, network science, Git commit, Git push, holdout,
post-2021, outcome, E0-M, or E0-U access.

## Verification and gates

The exact focused command covers the calibration runner, E7 runner, and this
governance module and must report exactly 48 passed tests with zero skipped or
deselected tests.  Full `ty check`, `poetry check`, publication guard, and
`git diff --check` are also mandatory publication evidence.

1. Publish exact H-E0-MCALF `4M+5A` as a direct child of P-E0-MCALE
   `79e7993…`.
2. Under separate authorization, run the new locker with `--check-only`.
   It performs schema and prelock reconstruction only and writes nothing.
3. Under another authorization, run `--execute-lock`; it may run only the
   frozen checks and publish the canonical P2 bundle.
4. Audit and publish exact P-E0-MCALF `2A`, then require its effective loader.
5. Only then may a newly authorized calibration one-shot run.  On any
   failure, stop again without retry.  E7 remains separately authorized after
   the exact six calibration outputs.

Git commit and Git push remain manual user-only barriers throughout.

## Acceptance criteria

- exact base P `79e7993…`, historical H `068dd76…`, H `4M+5A`, P `2A`,
  R `8A`, and companion `16/4/1`;
- consumed E0-MCALE incident sealed with reads/inference true, no retry, and
  finals/temporaries/guards all zero;
- predecessor target equation `8743=2646+6097` remains unchanged;
- exact raw equations `4140=2646+1494` and
  `20700=13230+7470`, exact common exclusion digest, paths, order, keys, and
  scalar types;
- explicit rejection of the old 2,931/285 and 14,655/1,425 records and every
  partial, foreign-digest, mistyped, or arithmetically inconsistent variant;
- producer, builder, lock validator, effective loader, and R loader agree on
  one raw exclusion evidence dialect;
- runner authority and namespace gates precede every scientific read and
  output action;
- no-clobber, rollback, fresh-clone, loader lifecycle, namespace, and race
  regressions remain closed;
- no data, model, scientific output, DVC pointer, or historical authority is
  rewritten by H or P.
