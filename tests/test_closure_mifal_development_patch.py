from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.experiments import closure_mifal_development_patch as patch
from src.experiments import lock_closure_mifal_development_patch as locker


def _record(path: str, role: str, marker: int) -> dict[str, Any]:
    return {
        "path": path,
        "role": role,
        "bytes": marker + 1,
        "sha256": f"{marker % 16:x}" * 64,
    }


def _command_evidence(
    command: tuple[str, ...],
    stdout: str,
    stderr: str = "",
) -> dict[str, Any]:
    return {
        "command": list(command),
        "returncode": 0,
        "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
        "stdout_line_count": len(stdout.splitlines()),
        "stderr_line_count": len(stderr.splitlines()),
    }


def _verification_bundle(schema_preflight: dict[str, Any]) -> dict[str, Any]:
    focused = _command_evidence(
        patch.FOCUSED_TEST_COMMAND,
        f"dots\n{patch.FOCUSED_TEST_COUNT} passed in 1.00s\n",
    )
    focused.update(
        {
            "test_count": patch.FOCUSED_TEST_COUNT,
            "skipped_count": 0,
            "deselected_count": 0,
        }
    )
    return {
        "schema_preflight": schema_preflight,
        "full_type_check": _command_evidence(
            patch.TYPE_CHECK_COMMAND, "All checks passed!\n"
        ),
        "focused_tests": focused,
        "poetry_check": _command_evidence(
            patch.POETRY_CHECK_COMMAND, "All set!\n"
        ),
        "publication_guard": _command_evidence(
            patch.PUBLICATION_GUARD_COMMAND,
            "Checking tracked files before publication...\n"
            "OK: tracked files look publication-ready.\n",
        ),
        "git_diff_check": _command_evidence(patch.DIFF_CHECK_COMMAND, ""),
    }


