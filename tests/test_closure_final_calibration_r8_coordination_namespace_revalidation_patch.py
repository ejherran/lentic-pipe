from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.data import prepare_commit_artifacts as precommit
from src.experiments import (
    closure_final_calibration_r8_coordination_namespace_revalidation_patch as patch,
)


def _finding_contract() -> tuple[precommit.ReproducibilityFinding, ...]:
    return tuple(
        precommit.ReproducibilityFinding(**record)
        for record in patch.GENERIC_MANIFEST_FINDINGS_CONTRACT
    )


def _validation(*, staged: bool = True) -> dict[str, Any]:
    return {
        "gate": "E0-MCALL",
        "status": "r8_coordination_namespace_revalidation_adoption_validated",
        "r8_output_count": 8,
        "calibration_output_count": 6,
        "e7_output_count": 2,
        "r_lifecycle_state": "both_bundles_completed_unpublished",
        "r8_outputs": list(patch.R8_OUTPUT_CONTRACT),
        "r8_outputs_sha256": "a" * 64,
        "expected_non_ok_findings": list(
            patch.GENERIC_MANIFEST_FINDINGS_CONTRACT
        ),
        "staged_scope_verified": staged,
        "coordination_forbidden_count": 46,
        "coordination_present_count": 0,
        "effective_p_mcall_verified": staged,
        "scientific_rerun_performed": False,
        "r8_rewrite_performed": False,
    }


def _unpublished(*, stage_state: str = "untracked") -> dict[str, Any]:
    return {
        "gate": "E0-MCALL",
        "status": "unpublished_p_mcall_lock_bundle_validated",
        "p_stage_state": stage_state,
        "p_output_count": 2,
        "physical_input_count": 16,
        "historical_input_count": 6,
        "companion_output_count": 1,
        "coordination_forbidden_count": 46,
        "coordination_present_count": 0,
        "r8_output_count": 8,
        "r8_outputs_sha256": "a" * 64,
        "r8_staging_authorized": False,
        "effective_authority": False,
        "scientific_rerun_authorized": False,
        "writes_performed": False,
    }


