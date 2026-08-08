# E0-MU: A0/A1 training-cohort implementation authority

## Purpose and exact scope

E0-MU is a corrective implementation overlay over the published E0-MT
authority. It does not change the E0-MT scientific runtime, target projection,
model, optimization, selection objective, preprocessing statistics, slot order,
or output schemas. Its only purpose is to make the implementation conform to
the already sealed distinction between the input-only preprocessing cohort and
the complete-target supervised cohort.

`H-E0-MU` must be a direct, non-merge child of published `P-E0-MT` at
`1b68c24da4efe8fcf5eeb4b90ad0a99e95c96d93`. Its exact scope is `4M+5A`.
The trainer, model-bundle auditor, and their two focused tests are modified.
The following five governance files are added:

1. `configs/closure_v1/anfis_ablation_training_cohort_patch_lock.schema.json`;
2. this document;
3. `src/experiments/closure_anfis_ablation_training_cohort_patch.py`;
4. `src/experiments/lock_closure_anfis_ablation_training_cohort_patch.py`;
5. `tests/test_closure_anfis_ablation_training_cohort_patch.py`.

Future `P-E0-MU` must be the direct, non-merge child of that H commit and add
exactly these two regular `100644` files:

- `reports/closure_v1/00_protocol/anfis_ablation_training_cohort_patch_lock.json`;
- `reports/closure_v1/00_protocol/anfis_ablation_training_cohort_patch_lock_manifest.json`.

No existing lock, companion, sequence, runtime, model, plan, benchmark, or DVC
pointer is modified.

## Discovery evidence and authorization status

The discovery invocation was only the read-only preflight:

```text
train_closure_anfis_ablation.py --model-id A0 --base-seed 1729 --device cpu --check-only
```

Published P-E0-MT passed before input inspection. The preflight then opened
only the development target projection through 2020-12, emitted two
`Pandas4Warning` messages for the deprecated
`set_index(..., verify_integrity=True)` form, and stopped with the exact
terminal error:

```text
Raw observed count drifted for x_mean_TP_ugL
```

The failure occurred before guard acquisition, fitting, output publication,
DVC, calibration, evaluation, E0-M, E0-U, or outcome access. The complete
80-final/80-final-temporary/10-guard/10-pointer namespace, including the ten
potential pointer temporaries, remained empty. Because
`--execute-one-shot` was never invoked, the A0/1729 one-shot authorization was
not consumed. E0-MU does not claim a retry and grants no batch execution.

No persisted stdout or new scientific result is asserted by this patch. The
failure facts above are the bounded observation that motivated the code
correction.

## Correct cohort geometry

E0-MT already seals two different training-only operations and E0-MU makes
their implementation explicit:

- the mask-aware, population (`ddof=0`) raw standardizer is input-only and is
  fit on all 8,352 published sequence origins whose `time_role=training`;
- supervised fitting and training priors use only the 5,932 training origins
  with three complete targets;
- model selection uses the 658 complete-target origins in 2019-01--2020-12;
- each supervised origin contributes exactly one tensor and exactly three
  horizon targets, producing 17,796 training target rows and 1,974 selection
  target rows.

The sealed standardizer statistics do not change. In particular, the expected
observed TP cell count remains 80,271. The defective origin collapse retained
the horizon-specific `evaluation_unit_id`, creating 17,796 training and 1,974
selection pseudo-origin rows and repeating tensors by horizon; its TP observed
count became 163,839. `evaluation_unit_id` is therefore excluded only from the
origin-level collapse. Horizon-level target identity and one-to-one target
joins remain required and are not weakened.

The corrected implementation also replaces both deprecated
`verify_integrity=True` calls with explicit duplicate checks followed by plain
index construction. Sequence `common_origin_id` and target
`(common_origin_id, horizon_months)` uniqueness fail closed before lookup. The
change removes warnings without changing canonical order or accepting a
duplicate.

The same input-only 8,352-origin standardizer is reconstructed for every A0
and A1 slot. The same complete-target 5,932/658 supervised identities and
targets remain paired across variants and seeds. Calibration metadata stays
closed; no 2021 target value is read.

