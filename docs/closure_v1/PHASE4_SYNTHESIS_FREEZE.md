# Closure V1 Phase 4 synthesis freeze

Status: `H-SYN implementation candidate`
Closure source: `ea8ddce7f8edb9a61db97e29178e52603fa371b1`
Contract: `closure_v1_phase4_synthesis_v1`

## Purpose

Phase 4 is an adjudication, synthesis and writing phase. It is not a new
experimental phase. This freeze defines a deterministic, outcome-free route
from the published Closure V1 evidence to two evidence matrices, one closure
report, twelve replacement tables, eight replacement figures and one bundle
manifest.

The route is intentionally split into three publication gates:

1. `H-SYN`: implementation, schema, tests and this freeze;
2. `P-SYN`: immutable data-only authority for the implementation and inputs;
3. `R-SYN`: deterministic rendering of the exact 24-output synthesis bundle.

Each gate must be published before the next one is executed. `P-SYN` must be
the direct child of `H-SYN`, and `R-SYN` may be built only from a published and
effective `P-SYN` authority. A local implementation or an unpublished lock is
not sufficient authority for a later gate.

## H-SYN publication scope

H-SYN is frozen as exactly nine additions and two modifications:

- `configs/closure_v1/phase4_synthesis.schema.json` (add);
- `configs/closure_v1/phase4_synthesis.yaml` (add);
- `docs/closure_v1/PHASE4_SYNTHESIS_FREEZE.md` (add);
- `src/experiments/lock_closure_synthesis.py` (add);
- `src/reporting/build_closure_synthesis.py` (add);
- `src/reporting/closure_synthesis_contract.py` (add);
- `tests/test_build_closure_synthesis.py` (add);
- `tests/test_closure_synthesis_contract.py` (add);
- `tests/test_lock_closure_synthesis.py` (add);
- `src/data/prepare_commit_artifacts.py` (modify);
- `tests/test_prepare_commit_artifacts.py` (modify).

The H-SYN precommit transaction may stage only those eleven paths. It must use
`--allow-unmanaged --no-push`, must observe DVC status `{}`, and must not run
`dvc add`, `dvc push`, model fitting, scientific network access or synthesis
materialization.

The repository-wide publication guard is still mandatory. The source freeze
contains three already-published U1/U2/U3 activation records whose sealed
runtime-environment evidence includes the same two historical absolute paths.
The H-SYN adapter accepts only the byte-exact, Git-bound finding set for those
three records. Any additional path, credential, bucket, non-English text or
other publication finding fails closed; the compensated report records no new
finding rather than treating the historical exception as generic success.

## Input boundary

The only numerical or state inputs are the 83 repository-relative paths in
`allowed_inputs` in `phase4_synthesis.yaml`. The list is explicit,
lexicographically ordered and closed. Input discovery, recursive walks and
following paths embedded in manifests are forbidden.

Every allowlisted input must:

- be a regular, non-symlink, source-controlled file;
- have mode `100644` in the closure-source commit;
- match its exact Git blob at the closure-source commit;
- be valid structured CSV, JSON, YAML or a DVC pointer;
- remain read-only throughout P-SYN and R-SYN.

The allowlist contains the final structured E1-E10 artifacts plus the minimum
protocol, surface, cohort, calibration, sequence/model terminal-state and
software-evidence authorities needed to interpret them. Four `.dvc` files are
identity evidence only; their Parquet payloads are never resolved or read.

The following are outside the input boundary and must never be opened by this
pipeline:

- `private/`, including `private/FULL.md`;
- `data/targets/`;
- raw or materialized `.parquet` payloads;
- the outcome-access JSONL log;
- Markdown or XML as numerical sources;
- any path discovered from a manifest rather than listed explicitly.

The one-byte `nla_semantic_metrics.csv` is an intentional empty sentinel and is
declared with `allow_empty: true`. Header-only E6 outputs and the nine E9
`model_unavailable` actions are likewise evidence states, not missing files.

## Scientific invariants

The synthesis must preserve all of the following:

- `P0`, `P1` and `A2` remain visible as `model_unavailable`;
- no model, checkpoint, denominator, effect, interval or p-value is
  reconstructed or substituted;
- `not_estimable` is not encoded as zero, a negative result or evidence of
  equivalence;
- estimand labels and their weighting remain distinct;
- results from different estimands or freezes are not pooled;
- confidence intervals, when available, precede p-values in interpretation;
- descriptive evidence is not promoted to confirmatory evidence;
- Holm universes remain exactly `A=3`, `B=78`, `C=1`, `D=9`, `E=1`, including
  unavailable registered cells;
- H1, H2, H3, H4, H5a and H5b all receive an explicit adjudication;
- causal field claims and official management recommendations remain
  forbidden.

The controlled availability vocabulary is:

- `not_applicable`;
- `model_unavailable`;
- `insufficient_support`;
- `descriptive_available`;
- `confirmatory_available`.

The first three states are non-estimable and therefore require empty numeric
estimate and uncertainty fields. Textual pseudo-null values such as `N/A`,
`nan`, `null` or `none` are forbidden in numeric matrix cells.

## Matrices

`FINAL_CLOSURE_MATRIX.csv` is the hypothesis-level adjudication ledger. Its
column order is fixed by the contract and includes hypothesis, estimand,
population, model/pair, availability, attempted and successful denominators,
metric, estimate, uncertainty, multiplicity family, verdict, limitation,
evidence paths and authority commit.

