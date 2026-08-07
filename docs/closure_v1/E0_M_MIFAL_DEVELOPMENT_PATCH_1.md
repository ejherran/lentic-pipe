# E0-MR — Closure V1 strict MIFAL development authority

## Status and exact scope

`H-E0-MR` is an additive development-only authority over
`aa0d2cbfac186464a8b6e17b87d71aeedaa92c95`, the published Closure V1
baseline bundle. Its direct parent must be that commit and its scope is exactly
nine additions:

- `configs/closure_v1/mifal_development_patch_lock.schema.json`;
- `configs/closure_v1/mifal_development_runtime.yaml`;
- this document;
- `src/experiments/closure_mifal_development_patch.py`;
- `src/experiments/lock_closure_mifal_development_patch.py`;
- `src/experiments/run_closure_mifal.py`;
- `src/mifal/closure_panel_adapter.py`;
- `tests/test_closure_mifal_development_patch.py`;
- `tests/test_run_closure_mifal.py`.

The historical MIFAL implementation, adapters, tests and reports remain
unchanged. In particular, the historical surface named
`observable_no_current_chla` deliberately retains `Chl_prev`; it is evidence
from an earlier iteration and is not M0. The locked
`configs/closure_v1/model_benchmark.yaml` continues to record M0 as
`blocked_pending_strict_adapter`. E0-MR is the only additive authority that may
resolve that block for a later development one-shot; it does not rewrite the
protocol file.

Python package initialization may load a symbol from the historical adapter as
an incidental, non-authoritative and no-I/O compatibility effect. E0-MR does
not claim that the module is never loaded. It forbids the M0 runner from
directly importing or invoking that adapter and forbids using it for any data
projection, payload, lineage or fallback.

A future `P-E0-MR` is a direct, non-merge child of the published H commit and
contains exactly two additions:

- `reports/closure_v1/00_protocol/mifal_development_patch_lock.json`;
- `reports/closure_v1/00_protocol/mifal_development_patch_lock_manifest.json`.

Until that exact P commit is published and passes the effective loader, M0
execution and every other execution authorization remain false.

## Strict input and eligibility contract

M0 uses the exact 29,196 common-origin rows, 9,732 intent-to-predict origins,
353 development WQP locations and horizons 1, 2 and 3. Holdout locations and
post-2021 outcomes are excluded. The panel scanner may request only identity
columns and the value/count/QC/standard-deviation fields needed for six
non-chlorophyll observations:

- `Tw` from water temperature;
- `TP` and `TN`, with the locked TN unit conversion;
- `Secchi` and `Turb` for light evidence;
- `DOb`, retained as qualified dissolved-oxygen evidence rather than a claim
  of bottom-water oxygen.

No observed chlorophyll-a value, lag, count, QC rate, standard deviation,
missingness signal, transform or derivative may be requested or materialized.
The adapter emits no `Chl`, `Chl_prev` or other observed biological-memory
input. Its lineage projection is an allowlist, not a post-read column drop.

Input eligibility is determined before target access. A row is eligible only
when it has its exact common key, one unique panel origin row and observed,
finite, physically bounded evidence in at least two of these four ecological
groups: temperature, nutrients, light and qualified dissolved oxygen. Missing
variables are omitted from the payload. They are not median-imputed or replaced
by a fabricated observation; MIFAL-ED/T2 represents them through its frozen
prior, default uncertainty, missingness bonus, `available=false` and zero
observational reliability. Every common-origin row remains in the output with
one terminal status. Silent deletion, fallback to the historical adapter and
replacement of a failed origin or location are forbidden.

The physical development surface satisfies the predeclared rule without using
targets: all 9,732 origins have evidence in two to four ecological groups
(9,209 have four, 505 have three and 18 have two). This fact is an input audit,
not permission to weaken or tune the rule after outcomes.

## MIFAL-ED/T2 semantics and structural prior

