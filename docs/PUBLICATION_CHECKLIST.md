# Publication Checklist

Run this checklist before pushing to GitHub.

1. `git status --short` shows no accidental raw data files staged.
2. `scripts/prepare_commit_artifacts.sh` has been run after the last data or
   model artifact change.
3. The timestamped `tmp/pre_commit_artifacts_*.md` report from the latest run
   has been reviewed.
4. `scripts/check_repo_publication_ready.sh` passes.
5. `scripts/list_publication_candidates.sh` has been reviewed line by line.
6. `poetry run ty check` passes.
7. `poetry run pytest` passes.
8. `poetry check` exits successfully.
9. GCS URLs in tracked files are placeholders such as
   `gs://YOUR_PRIVATE_BUCKET/dvc`, never real bucket names.
10. `data/catalog/raw_file_manifest.csv` includes SHA-256 fingerprints for all
   raw files and source metadata files.
11. `data/freeze/DATA_FREEZE.md` was regenerated after the last raw or derived
   artifact change.
12. `.dvc/config.local`, `.env`, and credential JSON files are not tracked.
13. `configs/sources.yaml` records acquisition route, filters, license, access
   policy, and redistribution policy for each `source_id`.
14. `configs/dvc_artifacts.yaml` lists every heavy artifact that is needed to
   reproduce current results.
15. DVC pointers are committed after `dvc add`; data blobs are not committed.
16. The private GCS bucket has public access prevention enabled before sharing
    DVC pull instructions.
