# Closure V1 Phase 4 final doctoral certification

Status: `H-CERT18 publication candidate; suite locked`

Contract: `closure_v1_phase4_final_certification_v18`

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
- historical H-CERT4: `44f96a7e2b204d80d8e336e90b4a0f4a3456c13f`;
- superseded P-CERT4: `21551c7e53b776b693f4f76b88682180093a0f31`.
- historical H-CERT5: `d18201462be9f6cc057d0187dec2b8b731b62e48`;
- superseded P-CERT5: `da7b673aa8a7cbdc428ca829e5b9f0a5ac79a3ef`;
- historical H-CERT6: `a67d58458c1eeb6b38e752dea4eb3bf91ec44ca9`;
- superseded P-CERT6: `6aea7e7d7908ea0b23dcee41b316759f299114f5`;
- historical H-CERT7: `67b156d4f5d65ac471597349d20098346e17a736`;
- superseded P-CERT7: `66505102124082e7926aac58215a0bd35a07ff4b`;
- historical H-CERT8: `6a339cb7fcec125e379d9829c76e90f5ded55d3a`;
- superseded P-CERT8: `095b55b208f69936a562eaf09c76fab3389df199`;
- historical H-CERT9: `f296236fa7cdc89ad6b85ce1642b478276b92553`;
- superseded P-CERT9: `73d12c7386b9e4a34d8f15b5330cecf357e05ac1`;
- historical H-CERT10: `825b3382f8d501cbc550bf7738a48d4d489dd5e8`;
- superseded P-CERT10: `9ca3126667eaa8c4fd754a3499a7a9eacdd2d2b0`;
- historical H-CERT11: `b83bc2cbccdae5f81bb8ee4b6547054b543260fd`;
- superseded P-CERT11: `af9e23ec1c21968b0d5bb52821619e21f8de5673`;
- historical H-CERT12: `bc5595bfca0e39cd3912f6b786442580d5c1a9fe`;
- superseded P-CERT12: `f97e0a5cf21aa9b65623cee0a8a656ab0537e2ad`;
- historical H-CERT14: `b6c22c3bdc9e3209f621ee1c4d79ae0ca7770dec`;
- superseded P-CERT14: `c0458d7294b0d088169b1f3471200ec1a7342f8b`;
- historical H-CERT15: `13640203e1c95d5ae9f8861fec3e6c842d90c545`;
- superseded P-CERT15: `fa00bbd07d47ff504f2323e418934824efab386a`;
- historical H-CERT16: `4f78e7d1a8f93eedda169c5499c331b8da15de1e`;
- superseded P-CERT16: `6c5fbaac2bf48393b3e7ef3e24d95006ecc016b9`;
- historical H-CERT17: `a7e4f10321c8ea8321d0c4917969ecc9ab39f59b`;
- superseded P-CERT17: `1677778862786d28b9f60e80b7e718432e0b0947`.

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
and H-CERT3/P-CERT3, H-CERT4/P-CERT4 and H-CERT5/P-CERT5 remain immutable
historical evidence; H-CERT6/P-CERT6, H-CERT7/P-CERT7, H-CERT8/P-CERT8 and
H-CERT9/P-CERT9, H-CERT10/P-CERT10, H-CERT11/P-CERT11 and
H-CERT12/P-CERT12, H-CERT14/P-CERT14, H-CERT15/P-CERT15 and
H-CERT16/P-CERT16 and H-CERT17/P-CERT17 now join that immutable history. H-CERT13 remained an
unpublished candidate and was invalidated before any commit; P-CERT13 and
R-CERT13 never existed. R-CERT14 failed closed during a read-only preflight
before any certification execution. The unique R-CERT15 and R-CERT16 launches
then failed closed during public tests. The unique R-CERT17 launch also failed
closed during public tests with a complete safe failure identity and exact
cleanup. H-CERT18/P-CERT18 are the only future effective authority. The
compatibility names `H-CERT` and `P-CERT` refer to H-CERT18 and P-CERT18:

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
                                                             H-CERT4 -> P-CERT4 (superseded failure)
                                                                                 |
                                                                                 v
                                                                    H-CERT5 -> P-CERT5 (superseded failure)
                                                                                 |
                                                                                 v
                                                                    H-CERT6 -> P-CERT6 (superseded failure)
                                                                                 |
                                                                                 v
                                                                    H-CERT7 -> P-CERT7 (superseded failure)
                                                                                 |
                                                                                 v
                                                                    H-CERT8 -> P-CERT8 (superseded failure)
                                                                                 |
                                                                                 v
                                                                    H-CERT9 -> P-CERT9 (superseded failure)
                                                                                 |
                                                                                 v
                                                                    H-CERT10 -> P-CERT10 (superseded failure)
                                                                                  |
                                                                                  v
                                                                    H-CERT11 -> P-CERT11 (superseded failure)
                                                                                  |
                                                                                  v
                                                                    H-CERT12 -> P-CERT12 (superseded failure)
                                                                                  | \
                                                                                  |  `-> H-CERT13 candidate (invalidated; no commit/P13/R13)
                                                                                  v
                                                                    H-CERT14 -> P-CERT14 -X R-CERT14 preflight
                                                                                 |
                                                                                 v
                                                                    H-CERT15 -> P-CERT15 -X R-CERT15 public tests
                                                                                 |
                                                                                 v
                                                                    H-CERT16 -> P-CERT16 -X R-CERT16 public tests
                                                                                 |
                                                                                 v
                                                                    H-CERT17 -> P-CERT17 -X R-CERT17 public tests
                                                                                 |
                                                                                 v
                                                                    H-CERT18 -> P-CERT18 -> R-CERT18
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
5. **P-CERT4** preserves its two-file authority. The R-CERT4 launch that
   consumed it completed one isolated DVC version probe and two local
   cache configuration commands, then failed closed on semantic configuration
   equivalence before the first pull. Cleanup succeeded exactly; it produced
   zero restored payloads, tests or R outputs and authorizes no retry.
6. **H-CERT5** publishes the cache-equivalence and least-capability correction:
   operational `cache.dir/type` are normalized before exact comparison, and
   credential descriptors are withheld until the first directed pull.
7. **P-CERT5** publishes a new two-file, data-only authority. It explicitly
   superseded P-CERT4 through P-CERT1. Its consumed R-CERT5 launch restored all
   eight exact targets but failed closed at the following DVC-status boundary;
   it produced no certification output and authorizes no retry.
8. **H-CERT6** published only the partial-clone DVC-status scope correction,
   the conservative R-CERT5 forensic record, schema, freeze and tests.
9. **P-CERT6** preserved its two-file, data-only authority. Its consumed
   R-CERT6 launch restored all eight exact targets and completed the exact
   ordered post-restore status sweep, then failed closed while serializing the
   portable in-process PostgreSQL start command. Cleanup succeeded exactly,
   removed the namespace, produced no certification output and authorizes no
   retry.
10. **H-CERT7** published only the PostgreSQL portable-path projection
    correction, the factual R-CERT6 record, schema, freeze and tests.
11. **P-CERT7** preserved its two-file, data-only authority. Its consumed
    R-CERT7 launch restored all eight exact targets, started PostgreSQL, then
    failed closed before tests because the sandbox projected an absent
    forbidden prefix as a masked path. Cleanup preserved and later archived
    the namespace; P-CERT7 authorizes no retry.
12. **H-CERT8** published only the exact forbidden-path dispositions,
    PostgreSQL cleanup ownership policy, factual R-CERT7 record, schema,
    freeze and tests.
13. **P-CERT8** preserved its two-file, data-only authority. Its consumed
    R-CERT8 launch restored and status-checked all eight targets and started
    PostgreSQL, but bubblewrap failed before Python, pytest or JUnit because
    the clone-local `.venv` and `tmp` mountpoints were absent below the
    read-only clone. Cleanup failed closed, preserved the namespace and
    authorizes no retry.
14. **H-CERT9** published only the exact clone-mountpoint preparation,
    pre-PostgreSQL bubblewrap smoke, path-free cleanup diagnostics, factual
    R-CERT8 record, schema, freeze and tests.
15. **P-CERT9** preserved its two-file, data-only authority. Its consumed
    R-CERT9 launch ran all 944 public cases: 857 passed, 65 failed, one errored
    and 21 skipped. It produced no OpenAPI, E2E, static-command or R output;
    cleanup failed closed with `database_owner_retained`, and no retry is
    authorized.
16. **H-CERT10** published only the exact 42-node sandbox/state skip ledger,
    the split public-test hard boundary versus OpenAPI/E2E audit hooks, the
    bounded PostgreSQL destroy poll, factual R-CERT9 record, schema, freeze
    and tests.
17. **P-CERT10** preserved its two-file, data-only authority. Its unique
    R-CERT10 launch failed at public-test collection with pytest return code
    3 (`INTERNAL_ERROR`): the sealed 944-node identity was compared with an
    observed 946-node collection containing two accidental parametrized
    policy checks. Exact cleanup removed the namespace; no final JUnit,
    OpenAPI, E2E, static check, payload or R output survived, and no retry is
    authorized.
18. **H-CERT11** restores the exact historical 944-node suite identity while
    retaining both policy validations inside an already existing test node;
    it also seals the factual R-CERT10 record, schema, freeze and tests.
19. **P-CERT11** preserved its two-file, data-only authority. Its unique
    R-CERT11 launch passed the exact 944-node collection gate and then failed
    in setup of the PostgreSQL-backed scientific-dataset API test with pytest
    return code 1 (`TESTS_FAILED`). The query-bearing test DSN was split at
    the slash inside its Unix-socket query, deriving database token `cert-db`
    and redirecting the attempted admin socket host to basename `postgres`.
    Exact cleanup removed the container, socket and namespace. No final JUnit
    or aggregate pytest totals were preserved; no OpenAPI, E2E, static check,
    payload or R output survived, and no retry is authorized.
20. **H-CERT12** replaces that query-bearing test DSN with a query-free DSN,
    keeps Unix-socket routing exclusively in `PGHOST`, seals only redacted
    connection semantics, and records the factual R-CERT11 failure.
21. **P-CERT12** preserved its two-file, data-only authority. Its unique
    R-CERT12 launch reached a successful PostgreSQL readiness probe, then
    failed closed because the retained socket-directory inventory was not the
    exact two expected claims. No observed inventory names or cardinality were
    preserved. Exact cleanup removed the container, socket namespace and run
    namespace; public tests and every later stage remained at zero, and no
    retry is authorized.
22. **H-CERT13** implemented the bounded PostgreSQL PID1/readiness/socket-
    stability handshake and preserved the factual R-CERT12 record without
    changing scientific behavior. It was never committed or published. After
    precommit, one manual main-worktree `.venv/bin/dvc status --json` returned
    0 with semantic stdout `{}`. Although read-only and attributable to zero
    public Git worktree/index change, that command violated the absolute DVC
    boundary and invalidated the entire candidate. No retry is authorized;
    ignored temporary reports are not authority.
23. **P-CERT13** was not generated or published, and **R-CERT13** was never
    executed. Their authority-file, certification-run and output counts are
    zero.
24. **H-CERT14** preserved every PostgreSQL hardening from H-CERT13, recorded
    the invalidation factually, and re-established the absolute main-worktree
    DVC boundary as a direct child of P-CERT12.
25. **P-CERT14** published its two-file, data-only authority as
    `c0458d7294b0d088169b1f3471200ec1a7342f8b`, the direct child of published
    H-CERT14. It remains immutable historical evidence.
26. **R-CERT14** did not execute. Its read-only builder preflight failed
    closed because the effective-authority projection dropped the required
    H-CERT13/P-CERT13 aliases instead of retaining them with `None` values.
    Thus `execution_runs=0`, `output_count=0`, and `retry_authorized=false`.
27. **H-CERT15** preserves H-CERT14/P-CERT14 and that preflight fact, restores
    the required `None` aliases in the effective-authority projection, and
    distinguishes check-only preflight from certification execution. It is a
    direct child of P-CERT14 and cannot execute certification.
28. **P-CERT15** published its two-file, data-only authority as
    `fa00bbd07d47ff504f2323e418934824efab386a`, preserving P-CERT14 and the
    complete historical reconstruction.
29. The unique **R-CERT15** launch was consumed. It reached `public_tests` and
    pytest returned 1 (`TESTS_FAILED`, safe category `nonzero_exit`). Because
    the old runner raised before safely reading the raw JUnit, the underlying
    cause, failed/error nodeids and aggregate executed-case totals were not
    persisted and remain unknown. The independently sealed 944-node collection
    and digest remain defensible, but are not substituted for missing execution
    evidence. Exact cleanup removed the owned container, socket and namespace;
    OpenAPI, E2E, static checks, payload construction and all eight outputs
    remained at zero. P-CERT15 authorizes no retry.
30. **H-CERT16** records that factual boundary and adds bounded, FD-relative,
    no-follow, identity-revalidated JUnit failure diagnostics without weakening
    the success gate or exposing raw diagnostics.
31. **P-CERT16** published its two-file, data-only authority as
    `6c5fbaac2bf48393b3e7ef3e24d95006ecc016b9`, preserving P-CERT15 and the
    complete historical reconstruction.
32. The unique **R-CERT16** launch was consumed. Pytest returned 1 during
    `public_tests`. The strict JUnit diagnostic attempted its bounded read
    before cleanup but safely projected only
    `failure_identity_unavailable/junit_malformed_or_hostile`: totals are `{}`;
    collection count/digest are `null`; failure/error nodeid lists are empty
    with their canonical empty-list digests; and every raw, message, traceback,
    stream, credential and absolute-path preservation flag is false. The
    underlying test cause and executed-case identity remain unknown. Exact
    cleanup removed the owned container, socket and namespace; no later stage
    or output ran, and P-CERT16 authorizes no retry.
33. **H-CERT17** preserves that factual record. It canonicalized exactly five
    pre-existing P0 skip-reason aliases to the sealed reason, prepends an
    unconditional `skipif(True, reason=...)` marker, and accepts only the exact
    failure/error nodeid pair and bounded pytest teardown declared-counter
    accounting described below.
34. **P-CERT17** published its two-file, data-only authority as
    `1677778862786d28b9f60e80b7e718432e0b0947`, preserving the complete
    historical reconstruction. Its unique **R-CERT17** launch was consumed:
    the sealed public suite collected all 944 cases, with 895 passed, seven
    failed, zero errors and 42 registered skips. All seven failures shared the
    pre-run cause `retained_sandbox_python_alias_rejected`; no DVC runtime or
    payload failure was observed. The bounded JUnit projection preserved the
    exact seven failed nodeids and their digest, while raw diagnostics remained
    absent. Exact cleanup removed the container, socket and namespace; no
    OpenAPI, E2E, static command, payload or final output ran. P-CERT17
    authorizes no retry.
35. **H-CERT18** preserves that factual R-CERT17 record and corrects only the
    retained runtime identity policy: `/cert-python` is accepted exclusively
    for the sealed public suite when it matches both `/proc/self/exe` and the
    injected `/usr` interpreter by full file identity. `/cert-poetry` is
    resolved only under that same proven context; the normal `/usr` policy is
    unchanged and arbitrary aliases remain forbidden.
36. **P-CERT18** will publish a new two-file, data-only authority. It
    supersedes P-CERT17 operationally without rewriting it. An unpublished
    P-CERT18 is ineffective. **R-CERT18** may execute once only from the clean,
    published P-CERT18 and may publish exactly eight evidence files, manifest
    last.
37. The repository owner manually publishes the final R commit and the
    `thesis-closure-v1` tag.

The executable target is the published P-CERT18 commit. Executing from
P-CERT1 through P-CERT17, adopting any failed temporary namespace, or treating
a superseded authority as effective is
forbidden. This avoids a circular
claim: a commit cannot contain evidence generated before that evidence exists.
R-CERT may add only the exact eight regular evidence files, so its executable
tree must equal P-CERT's executable tree. The final tag points to published R.
The report must say this explicitly; it must not claim that R literally tested
itself.

At every gate, `HEAD`, `main`, `origin/main`, `origin/HEAD`, live remote HEAD
and live remote main must agree. The worktree and index must have only the
gate's exact unstaged or staged scope. H-CERT18, P-CERT18 and R-CERT18 must never
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

H-CERT5 is exactly `11M` over P-CERT4, with the same eleven paths and modes.
Every path is modified; none is added or deleted.

P-CERT5 is exactly two new additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority_v5.json
configs/closure_v1/phase4_final_certification_authority_manifest_v5.json
```

