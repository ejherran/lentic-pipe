# Closure V1 Phase 4 final doctoral certification

Status: `H-CERT4 publication candidate; suite locked`

Contract: `closure_v1_phase4_final_certification_v4`

Authorities:

- Closure source: `ea8ddce7f8edb9a61db97e29178e52603fa371b1`;
- R-SYN: `528dcb74a7c08b65f262901e4562a67b784db8c9`;
- editorial manuscript receipt: `d1daa3059462854d6ddf5199fbc05515cec76982`;
- historical H-CERT1: `003ca2282af5d7156b5814b59d8f1ddfb7fc681e`;
- superseded P-CERT1: `67983d8ea823a59eb4af55b59da04fb4ae298dcb`;
- historical H-CERT2: `8e01709c54330502aee318500ab9248e90fe17c5`;
- superseded P-CERT2: `72273b52d47df83acc7618fe98a887b74d690a13`.
- historical H-CERT3: `2372d0f9cc36aa916b79f34641b2b01134057890`;
- superseded P-CERT3: `bcd306a9e8dd5162466124d8854b9d1d99a8517c`.

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

The chain is single-parent and exact. H-CERT1/P-CERT1 and H-CERT2/P-CERT2
and H-CERT3/P-CERT3 remain immutable historical evidence; H-CERT4/P-CERT4 are
the only future effective authority. The compatibility names `H-CERT` and
`P-CERT` refer to H-CERT4 and P-CERT4:

```text
ea8ddce -> 528dcb7 R-SYN -> d1daa30 editorial
                                  |
                                  v
                      003ca22 H-CERT1 -> 67983d8 P-CERT1 (superseded failure)
                                                 |
                                                 v
                                    8e01709 H-CERT2 -> 72273b5 P-CERT2
                                                              | (superseded failure)
                                                              v
                                                   H-CERT3 -> P-CERT3 (superseded failure)
                                                                        |
                                                                        v
                                                             H-CERT4 -> P-CERT4 -> R-CERT
                                                                                           |
                                                                                           v
                                                                                  thesis-closure-v1
```

The gates have distinct roles:

1. **H-CERT1** and **P-CERT1** preserve the first implementation and authority.
   The consumed R-CERT launch failed immediately after `git clone`, before any
   DVC pull or R output, and P-CERT1 never authorizes another launch.
2. **H-CERT2** and **P-CERT2** preserve the first corrective overlay and its
   two-file authority. Their R-CERT launch reached the first directed DVC
   pull, which failed before any successful pull or R output. Cleanup then
   failed closed and preserved the owned run namespace. P-CERT2 authorizes no
   retry.
3. **H-CERT3** and **P-CERT3** preserve the diagnostic correction and its
   two-file authority. Its one-shot R launch failed on the first directed DVC
   pull with return code 1 and category `nonzero_exit`: zero pulls, cache
   objects, payloads, status checks, tests, PostgreSQL/Docker/OpenAPI/E2E runs
   and R outputs completed. Cleanup failed closed, preserved the namespace,
   did not mask the active error, and P-CERT3 authorizes no retry.
4. **H-CERT4** publishes only the credential-FD, two separated owned DVC
   site-cache and retained-runtime correction, schema, freeze, and tests. It
   cannot execute certification.
5. **P-CERT4** publishes a new two-file, data-only authority. It explicitly
   supersedes P-CERT3, P-CERT2 and P-CERT1. An unpublished P-CERT4 is
   ineffective.
6. **R-CERT** executes only from a clean, published P-CERT4 and publishes eight
   evidence files, manifest last.
7. The repository owner manually publishes the final R commit and the
   `thesis-closure-v1` tag.

The executable target is the published P-CERT4 commit. Executing from
P-CERT1, P-CERT2 or P-CERT3, adopting any failed temporary namespace, or treating a
superseded authority as effective is forbidden. This avoids a circular
claim: a commit cannot contain evidence generated before that evidence exists.
R-CERT may add only the exact eight regular evidence files, so its executable
tree must equal P-CERT's executable tree. The final tag points to published R.
The report must say this explicitly; it must not claim that R literally tested
itself.

