# Final doctoral software certification — Closure V1 Phase 4

Execution commit: P-CERT `3f58cfda567f6885085a360c08194322ee551aaf`. The later R-CERT commit adds only this exact eight-file evidence bundle; every tracked path outside exact8 must remain byte-identical to P-CERT. No command is represented as having run literally against the later R commit.

## Result

- Locked public test suite: passed with only the exact justified skip ledger.
- OpenAPI/documented contract: passed.
- Three synthetic end-to-end workflows: passed.
- Full static type check and Poetry lock check: passed.
- Eight directed DVC restores: DVC authenticated the sealed pointer MD5/size in an initially empty isolated cache; Python opened no restored/cache payload and decoded no Parquet.
- Main worktree/cache: no DVC command, including version/status/pull, ran there. Two separate owned 0700 site-caches served runtime-version and restore/status roles; one retained DVC runtime was sealed before private configuration/pull and revalidated through final status/version. Main state was reconstructed statically from Git-bound configuration and the eight published DVC pointers under an immutable metadata/inode/inventory lease.
- Concurrency: one cooperative flock is retained on the Git directory; the legacy guard path stays absent, and detected external namespace mutation is a stop condition. Non-cooperating same-UID namespace mutation is explicitly outside the guarantee.
- E0-U and E1–E10 were not rerun; no model was fit, scored, recalibrated, or changed.

## Claim boundary

This certifies software execution, artifact restorability, and reproducibility controls. It does **not** establish, strengthen, or rerun scientific efficacy. Scientific conclusions remain bounded by the published R-SYN claim/evidence matrix and the editorial manuscript receipt. No post-Phase-4 work is authorized.
