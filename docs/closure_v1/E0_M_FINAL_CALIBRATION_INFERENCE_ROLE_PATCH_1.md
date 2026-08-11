# E0-MCALD — final-calibration inference-role patch 1

## Status and exact scope

`H-E0-MCALD` is a corrective, additive authority over the published
`P-E0-MCALC` commit
`89d2b85f84071d90dfde9d46ddd2af339331b047`. That commit is the exact child
of `H-E0-MCALC` at
`dcb0ee06ed4b118b65c5766fba59e67c20a7bf72`; neither published authority is
rewritten. The new H scope is exactly `4M+5A`:

- modified: `src/experiments/calibrate_closure_final_models.py`,
  `src/experiments/run_closure_anfis_learning_curve.py`,
  `tests/test_calibrate_closure_final_models.py` and
  `tests/test_closure_anfis_learning_curve.py`;
- added:
  `configs/closure_v1/final_calibration_inference_role_patch_lock.schema.json`,
  this document,
  `src/experiments/closure_final_calibration_inference_role_patch.py`,
  `src/experiments/lock_closure_final_calibration_inference_role_patch.py`
  and `tests/test_closure_final_calibration_inference_role_patch.py`.

The nine H-E0-MCALC components are reconstructed as five preserved physical
inputs and four superseded Git blobs. Both exact P-E0-MCALC JSON files remain
physical inputs. The nine current H-E0-MCALD components are physical inputs.
The new completion companion is therefore exact `16 physical + 4 historical
+ 1 output`.

A future `P-E0-MCALD` is one direct, non-merge child of H-E0-MCALD and adds
exactly:

- `reports/closure_v1/00_protocol/final_calibration_inference_role_patch_lock.json`;
- `reports/closure_v1/00_protocol/final_calibration_inference_role_patch_lock_manifest.json`.

The future R scope remains the same eight lightweight files: six calibration
outputs followed by two E7 outputs. H, P and R add no Parquet, model,
checkpoint, `.dvc` or outcome-log path.

## Consumed attempt and exact contradiction

The first authorized calibration one-shot under P-E0-MCALC was consumed once.
It passed the effective authority and empty run-namespace gates, opened only
the sealed development inputs and began exact A0 inference for seed `1729`.
It stopped with:

```text
E0-MCAL ANFIS 2021 inference failed: Selection prediction table contains another role
```

The failure occurred after scientific reads and prediction-array inference,
but before the first calibration prediction frame was returned and before any
output transaction or guard began. The post-failure audit found all eight R
finals, all R temporaries and every calibration/E7 guard absent, with Git
clean. That invocation must not be retried under P-E0-MCALC.

The error is a consumer/helper contract mismatch, not corruption of a sealed
selection table. All ten physical A0/A1 selection-prediction Parquets contain
exactly 1,974 rows and the sole role `model_selection`. In particular,
`A0/seed_1729` is 64,842 bytes with SHA-256
`6ca58207a32ba345fc4611c73a879e0546a608d7d076baf8f8da057373a3a4ae`,
exactly as its manifest records. Its target months span 2019-02 through
2020-12.

The same manifest legitimately records 658 model-selection origins/1,974
rows and 224 calibration-threshold origins/672 metadata-only rows. During
training it also records `calibration_target_rows_read=0`,
`calibration_target_accessed=false` and `calibration_authorized=false`. The
sealed A0 sequence is 713,811 bytes with SHA-256
`8988fce08378424d742b3825f11cfda658ac84cdf5e5e24f497ce1d2ebf01b3d`
and contains 9,732 development origins: 8,352 training, 1,061
model-selection and 319 calibration-threshold origins.

Final calibration correctly narrows those inputs to 224 complete
calibration-threshold origins and three horizons, hence 672 2021 rows per
model/seed slot. The consumer then called the historical private helper
`_selection_prediction_frame`. That helper faithfully copied
`time_role=calibration_threshold`, but unconditionally ended in the producer
validator `canonical_prediction_frame`, whose closed contract admits only
`time_role=model_selection`. The deterministic first failure is therefore
model `A0`, seed `1729`, role `calibration_threshold`; the message's
“selection table” refers to the newly constructed in-memory frame, not to a
published Parquet.

## Closed inference-role semantics

E0-MCALD leaves the historical selection producer and all published
Parquets/manifests unchanged. The calibration runner owns a separate strict
calibration-inference frame builder. It admits exactly:

- model ids `A0` and `A1`, with the registered seed for the current slot;
- the exact historical prediction-column order and exact scalar types;
- source `wqp`, assignment role `development` and the sole time role
  `calibration_threshold`;
