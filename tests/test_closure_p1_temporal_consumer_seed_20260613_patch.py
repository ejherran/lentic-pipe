from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from src.experiments import closure_contract
from src.experiments import (
    closure_p1_temporal_consumer_seed_20260613_patch as module,
)
from src.experiments import (
    lock_closure_p1_temporal_consumer_seed_20260613_patch as locker,
)


ZERO_SHA = "0" * 64
PATCH_HEAD = "a" * 40
LOCK_COMMIT = "b" * 40


def _record(path: str, role: str, *, size: int = 1) -> dict[str, Any]:
    return {"path": path, "role": role, "bytes": size, "sha256": ZERO_SHA}


def _schema_preflight() -> dict[str, Any]:
    return {
        "gate": "E0-MK",
        "schema_path": module.DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
        "schema_bytes": 1,
        "schema_sha256": ZERO_SHA,
        "supported_subset_verified": True,
        "minimum_keyword_absent": True,
        "format_keyword_absent": True,
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


def _identity() -> dict[str, Any]:
    record = _record(module.AUDITOR_SOURCE_PATH, "p1_sequence_bundle_auditor_callable")
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


def _audit_evidence() -> dict[str, Any]:
    record = _record(module.AUDITOR_SOURCE_PATH, "p1_sequence_bundle_auditor_callable")
    return {
        "execution_mode": "in_process_callable",
        "callable_module": module.AUDITOR_MODULE,
        "callable_name": module.AUDITOR_NAME,
        "callable_qualname": module.AUDITOR_QUALNAME,
        "callable_source_path": module.AUDITOR_SOURCE_PATH,
        "callable_code_filename": module.AUDITOR_SOURCE_PATH,
        "callable_git_commit": module.P1_BUNDLE_COMMIT,
        "callable_source_git": record,
        "callable_source_physical": record,
        "audit_version": module.p1_audit.AUDIT_VERSION,
        "status": "validated",
        "model_id": "P1",
        "base_seed": 20260613,
        "intent_origins": 9_732,
        "successful_origins": 9_227,
        "failed_origins": 505,
        "fit_successful_origins": 8_925,
        "fit_unavailable_origins": 488,
        "calibration_unavailable_origins": 17,
        "fit_failure_reason_counts": {"missing_target_state": 488},
        "sequence_fit_available": False,
        "expected_slot_status": "model_unavailable",
        "expected_fit_status": "not_attempted",
        "expected_failure_reason": "sequence_fit_rows_unavailable",
        "result_bytes": 1,
        "result_sha256": ZERO_SHA,
        "auditor_read_only": True,
        "consumer_executed": False,
        "fit_executed": False,
        "dvc_operation_executed": False,
        "future_outcomes_accessed": False,
    }


def _verification() -> dict[str, Any]:
    focused = _command_evidence(module.FOCUSED_TEST_COMMAND)
    focused.update(
        {
            "test_count": module.FOCUSED_TEST_COUNT,
            "skipped_count": 0,
            "deselected_count": 0,
            "summary_format": "pytest_timedelta",
            "duration_seconds": "60.00",
            "duration_clock": "0:01:00",
        }
    )
    first = _command_evidence(module.DVC_PUSH_COMMAND)
    first["terminal_status"] = "Everything is up to date."
    second = _command_evidence(module.DVC_PUSH_COMMAND)
    second["terminal_status"] = "Everything is up to date."
    return {
        "schema_subset_preflight": _schema_preflight(),
        "full_type_check": _command_evidence(module.TYPE_CHECK_COMMAND),
        "focused_tests": focused,
        "poetry_check": _command_evidence(module.POETRY_CHECK_COMMAND),
        "publication_guard": _command_evidence(module.PUBLICATION_GUARD_COMMAND),
        "git_diff_check": _command_evidence(module.DIFF_CHECK_COMMAND),
        "p1_bundle_audit": _audit_evidence(),
        "dvc_push_first": first,
        "dvc_push_second": second,
    }


def _prelock() -> dict[str, Any]:
    records = [
        _record(path, module.PATCH_COMPONENT_ROLES[path])
        for path in module.PATCH_PATHS
    ]
    components = {
        "count": 7,
        "paths": list(module.PATCH_PATHS),
        "paths_sha256": ZERO_SHA,
        "records": records,
        "records_sha256": ZERO_SHA,
    }
    entries = [
        {
            "status": "M" if path in module.PATCH_MODIFIED_PATHS else "A",
            "path": path,
        }
        for path in module.PATCH_PATHS
    ]
    consumer_paths = [f"closed/consumer/{index}" for index in range(19)]
    return {
        "patch_repository": {
            "head": PATCH_HEAD,
            "parent": module.PATCH_BASE_COMMIT,
            "branch": "main",
            "published_ref": module.PUBLISHED_REF,
            "published_head": PATCH_HEAD,
            "remote_main_oid": PATCH_HEAD,
            "worktree_status": "clean",
            "exact_diff_verified": True,
        },
        "git_diff": {
            "base_commit": module.PATCH_BASE_COMMIT,
            "patch_head": PATCH_HEAD,
            "entries": entries,
            "paths": list(module.PATCH_PATHS),
            "paths_sha256": ZERO_SHA,
            "added_count": 5,
            "modified_count": 2,
            "only_allowed_additions_and_modifications": True,
        },
        "patch_components": components,
        "base_authorities": {
            "e0_mi": {"gate": "E0-MI"},
            "e0_mj": {"gate": "E0-MJ"},
        },
        "p1_20260613_publication": {
            "commit": module.P1_BUNDLE_COMMIT,
            "records": [],
        },
        "current_runtime_builder_record": {
            **module.P1_ARTIFACT_BUILDER_RECORD,
            "role": "current_runtime_builder",
        },
        "consumer_prelock": {
            "model_id": "P1",
            "base_seed": 20260613,
            "count": 19,
            "paths": consumer_paths,
            "paths_sha256": ZERO_SHA,
            "all_absent_at_lock": True,
        },
        "progression_prelock": {
            "registered_path_count": 140,
            "expected_present_count": 16,
            "expected_present_paths": [
                *(f"prior/{index}" for index in range(12)),
                *(f"current/{index}" for index in range(4)),
            ],
            "expected_present_paths_sha256": ZERO_SHA,
            "registered_absent_count": 124,
            "exact_registered_namespace_verified": True,
            "prior_seeds": [1729, 20_260_612],
            "prior_present_count": 12,
            "prior_present_paths": [f"prior/{index}" for index in range(12)],
            "prior_present_paths_sha256": ZERO_SHA,
            "prior_residual_absent_count": 44,
            "current_seed": 20260613,
            "current_present_count": 4,
            "current_present_paths": [f"current/{index}" for index in range(4)],
            "current_present_paths_sha256": ZERO_SHA,
            "current_consumer_absent_count": 19,
            "current_sequence_temporary_absent_count": 5,
            "later_absent_count": 56,
            "later_paths_sha256": ZERO_SHA,
            "e0_m_absent_count": 4,
            "outcome_access_log_absent": True,
            "ordered_progression_verified": True,
            "future_outcomes_accessed": False,
        },
        "fit_availability": dict(module.FIT_AVAILABILITY),
    }


def test_h_patch_scope_is_exact_two_modified_plus_five_added() -> None:
    assert set(module.PATCH_MODIFIED_PATHS) == {
        "src/experiments/train_closure_pipe.py",
        "tests/test_train_closure_pipe.py",
    }
    assert set(module.PATCH_ADDED_PATHS) == {
        "configs/closure_v1/p1_temporal_consumer_seed_20260613_patch_lock.schema.json",
        "docs/closure_v1/E0_M_P1_TEMPORAL_CONSUMER_SEED_20260613_PATCH_1.md",
        "src/experiments/closure_p1_temporal_consumer_seed_20260613_patch.py",
        "src/experiments/lock_closure_p1_temporal_consumer_seed_20260613_patch.py",
        "tests/test_closure_p1_temporal_consumer_seed_20260613_patch.py",
    }
    assert len(module.PATCH_PATHS) == 7


def test_physical_schema_uses_real_closure_contract_subset() -> None:
    schema = json.loads(module.DEFAULT_PATCH_LOCK_SCHEMA.read_text(encoding="utf-8"))
    with pytest.raises(closure_contract.ClosureContractError) as raised:
        closure_contract.validate_json_schema({}, schema, instance_path="$.probe")
    assert "Unsupported JSON Schema keyword" not in str(raised.value)
    observed = module.preflight_p1_temporal_consumer_seed_20260613_patch_schema()
    assert observed["supported_subset_verified"] is True
    assert observed["minimum_keyword_absent"] is True
    assert observed["format_keyword_absent"] is True


def _closed_progression_paths() -> set[Path]:
    return {
        *module.p1_audit.PRIOR_P1_PATHS,
        module.p1_audit.P1_SEQUENCE_PATH,
        module.p1_audit.P1_POINTER_PATH,
        module.p1_audit.P1_SUMMARY_PATH,
        module.p1_audit.P1_MANIFEST_PATH,
    }


def test_progression_prelock_requires_exact_registered_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    present = _closed_progression_paths()
    monkeypatch.setattr(
        module,
        "_path_entry_exists",
        lambda path: path.relative_to(module.PROJECT_ROOT) in present,
    )

    observed = module.closure_progression_prelock()

    assert observed["registered_path_count"] == 140
    assert observed["expected_present_count"] == 16
    assert observed["registered_absent_count"] == 124
    assert observed["prior_residual_absent_count"] == 44
    assert observed["current_sequence_temporary_absent_count"] == 5
    assert observed["exact_registered_namespace_verified"] is True


def test_historical_e0_mj_preserves_both_prior_publications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = module._historical_e0_mj_authority(
        execution_head=module.PATCH_BASE_COMMIT
    )
    assert observed["gate"] == "E0-MJ"
    assert observed["preserved_components"]["count"] == 7
    assert observed["effective_loader_called"] is False

    monkeypatch.setattr(
        module.e0_mj,
        "_published_p1_20260612_bundle",
        lambda **kwargs: {"drifted": True},
    )
    with pytest.raises(
        module.P1TemporalConsumerSeed20260613PatchError,
        match="P1/20260612 publication drifted",
    ):
        module._historical_e0_mj_authority(
            execution_head=module.PATCH_BASE_COMMIT
        )


@pytest.mark.parametrize("residual_kind", ["prior", "current-temp"])
def test_progression_prelock_rejects_registered_residuals(
    monkeypatch: pytest.MonkeyPatch,
    residual_kind: str,
) -> None:
    present = _closed_progression_paths()
    registered = set(module.p1_audit.REGISTERED_P1_PATHS)
    if residual_kind == "prior":
        residual = next(
            path
            for path in registered.difference(present)
            if "seed_1729" in path.as_posix()
        )
    else:
        residual = Path(f"{module.p1_audit.P1_SEQUENCE_PATH.as_posix()}.tmp")
    assert residual in registered
    present.add(residual)
    monkeypatch.setattr(
        module,
        "_path_entry_exists",
        lambda path: path.relative_to(module.PROJECT_ROOT) in present,
    )

    with pytest.raises(
        module.P1TemporalConsumerSeed20260613PatchError,
        match="unexpected_registered",
    ):
        module.closure_progression_prelock()


@pytest.mark.parametrize("keyword", ["minimum", "format"])
@pytest.mark.parametrize("entrypoint", ["check_only", "execute_lock"])
def test_unsupported_schema_mutation_fails_before_any_downstream_action(
    monkeypatch: pytest.MonkeyPatch,
    keyword: str,
    entrypoint: str,
) -> None:
    schema = json.loads(module.DEFAULT_PATCH_LOCK_SCHEMA.read_text(encoding="utf-8"))
    schema["properties"]["created_at_utc"][keyword] = (
        0 if keyword == "minimum" else "date-time"
    )
    monkeypatch.setattr(module, "_load_regular_json", lambda *args, **kwargs: schema)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("schema failure must precede guards, prelock, commands, audit, and DVC")

    monkeypatch.setattr(locker, "_refuse_existing_outputs", forbidden)
    monkeypatch.setattr(locker, "_acquire_guards", forbidden)
    monkeypatch.setattr(
        locker,
        "collect_p1_temporal_consumer_seed_20260613_patch_prelock_state",
        forbidden,
    )
    monkeypatch.setattr(locker, "_run_command", forbidden)
    monkeypatch.setattr(locker, "run_p1_bundle_audit_in_process", forbidden)
    with pytest.raises(
        module.P1TemporalConsumerSeed20260613PatchError,
        match="keywords outside the closed contract subset",
    ):
        if entrypoint == "check_only":
            locker._check_only(
                module.DEFAULT_PATCH_LOCK_PATH,
                module.DEFAULT_PATCH_MANIFEST_PATH,
            )
        else:
            locker._execute_lock(
                module.DEFAULT_PATCH_LOCK_PATH,
                module.DEFAULT_PATCH_MANIFEST_PATH,
            )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_bytes", 0),
        ("schema_bytes", True),
        ("schema_sha256", "not-a-digest"),
    ],
)
def test_locker_rejects_invalid_schema_preflight_limits(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: Any,
) -> None:
    evidence = {**_schema_preflight(), field: value}
    monkeypatch.setattr(
        locker,
        "preflight_p1_temporal_consumer_seed_20260613_patch_schema",
        lambda: evidence,
    )
    with pytest.raises(
        module.P1TemporalConsumerSeed20260613PatchError,
        match="schema-subset preflight evidence drifted",
    ):
        locker._preflight_schema()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stdout_line_count", -1),
        ("stderr_line_count", -1),
        ("stdout_line_count", True),
        ("stderr_line_count", False),
    ],
)
def test_semantic_command_limits_reject_negative_or_boolean_counts(
    field: str,
    value: Any,
) -> None:
    evidence = _command_evidence(module.TYPE_CHECK_COMMAND)
    evidence[field] = value
    with pytest.raises(
        module.P1TemporalConsumerSeed20260613PatchError,
        match="must be a non-negative integer",
    ):
        module._validate_command_evidence(
            evidence,
            command=module.TYPE_CHECK_COMMAND,
            context="full_type_check",
        )


