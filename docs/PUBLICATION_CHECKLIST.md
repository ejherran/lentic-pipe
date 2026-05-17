# Publication Checklist

Run this checklist before pushing to GitHub.

1. `git status --short` shows no accidental raw data files staged.
2. `scripts/check_repo_publication_ready.sh` passes.
3. `scripts/list_publication_candidates.sh` has been reviewed line by line.
4. `poetry run ty check` passes.
5. `poetry run pytest` passes.
6. `poetry check` exits successfully.
7. GCS URLs in tracked files are placeholders such as
   `gs://YOUR_PRIVATE_BUCKET/dvc`, never real bucket names.
8. `data/catalog/raw_file_manifest.csv` includes SHA-256 fingerprints for all
   raw files and source metadata files.
9. `data/freeze/DATA_FREEZE.md` was regenerated after the last raw or derived
   artifact change.
10. `.dvc/config.local`, `.env`, and credential JSON files are not tracked.
11. `configs/sources.yaml` records acquisition route, filters, license, access
   policy, and redistribution policy for each `source_id`.
12. `configs/dvc_artifacts.yaml` lists every heavy artifact that is needed to
   reproduce current results.
13. DVC pointers are committed after `dvc add`; data blobs are not committed.
14. The private GCS bucket has public access prevention enabled before sharing
    DVC pull instructions.
