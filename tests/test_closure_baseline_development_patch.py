from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import pytest

from src.experiments import closure_baseline_development_patch as patch
from src.experiments import lock_closure_baseline_development_patch as locker


def _record(path: str, role: str, marker: int) -> dict[str, Any]:
    return {
        "path": path,
        "role": role,
        "bytes": marker + 1,
        "sha256": f"{marker % 16:x}" * 64,
    }


def _command(command: list[str]) -> dict[str, Any]:
    return {
        "command": command,
        "returncode": 0,
        "stdout_sha256": "a" * 64,
        "stderr_sha256": "b" * 64,
        "stdout_line_count": 1,
        "stderr_line_count": 0,
    }


def _sample_payload() -> dict[str, Any]:
    runtime = patch.load_and_validate_baseline_development_runtime(
        verify_physical_pins=False
    )
    components = [
        _record(path, patch.PATCH_COMPONENT_ROLES[path], index)
        for index, path in enumerate(patch.PATCH_PATHS)
    ]
    physical_inputs = [
        _record(f"physical/input_{index:02d}.bin", f"physical_{index:02d}", index + 8)
        for index in range(patch.EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT)
    ]
    finals = patch.baseline_final_paths(runtime)
    temporaries = tuple(f"{path}.tmp" for path in finals)
    future_pointers = tuple(runtime["dvc"]["future_pointer_paths"])
    pointer_temporaries = tuple(f"{path}.tmp" for path in future_pointers)
    preflight = patch.preflight_baseline_development_patch_schema()
    focused = {
        **_command(list(patch.FOCUSED_TEST_COMMAND)),
        "test_count": patch.FOCUSED_TEST_COUNT,
        "skipped_count": 0,
        "deselected_count": 0,
    }
    return {
        "lock_version": patch.LOCK_VERSION,
        "gate": patch.PATCH_GATE,
        "patch_id": patch.PATCH_ID,
        "experiment_id": patch.EXPERIMENT_ID,
        "surface_id": patch.SURFACE_ID,
        "status": "locked_unpublished",
        "created_at_utc": "2026-08-07T12:00:00+00:00",
        "repository": {
            "head": "1" * 40,
            "parent": patch.PATCH_BASE_COMMIT,
            "branch": "main",
            "tracking_ref": patch.PUBLISHED_REF,
            "tracking_head": "1" * 40,
            "remote_head": "1" * 40,
            "remote_observation_mode": "live_remote_main_verified",
            "worktree_status": "clean",
        },
        "h_patch": {
            "base_commit": patch.PATCH_BASE_COMMIT,
            "added_count": 8,
            "modified_count": 0,
            "paths": list(patch.PATCH_PATHS),
            "paths_sha256": patch._path_digest(patch.PATCH_PATHS),
            "components": components,
            "components_sha256": patch._record_digest(components),
        },
        "runtime_contract": {
            "record": next(
                record
                for record in components
                if record["path"] == patch.DEFAULT_RUNTIME_PATH.as_posix()
            ),
            "schema_subset_verified": True,
            "pins_verified": True,
            "target_cutoff": "2020-12",
            "target_projection": list(patch.TARGET_PROJECTION),
            "raw_prediction_contract": patch.expected_raw_prediction_contract(),
            "b1_seed_count": 5,
            "candidate_slot_count": 30,
            "maximum_pipeline_count": 30,
            "exact_preprocessor_record_count": 30,
            "minimum_final_path_count": 39,
            "maximum_final_path_count": 69,
            "physical_input_count": patch.EXPECTED_RUNTIME_PHYSICAL_INPUT_COUNT,
            "physical_inputs": physical_inputs,
            "physical_inputs_sha256": patch._record_digest(physical_inputs),
        },
        "prelock": {
            "output_namespace": {
                "final_count": 69,
                "final_paths": list(finals),
                "final_paths_sha256": patch._path_digest(finals),
                "all_final_absent": True,
                "temporary_count": 69,
                "temporary_paths_sha256": patch._path_digest(temporaries),
                "all_temporary_absent": True,
                "future_pointer_count": 3,
                "future_pointer_paths": list(future_pointers),
                "future_pointer_paths_sha256": patch._path_digest(future_pointers),
                "all_future_pointers_absent": True,
                "future_pointer_temporary_count": 3,
                "future_pointer_temporary_paths_sha256": patch._path_digest(
                    pointer_temporaries
                ),
                "all_future_pointer_temporaries_absent": True,
                "guard_path": runtime["outputs"]["publication"]["guard_path"],
                "guard_absent": True,
            },
            "e0_m_paths": list(patch.E0_M_PATHS),
            "all_e0_m_paths_absent": True,
            "outcome_access_log_path": patch.OUTCOME_ACCESS_LOG,
            "outcome_access_log_absent": True,
            "dvc_commands_run": False,
            "network_commands_run": True,
            "data_execution_run": False,
            "auditor_run": False,
            "future_outcomes_accessed": False,
        },
        "verification": {
            "schema_preflight": preflight,
            "full_type_check": _command(list(patch.TYPE_CHECK_COMMAND)),
            "focused_tests": focused,
            "poetry_check": _command(list(patch.POETRY_CHECK_COMMAND)),
            "publication_guard": _command(list(patch.PUBLICATION_GUARD_COMMAND)),
            "git_diff_check": _command(list(patch.DIFF_CHECK_COMMAND)),
        },
        "authorizations": dict(patch.UNPUBLISHED_AUTHORIZATIONS),
        "seals": dict(patch.PATCH_SEALS),
    }