def _synthetic_lock_payload(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    h_head = "1" * 40
    components = [
        _record(path, patch.PATCH_COMPONENT_ROLES[path], index)
        for index, path in enumerate(patch.PATCH_PATHS)
    ]
    physical_inputs = [
        _record(path, patch.PHYSICAL_INPUT_ROLES[path], index + len(components))
        for index, path in enumerate(patch.PHYSICAL_INPUT_PATHS)
    ]
    runtime = patch.load_and_validate_mifal_development_runtime(
        verify_physical_pins=False
    )
    runtime_record = next(
        record
        for record in components
        if record["path"] == patch.DEFAULT_RUNTIME_PATH.as_posix()
    )
    prelock = {
        "repository": {
            "head": h_head,
            "parent": patch.PATCH_BASE_COMMIT,
            "branch": "main",
            "tracking_ref": patch.PUBLISHED_REF,
            "tracking_head": h_head,
            "remote_head": h_head,
            "remote_observation_mode": "live_remote_main_verified",
            "worktree_status": "clean",
        },
        "h_patch": {
            "base_commit": patch.PATCH_BASE_COMMIT,
            "added_count": 9,
            "modified_count": 0,
            "deleted_count": 0,
            "paths": list(patch.PATCH_PATHS),
            "paths_sha256": patch._path_digest(patch.PATCH_PATHS),
            "components": components,
            "components_sha256": patch._record_digest(components),
        },
        "runtime_contract": patch._runtime_contract_binding(
            runtime_record=runtime_record,
            physical_inputs=physical_inputs,
        ),
        "prelock": patch._derived_prelock_binding(runtime),
    }
    preflight = patch.preflight_mifal_development_patch_schema()
    payload = patch.build_mifal_development_patch_lock_payload(
        prelock,
        _verification_bundle(preflight),
        created_at_utc="2026-08-07T12:00:00+00:00",
    )

    def fake_git(*args: str, repo_root: Path | None = None) -> str:
        del repo_root
        if args == ("rev-parse", "HEAD"):
            return h_head
        if args == ("branch", "--show-current"):
            return "main"
        if args == ("rev-parse", patch.PUBLISHED_REF):
            return h_head
        if args == ("status", "--porcelain=v1", "--untracked-files=all"):
            return ""
        raise AssertionError(f"Unexpected synthetic Git command: {args}")

    monkeypatch.setattr(patch, "_git", fake_git)
    monkeypatch.setattr(
        patch,
        "_single_parent",
        lambda commit, repo_root=None: patch.PATCH_BASE_COMMIT,
    )
    monkeypatch.setattr(
        patch,
        "_live_remote_main_head",
        lambda repo_root=None: h_head,
    )
    monkeypatch.setattr(
        patch,
        "_reconstruct_h_components",
        lambda value, repo_root=None: copy.deepcopy(components),
    )
    monkeypatch.setattr(
        patch,
        "_verify_runtime_physical_pins",
        lambda value, repo_root=None: copy.deepcopy(physical_inputs),
    )
    return payload


def _runtime() -> dict[str, Any]:
    return yaml.safe_load(
        (locker.PROJECT_ROOT / patch.DEFAULT_RUNTIME_PATH).read_text(encoding="utf-8")
    )


def _schema() -> dict[str, Any]:
    return json.loads(
        (locker.PROJECT_ROOT / patch.DEFAULT_PATCH_LOCK_SCHEMA).read_text(
            encoding="utf-8"
        )
    )


def _patch_locker_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(locker, "PROJECT_ROOT", root)
    monkeypatch.setattr(
        locker,
        "OUTPUT_GUARD_DIRECTORY",
        root / "tmp" / "closure_v1_e0_mr_locker",
    )
    monkeypatch.setattr(
        locker,
        "OUTPUT_GUARD_PATH",
        root
        / "tmp"
        / "closure_v1_e0_mr_locker"
        / "mifal_development_patch_lock.guard",
    )


def test_runtime_freezes_exact_h_scope_and_future_p_scope() -> None:
    runtime = _runtime()
    assert runtime["patch_scope"]["exact_added_count"] == 9
    assert runtime["patch_scope"]["exact_modified_count"] == 0
    assert runtime["patch_scope"]["exact_deleted_count"] == 0
    assert len(runtime["patch_scope"]["paths"]) == 9
    assert len(set(runtime["patch_scope"]["paths"])) == 9
    assert patch.DEFAULT_PATCH_LOCK_PATH.as_posix() == (
        "reports/closure_v1/00_protocol/mifal_development_patch_lock.json"
    )
    assert patch.DEFAULT_PATCH_MANIFEST_PATH.as_posix() == (
        "reports/closure_v1/00_protocol/"
        "mifal_development_patch_lock_manifest.json"
    )


def test_schema_freezes_nine_additions_and_all_authorizations_false() -> None:
    schema = _schema()
    h_patch = schema["$defs"]["hPatch"]["properties"]
    assert h_patch["added_count"]["const"] == 9
    assert h_patch["modified_count"]["const"] == 0
    assert h_patch["deleted_count"]["const"] == 0
    authorizations = schema["$defs"]["authorizations"]
    assert authorizations["required"]
    for name in authorizations["required"]:
        expected = name == "publication_required"
        assert authorizations["properties"][name]["const"] is expected


def test_runtime_freezes_strict_non_chlorophyll_projection() -> None:
    runtime = _runtime()
    adapter = runtime["strict_adapter"]
    assert adapter["variable_order"] == ["Tw", "TP", "TN", "Secchi", "Turb", "DOb"]
    assert adapter["minimum_observed_evidence_groups"] == 2
    assert adapter["target_artifact_inputs"] == []
    assert adapter["target_columns_scanned"] == []
    assert adapter["legacy_adapter_direct_import_authorized"] is False
    assert adapter["legacy_adapter_invocation_authorized"] is False
    assert adapter["legacy_adapter_data_projection_authorized"] is False
    assert adapter["package_initializer_symbol_loading"] == (
        "incidental_non_authoritative_no_io"
    )
    projection = adapter["exact_panel_projection"]
    assert len(projection) == 27
    assert all("chla" not in column.lower() for column in projection)


def test_runtime_freezes_global_prior_without_observed_memory() -> None:
    model = _runtime()["model"]
    assert model["core_version"] == "5.0.0"
    assert model["configuration"] == "v5_dataclass_defaults_without_tuning"
    assert model["initial_state"] == [0.05, 0.35]
    assert model["gammaM"] == 0.28
    assert model["missing_memory_fallback_interval"] == [0.0, 0.35]
    assert model["structural_memory_semantics"] == (
        "global_constant_prior_not_observed_or_site_specific_memory"
    )
    assert model["observed_memory_inputs"] == []
    assert model["observed_chlorophyll_inputs"] == []
    assert model["technical_seed"] == 1729
    assert model["step_call"] == {
        "dt_days_formula": "horizon_months_times_30_4375",
        "days_per_horizon_month": 30.4375,
        "assimilate": False,
        "update_state": False,
        "compute_voi": False,
    }


def test_raw_contract_is_exactly_twenty_eight_columns_and_probability_null() -> None:
    runtime = _runtime()
    contract = runtime["outputs"]["raw_prediction_contract"]
    columns = contract["columns"]
    assert len(columns) == 28
    assert len({column["name"] for column in columns}) == 28
    assert runtime["outputs"]["exact_raw_prediction_rows"] == 29_196
    assert contract["availability_status_values"] == ["success", "input_ineligible"]
    assert contract["success_probability_policy"] == (
        "predicted_bloom_probability_is_null_before_common_calibration"
    )
    assert contract["execution_exception_policy"] == (
        "transaction_abort_with_owned_inode_rollback"
    )
    assert runtime["model"]["predicted_bloom_probability_state"] == (
        "null_until_future_common_calibration"
    )


def test_runtime_freezes_input_only_eligibility_snapshot() -> None:
    denominators = _runtime()["denominators"]
    assert denominators["common_origin_rows"] == 29_196
    assert denominators["intent_origins"] == 9_732
    assert denominators["development_locations"] == 353
    assert denominators["evidence_group_snapshot_origins"] == {
        "eligible": 9_732,
        "ineligible": 0,
        "with_4_groups": 9_209,
        "with_3_groups": 505,
        "with_2_groups": 18,
        "with_1_group": 0,
        "with_0_groups": 0,
    }


def test_schema_preflight_is_definition_safe() -> None:
    result = patch.preflight_mifal_development_patch_schema()
    assert result["supported_subset_verified"] is True
    assert result["minimum_keyword_absent"] is True
    assert result["format_keyword_absent"] is True


def test_runtime_validator_accepts_the_closed_scientific_contract() -> None:
    runtime = patch.load_and_validate_mifal_development_runtime(
        verify_physical_pins=False
    )
    assert runtime["gate"] == "E0-MR"
    assert runtime["status"] == "ready_to_lock"


def test_companion_binds_exactly_thirty_two_inputs_and_locker_script() -> None:
    components = [
        _record(path, patch.PATCH_COMPONENT_ROLES[path], index)
        for index, path in enumerate(patch.PATCH_PATHS)
    ]
    physical_inputs = [
        _record(path, patch.PHYSICAL_INPUT_ROLES[path], index + len(components))
        for index, path in enumerate(patch.PHYSICAL_INPUT_PATHS)
    ]
    payload = {
        "h_patch": {
            "base_commit": patch.PATCH_BASE_COMMIT,
            "added_count": 9,
            "modified_count": 0,
            "deleted_count": 0,
            "paths": list(patch.PATCH_PATHS),
            "paths_sha256": patch._path_digest(patch.PATCH_PATHS),
            "components": components,
            "components_sha256": patch._record_digest(components),
        },
        "runtime_contract": {"physical_inputs": physical_inputs},
    }
    lock_record = _record(
        patch.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "mifal_development_patch_lock",
        40,
    )
    companion = patch._expected_companion(payload, lock_record)
    assert len(companion["inputs"]) == 32
    assert len({record["path"] for record in companion["inputs"]}) == 32
    assert companion["script"] in companion["inputs"]
    assert companion["script"]["path"] == (
        "src/experiments/lock_closure_mifal_development_patch.py"
    )
    assert companion["outputs"] == [lock_record]
    assert companion["historical_inputs"] == []
    assert companion["physical_inputs_only"] is True
    assert companion["manifest_written_last"] is True


def test_payload_validator_rejects_false_seals_across_every_authority_layer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _synthetic_lock_payload(monkeypatch)
    assert patch.validate_mifal_development_patch_lock_payload(payload) == payload

    def mutate_h_component(value: dict[str, Any]) -> None:
        value["h_patch"]["components"][0]["sha256"] = "f" * 64
        value["h_patch"]["components_sha256"] = patch._record_digest(
            value["h_patch"]["components"]
        )

    def mutate_physical_input(value: dict[str, Any]) -> None:
        value["runtime_contract"]["physical_inputs"][0]["sha256"] = "e" * 64
        value["runtime_contract"]["physical_inputs_sha256"] = patch._record_digest(
            value["runtime_contract"]["physical_inputs"]
        )

    def mutate_final_namespace(value: dict[str, Any]) -> None:
        paths = value["prelock"]["output_namespace"]["final_paths"]
        paths[0] = "data/closure_v1/development/mifal/M0/false.parquet"
        value["prelock"]["output_namespace"]["final_paths_sha256"] = (
            patch._path_digest(paths)
        )

    def mutate_temporary_namespace(value: dict[str, Any]) -> None:
        paths = value["prelock"]["output_namespace"]["temporary_paths"]
        paths[0] = "data/closure_v1/development/mifal/M0/false.parquet.tmp"
        value["prelock"]["output_namespace"]["temporary_paths_sha256"] = (
            patch._path_digest(paths)
        )

    def mutate_runtime_record(value: dict[str, Any]) -> None:
        value["runtime_contract"]["record"]["sha256"] = "d" * 64

    def mutate_raw_contract(value: dict[str, Any]) -> None:
        value["runtime_contract"]["raw_prediction_contract"][
            "candidate_policy"
        ] = "false_candidate"

    def mutate_projection(value: dict[str, Any]) -> None:
        value["runtime_contract"]["panel_projection"][0] = "false_column"

    mutations: tuple[tuple[str, Any], ...] = (
        ("tracking ref", lambda value: value["repository"].__setitem__("tracking_head", "2" * 40)),
        ("remote ref", lambda value: value["repository"].__setitem__("remote_head", "3" * 40)),
        ("parent", lambda value: value["repository"].__setitem__("parent", "4" * 40)),
        ("H component/blob", mutate_h_component),
        ("runtime record", mutate_runtime_record),
        ("physical pin", mutate_physical_input),
        ("raw contract", mutate_raw_contract),
        ("panel projection", mutate_projection),
        ("final namespace", mutate_final_namespace),
        ("temporary namespace", mutate_temporary_namespace),
        (
            "future pointer",
            lambda value: value["prelock"]["output_namespace"].__setitem__(
                "future_pointer_path", "data/closure_v1/development/mifal/M0/false.dvc"
            ),
        ),
        (
            "guard",
            lambda value: value["prelock"]["output_namespace"].__setitem__(
                "guard_path", "tmp/false.guard"
            ),
        ),
        (
            "E0-M namespace",
            lambda value: value["prelock"]["e0_m_paths"].__setitem__(
                0, "reports/closure_v1/00_protocol/false_lock.yaml"
            ),
        ),
        (
            "outcome namespace",
            lambda value: value["prelock"].__setitem__(
                "outcome_access_log_path", "reports/closure_v1/00_protocol/false.jsonl"
            ),
        ),
        (
            "execution flag",
            lambda value: value["prelock"].__setitem__("dvc_commands_run", True),
        ),
    )
    for _context, mutate in mutations:
        candidate = copy.deepcopy(payload)
        mutate(candidate)
        with pytest.raises(patch.MifalDevelopmentPatchError):
            patch.validate_mifal_development_patch_lock_payload(candidate)


def test_publication_guard_accepts_only_exact_two_line_success() -> None:
    locker._require_publication_guard_success(
        "Checking tracked files before publication...\n"
        "OK: tracked files look publication-ready.\n",
        "",
    )


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [
        (
            "Checking tracked files before publication...\n"
            "Repository publication guard passed.\n",
            "",
        ),
        (
            "Checking tracked files before publication...\n"
            "OK: tracked files look publication-ready.\n"
            "OK: tracked files look publication-ready.\n",
            "",
        ),
        (
            "Checking tracked files before publication...\n"
            "OK: tracked files look publication-ready.\n",
            "unexpected stderr",
        ),
        (
            "Checking tracked files before publication...\n\n"
            "OK: tracked files look publication-ready.\n",
            "",
        ),
    ],
)
def test_publication_guard_rejects_old_repeated_ambiguous_or_stderr(
    stdout: str,
    stderr: str,
) -> None:
    with pytest.raises(
        patch.MifalDevelopmentPatchError,
        match="single exact success",
    ):
        locker._require_publication_guard_success(stdout, stderr)