Its immutable canonical identities are authority `47274` bytes / SHA-256
`f079c81d7c06440e0cda110d0434301ddc9aa0c3b22ef8d4ddf989cb76d9f849`
and companion `2114` bytes / SHA-256
`f895eee5f6df76b4229f719fba2be398f11209b2ebf8893a886dea3d42947aba`.

H-CERT6 is exactly `11M` over P-CERT5, with the same eleven paths and modes.
Every path is modified; none is added or deleted.

P-CERT6 is exactly two new additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority_v6.json
configs/closure_v1/phase4_final_certification_authority_manifest_v6.json
```

Its immutable canonical identities are authority `55835` bytes / SHA-256
`aae4dba7483ac5cceb4076e4eaf74ebd75b6ffe8e766de5db77bf10f246c0720`
and companion `2255` bytes / SHA-256
`609ba901e766bd62816a42da3761d078f226b4270e240e954669361afb637657`.

H-CERT7 is exactly `11M` over P-CERT6, with the same eleven paths and modes.
Every path is modified; none is added or deleted.

P-CERT7 is exactly two new additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority_v7.json
configs/closure_v1/phase4_final_certification_authority_manifest_v7.json
```

Its immutable canonical identities are authority `61984` bytes / SHA-256
`a82ebb157fea898ecf7606a3493577a2a508b6f936590410419f1bc8ea33d53d`
and companion `2396` bytes / SHA-256
`b98a97ed7a021f5a26b2cb11ab7eb8a772526dfef54bb8876b3f849488332297`.

