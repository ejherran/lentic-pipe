# E0-U: Closure V1 Phase 3 sealed batch

## Purpose and irreversible boundary

This document defines the outcome-free preparation and the single irreversible
execution of the Closure V1 Phase 3 evaluation.  Phase 3 does not authorize a
collection of independent evaluator runs.  The only authorized physical
operation is the sealed runner transaction:

```text
/usr/bin/env -i LANG=C LC_ALL=C .venv/bin/python -I -S -B src/experiments/run_closure_benchmark.py --execute-sealed-batch
```

The transaction opens the post-2021 outcomes once, after a durable first log
record, executes E1 through E10 in memory, serializes all artifacts, publishes
exactly 52 outputs with one manifest-last sentinel per stage, and audits the
physical bytes.  Evaluators, target builders, compositors, and outcome readers
must not be invoked directly.

The immutable historical E0-M commit is
`4c92ed7249a91b7dd541fd22dde68b61574556b2` (R).  Phase 3 adds three direct,
non-merge descendants:

1. H, the outcome-free code, contract, documentation and test overlay;
2. P, the exact data-only evidence/input bundle generated against H;
3. U, the exact one-file activation generated against published P.

At execution, `HEAD~3`, `HEAD~2`, `HEAD~1`, and `HEAD` must be R, H, P, and U,
respectively.  `HEAD`, `main`, `origin/main`, `origin/HEAD`, and live remote
`main` must agree, the worktree and index must be clean, and the canonical
outcome access log must still be present and zero bytes.  Git commit and Git
push remain user-only operations.

The repository topology deliberately binds two distinct remote forms.  The
configured local `origin` must be exactly
`git@github.com:ejherran/lentic-pipe.git`, while live-remote authentication and
the activation manifest continue to use
`https://github.com/ejherran/lentic-pipe.git`.  A drift in either binding fails
closed; the SSH transport used for the configured origin is never substituted
for the HTTPS `ls-remote` authority.

The outcome-free H gate also requires its public regression suite to be
independent of the repository's current publication lifecycle.  Historical
ANFIS-registration tests reconstruct their pre-registration namespaces and
`.gitignore` inputs from sealed Git blobs or temporary fixtures; they never
reinterpret the already-published DVC pointers in the live H worktree as a
pre-registration state.  The historical DVC-interpreter regression treats a
changed system binary as the expected fail-closed result and exercises its
positive path in a synthetic fixture.  These repairs remain ordinary public
tests rather than adding broad E10 skips.  E10 executes a positive, H-bound
Phase 3 verification inventory: twenty-four exact test files plus twenty-four
additional exact node selectors.  It does not claim that repository-wide
discovery is one coherent estimand: the mature repository deliberately
preserves historical pre-publication tests and payload contracts from
mutually exclusive lifecycle states, while the E10 snapshot deliberately
omits target-bearing and unrelated ignored payloads.  The selected inventory
covers the Phase 3 authority, activation, context, E1--E10 contracts, source
evidence, API surface, publication adapters and the reconstructed historical
P0 authority; every selector is visible in the recorded command and bound to
H.
The frozen collection contains exactly 344 unique node IDs: 335 must pass and
the nine exact, classified nodes below remain visible as justified skips.
Consequently the final R-to-H scope is exactly 40 paths (24 modified and 16
added), and the corrective amendment on the published pre-repair H is exactly
thirteen modified paths.  The isolated ANFIS import repair was an exact four-
path amendment, and the subsequent E10 collection seal repair is an exact
five-path amendment; neither changes the final R-to-H exact40 scope.

## Preserved scientific decisions

The final availability decision is immutable:

- available: B0, B1, B2, F0, F1, M0, A0 and A1;
- terminally unavailable: P0, P1 and A2.

Unavailable models are not substituted, retrained, imputed with another model,
or removed from the intent denominator.  No evaluator may refit a model,
Platt transform, threshold, ordinal cutpoint, conformal factor, hypothesis, or
Holm family.  E2B remains `completed_unavailable` because no authenticated
pre-lock grouped prediction surface exists.  E6 and E9 remain terminally
unavailable under the current P1 decision while preserving their planned
denominators and confirmatory ledgers.

The evaluation unit is the source-scoped WQP monitoring location
(`source_id`, `site_id`), not a lake alias.  The locked location holdout has 88
sites and 4,488 common origins.  Horizons 1, 2 and 3 create exactly 13,464
intent-horizon rows.  E1 creates ten model families times five formal seed
slots per intent, or 673,200 prediction rows.  A2 has no formal slot and is
represented in the frozen hypothesis ledger, not by invented prediction rows.

All histories contain only the 12 months ending at the origin.  Observed
chlorophyll-a and all other future targets are forbidden from histories,
warmup state, model inputs and pre-open scoring.  Development fitting and
calibration end no later than 2021-12; the locked location holdout is mapped to
`evaluation_cohort=location_holdout`, `evaluation_role=test`.  Endpoint status
is explicit: bloom, continuous, uncertainty and ordinal availability are not
collapsed into one model-wide success flag.

## Authenticated context and scoring

