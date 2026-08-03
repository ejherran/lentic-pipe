from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

import yaml

from src.data.prepare_commit_artifacts import is_heavy_ignored_path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_declares_optional_dvc_gs_group() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    group = pyproject["tool"]["poetry"]["group"]["data-versioning"]

    assert group["optional"] is True
    assert group["dependencies"]["dvc"]["extras"] == ["gs"]


def test_pytest_defaults_to_the_public_test_tree() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]


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
    assert "src/data/build_waterbody_crosswalk.py" in script
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


def test_no_current_chla_full_artifacts_are_documented_as_dvc_artifacts() -> None:
    dvc_artifacts = (REPO_ROOT / "configs/dvc_artifacts.yaml").read_text(encoding="utf-8")

    assert "pipe_sequence_dataset_no_current_chla_v0" in dvc_artifacts
    assert "data/pipe_grud/pipe_sequence_dataset_no_current_chla_v0.parquet" in dvc_artifacts
    assert "pipe_rollout_backtest_rows_validation_no_current_chla_v0" in dvc_artifacts
    assert "reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_validation.parquet" in dvc_artifacts
    assert "pipe_rollout_backtest_rows_test_no_current_chla_v0" in dvc_artifacts
    assert "reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_test.parquet" in dvc_artifacts
    assert "pipe_rollout_calibrated_backtest_rows_no_current_chla_v0" in dvc_artifacts
    assert "reports/pipe_grud/no_current_chla/pipe_rollout_calibrated_backtest_rows.parquet" in dvc_artifacts
    assert "pipe_sequence_dataset_no_current_chla_wqp_focused_v0" in dvc_artifacts
    assert "data/pipe_grud/pipe_sequence_dataset_no_current_chla_wqp_focused_v0.parquet" in dvc_artifacts
    assert "pipe_rollout_backtest_rows_validation_no_current_chla_wqp_focused_v0" in dvc_artifacts
    assert (
        "reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_rows_validation.parquet"
        in dvc_artifacts
    )
    assert "pipe_rollout_backtest_rows_test_no_current_chla_wqp_focused_v0" in dvc_artifacts
    assert "reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_backtest_rows_test.parquet" in dvc_artifacts
    assert "pipe_rollout_calibrated_backtest_rows_no_current_chla_wqp_focused_v0" in dvc_artifacts
    assert (
        "reports/pipe_grud/no_current_chla_wqp_focused/pipe_rollout_calibrated_backtest_rows.parquet"
        in dvc_artifacts
    )


def test_closure_v1_common_origin_manifest_is_declared_as_an_explicit_dvc_artifact() -> None:
    base_path = REPO_ROOT / "configs/dvc_artifacts.yaml"
    protocol_lock = json.loads(
        (REPO_ROOT / "reports/closure_v1/00_protocol/protocol_lock.json").read_text(
            encoding="utf-8"
        )
    )
    locked_base = next(
        record
        for record in protocol_lock["source_artifacts"]
        if record["path"] == "configs/dvc_artifacts.yaml"
    )
    assert base_path.stat().st_size == locked_base["bytes"]
    assert hashlib.sha256(base_path.read_bytes()).hexdigest() == locked_base["sha256"]

    payload = yaml.safe_load(
        (REPO_ROOT / "configs/closure_v1/dvc_artifacts_post_lock.yaml").read_text(
            encoding="utf-8"
        )
    )
    matches = [
        artifact
        for artifact in payload["artifacts"]
        if artifact.get("artifact_id") == "closure_v1_common_origin_manifest"
    ]

    assert matches == [
        {
            "artifact_id": "closure_v1_common_origin_manifest",
            "path": "data/closure_v1/common_origin_manifest.parquet",
            "type": "closure_common_origin_manifest",
            "source_id": "wqp",
            "dvc": True,
            "github_policy": "pointer_only_keep_completion_manifest_in_git",
        }
    ]
    assert payload["inventory_id"] == "closure_v1_post_protocol_lock"
    assert is_heavy_ignored_path("data/closure_v1/common_origin_manifest.parquet")


def test_neural_ode_rollout_artifacts_are_documented_as_dvc_artifacts() -> None:
    dvc_artifacts = (REPO_ROOT / "configs/dvc_artifacts.yaml").read_text(encoding="utf-8")

    expected_paths = [
        "reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_rows_validation.parquet",
        "reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_rows_matched_grud_validation.parquet",
        "reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_backtest_rows_matched_grud_test.parquet",
        "reports/pipe_neural_ode/adaptive_wqp_focused/pipe_neural_ode_rollout_calibrated_backtest_rows.parquet",
        "reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_rows_matched_grud_validation.parquet",
        "reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_backtest_rows_matched_grud_test.parquet",
        "reports/pipe_neural_ode/adaptive_wqp_focused_history_v1_long80/pipe_neural_ode_history_rollout_calibrated_backtest_rows.parquet",
        "reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_backtest_rows_matched_grud_validation.parquet",
        "reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_backtest_rows_matched_grud_test.parquet",
        "reports/pipe_neural_ode/adaptive_wqp_focused_continuous_v2_full_direct_h123/pipe_neural_ode_continuous_direct_calibrated_backtest_rows.parquet",
    ]

    for path in expected_paths:
        assert path in dvc_artifacts


def test_prepare_commit_skips_row_level_smoke_parquets() -> None:
    assert not is_heavy_ignored_path(
        "reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_test_smoke.parquet"
    )
    assert not is_heavy_ignored_path(
        "reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_test_stochastic_smoke.parquet"
    )
    assert is_heavy_ignored_path("reports/pipe_grud/no_current_chla/pipe_rollout_backtest_rows_test.parquet")


def test_site_resolution_candidates_are_documented_as_dvc_artifacts() -> None:
    dvc_artifacts = (REPO_ROOT / "configs/dvc_artifacts.yaml").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    data_versioning = (REPO_ROOT / "docs/DATA_VERSIONING.md").read_text(encoding="utf-8")
    site_resolution = (REPO_ROOT / "docs/SITE_RESOLUTION.md").read_text(encoding="utf-8")
    resolution_config = (REPO_ROOT / "configs/site_resolution.yaml").read_text(encoding="utf-8")

    assert "waterbody_crosswalk_candidates_v0" in dvc_artifacts
    assert "data/interim/waterbody_crosswalk_candidates_v0.parquet" in dvc_artifacts
    assert "docs/SITE_RESOLUTION.md" in readme
    assert "src/data/build_waterbody_crosswalk.py" in readme
    assert "waterbody_crosswalk_candidates_v0" in data_versioning
    assert "configs/site_resolution.yaml" in site_resolution
    assert "accepted_crosswalks" in resolution_config


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
