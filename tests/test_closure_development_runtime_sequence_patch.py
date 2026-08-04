from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from src.experiments import closure_development_runtime_sequence_patch as patch
from src.experiments import lock_closure_development_runtime_sequence_patch as locker
from src.experiments.closure_contract import load_json_mapping, validate_json_schema


def _command_evidence(
    command: tuple[str, ...],
    *,
    test_count: int | None = None,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "command": list(command),
        "exit_code": 0,
        "stdout_sha256": "0" * 64,
        "stderr_sha256": "1" * 64,
        "stdout_line_count": 1,
        "stderr_line_count": 0,
        "success_marker_verified": True,
    }
    if test_count is not None:
        evidence.update(
            {
                "test_count": test_count,
                "skipped_count": 0,
                "deselected_count": 0,
            }
        )
    return evidence


def _verification(test_count: int) -> dict[str, Any]:
    return {
        "full_type_check": _command_evidence(patch.SEQUENCE_PATCH_TYPE_CHECK_COMMAND),
        "focused_tests": _command_evidence(
            patch.SEQUENCE_PATCH_FOCUSED_TEST_COMMAND,
            test_count=test_count,
        ),
        "poetry_check": _command_evidence(patch.SEQUENCE_PATCH_POETRY_CHECK_COMMAND),
        "publication_guard": _command_evidence(
            patch.SEQUENCE_PATCH_PUBLICATION_GUARD_COMMAND
        ),
        "git_diff_check": _command_evidence(patch.SEQUENCE_PATCH_DIFF_CHECK_COMMAND),
    }


def _file_record(path: str, role: str) -> dict[str, Any]:
    return {"path": path, "role": role, "bytes": 1, "sha256": "2" * 64}


def _prelock(head: str) -> dict[str, Any]:
    authority_records = [
        _file_record(path, str(record["role"]))
        for path, record in sorted(patch.BASE_AUTHORITY_RECORDS.items())
    ]
    preserved_records = [
        _file_record(
            "src/experiments/closure_development_runtime_patch.py",
            "preserved_locked_component",
        )
    ]
    authority = {
        "base_repository_head": patch.BASE_REPOSITORY_HEAD,
        "e0_dlp_patch_head": patch.BASE_PATCH_HEAD,
        "e0_dlp_lock_commit": patch.BASE_PATCH_LOCK_COMMIT,
        "records": authority_records,
        "records_sha256": patch._record_digest(authority_records),
        "preserved_components": {
            "count": len(preserved_records),
            "paths": [str(preserved_records[0]["path"])],
            "paths_sha256": patch._path_digest([str(preserved_records[0]["path"])]),
            "records": preserved_records,
            "records_sha256": patch._record_digest(preserved_records),
        },
        "base_e0_dl_unchanged": True,
        "base_e0_dlp_unchanged": True,
        "historical_schema_and_payload_validated": True,
        "physical_development_authority_verified": True,
        "e0_dlp_adopted_seed_physical_artifacts_verified": True,
    }
    component_records = [
        _file_record(path, patch.PATCH_COMPONENT_ROLES[path]) for path in patch.PATCH_PATHS
    ]
    components = {
        "count": len(component_records),
        "paths": list(patch.PATCH_PATHS),
        "paths_sha256": patch._path_digest(patch.PATCH_PATHS),
        "records": component_records,
        "records_sha256": patch._record_digest(component_records),
    }
    diff = {
        "base_commit": patch.BASE_REPOSITORY_HEAD,
        "patch_head": head,
        "entries": patch._expected_diff_entries(),
        "paths": list(patch.PATCH_PATHS),
        "paths_sha256": patch._path_digest(patch.PATCH_PATHS),
        "only_allowed_additions_and_modifications": True,
    }
    p0_paths = [path.as_posix() for path in patch.P0_ONE_SHOT_PATHS]
    return {
        "base_authority": authority,
        "patch_repository": {
            "head": head,
            "parent": patch.BASE_REPOSITORY_HEAD,
            "branch": "main",
            "published_ref": patch.PUBLISHED_REF,
            "published_head": head,
            "remote_main_oid": head,
            "worktree_status": "clean",
            "exact_diff_verified": True,
        },
        "patch_components": components,
        "git_diff": diff,
        "p0_outputs": {
            "count": len(p0_paths),
            "paths": p0_paths,
            "paths_sha256": patch._path_digest(p0_paths),
            "all_absent_at_lock": True,
        },
    }


