from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.data import prepare_commit_artifacts as precommit


BASE_R_MI = "53947df3b826ee10be8cf3b137bae913bc73d2bb"
H_SCOPE = dict(precommit._FORMAL_MODEL_LOCK_H_STAGED_SCOPE)
P_SCOPE = dict(precommit._FORMAL_MODEL_LOCK_P_STAGED_SCOPE)
R_SCOPE = dict(precommit._FORMAL_MODEL_LOCK_R_STAGED_SCOPE)


class FakePatchError(RuntimeError):
    pass


def _short(scope: dict[str, str], *, staged: bool = False) -> str:
    return "".join(
        f"{f'{state} ' if staged else '??' if state == 'A' else ' M'} {path}\n"
        for path, state in reversed(tuple(scope.items()))
    )


def _name_status(scope: dict[str, str]) -> str:
    return "".join(
        f"{state}\t{path}\n" for path, state in reversed(tuple(scope.items()))
    )


def _prelock(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "gate": "E0-M",
        "status": "formal_model_lock_infrastructure_incomplete",
        "runner_readiness": {
            "status": "sealed_batch_runner_incomplete",
            "missing_component_count": 11,
            "formal_model_lock_ready": False,
        },
        "formal_model_lock_ready": False,
        "missing_component_count": 11,
        "p_authority_generation_authorized": False,
        "formal_output_count": 0,
        "outcome_access_log_state": "absent",
        "writes_performed": False,
    }
    value.update(overrides)
    return value


def _unpublished(*, staged: bool = False, **overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "gate": "E0-M",
        "status": "locked_unpublished",
        "p_stage_state": "staged" if staged else "untracked",
        "effective_authority": False,
        "formal_lock_execution_authorized": False,
        "writes_performed": False,
    }
    value.update(overrides)
    return value


def _effective(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "gate": "E0-M",
        "status": "effective",
        "p_stage_state": "published",
        "r_state": "absent",
        "r_stage_state": "absent",
        "formal_lock_execution_authorized": True,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "outcome_access_authorized": False,
        "writes_performed": False,
    }
    value.update(overrides)
    return value


def _bundle(*, staged: bool = False, **overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "gate": "E0-M",
        "status": "formal_model_lock_validated",
        "r_stage_state": "exact5_staged" if staged else "exact5_untracked",
        "e0_m_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "outcome_access_authorized": False,
        "outcome_access_log_state": "present_empty",
        "outcome_access_log_record_count": 0,
        "writes_performed": False,
    }
    value.update(overrides)
    return value


