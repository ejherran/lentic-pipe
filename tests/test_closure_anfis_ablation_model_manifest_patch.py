from __future__ import annotations

import hashlib
import inspect
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.experiments import closure_anfis_ablation_model_manifest_patch as patch
from src.experiments import audit_closure_anfis_ablation_model_bundle as auditor
from src.experiments import lock_closure_anfis_ablation_model_manifest_patch as locker
from src.data import prepare_commit_artifacts as precommit_artifacts


ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "404983e3dfc511d982b2641aa4aea769dcbc6beb"
H_MU_COMMIT = "3fff3f272eb6f6ba8e644dd49436bc39ecbed1f8"
EXPECTED_ADDITIONS = {
    "configs/closure_v1/anfis_ablation_model_manifest_patch_lock.schema.json",
    "docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_MANIFEST_PATCH_1.md",
    "src/experiments/closure_anfis_ablation_model_manifest_patch.py",
    "src/experiments/lock_closure_anfis_ablation_model_manifest_patch.py",
    "tests/test_closure_anfis_ablation_model_manifest_patch.py",
}
EXPECTED_MODIFICATIONS = {
    "src/data/prepare_commit_artifacts.py",
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py",
    "src/experiments/train_closure_anfis_ablation.py",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py",
    "tests/test_train_closure_anfis_ablation.py",
}
EXPECTED_P_PATHS = {
    "reports/closure_v1/00_protocol/anfis_ablation_model_manifest_patch_lock.json",
    "reports/closure_v1/00_protocol/anfis_ablation_model_manifest_patch_lock_manifest.json",
}
EXPECTED_COMPONENT_GIT_MODES = {
    path: ("100755" if path == "src/data/prepare_commit_artifacts.py" else "100644")
    for path in EXPECTED_ADDITIONS | EXPECTED_MODIFICATIONS
}
ADOPTED_A0_LIGHT_PATHS = (
    "reports/closure_v1/02_models/A0/seed_1729_manifest.json",
    "reports/closure_v1/02_models/A0/seed_1729_preprocessor.json",
    "reports/closure_v1/02_models/A0/seed_1729_report.md",
    "reports/closure_v1/02_models/A0/seed_1729_selection_metrics.csv",
    "reports/closure_v1/02_models/A0/seed_1729_training_curve.csv",
)
ADOPTED_A0_SHA256 = (
    "1e5c2c21b9cb69a4dfa9139fcd6058e57afd4922a19bd1b3cd071a6608897fef",
    "0991ff130f694b69ae30bd37416d3ba2d63f67874b3d895976efb9e28c6ce277",
    "ebffd11d392c62e68e2afbd3ee05febfd05a7411fc83ca18563c7773a51faa62",
    "edfb193302b0fe21708e1ff1556dcdcdf817948a8bd35cef2f90b16be9cc0ec0",
    "6ca58207a32ba345fc4611c73a879e0546a608d7d076baf8f8da057373a3a4ae",
    "f6444a2047d2032334580f1322c4f61637a9028fd0aab27815a6c7386cf860eb",
    "6e12b1d2fc0a1fce8baf7c1f81edbeb1bdd3d013d4365d606d21cc20399d123e",
    "406bf44de3ecdc49ff3d5797cbca1ec0c11ebfbdc70ba262130b85a2e58e31e2",
)


def test_patch_identity_scope_and_companion_counts_are_exact() -> None:
    assert patch.PATCH_GATE == "E0-MV"
    assert patch.BASE_COMMIT == BASE_COMMIT
    assert patch.MU_H_HEAD == H_MU_COMMIT
    assert set(patch.PATCH_PATHS) == EXPECTED_ADDITIONS | EXPECTED_MODIFICATIONS
    assert len(patch.PATCH_PATHS) == 10
    assert patch.PATCH_COMPONENT_GIT_MODES == EXPECTED_COMPONENT_GIT_MODES
    assert patch.EXPECTED_COMPANION_INPUT_COUNT == 72
    assert patch.EXPECTED_HISTORICAL_INPUT_COUNT == 4
    assert patch.FOCUSED_TEST_COUNT == 87
    assert patch.DEFAULT_PATCH_LOCK_PATH.as_posix() in EXPECTED_P_PATHS
    assert patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix() in EXPECTED_P_PATHS
    assert patch._parse_focused_summary("87 passed in 1.23s\n", "")[
        "test_count"
    ] == 87
    for invalid in ("86 passed in 1.23s\n", "87.0 passed in 1.23s\n"):
        with pytest.raises(patch.AnfisAblationModelManifestPatchError):
            patch._parse_focused_summary(invalid, "")


def test_protocol_and_model_manifest_json_dialects_are_disjoint() -> None:
    payload = {"b": 2, "a": 1, "completion_marker_written_last": True}
    assert patch._canonical_json(payload) == (
        b'{"a":1,"b":2,"completion_marker_written_last":true}\n'
    )
    assert patch._model_manifest_json(payload) == (
        b'{\n'
        b'  "b": 2,\n'
        b'  "a": 1,\n'
        b'  "completion_marker_written_last": true\n'
        b'}\n'
    )
    with pytest.raises((TypeError, ValueError, patch.AnfisAblationModelManifestPatchError)):
        patch._model_manifest_json({"bad": float("nan")})


def test_exact_json_comparison_rejects_boolean_numeric_aliases() -> None:
    assert patch._exact_equal(False, False)
    assert patch._exact_equal(0, 0)
    assert not patch._exact_equal(False, 0)
    assert not patch._exact_equal(0, False)
    assert not patch._exact_equal(True, 1)
    assert not patch._exact_equal(1, True)
    assert not patch._exact_equal(80.0, 80)


