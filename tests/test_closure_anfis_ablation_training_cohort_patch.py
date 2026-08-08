from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from src.experiments import closure_anfis_ablation_training_cohort_patch as patch
from src.experiments import lock_closure_anfis_ablation_training_cohort_patch as locker


ROOT = Path(__file__).resolve().parents[1]
PRELOCK_SECTION_KEYS = (
    "repository",
    "h_patch",
    "mt_authority",
    "runtime_contract",
    "correction_evidence",
    "companion_contract",
    "prelock",
)


def _record(path: str, role: str, marker: int) -> dict[str, Any]:
    return {
        "path": path,
        "role": role,
        "bytes": marker + 1,
        "sha256": f"{marker % 16:x}" * 64,
    }


def _synthetic_publish_payload() -> dict[str, Any]:
    return {
        **{key: {"marker": key} for key in PRELOCK_SECTION_KEYS},
        "schema_version": "synthetic",
        "status": "locked_unpublished",
        "gate": "E0-MU",
    }


def _patch_synthetic_publisher(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, Any],
) -> dict[str, int]:
    state = {"prelock_collections": 0, "verification_runs": 0}
    schema_preflight = {"status": "synthetic_schema_valid"}
    verification = {
        "schema_preflight": schema_preflight,
        "execution_boundaries": dict(patch.VERIFICATION_EXECUTION_BOUNDARIES),
    }
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_training_cohort_patch_schema",
        lambda **kwargs: schema_preflight,
    )

    def collect(**kwargs: Any) -> dict[str, Any]:
        state["prelock_collections"] += 1
        return {key: copy.deepcopy(payload[key]) for key in PRELOCK_SECTION_KEYS}

    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_training_cohort_patch_prelock_state",
        collect,
    )

    def run_verification(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["expected_schema_preflight"] == schema_preflight
        state["verification_runs"] += 1
        return verification

    monkeypatch.setattr(
        patch,
        "run_anfis_ablation_training_cohort_patch_verification",
        run_verification,
    )
    monkeypatch.setattr(
        patch,
        "build_anfis_ablation_training_cohort_patch_lock_payload",
        lambda prelock, observed_verification, **kwargs: (
            payload
            if prelock
            == {key: payload[key] for key in PRELOCK_SECTION_KEYS}
            and observed_verification == verification
            else (_ for _ in ()).throw(AssertionError("trusted inputs drifted"))
        ),
    )
    monkeypatch.setattr(
        patch,
        "validate_anfis_ablation_training_cohort_patch_lock_payload",
        lambda value, **kwargs: None,
    )
    monkeypatch.setattr(
        patch,
        "_expected_companion",
        lambda value, lock_record, **kwargs: {
            "manifest_version": "synthetic_manifest_v1",
            "gate": "E0-MU",
            "status": "completed",
            "completion_marker_written_last": True,
        },
    )
    return state


def _verification_evidence(
    *, focused_stdout: str | None = None
) -> dict[str, Any]:
    summary = (
        focused_stdout
        if focused_stdout is not None
        else f"{patch.FOCUSED_TEST_COUNT} passed in 1.23s\n"
    )
    focused = {
        **patch._command_evidence(patch.FOCUSED_TEST_COMMAND, summary, ""),
        "stdout_text": summary,
        "test_count": patch.FOCUSED_TEST_COUNT,
        "skipped_count": 0,
        "deselected_count": 0,
    }
    return {
        "schema_preflight": (
            patch.preflight_anfis_ablation_training_cohort_patch_schema()
        ),
        "full_type_check": patch._command_evidence(
            patch.TYPE_CHECK_COMMAND, "All checks passed!\n", ""
        ),
        "focused_tests": focused,
        "poetry_check": patch._command_evidence(
            patch.POETRY_CHECK_COMMAND, "All set!\n", ""
        ),
        "publication_guard": patch._command_evidence(
            patch.PUBLICATION_GUARD_COMMAND,
            "Checking tracked files before publication...\n"
            "OK: tracked files look publication-ready.\n",
            "",
        ),
        "git_diff_check": patch._command_evidence(
            patch.DIFF_CHECK_COMMAND, "", ""
        ),
        "execution_boundaries": dict(patch.VERIFICATION_EXECUTION_BOUNDARIES),
    }


def test_h_scope_is_exact_four_modifications_five_additions() -> None:
    expected_modified = {
        "src/experiments/audit_closure_anfis_ablation_model_bundle.py",
        "src/experiments/train_closure_anfis_ablation.py",
        "tests/test_audit_closure_anfis_ablation_model_bundle.py",
        "tests/test_train_closure_anfis_ablation.py",
    }
    expected_added = {
        "configs/closure_v1/anfis_ablation_training_cohort_patch_lock.schema.json",
        "docs/closure_v1/E0_M_ANFIS_ABLATION_TRAINING_COHORT_PATCH_1.md",
        "src/experiments/closure_anfis_ablation_training_cohort_patch.py",
        "src/experiments/lock_closure_anfis_ablation_training_cohort_patch.py",
        "tests/test_closure_anfis_ablation_training_cohort_patch.py",
    }
    assert patch.BASE_COMMIT == "1b68c24da4efe8fcf5eeb4b90ad0a99e95c96d93"
    assert set(patch.SUPERSEDED_MT_PATHS) == expected_modified
    assert set(patch.PATCH_PATHS) == expected_modified | expected_added
    assert len(patch.PATCH_PATHS) == 9
    assert len(patch.PRESERVED_MT_PATHS) == 6
    assert not any(path.startswith("private/") for path in patch.PATCH_PATHS)
    assert all(not path.endswith(".dvc") for path in patch.PATCH_PATHS)


def test_p_mt_topology_and_future_p_mu_paths_are_distinct() -> None:
    assert patch.MT_H_PARENT == "e22fd44d8a1e13c5587237d9f7a38856ae262864"
    assert patch.MT_H_HEAD == "f371786bc1e8d6c22b4d911145a57c623303b296"
    assert patch.MT_P_HEAD == patch.BASE_COMMIT
    assert set(patch.P_MT_PATHS) == {
        "reports/closure_v1/00_protocol/anfis_ablation_training_development_patch_lock.json",
        "reports/closure_v1/00_protocol/anfis_ablation_training_development_patch_lock_manifest.json",
    }
    assert patch.DEFAULT_PATCH_LOCK_PATH.as_posix().endswith(
        "anfis_ablation_training_cohort_patch_lock.json"
    )
    assert patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix().endswith(
        "anfis_ablation_training_cohort_patch_lock_manifest.json"
    )
    assert set(patch.P_MT_PATHS).isdisjoint(
        {
            patch.DEFAULT_PATCH_LOCK_PATH.as_posix(),
            patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
        }
    )


def test_correction_evidence_is_exactly_the_non_consuming_check_only_failure() -> None:
    assert patch.CORRECTION_EVIDENCE == {
        "invocation_mode": "--check-only",
        "p_mt_gate_status": "effective_preflight_passed",
        "pandas4warning_count": 2,
        "deprecated_operation": "set_index_verify_integrity",
        "terminal_error": "Raw observed count drifted for x_mean_TP_ugL",
        "trainer_cli_started": True,
        "check_only_preflight_started": True,
        "execute_one_shot_invoked": False,
        "fit_started": False,
        "guard_created": False,
        "writes_created": False,
        "dvc_commands_run": False,
        "future_outcomes_accessed": False,
        "development_targets_through_2020_read": True,
        "calibration_2021_targets_read": False,
        "holdout_or_post_2021_targets_read": False,
        "pseudo_training_rows": 17796,
        "pseudo_selection_rows": 1974,
        "observed_tp_value_count": 163839,
        "sealed_tp_value_count": 80271,
        "input_only_scaler_origin_count": 8352,
        "supervised_training_origin_count": 5932,
        "supervised_selection_origin_count": 658,
        "evidence_source": "derived_from_published_inputs_and_failed_check_only_facts",
        "stdout_persisted": False,
    }
    assert patch.LOCK_SEALS["failed_check_only_not_consumed"] is True
    assert patch.LOCK_SEALS["runtime_contract_unchanged"] is True


def test_immutable_runtime_retains_scaler_and_supervised_geometry() -> None:
    runtime = patch.load_anfis_ablation_training_runtime(
        verify_physical_pins=False
    )
    assert runtime["gate"] == "E0-MT"
    assert runtime["preprocessing"]["fit_role"] == "training"
    assert runtime["preprocessing"]["raw_training_statistics"][
        "x_mean_TP_ugL"
    ]["observed_cells"] == 80271
    assert runtime["targets"]["training"] == {"origins": 5932, "rows": 17796}
    assert runtime["targets"]["model_selection"] == {"origins": 658, "rows": 1974}
    assert runtime["outputs"]["exact_final_path_count"] == 80
    assert runtime["outputs"]["exact_temporary_path_count"] == 80
    assert runtime["outputs"]["exact_guard_path_count"] == 10
    assert runtime["outputs"]["exact_prediction_pointer_count"] == 10


def test_unpublished_authorizations_remain_closed() -> None:
    assert patch.UNPUBLISHED_AUTHORIZATIONS["publication_required"] is True
    assert all(
        value is False
        for key, value in patch.UNPUBLISHED_AUTHORIZATIONS.items()
        if key != "publication_required"
    )
    forbidden = {
        "calibration_authorized",
        "calibration_target_access_authorized",
        "final_e7_metrics_authorized",
        "rollout_authorized",
        "e0_m_authorized",
        "evaluation_authorized",
        "e0_u_authorized",
        "dvc_commands_authorized",
        "scientific_network_authorized",
        "outcome_access_authorized",
        "future_outcomes_accessed",
        "batch_slot_execution_authorized",
    }
    assert forbidden.issubset(patch.UNPUBLISHED_AUTHORIZATIONS)


def test_schema_is_closed_and_has_unique_required_keys() -> None:
    schema = json.loads(
        (ROOT / patch.DEFAULT_PATCH_LOCK_SCHEMA).read_text(encoding="utf-8")
    )
    assert schema["additionalProperties"] is False
    assert len(schema["required"]) == len(set(schema["required"]))
    closed = schema["$defs"]["closedAuthorizations"]
    assert closed["additionalProperties"] is False
    assert len(closed["required"]) == len(set(closed["required"]))
    assert all(
        definition.get("const") is False
        for key, definition in closed["properties"].items()
        if key != "publication_required"
    )
    assert closed["properties"]["publication_required"]["const"] is True


@pytest.mark.parametrize("unsupported", ("default", "examples"))
def test_schema_preflight_rejects_unsupported_semantic_keywords_first(
    tmp_path: Path,
    unsupported: str,
) -> None:
    schema = json.loads(
        (ROOT / patch.DEFAULT_PATCH_LOCK_SCHEMA).read_text(encoding="utf-8")
    )
    schema[unsupported] = [] if unsupported == "examples" else None
    target = tmp_path / patch.DEFAULT_PATCH_LOCK_SCHEMA
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(schema), encoding="utf-8")
    with pytest.raises(
        patch.AnfisAblationTrainingCohortPatchError, match="Unsupported"
    ):
        patch.preflight_anfis_ablation_training_cohort_patch_schema(
            repo_root=tmp_path
        )