def test_check_only_runs_schema_before_remote_prelock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        patch,
        "preflight_mifal_development_patch_schema",
        lambda: events.append("schema") or {"gate": "E0-MR"},
    )
    monkeypatch.setattr(
        patch,
        "collect_mifal_development_patch_prelock_state",
        lambda: events.append("prelock")
        or {
            "repository": {"head": "1" * 40},
            "h_patch": {
                "added_count": 9,
                "modified_count": 0,
                "components": [None] * 9,
            },
        },
    )
    result = locker.check_only()
    assert events == ["schema", "prelock"]
    assert result["component_count"] == 9
    assert result["h_added_count"] == 9
    assert result["h_modified_count"] == 0
    assert result["writes_performed"] is False
    assert result["verification_commands_run"] is False
    assert result["dvc_commands_run"] is False
    assert result["network_commands_run"] is True
    assert result["scientific_network_commands_run"] is False
    assert result["future_outcomes_accessed"] is False


def test_execute_lock_recollects_before_two_output_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    prelock = {
        "repository": {"head": "1" * 40},
        "h_patch": {
            "added_count": 9,
            "modified_count": 0,
            "components": [None] * 9,
        },
    }
    verification = {"focused_tests": {"test_count": 1}}
    payload = {"gate": "E0-MR"}
    monkeypatch.setattr(
        patch,
        "preflight_mifal_development_patch_schema",
        lambda: events.append("schema") or {"gate": "E0-MR"},
    )
    monkeypatch.setattr(
        patch,
        "collect_mifal_development_patch_prelock_state",
        lambda: events.append("prelock") or prelock,
    )
    monkeypatch.setattr(
        locker,
        "run_mifal_development_patch_verification",
        lambda **kwargs: events.append("verify") or verification,
    )

    def build(
        observed_prelock: dict[str, Any],
        observed_verification: dict[str, Any],
        *,
        created_at_utc: str,
    ) -> dict[str, Any]:
        assert observed_prelock is prelock
        assert observed_verification is verification
        assert created_at_utc.endswith("+00:00")
        events.append("build")
        return payload

    monkeypatch.setattr(patch, "build_mifal_development_patch_lock_payload", build)
    monkeypatch.setattr(
        patch,
        "validate_mifal_development_patch_lock_payload",
        lambda value: events.append("validate") or value,
    )
    monkeypatch.setattr(
        locker,
        "_publish_lock_bundle",
        lambda value: events.append("publish") or (value, {}),
    )
    result = locker.execute_lock()
    assert events == [
        "schema",
        "prelock",
        "verify",
        "prelock",
        "build",
        "validate",
        "publish",
    ]
    assert result["published_output_count"] == 2
    assert result["mifal_one_shot_authorized"] is False
    assert result["calibration_authorized"] is False
    assert result["evaluation_authorized"] is False
    assert result["dvc_commands_run"] is False
    assert result["network_commands_run"] is True
    assert result["scientific_network_commands_run"] is False
    assert result["future_outcomes_accessed"] is False


