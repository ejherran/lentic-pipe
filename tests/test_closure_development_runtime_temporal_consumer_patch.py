from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import pytest

from src.experiments import closure_development_runtime_temporal_consumer_patch as patch
from src.experiments import (
    lock_closure_development_runtime_temporal_consumer_patch as locker,
)
from src.experiments.closure_contract import load_json_mapping, validate_json_schema


def _file_record(path: str, role: str = "locked_component") -> dict[str, Any]:
    return {
        "path": path,
        "role": role,
        "bytes": 1,
        "sha256": "1" * 64,
    }


def _bundle(paths: tuple[str, ...], *, role: str = "locked_component") -> dict[str, Any]:
    records = [_file_record(path, role) for path in paths]
    return {
        "count": len(paths),
        "paths": list(paths),
        "paths_sha256": patch._path_digest(paths),
        "records": records,
        "records_sha256": patch._record_digest(records),
    }


def _command_evidence(
    command: tuple[str, ...],
    *,
    focused: bool = False,
    dvc: bool = False,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "command": list(command),
        "returncode": 0,
        "stdout_sha256": "2" * 64,
        "stderr_sha256": "3" * 64,
        "stdout_line_count": 1,
        "stderr_line_count": 0,
    }
    if focused:
        evidence.update(
            {
                "test_count": patch.FOCUSED_TEST_COUNT,
                "skipped_count": 0,
                "deselected_count": 0,
            }
        )
    if dvc:
        evidence["terminal_status"] = "Everything is up to date."
    return evidence


def _verification() -> dict[str, Any]:
    return {
        "full_type_check": _command_evidence(patch.TYPE_CHECK_COMMAND),
        "focused_tests": _command_evidence(
            patch.FOCUSED_TEST_COMMAND,
            focused=True,
        ),
        "poetry_check": _command_evidence(patch.POETRY_CHECK_COMMAND),
        "publication_guard": _command_evidence(patch.PUBLICATION_GUARD_COMMAND),
        "git_diff_check": _command_evidence(patch.DIFF_CHECK_COMMAND),
        "dvc_push_first": _command_evidence(patch.DVC_PUSH_COMMAND, dvc=True),
        "dvc_push_second": _command_evidence(patch.DVC_PUSH_COMMAND, dvc=True),
    }


def _upstream_preserved_bundle() -> dict[str, Any]:
    payload = patch._load_regular_json(patch.DEFAULT_DLS_LOCK_PATH, context="P-DLS")
    return copy.deepcopy(payload["base_authority"]["preserved_components"])


