from __future__ import annotations

import inspect
import importlib
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from src.data import prepare_commit_artifacts as precommit


BASE_R_MI = "53947df3b826ee10be8cf3b137bae913bc73d2bb"
BASE_PREREQUISITE = "4bf1953660462b63115a47f97b1041e44d33d873"
SUPERSEDED_H_BATCH = "4d0f2ebd1d55cc21757755f90b5ae5e8ec6531f8"
SUPERSEDED_H_CHECK_ONLY = "367143285067b91f85df3b81542b30db9c74fc2f"
H_SCOPE = dict(precommit._FORMAL_MODEL_LOCK_H_STAGED_SCOPE)
H_CHECK_ONLY_SCOPE = dict(
    precommit._FORMAL_MODEL_LOCK_H_CHECK_ONLY_STAGED_SCOPE
)
H_OFFLINE_VALIDATION_SCOPE = dict(
    precommit._FORMAL_MODEL_LOCK_H_OFFLINE_VALIDATION_STAGED_SCOPE
)
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
        "status": "ready_to_lock",
        "runner_readiness": {
            "status": "sealed_batch_runner_ready_for_formal_lock",
            "missing_component_count": 0,
            "formal_model_lock_ready": True,
            "evaluator_available": True,
            "sealed_batch_execution_ready": True,
        },
        "formal_model_lock_ready": True,
        "missing_component_count": 0,
        "p_authority_generation_authorized": False,
        "formal_output_count": 0,
        "outcome_access_log_state": "absent",
        "formal_lock_execution_authorized": False,
        "r_execution_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "evaluation_authorized": False,
        "outcome_access_authorized": False,
        "target_paths_opened": False,
        "outcome_paths_opened": False,
        "future_outcomes_accessed": False,
        "scientific_execution_run": False,
        "verification_commands_run": False,
        "dvc_commands_run": False,
        "git_commands_mutating_run": False,
        "writes_performed": False,
    }
    value.update(overrides)
    return value


def _unpublished(*, staged: bool = False, **overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "gate": "E0-M",
        "status": "locked_unpublished",
        "p_stage_state": "staged" if staged else "untracked",
        "formal_model_lock_ready": True,
        "p_authority_generation_authorized": True,
        "effective_authority": False,
        "formal_lock_execution_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "evaluation_authorized": False,
        "outcome_access_authorized": False,
        "target_access_authorized": False,
        "dvc_commands_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
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
        "formal_model_lock_ready": True,
        "p_authority_generation_authorized": False,
        "effective_authority": True,
        "formal_lock_execution_authorized": True,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "outcome_access_authorized": False,
        "target_access_authorized": False,
        "dvc_commands_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
        "writes_performed": False,
    }
    value.update(overrides)
    return value


def _bundle(*, staged: bool = False, **overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "gate": "E0-M",
        "status": "formal_model_lock_validated",
        "r_stage_state": "exact5_staged" if staged else "exact5_untracked",
        "output_count": 5,
        "manifest_written_last": True,
        "formal_model_lock_ready": True,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "outcome_access_authorized": False,
        "target_access_authorized": False,
        "outcome_access_log_state": "present_empty",
        "outcome_access_log_record_count": 0,
        "future_outcomes_accessed": False,
        "scientific_execution_run": False,
        "dvc_commands_run": False,
        "git_commands_mutating_run": False,
        "writes_performed": False,
    }
    value.update(overrides)
    return value