def test_patch_scope_is_exactly_six_modifications_and_five_additions() -> None:
    assert len(patch.PATCH_MODIFIED_PATHS) == 6
    assert len(patch.PATCH_ADDED_PATHS) == 5
    assert len(patch.PATCH_PATHS) == 11
    assert set(patch.PATCH_MODIFIED_PATHS).isdisjoint(patch.PATCH_ADDED_PATHS)
    assert set(patch.PATCH_MODIFIED_PATHS) | set(patch.PATCH_ADDED_PATHS) == set(
        patch.PATCH_PATHS
    )
    entries = patch._expected_diff_entries()
    assert sum(entry["status"] == "M" for entry in entries) == 6
    assert sum(entry["status"] == "A" for entry in entries) == 5


def test_patch_correction_changes_representation_only() -> None:
    correction = patch.PATCH_CORRECTION
    assert correction["sequence_failure_encoding"] == (
        "outer_valid_with_12_null_float32_children"
    )
    assert correction["rollout_failure_encoding"] == "outer_valid_with_128_null_children"
    assert correction["success_payload_changed"] is False
    assert correction["scalar_target_null_encoding_changed"] is False
    assert correction["partially_null_tensor_accepted"] is False
    assert correction["sequence_bundle_guard"] == (
        "exclusive_ignored_guard_held_through_publication"
    )
    assert correction["sequence_output_publication"] == (
        "exclusive_temp_inode_hardlink_no_clobber"
    )
    assert patch.PATCH_SEALS["scientific_decisions_changed"] is False
    assert patch.PATCH_AUTHORIZATIONS == {
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }
    assert "p1_materialized_at_lock" not in patch.PATCH_SEALS


def test_schema_alone_closes_correction_authorizations_and_seals() -> None:
    head = "a" * 40
    payload = patch.build_sequence_patch_lock_payload(
        _prelock(head),
        _verification(patch.SEQUENCE_PATCH_FOCUSED_TEST_COUNT),
        created_at_utc="2026-08-04T15:00:00Z",
    )
    schema = load_json_mapping(patch.DEFAULT_SEQUENCE_PATCH_LOCK_SCHEMA)
    validate_json_schema(payload, schema, instance_path="$.lock")
    nonfocused_extra = copy.deepcopy(payload)
    nonfocused_extra["verification"]["full_type_check"]["test_count"] = 1
    with pytest.raises(ValueError, match="additionalProperties"):
        validate_json_schema(nonfocused_extra, schema, instance_path="$.lock")
    for section in ("compatibility_correction", "authorizations", "seals"):
        unknown = copy.deepcopy(payload)
        unknown[section]["unexpected_field"] = False
        with pytest.raises(ValueError, match="additionalProperties"):
            validate_json_schema(unknown, schema, instance_path="$.lock")
        for key, value in payload[section].items():
            drifted = copy.deepcopy(payload)
            drifted[section][key] = not value if isinstance(value, bool) else "drifted"
            with pytest.raises(ValueError, match="const"):
                validate_json_schema(drifted, schema, instance_path="$.lock")


def test_json_decoder_rejects_duplicate_keys_and_nonfinite_numbers() -> None:
    for encoded in (
        b'{"lock": 1, "lock": 2}',
        b'{"lock": {"nested": 1, "nested": 2}}',
        b'{"lock": NaN}',
    ):
        with pytest.raises(RuntimeError, match="canonical JSON"):
            patch._decode_json(encoded, context="test payload")


def test_p0_absence_guard_covers_eight_paths_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(patch, "PROJECT_ROOT", tmp_path)
    paths = tuple(Path(f"slot/path_{index}") for index in range(8))
    record = patch.assert_p0_one_shot_outputs_absent(paths)
    assert record["count"] == 8
    assert record["paths"] == [path.as_posix() for path in paths]
    assert record["all_absent_at_lock"] is True
    assert not (tmp_path / "slot").exists()


