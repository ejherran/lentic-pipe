from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.experiments import closure_final_calibration as calibration
from src.experiments import lock_closure_final_calibration as locker


ROOT = Path(__file__).resolve().parents[1]


def _schema() -> dict[str, Any]:
    return {"status": "schema_ready", "gate": "E0-MCAL"}


def _prelock() -> dict[str, Any]:
    return {
        "repository": {"head": calibration.BASE_COMMIT},
        "h_patch": {"component_count": 12},
        "runtime_contract": {"physical_input_count": 3},
    }


def _verification() -> dict[str, Any]:
    return {
        "schema_preflight": _schema(),
        "full_type_check": {"returncode": 0},
        "focused_tests": {"returncode": 0, "test_count": 64},
        "poetry_check": {"returncode": 0},
        "publication_guard": {"returncode": 0},
        "git_diff_check": {"returncode": 0},
    }


def test_cli_modes_are_closed_and_mutually_exclusive() -> None:
    assert locker.parse_args(["--check-only"]).check_only is True
    assert locker.parse_args(["--execute-lock"]).execute_lock is True
    assert locker.parse_args(["--check-effective"]).check_effective is True
    for argv in (
        [],
        ["--check-only", "--execute-lock"],
        ["--execute-lock", "--check-effective"],
        ["--unknown"],
    ):
        with pytest.raises(SystemExit):
            locker.parse_args(argv)


