# lentic-pipe

Reproducible system for simulation, alerting, and counterfactual planning of
algal proliferation and trophic state in lentic water bodies.

The project follows a frozen-data architecture with SHA-256 traceability,
leakage-safe temporal splits, baselines before complex models, expert
ANFIS/fuzzy state scoring, PIPE/GRU-D, controlled degradation, and DVC-backed
artifacts.

## Requirements

- Python `>=3.14,<3.15`
- Poetry as the only dependency manager
- DVC with GCS support to recover or publish heavy artifacts
- Authorized access to the private bucket if you need `dvc pull` or `dvc push`

Install Poetry if it is not available:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

`poetry.toml` keeps the virtual environment inside the repository:

```text
.venv/
```

That directory is not versioned.

## Installation

Minimal development install:

```bash
poetry install --with dev
```

Full install for data, modeling, and DVC workflows:

```bash
poetry install --with dev,modeling,sources,data-versioning
```

Verify the environment:

```bash
.venv/bin/python --version
poetry run ty check
poetry run pytest
.venv/bin/dvc --version
```

Add dependencies with Poetry:

```bash
poetry add pandas
poetry add --group dev pytest
poetry add --group modeling scikit-learn
```

After dependency changes, update and version the lock file:

```bash
poetry lock
```

## Data And DVC

Raw data lives under `data/raw/` and must not be versioned as Git blobs. GitHub
should contain code, tests, configs, documentation, manifests, hashes, small
reports, and `.dvc` pointer files.

Heavy artifacts live in private DVC/GCS storage:

- complete raw sources
- canonical observations
- panels, targets, and splits
- large diagnostics
- fuzzy state and large operational score exports
- PIPE/GRU-D datasets
- binary models

The real GCS bucket must not be written into versioned files. Use placeholders
only, such as:

```text
gs://YOUR_PRIVATE_BUCKET/dvc
```

Use this entry point to configure, upload, download, and diagnose DVC data:

```bash
scripts/dvc_data_assistant.sh --help
```

## Recover Data On Another Machine

After cloning the repository on an authorized machine:

```bash
git clone <repo>
cd lentic-pipe
poetry install --with dev,modeling,sources,data-versioning
mkdir -p private
```

Copy the service-account JSON to a Git-ignored path, for example:

```text
private/YOUR_SERVICE_ACCOUNT.json
```

Then configure DVC and download the artifacts:

```bash
scripts/dvc_data_assistant.sh setup \
  --bucket YOUR_PRIVATE_BUCKET \
  --credentialpath private/YOUR_SERVICE_ACCOUNT.json

scripts/dvc_data_assistant.sh pull
scripts/dvc_data_assistant.sh doctor
```

After pulling data, verify local integrity:

```bash
.venv/bin/python src/data/validate_sources.py
.venv/bin/python src/data/raw_manifest.py --reuse-existing
.venv/bin/python src/data/freeze.py --overwrite
```

Regenerated hashes must match the versioned freeze before downstream results
are trusted.

## Publish Or Update Data

When a machine creates or updates heavy artifacts:

```bash
.venv/bin/python src/data/dvc_add_from_manifest.py --dry-run
.venv/bin/python src/data/dvc_add_from_manifest.py
scripts/dvc_data_assistant.sh push
scripts/list_publication_candidates.sh
scripts/check_repo_publication_ready.sh
```

Commit only code, configs, docs, manifests, small reports, and `.dvc` pointer
files. Do not commit `.dvc/config.local`, raw data, model binaries, heavy
exports, or credential JSON files.

## Main Documentation

- `docs/DATA_SOURCES.md`
- `docs/DATA_LICENSES.md`
- `docs/DATA_ACCESS.md`
- `docs/DATA_VERSIONING.md`
- `docs/DVC_GCS_SETUP.md`
- `docs/PUBLICATION_CHECKLIST.md`
- `docs/DATA_FREEZE.md`

## Current State

- The three main raw sources are documented in `configs/sources.yaml`.
- SHA-256 hashes and the data freeze are versioned under `data/catalog/` and
  `data/freeze/`.
- Heavy artifacts are declared in `configs/dvc_artifacts.yaml`.
- DVC is initialized; the real remote and credentials live only in
  `.dvc/config.local`.
- `scripts/dvc_data_assistant.sh` is the recommended workflow for configuring,
  uploading, downloading, and diagnosing DVC data.
- `scripts/check_repo_publication_ready.sh` must pass before publishing to
  GitHub.
- `poetry run ty check` and `poetry run pytest` must pass before publishing
  code changes.