def test_physical_mode_check_rejects_setuid_with_low_bits_0644(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "setuid-artifact.json"
    artifact.write_bytes(b"{}\n")
    artifact.chmod(0o4644)
    assert artifact.lstat().st_mode & 0o777 == 0o644
    assert not patch._is_regular_file_mode_0644(artifact)


def test_h_component_git_mode_map_preserves_executable_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        patch,
        "_git_mode",
        lambda repo_root, commit, path: patch.PATCH_COMPONENT_GIT_MODES[path],
    )
    patch._require_exact_git_modes(
        ROOT, "f" * 40, patch.PATCH_COMPONENT_GIT_MODES, context="synthetic H"
    )

    monkeypatch.setattr(patch, "_git_mode", lambda *args: "100644")
    with pytest.raises(
        patch.AnfisAblationModelManifestPatchError, match="Git modes drifted"
    ):
        patch._require_exact_git_modes(
            ROOT, "f" * 40, patch.PATCH_COMPONENT_GIT_MODES, context="synthetic H"
        )


def test_precommit_deferred_models_target_requires_exact_path_and_no_push(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_commit_artifacts.py",
            "--allow-unmanaged",
            "--no-push",
            "--defer-dvc-target",
            "models",
        ],
    )
    parsed = precommit_artifacts.parse_args()
    assert parsed.defer_dvc_target == ["models"]
    assert parsed.no_push is True
    assert parsed.allow_unmanaged is True
    assert precommit_artifacts.normalize_deferred_dvc_targets(
        ["models"], no_push=True
    ) == [Path("models")]
    assert precommit_artifacts.normalize_deferred_dvc_targets(
        [], no_push=False
    ) == []
    for raw_targets, no_push in (
        (["models"], False),
        (["./models"], True),
        (["models/"], True),
        (["models", "data"], True),
        (["models", "models"], True),
    ):
        with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
            precommit_artifacts.normalize_deferred_dvc_targets(
                raw_targets, no_push=no_push
            )

    invocation = SimpleNamespace(
        yes=False,
        dry_run=False,
        skip_publication_check=False,
        jobs=None,
        allow_unmanaged=True,
        dvc_bin=None,
        manifest=precommit_artifacts.DEFAULT_DVC_MANIFEST,
        report=None,
    )
    precommit_artifacts.validate_deferred_dvc_invocation(
        invocation, [Path("models")], env={"DVC_NO_ANALYTICS": "1"}
    )
    for field, invalid_value, invalid_env in (
        ("dvc_bin", "fake-dvc", {"DVC_NO_ANALYTICS": "1"}),
        ("manifest", Path("custom.yaml"), {"DVC_NO_ANALYTICS": "1"}),
        ("report", Path("custom-report.md"), {"DVC_NO_ANALYTICS": "1"}),
        (
            "dvc_bin",
            None,
            {"DVC_NO_ANALYTICS": "1", "DVC_BIN": "fake-dvc"},
        ),
        ("dvc_bin", None, {}),
        ("dvc_bin", None, {"DVC_NO_ANALYTICS": "0"}),
        (
            "dvc_bin",
            None,
            {"DVC_NO_ANALYTICS": "1", "DVC_SITE_CACHE_DIR": "elsewhere"},
        ),
    ):
        original = getattr(invocation, field)
        setattr(invocation, field, invalid_value)
        with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
            precommit_artifacts.validate_deferred_dvc_invocation(
                invocation, [Path("models")], env=invalid_env
            )
        setattr(invocation, field, original)

    def staged_text(scope: dict[str, str]) -> str:
        return "".join(
            f"{status_code}\t{path}\n"
            for path, status_code in sorted(scope.items())
        )

    assert (
        precommit_artifacts.validate_deferred_dvc_staged_scope(
            staged_text(precommit_artifacts.DEFERRED_DVC_H_MV_STAGED_SCOPE)
        )
        == "H-E0-MV"
    )
    assert (
        precommit_artifacts.validate_deferred_dvc_staged_scope(
            staged_text(precommit_artifacts.DEFERRED_DVC_P_MV_STAGED_SCOPE)
        )
        == "P-E0-MV"
    )
    with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
        precommit_artifacts.validate_deferred_dvc_staged_scope(
            "M\tsrc/data/prepare_commit_artifacts.py\n"
        )
    pre_stage_h = "".join(
        f"{'??' if status_code == 'A' else ' M'} {path}\n"
        for path, status_code in sorted(
            precommit_artifacts.DEFERRED_DVC_H_MV_STAGED_SCOPE.items()
        )
    )
    assert (
        precommit_artifacts.validate_deferred_dvc_pre_stage_scope(pre_stage_h)
        == "H-E0-MV"
    )
    with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
        precommit_artifacts.validate_deferred_dvc_pre_stage_scope(
            " M src/data/prepare_commit_artifacts.py\n"
        )

    helper = tmp_path / "helper.py"
    helper.write_bytes(b"#!/usr/bin/env python3\n")
    helper.chmod(0o755)
    scope = {"helper.py": "M"}
    modes = {"helper.py": "100755"}
    blob_oid = "a" * 40
    extra_staged = False
    mismatched_blob = False

    def git_output(repo_root: Path, *args: str) -> str:
        del repo_root
        if args == ("diff", "--cached", "--name-status"):
            suffix = "A\textra.py\n" if extra_staged else ""
            return f"M\thelper.py\n{suffix}"
        if args == ("status", "--short", "--untracked-files=normal"):
            return "M  helper.py\n"
        if args == ("diff", "--name-status"):
            return ""
        if args == ("ls-files", "-s", "--", "helper.py"):
            return f"100755 {blob_oid} 0\thelper.py\n"
        if args == ("hash-object", "--no-filters", "--", "helper.py"):
            return ("b" * 40 if mismatched_blob else blob_oid) + "\n"
        raise AssertionError(args)

    monkeypatch.setattr(
        precommit_artifacts, "DEFERRED_DVC_H_MV_STAGED_SCOPE", scope
    )
    monkeypatch.setattr(
        precommit_artifacts, "DEFERRED_DVC_H_MV_GIT_MODES", modes
    )
    monkeypatch.setattr(precommit_artifacts, "_git_output", git_output)
    precommit_artifacts.validate_deferred_dvc_staged_bindings(
        "H-E0-MV", repo_root=tmp_path
    )
    mismatched_blob = True
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError, match="differs from worktree"
    ):
        precommit_artifacts.validate_deferred_dvc_staged_bindings(
            "H-E0-MV", repo_root=tmp_path
        )
    mismatched_blob = False
    helper.chmod(0o644)
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError, match="mode drifted"
    ):
        precommit_artifacts.validate_deferred_dvc_staged_bindings(
            "H-E0-MV", repo_root=tmp_path
        )
    helper.chmod(0o755)
    extra_staged = True
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError, match="exact H-E0-MV"
    ):
        precommit_artifacts.validate_deferred_dvc_staged_bindings(
            "H-E0-MV", repo_root=tmp_path
        )