@pytest.mark.parametrize(
    ("summary", "expected_format"),
    [
        ("7 passed in 59.99s\n", "pytest_short"),
        ("7 passed in 60.00s (0:01:00)\n", "pytest_timedelta"),
    ],
)
def test_mk_parser_preserves_both_pytest_duration_forms(
    monkeypatch: pytest.MonkeyPatch,
    summary: str,
    expected_format: str,
) -> None:
    monkeypatch.setattr(locker, "FOCUSED_TEST_COUNT", 7)
    observed = locker._parse_focused_summary(".......\n" + summary, "")
    assert observed["test_count"] == 7
    assert observed["summary_format"] == expected_format


def test_verification_preflights_schema_before_first_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(locker, "FOCUSED_TEST_COUNT", 7)

    def preflight() -> dict[str, Any]:
        events.append("schema")
        return _schema_preflight()

    monkeypatch.setattr(locker, "_preflight_schema", preflight)
    monkeypatch.setattr(locker.hardened, "_require_fixed_venv_executable", lambda *_: None)
    dvc_calls = 0

    def run(
        command: tuple[str, ...],
        **kwargs: Any,
    ) -> tuple[dict[str, Any], str, str]:
        nonlocal dvc_calls
        events.append("command")
        evidence = _command_evidence(command)
        if command == locker.TYPE_CHECK_COMMAND:
            return evidence, "All checks passed!\n", ""
        if command == locker.FOCUSED_TEST_COMMAND:
            return evidence, ".......\n7 passed in 60.00s (0:01:00)\n", ""
        if command == locker.POETRY_CHECK_COMMAND:
            return evidence, "All set!\n", ""
        if command == locker.DVC_PUSH_COMMAND:
            dvc_calls += 1
            terminal = "1 file pushed" if dvc_calls == 1 else "Everything is up to date."
            return evidence, terminal + "\n", ""
        return evidence, "", ""

    monkeypatch.setattr(locker, "_run_command", run)
    monkeypatch.setattr(locker, "run_p1_bundle_audit_in_process", _audit_evidence)
    observed = locker.run_p1_temporal_consumer_seed_20260613_patch_verification(
        expected_schema_preflight=_schema_preflight()
    )
    assert events[0] == "schema"
    assert observed["schema_subset_preflight"] == _schema_preflight()
    assert observed["dvc_push_second"]["terminal_status"] == "Everything is up to date."