H-CERT8 is exactly `11M` over P-CERT7, with the same eleven paths and modes.
Every path is modified; none is added or deleted.

P-CERT8 is exactly two new additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority_v8.json
configs/closure_v1/phase4_final_certification_authority_manifest_v8.json
```

Its immutable canonical identities are authority `69024` bytes / SHA-256
`a8c5a8228134b5fdf5eadcb5943c9f72639913c565a2b572801ddfb0c6058c64`
and companion `2537` bytes / SHA-256
`fae7ddfc08639110f606013b8ae05ded9a02fcdb47b118231b5b7db74054cbee`.

R-CERT8 had the same prescribed eight-addition scope below a new namespace,
but its consumed launch failed before publication and produced zero outputs.

H-CERT9 is exactly `11M` over P-CERT8, with the same eleven paths and modes.
Every path is modified; none is added or deleted.

P-CERT9 is exactly two new additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority_v9.json
configs/closure_v1/phase4_final_certification_authority_manifest_v9.json
```

Its immutable canonical identities are authority `79355` bytes / SHA-256
`b9d6a453b6b989f6202a4c6dfabde31d01502faa887c83ac808a41876423859e`
and companion `2678` bytes / SHA-256
`496f740f52ef03d46be615e482493dc58556dbbbeedfacbd1271418fbdf878d1`.

R-CERT9 had the same prescribed eight-addition scope, but its consumed launch
failed before publication and produced zero outputs.

H-CERT10 is exactly `11M` over P-CERT9, with the same eleven paths and modes.
Every path is modified; none is added or deleted.

P-CERT10 is exactly two new additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority_v10.json
configs/closure_v1/phase4_final_certification_authority_manifest_v10.json
```

Its immutable canonical identities are authority `92421` bytes / SHA-256
`1e8822415f71d35d40db0f7b384184f1759ce1e899f068510605e3d25f9976d0`
and companion `2826` bytes / SHA-256
`6a283c675bf5a61222df495f2374554d8d96caf1d2890305e2aea327a9e63932`.

R-CERT10 had the same prescribed eight-addition scope, but its consumed launch
failed before publication and produced zero outputs.

H-CERT11 is exactly `11M` over P-CERT10, with the same eleven paths and modes.
Every path is modified; none is added or deleted.

P-CERT11 is exactly two new additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority_v11.json
configs/closure_v1/phase4_final_certification_authority_manifest_v11.json
```

Its immutable canonical identities are authority `101492` bytes / SHA-256
`10a390b8b23436a443c960b22b46d424dbfad3555f961641dd6e8779489b4b81`
and companion `2972` bytes / SHA-256
`b9a0593cebaa5ff6ee919344e84cdeb6fead78c5e2b8af0f4a59a10590b6e716`.

R-CERT11 had the same prescribed eight-addition scope, but its consumed launch
failed before publication and produced zero outputs.

H-CERT12 is exactly `11M` over P-CERT11, with the same eleven paths and modes.
Every path is modified; none is added or deleted.

P-CERT12 is exactly two new additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority_v12.json
configs/closure_v1/phase4_final_certification_authority_manifest_v12.json
```

Its immutable canonical identities are authority `111368` bytes / SHA-256
`62373f7c4d425d010925deb283750a1f3a65a0e62dcd98f817c9f9de6ffe792b`
and companion `3116` bytes / SHA-256
`ee791c92b62d31c5366954656e40926f4afdc556ef4e6436019c12a2fa76868c`.

R-CERT12 had the same prescribed eight-addition scope, but its consumed launch
failed before publication and produced zero outputs.

H-CERT13 had the same prescribed `11M` candidate scope over P-CERT12, but it
was invalidated before commit. P-CERT13 produced zero authority files and
R-CERT13 produced zero outputs.

H-CERT14 is exactly `11M` over P-CERT12, with the same eleven paths and modes.
Every path is modified; none is added or deleted.

P-CERT14 is exactly two new additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority_v14.json
configs/closure_v1/phase4_final_certification_authority_manifest_v14.json
```

