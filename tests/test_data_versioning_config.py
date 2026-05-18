from __future__ import annotations

import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_declares_optional_dvc_gs_group() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    group = pyproject["tool"]["poetry"]["group"]["data-versioning"]

    assert group["optional"] is True
    assert group["dependencies"]["dvc"]["extras"] == ["gs"]


def test_dvc_setup_script_uses_local_config_for_real_remote() -> None:
    script = (REPO_ROOT / "scripts/setup_dvc_gcs.sh").read_text(encoding="utf-8")

    assert "remote add --local" in script
    assert "remote modify --local" in script
    assert "credentialpath" in script
    assert "DVC_GCS_CREDENTIALPATH" in script
    assert "remote default --local" in script
    assert "config --local core.site_cache_dir" in script
    assert ".dvc/tmp/site-cache" in script
    assert ".dvc/config.local" in script
    assert 'BUCKET="${BUCKET#gs://}"' in script
    assert 'DVC_REMOTE_URL=gs://YOUR_PRIVATE_BUCKET/dvc' in script
    assert 'gs://gs://' in script


def test_gcs_credential_check_documents_adc_without_committed_secret() -> None:
    script = (REPO_ROOT / "scripts/check_gcs_credentials.sh").read_text(encoding="utf-8")
    docs = (REPO_ROOT / "docs/DVC_GCS_SETUP.md").read_text(encoding="utf-8")

    assert "gcloud auth application-default print-access-token" in script
    assert "GOOGLE_APPLICATION_CREDENTIALS" in script
    assert "DVC_GCS_CREDENTIALPATH" in script
    assert "gcloud auth application-default login" in docs
    assert "YOUR_GCP_PROJECT_ID" in docs
    assert "YOUR_SERVICE_ACCOUNT.json" in docs
    assert "remote modify --local gcsremote credentialpath" in docs


def test_dvc_data_assistant_documents_setup_pull_push_workflow() -> None:
    script = (REPO_ROOT / "scripts/dvc_data_assistant.sh").read_text(encoding="utf-8")
    docs = (REPO_ROOT / "docs/DVC_GCS_SETUP.md").read_text(encoding="utf-8")

    assert "cmd_wizard" in script
    assert "cmd_pull" in script
    assert "cmd_push" in script
    assert "scripts/setup_dvc_gcs.sh" in script
    assert "scripts/check_repo_publication_ready.sh" in script
    assert "DVC_GCS_CREDENTIALPATH" in script
    assert "scripts/dvc_data_assistant.sh setup" in docs
    assert "scripts/dvc_data_assistant.sh pull" in docs
    assert "scripts/dvc_data_assistant.sh push" in docs


def test_reproduce_data_workspace_assistant_regenerates_post_pull_artifacts() -> None:
    script = (REPO_ROOT / "scripts/reproduce_data_workspace.sh").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    data_access = (REPO_ROOT / "docs/DATA_ACCESS.md").read_text(encoding="utf-8")
    dvc_setup = (REPO_ROOT / "docs/DVC_GCS_SETUP.md").read_text(encoding="utf-8")

    assert "src/data/validate_sources.py" in script
    assert "src/data/raw_manifest.py" in script
    assert "--reuse-existing" in script
    assert "src/data/report_observations.py" in script
    assert "src/data/freeze.py" in script
    assert "--overwrite" in script
    assert "data/interim/observations/observations_summary.csv" in script
    assert "Verify derived manifest path set" in script
    assert "--allow-path-set-change" in script
    assert "scripts/reproduce_data_workspace.sh" in readme
    assert "scripts/reproduce_data_workspace.sh" in data_access
    assert "scripts/reproduce_data_workspace.sh" in dvc_setup


def test_prepare_commit_artifact_assistant_stages_git_and_pushes_dvc() -> None:
    script = (REPO_ROOT / "src/data/prepare_commit_artifacts.py").read_text(encoding="utf-8")
    wrapper = (REPO_ROOT / "scripts/prepare_commit_artifacts.sh").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    checklist = (REPO_ROOT / "docs/PUBLICATION_CHECKLIST.md").read_text(encoding="utf-8")

    assert "configs/dvc_artifacts.yaml" in script
    assert "dvc_status_candidates" in script
    assert "unmanaged_ignored_heavy_paths" in script
    assert "validate_experiment_manifests" in script
    assert "validate_freeze_freshness" in script
    assert "Reproducibility Checks" in script
    assert "prompt_yes_no" in script
    assert '"add", path.as_posix()' in script
    assert "\"push\"" in script
    assert "\"git\", \"add\", \"-A\"" in script
    assert "DEFAULT_REPORT_DIR = Path(\"tmp\")" in script
    assert "pre_commit_artifacts_{timestamp}.md" in script
    assert "src/data/prepare_commit_artifacts.py" in wrapper
    assert "scripts/prepare_commit_artifacts.sh" in readme
    assert "scripts/prepare_commit_artifacts.sh" in checklist
    assert "tmp/pre_commit_artifacts_*.md" in checklist


def test_pipe_rollout_alerts_are_documented_as_dvc_artifacts() -> None:
    dvc_artifacts = (REPO_ROOT / "configs/dvc_artifacts.yaml").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    data_versioning = (REPO_ROOT / "docs/DATA_VERSIONING.md").read_text(encoding="utf-8")
    rollout_iteration = (REPO_ROOT / "docs/PIPE_ROLLOUT_ITERATION_1.md").read_text(encoding="utf-8")

    assert "pipe_rollout_alerts_v0" in dvc_artifacts
    assert "data/pipe_grud/pipe_rollout_alerts_v0.parquet" in dvc_artifacts
    assert "src/experiments/rollout_pipe_grud.py" in readme
    assert "src/experiments/evaluate_pipe_grud_rollouts.py" in readme
    assert "docs/PIPE_ROLLOUT_ITERATION_1.md" in readme
    assert "pipe_rollout_alerts_v0" in data_versioning
    assert "pipe_grud_rollout_backtest_v0" in data_versioning
    assert "rollout backtest" in data_versioning
    assert (
        "poetry run python src/experiments/evaluate_pipe_grud_rollouts.py --split test --samples 128 --batch-size 256"
        in rollout_iteration
    )
    assert "Iteration 2 Direction" in rollout_iteration


def test_publication_check_scans_for_service_account_key_content() -> None:
    script = (REPO_ROOT / "scripts/check_repo_publication_ready.sh").read_text(encoding="utf-8")

    assert '"service_account"' in script
    assert '"private_key"' in script
    assert "private/*.json" in script
    assert "tracked_secret_content_hits" in script


def test_publication_check_enforces_english_repository_text() -> None:
    script = (REPO_ROOT / "scripts/check_repo_publication_ready.sh").read_text(encoding="utf-8")

    assert "repo_language_hits" in script
    assert "Non-English repository text found in versionable files" in script
    assert "data/raw/**" in script
