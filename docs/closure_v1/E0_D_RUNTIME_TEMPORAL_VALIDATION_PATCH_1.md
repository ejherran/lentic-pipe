# E0-DLTV: Closure V1 Temporal Provenance Validation Patch 1

## Status and scope

E0-DLTV is an additive implementation-provenance overlay over the immutable
E0-DL, E0-DLP, E0-DLS, and E0-DLT authorities. It does not change a scientific
decision, split, denominator, state mapping, seed, or failed-slot rule.
Evaluation, E0-U, holdout outcomes, and post-2021 outcomes remain sealed.

The trigger was the first authorized P0 seed `1729` consumer attempt after
P-DLT publication. The external gate and exclusive slot guard passed, but the
consumer stopped before Parquet schema access, row decoding, tensorization,
fitting, or output publication. Its completion-manifest validator compared the
builder recorded by the immutable P0 artifact with the builder currently
imported by the consumer. Those records intentionally differ:

```text
P0 artifact builder at b075d4f:
  bytes  110034
  sha256 dc500d94c8ca4b3705d2cb849a037524e33915624cd86f9d355e5c4eebb347f6

current H-DLT builder:
  bytes  110061
  sha256 b709fdfcad3c4f69c9ce399665a171fbdcc902b488e85a40f0e13da3c4785170
```

H-DLT changed only the builder's external authorization routing after P0 had
already been materialized. The P0 manifest is therefore correct historical
provenance, not stale evidence. Rewriting that manifest, rebuilding P0, or
temporarily restoring historical source bytes is forbidden.

## Closed validation correction

The temporal consumer now treats two records as separate domains:

- `p0_artifact_builder_record` is derived independently from the Git blob at
  the published P0 bundle commit. The manifest's `script`, `source_code`, and
  `inputs` builder records must all equal it, but the manifest is never trusted
  as the authority for that value.
- `current_runtime_builder_record` is derived from the H-DLTV Git component and
  revalidated against the physical builder imported by the consumer. It is an
  execution dependency and is recorded as such in new temporal evidence.

Both records have the same path but different bytes and hashes. They must not
be merged into one path-keyed record set. The consumer validates the historical
record against the immutable sequence artifact and the current record against
the live runtime separately.

The P0 result remains predetermined by the published sequence denominator:
488 fit-role origins are unavailable. Every P0 seed must therefore emit only
report plus completion manifest with:

```text
slot_status=model_unavailable
fit_status=not_attempted
failure_reason=sequence_fit_rows_unavailable
```

No checkpoint, model, preprocessor, metric, training curve, or blend artifact
may be emitted. No denominator reduction, imputation, replacement, or retry on
the old runtime is permitted.

## Historical authority and topology

The authority chain remains strictly additive:

```text
H-DLT 928ee7d17441de93478ad0ad076b76d0afe29de6
-> P-DLT 7ddacf6577f55508f37c5fb627117613efc8cbd3
-> H-DLTV
-> P-DLTV
```

H-DLTV must be a direct, non-merge child of P-DLT. Its exact Git diff contains
six modifications and five additions.

The six H-DLT components superseded by H-DLTV are:

```text
src/experiments/build_closure_pipe_sequences.py
src/experiments/rollout_closure_pipe.py
src/experiments/train_closure_pipe.py
tests/test_build_closure_pipe_sequences.py
tests/test_rollout_closure_pipe.py
tests/test_train_closure_pipe.py
```

The five H-DLT components preserved byte-for-byte are:

```text
configs/closure_v1/development_runtime_temporal_consumer_patch_lock.schema.json
docs/closure_v1/E0_D_RUNTIME_TEMPORAL_CONSUMER_PATCH_1.md
src/experiments/closure_development_runtime_temporal_consumer_patch.py
src/experiments/lock_closure_development_runtime_temporal_consumer_patch.py
tests/test_closure_development_runtime_temporal_consumer_patch.py
```

The five H-DLTV additions are:

```text
configs/closure_v1/development_runtime_temporal_validation_patch_lock.schema.json
docs/closure_v1/E0_D_RUNTIME_TEMPORAL_VALIDATION_PATCH_1.md
src/experiments/closure_development_runtime_temporal_validation_patch.py
src/experiments/lock_closure_development_runtime_temporal_validation_patch.py
tests/test_closure_development_runtime_temporal_validation_patch.py
```

Builder, trainer, and rollout entrypoints route to the new fail-closed gate.
P-DLT lock and companion, all nested historical authorities, the P0 Git/DVC
bundle, and the P0 payload remain unchanged.

## Lock procedure

After H-DLTV is committed, pushed, clean, and identical to live
`origin/main`, the non-writing preflight is:

```bash
poetry run python \
  src/experiments/lock_closure_development_runtime_temporal_validation_patch.py \
  --check-only
```

It validates the exact 6+5+5 topology, the historical and current builder
records, the physical P0 bundle, and absence of all 95 P0 consumer final,
temporary, and guard paths. It does not run verification commands or write an
output.

The real lock requires a separate explicit authorization:

```bash
poetry run python \
  src/experiments/lock_closure_development_runtime_temporal_validation_patch.py \
  --execute-lock
```

The locker runs the full type check, the closed focused suite with exactly
175 passing tests and no skip/deselection, `poetry check`, the
publication guard, and `git diff --check`. It also requires two identical,
targeted P0 DVC pushes, each terminating exactly with
`Everything is up to date.`. It never runs a sequence builder, temporal
consumer, rollout, evaluation, E0-M, E0-U, or outcome reader.

P-DLTV must add exactly these two files as a direct, non-merge child of H-DLTV:

```text
reports/closure_v1/00_protocol/development_runtime_temporal_validation_patch_lock.json
reports/closure_v1/00_protocol/development_runtime_temporal_validation_patch_lock_manifest.json
```

The companion is written last. Both outputs are reserved for the entire gate,
published without clobbering, validated from their actual bytes, and rolled
back by owned inode if the bundle cannot complete.

## Single retry after publication

The first authorization was consumed by a technical pre-output attempt. It is
not a completed model slot and cannot be reused. Only after P-DLTV is
committed, pushed, clean, unchanged, and aligned with live `origin/main` may
the new loader return effective CPU development-fit authorization.

Before retry, all 19 final, temporary, and guard paths for P0 seed `1729` must
still be absent and the P0 inputs must retain their locked hashes. A new,
explicit authorization is then required for exactly one retry of seed `1729`.
The retry must be audited immediately and must produce only report plus
manifest `model_unavailable`. The remaining four P0 seeds stay sealed until
that first corrected slot is published and reviewed.

P-DLTV does not replace E0-M and does not authorize P1, evaluation, E0-U,
holdout access, or post-2021 outcomes.
