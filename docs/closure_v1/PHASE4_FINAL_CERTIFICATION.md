# Closure V1 Phase 4 final doctoral certification

Status: `H-CERT integration candidate`

Contract: `closure_v1_phase4_final_certification_v1`

Authorities:

- Closure source: `ea8ddce7f8edb9a61db97e29178e52603fa371b1`;
- R-SYN: `528dcb74a7c08b65f262901e4562a67b784db8c9`;
- editorial manuscript receipt: `d1daa3059462854d6ddf5199fbc05515cec76982`.

## Purpose and boundary

This contract closes Phase 4 with new, outcome-free evidence that the final
public software tree is testable, its OpenAPI surface is internally
consistent, its synthetic API workflow executes, and the eight exact DVC
objects required by the doctoral delivery are remotely restorable.

This certification is not a new scientific experiment. It does not authorize
another E0-U opening, E1--E10 execution, fit, reconstruction, scoring,
recalibration, threshold change, raw-target read, raw-outcome read, or Parquet
decode. It also does not turn software verification into scientific efficacy,
causality, ecological benefit, or a management recommendation.

The legacy plan once called E10 and writing “Phase 5”. The current continuity
authority explicitly consolidates final recertification into the last stage of
Phase 4. Completing this contract must therefore be followed by STOP; it does
not authorize work after Phase 4.

## Publication topology

The chain is single-parent and exact:

```text
ea8ddce ... -> 528dcb7 R-SYN -> d1daa30 editorial
                                     |
                                     v
                         H-CERT -> P-CERT -> R-CERT -> thesis-closure-v1
```

The gates have distinct roles:

1. **H-CERT** publishes implementation, schema, freeze, and tests. It cannot
   execute the certification.
2. **P-CERT** publishes a two-file, data-only authority. An unpublished P is
   ineffective.
3. **R-CERT** executes only from a clean, published P and publishes eight
   evidence files, manifest last.
4. The repository owner manually publishes the final R commit and the
   `thesis-closure-v1` tag.

The executable target is the published P-CERT commit. This avoids a circular
claim: a commit cannot contain evidence generated before that evidence exists.
R-CERT may add only the exact eight regular evidence files, so its executable
tree must equal P-CERT's executable tree. The final tag points to published R.
The report must say this explicitly; it must not claim that R literally tested
itself.

At every gate, `HEAD`, `main`, `origin/main`, `origin/HEAD`, live remote HEAD
and live remote main must agree. The worktree and index must have only the
gate's exact unstaged or staged scope, and main-worktree DVC status must be
`{}`. Merges, extra parents, renames, mode drift, scope widening, or an
unpublished parent fail closed.

## Exact publication scopes

H-CERT is exactly `9A+2M`:

```text
A configs/closure_v1/phase4_final_certification.schema.json
A configs/closure_v1/phase4_final_certification.yaml
A docs/closure_v1/PHASE4_FINAL_CERTIFICATION.md
M src/data/prepare_commit_artifacts.py                         mode 100755
A src/experiments/lock_phase4_final_certification.py
A src/reporting/build_phase4_final_certification.py
A src/reporting/phase4_final_certification_contract.py
A tests/test_build_phase4_final_certification.py
A tests/test_lock_phase4_final_certification.py
A tests/test_phase4_final_certification_contract.py
M tests/test_prepare_commit_artifacts.py
```

All other H paths have Git mode `100644`.

