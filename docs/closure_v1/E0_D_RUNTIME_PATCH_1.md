# Closure V1 E0-D Runtime Patch 1

Status: closed implementation contract v1.3, effective only after P-DLP
publication, identified as `E0-DLP`. It is a consumer-dialect correction plus
the append-only R-DLP portable-evidence erratum and G-DLP guard-harness
isolation erratum, followed by the T-DLP frozen-state temporal-anchor erratum,
layered on the published E0-DL lock. None is a fourth runtime-compatibility
correction. This contract does not replace E0-DL or E0-M and does not authorize
evaluation, E0-U, holdout access, or post-2021 outcome access.

## Purpose And Incident Classification

The first ANFIS slot, base seed `1729`, completed successfully under the
published E0-DL authority. Its producer wrote all final files atomically and
wrote the completion manifest last. A later strict sequence-consumer check
rejected that already completed bundle for three representational reasons:

1. the producer persisted the canonical publication reference
   `origin/main`, while the consumer required the different spelling
   `refs/remotes/origin/main`; and
2. the producer wrote `module_metrics.csv` in its fixed CSV schema order, but
   the consumer reconstructed the expected order from the first metrics
   object after a `sort_keys=True` JSON round trip. That round trip sorts JSON
   object keys and therefore cannot define CSV column order; and
3. the historical fitter interpolated module display names such as `ANFIS-N`
   into checkpoint and sample-key artifact paths, while the E0-DL planned-path
   inventory uses the closed tokens `anfis_n`, `anfis_f`, and
   `anfis_t_no_current`.

None of these conditions changes a value, row, sample, fitted parameter, quality
gate, state column, checkpoint payload, or scientific decision. The producer dialect
is internally consistent: `origin/main` is the exact publication value emitted
by the runtime authorization summary, and the CSV header is the exact fitted
metrics schema emitted by the producer. The uppercase ANFIS artifact paths are
preserved only as the frozen historical seed-`1729` dialect; all future ANFIS
slots use the locked lowercase tokens in both producer and consumer. This is
therefore a runtime-compatibility incident, not a failed fit and not evidence
that the seed bundle is invalid.

The correction is deliberately narrow. The consumer must require the exact
producer value `origin/main`, must reject the alternative spelling, and must
validate the CSV against closed dialect-specific column tuples instead of JSON
object insertion order. It must accept uppercase ANFIS artifact paths only for the
exact frozen seed-`1729` manifest under the published E0-DLP authority, and it
must require locked lowercase path tokens for every future slot. No permissive
alias, column-set comparison, reordering, normalization, or best-effort
conversion is allowed.

The first P-DLP check-only audit then exposed a separate reproducibility defect
in the lock evidence itself. The v1 implementation tried to prove producer
write order from current workspace `st_mtime_ns` values. DVC had preserved the
state Parquet bytes but adopted it through a hardlink whose materialization
metadata postdated the already sealed manifest. Git and DVC do not version the
producer's POSIX timestamp ordering, so that predicate is neither portable to
a fresh clone nor scientific evidence. R-DLP removes that predicate and
replaces it with the Git-locked producer control flow plus the frozen
content-addressed bundle. This changes no runtime decision, seed artifact,
timestamp, DVC object, scientific result, or outcome-access boundary.

After R-DLP was published, P-DLP check-only passed. The first real P-DLP gate
then exposed a verification-harness collision: the production locker correctly
held both output guards while executing the fixed focal suite, but
`test_output_guards_do_not_change_real_git_status` tried to acquire those same
default guard paths from the nested pytest process. The suite failed before
DVC verification and before either output was written; the outer locker
released its own guards and left a clean tree. G-DLP isolates only that test's
ignored `tmp/` namespace. It does not make production guards reentrant, release
them early, reorder the locker, skip a test, or change the fixed 231-test
command.

After G-DLP was published, its check-only audit passed. The second real
`--execute-lock` attempt toward P-DLP advanced to final in-memory patch-lock
schema validation and stopped because the physical seed-state audit reported
`minimum_year_month=1970-10`, while the v1.2 schema, semantic validator, and
synthetic fixture incorrectly required `2000-01`. No P-DLP lock or companion
was written, retained, committed, or published. The rejected in-memory payload
and raw verification subprocess output were not persisted and are not treated
as versioned evidence. Under the sealed locker control flow, reaching final
schema validation implies that the preceding type check, focal suite, DVC
verifier, and second prelock collection returned; this contract records that
control-flow implication without reconstructing unpersisted stdout or stderr
hashes and without claiming a remote upload.