def _patch_locker_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    guard_directory = root / "tmp" / "closure_v1_e0_mp_locker"
    monkeypatch.setattr(locker, "PROJECT_ROOT", root)
    monkeypatch.setattr(locker, "OUTPUT_GUARD_DIRECTORY", guard_directory)
    monkeypatch.setattr(
        locker,
        "OUTPUT_GUARD_PATH",
        guard_directory / "baseline_development_patch_lock.guard",
    )


def test_runtime_contract_and_raw_schema_are_exact() -> None:
    runtime = patch.load_and_validate_baseline_development_runtime(
        verify_physical_pins=False
    )
    assert runtime["outputs"]["raw_prediction_contract"] == (
        patch.expected_raw_prediction_contract()
    )
    assert runtime["outputs"]["minimum_final_path_count"] == 39
    assert runtime["outputs"]["maximum_final_path_count"] == 69
    assert runtime["models"]["B2"]["candidate_slot_count"] == 30
    assert runtime["models"]["B2"]["maximum_pipeline_count"] == 30
    assert runtime["models"]["B2"]["exact_preprocessor_record_count"] == 30
    assert runtime["reproducibility"]["threadpool_limit"] == 1


def test_runtime_binds_exactly_forty_unique_physical_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = patch.load_and_validate_baseline_development_runtime(
        verify_physical_pins=False
    )
    expected_by_path: dict[str, dict[str, Any]] = {}
    for expected in runtime["authority"].values():
        if isinstance(expected, dict) and "path" in expected:
            expected_by_path[str(expected["path"])] = expected
    for bundle in runtime["upstream_anfis_bundles"]:
        for role in ("state", "pointer", "manifest"):
            expected = bundle[role]
            expected_by_path[str(expected["path"])] = expected

    def synthetic_record(
        path: Path,
        *,
        role: str,
        repo_root: Path | None = None,
    ) -> dict[str, Any]:
        expected = expected_by_path[path.as_posix()]
        return {
            "path": path.as_posix(),
            "role": role,
            "bytes": int(expected.get("bytes", 1)),
            "sha256": str(expected["sha256"]),
        }

    monkeypatch.setattr(patch, "_file_record", synthetic_record)
    records = patch._verify_runtime_physical_pins(runtime)
    assert len(records) == 40
    assert len({record["path"] for record in records}) == 40
    assert {"models.dvc", "pyproject.toml", "poetry.lock"}.issubset(
        {record["path"] for record in records}
    )


def test_schema_preflight_is_definition_safe() -> None:
    result = patch.preflight_baseline_development_patch_schema()
    assert result["supported_subset_verified"] is True
    assert result["minimum_keyword_absent"] is True
    assert result["format_keyword_absent"] is True


def test_h_scope_is_exactly_eight_additions() -> None:
    assert len(patch.PATCH_PATHS) == 8
    assert len(set(patch.PATCH_PATHS)) == 8
    assert set(patch.PATCH_COMPONENT_ROLES) == set(patch.PATCH_PATHS)


def test_potential_namespace_is_69_and_dvc_pointer_namespace_is_closed() -> None:
    runtime = patch.load_and_validate_baseline_development_runtime(
        verify_physical_pins=False
    )
    result = patch.baseline_output_namespace_absence(runtime)
    assert result["final_count"] == 69
    assert result["future_pointer_count"] == 3
    assert result["future_pointer_temporary_count"] == 3


def test_sample_payload_passes_schema_and_semantic_validation() -> None:
    assert patch.validate_baseline_development_patch_lock_payload(_sample_payload())[
        "gate"
    ] == "E0-MP"


