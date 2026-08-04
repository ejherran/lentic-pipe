# E0-DLS: Closure V1 Sequence Serialization Patch 1

## Status and scope

E0-DLS is an additive implementation erratum over the immutable E0-DL and
E0-DLP authorities. It does not amend a scientific decision, denominator,
mapping, seed, temporal split, or authorization boundary. Evaluation, E0-U,
and post-2021 outcomes remain sealed.

The trigger was the first authorized P0 sequence materialization. The runtime
gate and all development-only input checks passed, but PyArrow 24.0.0 stopped
while writing the Parquet payload:

```text
pyarrow.lib.ArrowNotImplementedError: Lists with non-zero length null components are not supported
```

The writer removed its temporary Parquet. The summary, completion manifest,
DVC pointer, and their temporary siblings were never created. The P0 one-shot
slot therefore remains unmaterialized and must not be retried until E0-DLS is
published and a new execution authorization is granted.

## Root cause

The closed sequence and rollout schemas use nullable Arrow fixed-size lists.
A logically unavailable row was represented in memory as a null list parent.
Every fixed-size list parent still owns a non-zero number of physical child
slots, and the Arrow Parquet writer does not support that representation. This
is the case tracked by Apache Arrow issue
[`apache/arrow#24425`](https://github.com/apache/arrow/issues/24425).

Scalar nullable targets are unaffected. Compression, dictionary encoding,
row-group geometry, and the scientific state values are not causal.

## Closed representation correction

E0-DLS preserves the physical types and logical absence policy:

- a failed sequence input remains `fixed_size_list<float32>[12]`;
- its list parent is physically valid and its 12 float32 children are null;
- a failed rollout state sample remains `fixed_size_list<float32>[128]` with
  128 null children;
- a failed rollout IRC sample remains `fixed_size_list<float64>[128]` with 128
  null children;
- scalar targets and `raw_bloom_score` remain scalar nulls;
- successful rows retain their original numeric payloads;
- `sequence_status` or `prediction_status` remains the authoritative failure
  indicator.

The temporal consumer recognizes a logically null failed input only when it is
either the pre-serialization `None` value or an exact length-12 tensor whose
children are all missing after Parquet/Pandas round-trip. A partially missing
tensor, a wrong shape, or any finite placeholder fails closed. Failed rows are
never tensorized for fit.

The same additive patch closes the one-shot publication race exposed during
the failed retry. A slot-specific exclusive guard under ignored `tmp/` is held
for the complete sequence construction, each final is published from an
exclusively created temporary inode with a no-clobber hard link, and broken
symlinks count as existing evidence. This is operational hardening only; it
does not change a value, row, denominator, role, mapping, or seed.

## Publication topology

H-DLS must be a direct, non-merge child of
`45705d620ad529b702624706b07e8a39fc138f72`. Its Git diff contains exactly six
modifications and five additions.

The six modifications are:

```text
src/experiments/build_closure_pipe_sequences.py
src/experiments/rollout_closure_pipe.py
src/experiments/train_closure_pipe.py
tests/test_build_closure_pipe_sequences.py
tests/test_rollout_closure_pipe.py
tests/test_train_closure_pipe.py
```

The five additions are:

```text
configs/closure_v1/development_runtime_sequence_patch_lock.schema.json
docs/closure_v1/E0_D_RUNTIME_SEQUENCE_PATCH_1.md
src/experiments/closure_development_runtime_sequence_patch.py
src/experiments/lock_closure_development_runtime_sequence_patch.py
tests/test_closure_development_runtime_sequence_patch.py
```

After H-DLS is committed, pushed, clean, and identical to live `origin/main`,
the non-writing preflight is:

```bash
poetry run python src/experiments/lock_closure_development_runtime_sequence_patch.py \
  --check-only
```

The real one-shot lock command requires a separate explicit authorization:

```bash
poetry run python src/experiments/lock_closure_development_runtime_sequence_patch.py \
  --execute-lock
```

It runs the full type check, the closed focused suite, `poetry check`, the
publication guard, and `git diff --check`. It does not run a sequence builder,
temporal fit, rollout, DVC operation, evaluation, E0-U, or outcome reader. It
also proves that all eight P0 final, temporary, and future-pointer paths are
absent at lock time. Both lock outputs are reserved by exclusive ignored
guards throughout those checks; publication is no-clobber and rollback removes
only inodes created by the locker. The gate revalidates the physical E0-DL
authority and the adopted E0-DLP seed/model/DVC bundle without requiring the
two E0-DLP components intentionally superseded by H-DLS to retain their old
hashes.

P-DLS is the direct, non-merge child of H-DLS and adds exactly:

```text
reports/closure_v1/00_protocol/development_runtime_sequence_patch_lock.json
reports/closure_v1/00_protocol/development_runtime_sequence_patch_lock_manifest.json
```

The lock records H-DLS and its eleven component hashes. The companion is
written last and records the lock hash. The future P-DLS commit is discovered
from Git history, avoiding a circular hash.

## Authorization after publication

Only the three affected entrypoints delegate to E0-DLS: sequence building,
temporal training, and Closure rollout. The ANFIS fitter and the historical
E0-DL/E0-DLP validators remain byte-unchanged. E0-DLS returns effective
development-fit authority only when its lock and companion are committed,
published, unchanged, live-remote aligned, and all historical and physical
development predicates pass.

After P-DLS publication, a new explicit authorization is required to run P0
once. DVC registration and promotion remain separate post-materialization
steps. E0-M must cite E0-DL, E0-DLP, and E0-DLS together.
