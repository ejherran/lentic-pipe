from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.data import prepare_commit_artifacts as precommit
from src.experiments import (
    closure_final_calibration_r8_post_publication_authority_patch as patch,
)


def _readiness(*, effective: bool = False) -> dict[str, Any]:
    return {
        "gate": "E0-MCALM",
        "status": "formal_e0_m_static_readiness_validated",
        "effective_p_mcalm_verified": effective,
        "terminal_r_commit": patch.BASE_R_MCALL_COMMIT,
        "r8_published": True,
        "r8_output_count": 8,
        "r8_outputs_sha256": "a" * 64,
        "e0_m_output_count": 0,
        "outcome_access_log_state": "absent",
        "outcome_access_log_required_e0_m_state": "present_empty",
        "formal_e0_m_entrypoint_present": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "outcome_access_authorized": False,
        "scientific_rerun_authorized": False,
        "writes_performed": False,
    }


def _unpublished(*, stage_state: str = "untracked") -> dict[str, Any]:
    return {
        "gate": "E0-MCALM",
        "status": "unpublished_p_mcalm_lock_bundle_validated",
        "p_stage_state": stage_state,
        "p_output_count": 2,
        "physical_input_count": 16,
        "historical_input_count": 6,
        "companion_output_count": 1,
        "coordination_forbidden_count": 49,
        "coordination_present_count": 0,
        "r8_output_count": 8,
        "r8_outputs_sha256": "a" * 64,
        "r8_published": True,
        "r8_staging_authorized": False,
        "effective_authority": False,
        "e0_m_authorized": False,
        "scientific_rerun_authorized": False,
        "dvc_commands_authorized": False,
        "dvc_push_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
        "writes_performed": False,
    }


