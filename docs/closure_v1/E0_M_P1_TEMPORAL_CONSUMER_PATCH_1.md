# Closure V1 E0-MD P1 Temporal Consumer Patch 1

## Purpose

E0-MD is an additive, development-only gate for the first P1 temporal
consumer invocation. It adopts the immutable P1 sequence bundle for
`model_id=P1`, `base_seed=1729`, and `device=cpu` after that bundle has been
published and audited.

The gate resolves an authority-domain transition. E0-DLTVM was published
before the later P1 sequence hardenings, while E0-MC authorizes only the
already-consumed one-shot sequence build. Neither historical effective loader
may be repurposed to authorize the temporal consumer against later physical
bytes. E0-MD therefore reconstructs both authorities from their committed Git
snapshots and adopts the published P1 bundle explicitly.

This patch does not change the scientific runtime, sequence rows, state
mapping, denominators, or model-availability policy.

## Closed scope

H-E0-MD must be a direct, non-merge child of:

```text
82c0bc10a8b17ab700a8f0c28491a60572a11d81
```

Its exact diff is `2M+5A`.

Modified:

```text
src/experiments/train_closure_pipe.py
tests/test_train_closure_pipe.py
```

Added:

```text
configs/closure_v1/p1_temporal_consumer_patch_lock.schema.json
docs/closure_v1/E0_M_P1_TEMPORAL_CONSUMER_PATCH_1.md
src/experiments/closure_p1_temporal_consumer_patch.py
src/experiments/lock_closure_p1_temporal_consumer_patch.py
tests/test_closure_p1_temporal_consumer_patch.py
```

P-E0-MD must be the direct, non-merge child of H-E0-MD and add exactly:

```text
reports/closure_v1/00_protocol/p1_temporal_consumer_patch_lock.json
reports/closure_v1/00_protocol/p1_temporal_consumer_patch_lock_manifest.json
```

The lock and companion are immutable after publication.

## Historical authorities

### E0-MC and nested E0-MB

E0-MD reconstructs E0-MC from its schema-valid, Git-bound published lock
snapshot. It deliberately does not call the historical or effective E0-MC
loader, because the older nested E0-MB loader classifies the trainer as a
preserved H-E0-DLTVM component and therefore cannot validate the intentional
H-E0-MD trainer change. E0-MD requires:

- H-E0-MC `5bdac0fe8279297dbdb04e38146726431511fe7a`;
- P-E0-MC `d76f35b20a0d5b5515ec31acbca1e953730afce4`;
- the unchanged E0-MC lock and companion;
- the E0-MC current builder record
  `f0e653b29035acb11e39bc9a7776e7940394996d75f16bf3bccb4da30013c9cf`
  with 127,833 bytes;
- the nested historical E0-MB authority retained by the E0-MC lock.

E0-MD reconstructs the closed E0-MC context authorization needed to validate
the frozen seed-1729 ANFIS manifest. It does not re-open sequence-building
authority and does not invoke the consumed E0-MC effective one-shot loader.

### E0-DLTVM

E0-MD treats H-E0-DLTVM and P-E0-DLTVM as historical Git authorities:

```text
H-E0-DLTVM  3ee008faef331f40cf73d1f1e3db59608b0deab1
P-E0-DLTVM  4ba5ecd45da7f0b25277c0a13602999413fa2849
```

The effective E0-DLTVM loader is not called against the current runtime. Its
historical lock and companion are validated, all H-E0-DLTVM records are
reconstructed from Git, and only the components known to have been
superseded are exempted from physical-byte equality. Preserved components
must remain physically and historically exact.

## Adopted P1 bundle

The only adopted sequence publication is commit:

```text
82c0bc10a8b17ab700a8f0c28491a60572a11d81
```

It must be the direct child of P-E0-MC and contain exactly five additions:

```text
data/closure_v1/development/sequences/P1/seed_1729.parquet.dvc
reports/closure_v1/01_surface/sequences/P1/seed_1729_manifest.json
reports/closure_v1/01_surface/sequences/P1/seed_1729_summary.csv
src/experiments/audit_closure_p1_sequence_bundle.py
tests/test_audit_closure_p1_sequence_bundle.py
```

The read-only auditor must reconstruct and validate the physical Parquet,
summary, manifest, DVC pointer, E0-MC reference, boundaries, and exact
denominators without executing a consumer or model construction.

At the gate boundary the registered P1 namespace contains exactly the four
published sequence entries for seed 1729: Parquet, pointer, summary, and
manifest. All 19 consumer final, temporary, and guard paths remain absent.
All later-seed P1 paths, E0-M outputs, and the outcome-access log remain
absent.

## Availability semantics

The adopted bundle has 9,732 intent origins. In fit roles it contains:

```text
success                              8,925
autoregressive_target_unavailable      488
missing_target_state                   488
```

There are 17 additional unavailable rows in the calibration-threshold role.
Consequently the sequence is not scientifically fit-available. The only
permitted consumer result is:

```text
slot_status=model_unavailable
fit_status=not_attempted
failure_reason=sequence_fit_rows_unavailable
replacement_used=false
```

An effective E0-MD authority reports `p1_fit_authorized=true` solely to mean
that the locked temporal invocation may inspect the sequence and apply the
availability policy. It must simultaneously report
`sequence_fit_available=false`. No model, checkpoint, preprocessor, metrics,
curve, blend, or replacement artifact may be emitted. Only report plus
manifest may be published, with the manifest written last.

## Effective gate

The trainer calls:

```python
require_p1_temporal_consumer_authorized(
    model_id="P1",
    base_seed=1729,
    device="cpu",
)
```

before resolving output paths, acquiring the consumer guard, reading the P1
Parquet, or constructing a model. The returned authority binds:

- the exact E0-MD lock and companion records;
- the P1 artifact builder and current runtime builder records;
- the reconstructed E0-MC historical context authorization;
- the P1 bundle commit and audited availability evidence;
- the exact model, seed, and CPU device.

Any other model, seed, or device fails closed. At H-E0-MD and while the lock
is unpublished, both `p1_consumer_authorized` and `p1_fit_authorized` remain
false.

## Prohibitions

E0-MD does not authorize:

- another P1 sequence build or any retry;
- another P1 seed or batch execution;
- model fitting when retained fit-role failures exist;
- replacement, imputation, denominator adjustment, or row dropping;
- E0-M, E0-U, calibration-outcome access, evaluation, test, or holdout;
- post-2021 outcomes;
- DVC add, DVC push, Git commit, or Git push by the consumer.

## Lock workflow

After H-E0-MD is published, a separately authorized non-writing check runs:

```bash
poetry run python \
  src/experiments/lock_closure_p1_temporal_consumer_patch.py \
  --check-only
```

It must return `ready_to_lock`, keep both effective authorization flags false,
and perform no writes or DVC operations.

The separately authorized lock execution runs the frozen verification set,
the read-only P1 bundle audit, and two identical targeted DVC pushes for only
`seed_1729.parquet.dvc`. The second push must report exactly
`Everything is up to date.`. This external GCS egress requires informed
authorization at the execute-lock decision point; it is never run by
`--check-only`. The locker then publishes only lock and companion through
exclusive regular-file guards, no-clobber hard links, manifest-last ordering,
directory synchronization, and rollback limited to owned inodes.

Before publication:

```text
p1_consumer_authorized=false
p1_fit_authorized=false
publication_required=true
```

Only after exact `2A` publication and successful effective validation may the
single P1/1729/CPU consumer invocation proceed. Consumer execution requires a
new, explicit one-shot authorization and is not part of H-E0-MD or P-E0-MD.
