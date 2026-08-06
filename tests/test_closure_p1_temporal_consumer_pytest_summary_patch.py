from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from src.experiments import (
    closure_p1_temporal_consumer_pytest_summary_patch as module,
)
from src.experiments import (
    lock_closure_p1_temporal_consumer_pytest_summary_patch as locker,
)


ZERO_SHA = "0" * 64
PATCH_HEAD = "a" * 40
LOCK_COMMIT = "b" * 40


def _record(path: str, role: str, *, size: int = 1) -> dict[str, Any]:
    return {
        "path": path,
        "role": role,
        "bytes": size,
        "sha256": ZERO_SHA,
    }


def _identity() -> dict[str, Any]:
    record = _record(
        module.AUDITOR_SOURCE_PATH,
        "p1_sequence_bundle_auditor_callable",
    )
    return {
        "module": module.AUDITOR_MODULE,
        "name": module.AUDITOR_NAME,
        "qualname": module.AUDITOR_QUALNAME,
        "source_path": module.AUDITOR_SOURCE_PATH,
        "code_filename": module.AUDITOR_SOURCE_PATH,
        "git_commit": module.P1_BUNDLE_COMMIT,
        "git_source_record": record,
        "physical_source_record": record,
    }


def _audit_result() -> dict[str, Any]:
    return {
        "audit_version": module.p1_audit.AUDIT_VERSION,
        "status": "validated",
        "model_id": "P1",
        "base_seed": 1729,
        "counts": {
            "intent_origins": 9_732,
            "successful_origins": 9_227,
            "failed_origins": 505,
        },
        "fit_availability": {
            "available": False,
            "observed_fit_status_counts": {
                "success": 8_925,
                "autoregressive_target_unavailable": 488,
            },
            "observed_fit_failure_reason_counts": {
                "missing_target_state": 488,
            },
            "observed_calibration_failure_count": 17,
            "expected_temporal_slot_status": "model_unavailable",
            "expected_fit_status": "not_attempted",
            "expected_failure_reason": "sequence_fit_rows_unavailable",
            "consumer_executed_by_auditor": False,
            "fit_or_model_construction_executed_by_auditor": False,
        },
        "audited_namespaces_unchanged": True,
        "one_shot_reconsumed_by_auditor": False,
        "builder_cli_executed": False,
        "effective_loader_called_by_auditor": False,
        "fit_or_model_construction_executed_by_auditor": False,
        "dvc_operation_executed_by_auditor": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "bundle_future_outcomes_accessed": False,
        "future_outcomes_accessed_by_auditor": False,
    }


def _command_evidence(command: tuple[str, ...]) -> dict[str, Any]:
    return {
        "command": list(command),
        "returncode": 0,
        "stdout_sha256": ZERO_SHA,
        "stderr_sha256": ZERO_SHA,
        "stdout_line_count": 0,
        "stderr_line_count": 0,
    }


def _effective_summary() -> dict[str, Any]:
    return {
        "publication_verified": True,
        "remote_publication_verified": True,
        "historical_e0_me_verified": True,
        "historical_me_effective_loader_called": False,
        "p_e0_me_absent": True,
        "pytest_summary_parser_corrected": True,
        "historical_e0_md_verified": True,
        "historical_e0_dltvm_verified": True,
        "historical_dltvm_effective_loader_called": False,
        "p_e0_md_absent": True,
        "p1_sequence_bundle_verified": True,
        "in_process_audit_verified": True,
        "in_process_audit_evidence": {"status": "validated"},
        "consumer_namespace_absent": True,
        "authorization_effective": True,
        "p1_consumer_authorized": True,
        "p1_fit_authorized": True,
        "sequence_fit_available": False,
        "python_auditor_subprocess_used": False,
        "batch_seed_execution_authorized": False,
        "retry_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "fit_availability": dict(module.FIT_AVAILABILITY),
        "e0_me_context_authorization": {
            "gate": "E0-ME",
            "p_e0_me_absent": True,
            "historical_git_authority_verified": True,
            "historical_e0_md_verified": True,
            "historical_e0_dltvm_verified": True,
            "historical_me_effective_loader_called": False,
            "effective_loader_called": False,
        },
        "e0_md_context_authorization": {
            "gate": "E0-MD",
            "historical_e0_dltvm_verified": True,
            "historical_dltvm_effective_loader_called": False,
        },
        "e0_mc_context_authorization": {"gate": "E0-MC"},
    }