def _fake_patch(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "PATCH_GATE": patch.PATCH_GATE,
        "BASE_H_MCALK_COMMIT": patch.BASE_H_MCALK_COMMIT,
        "COORDINATION_NAMESPACE_CONTRACT": patch.COORDINATION_NAMESPACE_CONTRACT,
        "FINAL_CALIBRATION_H_STAGED_SCOPE": patch.FINAL_CALIBRATION_H_STAGED_SCOPE,
        "FINAL_CALIBRATION_P_STAGED_SCOPE": patch.FINAL_CALIBRATION_P_STAGED_SCOPE,
        "R8_STAGED_SCOPE": patch.R8_STAGED_SCOPE,
        "R8_OUTPUT_CONTRACT": patch.R8_OUTPUT_CONTRACT,
        "GENERIC_MANIFEST_FINDINGS_CONTRACT": (
            patch.GENERIC_MANIFEST_FINDINGS_CONTRACT
        ),
        "FinalCalibrationR8CoordinationNamespaceRevalidationPatchError": (
            patch.FinalCalibrationR8CoordinationNamespaceRevalidationPatchError
        ),
        "validate_final_calibration_r8_coordination_namespace_revalidation_adoption": (
            lambda **kwargs: _validation(staged=bool(kwargs["require_staged"]))
        ),
        "validate_final_calibration_r8_coordination_namespace_revalidation_unpublished_lock_bundle": (
            lambda **kwargs: _unpublished()
        ),
        "require_final_calibration_r8_coordination_namespace_revalidation_patch_authority": (
            lambda **kwargs: {
                "gate": "E0-MCALL",
                "status": "effective",
                "coordination_namespace_revalidation": (
                    patch.COORDINATION_NAMESPACE_CONTRACT
                ),
                "r_output_present_count": 8,
                "r_lifecycle_state": "both_bundles_completed_unpublished",
                "effective_authority": True,
                "r8_staging_authorized": True,
                "writes_performed": False,
            }
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _staged(scope: dict[str, str]) -> str:
    return "".join(
        f"{status}\t{path}\n" for path, status in reversed(tuple(scope.items()))
    )


def _pre_stage(*scopes: dict[str, str]) -> str:
    merged: dict[str, str] = {}
    for scope in scopes:
        merged.update(
            {
                path: "??" if status == "A" else " M"
                for path, status in scope.items()
            }
        )
    return "".join(
        f"{status} {path}\n" for path, status in reversed(tuple(merged.items()))
    )


def _adopt(
    monkeypatch: pytest.MonkeyPatch,
    findings: list[precommit.ReproducibilityFinding],
    *,
    fake: SimpleNamespace | None = None,
) -> list[precommit.ReproducibilityFinding]:
    selected = fake or _fake_patch()
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_coordination_namespace_revalidation_patch_module",
        lambda: selected,
    )
    return precommit.adopt_final_calibration_r8_coordination_namespace_revalidation_findings(
        findings,
        staged_status=_staged(selected.R8_STAGED_SCOPE),
    )


def test_mcall_precommit_scopes_and_topology_are_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert patch.PATCH_GATE == "E0-MCALL"
    assert patch.BASE_H_MCALK_COMMIT == "6f078da52c5dd699ea312df209bfef5a8d120d00"
    assert len(patch.FINAL_CALIBRATION_H_STAGED_SCOPE) == 6
    assert list(patch.FINAL_CALIBRATION_H_STAGED_SCOPE.values()).count("M") == 1
    assert list(patch.FINAL_CALIBRATION_H_STAGED_SCOPE.values()).count("A") == 5
    assert patch.FINAL_CALIBRATION_H_STAGED_SCOPE[patch.PRECOMMIT_PATH] == "M"
    assert patch.FINAL_CALIBRATION_P_STAGED_SCOPE == {
        patch.DEFAULT_PATCH_LOCK_PATH.as_posix(): "A",
        patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(): "A",
    }
    assert len(patch.R8_STAGED_SCOPE) == 8
    assert set(patch.R8_STAGED_SCOPE.values()) == {"A"}
    assert patch.SUPERSEDED_CHECK_ONLY == {
        "attempted_gate": "P-E0-MCALK",
        "mode": "check_only",
        "status": "superseded_check_only_interrupted_after_static_blocker_detected",
        "interruption": "KeyboardInterrupt",
        "phase": "read_only_historical_input_rehash",
        "last_observed_path": "data/fuzzy/state_vector_v0.parquet",
        "static_blocker": "predecessor_coordination_guard_race_and_loader_omission",
        "publication_started": False,
        "authorization_consumed": False,
        "writes_performed": False,
        "guard_created": False,
        "guard_removed": False,
        "p_output_count": 0,
        "temporary_output_count": 0,
        "coordination_present_count": 0,
        "r8_output_count": 8,
        "r8_bytes_changed": False,
        "r8_rewrite_performed": False,
        "scientific_rerun_performed": False,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
    }

    def forbidden_science(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise AssertionError("historical science must not be opened or rehashed")

    monkeypatch.setattr(patch.mcalk, "_p_mcalj_authority", forbidden_science)
    monkeypatch.setattr(patch.mcal, "_scientific_input_inventory", forbidden_science)
    historical = patch._historical_p_mcalj_git_authority(
        repo_root=patch.PROJECT_ROOT
    )
    assert historical["historical_scientific_inputs_rehashed"] is False
    assert historical["science_payloads_opened"] is False
    prelock = patch.collect_final_calibration_r8_coordination_namespace_revalidation_patch_prelock_state(
        verify_remote=False,
        repo_root=patch.PROJECT_ROOT,
    )
    assert prelock["p_mcalj_authority"][
        "historical_scientific_inputs_rehashed"
    ] is False
    assert prelock["p_mcalj_authority"]["science_payloads_opened"] is False
    assert prelock["prelock"]["scientific_writes_performed"] is False
    assert prelock["prelock"]["outcome_paths_opened"] is False
    namespace = patch._require_coordination_namespace(
        repo_root=patch.PROJECT_ROOT,
        current_outputs_state="absent",
    )
    assert namespace["historical_published_lock_count"] == 18
    assert namespace["never_published_lock_present_count"] == 0
    assert namespace["current_lock_present_count"] == 0
    assert namespace["coordination_forbidden_count"] == 46
    assert namespace["coordination_present_count"] == 0
    original_exists = patch.mcal._entry_exists
    historical_final = patch.HISTORICAL_PUBLISHED_LOCK_PATHS[0]
    assert original_exists(historical_final, repo_root=patch.PROJECT_ROOT)
    for forbidden in (
        patch.NEVER_PUBLISHED_LOCK_PATHS[0],
        patch.LOCK_TEMPORARY_PATHS[0],
    ):
        monkeypatch.setattr(
            patch.mcal,
            "_entry_exists",
            lambda path, *, repo_root, forbidden=forbidden: (
                True
                if path == forbidden
                else original_exists(path, repo_root=repo_root)
            ),
        )
        with pytest.raises(
            patch.FinalCalibrationR8CoordinationNamespaceRevalidationPatchError
        ):
            patch._require_coordination_namespace(
                repo_root=patch.PROJECT_ROOT,
                current_outputs_state="absent",
            )


def test_generic_findings_contract_is_exact_two_status_plus_two_script() -> None:
    findings = _finding_contract()
    assert [finding.level for finding in findings] == ["fail", "warn", "fail", "warn"]
    assert [finding.check for finding in findings] == ["manifest"] * 4
    assert len({finding.path for finding in findings}) == 2
    assert "completed_unpublished" in findings[0].message
    assert "terminal" in findings[2].message
    assert findings[1].message == findings[3].message


def test_exact_four_findings_are_adopted_without_mutating_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generic_ok = precommit.ReproducibilityFinding("ok", "manifest", "-", "covered")
    original = [generic_ok, *_finding_contract()]
    before = list(original)
    result = _adopt(monkeypatch, original)
    assert original == before
    assert result[0] == generic_ok
    assert len(result) == 2
    assert result[-1].level == "ok"
    assert result[-1].check == (
        "final_calibration_r8_coordination_namespace_revalidation"
    )


def test_non_exact_finding_multisets_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exact = list(_finding_contract())
    candidates = (
        exact[:-1],
        [*exact, precommit.ReproducibilityFinding("warn", "script", "x", "x")],
        [*exact, exact[0]],
        [replace(exact[0], message=exact[0].message + " drift"), *exact[1:]],
        [exact[0], replace(exact[1], level="ok"), *exact[2:]],
    )
    for candidate in candidates:
        result = _adopt(monkeypatch, list(candidate))
        assert result[-1].level == "fail"
        assert "exact four-finding multiset" in result[-1].message


def test_boundary_and_hash_validation_failures_are_not_adopted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for message in (
        "E0-MCALL scientific boundary drifted",
        "E0-MCALL immutable R8 output hash drifted",
    ):
        def fail(**kwargs: Any) -> dict[str, Any]:
            del kwargs
            raise patch.FinalCalibrationR8CoordinationNamespaceRevalidationPatchError(
                message
            )

        result = _adopt(
            monkeypatch,
            list(_finding_contract()),
            fake=_fake_patch(
                validate_final_calibration_r8_coordination_namespace_revalidation_adoption=fail
            ),
        )
        assert result[-1].level == "fail"
        assert message in result[-1].message

    released = False
    rollback_count = 0

    def acquire(*args: Any, **kwargs: Any) -> SimpleNamespace:
        del args, kwargs
        return SimpleNamespace(path="guard")

    def release(*args: Any, **kwargs: Any) -> None:
        nonlocal released
        del args, kwargs
        released = True

    def namespace(*, current_outputs_state: str, owned_guard: Any = None, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        if released and current_outputs_state == "present" and owned_guard is None:
            raise patch.FinalCalibrationR8CoordinationNamespaceRevalidationPatchError(
                "E0-MCALL predecessor MCALJ guard appeared after release"
            )
        return {"coordination_present_count": 0}

    def publish(path: Path, payload: bytes, *, repo_root: Path) -> SimpleNamespace:
        target = repo_root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return SimpleNamespace(path=path)

    def rollback(outputs: list[SimpleNamespace]) -> None:
        nonlocal rollback_count
        rollback_count = len(outputs)
        for output in outputs:
            (tmp_path / output.path).unlink(missing_ok=True)
        return None

    monkeypatch.setattr(patch, "_require_publication_verification", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        patch,
        "validate_final_calibration_r8_coordination_namespace_revalidation_patch_lock_payload",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(patch, "_physical_snapshot", lambda *args, **kwargs: ())
    monkeypatch.setattr(patch, "_require_physical_snapshot", lambda *args, **kwargs: None)
    monkeypatch.setattr(patch, "_require_repository_checkpoint", lambda *args, **kwargs: None)
    monkeypatch.setattr(patch, "_require_coordination_namespace", namespace)
    monkeypatch.setattr(patch.mcal, "_git_head", lambda *args, **kwargs: "h" * 40)
    monkeypatch.setattr(patch.mt, "_acquire_publication_guard", acquire)
    monkeypatch.setattr(patch.mt, "_release_publication_guard", release)
    monkeypatch.setattr(patch.mcalk, "_publish_bytes_no_clobber", publish)
    monkeypatch.setattr(patch.mcalk, "_rollback_outputs_best_effort", rollback)
    monkeypatch.setattr(patch, "_expected_companion", lambda *args, **kwargs: {"manifest_written_last": True})
    monkeypatch.setattr(
        patch.mcalk.mcalj,
        "_validate_owned_output_bytes",
        lambda *args, **kwargs: None,
    )
    payload = {"repository": {"h_patch_head": "h" * 40}}
    with pytest.raises(
        patch.FinalCalibrationR8CoordinationNamespaceRevalidationPatchError,
        match="predecessor MCALJ guard appeared after release",
    ):
        patch.publish_final_calibration_r8_coordination_namespace_revalidation_patch_lock_bundle(
            payload,
            repo_root=tmp_path,
        )
    assert rollback_count == 2
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_PATH).exists()
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).exists()


def test_strict_validation_summary_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value in (
        ("status", "wrong"),
        ("r8_output_count", 7),
        ("calibration_output_count", 5),
        ("e7_output_count", 1),
        ("coordination_forbidden_count", 45),
        ("coordination_present_count", 1),
        ("effective_p_mcall_verified", False),
        ("staged_scope_verified", False),
        ("scientific_rerun_performed", True),
        ("r8_rewrite_performed", True),
    ):
        result = _adopt(
            monkeypatch,
            list(_finding_contract()),
            fake=_fake_patch(
                validate_final_calibration_r8_coordination_namespace_revalidation_adoption=(
                    lambda key=key, value=value, **kwargs: {
                        **_validation(),
                        key: value,
                    }
                )
            ),
        )
        assert result[-1].level == "fail"
        assert "strict R8 adoption result drifted" in result[-1].message

    parse_count = 0
    namespace_count = 0

    def parse(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], bytes, object]:
        nonlocal parse_count
        del args, kwargs
        parse_count += 1
        value = {"repository": {"h_patch_head": "h" * 40}}
        if parse_count == 2:
            value = {"manifest_written_last": True}
        return value, b"{}\n", object()

    def namespace(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal namespace_count
        del args, kwargs
        namespace_count += 1
        if namespace_count == 2:
            raise patch.FinalCalibrationR8CoordinationNamespaceRevalidationPatchError(
                "E0-MCALL temporary appeared between loader snapshots"
            )
        return {"coordination_present_count": 0}

    monkeypatch.setattr(patch, "_parse_canonical_json_with_metadata", parse)
    monkeypatch.setattr(patch, "_validate_published_lock_payload", lambda *args, **kwargs: None)
    monkeypatch.setattr(patch, "_expected_companion", lambda *args, **kwargs: {"manifest_written_last": True})
    monkeypatch.setattr(patch.mcal, "_file_record", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        patch,
        "_validate_p_publication",
        lambda *args, **kwargs: {"p_patch_head": "p" * 40},
    )
    monkeypatch.setattr(patch, "_require_coordination_namespace", namespace)
    monkeypatch.setattr(patch.mcalk, "_validate_r8_bundle", lambda *args, **kwargs: {})
    monkeypatch.setattr(patch, "_physical_snapshot", lambda *args, **kwargs: ())
    with pytest.raises(
        patch.FinalCalibrationR8CoordinationNamespaceRevalidationPatchError,
        match="temporary appeared between loader snapshots",
    ):
        patch.load_effective_final_calibration_r8_coordination_namespace_revalidation_patch_authority(
            verify_remote=False,
            repo_root=Path("."),
        )


def test_wrapper_runs_generic_checks_unchanged_before_adoption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generic = list(_finding_contract())
    observed: dict[str, Any] = {}

    def generic_checks(**kwargs: Any) -> list[precommit.ReproducibilityFinding]:
        observed.update(kwargs)
        return generic

    monkeypatch.setattr(precommit, "reproducibility_checks", generic_checks)
    monkeypatch.setattr(
        precommit,
        "adopt_final_calibration_r8_coordination_namespace_revalidation_findings",
        lambda findings, **kwargs: [
            *findings,
            precommit.ReproducibilityFinding("ok", "adapter", "-", "ok"),
        ],
    )
    result = precommit.final_calibration_r8_coordination_namespace_revalidation_checks(
        staged_status=_staged(patch.R8_STAGED_SCOPE),
        selected_dvc_paths=[],
        artifacts=[],
        max_manifest_hash_bytes=123,
        verify_manifest_inputs=False,
    )
    assert result[:-1] == generic
    assert observed == {
        "staged_status": _staged(patch.R8_STAGED_SCOPE),
        "selected_dvc_paths": [],
        "artifacts": [],
        "max_manifest_hash_bytes": 123,
        "verify_manifest_inputs": False,
    }


def test_staged_and_workspace_scopes_reject_extra_missing_and_duplicate() -> None:
    staged = _staged(patch.R8_STAGED_SCOPE)
    workspace = _pre_stage(patch.R8_STAGED_SCOPE).replace("?? ", "A  ")
    precommit.validate_final_calibration_r8_coordination_namespace_revalidation_staged_scope(
        staged,
        gate="R-E0-MCALL",
    )
    precommit.validate_final_calibration_r8_coordination_namespace_revalidation_workspace_scope(
        workspace,
        gate="R-E0-MCALL",
    )
    for candidate in (
        staged + "A\textra.txt\n",
        "".join(staged.splitlines(keepends=True)[:-1]),
        staged + staged.splitlines(keepends=True)[0],
    ):
        with pytest.raises(
            precommit.FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError
        ):
            precommit.validate_final_calibration_r8_coordination_namespace_revalidation_staged_scope(
                candidate,
                gate="R-E0-MCALL",
            )
    for candidate in (
        workspace + "?? extra.txt\n",
        "".join(workspace.splitlines(keepends=True)[:-1]),
        workspace + workspace.splitlines(keepends=True)[0],
    ):
        with pytest.raises(
            precommit.FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError
        ):
            precommit.validate_final_calibration_r8_coordination_namespace_revalidation_workspace_scope(
                candidate,
                gate="R-E0-MCALL",
            )


def test_h_pre_stage_routes_only_h6_and_preserves_r8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _fake_patch()
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_coordination_namespace_revalidation_patch_module",
        lambda: fake,
    )
    monkeypatch.setattr(
        precommit,
        "_git_output",
        lambda *args: fake.BASE_H_MCALK_COMMIT + "\n",
    )
    exact = _pre_stage(fake.FINAL_CALIBRATION_H_STAGED_SCOPE, fake.R8_STAGED_SCOPE)
    result = precommit.final_calibration_r8_coordination_namespace_revalidation_pre_stage_scope(
        exact
    )
    assert result == (
        "H-E0-MCALL",
        tuple(sorted(fake.FINAL_CALIBRATION_H_STAGED_SCOPE)),
    )
    assert result is not None
    assert not set(result[1]) & set(fake.R8_STAGED_SCOPE)
    for drift in (
        exact + "?? extra.txt\n",
        exact + "malformed\n",
        exact + _pre_stage({next(iter(fake.R8_STAGED_SCOPE)): "A"}),
        exact.replace("?? ", " M", 1),
    ):
        with pytest.raises(
            precommit.FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError
        ):
            precommit.final_calibration_r8_coordination_namespace_revalidation_pre_stage_scope(
                drift
            )


def test_p_pre_stage_routes_only_p2_and_validates_companion_16_6_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def unpublished(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return _unpublished()

    fake = _fake_patch(
        validate_final_calibration_r8_coordination_namespace_revalidation_unpublished_lock_bundle=(
            unpublished
        )
    )
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_coordination_namespace_revalidation_patch_module",
        lambda: fake,
    )

    def git_output(repo_root: Path, *args: str) -> str:
        del repo_root
        if args == ("rev-parse", "HEAD"):
            return "h" * 40 + "\n"
        if args == ("rev-parse", "HEAD^"):
            return fake.BASE_H_MCALK_COMMIT + "\n"
        return _staged(fake.FINAL_CALIBRATION_H_STAGED_SCOPE)

    monkeypatch.setattr(precommit, "_git_output", git_output)
    result = precommit.final_calibration_r8_coordination_namespace_revalidation_pre_stage_scope(
        _pre_stage(fake.FINAL_CALIBRATION_P_STAGED_SCOPE, fake.R8_STAGED_SCOPE)
    )
    assert result == (
        "P-E0-MCALL",
        tuple(sorted(fake.FINAL_CALIBRATION_P_STAGED_SCOPE)),
    )
    assert calls == [{"repo_root": Path("."), "verify_remote": True}]
    for key, value in (
        ("historical_input_count", 5),
        ("coordination_forbidden_count", 45),
        ("coordination_present_count", 1),
        ("r8_outputs_sha256", "short"),
    ):
        monkeypatch.setattr(
            fake,
            "validate_final_calibration_r8_coordination_namespace_revalidation_unpublished_lock_bundle",
            lambda key=key, value=value, **kwargs: {
                **_unpublished(),
                key: value,
            },
        )
        with pytest.raises(
            precommit.FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError,
            match="semantic validation result drifted",
        ):
            precommit.final_calibration_r8_coordination_namespace_revalidation_pre_stage_scope(
                _pre_stage(
                    fake.FINAL_CALIBRATION_P_STAGED_SCOPE,
                    fake.R8_STAGED_SCOPE,
                )
            )


def test_r_pre_stage_requires_remote_effective_p_and_routes_exact8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def authority(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "gate": "E0-MCALL",
            "status": "effective",
            "coordination_namespace_revalidation": (
                patch.COORDINATION_NAMESPACE_CONTRACT
            ),
            "r_output_present_count": 8,
            "r_lifecycle_state": "both_bundles_completed_unpublished",
            "effective_authority": True,
            "r8_staging_authorized": True,
            "writes_performed": False,
        }

    fake = _fake_patch(
        require_final_calibration_r8_coordination_namespace_revalidation_patch_authority=authority
    )
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_coordination_namespace_revalidation_patch_module",
        lambda: fake,
    )
    monkeypatch.setattr(precommit, "_git_output", lambda *args: "p" * 40 + "\n")
    result = precommit.final_calibration_r8_coordination_namespace_revalidation_pre_stage_scope(
        _pre_stage(fake.R8_STAGED_SCOPE)
    )
    assert result == ("R-E0-MCALL", tuple(sorted(fake.R8_STAGED_SCOPE)))
    assert calls == [{"repo_root": Path("."), "verify_remote": True}]
    for drift in ("wrong", False, None, "namespace"):
        monkeypatch.setattr(
            fake,
            "require_final_calibration_r8_coordination_namespace_revalidation_patch_authority",
            lambda drift=drift, **kwargs: {
                "gate": "E0-MCALL",
                "status": drift if drift == "wrong" else "effective",
                "coordination_namespace_revalidation": (
                    {}
                    if drift == "namespace"
                    else patch.COORDINATION_NAMESPACE_CONTRACT
                ),
                "r_output_present_count": 8,
                "r_lifecycle_state": "both_bundles_completed_unpublished",
                "effective_authority": drift if drift is False else True,
                "r8_staging_authorized": (
                    drift if drift is False or drift is None else True
                ),
                "writes_performed": False,
            },
        )
        with pytest.raises(
            precommit.FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError
        ):
            precommit.final_calibration_r8_coordination_namespace_revalidation_pre_stage_scope(
                _pre_stage(fake.R8_STAGED_SCOPE)
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
    precommit.validate_final_calibration_r8_coordination_namespace_revalidation_invocation(
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
            precommit.FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError
        ):
            precommit.validate_final_calibration_r8_coordination_namespace_revalidation_invocation(
                candidate,
                env=env,
            )
    for changed_env in ({}, {**env, "DVC_BIN": "dvc"}):
        with pytest.raises(
            precommit.FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError
        ):
            precommit.validate_final_calibration_r8_coordination_namespace_revalidation_invocation(
                valid,
                env=changed_env,
            )


def test_snapshot_requires_exact8_regular_single_link_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _fake_patch()
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_coordination_namespace_revalidation_patch_module",
        lambda: fake,
    )
    inode = {record["path"]: index for index, record in enumerate(fake.R8_OUTPUT_CONTRACT)}
    physical = {record["path"]: dict(record) for record in fake.R8_OUTPUT_CONTRACT}

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
    first = precommit.snapshot_final_calibration_r8_coordination_namespace_outputs()
    assert len(first) == 8
    inode[first[0].path] += 100
    assert (
        precommit.snapshot_final_calibration_r8_coordination_namespace_outputs()
        != first
    )
    fake.R8_OUTPUT_CONTRACT = tuple(
        ({**record, "sha256": "0" * 64} if index == 0 else record)
        for index, record in enumerate(fake.R8_OUTPUT_CONTRACT)
    )
    with pytest.raises(
        precommit.FinalCalibrationR8CoordinationNamespaceRevalidationAdapterError,
        match="physical identity drifted",
    ):
        precommit.snapshot_final_calibration_r8_coordination_namespace_outputs()


