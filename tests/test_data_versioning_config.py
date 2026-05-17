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