@pytest.mark.parametrize("kind", ["file", "symlink"])
def test_p0_absence_guard_rejects_any_existing_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    monkeypatch.setattr(patch, "PROJECT_ROOT", tmp_path)
    target = tmp_path / "slot" / "sequence.parquet"
    target.parent.mkdir(parents=True)
    if kind == "file":
        target.write_bytes(b"partial")
    else:
        target.symlink_to(tmp_path / "missing-target")
    with pytest.raises(RuntimeError, match="must be absent"):
        patch.assert_p0_one_shot_outputs_absent((Path("slot/sequence.parquet"),))


def test_verification_requires_exact_commands_and_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(patch, "SEQUENCE_PATCH_FOCUSED_TEST_COUNT", 321)
    verification = _verification(321)
    patch.validate_sequence_patch_verification(verification)
    verification["focused_tests"]["test_count"] = 320
    with pytest.raises(RuntimeError, match="focused-test"):
        patch.validate_sequence_patch_verification(verification)
    verification = _verification(321)
    verification["full_type_check"]["stdout_line_count"] = -1
    with pytest.raises(RuntimeError, match="command evidence"):
        patch.validate_sequence_patch_verification(verification)


def test_lock_payload_validates_against_schema_and_closed_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = "a" * 40
    monkeypatch.setattr(patch, "SEQUENCE_PATCH_FOCUSED_TEST_COUNT", 321)
    prelock = _prelock(head)
    payload = patch.build_sequence_patch_lock_payload(
        prelock,
        _verification(321),
        created_at_utc="2026-08-04T15:00:00Z",
    )
    schema = load_json_mapping(patch.DEFAULT_SEQUENCE_PATCH_LOCK_SCHEMA)
    monkeypatch.setattr(patch, "_require_commit", lambda value, **_: value)
    monkeypatch.setattr(patch, "sequence_patch_git_diff_payload", lambda _: prelock["git_diff"])
    monkeypatch.setattr(
        patch,
        "sequence_patch_component_bundle",
        lambda _: prelock["patch_components"],
    )
    monkeypatch.setattr(
        patch,
        "_historical_authority_record",
        lambda **_: prelock["base_authority"],
    )
    patch.validate_development_runtime_sequence_patch_lock_payload(payload, schema)
    payload["authorizations"]["evaluation_authorized"] = True
    with pytest.raises(RuntimeError, match="JSON Schema const"):
        patch.validate_development_runtime_sequence_patch_lock_payload(payload, schema)
    monkeypatch.setattr(patch, "validate_json_schema", lambda *_args, **_kwargs: None)
    with pytest.raises(RuntimeError, match="fixed contract"):
        patch.validate_development_runtime_sequence_patch_lock_payload(payload, schema)


def test_historical_e0_dlp_authority_remains_byte_identical() -> None:
    authority = patch._historical_authority_record(require_physical_artifacts=False)
    assert authority["e0_dlp_patch_head"] == patch.BASE_PATCH_HEAD
    assert authority["e0_dlp_lock_commit"] == patch.BASE_PATCH_LOCK_COMMIT
    assert authority["base_e0_dl_unchanged"] is True
    assert authority["base_e0_dlp_unchanged"] is True
    assert authority["physical_development_authority_verified"] is True
    assert authority["e0_dlp_adopted_seed_physical_artifacts_verified"] is True
    preserved = authority["preserved_components"]
    assert preserved["count"] == len(preserved["paths"])
    assert set(patch.PATCH_MODIFIED_PATHS).isdisjoint(preserved["paths"])


