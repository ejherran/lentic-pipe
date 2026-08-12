from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from src.data import prepare_commit_artifacts as precommit
from src.experiments import (
    closure_final_calibration_r8_manifest_reproducibility_patch as patch,
)


def _finding_contract() -> tuple[precommit.ReproducibilityFinding, ...]:
    return tuple(
        precommit.ReproducibilityFinding(**record)
        for record in patch.GENERIC_MANIFEST_FINDINGS_CONTRACT
    )


def _validation() -> dict[str, Any]:
    return {
        "gate": "E0-MCALK",
        "status": "r8_manifest_reproducibility_adoption_validated",
        "r8_output_count": 8,
        "calibration_output_count": 6,
        "e7_output_count": 2,
        "r_lifecycle_state": "both_bundles_completed_unpublished",
        "r8_outputs": list(patch.R8_OUTPUT_CONTRACT),
        "expected_non_ok_findings": list(patch.GENERIC_MANIFEST_FINDINGS_CONTRACT),
        "staged_scope_verified": True,
        "scientific_rerun_performed": False,
        "r8_rewrite_performed": False,
    }


def _fake_patch(**overrides: Any) -> SimpleNamespace:
    def unpublished(**kwargs: Any) -> dict[str, Any]:
        del kwargs
        return {
            "gate": "E0-MCALK",
            "status": "unpublished_p_mcalk_lock_bundle_validated",
            "p_stage_state": "untracked",
            "p_output_count": 2,
            "physical_input_count": 16,
            "historical_input_count": 1,
            "companion_output_count": 1,
            "r8_output_count": 8,
            "r8_staging_authorized": False,
            "effective_authority": False,
            "scientific_rerun_authorized": False,
            "writes_performed": False,
        }

    values: dict[str, Any] = {
        "PATCH_GATE": patch.PATCH_GATE,
        "BASE_P_MCALJ_COMMIT": patch.BASE_P_MCALJ_COMMIT,
        "FINAL_CALIBRATION_H_STAGED_SCOPE": patch.FINAL_CALIBRATION_H_STAGED_SCOPE,
        "FINAL_CALIBRATION_P_STAGED_SCOPE": patch.FINAL_CALIBRATION_P_STAGED_SCOPE,
        "R8_STAGED_SCOPE": patch.R8_STAGED_SCOPE,
        "R8_OUTPUT_CONTRACT": patch.R8_OUTPUT_CONTRACT,
        "GENERIC_MANIFEST_FINDINGS_CONTRACT": (
            patch.GENERIC_MANIFEST_FINDINGS_CONTRACT
        ),
        "FinalCalibrationR8ManifestReproducibilityPatchError": (
            patch.FinalCalibrationR8ManifestReproducibilityPatchError
        ),
        "validate_final_calibration_r8_manifest_reproducibility_adoption": (
            lambda **kwargs: _validation()
        ),
        "validate_final_calibration_r8_manifest_reproducibility_unpublished_lock_bundle": (
            unpublished
        ),
        "require_final_calibration_r8_manifest_reproducibility_patch_authority": (
            lambda **kwargs: {
                "gate": "E0-MCALK",
                "r8_staging_authorized": True,
            }
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _staged(scope: dict[str, str]) -> str:
    return "".join(f"{status}\t{path}\n" for path, status in reversed(tuple(scope.items())))


def _pre_stage(*scopes: dict[str, str]) -> str:
    merged: dict[str, str] = {}
    for scope in scopes:
        merged.update(
            {path: "??" if status == "A" else " M" for path, status in scope.items()}
        )
    return "".join(f"{status} {path}\n" for path, status in reversed(tuple(merged.items())))


def _adopt(
    monkeypatch: pytest.MonkeyPatch,
    findings: list[precommit.ReproducibilityFinding],
    *,
    fake: SimpleNamespace | None = None,
) -> list[precommit.ReproducibilityFinding]:
    selected = fake or _fake_patch()
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_manifest_reproducibility_patch_module",
        lambda: selected,
    )
    return precommit.adopt_final_calibration_r8_manifest_reproducibility_findings(
        findings,
        staged_status=_staged(patch.R8_STAGED_SCOPE),
    )


def test_mcalk_precommit_scopes_are_exact() -> None:
    assert patch.PATCH_GATE == "E0-MCALK"
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


def test_generic_manifest_findings_contract_is_exact_two_plus_two() -> None:
    findings = _finding_contract()
    assert [finding.level for finding in findings] == ["fail", "warn", "fail", "warn"]
    assert [finding.path for finding in findings] == [
        patch.CALIBRATION_MANIFEST_PATH.as_posix(),
        patch.CALIBRATION_MANIFEST_PATH.as_posix(),
        patch.E7_MANIFEST_PATH.as_posix(),
        patch.E7_MANIFEST_PATH.as_posix(),
    ]
    assert "completed_unpublished" in findings[0].message
    assert "terminal" in findings[2].message
    assert findings[1].message == findings[3].message


def test_exact_four_findings_are_adopted_without_mutating_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generic_ok = precommit.ReproducibilityFinding("ok", "manifest", "-", "covered")
    original = [generic_ok, *_finding_contract()]
    snapshot = list(original)
    result = _adopt(monkeypatch, original)
    assert original == snapshot
    assert result[0] == generic_ok
    assert len(result) == 2
    assert result[-1].level == "ok"
    assert result[-1].check == "final_calibration_r8_manifest_reproducibility"


def test_missing_generic_finding_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _adopt(monkeypatch, list(_finding_contract()[:-1]))
    assert result[-1].level == "fail"
    assert "exact four-finding multiset" in result[-1].message


def test_extra_non_ok_generic_finding_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extra = precommit.ReproducibilityFinding("warn", "manifest", "other", "extra")
    result = _adopt(monkeypatch, [*_finding_contract(), extra])
    assert result[-1].level == "fail"
    assert extra in result


def test_duplicate_generic_finding_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    findings = list(_finding_contract())
    result = _adopt(monkeypatch, [*findings, findings[0]])
    assert result[-1].level == "fail"


def test_changed_status_finding_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    findings = list(_finding_contract())
    findings[0] = replace(findings[0], message=findings[0].message + " drift")
    assert _adopt(monkeypatch, findings)[-1].level == "fail"


def test_changed_script_warning_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    findings = list(_finding_contract())
    findings[1] = replace(findings[1], level="ok")
    assert _adopt(monkeypatch, findings)[-1].level == "fail"


def test_boundary_validation_failure_is_not_adopted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(**kwargs: Any) -> dict[str, Any]:
        del kwargs
        raise patch.FinalCalibrationR8ManifestReproducibilityPatchError(
            "E0-MCALK scientific boundary drifted"
        )

    result = _adopt(monkeypatch, list(_finding_contract()), fake=_fake_patch(
        validate_final_calibration_r8_manifest_reproducibility_adoption=fail
    ))
    assert result[-1].level == "fail"
    assert "scientific boundary drifted" in result[-1].message


def test_hash_validation_failure_is_not_adopted(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(**kwargs: Any) -> dict[str, Any]:
        del kwargs
        raise patch.FinalCalibrationR8ManifestReproducibilityPatchError(
            "E0-MCALK immutable R8 output drifted: synthetic"
        )

    result = _adopt(monkeypatch, list(_finding_contract()), fake=_fake_patch(
        validate_final_calibration_r8_manifest_reproducibility_adoption=fail
    ))
    assert result[-1].level == "fail"
    assert "immutable R8 output drifted" in result[-1].message
    original_read = patch.mcal._read_regular_bytes_and_metadata
    replaced_path = Path(cast(str, patch.R8_OUTPUT_CONTRACT[0]["path"]))

    def replacement(path: Path, **kwargs: Any) -> tuple[bytes, Any]:
        payload, metadata = original_read(path, **kwargs)
        if path == replaced_path:
            return b"stable replacement after validation", metadata
        return payload, metadata

    monkeypatch.setattr(
        patch.mcal, "_read_regular_bytes_and_metadata", replacement
    )
    with pytest.raises(
        patch.FinalCalibrationR8ManifestReproducibilityPatchError,
        match="immutable R8 snapshot drifted",
    ):
        patch._physical_snapshot(Path("."))


def test_strict_validation_summary_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _adopt(
        monkeypatch,
        list(_finding_contract()),
        fake=_fake_patch(
            validate_final_calibration_r8_manifest_reproducibility_adoption=(
                lambda **kwargs: {**_validation(), "r8_output_count": 7}
            )
        ),
    )
    assert result[-1].level == "fail"
    assert "strict R8 adoption result drifted" in result[-1].message


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
        "adopt_final_calibration_r8_manifest_reproducibility_findings",
        lambda findings, **kwargs: [*findings, precommit.ReproducibilityFinding("ok", "adapter", "-", "ok")],
    )
    result = precommit.final_calibration_r8_manifest_reproducibility_checks(
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


def test_staged_scope_rejects_extra_missing_and_duplicate_paths() -> None:
    exact = _staged(patch.R8_STAGED_SCOPE)
    precommit.validate_final_calibration_r8_manifest_reproducibility_staged_scope(
        exact, gate="R-E0-MCALK"
    )
    malformed = (
        exact + "A\textra.txt\n",
        "".join(exact.splitlines(keepends=True)[:-1]),
        exact + exact.splitlines(keepends=True)[0],
    )
    for candidate in malformed:
        with pytest.raises(
            precommit.FinalCalibrationR8ManifestReproducibilityAdapterError
        ):
            precommit.validate_final_calibration_r8_manifest_reproducibility_staged_scope(
                candidate, gate="R-E0-MCALK"
            )


def test_h_pre_stage_routes_only_h6_and_preserves_r8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _fake_patch()
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_manifest_reproducibility_patch_module",
        lambda: fake,
    )
    monkeypatch.setattr(precommit, "_git_output", lambda *args: fake.BASE_P_MCALJ_COMMIT + "\n")
    result = precommit.final_calibration_r8_manifest_reproducibility_pre_stage_scope(
        _pre_stage(fake.FINAL_CALIBRATION_H_STAGED_SCOPE, fake.R8_STAGED_SCOPE)
    )
    assert result is not None
    assert result == ("H-E0-MCALK", tuple(sorted(fake.FINAL_CALIBRATION_H_STAGED_SCOPE)))
    assert not set(result[1]) & set(fake.R8_STAGED_SCOPE)
    for drift in (
        _pre_stage(fake.FINAL_CALIBRATION_H_STAGED_SCOPE, fake.R8_STAGED_SCOPE)
        + "?? extra.txt\n",
        _pre_stage(fake.FINAL_CALIBRATION_H_STAGED_SCOPE, fake.R8_STAGED_SCOPE)
        + "malformed\n",
        _pre_stage(fake.FINAL_CALIBRATION_H_STAGED_SCOPE, fake.R8_STAGED_SCOPE)
        + _pre_stage({next(iter(fake.R8_STAGED_SCOPE)): "A"}),
    ):
        with pytest.raises(
            precommit.FinalCalibrationR8ManifestReproducibilityAdapterError
        ):
            precommit.final_calibration_r8_manifest_reproducibility_pre_stage_scope(
                drift
            )


def test_p_pre_stage_routes_only_p2_and_reconstructs_h(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validation_calls: list[dict[str, Any]] = []

    def unpublished(**kwargs: Any) -> dict[str, Any]:
        validation_calls.append(kwargs)
        return {
            "gate": "E0-MCALK",
            "status": "unpublished_p_mcalk_lock_bundle_validated",
            "p_stage_state": "untracked",
            "p_output_count": 2,
            "physical_input_count": 16,
            "historical_input_count": 1,
            "companion_output_count": 1,
            "r8_output_count": 8,
            "r8_staging_authorized": False,
            "effective_authority": False,
            "scientific_rerun_authorized": False,
            "writes_performed": False,
        }

    fake = _fake_patch(
        validate_final_calibration_r8_manifest_reproducibility_unpublished_lock_bundle=(
            unpublished
        )
    )
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_manifest_reproducibility_patch_module",
        lambda: fake,
    )

    def git_output(repo_root: Path, *args: str) -> str:
        del repo_root
        if args == ("rev-parse", "HEAD"):
            return "h" * 40 + "\n"
        if args == ("rev-parse", "HEAD^"):
            return fake.BASE_P_MCALJ_COMMIT + "\n"
        return _staged(fake.FINAL_CALIBRATION_H_STAGED_SCOPE)

    monkeypatch.setattr(precommit, "_git_output", git_output)
    result = precommit.final_calibration_r8_manifest_reproducibility_pre_stage_scope(
        _pre_stage(fake.FINAL_CALIBRATION_P_STAGED_SCOPE, fake.R8_STAGED_SCOPE)
    )
    assert result == ("P-E0-MCALK", tuple(sorted(fake.FINAL_CALIBRATION_P_STAGED_SCOPE)))
    assert validation_calls == [{"repo_root": Path("."), "verify_remote": True}]

    def coordinated_drift(**kwargs: Any) -> dict[str, Any]:
        del kwargs
        raise patch.FinalCalibrationR8ManifestReproducibilityPatchError(
            "E0-MCALK unpublished P companion drifted after coordinated lock rehash"
        )

    monkeypatch.setattr(
        fake,
        "validate_final_calibration_r8_manifest_reproducibility_unpublished_lock_bundle",
        coordinated_drift,
    )
    with pytest.raises(
        precommit.FinalCalibrationR8ManifestReproducibilityAdapterError,
        match="unpublished P companion drifted",
    ):
        precommit.final_calibration_r8_manifest_reproducibility_pre_stage_scope(
            _pre_stage(fake.FINAL_CALIBRATION_P_STAGED_SCOPE, fake.R8_STAGED_SCOPE)
        )


def test_r_pre_stage_requires_effective_p_and_routes_exact8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def authority(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"gate": "E0-MCALK", "r8_staging_authorized": True}

    fake = _fake_patch(
        require_final_calibration_r8_manifest_reproducibility_patch_authority=authority
    )
    monkeypatch.setattr(
        precommit,
        "_final_calibration_r8_manifest_reproducibility_patch_module",
        lambda: fake,
    )
    monkeypatch.setattr(precommit, "_git_output", lambda *args: "p" * 40 + "\n")
    result = precommit.final_calibration_r8_manifest_reproducibility_pre_stage_scope(
        _pre_stage(fake.R8_STAGED_SCOPE)
    )
    assert result == ("R-E0-MCALK", tuple(sorted(fake.R8_STAGED_SCOPE)))
    assert calls == [{"repo_root": Path("."), "verify_remote": True}]
    valid_args = SimpleNamespace(
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
    valid_env = {"DVC_NO_ANALYTICS": "1"}
    precommit.validate_final_calibration_r8_manifest_reproducibility_invocation(
        valid_args, env=valid_env
    )
    mutations = {
        "no_push": False,
        "yes": True,
        "dry_run": True,
        "skip_publication_check": True,
        "jobs": "1",
        "dvc_bin": "custom-dvc",
        "manifest": Path("custom.yaml"),
        "report": Path("custom.md"),
        "allow_unmanaged": False,
        "target": ["models"],
        "defer_dvc_target": ["models"],
        "register_anfis_ablation_model_family": True,
        "verify_manifest_inputs": True,
        "max_manifest_hash_bytes": 1,
    }
    for name, value in mutations.items():
        candidate = SimpleNamespace(**vars(valid_args))
        setattr(candidate, name, value)
        with pytest.raises(
            precommit.FinalCalibrationR8ManifestReproducibilityAdapterError
        ):
            precommit.validate_final_calibration_r8_manifest_reproducibility_invocation(
                candidate, env=valid_env
            )
    for env in ({}, {**valid_env, "DVC_BIN": "dvc"}, {
        **valid_env, "DVC_SITE_CACHE_DIR": "custom-cache"
    }):
        with pytest.raises(
            precommit.FinalCalibrationR8ManifestReproducibilityAdapterError
        ):
            precommit.validate_final_calibration_r8_manifest_reproducibility_invocation(
                valid_args, env=env
            )
    main_source = Path(precommit.__file__).read_text(encoding="utf-8")
    main_body = main_source[main_source.index("def main() -> int:") :]
    helper_call = main_body.index(
        "validate_final_calibration_r8_manifest_reproducibility_invocation("
    )
    dvc_call = main_body.index("dvc_status_before = dvc_status_json(dvc_bin)")
    assert helper_call < dvc_call
    selected_guard = main_source[
        main_source.index("selected_dvc_paths = unique_paths") :
        main_source.index("if changed_for_add and not args.yes")
    ]
    assert "final_calibration_stage_gate and selected_dvc_paths" in selected_guard
    discovery_guard = main_source[
        main_source.index("if final_calibration_stage_gate and (") :
        main_source.index("deferred_final_snapshot:")
    ]
    assert "unmanaged_paths" not in discovery_guard
    assert "rejected_unmanaged.append(path)" in main_source
