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


def _expected_closure_dvc_paths() -> dict[str, Path]:
    seeds = (1729, 20260612, 20260613, 20260614, 314159)
    expected = {
        "closure_v1_common_origin_manifest": Path(
            "data/closure_v1/common_origin_manifest.parquet"
        ),
        "closure_v1_expert_no_current_state": Path(
            "data/closure_v1/development/expert/expert_no_current_state.parquet"
        ),
        "closure_v1_p0_expert_sequence": Path(
            "data/closure_v1/development/sequences/P0/expert_no_current.parquet"
        ),
    }
    for seed in seeds:
        expected[f"closure_v1_anfis_state_seed_{seed}"] = Path(
            f"data/closure_v1/development/anfis/seed_{seed}/"
            "adaptive_no_current_state.parquet"
        )
        expected[f"closure_v1_p1_sequence_seed_{seed}"] = Path(
            f"data/closure_v1/development/sequences/P1/seed_{seed}.parquet"
        )
        for model_id in ("P0", "P1"):
            expected[f"closure_v1_{model_id.lower()}_rollout_seed_{seed}"] = Path(
                f"data/closure_v1/development/rollouts/{model_id}/seed_{seed}.parquet"
            )
    return expected


def test_default_dvc_add_inventory_includes_all_planned_closure_parquets() -> None:
    artifacts = load_configured_artifacts(DEFAULT_MANIFEST)

    closure_artifacts = {
        artifact.artifact_id: artifact.path
        for artifact in artifacts
        if artifact.artifact_id.startswith("closure_v1_")
    }

    assert closure_artifacts == _expected_closure_dvc_paths()
    assert len(closure_artifacts) == 23


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