def test_preserved_bundle_covers_every_locked_runtime_dependency() -> None:
    base_payload = patch._load_regular_json(
        patch.DEFAULT_BASE_LOCK_PATH,
        context="base lock",
    )
    patch_payload = patch._load_regular_json(
        patch.DEFAULT_BASE_PATCH_LOCK_PATH,
        context="patch lock",
    )
    expected: set[str] = set()
    for field in ("components", "runtime_dependencies"):
        expected.update(str(record["path"]) for record in base_payload[field])
    expected.update(
        str(base_payload["runtime_contract"][field]["path"])
        for field in ("config", "schema")
    )
    for field in ("patch_components", "base_component_drift"):
        expected.update(str(record["path"]) for record in patch_payload[field]["records"])
    expected.difference_update(patch.PATCH_MODIFIED_PATHS)
    bundle = patch._preserved_component_bundle(base_payload, patch_payload)
    assert bundle["paths"] == sorted(expected)
    assert bundle["count"] == len(expected)
    assert bundle["paths_sha256"] == patch._path_digest(sorted(expected))
    assert {record["path"] for record in bundle["records"]} == expected
    assert {
        "src/experiments/closure_contract.py",
        "src/fuzzy/adaptive_anfis.py",
        "src/experiments/rollout_pipe_grud.py",
    }.issubset(expected)
    dlp_drift_paths = {
        str(record["path"])
        for record in patch_payload["base_component_drift"]["records"]
    }
    superseded = dlp_drift_paths.intersection(patch.PATCH_MODIFIED_PATHS)
    assert superseded == {
        "src/experiments/build_closure_pipe_sequences.py",
        "tests/test_build_closure_pipe_sequences.py",
    }
    assert dlp_drift_paths.difference(superseded).issubset(bundle["paths"])


def test_preserved_bundle_is_fully_enforced_at_execution_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = {
        "paths": ["a.py", "b.py"],
        "records": [
            _file_record("a.py", "preserved_locked_component"),
            _file_record("b.py", "preserved_locked_component"),
        ],
    }
    observed: dict[str, Any] = {}
    monkeypatch.setattr(
        patch,
        "_assert_records_physical_and_current",
        lambda records, **kwargs: observed.update(records=list(records), **kwargs),
    )
    monkeypatch.setattr(
        patch,
        "_assert_paths_untouched",
        lambda base, descendant, paths, **kwargs: observed.update(
            base=base,
            descendant=descendant,
            paths=list(paths),
            **kwargs,
        ),
    )
    patch._assert_preserved_components(bundle, execution_head="a" * 40)
    assert [record["path"] for record in observed["records"]] == ["a.py", "b.py"]
    assert observed["paths"] == ["a.py", "b.py"]


def test_selective_e0_dlp_physical_audit_checks_seed_owner_environment_and_dvc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = {"device": "cpu"}
    owner = {"hash_value": "owner"}
    bundle = {"dvc": {"models_owner": owner}}
    environment = {"python": "closed"}
    remote_evidence = {"status": "verified"}
    payload = {
        "adopted_seed_bundle": bundle,
        "environment": environment,
        "dvc_remote_verification": remote_evidence,
    }
    observed: dict[str, Any] = {}
    monkeypatch.setattr(
        patch,
        "_validate_base_physical_authority",
        lambda *_args, **kwargs: observed.update(base_kwargs=kwargs)
        or {"runtime": runtime},
    )
    monkeypatch.setattr(
        patch,
        "_validate_locked_models_owner",
        lambda value, **kwargs: observed.update(owner=value, owner_kwargs=kwargs),
    )
    monkeypatch.setattr(
        patch,
        "adopted_seed_bundle_record",
        lambda base, **kwargs: observed.update(base=base, bundle_kwargs=kwargs) or bundle,
    )
    monkeypatch.setattr(
        patch,
        "environment_payload",
        lambda device, value: observed.update(device=device, environment_runtime=value)
        or environment,
    )
    monkeypatch.setattr(
        patch,
        "_validate_dvc_remote_evidence",
        lambda evidence, locked, **kwargs: observed.update(
            dvc_evidence=evidence,
            dvc_bundle=locked,
            dvc_kwargs=kwargs,
        ),
    )
    base = {"lock": "base"}
    patch._validate_historical_e0_dlp_physical_authority(
        base,
        payload,
        execution_head="a" * 40,
    )
    assert observed["owner"] == owner
    assert observed["owner_kwargs"] == {"patch_head": patch.BASE_PATCH_HEAD}
    assert observed["bundle_kwargs"]["execution_head"] == "a" * 40
    assert observed["bundle_kwargs"]["require_physical_artifacts"] is True
    assert observed["device"] == "cpu"
    assert observed["dvc_evidence"] == remote_evidence
    assert observed["dvc_bundle"] == bundle
    assert observed["dvc_kwargs"]["verify_current_remote_config"] is True

    monkeypatch.setattr(patch, "adopted_seed_bundle_record", lambda *_args, **_kwargs: {})
    with pytest.raises(RuntimeError, match="adopted seed bundle changed"):
        patch._validate_historical_e0_dlp_physical_authority(
            base,
            payload,
            execution_head="a" * 40,
        )