Its immutable canonical identities are authority `123750` bytes / SHA-256
`0244008e7d6f56a73bae119f8b4e4319606b04969776c6b18fa653bd3b5fbc0b`
and companion `3350` bytes / SHA-256
`bfd990b8e916f4028f0768dc773b424d189f93b74c70cf4d356a2a0ee0e1c3a2`.

R-CERT14 retained the prescribed eight-addition scope below, but its
read-only preflight failed before execution and produced zero outputs.

H-CERT15 is exactly `11M` over P-CERT14, with the same eleven paths and modes.
Every path is modified; none is added or deleted.

P-CERT15 is exactly two new additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority_v15.json
configs/closure_v1/phase4_final_certification_authority_manifest_v15.json
```

Its immutable canonical identities are authority `130583` bytes / SHA-256
`41f5099be018d89a7bfec099f8905fd1aacdbbc67f7d1d11cbecbe1c7640032b`
and companion `3494` bytes / SHA-256
`82ccf6daa047950ff4c06de31defeecff574f678065d032e4a3530eca9e6ab40`.

R-CERT15 retained the prescribed eight-addition scope, but its public-test
failure and exact cleanup produced zero final outputs.

H-CERT16 is exactly `11M` over P-CERT15, with the same eleven paths and modes.
Every path is modified; none is added or deleted.

P-CERT16 is exactly two new additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority_v16.json
configs/closure_v1/phase4_final_certification_authority_manifest_v16.json
```

Its immutable canonical identities are authority `142014` bytes / SHA-256
`aeff33d3ca0201fa86ded7759b6b3b7a12dad37b27c0a143f84a834fc9876797`
and companion `3638` bytes / SHA-256
`e78e86590722c8eccd9f0936553750a8530e07232237cf57cf867f7b5e3f6fd3`.

R-CERT16 retained the prescribed eight-addition scope, but its public-test
failure and exact cleanup produced zero final outputs.

H-CERT17 is exactly `11M` over P-CERT16, with the same eleven paths and modes.
Every path is modified; none is added or deleted.

P-CERT17 is exactly two new additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority_v17.json
configs/closure_v1/phase4_final_certification_authority_manifest_v17.json
```

Its immutable canonical identities are authority `154137` bytes / SHA-256
`d095c49c1038f4f4d11f1f5011b26152d666c67b8b7da4151a6fee70cbcaaacd`
and companion `3782` bytes / SHA-256
`baa72773861fd9b24d55a106059690ead7089d7f3ccfeaf458f6b322b5481240`.

R-CERT17 retained the prescribed eight-addition scope, but its public-test
failure and exact cleanup produced zero final outputs.

H-CERT18 is exactly `11M` over P-CERT17, with the same eleven paths and modes.
Every path is modified; none is added or deleted.

P-CERT18 is exactly two new additions, authority first and companion last:

```text
configs/closure_v1/phase4_final_certification_authority_v18.json
configs/closure_v1/phase4_final_certification_authority_manifest_v18.json
```

R-CERT18 is exactly eight additions below the certification namespace:

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

All published P1/P2/P3/P4/P5/P6/P7/P8/P9/P10/P11/P12/P14/P15/P16/P17 and
future P18/R18 files are single-link regular `100644`
files. The final manifest is created and linked last. An existing path is
never adopted, replaced, or truncated.

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

R-CERT18 creates a fresh clone of live `origin/main` at the exact published P-CERT18
commit and an initially empty, private DVC cache. The main worktree and its
cache are never targets, and no DVC executable is invoked there. Real DVC
execution is confined to the owned isolated R-CERT18 clone. The builder runs
exactly eight directed pull commands, one pointer per directed pull command,
in the YAML order:

```text
.venv/bin/dvc pull --no-run-cache -j 1 {pointer_path}
```

Isolated configuration and directed status verification are auxiliary DVC
commands in that clone; they are not counted among the eight directed pulls.
Both the post-restore sweep and the post-verification sweep invoke
`dvc status` once per pointer, in the same exact eight-path YAML order. A bare
or global `dvc status` is forbidden because the clone intentionally restores
only this published subset of the repository's DVC pointers. Each final
directed status result must be empty.

The tracked `.dvc/config` does not contain the remote/default declaration.
The operational remote is supplied by the ignored `.dvc/config.local`. Before
execution that local file must be a single-link regular file with mode 0600 or
0644. A relative `credentialpath` is resolved privately below `private/`; its
target is opened no-follow, retained by descriptor, required to be a
single-link regular file with no group/other write bit, and rebased only in the
isolated copy to `/proc/self/fd/<fd>`. The two local `dvc config` commands do
not inherit credential descriptors; the first subprocess capable of using
them is the first directed pull. The source and isolated effective remote, URL
and non-cache settings must be equivalent after validating and normalizing
only the owned `cache.dir` and `cache.type=copy`; every extra section or cache
key fails closed. No credential name, URL, path, descriptor number, hash or
content is serialized.

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
operational_cache_fields_normalized_before_section_set_equivalence: true
only_owned_cache_dir_and_type_may_differ: true
credential_fds_passed_to_dvc_config_commands: false
first_credential_fd_subprocess_exposure: first_directed_dvc_pull
post_restore_status_pointer_paths: exact_ordered_eight_published_pointer_paths
post_verification_status_pointer_paths: exact_ordered_eight_published_pointer_paths
partial_clone_global_status_authorized: false
```

The PostgreSQL container start keeps two distinct representations. The real
execution command retains the owned host and container paths required by
Docker, but the portable evidence projection replaces the four
container/namespace-dependent arguments before any command serialization:

```yaml
volume: <OWNED_DB_SOCKET>:<CONTAINER_POSTGRES_SOCKET>
data_tmpfs: <CONTAINER_POSTGRES_DATA>:rw,size=512m
runtime_tmpfs: <CONTAINER_TMP>:rw,size=64m
unix_socket_directories: unix_socket_directories=<CONTAINER_POSTGRES_SOCKET>
absolute_paths_serialized: false
```

The projection is exact and closed: no other placeholder spelling, argument
order, absolute path, host path, credential or database URL may enter public
evidence. Redaction never modifies the command actually passed to Docker.

The test connection is separately sealed as a query-free DSN. Its semantic
record contains the `postgresql+asyncpg` scheme, database
`closure_phase4_cert`, absent hostname/port/password/query components, and a
required `PGHOST` source named `owned_unix_socket_environment`. The historical
helper's last-slash rewrite must therefore derive target database
`closure_phase4_cert` and admin database `postgres` without changing socket
routing. Neither the complete DSN nor the `PGHOST` value, credentials, or an
absolute socket path is serialized. Exact runtime values remain internal and
must match this policy before public pytest starts.

PostgreSQL startup is separately sealed by
`postgres_startup_stability_policy`. The owned container must expose exact
PID1 executable `postgres` before readiness and again after the socket claim.
Readiness addresses the explicit Unix-socket directory. The same exact two
single-link claims must be identity-revalidated before return, with the owned
container binding checked around every probe and the handoff updated only for
that same container and claim set. The bounded stability loop is at most 120
attempts at 0.25-second intervals. Inventory observation is deliberately
deferred until final PID1 and explicit readiness both pass, so the temporary
postmaster's sockets are neither observed as candidate claims nor adopted.
For each capture then eligible, only an empty inventory or a non-empty subset
of the two expected names is retryable; an observed unexpected name, inode
type, link count or replacement fails immediately. Cleanup never recaptures
or adopts entries after stop. Observed inventories, container identities and
absolute paths are not serialized.

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
precommit and certification tests. Exactly 42 collected nodes have the honest
reason `final_certification_sandbox_or_state_incompatible`: the seven
historical exclusions, 14 dynamic R-CERT9 model/P0 skips, 16 P0-availability
tests, three Phase 3 context tests, one E0-U authority test and one Neural ODE
preflight test. The list is exact and ordered in the contract; it does not
claim these state-dependent cases passed.