This was not data drift. The published E0-DL lock and expert-state lineage
already bind `1970-10`, and the frozen ANFIS-T sample-key artifact contains a
`1970-10` key. T-DLP corrects only the false v1.2 metadata anchor and moves its
exact validation into the check-only prelock path. It does not filter rows,
rewrite the state, change DVC ownership, alter the audit algorithm, or change
any scientific, authorization, or outcome-access boundary.

## Immutable Authorities And Frozen Evidence

The base E0-DL authority remains immutable:

| Record | Immutable value |
|---|---|
| E0-DL publication commit `L` | `e7becdd5553decc92bbcf0af4cede7425ed12546` |
| E0-DL locked repository head `H` | `4fe2d02a0abf4e044e5f2aa223c99ccc95ee7cd3` |
| E0-DL path | `reports/closure_v1/00_protocol/development_runtime_lock.json` |
| E0-DL SHA-256 | `5d858028ff5df561cc4a5e6086d9f83d08ac4c5ef6ffe27e844001f9fa495a81` |
| E0-DL lock version | `closure_development_runtime_lock_v1` |
| Planned heavy/light paths | `201` |
| Planned-path digest | `833fe57a573db135357a596949728fd0b6a436997ece0ba2c5555b815a42672c` |

E0-DLP must validate the original E0-DL component records against the Git
objects at the locked head, rather than pretending that the six allowlisted
current files still have their old bytes. It must then validate the current
bytes separately as the patch. The base JSON, its schema, its recorded hashes,
and its authorization claims must not be edited or regenerated.

The completed seed `1729` bundle is also immutable. Its frozen anchors are:

| Record | Bytes | SHA-256 |
|---|---:|---|
| `reports/closure_v1/01_surface/anfis/seed_1729/manifest.json` | 20,768 | `b38e54d21dd64edbf5a5968d9bee505569ea72b9f03c6750baf9a54114e9ef82` |
| `data/closure_v1/development/anfis/seed_1729/adaptive_no_current_state.parquet` | 1,215,081 | `c1987e31edb5b0f830f433120715f2abb7d7a375f8f38e6ad24056fc12447c69` |
| `reports/closure_v1/01_surface/anfis/seed_1729/lineage_audit.json` | 2,863 | `f54c8a5cdc15de8b31dd8337fda3ac1025ef500c7ad935811a643e4216e8a894` |

The manifest binds the following thirteen outputs. E0-DLP must adopt exactly
these physical records and no substitutes:

| Role/path | Bytes | SHA-256 |
|---|---:|---|
| Adaptive state Parquet | 1,215,081 | `c1987e31edb5b0f830f433120715f2abb7d7a375f8f38e6ad24056fc12447c69` |
| `ANFIS-N.pt` | 5,050 | `cbf3ec20445b0cdb0b4915bb3b5fcff3a293688cdf605fb1d4300728341b61d6` |
| `ANFIS-N_sample_keys.csv` | 463,207 | `754a8b8c29bdd40145f859983da64f3287ae8c527a413e0b9e8d68bb83a92b8c` |
| `ANFIS-F.pt` | 8,250 | `741d3ab0b9980c1f4c61447b1d9150bdd24ba649ab7c7057181c7c825c7bcfc6` |
| `ANFIS-F_sample_keys.csv` | 458,422 | `f15beef010139fcb8c5ef5f729d41e3de0a67492c87982f0f8a8a0838375ac72` |
| `ANFIS-T-no-current.pt` | 4,147 | `45064d6b3bffe102a4d4d6689f0bc0709791cd5df5b328323f96e7c3b507e6a8` |
| `ANFIS-T-no-current_sample_keys.csv` | 503,037 | `5b31f6b032df20b3e5a5a1d5fa2ba4b0beeeb174284ff5229b30bfe570a91114` |
| `module_metrics.csv` | 1,104 | `85ae8a11f52edf9c9cf927595782a64eff74ab76f1b58f4324095bd9ef274e22` |
| `training_curve.csv` | 7,673 | `bace68b15b08ce460d124f113961e827d4e415863933192a2b23c632fb372af8` |
| `memberships_initial.csv` | 1,293 | `cf49de8f2aa49679baeaad9d856acc6384c76f9f31d6e4fff3436f8ec6c46467` |
| `memberships_final.csv` | 1,719 | `f6d0fbcf7f04743a59a804162fb252f429e2bfe2bc4272bf27924490c7aff1bd` |
| `report.md` | 444 | `feb6e21a63d73cdf1312159ab0fdde7bd46b8fa1eb8e4cf9d32c9e487822aeae` |
| `lineage_audit.json` | 2,863 | `f54c8a5cdc15de8b31dd8337fda3ac1025ef500c7ad935811a643e4216e8a894` |