def test_p0_absence_is_historical_lock_evidence_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = "a" * 40
    prelock = _prelock(head)
    payload = patch.build_sequence_patch_lock_payload(
        prelock,
        _verification(patch.SEQUENCE_PATCH_FOCUSED_TEST_COUNT),
        created_at_utc="2026-08-04T15:00:00Z",
    )
    schema = load_json_mapping(patch.DEFAULT_SEQUENCE_PATCH_LOCK_SCHEMA)
    monkeypatch.setattr(patch, "_require_commit", lambda value, **_: value)
    monkeypatch.setattr(patch, "sequence_patch_git_diff_payload", lambda _: prelock["git_diff"])
    monkeypatch.setattr(
        patch,
        "sequence_patch_component_bundle",
        lambda _: prelock["patch_components"],
    )
    monkeypatch.setattr(
        patch,
        "_historical_authority_record",
        lambda **_: prelock["base_authority"],
    )
    monkeypatch.setattr(
        patch,
        "assert_p0_one_shot_outputs_absent",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("historical evidence must not re-check post-lock P0")
        ),
    )
    patch.validate_development_runtime_sequence_patch_lock_payload(payload, schema)


def test_sequence_patch_gate_rejects_non_cpu_before_loading_lock() -> None:
    with pytest.raises(RuntimeError, match="locked CPU"):
        patch.require_development_fit_authorized_with_sequence_patch(device="auto")


def test_sequence_patch_gate_preserves_evaluation_seals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary = {
        "publication_verified": True,
        "remote_publication_verified": True,
        "physical_artifacts_verified": True,
        "historical_authority_verified": True,
        "patch_components_verified": True,
        "locked_head_is_ancestor": True,
        "locked_parent_published_at_lock": True,
        "development_fit_authorized": True,
        "fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }
    monkeypatch.setattr(
        patch,
        "load_and_validate_development_runtime_sequence_patch_lock",
        lambda **_: ({}, summary),
    )
    assert patch.require_development_fit_authorized_with_sequence_patch(device="cpu") == summary
    summary["e0_u_authorized"] = True
    with pytest.raises(RuntimeError, match="evaluation seals"):
        patch.require_development_fit_authorized_with_sequence_patch(device="cpu")


def _locker_test_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path]:
    monkeypatch.setattr(locker, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        locker,
        "OUTPUT_GUARD_DIRECTORY",
        tmp_path / "tmp" / "closure_v1_e0_dls_locker",
    )
    lock_path = tmp_path / patch.DEFAULT_SEQUENCE_PATCH_LOCK_PATH
    companion_path = tmp_path / patch.DEFAULT_SEQUENCE_PATCH_MANIFEST_PATH
    lock_path.parent.mkdir(parents=True)
    return lock_path, companion_path


def test_locker_refuses_every_final_temporary_or_guard_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock_path, companion_path = _locker_test_paths(tmp_path, monkeypatch)
    guard_paths = locker._output_guard_paths(
        lock_path,
        companion_path,
        create_directory=True,
    )
    candidates = (
        lock_path,
        lock_path.with_suffix(lock_path.suffix + ".tmp"),
        companion_path,
        companion_path.with_suffix(companion_path.suffix + ".tmp"),
        *guard_paths,
    )
    for candidate in candidates:
        candidate.symlink_to(tmp_path / "missing-target")
        with pytest.raises(RuntimeError, match="Refusing to overwrite"):
            locker._refuse_existing_outputs(lock_path, companion_path)
        candidate.unlink()