- 224 unique complete origins and 672 rows per slot, with horizons `{1,2,3}`;
- `target_year_month = origin_year_month + horizon_months`, with target months
  confined to 2021-01 through 2021-12;
- successful availability, empty failure reason and the sealed direct bloom
  probability/risk-distribution score semantics;
- integer binary observed bloom, finite numeric predictions and targets,
  probabilities in `[0,1]`, positive sigma inside the sealed log-variance
  clamp, unique identities and canonical stable ordering.

An empty frame, another role, a model/seed mismatch, null or coerced scalar,
wrong denominator, duplicate, missing horizon, malformed month, out-of-range
value or nonfinite number fails closed. Selection outputs continue to pass
only the historical `model_selection` validator; no validator is widened and
no role is rewritten after validation.

The candidate correction from E0-MCALC remains exact: B0/B1 retain the empty
candidate sentinel, B2 retains the two sealed candidates and M0 retains
`mifal_ed_t2_v5_defaults`. No prediction, target, formula, seed, model state,
denominator, threshold, cutpoint, period or E7 terminal rule changes. Holdout,
post-2021, outcome, E0-M, E0-U, DVC and scientific-network authorizations
remain false.

## Authority, publication and lifecycle

The strict validator reconstructs P-E0-MCALC and H-E0-MCALC from Git, binds
the exact prior lock and companion, and partitions the four superseded runner
and focused-test blobs from their physical successors. The P-E0-MCALD
companion contains:

- 16 unique physical inputs: five preserved H-E0-MCALC components, both
  P-E0-MCALC files and all nine H-E0-MCALD components;
- four historical inputs: the superseded calibration/E7 runners and their
  two focused-test modules;
- the current MCALD locker exactly once as top-level `script` and once in
  `inputs`;
- one output record for the MCALD lock;
- canonical `manifest_written_last=true`, with scientific execution, DVC and
  outcome access false.

Publication inherits the audited anchored/no-follow exclusive guard,
hardlink no-clobber, `temp_identity`-only cleanup, frozen-payload validation,
repeated branch/HEAD/tracking/live-remote and physical snapshots, joint output
identity checkpoints, foreign-preserving rollback and non-fatal post-commit
descriptor-close semantics. The companion is the logical and physical
completion marker. Effective loading inherits canonical/schema/semantic
reconstruction, fresh-clone-safe Git bindings, exact static boundaries,
repeated namespace/ref/snapshot checks and full P metadata linearization.

The R lifecycle remains closed: `0 -> 6 -> 8`. Calibration is authorized only
at zero R outputs; E7 is authorized only after the exact six-file calibration
bundle; neither runner permits a retry after its own bundle exists. Partial
bundles, temporaries, guards, legacy P, outcome logs and E0-M outputs fail
closed before scientific I/O.

## Gates

1. Publish exact H-E0-MCALD as `4M+5A` over `89d2b85…`.
2. Run the new locker with `--check-only`. Schema preflight is first; it
   reconstructs H/P history, the consumed incident, inference-role semantics,
   family/scientific inputs, empty new P/R namespaces, clean refs and live
   `origin/main`. It writes nothing and runs no tests, DVC, calibration, E7 or
   outcomes.
3. Under separate authorization, run `--execute-lock`. It may run only full
   `ty check`, the exact 48-test focused suite, `poetry check`, publication
   guard and `git diff --check`, then publish lock followed by companion.
4. Audit and publish exact P-E0-MCALD as `2A`; require effective loading before
   a newly authorized calibration attempt.
5. Execute calibration once. On any failure, stop without retry; otherwise
   audit its exact six-file bundle, then authorize and execute E7 once before
   publishing the unchanged exact `8A` R scope.

Every execution requires a new explicit authorization. The failed MCALC
invocation is evidence only and is never reused. Git commit and Git push
remain user-only operations.

## Acceptance criteria

- exact H `4M+5A`, P `2A`, R `8A`, with base P `89d2b85…` and historical H
  `dcb0ee0…`;
- previous authority partition `5 preserved + 4 superseded`, prior P2
  preserved, and companion `16 physical + 4 historical + 1 output`;
- consumed A0/1729 failure is recorded at inference-role validation, with
  scientific reads/inference true but finals/temporaries/guards all zero and
  retry false;
- physical selection tables remain exact `model_selection`; generated
  calibration frames admit only exact `calibration_threshold` 224/672 2021
  semantics and exact scalar types;
- authority/loaders and both runners adopt only effective P-E0-MCALD;
- no-clobber/rollback regressions preserve foreign names and remove only exact
  owned identities;
- every holdout, post-2021, outcome, E0-M, E0-U, DVC and network boundary
  remains false.