def _prelock(head: str = "a" * 40) -> dict[str, Any]:
    preserved = _bundle(patch.PRESERVED_DLS_COMPONENT_PATHS)
    superseded_records = [
        _file_record(path, "historical_dls_component")
        for path in patch.SUPERSEDED_COMPONENT_PATHS
    ]
    authority_records = [
        copy.deepcopy(patch.DLS_AUTHORITY_RECORDS[path])
        for path in sorted(patch.DLS_AUTHORITY_RECORDS)
    ]
    p0_records = [
        _file_record(path, "published_p0_bundle_component")
        for path in patch.P0_BUNDLE_GIT_PATHS
    ]
    authority = {
        "dls_patch_head": patch.DLS_PATCH_HEAD,
        "dls_lock_commit": patch.DLS_LOCK_COMMIT,
        "records": authority_records,
        "records_sha256": patch._record_digest(authority_records),
        "p_dls_base_preserved_components": _upstream_preserved_bundle(),
        "preserved_components": preserved,
        "superseded_components": {
            "count": 6,
            "paths": list(patch.SUPERSEDED_COMPONENT_PATHS),
            "paths_sha256": patch._path_digest(patch.SUPERSEDED_COMPONENT_PATHS),
            "historical_records": superseded_records,
            "historical_records_sha256": patch._record_digest(superseded_records),
            "historical_records_verified_at_h_dls": True,
            "current_bytes_required_to_match_h_dls": False,
        },
        "p_dls_payload_validated": True,
        "p_dls_companion_hash_validated": True,
        "physical_development_authority_verified": True,
        "p0_bundle": {
            "commit": patch.P0_BUNDLE_COMMIT,
            "parent": patch.DLS_LOCK_COMMIT,
            "records": p0_records,
            "records_sha256": patch._record_digest(p0_records),
            "payload": {
                "path": patch.P0_PAYLOAD_PATH.as_posix(),
                "role": "p0_sequence_payload",
                "bytes": patch.P0_PAYLOAD_BYTES,
                "sha256": patch.P0_PAYLOAD_SHA256,
                "md5": patch.P0_PAYLOAD_MD5,
            },
            "pointer_md5": patch.P0_PAYLOAD_MD5,
            "pointer_size": patch.P0_PAYLOAD_BYTES,
            "physical_payload_verified": True,
            "future_outcomes_accessed": False,
        },
    }
    components = _bundle(patch.PATCH_PATHS)
    components["records"] = [
        _file_record(path, patch.PATCH_COMPONENT_ROLES[path])
        for path in patch.PATCH_PATHS
    ]
    components["records_sha256"] = patch._record_digest(components["records"])
    entries = [
        {
            "status": "M" if path in patch.SUPERSEDED_COMPONENT_PATHS else "A",
            "path": path,
        }
        for path in patch.PATCH_PATHS
    ]
    output_paths = [path.as_posix() for path in patch.temporal_consumer_output_paths()]
    return {
        "base_authority": authority,
        "patch_repository": {
            "head": head,
            "parent": patch.PATCH_BASE_COMMIT,
            "branch": "main",
            "published_ref": patch.PUBLISHED_REF,
            "published_head": head,
            "remote_main_oid": head,
            "worktree_status": "clean",
            "exact_diff_verified": True,
        },
        "patch_components": components,
        "git_diff": {
            "base_commit": patch.PATCH_BASE_COMMIT,
            "patch_head": head,
            "entries": entries,
            "paths": list(patch.PATCH_PATHS),
            "paths_sha256": patch._path_digest(patch.PATCH_PATHS),
            "only_allowed_additions_and_modifications": True,
        },
        "consumer_prelock": {
            "model_id": "P0",
            "base_seeds": list(patch.REGISTERED_SEEDS),
            "count": len(output_paths),
            "paths": output_paths,
            "paths_sha256": patch._path_digest(output_paths),
            "all_absent_at_lock": True,
        },
    }


def test_patch_scope_is_exact_six_superseded_plus_five_added() -> None:
    assert len(patch.SUPERSEDED_COMPONENT_PATHS) == 6
    assert len(patch.PRESERVED_DLS_COMPONENT_PATHS) == 5
    assert len(patch.PATCH_ADDED_PATHS) == 5
    assert len(patch.PATCH_PATHS) == 11
    assert set(patch.PATCH_ADDED_PATHS).isdisjoint(patch.SUPERSEDED_COMPONENT_PATHS)
    assert set(patch.PATCH_ADDED_PATHS) | set(patch.SUPERSEDED_COMPONENT_PATHS) == set(
        patch.PATCH_PATHS
    )


def test_p_dls_partition_rejects_missing_duplicate_or_unknown_records() -> None:
    records = [
        _file_record(path)
        for path in (*patch.SUPERSEDED_COMPONENT_PATHS, *patch.PRESERVED_DLS_COMPONENT_PATHS)
    ]
    superseded, preserved = patch.partition_dls_component_records(records)
    assert [record["path"] for record in superseded] == list(
        patch.SUPERSEDED_COMPONENT_PATHS
    )
    assert [record["path"] for record in preserved] == list(
        patch.PRESERVED_DLS_COMPONENT_PATHS
    )
    for malformed in (records[:-1], [*records, records[0]], [*records[:-1], _file_record("x")]):
        with pytest.raises(RuntimeError, match=r"closed 6\+5 partition"):
            patch.partition_dls_component_records(malformed)