def test_closed_scope_is_exact_two_modifications_and_five_additions() -> None:
    assert module.PATCH_BASE_COMMIT == module.H_E0_ME_COMMIT
    assert module.PATCH_MODIFIED_PATHS == (
        "src/experiments/train_closure_pipe.py",
        "tests/test_train_closure_pipe.py",
    )
    assert len(module.PATCH_ADDED_PATHS) == 5
    assert len(module.PATCH_PATHS) == 7
    assert set(module.PATCH_ADDED_PATHS).isdisjoint(module.PATCH_MODIFIED_PATHS)
    assert module.FOCUSED_TEST_COUNT == 262


def test_schema_is_strict_and_closes_callable_evidence() -> None:
    schema = json.loads(module.DEFAULT_PATCH_LOCK_SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["gate"] == {"const": "E0-MF"}
    audit = schema["$defs"]["auditEvidence"]
    assert audit["additionalProperties"] is False
    assert {
        "callable_module",
        "callable_name",
        "callable_qualname",
        "callable_source_path",
        "callable_code_filename",
        "callable_git_commit",
        "callable_source_git",
        "callable_source_physical",
        "result_bytes",
        "result_sha256",
    }.issubset(audit["required"])
    correction = schema["properties"]["correction"]
    correction_flags = {
        "failed_execute_lock_authorization_consumed": True,
        "failed_execute_lock_process_started": True,
        "failed_execute_lock_prelock_completed": True,
        "failed_execute_lock_guards_acquired": True,
        "failed_execute_lock_guards_rolled_back": True,
        "failed_execute_lock_full_type_check_run": True,
        "failed_execute_lock_full_type_check_passed": True,
        "failed_execute_lock_focused_pytest_run": True,
        "failed_execute_lock_focused_pytest_returncode_zero": True,
        "failed_execute_lock_focused_pytest_parser_rejected": True,
        "failed_execute_lock_focused_pytest_stdout_preserved": False,
        "failed_execute_lock_poetry_check_run": False,
        "failed_execute_lock_publication_guard_run": False,
        "failed_execute_lock_diff_check_run": False,
        "failed_execute_lock_in_process_audit_run": False,
        "failed_execute_lock_dvc_commands_run": False,
        "failed_execute_lock_payload_built": False,
        "failed_execute_lock_outputs_written": False,
    }
    assert set(correction_flags).issubset(correction["required"])
    for field, value in correction_flags.items():
        assert correction["properties"][field] == {"const": value}


def test_patch_git_diff_requires_exact_direct_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_require_commit", lambda value, **_: value)
    monkeypatch.setattr(
        module,
        "_git",
        lambda *args: f"{PATCH_HEAD} {module.PATCH_BASE_COMMIT}",
    )
    expected = [
        {
            "status": "M" if path in module.PATCH_MODIFIED_PATHS else "A",
            "path": path,
        }
        for path in module.PATCH_PATHS
    ]
    monkeypatch.setattr(module, "_observed_diff_entries", lambda *args: expected)
    observed = module.patch_git_diff_payload(PATCH_HEAD)
    assert observed["entries"] == expected
    assert observed["modified_count"] == 2
    assert observed["added_count"] == 5


def test_patch_git_diff_rejects_scope_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_require_commit", lambda value, **_: value)
    monkeypatch.setattr(
        module,
        "_git",
        lambda *args: f"{PATCH_HEAD} {module.PATCH_BASE_COMMIT}",
    )
    monkeypatch.setattr(
        module,
        "_observed_diff_entries",
        lambda *args: [{"status": "A", "path": "unexpected"}],
    )
    with pytest.raises(
        module.P1TemporalConsumerPytestSummaryPatchError,
        match=r"2M\+5A",
    ):
        module.patch_git_diff_payload(PATCH_HEAD)


def test_historical_me_partition_is_exact_and_p_me_is_not_synthesized() -> None:
    assert module.ME_SUPERSEDED_PATHS == module.PATCH_MODIFIED_PATHS
    assert len(module.ME_SUPERSEDED_PATHS) == 2
    assert len(module.ME_PRESERVED_PATHS) == 5
    assert set(module.ME_SUPERSEDED_PATHS).isdisjoint(module.ME_PRESERVED_PATHS)
    source = inspect.getsource(module._historical_e0_me_authority)
    assert "load_and_validate_p1_temporal_consumer_verification_patch_lock" not in source


def test_historical_me_authority_reconstructs_md_without_effective_me_loader() -> None:
    execution_head = module._require_commit(
        module._git("rev-parse", "HEAD"),
        context="test execution HEAD",
    )
    authority = module._historical_e0_me_authority(execution_head=execution_head)
    context = authority["e0_me_context_authorization"]
    assert authority["gate"] == "E0-ME"
    assert authority["e0_md"]["gate"] == "E0-MD"
    assert authority["effective_loader_called"] is False
    assert context["historical_e0_md_verified"] is True
    assert context["historical_me_effective_loader_called"] is False


def test_p_e0_me_absence_rejects_broken_symlink(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    path = tmp_path / module.e0_me.DEFAULT_PATCH_LOCK_PATH
    path.parent.mkdir(parents=True)
    path.symlink_to(path.parent / "missing")
    assert not path.exists()
    monkeypatch.setattr(module, "_git", lambda *args: "")
    with pytest.raises(
        module.P1TemporalConsumerPytestSummaryPatchError,
        match="physically absent",
    ):
        module._assert_p_e0_me_absent()


def test_p_e0_me_absence_rejects_git_introduction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "_git", lambda *args: PATCH_HEAD)
    with pytest.raises(
        module.P1TemporalConsumerPytestSummaryPatchError,
        match="Git history",
    ):
        module._assert_p_e0_me_absent()


def test_auditor_callable_identity_is_fixed_to_published_source() -> None:
    identity = module._auditor_identity_record()
    assert identity["module"] == module.AUDITOR_MODULE
    assert identity["name"] == module.AUDITOR_NAME
    assert identity["qualname"] == module.AUDITOR_QUALNAME
    assert identity["source_path"] == module.AUDITOR_SOURCE_PATH
    assert identity["code_filename"] == module.AUDITOR_SOURCE_PATH
    assert identity["git_source_record"] == identity["physical_source_record"]


def test_closed_audit_evidence_is_canonical_and_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_auditor_identity_record", _identity)
    result = _audit_result()
    encoded = json.dumps(
        result,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    evidence = module._closed_audit_evidence(result)
    assert evidence["status"] == "validated"
    assert evidence["intent_origins"] == 9_732
    assert evidence["successful_origins"] == 9_227
    assert evidence["failed_origins"] == 505
    assert evidence["fit_successful_origins"] == 8_925
    assert evidence["fit_unavailable_origins"] == 488
    assert evidence["calibration_unavailable_origins"] == 17
    assert evidence["result_bytes"] == len(encoded)
    assert evidence["result_sha256"] == hashlib.sha256(encoded).hexdigest()


def test_closed_audit_evidence_rejects_count_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_auditor_identity_record", _identity)
    result = _audit_result()
    result["counts"]["successful_origins"] = 9_226
    with pytest.raises(
        module.P1TemporalConsumerPytestSummaryPatchError,
        match="closed counts drifted",
    ):
        module._closed_audit_evidence(result)


def test_closed_audit_evidence_rejects_noncanonical_nan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_auditor_identity_record", _identity)
    result = _audit_result()
    result["unexpected_nonfinite"] = float("nan")
    with pytest.raises(
        module.P1TemporalConsumerPytestSummaryPatchError,
        match="not canonical JSON",
    ):
        module._closed_audit_evidence(result)


def test_in_process_audit_calls_fixed_callable_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    def identity() -> dict[str, Any]:
        events.append("identity")
        return _identity()

    def audit() -> dict[str, Any]:
        events.append("audit")
        return _audit_result()

    monkeypatch.setattr(module, "_auditor_identity_record", identity)
    monkeypatch.setattr(module.p1_audit, "audit_p1_sequence_bundle", audit)
    evidence = module.run_p1_bundle_audit_in_process()
    assert events == ["identity", "audit", "identity"]
    assert evidence["execution_mode"] == "in_process_callable"
    assert not hasattr(module, "P1_AUDIT_COMMAND")


def test_in_process_audit_rejects_replaced_callable_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def replacement() -> dict[str, Any]:
        return _audit_result()

    monkeypatch.setattr(module.p1_audit, "audit_p1_sequence_bundle", replacement)
    with pytest.raises(
        module.P1TemporalConsumerPytestSummaryPatchError,
        match="callable identity drifted",
    ):
        module.run_p1_bundle_audit_in_process()


def test_verification_preflights_only_ty_pytest_and_dvc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preflighted: list[tuple[str, ...]] = []
    commands: list[tuple[str, ...]] = []
    dvc_calls = 0

    monkeypatch.setattr(locker, "FOCUSED_TEST_COUNT", 1)
    monkeypatch.setattr(
        locker.hardened,
        "_require_fixed_venv_executable",
        lambda command: preflighted.append(tuple(command)),
    )

    def run(
        command: tuple[str, ...],
        **_: Any,
    ) -> tuple[dict[str, Any], str, str]:
        nonlocal dvc_calls
        commands.append(tuple(command))
        evidence = _command_evidence(tuple(command))
        if tuple(command) == locker.TYPE_CHECK_COMMAND:
            return evidence, "All checks passed!\n", ""
        if tuple(command) == locker.FOCUSED_TEST_COMMAND:
            return evidence, "1 passed in 77.80s (0:01:17)\n", ""
        if tuple(command) == locker.POETRY_CHECK_COMMAND:
            return evidence, "All set!\n", ""
        if tuple(command) == locker.DVC_PUSH_COMMAND:
            dvc_calls += 1
            terminal = "1 file pushed" if dvc_calls == 1 else "Everything is up to date."
            return evidence, terminal + "\n", ""
        return evidence, "", ""

    monkeypatch.setattr(locker, "_run_command", run)
    monkeypatch.setattr(
        locker,
        "run_p1_bundle_audit_in_process",
        lambda: {"execution_mode": "in_process_callable"},
    )
    observed = locker.run_p1_temporal_consumer_pytest_summary_patch_verification()
    assert preflighted == [
        locker.TYPE_CHECK_COMMAND,
        locker.FOCUSED_TEST_COMMAND,
        locker.DVC_PUSH_COMMAND,
    ]
    assert commands.count(locker.DVC_PUSH_COMMAND) == 2
    assert observed["dvc_push_first"]["terminal_status"] == "1 file pushed"
    assert observed["dvc_push_second"]["terminal_status"] == (
        "Everything is up to date."
    )


def test_verification_audit_failure_occurs_before_any_dvc_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(locker, "FOCUSED_TEST_COUNT", 1)
    monkeypatch.setattr(
        locker.hardened,
        "_require_fixed_venv_executable",
        lambda command: None,
    )

    def run(
        command: tuple[str, ...],
        **_: Any,
    ) -> tuple[dict[str, Any], str, str]:
        commands.append(tuple(command))
        evidence = _command_evidence(tuple(command))
        if tuple(command) == locker.TYPE_CHECK_COMMAND:
            return evidence, "All checks passed!\n", ""
        if tuple(command) == locker.FOCUSED_TEST_COMMAND:
            return evidence, "1 passed in 0.01s\n", ""
        if tuple(command) == locker.POETRY_CHECK_COMMAND:
            return evidence, "All set!\n", ""
        if tuple(command) == locker.DVC_PUSH_COMMAND:
            raise AssertionError("DVC must remain unreachable after audit failure")
        return evidence, "", ""

    monkeypatch.setattr(locker, "_run_command", run)
    monkeypatch.setattr(
        locker,
        "run_p1_bundle_audit_in_process",
        lambda: (_ for _ in ()).throw(
            module.P1TemporalConsumerPytestSummaryPatchError("injected audit failure")
        ),
    )
    with pytest.raises(
        module.P1TemporalConsumerPytestSummaryPatchError,
        match="injected audit failure",
    ):
        locker.run_p1_temporal_consumer_pytest_summary_patch_verification()
    assert locker.DVC_PUSH_COMMAND not in commands


def test_malformed_long_summary_stops_before_all_downstream_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(locker, "FOCUSED_TEST_COUNT", 1)
    monkeypatch.setattr(
        locker.hardened,
        "_require_fixed_venv_executable",
        lambda command: None,
    )

    def run(
        command: tuple[str, ...],
        **_: Any,
    ) -> tuple[dict[str, Any], str, str]:
        commands.append(tuple(command))
        evidence = _command_evidence(tuple(command))
        if tuple(command) == locker.TYPE_CHECK_COMMAND:
            return evidence, "All checks passed!\n", ""
        if tuple(command) == locker.FOCUSED_TEST_COMMAND:
            # This is the exact ME defect class: rc=0 and missing >=60 clock.
            return evidence, "1 passed in 77.80s\n", ""
        raise AssertionError(f"downstream command became reachable: {command}")

    monkeypatch.setattr(locker, "_run_command", run)
    monkeypatch.setattr(
        locker,
        "run_p1_bundle_audit_in_process",
        lambda: pytest.fail("auditor must remain unreachable after parser failure"),
    )
    with pytest.raises(
        module.P1TemporalConsumerPytestSummaryPatchError,
        match="long pytest summary clock drifted",
    ):
        locker.run_p1_temporal_consumer_pytest_summary_patch_verification()
    assert commands == [locker.TYPE_CHECK_COMMAND, locker.FOCUSED_TEST_COMMAND]


def test_verification_rejects_non_idempotent_second_dvc_push() -> None:
    with pytest.raises(
        module.P1TemporalConsumerPytestSummaryPatchError,
        match="idempotent",
    ):
        locker._dvc_terminal_status(
            "1 file pushed\n",
            "",
            require_idempotent=True,
        )


@pytest.mark.parametrize(
    ("summary", "expected_format", "expected_clock"),
    [
        ("7 passed in 0.01s\n", "pytest_short", None),
        ("7 passed in 59.99s\n", "pytest_short", None),
        ("7 passed in 60.00s (0:01:00)\n", "pytest_timedelta", "0:01:00"),
        ("7 passed in 77.80s (0:01:17)\n", "pytest_timedelta", "0:01:17"),
        ("7 passed in 3601.25s (1:00:01)\n", "pytest_timedelta", "1:00:01"),
    ],
)
def test_pytest_9_0_3_summary_parser_accepts_exact_duration_forms(
    monkeypatch: pytest.MonkeyPatch,
    summary: str,
    expected_format: str,
    expected_clock: str | None,
) -> None:
    monkeypatch.setattr(locker, "FOCUSED_TEST_COUNT", 7)
    observed = locker._parse_focused_summary(".......\n" + summary, "")
    assert observed["test_count"] == 7
    assert observed["summary_format"] == expected_format
    assert observed["duration_clock"] == expected_clock


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [
        ("7 passed in 60.00s\n", ""),
        ("7 passed in 59.99s (0:00:59)\n", ""),
        ("7 passed in 77.80s (0:01:18)\n", ""),
        ("7 passed in 1.0s\n", ""),
        ("6 passed in 1.00s\n", ""),
        ("7 passed, 1 skipped in 1.00s\n", ""),
        ("7 passed in 1.00s\n7 passed in 1.00s\n", ""),
        ("7 passed in 1.00s\ntrailing\n", ""),
        ("7 passed in 1.00s\n", "plugin output\n"),
    ],
)
def test_pytest_9_0_3_summary_parser_rejects_nonclosed_forms(
    monkeypatch: pytest.MonkeyPatch,
    stdout: str,
    stderr: str,
) -> None:
    monkeypatch.setattr(locker, "FOCUSED_TEST_COUNT", 7)
    with pytest.raises(module.P1TemporalConsumerPytestSummaryPatchError):
        locker._parse_focused_summary(stdout, stderr)


def test_effective_loader_orders_publication_before_physical_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    payload = {
        "patch_repository": {"head": PATCH_HEAD},
        "base_authority": {
            "e0_me": {
                "e0_me_context_authorization": {
                    "gate": "E0-ME",
                    "p_e0_me_absent": True,
                    "historical_git_authority_verified": True,
                    "historical_e0_md_verified": True,
                    "historical_e0_dltvm_verified": True,
                    "historical_me_effective_loader_called": False,
                    "effective_loader_called": False,
                },
                "e0_md_context_authorization": {"gate": "E0-MD"},
                "e0_mc_context_authorization": {"gate": "E0-MC"},
            }
        },
        "verification": {"p1_bundle_audit": {"status": "validated"}},
    }
    companion = {"status": "completed"}

    def load(path: Path, **_: Any) -> dict[str, Any]:
        if path == module.DEFAULT_PATCH_LOCK_PATH:
            return payload
        if path == module.DEFAULT_PATCH_LOCK_SCHEMA:
            return {}
        return companion

    def validate(
        _payload: Mapping[str, Any],
        _schema: Mapping[str, Any],
        *,
        require_physical_audit: bool,
    ) -> None:
        events.append("physical_audit" if require_physical_audit else "static")

    lock_record = _record(
        module.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "external_p1_temporal_consumer_pytest_summary_patch_lock",
    )
    companion_record = _record(
        module.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        "p1_temporal_consumer_pytest_summary_patch_companion",
    )
    monkeypatch.setattr(module, "_load_regular_json", load)
    monkeypatch.setattr(
        module,
        "validate_p1_temporal_consumer_pytest_summary_patch_lock_payload",
        validate,
    )
    monkeypatch.setattr(
        module,
        "_file_record",
        lambda path, role: lock_record
        if path == module.DEFAULT_PATCH_LOCK_PATH
        else companion_record,
    )
    monkeypatch.setattr(
        module,
        "_expected_companion",
        lambda *args, **kwargs: companion,
    )
    monkeypatch.setattr(module, "_require_commit", lambda value, **_: value)
    monkeypatch.setattr(module, "_require_ancestor", lambda *args: None)
    monkeypatch.setattr(
        module,
        "_git",
        lambda *args: PATCH_HEAD if args[:2] == ("rev-parse", "HEAD") else "",
    )

    def publication(*args: Any, **kwargs: Any) -> tuple[str, dict[str, Any], dict[str, Any]]:
        events.append("publication")
        return LOCK_COMMIT, lock_record, companion_record

    monkeypatch.setattr(module, "_validate_publication_bundle", publication)
    _, summary = module.load_and_validate_p1_temporal_consumer_pytest_summary_patch_lock(
        require_published=True,
        verify_remote=True,
    )
    assert events == ["static", "publication", "physical_audit"]
    assert summary["in_process_audit_verified"] is True
    assert summary["in_process_audit_evidence"] == {"status": "validated"}
    assert summary["e0_me_context_authorization"]["gate"] == "E0-ME"
    assert summary["historical_e0_me_verified"] is True
    assert summary["historical_me_effective_loader_called"] is False
    assert summary["p_e0_me_absent"] is True
    assert summary["pytest_summary_parser_corrected"] is True
    assert summary["e0_md_context_authorization"]["gate"] == "E0-MD"
    assert summary["historical_e0_dltvm_verified"] is True
    assert summary["historical_dltvm_effective_loader_called"] is False
    assert summary["e0_mc_context_authorization"]["gate"] == "E0-MC"


def test_effective_publication_rejects_descendant_execution_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"patch_repository": {"head": PATCH_HEAD}}
    descendant = "c" * 40
    monkeypatch.setattr(module, "_introduced_commit", lambda path: LOCK_COMMIT)

    def git(*args: str) -> str:
        if args[:4] == ("rev-list", "--parents", "-n", "1"):
            return f"{LOCK_COMMIT} {PATCH_HEAD}"
        if args == ("branch", "--show-current"):
            return "main"
        if args[:1] == ("rev-parse",):
            return descendant
        return ""

    monkeypatch.setattr(module, "_git", git)
    monkeypatch.setattr(
        module,
        "_observed_diff_entries",
        lambda *args: [
            {
                "status": "A",
                "path": module.DEFAULT_PATCH_LOCK_PATH.as_posix(),
            },
            {
                "status": "A",
                "path": module.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
            },
        ],
    )
    with pytest.raises(
        module.P1TemporalConsumerPytestSummaryPatchError,
        match="exact P-E0-MF lock commit",
    ):
        module._validate_publication_bundle(
            payload,
            execution_head=descendant,
            verify_remote=True,
        )