`src/experiments/closure_phase3_context.py` is owned and authenticated by the
runner.  It is injected into the stdlib-only E0-U authority only after the
runtime has been sealed.  Model scoring happens before the first target open.
The context builder consumes the frozen R10 input surface, the R8 calibration
records, the immutable holdout assignment, and the P input overlay.  The P
overlay contains:

- a NumPy archive that exports the exact five-seed ANFIS and A0/A1 checkpoint
  tensors, including an internal canonical manifest and pre-outcome
  Torch-to-NumPy parity evidence;
- an adaptive-state warmup Parquet projected only from permitted physical
  input columns;
- a lightweight manifest written last.

The builder creates exact least-privilege views.  The initial authenticated
table registry is limited to `predictions_long`, `intent_origins`,
`target_outcomes`, `e2_site_strata`, `future_trophic_indicators`,
`hypothesis_registry`, `e7_predictions`, `locked_conformal_factors`, and
`uncertainty_evaluation`.  Each evaluator receives only its declared input
tables and prior stage outputs.  E7 and E8 views are derived from the E1
identity surface so their denominators cannot diverge.

Before the durable access record, the runner invokes the context module's
input-only preflight in the same sealed module namespace that will later build
the context.  That preflight authenticates and decodes every pre-target input
through directory-FD walks with `O_NOFOLLOW`, hashes and decodes each payload
from the same descriptor, recaptures the leaf and every ancestor, and completes
all model scoring without opening targets or the panel.  The authority's
Git/DVC binding for the P manifest, runtime NPZ and warmup Parquet must equal
the three records actually opened by this preflight.  The runner accepts only
the exact locked denominators and a closed snapshot digest.  The same snapshot
also includes the six E10 source payloads and their manifest as seven ordered,
single-descriptor records bound to H.

Before U can be written, the activation process loads the overlay builder only
after binding its physical bytes to the exact H blob.  It then reopens the 27
ordered input sources through anchored descriptors, decodes all 25 Torch
checkpoints with weights-only CPU loading, recomputes the 25 parity checks and
195 canonical arrays, and regenerates the NPZ, warmup Parquet and manifest in
memory.  All three regenerated payloads must be byte-identical to P.  U seals
this deep-validation receipt, including source and output hashes, counts,
projections and zero-outcome/zero-write assertions.  The stdlib-only authority
revalidates the receipt against H, the live P files and the P manifest before
granting E0-U; the one-shot runtime therefore does not need to import Torch.

After the access record has been appended and fsynced, the context builder
does not reuse any preflight DataFrame, array or model output.  It reopens,
rehashes, decodes and rescores all pre-target inputs through fresh anchored
descriptors and requires the complete ordered `(path, bytes, sha256)` snapshot
to equal the pre-open snapshot.  Only then may it open the target table and
the permitted panel projection.  A namespace replacement, symlink, inode
swap, source-evidence swap or input mutation on either side of the durable
boundary therefore fails closed.

The 90 R8 conformal factors are consumed and revalidated as locked `q_c`
values; they are never recomputed from evaluation data.  The 27-row frozen
hypothesis registry remains exact, with fixed Holm universes A=3, B=78, C=1,
D=9 and E=1.  Non-estimable hypotheses retain their ledger row and intent
denominator with null effect, confidence interval and p-value.

## Stage interpretation

The physical order is fixed:

```text
E1 -> E2 -> E3 -> E4 -> E5 -> E6 -> E7 -> E8 -> E9 -> E10
```

- E1 publishes the benchmark, endpoint-specific availability, failures and
  shared-success comparisons for the locked holdout.
- E2 publishes holdout stratification; legacy generalization gaps and E2B are
  explicitly non-estimable rather than reconstructed from fit data.
- E3 evaluates the prelocked probabilities and thresholds at 25/30/33/50
  without refit and computes differences only on exact shared-success rows.
- E4 preserves cohort/role and evaluates only legitimate ordinal endpoints
  against future trophic reference indicators.
- E5 emits the exact frozen confirmatory ledger and fixed Holm universes.
- E6 emits the 78 planned family-B cells as non-estimable under P1
  unavailability; it does not fabricate degradation predictions.
- E7 uses the new outcome-bearing namespace
  `reports/closure_v1/07_anfis_ablation_evaluation/`; the historical
  `07_anfis_ablation/anfis_learning_curve.csv` remains untouched.
- E8 evaluates raw and locked conformal uncertainty for A0/A1 and preserves
  family E as non-estimable for P1.
- E9 emits the planned inference, sensitivity, coherence and failure ledgers
  with the locked intent denominator; it does not fabricate planning deltas.
- E10 composes operational software evidence frozen against H.

Every metric distinguishes intent-to-predict, input-eligible,
prediction-success and metric-evaluable universes.  Quality comparisons use
the exact shared-success intersection; missing outcomes or failed predictions
never reduce the declared intent denominator.

## P evidence and input bundle

P contains exactly ten tracked additions and no Python source:

1. two DVC pointers for `phase3_runtime_weights.npz` and
   `adaptive_state_warmup.parquet`;