def test_check_only_preflights_schema_before_prelock_and_exposes_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        locker,
        "_preflight_schema",
        lambda: events.append("schema") or _schema_preflight(),
    )
    monkeypatch.setattr(locker, "_refuse_existing_outputs", lambda *args: None)

    def collect(**kwargs: Any) -> dict[str, Any]:
        events.append("prelock")
        return {
            "patch_repository": {"head": PATCH_HEAD},
            "patch_components": {"count": 7},
            "base_authorities": {
                "e0_mi": {"gate": "E0-MI"},
                "e0_mj": {"gate": "E0-MJ"},
            },
            "p1_20260613_publication": {"commit": module.P1_BUNDLE_COMMIT},
            "consumer_prelock": {"all_absent_at_lock": True},
            "progression_prelock": {"ordered_progression_verified": True},
            "fit_availability": dict(module.FIT_AVAILABILITY),
        }

    monkeypatch.setattr(
        locker,
        "collect_p1_temporal_consumer_seed_20260613_patch_prelock_state",
        collect,
    )
    observed = locker._check_only(
        module.DEFAULT_PATCH_LOCK_PATH,
        module.DEFAULT_PATCH_MANIFEST_PATH,
    )
    assert events == ["schema", "prelock"]
    assert observed["schema_subset_preflight"] == _schema_preflight()
    assert observed["writes_performed"] is False