At every gate, `HEAD`, `main`, `origin/main`, `origin/HEAD`, live remote HEAD
and live remote main must agree. The worktree and index must have only the
gate's exact unstaged or staged scope. H-CERT4, P-CERT4 and R-CERT must never
execute `dvc status` or any other DVC command in the main worktree. Main DVC
state is reconstructed only from the exact Git tree, the Git-bound tracked
`.dvc/config`, and the eight versioned pointer blobs; the authority records
`status_executed=false` and `static_boundary_verified=true`. Merges, extra
parents, renames, mode drift, scope widening, or an unpublished parent fail
closed.

## Exact publication scopes

Historical H-CERT1 was exactly `9A+2M` and remains byte-intact:

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

Historical P-CERT1 was exactly two additions and remains byte-intact:

```text
configs/closure_v1/phase4_final_certification_authority.json
configs/closure_v1/phase4_final_certification_authority_manifest.json
```

H-CERT2 is exactly `11M` over P-CERT1, with the same eleven paths shown in the
H-CERT1 list. Every path is modified, none is added or deleted, and
`src/data/prepare_commit_artifacts.py` remains mode `100755`; the other ten
paths remain `100644`.

P-CERT2 is exactly two new additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority_v2.json
configs/closure_v1/phase4_final_certification_authority_manifest_v2.json
```

H-CERT3 is exactly `11M` over P-CERT2, with the same eleven paths and modes.
Every path is modified; none is added or deleted.

P-CERT3 is exactly two new additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority_v3.json
configs/closure_v1/phase4_final_certification_authority_manifest_v3.json
```

H-CERT4 is exactly `11M` over P-CERT3, with the same eleven paths and modes.
Every path is modified; none is added or deleted.

P-CERT4 is exactly two new additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority_v4.json
configs/closure_v1/phase4_final_certification_authority_manifest_v4.json
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

All P1/P2/P3/P4/R files are single-link regular `100644` files. The final manifest is
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

R-CERT creates a fresh clone of live `origin/main` at the exact published P-CERT4
commit and an initially empty, private DVC cache. The main worktree and its
cache are never targets, and no DVC executable is invoked there. Real DVC
execution is confined to the owned isolated R-CERT clone. The builder runs
exactly eight directed pull commands, one pointer per directed pull command,
in the YAML order:

```text
.venv/bin/dvc pull --no-run-cache -j 1 {pointer_path}
```

Isolated configuration and directed status verification are auxiliary DVC
commands in that clone; they are not counted among the eight directed pulls.

The tracked `.dvc/config` does not contain the remote/default declaration.
The operational remote is supplied by the ignored `.dvc/config.local`. Before
execution that local file must be a single-link regular file with mode 0600 or
0644. A relative `credentialpath` is resolved privately below `private/`; its
target is opened no-follow, retained by descriptor, required to be a
single-link regular file with no group/other write bit, and rebased only in the
isolated copy to `/proc/self/fd/<fd>`. The descriptor is passed solely to DVC.
The source and isolated effective remote, URL and non-cache settings must be
equivalent. No credential name, URL, path, descriptor number, hash or content
is serialized.

Every isolated DVC command receives `DVC_SITE_CACHE_DIR` pointing to a private
owned `0700` directory inside the run, separate from the initially empty
object cache. A copied `core.site_cache_dir` is never used. The source main
site-cache metadata/inode inventory is snapshotted before the run and must
remain unchanged afterward; private site-cache payloads are neither opened nor
hashed by that lease check. Historical records created by earlier failed runs
are preserved, not deleted. Both owned site caches and the owned object cache
are removed with the temporary run. Pull success against the empty object cache
is the remote-availability evidence.

The public `environment.json.dvc` record keeps `main_dvc_command_run=false`
and additionally seals this exact retained-runtime/site-cache projection:

```yaml
owned_site_cache_count: 2
owned_site_cache_roles: [runtime_version, restore_status]
owned_site_cache_filesystem_mode: "0700"
owned_site_caches_separated: true
owned_site_cache_paths_serialized: false
version_seal_before_private_config_or_pull: true
single_dvc_runtime_retained_through_final_status_and_version_probe: true
dvc_runtime_cross_call_identity_revalidated: true
```

The final manifest's `clone.dvc_site_caches` block seals the same count,
ordered roles, mode, separation, path omission, version-seal ordering and
retained-runtime identity fields, plus exactly:

```yaml
used_by_all_isolated_dvc_commands: true
copied_core_site_cache_dir_used: false
```

Neither public record contains an owned site-cache path. The main site-cache
lease asserts only
`main_dvc_site_cache_metadata_inode_inventory_unchanged=true`; it makes no
byte/content equality claim.

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

The H-CERT4 suite lock is final. Two independent outcome-free collections over
the frozen bytes produced the same exact identity:

```yaml
suite_lock:
  status: locked
  selector_count: 39
  collected_test_count: 944
  nodeids_sha256: 8422082eca90068bf6d6fff4f1e4d9b9964535e12c8fd6b0844658bbdf683349
  allowed_skip_count: 7
```

The 39 selectors, 944 collected nodes, ordered-node digest and seven allowed
skips matched in both runs with the outcome-free guard active. The schema's
pending branch remains available only for integration fixtures; P-CERT4
generation and R-CERT reject it. Closure outcomes, raw targets and restored
Parquet payloads remained forbidden during both collections.

P-CERT3 remains byte-reconstructed with its historical 920-node suite lock;
H-CERT4/P-CERT4 supersede that operational lock without rewriting it.

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

Verification runs from the exact P-CERT4 clone with its tracked tree read-only, the
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

The P-CERT4 authority is canonical JSON. It reconstructs every historical
H-CERT1/P-CERT1/H-CERT2/P-CERT2/H-CERT3/P-CERT3 component from Git, every
active H-CERT4 component, all ten
anchors, all eight pointer records, the exact suite lock, output order,
isolation, diagnostic and authorization policies. It records P-CERT1,
P-CERT2 and P-CERT3 as superseded failed launches with no retry authorization.
Its companion is written last. Execution becomes effective only after the
exact two-file P-CERT4 commit is observed as the single-parent child of
H-CERT4 in local refs and live origin.

Every cooperating H/P/R publisher and the R builder serializes its whole
transaction with non-blocking exclusive `flock` on a retained descriptor for
the repository's `.git` directory. The legacy disposable guard path
`tmp/closure_v1_phase4_final_certification/certification.guard` must remain
absent; no certification component creates, adopts, renames, or removes that
path. The R builder snapshots main Git state and verifies the static DVC
boundary from the Git-bound tracked `.dvc/config` plus the eight versioned
pointer blobs, without invoking DVC in the main worktree. It then performs the
isolated work, prepares eight private temporary payloads, and links them
no-clobber in contract order. The manifest link is last, and every owned
temporary namespace must be cleaned before R precommit.

This is an explicit POSIX concurrency boundary. `unlink(2)` and `rmdir(2)`
address a directory entry by name; portable POSIX does not provide a
conditional “remove this name only if it still denotes inode X” operation.
The implementation therefore revalidates identity before and after name-based
cleanup as best-effort drift detection, but it does **not** claim conditional
unlink by inode. Any observed external namespace mutation is a STOP condition.
Non-cooperating mutation of the same namespace by another process running as
the same UID is out of scope; cooperating processes must honor the retained
`.git` flock.

The H-CERT2 correction admits exactly one directory-link increment only at the
`after_git_clone` transition: creating the owned `clone/` subdirectory changes
the owned work directory's `st_nlink` by exactly `+1`. Identity, mode and all
other transitions remain exact; any other link-count delta fails closed. The
clone is registered in the owned cleanup inventory after the exact transition
check and before any subsequent post-clone validation, so an early later
failure can be cleaned without adopting foreign names.
If safe owned cleanup succeeds, the primary exception is preserved. If cleanup
cannot be established as safe or itself fails, the cleanup/composite failure
prevails fail-closed; the contract does not claim preservation of the primary
error in that case.