Only six of the 42 nodes are outside the 33 positive test files and are added
as supplemental CLI selectors. Consequently the exact non-duplicating command
selector count remains 39. Any skip outside the exact 42-node ledger is
critical and fails closed.

The H-CERT7 suite lock remains exactly the published 944-node lock. Two
independent outcome-free collections over
the frozen bytes produced the same exact identity:

```yaml
suite_lock:
  status: locked
  selector_count: 39
  collected_test_count: 944
  nodeids_sha256: 8422082eca90068bf6d6fff4f1e4d9b9964535e12c8fd6b0844658bbdf683349
  allowed_skip_count: 42
```

The 39 selectors, 944 collected nodes, ordered-node digest and 42 allowed
skips remain locked. The schema's pending branch is available only for
integration fixtures; P-CERT18 generation and R-CERT18 reject it. Closure
outcomes, raw targets and restored
Parquet payloads remained forbidden during both collections.

P-CERT3 remains byte-reconstructed with its historical 920-node suite lock;
H-CERT4/P-CERT4, H-CERT5/P-CERT5 and H-CERT6/P-CERT6 remain
byte-reconstructed with their 944-node suite lock; H-CERT7/P-CERT7 remain
byte-reconstructed with that same lock; H-CERT8/P-CERT8 remain
byte-reconstructed too; H-CERT9/P-CERT9 are also reconstructed byte-exactly.
H-CERT10/P-CERT10, H-CERT11/P-CERT11 and H-CERT12/P-CERT12 remain
byte-reconstructed as failed historical authorities. H-CERT13 was an
unpublished candidate invalidated before commit; neither P-CERT13 nor
R-CERT13 existed. H-CERT14/P-CERT14 remain byte-reconstructed historical
authority, and R-CERT14 remains a zero-execution preflight failure.
H-CERT15/P-CERT15 remain byte-reconstructed historical authority, and
R-CERT15 remains a consumed, failed public-test execution with no retry.
H-CERT16/P-CERT16 remain byte-reconstructed historical authority, and
R-CERT16 remains a consumed, failed public-test execution with no retry.
H-CERT17/P-CERT17 remain byte-reconstructed historical authority, and
R-CERT17 remains a consumed, failed public-test execution with exact safe
failure identity and no retry. H-CERT18/P-CERT18 supersede only the
operational authority without rewriting history. The
946-node diagnostic identity belongs only to the factual
R-CERT10 postmortem and is never an active suite lock.

The public suite requires zero failures/errors, exactly the 42 registered
skips, a full `ty check`, and `poetry check --lock`. E2E is exactly the three
synthetic external, non-Closure API nodes frozen in the YAML. A dedicated
loopback PostgreSQL fixture is required for the public HTTP test that would
otherwise skip.

## OpenAPI and environment evidence

The final OpenAPI contract must remain version 3.x with exactly 69 paths, 83
operations and 38 documented operations. Operation IDs must be unique, path
parameters exact, and documented operations missing from OpenAPI must equal
zero.

Verification runs from the exact P-CERT18 clone with its tracked tree
read-only, the host virtual environment read-only, and an owned writable
temporary namespace. Public pytest uses the bubblewrap masks, read-only binds
and namespace isolation as its hard boundary; it deliberately installs no
process-global Python audit hook. OpenAPI and synthetic E2E retain their
Python audit hooks. These boundaries deny:

- all `private/` reads;
- `data/targets/`;
- raw/unblinded evaluation-outcome namespaces;
- the outcome-access log;
- all eight restored Parquet payloads during software verification.

External network is limited to live Git remote-reference validation, cloning
live origin and the eight directed DVC pulls. The test sandbox permits loopback
PostgreSQL only. The evidence must not
serialize credentials, remote URLs, database URLs, absolute local paths, home
paths, bucket names, or raw command output that may contain them. Portable
command templates and stdout/stderr hashes are sufficient.

The sandbox projection distinguishes path kind before invoking bubblewrap.
The four forbidden prefixes (`private/`, `data/targets/`,
`data/closure_v1/unblinded/`, and
`data/closure_v1/evaluation_outcomes/`) must be absent in the exact clone and
are never synthesized merely to mask them. The tracked outcome-access log must
first be an exact regular file and is then projected as an empty regular-file
mask. Any other kind, presence state, symlink, substitution, or disposition
fails closed before public tests.

PostgreSQL shutdown targets only the exact owned container ID and first uses a
graceful stop with a 30-second timeout. Once that container is proved absent,
the retained socket-directory descriptor may remove only the exact two claims
`.s.PGSQL.5432` (socket) and `.s.PGSQL.5432.lock` (regular file), after
revalidating name, kind, device, inode and link count. Arbitrary residual
adoption is forbidden and the directory must end empty. Internal cleanup
diagnostics retain only safe categories; raw internal stdout/stderr is never
serialized.

After the single stop command, destroy confirmation is a bounded poll of at
most 120 attempts at 0.1-second intervals. Mixed object/container presence is
accepted only for the same retained owned identity, and destruction is
confirmed only when both the name lookup and the retained-container-ID lookup
are absent in the same poll; any foreign identity fails closed. Socket cleanup
begins only after that double absence; timeout preserves the owner and the
namespace rather than widening cleanup.

The exact clone-local mountpoints `.venv` and `tmp` must initially be absent.
Immediately after clone registration and before private DVC configuration,
the builder exclusively creates both as empty `0700`, Git-ignored directories,
retains the clone descriptor, revalidates identity, freezes them with the
clone inventory and rolls them back only by owned inode. A symlink or existing
inode is never adopted, and neither absolute paths nor the run namespace are
serialized.

Inside the sealed public-suite bubblewrap process, the retained interpreter
has the single exact alias `/cert-python`. That alias is accepted only when
the process root is `/workspace`, the injected host target is below `/usr`,
and full device/inode/mode/link-count identity agrees among the alias,
`/proc/self/exe` and the injected target. The retained Poetry tree has the
single exact root `/cert-poetry` and is resolved only after that same Python
context is proven. Outside this narrow context the established `/usr` Python
origin rule remains in force. Similar names, symlinks, mutable aliases and
arbitrary retained runtime roots fail closed.

After DVC restoration and clone-inventory freeze, but before PostgreSQL, the
builder runs one exact bubblewrap smoke using the portable command
`[<SANDBOX_SMOKE>]`. The smoke performs a real touch through the workspace
`tmp` mount, verifies the external marker and removes it by owned inode. It
must return zero with empty stdout/stderr and starts neither Python nor pytest;
network is forbidden.

Cleanup diagnostics are closed to the ordered reason-code allowlist
`database_owner_retained`, `frozen_inventory_drift`,
`socket_inventory_nonempty`, `owned_site_cache_drift`,
`sandbox_inventory_drift`, `work_tree_remove_failed`, and
`unclassified_cleanup_failure`. A persisted cleanup record contains only
`status`, `namespace_preserved`, and `reason_codes`; raw exceptions, streams,
absolute paths, container IDs, namespace paths and run IDs are forbidden.