def test_output_guard_is_exclusive_and_removes_only_its_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock_path, companion_path = _locker_test_paths(tmp_path, monkeypatch)
    guard_path = locker._output_guard_paths(
        lock_path,
        companion_path,
        create_directory=True,
    )[0]
    guard = locker._open_output_guard(guard_path)
    try:
        with pytest.raises(RuntimeError, match="existing E0-DLS guard"):
            locker._open_output_guard(guard_path)
        assert locker._guard_is_owned(guard)
    finally:
        locker._release_output_guard(guard)
    assert not guard_path.exists()


def test_guarded_publication_never_clobbers_a_racing_final(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock_path, companion_path = _locker_test_paths(tmp_path, monkeypatch)
    guards = locker._acquire_output_guards(lock_path, companion_path)
    try:
        lock_path.write_bytes(b"racing writer\n")
        with pytest.raises(RuntimeError, match="created during checks"):
            locker._publish_guarded_bytes(
                b"ours\n",
                lock_path,
                patch.DEFAULT_SEQUENCE_PATCH_LOCK_PATH,
                guards[0],
            )
        assert lock_path.read_bytes() == b"racing writer\n"
    finally:
        for guard in reversed(guards):
            locker._release_output_guard(guard)


def test_guarded_publication_rolls_back_when_directory_fsync_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock_path, companion_path = _locker_test_paths(tmp_path, monkeypatch)
    guards = locker._acquire_output_guards(lock_path, companion_path)
    original_fsync = os.fsync
    calls = 0

    def fail_after_link(descriptor: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("directory fsync failed")
        original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", fail_after_link)
    try:
        with pytest.raises(OSError, match="directory fsync failed"):
            locker._publish_guarded_bytes(
                b"ours\n",
                lock_path,
                patch.DEFAULT_SEQUENCE_PATCH_LOCK_PATH,
                guards[0],
            )
        assert not lock_path.exists()
        assert locker._guard_is_owned(guards[0])
    finally:
        monkeypatch.setattr(os, "fsync", original_fsync)
        for guard in reversed(guards):
            locker._release_output_guard(guard)


def test_guarded_publication_detects_a_parent_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock_path, companion_path = _locker_test_paths(tmp_path, monkeypatch)
    guards = locker._acquire_output_guards(lock_path, companion_path)
    original_link = os.link
    original_parent = lock_path.parent
    moved_parent = original_parent.with_name("moved-protocol")

    def swap_parent_then_link(*args: Any, **kwargs: Any) -> None:
        original_parent.rename(moved_parent)
        original_parent.mkdir()
        original_link(*args, **kwargs)

    monkeypatch.setattr(os, "link", swap_parent_then_link)
    try:
        with pytest.raises(RuntimeError, match="identity drifted"):
            locker._publish_guarded_bytes(
                b"lock\n",
                lock_path,
                patch.DEFAULT_SEQUENCE_PATCH_LOCK_PATH,
                guards[0],
            )
        assert not lock_path.exists()
        assert not (moved_parent / lock_path.name).exists()
    finally:
        monkeypatch.setattr(os, "link", original_link)
        for guard in reversed(guards):
            locker._release_output_guard(guard)


def test_owned_rollback_preserves_a_replacement_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock_path, companion_path = _locker_test_paths(tmp_path, monkeypatch)
    guards = locker._acquire_output_guards(lock_path, companion_path)
    owner = locker._publish_guarded_bytes(
        b"owned\n",
        lock_path,
        patch.DEFAULT_SEQUENCE_PATCH_LOCK_PATH,
        guards[0],
    )
    try:
        lock_path.unlink()
        lock_path.write_bytes(b"replacement\n")
        locker._unlink_if_owned(owner)
        assert lock_path.read_bytes() == b"replacement\n"
    finally:
        locker._close_owned_directory(owner)
        for guard in reversed(guards):
            locker._release_output_guard(guard)


def test_exact_pytest_summary_rejects_every_extra_outcome() -> None:
    count = patch.SEQUENCE_PATCH_FOCUSED_TEST_COUNT
    assert locker._parse_exact_focused_summary(
        f"progress\n{count} passed in 1.25s\n",
        "",
    ) == count
    for stdout, stderr in (
        (f"{count} passed, 1 warning in 1.25s\n", ""),
        (f"{count} passed in 1.25s\n1 xfailed\n", ""),
        (f"{count} passed in 1.25s\n", "warning emitted"),
        (f"{count - 1} passed in 1.25s\n", ""),
    ):
        with pytest.raises(RuntimeError, match="exact clean result"):
            locker._parse_exact_focused_summary(stdout, stderr)


def test_pytest_environment_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, str] = {}
    monkeypatch.setenv("PYTEST_UNKNOWN_PARENT_OPTION", "unsafe")

    def run(*_args: Any, **kwargs: Any) -> SimpleNamespace:
        observed.update(kwargs["env"])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(locker.subprocess, "run", run)
    locker._run_command(
        ("closed-command",),
        environment=patch.SEQUENCE_PATCH_TEST_ENVIRONMENT,
        sanitize_pytest_environment=True,
    )
    assert "PYTEST_UNKNOWN_PARENT_OPTION" not in observed
    assert observed["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"


def _configure_execute_lock_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    snapshots: list[dict[str, Any]],
    fail_second_publication: bool = False,
) -> list[str]:
    events: list[str] = []
    lock_path = tmp_path / "lock.json"
    companion_path = tmp_path / "companion.json"
    schema_path = tmp_path / patch.DEFAULT_SEQUENCE_PATCH_LOCK_SCHEMA
    schema_path.parent.mkdir(parents=True)
    schema_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(locker, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        locker,
        "_closed_output",
        lambda _path, expected: (
            lock_path
            if expected == patch.DEFAULT_SEQUENCE_PATCH_LOCK_PATH
            else companion_path
        ),
    )
    guards = (object(), object())
    monkeypatch.setattr(
        locker,
        "_acquire_output_guards",
        lambda *_args: events.append("guards") or guards,
    )
    monkeypatch.setattr(
        locker,
        "_assert_guarded_publication_state",
        lambda *_args: events.append("namespace"),
    )
    monkeypatch.setattr(
        locker,
        "collect_sequence_patch_prelock_state",
        lambda **_kwargs: events.append("snapshot") or snapshots.pop(0),
    )
    monkeypatch.setattr(
        locker,
        "run_sequence_patch_verification",
        lambda: events.append("verification") or {},
    )
    monkeypatch.setattr(locker, "_assert_p0_snapshot", lambda _expected: events.append("p0"))
    monkeypatch.setattr(
        locker,
        "build_sequence_patch_lock_payload",
        lambda *_args, **_kwargs: events.append("build")
        or {"patch_repository": {"head": "a" * 40}},
    )
    monkeypatch.setattr(
        locker,
        "validate_development_runtime_sequence_patch_lock_payload",
        lambda *_args, **_kwargs: events.append("validate"),
    )
    publication_count = 0

    def publish(
        _payload: bytes,
        path: Path,
        _expected: Path,
        _guard: object,
    ) -> locker._OwnedFile:
        nonlocal publication_count
        publication_count += 1
        events.append(f"publish:{path.name}")
        if fail_second_publication and publication_count == 2:
            raise RuntimeError("second publication failed")
        return locker._OwnedFile(path=path, device=1, inode=publication_count)

    monkeypatch.setattr(locker, "_publish_guarded_bytes", publish)
    monkeypatch.setattr(
        locker,
        "_owned_file_record",
        lambda owner, **_kwargs: events.append(f"record:{owner.path.name}")
        or {
            "path": owner.path.name,
            "role": "record",
            "bytes": 1,
            "sha256": "f" * 64,
        },
    )
    monkeypatch.setattr(
        locker,
        "_companion_payload",
        lambda *_args: events.append("companion") or {"companion": True},
    )
    monkeypatch.setattr(
        locker,
        "load_and_validate_development_runtime_sequence_patch_lock",
        lambda **_kwargs: events.append("load") or ({}, {}),
    )
    monkeypatch.setattr(
        locker,
        "_unlink_if_owned",
        lambda owner: events.append(f"unlink:{owner.path.name}"),
    )
    monkeypatch.setattr(
        locker,
        "_close_owned_directory",
        lambda owner: events.append(f"close:{owner.path.name}"),
    )
    monkeypatch.setattr(
        locker,
        "_release_output_guard",
        lambda _guard: events.append("release"),
    )
    return events


def test_execute_lock_orders_lock_before_companion_and_revalidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"p0_outputs": {"count": 8}}
    events = _configure_execute_lock_harness(
        tmp_path,
        monkeypatch,
        snapshots=[copy.deepcopy(state), copy.deepcopy(state)],
    )
    result = locker.execute_lock()
    assert result["status"] == "locked_unpublished"
    assert events.index("guards") < events.index("verification")
    assert events.index("publish:lock.json") < events.index("companion")
    assert events.index("companion") < events.index("publish:companion.json")
    assert events.count("p0") == 4
    assert events.count("namespace") == 5
    assert events[-2:] == ["release", "release"]