def _fake(**overrides: Any) -> SimpleNamespace:
    physical = ("physical",)
    values: dict[str, Any] = {
        "PATCH_GATE": "E0-M",
        "H_GATE": "H-E0-MBATCH",
        "H_CHECK_ONLY_PATCH_GATE": "H-E0-MBATCHP1",
        "H_OFFLINE_VALIDATION_PATCH_GATE": "H-E0-MBATCHP2",
        "P_GATE": "P-E0-M",
        "R_GATE": "R-E0-M",
        "BASE_R_MID_COMMIT": BASE_R_MI,
        "BASE_H_E0_M_PREREQUISITE_COMMIT": BASE_PREREQUISITE,
        "SUPERSEDED_H_E0_M_BATCH_COMMIT": SUPERSEDED_H_BATCH,
        "SUPERSEDED_H_E0_M_CHECK_ONLY_PATCH_COMMIT": (
            SUPERSEDED_H_CHECK_ONLY
        ),
        "PATCH_PATHS": tuple(sorted(H_SCOPE)),
        "FORMAL_MODEL_LOCK_H_STAGED_SCOPE": dict(H_SCOPE),
        "FORMAL_MODEL_LOCK_H_CHECK_ONLY_STAGED_SCOPE": dict(
            H_CHECK_ONLY_SCOPE
        ),
        "FORMAL_MODEL_LOCK_H_OFFLINE_VALIDATION_STAGED_SCOPE": dict(
            H_OFFLINE_VALIDATION_SCOPE
        ),
        "FORMAL_MODEL_LOCK_P_STAGED_SCOPE": dict(P_SCOPE),
        "FORMAL_MODEL_LOCK_R_STAGED_SCOPE": dict(R_SCOPE),
        "FINAL_CALIBRATION_H_STAGED_SCOPE": dict(H_SCOPE),
        "FINAL_CALIBRATION_P_STAGED_SCOPE": dict(P_SCOPE),
        "FINAL_CALIBRATION_R_STAGED_SCOPE": dict(R_SCOPE),
        "GENERIC_MANIFEST_FINDINGS_CONTRACT": (
            {
                "level": "fail",
                "check": "manifest",
                "path": "reports/closure_v1/00_protocol/hypothesis_registry.csv",
                "message": "Staged report artifact is not listed in any experiment manifest output.",
            },
            {
                "level": "fail",
                "check": "manifest",
                "path": "reports/closure_v1/00_protocol/locked_batch_command.txt",
                "message": "Staged report artifact is not listed in any experiment manifest output.",
            },
        ),
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


def test_topology_is_exact_h17_p2_r5_and_e1_e10_are_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from src.experiments import closure_formal_model_lock as core
    from src.experiments import lock_closure_formal_model_lock as locker
    from src.experiments import run_closure_benchmark as runner

    assert (len(H_SCOPE), len(P_SCOPE), len(R_SCOPE)) == (17, 2, 5)
    assert len(H_CHECK_ONLY_SCOPE) == 5
    assert len(H_OFFLINE_VALIDATION_SCOPE) == 5
    assert set(H_CHECK_ONLY_SCOPE.values()) == {"M"}
    assert set(H_OFFLINE_VALIDATION_SCOPE.values()) == {"M"}
    assert set(H_CHECK_ONLY_SCOPE) == {
        "docs/closure_v1/E0_M_FORMAL_MODEL_LOCK.md",
        "src/data/prepare_commit_artifacts.py",
        "src/experiments/closure_formal_model_lock.py",
        "src/experiments/lock_closure_formal_model_lock.py",
        "tests/test_closure_formal_model_lock.py",
    }
    assert set(H_CHECK_ONLY_SCOPE) < set(H_SCOPE)
    assert H_OFFLINE_VALIDATION_SCOPE == H_CHECK_ONLY_SCOPE
    assert tuple(H_SCOPE.values()).count("M") == 7
    assert tuple(H_SCOPE.values()).count("A") == 10
    assert not set(H_SCOPE) & set(P_SCOPE)
    assert not set(H_SCOPE) & set(R_SCOPE)
    assert not set(P_SCOPE) & set(R_SCOPE)
    assert H_SCOPE["src/data/prepare_commit_artifacts.py"] == "M"
    assert H_SCOPE["src/experiments/run_closure_benchmark.py"] == "M"
    assert core.BASE_R_MID_COMMIT == BASE_R_MI
    assert core.BASE_H_E0_M_PREREQUISITE_COMMIT == BASE_PREREQUISITE
    assert core.SUPERSEDED_H_E0_M_BATCH_COMMIT == SUPERSEDED_H_BATCH
    assert (
        core.SUPERSEDED_H_E0_M_CHECK_ONLY_PATCH_COMMIT
        == SUPERSEDED_H_CHECK_ONLY
    )
    assert core.H_GATE == "H-E0-MBATCH"
    assert core.H_CHECK_ONLY_PATCH_GATE == "H-E0-MBATCHP1"
    assert core.H_OFFLINE_VALIDATION_PATCH_GATE == "H-E0-MBATCHP2"
    assert core.R8_AUTHORITY_OUTPUTS_SHA256 == (
        "524928813b26bed6de9feee34eff1e946f9fc214521c3a39171ed905b3faf7a2"
    )
    assert core.R8_PORTABLE_OUTPUTS_SHA256 == (
        "ae353e664a6136803aad1c410d7355e5dead9c907ca01a57799f41c967855af5"
    )
    assert core.H_CHECK_ONLY_PATCH_HISTORICAL_INPUTS_SHA256 == (
        "33d3e44c899797570e1a0ccd3514902d57ce40c67a8f9c6043d7398f9064e426"
    )
    artifact_snapshot = core._model_artifact_snapshot(
        Path("."), git_commit=core.BASE_H_E0_M_PREREQUISITE_COMMIT
    )
    assert len(artifact_snapshot) == core.MODEL_ARTIFACT_RECORD_COUNT == 220
    assert len({record["path"] for record in artifact_snapshot}) == len(
        artifact_snapshot
    )
    assert sum(len(record["roles"]) for record in artifact_snapshot) == 220
    assert all(
        set(record)
        == {
            "path",
            "bytes",
            "sha256",
            "device",
            "inode",
            "mode",
            "nlink",
            "mtime_ns",
            "ctime_ns",
            "roles",
        }
        for record in artifact_snapshot
    )
    physical_snapshot = core._physical_snapshot(Path("."))
    assert tuple(
        record for record in physical_snapshot if "roles" in record
    ) == artifact_snapshot
    drifted_physical = tuple(
        (
            {**record, "sha256": "0" * 64}
            if record["path"] == artifact_snapshot[0]["path"]
            else record
        )
        for record in physical_snapshot
    )
    with monkeypatch.context() as boundary_patch:
        boundary_patch.setattr(core.mcal, "_git_head", lambda *_a, **_k: "p" * 40)
        boundary_patch.setattr(
            core.mcal, "_git", lambda *_a, **_k: "main\n"
        )
        boundary_patch.setattr(
            core.mcal, "_live_remote_main_head", lambda *_a, **_k: "p" * 40
        )
        boundary_patch.setattr(
            core.mcal, "_single_parent", lambda *_a, **_k: "h" * 40
        )
        boundary_patch.setattr(core, "_status_map", lambda *_a, **_k: {})
        boundary_patch.setattr(core, "_require_namespace", lambda *_a, **_k: {})
        boundary_patch.setattr(core, "_p_pair_snapshot", lambda *_a, **_k: ())
        boundary_patch.setattr(
            core, "_physical_snapshot", lambda *_a, **_k: drifted_physical
        )
        with pytest.raises(
            core.ClosureFormalModelLockError,
            match="physical authority changed",
        ):
            core._require_r_repository_boundary(
                authority={
                    "h_batch_head": "h" * 40,
                    "p_patch_head": "p" * 40,
                },
                expected_present=(),
                expected_p_snapshot=(),
                expected_physical_snapshot=physical_snapshot,
                verify_remote=True,
                repo_root=Path("."),
                owned_guard=None,
            )
    assert tuple(sorted(R_SCOPE)) == (
        "reports/closure_v1/00_protocol/calibration_lock.yaml",
        "reports/closure_v1/00_protocol/hypothesis_registry.csv",
        "reports/closure_v1/00_protocol/locked_batch_command.txt",
        "reports/closure_v1/00_protocol/model_lock.yaml",
        "reports/closure_v1/00_protocol/outcome_access_log.jsonl",
    )
    assert core.PATCH_PATHS == tuple(sorted(H_SCOPE))
    assert core.FORMAL_MODEL_LOCK_H_STAGED_SCOPE == H_SCOPE
    assert core.FORMAL_MODEL_LOCK_H_CHECK_ONLY_STAGED_SCOPE == H_CHECK_ONLY_SCOPE
    assert (
        core.FORMAL_MODEL_LOCK_H_OFFLINE_VALIDATION_STAGED_SCOPE
        == H_OFFLINE_VALIDATION_SCOPE
    )
    assert core.FORMAL_MODEL_LOCK_P_STAGED_SCOPE == P_SCOPE
    assert core.FORMAL_MODEL_LOCK_R_STAGED_SCOPE == R_SCOPE
    assert core.FINAL_CALIBRATION_H_STAGED_SCOPE == H_SCOPE
    assert core.FINAL_CALIBRATION_P_STAGED_SCOPE == P_SCOPE
    assert core.FINAL_CALIBRATION_R_STAGED_SCOPE == R_SCOPE
    predecessor_modules = (core.mid.mic.mcalm, core.mid.mic.mib, core.mid.mic, core.mid)
    expected_predecessor_coordination = {
        *core.mid.mic.mcalm.COORDINATION_NAMESPACE_PATHS,
        *core.mid.mic.mib.COORDINATION_NAMESPACE_PATHS,
        *core.mid.mic.LOCK_TEMPORARY_PATHS,
        core.mid.mic.LOCKER_GUARD_PATH,
        *core.mid.LOCK_TEMPORARY_PATHS,
        core.mid.LOCKER_GUARD_PATH,
    }
    assert set(core.PREDECESSOR_COORDINATION_NAMESPACE_PATHS) == (
        expected_predecessor_coordination
    )
    for module in predecessor_modules:
        for name, value in vars(module).items():
            if (
                ("GUARD_PATH" in name or name.endswith("TEMPORARY_PATHS"))
                and isinstance(value, (Path, tuple))
            ):
                paths = (value,) if isinstance(value, Path) else value
                assert set(paths) <= expected_predecessor_coordination
    assert precommit._closure_formal_model_lock_scopes(core) == (
        H_SCOPE,
        P_SCOPE,
        R_SCOPE,
    )
    prelock = core.collect_formal_model_lock_prelock_state(verify_remote=False)
    assert prelock["status"] == "ready_to_lock"
    assert prelock["runner_readiness"]["status"] == (
        "sealed_batch_runner_ready_for_formal_lock"
    )
    assert prelock["missing_component_count"] == 0
    assert prelock["formal_model_lock_ready"] is True
    assert prelock["p_authority_generation_authorized"] is (
        prelock["repository"]["h_state"] == "published"
    )
    assert prelock["calibration_evidence"]["outputs_sha256"] == (
        core.R8_AUTHORITY_OUTPUTS_SHA256
    )
    assert core._sha256_bytes(
        core._canonical_json_bytes(prelock["calibration_evidence"]["outputs"])
    ) == core.R8_PORTABLE_OUTPUTS_SHA256
    assert prelock["formal_output_count"] == 0
    assert prelock["outcome_access_log_state"] == "absent"
    assert prelock["target_paths_opened"] is False
    assert prelock["outcome_paths_opened"] is False
    assert prelock["future_outcomes_accessed"] is False
    assert prelock["writes_performed"] is False
    historical_inputs = core._historical_h_check_only_patch_records(Path("."))
    assert len(historical_inputs) == len(H_OFFLINE_VALIDATION_SCOPE) == 5
    assert [record["path"] for record in historical_inputs] == sorted(
        H_OFFLINE_VALIDATION_SCOPE
    )
    assert all(
        set(record)
        == {
            "role",
            "path",
            "commit",
            "git_mode",
            "git_oid",
            "bytes",
            "sha256",
        }
        and record["role"]
        == "superseded_h_e0_m_check_only_patch_component"
        and record["commit"] == SUPERSEDED_H_CHECK_ONLY
        for record in historical_inputs
    )
    assert core._sha256_bytes(core._canonical_json_bytes(historical_inputs)) == (
        core.H_CHECK_ONLY_PATCH_HISTORICAL_INPUTS_SHA256
    )
    with monkeypatch.context() as locker_patch:
        locker_patch.setattr(
            locker.patch,
            "preflight_formal_model_lock_schema",
            lambda **_kwargs: {"gate": "E0-M", "status": "schema_validated"},
        )
        captures = iter(
            (
                (("physical",), _prelock(p_authority_generation_authorized=True)),
                (("physical",), _prelock(p_authority_generation_authorized=True)),
            )
        )
        locker_patch.setattr(locker, "_capture_prelock_state", lambda: next(captures))
        locker_patch.setattr(
            locker,
            "_run_command",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("check-only executed a verification command")
            ),
        )
        checked = locker.check_only()
        assert checked["p_authority_generation_authorized"] is True
        assert checked["prelock"]["p_authority_generation_authorized"] is True
        assert checked["verification_commands_run"] is False
        assert checked["writes_performed"] is False
    with monkeypatch.context() as locker_patch:
        locker_patch.setattr(
            locker.patch,
            "preflight_formal_model_lock_schema",
            lambda **_kwargs: {"gate": "E0-M", "status": "schema_validated"},
        )
        captures = iter(
            (
                (("physical",), _prelock()),
                (("physical",), _prelock()),
            )
        )
        locker_patch.setattr(locker, "_capture_prelock_state", lambda: next(captures))
        locker_patch.setattr(
            locker,
            "_run_command",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("rejected check-only executed a verification command")
            ),
        )
        with pytest.raises(
            core.ClosureFormalModelLockError,
            match="published H-E0-MBATCHP2 readiness drifted",
        ):
            locker.check_only()
    assert runner.GATE == runner.PATCH_GATE == runner.FORMAL_MODEL_LOCK_GATE == "E0-M"
    assert runner.UNBLINDING_GATE == "E0-U"
    assert runner.SEALED_BATCH_ARGV == runner.SEALED_BATCH_PYTHON_ARGV
    assert runner.SEALED_BATCH_COMMAND_ARGV == runner.SEALED_BATCH_LAUNCH_ARGV
    assert runner.SEALED_BATCH_COMMAND == (
        "/usr/bin/env -i LANG=C LC_ALL=C .venv/bin/python -I -S -B "
        "src/experiments/run_closure_benchmark.py --execute-sealed-batch\n"
    )
    assert runner.validate_sealed_batch_contract(runner.sealed_batch_contract())
    assert runner.validate_sealed_batch_command(runner.SEALED_BATCH_COMMAND)
    readiness = runner.check_only()
    assert readiness["status"] == "sealed_batch_runner_ready_for_formal_lock"
    assert readiness["missing_component_count"] == 0
    assert readiness["startup_contract"] == runner.sealed_batch_contract()[
        "startup_contract"
    ]
    assert readiness["startup_contract"]["authority_require"] == {
        "first_capability_operation": True,
        "private_apis_removed_from_component_payload": True,
        "result_exact_keys": True,
        "runtime_environment_record_key": "sealed_runtime_environment_record",
        "source_record_key": "sealed_authority_source_record",
    }
    for key in (
        "formal_model_lock_ready",
        "evaluator_available",
        "sealed_batch_execution_ready",
    ):
        assert readiness[key] is True
    for key in (
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
    assert "importlib.import_module" not in inspect.getsource(
        runner._load_ready_components
    )
    assert "importlib.import_module" not in inspect.getsource(
        runner._load_e0_u_authority_module
    )
    assert runner.COMPONENT_ARTIFACT_CONTRACTS["E4_reference_targets"][
        "artifact_paths"
    ] == ()
    assert runner.COMPONENT_ARTIFACT_CONTRACTS["E4_trophic_evaluation"][
        "artifact_paths"
    ] == runner.BATCH_STAGES[4].output_paths
    assert set(runner.EXPECTED_ARTIFACT_FORMATS) == set(
        runner.EXPECTED_ARTIFACT_PATHS
    )
    assert tuple(runner.EXPECTED_PUBLICATION_ORDER)[-1] == (
        "reports/closure_v1/10_api/environment.json"
    )
    assert runner.PUBLICATION_AUDIT_RECORD_KEYS == {
        "path",
        "bytes",
        "sha256",
        "device",
        "inode",
        "mode",
        "nlink",
        "mtime_ns",
        "ctime_ns",
    }
    sealed_root = tmp_path / "sealed-source"
    sealed_path = Path("src/experiments/sealed_probe.py")
    (sealed_root / sealed_path.parent).mkdir(parents=True)
    (sealed_root / sealed_path).write_text("VALUE = 'sealed-source-bytes'\n", encoding="utf-8")
    payload, metadata = runner._read_regular_source(sealed_path, repo_root=sealed_root)
    expected_source = runner._source_identity_record(sealed_path, payload, metadata)
    module_name = "src.experiments.sealed_probe"
    previous_module = runner.sys.modules.get(module_name)
    foreign_module = type(runner)(module_name)
    foreign_module.__dict__["VALUE"] = "foreign-cache"
    runner.sys.modules[module_name] = foreign_module
    try:
        with monkeypatch.context() as scoped:
            scoped.setattr(
                importlib,
                "import_module",
                lambda *_a, **_k: (_ for _ in ()).throw(
                    AssertionError("importlib/pyc consulted")
                ),
            )
            sealed_module, observed_source = runner._execute_sealed_source_module(
                module_name=module_name,
                source_path=sealed_path,
                repo_root=sealed_root,
                expected_source_record=expected_source,
            )
        assert sealed_module.VALUE == "sealed-source-bytes"
        assert observed_source == expected_source
    finally:
        if previous_module is None:
            runner.sys.modules.pop(module_name, None)
        else:
            runner.sys.modules[module_name] = previous_module
    with pytest.raises(runner.ClosureBenchmarkError, match="source binding"):
        runner._require_source_identity(
            {**expected_source, "sha256": "0" * 64},
            expected_source,
            context="negative-source-probe",
        )
    for invalid_authority in (
        b"from __future__ import annotations\nclass X:\n    pass\n",
        b"from __future__ import annotations\ndef f(value=(x for x in ())):\n    return value\n",
        b"from __future__ import annotations\ndef f():\n    import antigravity\n",
        b"from __future__ import annotations\ndef f(value: factory()):\n    return value\n",
        (
            b"from __future__ import annotations\n"
            b"def f():\n"
            b"    import os\n"
            b"    key = '_' * 2 + 'import' + '_' * 2\n"
            b"    return os.__dict__['__builtins__'][key]('site')\n"
        ),
        (
            b"from __future__ import annotations\n"
            b"class X:\n"
            b"    def __class_getitem__(cls, value):\n"
            b"        return value\n"
            b"def f(value: X[0]):\n"
            b"    return value\n"
        ),
    ):
        with pytest.raises(runner.ClosureBenchmarkError):
            runner._require_stdlib_only_authority_source(invalid_authority)
    with monkeypatch.context() as environment_patch:
        environment_patch.setattr(
            runner.os,
            "environ",
            {"LANG": "C", "LC_ALL": "C", "FOREIGN": "1"},
        )
        with pytest.raises(runner.ClosureBenchmarkError, match="not sanitized"):
            runner._exact_process_environment()
    public_authority = {
        **{key: None for key in runner.E0_U_AUTHORITY_RESULT_KEYS},
        **{key: None for key in runner.E0_U_AUTHORITY_INTERNAL_KEYS},
    }
    assert set(runner._public_authority_payload(public_authority)) == (
        runner.E0_U_AUTHORITY_RESULT_KEYS
    )
    with pytest.raises(runner.ClosureBenchmarkError, match="internal authority keys"):
        runner._public_authority_payload({**public_authority, "hidden": object()})
    remote_consulted = False
    with monkeypatch.context() as source_patch:
        source_patch.setattr(
            runner,
            "E0_U_AUTHORITY_PATH",
            Path("src/experiments/definitely_absent_e0_u_authority.py"),
        )

        def forbidden_remote() -> str:
            nonlocal remote_consulted
            remote_consulted = True
            raise AssertionError("live remote consulted before local authority source")

        source_patch.setattr(runner, "_live_remote_main_head", forbidden_remote)
        with pytest.raises(runner.ClosureBenchmarkError):
            runner._git_bound_e0_u_authority_source_record()
    assert remote_consulted is False
    with monkeypatch.context() as object_patch:
        object_patch.setattr(runner, "_sealed_git", lambda *_a, **_k: b"foreign")
        with pytest.raises(runner.ClosureBenchmarkError, match="content address"):
            runner._content_addressed_git_object("blob", "0" * 40)
    with pytest.raises(runner.ClosureBenchmarkError, match="runner source binding"):
        runner._validate_authority_source_bindings(
            {
                runner.E0_U_RUNNER_SOURCE_RECORD_KEY: {},
                runner.E0_U_COMPONENT_SOURCE_RECORDS_KEY: readiness[
                    "component_readiness"
                ]["component_source_records"],
            },
            readiness["component_readiness"],
        )
    pd = pytest.importorskip("pandas")
    with pytest.raises(runner.ClosureBenchmarkError, match="artifact ownership"):
        runner._validate_component_result(
            {
                "component_id": "E4_reference_targets",
                "stage_id": "E4",
                "status": "completed",
                "artifacts": {
                    runner.BATCH_STAGES[4].output_paths[0]: {
                        "format": "csv",
                        "payload": pd.DataFrame({"value": [1]}),
                        "manifest_last": False,
                    }
                },
                "tables": {
                    "trophic_reference_targets": pd.DataFrame({"value": [1]})
                },
                "diagnostics": {
                    "row_count": 1,
                    "site_count": 1,
                    "non_chla_reference_row_count": 0,
                    "future_indicator_imputation_performed": False,
                },
                "outcome_paths_opened": True,
                "writes_performed": False,
            },
            component_id="E4_reference_targets",
            stage_id="E4",
            output_tables=("trophic_reference_targets",),
            required_nonempty_tables=("trophic_reference_targets",),
        )
    with pytest.raises(runner.ClosureBenchmarkError, match="non-canonical payload"):
        runner._validate_component_result(
            {
                "component_id": "E4_reference_targets",
                "stage_id": "E4",
                "status": "completed",
                "artifacts": {},
                "tables": {
                    "trophic_reference_targets": pd.DataFrame({"value": [1]})
                },
                "diagnostics": {
                    "row_count": 1,
                    "site_count": 1,
                    "non_chla_reference_row_count": 0,
                    "future_indicator_imputation_performed": False,
                    "hidden_rows": pd.DataFrame({"outcome": [1]}),
                },
                "outcome_paths_opened": True,
                "writes_performed": False,
            },
            component_id="E4_reference_targets",
            stage_id="E4",
            output_tables=("trophic_reference_targets",),
            required_nonempty_tables=("trophic_reference_targets",),
        )
    with pytest.raises(runner.ClosureBenchmarkError, match="diagnostics contract"):
        runner._validate_component_diagnostics(
            {
                "component_contract_sha256": runner.COMPONENT_CONTRACT_SHA256[
                    "E9_planning_inference"
                ],
                "input_row_count": 1,
                "shared_success_row_count": 0,
                "failure_row_count": 1,
                "bootstrap_replicates": 2000,
                "holm_universe_size": 9,
                "refit_performed": False,
            },
            component_id="E9_planning_inference",
            status="completed",
        )
    with pytest.raises(runner.ClosureBenchmarkError, match="audit keys"):
        runner._validate_post_publication_audit(
            {}, execution_id="probe", expected_bytes={}, observed_records=()
        )
    publication_source = inspect.getsource(
        runner._execute_with_verified_e0_u_authority
    )
    assert publication_source.index("physical_before =") < publication_source.index(
        "audit_raw = auditor("
    ) < publication_source.index("physical_after =")
    publisher_index = publication_source.index("published_raw = publisher(")
    assert publication_source.rfind(
        "_recapture_runtime_environment(runtime_state)", 0, publisher_index
    ) > publication_source.index("expected_artifact_bytes =")
    terminal_snapshot_index = publication_source.rindex(
        "_require_terminal_published_artifact_snapshot("
    )
    assert (
        publication_source.rindex("_recapture_authority_source(authority)")
        < publication_source.rindex(
            "_recapture_runtime_environment(runtime_state)"
        )
        < terminal_snapshot_index
        < publication_source.rindex("return result")
    )
    terminal_state = {"mutated": False}
    terminal_baseline = ({"path": "simulated", "sha256": "before"},)

    def mutate_during_last_recapture(_state: object) -> None:
        terminal_state["mutated"] = True

    def simulated_terminal_snapshot(
        _expected: object, *, repo_root: Path
    ) -> tuple[dict[str, str], ...]:
        assert repo_root == Path(".")
        return (
            {
                "path": "simulated",
                "sha256": "after" if terminal_state["mutated"] else "before",
            },
        )

    with monkeypatch.context() as terminal_patch:
        terminal_patch.setattr(
            runner,
            "_recapture_runtime_environment",
            mutate_during_last_recapture,
        )
        terminal_patch.setattr(
            runner,
            "_published_artifact_snapshot",
            simulated_terminal_snapshot,
        )
        runner._recapture_runtime_environment({})
        with pytest.raises(runner.ClosureBenchmarkError, match="terminal success"):
            runner._require_terminal_published_artifact_snapshot(
                {}, terminal_baseline, repo_root=Path(".")
            )
    execute_source = inspect.getsource(runner.execute_sealed_batch)
    assert (
        execute_source.index("_require_sealed_startup_environment()")
        < execute_source.index("authority_source = _git_bound_e0_u_authority_source_record()")
        < execute_source.index("authority = _require_e0_u_authority_first(authority_source)")
        < execute_source.index("runtime_state = _activate_sealed_runtime_environment(authority)")
        < execute_source.index("collect_sealed_batch_component_readiness")
    )
    import subprocess

    isolated_probe = (
        'import runpy,sys,types; '
        'n=runpy.run_path("src/experiments/run_closure_benchmark.py",run_name="sealed_test_probe"); '
        'm=types.ModuleType(n["E0_U_AUTHORITY_MODULE"]); '
        'sys.modules[n["E0_U_AUTHORITY_MODULE"]]=m; '
        'b=n["_runtime_environment_record"](); '
        'b["bootstrap_import_state"]=n["_bootstrap_import_state_record"](); '
        'a={n["E0_U_RUNTIME_ENVIRONMENT_RECORD_KEY"]:b}; '
        's=n["_activate_sealed_runtime_environment"](a); '
        'r=n["collect_sealed_batch_component_readiness"](repo_root=n["PROJECT_ROOT"]); '
        'c=n["_load_ready_components"](r); '
        'n["_recapture_runtime_environment"](s); '
        'E=n["ClosureBenchmarkError"]; '
        'exec("k=next(k for k,v in s[\\"importer_cache\\"].items() if v is not None)\\n'
        'o=sys.path_importer_cache[k]\\nsys.path_importer_cache[k]=object()\\n'
        'cache_rejected=False\\ntry:\\n n[\\"_recapture_runtime_environment\\"](s)\\n'
        'except E:\\n cache_rejected=True\\nfinally:\\n sys.path_importer_cache[k]=o"); '
        'n["_recapture_runtime_environment"](s); '
        'print(len(c),"site" in sys.modules,cache_rejected)'
    )
    isolated = subprocess.run(
        (
            "/usr/bin/env",
            "-i",
            "LANG=C",
            "LC_ALL=C",
            ".venv/bin/python",
            "-I",
            "-S",
            "-B",
            "-c",
            isolated_probe,
        ),
        cwd=Path("."),
        check=False,
        capture_output=True,
        text=True,
    )
    assert isolated.returncode == 0, isolated.stderr
    assert isolated.stdout == "10 False True\n"
    authority = {
        "gate": "E0-U",
        "effective_authority": True,
        "sealed_batch_execution_authorized": True,
        "e0_m_authorized": True,
        "e0_u_authorized": True,
        "evaluation_authorized": True,
        "outcome_access_authorized": True,
        "writes_performed": False,
        "sealed_batch_command": runner.SEALED_BATCH_COMMAND,
    }
    contract = runner.sealed_batch_contract()
    expected_digest = runner.sealed_batch_contract_sha256()
    empty_context = {
        "execution_id": "pure-component-probe",
        "rng_seed": 1729,
        "tables": {},
        "stage_results": {},
        "model_availability": dict(runner.CURRENT_MODEL_AVAILABILITY),
        "software_evidence": {
            key: "sealed" for key in runner.SOFTWARE_EVIDENCE_KEYS
        },
    }
    assert callable(runner._execute_e1_locked_benchmark_stage)
    with pytest.raises(runner.ClosureBenchmarkError, match="locked table is absent"):
        runner._execute_e1_locked_benchmark_stage(
            authority,
            contract,
            empty_context,
            Path("."),
        )
    observed_stages = {"E1"}
    for component in runner.BATCH_COMPONENTS:
        module = importlib.import_module(component.module_name)
        result = getattr(module, component.preflight_api)(
            authority, contract, Path(".")
        )
        assert result == {
            "component_id": component.component_id,
            "stage_id": component.stage_id,
            "status": "ready",
            "contract_sha256": expected_digest,
            "outcome_paths_opened": False,
            "writes_performed": False,
        }
        try:
            terminal = getattr(module, component.execute_api)(
                authority, contract, empty_context, Path(".")
            )
        except Exception as exc:
            assert exc.__class__.__module__ == module.__name__
        else:
            assert terminal["component_id"] == component.component_id
            assert terminal["stage_id"] == component.stage_id
            assert terminal["status"] in {"completed", "completed_unavailable"}
            assert terminal["outcome_paths_opened"] is True
            assert terminal["writes_performed"] is False
        observed_stages.add(component.stage_id)
    assert observed_stages == {f"E{index}" for index in range(1, 11)}


def test_selector_routes_h_before_mid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(precommit, "_closure_formal_model_lock_module", _fake)
    monkeypatch.setattr(
        precommit, "_require_closure_formal_model_lock_stage_base", lambda *a, **k: None
    )
    assert precommit.closure_formal_model_lock_pre_stage_scope(_short(H_SCOPE)) == (
        "H-E0-MBATCH",
        tuple(sorted(H_SCOPE)),
    )
    monkeypatch.setattr(
        precommit,
        "_git_output",
        lambda *_args, **_kwargs: SUPERSEDED_H_CHECK_ONLY + "\n",
    )
    assert precommit.closure_formal_model_lock_pre_stage_scope(
        _short(H_OFFLINE_VALIDATION_SCOPE)
    ) == (
        "H-E0-MBATCHP2",
        tuple(sorted(H_OFFLINE_VALIDATION_SCOPE)),
    )
    monkeypatch.setattr(
        precommit,
        "_git_output",
        lambda *_args, **_kwargs: SUPERSEDED_H_BATCH + "\n",
    )
    assert precommit.closure_formal_model_lock_pre_stage_scope(
        _short(H_CHECK_ONLY_SCOPE)
    ) == (
        "H-E0-MBATCHP1",
        tuple(sorted(H_CHECK_ONLY_SCOPE)),
    )
    source = inspect.getsource(precommit.main)
    assert source.index("closure_formal_model_lock_pre_stage_scope") < source.index(
        "closure_locked_evaluation_input_manifest_dialect_pre_stage_scope"
    )


def test_selector_routes_p_only_from_exact_published_h(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []
    monkeypatch.setattr(precommit, "_closure_formal_model_lock_module", _fake)
    def git_output(root: Path, *args: str) -> str:
        if args[:2] == ("rev-parse", "HEAD"):
            return "h" * 40 + "\n"
        if args[:2] == ("rev-parse", "h" * 40):
            return "h" * 40 + "\n"
        if args[:2] == ("rev-parse", f"{'h' * 40}^"):
            return SUPERSEDED_H_CHECK_ONLY + "\n"
        if args[:2] == ("rev-parse", SUPERSEDED_H_CHECK_ONLY):
            return SUPERSEDED_H_CHECK_ONLY + "\n"
        if args[:2] == ("rev-parse", f"{SUPERSEDED_H_CHECK_ONLY}^"):
            return SUPERSEDED_H_BATCH + "\n"
        if args[:2] == ("rev-parse", SUPERSEDED_H_BATCH):
            return SUPERSEDED_H_BATCH + "\n"
        if args[:2] == ("rev-parse", f"{SUPERSEDED_H_BATCH}^"):
            return BASE_PREREQUISITE + "\n"
        if args[0] == "diff-tree":
            return _name_status(
                H_SCOPE
                if args[-1] == SUPERSEDED_H_BATCH
                else H_CHECK_ONLY_SCOPE
                if args[-1] == SUPERSEDED_H_CHECK_ONLY
                else H_OFFLINE_VALIDATION_SCOPE
            )
        if args[0] == "diff":
            return _name_status(H_SCOPE)
        raise AssertionError(args)

    monkeypatch.setattr(precommit, "_git_output", git_output)
    monkeypatch.setattr(
        precommit,
        "_require_closure_formal_model_lock_unpublished",
        lambda **kwargs: calls.append(kwargs["require_staged"]),
    )
    assert precommit.closure_formal_model_lock_pre_stage_scope(_short(P_SCOPE)) == (
        "P-E0-M",
        tuple(sorted(P_SCOPE)),
    )
    assert calls == [False]


def test_selector_routes_r_only_from_exact_published_h_and_p(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(precommit, "_closure_formal_model_lock_module", _fake)
    h_head = "h" * 40
    p_head = "p" * 40

    def git_output(root: Path, *args: str) -> str:
        if args[:2] == ("rev-parse", "HEAD"):
            return p_head + "\n"
        if args[:2] == ("rev-parse", f"{p_head}^"):
            return h_head + "\n"
        if args[:2] == ("rev-parse", h_head):
            return h_head + "\n"
        if args[:2] == ("rev-parse", f"{h_head}^"):
            return SUPERSEDED_H_CHECK_ONLY + "\n"
        if args[:2] == ("rev-parse", SUPERSEDED_H_CHECK_ONLY):
            return SUPERSEDED_H_CHECK_ONLY + "\n"
        if args[:2] == ("rev-parse", f"{SUPERSEDED_H_CHECK_ONLY}^"):
            return SUPERSEDED_H_BATCH + "\n"
        if args[:2] == ("rev-parse", SUPERSEDED_H_BATCH):
            return SUPERSEDED_H_BATCH + "\n"
        if args[:2] == ("rev-parse", f"{SUPERSEDED_H_BATCH}^"):
            return BASE_PREREQUISITE + "\n"
        if args[0] == "diff-tree":
            return _name_status(
                H_SCOPE
                if args[-1] == SUPERSEDED_H_BATCH
                else H_CHECK_ONLY_SCOPE
                if args[-1] == SUPERSEDED_H_CHECK_ONLY
                else H_OFFLINE_VALIDATION_SCOPE
                if args[-1] == h_head
                else P_SCOPE
            )
        if args[0] == "diff":
            return _name_status(H_SCOPE)
        raise AssertionError(args)

    monkeypatch.setattr(precommit, "_git_output", git_output)
    monkeypatch.setattr(
        precommit,
        "_require_closure_formal_model_lock_authority",
        lambda **kwargs: _effective(
            h_batch_head=h_head,
            p_patch_head=p_head,
            r_state="complete",
            r_stage_state="exact5_untracked",
            formal_lock_execution_authorized=False,
        ),
    )
    monkeypatch.setattr(
        precommit,
        "_require_closure_formal_model_lock_bundle",
        lambda **kwargs: calls.append(f"bundle:{kwargs['require_staged']}")
        or _bundle(staged=kwargs["require_staged"]),
    )
    assert precommit.closure_formal_model_lock_pre_stage_scope(_short(R_SCOPE)) == (
        "R-E0-M",
        tuple(sorted(R_SCOPE)),
    )
    assert calls == ["bundle:False"]


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
    for gate in (
        "H-E0-MBATCH",
        "H-E0-MBATCHP1",
        "H-E0-MBATCHP2",
        "P-E0-M",
        "R-E0-M",
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
        ("H-E0-MBATCH", H_SCOPE),
        ("H-E0-MBATCHP1", H_CHECK_ONLY_SCOPE),
        ("H-E0-MBATCHP2", H_OFFLINE_VALIDATION_SCOPE),
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
            gate="H-E0-MBATCH"
        )
    ) == 17
    assert len(
        precommit.validate_closure_formal_model_lock_staged_bindings(
            gate="H-E0-MBATCHP1"
        )
    ) == 5
    assert len(
        precommit.validate_closure_formal_model_lock_staged_bindings(
            gate="H-E0-MBATCHP2"
        )
    ) == 5


def test_h_stage_base_requires_exact_prerequisite_and_prelock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    patch = _fake()
    monkeypatch.setattr(
        precommit, "_git_output", lambda *a, **k: BASE_PREREQUISITE + "\n"
    )
    monkeypatch.setattr(
        precommit,
        "_require_closure_formal_model_lock_prelock",
        lambda **kwargs: calls.append("prelock"),
    )
    precommit._require_closure_formal_model_lock_stage_base(
        "H-E0-MBATCH", patch=patch, repo_root=Path(".")
    )
    def correction_git_output(root: Path, *args: str) -> str:
        if args[:2] == ("rev-parse", "HEAD"):
            return SUPERSEDED_H_BATCH + "\n"
        if args[:2] == ("rev-parse", SUPERSEDED_H_BATCH):
            return SUPERSEDED_H_BATCH + "\n"
        if args[:2] == ("rev-parse", f"{SUPERSEDED_H_BATCH}^"):
            return BASE_PREREQUISITE + "\n"
        if args[0] == "diff-tree":
            return _name_status(H_SCOPE)
        raise AssertionError(args)

    monkeypatch.setattr(precommit, "_git_output", correction_git_output)
    monkeypatch.setattr(
        precommit,
        "_require_closure_formal_model_lock_unpublished",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("H correction opened P")
        ),
    )
    monkeypatch.setattr(
        precommit,
        "_require_closure_formal_model_lock_authority",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("H correction opened authority")
        ),
    )
    monkeypatch.setattr(
        precommit,
        "_require_closure_formal_model_lock_bundle",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("H correction opened R")
        ),
    )
    precommit._require_closure_formal_model_lock_stage_base(
        "H-E0-MBATCHP1", patch=patch, repo_root=Path(".")
    )

    def offline_validation_git_output(root: Path, *args: str) -> str:
        if args[:2] == ("rev-parse", "HEAD"):
            return SUPERSEDED_H_CHECK_ONLY + "\n"
        if args[:2] == ("rev-parse", SUPERSEDED_H_CHECK_ONLY):
            return SUPERSEDED_H_CHECK_ONLY + "\n"
        if args[:2] == ("rev-parse", f"{SUPERSEDED_H_CHECK_ONLY}^"):
            return SUPERSEDED_H_BATCH + "\n"
        if args[:2] == ("rev-parse", SUPERSEDED_H_BATCH):
            return SUPERSEDED_H_BATCH + "\n"
        if args[:2] == ("rev-parse", f"{SUPERSEDED_H_BATCH}^"):
            return BASE_PREREQUISITE + "\n"
        if args[0] == "diff-tree":
            return _name_status(
                H_SCOPE
                if args[-1] == SUPERSEDED_H_BATCH
                else H_CHECK_ONLY_SCOPE
            )
        if args[0] == "diff":
            return _name_status(H_SCOPE)
        raise AssertionError(args)

    monkeypatch.setattr(precommit, "_git_output", offline_validation_git_output)
    precommit._require_closure_formal_model_lock_stage_base(
        "H-E0-MBATCHP2", patch=patch, repo_root=Path(".")
    )
    assert calls == ["prelock", "prelock", "prelock"]