def test_historical_authority_copies_nested_40_component_bundle_exactly() -> None:
    source = patch._load_regular_json(patch.DEFAULT_DLS_LOCK_PATH, context="P-DLS")
    observed = patch._historical_dls_authority(require_physical_artifacts=False)
    expected = source["base_authority"]["preserved_components"]
    assert observed["p_dls_base_preserved_components"] == expected
    assert expected["count"] == patch.P_DLS_BASE_PRESERVED_COUNT == 40
    assert expected["paths_sha256"] == patch.P_DLS_BASE_PRESERVED_PATHS_SHA256
    assert expected["records_sha256"] == patch.P_DLS_BASE_PRESERVED_RECORDS_SHA256
    assert observed["physical_development_authority_verified"] is True
    assert observed["p0_bundle"]["physical_payload_verified"] is True
    assert observed["p0_bundle"]["payload"] == {
        "path": patch.P0_PAYLOAD_PATH.as_posix(),
        "role": "p0_sequence_payload",
        "bytes": patch.P0_PAYLOAD_BYTES,
        "sha256": patch.P0_PAYLOAD_SHA256,
        "md5": patch.P0_PAYLOAD_MD5,
    }


def test_strict_json_decoder_and_git_errors_never_expose_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for encoded in (
        b'{"lock": 1, "lock": 2}',
        b'{"lock": {"nested": 1, "nested": 2}}',
        b'{"lock": NaN}',
        b'{"lock": Infinity}',
    ):
        with pytest.raises(RuntimeError, match="canonical JSON"):
            patch._decode_json(encoded, context="test payload")
    monkeypatch.setattr(
        patch.subprocess,
        "run",
        lambda *_args, **_kwargs: patch.subprocess.CompletedProcess(
            args=["git", "ls-remote"],
            returncode=128,
            stdout="",
            stderr="https://token@example.invalid/private.git",
        ),
    )
    with pytest.raises(RuntimeError) as caught:
        patch._git("ls-remote", "origin")
    assert "token" not in str(caught.value)
    assert "example.invalid" not in str(caught.value)


def test_path_resolution_rejects_symlinked_escape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    outside = tmp_path / "outside"
    repository.mkdir()
    outside.mkdir()
    (repository / "escape").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(patch, "PROJECT_ROOT", repository)
    with pytest.raises(RuntimeError, match="escapes repository"):
        patch._relative(Path("escape/authority.json"))