P-CERT is exactly two additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority.json
configs/closure_v1/phase4_final_certification_authority_manifest.json
```

R-CERT is exactly eight additions below a new namespace:

```text
reports/closure_v1/12_certification/public_tests.xml
reports/closure_v1/12_certification/test_report.md
reports/closure_v1/12_certification/openapi.json
reports/closure_v1/12_certification/openapi_contract_report.md
reports/closure_v1/12_certification/end_to_end_report.md
reports/closure_v1/12_certification/environment.json
reports/closure_v1/12_certification/FINAL_DOCTORAL_CERTIFICATION_REPORT.md
reports/closure_v1/12_certification/final_certification_manifest.json
```

All P/R files are single-link regular `100644` files. The final manifest is
created and linked last. An existing path is never adopted, replaced, or
truncated.

## Public evidence anchors

P-CERT binds ten regular public files to their exact Git blobs in the
editorial commit:

- tracked DVC cache configuration, recorded only by hash and Git identity;
- `poetry.lock` and `pyproject.toml`;
- the two public API contract documents;
- R-SYN's claim matrix and manifest;
- the editorial evidence-matrix manifest;
- the manuscript build receipt and its companion.

The receipt attests to the ignored private manuscript without embedding or
reopening it. It binds the 80-page PDF SHA-256
`b20908f37c93b8039431132ffb3def28fa08154b75cb5283011cf1f3bbb05044`
and the TeX SHA-256
`c9510de37877b7452f1397e5e13d54f5825df7e1b09b9cfb6bad8035ec0525dd`.
Final certification verifies that published attestation; it does not read the
private PDF, TeX source, listings, or `private/FULL.md`.

## Exact DVC restorability inventory

R-CERT creates a fresh clone of live `origin/main` at the exact published P
commit and an initially empty, private DVC cache. The main worktree and its
cache are never targets. The builder runs exactly eight commands, one pointer
per command, in the YAML order:

```text
.venv/bin/dvc pull --no-run-cache -j 1 {pointer_path}
```

The tracked `.dvc/config` does not contain the remote/default declaration.
The operational remote is supplied by the ignored `.dvc/config.local`. Before
execution that local file must be a single-link regular file with mode 0600 or
0644. It is copied or mounted only into the owned isolated clone; its bytes,
URL, path, remote name and credentials are not authority inputs and are never
serialized. Pull success against the empty cache is the remote-availability
evidence. The owned copy is removed with the temporary clone.

The four locked-evaluation scientific inputs are:

| Pointer | MD5 | Bytes |
|---|---|---:|
| `input_history.parquet.dvc` | `d02d1b0b94f740ce990d06a7a949b09c` | 480855 |
| `intent_origins.parquet.dvc` | `b9bad06b799f342f9bf54eb0a2cbec7a` | 171047 |
| `origin_features.parquet.dvc` | `da118c0515bdbd9705539bce1305bf11` | 238955 |
| `sequence_features.parquet.dvc` | `f858efff8a4c2e25f4c5b287258f0176` | 436677 |

The four final scientific outputs are:

| Pointer | MD5 | Bytes |
|---|---|---:|
| `data/closure_v1/degradation_masks.parquet.dvc` | `c483aab92229b79d5f77d4024c768be6` | 6037 |
| `data/closure_v1/predictions_long.parquet.dvc` | `8674d3247c5aa1a866199881c1389332` | 1794498 |
| `reports/closure_v1/05_inference/bootstrap_distributions.parquet.dvc` | `59ea9456ed60a49013fee3e0d0088711` | 2380 |
| `reports/closure_v1/09_planning/planning_origin_deltas.parquet.dvc` | `f67f23c22af0056b67852cc645703d19` | 7788 |

`--deps`, recursive scope, all-branch/tag/commit scope, `--allow-missing`, DVC
add, and DVC push are forbidden. The builder records pointer identity, declared
MD5/size, exact command result, regular restored output and directed DVC
status. DVC necessarily transports and authenticates bytes, but neither the
builder nor any test may open or decode a restored Parquet payload.

## Closed public suite

The suite has 33 positive test-file selectors. It preserves the historical
Phase 3/API public inventory and adds the final synthesis, editorial,
precommit and certification tests. Seven collected nodes have an exact skip
ledger:

- six historical tests whose repository-state or target-dependent behavior is
  outside the final outcome-free boundary;
- `test_check_only_before_p_syn_is_non_writing`, whose assertion is bound to
  the historical pre-P-SYN state rather than the final P-CERT tree.

The seventh node is already collected through its positive test file. It is
not repeated as a CLI selector. Consequently the exact non-duplicating command
selector count is 39: 33 file selectors plus six supplemental node selectors.
The skip ledger count is seven. Any other skip is critical and fails closed.

The public suite lock is final:

```yaml
suite_lock:
  status: locked
  selector_count: 39
  collected_test_count: 892
  nodeids_sha256: 583e39e0f1093c51be2421f88df250b2fc84ecd88e52087134a80cc91b8ec5a2
  allowed_skip_count: 7
