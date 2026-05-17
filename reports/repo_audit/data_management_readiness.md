# Data Management Readiness

## Scope

This audit summarizes the repository state after adding DVC-backed data
governance, source documentation, publication checks, and static type checking.

## Current State

- Heavy raw, interim, panel, target, diagnostic, fuzzy, PIPE/GRU-D, report
  export, and model artifacts are kept out of Git.
- DVC is initialized and commit-ready pointer files exist for the declared
  heavy artifacts in `configs/dvc_artifacts.yaml`.
- The real GCS remote URL and credential path are machine-local settings stored
  only in `.dvc/config.local`.
- The public docs use only placeholder GCS URLs such as
  `gs://YOUR_PRIVATE_BUCKET/dvc`.
- `configs/sources.yaml` records source identity, access policy, acquisition
  route, local raw path, license field, adapter, and future-source policy.
- AquaMatch is documented as a direct authenticated EDI browser download by the
  project owner, not as a third-party mirror.
- WQP acquisition is documented with the original browser query and the
  equivalent resumable WQX3 scripts.
- LakeBeD acquisition is documented as a project-script download from the public
  Hugging Face dataset snapshot. Local `.cache/` files are excluded from raw
  manifests and DVC artifacts.

## Reproducibility Anchors

- Raw SHA-256 manifest: `data/catalog/raw_file_manifest.csv`
- Source catalog: `data/catalog/source_catalog.json`
- Data freeze: `data/freeze/DATA_FREEZE.md`
- Derived SHA-256 manifest: `data/freeze/derived_file_manifest_v0.csv`
- DVC artifact declaration: `configs/dvc_artifacts.yaml`
- DVC setup and recovery guide: `docs/DVC_GCS_SETUP.md`
- Data access policy: `docs/DATA_ACCESS.md`
- Publication checklist: `docs/PUBLICATION_CHECKLIST.md`
- Continuity log for private handoff: `private/WORK_LOG.md`

## Required Verification Before Publication

```bash
scripts/list_publication_candidates.sh
poetry run ty check
poetry run pytest
poetry check
scripts/check_repo_publication_ready.sh
```

`scripts/list_publication_candidates.sh` is read-only and prints the Git/DVC
candidate inventory that must be reviewed before the first commit.

## Required Verification On A New Machine

```bash
poetry install --with dev,modeling,sources,data-versioning
mkdir -p private
scripts/dvc_data_assistant.sh setup --bucket YOUR_PRIVATE_BUCKET --credentialpath private/YOUR_SERVICE_ACCOUNT.json
scripts/dvc_data_assistant.sh pull
scripts/dvc_data_assistant.sh doctor
.venv/bin/python src/data/validate_sources.py
.venv/bin/python src/data/raw_manifest.py --reuse-existing
.venv/bin/python src/data/freeze.py --overwrite
```

The regenerated SHA-256 manifests and freeze must match the committed freeze
before downstream model outputs are trusted.

## Closed Publication Risks

- WQP terms were reviewed against official WQP/EPA pages. The conservative
  policy remains: publish scripts, filters, hashes, and manifests, but keep the
  full raw mirror in authorized DVC/GCS storage rather than public Git blobs
  because WQP aggregates many provider organizations and does not expose one
  blanket raw redistribution license.
- Poetry package metadata has been migrated to `[project]`; `poetry check`
  exits cleanly without the previous Poetry 2 metadata warnings.
- First-commit scope review is now supported by
  `scripts/list_publication_candidates.sh` plus
  `scripts/check_repo_publication_ready.sh`.
- DVC upload to the configured GCS remote was verified after push. On
  `2026-05-17`, `.venv/bin/dvc status` reported local data and pipelines up to
  date, and `.venv/bin/dvc status --cloud` reported `Cache and remote
  'gcsremote' are in sync.`

## Residual Risks

- DVC remote access is machine-specific. Each authorized machine must configure
  `.dvc/config.local` with its own bucket access and credential path.
- Clean-clone recovery has not yet been tested on a second machine. That remains
  the final end-to-end reproducibility check before relying on machine migration
  alone.