2. the input-overlay manifest;
3. six E10 source-evidence payloads;
4. the E10 source-evidence manifest, written last within that bundle.

The six evidence payloads are the complete JUnit report for the exact public
Phase 3 verification inventory, a human-readable test report, OpenAPI JSON, an
OpenAPI-to-contract report, an end-to-end report, and an environment record.
They bind the exact H commit, positive selectors, commands, database backend,
skips, contract hashes, offline DVC restore and outcome-isolation policy.  A
broad `pytest tests` command is forbidden by this contract.  The PostgreSQL
fixture is a nonce-named database proven absent before the run, created
exclusively for the generator, and dropped with absence verified in `finally`.
They live under
`reports/closure_v1/00_protocol/software_evidence_source/`, never in E10's
final output namespace.  Any code change after their generation invalidates P
and requires a new H plus regenerated evidence.

The public suite, OpenAPI, end-to-end and runtime probes execute in bubblewrap
against a materialized exact-H snapshot, never against the mutable host
worktree.  Tracked files are exported from the H tree; every permitted Closure
and model DVC pointer is restored copy-only from its authenticated local cache
object; and ordered inventories before and after execution must be identical.
The snapshot, host `.git` metadata and the locked `.venv` are mounted
read-only.  A private writable tmpfs is the only command workspace, Linux
capabilities are dropped, and no network is used for snapshot construction.

A synthetic read-only metadata directory hides the real `data/targets` tree;
opaque empty read-only overlays hide both future Closure namespaces;
`private/FULL.md` is replaced by an unreadable empty regular file; and the
tracked canonical access log is replaced by a read-only empty file whose only
permitted read returns synthetic EOF without opening the host path.  A
kernel-level probe records the exact read result and read/write errno for all
five masks: `ENOENT` for reads through the two opaque directories, `EACCES`
for target and `FULL.md` reads, synthetic EOF for the access-log read, and the
sealed `EACCES`/`EROFS` write outcomes by entry type.  The six selected nodes
that require real target artifacts and the three selected nodes that create
Git commits in temporary fixture repositories remain collected and are
skipped only by exact node-id registries, with their classifications preserved
in JUnit and the report.  No broader skip, Git commit or Git push is
authorized.

## U activation

The activation writer is outcome-free and must be invoked only from published,
clean P with the exact isolated command printed by its check-only result.  It
captures the runner, context builder, ten evaluator source records, three
support source records, the sealed Python/runtime dependency record, the batch
contract digest, the exact-52 path and publication-order digests, the R/H/P
scope records, the deep P regeneration receipt, and the DVC/Git policy.  It
publishes only:

```text
reports/closure_v1/00_protocol/closure_e0_u_activation.json
```

U must be the direct one-file child of P.  Generating U does not append the
access log and does not authorize a run from an unpublished or dirty tree.
After U is committed and pushed by the user, the published-validation mode
recaptures every bound source and runtime byte without opening outcomes or
writing files.

## Output ownership and DVC

The sealed transaction owns exactly 52 physical outputs across E1-E10.  Four
are Parquet and 48 are lightweight.  The activation partitions them before
unblinding:

- all four Parquets are physical outputs registered with explicit `.dvc`
  pointers only after a successful physical audit;
- the P runtime payload
  `data/closure_v1/locked_evaluation/phase3_runtime_weights.npz` is ignored by
  one exact repository-root rule and is published only through its explicit
  `.dvc` pointer; the pointer and lightweight overlay manifest remain in Git;
- all 48 lightweight artifacts are direct Git paths;
- implicit DVC discovery is forbidden;
- DVC push is permitted only after the post-publication audit and is separate
  from user-only Git push.

The 52 artifacts are published in the exact runner order.  Every stage
manifest is its stage's last output and the overall transaction uses exclusive
guards, parent descriptor chains anchored through transaction close, hardlink
no-clobber publication, and `unlinkat` rollback limited to device/inode pairs
created by the current process.  Repository-root or ancestor substitution is a
terminal failure and cannot redirect either publication or rollback.

## Final preflight and no-retry rule

Before the single run, all of the following must pass together: published
R-H-P-U topology and live remote binding; clean tree/index; empty access log;
all 52 outputs absent; no guards or temporary files; exact runtime; exact
source records; valid P input overlay; complete E10 evidence; explicit E2B,
DVC and unavailable-model policies; and a check-only that reports zero outcome
opens and zero writes.

After every context and component preflight, the runner performs two identical
sealed Git snapshots immediately before invoking the authority factory.  Both
must show U at `HEAD`, `main`, `origin/main` and `origin/HEAD`, the expected
symbolic refs, and an empty porcelain status including untracked paths.  Only
then may the authority append the first durable access record.

The user authorization is one-shot.  The first durable JSONL record is written
and fsynced before the context builder receives the capability to open targets.
A failure before that record requires a versioned fix and a new authorization.
A failure after the record preserves the non-empty append-only log and cannot
be represented as a first attempt; recovery requires an explicit transition,
new version and new authorization.  Once metrics are computed or the batch
succeeds, a second locked execution is forbidden.
