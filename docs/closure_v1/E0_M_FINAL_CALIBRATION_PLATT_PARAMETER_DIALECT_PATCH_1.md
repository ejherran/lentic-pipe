# E0-MCALJ — Final-calibration Platt-parameter dialect patch 1

## Status and authority

This document defines the additive `E0-MCALJ` authority for the serialized
Platt-calibrator parameter dialect. It changes no scientific input, target,
prediction, model, fit, solver, calibration-method selector, E7 method, or R
output path. Its published base is P-E0-MCALI commit
`fbbb9ebb8260c43146ce6407d6629c20ce8cf4d9`; the historical H-E0-MCALI
commit is `495ef14b2f110477318276755e7f6fc7d9ad2229`.

E0-MCALJ is a new gate. It does not restore the consumed E0-MCALI
authorization, and the failed invocation must not be retried under
P-E0-MCALI. Only a separately authorized one-shot under a published,
effective P-E0-MCALJ may begin another calibration attempt.

## Consumed incident and containment

The E0-MCALI calibration invocation passed its public authority and exact R0
namespace gates, opened only the sealed development surface, completed the
registered inference and calibration fits, and built the six-file calibration
payload. Its ordered transaction acquired its own calibration guard and
published the six files provisionally, with the manifest last. The private
owned-run revalidator then opened and semantically validated that provisional
bundle and stopped fail-closed with:

```text
E0-MCALII Platt parameters drifted
```

The incident is consumed and non-retryable under E0-MCALI. The ordered
transaction rolled back all six provisional outputs and its own guard. The
final containment state has zero calibration finals, zero E7 finals, zero R
temporaries, and zero active runner guards. P-E0-MCALI and every sealed
scientific input remain intact. The holdout, post-2021, outcome, E0-M, E0-U, DVC,
Git-publication, and scientific-network boundaries remain closed.

The closed incident record fixes
`phase=calibration_bundle_active_guard_scientific_output_validation` and
`failure_code=platt_parameter_input_literal_rejected_by_sealed_two_key_parser`.
It records scientific reads, ten ANFIS inference slots, calibration fitting,
payload construction, one owned guard, and six provisional finals before the
failure; rollback is complete and filesystem side-effect count is zero.
`authorization_consumed=true` and `retry_authorized=false` are immutable.

The doubled `MCALII` spelling is not another gate. The inner adapter first
translated a historical `E0-MCALH` validation error to `E0-MCALI`. An outer
catch then applied an unanchored replacement of the `E0-MCAL` prefix, which is
also the prefix of `E0-MCALI`, producing `E0-MCALII`. E0-MCALJ emits one
unambiguous `E0-MCALJ` prefix without repeated textual substitution.

## Root cause

The producer and consumer sealed incompatible representations at the initial
E0-MCAL implementation and every later overlay preserved both byte-for-byte.
For every selected `platt_logistic` refit, the producer serializes:

```json
{
  "coefficient": 0.0,
  "input": "raw_probability",
  "intercept": 0.0
}
```

where the two numeric values shown above stand only for finite fitted values.
The strict output validator instead required the key set to be exactly
`{"coefficient", "intercept"}`. It therefore rejected the additional,
producer-authored `input` discriminator before comparing or interpreting the
coefficient or intercept.

This is a representation-contract defect, not evidence that fitted Platt
parameters changed. The error text `parameters drifted` names the rejected key
set; no tolerance, dtype, coefficient, intercept, group-order, seed, horizon,
or solver comparison had run at that failure point. The first failing record
is simply the first selected Platt record encountered in the sealed
model/seed/horizon order; the incident does not establish that its numerical
fit differs from any prior computation.

The Platt implementation remains fixed: `LogisticRegression` with
`C=1_000_000.0`, solver `lbfgs`, intercept enabled, `max_iter=2000`,
`tol=1e-12`, and `random_state=1729`, under the runner's one-thread execution
policy. The selection tolerance remains exactly `0.001` Brier, followed by
ECE10 and the fixed simplicity order. None of these values is relaxed or
re-estimated by the patch. The existing execution policy still forbids a
bitwise-reproducibility claim across processes or BLAS backends; MCALJ does not
turn a representation fix into such a numerical claim.

## Exact Platt parameter contract

For a `platt_logistic` calibrator, the serialized `parameters` object has
exactly three keys:

- `coefficient`: one exact finite JSON float;
- `intercept`: one exact finite JSON float;
- `input`: the exact string `raw_probability`.

Extra keys, missing keys, non-float or non-finite numeric values, booleans,
integer substitutions, and any other input token fail closed. Identity keeps
the exact empty parameter object. Isotonic keeps its exact existing
`out_of_bounds`, `x_thresholds`, and `y_thresholds` contract.

