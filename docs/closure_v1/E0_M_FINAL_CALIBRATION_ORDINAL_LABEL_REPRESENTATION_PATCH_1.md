# E0-MCALG — Final-calibration ordinal-label representation patch 1

## Status and authority

This document defines the additive `E0-MCALG` authority that repairs the
nullable integer representation of normalized ordinal labels. It changes no
scientific input, target, score, model, calibration method, E7 method, or R
output path. Its published base is P-E0-MCALF commit
`11a130809c2ad5d37c100e681d1f7a03c611603d`; the historical H-E0-MCALF
commit is `12099beebe63997403aa086820d1a059498d23e3`.

E0-MCALG is a new gate. It does not restore the consumed E0-MCALF calibration
authorization. The failed invocation must not be retried under P-E0-MCALF.
Only a separately authorized one-shot under a published, effective
P-E0-MCALG may start another calibration attempt.

## Consumed incident and containment

The E0-MCALF invocation passed authority and namespace gates, opened only the
sealed development scientific surface, and completed ten A0/A1 inference
slots. The pure normalized-frame validator then stopped with exit 2:

```text
E0-MCAL ordinal labels must be exact integer classes
```

The closed incident is:

- `attempted_gate=E0-MCALF`;
- `status=failed_closed_no_outputs`;
- `phase=normalized_calibration_frame_validation`;
- `failure_code=ordinal_label_nullable_integer_representation_drift`;
- `authorization_consumed=true` and `retry_authorized=false`;
- scientific reads and ten inference slots occurred;
- calibration fitting and bundle construction did not occur;
- finals, temporaries, active guards, and filesystem side effects are zero.

The failure preceded output serialization, guard acquisition, temporary-file
creation, and publication. The six calibration finals, two E7 finals, all R
temporaries, and both runner guards remain absent. The holdout, post-2021,
outcome, E0-M, E0-U, DVC, Git publication, and scientific-network boundaries
remain closed.

## Root cause

The physical inputs satisfy their contracts. B0, B1, and B2 raw scores are
Arrow `double`, nullable, and become Pandas `float64`; ordinal class labels are
not stored in those score columns. The target source column
`target_trophic_state_h` is Arrow `large_string`; the producer accepts only
the four sealed trophic-state strings and maps them exactly to integer classes
0, 1, 2, and 3.

The baseline normalizer emitted `ordinal_label` as NumPy `int8` for B0, B1,
and B2, but emitted scalar `np.nan` for the non-ordinal M0 rows. The A0 and A1
selection and inference producers also emitted `np.nan`. Pandas therefore
promoted the mixed column to `float64` during concatenation. Selecting the
B0/B1/B2 rows afterwards preserves that column dtype, even when every value
is numerically integral. The exact-type validator correctly rejected the
result; no scientific value or physical Arrow schema drifted.

The historical fixtures concealed this mismatch by explicitly replacing the
already mixed synthetic column with `pd.array(..., dtype="Int8")`. Producer
tests checked row counts and evidence but did not assert the dtype after the
real producer concatenation, while the one-shot test substituted the input
loader with that pre-normalized fixture.

## Exact representation contract

The normalized prediction surface has one nullable integer representation:

- column name `ordinal_label`;
- Pandas extension dtype exactly `Int8`;
- B0, B1, and B2 values are non-null exact integer classes in `{0,1,2,3}`;
- M0, A0, and A1 values are all `pd.NA`;
- ordinal applicability is unchanged and `ordinal_score` remains a bounded
  floating score only for B0/B1/B2;
- the four trophic-state strings retain their exact ordered class mapping;
- no Parquet, target, raw score, prediction, model, or manifest is rewritten.

Construction must preserve this dtype at the producer boundary. Ordinal
producers create exact nullable `Int8` values only after their source tokens
and null absence are validated. Non-ordinal producers create an indexed
nullable `Int8` series filled with `pd.NA`. Every component concat and the
final concat check the exact dtype, applicability mask, null partition, and
class set before returning.

There is no permissive repair in a validator. Integral floats such as `1.0`,
booleans, strings, fractional values, out-of-range integers, ordinal nulls,
and non-ordinal non-null values all fail closed. An arbitrary mixed column is
never accepted by applying `to_numeric`, rounding, truncation, or a post-hoc
`astype` conversion.