def test_focused_summary_requires_one_exact_clean_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(patch, "FOCUSED_TEST_COUNT", 41)
    assert locker._parse_focused_summary("41 passed in 12.34s\n", "") == {
        "test_count": 41,
        "skipped_count": 0,
        "deselected_count": 0,
    }
    with pytest.raises(patch.MifalDevelopmentPatchError):
        locker._parse_focused_summary("41 passed, 1 warning in 12.34s\n", "")


def test_validator_accepts_exact_deterministic_command_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preflight = {"gate": "E0-MR"}
    monkeypatch.setattr(patch, "FOCUSED_TEST_COUNT", 59)
    monkeypatch.setattr(
        patch,
        "preflight_mifal_development_patch_schema",
        lambda **kwargs: preflight,
    )
    patch._validate_verification_binding(_verification_bundle(preflight))


def test_validator_rejects_schema_valid_false_command_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preflight = {"gate": "E0-MR"}
    monkeypatch.setattr(patch, "FOCUSED_TEST_COUNT", 59)
    monkeypatch.setattr(
        patch,
        "preflight_mifal_development_patch_schema",
        lambda **kwargs: preflight,
    )
    baseline = _verification_bundle(preflight)
    mutations = (
        ("full_type_check", "false type marker\n", ""),
        ("poetry_check", "false poetry marker\n", ""),
        (
            "publication_guard",
            "Checking tracked files before publication...\n"
            "Repository publication guard passed.\n",
            "",
        ),
        ("git_diff_check", "dirty diff\n", ""),
        ("full_type_check", "All checks passed!\n", "unexpected stderr\n"),
    )
    command_by_field = {
        "full_type_check": patch.TYPE_CHECK_COMMAND,
        "poetry_check": patch.POETRY_CHECK_COMMAND,
        "publication_guard": patch.PUBLICATION_GUARD_COMMAND,
        "git_diff_check": patch.DIFF_CHECK_COMMAND,
    }
    for field, stdout, stderr in mutations:
        candidate = copy.deepcopy(baseline)
        candidate[field] = _command_evidence(
            command_by_field[field], stdout, stderr
        )
        with pytest.raises(patch.MifalDevelopmentPatchError):
            patch._validate_verification_binding(candidate)
    false_command = copy.deepcopy(baseline)
    false_command["full_type_check"]["command"] = ["false-evidence"]
    with pytest.raises(patch.MifalDevelopmentPatchError):
        patch._validate_verification_binding(false_command)