def test_precommit_deferred_git_exclude_environment_is_exact(
    tmp_path: Path,
) -> None:
    exclude = tmp_path / "a0-excludes"
    payload = "".join(
        f"{pattern}\n"
        for pattern in precommit_artifacts.DEFERRED_DVC_A0_LIGHT_EXCLUDE_PATTERNS
    )
    exclude.write_text(payload, encoding="utf-8")
    exclude.chmod(0o600)
    environment = {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.excludesFile",
        "GIT_CONFIG_VALUE_0": exclude.as_posix(),
    }
    snapshot = precommit_artifacts.validate_deferred_dvc_git_exclude_environment(
        env=environment
    )
    metadata = exclude.lstat()
    assert snapshot == (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mtime_ns,
        hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    )

    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_exclude = real_parent / "a0-excludes"
    linked_exclude.write_text(payload, encoding="utf-8")
    linked_exclude.chmod(0o600)
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="lexical ancestor is not a directory",
    ):
        precommit_artifacts.validate_deferred_dvc_git_exclude_environment(
            env={
                **environment,
                "GIT_CONFIG_VALUE_0": (linked_parent / "a0-excludes").as_posix(),
            }
        )

    invalid_environments = (
        {**environment, "GIT_CONFIG_KEY_1": "core.fileMode"},
        {**environment, "GIT_CONFIG_COUNT": "2"},
        {**environment, "GIT_CONFIG_KEY_0": "core.excludesfile"},
        {**environment, "GIT_CONFIG_VALUE_0": "relative-excludes"},
        {**environment, "GIT_CONFIG_PARAMETERS": "'core.excludesFile'='/dev/null'"},
        {**environment, "GIT_INDEX_FILE": "/tmp/alternate-index"},
        {**environment, "GIT_DIR": "/tmp/alternate-git-dir"},
    )
    for invalid in invalid_environments:
        with pytest.raises(precommit_artifacts.DeferredDvcTargetError):
            precommit_artifacts.validate_deferred_dvc_git_exclude_environment(
                env=invalid
            )

    exclude.chmod(0o644)
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError, match="mode drifted"
    ):
        precommit_artifacts.validate_deferred_dvc_git_exclude_environment(
            env=environment
        )


def test_precommit_deferred_snapshot_rejects_physical_hash_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = tmp_path / "models/synthetic.pt"
    manifest = tmp_path / "reports/synthetic_manifest.json"
    model.parent.mkdir(parents=True)
    manifest.parent.mkdir(parents=True)
    model.write_bytes(b"sealed-model")
    manifest.write_bytes(b"drifted-manifest")
    model.chmod(0o644)
    manifest.chmod(0o644)
    os.utime(model, ns=(1_000_000_000, 1_000_000_000))
    os.utime(manifest, ns=(2_000_000_000, 2_000_000_000))
    monkeypatch.setattr(
        precommit_artifacts,
        "DEFERRED_DVC_A0_FINAL_RECORDS",
        (
            (
                "model",
                "models/synthetic.pt",
                len(b"sealed-model"),
                hashlib.sha256(b"sealed-model").hexdigest(),
            ),
            (
                "manifest",
                "reports/synthetic_manifest.json",
                len(b"drifted-manifest"),
                "0" * 64,
            ),
        ),
    )
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="Deferred A0 final bytes drifted",
    ):
        precommit_artifacts.snapshot_deferred_dvc_models_bundle(repo_root=tmp_path)
    assert stat.S_IMODE(model.lstat().st_mode) == 0o644
    assert stat.S_IMODE(manifest.lstat().st_mode) == 0o644

    real_models = tmp_path / "real-models"
    real_models.mkdir()
    model.rename(real_models / model.name)
    model.parent.rmdir()
    model.parent.symlink_to(real_models, target_is_directory=True)
    monkeypatch.setattr(
        precommit_artifacts,
        "DEFERRED_DVC_A0_FINAL_RECORDS",
        (
            (
                "model",
                "models/synthetic.pt",
                len(b"sealed-model"),
                hashlib.sha256(b"sealed-model").hexdigest(),
            ),
            (
                "manifest",
                "reports/synthetic_manifest.json",
                len(b"drifted-manifest"),
                hashlib.sha256(b"drifted-manifest").hexdigest(),
            ),
        ),
    )
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="lexical ancestor is not a directory",
    ):
        precommit_artifacts.snapshot_deferred_dvc_models_bundle(repo_root=tmp_path)


def test_precommit_deferred_status_and_post_snapshot_drift_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = (
        precommit_artifacts.DeferredDvcFinalSnapshot(
            path="models/synthetic.pt",
            device=1,
            inode=2,
            mtime_ns=3,
            size=4,
            sha256="5" * 64,
            mode=0o644,
        ),
    )
    after = (
        precommit_artifacts.DeferredDvcFinalSnapshot(
            path="models/synthetic.pt",
            device=1,
            inode=2,
            mtime_ns=4,
            size=4,
            sha256="5" * 64,
            mode=0o644,
        ),
    )
    physical_calls: list[str] = []
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_deferred_models_pointer",
        lambda root: physical_calls.append("pointer"),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "_validate_deferred_models_tree",
        lambda root: physical_calls.append("tree"),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "snapshot_deferred_dvc_models_bundle",
        lambda **kwargs: after,
    )
    monkeypatch.setattr(precommit_artifacts, "_git_output", lambda *args: "")

    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError, match="exact single modified"
    ):
        precommit_artifacts.validate_deferred_dvc_models_state(
            {}, repo_root=tmp_path
        )
    assert physical_calls == []

    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError, match="snapshot drifted"
    ):
        precommit_artifacts.validate_deferred_dvc_models_state(
            precommit_artifacts.DEFERRED_DVC_MODELS_STATUS,
            repo_root=tmp_path,
            expected_final_snapshot=before,
        )
    assert physical_calls == ["pointer", "tree"]


