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
```

After pulling data, regenerate all lightweight reproducibility artifacts:

```bash
scripts/reproduce_data_workspace.sh
scripts/dvc_data_assistant.sh doctor
```

The recovery assistant rebuilds source manifests, canonical observation
summaries, and the data freeze. It also fails if the derived-manifest path set
changes unexpectedly, so a missing regenerated file cannot silently disappear
from the freeze.

## Publish Or Update Data

When a machine creates or updates heavy artifacts:

```bash
scripts/prepare_commit_artifacts.sh
scripts/list_publication_candidates.sh
scripts/check_repo_publication_ready.sh
```

The pre-commit artifact assistant detects DVC-tracked data changes, asks before
adding unmanaged ignored data paths to DVC, runs `dvc add`, runs `dvc push`,
stages Git changes, validates DVC pointers, checks experiment manifest hashes,
flags stale data-freeze risk, and writes a timestamped upload preparation report
under ignored `tmp/`.

Commit only code, configs, docs, manifests, small reports, and `.dvc` pointer
files. Do not commit `.dvc/config.local`, raw data, model binaries, heavy
exports, or credential JSON files.

## Main Documentation

- `docs/DATA_SOURCES.md`
- `docs/DATA_LICENSES.md`
- `docs/DATA_ACCESS.md`
- `docs/DATA_VERSIONING.md`
- `docs/SITE_RESOLUTION.md`
- `docs/DVC_GCS_SETUP.md`
- `docs/PUBLICATION_CHECKLIST.md`
- `docs/DATA_FREEZE.md`
- `docs/PIPE_ROLLOUT_ITERATION_1.md`
- `docs/PIPE_ROLLOUT_ITERATION_2.md`
- `docs/CONTROLLED_DEGRADATION_PROTOCOL.md`

## Current State

- The four raw sources are documented in `configs/sources.yaml`: LakeBeD-US-CSE,
  WQP, AquaMatch Chl-a, and EPA NLA.
- SHA-256 hashes and the data freeze are versioned under `data/catalog/` and
  `data/freeze/`.
- Heavy artifacts are declared in `configs/dvc_artifacts.yaml`.
- Cross-source waterbody matching is handled as an auditable candidate layer via
  `configs/site_resolution.yaml` and `src/data/build_waterbody_crosswalk.py`;
  source-scoped site IDs remain authoritative until a reviewed crosswalk is
  promoted.
- The focused NLA-WQP review is documented in
  `reports/data/nla_wqp_crosswalk_review.md`; WQP is the panel backbone and NLA
  is treated as a validation, provenance, and enrichment layer.
- DVC is initialized; the real remote and credentials live only in
  `.dvc/config.local`.
- `scripts/dvc_data_assistant.sh` is the recommended workflow for configuring,
  uploading, downloading, and diagnosing DVC data.
- `scripts/reproduce_data_workspace.sh` is the recommended workflow for
  regenerating local reproducibility artifacts after `dvc pull`.
- `scripts/prepare_commit_artifacts.sh` is the recommended workflow for
  preparing Git staging and DVC upload before a manual commit.
- `src/experiments/rollout_pipe_grud.py` generates recursive PIPE/GRU-D state
  rollouts and alert summaries from the frozen promoted model.
- `src/experiments/evaluate_pipe_grud_rollouts.py` backtests recursive
  PIPE/GRU-D rollouts against observed future fuzzy states before treating
  alert behavior as thesis evidence.
- `docs/PIPE_ROLLOUT_ITERATION_1.md` records the first reproducible rollout
  iteration, including operational artifacts, historical backtest metrics, and
  the Iteration 2 direction.
- `docs/PIPE_ROLLOUT_ITERATION_2.md` defines the validation/test rollout alert
  calibration protocol, the Iteration 2B policy frontier, and the provisional
  downstream default: the balanced `closest_pr` policy. Conservative fixed
  thresholds and sensitive F2 thresholds remain documented comparison profiles.
- `docs/CONTROLLED_DEGRADATION_PROTOCOL.md` defines the controlled degradation
  scenario families, `configs/degradation_scenarios.yaml` provides the
  machine-readable scenario grid, and
  `src/experiments/evaluate_controlled_degradation.py` provides the first
  reproducible evaluator for precomputed rollout score surfaces.
- `scripts/check_repo_publication_ready.sh` must pass before publishing to
  GitHub.
- `poetry run ty check` and `poetry run pytest` must pass before publishing
  code changes.