def test_locker_commands_exclude_science_dvc_auditors_and_outcomes() -> None:
    commands = (
        patch.TYPE_CHECK_COMMAND,
        patch.FOCUSED_TEST_COMMAND,
        patch.POETRY_CHECK_COMMAND,
        patch.PUBLICATION_GUARD_COMMAND,
        patch.DIFF_CHECK_COMMAND,
    )
    command_text = "\n".join(" ".join(command) for command in commands).lower()
    for forbidden in ("dvc", "audit", "outcome_access_log"):
        assert forbidden not in command_text
    assert all(
        token != "src/experiments/run_closure_mifal.py"
        for command in commands
        for token in command
    )


def test_guard_parent_symlink_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "tmp").symlink_to(outside, target_is_directory=True)
    with pytest.raises(patch.MifalDevelopmentPatchError):
        locker._acquire_guard()


def test_guard_write_failure_removes_only_owned_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)

    def fail_write(descriptor: int, payload: bytes, *, context: str) -> None:
        raise OSError("injected guard write failure")

    monkeypatch.setattr(locker, "_write_all", fail_write)
    with pytest.raises(OSError, match="injected"):
        locker._acquire_guard()
    assert not os.path.lexists(locker.OUTPUT_GUARD_PATH)


def test_guard_write_failure_preserves_foreign_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)

    def replace_then_fail(descriptor: int, payload: bytes, *, context: str) -> None:
        locker.OUTPUT_GUARD_PATH.unlink()
        locker.OUTPUT_GUARD_PATH.write_bytes(b"foreign")
        raise OSError("injected replacement")

    monkeypatch.setattr(locker, "_write_all", replace_then_fail)
    with pytest.raises(
        patch.MifalDevelopmentPatchError,
        match="cleanup failed closed",
    ):
        locker._acquire_guard()
    assert locker.OUTPUT_GUARD_PATH.read_bytes() == b"foreign"