def test_schema_preflight_rejects_float_numeric_const(tmp_path: Path) -> None:
    schema = json.loads(
        (ROOT / patch.DEFAULT_PATCH_LOCK_SCHEMA).read_text(encoding="utf-8")
    )
    schema["$defs"]["commandEvidence"]["properties"]["returncode"]["const"] = 0.0
    target = tmp_path / patch.DEFAULT_PATCH_LOCK_SCHEMA
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(schema), encoding="utf-8")
    with pytest.raises(patch.AnfisAblationTrainingCohortPatchError):
        patch.preflight_anfis_ablation_training_cohort_patch_schema(
            repo_root=tmp_path
        )


def test_canonical_json_is_stable_and_rejects_nan() -> None:
    assert patch._canonical_json({"b": 2, "a": 1}) == b'{"a":1,"b":2}\n'
    with pytest.raises(ValueError):
        patch._canonical_json({"bad": float("nan")})


def test_check_only_runs_schema_before_remote_prelock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_training_cohort_patch_schema",
        lambda: events.append("schema") or {"status": "schema_valid"},
    )
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_training_cohort_patch_prelock_state",
        lambda *, verify_remote: events.append("prelock")
        or {
            "repository": {"head": "1" * 40},
            "h_patch": {"component_count": 9},
            "companion_contract": {
                "physical_input_count": 64,
                "historical_input_count": 4,
            },
        },
    )
    result = locker.check_only()
    assert events == ["schema", "prelock"]
    assert result["status"] == "ready_to_lock"
    assert result["gate"] == "E0-MU"
    assert result["component_count"] == 9
    assert result["physical_input_count"] == 64
    assert result["historical_input_count"] == 4
    assert result["writes_performed"] is False
    assert result["verification_commands_run"] is False
    assert result["development_preflight_loader_run"] is False
    assert result["development_targets_through_2020_read_during_verification"] is False
    assert (
        result[
            "development_preprocessing_and_priors_reconstructed_during_verification"
        ]
        is False
    )
    assert result["trainer_entrypoint_run"] is False
    assert result["model_fit_or_optimization_run"] is False
    assert result["auditor_entrypoint_run"] is False
    assert result["calibration_2021_targets_read_during_verification"] is False
    assert result["holdout_or_post_2021_targets_read_during_verification"] is False
    assert result["dvc_commands_run"] is False
    assert result["future_outcomes_accessed"] is False


