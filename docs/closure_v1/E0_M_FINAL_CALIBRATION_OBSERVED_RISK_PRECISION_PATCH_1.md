# E0-MCALH — Final-calibration observed-risk precision patch 1

## Status and authority

This document defines the additive `E0-MCALH` authority that preserves exact
target-risk precision across the 2021 A0/A1 inference producer. It changes no
scientific input, target formula, target value, model, prediction, calibration
method, E7 method, or R output path. Its published base is P-E0-MCALG commit
`34a4578efa37d0ccf09e7fc45adf655d3b5a21c1`; the historical H-E0-MCALG
commit is `ba15b7647811bbef2b63b3eb904ba427788da048`.

E0-MCALH is a new gate. It does not restore the consumed E0-MCALG calibration
authorization. The failed invocation must not be retried under P-E0-MCALG.
Only a separately authorized one-shot under a published, effective P-E0-MCALH
may start another calibration attempt.

## Consumed incident and containment

The E0-MCALG invocation passed authority and namespace gates, opened only the
sealed development scientific surface, and completed ten A0/A1 inference
slots. The normalized-frame validator then stopped with exit 2 at the first
uncertainty group, `('A0', 1729, 1)`:

```text
E0-MCAL group risks differ from targets: ('A0', 1729, 1)
```

The closed incident is:

- `attempted_gate=E0-MCALG`;
- `status=failed_closed_no_outputs`;
- `phase=normalized_calibration_frame_validation`;
- `failure_code=a0_seed_1729_horizon_1_observed_risk_float32_precision_loss`;
- `authorization_consumed=true` and `retry_authorized=false`;
- scientific reads and ten A0/A1 inference slots occurred;
- calibration fitting and bundle construction did not occur;
- finals, temporaries, active guards, and filesystem side effects are zero.

The failure preceded calibration fit, output serialization, guard acquisition,
temporary-file creation, and publication. The six calibration finals, two E7
finals, all R temporaries, and both runner guards remain absent. The holdout,
post-2021, outcome, E0-M, E0-U, DVC, Git publication, and scientific-network
boundaries remain closed.

## Root cause and physical evidence

The target authority stores `target_risk_chla_h` as Arrow `double` and Pandas
`float64`. Its producer computes the bounded logarithmic risk in double
precision. The published 2019–2020 ANFIS selection predictions also store
`observed_risk` as Arrow `double`; all 1,974 A0/seed-1729 selection rows equal
the target authority bit for bit after the exact five-key join.

The 2021 inference path allocated `bloom` as NumPy `float32` and then allocated
`risk` with `np.empty_like(bloom)`. Copying authoritative target risks into
that array narrowed them to `float32`. Emitting scalar values widened those
rounded values back to Pandas/NumPy `float64`, but could not restore the lost
bits. The consumer correctly performs a one-to-one inner join on
`source_id`, `site_id`, `origin_year_month`, `target_year_month`, and
`horizon_months`, checks the exact key universe, and compares both sides with
`np.array_equal`; neither order nor identity drift caused the failure.

Across the 672 exact 2021 target rows, the roundtrip changes 261 values:
90/224 at horizon 1, 87/224 at horizon 2, and 84/224 at horizon 3. The maximum
absolute difference is `2.9706991200306732e-08`. The first failing group is
A0/1729/horizon 1 because it is the first uncertainty group in producer order,
not because its keys or model outputs are special.

The historical tests concealed the defect in two ways. Final-bundle fixtures
constructed `observed_risk` and `target_risk_chla_h` from the same Python
`float64` expression. The inference test substituted a synthetic `float32`
training bundle and asserted only counts, roles, and inference inputs; it did
not feed those rows into the exact target-identity validator.

## Exact precision contract

The normalized risk authority has one exact representation:

- source and normalized field are `target_risk_chla_h` and `observed_risk`;
- source Arrow and Pandas dtypes are `double` and `float64`;
- the 2021 calibration `TrainingBundle.risk` dtype is exactly NumPy
  `float64`;
- `TrainingBundle.bloom` remains exactly NumPy `float32`, because binary 0/1
  labels are represented exactly;
- every A0/A1 observed risk is finite, in the closed unit interval, and equals
  its authoritative target bit for bit after an exact one-to-one key join;
- all 672 target rows and the exact 224/224/224 horizon partition are retained;
- no target, Parquet, selection prediction, model, or manifest is rewritten.

There is no tolerance or permissive repair. `allclose`, epsilon comparisons,
rounding, truncation, quantization, decimal formatting, and a
`float64 -> float32 -> float64` roundtrip are forbidden as authority. A
non-exact value fails closed even when numerically close. The producer must
allocate the risk matrix independently as `float64`, validate that dtype, and
retain the existing exact target join and final equality check.

## Additive topology

H-E0-MCALH is exactly `4M+5A` over P-E0-MCALG.

Modified successors:

- `src/experiments/calibrate_closure_final_models.py`;
- `src/experiments/run_closure_anfis_learning_curve.py`;
- `tests/test_calibrate_closure_final_models.py`;
- `tests/test_closure_anfis_learning_curve.py`.

Added components:

- `configs/closure_v1/final_calibration_observed_risk_precision_patch_lock.schema.json`;
- `docs/closure_v1/E0_M_FINAL_CALIBRATION_OBSERVED_RISK_PRECISION_PATCH_1.md`;
- `src/experiments/closure_final_calibration_observed_risk_precision_patch.py`;
- `src/experiments/lock_closure_final_calibration_observed_risk_precision_patch.py`;
- `tests/test_closure_final_calibration_observed_risk_precision_patch.py`.

P-E0-MCALH is exactly two additions: the canonical lock and its companion
under `reports/closure_v1/00_protocol/`, both with stem
`final_calibration_observed_risk_precision_patch_lock`.

R retains the exact lifecycle `0 -> 6 -> 8`: the six unchanged files in
`reports/closure_v1/03_calibration/`, followed by the two unchanged files in
`reports/closure_v1/07_anfis_ablation/`.

Five non-runner H-E0-MCALG components are preserved physically, four runner
and test components are sealed as historical Git inputs and superseded, and
both P-E0-MCALG files remain physical predecessor inputs.

## Lock, companion, publisher, and loader

The companion contains exactly 16 unique physical inputs, four historical Git
inputs, and one lock output. The 16 inputs are five preserved H-E0-MCALG
components, both P-E0-MCALG files, and all nine H-E0-MCALH components. The
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
checkpoints. It validates the exact observed-risk precision contract locally
without mutating predecessor globals or weakening exact equality.

## Runner ordering and verification

Both runners import only the E0-MCALH authority. Calibration calls authority
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

1. Publish exact H-E0-MCALH `4M+5A` as a direct child of P-E0-MCALG.
2. Run the new locker `--check-only` under separate authorization; it writes
   nothing and runs no verification command.
3. Under another authorization, run `--execute-lock`; it may run only the
   frozen checks and publish the canonical P2 bundle.
4. Audit and publish exact P-E0-MCALH `2A`, then require its effective loader.
5. Only then may a newly authorized one-shot run. Stop on any failure without
   retry. E7 remains separately authorized after exact calibration R6.

Acceptance requires exact base `34a4578...`, historical H `ba15b76...`, H
`4M+5A`, P `2A`, R `8A`, companion `16/4/1`, exact risk `float64` and bloom
`float32`, rejection of all tolerant or rounded risk identities, runner gate
ordering, science-free focused 48, hardened publication/loading, and all
scientific and publication authorizations false in P. Git commit and Git push
remain manual user-only barriers.