def test_mocked_complete_transaction_uses_real_schema_and_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert module.FOCUSED_TEST_COUNT > 0
    prelock = _prelock()
    verification = _verification()
    components = prelock["patch_components"]
    historical_mi = prelock["base_authorities"]["e0_mi"]
    historical_mj = prelock["base_authorities"]["e0_mj"]
    publication = prelock["p1_20260613_publication"]
    consumer = prelock["consumer_prelock"]
    progression = prelock["progression_prelock"]
    guards = (object(), object())
    owners = (object(), object())
    cleanup: dict[str, Any] = {}
    namespace_owner_counts: list[int] = []

    monkeypatch.setattr(module, "_file_record", lambda path, **kwargs: _record(path.as_posix(), kwargs["role"]))
    monkeypatch.setattr(module, "_auditor_identity_record", _identity)
    monkeypatch.setattr(module, "_require_commit", lambda value, **kwargs: value)
    monkeypatch.setattr(module, "_require_ancestor", lambda *args: None)
    monkeypatch.setattr(module, "_git", lambda *args: PATCH_HEAD)
    monkeypatch.setattr(module, "patch_git_diff_payload", lambda head: prelock["git_diff"])
    monkeypatch.setattr(module, "patch_component_bundle", lambda head: components)
    monkeypatch.setattr(module, "_assert_paths_untouched", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "_historical_e0_mi_authority", lambda **kwargs: historical_mi)
    monkeypatch.setattr(module, "_historical_e0_mj_authority", lambda **kwargs: historical_mj)
    monkeypatch.setattr(module, "_published_p1_20260613_bundle", lambda **kwargs: publication)
    monkeypatch.setattr(module, "p1_consumer_namespace_absence", lambda: consumer)
    monkeypatch.setattr(module, "closure_progression_prelock", lambda: progression)
    monkeypatch.setattr(
        module,
        "preflight_p1_temporal_consumer_seed_20260613_patch_schema",
        lambda: _schema_preflight(),
    )

    monkeypatch.setattr(locker, "_preflight_schema", lambda: _schema_preflight())
    monkeypatch.setattr(locker, "_closed_output", lambda path, expected: path)
    monkeypatch.setattr(locker, "_acquire_guards", lambda *args: guards)

    def assert_namespace(
        lock_path: Path,
        companion_path: Path,
        observed_guards: tuple[Any, Any],
        observed_owners: list[Any],
    ) -> None:
        assert lock_path == module.DEFAULT_PATCH_LOCK_PATH
        assert companion_path == module.DEFAULT_PATCH_MANIFEST_PATH
        assert observed_guards == guards
        namespace_owner_counts.append(len(observed_owners))

    monkeypatch.setattr(locker.hardened, "_assert_lock_namespace", assert_namespace)
    monkeypatch.setattr(
        locker,
        "collect_p1_temporal_consumer_seed_20260613_patch_prelock_state",
        lambda **kwargs: prelock,
    )
    monkeypatch.setattr(
        locker,
        "run_p1_temporal_consumer_seed_20260613_patch_verification",
        lambda **kwargs: verification,
    )
    monkeypatch.setattr(locker, "p1_consumer_namespace_absence", lambda: consumer)
    monkeypatch.setattr(locker, "_expected_companion", lambda *args, **kwargs: {})
    monkeypatch.setattr(locker, "load_and_validate_p1_temporal_consumer_seed_20260613_patch_lock", lambda **kwargs: ({}, {}))
    publications: list[object] = []

    def publish(*args: Any, **kwargs: Any) -> object:
        owner = owners[len(publications)]
        publications.append(owner)
        return owner

    monkeypatch.setattr(locker.hardened, "_publish_guarded_bytes", publish)
    monkeypatch.setattr(
        locker.hardened,
        "_owned_file_record",
        lambda owner, **kwargs: _record("lock.json", kwargs["role"]),
    )

    def clean(
        observed_owners: list[Any],
        observed_guards: tuple[Any, Any],
        **kwargs: Any,
    ) -> None:
        cleanup.update(owners=list(observed_owners), guards=observed_guards, **kwargs)

    monkeypatch.setattr(locker.hardened, "_cleanup_lock_resources", clean)
    observed = locker._execute_lock(
        module.DEFAULT_PATCH_LOCK_PATH,
        module.DEFAULT_PATCH_MANIFEST_PATH,
    )
    assert observed["status"] == "locked_unpublished"
    assert publications == list(owners)
    assert cleanup["owners"] == list(owners)
    assert cleanup["succeeded"] is True
    assert namespace_owner_counts == [0, 0, 1, 2, 2]


