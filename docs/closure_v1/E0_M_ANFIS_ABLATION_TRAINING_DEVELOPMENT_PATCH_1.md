# E0-MT: development-only A0/A1 training authority

## Purpose and boundaries

E0-MT closes the minimum implementation required to compare A0 and A1 without
opening calibration, holdout, or evaluation outcomes. This slice is an
additive overlay and a direct child of the A0/A1 sequence bundle published at
`e22fd44`. It does not modify the plan, benchmark, published sequences, or any
previous lock.

The only estimable result of this slice is A1 versus A0 on development data.
P0 and P1 remain `model_unavailable/not_attempted`; E0-MT neither replaces
them nor authorizes a complete E7 factorial conclusion. The ANFIS learning
curve for 4,096/16,384/65,536 rows remains a separate gate.

## Git scope

H-E0-MT consists of exactly ten additions:

1. `configs/closure_v1/anfis_ablation_training_development_runtime.yaml`;
2. `configs/closure_v1/anfis_ablation_training_development_patch_lock.schema.json`;
3. this document;
4. `src/experiments/closure_anfis_ablation_training_development_patch.py`;
5. `src/experiments/lock_closure_anfis_ablation_training_development_patch.py`;
6. `src/experiments/train_closure_anfis_ablation.py`;
7. `src/experiments/audit_closure_anfis_ablation_model_bundle.py`;
8. `tests/test_closure_anfis_ablation_training_development_patch.py`;
9. `tests/test_train_closure_anfis_ablation.py`;
10. `tests/test_audit_closure_anfis_ablation_model_bundle.py`.

P-E0-MT is a direct, non-merge child with exactly two additions:

- `reports/closure_v1/00_protocol/anfis_ablation_training_development_patch_lock.json`;
- `reports/closure_v1/00_protocol/anfis_ablation_training_development_patch_lock_manifest.json`.

The companion binds every H component and every physical input declared by
the runtime, without duplicates, with `historical_inputs=[]`, the locker as
`script`, the lock as its only output, and manifest-last publication.

## Shared target and cohort

A0 and A1 use exactly the same supervised problem. For every origin, the
following values are projected in h1, h2, and h3 order:

- binary `bloom_h`;
- finite `target_risk_chla_h` in `[0,1]`.

The join uses the five physical keys
`source_id/site_id/origin_year_month/target_year_month/horizon_months`,
requires WQP, `assignment_role=development`, one-to-one cardinality, and
three complete horizons. Only targets whose origin and target are both no
later than 2020-12 are materialized. Labels from 2021, calibration, holdout,
and E0-U are neither scanned nor summarized.

The closed denominators are:

- training: 5,932 origins and 17,796 horizon rows;
- model selection: 658 origins and 1,974 horizon rows;
- calibration threshold: 224 complete origins known from metadata only,
  without opening their targets;
- zero test, holdout, unknown, or post-2020 target rows.

For training, the h1/h2/h3 bloom-positive counts are 1,782/1,802/1,842. The
residual prevalences are
0.3004045853000674/0.30377612946729604/0.3105192178017532, and the risk priors
are 0.5889835052483097/0.5918203351433461/0.5957344105135742. They are derived
only from training and must be reconstructed before and after every fit.

## Inputs and preprocessing

A0 consumes the published `[12,18]` tensor: seven raw no-current means, seven
observed masks, and four seasonal channels. A1 consumes `[12,27]`, the same
tensor plus nine adaptive ANFIS states from the same seed. The five seeds are
`1729, 20260612, 20260613, 20260614, 314159`.

The seven raw means are standardized with the population mean and standard
deviation (`ddof=0`) computed only at mask-one positions from training
origins. After standardization, mask-zero positions are structurally set to
zero. Masks, seasonal channels, and the nine A1 states pass through unchanged.
Statistics are computed in float64, and the model tensor is float32. Nothing
is fit on model-selection or calibration data.

## Model and selection

The ten slots are consumed in seed-paired order:

`A0/1729, A1/1729, A0/20260612, A1/20260612, A0/20260613, A1/20260613,
A0/20260614, A1/20260614, A0/314159, A1/314159`.

Both variants use a batch-first GRU with hidden size 96, one layer, zero
dropout, CPU execution, and one thread. `add_last` is forbidden: the first A0
channels are covariates, not targets. To preserve a comparable residual
formulation, the heads predict deltas from the bloom-prevalence logit and the
mean-training-risk logit, separately by horizon. Each horizon emits a bloom
probability, a risk mean in `[0,1]`, and a risk log variance clipped to
`[-10,2]`.

Optimization is fixed to AdamW (`lr=0.001`, `weight_decay=0.00001`), global
gradient clipping at 1.0, batch size 2,048, at most 20 epochs, and early
stopping after five epochs with `min_delta=0`; a tie retains the earliest
epoch. The loss equally weights bloom BCE, risk Gaussian NLL, and risk MSE,
then averages the three horizons. Selection equally combines bloom Brier,
risk RMSE, and risk MAE, each normalized against the training prior for the
same horizon. There is no seed search, tuning, calibration, thresholding, or
refit with model-selection data.

## One-shot outputs

Each slot publishes exactly eight final paths, with the manifest written last:

- final model and raw-best checkpoint under `models/closure_v1/anfis_ablation/`;
- preprocessor/prior JSON;
- training-curve CSV;
- model-selection prediction Parquet (658 x 3 = 1,974 rows);
- model-selection metrics CSV;
- Markdown report;
- JSON manifest.

The selection Parquet contains no calibration, test, or holdout rows and
resides under `data/closure_v1/development/anfis_ablation/`. Models and
checkpoints are registered later through `models.dvc`; each selection Parquet
uses an explicit pointer. Registration and the two targeted, idempotent pushes
are later, separate gates and never run in H/P or during fitting.

The namespace contains eighty final paths, eighty temporary paths, and ten
potential guards. Every invocation is one-shot and target-aware and accepts
only the next slot in the physical prefix. Replay, holes, future or extra
slots, partial pointers, existing outputs, and foreign inodes fail closed. The
transaction uses FD-anchored parents, `O_NOFOLLOW`, `O_EXCL` temporary files,
no-clobber hard links, owned-inode-only rollback, and manifest-last
publication.

## Gates

`--check-only` validates the schema, H, live Git refs/remote, physical inputs,
sequences, cutoff-safe targets, and namespace without running tests, fitting,
the auditor, DVC, or writes. `--execute-lock` additionally runs full `ty`, the
exact focused suite, `poetry check`, the publication guard, and the diff
check; it then recollects state and publishes only the lock and companion.
The only permitted network access is read-only Git publication verification;
scientific network access and DVC remain false.

Before P is published, every authorization is false. After an exact,
published P, only the development-only target adapter and the A0/A1 one-shots
for the next slot are enabled. Any slot other than the next one, target access
beyond the cutoff, calibration, thresholding, rollout, evaluation, E0-M,
E0-U, DVC, retry, replacement, and the outcome log remain false unless a
later gate grants the corresponding specific authorization.