On a nonzero public pytest exit, H-CERT17 does not require success before
attempting a diagnostic projection. It may read only the owned
`public-tests-raw.xml`, through the retained sandbox-directory descriptor,
with FD-relative no-follow open, regular/single-link checks, a 16 MiB bound,
and identity revalidation before and after the read. DOCTYPEs, entity
declarations, unknown XML elements or attributes, nodeids outside the sealed
suite, collection-count/digest drift and skip-ledger drift are rejected. Each
logical identity must have one testcase record, except that exactly two records
are admitted only when their exact outcomes are `{failure,error}`; every other
duplicate, a third record, or any wider outcome combination fails closed. A
contract policy seals this as
`duplicate_testcase_nodeid_policy=single_record_or_exact_failure_error_pair`,
`duplicate_testcase_pair_max_records=2` and exact outcomes
`[failure,error]`. A
structurally valid but unsealed skip reason is classified as
`junit_sealed_suite_drift`; malformed or hostile XML remains
`junit_malformed_or_hostile`.

The runtime marker is `skipif(True, reason=<sealed reason>)`, prepended with
`append=False` so it precedes pre-existing marks. The parser nevertheless
accepts only the canonical reason or the contract's exact five
nodeid-to-reason aliases, all with raw reason
`The ignored P0 payload is restored only in an authorized data workspace`:

- `tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_physical_schema_matches_closed_fields`;
- `tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_audit_failure_is_read_only[early]`;
- `tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_audit_failure_is_read_only[late]`;
- `tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_audit_pass_is_read_only`;
- `tests/test_audit_closure_p0_sequence_bundle.py::test_real_p0_cli_is_repeatable_and_read_only`.

Both success and failure parsing canonicalize those aliases to the sealed
reason; no other alias or raw reason is retained. After the exact 944 logical
identities, digest and 42-node skip ledger are validated, declared
`failures`, `errors` and `skipped` must be exact. A canonical integer `tests`
attribute may be only in `[N, N + errors]`, where `N` is the logical identity
count, because pytest 9 may increment the declared test counter for a
call-pass plus teardown-error outcome even when that logical identity has a
single testcase XML record. This is counter accounting, not authorization for
another duplicate testcase record. Values
above that bound fail closed and never widen the
identity ledger. A valid projection contains only the return code, normalized
exact totals, sorted failure/error nodeids and their canonical-JSON SHA-256
digests, plus the sealed collection count/digest. Messages, tracebacks, raw JUnit, raw streams,
credentials and absolute paths are never serialized. If safe projection is
impossible, the evidence records only `failure_identity_unavailable` and one
allowlisted reason (`junit_absent`, `junit_unsafe_identity`,
`junit_oversized`, `junit_malformed_or_hostile`, or
`junit_sealed_suite_drift`). Diagnostic unavailability never masks the active
test failure, and the same safe evidence is propagated if cleanup also fails.

Git commits created by unit-test fixtures are allowed only inside fixture-owned
temporary repositories. The orchestrator may not run Git commit, push, or tag;
those remain manual repository-owner actions.

## Authority and result publication

The P-CERT18 authority is canonical JSON. It reconstructs every historical
H-CERT1/P-CERT1/H-CERT2/P-CERT2/H-CERT3/P-CERT3/H-CERT4/P-CERT4 and
H-CERT5/P-CERT5/H-CERT6/P-CERT6/H-CERT7/P-CERT7/H-CERT8/P-CERT8 and
H-CERT9/P-CERT9/H-CERT10/P-CERT10/H-CERT11/P-CERT11/H-CERT12/P-CERT12 and
H-CERT14/P-CERT14/H-CERT15/P-CERT15/H-CERT16/P-CERT16/H-CERT17/P-CERT17
component from Git, every active H-CERT18 component, all ten anchors, all eight
pointer records, the exact suite lock, output order, isolation, diagnostic and
authorization policies. It records P-CERT1 through P-CERT12 as superseded
failed launches, the H-CERT13 invalidation, the R-CERT14 preflight failure and
the consumed R-CERT15, R-CERT16 and R-CERT17 public-test failures, all with no
retry authorization.
Its companion is written last. Execution becomes effective only after the
exact two-file P-CERT18 commit is observed as the single-parent child of
H-CERT18 in local refs and live origin.

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

P-CERT5 sealed the factual R-CERT4 launch that consumed P-CERT4:
one isolated clone, one DVC version command, two Docker version probes and two
local cache-configuration commands;
zero directed pulls, status checks, cache objects, restored payloads, data
reads, database/test/OpenAPI/E2E runs and R outputs. The surfaced error was the
sanitized in-process validation `private DVC configuration section set
drifted`. Exact owned cleanup succeeded, removed the run namespace and did not
mask the active error. Because credential descriptors were available to the
two configuration subprocesses, the record makes no claim that they were not
read and no absolute zero-egress claim; it records only zero verifiable DVC
payload-egress commands. P-CERT4 remains immutable and retry is false.

P-CERT6 additionally seals the conservative factual record of the consumed
R-CERT5 launch. The only surfaced execution diagnostic was the sanitized
`execution_and_cleanup_failed_closed` error: execution-stage command `[]`,
return code absent, stderr category `unavailable_not_persisted`, no raw
stdout/stderr, credentials or absolute paths preserved; cleanup failed closed,
did not mask the active error and preserved the namespace. Read-only metadata
establishes one clone, one DVC version probe, two local DVC configuration
commands, eight successful directed pulls, eight cache objects and eight
restored checkouts. It confirms at least seven and at most eight directed
status checks; it deliberately does not claim an exact count of eight. There
were zero database starts, public-test runs, OpenAPI generations, synthetic
E2E runs, R-CERT outputs, raw target/outcome reads, or Python Parquet opens or
decodes. The namespace is archived under ignored `tmp/`; neither its path nor
run identifier is serialized, and the archive is forensic evidence rather
than authority. P-CERT5 is immutable and `retry_authorized=false`.

P-CERT7 additionally seals the factual record of the consumed R-CERT6 launch.
The surfaced in-process error occurred while projecting the portable
PostgreSQL start command: `absolute command paths may not be serialized`.
Its public diagnostic has stage
`postgres_start_portable_command_serialization`, command `[]`, return code
`null`, safe stderr category `unavailable_not_persisted`, and preserves no raw
stdout, raw stderr, credential or absolute path. Read-only metadata establishes
one clone, one DVC version command, two local DVC configuration commands,
eight successful directed pulls, eight cache objects, eight restored
checkouts, eight directed unit-status checks and one completed post-restore
exact-eight status sweep. It establishes zero post-verification status sweeps,
global DVC status commands, PostgreSQL fixture starts, Docker container runs,
public-test runs, OpenAPI generations, synthetic E2E runs, R-CERT payload
builds or outputs, raw target/outcome reads, and Python Parquet payload opens
or decodes. Exact owned cleanup succeeded, removed the namespace and did not
mask the active error. No failed namespace was archived as authority.
P-CERT6 is immutable and `retry_authorized=false`.