def test_main_serializes_success_and_translates_only_domain_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(locker, "check_only", lambda: {"status": "ready_to_lock"})
    assert locker.main(["--check-only"]) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "ready_to_lock"}

    def fail() -> dict[str, Any]:
        raise calibration.FinalCalibrationError("closed")

    monkeypatch.setattr(locker, "execute_lock", fail)
    assert locker.main(["--execute-lock"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "closed"

    monkeypatch.setattr(locker, "check_effective", lambda: (_ for _ in ()).throw(ValueError("foreign")))
    with pytest.raises(ValueError, match="foreign"):
        locker.main(["--check-effective"])


def test_check_only_is_nonwriting_and_delegates_schema_then_prelock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def schema() -> dict[str, Any]:
        calls.append("schema")
        return _schema()

    def prelock(*, verify_remote: bool) -> dict[str, Any]:
        assert verify_remote is True
        calls.append("prelock")
        return _prelock()

    monkeypatch.setattr(calibration, "preflight_final_calibration_schema", schema)
    monkeypatch.setattr(calibration, "collect_final_calibration_prelock_state", prelock)
    result = locker.check_only()
    assert calls == ["schema", "prelock"]
    assert result["status"] == "ready_to_lock"
    assert result["component_count"] == 12
    for key in (
        "writes_performed",
        "verification_commands_run",
        "calibration_run",
        "learning_curve_run",
        "dvc_commands_run",
        "scientific_network_commands_run",
        "future_outcomes_accessed",
    ):
        assert result[key] is False


def test_check_only_fails_closed_on_missing_exact_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(calibration, "preflight_final_calibration_schema", _schema)
    monkeypatch.setattr(
        calibration,
        "collect_final_calibration_prelock_state",
        lambda **_: {"repository": {}, "h_patch": {}, "runtime_contract": {}},
    )
    with pytest.raises(KeyError):
        locker.check_only()


def test_execute_lock_linearizes_validation_before_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    prelock = _prelock()
    payload = {"gate": "E0-MCAL"}
    lock = {"path": "lock"}
    companion = {"path": "companion"}
    monkeypatch.setattr(calibration, "preflight_final_calibration_schema", lambda: _schema())

    def collect(*, verify_remote: bool) -> dict[str, Any]:
        assert verify_remote is True
        calls.append("collect")
        return prelock

    monkeypatch.setattr(calibration, "collect_final_calibration_prelock_state", collect)
    monkeypatch.setattr(
        locker,
        "run_final_calibration_verification",
        lambda **_: calls.append("verify") or _verification(),
    )

    def build(**kwargs: Any) -> dict[str, Any]:
        assert kwargs == {"prelock": prelock, "verification": _verification()}
        calls.append("build")
        return payload

    monkeypatch.setattr(calibration, "build_final_calibration_lock_payload", build)
    monkeypatch.setattr(
        calibration,
        "validate_final_calibration_lock_payload",
        lambda value: calls.append("validate") if value is payload else None,
    )
    monkeypatch.setattr(
        calibration,
        "publish_final_calibration_lock_bundle",
        lambda value: (calls.append("publish") or (lock, companion))
        if value is payload
        else (_ for _ in ()).throw(AssertionError),
    )
    result = locker.execute_lock()
    assert calls == ["collect", "verify", "collect", "build", "validate", "publish"]
    assert result["status"] == "locked_unpublished"
    assert result["lock"] is lock
    assert result["companion"] is companion


def test_execute_lock_rejects_prelock_drift_before_build_or_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    states = [_prelock(), {**_prelock(), "drift": True}]
    monkeypatch.setattr(calibration, "preflight_final_calibration_schema", lambda: _schema())
    monkeypatch.setattr(
        calibration,
        "collect_final_calibration_prelock_state",
        lambda **_: states.pop(0),
    )
    monkeypatch.setattr(locker, "run_final_calibration_verification", lambda **_: _verification())
    monkeypatch.setattr(
        calibration,
        "build_final_calibration_lock_payload",
        lambda **_: (_ for _ in ()).throw(AssertionError("build reached")),
    )
    with pytest.raises(calibration.FinalCalibrationError, match="changed"):
        locker.execute_lock()


def test_verification_runs_only_the_five_frozen_commands_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def run(command: tuple[str, ...], **_: Any) -> tuple[dict[str, Any], str, str]:
        calls.append(tuple(command))
        if tuple(command) == tuple(calibration.TYPE_CHECK_COMMAND):
            output = "All checks passed!\n"
        elif tuple(command) == tuple(calibration.FOCUSED_TEST_COMMAND):
            output = f"{calibration.FOCUSED_TEST_COUNT} passed in 1.00s\n"
        elif tuple(command) == tuple(calibration.POETRY_CHECK_COMMAND):
            output = "All set!\n"
        elif tuple(command) == tuple(calibration.PUBLICATION_GUARD_COMMAND):
            output = (
                "Checking tracked files before publication...\n"
                "OK: tracked files look publication-ready.\n"
            )
        else:
            output = ""
        return {"command": list(command), "returncode": 0}, output, ""

    monkeypatch.setattr(locker, "_run_command", run)
    monkeypatch.setattr(calibration, "preflight_final_calibration_schema", lambda: _schema())
    result = locker.run_final_calibration_verification(
        expected_schema_preflight=_schema()
    )
    assert calls == [
        tuple(calibration.TYPE_CHECK_COMMAND),
        tuple(calibration.FOCUSED_TEST_COMMAND),
        tuple(calibration.POETRY_CHECK_COMMAND),
        tuple(calibration.PUBLICATION_GUARD_COMMAND),
        tuple(calibration.DIFF_CHECK_COMMAND),
    ]
    assert result["focused_tests"]["test_count"] == 64


def test_verification_rejects_schema_drift_before_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        calibration,
        "preflight_final_calibration_schema",
        lambda: {"status": "drift"},
    )
    monkeypatch.setattr(
        locker,
        "_run_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("command ran")),
    )
    with pytest.raises(calibration.FinalCalibrationError, match="schema changed"):
        locker.run_final_calibration_verification(
            expected_schema_preflight=_schema()
        )


def test_focused_summary_accepts_only_exact_clean_frozen_count() -> None:
    assert locker._parse_focused_summary("64 passed in 0.01s\n", "") == {
        "test_count": 64,
        "skipped_count": 0,
        "deselected_count": 0,
    }
    for stdout, stderr in (
        ("275 passed in 0.01s\n", ""),
        ("64 passed, 1 skipped in 0.01s\n", ""),
        ("64 passed in 0.01s\nextra\n", ""),
        ("64 passed in 0.01s\n", "warning"),
        ("", ""),
    ):
        with pytest.raises(calibration.FinalCalibrationError):
            locker._parse_focused_summary(stdout, stderr)


def test_run_command_sanitizes_only_pytest_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, str] = {}

    def run(*_args: Any, **kwargs: Any) -> SimpleNamespace:
        observed.update(kwargs["env"])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setenv("PYTEST_ADDOPTS", "--collect-only")
    monkeypatch.setenv("E0_MCAL_SENTINEL", "kept")
    monkeypatch.setattr(locker.subprocess, "run", run)
    locker._run_command(("pytest",), sanitize_pytest_environment=True)
    assert "PYTEST_ADDOPTS" not in observed
    assert observed["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert observed["E0_MCAL_SENTINEL"] == "kept"


def test_run_command_uses_closed_cwd_capture_and_no_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def run(*args: Any, **kwargs: Any) -> SimpleNamespace:
        observed["args"] = args
        observed.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(locker.subprocess, "run", run)
    evidence, stdout, stderr = locker._run_command(("tool", "arg"))
    assert observed["args"] == (["tool", "arg"],)
    assert observed["cwd"] == locker.PROJECT_ROOT
    assert observed["capture_output"] is True
    assert "shell" not in observed
    assert (stdout, stderr) == ("ok\n", "")
    assert evidence["returncode"] == 0


def test_run_command_translates_nonzero_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def run(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        return SimpleNamespace(returncode=7, stdout="out", stderr="err")

    monkeypatch.setattr(locker.subprocess, "run", run)
    with pytest.raises(calibration.FinalCalibrationError, match=r"failed \(7\)"):
        locker._run_command(("tool",))
    assert calls == 1


def test_success_markers_and_publication_output_are_exact() -> None:
    locker._require_marker("All checks passed!", "", "All checks passed!", context="ty")
    locker._require_empty_output("", "", context="diff")
    locker._require_publication_guard_success(
        "Checking tracked files before publication...\n"
        "OK: tracked files look publication-ready.\n",
        "",
    )
    for call in (
        lambda: locker._require_marker("", "", "ok", context="x"),
        lambda: locker._require_empty_output("noise", "", context="x"),
        lambda: locker._require_publication_guard_success("OK\n", ""),
    ):
        with pytest.raises(calibration.FinalCalibrationError):
            call()


def test_check_effective_delegates_to_strict_remote_loader_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []
    authority = {"gate": "E0-MCAL", "status": "effective"}

    def load(*, verify_remote: bool) -> dict[str, Any]:
        calls.append(verify_remote)
        return authority

    monkeypatch.setattr(calibration, "load_effective_final_calibration_authority", load)
    assert locker.check_effective() is authority
    assert calls == [True]


def test_execute_result_never_claims_calibration_outcomes_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(calibration, "preflight_final_calibration_schema", lambda: _schema())
    monkeypatch.setattr(calibration, "collect_final_calibration_prelock_state", lambda **_: _prelock())
    monkeypatch.setattr(locker, "run_final_calibration_verification", lambda **_: _verification())
    monkeypatch.setattr(calibration, "build_final_calibration_lock_payload", lambda **_: {})
    monkeypatch.setattr(calibration, "validate_final_calibration_lock_payload", lambda _value: None)
    monkeypatch.setattr(calibration, "publish_final_calibration_lock_bundle", lambda _value: ({}, {}))
    result = locker.execute_lock()
    assert result["status"] == "locked_unpublished"
    for key in (
        "calibration_run",
        "learning_curve_run",
        "dvc_commands_run",
        "scientific_network_commands_run",
        "future_outcomes_accessed",
    ):
        assert result[key] is False


def test_locker_source_contains_no_scientific_or_dvc_entrypoint() -> None:
    source = inspect.getsource(locker)
    assert "read_parquet" not in source
    assert "dvc add" not in source
    assert "dvc push" not in source
    assert "execute_one_shot" not in source
    assert "--check-only" in source
    assert "--execute-lock" in source
    assert "--check-effective" in source
