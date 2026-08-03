from __future__ import annotations

from pathlib import Path

from src.data.dvc_add_from_manifest import (
    DEFAULT_MANIFEST,
    dvc_add_commands,
    dvc_environment,
    load_artifacts,
    load_configured_artifacts,
    resolve_dvc_bin,
)


def test_default_dvc_add_inventory_includes_closure_post_lock_overlay() -> None:
    artifacts = load_configured_artifacts(DEFAULT_MANIFEST)

    assert any(
        artifact.artifact_id == "closure_v1_common_origin_manifest"
        and artifact.path == Path("data/closure_v1/common_origin_manifest.parquet")
        for artifact in artifacts
    )


def test_dvc_manifest_loader_builds_commands_for_existing_paths(tmp_path: Path) -> None:
    existing = tmp_path / "data" / "raw" / "wqp"
    existing.mkdir(parents=True)
    missing = tmp_path / "data" / "raw" / "future"
    manifest = tmp_path / "dvc_artifacts.yaml"
    manifest.write_text(
        f"""
schema_version: 1
artifacts:
  - artifact_id: raw_wqp
    path: {existing.as_posix()}
    type: raw_source
    source_id: wqp
    dvc: true
  - artifact_id: raw_future
    path: {missing.as_posix()}
    type: raw_source
    source_id: future
    dvc: true
  - artifact_id: small_report
    path: reports/report.md
    type: report
    source_id: multi_source
    dvc: false
""",
        encoding="utf-8",
    )

    artifacts = load_artifacts(manifest)
    commands, missing_artifacts = dvc_add_commands(artifacts, include_missing=False, dvc_bin=".venv/bin/dvc")

    assert commands == [[".venv/bin/dvc", "add", existing.as_posix()]]
    assert [artifact.artifact_id for artifact in missing_artifacts] == ["raw_future"]


def test_dvc_bin_resolution_accepts_explicit_executable(tmp_path: Path) -> None:
    dvc_bin = tmp_path / "dvc"
    dvc_bin.write_text("#!/usr/bin/env sh\n", encoding="utf-8")
    dvc_bin.chmod(0o755)

    assert resolve_dvc_bin(dvc_bin.as_posix()) == dvc_bin.as_posix()


def test_dvc_environment_defaults_to_local_site_cache(monkeypatch) -> None:
    monkeypatch.delenv("DVC_SITE_CACHE_DIR", raising=False)

    assert dvc_environment()["DVC_SITE_CACHE_DIR"] == ".dvc/tmp/site-cache"
