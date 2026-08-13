# E0-MIB — Locked-evaluation input bundle

## Status and boundary

This document defines the additive `E0-MIB` prerequisite for the future
Closure V1 locked-evaluation batch.  It materializes an input-only evaluation
surface before the batch executable and the formal E0-M lock are created.  It
does not evaluate a model, decode a post-2021 target, inspect target
availability, calculate a metric, create an outcome-access record, or authorize
E0-M or E0-U.

The exact base is the published P-E0-MCALM commit
`81c1fc485902d484264fccc53cf88888c359930d`.  H-E0-MIB must be its direct,
non-merge child.  E0-MIB preserves the complete MCALM H/P history and the
published eight-file final-calibration/E7 bundle.  Those records are inputs to
the new authority; they are never regenerated, copied, normalized, staged, or
rewritten by E0-MIB.

The future scientific producer command is fixed as:

```text
poetry run python src/experiments/closure_locked_evaluation_input_bundle.py --execute-input-bundle
```

The command does not exist as authority merely because its source is present.
It becomes eligible for one input-bundle execution only after P-E0-MIB is
published and its effective loader succeeds.  The one-shot execution remains a
separate, informed authorization.  The H/P locker never invokes the producer.

## Why the input bundle is separate

The locked-evaluation batch needs a fixed intent-to-predict universe and fixed
input tensors before post-2021 outcomes can be opened.  Deriving that universe
from target availability after E0-U would permit outcome-dependent row
selection.  Conversely, embedding input construction in the future batch
would mix an outcome-blind cohort decision with outcome-bearing evaluation and
make a partial failure ambiguous.

E0-MIB therefore seals only information available from the permitted input
history.  It establishes which origins the system intended to predict and the
exact histories/features presented to the later evaluator.  Missing future
targets, unavailable models, and failed predictions never cause an origin to
be removed or replaced.

## Exact H, P, and R topology

H-E0-MIB has exact scope `1M+5A`:

- modification: `src/data/prepare_commit_artifacts.py`;
- addition: `configs/closure_v1/locked_evaluation_input_bundle_lock.schema.json`;
- addition: this document;
- addition: `src/experiments/closure_locked_evaluation_input_bundle.py`;
- addition: `src/experiments/lock_closure_locked_evaluation_input_bundle.py`;
- addition: `tests/test_closure_locked_evaluation_input_bundle.py`.

P-E0-MIB is a direct, non-merge child of H and contains exactly two `100644`
additions:

- `configs/closure_v1/locked_evaluation_input_bundle_lock.json`;
- `configs/closure_v1/locked_evaluation_input_bundle_lock_manifest.json`.

R-E0-MI is a direct, non-merge child of P and contains exactly six `100644`
additions.  Four are DVC pointer files and two are lightweight reports:

- `data/closure_v1/locked_evaluation/input_history.parquet.dvc`;
- `data/closure_v1/locked_evaluation/intent_origins.parquet.dvc`;
- `data/closure_v1/locked_evaluation/origin_features.parquet.dvc`;
- `data/closure_v1/locked_evaluation/sequence_features.parquet.dvc`;
- `reports/closure_v1/01_surface/locked_evaluation_input_summary.json`;
- `reports/closure_v1/01_surface/locked_evaluation_input_manifest.json`.

The four corresponding physical files are exact, heavy outputs outside the Git
scope:

- `data/closure_v1/locked_evaluation/input_history.parquet`;
- `data/closure_v1/locked_evaluation/intent_origins.parquet`;
- `data/closure_v1/locked_evaluation/origin_features.parquet`;
- `data/closure_v1/locked_evaluation/sequence_features.parquet`.

The producer publishes all four Parquet files and the summary before the
manifest.  DVC registration is a later directed R-precommit action and may add
only the four exact pointers.  The R manifest is the final lightweight output
and the final tracked R path.  No wildcard directory, implicit pointer,
additional report, model, prediction, target projection, or metric is part of
the R scope.

## Outcome-blind origin universe

The input upper bound is derived only from the last calendar month for which
the locked panel supplies the required permitted input fields.  It must not be
derived from the last observed target month, from a target join, from target
row counts, or from any test of post-2021 outcome availability.

An intent origin is eligible only when its canonical origin month is at least
`2022-01`, its location has the immutable Closure V1 holdout assignment, and
its permitted input-history contract can be evaluated without opening a
post-2021 outcome.  The bundle records every such origin even if a future
target, model, sequence, or prediction will be unavailable.