The matrix contains exactly 130 rows: the 92 registered Holm cells, nine
A1-A0 descriptive deltas, twelve B2-B1 proxy summaries, one Carlson summary,
one E2 `0/1050` sentinel, one E6 `0/78` summary, one E8 `26/30` summary, four
E7 learning/membership sentinels and nine separate H5b rows. The H5b rows use
the registered `delta_objective_vs_no_action` endpoint and remain
`not_applicable`; they do not invent a net-benefit metric.

`THESIS_CLAIM_EVIDENCE_MATRIX.csv` is the writing boundary. Each row binds one
claim to a concrete artifact/filter/metric/denominator and records both
allowed and forbidden wording. It does not authorize manuscript editing by
itself; the matrices and `FINAL_CLOSURE_REPORT.md` must first be reviewed and
approved.

The claim matrix contains exactly 20 atomic rows and includes explicit reuse
boundaries for Chapter V, summary, abstract and conclusion in addition to
Methods and Results.

Both matrices use blank CSV numeric cells for unavailable estimates. They do
not use zeros or textual null tokens. Counts are integers. Other displayed
metrics use round-half-even only at the rendering boundary; scientific
decisions always use the unrounded source values.

## R-SYN output contract

R-SYN publishes exactly 24 regular files below
`reports/closure_v1/11_synthesis/`, in the order sealed by the YAML contract:

- two matrices;
- `FINAL_CLOSURE_REPORT.md`;
- tables `T01` through `T12`;
- figures `F01` through `F08`;
- `synthesis_bundle_manifest.json`, written last.

The table row counts are sealed as `T01=99`, `T02=33`, `T03=198`, `T04=24`,
`T05=11`, `T06=48`, `T07=31`, `T08=92`, `T09=7`, `T10=36`, `T11=87` and
`T12=5`. These counts prevent a generic source dump from satisfying the
contract. T01 is the 11-model by E1-E9 grid; T02 is the 11-model by
three-horizon funnel; T08 is the exact 92-cell Holm ledger; and T11 preserves
all 78 E6 cells plus all nine E9 actions.

Tables retain explicit source/filter/denominator columns and aggregate only
the groupings sealed by the contract; they never collapse availability or
estimands silently. SVG files carry a literal caption, a matching `<title>` and a
`<desc>` that records their source/filter boundary. The output manifest binds
every preceding path by byte count and SHA-256 and contains no wall-clock
timestamp.

F02 carries quantitative attempted, successful and metric-evaluable
availability by horizon alongside every conditional metric. F07 separates the
9/15 direct-ANFIS descriptive cells from 13 auxiliary B1/B2 context cells and
keeps the six direct unavailable/insufficient cells visible. F08 binds U3
`d72bb727f7d524bb423cb7cbaf425104291b7f31`, H4
`d53eaef9eb5aaf90fe02c8e337346879f6403c4d` and final freeze
`ea8ddce7f8edb9a61db97e29178e52603fa371b1`; it never substitutes an execution
identifier or prose placeholder for a Git identity.

R-SYN is a no-DVC bundle. Publication is exclusive and no-clobber: it uses a
guard under `tmp/closure_v1_phase4_synthesis/`, prepares private temporary
files, links outputs in contract order and rolls back only inodes it owns if
publication fails. An existing synthesis namespace is never replaced.

## Forbidden operations

H-SYN, P-SYN and R-SYN do not authorize:

- reopening or retrying E0-U;
- rerunning E1-E10;
- rescoring, refitting or reconstructing P0, P1 or A2;
- recalibration or threshold changes;
- reading raw targets, outcomes or DVC payloads;
- using `private/FULL.md` as evidence;
- editing the thesis manuscript before matrix/report approval;
- committing or pushing on behalf of the repository owner.

## Gate commands

Before H-SYN publication, the non-writing checks are:

```bash
poetry run python src/reporting/build_closure_synthesis.py --check-only
poetry run python src/experiments/lock_closure_synthesis.py --check-only
```

On the source commit, the first command must report `ready_for_p_syn`; the
second must report `ready_to_publish_h`. Neither command may create P-SYN or
R-SYN paths, guards or temporary files.

After H-SYN has been committed and published as the direct child of the
closure source, a separately authorized `--generate` creates only:

- `configs/closure_v1/phase4_synthesis_authority.json`;
- `configs/closure_v1/phase4_synthesis_authority_manifest.json`.

The companion manifest is written last. Publication of those two files as an
exact two-addition commit is required before any separately authorized
`--build` of R-SYN.

## Stop rules

Stop without retrying or widening scope if any of these conditions occurs:

- Git refs, parentage, live remote `HEAD`/`refs/heads/main` or
  worktree/index state drift;
- an H-SYN/P-SYN/R-SYN scope differs from its exact frozen set;
- an allowlisted file differs from its closure-source Git blob;
- a forbidden namespace, symlink, hardlink anomaly or existing output appears;
- the DVC status is not `{}` at the H-SYN publication boundary;
- P-SYN is partial, non-canonical, unpublished or not the direct child of
  H-SYN;
- a model/denominator substitution, reduced Holm universe or invented numeric
  result is detected;
- a guard, temporary file or rollback cannot be proven to be owned by the
  current transaction.

Any failure consumes no scientific authorization by itself, but the failed
state must be audited before a new mutating invocation is considered.