def test_regular_reader_rejects_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}\n", encoding="utf-8")
    (tmp_path / "link.json").symlink_to(target)
    monkeypatch.setattr(patch, "PROJECT_ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="not a regular file"):
        patch._read_regular_bytes(Path("link.json"), context="authority")


def test_regular_reader_rejects_symlinked_ancestor_even_inside_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "authority.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "linked").symlink_to(real, target_is_directory=True)
    monkeypatch.setattr(patch, "PROJECT_ROOT", tmp_path)

    with pytest.raises(RuntimeError, match="linked ancestor"):
        patch._read_regular_bytes(
            Path("linked/authority.json"),
            context="authority",
        )


def test_consumer_prelock_covers_finals_temps_and_exact_guards() -> None:
    paths = patch.temporal_consumer_output_paths()
    assert len(paths) == 95
    assert len(set(paths)) == 95
    for seed in patch.REGISTERED_SEEDS:
        assert Path(
            f"tmp/closure_v1_temporal_consumer/P0_seed_{seed}.guard"
        ) in paths


def test_consumer_absence_rejects_broken_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(patch, "PROJECT_ROOT", tmp_path)
    candidate = tmp_path / "slot.guard"
    candidate.symlink_to(tmp_path / "missing")
    with pytest.raises(RuntimeError, match="must be absent"):
        patch.consumer_namespace_absence((Path("slot.guard"),))


def test_verification_requires_clean_tests_and_two_idempotent_dvc_pushes() -> None:
    verification = _verification()
    patch.validate_temporal_consumer_patch_verification(verification)
    verification["focused_tests"]["skipped_count"] = 1
    with pytest.raises(RuntimeError, match="focused-test"):
        patch.validate_temporal_consumer_patch_verification(verification)
    verification = _verification()
    verification["focused_tests"]["test_count"] = patch.FOCUSED_TEST_COUNT - 1
    with pytest.raises(RuntimeError, match="focused-test"):
        patch.validate_temporal_consumer_patch_verification(verification)
    verification = _verification()
    verification["dvc_push_second"]["terminal_status"] = "1 file pushed"
    with pytest.raises(RuntimeError, match="not exact and idempotent"):
        patch.validate_temporal_consumer_patch_verification(verification)


def test_lock_payload_matches_closed_schema_and_rebuilt_authorities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prelock = _prelock()
    prelock["base_authority"] = patch._historical_dls_authority(
        require_physical_artifacts=False
    )
    payload = patch.build_temporal_consumer_patch_lock_payload(
        prelock,
        _verification(),
        created_at_utc="2026-08-04T20:00:00Z",
    )
    schema = load_json_mapping(patch.DEFAULT_PATCH_LOCK_SCHEMA)
    validate_json_schema(payload, schema, instance_path="$.lock")
    monkeypatch.setattr(patch, "_require_commit", lambda value, **_: value)
    monkeypatch.setattr(patch, "patch_git_diff_payload", lambda _head: prelock["git_diff"])
    monkeypatch.setattr(
        patch,
        "patch_component_bundle",
        lambda _head: prelock["patch_components"],
    )
    patch.validate_development_runtime_temporal_consumer_patch_lock_payload(
        payload,
        schema,
    )
    payload["correction"]["denominator_changed"] = True
    with pytest.raises(RuntimeError, match="JSON Schema const"):
        patch.validate_development_runtime_temporal_consumer_patch_lock_payload(
            payload,
            schema,
        )


def test_schema_closes_nested_authority_and_evidence_dialects() -> None:
    payload = patch.build_temporal_consumer_patch_lock_payload(
        _prelock(),
        _verification(),
        created_at_utc="2026-08-04T20:00:00Z",
    )
    schema = load_json_mapping(patch.DEFAULT_PATCH_LOCK_SCHEMA)
    for section in ("base_authority", "correction", "authorizations", "seals"):
        malformed = copy.deepcopy(payload)
        malformed[section]["unexpected"] = False
        with pytest.raises(ValueError, match="additionalProperties"):
            validate_json_schema(malformed, schema, instance_path="$.lock")
    malformed = copy.deepcopy(payload)
    malformed["verification"]["dvc_push_first"]["extra"] = True
    with pytest.raises(ValueError, match="additionalProperties"):
        validate_json_schema(malformed, schema, instance_path="$.lock")


def test_companion_binds_p_dls_and_p0_authorities() -> None:
    payload = patch.build_temporal_consumer_patch_lock_payload(
        _prelock(),
        _verification(),
        created_at_utc="2026-08-04T20:00:00Z",
    )
    companion = patch._expected_companion(
        payload,
        lock_record=_file_record(
            patch.DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "external_development_runtime_temporal_consumer_patch_lock",
        ),
    )
    inputs = {record["path"] for record in companion["inputs"]}
    assert {
        patch.DEFAULT_DLS_LOCK_PATH.as_posix(),
        patch.DEFAULT_DLS_MANIFEST_PATH.as_posix(),
        patch.DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
        "src/experiments/closure_development_runtime_temporal_consumer_patch.py",
        patch.P0_POINTER_PATH.as_posix(),
        patch.P0_MANIFEST_PATH.as_posix(),
    } == inputs
    assert companion["authoritative_lock_path"] == patch.DEFAULT_PATCH_LOCK_PATH.as_posix()


def test_loader_fails_closed_before_p_dlt_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(patch, "PROJECT_ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="is absent"):
        patch.load_and_validate_development_runtime_temporal_consumer_patch_lock()


def test_gate_rejects_non_cpu_before_loading_lock() -> None:
    with pytest.raises(RuntimeError, match="locked CPU"):
        patch.require_development_fit_authorized_with_temporal_consumer_patch(
            device="auto"
        )


def test_gate_requires_every_effective_authorization_predicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary = {
        "publication_verified": True,
        "remote_publication_verified": True,
        "physical_artifacts_verified": True,
        "historical_authority_verified": True,
        "patch_components_verified": True,
        "locked_head_is_ancestor": True,
        "development_fit_authorized": True,
        "fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }
    monkeypatch.setattr(
        patch,
        "load_and_validate_development_runtime_temporal_consumer_patch_lock",
        lambda **_: ({}, summary),
    )
    assert (
        patch.require_development_fit_authorized_with_temporal_consumer_patch(
            device="cpu"
        )
        == summary
    )
    summary["remote_publication_verified"] = False
    with pytest.raises(RuntimeError, match="development-fit predicates"):
        patch.require_development_fit_authorized_with_temporal_consumer_patch(
            device="cpu"
        )


def test_locker_parsers_require_exact_clean_terminal_results() -> None:
    count = patch.FOCUSED_TEST_COUNT
    assert locker._parse_focused_summary(f"{count} passed in 1.25s\n", "") == count
    for stdout, stderr in (
        (f"{count} passed, 1 skipped in 1.25s\n", ""),
        (f"{count} passed in 1.25s\n", "warning"),
        (f"{count - 1} passed in 1.25s\n", ""),
        (f"{count} passed in 1.25s\n{count} passed in 1.50s\n", ""),
    ):
        with pytest.raises(RuntimeError, match="exact clean result"):
            locker._parse_focused_summary(stdout, stderr)
    assert (
        locker._terminal_status(
            "Everything is up to date.\nChecking tracked files before publication...\n",
            "",
        )
        == "Everything is up to date."
    )
    with pytest.raises(RuntimeError, match="not exactly idempotent"):
        locker._terminal_status("1 file pushed\n", "")


def test_locker_sanitizes_python_and_executable_search_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}
    for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "POETRY_ACTIVE"):
        monkeypatch.setenv(key, f"untrusted-{key.lower()}")
    monkeypatch.setenv("PATH", "/untrusted/bin")

    def completed(*args: Any, **kwargs: Any) -> Any:
        captured.update(kwargs["env"])
        return locker.subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(locker.subprocess, "run", completed)
    locker._run_command(("git", "diff", "--check"))

    for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "POETRY_ACTIVE"):
        assert key not in captured
    assert captured["PYTHONNOUSERSITE"] == "1"
    assert "/untrusted/bin" not in captured["PATH"]
    assert captured["DVC_BIN"] == str(locker.PROJECT_ROOT / ".venv/bin/dvc")
    with pytest.raises(RuntimeError, match="escaped the closed DVC policy"):
        locker._run_command(
            ("git", "diff", "--check"),
            environment={"PYTHONPATH": "/untrusted"},
        )