def test_transaction_revalidates_p_semantics_and_r_remote_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def unpublished(**kwargs: Any) -> dict[str, Any]:
        calls.append(("p", kwargs))
        return _unpublished(stage_state="staged")

    def authority(**kwargs: Any) -> dict[str, Any]:
        calls.append(("r", kwargs))
        return {
            "gate": "E0-MCALL",
            "status": "effective",
            "coordination_namespace_revalidation": (
                patch.COORDINATION_NAMESPACE_CONTRACT
            ),
            "r_output_present_count": 8,
            "r_lifecycle_state": "both_bundles_completed_unpublished",
            "effective_authority": True,
            "r8_staging_authorized": True,
            "writes_performed": False,
        }

    def adoption(**kwargs: Any) -> dict[str, Any]:
        calls.append(("adopt", kwargs))
        return _validation(staged=bool(kwargs["require_staged"]))

    fake = _fake_patch(
        validate_final_calibration_r8_coordination_namespace_revalidation_unpublished_lock_bundle=unpublished,
        require_final_calibration_r8_coordination_namespace_revalidation_patch_authority=authority,
        validate_final_calibration_r8_coordination_namespace_revalidation_adoption=adoption,
    )
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_coordination_namespace_revalidation_patch_module",
        lambda: fake,
    )
    monkeypatch.setattr(
        precommit,
        "validate_final_calibration_r8_coordination_namespace_revalidation_staged_scope",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        precommit,
        "validate_final_calibration_r8_coordination_namespace_revalidation_workspace_scope",
        lambda *args, **kwargs: None,
    )
    snapshot = (precommit.FinalCalibrationR8PhysicalIdentity("x", 1, 1, 0o644, 1, 1, "x", 1, 1),)
    monkeypatch.setattr(
        precommit,
        "snapshot_final_calibration_r8_coordination_namespace_outputs",
        lambda **kwargs: snapshot,
    )
    monkeypatch.setattr(precommit, "_git_output", lambda *args: "scope\n")
    for gate in ("P-E0-MCALL", "R-E0-MCALL"):
        precommit.revalidate_final_calibration_r8_coordination_namespace_revalidation_transaction(
            gate=gate,
            staged_status="scope\n",
            expected_snapshot=snapshot,
        )
    assert ("p", {"repo_root": Path("."), "verify_remote": True}) in calls
    assert ("r", {"repo_root": Path("."), "verify_remote": True}) in calls
    assert ("adopt", {"repo_root": Path("."), "require_staged": False}) in calls
    assert ("adopt", {"repo_root": Path("."), "require_staged": True}) in calls


