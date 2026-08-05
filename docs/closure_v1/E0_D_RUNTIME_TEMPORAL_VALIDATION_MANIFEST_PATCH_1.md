# E0-DLTVM: Closure V1 Temporal Validation Manifest-Dialect Patch 1

## Status and scope

E0-DLTVM is an additive implementation-only overlay over published H-DLTV
`40c0fb08b279383083d129f2228403e5753cddda`. It changes no scientific
decision, split, denominator, state mapping, seed, or unavailable-slot rule.
Evaluation, E0-U, holdout outcomes, and post-2021 outcomes remain sealed.

The trigger was the pre-commit validation of the unpublished P-DLTV bundle.
The strict DLTV loader correctly kept two builder domains separate, but its
generic companion placed the historical P0 builder in `inputs`. The generic
artifact assistant treats every record in that field as a current physical
dependency and therefore compared:

```text
P0 artifact builder at b075d4f:
  bytes  110034
  sha256 dc500d94c8ca4b3705d2cb849a037524e33915624cd86f9d355e5c4eebb347f6

physical H-DLTV builder at 40c0fb0:
  bytes  110067
  sha256 498c5b8ac673605e2164426624e968cd02c2180c2d2e0135c8e586c76b8ff411
```

Both records are correct. The first is immutable Git provenance for the P0
artifact; the second is the live runtime source. Rewriting either record,
temporarily restoring historical bytes, weakening the generic assistant, or
publishing a bundle with a reproducibility failure is forbidden.

## Closed dialect correction

The P-DLTVM companion has two disjoint fields:

- `inputs` contains only files whose byte count and SHA-256 must match the
  current physical path;
- `historical_inputs` contains Git-blob provenance and is never compared to a
  current path by the generic assistant.

The strict E0-DLTVM loader derives every historical record independently and
requires exact equality. The companion cannot self-declare its authority.
Historical P0 provenance is anchored to the Git blob at `b075d4f`, the P0
manifest triplet, and published P-DLT. Historical H-DLTV runtime provenance is
anchored to the Git blob at `40c0fb0`. The current runtime builder is anchored
to the H-DLTVM Git component and its physical bytes. All three records must be
distinct.

The generic artifact assistant remains unchanged. A regression executes its
real manifest validator with input hashing enabled and proves that historical
records are ignored only by that generic physical-input pass; current input
drift still fails. The strict loader continues to reject any mutation,
omission, duplication, or relocation of historical records.

## Historical authority and topology

The authority chain is:

```text
P-DLT 7ddacf6577f55508f37c5fb627117613efc8cbd3
-> H-DLTV 40c0fb08b279383083d129f2228403e5753cddda
-> H-DLTVM
-> P-DLTVM
```

H-DLTVM must be a direct, non-merge child of H-DLTV. Its exact Git diff is
closed to six modifications and five additions.

Modified runtime paths:

```text
src/experiments/build_closure_pipe_sequences.py
src/experiments/rollout_closure_pipe.py
src/experiments/train_closure_pipe.py
tests/test_build_closure_pipe_sequences.py
tests/test_rollout_closure_pipe.py
tests/test_train_closure_pipe.py
```

Added authority paths:

```text
configs/closure_v1/development_runtime_temporal_validation_manifest_patch_lock.schema.json
docs/closure_v1/E0_D_RUNTIME_TEMPORAL_VALIDATION_MANIFEST_PATCH_1.md
src/experiments/closure_development_runtime_temporal_validation_manifest_patch.py
src/experiments/lock_closure_development_runtime_temporal_validation_manifest_patch.py
tests/test_closure_development_runtime_temporal_validation_manifest_patch.py
```

The five H-DLTV authority additions remain byte-identical and are validated
from Git. Builder, trainer, and rollout route to the new fail-closed gate before
reading model, sequence, common-origin, or output paths.

## Lock procedure

After H-DLTVM is committed, pushed, clean, and aligned with live
`origin/main`, the non-writing preflight is:

```bash
poetry run python \
  src/experiments/lock_closure_development_runtime_temporal_validation_manifest_patch.py \
  --check-only
```

It validates topology, Git components, all three builder domains, the physical
P0 authority, and absence of all 95 P0 consumer final, temporary, and guard
paths. It runs no verification command and writes nothing.

The real lock requires separate explicit authorization:

```bash
poetry run python \
  src/experiments/lock_closure_development_runtime_temporal_validation_manifest_patch.py \
  --execute-lock
```

The locker runs the full type check, the closed focused suite with exactly 197
passing tests and no skip or deselection, `poetry check`, the publication
guard, and `git diff --check`. It also requires two identical targeted P0 DVC
pushes ending exactly with `Everything is up to date.`. These heavy and
external operations are not authorized by this source overlay.

P-DLTVM must be a direct, non-merge child of H-DLTVM and add exactly:

```text
reports/closure_v1/00_protocol/development_runtime_temporal_validation_dialect_patch_lock.json
reports/closure_v1/00_protocol/development_runtime_temporal_validation_dialect_patch_lock_manifest.json
```

The lock seals H-DLTVM and the companion dialect. The companion is written
last. Both files use exclusive guards, no-follow/no-clobber publication, and
owned-inode rollback.

## Authorization boundary

Before P-DLTVM publication the effective development-fit authorization remains
false. P-DLTVM never authorizes evaluation, E0-U, holdout access, post-2021
outcomes, or E0-M. A retry of seed `1729` requires a new explicit authorization
only after P-DLTVM is published and independently audited.