M0 reuses `src/mifal/ed_t2.py` version 5 and its frozen defaults; E0-MR does not
create a second MIFAL implementation. The technical seed is 1729 and identifies
the deterministic slot. Each exact row starts independently and uses:

- `initial_state=(0.05, 0.35)`;
- `gammaM=0.28`;
- the no-observed-memory fallback interval `Memory=(0.0, 0.35)`;
- `observed_memory_inputs=[]`;
- no observation assimilation, no state update, no value-of-information pass
  and no carry between sites, origins or horizons;
- the locked horizon-to-days conversion from the runtime contract.

The initial state, `gammaM` and fallback interval are a constant global
structural prior. They are not observed chlorophyll memory, are not learned
from one site or row and must not be described as site-specific evidence.
Because `Chl` and `Chl_prev` are unavailable, they cannot contribute to the
Memory index or observation assimilation. The manifest and model specification
must expose these facts rather than hiding them behind the label “no-current”.

The raw M0 score is the uncalibrated conservative ED/T2 risk. The raw contract
has exactly 28 columns, preserves its interval and reliability diagnostics and
keeps `predicted_bloom_probability` null. Calibration and thresholding occur
only under later, separately locked roles; an uncalibrated risk score must not
be relabeled as a calibrated probability.

## Failure and output boundary

Missing panel history or fewer than two observed ecological groups produces
`input_ineligible` with the registered incomplete-input code. Scores and
interval fields are null for that retained row. A forbidden chlorophyll
lineage, duplicate physical key, authority drift, namespace collision, ED/T2
exception or nonfinite model result aborts the whole transaction and rolls back
all owned outputs. There is no unregistered numerical-error row status, silent
replacement or partial-success publication.

The one-shot may produce exactly these six final paths:

- `data/closure_v1/development/mifal/M0/raw_scores.parquet`;
- `reports/closure_v1/02_models/M0/model_spec.json`;
- `reports/closure_v1/02_models/M0/lineage_audit.json`;
- `reports/closure_v1/02_models/M0/availability.csv`;
- `reports/closure_v1/02_models/M0/report.md`;
- `reports/closure_v1/02_models/M0/manifest.json`.

The manifest is written last. The one-shot may not read targets, calculate
development or holdout metrics, fit a calibrator, create a checkpoint, open an
outcome log, create E0-M/E0-U, invoke DVC or use the network. A future DVC
pointer for the raw Parquet is registered only after a read-only audit and a
separate authorization.

## H/P gate and transaction workflow

1. Publish exact H-E0-MR as `9A` over the baseline bundle.
2. Run `--check-only`. Schema validation is the first operation. It verifies
   H topology, pinned source/input hashes, strict projection, empty output and
   pointer namespaces, clean refs and the live tracking ref. It writes nothing
   and runs no type check, tests, M0, DVC, auditor or outcome command.
3. Under separate authorization, run `--execute-lock`. Its only commands are
   the full type check, the exact focused suite of 62 tests with zero
   skips/deselections, `poetry check`, the publication guard with the real
   success marker, and `git diff --check`.
4. Recollect the prelock after verification, then publish only lock followed by
   companion. Directory descriptors are opened no-follow; guards and
   temporaries are exclusive; hardlink publication is no-clobber; rollback may
   unlink only the inode owned by the locker. The companion is the manifest-last
   completion marker and binds exactly 32 unique physical inputs: the 23
   runtime inputs plus the nine H components. It includes the locker as both
   its generating `script` record and one of those unique physical inputs.
5. Audit and publish exact P-E0-MR as `2A`, then run `--check-effective`.
6. Only the resulting effective P authority may permit one separately
   authorized M0 one-shot. Calibration, evaluation, E0-M, E0-U, DVC,
   scientific network access and outcomes remain false.

H/P never execute M0. A failed one-shot consumes its authorization and must be
audited before any new authority can be considered.