def _patch_synthetic_deferred_precommit_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    drift_after_staging: bool,
) -> tuple[
    list[list[str]],
    Path,
    list[tuple[precommit_artifacts.DeferredDvcFinalSnapshot, ...] | None],
    list[str],
]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DVC_NO_ANALYTICS", "1")
    Path("tmp").mkdir()
    synthetic_dvc = Path("synthetic-dvc")
    synthetic_dvc.write_text("#!/bin/sh\n", encoding="utf-8")
    synthetic_dvc.chmod(0o755)
    monkeypatch.setattr(precommit_artifacts, "DEFAULT_DVC_BIN", synthetic_dvc)
    report_path = Path("tmp/precommit-report.md")
    arguments = SimpleNamespace(
        defer_dvc_target=["models"],
        no_push=True,
        yes=False,
        dry_run=False,
        skip_publication_check=False,
        jobs=None,
        allow_unmanaged=True,
        report=None,
        dvc_bin=None,
        manifest=Path("configs/dvc_artifacts.yaml"),
        target=[],
        max_manifest_hash_bytes=1,
        verify_manifest_inputs=False,
    )
    artifact = precommit_artifacts.DvcArtifact(
        artifact_id="models",
        path=Path("models"),
        artifact_type="directory",
        source_id="closure_v1",
        dvc=True,
    )
    snapshot = (
        precommit_artifacts.DeferredDvcFinalSnapshot(
            path="models/synthetic.pt",
            device=1,
            inode=2,
            mtime_ns=3,
            size=4,
            sha256="5" * 64,
            mode=0o644,
        ),
    )
    commands: list[list[str]] = []
    staged_status = "".join(
        f"{status_code}\t{path}\n"
        for path, status_code in sorted(
            precommit_artifacts.DEFERRED_DVC_H_MV_STAGED_SCOPE.items()
        )
    )
    short_status = "".join(
        f"{status_code}  {path}\n"
        for path, status_code in sorted(
            precommit_artifacts.DEFERRED_DVC_H_MV_STAGED_SCOPE.items()
        )
    )
    pre_stage_status = "".join(
        f"{'??' if status_code == 'A' else ' M'} {path}\n"
        for path, status_code in sorted(
            precommit_artifacts.DEFERRED_DVC_H_MV_STAGED_SCOPE.items()
        )
    )
    status_calls = 0

    def versionable_changes() -> str:
        nonlocal status_calls
        status_calls += 1
        return pre_stage_status if status_calls == 1 else short_status
    expected_snapshots: list[
        tuple[precommit_artifacts.DeferredDvcFinalSnapshot, ...] | None
    ] = []
    staged_binding_gates: list[str] = []
    validation_calls = 0

    def validate_state(
        dvc_status: dict[str, Any],
        *,
        expected_final_snapshot: tuple[
            precommit_artifacts.DeferredDvcFinalSnapshot, ...
        ]
        | None = None,
        **kwargs: Any,
    ) -> tuple[precommit_artifacts.DeferredDvcFinalSnapshot, ...]:
        nonlocal validation_calls
        del kwargs
        validation_calls += 1
        assert dvc_status == precommit_artifacts.DEFERRED_DVC_MODELS_STATUS
        expected_snapshots.append(expected_final_snapshot)
        if drift_after_staging and validation_calls == 3:
            raise precommit_artifacts.DeferredDvcTargetError(
                "injected post-stage snapshot drift"
            )
        if expected_final_snapshot is not None:
            assert expected_final_snapshot == snapshot
        return snapshot

    def run_command(
        command: list[str], **kwargs: Any
    ) -> precommit_artifacts.CommandResult:
        del kwargs
        commands.append(list(command))
        if command == ["git", "diff", "--cached", "--name-status"]:
            stdout = staged_status
        elif command == ["git", "-C", ".", "diff", "--name-status"]:
            stdout = ""
        else:
            stdout = "PASS\n"
        return precommit_artifacts.CommandResult(
            command=list(command), returncode=0, stdout=stdout, stderr=""
        )

    monkeypatch.setattr(precommit_artifacts, "parse_args", lambda: arguments)
    monkeypatch.setattr(precommit_artifacts, "ensure_repo_root", lambda: None)
    monkeypatch.setattr(
        precommit_artifacts, "default_report_path", lambda: report_path
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_deferred_dvc_git_exclude_environment",
        lambda: (1, 2, 3, "4" * 64),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "resolve_dvc_bin",
        lambda explicit: precommit_artifacts.DEFAULT_DVC_BIN.as_posix(),
    )
    monkeypatch.setattr(
        precommit_artifacts, "load_configured_dvc_artifacts", lambda path: [artifact]
    )
    monkeypatch.setattr(precommit_artifacts, "versionable_changes", versionable_changes)
    monkeypatch.setattr(
        precommit_artifacts,
        "dvc_status_json",
        lambda dvc_bin: dict(precommit_artifacts.DEFERRED_DVC_MODELS_STATUS),
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "dvc_status_candidates",
        lambda status, artifacts: [artifact],
    )
    monkeypatch.setattr(
        precommit_artifacts, "declared_artifacts_missing_pointers", lambda artifacts: []
    )
    monkeypatch.setattr(
        precommit_artifacts, "unmanaged_ignored_heavy_paths", lambda artifacts: []
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_deferred_dvc_target_selection",
        lambda deferred_paths, **kwargs: None,
    )
    monkeypatch.setattr(
        precommit_artifacts, "validate_deferred_dvc_models_state", validate_state
    )
    monkeypatch.setattr(
        precommit_artifacts,
        "validate_deferred_dvc_staged_bindings",
        lambda gate: staged_binding_gates.append(gate),
    )
    monkeypatch.setattr(precommit_artifacts, "run_command", run_command)
    monkeypatch.setattr(
        precommit_artifacts, "reproducibility_checks", lambda **kwargs: []
    )
    return commands, report_path, expected_snapshots, staged_binding_gates