The producer must not materialize future target months while constructing the
input bundle.  For each retained intent origin and each locked horizon
`h in {1,2,3}`, the future month is calculated arithmetically inside the later
evaluation batch as `origin_year_month + h`.  That arithmetic does not imply
that an outcome exists.  Availability is learned only after E0-U and is
reported as a terminal evaluation status, never used to alter this bundle.

The four physical tables have disjoint roles:

- `intent_origins` is the unique, ordered intent-to-predict denominator and
  contains identifiers, assignment role, origin month, and audit lineage;
- `input_history` contains only the permitted historical observations needed
  by the locked models, with no current or lagged observed Chl-a lineage where
  the primary surface forbids it;
- `origin_features` contains deterministic, outcome-blind features fixed at
  the origin;
- `sequence_features` contains the exact ordered input tensors/masks and their
  model/seed applicability, while preserving explicit unavailability rather
  than substituting a different model or row.

Every table has an exact schema, column order, Arrow dtype/nullability
contract, lexicographic row order, unique key, row-count relationship, and
cross-table foreign-key rule in the E0-MIB runtime/schema.  Duplicate keys,
unknown columns, noncanonical months, a holdout-assignment mismatch, a
post-2021 target field, target-availability evidence, observed-Chl-a lineage
on a forbidden surface, or a missing intent origin fails closed.

## Forbidden science and authorization flags

H/P processing and effective P loading while R is absent are source-, config-,
Git-, ref-, remote-, and namespace-only.  `--check-only`, module import, schema
preflight, prelock collection, payload construction, payload validation, H/P
publication, and effective P loading before R exists must not:

- import or invoke the input-bundle scientific producer;
- open a panel, target, state, sequence, model, prediction, or Parquet file;
- inspect post-2021 outcome values or their availability;
- create an intent origin or derive the panel upper bound;
- run training, inference, calibration, degradation, planning, or metrics;
- run DVC add/push/pull, stage, commit, or push Git;
- create any E0-M output or the outcome-access log.

All H/P payloads and loader results keep `future_outcomes_accessed`,
`outcome_access_authorized`, `e0_u_authorized`, `e0_m_authorized`, training,
calibration, evaluation, DVC, staging, commit, and push authorization false.
The effective P authority may authorize only the exact future input-bundle
producer command and exact R namespace.  It never authorizes the future locked
evaluation batch.

Once R exists, terminal effective loading intentionally performs deep R
validation: it opens only the locked assignment, the permitted input-only panel
projection, and the exact four R Parquets to reconstruct the expected bundle
and require exact semantic equality.  It never opens a target, outcome, or
target-availability path and grants no evaluation or outcome authority.

The R producer remains outcome-blind.  It may read only the exact input sources
and identifiers named by P-E0-MIB.  Tests must tripwire panel/target loaders so
that H/P import and check-only cannot accidentally enter that code path; R
tests use synthetic fixtures for input-bound arithmetic and schema semantics.

## Companion and immutable predecessor bindings

The P companion has exact cardinality `16/6/1`:

- 16 current physical inputs: the two published P-E0-MCALM files, the six
  H-E0-MIB components, and the eight published calibration/E7 R outputs;
- six historical Git inputs: the exact superseded H-E0-MCALM component blobs;
- one output: the E0-MIB lock JSON.

Each current record binds path, Git mode/blob where applicable, SHA-256, size,
and stable filesystem identity.  Historical records are reconstructed from
the exact Git objects and are not compared with superseding worktree bytes.
The current locker occurs once as the companion `script` and once in current
inputs.  The companion is canonical JSON, has no duplicate keys, and is
published last.

The eight predecessor R outputs remain byte- and identity-exact throughout
check-only, verification, publication, guard release, rollback, and effective
loading.  E0-MIB validation of those files is local and science-free: it uses
their frozen byte/Git/output records, never follows their scientific input
inventories or decodes their content.

## H/P locker semantics

`--check-only` performs only schema preflight and two independent captures of
the exact H-over-base topology, clean index/worktree, local refs and live
remote, absent P/R/current coordination namespaces, immutable predecessor
bindings, and the exact 16-file physical snapshot.  It compares both captures
and writes nothing.  It runs no type check, pytest, Poetry check, publication
guard, diff check, science, DVC, staging, commit, or push command.

`--execute-lock` first repeats that read-only capture.  It then runs exactly:

- `poetry run ty check`;
- `poetry run pytest -q tests/test_prepare_commit_artifacts.py tests/test_closure_locked_evaluation_input_bundle.py`;
- `poetry check`;
- `scripts/check_repo_publication_ready.sh`;
- `git diff --check`.

The focused suite is frozen at exactly 48 passed, zero skipped, and zero
deselected.  The locker sanitizes `PYTEST_ADDOPTS`, disables third-party pytest
autoload, requires one exact terminal summary, and rejects warning, skip,
deselection, xfail, xpass, error, or failure markers.

After verification it recaptures schema, topology, refs/remote, namespace, and
all 16 physical identities.  Any drift fails before publication.  The
publisher acquires an exclusive no-follow guard, creates lock first and
companion last with anchored parent descriptors, exclusive temporary names,
and hardlink no-clobber, and repeatedly revalidates ownership and namespace
before and after guard release.  Rollback removes only still-owned E0-MIB
inodes.  A foreign file, symlink, directory, FIFO, socket, stale temporary, or
guard fails closed and is never removed.

`--check-effective` requires published P as clean `HEAD`, exact H as its direct
parent, the P-E0-MCALM base as H's direct parent, exact P scope `2A`, exact
`16/6/1`, canonical payload rebuild, live aligned remote, closed coordination
namespace, and unchanged predecessor R8.  It may report
`input_bundle_execution_authorized=true` only for the exact producer command,
with all evaluation/E0-M/E0-U/outcome flags false.

The locker never creates, stages, moves, registers, or hashes any future R
physical output.  P publication and R production require separate user
authorizations and manual barriers.

## R transaction requirements

The future R producer must revalidate effective P authority, the exact command
line, refs/remote, all source bindings, and an empty exact R namespace before
scientific imports or input reads.  It acquires one exclusive run guard and
uses no-follow parent traversal, exclusive temporary files, hardlink
no-clobber, stable input descriptors, and rollback by owned inode.

It snapshots every permitted source before reading and revalidates that
snapshot before each publication boundary, after manifest publication, after
guard release, and before ownership transfer.  The four physical Parquets are
published first in frozen order, followed by the summary and manifest last.
An in-process failure before transfer rolls back all still-owned R files; a
crash or foreign replacement leaves a visibly incomplete namespace that fails
closed and requires audit rather than automatic cleanup or retry.

The manifest binds all four physical SHA-256/size/schema/row records, the
intent-origin denominator, input-derived upper bound evidence, P authority,
producer/config/code hashes, exact output order, and explicit false outcome
flags.  It cannot claim target completeness, metric evaluability, model
success, E0-U, or E0-M.

DVC registration occurs only after an independent post-run audit under a new
authorization.  It must create exactly the four named pointer files, perform a
directed push of only those objects, verify the remote, and leave the physical
bytes/inodes and two lightweight reports unchanged.  The publication assistant
may then stage exactly R's six additions.  E0-MIB itself grants none of those
commands.

## Governance and acceptance

Governance covers exact base/H/P/R topology and modes; companion `16/6/1`;
science-free H/P import/check-only; the input-derived upper bound; origins
`>=2022-01`; arithmetic horizon expansion deferred to the batch; exact four
physical/six tracked R paths; no target or target-availability lineage;
deterministic canonical schemas; no-clobber, manifest-last, ownership rollback,
and release/loader races; and false E0-M/E0-U/outcome/DVC/evaluation flags.

Acceptance requires:

1. H-E0-MIB is exact `1M+5A` over `81c1fc4859...` and passes the focused 48,
   full type check, schema, Poetry, publication, and diff gates.
2. Check-only returns `ready_to_lock` with two equal science-free snapshots and
   zero writes or verification commands.
3. Execute-lock publishes only the exact P pair, lock first and companion last;
   the predecessor 16-file physical snapshot remains identical.
4. P-E0-MIB is published as exact `2A`; its effective loader returns only the
   narrow input-bundle execution authority.
5. Under a later one-shot authorization, R creates exactly four physical
   Parquets, four DVC pointers, one summary, and one manifest, with R exact
   `6A`, physical identity preserved through registration, and manifest last.
6. No post-2021 outcome value or availability is opened; no evaluation metric,
   model fit, prediction, E0-M file, outcome-access record, or E0-U authority
   exists at the E0-MIB terminal state.

Stop after each H, P, producer, DVC, precommit, and R-publication boundary for
an independent read-only audit.  The next phase is a separately designed
locked-evaluation executable and formal E0-M; neither is implied by E0-MIB.
