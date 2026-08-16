# E0-U: Closure V1 Phase 3 sealed recovery batch

## Purpose

This contract defines the only permitted transition after the first sealed
Phase 3 execution consumed its one-shot authorization and failed after the
durable outcome-access boundary. It does not erase, replace, or reinterpret
that attempt. The recovery is a second attempt with a new published authority,
a new execution identifier, a new exclusive guard, and an append-only second
access-log record.

The historical chain is immutable:

```text
R  4c92ed7249a91b7dd541fd22dde68b61574556b2
H1 9e66478d7c071067a750e7dd9a6a318fa93a2c88
P1 caaf2d6d0a00a31febeed89b54ea078b60d7f92a
U1 4aecf19cd913b82a6a3d26669f09684e67efda8a
```

Recovery adds three direct, non-merge descendants without rewriting that
history:

```text
R -> H1 -> P1 -> U1 -> H2 -> P2 -> U2
```

H2 contains the source-level E1 correction and the recovery contract. P2 is a
new outcome-free evidence bundle generated against published H2. U2 is the
single recovery activation at
`reports/closure_v1/00_protocol/closure_e0_u_recovery_activation.json`,
generated against published P2. Git commit and Git push remain user-only
operations.

## Preserved first-attempt evidence

The canonical receipt
`reports/closure_v1/00_protocol/closure_e0_u_attempt_1_failure.json` records
only facts that remain observable or can be established from the sealed
source after the failed process exited:

- attempt 1 used execution
  `closure-v1-e0-u-caaf2d6d0a00a31f-735c2cf8ab3715aa`;
- the original activation is the 34,368-byte Git blob
  `32d90942b8a683aebacf44ca5fe6c2b12d1a3c7c`, with SHA-256
  `8f04bd4429717be662b6166c913fb1d15adaa69b1c0ba147d75162eb0a39bc94`;
- the append-only access-log prefix is exactly 256 bytes, contains one record,
  and has SHA-256
  `ae3e47dd6ad1f05cd79e6a494174f951f1c71fa9336514640bd4c15855c1b038`;
- the process exited with code 2 and the exact error
  `E0-U opened logical table scope drifted`;
- source-level review places the failure after full context materialization
  and outcome opening, but before E1 normalization, E1 metrics, or result
  construction; and
- none of the 52 final artifacts was published.

The old path `tmp/closure_v1_e0_u/sealed_batch.guard` was observed after
process exit as a regular, empty `0600` file with one link on device 2069 and
inode 80609290. That observation does not prove process ownership: the
authority's in-memory ownership identity is not recoverable after process
exit. The guard is therefore never deleted, adopted, or reused by recovery.
Its observation is versioned in the receipt; the physical file remains local
and untracked.

The receipt is a source-diagnosed recovery input, not a synthesized traceback
or a claim that the failed process emitted a cryptographically signed failure
record. Any mismatch in its canonical bytes, its historical Git binding, or
the access-log prefix fails closed.

## Recovery authority

U2 must bind all of the following before it can become effective:

- the exact R/H1/P1/U1 historical chain and original activation blob;
- direct-parent H2/P2 topology, exact H2 and P2 scopes, aligned local tracking
  refs, and live remote `main`;
- the canonical failure receipt and exact one-record access-log prefix;
- the corrected runner, current E0-U authority, context builder, evaluator and
  support sources, sealed runtime, batch contract, artifact order, and DVC
  policy;
- freshly generated H2-bound E10 source evidence and the preserved Phase 3
  input overlay; and
- the exact recovery command and distinct recovery guard path.

The Phase 3 context-builder source remains byte-preserved. The H2 runner owns
a closed recovery adapter: after authenticating that module's legacy E10 root,
manifest and seven-path tuple literally, it binds those names and the loader
only to the real P2 recovery namespace. The adapter forces
`recovery-attempt-1` and recaptures all four bindings before and after both
preflight and context materialization. It cannot synthesize or relabel a P1
snapshot as P2 evidence.

The activation is effective only after U2 is the published, direct one-file
child of P2 and `HEAD`, `main`, `origin/main`, `origin/HEAD`, and live remote
`main` agree. The worktree and index must be clean. The first access-log record
must remain byte-for-byte unchanged, all 52 output paths must remain absent,
and the new recovery namespace must contain no guard or temporary output.

The old activation remains historical authority for attempt 1 only. It cannot
authorize attempt 2. Conversely, U2 cannot relabel attempt 1 as outcome-free or
as a first attempt.

## Single recovery execution

The only authorized physical command is the exact line stored in
`reports/closure_v1/00_protocol/locked_recovery_batch_command.txt`:

```text
/usr/bin/env -i LANG=C LC_ALL=C .venv/bin/python -I -S -B src/experiments/run_closure_benchmark.py --execute-sealed-recovery-batch
```

The recovery runner uses only
`tmp/closure_v1_e0_u_recovery_1/sealed_batch.guard`. It never removes or
reuses `tmp/closure_v1_e0_u/sealed_batch.guard`. Before granting outcome
capability it validates the historical receipt, the unchanged one-record log
prefix, published U2, the sealed runtime and sources, and absence of every
final output.

The authority then appends and fsyncs a second canonical JSONL record before
opening outcomes. That record must identify `attempt_ordinal=2`,
`first_attempt=false`, the new execution identifier, and the published
recovery activation. Existing bytes are never truncated or rewritten. The
context is rebuilt and inputs are revalidated across the durable boundary;
the corrected E1 executor accepts only its declared least-privilege three-table
view before normalization.

On success the transaction publishes the same exact 52-artifact contract,
with manifest-last ordering, exclusive no-clobber publication, physical audit,
and DVC registration only after all outputs pass. The modified access log is
the fifty-third tracked path in the final sealed batch.

A failure before the second durable record requires a new versioned fix and a
new authorization. A failure after that record preserves both append-only
records and cannot be retried under U2. No direct evaluator invocation, output
salvage, manual log edit, guard deletion, model refit, target inspection, or
outcome inspection is authorized by this contract.
