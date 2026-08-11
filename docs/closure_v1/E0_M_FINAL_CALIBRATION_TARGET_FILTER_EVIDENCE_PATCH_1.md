# E0-MCALE — Final-calibration target-filter evidence patch 1

## Status and authority

This document defines the additive `E0-MCALE` authority that repairs the
target-filter evidence dialect without changing any scientific input, model,
prediction, denominator, calibration algorithm, E7 algorithm, or output path.
It is based on published P-E0-MCALD commit
`56e8096a605a9de099af17a71db7d6b199e660b5`.  The historical H-E0-MCALD
commit is `8e8e0a0acca3f93603be7434ecb9ebbfeac34630`.

The patch is a new gate.  The consumed E0-MCALD calibration authorization is
not restored and the failed invocation must never be retried under P-E0-MCALD.
Only a separately authorized run under a published, effective P-E0-MCALE may
start a new one-shot calibration attempt.

## Consumed incident

The E0-MCALD one-shot reached the development-only scientific readers and the
A0/A1 inference path, then failed closed at the first pure builder check with:

```text
E0-MCAL target filter evidence drifted
```

The failure occurred before calibration fitting, output serialization, guard
acquisition, temporary creation, or final publication.  The repository
therefore remained at exact R0: six calibration finals, two E7 finals, all
their temporaries, and both runner guards were absent.  No holdout,
post-2021, outcome, E0-M, E0-U, DVC, or scientific-network boundary was
opened.  Scientific input reads and A0/A1 inference did occur.  The
authorization is consumed and `retry_authorized=false`.

## Root cause

The physical target producer and anchored PyArrow scanner were correct.  The
scanner applies the sealed predicate to 121 eligible development sites and
materializes 8,743 unique target keys.  The subsequent exact inner join to
the complete common-origin universe retains 2,646 unique keys and excludes
6,097 scanner keys:

```text
8743 = 2646 + 6097
```

All 2,646 projected keys exist in the scanner result.  The scanner result has
zero duplicate keys and the closed target-year partition is 3,121 rows for
2019, 2,839 for 2020, and 2,783 for 2021.  Its month ranges are origin
`2018-10..2021-11` and target `2019-01..2021-12`; boundary and holdout counts
are both zero.

The runner correctly recorded `materialized_row_count=len(scanner_frame)`,
which is 8,743.  The historical evidence validator instead compared that
field with the post-projection denominator 2,646.  The synthetic historical
fixture repeated the same category error and used 353 assigned development
sites rather than the 121 eligible sites actually supplied to this scanner.
No physical data or scientific result drift caused the failure.

## Exact target evidence dialect

The first `input_filter_evidence` record has exactly these 16 keys and no
others:

```text
role
scanner
predicate
projection
materialized_row_count
projected_complete_target_row_count
outside_common_origin_projection_row_count
row_count_equation
minimum_origin_year_month
maximum_origin_year_month
minimum_target_year_month
maximum_target_year_month
boundary_crossing_rows
holdout_rows_materialized
development_site_count
development_site_ids_sha256
```

Their closed values are:

```text
role = target_predicate_scan_and_common_origin_projection
scanner = pyarrow_dataset_anchored_fd_predicate_pushdown
predicate = source_id=wqp AND site_id IN development AND origin<=2021-12 AND 2019-01<=target<=2021-12
projection = exact_common_origin_key_inner_join
materialized_row_count = 8743
projected_complete_target_row_count = 2646
outside_common_origin_projection_row_count = 6097
row_count_equation = materialized_row_count=projected_complete_target_row_count+outside_common_origin_projection_row_count
minimum_origin_year_month = 2018-10
maximum_origin_year_month = 2021-11
minimum_target_year_month = 2019-01
maximum_target_year_month = 2021-12
boundary_crossing_rows = 0
holdout_rows_materialized = 0
development_site_count = 121
development_site_ids_sha256 = 42ece001484bdfa38ef8ac849e7b085ba14f244ee89f7a11474f377de721dea5
```

Every count is an exact non-boolean JSON integer.  Every identity, method,
predicate, equation, month, and digest is an exact JSON string.  The digest
is computed from canonical JSON `{"site_ids": sorted_unique_sites}` with one
terminal newline.  The count equation must hold arithmetically as well as
textually.  A record that reuses the old value 2,646 as
`materialized_row_count`, swaps the two denominators, accepts `bool` as an
integer, changes a range or zero, uses a merely well-formed foreign digest,
or adds/removes a key fails closed.

The four raw-score exclusion records retain their exact existing dialect and
counts:

- B0 and M0: `2931 = 2646 + 285`;
- B1 and B2: `14655 = 13230 + 1425`.

Their integer and SHA-256 fields remain exact typed values.  E0-MCALE changes
only the interpretation and sealing of the first target evidence record.

## Additive topology

H-E0-MCALE is exactly `4M+5A` over P-E0-MCALD:

Modified historical successors:

- `src/experiments/calibrate_closure_final_models.py`;
- `src/experiments/run_closure_anfis_learning_curve.py`;
- `tests/test_calibrate_closure_final_models.py`;
- `tests/test_closure_anfis_learning_curve.py`.

Added overlay components:

- `configs/closure_v1/final_calibration_target_filter_evidence_patch_lock.schema.json`;
- `docs/closure_v1/E0_M_FINAL_CALIBRATION_TARGET_FILTER_EVIDENCE_PATCH_1.md`;
- `src/experiments/closure_final_calibration_target_filter_evidence_patch.py`;
- `src/experiments/lock_closure_final_calibration_target_filter_evidence_patch.py`;
- `tests/test_closure_final_calibration_target_filter_evidence_patch.py`.

P-E0-MCALE is exactly two additions:

- `reports/closure_v1/00_protocol/final_calibration_target_filter_evidence_patch_lock.json`;
- `reports/closure_v1/00_protocol/final_calibration_target_filter_evidence_patch_lock_manifest.json`.

R remains the unchanged ordered lifecycle `0 -> 6 -> 8`:

- `reports/closure_v1/03_calibration/calibrator_specs.json`;
- `reports/closure_v1/03_calibration/calibration_metrics.csv`;
- `reports/closure_v1/03_calibration/alert_thresholds.csv`;
- `reports/closure_v1/03_calibration/ordinal_cutpoints.csv`;
- `reports/closure_v1/03_calibration/model_availability.csv`;
- `reports/closure_v1/03_calibration/final_calibration_manifest.json`;
- `reports/closure_v1/07_anfis_ablation/anfis_learning_curve.csv`;
- `reports/closure_v1/07_anfis_ablation/anfis_learning_curve_manifest.json`.

The five non-runner H-E0-MCALD components are preserved physically.  Its four
runner/test components are retained as historical Git inputs and superseded
by the four current files.  Both P-E0-MCALD files remain physical inputs.

## Lock and companion

The P companion contains exactly:

- 16 unique physical inputs: five preserved H-E0-MCALD components, both
  P-E0-MCALD files, and all nine H-E0-MCALE components;
- four historical Git inputs: the superseded calibration/E7 runners and
  their two tests;
- one output record for the E0-MCALE lock;
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
16-key evidence dialect locally and never mutates a historical module global
or delegates the incorrect historical `2646-as-materialized` literal.

## Runner ordering and boundaries

Both runners import only the effective E0-MCALE authority.  Calibration must
call `require_final_calibration_authority` and then
`require_final_calibration_run_namespace` before configuring the runtime,
opening any scientific payload, performing inference, or resolving an output
parent.  E7 follows the same gate order and is unavailable until the exact
six-file calibration bundle exists.

The calibration producer records the physical scanner audit, adds the exact
common-origin projection evidence, validates all 16 keys and their exact
types before calibration work, and serializes that same evidence into the
manifest.  The old 2,646-as-materialized record is rejected by the producer,
builder, P authority, effective loader, and R loader.

Partial output groups, any temporary, any runner/locker guard, legacy P,
outcome log, or E0-M output fail closed before scientific I/O.  No gate in
this overlay authorizes DVC, network science, Git commit, Git push, holdout,
post-2021, outcome, E0-M, or E0-U access.

## Verification and gates

The exact focused command covers the calibration runner, E7 runner, and this
governance module and must report exactly 48 passed tests with zero skipped or
deselected tests.  Full `ty check`, `poetry check`, publication guard, and
`git diff --check` are also mandatory publication evidence.

1. Publish exact H-E0-MCALE `4M+5A` as a direct child of P-E0-MCALD
   `56e8096…`.
2. Under separate authorization, run the new locker with `--check-only`.
   It performs schema and prelock reconstruction only and writes nothing.
3. Under another authorization, run `--execute-lock`; it may run only the
   frozen checks and publish the canonical P2 bundle.
4. Audit and publish exact P-E0-MCALE `2A`, then require its effective loader.
5. Only then may a newly authorized calibration one-shot run.  On any
   failure, stop again without retry.  E7 remains separately authorized after
   the exact six calibration outputs.

Git commit and Git push remain manual user-only barriers throughout.

## Acceptance criteria

- exact base P `56e8096…`, historical H `8e8e0a0…`, H `4M+5A`, P `2A`,
  R `8A`, and companion `16/4/1`;
- consumed E0-MCALD incident sealed with reads/inference true, no retry, and
  finals/temporaries/guards all zero;
- exact target equation `8743=2646+6097`, 121 sites, sealed site digest,
  projection method, ranges, zeros, keys, and scalar types;
- explicit rejection of the old 2,646-as-materialized record and every
  partial, foreign, mistyped, or arithmetically inconsistent variant;
- producer, builder, lock validator, effective loader, and R loader agree on
  one target evidence dialect;
- runner authority and namespace gates precede every scientific read and
  output action;
- no-clobber, rollback, fresh-clone, loader lifecycle, namespace, and race
  regressions remain closed;
- no data, model, scientific output, DVC pointer, or historical authority is
  rewritten by H or P.