def test_execute_lock_calls_the_single_trusted_execution_boundary_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def trusted_boundary() -> tuple[dict[str, Any], dict[str, Any]]:
        nonlocal calls
        calls += 1
        return {"role": "lock"}, {"role": "companion"}

    monkeypatch.setattr(
        patch,
        "execute_and_publish_anfis_ablation_training_cohort_lock_bundle",
        trusted_boundary,
    )
    result = locker.execute_lock()
    assert calls == 1
    assert result["status"] == "locked_unpublished"
    assert result["development_preflight_loader_run"] is True
    assert result["development_targets_through_2020_read_during_verification"] is True
    assert (
        result[
            "development_preprocessing_and_priors_reconstructed_during_verification"
        ]
        is True
    )
    assert result["trainer_entrypoint_run"] is False
    assert result["model_fit_or_optimization_run"] is False
    assert result["auditor_entrypoint_run"] is False
    assert result["calibration_2021_targets_read_during_verification"] is False
    assert result["holdout_or_post_2021_targets_read_during_verification"] is False
    assert result["dvc_commands_run"] is False


def test_focused_summary_requires_one_exact_clean_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(patch, "FOCUSED_TEST_COUNT", 81)
    assert patch._parse_focused_summary("81 passed in 1.23s\n", "") == {
        "test_count": 81,
        "skipped_count": 0,
        "deselected_count": 0,
    }
    for stdout, stderr in (
        ("", ""),
        ("80 passed in 1.23s\n", ""),
        ("81 passed in 1.2s\n", ""),
        ("81 passed, 1 warning in 1.23s\n", ""),
        ("81 passed in 1.23s\n", "noise"),
        ("81 passed in 1.23s\n81 passed in 1.24s\n", ""),
    ):
        with pytest.raises(patch.AnfisAblationTrainingCohortPatchError):
            patch._parse_focused_summary(stdout, stderr)


