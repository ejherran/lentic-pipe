# Closure V1 E0-MA Model Availability Policy

## Purpose

E0-MA is an additive, development-only gate between the completed P0 slots and
the first P1 sequence build. It defines how the future E0-M model lock records
a terminal `model_unavailable` slot without weakening or rewriting any sealed
authority. E0-MA is not E0-M and does not authorize calibration, evaluation,
holdout access, or post-2021 outcome access.

All five fixed P0 seeds ended with the same terminal state:

- `slot_status=model_unavailable`;
- `fit_status=not_attempted`;
- `failure_reason=sequence_fit_rows_unavailable`;
- 8,925 fit-role sequences available and 488 unavailable because the
  autoregressive target state was missing;
- no model, checkpoint, preprocessor, metrics, training curve, blend artifact,
  calibrator, replacement, or denominator adjustment.

The counts are per fixed seed. They must never be summed across seeds and
reported as an ecological denominator.

## Additive Authority

The sealed `model_benchmark.yaml`, analysis plan, E0-DL lock, and E0-DLTVM
lock remain byte-identical. H-E0-MA adds exactly five files:

1. `configs/closure_v1/model_lock_availability_policy.yaml`;
2. its closed JSON Schema;
3. the read-only auditor, atomic generator, and strict published loader;
4. focused fail-closed tests;
5. this document.

The H commit must be a direct child of the fixed P0 closure commit
`1a4aa4836548756e74008fb934f56b5251d22491` and contain exactly those five
additions. No sealed runtime, builder, trainer, benchmark, or analysis file is
part of this slice.

## Denominator Authority

The registry reconstructs the P0 sequence denominator from the immutable
manifest and summary committed in `b075d4f1606aa35c1b86493604c18845f2d28a2f`:

| Time role | Intent | Success | Autoregressive target unavailable |
| --- | ---: | ---: | ---: |
| training | 8,352 | 7,909 | 443 |
| model selection | 1,061 | 1,016 | 45 |
| calibration threshold | 319 | 302 | 17 |
| all development origins | 9,732 | 9,227 | 505 |

The fit-role denominator contains only training and model-selection roles:
9,413 intent origins, 8,925 available sequences, and 488 unavailable origins.
These are input-availability counts, not attempted fits. Holdout overlap and
post-2021 rows are both zero. The auditor verifies the manifest, CSV,
role-specific reconstruction, physical SHA-256 records, and Git blobs at both
the source commit and the fixed P0 closure commit.

## Conditional Hash Matrix

| Slot state | Required evidence | Forbidden evidence |
| --- | --- | --- |
| `available/passed` | hashes for model, checkpoint, preprocessor, metrics, training curve, both blend outputs, and DVC ownership for heavy artifacts | missing or placeholder hashes |
| `model_unavailable/not_attempted` | immutable manifest/report, denominator, cause, no-replacement, input/source-record digests, and exact physical-absence evidence | model, checkpoint, preprocessor, metrics, training curve, blend, calibrator artifacts or hashes, including null placeholders |

Calibration artifacts are required only when an available upstream model has
reached the terminal `calibration_completed` state. An unavailable upstream
model is recorded as `not_attempted_upstream_model_unavailable`, with zero
calibration artifact records and physical absence across the paths registered
by E0-M. An identity calibrator for an available model must hash a serialized
identity specification rather than inventing a binary placeholder.

Code/config hashes, seeds, lineage, zero holdout-fit overlap, the sealed batch
command, and the outcome-access state remain unconditional future E0-M
requirements.

## Confirmatory Comparison

`H1_P1_vs_P0` remains in multiplicity family A with status
`not_estimable_model_unavailable`:

- no P0 replacement or model substitution is allowed;
- no denominator is adjusted;
- no effect estimate, confidence interval, or p-value is emitted or fabricated;
- the predeclared Holm family universe and family membership are retained for
  transparent reporting.

P1 remains meaningful against eligible comparators because P1 consumes the
paired ANFIS state rather than a fitted P0 model. This policy does not authorize
P1 fitting.

## Read-only Audit

The auditor verifies:

1. the closed policy/schema;
2. the exact linear five-commit P0 evidence chain;
3. exactly two additions, report plus manifest, in every seed commit;
4. each report/manifest against its original Git blob and the fixed closure
   commit;
5. all 23 input records and 10 source records per seed against physical bytes
   and SHA-256;
6. the exact 19-path namespace per seed, including broken-symlink semantics,
   with only report and manifest present;
7. the denominator authority described above;
8. absence of registry outputs/temporaries/guards, P1, E0-M, E0-U, and the
   outcome-access log. E0-M must later create that log in a present-and-empty
   state; creating it does not authorize outcome access.

```bash
poetry run python src/experiments/audit_closure_p0_model_availability.py \
  --check-only
```

Check-only performs no writes, DVC commands, network commands, or outcome-file
opens and reports each of those side effects explicitly as `false`.

## Registry Bundle and Atomicity

After H-E0-MA is published, a separately authorized `--generate` invocation
may create exactly two untracked files:

- `reports/closure_v1/00_protocol/p0_model_availability_registry.json`;
- `reports/closure_v1/00_protocol/p0_model_availability_registry_manifest.json`.

The generator requires a clean published H commit, aligned local refs, and the
same live `origin/main`. It holds two exclusive staging guards under ignored
`tmp/`, walks parents with directory file descriptors and `O_NOFOLLOW`, checks
that staging and destination share a filesystem, and publishes with hard links
that cannot clobber an existing path. The registry is published first and its
file record is placed in the companion; the companion completion marker is
published last. Any failure rolls back only inodes owned by the transaction and
preserves a third-party replacement.

The companion uses the generic experiment-manifest dialect:

- `status=completed`;
- a physical `script` record;
- physical `inputs` records;
- `outputs=[registry record]`;
- `completion_marker_written_last=true`.

Neither file is registered in DVC. The registry payload deliberately records
`effective_in_payload=false`; it cannot self-authorize.

Before reporting a successful transaction, the generator re-runs the full
local P0/denominator/absence audit while both exclusive guards remain held,
rehashes both owned final inodes, and reconstructs every registry and companion
field from the closed physical policy. Any discrepancy triggers inode-owned
rollback of the two-file bundle.

## Publication and Decision Gates

1. Review and publish H-E0-MA as the exact five-addition child of the fixed P0
   closure commit.
2. Re-run check-only from the clean published H commit.
3. **Decision point:** explicitly authorize `--generate`. This performs live
   remote verification and the one-shot local two-file write, but no DVC or
   outcome access.
4. Audit the two files, then separately authorize the precommit assistant.
5. Publish the registry bundle as an exact two-addition commit directly on top
   of H-E0-MA.
6. Run `--validate-published`. The strict loader requires both paths in the
   same 2A commit, the correct direct parent, canonical JSON, a clean worktree
   at that exact commit, and aligned local/live remote refs. Live remote
   verification is mandatory and has no bypass. The loader re-runs the closed
   P0 audit, rechecks absence of P1, E0-M, outcome log, temporaries, and guards,
   and reconstructs every scientific and publication field from the physical
   policy and Git-bound evidence. Only then does it return
   `registry_effective=true` and authorize the P1 sequence builder alone.
7. **Decision point:** explicitly authorize the one-shot P1 sequence builder
   for seed `1729`. Audit and publish that bundle before any P1 trainer or next
   seed is considered.

E0-M, E0-U, P1 fit, holdout access, post-2021 outcome access, and batch seed
execution remain unauthorized throughout E0-MA.