def test_effective_publication_rejects_detached_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"patch_repository": {"head": PATCH_HEAD}}
    monkeypatch.setattr(module, "_introduced_commit", lambda path: LOCK_COMMIT)

    def git(*args: str) -> str:
        if args[:4] == ("rev-list", "--parents", "-n", "1"):
            return f"{LOCK_COMMIT} {PATCH_HEAD}"
        if args == ("branch", "--show-current"):
            return ""
        return LOCK_COMMIT

    monkeypatch.setattr(module, "_git", git)
    monkeypatch.setattr(
        module,
        "_observed_diff_entries",
        lambda *args: [
            {
                "status": "A",
                "path": module.DEFAULT_PATCH_LOCK_PATH.as_posix(),
            },
            {
                "status": "A",
                "path": module.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
            },
        ],
    )
    with pytest.raises(
        module.P1TemporalConsumerPytestSummaryPatchError,
        match="requires branch main",
    ):
        module._validate_publication_bundle(
            payload,
            execution_head=LOCK_COMMIT,
            verify_remote=True,
        )


@pytest.mark.parametrize(
    ("model_id", "base_seed", "device"),
    [("P0", 1729, "cpu"), ("P1", 20260612, "cpu"), ("P1", 1729, "cuda")],
)
def test_authorization_api_rejects_wrong_slot_before_loader(
    monkeypatch: pytest.MonkeyPatch,
    model_id: str,
    base_seed: int,
    device: str,
) -> None:
    monkeypatch.setattr(
        module,
        "load_and_validate_p1_temporal_consumer_pytest_summary_patch_lock",
        lambda **kwargs: pytest.fail("loader must not run"),
    )
    with pytest.raises(
        module.P1TemporalConsumerPytestSummaryPatchError,
        match="only the P1 seed 1729 CPU",
    ):
        module.require_p1_temporal_consumer_pytest_summary_patch_authorized(
            model_id=model_id,
            base_seed=base_seed,
            device=device,
        )