def test_precommit_deferred_main_runs_no_dvc_add_or_push_and_reports_truthfully(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands, report_path, expected_snapshots, staged_binding_gates = (
        _patch_synthetic_deferred_precommit_main(
            tmp_path, monkeypatch, drift_after_staging=False
        )
    )
    assert precommit_artifacts.main() == 0
    assert len(expected_snapshots) == 5
    assert expected_snapshots[0] is None
    assert expected_snapshots[1] is not None
    assert expected_snapshots[2] == expected_snapshots[1]
    assert expected_snapshots[3] == expected_snapshots[1]
    assert expected_snapshots[4] == expected_snapshots[1]
    assert staged_binding_gates == ["H-E0-MV"] * 4
    expected_git_add = [
        "git",
        "add",
        "-A",
        "--",
        *sorted(precommit_artifacts.DEFERRED_DVC_H_MV_STAGED_SCOPE),
    ]
    assert expected_git_add in commands
    assert all(
        command[:2]
        not in (["synthetic-dvc", "add"], ["synthetic-dvc", "push"])
        for command in commands
    )
    assert all("--cloud" not in command for command in commands)
    report = report_path.read_text(encoding="utf-8")
    assert stat.S_IMODE(report_path.lstat().st_mode) == 0o600
    for token in (
        "## Selected DVC Targets\n\n- none",
        "## Deferred DVC Targets (Not Added)",
        "## Deferred DVC A0 Snapshot",
        '"identical": true',
        "`OK` `models`",
        "## DVC Status Before",
        "## DVC Status After Staging",
        '"models.dvc"',
        "No DVC add commands were run.",
        "## DVC Push\n\nNot run.",
    ):
        assert token in report
    with pytest.raises(
        precommit_artifacts.DeferredDvcTargetError,
        match="Refusing to overwrite",
    ):
        precommit_artifacts.write_report(
            report_path,
            dry_run=False,
            selected_dvc_paths=[],
            deferred_dvc_paths=[Path("models")],
            deferred_snapshot_before=expected_snapshots[1],
            deferred_snapshot_after=expected_snapshots[1],
            rejected_unmanaged_paths=[],
            git_status_before="M helper\n",
            dvc_status_before=precommit_artifacts.DEFERRED_DVC_MODELS_STATUS,
            dvc_status_after=precommit_artifacts.DEFERRED_DVC_MODELS_STATUS,
            cloud_status_before=None,
            dvc_add_results=[],
            dvc_push_result=None,
            git_add_result=None,
            publication_check_result=None,
            reproducibility_findings=[],
            staged_status="M\thelper\n",
            exclusive=True,
        )
    normal_report = Path("normal-report.md")
    precommit_artifacts.write_report(
        normal_report,
        dry_run=False,
        selected_dvc_paths=[],
        deferred_dvc_paths=[],
        deferred_snapshot_before=None,
        deferred_snapshot_after=None,
        rejected_unmanaged_paths=[],
        git_status_before="clean",
        dvc_status_before={},
        dvc_status_after=None,
        cloud_status_before=None,
        dvc_add_results=[],
        dvc_push_result=None,
        git_add_result=None,
        publication_check_result=None,
        reproducibility_findings=[],
        staged_status="none",
    )
    assert "Not applicable." in normal_report.read_text(encoding="utf-8")


def test_precommit_deferred_main_rejects_post_stage_snapshot_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands, report_path, expected_snapshots, staged_binding_gates = (
        _patch_synthetic_deferred_precommit_main(
            tmp_path, monkeypatch, drift_after_staging=True
        )
    )
    assert precommit_artifacts.main() == 2
    assert len(expected_snapshots) == 3
    assert expected_snapshots[0] is None
    assert expected_snapshots[1] is not None
    assert expected_snapshots[2] == expected_snapshots[1]
    assert staged_binding_gates == ["H-E0-MV"]
    expected_git_add = [
        "git",
        "add",
        "-A",
        "--",
        *sorted(precommit_artifacts.DEFERRED_DVC_H_MV_STAGED_SCOPE),
    ]
    assert expected_git_add in commands
    assert all(
        command[:2]
        not in (["synthetic-dvc", "add"], ["synthetic-dvc", "push"])
        for command in commands
    )
    assert not report_path.exists()


def test_adopted_a0_inventory_is_exact_and_not_a_companion_input() -> None:
    records = patch.HISTORICAL_A0_FINAL_RECORDS
    assert len(records) == 8
    assert tuple(str(record["sha256"]) for record in records) == ADOPTED_A0_SHA256
    assert tuple(sorted(patch.HISTORICAL_A0_LIGHT_PATHS)) == tuple(
        sorted(ADOPTED_A0_LIGHT_PATHS)
    )
    assert [record["role"] for record in records] == [
        "model",
        "checkpoint",
        "preprocessor",
        "training_curve",
        "selection_predictions",
        "selection_metrics",
        "report",
        "manifest",
    ]
    assert patch.HISTORICAL_A0_AUTHORITY["gate"] == "E0-MU"
    assert patch.HISTORICAL_A0_AUTHORITY["p_patch_head"] == BASE_COMMIT


def test_cli_modes_are_closed_and_target_aware() -> None:
    assert locker.parse_args(["--check-only"]).check_only is True
    assert locker.parse_args(["--execute-lock"]).execute_lock is True
    build = locker.parse_args(
        ["--check-effective", "--model-id", "A1", "--base-seed", "1729"]
    )
    assert (build.model_id, build.base_seed, build.audit_current_unpublished) == (
        "A1",
        1729,
        False,
    )
    audit = locker.parse_args(
        [
            "--check-effective",
            "--model-id",
            "A0",
            "--base-seed",
            "1729",
            "--audit-current-unpublished",
        ]
    )
    assert audit.audit_current_unpublished is True
    for arguments in (
        ["--check-effective"],
        ["--check-effective", "--model-id", "A0"],
        ["--check-only", "--model-id", "A0", "--base-seed", "1729"],
        ["--execute-lock", "--audit-current-unpublished"],
        ["--check-only", "--execute-lock"],
    ):
        with pytest.raises(SystemExit):
            locker.parse_args(arguments)


def test_check_only_is_schema_first_and_non_writing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    def preflight() -> dict[str, Any]:
        events.append("schema")
        return {"status": "supported_subset_passed"}

    def collect(*, verify_remote: bool) -> dict[str, Any]:
        assert verify_remote is True
        events.append("collect")
        return {
            "repository": {"head": "h"},
            "h_patch": {"component_count": 10},
            "companion_contract": {
                "physical_input_count": 72,
                "historical_input_count": 4,
            },
            "adopted_a0_bundle": {
                "model_id": "A0",
                "base_seed": 1729,
                "output_count": 8,
            },
        }

    monkeypatch.setattr(
        patch, "preflight_anfis_ablation_model_manifest_patch_schema", preflight
    )
    monkeypatch.setattr(
        patch, "collect_anfis_ablation_model_manifest_patch_prelock_state", collect
    )
    monkeypatch.setattr(
        patch,
        "run_anfis_ablation_model_manifest_patch_verification",
        lambda: pytest.fail("check-only must not run verification"),
    )
    monkeypatch.setattr(
        patch,
        "execute_and_publish_anfis_ablation_model_manifest_patch_lock_bundle",
        lambda: pytest.fail("check-only must not publish"),
    )
    result = locker.check_only()
    assert events == ["schema", "collect"]
    assert result["status"] == "ready_to_lock"
    assert result["component_count"] == 10
    assert result["physical_input_count"] == 72
    assert result["historical_input_count"] == 4
    assert result["adopted_output_count"] == 8
    assert result["writes_performed"] is False
    assert result["verification_commands_run"] is False


def test_public_execute_boundary_accepts_no_payload_and_runs_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def publish() -> tuple[dict[str, Any], dict[str, Any]]:
        nonlocal calls
        calls += 1
        return ({"gate": "E0-MV"}, {"status": "completed"})

    monkeypatch.setattr(
        patch,
        "execute_and_publish_anfis_ablation_model_manifest_patch_lock_bundle",
        publish,
    )
    assert list(inspect.signature(locker.execute_lock).parameters) == []
    result = locker.execute_lock()
    assert calls == 1
    assert result["status"] == "locked_unpublished"
    assert result["model_fit_or_optimization_run"] is False
    assert result["auditor_entrypoint_run"] is False
    assert result["dvc_commands_run"] is False


def test_validator_public_publishers_accept_no_payload_or_evidence() -> None:
    for function in (
        patch.execute_and_publish_anfis_ablation_model_manifest_patch_lock_bundle,
        patch.publish_anfis_ablation_model_manifest_patch_lock_bundle,
    ):
        parameters = inspect.signature(function).parameters
        assert set(parameters) == {"repo_root"}
        assert parameters["repo_root"].kind is inspect.Parameter.KEYWORD_ONLY


def _patch_synthetic_publisher(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], dict[str, Any]]:
    prelock = {
        "repository": {"head": "h"},
        "h_patch": {"component_count": 10},
        "mu_authority": {"status": "published"},
        "adopted_a0_bundle": {"model_id": "A0", "base_seed": 1729},
        "manifest_dialect": {"indent": 2},
        "companion_contract": {
            "physical_input_count": 72,
            "historical_input_count": 4,
        },
        "prelock": {"writes_performed": False},
    }
    payload = {"gate": "E0-MV", **prelock}
    companion = {"status": "completed", "completion_marker_written_last": True}
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_model_manifest_patch_schema",
        lambda **kwargs: {"status": "supported_subset_passed"},
    )
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_model_manifest_patch_prelock_state",
        lambda **kwargs: prelock,
    )
    monkeypatch.setattr(
        patch,
        "run_anfis_ablation_model_manifest_patch_verification",
        lambda **kwargs: {"status": "passed"},
    )
    monkeypatch.setattr(
        patch,
        "build_anfis_ablation_model_manifest_patch_lock_payload",
        lambda *args, **kwargs: payload,
    )
    monkeypatch.setattr(
        patch,
        "validate_anfis_ablation_model_manifest_patch_lock_payload",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        patch,
        "_expected_companion",
        lambda *args, **kwargs: companion,
    )
    monkeypatch.setattr(
        patch,
        "_revalidate_publication_state_under_guard",
        lambda *args, **kwargs: None,
    )
    return payload, companion