```

Two independent collections over the exact 39-selector command produced the
same 892 unique node IDs and the same ordered-node digest shown above. Both
collections ran with the outcome-free guard active: Closure outcomes, raw
targets and restored Parquet payloads remained forbidden. The
`pending_integration` schema branch and `allow_pending_suite=True` remain only
for historical/integration fixtures; the real YAML is locked and the default
loader requires the exact values above. P-CERT and R-CERT never use the
pending escape hatch.

The public suite requires zero failures/errors, exactly the seven registered
skips, a full `ty check`, and `poetry check --lock`. E2E is exactly the three
synthetic external, non-Closure API nodes frozen in the YAML. A dedicated
loopback PostgreSQL fixture is required for the public HTTP test that would
otherwise skip.

## OpenAPI and environment evidence

The final OpenAPI contract must remain version 3.x with exactly 69 paths, 83
operations and 38 documented operations. Operation IDs must be unique, path
parameters exact, and documented operations missing from OpenAPI must equal
zero.

Verification runs from the exact P clone with its tracked tree read-only, the
host virtual environment read-only, and an owned writable temporary namespace.
OS masks plus the Python audit hook deny:

- all `private/` reads;
- `data/targets/`;
- raw/unblinded evaluation-outcome namespaces;
- the outcome-access log;
- all eight restored Parquet payloads during software verification.

External network is limited to cloning live origin and the eight directed DVC
pulls. The test sandbox permits loopback PostgreSQL only. The evidence must not
serialize credentials, remote URLs, database URLs, absolute local paths, home
paths, bucket names, or raw command output that may contain them. Portable
command templates and stdout/stderr hashes are sufficient.

Git commits created by unit-test fixtures are allowed only inside fixture-owned
temporary repositories. The orchestrator may not run Git commit, push, or tag;
those remain manual repository-owner actions.

## Authority and result publication

The P authority is canonical JSON. It reconstructs every H component, all ten
anchors, all eight pointer records, the exact suite lock, output order,
isolation policy and authorization policy. Its companion is written last.
Execution becomes effective only after the exact two-file P commit is observed
as the single-parent child of H in local refs and live origin.

Every cooperating H/P/R publisher and the R builder serializes its whole
transaction with non-blocking exclusive `flock` on a retained descriptor for
the repository's `.git` directory. The legacy disposable guard path
`tmp/closure_v1_phase4_final_certification/certification.guard` must remain
absent; no certification component creates, adopts, renames, or removes that
path. The R builder snapshots main Git/DVC state, performs the isolated work,
prepares eight private temporary payloads, and links them no-clobber in
contract order. The manifest link is last, and every owned temporary namespace
must be cleaned before R precommit.

This is an explicit POSIX concurrency boundary. `unlink(2)` and `rmdir(2)`
address a directory entry by name; portable POSIX does not provide a
conditional “remove this name only if it still denotes inode X” operation.
The implementation therefore revalidates identity before and after name-based
cleanup as best-effort drift detection, but it does **not** claim conditional
unlink by inode. Any observed external namespace mutation is a STOP condition.
Non-cooperating mutation of the same namespace by another process running as
the same UID is out of scope; cooperating processes must honor the retained
`.git` flock.

The final manifest binds the seven preceding outputs, P authority and
companion, H components, public anchors, eight pointer/restoration records,
test and OpenAPI identities, environment and safety statements. The final
human report must retain this claim boundary:

> software restorability and reproducibility were certified; scientific
> efficacy was not re-evaluated or established.

## Precommit and manual publication

The precommit selector order is R-CERT, P-CERT, H-CERT, then earlier Phase 4
and historical adapters. Every gate uses:

```text
--allow-unmanaged --no-push
```

The adapter retains the same `.git` flock throughout its transaction and runs
the repository publication checker with only the already published,
byte-exact U1/U2/U3 findings compensated. Any new finding fails. It verifies
real generic manifests, exact paths/modes/blobs, aligned refs, clean DVC,
targeted staging and rollback that preserves foreign index entries. The legacy
guard path remains absent.

H and P precommit do not clone, pull, test, generate OpenAPI, or create R
outputs. R precommit validates existing evidence and does not recertify or run
DVC. No adapter commits, pushes, or tags.

After the owner publishes R, the final audit must prove direct P parent,
exact8 scope, local/remote refs, clean Git/DVC, effective manifest, and no
owned temporary state. The owner then creates and publishes
`thesis-closure-v1` at exact R. Once the local and remote peeled tag both equal
R, Phase 4 is complete and work stops.

## STOP conditions

Stop without widening scope or automatic retry on any of the following:

- ref, remote, parent, scope, mode, blob, tag or suite-lock drift;
- a non-pristine clone/cache, pointer mismatch, non-exact pull, missing
  restored object, or main-worktree DVC change;
- any forbidden/private/raw/Parquet read or unexpected network access;
- a test failure/error, unregistered skip, OpenAPI mismatch, or E2E mismatch;
- an existing, partial, symlinked, hardlinked, or extra result path;
- a credential, remote/database URL, bucket name, or absolute local path in a
  public payload;
- any attempt to rerun E0-U/E1--E10, fit, score, reconstruct, recalibrate,
  change thresholds, run DVC add/push, or publish Git automatically;
- any request to begin work after Phase 4.

A transient remote, database or tool failure does not authorize an automatic
retry. Audit first. If code or contract bytes must change, publish a new H/P
chain. Scientific outcomes remain closed throughout.
