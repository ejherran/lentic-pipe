# E0-MCALI — Final-calibration owned-run guard revalidation patch 1

## Status and authority

This document defines the additive `E0-MCALI` authority for revalidating an
E0-MCAL publication while its own exclusive run guard is active. It changes
no scientific input, target, prediction, model, fit, calibration method, E7
method, or R output path. Its published base is P-E0-MCALH commit
`c6dbe43f01e484c7270c6a19f9a69d0b753036c7`; the historical H-E0-MCALH
commit is `e107316cbe302fc806676f620af00df6244530a5`.

E0-MCALI is a new gate. It does not restore the consumed E0-MCALH
authorization, and the failed invocation must not be retried under
P-E0-MCALH. Only a separately authorized one-shot under a published,
effective P-E0-MCALI may begin another calibration attempt.

## Consumed incident and containment

The E0-MCALH invocation passed its effective-authority and R0 namespace gates,
opened only the sealed development surface, completed inference and fitting,
and built the six-file calibration payload. Its ordered transaction then
acquired the calibration guard and published all six files provisionally,
with the manifest last. The authority revalidation performed inside that
transaction stopped fail-closed because the effective namespace correctly
treated the active calibration guard as foreign coordination:

```text
E0-MCALH effective coordination/temporary namespace is occupied:
['tmp/closure_v1_e0_mcal/final_calibration.guard']
```

The closed incident is:

- `attempted_gate=E0-MCALH`;
- `status=failed_closed_rolled_back_no_outputs`;
- `phase=calibration_bundle_publication_authority_revalidation`;
- `failure_code=owned_calibration_guard_rejected_by_effective_namespace_revalidation`;
- `authorization_consumed=true` and `retry_authorized=false`;
- scientific reads, inference, calibration fitting, and payload construction
  occurred;
- six provisional calibration finals and one owned guard existed inside the
  transaction;
- rollback removed all six provisional finals in reverse order and removed
  only the owned guard identity;
- final, temporary, and active-guard counts after rollback are zero.

P-E0-MCALH, all scientific inputs, and all predecessor authorities remain
intact. The two E7 outputs, holdout, post-2021, outcome, E0-M, E0-U, DVC,
Git-publication, and scientific-network boundaries remain closed.

## Root cause and masked second failure

The public loader is intentionally fail-closed whenever either runner guard
exists. The calibration runner nevertheless called that same public loader
after `OrderedBundleTransaction.__enter__` acquired its own guard and after
the six provisional calibration outputs had been linked. The loader therefore
failed on its coordination check before it could complete authority
revalidation.

Ignoring the guard pathname would be both unsafe and insufficient. A pathname
does not prove ownership and may refer to a foreign or replaced inode. In
addition, the provisional six-file namespace has lifecycle
`calibration_completed_unpublished_ready_for_e7_bundle`, while the authority
captured before execution has lifecycle `ready_for_calibration_bundle`.
Comparing the two complete authority dictionaries would still fail even when
their immutable P/scientific binding is identical.

The corresponding E7 transition has the same latent shape: a legitimate
owned E7 guard protects the transition from exact R6 to exact R8. The patch
closes both transitions before E7 is attempted.

## Owned capability contract

The public authority loader and the public namespace gate remain unchanged:
an active calibration or E7 guard always fails closed. Owned-run revalidation
uses a separate private capability-bound surface and never grants effective
authority to an arbitrary caller.

The private surface recognizes exactly the transaction phases
`active_guard` and `post_release`. The first validates the owned guard and
provisional bundle; the second validates the exact committed lifecycle after
the owned guard has been released.

The capability is valid only when all of the following remain exact:

- runner identity is `calibration` or `e7` and matches its registered guard;
- guard path is resolved through an anchored no-follow parent walk, and
  device, inode, regular-file mode, link count, byte count, payload SHA-256,
  and owned transaction identity all agree;
- mode is the sealed private guard mode, link count is one, and no symlink or
  alternate pathname is accepted;
- expected lifecycle transition is exactly R0 to provisional R6 for
  calibration, or R6 to provisional R8 for E7; its three counts are exact
  non-boolean integers, its state is an exact string, and its five flags are
  exact booleans;
- every provisional output is owned by the same transaction, has exact path,
  bytes, metadata and inode, and the bundle is complete with manifest last;
- P lock/companion, H and transitive history, scientific inputs, branch, HEAD,
  tracking ref, live remote and workspace scope equal the captured immutable
  authority binding;
- no additional guard, temporary, legacy P, outcome, E0-M or unrelated
  workspace path exists.

A path-only token, wrong runner, foreign guard, same-path inode swap,
additional guard, partial output bundle, unexpected output, metadata or byte
drift, ref drift, scientific-input drift, or lifecycle drift fails closed.
Cleanup may unlink only identities owned by the transaction; foreign names
and replacements survive for diagnosis.