@pytest.mark.parametrize(
    "mutation",
    ["missing", "duplicate", "wrong_role", "wrong_path"],
)
def test_h_component_shape_mutations_fail_closed(mutation: str) -> None:
    payload = _sample_payload()
    components = payload["h_patch"]["components"]
    if mutation == "missing":
        components.pop()
    elif mutation == "duplicate":
        components[-1] = copy.deepcopy(components[0])
    elif mutation == "wrong_role":
        components[0]["role"] = "wrong"
    else:
        components[0]["path"] = "wrong/path"
    payload["h_patch"]["components_sha256"] = patch._record_digest(components)
    with pytest.raises(patch.BaselineDevelopmentPatchError):
        patch.validate_baseline_development_patch_lock_payload(payload)


def test_h_component_hash_is_reconstructed_from_git(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _sample_payload()
    locked = copy.deepcopy(payload["h_patch"]["components"])
    mutated = copy.deepcopy(locked)
    mutated[0]["sha256"] = "f" * 64
    payload["h_patch"]["components"] = mutated
    payload["h_patch"]["components_sha256"] = patch._record_digest(mutated)
    monkeypatch.setattr(patch, "_git", lambda *args, **kwargs: patch.PATCH_BASE_COMMIT)
    monkeypatch.setattr(
        patch,
        "_observed_diff_entries",
        lambda *args, **kwargs: [
            {"status": "A", "path": path} for path in patch.PATCH_PATHS
        ],
    )
    by_path = {record["path"]: record for record in locked}
    monkeypatch.setattr(
        patch,
        "_git_blob_record",
        lambda commit, path, role, repo_root=None: copy.deepcopy(by_path[path]),
    )
    monkeypatch.setattr(
        patch,
        "_file_record",
        lambda path, role, repo_root=None: copy.deepcopy(by_path[Path(path).as_posix()]),
    )
    with pytest.raises(patch.BaselineDevelopmentPatchError, match="Git blobs"):
        patch._reconstruct_h_components(payload)


def test_companion_binds_48_unique_physical_inputs_and_one_output() -> None:
    payload = _sample_payload()
    companion = patch._expected_companion(
        payload,
        _record(patch.DEFAULT_PATCH_LOCK_PATH.as_posix(), "baseline_development_patch_lock", 60),
    )
    assert len(companion["inputs"]) == 48
    assert len({record["path"] for record in companion["inputs"]}) == 48
    assert companion["historical_inputs"] == []
    assert len(companion["outputs"]) == 1
    assert companion["manifest_written_last"] is True
    assert companion["network_commands_run"] is True


def test_companion_rejects_duplicate_physical_path() -> None:
    payload = _sample_payload()
    payload["runtime_contract"]["physical_inputs"][0]["path"] = patch.PATCH_PATHS[0]
    with pytest.raises(patch.BaselineDevelopmentPatchError, match="48 unique"):
        patch._expected_companion(payload, _record("lock.json", "lock", 60))


def test_effective_summary_exposes_authority_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _sample_payload()
    monkeypatch.setattr(
        patch, "preflight_baseline_development_patch_schema", lambda **kwargs: {}
    )
    monkeypatch.setattr(
        patch,
        "load_and_validate_baseline_development_patch_lock",
        lambda **kwargs: payload,
    )
    monkeypatch.setattr(
        patch,
        "_validate_p_publication",
        lambda *args, **kwargs: {
            "h_patch_head": "1" * 40,
            "p_patch_head": "2" * 40,
            "remote_head": "2" * 40,
        },
    )
    monkeypatch.setattr(
        patch,
        "_file_record",
        lambda path, role, repo_root=None: {
            "path": Path(path).as_posix(),
            "role": role,
            "bytes": 1,
            "sha256": "e" * 64 if "manifest" in role else "d" * 64,
        },
    )
    result = patch.load_effective_baseline_development_authority()
    assert result["h_patch_head"] == "1" * 40
    assert result["p_patch_head"] == "2" * 40
    assert result["lock_sha256"] == "d" * 64
    assert result["companion_sha256"] == "e" * 64
    assert result["runner_sha256"] == next(
        record["sha256"]
        for record in payload["h_patch"]["components"]
        if record["path"] == "src/experiments/fit_closure_baselines.py"
    )


def test_require_authority_refuses_disabling_live_remote_verification() -> None:
    with pytest.raises(patch.BaselineDevelopmentPatchError):
        patch.require_baseline_development_authority(verify_remote=False)


def test_live_remote_parser_rejects_ambiguous_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(patch, "_git", lambda *args, **kwargs: "a\nb")
    with pytest.raises(patch.BaselineDevelopmentPatchError):
        patch._live_remote_main_head()


def test_check_only_runs_schema_before_remote_prelock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        locker,
        "preflight_baseline_development_patch_schema",
        lambda: events.append("schema") or {"gate": "E0-MP"},
    )
    monkeypatch.setattr(
        locker,
        "collect_baseline_development_patch_prelock_state",
        lambda: events.append("prelock")
        or {
            "repository": {"head": "1" * 40},
            "h_patch": {"added_count": 8},
            "runtime_contract": {
                "minimum_final_path_count": 39,
                "maximum_final_path_count": 69,
            },
        },
    )
    result = locker.check_only()
    assert events == ["schema", "prelock"]
    assert result["writes_performed"] is False
    assert result["network_commands_run"] is True