## Additive topology

H-E0-MCALG is exactly `4M+5A` over P-E0-MCALF.

Modified successors:

- `src/experiments/calibrate_closure_final_models.py`;
- `src/experiments/run_closure_anfis_learning_curve.py`;
- `tests/test_calibrate_closure_final_models.py`;
- `tests/test_closure_anfis_learning_curve.py`.

Added components:

- `configs/closure_v1/final_calibration_ordinal_label_representation_patch_lock.schema.json`;
- `docs/closure_v1/E0_M_FINAL_CALIBRATION_ORDINAL_LABEL_REPRESENTATION_PATCH_1.md`;
- `src/experiments/closure_final_calibration_ordinal_label_representation_patch.py`;
- `src/experiments/lock_closure_final_calibration_ordinal_label_representation_patch.py`;
- `tests/test_closure_final_calibration_ordinal_label_representation_patch.py`.

P-E0-MCALG is exactly two additions: the canonical lock and its companion
under `reports/closure_v1/00_protocol/`, both with stem
`final_calibration_ordinal_label_representation_patch_lock`.

R retains the exact lifecycle `0 -> 6 -> 8`: the six unchanged files in
`reports/closure_v1/03_calibration/`, followed by the two unchanged files in
`reports/closure_v1/07_anfis_ablation/`.

Five non-runner H-E0-MCALF components are preserved physically, four runner
and test components are sealed as historical Git inputs and superseded, and
both P-E0-MCALF files remain physical predecessor inputs.

## Lock, companion, publisher, and loader

The companion contains exactly 16 unique physical inputs, four historical Git
inputs, and one lock output. The 16 inputs are five preserved H-E0-MCALF
components, both P-E0-MCALF files, and all nine H-E0-MCALG components. The
locker appears exactly once as top-level `script` and once in `inputs`.
`manifest_written_last=true`, `scientific_execution_run=false`,
`dvc_commands_run=false`, and `outcome_paths_opened=false` are mandatory.

Publication inherits frozen-payload reconstruction, exclusive no-follow
guarding, anchored parent descriptors, hardlink no-clobber, temp-identity-only
cleanup, lock-first/companion-last order, repeated branch/HEAD/tracking/live
remote and physical snapshots, joint output metadata and inode checkpoints,
foreign-preserving rollback, and non-fatal close after linearization.

Effective loading inherits canonical/schema/semantic reconstruction,
fresh-clone-safe Git bindings, transitive predecessor authority, repeated
static-boundary, repository, remote, R-lifecycle, and full P-metadata
checkpoints. It validates the exact nullable-label contract locally without
mutating predecessor globals or delegating the historically insufficient
fixture behavior.

## Runner ordering and verification

Both runners import only the E0-MCALG authority. Calibration calls authority
and then run-namespace gates before runtime configuration, scientific I/O,
inference, fitting, or output-parent resolution. E7 follows the same ordering
and remains unavailable until the exact six-file calibration bundle exists.

The focused command covers the calibration runner, E7 runner, and this
governance module and reports exactly 48 passed tests with zero skipped or
deselected tests. It is science-free: governance tripwires prohibit inventory,
Parquet, target, DVC, outcome, and scientific-network access. Full `ty check`,
`poetry check`, publication guard, schema preflight, and `git diff --check`
are mandatory.

## Publication sequence and acceptance

1. Publish exact H-E0-MCALG `4M+5A` as a direct child of P-E0-MCALF.
2. Run the new locker `--check-only` under separate authorization; it writes
   nothing and runs no verification command.
3. Under another authorization, run `--execute-lock`; it may run only the
   frozen checks and publish the canonical P2 bundle.
4. Audit and publish exact P-E0-MCALG `2A`, then require its effective loader.
5. Only then may a newly authorized one-shot run. Stop on any failure without
   retry. E7 remains separately authorized after exact calibration R6.

Acceptance requires exact base `11a1308...`, historical H `12099be...`, H
`4M+5A`, P `2A`, R `8A`, companion `16/4/1`, exact `Int8`/applicability
semantics, rejection of float-even-if-integral/bool/string/fractional drift,
runner gate ordering, science-free focused 48, hardened publication/loading,
and all scientific and publication authorizations false in P. Git commit and
Git push remain manual user-only barriers.