The manifest itself is the fourteenth physical final and the completion
marker. The complete bundle audit must prove `13` manifest output records,
`14` physical finals, matching sizes and SHA-256 values, no temporary files,
and no replacement or stale output.

Completion order is proved without filesystem timestamps. The historical
producer blob at `e7becdd5553decc92bbcf0af4cede7425ed12546` is exactly 59,865
bytes with SHA-256
`8177a9e19943222e51b16befc6f05e3978faa8abd46d37b7f43fa724fbd454f2`.
Its `write_anfis_slot_bundle` control flow ends with the atomic manifest write
to `anfis_manifest_template`, followed only by `return payload`. The historical
37,021-byte regression has SHA-256
`1022b4a1915e787fc92dae011d4d04a0a53f4dae784e64bdc442a9f906f212b6`
and contains `test_slot_bundle_writes_completion_manifest_last`. This producer
evidence is combined with `completion_marker_written_last=true`, all thirteen
manifest output records, all fourteen physical final hashes, exact DVC
ownership, and zero temporary/partial files. Workspace mtime, ctime, inode,
and link-count metadata are explicitly non-authoritative.

## One-Shot Preservation And Adoption

Seed `1729` must not be fitted again. Its Parquet, checkpoints, CSV files,
lineage audit, report, timestamps, and completion manifest must not be edited,
rewritten, normalized, copied over, or replaced. In particular, the JSON must
not be reordered to satisfy the consumer, and the metrics CSV must not be
reordered to imitate sorted JSON keys.

R-DLP must not touch or synthesize timestamps to imitate the original producer
order. The earlier DVC adoption may legitimately alter materialization
metadata while preserving content; `original_seed_rematerialized=false` in
this contract means that R-DLP performs no new fit, payload rewrite, copy, or
replacement. It does not claim that DVC never managed the physical link.

E0-DLP adopts the bundle as evidence generated while the unmodified E0-DL
authority was effective. Adoption is not retroactive production under the
patch and must not relabel the manifest's producer provenance. The manifest
continues to name execution head `e7becdd5553decc92bbcf0af4cede7425ed12546`,
publication ref `origin/main`, and the original E0-DL SHA-256. E0-DLP records
that immutable provenance plus the complete bundle identity in its own audit.

The legacy authorization-summary shape remains unchanged for compatibility
with the already sealed manifest dialect. The authoritative provenance chain
is external and conjunctive:

```text
E0-DL at L + E0-DLP at P-DLP
```

The later E0-M model lock must cite and verify both lock files. It must not
infer E0-DLP adoption merely from successful consumer validation.

## Central Overlay Design

E0-DLP is a central overlay, not a wrapper command. The central sequence
adapter owns the strict ANFIS-manifest validation used by sequence generation;
the training and rollout paths import that validation through their existing
dependency chain. Correcting the shared validator therefore preserves the
canonical commands and avoids a second family of wrappers or manifests.

The runtime authorization validator is made overlay-aware so that it can:

1. load and validate the immutable base E0-DL lock;
2. verify every base component against its Git bytes at the base locked head;
3. detect whether any base component differs in the current published tree;
4. require E0-DLP whenever a difference is present;
5. require that the complete difference is exactly the closed allowlist below;
6. validate the E0-DLP schema, ancestry, publication, file hashes, incident
   assertions, seed adoption, and seals; and
7. return the existing authorization-summary dialect only after the base and
   patch predicates both pass.

There is no fallback from a diverged base component to base-only authorization.
If any allowlisted file differs from E0-DL and the patch lock is missing,
untracked, unpublished, stale, or invalid, effective fit authorization is
false before modeling-row or model I/O. If no base component differs, the
original E0-DL validation remains sufficient.

## Exact Closed Allowlist

The only E0-DL-recorded paths permitted to differ are:

```text
src/experiments/build_closure_pipe_sequences.py
src/experiments/closure_development_runtime_lock.py
src/experiments/fit_closure_anfis_state.py
tests/test_build_closure_pipe_sequences.py
tests/test_closure_development_runtime_lock.py
tests/test_fit_closure_anfis_state.py
```

The only new patch components, introduced in A-DLP and unchanged in H-DLP,
are:

```text
configs/closure_v1/development_runtime_patch_lock.schema.json
src/experiments/closure_development_runtime_patch.py
src/experiments/lock_closure_development_runtime_patch.py
tests/test_closure_development_runtime_patch.py
docs/closure_v1/E0_D_RUNTIME_PATCH_1.md
```

R-DLP modifies exactly four of those already introduced paths and no other
path:

```text
configs/closure_v1/development_runtime_patch_lock.schema.json
docs/closure_v1/E0_D_RUNTIME_PATCH_1.md
src/experiments/closure_development_runtime_patch.py
tests/test_closure_development_runtime_patch.py
```

R-DLP is therefore four modifications relative to H-DLP while the aggregate
`L..R-DLP` inventory remains the same `23` unique paths.

G-DLP modifies exactly those same four already introduced paths. It changes no
locker source and adds no path. G-DLP is therefore four modifications relative
to R-DLP while the aggregate `L..G-DLP` inventory remains the same `23` unique
paths.

T-DLP modifies exactly those same four contract paths once more. It changes no
locker source and adds no path. T-DLP is therefore four modifications relative
to G-DLP while the aggregate `L..T-DLP` inventory remains the same `23` unique
paths.

The only new P-DLP artifacts are:

```text
reports/closure_v1/00_protocol/development_runtime_patch_lock.json
reports/closure_v1/00_protocol/development_runtime_patch_lock_manifest.json
```

The patch lock must store the path, byte size, SHA-256, base-record SHA-256
where applicable, and role for every path in those closed sets. It must also
store an ordered digest of each set so that omission, addition, aliasing,
renaming, traversal, symlink escape, duplicate paths, or case drift fails.

No other base component or runtime dependency may drift. The only fitter
change is display-name-to-token path rendering; the planned paths and payload
schemas do not change. In particular, this patch forbids changes to the
protocol lock, E0-DL JSON or schema, runtime YAML or schema, experiment matrix,
primary/secondary surface configs, model benchmark, seed schedule, mapping,
trainer, rollout implementation, planned-path inventory, DVC ownership model,
target metadata, assignment, common-origin bundle, expert-state bundle, or
restored sources. The patch must not expand its own allowlist after
publication.

## Publication Gates

### A-DLP: Frozen-Artifact Adoption And Patch Preparation

The generic publication assistant verifies every staged seed-manifest input
against the current filesystem, including the historical runtime validator.
To preserve that valid check, A-DLP is published while the runtime-validator
and fitter bytes are still unchanged. It contains exactly `19` paths relative
to `L`: the immutable seed manifest and nine lightweight outputs, the explicit
state pointer, the updated `models.dvc`, the sequence-consumer correction and
its regression, and the five new patch components. The historical fitter,
runtime validator, and their tests remain byte-identical to `L` in A-DLP.
The separately authorized DVC operation and two identical targeted pushes,
invoked through the fixed repository executable `.venv/bin/dvc`, must complete
before A-DLP. A-DLP does not authorize another fit or consumer run:
the sequence-builder drift makes the original E0-DL gate fail closed.

### H-DLP: Patch Implementation

H-DLP is a direct non-merge child of A-DLP. It changes exactly four paths: the
runtime validator and its test, plus the fitter path-token renderer and its
test. Across `L..H-DLP`, the complete diff therefore contains exactly `23`
paths: six allowlisted modifications, five new components, and twelve
immutable seed/DVC adoption records. Before publication it must pass:

- the closed patch schema and validator tests;
- regressions for the exact `origin/main` reference and rejection of
  `refs/remotes/origin/main`;
- a sorted-JSON round-trip regression proving that fitted CSV order is
  independent of JSON key order;
- a regression proving that future fitted and unavailable slots use the
  locked lowercase artifact tokens while the exact frozen seed `1729` retains
  its uppercase historical paths;
- exact fitted and unavailable metrics-column dialect tests;
- mutation tests for every path, hash, ancestry, publication, seed-adoption,
  and seal predicate;