def _fake_patch(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "PATCH_GATE": patch.PATCH_GATE,
        "BASE_R_MCALL_COMMIT": patch.BASE_R_MCALL_COMMIT,
        "FINAL_CALIBRATION_H_STAGED_SCOPE": patch.FINAL_CALIBRATION_H_STAGED_SCOPE,
        "FINAL_CALIBRATION_P_STAGED_SCOPE": patch.FINAL_CALIBRATION_P_STAGED_SCOPE,
        "R8_OUTPUT_CONTRACT": patch.R8_OUTPUT_CONTRACT,
        "FinalCalibrationR8PostPublicationAuthorityPatchError": (
            patch.FinalCalibrationR8PostPublicationAuthorityPatchError
        ),
        "validate_final_calibration_r8_post_publication_authority_model_lock_readiness": (
            lambda **kwargs: _readiness(
                effective=bool(kwargs["require_effective"])
            )
        ),
        "validate_final_calibration_r8_post_publication_authority_unpublished_lock_bundle": (
            lambda **kwargs: _unpublished()
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _staged(scope: dict[str, str]) -> str:
    return "".join(
        f"{status}\t{path}\n" for path, status in reversed(tuple(scope.items()))
    )


def _short(scope: dict[str, str], *, staged: bool = False) -> str:
    rows = []
    for path, status in reversed(tuple(scope.items())):
        code = f"{status} " if staged else "??" if status == "A" else " M"
        rows.append(f"{code} {path}\n")
    return "".join(rows)


def test_mcalm_topology_is_h6_p2_without_r_restage() -> None:
    assert patch.PATCH_GATE == "E0-MCALM"
    assert patch.BASE_R_MCALL_COMMIT == "09309c2d16820f5d93fe9fd38dadef92377fd005"
    assert len(patch.FINAL_CALIBRATION_H_STAGED_SCOPE) == 6
    assert list(patch.FINAL_CALIBRATION_H_STAGED_SCOPE.values()).count("M") == 1
    assert list(patch.FINAL_CALIBRATION_H_STAGED_SCOPE.values()).count("A") == 5
    assert patch.FINAL_CALIBRATION_H_STAGED_SCOPE[patch.PRECOMMIT_PATH] == "M"
    assert len(patch.FINAL_CALIBRATION_P_STAGED_SCOPE) == 2
    assert set(patch.FINAL_CALIBRATION_P_STAGED_SCOPE.values()) == {"A"}
    assert not set(patch.R8_STAGED_SCOPE) & set(
        patch.FINAL_CALIBRATION_H_STAGED_SCOPE
    )
    assert not set(patch.R8_STAGED_SCOPE) & set(
        patch.FINAL_CALIBRATION_P_STAGED_SCOPE
    )
    assert patch.COORDINATION_NAMESPACE_CONTRACT[
        "coordination_forbidden_count"
    ] == 49
    assert patch.COORDINATION_NAMESPACE_CONTRACT["historical_published_lock_count"] == 20


def test_h_pre_stage_routes_only_h6_from_clean_published_r(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def readiness(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return _readiness(effective=False)

    fake = _fake_patch(
        validate_final_calibration_r8_post_publication_authority_model_lock_readiness=readiness
    )
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_post_publication_authority_patch_module",
        lambda: fake,
    )
    monkeypatch.setattr(
        precommit,
        "_git_output",
        lambda *args: fake.BASE_R_MCALL_COMMIT + "\n",
    )
    result = precommit.final_calibration_r8_post_publication_authority_pre_stage_scope(
        _short(fake.FINAL_CALIBRATION_H_STAGED_SCOPE)
    )
    assert result == (
        "H-E0-MCALM",
        tuple(sorted(fake.FINAL_CALIBRATION_H_STAGED_SCOPE)),
    )
    assert calls == [
        {
            "repo_root": Path("."),
            "verify_remote": True,
            "require_effective": False,
        }
    ]
    assert result is not None
    assert not set(result[1]) & set(patch.R8_STAGED_SCOPE)


def test_h_pre_stage_rejects_extra_missing_duplicate_and_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _fake_patch()
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_post_publication_authority_patch_module",
        lambda: fake,
    )
    monkeypatch.setattr(
        precommit,
        "_git_output",
        lambda *args: fake.BASE_R_MCALL_COMMIT + "\n",
    )
    exact = _short(fake.FINAL_CALIBRATION_H_STAGED_SCOPE)
    candidates = (
        exact + "?? extra.txt\n",
        "".join(exact.splitlines(keepends=True)[:-1]),
        exact + exact.splitlines(keepends=True)[0],
        exact + "malformed\n",
        exact.replace("?? ", " M", 1),
    )
    for candidate in candidates:
        with pytest.raises(
            precommit.FinalCalibrationR8PostPublicationAuthorityAdapterError
        ):
            precommit.final_calibration_r8_post_publication_authority_pre_stage_scope(
                candidate
            )


def test_p_pre_stage_routes_only_p2_and_reconstructs_h(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def unpublished(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return _unpublished()

    fake = _fake_patch(
        validate_final_calibration_r8_post_publication_authority_unpublished_lock_bundle=unpublished
    )
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_post_publication_authority_patch_module",
        lambda: fake,
    )

    def git_output(repo_root: Path, *args: str) -> str:
        del repo_root
        if args == ("rev-parse", "HEAD"):
            return "h" * 40 + "\n"
        if args == ("rev-parse", "HEAD^"):
            return fake.BASE_R_MCALL_COMMIT + "\n"
        return _staged(fake.FINAL_CALIBRATION_H_STAGED_SCOPE)

    monkeypatch.setattr(precommit, "_git_output", git_output)
    result = precommit.final_calibration_r8_post_publication_authority_pre_stage_scope(
        _short(fake.FINAL_CALIBRATION_P_STAGED_SCOPE)
    )
    assert result == (
        "P-E0-MCALM",
        tuple(sorted(fake.FINAL_CALIBRATION_P_STAGED_SCOPE)),
    )
    assert calls == [{"repo_root": Path("."), "verify_remote": True}]


def test_p_pre_stage_rejects_semantic_count_namespace_and_publication_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake = _fake_patch()
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_post_publication_authority_patch_module",
        lambda: fake,
    )

    def git_output(repo_root: Path, *args: str) -> str:
        del repo_root
        if args == ("rev-parse", "HEAD"):
            return "h" * 40 + "\n"
        if args == ("rev-parse", "HEAD^"):
            return fake.BASE_R_MCALL_COMMIT + "\n"
        return _staged(fake.FINAL_CALIBRATION_H_STAGED_SCOPE)

    monkeypatch.setattr(precommit, "_git_output", git_output)
    for key, value in (
        ("physical_input_count", 15),
        ("historical_input_count", 5),
        ("coordination_forbidden_count", 48),
        ("coordination_present_count", 1),
        ("r8_published", False),
        ("r8_staging_authorized", True),
        ("dvc_commands_authorized", True),
        ("git_push_authorized", True),
    ):
        monkeypatch.setattr(
            fake,
            "validate_final_calibration_r8_post_publication_authority_unpublished_lock_bundle",
            lambda key=key, value=value, **kwargs: {
                **_unpublished(),
                key: value,
            },
        )
        with pytest.raises(
            precommit.FinalCalibrationR8PostPublicationAuthorityAdapterError,
            match="semantic validation result drifted",
        ):
            precommit.final_calibration_r8_post_publication_authority_pre_stage_scope(
                _short(fake.FINAL_CALIBRATION_P_STAGED_SCOPE)
            )

    released = False
    post_release_present_count = 0
    rollback_count = 0
    publication_order: list[Path] = []

    def acquire(*args: Any, **kwargs: Any) -> SimpleNamespace:
        del args, kwargs
        return SimpleNamespace(path="guard")

    def release(*args: Any, **kwargs: Any) -> None:
        nonlocal released
        del args, kwargs
        released = True

    def namespace(
        *, current_outputs_state: str, owned_guard: Any = None, **kwargs: Any
    ) -> dict[str, Any]:
        nonlocal post_release_present_count
        del kwargs
        if released and current_outputs_state == "present" and owned_guard is None:
            post_release_present_count += 1
            raise patch.FinalCalibrationR8PostPublicationAuthorityPatchError(
                "E0-MCALM temporary appeared after guard release"
            )
        return {"coordination_present_count": 0}

    def publish(path: Path, payload: bytes, *, repo_root: Path) -> SimpleNamespace:
        publication_order.append(path)
        target = repo_root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return SimpleNamespace(path=path)

    def rollback(outputs: list[SimpleNamespace]) -> None:
        nonlocal rollback_count
        rollback_count = len(outputs)
        for output in outputs:
            (tmp_path / output.path).unlink(missing_ok=True)

    monkeypatch.setattr(
        patch,
        "validate_final_calibration_r8_post_publication_authority_patch_lock_payload",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        patch, "_require_publication_verification", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        patch, "_require_repository_checkpoint", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(patch, "_require_coordination_namespace", namespace)
    monkeypatch.setattr(patch, "_physical_snapshot", lambda *args, **kwargs: ())
    monkeypatch.setattr(
        patch, "_require_physical_snapshot", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(patch.mcal, "_git_head", lambda *args, **kwargs: "h" * 40)
    monkeypatch.setattr(patch.mt, "_acquire_publication_guard", acquire)
    monkeypatch.setattr(patch.mt, "_release_publication_guard", release)
    monkeypatch.setattr(patch.mcall.mcalk, "_publish_bytes_no_clobber", publish)
    monkeypatch.setattr(patch.mcall.mcalk, "_rollback_outputs_best_effort", rollback)
    monkeypatch.setattr(
        patch,
        "_expected_companion",
        lambda *args, **kwargs: {"manifest_written_last": True},
    )
    monkeypatch.setattr(
        patch.mcall.mcalk.mcalj,
        "_validate_owned_output_bytes",
        lambda *args, **kwargs: None,
    )
    with pytest.raises(
        patch.FinalCalibrationR8PostPublicationAuthorityPatchError,
        match="temporary appeared after guard release",
    ):
        patch.publish_final_calibration_r8_post_publication_authority_patch_lock_bundle(
            {"repository": {"h_patch_head": "h" * 40}},
            repo_root=tmp_path,
        )
    assert post_release_present_count == 1
    assert publication_order == [
        patch.DEFAULT_PATCH_LOCK_PATH,
        patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
    ]
    assert rollback_count == 2
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_PATH).exists()
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).exists()


def test_no_mcalm_candidate_leaves_generic_status_unclaimed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _fake_patch()
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_post_publication_authority_patch_module",
        lambda: fake,
    )
    assert (
        precommit.final_calibration_r8_post_publication_authority_pre_stage_scope(
            "?? unrelated.txt\n"
        )
        is None
    )
    assert (
        precommit.final_calibration_r8_post_publication_authority_pre_stage_scope("")
        is None
    )


def test_staged_scope_is_exact_for_h_and_p() -> None:
    for gate, scope in (
        ("H-E0-MCALM", patch.FINAL_CALIBRATION_H_STAGED_SCOPE),
        ("P-E0-MCALM", patch.FINAL_CALIBRATION_P_STAGED_SCOPE),
    ):
        exact = _staged(scope)
        precommit.validate_final_calibration_r8_post_publication_authority_staged_scope(
            exact,
            gate=gate,
        )
        for candidate in (
            exact + "A\textra.txt\n",
            "".join(exact.splitlines(keepends=True)[:-1]),
            exact + exact.splitlines(keepends=True)[0],
        ):
            with pytest.raises(
                precommit.FinalCalibrationR8PostPublicationAuthorityAdapterError
            ):
                precommit.validate_final_calibration_r8_post_publication_authority_staged_scope(
                    candidate,
                    gate=gate,
                )


def test_workspace_scope_contains_only_staged_h_or_p_and_never_r8() -> None:
    for gate, scope in (
        ("H-E0-MCALM", patch.FINAL_CALIBRATION_H_STAGED_SCOPE),
        ("P-E0-MCALM", patch.FINAL_CALIBRATION_P_STAGED_SCOPE),
    ):
        exact = _short(scope, staged=True)
        precommit.validate_final_calibration_r8_post_publication_authority_workspace_scope(
            exact,
            gate=gate,
        )
        for candidate in (
            exact + "?? extra.txt\n",
            exact + f"A  {next(iter(patch.R8_STAGED_SCOPE))}\n",
            "".join(exact.splitlines(keepends=True)[:-1]),
        ):
            with pytest.raises(
                precommit.FinalCalibrationR8PostPublicationAuthorityAdapterError
            ):
                precommit.validate_final_calibration_r8_post_publication_authority_workspace_scope(
                    candidate,
                    gate=gate,
                )


def test_invocation_is_closed_before_dvc_discovery() -> None:
    valid = SimpleNamespace(
        no_push=True,
        yes=False,
        dry_run=False,
        skip_publication_check=False,
        jobs=None,
        dvc_bin=None,
        manifest=precommit.DEFAULT_DVC_MANIFEST,
        report=None,
        allow_unmanaged=True,
        target=[],
        defer_dvc_target=[],
        register_anfis_ablation_model_family=False,
        verify_manifest_inputs=False,
        max_manifest_hash_bytes=precommit.DEFAULT_MAX_MANIFEST_HASH_BYTES,
    )
    env = {"DVC_NO_ANALYTICS": "1"}
    precommit.validate_final_calibration_r8_post_publication_authority_invocation(
        valid,
        env=env,
    )
    mutations = {
        "no_push": False,
        "yes": True,
        "dry_run": True,
        "skip_publication_check": True,
        "jobs": "1",
        "dvc_bin": "custom",
        "manifest": Path("custom.yaml"),
        "report": Path("custom.md"),
        "allow_unmanaged": False,
        "target": ["x"],
        "defer_dvc_target": ["x"],
        "register_anfis_ablation_model_family": True,
        "verify_manifest_inputs": True,
        "max_manifest_hash_bytes": 1,
    }
    for name, value in mutations.items():
        candidate = SimpleNamespace(**vars(valid))
        setattr(candidate, name, value)
        with pytest.raises(
            precommit.FinalCalibrationR8PostPublicationAuthorityAdapterError
        ):
            precommit.validate_final_calibration_r8_post_publication_authority_invocation(
                candidate,
                env=env,
            )
    for changed_env in ({}, {**env, "DVC_BIN": "dvc"}):
        with pytest.raises(
            precommit.FinalCalibrationR8PostPublicationAuthorityAdapterError
        ):
            precommit.validate_final_calibration_r8_post_publication_authority_invocation(
                valid,
                env=changed_env,
            )


def test_snapshot_requires_exact8_published_regular_single_link_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _fake_patch()
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_post_publication_authority_patch_module",
        lambda: fake,
    )
    physical = {record["path"]: dict(record) for record in fake.R8_OUTPUT_CONTRACT}
    inode = {path: index for index, path in enumerate(physical)}

    def identity(path: Path, **kwargs: Any) -> SimpleNamespace:
        del kwargs
        expected = physical[path.as_posix()]
        return SimpleNamespace(
            device=1,
            inode=inode[path.as_posix()],
            mode=0o644,
            nlink=1,
            size=expected["bytes"],
            sha256=expected["sha256"],
            mtime_ns=1,
            ctime_ns=1,
        )

    monkeypatch.setattr(precommit, "_registration_file_identity", identity)
    first = precommit.snapshot_final_calibration_r8_post_publication_outputs()
    assert len(first) == 8
    inode[first[0].path] += 100
    assert precommit.snapshot_final_calibration_r8_post_publication_outputs() != first
    physical[first[0].path]["sha256"] = "0" * 64
    with pytest.raises(
        precommit.FinalCalibrationR8PostPublicationAuthorityAdapterError,
        match="published R8 identity drifted",
    ):
        precommit.snapshot_final_calibration_r8_post_publication_outputs()