After guard release, the transaction must call the ordinary public loader
again. That pass permits no guard exception, requires the same immutable
authority binding, and requires the exact committed R6 or R8 lifecycle. The
transaction reopens and validates all owned outputs after this callback and
only then linearizes success.

## Additive topology

H-E0-MCALI is exactly `4M+5A` over P-E0-MCALH.

Modified successors:

- `src/experiments/calibrate_closure_final_models.py`;
- `src/experiments/run_closure_anfis_learning_curve.py`;
- `tests/test_calibrate_closure_final_models.py`;
- `tests/test_closure_anfis_learning_curve.py`.

Added components:

- `configs/closure_v1/final_calibration_owned_run_guard_revalidation_patch_lock.schema.json`;
- `docs/closure_v1/E0_M_FINAL_CALIBRATION_OWNED_RUN_GUARD_REVALIDATION_PATCH_1.md`;
- `src/experiments/closure_final_calibration_owned_run_guard_revalidation_patch.py`;
- `src/experiments/lock_closure_final_calibration_owned_run_guard_revalidation_patch.py`;
- `tests/test_closure_final_calibration_owned_run_guard_revalidation_patch.py`.

P-E0-MCALI is exactly two additions: the canonical lock and its companion
under `reports/closure_v1/00_protocol/`, both with stem
`final_calibration_owned_run_guard_revalidation_patch_lock`.

R retains the exact lifecycle `0 -> 6 -> 8`: the six unchanged calibration
files in `reports/closure_v1/03_calibration/`, followed by the two unchanged
E7 files in `reports/closure_v1/07_anfis_ablation/`.

Five non-runner H-E0-MCALH components are preserved physically, four runner
and test components are sealed as historical Git inputs and superseded, and
both P-E0-MCALH files remain physical predecessor inputs.

## Lock, companion, publisher, and loader

The companion contains exactly 16 unique physical inputs, four historical Git
inputs, and one lock output. The 16 are five preserved H-E0-MCALH components,
both P-E0-MCALH files, and all nine H-E0-MCALI components. The locker appears
exactly once as top-level `script` and once in `inputs`.
`manifest_written_last=true`, `scientific_execution_run=false`,
`dvc_commands_run=false`, and `outcome_paths_opened=false` are mandatory.

Lock publication inherits canonical frozen-payload reconstruction, exclusive
no-follow guarding, anchored descriptors, hardlink no-clobber,
temp-identity-only cleanup, lock-first/companion-last order, repeated physical
and Git/ref snapshots, joint output metadata/inode checkpoints,
foreign-preserving rollback, and non-fatal close after linearization.

Effective loading inherits canonical/schema/semantic reconstruction,
fresh-clone-safe Git bindings, transitive predecessor history, repeated static
boundary, repository, remote, R lifecycle and full P metadata checkpoints.
The new owned capability is not accepted by the public loader and cannot make
a partial or guarded R namespace effective.

## Runner ordering and verification

Both runners import only E0-MCALI. Each calls public authority and namespace
gates before runtime configuration or scientific I/O. Immediately before
publication it recaptures the immutable authority binding. During publication
it uses only the capability-bound private revalidator; after guard release it
uses the public loader and exact terminal lifecycle again.

The focused command covers the calibration runner, E7 runner and this
governance module and reports exactly 48 passed tests with zero skipped or
deselected tests. It is science-free: governance tripwires prohibit real
inventory, Parquet, target, outcome, DVC and scientific-network access. Full
`ty check`, `poetry check`, publication guard, schema preflight and
`git diff --check` are mandatory.

## Publication sequence and acceptance

1. Publish exact H-E0-MCALI `4M+5A` as a direct child of P-E0-MCALH.
2. Run the new locker `--check-only` under separate authorization; it writes
   nothing and runs no verification command.
3. Under another authorization, run `--execute-lock`; it may run only the
   frozen checks and publish the canonical P2 bundle.
4. Audit and publish exact P-E0-MCALI `2A`, then require its public effective
   loader with no active guard.
5. Only then may a newly authorized calibration one-shot run. Stop on any
   failure without retry. E7 remains separately authorized after exact R6.

Acceptance requires exact base `c6dbe43...`, historical H `e107316...`, H
`4M+5A`, P `2A`, R `8A`, companion `16/4/1`, public-loader guard fail-closed,
identity-bound private revalidation, exact R0/R6/R8 transitions, rejection of
foreign/path-only/swapped/partial states, science-free focused 48, hardened
publication/loading, and all scientific/publication authorizations false in
P. Git commit and Git push remain manual user-only barriers.
