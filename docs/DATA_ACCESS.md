# Data Access

The repository is designed so GitHub can remain lightweight while data and
models are recovered through DVC when the user has access to the private remote.

## Public Repository Contents

The public repository may include:

- code and tests
- `configs/*.yaml`
- `data/catalog/*.json` and `data/catalog/*.csv` hash manifests
- `data/freeze/*.json`, `data/freeze/*.csv`, and `data/freeze/DATA_FREEZE.md`
- `docs/*.md`
- small markdown reports and small CSV summaries
- `.dvc` pointer files after DVC is initialized

## Private Or DVC-Managed Contents

The following must not be Git blobs:

- `data/raw/**`
- `data/interim/**`
- large `data/panel/*.parquet`
- large `data/targets/*.parquet`
- large `data/diagnostics/*.csv`
- `data/fuzzy/**`
- `data/pipe_grud/**`
- binary model artifacts under `models/**`
- large operational report exports
- resumable download chunks under `data/cache/**`

WQP deserves special handling: official WQP/EPA documentation describes the
portal as publicly available for download/retrieval, but it aggregates data from
many providers.

In this project, "private raw mirror" does not mean the WQP data cannot be used
or reproduced. It means the large local copy under `data/raw/wqp/` is stored in
the authorized DVC/GCS remote rather than committed to public GitHub as CSV
blobs. Public Git may include the acquisition scripts, exact query filters,
metadata, hashes, DVC pointers, and derived summaries. An authorized user can
recover the same raw files with `dvc pull`; an unauthenticated public reader can
recreate the acquisition route from the documented WQP query and scripts.

## GCS Remote Policy

The real bucket name and credentials are local configuration only. Commit only
placeholders such as:

```text
gs://YOUR_PRIVATE_BUCKET/dvc
```

Do not commit `.env`, service account JSON files, `.dvc/config.local`, or any
machine-specific credential paths.

## Recovery Flow For Authorized Users

After DVC is initialized and objects have been pushed:

```bash
scripts/dvc_data_assistant.sh setup --bucket YOUR_PRIVATE_BUCKET --credentialpath private/YOUR_SERVICE_ACCOUNT.json
scripts/dvc_data_assistant.sh pull
scripts/reproduce_data_workspace.sh
```

The recovery assistant regenerates source manifests, canonical observation
summaries, and the data freeze. It fails if a path present in the committed
derived manifest disappears during regeneration, unless the change is
explicitly acknowledged with `--allow-path-set-change`.