def test_h_transaction_revalidates_remote_readiness_and_r8_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def readiness(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return _readiness(effective=False)

    fake = _fake_patch(
        validate_final_calibration_r8_post_publication_authority_model_lock_readiness=readiness
    )
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_post_publication_authority_patch_module",
        lambda: fake,
    )
    monkeypatch.setattr(
        precommit,
        "validate_final_calibration_r8_post_publication_authority_staged_scope",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        precommit,
        "validate_final_calibration_r8_post_publication_authority_workspace_scope",
        lambda *args, **kwargs: None,
    )
    snapshot = (
        precommit.FinalCalibrationR8PhysicalIdentity(
            "x", 1, 1, 0o644, 1, 1, "x", 1, 1
        ),
    )
    monkeypatch.setattr(
        precommit,
        "snapshot_final_calibration_r8_post_publication_outputs",
        lambda **kwargs: snapshot,
    )
    monkeypatch.setattr(precommit, "_git_output", lambda *args: "scope\n")
    precommit.revalidate_final_calibration_r8_post_publication_authority_transaction(
        gate="H-E0-MCALM",
        staged_status="scope\n",
        expected_snapshot=snapshot,
    )
    assert calls == [
        {
            "repo_root": Path("."),
            "verify_remote": True,
            "require_effective": False,
        }
    ]


