from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from src.experiments import lock_closure_development_runtime as locker
from src.experiments.closure_development_runtime_lock import DevelopmentRuntimeLockError


def _prelock() -> dict[str, Any]:
    return {
        "runtime": {"implementation_lock": {"dvc_remote_name": "gcsremote"}},
        "locked_repository": {
            "head": "a" * 40,
            "branch": "main",
            "worktree_status": "clean",
            "dirty_paths": [],
        },
        "canonical_origin": {
            "remote_name": "origin",
            "identity_algorithm": "git_remote_host_path_v1_sha256_utf8",
            "identity_sha256": (
                "475fdf8ad6839d3d291010ff999b4e4c0f8604a0e8d8a09fcebe5ccb843d1905"
            ),
            "fetch_url_count": 1,
            "push_url_count": 1,
            "fetch_push_identity_equal": True,
        },
        "locked_parent_publication": {
            "head": "a" * 40,
            "tracking_ref": "origin/main",
            "tracking_oid": "a" * 40,
            "local_tracking_verified": True,
            "remote_ref": "refs/heads/main",
            "remote_oid": "a" * 40,
            "remote_verified": True,
        },
        "runtime_contract": {},
        "components": [],
        "runtime_dependencies": [],
        "parents": [],
        "restored_development_sources": [],
        "common_origin": {
            "dvc": {"pointer_path": "data/closure_v1/common_origin_manifest.parquet.dvc"}
        },
        "expert_state": {
            "dvc": {
                "pointer_path": (
                    "data/closure_v1/development/expert/"
                    "expert_no_current_state.parquet.dvc"
                )
            }
        },
        "planned_artifacts": {
            "count": 201,
            "sha256": "833fe57a573db135357a596949728fd0b6a436997ece0ba2c5555b815a42672c",
            "records": [],
        },
        "environment": {"device": "cpu"},
    }


def _evidence(command: tuple[str, ...]) -> dict[str, Any]:
    return {
        "command": list(command),
        "exit_code": 0,
        "stdout_sha256": "b" * 64,
        "stderr_sha256": "c" * 64,
        "passed": True,
    }


def _dvc_evidence() -> dict[str, Any]:
    return {"dvc_remote_verified_at_lock": True}


def test_parser_requires_explicit_mode_and_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["locker"])
    with pytest.raises(SystemExit):
        locker.build_parser().parse_args()

    args = locker.build_parser().parse_args(["--device", "cpu", "--check-only"])
    assert args.device == "cpu"
    assert args.check_only is True
    assert args.execute_lock is False


def test_check_only_prints_preflight_and_never_runs_commands_or_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "development_runtime_lock.json"
    prelock = _prelock()
    monkeypatch.setattr(locker, "collect_prelock_state", lambda **kwargs: prelock)
    monkeypatch.setattr(
        locker,
        "focused_test_command",
        lambda runtime: ("poetry", "run", "pytest", "tests/test_adapter.py", "-q"),
    )
    monkeypatch.setattr(
        locker,
        "command_evidence",
        lambda command: (_ for _ in ()).throw(AssertionError("verification command ran")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["locker", "--device", "cpu", "--check-only", "--output", str(output)],
    )

    locker.main()

    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "ready_to_lock"
    assert summary["development_fit_authorized"] is False
    assert summary["evaluation_authorized"] is False
    assert summary["e0_u_authorized"] is False
    assert summary["outputs_written"] == []
    assert not output.exists()


def test_real_lock_refuses_existing_output_before_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "development_runtime_lock.json"
    output.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(
        locker,
        "collect_prelock_state",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("preflight ran")),
    )

    with pytest.raises(DevelopmentRuntimeLockError, match="Refusing to overwrite"):
        locker.create_development_runtime_lock(
            runtime_config=Path("runtime.yaml"),
            runtime_schema=Path("runtime.schema.json"),
            lock_schema=Path("lock.schema.json"),
            output=output,
            device="cpu",
            verify_dvc_remote_by_idempotent_push_flag=True,
        )


def test_real_lock_requires_explicit_dvc_remote_verification_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "development_runtime_lock.json"
    monkeypatch.setattr(
        locker,
        "collect_prelock_state",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("preflight ran")),
    )

    with pytest.raises(
        DevelopmentRuntimeLockError,
        match="--verify-dvc-remote-by-idempotent-push",
    ):
        locker.create_development_runtime_lock(
            runtime_config=Path("runtime.yaml"),
            runtime_schema=Path("runtime.schema.json"),
            lock_schema=Path("lock.schema.json"),
            output=output,
            device="cpu",
            verify_dvc_remote_by_idempotent_push_flag=False,
        )

    assert not output.exists()