def test_validator_publisher_is_lock_then_manifest_last(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected_lock, expected_companion = _patch_synthetic_publisher(monkeypatch)
    order: list[Path] = []
    real_publish = patch.mt._publish_bytes_no_clobber

    def ordered_publish(path: Path, payload: bytes, *, repo_root: Path):
        order.append(path)
        return real_publish(path, payload, repo_root=repo_root)

    monkeypatch.setattr(patch.mt, "_publish_bytes_no_clobber", ordered_publish)
    lock, companion = (
        patch.execute_and_publish_anfis_ablation_model_manifest_patch_lock_bundle(
            repo_root=tmp_path
        )
    )
    assert lock == expected_lock
    assert companion == expected_companion
    assert order == [
        patch.DEFAULT_PATCH_LOCK_PATH,
        patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
    ]
    assert not (tmp_path / patch.LOCKER_GUARD_PATH).exists()
    assert not (
        tmp_path / patch.mt._temporary_path(patch.DEFAULT_PATCH_LOCK_PATH)
    ).exists()
    assert not (
        tmp_path / patch.mt._temporary_path(
            patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH
        )
    ).exists()


def test_validator_publisher_rolls_back_owned_lock_on_manifest_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_synthetic_publisher(monkeypatch)
    real_publish = patch.mt._publish_bytes_no_clobber

    def fail_manifest(path: Path, payload: bytes, *, repo_root: Path):
        if path == patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH:
            raise OSError("injected companion failure")
        return real_publish(path, payload, repo_root=repo_root)

    monkeypatch.setattr(patch.mt, "_publish_bytes_no_clobber", fail_manifest)
    with pytest.raises(OSError, match="injected companion failure"):
        patch.execute_and_publish_anfis_ablation_model_manifest_patch_lock_bundle(
            repo_root=tmp_path
        )
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_PATH).exists()
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).exists()
    assert not (tmp_path / patch.LOCKER_GUARD_PATH).exists()