def test_locker_failure_rolls_back_empty_owner_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guards = (object(), object())
    cleanup: dict[str, Any] = {}
    monkeypatch.setattr(locker, "_preflight_schema", lambda: _schema_preflight())
    monkeypatch.setattr(locker, "_closed_output", lambda path, expected: path)
    monkeypatch.setattr(locker, "_acquire_guards", lambda *args: guards)
    monkeypatch.setattr(locker.hardened, "_assert_lock_namespace", lambda *args: None)
    monkeypatch.setattr(
        locker,
        "collect_p1_temporal_consumer_seed_20260613_patch_prelock_state",
        lambda **kwargs: (_ for _ in ()).throw(
            module.P1TemporalConsumerSeed20260613PatchError("injected failure")
        ),
    )

    def clean(owners: list[Any], observed_guards: tuple[Any, Any], **kwargs: Any) -> None:
        cleanup.update(owners=list(owners), guards=observed_guards, **kwargs)

    monkeypatch.setattr(locker.hardened, "_cleanup_lock_resources", clean)
    with pytest.raises(
        module.P1TemporalConsumerSeed20260613PatchError,
        match="injected failure",
    ):
        locker._execute_lock(
            module.DEFAULT_PATCH_LOCK_PATH,
            module.DEFAULT_PATCH_MANIFEST_PATH,
        )
    assert cleanup["owners"] == []
    assert cleanup["guards"] == guards
    assert cleanup["succeeded"] is False