The MCALJ validator first enforces this public three-key dialect. It then makes
an isolated deep copy, removes only the already-validated `input` field from
each Platt record in that copy, rewrites only the copied predecessor gate, and
passes the adapted copy to the historical semantic validator. The canonical R
bytes and caller object are never rewritten or mutated. Method-selection,
refit year, fit-row count, metrics, thresholds, group order, manifest hashes,
and all historical semantic checks remain active.

## Additive topology

H-E0-MCALJ is exactly `4M+5A` over P-E0-MCALI.

Modified successors:

- `src/experiments/calibrate_closure_final_models.py`;
- `src/experiments/run_closure_anfis_learning_curve.py`;
- `tests/test_calibrate_closure_final_models.py`;
- `tests/test_closure_anfis_learning_curve.py`.

Added components:

- `configs/closure_v1/final_calibration_platt_parameter_dialect_patch_lock.schema.json`;
- `docs/closure_v1/E0_M_FINAL_CALIBRATION_PLATT_PARAMETER_DIALECT_PATCH_1.md`;
- `src/experiments/closure_final_calibration_platt_parameter_dialect_patch.py`;
- `src/experiments/lock_closure_final_calibration_platt_parameter_dialect_patch.py`;
- `tests/test_closure_final_calibration_platt_parameter_dialect_patch.py`.

P-E0-MCALJ is exactly two additions: the canonical lock and companion under
`reports/closure_v1/00_protocol/`, both with stem
`final_calibration_platt_parameter_dialect_patch_lock`.

R retains the exact lifecycle `0 -> 6 -> 8`: the six unchanged calibration
files in `reports/closure_v1/03_calibration/`, followed by the two unchanged
E7 files in `reports/closure_v1/07_anfis_ablation/`.

Five non-runner H-E0-MCALI components are preserved physically, four runner
and test components are sealed as historical Git inputs and superseded, and
both P-E0-MCALI files remain physical predecessor inputs.

## Lock, companion, publisher, and loader

The companion contains exactly 16 unique physical inputs, four historical Git
inputs, and one lock output. The 16 are five preserved H-E0-MCALI components,
both P-E0-MCALI files, and all nine H-E0-MCALJ components. The locker appears
exactly once as top-level `script` and once in `inputs`.
`manifest_written_last=true`, `scientific_execution_run=false`,
`dvc_commands_run=false`, and `outcome_paths_opened=false` remain mandatory.

Publication and effective loading inherit MCALI's canonical frozen payload,
exclusive no-follow guard, anchored descriptors, hardlink no-clobber,
manifest-last publication, inode-bound rollback, repeated Git/ref/remote and
physical snapshots, exact R lifecycle, public-loader rejection of active
guards, and private capability-bound R0-to-R6 and R6-to-R8 revalidation. The
patch changes only the Platt representation adapter and error-prefix contract.

## Runner ordering and verification

Both runners import only E0-MCALJ. Each calls public authority and namespace
gates before runtime configuration or scientific I/O and retains MCALI's
private owned-run publication API. No alternate loader, tolerant validator,
or direct predecessor-global mutation is authorized.

The focused command covers the calibration runner, E7 runner, and this
governance module and reports exactly 48 passed tests with zero skipped or
deselected tests. Governance tripwires prohibit real scientific inventory,
Parquet, target, outcome, DVC, and scientific-network access. Regressions must
prove exact-three acceptance, exact-two/extra/wrong-token/non-finite rejection,
copy-only adaptation, historical semantic retention, and a single MCALJ error
prefix. Full `ty check`, `poetry check`, publication guard, schema preflight,
and `git diff --check` are mandatory.

## Publication sequence and acceptance

1. Publish exact H-E0-MCALJ `4M+5A` as a direct child of P-E0-MCALI.
2. Run the MCALJ locker `--check-only` under separate authorization; it writes
   nothing and runs no verification command.
3. Under another authorization, run `--execute-lock`; it may run only the
   frozen checks and publish the canonical P2 bundle.
4. Audit and publish exact P-E0-MCALJ `2A`, then require its public effective
   loader with no active guard.
5. Only then may one newly authorized calibration one-shot run. Stop on any
   failure without retry. E7 remains separately authorized after exact R6.

Acceptance requires exact base `fbbb9ebb...`, historical H `495ef14...`, H
`4M+5A`, P `2A`, R `8A`, companion `16/4/1`, exact-three Platt parameters,
copy-only historical adaptation, one MCALJ error prefix, all inherited
publication/loading/race boundaries, science-free focused 48, and all
scientific/publication authorizations false in P. Git commit and Git push
remain manual user-only barriers.