def test_second_publication_failure_rolls_back_the_owned_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"p0_outputs": {"count": 8}}
    events = _configure_execute_lock_harness(
        tmp_path,
        monkeypatch,
        snapshots=[copy.deepcopy(state), copy.deepcopy(state)],
        fail_second_publication=True,
    )
    with pytest.raises(RuntimeError, match="second publication failed"):
        locker.execute_lock()
    assert "unlink:lock.json" in events
    assert "unlink:companion.json" not in events
    assert events[-2:] == ["release", "release"]


def test_snapshot_drift_stops_before_any_publication_and_releases_guards(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = _configure_execute_lock_harness(
        tmp_path,
        monkeypatch,
        snapshots=[
            {"p0_outputs": {"count": 8}},
            {"p0_outputs": {"count": 7}},
        ],
    )
    with pytest.raises(RuntimeError, match="prelock state changed"):
        locker.execute_lock()
    assert not any(event.startswith("publish:") for event in events)
    assert events[-2:] == ["release", "release"]


def test_final_p0_drift_rolls_back_both_published_inodes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"p0_outputs": {"count": 8}}
    events = _configure_execute_lock_harness(
        tmp_path,
        monkeypatch,
        snapshots=[copy.deepcopy(state), copy.deepcopy(state)],
    )
    calls = 0

    def p0(_expected: Mapping[str, Any]) -> None:
        nonlocal calls
        calls += 1
        events.append("p0")
        if calls == 4:
            raise RuntimeError("P0 appeared during final validation")

    monkeypatch.setattr(locker, "_assert_p0_snapshot", p0)
    with pytest.raises(RuntimeError, match="P0 appeared"):
        locker.execute_lock()
    assert events.index("unlink:companion.json") < events.index("unlink:lock.json")
    assert events[-2:] == ["release", "release"]