def test_pytest_runner_overrides_hostile_inherited_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hostile = {
        "PYTEST_ADDOPTS": "--maxfail=1 -p hostile",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "0",
        "PYTEST_PLUGINS": "hostile_plugin",
        "PY_COLORS": "1",
    }
    for key, value in hostile.items():
        monkeypatch.setenv(key, value)
    observed: dict[str, str] = {}

    class Result:
        returncode = 0
        stdout = "synthetic success\n"
        stderr = ""

    def fake_run(command: list[str], **kwargs: Any) -> Result:
        assert command == ["synthetic-pytest"]
        environment = kwargs["env"]
        observed.update(
            {
                key: environment[key]
                for key in patch.FOCUSED_PYTEST_ENVIRONMENT
            }
        )
        return Result()

    monkeypatch.setattr(patch.subprocess, "run", fake_run)
    evidence, stdout, stderr = patch._run_command(
        ("synthetic-pytest",),
        repo_root=tmp_path,
        sanitize_pytest_environment=True,
    )
    assert observed == {
        "PYTEST_ADDOPTS": "",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTEST_PLUGINS": "",
        "PY_COLORS": "0",
    }
    assert evidence["returncode"] == 0
    assert stdout == "synthetic success\n"
    assert stderr == ""


@pytest.mark.parametrize(
    "mutation",
    ("empty_stdout", "false_summary", "hash_drift", "line_count_drift"),
)
def test_focused_evidence_binds_real_stdout_and_terminal_summary(
    mutation: str,
) -> None:
    verification = _verification_evidence()
    focused = verification["focused_tests"]
    assert isinstance(focused, dict)
    if mutation == "empty_stdout":
        focused["stdout_text"] = ""
    elif mutation == "false_summary":
        false_summary = f"{patch.FOCUSED_TEST_COUNT} passed, 1 warning in 1.23s\n"
        focused.update(
            {
                "stdout_text": false_summary,
                "stdout_sha256": patch._sha256_bytes(false_summary.encode("utf-8")),
                "stdout_line_count": 1,
            }
        )
    elif mutation == "hash_drift":
        focused["stdout_sha256"] = "f" * 64
    else:
        focused["stdout_line_count"] = int(focused["stdout_line_count"]) + 1
    with pytest.raises(
        patch.AnfisAblationTrainingCohortPatchError, match="focused"
    ):
        patch._validate_verification(verification, repo_root=ROOT)


@pytest.mark.parametrize(
    ("record_name", "field", "value"),
    (
        pytest.param("full_type_check", "returncode", 0.0, id="returncode-float"),
        pytest.param("full_type_check", "returncode", False, id="returncode-bool"),
        pytest.param(
            "focused_tests",
            "test_count",
            float(patch.FOCUSED_TEST_COUNT),
            id="test-count-float",
        ),
        pytest.param(
            "focused_tests",
            "skipped_count",
            False,
            id="skipped-count-bool",
        ),
    ),
)
def test_verification_numeric_evidence_requires_exact_integers(
    record_name: str,
    field: str,
    value: object,
) -> None:
    verification = _verification_evidence()
    record = verification[record_name]
    assert isinstance(record, dict)
    record[field] = value
    with pytest.raises(patch.AnfisAblationTrainingCohortPatchError):
        patch._validate_verification(verification, repo_root=ROOT)


def test_locker_commands_do_not_execute_science_or_dvc() -> None:
    commands = (
        patch.TYPE_CHECK_COMMAND,
        patch.FOCUSED_TEST_COMMAND,
        patch.POETRY_CHECK_COMMAND,
        patch.PUBLICATION_GUARD_COMMAND,
        patch.DIFF_CHECK_COMMAND,
    )
    command_text = "\n".join(" ".join(command) for command in commands).lower()
    assert "dvc" not in command_text
    forbidden_scripts = {
        "src/experiments/train_closure_anfis_ablation.py",
        "src/experiments/audit_closure_anfis_ablation_model_bundle.py",
    }
    assert all(token not in forbidden_scripts for command in commands for token in command)


def test_cli_requires_target_only_for_effective_mode() -> None:
    assert locker.parse_args(["--check-only"]).check_only is True
    assert locker.parse_args(["--execute-lock"]).execute_lock is True
    effective = locker.parse_args(
        ["--check-effective", "--model-id", "A0", "--base-seed", "1729"]
    )
    assert effective.model_id == "A0" and effective.base_seed == 1729
    for arguments in (
        ["--check-effective"],
        ["--check-effective", "--model-id", "A0"],
        ["--check-only", "--model-id", "A0", "--base-seed", "1729"],
        ["--check-only", "--execute-lock"],
    ):
        with pytest.raises(SystemExit):
            locker.parse_args(arguments)