def test_authorization_api_requires_context_and_in_process_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary = _effective_summary()
    monkeypatch.setattr(
        module,
        "load_and_validate_p1_temporal_consumer_pytest_summary_patch_lock",
        lambda **kwargs: ({}, summary),
    )
    observed = module.require_p1_temporal_consumer_pytest_summary_patch_authorized(
        model_id="P1",
        base_seed=1729,
        device="cpu",
    )
    assert observed is summary
    assert observed["in_process_audit_evidence"]["status"] == "validated"

    missing_dltvm_context = {
        **summary,
        "e0_md_context_authorization": {"gate": "E0-MD"},
    }
    monkeypatch.setattr(
        module,
        "load_and_validate_p1_temporal_consumer_pytest_summary_patch_lock",
        lambda **kwargs: ({}, missing_dltvm_context),
    )
    with pytest.raises(
        module.P1TemporalConsumerPytestSummaryPatchError,
        match="e0_md_context_authorization drifted",
    ):
        module.require_p1_temporal_consumer_pytest_summary_patch_authorized(
            model_id="P1",
            base_seed=1729,
            device="cpu",
        )


def test_guard_namespace_is_unique_to_e0_mf() -> None:
    assert locker.OUTPUT_GUARD_DIRECTORY.name == "closure_v1_e0_mf_locker"
    assert len(locker.OUTPUT_GUARD_NAMES) == 2
    assert all("pytest_summary_patch" in name for name in locker.OUTPUT_GUARD_NAMES)