def test_real_lock_runs_fixed_checks_revalidates_state_and_writes_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "development_runtime_lock.json"
    prelock = _prelock()
    calls: list[str] = []

    def collect(**kwargs: Any) -> dict[str, Any]:
        calls.append("collect")
        return prelock

    def evidence(command: tuple[str, ...]) -> dict[str, Any]:
        calls.append("command:" + " ".join(command))
        return _evidence(command)

    monkeypatch.setattr(locker, "collect_prelock_state", collect)
    monkeypatch.setattr(locker, "command_evidence", evidence)
    monkeypatch.setattr(
        locker,
        "verify_dvc_remote_by_idempotent_push",
        lambda *args: calls.append("dvc-verify") or _dvc_evidence(),
    )
    monkeypatch.setattr(
        locker,
        "focused_test_command",
        lambda runtime: ("poetry", "run", "pytest", "tests/test_adapter.py", "-q"),
    )
    monkeypatch.setattr(locker, "load_json_mapping", lambda _: {})
    monkeypatch.setattr(locker, "validate_development_runtime_lock_payload", lambda *args: None)

    created = locker.create_development_runtime_lock(
        runtime_config=Path("runtime.yaml"),
        runtime_schema=Path("runtime.schema.json"),
        lock_schema=Path("lock.schema.json"),
        output=output,
        device="cpu",
        verify_dvc_remote_by_idempotent_push_flag=True,
    )

    assert created == output
    assert calls == [
        "collect",
        "command:poetry run ty check",
        "command:poetry run pytest tests/test_adapter.py -q",
        "dvc-verify",
        "collect",
    ]
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["lock_version"] == "closure_development_runtime_lock_v1"
    assert payload["authorizations"] == {
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
    }
    assert payload["seals"]["future_outcomes_accessed"] is False
    assert not output.with_suffix(".json.tmp").exists()


def test_real_lock_does_not_write_if_checks_change_prelock_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "development_runtime_lock.json"
    before = _prelock()
    after = _prelock()
    after["locked_repository"] = {**after["locked_repository"], "head": "d" * 40}
    states = iter([before, after])
    monkeypatch.setattr(locker, "collect_prelock_state", lambda **kwargs: next(states))
    monkeypatch.setattr(locker, "command_evidence", lambda command: _evidence(tuple(command)))
    monkeypatch.setattr(
        locker,
        "verify_dvc_remote_by_idempotent_push",
        lambda *args: _dvc_evidence(),
    )
    monkeypatch.setattr(
        locker,
        "focused_test_command",
        lambda runtime: ("poetry", "run", "pytest", "tests/test_adapter.py", "-q"),
    )

    with pytest.raises(DevelopmentRuntimeLockError, match="changed during E0-DL checks"):
        locker.create_development_runtime_lock(
            runtime_config=Path("runtime.yaml"),
            runtime_schema=Path("runtime.schema.json"),
            lock_schema=Path("lock.schema.json"),
            output=output,
            device="cpu",
            verify_dvc_remote_by_idempotent_push_flag=True,
        )

    assert not output.exists()


def test_real_lock_does_not_write_when_dvc_push_was_not_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "development_runtime_lock.json"
    monkeypatch.setattr(locker, "collect_prelock_state", lambda **kwargs: _prelock())
    monkeypatch.setattr(
        locker,
        "command_evidence",
        lambda command: _evidence(tuple(command)),
    )
    monkeypatch.setattr(
        locker,
        "focused_test_command",
        lambda runtime: ("poetry", "run", "pytest", "tests/test_adapter.py", "-q"),
    )
    monkeypatch.setattr(
        locker,
        "verify_dvc_remote_by_idempotent_push",
        lambda *args: (_ for _ in ()).throw(
            DevelopmentRuntimeLockError("objects were uploaded")
        ),
    )

    with pytest.raises(DevelopmentRuntimeLockError, match="uploaded"):
        locker.create_development_runtime_lock(
            runtime_config=Path("runtime.yaml"),
            runtime_schema=Path("runtime.schema.json"),
            lock_schema=Path("lock.schema.json"),
            output=output,
            device="cpu",
            verify_dvc_remote_by_idempotent_push_flag=True,
        )
    assert not output.exists()


def test_atomic_writer_removes_temporary_file_after_serialization_failure(
    tmp_path: Path,
) -> None:
    output = tmp_path / "development_runtime_lock.json"

    with pytest.raises(ValueError):
        locker._write_json_atomic({"non_finite": float("nan")}, output)

    assert not output.exists()
    assert not output.with_suffix(".json.tmp").exists()


def test_create_removes_final_output_if_atomic_writer_raises_after_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "development_runtime_lock.json"
    prelock = _prelock()
    monkeypatch.setattr(locker, "collect_prelock_state", lambda **kwargs: prelock)
    monkeypatch.setattr(locker, "command_evidence", lambda command: _evidence(tuple(command)))
    monkeypatch.setattr(
        locker,
        "verify_dvc_remote_by_idempotent_push",
        lambda *args: _dvc_evidence(),
    )
    monkeypatch.setattr(
        locker,
        "focused_test_command",
        lambda runtime: ("poetry", "run", "pytest", "tests/test_adapter.py", "-q"),
    )
    monkeypatch.setattr(locker, "load_json_mapping", lambda _: {})
    monkeypatch.setattr(locker, "validate_development_runtime_lock_payload", lambda *args: None)

    def partial_write(payload: dict[str, Any], path: Path) -> None:
        path.write_text("partial", encoding="utf-8")
        raise RuntimeError("write failed")

    monkeypatch.setattr(locker, "_write_json_atomic", partial_write)

    with pytest.raises(RuntimeError, match="write failed"):
        locker.create_development_runtime_lock(
            runtime_config=Path("runtime.yaml"),
            runtime_schema=Path("runtime.schema.json"),
            lock_schema=Path("lock.schema.json"),
            output=output,
            device="cpu",
            verify_dvc_remote_by_idempotent_push_flag=True,
        )

    assert not output.exists()