def test_companion_binds_exactly_64_physical_plus_four_historical() -> None:
    runtime_physical = [
        _record(f"physical/runtime_{index:02d}.bin", f"runtime_{index:02d}", index)
        for index in range(47)
    ]
    preserved = [
        _record(f"preserved/mt_{index}.py", f"preserved_{index}", 50 + index)
        for index in range(6)
    ]
    h_components = [
        _record(path, patch.PATCH_COMPONENT_ROLES[path], 60 + index)
        for index, path in enumerate(patch.PATCH_PATHS)
    ]
    p_components = [
        _record(path, patch.P_MT_COMPONENT_ROLES[path], 70 + index)
        for index, path in enumerate(patch.P_MT_PATHS)
    ]
    historical = [
        {
            **_record(path, f"superseded_{index}", 80 + index),
            "commit": patch.MT_H_HEAD,
            "hash_source": "git_blob_at_commit",
            "current_bytes_required_to_match_historical": False,
        }
        for index, path in enumerate(patch.SUPERSEDED_MT_PATHS)
    ]
    payload = {
        "h_patch": {"components": h_components},
        "mt_authority": {
            "preserved_components": preserved,
            "historical_components": historical,
            "p_components": p_components,
        },
        "runtime_contract": {"physical_inputs": runtime_physical},
    }
    lock_record = _record(
        patch.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "anfis_ablation_training_cohort_patch_lock",
        90,
    )
    companion = patch._expected_companion(payload, lock_record)
    assert len(companion["inputs"]) == 64
    assert len({record["path"] for record in companion["inputs"]}) == 64
    assert len(companion["historical_inputs"]) == 4
    assert len({record["path"] for record in companion["historical_inputs"]}) == 4
    assert companion["script"] == next(
        record
        for record in h_components
        if record["path"] == patch.LOCKER_PATH.as_posix()
    )
    assert companion["outputs"] == [lock_record]
    assert companion["historical_inputs_compared_to_current_paths"] is False
    assert companion["manifest_written_last"] is True
    assert companion["development_preflight_loader_run"] is True
    assert (
        companion["development_targets_through_2020_read_during_verification"]
        is True
    )
    assert (
        companion[
            "development_preprocessing_and_priors_reconstructed_during_verification"
        ]
        is True
    )
    assert companion["trainer_entrypoint_run"] is False
    assert companion["auditor_entrypoint_run"] is False
    assert companion["model_fit_or_optimization_run"] is False
    assert companion["calibration_2021_targets_read_during_verification"] is False
    assert (
        companion["holdout_or_post_2021_targets_read_during_verification"]
        is False
    )
    assert companion["future_outcomes_accessed"] is False
    assert companion["dvc_commands_run"] is False
    assert "trainer_run" not in companion
    assert "data_execution_run" not in companion

    duplicate = copy.deepcopy(payload)
    duplicate["runtime_contract"]["physical_inputs"][0]["path"] = h_components[0][
        "path"
    ]
    with pytest.raises(
        patch.AnfisAblationTrainingCohortPatchError, match="64 unique"
    ):
        patch._expected_companion(duplicate, lock_record)

    duplicate_history = copy.deepcopy(payload)
    duplicate_history["mt_authority"]["historical_components"][0]["path"] = (
        duplicate_history["mt_authority"]["historical_components"][1]["path"]
    )
    with pytest.raises(
        patch.AnfisAblationTrainingCohortPatchError, match="four historical"
    ):
        patch._expected_companion(duplicate_history, lock_record)


def test_effective_flag_matrix_is_targeted_and_outcome_closed() -> None:
    a0 = patch._effective_authorizations(model_id="A0", audit=False)
    a1 = patch._effective_authorizations(model_id="A1", audit=False)
    audit = patch._effective_authorizations(model_id="A0", audit=True)
    assert a0["a0_development_fit_authorized"] is True
    assert a0["a1_development_fit_authorized"] is False
    assert a1["a0_development_fit_authorized"] is False
    assert a1["a1_development_fit_authorized"] is True
    assert audit["a0_development_fit_authorized"] is False
    assert audit["a1_development_fit_authorized"] is False
    assert audit["model_bundle_audit_authorized"] is True
    assert a0["model_bundle_audit_authorized"] is False
    for matrix in (a0, a1, audit):
        assert matrix["target_access_through_2020_authorized"] is True
        assert matrix["selection_diagnostics_authorized"] is True
        assert all(
            matrix[key] is False
            for key in (
                "calibration_authorized",
                "calibration_target_access_authorized",
                "final_e7_metrics_authorized",
                "rollout_authorized",
                "e0_m_authorized",
                "evaluation_authorized",
                "e0_u_authorized",
                "dvc_commands_authorized",
                "scientific_network_authorized",
                "outcome_access_authorized",
                "future_outcomes_accessed",
                "batch_slot_execution_authorized",
            )
        )


def test_effective_loader_refuses_disabling_live_remote_verification() -> None:
    with pytest.raises(
        patch.AnfisAblationTrainingCohortPatchError, match="live remote"
    ):
        patch.load_effective_anfis_ablation_training_cohort_authority(
            model_id="A0",
            base_seed=1729,
            verify_remote=False,
        )


