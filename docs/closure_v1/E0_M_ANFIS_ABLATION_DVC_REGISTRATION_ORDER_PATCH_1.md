# E0-MZA — ANFIS-ablation DVC registration order patch

## Purpose

E0-MZA is an additive governance overlay over the published P-E0-MZ commit
`74410ceb42cbea471b4a3cf8d1bd4e2f197ad058`. It repairs one fail-closed
ordering defect discovered before R-E0-MZ began: the generic missing-pointer
discovery returns the exact ten prediction payloads in lexical path order,
while the MZ registration preflight compared that result directly with the
scientific slot order, interleaved `A0`, `A1` for each base seed.

The discovered set was complete and correct. The order-only comparison would
have rejected R before its transaction, DVC status, DVC add, report, or Git
staging. No R-E0-MZ side effect occurred. E0-MZA preserves that incident as
history and replaces the invalid sequence comparison with two separate
contracts:

- discovery is an unordered exact set of ten unique payloads;
- execution is the canonical interleaved sequence followed by `models`.

This overlay does not refit, recalibrate, evaluate, rewrite, register, or
reinterpret any scientific artifact. It authorizes neither DVC add nor DVC
push.

## Published authority and incident

The validator reconstructs this exact direct-parent topology:

```text
2f0643ab6f634fdcce71f0ee0d847c448d2c61f5  adopted 45 lightweight files
    |
    +-- ab1d7189ab8ce549a2517a71fef61ea66e2dcf7f  H-E0-MZ, exact 4M+5A
            |
            +-- 74410ceb42cbea471b4a3cf8d1bd4e2f197ad058  P-E0-MZ, exact 2A
                    |
                    +-- H-E0-MZA, exact 5M+5A
```

At `74410ce`, the exact missing paths are lexically discovered as all five
`A0` paths followed by all five `A1` paths. The sealed scientific order is:

```text
A0/1729, A1/1729,
A0/20260612, A1/20260612,
A0/20260613, A1/20260613,
A0/20260614, A1/20260614,
A0/314159, A1/314159
```

E0-MZA requires `count=10`, `unique_count=10`, and `set_exact=true` for
discovery. Missing, extra, duplicated, renamed, or already-present pointers
remain fatal. Only after that set validation may the helper reconstruct the
canonical sequence above; `models` is the eleventh and final DVC target.

## Scientific state preserved

The authority remains the same exact family:

- model IDs `A0` and `A1`;
- base seeds `1729`, `20260612`, `20260613`, `20260614`, and `314159`;
- ten `completed` / `available` / `passed` slots;
- 80 regular `0644`, single-link finals;
- 50 lightweight files tracked in Git;
- 20 model/checkpoint files and ten selection-prediction Parquets physically
  present but not individually registered;
- baseline `models.dvc` unchanged from P-E0-MZ;
- all ten prediction `.dvc` pointers, their temporaries, registration guards,
  backup anchors, and isolated-config directories absent.

Each slot keeps the sealed development-only denominators and lineage.
Calibration target values, test, holdout, post-2021 outcomes, E0-M, and E0-U
remain outside this authority. An ordering patch is not performance evidence.

## H/P/R topology and exact scopes

H-E0-MZA must be the direct, non-merge child of exact P-E0-MZ
`74410ceb42cbea471b4a3cf8d1bd4e2f197ad058`. Its scope is exactly `5M+5A`.

Exactly these five existing paths are modified:

```text
src/data/prepare_commit_artifacts.py
tests/test_closure_anfis_ablation_dvc_registration_patch.py
tests/test_closure_anfis_ablation_dvc_registration_adoption_patch.py
tests/test_closure_anfis_ablation_model_publication_adoption_patch.py
tests/test_closure_anfis_ablation_model_publication_patch.py
```

Exactly these five paths are added:

```text
configs/closure_v1/anfis_ablation_dvc_registration_order_patch_lock.schema.json
docs/closure_v1/E0_M_ANFIS_ABLATION_DVC_REGISTRATION_ORDER_PATCH_1.md
src/experiments/closure_anfis_ablation_dvc_registration_order_patch.py
src/experiments/lock_closure_anfis_ablation_dvc_registration_order_patch.py
tests/test_closure_anfis_ablation_dvc_registration_order_patch.py
```

The helper remains Git mode `100755`; every other H component is `100644`.

P-E0-MZA must be the direct, non-merge child of H-E0-MZA and add only these
two regular, single-link `100644` canonical JSON files:

```text
reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_order_patch_lock.json
reports/closure_v1/00_protocol/anfis_ablation_dvc_registration_order_patch_lock_manifest.json
```