def test_fixed_verification_executable_rejects_symlinked_venv_ancestor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outside = tmp_path / "outside/bin"
    outside.mkdir(parents=True)
    executable = outside / "ty"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    (tmp_path / ".venv").symlink_to(outside.parent, target_is_directory=True)
    monkeypatch.setattr(locker, "PROJECT_ROOT", tmp_path)

    with pytest.raises(RuntimeError, match="verification executable is absent"):
        locker._require_fixed_venv_executable((".venv/bin/ty", "check"))


def test_check_only_runs_no_verification_or_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    prelock = _prelock()
    monkeypatch.setattr(
        locker,
        "_refuse_existing_outputs",
        lambda *_args: events.append("absence"),
    )
    monkeypatch.setattr(
        locker,
        "collect_temporal_consumer_patch_prelock_state",
        lambda **_kwargs: events.append("prelock") or prelock,
    )
    monkeypatch.setattr(
        locker,
        "run_temporal_consumer_patch_verification",
        lambda: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    result = locker._check_only(
        patch.DEFAULT_PATCH_LOCK_PATH,
        patch.DEFAULT_PATCH_MANIFEST_PATH,
    )
    assert events == ["absence", "prelock"]
    assert result["status"] == "ready_to_lock"
    assert result["writes_performed"] is False
    assert result["verification_commands_run"] is False


def _locker_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path]:
    monkeypatch.setattr(locker, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        locker,
        "OUTPUT_GUARD_DIRECTORY",
        tmp_path / "tmp" / "closure_v1_e0_dlt_locker",
    )
    lock_path = tmp_path / patch.DEFAULT_PATCH_LOCK_PATH
    companion_path = tmp_path / patch.DEFAULT_PATCH_MANIFEST_PATH
    lock_path.parent.mkdir(parents=True)
    return lock_path, companion_path