def test_temporary_fsync_failure_rolls_back_owned_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)
    parent = tmp_path / "reports" / "closure_v1" / "00_protocol"
    parent.mkdir(parents=True)
    expected = Path("reports/closure_v1/00_protocol/item.tmp")
    real_fsync = locker.os.fsync
    calls = 0

    def fail_once(descriptor: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("injected fsync failure")
        real_fsync(descriptor)

    monkeypatch.setattr(locker.os, "fsync", fail_once)
    with pytest.raises(OSError, match="injected"):
        locker._write_temp(tmp_path / expected, expected, b"owned")
    assert not os.path.lexists(tmp_path / expected)


def test_temp_symlink_is_not_followed_or_clobbered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)
    parent = tmp_path / "reports" / "closure_v1" / "00_protocol"
    parent.mkdir(parents=True)
    foreign = tmp_path / "foreign"
    foreign.write_bytes(b"foreign")
    expected = Path("reports/closure_v1/00_protocol/item.tmp")
    (tmp_path / expected).symlink_to(foreign)
    with pytest.raises(patch.MifalDevelopmentPatchError, match="clobber"):
        locker._write_temp(tmp_path / expected, expected, b"owned")
    assert foreign.read_bytes() == b"foreign"


def test_owned_rollback_preserves_foreign_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)
    parent = tmp_path / "reports" / "closure_v1" / "00_protocol"
    parent.mkdir(parents=True)
    expected = Path("reports/closure_v1/00_protocol/item.tmp")
    owner = locker._write_temp(tmp_path / expected, expected, b"owned")
    os.unlink(owner.path.name, dir_fd=owner.directory_file_descriptor)
    (tmp_path / expected).write_bytes(b"foreign")
    try:
        with pytest.raises(patch.MifalDevelopmentPatchError, match="foreign"):
            locker._rollback_if_owned(owner, context="test")
        assert (tmp_path / expected).read_bytes() == b"foreign"
    finally:
        locker._close_owner(owner)