@pytest.mark.parametrize(
    "arguments",
    (
        {
            "model_id": "A0",
            "base_seed": 1729,
            "audit_current_unpublished": 1,
        },
        {"audit_current_unpublished": True},
        {"model_id": "A0"},
        {"base_seed": 1729},
        {"model_id": 1, "base_seed": 1729},
        {"model_id": "A2", "base_seed": 1729},
        {"model_id": "A0", "base_seed": True},
        {"model_id": "A0", "base_seed": -1},
    ),
)
def test_effective_loader_rejects_invalid_target_before_any_lock_or_data_io(
    monkeypatch: pytest.MonkeyPatch,
    arguments: dict[str, Any],
) -> None:
    touched = False

    def forbidden_load(*args: Any, **kwargs: Any) -> Any:
        nonlocal touched
        touched = True
        raise AssertionError("lock/data I/O must not run")

    monkeypatch.setattr(patch, "_load_json", forbidden_load)
    with pytest.raises(patch.AnfisAblationTrainingCohortPatchError):
        patch.load_effective_anfis_ablation_training_cohort_authority(
            verify_remote=True,
            **arguments,
        )
    assert touched is False


def test_summary_loader_audits_complete_post_dvc_prefix_without_authorizing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"kind": "synthetic_lock"}
    companion = {"kind": "synthetic_companion"}
    pointer_paths = {
        patch.mt._pointer_path(model_id, base_seed)
        for model_id, base_seed in patch.ORDERED_SLOTS
    }
    pointer_reads: set[Path] = set()

    def load_json(path: Path, **kwargs: Any) -> dict[str, str]:
        return (
            payload
            if path == patch.DEFAULT_PATCH_LOCK_PATH
            else companion
        )

    monkeypatch.setattr(patch, "_load_json", load_json)
    monkeypatch.setattr(
        patch,
        "_read_regular_bytes",
        lambda path, **kwargs: patch._canonical_json(load_json(path)),
    )

    def lexists(path: Path) -> bool:
        relative = path.relative_to(tmp_path)
        pointer_reads.add(relative)
        return relative in pointer_paths

    monkeypatch.setattr(patch, "_lexists", lexists)
    validation_flags: list[bool] = []
    monkeypatch.setattr(
        patch,
        "validate_anfis_ablation_training_cohort_patch_lock_payload",
        lambda value, **kwargs: validation_flags.append(
            kwargs["allow_models_dvc_drift"]
        ),
    )
    monkeypatch.setattr(
        patch,
        "_file_record",
        lambda path, **kwargs: {"path": path.as_posix()},
    )
    monkeypatch.setattr(
        patch,
        "_expected_companion",
        lambda *args, **kwargs: companion,
    )
    monkeypatch.setattr(
        patch,
        "_validate_p_publication",
        lambda *args, **kwargs: {"h_patch_head": "1" * 40},
    )
    static = {"gate": "E0-MU", "status": "effective_preflight_passed"}
    monkeypatch.setattr(
        patch,
        "_static_effective_authority",
        lambda *args, **kwargs: static,
    )
    audit_modes: list[bool] = []

    def validate_prefix(
        authority: dict[str, str],
        *,
        audit_mode: bool,
        repo_root: Path,
    ) -> int:
        assert authority == static
        assert repo_root == tmp_path
        audit_modes.append(audit_mode)
        return 10

    monkeypatch.setattr(patch.mt, "_validate_exact_training_prefix", validate_prefix)

    result = patch.load_effective_anfis_ablation_training_cohort_authority(
        repo_root=tmp_path
    )
    assert pointer_reads == pointer_paths
    assert validation_flags == [True]
    assert audit_modes == [True]
    assert result["completed_prefix_count"] == 10
    assert result["authorized_model_id"] is None
    assert result["authorized_base_seed"] is None
    assert result["slot_creation_prefix_count"] is None
    assert all(
        result[key] is False for key in patch._summary_authorizations()
    )


def test_training_namespace_rejects_prediction_pointer_temporary(
    tmp_path: Path,
) -> None:
    pointer = patch.mt._pointer_path("A0", 1729)
    temporary = tmp_path / Path(pointer.as_posix() + ".tmp")
    temporary.parent.mkdir(parents=True)
    temporary.write_bytes(b"foreign")
    with pytest.raises(
        patch.AnfisAblationTrainingCohortPatchError, match="namespace"
    ):
        patch._training_namespace_absence(tmp_path)
    assert temporary.read_bytes() == b"foreign"