P-CERT8 additionally seals the conservative factual record of the consumed
R-CERT7 launch. Its sanitized in-process diagnostic is
`sandbox_projection` / `forbidden_path_kind_mismatch`, with command `[]`,
return code `null`, safe stderr category `unavailable_not_persisted`, and no
raw stdout/stderr, credential or absolute path. Read-only evidence establishes
one isolated clone; eight successful directed pulls, cache objects, restored
checkouts and unit status checks; one completed post-restore exact-eight sweep;
one PostgreSQL fixture start and one Docker container run. The failure preceded
public tests, OpenAPI, synthetic E2E, payload construction and all eight R
outputs. Cleanup failed closed, preserved the namespace and did not mask the
active error; the exact owned container was absent while two residual
PostgreSQL socket entries remained. The namespace was later archived under
ignored `tmp/` without serializing its path or run ID. That archive is not
authority, P-CERT7 remains immutable, and `retry_authorized=false`.

P-CERT9 additionally seals the factual record of the consumed R-CERT8
launch. It completed one isolated clone, one DVC version probe, two local DVC
configuration commands, eight successful directed pulls, eight cache objects,
eight restored checkouts, eight directed unit-status checks, one exact-eight
post-restore sweep, two Docker version probes, one PostgreSQL fixture start,
one container run, one verification-runtime acquisition and one bubblewrap
process. Bubblewrap then failed at the `public_tests` stage with return code
`1` and safe stderr category `nonzero_exit`, before Python, pytest, JUnit,
public-test collection or execution, post-verification status, OpenAPI, E2E,
payload construction or any R output. The observed safe cause is
`required_mountpoints_absent_under_read_only_clone` for clone-relative
`.venv` and `tmp`; no raw diagnostic or absolute path is preserved. Cleanup
failed closed for the allowlisted secondary reason
`unclassified_cleanup_failure`, preserved the namespace, established the
owned container absent and the socket directory empty, and did not mask the
active error. The ignored archive records no path or run ID and is not
authority. P-CERT8 is immutable and `retry_authorized=false`.

P-CERT10 additionally seals the factual record of the consumed R-CERT9
launch. The public-test process returned 1 after reporting exactly 944 cases:
857 passes, 65 failures, one error and 21 skips. The run completed all eight
directed pulls and the post-restore sweep, started PostgreSQL, passed the
bubblewrap smoke and reached pytest; it did not run post-verification status,
OpenAPI, synthetic E2E, static checks, payload construction or any R output.
Cleanup failed closed with the allowlisted reason
`database_owner_retained`, preserved the namespace and did not mask the
active public-test error. The ignored archive is forensic evidence rather
than authority and neither its path nor run ID is serialized. P-CERT9 is
immutable and `retry_authorized=false`.

P-CERT11 additionally seals the factual record of the unique consumed
R-CERT10 launch. Public pytest returned 3 (`INTERNAL_ERROR`) at the
`public_tests` stage. Deterministic outcome-free postmortem collection found
that the authority sealed 944 nodes and digest
`8422082eca90068bf6d6fff4f1e4d9b9964535e12c8fd6b0844658bbdf683349`,
while the executed H-CERT10 tree collected 946 nodes with digest
`644bc8548b730c98a62773dcc01622a6d5322ffabbcc31aa0e63b12275df9295`.
The two extras were the `<lambda>25` and `<lambda>26` instances of
`test_every_contract_boundary_fails_closed`. Exact cleanup succeeded and
removed the run namespace; the final eight outputs and final JUnit are absent.
The failed control flow did not proceed to OpenAPI, E2E, `ty`, Poetry or
payload construction. P-CERT10 is immutable and `retry_authorized=false`.

P-CERT12 additionally seals the factual record of the unique consumed
R-CERT11 launch. Public pytest passed the locked 944-node collection gate and
returned 1 (`TESTS_FAILED`) during setup of
`test_register_experiment_scientific_dataset_creates_sql_and_science_links`.
The deterministic source-only postmortem records
`naive_database_url_rsplit_misparsed_unix_socket_query`: the helper's
last-slash split derived target token `cert-db`, retained admin database
`closure_phase4_cert`, and moved the socket-host basename to `postgres`.
The record contains neither the full DSN nor an absolute socket path. Because
the command failure was raised before the raw JUnit was read and normalized,
the final JUnit and exact executed-case totals are not preserved; authority
records only the exact 944-node successful collection, one public-test run and
a conservative executed lower bound of one. Exact cleanup removed the owned
container, socket directory and run namespace. Post-verification DVC status,
OpenAPI, E2E, static commands, payload construction and all eight R outputs
remain zero. P-CERT11 is immutable and `retry_authorized=false`.

P-CERT14 additionally seals the factual record of the unique consumed
R-CERT12 launcher, which returned 1 after the internal
`postgres_startup_socket_inventory` stage reported
`socket_inventory_not_exact_two`. The prior clone, version seal, two local DVC
configuration commands, eight directed pulls, eight directed unit-status
checks, one exact post-restore status sweep, runtime acquisition, bubblewrap
smoke, PostgreSQL container start and at least one readiness probe had
completed. Exactly one readiness success led to one failed inventory-capture
attempt; the total probe count and observed inventory content/cardinality were
not preserved. Public Python/pytest, JUnit, OpenAPI, E2E, static checks,
payload construction and all eight R outputs remained zero. Exact cleanup
removed the owned container, socket directory and namespace; no relevant
process or PostgreSQL listener remained. P-CERT12 is immutable and
`retry_authorized=false`.

P-CERT14 also seals the factual invalidation of the unpublished H-CERT13
candidate. H-CERT13 completed three check-only runs successfully. Precommit
was invoked three times. The first successful run produced an ignored
temporary report; immediately afterward, one manual
`.venv/bin/dvc status --json` ran in the main worktree, returned 0 and emitted
the semantic empty object `{}`. A later invocation rejected staged input with
return code 2 and produced no report, and the final successful invocation
produced a second ignored temporary report. The exact 11-path candidate was
unstaged twice. Although the DVC command was read-only in semantics and no
public Git worktree or index change was attributable to it, its invocation
violated the absolute main-worktree DVC boundary. Whether ignored DVC metadata
changed was not assessed. Temporary report paths and hashes are neither
serialized nor authority. H-CERT13 had no
commit, push or publication; P-CERT13 generated zero files and R-CERT13 had
zero launches and outputs. There were no DVC add/push commands, certification
executions, PostgreSQL fixture starts, Docker commands, raw target/outcome or
scientific-payload reads, or Parquet payload opens/decodes. The candidate is
failed closed and `retry_authorized=false`.

P-CERT15 additionally seals the factual R-CERT14 preflight failure without
misclassifying it as a certification launch. From the clean, published
P-CERT14 tree, the read-only builder `--check-only` reached the
effective-authority projection and failed closed because that projection
removed the required H-CERT13/P-CERT13 compatibility aliases instead of
retaining both aliases with `None` values. No `--build` invocation occurred:
`execution_runs=0`, all eight output paths remained absent, no DVC command,
PostgreSQL fixture, Docker command, public test, OpenAPI generation or E2E run
occurred, and `retry_authorized=false`. P-CERT14 remains immutable.
One separate operator invocation selected the locker with `--check-only`;
that diagnostic returned code 2, was read-only and is not certification
authority. The factual record keeps it distinct from the single builder
preflight above.