def test_p_stage_base_rejects_topology_drift_before_unpublished(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []
    patch = _fake()

    def git_output(root: Path, *args: str) -> str:
        if args[:2] == ("rev-parse", "HEAD"):
            return SUPERSEDED_H_CHECK_ONLY + "\n"
        if args[:2] == ("rev-parse", SUPERSEDED_H_CHECK_ONLY):
            return SUPERSEDED_H_CHECK_ONLY + "\n"
        if args[:2] == ("rev-parse", f"{SUPERSEDED_H_CHECK_ONLY}^"):
            return SUPERSEDED_H_BATCH + "\n"
        raise AssertionError(args)

    monkeypatch.setattr(precommit, "_git_output", git_output)
    monkeypatch.setattr(
        precommit,
        "_require_closure_formal_model_lock_unpublished",
        lambda **kwargs: calls.append(kwargs["require_staged"]),
    )
    with pytest.raises(
        precommit.ClosureFormalModelLockAdapterError,
        match="direct child",
    ):
        precommit._require_closure_formal_model_lock_stage_base(
            "P-E0-M", patch=patch, repo_root=Path(".")
        )
    assert calls == []

    def reverted_cumulative_git_output(root: Path, *args: str) -> str:
        if args[:2] == ("rev-parse", "HEAD"):
            return "h" * 40 + "\n"
        if args[:2] == ("rev-parse", "h" * 40):
            return "h" * 40 + "\n"
        if args[:2] == ("rev-parse", f"{'h' * 40}^"):
            return SUPERSEDED_H_CHECK_ONLY + "\n"
        if args[0] == "diff-tree":
            return _name_status(H_OFFLINE_VALIDATION_SCOPE)
        if args[0] == "diff":
            reverted = dict(H_SCOPE)
            reverted.pop("docs/closure_v1/E0_M_FORMAL_MODEL_LOCK.md")
            return _name_status(reverted)
        raise AssertionError(args)

    monkeypatch.setattr(precommit, "_git_output", reverted_cumulative_git_output)
    with pytest.raises(
        precommit.ClosureFormalModelLockAdapterError,
        match="cumulative H-E0-MBATCHP2 scope",
    ):
        precommit._require_closure_formal_model_lock_stage_base(
            "P-E0-M", patch=patch, repo_root=Path(".")
        )
    assert calls == []


def test_r_stage_base_rejects_topology_drift_before_authority_or_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    patch = _fake()
    def git_output(root: Path, *args: str) -> str:
        if args[:2] == ("rev-parse", "HEAD"):
            return "p" * 40 + "\n"
        if args[:2] == ("rev-parse", f"{'p' * 40}^"):
            return SUPERSEDED_H_CHECK_ONLY + "\n"
        if args[:2] == ("rev-parse", SUPERSEDED_H_CHECK_ONLY):
            return SUPERSEDED_H_CHECK_ONLY + "\n"
        if args[:2] == ("rev-parse", f"{SUPERSEDED_H_CHECK_ONLY}^"):
            return SUPERSEDED_H_BATCH + "\n"
        if args[0] == "diff-tree":
            return _name_status(P_SCOPE)
        raise AssertionError(args)

    monkeypatch.setattr(precommit, "_git_output", git_output)
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
        precommit.ClosureFormalModelLockAdapterError,
        match="direct child",
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
    )["status"] == "ready_to_lock"
    states = iter((_prelock(), _prelock(formal_output_count=1)))
    patch.collect_formal_model_lock_prelock_state = lambda **kwargs: next(states)
    with pytest.raises(precommit.ClosureFormalModelLockAdapterError):
        precommit._require_closure_formal_model_lock_prelock(
            patch=patch, repo_root=Path(".")
        )


