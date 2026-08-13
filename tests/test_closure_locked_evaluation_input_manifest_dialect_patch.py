from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.data import prepare_commit_artifacts as precommit
from src.experiments import (
    closure_locked_evaluation_input_manifest_dialect_patch as mid,
)


BASE_P_MIC = "707fbe92c7147d281c2a272178289e948a137b1b"
H_SCOPE = dict(precommit._LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_H_STAGED_SCOPE)
P_SCOPE = dict(precommit._LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_P_STAGED_SCOPE)
R_SCOPE = dict(precommit._LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_R_STAGED_SCOPE)
FINDING_RECORDS = tuple(dict(record) for record in mid.GENERIC_MANIFEST_FINDINGS_CONTRACT)
EXPECTED_FINDINGS = tuple(
    precommit.ReproducibilityFinding(**record) for record in FINDING_RECORDS
)


class FakePatchError(RuntimeError):
    pass


def _short(scope: dict[str, str], *, staged: bool = False) -> str:
    return "".join(
        f"{f'{status} ' if staged else '??' if status == 'A' else ' M'} {path}\n"
        for path, status in reversed(tuple(scope.items()))
    )


def _name_status(scope: dict[str, str]) -> str:
    return "".join(
        f"{status}\t{path}\n" for path, status in reversed(tuple(scope.items()))
    )


def _success_adoption(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "gate": "E0-MID",
        "r_gate": "R-E0-MID",
        "underlying_r_gate": "R-E0-MI",
        "status": "locked_evaluation_input_manifest_dialect_adoption_validated",
        "r_stage_state": "exact6_staged",
        "physical_output_count": 4,
        "tracked_output_count": 6,
        "pointer_count": 4,
        "summary_count": 1,
        "manifest_count": 1,
        "r_output_count": 10,
        "r_outputs_sha256": (
            "2b1e89ffa6816ad3bbaa8e1e8c5122b6b0b014dfc4645886443ffabe84036c17"
        ),
        "expected_non_ok_findings": [dict(record) for record in FINDING_RECORDS],
        "staged_scope_verified": True,
        "input_only": True,
        "target_paths_opened": False,
        "target_availability_inspected": False,
        "outcome_paths_opened": False,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "writes_performed": False,
    }
    value.update(overrides)
    return value