def test_locker_refuses_broken_symlink_at_every_reserved_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock_path, companion_path = _locker_paths(tmp_path, monkeypatch)
    guard_paths = locker._guard_paths(create_directory=True)
    candidates = (
        lock_path,
        lock_path.with_suffix(lock_path.suffix + ".tmp"),
        companion_path,
        companion_path.with_suffix(companion_path.suffix + ".tmp"),
        *guard_paths,
    )
    for candidate in candidates:
        candidate.symlink_to(tmp_path / "missing")
        with pytest.raises(RuntimeError, match="Refusing to overwrite"):
            locker._refuse_existing_outputs(lock_path, companion_path)
        candidate.unlink()
    closure_root = tmp_path / "reports" / "closure_v1"
    moved_root = tmp_path / "preserved-closure-v1"
    outside = tmp_path / "outside"
    (outside / "00_protocol").mkdir(parents=True)
    closure_root.rename(moved_root)
    closure_root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(RuntimeError, match="linked ancestor"):
        locker._closed_output(lock_path, patch.DEFAULT_PATCH_LOCK_PATH)
    assert not (outside / "00_protocol" / lock_path.name).exists()


def test_locker_guard_open_rejects_symlinked_tmp_ancestor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _locker_paths(tmp_path, monkeypatch)
    guard_path = locker._guard_paths(create_directory=True)[0]
    tmp_root = tmp_path / "tmp"
    preserved_tmp = tmp_path / "preserved-tmp"
    outside = tmp_path / "outside"
    (outside / "closure_v1_e0_dlt_locker").mkdir(parents=True)
    tmp_root.rename(preserved_tmp)
    tmp_root.symlink_to(outside, target_is_directory=True)

    with pytest.raises(RuntimeError, match="linked ancestor"):
        locker._open_guard(guard_path)
    assert not (outside / "closure_v1_e0_dlt_locker" / guard_path.name).exists()


def test_guarded_publication_never_clobbers_and_rollback_is_inode_owned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock_path, companion_path = _locker_paths(tmp_path, monkeypatch)
    guards = locker._acquire_guards(lock_path, companion_path)
    try:
        lock_path.write_bytes(b"racing writer\n")
        with pytest.raises(RuntimeError, match="clobber"):
            locker._publish_guarded_bytes(
                b"ours\n",
                lock_path,
                patch.DEFAULT_PATCH_LOCK_PATH,
                guards[0],
            )
        assert lock_path.read_bytes() == b"racing writer\n"
        lock_path.unlink()
        owned = locker._publish_guarded_bytes(
            b"owned\n",
            lock_path,
            patch.DEFAULT_PATCH_LOCK_PATH,
            guards[0],
        )
        lock_path.unlink()
        lock_path.write_bytes(b"replacement\n")
        locker._unlink_if_owned(owned)
        assert lock_path.read_bytes() == b"replacement\n"
        os.close(owned.directory_file_descriptor)
    finally:
        for guard in reversed(guards):
            locker._release_guard(guard)