def test_p_transaction_revalidates_staged_unpublished_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def unpublished(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return _unpublished(stage_state="staged")

    fake = _fake_patch(
        validate_final_calibration_r8_post_publication_authority_unpublished_lock_bundle=unpublished
    )
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_post_publication_authority_patch_module",
        lambda: fake,
    )
    monkeypatch.setattr(
        precommit,
        "validate_final_calibration_r8_post_publication_authority_staged_scope",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        precommit,
        "validate_final_calibration_r8_post_publication_authority_workspace_scope",
        lambda *args, **kwargs: None,
    )
    snapshot = (
        precommit.FinalCalibrationR8PhysicalIdentity(
            "x", 1, 1, 0o644, 1, 1, "x", 1, 1
        ),
    )
    monkeypatch.setattr(
        precommit,
        "snapshot_final_calibration_r8_post_publication_outputs",
        lambda **kwargs: snapshot,
    )
    monkeypatch.setattr(precommit, "_git_output", lambda *args: "scope\n")
    precommit.revalidate_final_calibration_r8_post_publication_authority_transaction(
        gate="P-E0-MCALM",
        staged_status="scope\n",
        expected_snapshot=snapshot,
    )
    assert calls == [{"repo_root": Path("."), "verify_remote": True}]


def test_readiness_summary_drift_and_core_error_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _fake_patch()
    for key, value in (
        ("status", "wrong"),
        ("effective_p_mcalm_verified", True),
        ("terminal_r_commit", "0" * 40),
        ("r8_published", False),
        ("r8_output_count", 7),
        ("r8_outputs_sha256", "short"),
        ("e0_m_output_count", 1),
        ("outcome_access_log_state", "present"),
        ("formal_e0_m_entrypoint_present", True),
        ("e0_m_authorized", True),
        ("e0_u_authorized", True),
        ("outcome_access_authorized", True),
        ("scientific_rerun_authorized", True),
        ("writes_performed", True),
    ):
        fake.validate_final_calibration_r8_post_publication_authority_model_lock_readiness = (
            lambda key=key, value=value, **kwargs: {
                **_readiness(effective=False),
                key: value,
            }
        )
        with pytest.raises(
            precommit.FinalCalibrationR8PostPublicationAuthorityAdapterError,
            match="readiness result drifted",
        ):
            precommit._require_final_calibration_r8_post_publication_authority_readiness(
                patch=fake,
                repo_root=Path("."),
                require_effective=False,
            )
    fake.validate_final_calibration_r8_post_publication_authority_model_lock_readiness = (
        lambda **kwargs: (_ for _ in ()).throw(
            patch.FinalCalibrationR8PostPublicationAuthorityPatchError(
                "E0-MCALM namespace drifted"
            )
        )
    )
    with pytest.raises(
        precommit.FinalCalibrationR8PostPublicationAuthorityAdapterError,
        match="E0-MCALM namespace drifted",
    ):
        precommit._require_final_calibration_r8_post_publication_authority_readiness(
            patch=fake,
            repo_root=Path("."),
            require_effective=False,
        )

    parse_count = 0
    namespace_count = 0

    def parse(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], bytes, object]:
        nonlocal parse_count
        del args, kwargs
        parse_count += 1
        value = {"repository": {"h_patch_head": "h" * 40}}
        if parse_count % 2 == 0:
            value = {"manifest_written_last": True}
        return value, b"{}\n", object()

    def namespace(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal namespace_count
        del args, kwargs
        namespace_count += 1
        if namespace_count == 2:
            raise patch.FinalCalibrationR8PostPublicationAuthorityPatchError(
                "E0-MCALM temporary appeared between loader snapshots"
            )
        return {"coordination_present_count": 0}

    publication = {
        "h_patch_head": "h" * 40,
        "p_patch_head": "p" * 40,
        "remote_head": "p" * 40,
    }
    r8 = {"r8_output_count": 8, "r8_outputs_sha256": "a" * 64}
    monkeypatch.setattr(patch, "_parse_canonical_json_with_metadata", parse)
    monkeypatch.setattr(
        patch, "_validate_published_lock_payload", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        patch,
        "_expected_companion",
        lambda *args, **kwargs: {"manifest_written_last": True},
    )
    monkeypatch.setattr(patch.mcal, "_file_record", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        patch, "_validate_p_publication", lambda *args, **kwargs: publication
    )
    monkeypatch.setattr(patch, "_require_coordination_namespace", namespace)
    monkeypatch.setattr(
        patch, "_validate_r8_bundle_post_publication", lambda *args, **kwargs: r8
    )
    monkeypatch.setattr(patch, "_physical_snapshot", lambda *args, **kwargs: ())
    monkeypatch.setattr(
        patch, "_require_physical_snapshot", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        patch.mcall.mcalk.mcalj, "_metadata_identity", lambda value: None
    )
    with pytest.raises(
        patch.FinalCalibrationR8PostPublicationAuthorityPatchError,
        match="temporary appeared between loader snapshots",
    ):
        patch.load_effective_final_calibration_r8_post_publication_authority_patch_authority(
            verify_remote=False,
            repo_root=Path("."),
        )

    parse_count = 0
    namespace_count = 0
    monkeypatch.setattr(
        patch,
        "_require_coordination_namespace",
        lambda *args, **kwargs: {"coordination_present_count": 0},
    )
    authority = (
        patch.load_effective_final_calibration_r8_post_publication_authority_patch_authority(
            verify_remote=False,
            repo_root=Path("."),
        )
    )
    assert authority["r_lifecycle_state"] == "both_bundles_published_terminal"
    assert authority["r_outputs_published"] is True
    assert authority["r_outputs_ready_for_staging"] is False
    assert authority["r8_staging_authorized"] is False
    assert authority["formal_e0_m_execution_authorized"] is False
    assert authority["e0_m_authorized"] is False
    assert authority["outcome_access_authorized"] is False


def test_unpublished_core_error_keeps_one_mcalm_prefix() -> None:
    fake = _fake_patch(
        validate_final_calibration_r8_post_publication_authority_unpublished_lock_bundle=(
            lambda **kwargs: (_ for _ in ()).throw(
                patch.FinalCalibrationR8PostPublicationAuthorityPatchError(
                    "E0-MCALM unpublished companion drifted"
                )
            )
        )
    )
    with pytest.raises(
        precommit.FinalCalibrationR8PostPublicationAuthorityAdapterError
    ) as captured:
        precommit._require_final_calibration_r8_post_publication_authority_unpublished_p_validation(
            patch=fake,
            repo_root=Path("."),
            expected_stage_state="untracked",
        )
    assert str(captured.value).count("E0-MCALM") == 1
    assert "E0-MCALL" not in str(captured.value)


def test_main_routes_mcalm_first_and_uses_directed_add_with_two_checkpoints() -> None:
    assert isinstance(
        precommit._final_calibration_stage_adapter_error("H-E0-MCALM", "x"),
        precommit.FinalCalibrationR8PostPublicationAuthorityAdapterError,
    )
    assert isinstance(
        precommit._final_calibration_stage_adapter_error("R-E0-MCALL", "x"),
        precommit.FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError,
    )
    assert isinstance(
        precommit._final_calibration_stage_adapter_error("R-E0-MCALK", "x"),
        precommit.FinalCalibrationR8ManifestReproducibilityAdapterError,
    )
    source = Path(precommit.__file__).read_text(encoding="utf-8")
    main = source[source.index("def main() -> int:") :]
    mcalm = main.index(
        "final_calibration_r8_post_publication_authority_pre_stage_scope("
    )
    mcall = main.index(
        "final_calibration_r8_coordination_namespace_revalidation_pre_stage_scope("
    )
    mcalk = main.index(
        "final_calibration_r8_manifest_reproducibility_pre_stage_scope("
    )
    dvc = main.index("dvc_status_before = dvc_status_json(dvc_bin)")
    assert mcalm < mcall < mcalk < dvc
    assert '"status", "--short", "--untracked-files=all"' in main
    assert '"git",\n                "add",\n                "-A",\n                "--",' in main
    assert "final_calibration_stage_gate and selected_dvc_paths" in main
    assert "deferred_dvc_paths or final_calibration_stage_gate" in main
    assert main.count(
        "revalidate_final_calibration_r8_post_publication_authority_transaction("
    ) == 2


def test_mcalm_keeps_generic_reproducibility_checks_unchanged_and_has_no_r_gate() -> None:
    source = Path(precommit.__file__).read_text(encoding="utf-8")
    main = source[source.index("def main() -> int:") :]
    assert 'final_calibration_stage_gate == "R-E0-MCALM"' not in main
    assert "final_calibration_r8_post_publication_authority_checks" not in source
    assert 'else:\n            reproducibility_findings = reproducibility_checks(' in main
    assert "R8_STAGED_SCOPE" not in str(patch.FINAL_CALIBRATION_H_STAGED_SCOPE)
    assert "R8_STAGED_SCOPE" not in str(patch.FINAL_CALIBRATION_P_STAGED_SCOPE)