def test_companion_is_bound_to_lock_hash_and_written_last_contract() -> None:
    head = "a" * 40
    payload = {
        "created_at_utc": "2026-08-04T15:00:00Z",
        "patch_components": _prelock(head)["patch_components"],
        "base_authority": _prelock(head)["base_authority"],
    }
    lock_record = {
        "path": patch.DEFAULT_SEQUENCE_PATCH_LOCK_PATH.as_posix(),
        "role": "external_development_runtime_sequence_patch_lock",
        "bytes": 123,
        "sha256": "f" * 64,
    }
    companion = locker._companion_payload(payload, lock_record)
    assert companion["outputs"] == [lock_record]
    assert companion["development_fit_authorized"] is True
    assert companion["evaluation_authorized"] is False
    assert companion["e0_u_authorized"] is False
    assert companion["future_outcomes_accessed"] is False


def test_lock_schema_and_doc_are_parseable_and_public() -> None:
    schema = load_json_mapping(patch.DEFAULT_SEQUENCE_PATCH_LOCK_SCHEMA)
    assert schema["properties"]["gate"] == {"const": "E0-DLS"}
    doc = patch.PROJECT_ROOT / "docs/closure_v1/E0_D_RUNTIME_SEQUENCE_PATCH_1.md"
    assert "E0-DLS" in doc.read_text(encoding="utf-8")
    json.dumps(schema, sort_keys=True)