def test_validator_publisher_rolls_back_when_guarded_input_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_synthetic_publisher(monkeypatch)
    watched = tmp_path / "watched-a0-input.bin"
    watched.write_bytes(b"sealed")
    calls = 0

    def revalidate(*args: Any, **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            watched.write_bytes(b"mutated-after-first-guarded-check")
            return
        if watched.read_bytes() != b"sealed":
            raise patch.AnfisAblationModelManifestPatchError(
                "guarded adopted A0 input drifted"
            )

    monkeypatch.setattr(
        patch, "_revalidate_publication_state_under_guard", revalidate
    )
    with pytest.raises(
        patch.AnfisAblationModelManifestPatchError,
        match="guarded adopted A0 input drifted",
    ):
        patch.execute_and_publish_anfis_ablation_model_manifest_patch_lock_bundle(
            repo_root=tmp_path
        )
    assert calls == 2
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_PATH).exists()
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).exists()
    assert not (tmp_path / patch.LOCKER_GUARD_PATH).exists()


def test_validator_publisher_rolls_back_when_slot_guard_appears_under_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_synthetic_publisher(monkeypatch)
    injected = tmp_path / patch.mt._guard_path("A1", 1729)
    calls = 0

    def revalidate(*args: Any, **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            injected.parent.mkdir(parents=True, exist_ok=True)
            injected.write_bytes(b"foreign slot publication\n")
            return
        if injected.exists():
            raise patch.AnfisAblationModelManifestPatchError(
                "guarded training namespace drifted"
            )

    monkeypatch.setattr(
        patch, "_revalidate_publication_state_under_guard", revalidate
    )
    with pytest.raises(
        patch.AnfisAblationModelManifestPatchError,
        match="guarded training namespace drifted",
    ):
        patch.execute_and_publish_anfis_ablation_model_manifest_patch_lock_bundle(
            repo_root=tmp_path
        )
    assert calls == 2
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_PATH).exists()
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).exists()
    assert not (tmp_path / patch.LOCKER_GUARD_PATH).exists()


def test_validator_publisher_refuses_existing_final_without_clobber(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_synthetic_publisher(monkeypatch)
    existing = tmp_path / patch.DEFAULT_PATCH_LOCK_PATH
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"foreign")
    with pytest.raises(
        patch.AnfisAblationModelManifestPatchError, match="namespace is occupied"
    ):
        patch.execute_and_publish_anfis_ablation_model_manifest_patch_lock_bundle(
            repo_root=tmp_path
        )
    assert existing.read_bytes() == b"foreign"
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).exists()
    assert not (tmp_path / patch.LOCKER_GUARD_PATH).exists()