def _fake(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "PATCH_GATE": "E0-MID",
        "PATCH_COMPONENT_GIT_MODES": dict(
            precommit._LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_H_GIT_MODES
        ),
        "LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_H_STAGED_SCOPE": dict(H_SCOPE),
        "LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_P_STAGED_SCOPE": dict(P_SCOPE),
        "LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_R_STAGED_SCOPE": dict(R_SCOPE),
        "GENERIC_MANIFEST_FINDINGS_CONTRACT": tuple(
            dict(record) for record in FINDING_RECORDS
        ),
        "ClosureLockedEvaluationInputManifestDialectPatchError": FakePatchError,
        "validate_locked_evaluation_input_manifest_dialect_adoption": (
            lambda **kwargs: _success_adoption()
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _args(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "target": [],
        "no_push": True,
        "yes": False,
        "dry_run": False,
        "skip_publication_check": False,
        "jobs": None,
        "dvc_bin": None,
        "manifest": precommit.DEFAULT_DVC_MANIFEST,
        "report": None,
        "allow_unmanaged": True,
        "defer_dvc_target": [],
        "register_anfis_ablation_model_family": False,
        "verify_manifest_inputs": False,
        "max_manifest_hash_bytes": precommit.DEFAULT_MAX_MANIFEST_HASH_BYTES,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _adopt(
    monkeypatch: pytest.MonkeyPatch,
    findings: list[precommit.ReproducibilityFinding],
    *,
    patch: SimpleNamespace | None = None,
    staged_status: str | None = None,
) -> list[precommit.ReproducibilityFinding]:
    selected = _fake() if patch is None else patch
    monkeypatch.setattr(
        precommit,
        "_closure_locked_evaluation_input_manifest_dialect_patch_module",
        lambda: selected,
    )
    return precommit.adopt_closure_locked_evaluation_input_manifest_dialect_findings(
        findings,
        staged_status=_name_status(R_SCOPE) if staged_status is None else staged_status,
    )


def _assert_preserved_failure(
    original: list[precommit.ReproducibilityFinding],
    result: list[precommit.ReproducibilityFinding],
) -> None:
    assert result[:-1] == original
    assert result[-1].level == "fail"
    assert result[-1].check == "locked_evaluation_input_manifest_dialect"
    assert result[-1].path == "R-E0-MID"


def test_topology_is_exact_h6_p2_r6(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (len(H_SCOPE), len(P_SCOPE), len(R_SCOPE)) == (6, 2, 6)
    assert not set(H_SCOPE) & set(P_SCOPE)
    assert not set(H_SCOPE) & set(R_SCOPE)
    assert not set(P_SCOPE) & set(R_SCOPE)
    assert mid.PATCH_GATE == "E0-MID"
    assert mid.LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_H_STAGED_SCOPE == H_SCOPE
    assert mid.LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_P_STAGED_SCOPE == P_SCOPE
    assert mid.LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_R_STAGED_SCOPE == R_SCOPE
    assert mid.PATCH_COMPONENT_GIT_MODES == (
        precommit._LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_H_GIT_MODES
    )
    archive = mid._r_archive_metadata_snapshot(Path(".").resolve())
    assert archive == mid.ARCHIVED_R_IDENTITY_CONTRACT
    replaced: list[dict[str, Any]] = [
        dict(record) for record in mid.ARCHIVED_R_IDENTITY_CONTRACT
    ]
    replaced[0]["inode"] = int(replaced[0]["inode"]) + 1
    replacement_contract = tuple(replaced)
    monkeypatch.setattr(mid, "ARCHIVED_R_IDENTITY_CONTRACT", replacement_contract)
    monkeypatch.setattr(
        mid,
        "ARCHIVED_R_IDENTITY_SHA256",
        mid._sha256_bytes(mid._canonical_json_bytes(replacement_contract)),
    )
    with pytest.raises(
        mid.ClosureLockedEvaluationInputManifestDialectPatchError,
        match="archive exact identity contract drifted",
    ):
        mid._r_archive_metadata_snapshot(Path(".").resolve())


def test_selector_routes_h_before_mic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        precommit,
        "_closure_locked_evaluation_input_manifest_dialect_patch_module",
        _fake,
    )
    monkeypatch.setattr(
        precommit,
        "_require_closure_locked_evaluation_input_manifest_dialect_stage_base",
        lambda *args, **kwargs: None,
    )
    result = precommit.closure_locked_evaluation_input_manifest_dialect_pre_stage_scope(
        _short(H_SCOPE)
    )
    assert result == ("H-E0-MID", tuple(sorted(H_SCOPE)))


def test_selector_routes_p(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        precommit,
        "_closure_locked_evaluation_input_manifest_dialect_patch_module",
        _fake,
    )
    monkeypatch.setattr(
        precommit,
        "_require_closure_locked_evaluation_input_manifest_dialect_stage_base",
        lambda *args, **kwargs: None,
    )
    result = precommit.closure_locked_evaluation_input_manifest_dialect_pre_stage_scope(
        _short(P_SCOPE)
    )
    assert result == ("P-E0-MID", tuple(sorted(P_SCOPE)))


def test_selector_routes_restored_r6(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        precommit,
        "_closure_locked_evaluation_input_manifest_dialect_patch_module",
        _fake,
    )
    monkeypatch.setattr(
        precommit,
        "_require_closure_locked_evaluation_input_manifest_dialect_stage_base",
        lambda *args, **kwargs: None,
    )
    result = precommit.closure_locked_evaluation_input_manifest_dialect_pre_stage_scope(
        _short(R_SCOPE)
    )
    assert result == ("R-E0-MID", tuple(sorted(R_SCOPE)))


def test_selector_rejects_partial_extra_duplicate_and_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        precommit,
        "_closure_locked_evaluation_input_manifest_dialect_patch_module",
        _fake,
    )
    first = _short(H_SCOPE).splitlines(keepends=True)[0]
    for status in (
        first,
        _short(H_SCOPE) + "?? extra\n",
        _short(H_SCOPE) + first,
        _short(H_SCOPE) + "broken\n",
    ):
        with pytest.raises(
            precommit.ClosureLockedEvaluationInputManifestDialectAdapterError
        ):
            precommit.closure_locked_evaluation_input_manifest_dialect_pre_stage_scope(
                status
            )


def test_non_mid_status_remains_generic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        precommit,
        "_closure_locked_evaluation_input_manifest_dialect_patch_module",
        _fake,
    )
    assert (
        precommit.closure_locked_evaluation_input_manifest_dialect_pre_stage_scope(
            "?? unrelated\n"
        )
        is None
    )
    for predecessor in (
        {
            "coordination_present_count": 1,
            "formal_e0_m_output_present_count": 0,
            "outcome_access_log_absent": True,
        },
        {
            "coordination_present_count": 0,
            "formal_e0_m_output_present_count": 1,
            "outcome_access_log_absent": True,
        },
        {
            "coordination_present_count": 0,
            "formal_e0_m_output_present_count": 0,
            "outcome_access_log_absent": False,
        },
    ):
        monkeypatch.setattr(
            mid.mic,
            "_require_namespace",
            lambda **kwargs: dict(predecessor),
        )
        with pytest.raises(
            mid.ClosureLockedEvaluationInputManifestDialectPatchError,
            match="predecessor E0-M/outcome/coordination namespace drifted",
        ):
            mid._namespace_state(
                repo_root=tmp_path,
                p_present=False,
                r_present=False,
            )


def test_invocation_is_closed_and_adoption_only() -> None:
    env = {"DVC_NO_ANALYTICS": "1"}
    for gate in ("H-E0-MID", "P-E0-MID", "R-E0-MID"):
        precommit.validate_closure_locked_evaluation_input_manifest_dialect_invocation(
            _args(),
            gate=gate,
            env=env,
        )
    mutations = (
        {"target": ["data/closure_v1/locked_evaluation/input_history.parquet"]},
        {"no_push": False},
        {"yes": True},
        {"dry_run": True},
        {"skip_publication_check": True},
        {"jobs": "2"},
        {"dvc_bin": ".venv/bin/dvc"},
        {"manifest": Path("other.yaml")},
        {"report": Path("other.md")},
        {"allow_unmanaged": False},
        {"defer_dvc_target": ["models"]},
        {"register_anfis_ablation_model_family": True},
        {"verify_manifest_inputs": True},
        {"max_manifest_hash_bytes": 1},
    )
    for mutation in mutations:
        with pytest.raises(
            precommit.ClosureLockedEvaluationInputManifestDialectAdapterError
        ):
            precommit.validate_closure_locked_evaluation_input_manifest_dialect_invocation(
                _args(**mutation),
                gate="R-E0-MID",
                env=env,
            )
    for bad_env in ({}, {"DVC_NO_ANALYTICS": "1", "DVC_BIN": "dvc"}):
        with pytest.raises(
            precommit.ClosureLockedEvaluationInputManifestDialectAdapterError
        ):
            precommit.validate_closure_locked_evaluation_input_manifest_dialect_invocation(
                _args(),
                gate="R-E0-MID",
                env=bad_env,
            )


def test_staged_scope_and_bindings_are_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch = _fake()
    monkeypatch.setattr(
        precommit,
        "_closure_locked_evaluation_input_manifest_dialect_patch_module",
        lambda: patch,
    )
    precommit.validate_closure_locked_evaluation_input_manifest_dialect_staged_scope(
        _name_status(P_SCOPE),
        gate="P-E0-MID",
    )
    precommit.validate_closure_locked_evaluation_input_manifest_dialect_workspace_scope(
        _short(P_SCOPE, staged=True),
        gate="P-E0-MID",
    )
    oid = "a" * 40

    def git_output(repo_root: Path, *args: str) -> str:
        del repo_root
        path = args[-1]
        if args[0] == "ls-files":
            return f"100644 {oid} 0\t{path}\n"
        if args[0] == "hash-object":
            return f"{oid}\n"
        raise AssertionError(args)

    monkeypatch.setattr(precommit, "_git_output", git_output)
    monkeypatch.setattr(
        precommit,
        "_registration_file_identity",
        lambda path, **kwargs: precommit.RegistrationFileIdentity(
            path=path.as_posix(),
            device=1,
            inode=2,
            mode=0o644,
            nlink=1,
            size=3,
            sha256="b" * 64,
            mtime_ns=4,
            ctime_ns=5,
        ),
    )
    records = (
        precommit.validate_closure_locked_evaluation_input_manifest_dialect_staged_bindings(
            gate="P-E0-MID"
        )
    )
    assert len(records) == 2
    with pytest.raises(
        precommit.ClosureLockedEvaluationInputManifestDialectAdapterError
    ):
        precommit.validate_closure_locked_evaluation_input_manifest_dialect_staged_scope(
            _name_status({next(iter(P_SCOPE)): "A"}),
            gate="P-E0-MID",
        )


def test_generic_exact_three_are_adopted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, Any]] = []

    def validate(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return _success_adoption()

    patch = _fake(
        validate_locked_evaluation_input_manifest_dialect_adoption=validate
    )
    original = [
        precommit.ReproducibilityFinding("ok", "dvc", "-", "clean"),
        *EXPECTED_FINDINGS,
        precommit.ReproducibilityFinding("ok", "freeze", "-", "fresh"),
    ]
    before = list(original)
    result = _adopt(monkeypatch, original, patch=patch)
    assert original == before
    assert [(finding.level, finding.check) for finding in result] == [
        ("ok", "dvc"),
        ("ok", "freeze"),
        ("ok", "locked_evaluation_input_manifest_dialect"),
    ]
    assert calls == [
        {"repo_root": Path("."), "require_staged": True, "verify_remote": True}
    ]

    core_authority = {
        "r_adoption_authorized": True,
        "r_stage_state": "exact6_staged",
        "r_adoption_gate": mid.R_ADOPTION_GATE,
    }
    core_calls: list[tuple[bool, Path | None]] = []

    def core_require(
        *, verify_remote: bool = True, repo_root: Path | None = None
    ) -> dict[str, Any]:
        core_calls.append((verify_remote, repo_root))
        return dict(core_authority)

    monkeypatch.setattr(
        mid,
        "require_closure_locked_evaluation_input_manifest_dialect_patch_authority",
        core_require,
    )
    monkeypatch.setattr(mid, "_r_bundle_snapshot", lambda repo_root=None: ("stable",))
    monkeypatch.setattr(
        mid,
        "_validate_r_science",
        lambda *, repo_root: {"r_outputs_sha256": mid.R_OUTPUTS_SHA256},
    )
    direct = mid.validate_locked_evaluation_input_manifest_dialect_adoption(
        repo_root=tmp_path,
        require_staged=True,
        verify_remote=True,
    )
    assert direct["gate"] == "E0-MID"
    assert direct["r_gate"] == "R-E0-MID"
    assert direct["r_stage_state"] == "exact6_staged"
    assert direct["expected_non_ok_findings"] == list(FINDING_RECORDS)
    assert direct["writes_performed"] is False
    assert core_calls == [(True, tmp_path), (True, tmp_path)]


def test_missing_finding_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = list(EXPECTED_FINDINGS[:-1])
    _assert_preserved_failure(original, _adopt(monkeypatch, original))


def test_extra_finding_is_preserved_and_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = [
        *EXPECTED_FINDINGS,
        precommit.ReproducibilityFinding("warn", "script", "extra", "extra"),
    ]
    _assert_preserved_failure(original, _adopt(monkeypatch, original))


def test_duplicate_finding_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = [*EXPECTED_FINDINGS, EXPECTED_FINDINGS[0]]
    _assert_preserved_failure(original, _adopt(monkeypatch, original))


def test_message_severity_and_type_drift_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = [
        precommit.ReproducibilityFinding(
            expected.level,
            expected.check,
            expected.path,
            expected.message + " drift",
        )
        if index == 0
        else expected
        for index, expected in enumerate(EXPECTED_FINDINGS)
    ]
    severity = [
        precommit.ReproducibilityFinding(
            "warn",
            EXPECTED_FINDINGS[0].check,
            EXPECTED_FINDINGS[0].path,
            EXPECTED_FINDINGS[0].message,
        ),
        *EXPECTED_FINDINGS[1:],
    ]
    _assert_preserved_failure(message, _adopt(monkeypatch, message))
    _assert_preserved_failure(severity, _adopt(monkeypatch, severity))
    malformed = _fake(
        GENERIC_MANIFEST_FINDINGS_CONTRACT=(object(), *FINDING_RECORDS[1:])
    )
    original = list(EXPECTED_FINDINGS)
    _assert_preserved_failure(
        original,
        _adopt(monkeypatch, original, patch=malformed),
    )


def test_wrong_scope_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    patch = _fake(
        validate_locked_evaluation_input_manifest_dialect_adoption=(
            lambda **kwargs: calls.append(kwargs) or _success_adoption()
        )
    )
    original = list(EXPECTED_FINDINGS)
    result = _adopt(
        monkeypatch,
        original,
        patch=patch,
        staged_status=_name_status(P_SCOPE),
    )
    _assert_preserved_failure(original, result)
    assert calls == []


def test_strict_core_failure_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fail(**kwargs: Any) -> dict[str, Any]:
        del kwargs
        raise FakePatchError("strict MID validation failed")

    original = list(EXPECTED_FINDINGS)
    result = _adopt(
        monkeypatch,
        original,
        patch=_fake(validate_locked_evaluation_input_manifest_dialect_adoption=fail),
    )
    _assert_preserved_failure(original, result)
    assert result[-1].message == "strict MID validation failed"

    lock = {"repository": {"h_patch_head": "h" * 40}}
    companion = {"manifest_written_last": True}
    monkeypatch.setattr(
        mid,
        "_parse_canonical_json",
        lambda path, **kwargs: (
            lock if path == mid.DEFAULT_PATCH_LOCK_PATH else companion,
            b"{}\n",
            SimpleNamespace(),
        ),
    )
    monkeypatch.setattr(mid, "_validate_published_lock_payload", lambda *a, **k: None)
    monkeypatch.setattr(mid, "_expected_companion", lambda *a, **k: companion)
    publication = {
        "h_patch_head": "h" * 40,
        "p_patch_head": "p" * 40,
        "r_patch_head": None,
        "remote_head": "p" * 40,
        "r_state": "complete",
        "r_stage_state": "exact6_staged",
    }
    monkeypatch.setattr(mid, "_p_publication_state", lambda **kwargs: publication)
    monkeypatch.setattr(mid, "_p_pair_snapshot", lambda root: ("p",))
    monkeypatch.setattr(mid, "_physical_snapshot", lambda root: ("physical",))
    monkeypatch.setattr(mid, "_require_physical_snapshot", lambda *a, **k: None)
    monkeypatch.setattr(
        mid.mic.mcalm.mcall.mcalk.mcalj,
        "_metadata_identity",
        lambda metadata: ("stable",),
    )
    r_snapshots = iter((("sealed-r10",), ("tampered-r10",)))
    monkeypatch.setattr(mid, "_r_bundle_snapshot", lambda root=None: next(r_snapshots))
    with pytest.raises(
        mid.ClosureLockedEvaluationInputManifestDialectPatchError,
        match="R bundle changed during effective authority loading",
    ):
        mid.load_effective_closure_locked_evaluation_input_manifest_dialect_patch_authority(
            repo_root=tmp_path,
            verify_remote=True,
        )


def test_main_routing_has_no_dvc_add_for_mid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = inspect.getsource(precommit.main)
    mid_selector = source.index(
        "closure_locked_evaluation_input_manifest_dialect_pre_stage_scope"
    )
    mic_selector = source.index(
        "closure_locked_evaluation_input_panel_dvc_identity_pre_stage_scope"
    )
    assert mid_selector < mic_selector
    assert 'mib_r_gate = final_calibration_stage_gate == "R-E0-MI"' in source
    assert 'final_calibration_stage_gate == "R-E0-MID"' in source
    assert "validate_closure_locked_evaluation_input_manifest_dialect_invocation" in source
    assert "closure_locked_evaluation_input_manifest_dialect_checks" in source
    assert "revalidate_closure_locked_evaluation_input_manifest_dialect_transaction" in source
    assert "git_add_command = [" in source
    assert "*final_calibration_stage_paths" in source

    released = False
    rollback_count = 0
    namespace_calls: list[tuple[bool, bool, bool]] = []
    publication_order: list[Path] = []

    def acquire(*args: Any, **kwargs: Any) -> SimpleNamespace:
        del args, kwargs
        return SimpleNamespace(path="owned-mid-guard")

    def release(*args: Any, **kwargs: Any) -> None:
        nonlocal released
        del args, kwargs
        released = True

    def namespace(
        *,
        p_present: bool,
        r_present: bool,
        owned_lock_guard: Any | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        del kwargs
        namespace_calls.append(
            (p_present, r_present, owned_lock_guard is not None)
        )
        if released and p_present and owned_lock_guard is None:
            raise mid.ClosureLockedEvaluationInputManifestDialectPatchError(
                "E0-MID predecessor guard appeared after release"
            )
        return {"coordination_present_count": 0}

    def publish(path: Path, payload: bytes, *, repo_root: Path) -> SimpleNamespace:
        target = repo_root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        publication_order.append(path)
        return SimpleNamespace(path=path)

    def rollback(outputs: list[SimpleNamespace]) -> None:
        nonlocal rollback_count
        rollback_count = len(outputs)
        for output in outputs:
            (tmp_path / output.path).unlink(missing_ok=True)
        return None

    monkeypatch.setattr(mid, "_git_head", lambda *args, **kwargs: "h" * 40)
    monkeypatch.setattr(
        mid,
        "validate_closure_locked_evaluation_input_manifest_dialect_patch_lock_payload",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(mid, "_require_publication_verification", lambda *a, **k: None)
    monkeypatch.setattr(mid, "_require_repository_checkpoint", lambda **kwargs: None)
    monkeypatch.setattr(mid, "_namespace_state", namespace)
    monkeypatch.setattr(mid, "_r_archive_metadata_snapshot", lambda root=None: ())
    monkeypatch.setattr(mid, "_physical_snapshot", lambda root=None: ())
    monkeypatch.setattr(mid, "_require_physical_snapshot", lambda *a, **k: None)
    monkeypatch.setattr(mid.mt, "_acquire_publication_guard", acquire)
    monkeypatch.setattr(mid.mt, "_release_publication_guard", release)
    monkeypatch.setattr(
        mid.mic.mcalm.mcall.mcalk,
        "_publish_bytes_no_clobber",
        publish,
    )
    monkeypatch.setattr(
        mid.mic.mcalm.mcall.mcalk,
        "_rollback_outputs_best_effort",
        rollback,
    )
    monkeypatch.setattr(
        mid.mic.mcalm.mcall.mcalk.mcalj,
        "_validate_owned_output_bytes",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        mid,
        "_expected_companion",
        lambda *args, **kwargs: {"manifest_written_last": True},
    )
    with pytest.raises(
        mid.ClosureLockedEvaluationInputManifestDialectPatchError,
        match="predecessor guard appeared after release",
    ):
        mid.publish_closure_locked_evaluation_input_manifest_dialect_patch_lock_bundle(
            {"repository": {"h_patch_head": "h" * 40}},
            repo_root=tmp_path,
        )
    assert publication_order == [
        mid.DEFAULT_PATCH_LOCK_PATH,
        mid.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
    ]
    assert namespace_calls[:3] == [
        (False, False, False),
        (False, False, True),
        (True, False, True),
    ]
    assert namespace_calls[-1] == (True, False, False)
    assert rollback_count == 2
    assert not (tmp_path / mid.DEFAULT_PATCH_LOCK_PATH).exists()
    assert not (tmp_path / mid.DEFAULT_PATCH_LOCK_MANIFEST_PATH).exists()