def test_publication_refuses_existing_final_without_losing_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)
    parent = tmp_path / "reports" / "closure_v1" / "00_protocol"
    parent.mkdir(parents=True)
    guard = locker._acquire_guard()
    temp_expected = Path("reports/closure_v1/00_protocol/item.tmp")
    final_expected = Path("reports/closure_v1/00_protocol/item.json")
    temp = locker._write_temp(tmp_path / temp_expected, temp_expected, b"owned")
    (tmp_path / final_expected).write_bytes(b"foreign")
    try:
        with pytest.raises(patch.MifalDevelopmentPatchError, match="clobber"):
            locker._publish_temp(
                temp,
                tmp_path / final_expected,
                final_expected,
                guard,
            )
        assert (tmp_path / final_expected).read_bytes() == b"foreign"
        assert locker._owner_state(temp) == "owned"
    finally:
        locker._rollback_if_owned(temp, context="test temporary")
        locker._close_owner(temp)
        locker._release_guard(guard)


def test_lock_bundle_publishes_companion_last_and_cleans_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)
    parent = tmp_path / "reports" / "closure_v1" / "00_protocol"
    parent.mkdir(parents=True)
    lock_path = Path("reports/closure_v1/00_protocol/lock.json")
    manifest_path = Path("reports/closure_v1/00_protocol/lock_manifest.json")
    monkeypatch.setattr(patch, "DEFAULT_PATCH_LOCK_PATH", lock_path)
    monkeypatch.setattr(patch, "DEFAULT_PATCH_MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(
        patch,
        "_expected_companion",
        lambda payload, record: {
            "payload_sha256": record["sha256"],
            "manifest_written_last": True,
        },
    )
    locker._publish_lock_bundle({"gate": "E0-MR"})
    assert (tmp_path / lock_path).is_file()
    assert (tmp_path / manifest_path).is_file()
    assert (tmp_path / manifest_path).stat().st_mtime_ns >= (
        tmp_path / lock_path
    ).stat().st_mtime_ns
    assert not os.path.lexists(Path((tmp_path / lock_path).as_posix() + ".tmp"))
    assert not os.path.lexists(Path((tmp_path / manifest_path).as_posix() + ".tmp"))
    assert not os.path.lexists(locker.OUTPUT_GUARD_PATH)


def test_cli_modes_are_mutually_exclusive() -> None:
    assert locker.parse_args(["--check-only"]).check_only is True
    with pytest.raises(SystemExit):
        locker.parse_args(["--check-only", "--execute-lock"])