def test_companion_failure_rolls_back_lock_owner_manifest_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guards = (object(), object())
    owner = object()
    cleanup: dict[str, Any] = {}
    publications: list[str] = []
    prelock = {"patch_repository": {"head": PATCH_HEAD}}
    monkeypatch.setattr(locker, "_preflight_schema", lambda: _schema_preflight())
    monkeypatch.setattr(locker, "_closed_output", lambda path, expected: path)
    monkeypatch.setattr(locker, "_acquire_guards", lambda *args: guards)
    monkeypatch.setattr(locker.hardened, "_assert_lock_namespace", lambda *args: None)
    monkeypatch.setattr(locker, "collect_p1_temporal_consumer_seed_20260613_patch_prelock_state", lambda **kwargs: prelock)
    monkeypatch.setattr(locker, "run_p1_temporal_consumer_seed_20260613_patch_verification", lambda **kwargs: {})
    monkeypatch.setattr(locker, "p1_consumer_namespace_absence", lambda: {})
    monkeypatch.setattr(locker, "build_p1_temporal_consumer_seed_20260613_patch_lock_payload", lambda *args, **kwargs: {"patch_repository": {"head": PATCH_HEAD}})
    monkeypatch.setattr(locker, "_load_regular_json", lambda *args, **kwargs: {})
    monkeypatch.setattr(locker, "validate_p1_temporal_consumer_seed_20260613_patch_lock_payload", lambda *args, **kwargs: None)
    monkeypatch.setattr(locker, "_expected_companion", lambda *args, **kwargs: {})
    monkeypatch.setattr(locker.hardened, "_owned_file_record", lambda *args, **kwargs: _record("lock.json", "lock"))

    def publish(*args: Any, **kwargs: Any) -> object:
        if not publications:
            publications.append("lock")
            return owner
        publications.append("companion")
        raise locker.hardened.DevelopmentRuntimeTemporalConsumerPatchError(
            "injected companion failure"
        )

    def clean(owners: list[Any], observed_guards: tuple[Any, Any], **kwargs: Any) -> None:
        cleanup.update(owners=list(owners), guards=observed_guards, **kwargs)

    monkeypatch.setattr(locker.hardened, "_publish_guarded_bytes", publish)
    monkeypatch.setattr(locker.hardened, "_cleanup_lock_resources", clean)
    with pytest.raises(
        module.P1TemporalConsumerSeed20260613PatchError,
        match="injected companion failure",
    ):
        locker._execute_lock(
            module.DEFAULT_PATCH_LOCK_PATH,
            module.DEFAULT_PATCH_MANIFEST_PATH,
        )
    assert publications == ["lock", "companion"]
    assert cleanup["owners"] == [owner]
    assert cleanup["succeeded"] is False


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
        module.P1TemporalConsumerSeed20260613PatchError,
        match="Refusing to overwrite",
    ):
        locker._refuse_existing_outputs(lock_path, companion_path)