def test_main_routes_mcall_before_mcalk_with_directed_add_and_all_status() -> None:
    source = Path(precommit.__file__).read_text(encoding="utf-8")
    main = source[source.index("def main() -> int:") :]
    mcall = main.index(
        "final_calibration_r8_coordination_namespace_revalidation_pre_stage_scope("
    )
    mcalk = main.index(
        "final_calibration_r8_manifest_reproducibility_pre_stage_scope("
    )
    dvc = main.index("dvc_status_before = dvc_status_json(dvc_bin)")
    assert mcall < mcalk < dvc
    assert '"status", "--short", "--untracked-files=all"' in main
    assert '"git",\n                "add",\n                "-A",\n                "--",' in main
    assert "final_calibration_stage_gate and selected_dvc_paths" in main
    assert "deferred_dvc_paths or final_calibration_stage_gate" in main
    assert main.count(
        "revalidate_final_calibration_r8_coordination_namespace_revalidation_transaction("
    ) == 2


def test_only_single_mcall_error_prefix_is_exposed_at_adapter_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = patch.FinalCalibrationR8CoordinationNamespaceRevalidationPatchError(
        "E0-MCALL coordination namespace drifted"
    )
    fake = _fake_patch(
        validate_final_calibration_r8_coordination_namespace_revalidation_adoption=(
            lambda **kwargs: (_ for _ in ()).throw(error)
        )
    )
    result = _adopt(monkeypatch, list(_finding_contract()), fake=fake)
    assert result[-1].message.count("E0-MCALL") == 1
    assert "E0-MCALK" not in result[-1].message
    assert "E0-MCALJ" not in result[-1].message