def _fake(**overrides: Any) -> SimpleNamespace:
    physical = ("physical",)
    values: dict[str, Any] = {
        "PATCH_GATE": "E0-M",
        "H_GATE": "H-E0-M",
        "P_GATE": "P-E0-M",
        "R_GATE": "R-E0-M",
        "PATCH_PATHS": tuple(sorted(H_SCOPE)),
        "FORMAL_MODEL_LOCK_H_STAGED_SCOPE": dict(H_SCOPE),
        "FORMAL_MODEL_LOCK_P_STAGED_SCOPE": dict(P_SCOPE),
        "FORMAL_MODEL_LOCK_R_STAGED_SCOPE": dict(R_SCOPE),
        "FINAL_CALIBRATION_H_STAGED_SCOPE": dict(H_SCOPE),
        "FINAL_CALIBRATION_P_STAGED_SCOPE": dict(P_SCOPE),
        "FINAL_CALIBRATION_R_STAGED_SCOPE": dict(R_SCOPE),
        "DEFAULT_SCHEMA_PATH": Path("configs/closure_v1/formal_model_lock.schema.json"),
        "DEFAULT_AUTHORITY_PATH": Path(
            "configs/closure_v1/formal_model_lock_authority.json"
        ),
        "DEFAULT_AUTHORITY_MANIFEST_PATH": Path(
            "configs/closure_v1/formal_model_lock_authority_manifest.json"
        ),
        "MODEL_LOCK_PATH": Path("reports/closure_v1/00_protocol/model_lock.yaml"),
        "CALIBRATION_LOCK_PATH": Path(
            "reports/closure_v1/00_protocol/calibration_lock.yaml"
        ),
        "HYPOTHESIS_REGISTRY_PATH": Path(
            "reports/closure_v1/00_protocol/hypothesis_registry.csv"
        ),
        "LOCKED_BATCH_COMMAND_PATH": Path(
            "reports/closure_v1/00_protocol/locked_batch_command.txt"
        ),
        "OUTCOME_ACCESS_LOG_PATH": Path(
            "reports/closure_v1/00_protocol/outcome_access_log.jsonl"
        ),
        "ClosureFormalModelLockError": FakePatchError,
        "_physical_snapshot": lambda **kwargs: physical,
        "collect_formal_model_lock_prelock_state": lambda **kwargs: _prelock(),
        "validate_formal_model_lock_unpublished_authority_bundle": (
            lambda require_staged=False, **kwargs: _unpublished(staged=require_staged)
        ),
        "require_formal_model_lock_authority": lambda **kwargs: _effective(),
        "validate_formal_model_lock_bundle": (
            lambda require_staged=True, **kwargs: _bundle(staged=require_staged)
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


def test_topology_is_exact_h7_p2_r5() -> None:
    from src.experiments import closure_formal_model_lock as core
    from src.experiments import run_closure_benchmark as runner

    assert (len(H_SCOPE), len(P_SCOPE), len(R_SCOPE)) == (7, 2, 5)
    assert not set(H_SCOPE) & set(P_SCOPE)
    assert not set(H_SCOPE) & set(R_SCOPE)
    assert not set(P_SCOPE) & set(R_SCOPE)
    assert H_SCOPE["src/data/prepare_commit_artifacts.py"] == "M"
    assert H_SCOPE["src/experiments/run_closure_benchmark.py"] == "A"
    assert tuple(sorted(R_SCOPE)) == (
        "reports/closure_v1/00_protocol/calibration_lock.yaml",
        "reports/closure_v1/00_protocol/hypothesis_registry.csv",
        "reports/closure_v1/00_protocol/locked_batch_command.txt",
        "reports/closure_v1/00_protocol/model_lock.yaml",
        "reports/closure_v1/00_protocol/outcome_access_log.jsonl",
    )
    assert core.PATCH_PATHS == tuple(sorted(H_SCOPE))
    assert core.FORMAL_MODEL_LOCK_H_STAGED_SCOPE == H_SCOPE
    assert core.FORMAL_MODEL_LOCK_P_STAGED_SCOPE == P_SCOPE
    assert core.FORMAL_MODEL_LOCK_R_STAGED_SCOPE == R_SCOPE
    assert core.FINAL_CALIBRATION_H_STAGED_SCOPE == H_SCOPE
    assert core.FINAL_CALIBRATION_P_STAGED_SCOPE == P_SCOPE
    assert core.FINAL_CALIBRATION_R_STAGED_SCOPE == R_SCOPE
    assert precommit._closure_formal_model_lock_scopes(core) == (
        H_SCOPE,
        P_SCOPE,
        R_SCOPE,
    )
    prelock = core.collect_formal_model_lock_prelock_state(verify_remote=False)
    assert prelock["status"] == "formal_model_lock_infrastructure_incomplete"
    assert prelock["runner_readiness"]["status"] == (
        "sealed_batch_runner_incomplete"
    )
    assert prelock["missing_component_count"] == 11
    assert prelock["formal_model_lock_ready"] is False
    assert prelock["p_authority_generation_authorized"] is False
    assert prelock["formal_output_count"] == 0
    assert prelock["outcome_access_log_state"] == "absent"
    assert prelock["target_paths_opened"] is False
    assert prelock["outcome_paths_opened"] is False
    assert prelock["future_outcomes_accessed"] is False
    assert prelock["writes_performed"] is False
    incomplete = _prelock()
    with pytest.raises(
        core.ClosureFormalModelLockError, match="exact11 missing"
    ):
        core.build_formal_model_lock_authority_payload(incomplete)
    for blocked in (
        core.validate_formal_model_lock_unpublished_authority_bundle,
        core.load_effective_formal_model_lock_authority,
        core.require_formal_model_lock_authority,
        core.execute_formal_model_lock,
        core.validate_formal_model_lock_bundle,
    ):
        with pytest.raises(core.ClosureFormalModelLockError, match="exact11 missing"):
            blocked()
    assert runner.GATE == runner.PATCH_GATE == runner.FORMAL_MODEL_LOCK_GATE == "E0-M"
    assert runner.UNBLINDING_GATE == "E0-U"
    assert runner.SEALED_BATCH_COMMAND_ARGV == runner.SEALED_BATCH_ARGV
    assert runner.SEALED_BATCH_COMMAND == " ".join(runner.SEALED_BATCH_ARGV) + "\n"
    assert runner.validate_sealed_batch_contract(runner.sealed_batch_contract())
    assert runner.validate_sealed_batch_command(runner.SEALED_BATCH_COMMAND)
    readiness = runner.check_only()
    assert readiness["status"] == "sealed_batch_runner_incomplete"
    assert readiness["missing_component_count"] == 11
    for key in (
        "formal_model_lock_ready",
        "evaluator_available",
        "sealed_batch_execution_ready",
        "e0_m_authorized",
        "e0_u_authorized",
        "evaluation_authorized",
        "outcome_access_authorized",
        "target_paths_opened",
        "outcome_paths_opened",
        "future_outcomes_accessed",
        "writes_performed",
    ):
        assert readiness[key] is False
    execute_source = inspect.getsource(runner.execute_sealed_batch)
    assert execute_source.index("authority = _require_e0_u_authority_first()") < (
        execute_source.index("collect_sealed_batch_component_readiness")
    )


def test_selector_routes_h_before_mid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(precommit, "_closure_formal_model_lock_module", _fake)
    monkeypatch.setattr(
        precommit, "_require_closure_formal_model_lock_stage_base", lambda *a, **k: None
    )
    assert precommit.closure_formal_model_lock_pre_stage_scope(_short(H_SCOPE)) == (
        "H-E0-M",
        tuple(sorted(H_SCOPE)),
    )
    source = inspect.getsource(precommit.main)
    assert source.index("closure_formal_model_lock_pre_stage_scope") < source.index(
        "closure_locked_evaluation_input_manifest_dialect_pre_stage_scope"
    )


def test_selector_blocks_p_while_infrastructure_is_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(precommit, "_closure_formal_model_lock_module", _fake)
    monkeypatch.setattr(precommit, "_git_output", lambda *a, **k: BASE_R_MI + "\n")
    with pytest.raises(
        precommit.ClosureFormalModelLockAdapterError, match="11 missing"
    ):
        precommit.closure_formal_model_lock_pre_stage_scope(_short(P_SCOPE))


def test_selector_blocks_r_while_infrastructure_is_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(precommit, "_closure_formal_model_lock_module", _fake)
    monkeypatch.setattr(precommit, "_git_output", lambda *a, **k: BASE_R_MI + "\n")
    with pytest.raises(
        precommit.ClosureFormalModelLockAdapterError, match="11 missing"
    ):
        precommit.closure_formal_model_lock_pre_stage_scope(_short(R_SCOPE))


def test_selector_rejects_partial_extra_duplicate_and_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(precommit, "_closure_formal_model_lock_module", _fake)
    first = _short(H_SCOPE).splitlines(keepends=True)[0]
    for status in (
        first,
        _short(H_SCOPE) + "?? extra\n",
        _short(H_SCOPE) + first,
        _short(H_SCOPE) + "broken\n",
    ):
        with pytest.raises(precommit.ClosureFormalModelLockAdapterError):
            precommit.closure_formal_model_lock_pre_stage_scope(status)


def test_non_formal_status_remains_generic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(precommit, "_closure_formal_model_lock_module", _fake)
    assert precommit.closure_formal_model_lock_pre_stage_scope("?? unrelated\n") is None


def test_invocation_is_closed_no_dvc() -> None:
    env = {"DVC_NO_ANALYTICS": "1"}
    precommit.validate_closure_formal_model_lock_invocation(
        _args(), gate="H-E0-M", env=env
    )
    for gate in ("P-E0-M", "R-E0-M"):
        with pytest.raises(
            precommit.ClosureFormalModelLockAdapterError, match="11 formal"
        ):
            precommit.validate_closure_formal_model_lock_invocation(
                _args(), gate=gate, env=env
            )
    invalid = (
        _args(target=["data/x"]),
        _args(no_push=False),
        _args(allow_unmanaged=False),
        _args(dry_run=True),
        _args(verify_manifest_inputs=True),
    )
    for args in invalid:
        with pytest.raises(precommit.ClosureFormalModelLockAdapterError):
            precommit.validate_closure_formal_model_lock_invocation(
                args, gate="R-E0-M", env=env
            )


def test_staged_and_workspace_scopes_are_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(precommit, "_closure_formal_model_lock_module", _fake)
    for gate, scope in (
        ("H-E0-M", H_SCOPE),
        ("P-E0-M", P_SCOPE),
        ("R-E0-M", R_SCOPE),
    ):
        precommit.validate_closure_formal_model_lock_staged_scope(
            _name_status(scope), gate=gate
        )
        precommit.validate_closure_formal_model_lock_workspace_scope(
            _short(scope, staged=True), gate=gate
        )
        with pytest.raises(precommit.ClosureFormalModelLockAdapterError):
            precommit.validate_closure_formal_model_lock_staged_scope(
                _name_status(scope) + "A\textra\n", gate=gate
            )


def test_staged_bindings_require_modes_oids_and_single_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch = _fake()
    monkeypatch.setattr(precommit, "_closure_formal_model_lock_module", lambda: patch)
    oid = "a" * 40

    def git_output(root: Path, *args: str) -> str:
        raw_path = args[-1]
        if args[0] == "ls-files":
            mode = precommit._FORMAL_MODEL_LOCK_H_GIT_MODES[raw_path]
            return f"{mode} {oid} 0\t{raw_path}\n"
        if args[0] == "hash-object":
            return oid + "\n"
        raise AssertionError(args)

    monkeypatch.setattr(precommit, "_git_output", git_output)
    monkeypatch.setattr(
        precommit,
        "_registration_file_identity",
        lambda path, **kwargs: precommit.RegistrationFileIdentity(
            path=path.as_posix(), device=1, inode=2, mode=kwargs["mode"], nlink=1,
            size=1, sha256="b" * 64, mtime_ns=3, ctime_ns=4,
        ),
    )
    assert len(
        precommit.validate_closure_formal_model_lock_staged_bindings(
            gate="H-E0-M"
        )
    ) == 7


def test_h_stage_base_requires_exact_r_mi_and_prelock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    patch = _fake()
    monkeypatch.setattr(precommit, "_git_output", lambda *a, **k: BASE_R_MI + "\n")
    monkeypatch.setattr(
        precommit,
        "_require_closure_formal_model_lock_prelock",
        lambda **kwargs: calls.append("prelock"),
    )
    precommit._require_closure_formal_model_lock_stage_base(
        "H-E0-M", patch=patch, repo_root=Path(".")
    )
    assert calls == ["prelock"]


def test_p_stage_base_blocks_before_git_or_unpublished(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []
    patch = _fake()

    def git_output(root: Path, *args: str) -> str:
        return BASE_R_MI + "\n" if args[0] == "rev-parse" else _name_status(H_SCOPE)

    monkeypatch.setattr(precommit, "_git_output", git_output)
    monkeypatch.setattr(
        precommit,
        "_require_closure_formal_model_lock_unpublished",
        lambda **kwargs: calls.append(kwargs["require_staged"]),
    )
    with pytest.raises(
        precommit.ClosureFormalModelLockAdapterError, match="11 missing"
    ):
        precommit._require_closure_formal_model_lock_stage_base(
            "P-E0-M", patch=patch, repo_root=Path(".")
        )
    assert calls == []


def test_r_stage_base_blocks_before_authority_or_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    patch = _fake()
    monkeypatch.setattr(precommit, "_git_output", lambda *a, **k: "head\n")
    monkeypatch.setattr(
        precommit, "_require_closure_formal_model_lock_authority",
        lambda **kwargs: calls.append("authority"),
    )
    monkeypatch.setattr(
        precommit, "_require_closure_formal_model_lock_bundle",
        lambda **kwargs: calls.append(
            f"bundle:{kwargs['require_staged']}"
        ),
    )
    with pytest.raises(
        precommit.ClosureFormalModelLockAdapterError, match="11 missing"
    ):
        precommit._require_closure_formal_model_lock_stage_base(
            "R-E0-M", patch=patch, repo_root=Path(".")
        )
    assert calls == []


def test_prelock_is_double_captured_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch = _fake()
    assert precommit._require_closure_formal_model_lock_prelock(
        patch=patch, repo_root=Path(".")
    )["status"] == "formal_model_lock_infrastructure_incomplete"
    states = iter((_prelock(), _prelock(formal_output_count=1)))
    patch.collect_formal_model_lock_prelock_state = lambda **kwargs: next(states)
    with pytest.raises(precommit.ClosureFormalModelLockAdapterError):
        precommit._require_closure_formal_model_lock_prelock(
            patch=patch, repo_root=Path(".")
        )


def test_unpublished_effective_and_bundle_statuses_are_strict() -> None:
    patch = _fake()
    with pytest.raises(
        precommit.ClosureFormalModelLockAdapterError, match="P-E0-M is blocked"
    ):
        precommit._require_closure_formal_model_lock_unpublished(
            patch=patch, repo_root=Path("."), require_staged=True
        )
    with pytest.raises(
        precommit.ClosureFormalModelLockAdapterError, match="R-E0-M is blocked"
    ):
        precommit._require_closure_formal_model_lock_authority(
            patch=patch, repo_root=Path(".")
        )
    assert precommit._require_closure_formal_model_lock_bundle(
        patch=patch, repo_root=Path("."), require_staged=True
    )["outcome_access_log_record_count"] == 0
    with pytest.raises(precommit.ClosureFormalModelLockAdapterError):
        precommit._require_closure_formal_model_lock_unpublished(
            patch=_fake(
                validate_formal_model_lock_unpublished_authority_bundle=lambda **k: {}
            ),
            repo_root=Path("."),
            require_staged=False,
        )
    with pytest.raises(precommit.ClosureFormalModelLockAdapterError):
        precommit._require_closure_formal_model_lock_authority(
            patch=_fake(require_formal_model_lock_authority=lambda **k: {}),
            repo_root=Path("."),
        )
    with pytest.raises(precommit.ClosureFormalModelLockAdapterError):
        precommit._require_closure_formal_model_lock_bundle(
            patch=_fake(validate_formal_model_lock_bundle=lambda **k: {}),
            repo_root=Path("."),
            require_staged=True,
        )


def test_h_transaction_revalidates_prelock_and_physical_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch = _fake()
    calls: list[str] = []
    monkeypatch.setattr(precommit, "_closure_formal_model_lock_module", lambda: patch)
    monkeypatch.setattr(
        precommit, "validate_closure_formal_model_lock_staged_scope", lambda *a, **k: None
    )
    monkeypatch.setattr(
        precommit, "validate_closure_formal_model_lock_workspace_scope", lambda *a, **k: None
    )
    binding = ("binding",)
    monkeypatch.setattr(
        precommit, "validate_closure_formal_model_lock_staged_bindings", lambda **k: binding
    )
    monkeypatch.setattr(
        precommit, "snapshot_closure_formal_model_lock_physical_state", lambda **k: ("physical",)
    )
    monkeypatch.setattr(precommit, "_git_output", lambda *a, **k: BASE_R_MI + "\n")
    monkeypatch.setattr(
        precommit, "_require_closure_formal_model_lock_prelock",
        lambda **k: calls.append("h:prelock"),
    )
    precommit.revalidate_closure_formal_model_lock_transaction(
        gate="H-E0-M", staged_status=_name_status(H_SCOPE),
        expected_physical_snapshot=("physical",),
    )
    assert calls == ["h:prelock"]


def test_main_routes_formal_before_mid_and_never_dvc_adds() -> None:
    source = inspect.getsource(precommit.main)
    assert source.index("closure_formal_model_lock_pre_stage_scope") < source.index(
        "closure_locked_evaluation_input_manifest_dialect_pre_stage_scope"
    )
    assert "if formal_model_lock_active:" in source
    assert "validate_closure_formal_model_lock_invocation" in source
    assert "revalidate_closure_formal_model_lock_transaction" in source
    assert 'mib_r_gate = final_calibration_stage_gate == "R-E0-MI"' in source
    assert 'final_calibration_stage_gate and selected_dvc_paths' in source
    assert "git\",\n                        \"add\",\n                        \"-A\"" in source