def test_check_only_exposes_historical_me_without_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    historical_me = {"gate": "E0-ME", "effective_loader_called": False}
    monkeypatch.setattr(locker, "_refuse_existing_outputs", lambda *args: None)
    monkeypatch.setattr(
        locker,
        "collect_p1_temporal_consumer_pytest_summary_patch_prelock_state",
        lambda **kwargs: {
            "patch_repository": {"head": PATCH_HEAD},
            "patch_components": {"count": 7},
            "base_authority": {"e0_me": historical_me},
            "consumer_prelock": {"all_absent_at_lock": True},
            "fit_availability": dict(module.FIT_AVAILABILITY),
        },
    )
    observed = locker._check_only(
        module.DEFAULT_PATCH_LOCK_PATH,
        module.DEFAULT_PATCH_MANIFEST_PATH,
    )
    assert observed["status"] == "ready_to_lock"
    assert observed["historical_e0_me"] is historical_me
    assert observed["writes_performed"] is False
    assert observed["verification_commands_run"] is False
    assert observed["in_process_audit_run"] is False
    assert observed["dvc_commands_run"] is False


def test_locker_failure_rolls_back_owned_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guards = (object(), object())
    cleanup: dict[str, Any] = {}
    monkeypatch.setattr(locker, "_closed_output", lambda path, expected: path)
    monkeypatch.setattr(locker, "_acquire_guards", lambda *args: guards)
    monkeypatch.setattr(locker.hardened, "_assert_lock_namespace", lambda *args: None)
    monkeypatch.setattr(
        locker,
        "collect_p1_temporal_consumer_pytest_summary_patch_prelock_state",
        lambda **kwargs: (_ for _ in ()).throw(
            module.P1TemporalConsumerPytestSummaryPatchError("injected failure")
        ),
    )

    def cleanup_resources(
        owners: list[Any],
        observed_guards: tuple[Any, Any],
        *,
        succeeded: bool,
        active_error: BaseException | None,
    ) -> None:
        cleanup.update(
            owners=list(owners),
            guards=observed_guards,
            succeeded=succeeded,
            active_error=active_error,
        )

    monkeypatch.setattr(locker.hardened, "_cleanup_lock_resources", cleanup_resources)
    with pytest.raises(
        module.P1TemporalConsumerPytestSummaryPatchError,
        match="injected failure",
    ):
        locker._execute_lock(
            module.DEFAULT_PATCH_LOCK_PATH,
            module.DEFAULT_PATCH_MANIFEST_PATH,
        )
    assert cleanup["owners"] == []
    assert cleanup["guards"] == guards
    assert cleanup["succeeded"] is False
    assert isinstance(cleanup["active_error"], BaseException)