def test_unpublished_effective_bundle_and_pure_r_builder_are_strict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from src.experiments import closure_formal_model_lock as core

    patch = _fake()
    assert precommit._require_closure_formal_model_lock_unpublished(
        patch=patch, repo_root=Path("."), require_staged=True
    )["p_authority_generation_authorized"] is True
    assert precommit._require_closure_formal_model_lock_authority(
        patch=patch, repo_root=Path(".")
    )["formal_lock_execution_authorized"] is True
    assert precommit._require_closure_formal_model_lock_bundle(
        patch=patch, repo_root=Path("."), require_staged=True
    )["e0_m_authorized"] is False
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

    h2_head = "2" * 40
    online_repository = {
        "base_r_mid_commit": BASE_R_MI,
        "base_h_e0_m_prerequisite_commit": BASE_PREREQUISITE,
        "h_batch_head": h2_head,
        "h_state": "published",
        "head": h2_head,
        "main": h2_head,
        "origin_main": h2_head,
        "origin_head": h2_head,
        "remote_main": h2_head,
        "branch": "main",
        "verify_remote": True,
        "workspace_status": [],
    }
    authority_prelock = {
        **_prelock(p_authority_generation_authorized=True),
        "repository": online_repository,
        "h_patch": {
            "components": [
                {
                    "role": "formal_model_lock_locker",
                    "path": core.LOCKER_PATH.as_posix(),
                    "bytes": 1,
                    "sha256": "a" * 64,
                }
            ]
        },
        "runner_readiness": {"status": "ready"},
        "calibration_evidence": {
            "outputs": [],
            "outputs_sha256": core.R8_AUTHORITY_OUTPUTS_SHA256,
        },
        "locked_input_evidence": {},
        "model_policy_evidence": {},
        "formal_outputs": {},
    }
    authority_payload = core.build_formal_model_lock_authority_payload(
        authority_prelock,
        generated_at_utc="2026-08-14T00:00:00+00:00",
        repo_root=tmp_path,
    )

    def reconstructed_prelock(*, verify_remote: bool, **_kwargs: Any) -> dict[str, Any]:
        reconstructed = core._deep_copy(authority_prelock)
        reconstructed["repository"]["verify_remote"] = verify_remote
        return reconstructed

    with monkeypatch.context() as authority_patch:
        authority_patch.setattr(core.mcal, "_load_json_object", lambda *a, **k: {})
        authority_patch.setattr(core.mcal, "validate_json_schema", lambda *a, **k: None)
        authority_patch.setattr(core.mcal, "_entry_exists", lambda *a, **k: False)
        authority_patch.setattr(
            core, "collect_formal_model_lock_prelock_state", reconstructed_prelock
        )
        assert core.validate_formal_model_lock_authority_payload(
            authority_payload, verify_remote=True, repo_root=tmp_path
        ) == authority_payload
        assert core.validate_formal_model_lock_authority_payload(
            authority_payload, verify_remote=False, repo_root=tmp_path
        ) == authority_payload
        for key in ("remote_main", "origin_main", "head"):
            drifted = core._deep_copy(authority_payload)
            drifted["repository"][key] = "f" * 40
            with pytest.raises(
                core.ClosureFormalModelLockError,
                match="semantic reconstruction drifted",
            ):
                core.validate_formal_model_lock_authority_payload(
                    drifted, verify_remote=False, repo_root=tmp_path
                )
        unsealed_remote = core._deep_copy(authority_payload)
        unsealed_remote["repository"]["verify_remote"] = False
        with pytest.raises(
            core.ClosureFormalModelLockError,
            match="must seal successful live-remote verification",
        ):
            core.validate_formal_model_lock_authority_payload(
                unsealed_remote, verify_remote=False, repo_root=tmp_path
            )

    authority_bytes = core._canonical_json_bytes(authority_payload)
    companion = core._expected_authority_companion(
        authority_payload,
        {
            "role": "formal_model_lock_authority",
            "path": core.DEFAULT_AUTHORITY_PATH.as_posix(),
            "bytes": len(authority_bytes),
            "sha256": core._sha256_bytes(authority_bytes),
        },
        repo_root=Path("."),
    )
    assert companion["historical_inputs_sha256"] == (
        core.H_CHECK_ONLY_PATCH_HISTORICAL_INPUTS_SHA256
    )
    assert companion["historical_inputs"] == (
        core._historical_h_check_only_patch_records(Path("."))
    )
    assert len(companion["historical_inputs"]) == 5
    companion_drifts: list[dict[str, Any]] = []
    missing_historical = core._deep_copy(companion)
    missing_historical["historical_inputs"] = missing_historical[
        "historical_inputs"
    ][:-1]
    companion_drifts.append(missing_historical)
    extra_historical = core._deep_copy(companion)
    extra_historical["historical_inputs"].append(
        {**extra_historical["historical_inputs"][0], "path": "foreign.py"}
    )
    companion_drifts.append(extra_historical)
    reordered_historical = core._deep_copy(companion)
    reordered_historical["historical_inputs"].reverse()
    companion_drifts.append(reordered_historical)
    drifted_historical = core._deep_copy(companion)
    drifted_historical["historical_inputs"][0]["sha256"] = "f" * 64
    companion_drifts.append(drifted_historical)
    with monkeypatch.context() as companion_patch:
        companion_patch.setattr(
            core,
            "_repository_state",
            lambda **_kwargs: (
                {"h_state": "published", "h_batch_head": h2_head},
                {},
            ),
        )
        companion_patch.setattr(
            core,
            "_status_map",
            lambda *_args, **_kwargs: {
                path.as_posix(): "??" for path in core.CURRENT_LOCK_PATHS
            },
        )
        companion_patch.setattr(
            core,
            "validate_formal_model_lock_authority_payload",
            lambda *args, **kwargs: dict(authority_payload),
        )
        companion_patch.setattr(
            core,
            "_historical_h_check_only_patch_records",
            lambda *_args, **_kwargs: core._deep_copy(
                companion["historical_inputs"]
            ),
        )
        for drifted_companion in companion_drifts:
            parsed = iter(
                (
                    (authority_payload, authority_bytes, object()),
                    (
                        drifted_companion,
                        core._canonical_json_bytes(drifted_companion),
                        object(),
                    ),
                )
            )
            companion_patch.setattr(
                core, "_parse_canonical_json", lambda *a, **k: next(parsed)
            )
            with pytest.raises(
                core.ClosureFormalModelLockError,
                match="unpublished P companion drifted",
            ):
                core.validate_formal_model_lock_unpublished_authority_bundle(
                    verify_remote=False, repo_root=tmp_path
                )

    adapter_calls: list[str] = []
    dialect_patch = _fake(
        require_formal_model_lock_authority=lambda **kwargs: (
            adapter_calls.append("authority")
            or _effective(
                r_state="complete",
                r_stage_state="exact5_staged",
                formal_lock_execution_authorized=False,
            )
        ),
        validate_formal_model_lock_bundle=lambda **kwargs: (
            adapter_calls.append(f"bundle:{kwargs['require_staged']}")
            or _bundle(staged=kwargs["require_staged"])
        ),
    )
    monkeypatch.setattr(
        precommit, "_closure_formal_model_lock_module", lambda: dialect_patch
    )
    generic_ok = precommit.ReproducibilityFinding("ok", "dvc", "-", "clean")
    exact_failures = [
        precommit.ReproducibilityFinding(**record)
        for record in dialect_patch.GENERIC_MANIFEST_FINDINGS_CONTRACT
    ]
    adopted = precommit.adopt_closure_formal_model_lock_findings(
        [generic_ok, *reversed(exact_failures)],
        staged_status=_name_status(R_SCOPE),
    )
    assert adopted[0] == generic_ok
    assert adopted[-1].level == "ok"
    assert adopted[-1].check == "formal_model_lock_dialect"
    assert adapter_calls == ["authority", "bundle:True"]
    adversarial_multisets = (
        [generic_ok, exact_failures[0]],
        [generic_ok, *exact_failures, exact_failures[0]],
        [
            generic_ok,
            *exact_failures,
            precommit.ReproducibilityFinding("warn", "manifest", "x", "x"),
        ],
        [
            generic_ok,
            precommit.ReproducibilityFinding(
                "warn",
                exact_failures[0].check,
                exact_failures[0].path,
                exact_failures[0].message,
            ),
            exact_failures[1],
        ],
        [
            generic_ok,
            precommit.ReproducibilityFinding(
                exact_failures[0].level,
                "script",
                exact_failures[0].path,
                exact_failures[0].message,
            ),
            exact_failures[1],
        ],
        [
            generic_ok,
            precommit.ReproducibilityFinding(
                exact_failures[0].level,
                exact_failures[0].check,
                "foreign.csv",
                exact_failures[0].message,
            ),
            exact_failures[1],
        ],
        [
            generic_ok,
            precommit.ReproducibilityFinding(
                exact_failures[0].level,
                exact_failures[0].check,
                exact_failures[0].path,
                "foreign message",
            ),
            exact_failures[1],
        ],
    )
    for observed in adversarial_multisets:
        rejected = precommit.adopt_closure_formal_model_lock_findings(
            observed,
            staged_status=_name_status(R_SCOPE),
        )
        assert rejected[:-1] == observed
        assert rejected[-1].level == "fail"
        assert rejected[-1].check == "formal_model_lock_dialect"

    model_availability = [
        {"model_id": model_id, "availability": availability}
        for model_id, availability in core.runner.CURRENT_MODEL_AVAILABILITY.items()
    ]
    content_record = {
        "role": "holdout_leakage_audit",
        "path": core.HOLDOUT_LEAKAGE_AUDIT_PATH.as_posix(),
        "bytes": 1,
        "sha256": "a" * 64,
        "mode": 0o644,
        "git_oid": "b" * 40,
        "git_mode": "100644",
        "git_commit": "a" * 40,
    }
    scientific_commits: list[str | None] = []
    monkeypatch.setattr(
        core,
        "_model_availability_records",
        lambda root, *, git_commit=None: (
            scientific_commits.append(git_commit)
            or (model_availability, {**content_record, "role": "availability"})
        ),
    )
    monkeypatch.setattr(
        core,
        "_model_manifest_inventory",
        lambda root, *, git_commit=None: (
            scientific_commits.append(git_commit)
            or {"manifest_count": 0, "artifact_count": 0}
        ),
    )
    monkeypatch.setattr(
        core.mcal,
        "_load_json_object",
        lambda *a, **k: {
            "status": "passed",
            "future_outcomes_accessed": False,
            "selected_internal_holdout_locations": 88,
            "checks": {"locked": True},
        },
    )
    monkeypatch.setattr(
        core,
        "_read_scientific_git_bytes_and_record",
        lambda *a, git_commit, **k: (
            scientific_commits.append(git_commit)
            or (
                json.dumps(
                    {
                        "status": "passed",
                        "future_outcomes_accessed": False,
                        "selected_internal_holdout_locations": 88,
                        "checks": {"locked": True},
                    }
                ).encode(),
                content_record,
            )
        ),
    )
    monkeypatch.setattr(
        core.runner,
        "runner_source_record",
        lambda **k: {"path": core.RUNNER_PATH.as_posix(), "sha256": "b" * 64},
    )
    outputs = core._build_formal_output_bytes(
        {
            "h_batch_head": "b" * 40,
            "p_patch_head": "a" * 40,
            "calibration_evidence": {"status": "sealed"},
        },
        repo_root=Path("."),
    )
    assert tuple(path for path, _payload in outputs) == core.FORMAL_OUTPUT_PATHS
    assert outputs[3] == (core.OUTCOME_ACCESS_LOG_PATH, b"")
    model_lock = json.loads(outputs[-1][1])
    assert model_lock["status"] == "completed_unpublished"
    assert model_lock["manifest_written_last"] is True
    assert model_lock["e0_m_authorized"] is False
    assert model_lock["e0_m_effective_after_publication"] is True
    assert model_lock["outcome_access_log_state"] == "present_empty"
    assert model_lock["outcome_access_log_record_count"] == 0
    assert model_lock["e0_u_authorized"] is False
    assert model_lock["evaluation_authorized"] is False
    assert scientific_commits == ["a" * 40] * 3

    binding_resolver = core._scientific_binding_commit
    head = "c" * 40
    parent = "a" * 40
    observed_scope: dict[str, Any] = {
        "added": 5,
        "modified": 0,
        "deleted": 0,
        "path_count": 5,
        "paths": sorted(path.as_posix() for path in core.FORMAL_OUTPUT_PATHS),
    }
    monkeypatch.setattr(core.mcal, "_git_head", lambda root: head)
    monkeypatch.setattr(
        core.mcal, "_single_parent", lambda root, commit, context: parent
    )
    monkeypatch.setattr(
        core.mcal, "_git_scope", lambda root, before, after: observed_scope
    )
    assert binding_resolver(tmp_path) == parent
    observed_scope = {
        "added": 2,
        "modified": 0,
        "deleted": 0,
        "path_count": 2,
        "paths": sorted(path.as_posix() for path in core.CURRENT_LOCK_PATHS),
    }
    assert binding_resolver(tmp_path) == head
    monkeypatch.setattr(
        core.mcal,
        "_git_scope",
        lambda *args: (_ for _ in ()).throw(RuntimeError("Git unavailable")),
    )
    with pytest.raises(core.ClosureFormalModelLockError):
        binding_resolver(tmp_path)

    monkeypatch.setattr(core, "_scientific_binding_commit", lambda *a, **k: "a" * 40)
    monkeypatch.setattr(
        core,
        "_scientific_git_record",
        lambda path, *, role, repo_root, git_commit: {
            "role": role,
            "path": path.as_posix(),
            "git_commit": git_commit,
        },
    )
    scientific_snapshot = core._scientific_input_snapshot(Path("."))
    assert len(core.MODEL_MANIFEST_PATHS) == core.MODEL_MANIFEST_COUNT == 28
    assert len(core.MODEL_DVC_POINTER_PATHS) == core.MODEL_DVC_POINTER_COUNT == 10
    assert len(scientific_snapshot) == core.SCIENTIFIC_GIT_INPUT_COUNT == 40
    assert {record["git_commit"] for record in scientific_snapshot} == {"a" * 40}

    execute_source = inspect.getsource(core.execute_formal_model_lock)
    guard_index = execute_source.index("_acquire_publication_guard")
    assert guard_index < execute_source.index("require_formal_model_lock_authority")
    assert guard_index < execute_source.index("_build_formal_output_bytes")
    assert execute_source.count("_require_owned_formal_run_guard") >= 6
    unpublished_source = inspect.getsource(
        core.validate_formal_model_lock_unpublished_authority_bundle
    )
    assert unpublished_source.index("content_before =") < unpublished_source.index(
        "repository_before ="
    ) < unpublished_source.index("content_after =") < unpublished_source.index(
        "repository_after ="
    )

    boundary_events: list[str] = []
    monkeypatch.setattr(
        core,
        "_effective_content_snapshot",
        lambda **kwargs: boundary_events.append("content") or {"sealed": True},
    )
    monkeypatch.setattr(
        core,
        "_effective_repository_snapshot",
        lambda **kwargs: boundary_events.append("repository") or {"refs": "sealed"},
    )
    assert core._effective_boundary_snapshot(
        repo_root=tmp_path,
        verify_remote=False,
        h_head="h" * 40,
        p_head="p" * 40,
        r_head=None,
        r_present=False,
    ) == {"refs": "sealed", "sealed": True}
    assert boundary_events == ["content", "repository", "content", "repository"]

    payload = b"sealed-model-artifact\n"
    regular = tmp_path / "reports" / "artifact.bin"
    regular.parent.mkdir(parents=True)
    regular.write_bytes(payload)
    record = {
        "role": "report",
        "path": "reports/artifact.bin",
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    assert core._validate_manifest_output_record(record, repo_root=tmp_path) == record
    alias = tmp_path / "regular-alias"
    os.link(regular, alias)
    with pytest.raises(core.ClosureFormalModelLockError):
        core._validate_manifest_output_record(record, repo_root=tmp_path)
    alias.unlink()

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "escaped.bin").write_bytes(payload)
    (tmp_path / "symlink-parent").symlink_to(outside, target_is_directory=True)
    with pytest.raises(core.ClosureFormalModelLockError):
        core._validate_manifest_output_record(
            {**record, "path": "symlink-parent/escaped.bin"}, repo_root=tmp_path
        )

    dvc_payload = tmp_path / "data" / "cached.bin"
    dvc_payload.parent.mkdir()
    dvc_payload.write_bytes(payload)
    os.chmod(dvc_payload, 0o444)
    md5 = hashlib.md5(payload, usedforsecurity=False).hexdigest()
    cache = tmp_path / ".dvc" / "cache" / "files" / "md5" / md5[:2] / md5[2:]
    cache.parent.mkdir(parents=True)
    os.link(dvc_payload, cache)
    (tmp_path / "data" / "cached.bin.dvc").write_text(
        "outs:\n"
        f"- md5: {md5}\n"
        f"  size: {len(payload)}\n"
        "  hash: md5\n"
        "  path: cached.bin\n",
        encoding="utf-8",
    )
    dvc_record = {**record, "path": "data/cached.bin"}
    assert core._validate_manifest_output_record(
        dvc_record, repo_root=tmp_path
    ) == dvc_record
    (tmp_path / "data" / "cached.bin.dvc").write_text(
        "outs:\n"
        f"- md5: {'0' * 32}\n"
        f"  size: {len(payload)}\n"
        "  hash: md5\n"
        "  path: cached.bin\n",
        encoding="utf-8",
    )
    with pytest.raises(core.ClosureFormalModelLockError):
        core._validate_manifest_output_record(dvc_record, repo_root=tmp_path)