- sequence, training, and rollout import-chain regressions;
- the full repository type check and the required focal test suite; and
- the repository precommit/publication assistant with no unexplained warning
  or failure.

H-DLP must then be committed and published as a clean descendant of `L`, with
the live remote branch resolving to the same commit. The frozen seed bundle is
not rewritten or smuggled into H-DLP. From the moment H-DLP changes a base
component until P-DLP is published, all affected fit, sequence, training, and
rollout entry points must fail closed.

### R-DLP: Portable-Evidence Erratum

R-DLP is a direct non-merge child of H-DLP commit
`350c6b61c497384f5db7fee99e731c02d521e33d`. It modifies exactly the schema,
protocol document, patch validator, and patch-validator test listed above. It
must preserve A-DLP at
`e8fa8b8e8ca26e3457bd073934c158c1d8ee15bf`, H-DLP, their direct-parent
topology, and the exact `19 + 4 + 4` publication sequence. Since the four R-DLP
paths were introduced in A-DLP, the aggregate `L..R-DLP` diff remains exactly
the same 23-path A/M inventory.

The v1.1 contract introduced an explicit implementation erratum classified as
`reproducibility_evidence_correction_only`. It supersedes only
`workspace_filesystem_mtime_order_v1` and requires
`filesystem_mtime_used=false`. The replacement evidence verifies the exact
historical producer and regression Git blobs, parses the producer control flow
fail-closed, binds the manifest marker and all frozen file hashes, and treats
DVC materialization metadata as non-authoritative. It must reject any mtime,
ctime, inode, or link-count field and any content, path, ownership, or topology
drift.

R-DLP adds no fourth runtime correction, changes no authorization or seal, and
does not run a fit, DVC operation, sequence builder, training job, rollout, or
outcome read. It must retain the exact `231`-test focal suite, pass the full
type check and repository publication assistant, and be published cleanly
before G-DLP is prepared.

### G-DLP: Nested Guard-Harness Isolation

G-DLP is a direct non-merge child of R-DLP commit
`65f169bf3357a9a3b9aaee19883d33b5fb0278d0`. It modifies exactly the same four
contract paths as R-DLP and preserves the complete direct-parent sequence
`L -> A-DLP -> H-DLP -> R-DLP -> G-DLP`. The segment cardinalities are
`19 + 4 + 4 + 4`; because R-DLP and G-DLP modify the same paths introduced in
A-DLP, the aggregate `L..G-DLP` inventory remains exactly 23 paths.

The v1.2 lock records
`nested_guard_regression_namespace_collision_1` as a
`verification_harness_isolation_correction_only` erratum. The existing test
uses a unique digest-derived output and guard namespace directly under the
ignored repository `tmp/` root, verifies the real Git status before and during
guard ownership, confirms that any live production-guard entries are
unchanged, releases only its own inodes, and removes its empty namespaces. The
digest is not persisted and exposes no local path.

Production continues to use `tmp/closure_v1_e0_dlp_locker`; both production
guards remain exclusive and held for the entire gate. G-DLP does not modify
the locker source or execution order, does not change the fixed focal command
or its exact `231` count, and does not skip or weaken any guard regression. The
failed pre-G attempt wrote no outputs and did not reach DVC. G-DLP changes no
scientific contract, artifact, DVC owner, authorization, seal, or outcome
access.

### T-DLP: Frozen-State Temporal-Anchor Erratum

T-DLP is a direct non-merge child of G-DLP commit
`5580343cd7d4ecf215f1fb638633106b7aaf0f92`. It modifies exactly the schema,
protocol document, patch validator, and patch-validator test already modified
by R-DLP and G-DLP. It preserves the complete direct-parent sequence
`L -> A-DLP -> H-DLP -> R-DLP -> G-DLP -> T-DLP`. The segment cardinalities
are `19 + 4 + 4 + 4 + 4`; because every post-H erratum modifies the same four
paths introduced in A-DLP, the aggregate `L..T-DLP` inventory remains exactly
23 paths.

The v1.3 lock records `seed_state_minimum_year_month_anchor_drift_1` as a
`frozen_metadata_anchor_correction_only` erratum. It supersedes only the
unsupported synthetic value `2000-01` with the authoritative `1970-10` bound.
The authority is the published E0-DL expert-state semantic audit, its public
lineage audit, and the frozen ANFIS-T sample-key evidence. The exact physical
seed-state audit is checked against those anchors during prelock collection,
so `--check-only` now fails before type checking, pytest, or DVC if they ever
diverge again. Final payload validation reuses the same closed audit helper.