P-CERT16 additionally seals the consumed R-CERT15 launch. The exact sanitized
pytest command used the 39 non-duplicating selectors, `-ra -q`, the sealed
plugin, disabled cache provider and `tmp/public-tests-raw.xml`. Pytest returned
1 (`TESTS_FAILED`, `nonzero_exit`). The old error path preserved neither raw
streams nor JUnit and therefore did not preserve a safe cause, failure/error
nodeids or aggregate totals; those facts remain explicitly unknown. The
sealed 944-node count and ordered-node digest are independent collection
evidence only. The one isolated clone completed eight directed pulls and the
post-restore status sweep, started the owned PostgreSQL fixture, passed the
sandbox smoke and launched pytest once. Exact cleanup removed the container,
socket and namespace without masking the active error. OpenAPI, E2E, static
commands, payload construction and all eight final outputs remained at zero;
`retry_authorized=false`.

P-CERT17 additionally seals the consumed R-CERT16 launch. The same sanitized
pytest shape returned 1 (`TESTS_FAILED`, `nonzero_exit`). Its bounded raw-JUnit
read ran before cleanup but the strict parser exposed no safe case identity:
`status=failure_identity_unavailable`,
`unavailable_reason=junit_malformed_or_hostile`, `totals={}`, null collection
count/digest, empty failure/error lists and their canonical empty-list digests.
All preservation flags are false. The sealed collection remains independent
evidence and is not substituted for missing execution evidence. The one
isolated clone completed eight directed pulls and status checks, started the
owned PostgreSQL fixture, passed the smoke and launched pytest once. Exact
cleanup succeeded without masking the active error; later verification stages,
payload construction and all outputs remained at zero. The record does not
invent an underlying failed node or total, and `retry_authorized=false`.

P-CERT18 additionally seals the consumed R-CERT17 launch. The exact 944-node
suite retained collection digest
`8422082eca90068bf6d6fff4f1e4d9b9964535e12c8fd6b0844658bbdf683349`;
pytest returned 1 with 895 passes, seven failures, zero errors and 42 skips.
The safe failed-node digest is
`e328bbeea535afadf98704170520cc4c38d660b7b89dee32fdbf9ba5ab776eb6`
and the canonical empty error-node digest is
`37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.
The exact failed identities are:

- `tests/test_build_phase4_final_certification.py::test_bwrap_effect_sources_are_retained_fd_paths_not_mutable_names`;
- `tests/test_build_phase4_final_certification.py::test_dvc_executable_swap_is_detected_after_fd_anchored_invocation`;
- `tests/test_build_phase4_final_certification.py::test_dvc_launcher_swap_never_executes_foreign_launcher`;
- `tests/test_build_phase4_final_certification.py::test_dvc_restore_never_opens_or_reads_parquet_or_cache_payloads_in_python`;
- `tests/test_build_phase4_final_certification.py::test_dvc_restore_uses_eight_exact_unit_commands_and_empty_private_cache`;
- `tests/test_build_phase4_final_certification.py::test_global_dvc_status_always_disables_analytics`;
- `tests/test_build_phase4_final_certification.py::test_runtime_dvc_version_probe_disables_analytics`.

All seven failures occurred before their DVC subprocess calls because the
lexical system-interpreter guard rejected the exact outer-sandbox
`/cert-python` alias. This is not evidence of a DVC runtime, network or payload
failure. The deterministic postmortem and bounded JUnit projection preserve
only the safe identities and totals; messages, tracebacks, raw JUnit, streams,
credentials and absolute paths remain absent. Exact cleanup removed the owned
container, socket and namespace, all eight final paths remained absent, and
`retry_authorized=false`.

The builder retains its owned isolated-clone cleanup snapshot while auxiliary
configuration, the eight directed pulls and directed status verification run
there. A partial tree left by a failed DVC command is never adopted into
cleanup ownership and no unrecognized name is deleted. If final cleanup cannot
prove the namespace is still the exact owned namespace, the builder preserves
it. The surfaced composite error
must identify both the sanitized active verification error and the cleanup
failure; the cleanup failure cannot mask the active stage. No raw stream,
secret or absolute path may appear in that composite.

The final manifest binds the seven preceding outputs, P-CERT18 authority and
companion, historical H1/P1/H2/P2/H3/P3/H4/P4/H5/P5/H6/P6/H7/P7/H8/P8/H9/P9/H10/P10/H11/P11/H12/P12, the factual invalidated H13 candidate,
historical H14/P14/H15/P15/H16/P16/H17/P17, the zero-execution R14 preflight
failure, the consumed R15/R16/R17 public-test failures and active H18
components, public anchors,
eight pointer/restoration records,
test and OpenAPI identities, environment and safety statements. The final
human report must retain this claim boundary:

> software restorability and reproducibility were certified; scientific
> efficacy was not re-evaluated or established.

## Precommit and manual publication

The precommit selector order is R-CERT18, P-CERT18, H-CERT18, then earlier Phase 4
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

H-CERT18 and P-CERT18 precommit do not clone, pull, test, generate OpenAPI, or create R
outputs. R precommit validates existing evidence and does not recertify or run
DVC. No adapter commits, pushes, or tags.

After the owner publishes R, the final audit must prove direct P-CERT18 parent,
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
- any attempt to execute R-CERT18 from superseded P-CERT1 through P-CERT12,
  nonexistent P-CERT13, or superseded P-CERT14/P-CERT15/P-CERT16/P-CERT17,
  or reuse/adopt any retained failed-run namespace;
- a post-clone directory-link delta other than exactly `+1` at
  `after_git_clone`, or failure to register the clone after that exact
  transition check and before subsequent validation;
- loss of the primary error after safe owned cleanup, or any unsafe/unowned
  cleanup attempt; cleanup failure itself remains a fail-closed error;
- raw stdout/stderr, credentials or absolute paths in diagnostics; failure to
  preserve a non-exact namespace; or a cleanup error that masks the sanitized
  active stage instead of surfacing a composite failure;
- any failed-test JUnit diagnostic that is oversized, not FD-safe and
  identity-revalidated, hostile or malformed, contains an unknown/outside-suite
  identity or a duplicate other than the exact two-record `{failure,error}`
  pair, drifts from the sealed collection or skip ledger,
  leaks messages/tracebacks/raw bytes/paths/credentials, or is lost from a
  composite cleanup failure;
- a non-pristine clone/cache, pointer mismatch, non-exact pull, missing
  restored object, any main-worktree DVC command, or static Git/pointer
  boundary drift;
- a global DVC status in the intentionally partial clone, or any change to the
  exact ordered eight-pointer scope of either directed status sweep;
- any drift in the four exact PostgreSQL portable-path placeholders, any
  serialization of their real absolute paths, or any mutation of the real
  Docker execution command by the evidence projection;
- any query, hostname, port or password component in the test DSN; absent or
  non-owned `PGHOST` routing; helper-derived target/admin database drift; or
  serialization of the complete DSN or Unix-socket value;
- any PostgreSQL PID1 mismatch, non-explicit socket readiness, unstable or
  replaced exact-two claim, retry of an unexpected inventory name/type/link,
  post-stop recapture/adoption, or serialization of observed inventory or
  container identity;
- any forbidden-prefix presence/disposition drift, any non-regular outcome
  log mask source, arbitrary PostgreSQL residual adoption, residual
  name/kind/device/inode/link-count drift, or unsafe internal diagnostics;
- any mountpoint that is not initially absent then exclusively created empty
  and `0700`, any mountpoint inventory/rollback drift, any failure of the exact
  bubblewrap touch smoke or owned marker cleanup, or any cleanup reason outside
  the closed path-free allowlist;
- any retained-runtime alias other than exact `/cert-python` and
  `/cert-poetry`, any use outside the proven sealed-suite context, or any
  mismatch against `/proc/self/exe` and the injected `/usr` interpreter;
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