def test_future_p_mk_publication_is_exact_two_additions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"patch_repository": {"head": PATCH_HEAD}}
    monkeypatch.setattr(module, "_introduced_commit", lambda path: LOCK_COMMIT)

    def git(*args: str) -> str:
        if args[:4] == ("rev-list", "--parents", "-n", "1"):
            return f"{LOCK_COMMIT} {PATCH_HEAD}"
        if args == ("branch", "--show-current"):
            return "main"
        if args[:1] == ("rev-parse",):
            return LOCK_COMMIT
        return ""

    monkeypatch.setattr(module, "_git", git)
    monkeypatch.setattr(
        module,
        "_observed_diff_entries",
        lambda *args: [
            {"status": "A", "path": module.DEFAULT_PATCH_LOCK_PATH.as_posix()},
            {"status": "A", "path": module.DEFAULT_PATCH_MANIFEST_PATH.as_posix()},
        ],
    )
    monkeypatch.setattr(module, "_assert_paths_untouched", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "_require_ancestor", lambda *args: None)
    monkeypatch.setattr(module, "_require_commit", lambda value, **kwargs: value)
    monkeypatch.setattr(module, "_remote_main_oid", lambda: LOCK_COMMIT)
    monkeypatch.setattr(module, "_git_record", lambda commit, path, **kwargs: _record(path, kwargs["role"]))
    lock_commit, _, _ = module._validate_publication_bundle(
        payload,
        execution_head=LOCK_COMMIT,
        verify_remote=True,
    )
    assert lock_commit == LOCK_COMMIT


