# Data Versioning

The data governance unit is:

```text
source_id x artifact_type x version_or_freeze_id
```

Examples:

```text
raw_wqp
observations_wqp
waterbody_crosswalk_candidates_v0
monthly_wide_panel_v0
monthly_targets_v0
pipe_sequence_dataset_v0
pipe_rollout_alerts_v0
pipe_grud_rollout_backtest_v0
```

## Current DVC State

The repository is prepared for DVC-backed data governance:

- heavy data and model artifacts are ignored by Git
- the immutable E0-P DVC inventory is declared in
  `configs/dvc_artifacts.yaml`, with post-lock additions declared only in
  anchored overlays
- DVC is initialized
- committed `.dvc` pointer files describe the heavy artifacts
- the real GCS remote and credential path live only in `.dvc/config.local`

The committed `.dvc/config` must remain free of private bucket names and
machine-specific credential paths.

## Required Order

1. Declare or update source metadata in `configs/sources.yaml`.
2. Regenerate raw SHA-256 manifests with `src/data/raw_manifest.py --reuse-existing`
   unless a full rehash is required.
3. Regenerate `data/freeze/DATA_FREEZE.md` if raw files or derived artifacts
   changed.
4. Rebuild the site registry and cross-source candidate layer before rebuilding
   panels when source coverage changes.
5. Add or refresh artifacts declared in the immutable base inventory and its
   anchored post-lock overlays.
6. Run `scripts/prepare_commit_artifacts.sh`.
7. Commit only code, configs, docs, manifests, reports, and `.dvc` pointers.

## Local DVC Write Protection

DVC may restore cache-linked artifacts as read-only files. Before regenerating a
DVC-tracked artifact in place, unprotect the specific local output files that
the command will overwrite.

Example:

```bash
.venv/bin/dvc unprotect data/interim/site_registry.parquet data/interim/site_registry.csv
poetry run python src/data/site_registry.py --progress-every-parts 25
```

`dvc unprotect` is a local workspace operation. It does not upload data, change
the remote, update Git history, or refresh `.dvc` pointer hashes. After the
artifact is regenerated and reviewed, use the normal DVC add/push preparation
flow.

## Integrity Rules

- Any raw file change invalidates the current freeze.
- Any adapter, site-resolution, panel, target, split, fuzzy state, PIPE
  sequence, PIPE rollout, rollout backtest, alert, or model change requires
  updated derived hashes before results are used.
- PIPE rollout backtest CSV/Markdown/JSON outputs under
  `reports/pipe_grud/pipe_rollout_backtest_*` are small report artifacts and
  are kept in Git. Row-level rollout backtest parquet exports are DVC-tracked
  through their `.dvc` pointers. The heavy operational rollout table remains
  DVC-tracked through `data/pipe_grud/pipe_rollout_alerts_v0.parquet.dvc`.
- Neural ODE v0, v1 long80, and v2 direct row-level rollout/calibrated parquet
  exports are declared individually in `configs/dvc_artifacts.yaml`. Their
  lightweight manifests, metrics, and reports remain in Git. A row-level
  artifact must not be described as remotely restorable until its `.dvc`
  pointer has been committed and the corresponding object has been pushed.
- Closure V1 CSV/JSON manifests and cohort assignments remain
  versionable when small. Parquet predictions, masks, bootstrap distributions,
  and other heavy closure payloads require explicit DVC pointers. The E0-P
  inventory in `configs/dvc_artifacts.yaml` is immutable; post-lock Closure
  declarations extend it through
  `configs/closure_v1/dvc_artifacts_post_lock.yaml`. Both DVC preparation
  entry points validate the overlay's path, byte count, and SHA-256 anchor to
  the protocol-locked base before merging the inventories. Declaration and a
  completion manifest alone do not make an artifact published or remotely
  restorable: its pointer must be committed and its matching object pushed.
- The pre-commit artifact assistant validates staged DVC pointer structure,
  verifies current SHA-256 hashes for experiment manifest outputs within the
  configured size limit, verifies generating-script hashes, and fails when
  freeze-sensitive pipeline changes are staged without the required
  `data/freeze/*` outputs.
- Source-scoped site identities must be preserved. Cross-source matching must be
  explicit and auditable. `waterbody_crosswalk_candidates_v0` is a review layer,
  not an accepted merge table.
- Download cache files under `data/cache/**` are local resumable working files,
  not canonical raw data. Final raw files must live under `data/raw/<source_id>/`.
- Local tool caches inside raw directories, such as `.cache/huggingface`, are
  excluded from raw SHA-256 manifests and DVC artifacts. They are acquisition
  byproducts, not canonical source data.