## Historical reconstruction and companion topology

The E0-MU validator reconstructs published H-E0-MT
`f371786bc1e8d6c22b4d911145a57c623303b296` and P-E0-MT without invoking the
superseded effective loader. Six unchanged H-E0-MT components remain current
physical inputs. The historical trainer, auditor, and their two tests are
reconstructed from Git at H-E0-MT and appear only in `historical_inputs`.
Published P-E0-MT lock and companion remain immutable physical provenance.

The future E0-MU companion is exact and maximal:

- 64 unique physical `inputs`: the 47 runtime pins, six preserved H-E0-MT
  components, both P-E0-MT authority files, and all nine current H-E0-MU
  components;
- four Git-bound `historical_inputs`: the superseded H-E0-MT trainer, auditor,
  and their two tests;
- the current E0-MU locker as top-level `script`, also present once in
  `inputs`;
- the E0-MU lock as the sole `outputs` record.

Roles, paths, commits, modes, byte counts, hashes, ordering, and uniqueness are
closed. Historical records are compared with Git blobs, not with the current
modified files. The companion is written last and is the only completion
marker.

## Gates, transaction, and effective authority

`--check-only` performs schema-first validation, exact H/P-MT reconstruction,
single-parent Git topology, `100644` modes for all nine H-E0-MU, ten H-E0-MT,
and two P-E0-MT paths, live Git publication alignment, physical pin checks,
and empty-namespace checks. The schema supported-subset gate rejects semantic
keywords such as `default` or `examples` rather than silently ignoring them.
It writes nothing and runs no tests, trainer, auditor, DVC command, or
scientific network operation.

Under a separate authorization, `--execute-lock` may run only full `ty`, the
frozen focused suite, `poetry check`, the exact publication guard, and
`git diff --check`. Focused pytest evidence retains its exact stdout and binds
its hash and line count; the validator independently requires one clean,
terminal exact-count summary. Pytest runs with `PYTEST_ADDOPTS=''`,
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `PYTEST_PLUGINS=''`, and `PY_COLORS=0`,
overriding any inherited host values. That physical suite invokes the development
preflight loader, reads the published sequences/common-origin inputs and only
the development target projection through 2020-12, and reconstructs the
input preprocessing and training priors. It does not invoke the trainer or
auditor entrypoints and performs no model fit or optimization; calibration
2021, holdout/post-2021 targets, and outcomes remain unread.

The public execute-and-publish boundary accepts no caller-supplied payload or
verification. Inside that single trusted boundary it runs the full type check
and focused suite exactly once, recollects an identical prelock, builds and
validates the payload from that evidence, and publishes only the E0-MU lock
followed by its companion. Publication uses exclusive no-follow guards,
descriptor-anchored parents, exclusive sibling temporaries, hard-link
no-clobber, manifest-last ordering, and owned-inode-only rollback. Foreign
inodes and parent substitutions are never removed.

Until exact P-E0-MU is published, every execution authorization remains false.
After publication, the E0-MU effective loader may authorize only the exact
next slot in the existing order. In build mode it enables the matching A0 or
A1 development fit, target access through 2020-12, and selection diagnostics.
In audit mode it enables only read-only validation of an already completed
prefix slot. Runtime plus the E0-MU lock and companion are the three authority
records embedded in future model manifests.

Calibration and calibration-target access, final E7 claims, rollout, E0-M,
evaluation, E0-U, DVC, scientific network egress, outcome access, future
outcomes, replacement, replay, retry, and batch-slot execution remain false.
P0/P1 remain unavailable and the learning-curve gate remains separate.

## Publication sequence

1. Audit and publish exact H-E0-MU `4M+5A` over P-E0-MT.
2. Run the non-writing E0-MU `--check-only`.
3. Under separate authorization, run `--execute-lock` and audit its two-file
   unpublished bundle.
4. Publish exact P-E0-MU `2A` and run `--check-effective`.
5. Re-run A0/1729 `--check-only`; only after it passes may the still-unconsumed
   A0/1729 one-shot be separately authorized.

H/P-E0-MU never fit a model, execute an auditor, register or push DVC, or open
calibration/evaluation outcomes.