T-DLP changes neither the physical audit algorithm nor any state byte,
timestamp, row selection, DVC pointer, DVC owner, locker source, locker order,
fixed test command, authorization, seal, or outcome boundary. The focal suite
remains exactly 231 tests. The failed attempt toward P-DLP reached final schema
validation but persisted no payload, raw subprocess log, lock, or companion.
Its DVC-verifier return is recorded only as an implication of the sealed locker
control flow; no remote-upload claim is reconstructed.

### P-DLP: External Patch Lock

Only after T-DLP is clean and published may the external locker generate
`development_runtime_patch_lock.json` and its lightweight publication
manifest. The locker is one-shot and outcome-blind. It must refuse either
existing final, either temporary path (including broken symlinks), any
non-regular output, or any non-default input/output path, and must not modify
E0-DL or any seed file. `--check-only` performs no type check, test, DVC push,
or write. `--execute-lock` reserves both output paths with exclusive
no-follow guards for the entire gate, runs the fixed full type check, the
fixed `231`-test focal suite in a sanitized pytest environment, and two exact
already-up-to-date targeted DVC pushes through `.venv/bin/ty`,
`.venv/bin/pytest`, and `.venv/bin/dvc`, respectively, then proves that the
prelock state did not change. It publishes the authoritative lock first and the
non-authoritative generic-precommit companion last using atomic no-clobber
links. On failure it removes only output inodes created by that invocation.

P-DLP must bind:

- the exact E0-DL path, version, SHA-256, locked head, and publication commit;
- A-DLP, H-DLP, R-DLP, G-DLP, and T-DLP's exact direct-parent topology from
  `L`, T-DLP's canonical origin identity, live publication reference, and clean
  tracked state;
- the complete closed path sets and their current Git/physical hashes;
- the three exact runtime-compatibility corrections and their regression
  evidence;
- all fourteen frozen seed `1729` file records and the portable
  content-addressed completion-order evidence;
- all three errata and the preserved production-guard semantics;
- the unchanged scientific anchors and authorization boundaries; and
- every seal in the next section.

The generated pair must be reviewed and committed as one direct, non-merge
child of T-DLP. That P-DLP commit contains exactly two additions—the lock and
its companion—and no modification or unrelated file. Both must be regular
files, no descendant commit may touch either path, and their bytes must remain
identical in P-DLP, current HEAD, local `origin/main`, and the live remote.
Effective patched development-fit authorization becomes true only after that
publication. It never authorizes evaluation, E0-U, or holdout access, and it
does not itself execute another fit, sequence build, training run, rollout, or
DVC action; those operations still require their existing command-specific
gate and explicit approval.

## Scientific Invariants

The incident patch changes no scientific or experimental decision. The
following seed `1729` facts remain exact:

- base seed `1729`; module substreams `1830`, `1931`, and `2133` for
  `ANFIS-N`, `ANFIS-F`, and `ANFIS-T-no-current`;
- SHA-256 ranking without replacement and exactly `4,096` selected keys per
  module;
- `60` full-batch epochs, the fixed optimizer/profile, CPU execution, and one
  intra-op plus one inter-op Torch thread;
- all three post-update training-sample spread gates passed;
- `42,110` adaptive-state rows across exactly `353` development monitoring
  locations, with `8,041` exact-previous-month gaps;
- time roles through `2021-12` only, with zero holdout overlap;
- the primary no-current-Chl-a feature, state, target, and recycling mappings;
- fixed level/uncertainty range `[0,1]`, signed-delta range `[-1,1]`, and the
  exact state output schema;
- no seed replacement, no best-seed selection, and no denominator change; and
- the existing sequence geometry, temporal model, rollout kernel, calibration
  rules, thresholds, and four analysis denominators.

The selected-key digests remain:

| Module | Eligible-universe SHA-256 | Selected-keys SHA-256 |
|---|---|---|
| `ANFIS-N` | `5e8ad0e8912e4f3546929dd30099ad9f3fc65414bba56156a753ea6427fb3d98` | `c1c4ed2dd189cbaa38f2ba94023f230aa229697b5893e18e385d8af38d5fe2f0` |
| `ANFIS-F` | `fc55fb5b058e1da5500a8c01889719e45e8e64b39d3ad0a430ed9522d065d438` | `1286f1be330889bddc9583e8c72a966fb6e184fec95515919c0adb22365c0a85` |
| `ANFIS-T-no-current` | `347b245348afa267327167159b68fe449cf669318fa6601c59e3109cd16c1655` | `1526fab41d004dbabcbbf79081805e6b00a4f467c0f212fd35b9c097824b6d83` |

Changing any item in this section is outside E0-DLP and requires a separately
reviewed protocol/runtime amendment.

## Seals And Authorization Boundaries

E0-DLP must preserve and independently assert the following closed state:

```text
development_fit_authorized=true only after E0-DL and E0-DLP both validate
evaluation_authorized=false
e0_u_authorized=false
future_outcomes_accessed=false
post_2021_outcome_semantic_decode=false
lock_generation_reads_scientific_outcome_rows=false
lock_generation_reads_post_2021_outcomes=false
zero_holdout_overlap=true
no_post_2021_materialization=true
does_not_replace_e0_m_model_lock=true
```

Patch generation may hash all frozen files and semantically audit only the
already frozen through-2021 derived adaptive-state Parquet, sample-key CSVs,
and safe checkpoint metadata. It must not read the source panel, targets,
test/holdout outcome rows, or post-2021 outcomes. It must not inspect
post-cutoff outcome availability, missingness, counts, QC, or summaries. It
must preserve the canonical origin identity and must contain no remote URL,
credential, token, bucket name, local configuration, or secret.

The base seal `external_lock_bundle_committed_before_fit=true` remains a true
historical assertion about E0-DL at `L`. E0-DLP must record the later chronology
honestly: the frozen seed `1729` producer bundle was completed under `L` before
the consumer incident was discovered; H-DLP, R-DLP, G-DLP, T-DLP, and P-DLP
are published after that bundle and before any affected consumer or subsequent
fit is allowed to run.
The patch must never recast P-DLP as a pre-fit authority for the already
completed seed.

## DVC Adoption Before H-DLP

A separately authorized DVC-adoption gate must register the existing bytes
before A-DLP is committed. This keeps A-DLP/H-DLP clean, published, and
independently reconstructable before the external P-DLP lock is generated. The adoption gate
must not invoke the fitter or alter any frozen seed file:

- the adaptive-state Parquet receives its explicit `.parquet.dvc` pointer;
- the three checkpoints remain owned through the monolithic `models.dvc`; and
- the small JSON, CSV, and Markdown evidence may be committed to Git.

DVC adoption is administrative. The resulting pointer/owner records must bind
the same artifact SHA-256 values, payload MD5 values, and byte sizes, and the
targeted remote push must be followed by an identical idempotent push. A
changed payload hash, missing record, unexpected owner, or extra artifact
invalidates adoption. The explicit state pointer freezes payload MD5
`183bc5e98b1d5fa5084300ded6476712`. The H-DLP `models.dvc` owner must be the
`173`-file base tree plus exactly the three uppercase historical seed-`1729`
checkpoints: `176` files and `115,709,141` bytes. P-DLP embeds the canonical
tree entries and reconstructs both the base and adoption directory-object
MD5/SHA-256 identities, so later validation does not depend on retaining an
obsolete historical `.dir` cache object.

A-DLP must include the explicit state pointer, the updated monolithic
`models.dvc`, and the ten small JSON/CSV/Markdown seed records. P-DLP then
seals those published records without rewriting them. After P-DLP,
`models.dvc` may evolve only additively: every one of the `176` locked entries
must remain path/MD5-exact, and every extra path must belong to the E0-DL
planned model inventory. The physical `models/` tree and current DVC cache
must exactly match the committed pointer, and an evolved pointer must be
published unchanged on `origin/main` before the next strict runner. In the
operational workflow, each independent fit is therefore followed by DVC
registration, targeted push, commit, and Git push before the next fit. The
runtime gate proves local ownership and Git publication of later additions;
their final remote completeness remains an explicit per-fit workflow duty and
is cross-bound by E0-M. E0-M must verify the final owner and cite both E0-DL
and E0-DLP.

This document authorizes neither that DVC operation nor any downstream
experiment. It only defines the evidence and ordering required to preserve the
one-shot seed while closing the consumer-dialect gap.
