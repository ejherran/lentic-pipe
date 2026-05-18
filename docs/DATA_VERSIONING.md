# Data Versioning

The data governance unit is:

```text
source_id x artifact_type x version_or_freeze_id
```

Examples:

```text
raw_wqp
observations_wqp
monthly_wide_panel_v0
monthly_targets_v0
pipe_sequence_dataset_v0
pipe_rollout_alerts_v0
pipe_grud_rollout_backtest_v0
```

## Current DVC State

The repository is prepared for DVC-backed data governance:

- heavy data and model artifacts are ignored by Git
- the DVC inventory is declared in `configs/dvc_artifacts.yaml`
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
4. Add or refresh declared artifacts from `configs/dvc_artifacts.yaml`.
5. Run `scripts/prepare_commit_artifacts.sh`.
6. Commit only code, configs, docs, manifests, reports, and `.dvc` pointers.

## Integrity Rules

- Any raw file change invalidates the current freeze.
- Any adapter, panel, target, split, fuzzy state, PIPE sequence, PIPE rollout,
  rollout backtest, alert, or model change requires updated derived hashes
  before results are used.
- PIPE rollout backtest outputs under `reports/pipe_grud/pipe_rollout_backtest_*`
  are small report artifacts and are kept in Git. The heavy operational rollout
  table remains DVC-tracked through `data/pipe_grud/pipe_rollout_alerts_v0.parquet.dvc`.
- The pre-commit artifact assistant validates staged DVC pointer structure,
  verifies current SHA-256 hashes for experiment manifest outputs within the
  configured size limit, verifies generating-script hashes, and fails when
  freeze-sensitive pipeline changes are staged without the required
  `data/freeze/*` outputs.
- Source-scoped site identities must be preserved. Cross-source matching must be
  explicit and auditable.
- Download cache files under `data/cache/**` are local resumable working files,
  not canonical raw data. Final raw files must live under `data/raw/<source_id>/`.
- Local tool caches inside raw directories, such as `.cache/huggingface`, are
  excluded from raw SHA-256 manifests and DVC artifacts. They are acquisition
  byproducts, not canonical source data.