def _synthetic_lock_resources() -> tuple[
    tuple[locker._OwnedFile, ...],
    tuple[locker._OutputGuard, ...],
]:
    owners = (
        locker._OwnedFile(Path("lock.json"), 1, 11, 101),
        locker._OwnedFile(Path("manifest.json"), 1, 12, 102),
    )
    guards = (
        locker._OutputGuard(Path("lock.guard"), 1, 21, 201, 301),
        locker._OutputGuard(Path("manifest.guard"), 1, 22, 202, 302),
    )
    return owners, guards


def test_lock_cleanup_attempts_every_resource_and_preserves_original_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owners, guards = _synthetic_lock_resources()
    events: list[tuple[str, int | str]] = []

    def unlink(owner: locker._OwnedFile) -> None:
        events.append(("unlink", owner.inode))
        if owner.inode == 12:
            raise OSError("injected unlink failure")

    def fsync(descriptor: int) -> None:
        events.append(("fsync", descriptor))

    def close(descriptor: int) -> None:
        events.append(("close", descriptor))

    def release(guard: locker._OutputGuard) -> None:
        events.append(("release", guard.inode))
        if guard.inode == 22:
            raise OSError("injected guard failure")

    monkeypatch.setattr(locker, "_unlink_if_owned", unlink)
    monkeypatch.setattr(locker.os, "fsync", fsync)
    monkeypatch.setattr(locker.os, "close", close)
    monkeypatch.setattr(locker, "_release_guard", release)
    original = RuntimeError("original lock failure")
    with pytest.raises(RuntimeError, match="cleanup could not be completed") as raised:
        locker._cleanup_lock_resources(
            owners,
            guards,
            succeeded=False,
            active_error=original,
        )

    assert raised.value.__cause__ is original
    assert {event for event in events if event[0] == "unlink"} == {
        ("unlink", 11),
        ("unlink", 12),
    }
    assert {event for event in events if event[0] == "release"} == {
        ("release", 21),
        ("release", 22),
    }
    assert {event for event in events if event[0] == "close"} == {
        ("close", 101),
        ("close", 102),
    }
    assert raised.value.__notes__


def test_successful_lock_rolls_back_finals_if_guard_release_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owners, guards = _synthetic_lock_resources()
    unlinked: list[int] = []
    released: list[int] = []

    monkeypatch.setattr(
        locker,
        "_unlink_if_owned",
        lambda owner: unlinked.append(owner.inode),
    )
    monkeypatch.setattr(locker.os, "fsync", lambda descriptor: None)
    monkeypatch.setattr(locker.os, "close", lambda descriptor: None)

    def release(guard: locker._OutputGuard) -> None:
        released.append(guard.inode)
        if guard.inode == 22:
            raise OSError("injected guard failure")

    monkeypatch.setattr(locker, "_release_guard", release)
    with pytest.raises(RuntimeError, match="cleanup could not be completed"):
        locker._cleanup_lock_resources(
            owners,
            guards,
            succeeded=True,
            active_error=None,
        )

    assert sorted(unlinked) == [11, 12]
    assert sorted(released) == [21, 22]


def test_guarded_publication_closes_parent_when_rollback_unlink_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock_path, companion_path = _locker_paths(tmp_path, monkeypatch)
    guards = locker._acquire_guards(lock_path, companion_path)
    real_close = os.close
    closed: list[int] = []

    def tracked_close(descriptor: int) -> None:
        closed.append(descriptor)
        real_close(descriptor)

    def fail_unlink(owner: locker._OwnedFile) -> None:
        raise OSError("injected unlink failure")

    monkeypatch.setattr(locker, "_owned", lambda owner: False)
    monkeypatch.setattr(locker, "_unlink_if_owned", fail_unlink)
    monkeypatch.setattr(locker.os, "close", tracked_close)
    try:
        with pytest.raises(RuntimeError, match="rollback could not be completed") as raised:
            locker._publish_guarded_bytes(
                b"owned\n",
                lock_path,
                patch.DEFAULT_PATCH_LOCK_PATH,
                guards[0],
            )
        assert closed
        assert raised.value.__notes__
    finally:
        for guard in reversed(guards):
            locker._release_guard(guard)