def test_unregistered_prefix_rejects_force_added_light_final(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slot = ("A0", 1729)
    paths = {
        "model": Path("models/A0.pt"),
        "checkpoint": Path("models/A0.checkpoint.pt"),
        "preprocessor": Path("reports/A0_preprocessor.json"),
        "training_curve": Path("reports/A0_training_curve.csv"),
        "selection_predictions": Path("data/A0_predictions.parquet"),
        "selection_metrics": Path("reports/A0_selection_metrics.csv"),
        "report": Path("reports/A0_report.md"),
        "manifest": Path("reports/A0_manifest.json"),
    }
    finals = {(tmp_path / path).as_posix() for path in paths.values()}
    light = sorted(paths[name].as_posix() for name in patch.LIGHT_SLOT_OUTPUT_NAMES)
    status = "\n".join(f"?? {path}" for path in light) + "\n"

    monkeypatch.setattr(patch, "ORDERED_SLOTS", (slot,))
    monkeypatch.setattr(
        patch.mt,
        "anfis_ablation_training_slot_paths",
        lambda model_id, base_seed: paths,
    )
    monkeypatch.setattr(
        patch,
        "_lexists",
        lambda path: Path(path).as_posix() in finals,
    )
    monkeypatch.setattr(patch, "_historical_a0_bundle", lambda *args, **kwargs: {})
    monkeypatch.setattr(patch, "E0_M_PATHS", ())
    monkeypatch.setattr(patch, "_git", lambda *args: status)
    assert patch._validate_exact_training_prefix(
        {}, audit_mode=False, repo_root=tmp_path
    ) == 1

    staged = f"A  {light[0]}\n" + "\n".join(
        f"?? {path}" for path in light[1:]
    ) + "\n"
    monkeypatch.setattr(patch, "_git", lambda *args: staged)
    with pytest.raises(
        patch.AnfisAblationModelManifestPatchError,
        match="unregistered slot status drifted",
    ):
        patch._validate_exact_training_prefix(
            {}, audit_mode=False, repo_root=tmp_path
        )


def test_completed_mv_slot_translates_semantic_core_failure_and_rejects_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = {
        "model": Path("models/synthetic.pt"),
        "manifest": Path("reports/synthetic_manifest.json"),
    }
    monkeypatch.setattr(
        patch.mt,
        "anfis_ablation_training_slot_paths",
        lambda model_id, base_seed: paths,
    )
    static: dict[str, Any] = {
        "gate": "E0-MV",
        "status": "effective_preflight_passed",
        "h_patch_head": "1" * 40,
        "p_patch_head": "2" * 40,
        "h_components_sha256": "3" * 64,
        "physical_inputs_sha256": "4" * 64,
        "runtime_sha256": "5" * 64,
        "lock_sha256": "6" * 64,
        "companion_sha256": "7" * 64,
        "runtime": {"role": "runtime"},
        "lock": {"role": "lock"},
        "companion": {"role": "companion"},
    }
    binding = patch._slot_manifest_binding(
        static, model_id="A1", base_seed=1729, index=1
    )

    def record(path: Path, *, role: str, repo_root: Path) -> dict[str, Any]:
        return {
            "role": role,
            "path": path.as_posix(),
            "bytes": 1,
            "sha256": "8" * 64,
        }

    trainer_record = {
        "role": "trainer",
        "path": "src/experiments/train_closure_anfis_ablation.py",
        "bytes": 2,
        "sha256": "9" * 64,
    }
    manifest: dict[str, Any] = {
        "status": "completed",
        "slot_status": "available",
        "fit_status": "passed",
        "model_id": "A1",
        "base_seed": 1729,
        "authority": binding,
        "outputs": [record(paths["model"], role="model", repo_root=tmp_path)],
        "script": trainer_record,
        "source_code": [trainer_record],
        "authority_records": [
            static["runtime"],
            static["lock"],
            static["companion"],
        ],
        "completion_marker_written_last": True,
    }
    monkeypatch.setattr(patch, "_file_record", record)
    monkeypatch.setattr(patch, "_current_trainer_record", lambda root: trainer_record)
    monkeypatch.setattr(
        patch,
        "_read_regular_bytes",
        lambda path, **kwargs: patch._model_manifest_json(manifest),
    )
    monkeypatch.setattr(
        auditor, "_load_runtime_contract", lambda root: ({"gate": "E0-MT"}, {})
    )
    semantic_calls = 0

    def semantic_pass(**kwargs: Any) -> dict[str, Any]:
        nonlocal semantic_calls
        semantic_calls += 1
        return {
            "status": "passed",
            "schema_exact": True,
            "hash_bindings_verified": True,
            "calibration_targets_read": False,
            "test_or_holdout_targets_read": False,
            "future_outcomes_accessed": False,
            "dvc_command_executed": False,
            "scientific_network_egress": False,
            "writes_performed": False,
        }

    monkeypatch.setattr(
        auditor, "validate_anfis_ablation_model_bundle_semantics", semantic_pass
    )
    patch._validate_completed_mv_slot(
        static,
        model_id="A1",
        base_seed=1729,
        target_index=1,
        repo_root=tmp_path,
        target_reference=object(),
    )
    assert semantic_calls == 1

    manifest["status"] = "tampered"
    with pytest.raises(
        patch.AnfisAblationModelManifestPatchError, match="manifest drifted"
    ):
        patch._validate_completed_mv_slot(
            static,
            model_id="A1",
            base_seed=1729,
            target_index=1,
            repo_root=tmp_path,
            target_reference=object(),
        )
    assert semantic_calls == 1
    manifest["status"] = "completed"

    def semantic_failure(**kwargs: Any) -> dict[str, Any]:
        raise auditor.AnfisAblationModelAuditError("injected semantic tamper")

    monkeypatch.setattr(
        auditor, "validate_anfis_ablation_model_bundle_semantics", semantic_failure
    )
    with pytest.raises(
        patch.AnfisAblationModelManifestPatchError, match="failed semantic audit"
    ) as failure:
        patch._validate_completed_mv_slot(
            static,
            model_id="A1",
            base_seed=1729,
            target_index=1,
            repo_root=tmp_path,
            target_reference=object(),
        )
    assert isinstance(failure.value.__cause__, auditor.AnfisAblationModelAuditError)


def test_effective_cli_forwards_exact_target_and_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[dict[str, Any]] = []

    def load(**kwargs: Any) -> dict[str, Any]:
        observed.append(kwargs)
        return {
            "gate": "E0-MV",
            "authorized_model_id": kwargs["model_id"],
            "authorized_base_seed": kwargs["base_seed"],
            "audit_current_unpublished": kwargs["audit_current_unpublished"],
        }

    monkeypatch.setattr(
        patch, "load_effective_anfis_ablation_model_manifest_authority", load
    )
    result = locker.check_effective(
        model_id="A0", base_seed=1729, audit_current_unpublished=True
    )
    assert observed == [
        {
            "model_id": "A0",
            "base_seed": 1729,
            "audit_current_unpublished": True,
            "verify_remote": True,
        }
    ]
    assert result["audit_current_unpublished"] is True


def test_locker_main_translates_only_the_closed_patch_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        locker,
        "check_only",
        lambda: (_ for _ in ()).throw(
            patch.AnfisAblationModelManifestPatchError("closed")
        ),
    )
    assert locker.main(["--check-only"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "closed\n"


def test_document_closes_archive_and_uses_command_scoped_excludes() -> None:
    document = (
        ROOT / "docs/closure_v1/E0_M_ANFIS_ABLATION_MODEL_MANIFEST_PATCH_1.md"
    ).read_text(encoding="utf-8")
    for path in ADOPTED_A0_LIGHT_PATHS:
        assert f"/{path}" in document
    for token in (
        "GIT_CONFIG_COUNT=1",
        "GIT_CONFIG_KEY_0=core.excludesFile",
        "GIT_CONFIG_VALUE_0=<absolute exclusive temporary file>",
        "0600",
        "--allow-unmanaged --no-push",
        "--defer-dvc-target models",
        "models.dvc",
        "72",
        "historical_inputs",
        "slot_manifest_authority",
        "slot_source_record",
    ):
        assert token in document
    assert "Archiving, renaming, copying back" in document
    assert "`5M+5A`" in document


def test_locker_source_cannot_train_audit_or_run_dvc() -> None:
    source = inspect.getsource(locker)
    for forbidden in (
        "train_closure_anfis_ablation.py",
        "audit_closure_anfis_ablation_model_bundle.py",
        "dvc add",
        "dvc push",
        "execute_one_shot",
    ):
        assert forbidden not in source