def test_future_p_mk_rejects_any_third_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"patch_repository": {"head": PATCH_HEAD}}
    monkeypatch.setattr(module, "_introduced_commit", lambda path: LOCK_COMMIT)
    monkeypatch.setattr(
        module,
        "_git",
        lambda *args: f"{LOCK_COMMIT} {PATCH_HEAD}" if args[:1] == ("rev-list",) else "main",
    )
    monkeypatch.setattr(
        module,
        "_observed_diff_entries",
        lambda *args: [
            {"status": "A", "path": module.DEFAULT_PATCH_LOCK_PATH.as_posix()},
            {"status": "A", "path": module.DEFAULT_PATCH_MANIFEST_PATH.as_posix()},
            {"status": "A", "path": "unexpected.json"},
        ],
    )
    with pytest.raises(
        module.P1TemporalConsumerSeed20260613PatchError,
        match="exactly lock plus companion",
    ):
        module._validate_publication_bundle(
            payload,
            execution_head=LOCK_COMMIT,
            verify_remote=False,
        )


def test_guard_namespace_and_authorizations_remain_closed() -> None:
    assert locker.OUTPUT_GUARD_DIRECTORY.name == "closure_v1_e0_mk_locker"
    assert len(locker.OUTPUT_GUARD_NAMES) == 2
    assert all("seed_20260613_patch" in name for name in locker.OUTPUT_GUARD_NAMES)
    assert module.PATCH_AUTHORIZATIONS["p1_consumer_authorized"] is False
    assert module.PATCH_AUTHORIZATIONS["p1_fit_authorized"] is False
    assert module.PATCH_AUTHORIZATIONS["fit_attempt_authorized"] is False
    assert module.PATCH_AUTHORIZATIONS["p1_sequence_builder_authorized"] is False
    assert module.PATCH_AUTHORIZATIONS["dvc_commands_authorized"] is False
    assert module.PATCH_AUTHORIZATIONS["replacement_authorized"] is False
    assert module.PATCH_AUTHORIZATIONS["e0_m_authorized"] is False
    assert module.PATCH_AUTHORIZATIONS["e0_u_authorized"] is False
    assert module.PATCH_AUTHORIZATIONS["future_outcomes_accessed"] is False