def test_single_parent_rejects_merge_topology(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "1" * 40
    monkeypatch.setattr(
        patch,
        "_git",
        lambda *args, **kwargs: f"{commit} {'2' * 40} {'3' * 40}",
    )
    with pytest.raises(
        patch.AnfisAblationTrainingCohortPatchError, match="non-merge"
    ):
        patch._single_parent(ROOT, commit, context="synthetic merge")


@pytest.mark.parametrize(
    ("commit", "paths", "context"),
    (
        ("1" * 40, patch.PATCH_PATHS, "H-E0-MU"),
        (patch.MT_H_HEAD, patch.mt.PATCH_PATHS, "H-E0-MT"),
        (patch.MT_P_HEAD, patch.P_MT_PATHS, "P-E0-MT"),
    ),
)
def test_reconstructed_authority_rejects_executable_git_mode(
    monkeypatch: pytest.MonkeyPatch,
    commit: str,
    paths: tuple[str, ...],
    context: str,
) -> None:
    bad_path = paths[-1]
    monkeypatch.setattr(
        patch.mt,
        "_git_mode",
        lambda repo_root, observed_commit, path: (
            "100755" if path == bad_path else "100644"
        ),
    )
    with pytest.raises(
        patch.AnfisAblationTrainingCohortPatchError, match="100644"
    ):
        patch._require_git_modes(ROOT, commit, paths, context=context)


def test_publisher_is_lock_then_manifest_last_and_cleans_control_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _synthetic_publish_payload()
    state = _patch_synthetic_publisher(monkeypatch, payload)
    order: list[str] = []
    real_publish = patch.mt._publish_bytes_no_clobber

    def ordered_publish(final_path: Path, body: bytes, *, repo_root: Path):
        order.append(final_path.as_posix())
        return real_publish(final_path, body, repo_root=repo_root)

    monkeypatch.setattr(patch.mt, "_publish_bytes_no_clobber", ordered_publish)
    lock, companion = patch.publish_anfis_ablation_training_cohort_lock_bundle(
        repo_root=tmp_path
    )
    assert state["verification_runs"] == 1
    assert lock == payload
    assert companion["completion_marker_written_last"] is True
    assert order == [
        patch.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
    ]
    assert json.loads(
        (tmp_path / patch.DEFAULT_PATCH_LOCK_PATH).read_text(encoding="utf-8")
    ) == payload
    assert json.loads(
        (tmp_path / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).read_text(
            encoding="utf-8"
        )
    ) == companion
    assert not (tmp_path / patch.LOCKER_GUARD_PATH).exists()
    assert not (
        tmp_path / patch.mt._temporary_path(patch.DEFAULT_PATCH_LOCK_PATH)
    ).exists()
    assert not (
        tmp_path / patch.mt._temporary_path(patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH)
    ).exists()


def test_publisher_rolls_back_lock_when_manifest_publication_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _synthetic_publish_payload()
    state = _patch_synthetic_publisher(monkeypatch, payload)
    real_publish = patch.mt._publish_bytes_no_clobber

    def fail_manifest(final_path: Path, body: bytes, *, repo_root: Path):
        if final_path == patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH:
            raise OSError("injected companion failure")
        return real_publish(final_path, body, repo_root=repo_root)

    monkeypatch.setattr(patch.mt, "_publish_bytes_no_clobber", fail_manifest)
    with pytest.raises(OSError, match="injected"):
        patch.publish_anfis_ablation_training_cohort_lock_bundle(
            repo_root=tmp_path
        )
    assert state["verification_runs"] == 1
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_PATH).exists()
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).exists()
    assert not (tmp_path / patch.LOCKER_GUARD_PATH).exists()


def test_publisher_refuses_existing_final_without_clobber(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _synthetic_publish_payload()
    state = _patch_synthetic_publisher(monkeypatch, payload)
    final = tmp_path / patch.DEFAULT_PATCH_LOCK_PATH
    final.parent.mkdir(parents=True)
    final.write_bytes(b"foreign")
    with pytest.raises(
        patch.AnfisAblationTrainingCohortPatchError, match="namespace is occupied"
    ):
        patch.publish_anfis_ablation_training_cohort_lock_bundle(
            repo_root=tmp_path
        )
    assert state["verification_runs"] == 1
    assert final.read_bytes() == b"foreign"
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).exists()
    assert not (tmp_path / patch.LOCKER_GUARD_PATH).exists()


def test_publisher_does_not_follow_controlled_temporary_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _synthetic_publish_payload()
    state = _patch_synthetic_publisher(monkeypatch, payload)
    foreign = tmp_path / "foreign"
    foreign.write_bytes(b"foreign")
    temporary = tmp_path / patch.mt._temporary_path(patch.DEFAULT_PATCH_LOCK_PATH)
    temporary.parent.mkdir(parents=True)
    temporary.symlink_to(foreign)
    with pytest.raises(
        patch.AnfisAblationTrainingCohortPatchError, match="namespace is occupied"
    ):
        patch.publish_anfis_ablation_training_cohort_lock_bundle(
            repo_root=tmp_path
        )
    assert state["verification_runs"] == 1
    assert temporary.is_symlink()
    assert foreign.read_bytes() == b"foreign"
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_PATH).exists()
    assert not (tmp_path / patch.LOCKER_GUARD_PATH).exists()


def test_publisher_rollback_preserves_foreign_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _synthetic_publish_payload()
    state = _patch_synthetic_publisher(monkeypatch, payload)
    real_publish = patch.mt._publish_bytes_no_clobber

    def replace_then_fail(final_path: Path, body: bytes, *, repo_root: Path):
        if final_path == patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH:
            raise OSError("injected companion failure")
        owned = real_publish(final_path, body, repo_root=repo_root)
        physical = repo_root / final_path
        physical.unlink()
        physical.write_bytes(b"foreign")
        return owned

    monkeypatch.setattr(patch.mt, "_publish_bytes_no_clobber", replace_then_fail)
    with pytest.raises(OSError, match="injected"):
        patch.publish_anfis_ablation_training_cohort_lock_bundle(
            repo_root=tmp_path
        )
    assert state["verification_runs"] == 1
    assert (tmp_path / patch.DEFAULT_PATCH_LOCK_PATH).read_bytes() == b"foreign"
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).exists()
    assert not (tmp_path / patch.LOCKER_GUARD_PATH).exists()


