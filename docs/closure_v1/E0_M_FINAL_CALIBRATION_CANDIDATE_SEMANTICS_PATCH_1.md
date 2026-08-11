# E0-MCALC — final-calibration candidate-semantics patch 1

## Status and exact scope

`H-E0-MCALC` is a corrective, additive authority over the published
`P-E0-MCALP` commit
`6b74440e31d67a6b1a26609347639ae2ba33ec01`. That commit is the exact child
of `H-E0-MCALP` at
`59225001a8b1c006213b6a3d963126a6b3f73ccf`; neither published authority is
rewritten. The new H scope is exactly `4M+5A`:

- modified: `src/experiments/calibrate_closure_final_models.py`,
  `src/experiments/run_closure_anfis_learning_curve.py`,
  `tests/test_calibrate_closure_final_models.py` and
  `tests/test_closure_anfis_learning_curve.py`;
- added:
  `configs/closure_v1/final_calibration_candidate_semantics_patch_lock.schema.json`,
  this document,
  `src/experiments/closure_final_calibration_candidate_semantics_patch.py`,
  `src/experiments/lock_closure_final_calibration_candidate_semantics_patch.py`
  and `tests/test_closure_final_calibration_candidate_semantics_patch.py`.

The nine H-E0-MCALP components are reconstructed as five preserved physical
inputs and four superseded Git blobs. Both exact P-E0-MCALP JSON files remain
physical inputs. The nine current H-E0-MCALC components are physical inputs.
The new completion companion is therefore exact `16 physical + 4 historical
+ 1 output`.

A future `P-E0-MCALC` is one direct, non-merge child of H-E0-MCALC and adds
exactly:

- `reports/closure_v1/00_protocol/final_calibration_candidate_semantics_patch_lock.json`;
- `reports/closure_v1/00_protocol/final_calibration_candidate_semantics_patch_lock_manifest.json`.

The future R scope remains the same eight lightweight files: six calibration
outputs followed by two E7 outputs. H, P and R add no Parquet, model,
checkpoint, `.dvc` or outcome-log path.

## Consumed attempt and exact contradiction

The first authorized calibration one-shot under P-E0-MCALP was consumed once.
It passed authority and namespace gates, opened only the sealed development
inputs, and stopped with:

```text
E0-MCAL B0 raw scores text identity drifted: candidate
```

It failed before building or publishing any R member. The post-failure audit
found all eight R finals, all R temporaries and every calibration/E7 guard
absent, with Git clean. That invocation must not be retried under P-E0-MCALP.

The failure is a validator contradiction, not data corruption. The sealed B0
Parquet has 29,196 rows and the exact Arrow field
`candidate: string, nullable=false`. Every Pandas value is a Python `str`, and
every value is the empty sentinel `""`. The producer deliberately initializes
B0 and B1 with that sentinel and rejects non-empty candidates for both models.
The consumer nevertheless rejected every empty text value except
`failure_reason`; the synthetic regression had used the invented token
`registered`, masking the physical dialect.

P-E0-MCALP binds the unchanged B0 payload at SHA-256
`7b234e2e2893141d6c6a21367d4708f0f528790f38ca12f4da808926c00f83f3`
and 1,366,742 bytes, and its pointer at SHA-256
`854310b34ca0f1d28be226a65475cc67accd4108a7254b4d1c39ffdb0fd6e491`.
No source artifact is regenerated or reinterpreted.

## Closed candidate semantics

E0-MCALC admits exactly the producer-sealed mapping:

- B0: the sole candidate value is `""`;
- B1: the sole candidate value is `""`;
- B2: the exact set is `logistic_sgd` and
  `hist_gradient_boosting_classifier`;
- M0: the sole value is `mifal_ed_t2_v5_defaults`.

The empty sentinel is allowed only for B0/B1 `candidate` and for the already
defined successful-row `failure_reason`. A null, non-string, extra token,
missing B2 candidate, empty B2/M0 candidate or non-empty B0/B1 candidate fails
closed. The Arrow type/nullability checks, payload and pointer hashes, model
identity, seed/horizon sets, availability, selected-family logic, numeric
interval checks and input snapshot revalidation remain mandatory.

This patch changes no prediction, label, formula, seed, denominator,
calibrator, threshold, cutpoint, period or E7 terminal rule. The scientific
boundary remains WQP development-only through 2021-12. Holdout, post-2021,
outcome, E0-M, E0-U, DVC and scientific-network authorizations remain false.

## Authority, publication and lifecycle

The strict validator reconstructs P-E0-MCALP and H-E0-MCALP from Git, binds
the exact prior lock and companion, and partitions the four superseded runner
and focused-test blobs from the physical current successors. The P-E0-MCALC
companion contains:

- 16 unique physical inputs: five preserved H-E0-MCALP components, both
  P-E0-MCALP files and all nine H-E0-MCALC components;
- four historical inputs: the superseded calibration/E7 runners and their
  two focused-test modules;
- the current MCALC locker exactly once as top-level `script` and once in
  `inputs`;
- one output record for the MCALC lock;
- canonical `manifest_written_last=true`, with scientific execution, DVC and
  outcome access false.

Publication inherits the audited anchored/no-follow, exclusive guard,
hardlink no-clobber, `temp_identity`-only cleanup, joint identity checkpoint,
foreign-preserving rollback and non-fatal post-commit descriptor-close
semantics. The companion is the logical and physical completion marker.

The R lifecycle remains closed: `0 -> 6 -> 8`. Calibration is authorized only
at zero R outputs; E7 is authorized only after the exact six-file calibration
bundle; neither runner permits a retry after its own bundle exists. Partial
bundles, temporaries, guards, legacy P, outcome logs and E0-M outputs fail
closed before scientific I/O.

## Gates

1. Publish exact H-E0-MCALC as `4M+5A` over `6b74440…`.
2. Run the new locker with `--check-only`. Schema preflight is first; it
   reconstructs H/P history, candidate semantics, family/scientific inputs,
   empty new P/R namespaces, clean refs and live `origin/main`. It writes
   nothing and runs no tests, DVC, calibration, E7 or outcomes.
3. Under separate authorization, run `--execute-lock`. It may run only full
   `ty check`, the exact focused suite, `poetry check`, publication guard and
   `git diff --check`, then publish lock followed by companion.
4. Audit and publish exact P-E0-MCALC as `2A`; require effective loading before
   a newly authorized calibration attempt.
5. Execute calibration once, audit its exact six-file bundle, then execute E7
   once and publish the unchanged exact `8A` R scope.

Every execution requires a new explicit authorization. No old failed
invocation is reused. Git commit and Git push remain user-only operations.

## Acceptance criteria

- exact H `4M+5A`, P `2A`, R `8A`, with base P `6b74440…` and historical H
  `5922500…`;
- previous authority partition `5 preserved + 4 superseded`, prior P2
  preserved, and companion `16 physical + 4 historical + 1 output`;
- exact candidate mapping for B0/B1/B2/M0, including the B0/B1 empty sentinel;
- physical-schema regression uses producer-faithful candidate values and
  rejects every widened mapping;
- authority/loaders and both runners adopt only effective P-E0-MCALC;
- rollback/no-clobber regressions preserve foreign names and remove only exact
  owned identities;
- the consumed failure remains clean and cannot be retried under P-E0-MCALP;
- every holdout, post-2021, outcome, E0-M, E0-U, DVC and network boundary
  remains false.