def test_focused_summary_requires_one_exact_clean_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(locker, "FOCUSED_TEST_COUNT", 52)
    assert locker._parse_focused_summary("52 passed in 12.34s\n", "")["test_count"] == 52
    with pytest.raises(patch.BaselineDevelopmentPatchError):
        locker._parse_focused_summary("52 passed, 1 warning in 12.34s\n", "")


def test_locker_commands_exclude_science_dvc_and_auditors() -> None:
    command_text = "\n".join(
        " ".join(command)
        for command in (
            patch.TYPE_CHECK_COMMAND,
            patch.FOCUSED_TEST_COMMAND,
            patch.POETRY_CHECK_COMMAND,
            patch.PUBLICATION_GUARD_COMMAND,
            patch.DIFF_CHECK_COMMAND,
        )
    ).lower()
    assert "dvc" not in command_text
    assert "audit" not in command_text
    assert all(
        token != "src/experiments/fit_closure_baselines.py"
        for command in (
            patch.TYPE_CHECK_COMMAND,
            patch.FOCUSED_TEST_COMMAND,
            patch.POETRY_CHECK_COMMAND,
            patch.PUBLICATION_GUARD_COMMAND,
            patch.DIFF_CHECK_COMMAND,
        )
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
    with pytest.raises(patch.BaselineDevelopmentPatchError):
        locker._acquire_guard()


def test_guard_write_failure_removes_only_its_owned_inode(
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
        patch.BaselineDevelopmentPatchError,
        match="cleanup failed closed",
    ):
        locker._acquire_guard()
    assert locker.OUTPUT_GUARD_PATH.read_bytes() == b"foreign"


def test_temporary_fsync_failure_rolls_back_owned_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)
    parent = tmp_path / "configs" / "closure_v1"
    parent.mkdir(parents=True)
    expected = Path("configs/closure_v1/item.tmp")
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
    parent = tmp_path / "configs" / "closure_v1"
    parent.mkdir(parents=True)
    foreign = tmp_path / "foreign"
    foreign.write_bytes(b"foreign")
    expected = Path("configs/closure_v1/item.tmp")
    (tmp_path / expected).symlink_to(foreign)
    with pytest.raises(patch.BaselineDevelopmentPatchError, match="clobber"):
        locker._write_temp(tmp_path / expected, expected, b"owned")
    assert foreign.read_bytes() == b"foreign"


def test_owned_rollback_preserves_foreign_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)
    parent = tmp_path / "configs" / "closure_v1"
    parent.mkdir(parents=True)
    expected = Path("configs/closure_v1/item.tmp")
    owner = locker._write_temp(tmp_path / expected, expected, b"owned")
    os.unlink(owner.path.name, dir_fd=owner.directory_file_descriptor)
    (tmp_path / expected).write_bytes(b"foreign")
    try:
        with pytest.raises(patch.BaselineDevelopmentPatchError, match="foreign"):
            locker._rollback_if_owned(owner, context="test")
        assert (tmp_path / expected).read_bytes() == b"foreign"
    finally:
        locker._close_owner(owner)


def test_publication_refuses_existing_final_without_losing_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_locker_root(monkeypatch, tmp_path)
    parent = tmp_path / "configs" / "closure_v1"
    parent.mkdir(parents=True)
    guard = locker._acquire_guard()
    temp_expected = Path("configs/closure_v1/item.tmp")
    final_expected = Path("configs/closure_v1/item.json")
    temp = locker._write_temp(tmp_path / temp_expected, temp_expected, b"owned")
    (tmp_path / final_expected).write_bytes(b"foreign")
    try:
        with pytest.raises(patch.BaselineDevelopmentPatchError, match="clobber"):
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


def test_cli_modes_are_mutually_exclusive() -> None:
    assert locker.parse_args(["--check-only"]).check_only is True
    with pytest.raises(SystemExit):
        locker.parse_args(["--check-only", "--execute-lock"])