def test_locker_companion_failure_rolls_back_owned_lock_manifest_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guards = (object(), object())
    cleanup: dict[str, Any] = {}
    publications: list[str] = []
    owner = object()
    prelock = {"patch_repository": {"head": PATCH_HEAD}}
    monkeypatch.setattr(locker, "_closed_output", lambda path, expected: path)
    monkeypatch.setattr(locker, "_acquire_guards", lambda *args: guards)
    monkeypatch.setattr(locker.hardened, "_assert_lock_namespace", lambda *args: None)
    monkeypatch.setattr(
        locker,
        "collect_p1_temporal_consumer_pytest_summary_patch_prelock_state",
        lambda **kwargs: prelock,
    )
    monkeypatch.setattr(
        locker,
        "run_p1_temporal_consumer_pytest_summary_patch_verification",
        lambda: {},
    )
    monkeypatch.setattr(locker, "p1_consumer_namespace_absence", lambda: {})
    monkeypatch.setattr(
        locker,
        "build_p1_temporal_consumer_pytest_summary_patch_lock_payload",
        lambda *args, **kwargs: {"patch_repository": {"head": PATCH_HEAD}},
    )
    monkeypatch.setattr(locker, "_load_regular_json", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        locker,
        "validate_p1_temporal_consumer_pytest_summary_patch_lock_payload",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(locker, "_expected_companion", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        locker.hardened,
        "_owned_file_record",
        lambda *args, **kwargs: _record("lock.json", "lock"),
    )

    def publish(*args: Any, **kwargs: Any) -> object:
        if not publications:
            publications.append("lock")
            return owner
        publications.append("companion")
        raise locker.hardened.DevelopmentRuntimeTemporalConsumerPatchError(
            "injected companion failure"
        )

    def cleanup_resources(
        owners: list[Any],
        observed_guards: tuple[Any, Any],
        *,
        succeeded: bool,
        active_error: BaseException | None,
    ) -> None:
        cleanup.update(
            owners=list(owners),
            guards=observed_guards,
            succeeded=succeeded,
            active_error=active_error,
        )

    monkeypatch.setattr(locker.hardened, "_publish_guarded_bytes", publish)
    monkeypatch.setattr(locker.hardened, "_cleanup_lock_resources", cleanup_resources)
    with pytest.raises(
        module.P1TemporalConsumerPytestSummaryPatchError,
        match="injected companion failure",
    ):
        locker._execute_lock(
            module.DEFAULT_PATCH_LOCK_PATH,
            module.DEFAULT_PATCH_MANIFEST_PATH,
        )
    assert publications == ["lock", "companion"]
    assert cleanup["owners"] == [owner]
    assert cleanup["guards"] == guards
    assert cleanup["succeeded"] is False
    assert isinstance(cleanup["active_error"], BaseException)


def test_refuse_existing_outputs_is_lexical_and_no_clobber(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "lock.json"
    companion_path = tmp_path / "manifest.json"
    lock_path.symlink_to(tmp_path / "missing")
    monkeypatch.setattr(locker, "_closed_output", lambda path, expected: path)
    monkeypatch.setattr(
        locker,
        "_guard_paths",
        lambda **kwargs: (tmp_path / "one.guard", tmp_path / "two.guard"),
    )
    with pytest.raises(
        module.P1TemporalConsumerPytestSummaryPatchError,
        match="Refusing to overwrite",
    ):
        locker._refuse_existing_outputs(lock_path, companion_path)


def test_protocol_keeps_consumer_and_outcomes_sealed() -> None:
    assert module.PATCH_AUTHORIZATIONS["p1_consumer_authorized"] is False
    assert module.PATCH_AUTHORIZATIONS["p1_fit_authorized"] is False
    assert module.PATCH_AUTHORIZATIONS["e0_m_authorized"] is False
    assert module.PATCH_AUTHORIZATIONS["e0_u_authorized"] is False
    assert module.PATCH_AUTHORIZATIONS["future_outcomes_accessed"] is False
    assert module.PATCH_CORRECTION["auditor_execution_mode"] == (
        "in_process_callable"
    )
    assert module.PATCH_CORRECTION["pytest_summary_reference_version"] == "9.0.3"
    assert module.PATCH_CORRECTION["failed_execute_lock_authorization_consumed"] is True
    assert module.PATCH_CORRECTION["failed_execute_lock_process_started"] is True
    assert module.PATCH_CORRECTION["failed_execute_lock_prelock_completed"] is True
    assert module.PATCH_CORRECTION["failed_execute_lock_guards_acquired"] is True
    assert module.PATCH_CORRECTION["failed_execute_lock_guards_rolled_back"] is True
    assert module.PATCH_CORRECTION["failed_execute_lock_full_type_check_run"] is True
    assert module.PATCH_CORRECTION["failed_execute_lock_full_type_check_passed"] is True
    assert module.PATCH_CORRECTION["failed_execute_lock_focused_pytest_run"] is True
    assert (
        module.PATCH_CORRECTION["failed_execute_lock_focused_pytest_returncode_zero"]
        is True
    )
    assert (
        module.PATCH_CORRECTION["failed_execute_lock_focused_pytest_parser_rejected"]
        is True
    )
    assert (
        module.PATCH_CORRECTION["failed_execute_lock_focused_pytest_stdout_preserved"]
        is False
    )
    assert module.PATCH_CORRECTION["failed_execute_lock_poetry_check_run"] is False
    assert module.PATCH_CORRECTION["failed_execute_lock_publication_guard_run"] is False
    assert module.PATCH_CORRECTION["failed_execute_lock_diff_check_run"] is False
    assert module.PATCH_CORRECTION["failed_execute_lock_in_process_audit_run"] is False
    assert module.PATCH_CORRECTION["failed_execute_lock_dvc_commands_run"] is False
    assert module.PATCH_CORRECTION["failed_execute_lock_payload_built"] is False
    assert module.PATCH_CORRECTION["failed_execute_lock_outputs_written"] is False