The failed P-CERT2 launch established a narrower diagnostic requirement. The
active verification error may preserve only a portable, sanitized command,
its return code when available, and a safe stderr category when available.
Raw stdout, raw stderr, credentials and absolute paths are never preserved or
serialized. In the historical run the inner return code and safe stderr
category were not persisted, so P-CERT3 records them as `null` and
`unavailable_not_persisted`; it does not infer them from the orchestrator's
exit code.

P-CERT4 additionally seals the factual P-CERT3 launch record described above,
including return code `1`, category `nonzero_exit`, failed-closed cleanup with
the namespace preserved, and `retry_authorized=false`. It does not serialize
the retained namespace path or random run identifier; that ignored archive is
forensic evidence, not authority.

The builder retains its owned isolated-clone cleanup snapshot while auxiliary
configuration, the eight directed pulls and directed status verification run
there. A partial tree left by a failed DVC command is never adopted into
cleanup ownership and no unrecognized name is deleted. If final cleanup cannot
prove the namespace is still the exact owned namespace, the builder preserves
it. The surfaced composite error
must identify both the sanitized active verification error and the cleanup
failure; the cleanup failure cannot mask the active stage. No raw stream,
secret or absolute path may appear in that composite.

The final manifest binds the seven preceding outputs, P-CERT4 authority and
companion, historical H1/P1/H2/P2/H3/P3 and active H4 components, public anchors,
eight pointer/restoration records,
test and OpenAPI identities, environment and safety statements. The final
human report must retain this claim boundary:

> software restorability and reproducibility were certified; scientific
> efficacy was not re-evaluated or established.

## Precommit and manual publication

The precommit selector order is R-CERT, P-CERT4, H-CERT4, then earlier Phase 4
and historical adapters. Every gate uses:

```text
--allow-unmanaged --no-push
```

The adapter retains the same `.git` flock throughout its transaction and runs
the repository publication checker with only the already published,
byte-exact U1/U2/U3 findings compensated. Any new finding fails. It verifies
real generic manifests, exact paths/modes/blobs, aligned refs, the static
main-worktree DVC boundary from the Git-bound `.dvc/config` and eight versioned
pointer blobs, the recorded isolated-clone DVC evidence, targeted staging and
rollback that preserves foreign index entries. It does not infer or claim a
clean main-worktree DVC status. The legacy guard path remains absent.

H-CERT4 and P-CERT4 precommit do not clone, pull, test, generate OpenAPI, or create R
outputs. R precommit validates existing evidence and does not recertify or run
DVC. No adapter commits, pushes, or tags.

After the owner publishes R, the final audit must prove direct P-CERT4 parent,
exact8 scope, local/remote refs, clean Git, the static main-worktree DVC
boundary from Git plus the eight versioned pointer blobs, the isolated-clone
DVC evidence, effective manifest, and no owned temporary state. It must not
claim main-worktree DVC cleanliness because no DVC status command runs there.
The owner then creates and publishes
`thesis-closure-v1` at exact R. Once the local and remote peeled tag both equal
R, Phase 4 is complete and work stops.

## STOP conditions

Stop without widening scope or automatic retry on any of the following:

- ref, remote, parent, scope, mode, blob, tag or suite-lock drift;
- any attempt to execute R-CERT from superseded P-CERT1, P-CERT2 or P-CERT3,
  or reuse/adopt any retained failed-run namespace;
- a post-clone directory-link delta other than exactly `+1` at
  `after_git_clone`, or failure to register the clone after that exact
  transition check and before subsequent validation;
- loss of the primary error after safe owned cleanup, or any unsafe/unowned
  cleanup attempt; cleanup failure itself remains a fail-closed error;
- raw stdout/stderr, credentials or absolute paths in diagnostics; failure to
  preserve a non-exact namespace; or a cleanup error that masks the sanitized
  active stage instead of surfacing a composite failure;
- a non-pristine clone/cache, pointer mismatch, non-exact pull, missing
  restored object, any main-worktree DVC command, or static Git/pointer
  boundary drift;
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