Only after P-E0-MZA is committed and published may R-E0-MZA run. Its exact Git
scope remains `10A+1M`:

- ten new selection-prediction `.parquet.dvc` pointers in canonical slot
  order;
- one modified `models.dvc`, last, covering the existing 20 model/checkpoint
  files under the monolithic `models` target.

The 50 lightweight files, both P authorities, H components, family payloads,
and every unrelated path must remain unstaged and unchanged.

## Companion partition

The P-E0-MZA companion binds exactly 16 current physical inputs and 13
historical Git inputs.

Current physical inputs are:

- the two published P-E0-MZ authority files;
- four H-E0-MZ components preserved physically by H-E0-MZA;
- all ten H-E0-MZA components.

Historical inputs are:

- four inherited P-E0-MX blobs superseded by H-E0-MY;
- four H-E0-MY blobs superseded by H-E0-MZ;
- five H-E0-MZ blobs superseded by H-E0-MZA.

Historical blobs are reconstructed from their exact commits. They are never
substituted with, or byte-compared against, their superseding worktree paths.
The 80 family files are sealed by family records rather than duplicated in
the companion lists.

## Gates

The schema-first, non-writing H preflight is:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_dvc_registration_order_patch.py \
  --check-only
```

It validates topology, exact H scope, P-E0-MZ authority, the family80
snapshot, baseline `models.dvc`, artifact inventories, missing-pointer set,
canonical execution order, runtime/config contracts, and absent P/R/temp
namespace. It writes nothing and runs no verification, DVC, training,
auditing, or scientific-network command.

The separately authorized lock publication is:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_dvc_registration_order_patch.py \
  --execute-lock
```

It runs only the frozen read-only verification commands, then publishes lock
and companion with exclusive no-follow/no-clobber creation and
companion-last completion. A failure rolls back every transaction-owned
inode best-effort without touching foreign replacements.

After exact P publication, effective authority is checked with:

```bash
poetry run python \
  src/experiments/lock_closure_anfis_ablation_dvc_registration_order_patch.py \
  --check-effective
```

The public loader accepts no caller-supplied transaction record. The separate
internal loader accepts only the active R transaction record and revalidates
its guard, anchor, copied baseline, family, Git authority, and registration
records before R can linearize.

## Registration boundary

R-E0-MZA remains a dedicated `--no-push` workflow. H/P precommit continues to
use deferred `models`; it is not the R entrypoint. The future R invocation
must use only the family-registration flag, default repository manifests and
binaries, `DVC_NO_ANALYTICS=1`, canonical HOME/XDG/PATH, and a closed
environment. In particular, inherited `GIT_PAGER` and every other `GIT_*`,
`PYTHON*`, `LD_*`, or unsupported `DVC_*` redirect must be absent or removed
before validation.

The R transaction must:

1. require effective published P-E0-MZA before DVC inspection;
2. validate the exact ten unique missing payloads as a set;
3. reconstruct the canonical interleaved ten-target sequence and append
   `models` last;
4. run every target only as repository `.venv/bin/dvc add --no-relink` under
   sealed runtime and isolated repository/local/global/system configuration;
5. preserve all 80 finals byte-for-byte and validate pointer/model records by
   bytes, digest, mode, links, inode, mtime, and ctime;
6. roll back every transaction-owned pointer, `models.dvc` mutation, exact
   partial/autostaged index subset, temporary, guard, anchor, and isolated
   config node on any pre-linearization failure;
7. stage exactly `10A+1M`, write the report only after final authority checks,
   and never push DVC;
8. retain durable coordination through the internal loader and use the
   `commit_ready` marker as the linearization point.

The eleven DVC adds, any later DVC push, Git commit, and Git push are separate
authorization boundaries.

## Adversarial closure

E0-MZA must fail closed for:

- missing, extra, duplicated, renamed, or pre-existing prediction pointers;
- an execution order other than interleaved exact10 plus `models` last;
- drift in P-E0-MZ, any H component, the 16/13 companion partition, schema,
  lock, companion, family final, manifest relationship, or `models.dvc`;
- symlink/hardlink substitution, noncanonical mode, transient metadata drift,
  unexpected namespace entries, or caller-forged coordination;
- staged/unstaged/excluded-scope drift or partial index rollback;
- runtime wrapper/interpreter/Git drift, inherited config, relinking,
  autostage, `GIT_PAGER`, or any unsupported environment redirect;
- publication failure, owned-output replacement, or loader failure before
  the R linearization point;
- any training, calibration, evaluation, future-outcome, DVC-push, or network
  authorization becoming true.

E0-MZA repairs only the governance order mismatch. Heavy registration remains
false until exact R-E0-MZA completes and is separately committed and
published.