def test_h_p_r_transactions_revalidate_semantics_and_physical_snapshot(
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
    monkeypatch.setattr(
        precommit, "_git_output", lambda *a, **k: BASE_PREREQUISITE + "\n"
    )
    monkeypatch.setattr(
        precommit, "_require_closure_formal_model_lock_prelock",
        lambda **k: calls.append("h:prelock"),
    )
    monkeypatch.setattr(
        precommit,
        "_require_closure_formal_model_lock_unpublished",
        lambda **k: calls.append(f"p:{k['require_staged']}"),
    )
    monkeypatch.setattr(
        precommit,
        "_require_closure_formal_model_lock_authority",
        lambda **k: calls.append("r:authority"),
    )
    monkeypatch.setattr(
        precommit,
        "_require_closure_formal_model_lock_bundle",
        lambda **k: calls.append(f"r:bundle:{k['require_staged']}"),
    )
    precommit.revalidate_closure_formal_model_lock_transaction(
        gate="H-E0-MBATCH",
        staged_status=_name_status(H_SCOPE),
        expected_physical_snapshot=("physical",),
    )

    def correction_git_output(root: Path, *args: str) -> str:
        if args[:2] == ("rev-parse", "HEAD"):
            return SUPERSEDED_H_BATCH + "\n"
        if args[:2] == ("rev-parse", SUPERSEDED_H_BATCH):
            return SUPERSEDED_H_BATCH + "\n"
        if args[:2] == ("rev-parse", f"{SUPERSEDED_H_BATCH}^"):
            return BASE_PREREQUISITE + "\n"
        if args[0] == "diff-tree":
            return _name_status(H_SCOPE)
        return ""

    monkeypatch.setattr(precommit, "_git_output", correction_git_output)
    precommit.revalidate_closure_formal_model_lock_transaction(
        gate="H-E0-MBATCHP1",
        staged_status=_name_status(H_CHECK_ONLY_SCOPE),
        expected_physical_snapshot=("physical",),
    )

    def offline_validation_git_output(root: Path, *args: str) -> str:
        if args[:2] == ("rev-parse", "HEAD"):
            return SUPERSEDED_H_CHECK_ONLY + "\n"
        if args[:2] == ("rev-parse", SUPERSEDED_H_CHECK_ONLY):
            return SUPERSEDED_H_CHECK_ONLY + "\n"
        if args[:2] == ("rev-parse", f"{SUPERSEDED_H_CHECK_ONLY}^"):
            return SUPERSEDED_H_BATCH + "\n"
        if args[:2] == ("rev-parse", SUPERSEDED_H_BATCH):
            return SUPERSEDED_H_BATCH + "\n"
        if args[:2] == ("rev-parse", f"{SUPERSEDED_H_BATCH}^"):
            return BASE_PREREQUISITE + "\n"
        if args[0] == "diff-tree":
            return _name_status(
                H_SCOPE
                if args[-1] == SUPERSEDED_H_BATCH
                else H_CHECK_ONLY_SCOPE
            )
        if args[0] == "diff":
            return _name_status(H_SCOPE)
        return ""

    monkeypatch.setattr(precommit, "_git_output", offline_validation_git_output)
    precommit.revalidate_closure_formal_model_lock_transaction(
        gate="H-E0-MBATCHP2",
        staged_status=_name_status(H_OFFLINE_VALIDATION_SCOPE),
        expected_physical_snapshot=("physical",),
    )
    monkeypatch.setattr(precommit, "_git_output", lambda *a, **k: "")
    for gate, scope in (("P-E0-M", P_SCOPE), ("R-E0-M", R_SCOPE)):
        precommit.revalidate_closure_formal_model_lock_transaction(
            gate=gate,
            staged_status=_name_status(scope),
            expected_physical_snapshot=("physical",),
        )
    assert calls == [
        "h:prelock",
        "h:prelock",
        "h:prelock",
        "p:True",
        "r:authority",
        "r:bundle:True",
    ]


def test_main_routes_formal_before_mid_and_never_calls_dvc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_dvc(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"formal E0-M touched DVC: {args!r} {kwargs!r}")

    monkeypatch.setattr(precommit, "resolve_dvc_bin", forbidden_dvc)
    monkeypatch.setattr(
        precommit,
        "validate_closure_locked_evaluation_input_dvc_binary",
        forbidden_dvc,
    )
    monkeypatch.setattr(precommit, "dvc_status_json", forbidden_dvc)
    dvc_bin, logical_before = precommit._initialize_precommit_dvc_observation(
        None,
        formal_model_lock_active=True,
        require_locked_input_binary=True,
    )
    assert dvc_bin == precommit.DEFAULT_DVC_BIN.as_posix()
    assert logical_before == {}
    assert precommit._recapture_precommit_dvc_status(
        dvc_bin, formal_model_lock_active=True
    ) == {}

    source = inspect.getsource(precommit.main)
    assert source.index("closure_formal_model_lock_pre_stage_scope") < source.index(
        "closure_locked_evaluation_input_manifest_dialect_pre_stage_scope"
    )
    assert "if formal_model_lock_active:" in source
    assert "validate_closure_formal_model_lock_invocation" in source
    assert "revalidate_closure_formal_model_lock_transaction" in source
    assert source.count("_initialize_precommit_dvc_observation(") == 1
    assert source.count("_recapture_precommit_dvc_status(") == 2
    for closed_inspection in (
        "load_configured_dvc_artifacts",
        "declared_artifacts_missing_pointers",
        "manual_targets = unique_paths",
        "unmanaged_ignored_heavy_paths",
    ):
        assert closed_inspection in source
    assert 'mib_r_gate = final_calibration_stage_gate == "R-E0-MI"' in source
    assert 'final_calibration_stage_gate and selected_dvc_paths' in source
    assert "git\",\n                        \"add\",\n                        \"-A\"" in source
