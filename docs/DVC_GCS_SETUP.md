# DVC And GCS Setup

This document covers local DVC setup for the private GCS data remote. The real
bucket name, credential paths, and `.dvc/config.local` are machine-specific and
must not be committed.

## Unified Assistant

Use this script as the main entry point:

```bash
scripts/dvc_data_assistant.sh --help
```

Common commands:

```bash
scripts/dvc_data_assistant.sh wizard
scripts/dvc_data_assistant.sh setup --bucket YOUR_PRIVATE_BUCKET --credentialpath private/YOUR_SERVICE_ACCOUNT.json
scripts/dvc_data_assistant.sh pull
scripts/dvc_data_assistant.sh push
scripts/dvc_data_assistant.sh status
scripts/dvc_data_assistant.sh doctor
```

The assistant writes local-only DVC settings to `.dvc/config.local`, configures
the local DVC state cache under `.dvc/tmp/site-cache`, and keeps the committed
`.dvc/config` free of private bucket names and credentials.

## Install DVC With GCS Support

Use Poetry when adding DVC to the project environment:

```bash
poetry lock
poetry install --with dev,modeling,data-versioning
.venv/bin/dvc --version
```

## Configure The Private Remote

Do not write the real bucket name into committed files. Set it only at runtime:

```bash
export DVC_BUCKET="YOUR_PRIVATE_BUCKET"
scripts/setup_dvc_gcs.sh
```

or:

```bash
export DVC_REMOTE_URL="gs://YOUR_PRIVATE_BUCKET/dvc"
scripts/setup_dvc_gcs.sh
```

`DVC_BUCKET` is the bucket name only, without `gs://`. If you prefer to pass a
full URL, use `DVC_REMOTE_URL`.

The setup script writes the real remote URL to local DVC configuration:

```text
.dvc/config.local
```

It also configures the DVC state cache locally under `.dvc/tmp/site-cache`, so
DVC does not depend on `/var/tmp` permissions in WSL or sandboxed shells.

## Configure Google Credentials

DVC uses the Google Application Default Credentials that are available to
Python libraries such as `gcsfs`.

For a personal workstation, use ADC:

```bash
gcloud auth login
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID
scripts/check_gcs_credentials.sh
```

If you prefer a service account, keep the JSON key outside the repository and
configure it only in local DVC config:

```bash
export DVC_GCS_CREDENTIALPATH="$HOME/.config/gcloud/YOUR_SERVICE_ACCOUNT.json"
export DVC_BUCKET="YOUR_PRIVATE_BUCKET"
scripts/check_gcs_credentials.sh
scripts/setup_dvc_gcs.sh
```

This writes `credentialpath` to `.dvc/config.local`, not to `.dvc/config`.
The equivalent manual command is:

```bash
.venv/bin/dvc remote modify --local gcsremote credentialpath "$HOME/.config/gcloud/YOUR_SERVICE_ACCOUNT.json"
```

If you keep a local key under `private/`, that directory must remain ignored by
Git. This is acceptable for one workstation, but the key still needs to be
copied to each authorized machine through a secure channel:

```bash
mkdir -p private
cp /secure/path/YOUR_SERVICE_ACCOUNT.json private/YOUR_SERVICE_ACCOUNT.json
scripts/dvc_data_assistant.sh setup --bucket YOUR_PRIVATE_BUCKET --credentialpath private/YOUR_SERVICE_ACCOUNT.json
```

If you prefer to rely on environment variables instead of DVC config, use:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcloud/YOUR_SERVICE_ACCOUNT.json"
```

To also test bucket access without printing bucket contents:

```bash
DVC_BUCKET="YOUR_PRIVATE_BUCKET" scripts/check_gcs_credentials.sh --check-bucket
```

The bucket access check uses `gcloud` ADC. If you configured DVC with a
service-account `credentialpath`, the practical access test is `dvc push`.

## New Machine Recovery

After cloning the repository on a new authorized machine:

```bash
poetry install --with dev,modeling,data-versioning
mkdir -p private
```

Place the service-account JSON in `private/` or another ignored local path, then
run:

```bash
scripts/dvc_data_assistant.sh setup --bucket YOUR_PRIVATE_BUCKET --credentialpath private/YOUR_SERVICE_ACCOUNT.json
scripts/dvc_data_assistant.sh pull
```

After `pull`, regenerate local reproducibility artifacts:

```bash
scripts/reproduce_data_workspace.sh
scripts/dvc_data_assistant.sh doctor
```

The recovery assistant rebuilds source manifests, canonical observation
summaries, and the data freeze. It also compares the regenerated derived
manifest path set against the committed one so missing regenerated files fail
the recovery flow instead of silently disappearing.

## Upload Flow

On the machine that produced or updated heavy artifacts:

```bash
scripts/prepare_commit_artifacts.sh
scripts/check_repo_publication_ready.sh
```

The pre-commit artifact assistant classifies Git and DVC candidates, asks
before adding unmanaged ignored data paths to DVC, runs `dvc add`, runs
`dvc push`, stages Git changes, validates DVC pointers, checks experiment
manifest hashes, flags stale data-freeze risk, and writes a timestamped local
report under ignored `tmp/`. The Git commit remains a manual step.

Commit only code, configs, docs, reports/manifests, and `.dvc` pointer files.
Do not commit `.dvc/config.local`, raw data, model binaries, or credential JSON
files.

Expected tracked files after setup:

```text
.dvc/config
.dvc/.gitignore
.dvcignore
```

Expected untracked/local-only files:

```text
.dvc/config.local
.env
*.json credential files
```

## Preview DVC Adds

Before running `dvc add`, preview the commands:

```bash
.venv/bin/python src/data/dvc_add_from_manifest.py --dry-run
```

When ready:

```bash
.venv/bin/python src/data/dvc_add_from_manifest.py
.venv/bin/dvc status
.venv/bin/dvc push
```

Then run the publication check:

```bash
scripts/check_repo_publication_ready.sh
```