def test_publisher_parent_swap_rolls_back_through_retained_descriptors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _synthetic_publish_payload()
    state = _patch_synthetic_publisher(monkeypatch, payload)
    real_publish = patch.mt._publish_bytes_no_clobber
    swapped_parent: Path | None = None

    def swap_after_lock(final_path: Path, body: bytes, *, repo_root: Path):
        nonlocal swapped_parent
        owned = real_publish(final_path, body, repo_root=repo_root)
        if final_path == patch.DEFAULT_PATCH_LOCK_PATH:
            lexical_parent = repo_root / final_path.parent
            swapped_parent = lexical_parent.with_name("00_protocol_owned_old")
            lexical_parent.rename(swapped_parent)
            lexical_parent.mkdir()
        return owned

    monkeypatch.setattr(patch.mt, "_publish_bytes_no_clobber", swap_after_lock)
    with pytest.raises(
        (patch.AnfisAblationTrainingCohortPatchError, FileNotFoundError)
    ):
        patch.publish_anfis_ablation_training_cohort_lock_bundle(
            repo_root=tmp_path
        )
    assert state["verification_runs"] == 1
    assert swapped_parent is not None
    assert not (swapped_parent / patch.DEFAULT_PATCH_LOCK_PATH.name).exists()
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_PATH).exists()
    assert not (tmp_path / patch.DEFAULT_PATCH_LOCK_MANIFEST_PATH).exists()
    assert not (tmp_path / patch.LOCKER_GUARD_PATH).exists()


@pytest.mark.parametrize(
    "reason",
    (
        "final namespace is occupied",
        "guard namespace is occupied",
        "prediction pointer namespace is occupied",
        "repository ref drifted",
    ),
)
def test_publisher_recollects_and_rejects_bypass_before_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reason: str,
) -> None:
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_training_cohort_patch_schema",
        lambda **kwargs: {"status": "synthetic_schema_valid"},
    )
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_training_cohort_patch_prelock_state",
        lambda **kwargs: (_ for _ in ()).throw(
            patch.AnfisAblationTrainingCohortPatchError(reason)
        ),
    )
    acquired = False

    def forbidden_acquire(*args: Any, **kwargs: Any) -> Any:
        nonlocal acquired
        acquired = True
        raise AssertionError("guard acquisition must not run")

    monkeypatch.setattr(patch.mt, "_acquire_publication_guard", forbidden_acquire)
    with pytest.raises(patch.AnfisAblationTrainingCohortPatchError, match=reason):
        patch.publish_anfis_ablation_training_cohort_lock_bundle(repo_root=tmp_path)
    assert acquired is False


def test_publisher_rejects_prelock_snapshot_drift_before_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema_preflight = {"status": "synthetic_schema_valid"}
    monkeypatch.setattr(
        patch,
        "preflight_anfis_ablation_training_cohort_patch_schema",
        lambda **kwargs: schema_preflight,
    )
    payload = _synthetic_publish_payload()
    before = {key: copy.deepcopy(payload[key]) for key in PRELOCK_SECTION_KEYS}
    after = copy.deepcopy(before)
    after["repository"] = {"marker": "changed"}
    snapshots = iter((before, after))
    monkeypatch.setattr(
        patch,
        "collect_anfis_ablation_training_cohort_patch_prelock_state",
        lambda **kwargs: next(snapshots),
    )
    verification_runs = 0

    def run_verification(**kwargs: Any) -> dict[str, Any]:
        nonlocal verification_runs
        assert kwargs["expected_schema_preflight"] == schema_preflight
        verification_runs += 1
        return {"trusted": True}

    monkeypatch.setattr(
        patch,
        "run_anfis_ablation_training_cohort_patch_verification",
        run_verification,
    )
    acquired = False

    def forbidden_acquire(*args: Any, **kwargs: Any) -> Any:
        nonlocal acquired
        acquired = True
        raise AssertionError("guard acquisition must not run")

    monkeypatch.setattr(patch.mt, "_acquire_publication_guard", forbidden_acquire)
    with pytest.raises(
        patch.AnfisAblationTrainingCohortPatchError, match="prelock"
    ):
        patch.publish_anfis_ablation_training_cohort_lock_bundle(repo_root=tmp_path)
    assert verification_runs == 1
    assert acquired is False


def test_public_publisher_rejects_caller_supplied_payload_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = False

    def forbidden_boundary(**kwargs: Any) -> Any:
        nonlocal entered
        entered = True
        raise AssertionError("trusted execution boundary must not run")

    monkeypatch.setattr(
        patch,
        "execute_and_publish_anfis_ablation_training_cohort_lock_bundle",
        forbidden_boundary,
    )
    publisher: Any = patch.publish_anfis_ablation_training_cohort_lock_bundle
    with pytest.raises(TypeError):
        publisher(_synthetic_publish_payload(), repo_root=tmp_path)
    assert entered is False
