# E0-MP — Closure V1 baseline development authority

## Status and scope

`H-E0-MP` is an additive implementation authority over
`a9aa51aaa1566d0b8e7154697fae69c458c5019f`. It contains exactly eight new
files and modifies neither the historical baseline runners nor the DVC
ownership overlay. A future `P-E0-MP` may contain exactly two new files:

- `reports/closure_v1/00_protocol/baseline_development_patch_lock.json`;
- `reports/closure_v1/00_protocol/baseline_development_patch_lock_manifest.json`.

The machine-readable scientific contract is
`configs/closure_v1/baseline_development_runtime.yaml`. The lock schema,
validator, locker, runner and both focused tests are part of the same exact H
commit. Until P is published and passes `--check-effective`, every execution
authorization remains false.

## Scientific boundary

E0-MP authorizes only one development batch for B0, B1 and B2. The target
scanner projects exactly the five join keys plus `bloom_h` and
`target_risk_chla_h`, and pushes both
`origin_year_month <= 2020-12` and `target_year_month <= 2020-12` into the
Parquet scan. Calibration labels from 2021 are not materialized. Holdout
locations, evaluation, E0-M, E0-U and post-2021 outcomes remain inaccessible.

- **B0** fits an unsmoothed horizon prevalence on complete training origins
  and emits one score for every one of the 29,196 intent rows.
- **B1** uses all five published ANFIS seeds. At the exact origin month it
  persists `clip((yN + (1-yF) + yT_no_chla)/3, 0, 1)` across h1–h3. It has no
  fallback to another month, seed, observed Chl-a value or target. Its
  uncalibrated score is interpreted as a Chl-a-free IRC persistence
  probability; `raw_score` and `predicted_bloom_probability` contain that same
  clipped value. Development diagnostics include PR-AUC/Brier for bloom and
  RMSE/MAE against the risk channel; neither target channel becomes a model
  feature and no calibrator is fitted.
- **B2** uses the 38 physical non-Chl-a columns and four calendar features in
  the locked allowlist order. Logistic SGD and histogram gradient boosting
  define five-seed × three-horizon × two-family candidate slots. The calendar
  columns are derived as float32 and the imputed model matrix is float64; CPU
  execution is restricted to one threadpool worker. All 30 slots and all 30
  explicit preprocessor records remain represented. A failed fit retains its
  rows as `model_unavailable` and omits only that pipeline joblib, so there are
  zero to 30 pipeline files. Family selection requires five finite seeds, uses
  mean Brier with the fixed 0.001 tolerance, then mean PR-AUC and finally the
  logistic tie-break.

The candidate table retains every declared row and failure. Seeds are not
pooled as independent observations and no best seed is selected.

## Output and transaction contract

The future one-shot namespace reserves 69 potential final paths:

- three raw-score Parquets: B0, B1 and B2;
- zero to 30 B2 pipelines, one per successful candidate slot;
- 30 B2 preprocessor records;
- six lightweight files, with `manifest.json` published last.

Thus every completed bundle contains 39–69 finals, while all 69 potential
paths are absent at H/P lock time. The raw Parquets use the exact 22-column
schema, dtypes, nullability, status values and canonical ordering sealed by the
runtime. Successful rows have finite closed-unit-interval scores; unavailable
rows retain their declared denominator with both score fields null.

The expected raw-score denominator is 467,136 rows: 29,196 B0, 145,980 B1
and 291,960 B2 candidate rows. H and P require all 69 potential finals, all 69
temporary paths, the three future raw-score DVC pointers and the runner guard
to be absent. The runner uses exclusive guards,
no-follow parent walks, exclusive temporary creation, hardlink no-clobber and
rollback only for inodes it owns. DVC registration is a later, separately
authorized post-audit operation; H, P and the one-shot itself execute no DVC.

## Gate workflow

1. Publish exact H-E0-MP as eight additions over the stated base.
2. Run locker `--check-only`. It validates the schema first, verifies
   `origin/main` with read-only `git ls-remote`, and performs no writes,
   science, DVC, auditor or outcome access.
3. Under a separate authorization, run `--execute-lock`. It performs only the
   full type check, the exact focused suite, Poetry validation, publication
   guard and diff check. It writes lock then companion, with the companion as
   completion marker.
4. Audit and publish exact P-E0-MP as lock plus companion.
5. Run `--check-effective`. Only then do the four flags
   `baseline_one_shot_authorized`, `b0_fit_authorized`,
   `b1_execution_authorized` and `b2_fit_authorized` become true.
6. Execute the baseline one-shot once under another explicit authorization.

The lock companion binds the eight H components plus 40 unique physical
runtime inputs, including the holdout manifest, dependency locks and the
existing `models.dvc`; it has 48 physical inputs and no historical inputs.
Even when effective, calibration, E0-M, evaluation, E0-U, DVC, scientific
network and outcome-access flags remain false. The read-only remote Git check
is gate evidence, not baseline egress. Failure consumes an execution
authorization and requires read-only audit before any new attempt.
