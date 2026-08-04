#!/usr/bin/env python
"""Create the one-time additive Closure V1 E0-DLS lock bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments.closure_development_runtime_sequence_patch import (
    DEFAULT_SEQUENCE_PATCH_LOCK_PATH,
    DEFAULT_SEQUENCE_PATCH_LOCK_SCHEMA,
    DEFAULT_SEQUENCE_PATCH_MANIFEST_PATH,
    PATCH_GATE,
    PATCH_ID,
    SEQUENCE_PATCH_DIFF_CHECK_COMMAND,
    SEQUENCE_PATCH_FOCUSED_TEST_COMMAND,
    SEQUENCE_PATCH_FOCUSED_TEST_COUNT,
    SEQUENCE_PATCH_POETRY_CHECK_COMMAND,
    SEQUENCE_PATCH_PUBLICATION_GUARD_COMMAND,
    SEQUENCE_PATCH_TEST_ENVIRONMENT,
    SEQUENCE_PATCH_TYPE_CHECK_COMMAND,
    DevelopmentRuntimeSequencePatchError,
    assert_p0_one_shot_outputs_absent,
    build_sequence_patch_lock_payload,
    collect_sequence_patch_prelock_state,
    load_and_validate_development_runtime_sequence_patch_lock,
    validate_development_runtime_sequence_patch_lock_payload,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_GUARD_DIRECTORY = PROJECT_ROOT / "tmp" / "closure_v1_e0_dls_locker"
OUTPUT_GUARD_NAMES = (
    "development_runtime_sequence_patch_lock.guard",
    "development_runtime_sequence_patch_lock_manifest.guard",
)
FORBIDDEN_PYTEST_SUMMARY_TOKEN_RE = re.compile(
    r"\b(?:warnings?|skipped|deselected|xfailed|xpassed)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class _OwnedFile:
    path: Path
    device: int
    inode: int
    directory_file_descriptor: int | None = None


@dataclass(frozen=True)
class _OutputGuard:
    owned: _OwnedFile
    file_descriptor: int
    directory_file_descriptor: int


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _line_count(payload: str) -> int:
    return len(payload.splitlines())


def _run_command(
    command: Sequence[str],
    *,
    environment: Mapping[str, str] | None = None,
    success_marker: str | None = None,
    require_empty_output: bool = False,
    sanitize_pytest_environment: bool = False,
) -> tuple[dict[str, Any], str, str]:
    env = os.environ.copy()
    if sanitize_pytest_environment:
        for key in tuple(env):
            if key.startswith("PYTEST_") or key == "PY_COLORS":
                env.pop(key)
    if environment is not None:
        env.update(environment)
    try:
        result = subprocess.run(
            list(command),
            cwd=PROJECT_ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=3600,
        )
    except subprocess.TimeoutExpired as exc:
        raise DevelopmentRuntimeSequencePatchError(
            f"E0-DLS verification timed out: {' '.join(command)}"
        ) from exc
    stdout = result.stdout
    stderr = result.stderr
    if result.returncode != 0:
        raise DevelopmentRuntimeSequencePatchError(
            f"E0-DLS verification failed: {' '.join(command)}"
        )
    combined = stdout + "\n" + stderr
    if success_marker is not None and success_marker not in combined:
        raise DevelopmentRuntimeSequencePatchError(
            f"E0-DLS success marker is absent for {' '.join(command)}"
        )
    if require_empty_output and (stdout.strip() or stderr.strip()):
        raise DevelopmentRuntimeSequencePatchError(
            f"E0-DLS expected no output from {' '.join(command)}"
        )
    evidence = {
        "command": list(command),
        "exit_code": 0,
        "stdout_sha256": _sha256(stdout.encode("utf-8")),
        "stderr_sha256": _sha256(stderr.encode("utf-8")),
        "stdout_line_count": _line_count(stdout),
        "stderr_line_count": _line_count(stderr),
        "success_marker_verified": True,
    }
    return evidence, stdout, stderr


def _require_fixed_verification_executable(command: Sequence[str]) -> None:
    if not command or Path(command[0]).parent != Path(".venv/bin"):
        raise DevelopmentRuntimeSequencePatchError(
            "E0-DLS fixed verification executable escaped .venv/bin"
        )
    executable = PROJECT_ROOT / command[0]
    try:
        metadata = executable.lstat()
    except FileNotFoundError as exc:
        raise DevelopmentRuntimeSequencePatchError(
            f"E0-DLS fixed verification executable is absent: {command[0]}"
        ) from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or executable.is_symlink()
        or not os.access(executable, os.X_OK)
    ):
        raise DevelopmentRuntimeSequencePatchError(
            f"E0-DLS fixed verification executable is unsafe: {command[0]}"
        )


def _parse_exact_focused_summary(stdout: str, stderr: str) -> int:
    combined = stdout + "\n" + stderr
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    summary_re = re.compile(
        rf"^{SEQUENCE_PATCH_FOCUSED_TEST_COUNT} passed in [0-9]+(?:\.[0-9]+)?s$"
    )
    matches = [line for line in lines if summary_re.fullmatch(line)]
    if (
        not lines
        or matches != [lines[-1]]
        or FORBIDDEN_PYTEST_SUMMARY_TOKEN_RE.search(combined) is not None
    ):
        raise DevelopmentRuntimeSequencePatchError(
            "E0-DLS focused pytest summary is not the one exact clean result"
        )
    return SEQUENCE_PATCH_FOCUSED_TEST_COUNT


def run_sequence_patch_verification() -> dict[str, Any]:
    _require_fixed_verification_executable(SEQUENCE_PATCH_TYPE_CHECK_COMMAND)
    _require_fixed_verification_executable(SEQUENCE_PATCH_FOCUSED_TEST_COMMAND)
    type_check, _, _ = _run_command(
        SEQUENCE_PATCH_TYPE_CHECK_COMMAND,
        success_marker="All checks passed!",
    )
    focused, stdout, stderr = _run_command(
        SEQUENCE_PATCH_FOCUSED_TEST_COMMAND,
        environment=SEQUENCE_PATCH_TEST_ENVIRONMENT,
        sanitize_pytest_environment=True,
    )
    passed = _parse_exact_focused_summary(stdout, stderr)
    focused.update(
        {
            "test_count": passed,
            "skipped_count": 0,
            "deselected_count": 0,
        }
    )
    poetry_check, _, _ = _run_command(
        SEQUENCE_PATCH_POETRY_CHECK_COMMAND,
        success_marker="All set!",
    )
    publication_guard, _, _ = _run_command(
        SEQUENCE_PATCH_PUBLICATION_GUARD_COMMAND,
    )
    diff_check, _, _ = _run_command(
        SEQUENCE_PATCH_DIFF_CHECK_COMMAND,
        require_empty_output=True,
    )
    return {
        "full_type_check": type_check,
        "focused_tests": focused,
        "poetry_check": poetry_check,
        "publication_guard": publication_guard,
        "git_diff_check": diff_check,
    }


def _closed_output(path: Path, expected: Path) -> Path:
    candidate = path if path.is_absolute() else PROJECT_ROOT / path
    lexical = Path(os.path.abspath(candidate))
    required = PROJECT_ROOT.resolve() / expected
    if lexical != required:
        raise DevelopmentRuntimeSequencePatchError(
            f"E0-DLS output must use the closed path: {expected.as_posix()}"
        )
    parent = lexical.parent.resolve(strict=True)
    if parent != required.parent.resolve(strict=True):
        raise DevelopmentRuntimeSequencePatchError(
            f"E0-DLS output parent drifted: {expected.as_posix()}"
        )
    if not stat.S_ISDIR(lexical.parent.lstat().st_mode):
        raise DevelopmentRuntimeSequencePatchError(
            f"E0-DLS output parent is not a real directory: {expected.as_posix()}"
        )
    return lexical


def _open_real_directory(path: Path, *, context: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise DevelopmentRuntimeSequencePatchError(
            f"{context} is unavailable or not a real directory: {path}"
        ) from exc
    try:
        opened = os.fstat(descriptor)
        lexical = path.lstat()
        if (
            not stat.S_ISDIR(opened.st_mode)
            or not stat.S_ISDIR(lexical.st_mode)
            or (opened.st_dev, opened.st_ino) != (lexical.st_dev, lexical.st_ino)
        ):
            raise DevelopmentRuntimeSequencePatchError(
                f"{context} directory identity drifted: {path}"
            )
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _is_owned(owned: _OwnedFile) -> bool:
    if owned.directory_file_descriptor is None:
        return False
    try:
        directory = os.fstat(owned.directory_file_descriptor)
        lexical_directory = owned.path.parent.lstat()
        metadata = os.stat(
            owned.path.name,
            dir_fd=owned.directory_file_descriptor,
            follow_symlinks=False,
        )
        lexical = owned.path.lstat()
    except (FileNotFoundError, OSError):
        return False
    return (
        stat.S_ISDIR(directory.st_mode)
        and stat.S_ISDIR(lexical_directory.st_mode)
        and (directory.st_dev, directory.st_ino)
        == (lexical_directory.st_dev, lexical_directory.st_ino)
        and stat.S_ISREG(metadata.st_mode)
        and stat.S_ISREG(lexical.st_mode)
        and (metadata.st_dev, metadata.st_ino) == (owned.device, owned.inode)
        and (lexical.st_dev, lexical.st_ino) == (owned.device, owned.inode)
    )


def _unlink_if_owned(owned: _OwnedFile) -> None:
    if owned.directory_file_descriptor is None:
        return
    try:
        metadata = os.stat(
            owned.path.name,
            dir_fd=owned.directory_file_descriptor,
            follow_symlinks=False,
        )
    except (FileNotFoundError, OSError):
        return
    if (
        stat.S_ISREG(metadata.st_mode)
        and (metadata.st_dev, metadata.st_ino) == (owned.device, owned.inode)
    ):
        os.unlink(owned.path.name, dir_fd=owned.directory_file_descriptor)


def _close_owned_directory(owned: _OwnedFile) -> None:
    if owned.directory_file_descriptor is not None:
        os.close(owned.directory_file_descriptor)


def _guard_is_owned(guard: _OutputGuard) -> bool:
    try:
        opened = os.fstat(guard.file_descriptor)
        metadata = os.stat(
            guard.owned.path.name,
            dir_fd=guard.directory_file_descriptor,
            follow_symlinks=False,
        )
    except (FileNotFoundError, OSError):
        return False
    return (
        stat.S_ISREG(opened.st_mode)
        and stat.S_ISREG(metadata.st_mode)
        and (opened.st_dev, opened.st_ino)
        == (guard.owned.device, guard.owned.inode)
        and (metadata.st_dev, metadata.st_ino)
        == (guard.owned.device, guard.owned.inode)
    )


def _open_output_guard(path: Path) -> _OutputGuard:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    directory_descriptor = _open_real_directory(
        path.parent,
        context="E0-DLS output-guard parent",
    )
    try:
        descriptor = os.open(
            path.name,
            flags,
            0o600,
            dir_fd=directory_descriptor,
        )
    except FileExistsError as exc:
        os.close(directory_descriptor)
        raise DevelopmentRuntimeSequencePatchError(
            f"Refusing an existing E0-DLS guard: {path}"
        ) from exc
    except BaseException:
        os.close(directory_descriptor)
        raise
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise DevelopmentRuntimeSequencePatchError(
                f"E0-DLS output guard is not a regular file: {path}"
            )
        return _OutputGuard(
            owned=_OwnedFile(path=path, device=metadata.st_dev, inode=metadata.st_ino),
            file_descriptor=descriptor,
            directory_file_descriptor=directory_descriptor,
        )
    except BaseException:
        os.close(descriptor)
        os.close(directory_descriptor)
        raise


def _output_guard_paths(
    output: Path,
    companion_output: Path,
    *,
    create_directory: bool,
) -> tuple[Path, Path]:
    resolved_output = _closed_output(output, DEFAULT_SEQUENCE_PATCH_LOCK_PATH)
    resolved_companion = _closed_output(
        companion_output,
        DEFAULT_SEQUENCE_PATCH_MANIFEST_PATH,
    )
    tmp_root = PROJECT_ROOT / "tmp"
    if OUTPUT_GUARD_DIRECTORY.parent != tmp_root:
        raise DevelopmentRuntimeSequencePatchError(
            "E0-DLS coordination directory escaped the ignored tmp/ root"
        )
    repository_descriptor = _open_real_directory(
        PROJECT_ROOT,
        context="E0-DLS repository root",
    )
    tmp_descriptor: int | None = None
    guard_descriptor: int | None = None
    try:
        try:
            tmp_metadata = os.stat(
                "tmp",
                dir_fd=repository_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            if not create_directory:
                return (
                    OUTPUT_GUARD_DIRECTORY / OUTPUT_GUARD_NAMES[0],
                    OUTPUT_GUARD_DIRECTORY / OUTPUT_GUARD_NAMES[1],
                )
            os.mkdir("tmp", mode=0o700, dir_fd=repository_descriptor)
            tmp_metadata = os.stat(
                "tmp",
                dir_fd=repository_descriptor,
                follow_symlinks=False,
            )
        if not stat.S_ISDIR(tmp_metadata.st_mode):
            raise DevelopmentRuntimeSequencePatchError(
                "Ignored repository tmp/ root must be a real directory"
            )
        directory_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        directory_flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        tmp_descriptor = os.open("tmp", directory_flags, dir_fd=repository_descriptor)
        guard_name = OUTPUT_GUARD_DIRECTORY.name
        try:
            guard_metadata = os.stat(
                guard_name,
                dir_fd=tmp_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            if not create_directory:
                return (
                    OUTPUT_GUARD_DIRECTORY / OUTPUT_GUARD_NAMES[0],
                    OUTPUT_GUARD_DIRECTORY / OUTPUT_GUARD_NAMES[1],
                )
            os.mkdir(guard_name, mode=0o700, dir_fd=tmp_descriptor)
            guard_metadata = os.stat(
                guard_name,
                dir_fd=tmp_descriptor,
                follow_symlinks=False,
            )
        if not stat.S_ISDIR(guard_metadata.st_mode):
            raise DevelopmentRuntimeSequencePatchError(
                "E0-DLS coordination path must be a real directory"
            )
        guard_descriptor = os.open(
            guard_name,
            directory_flags,
            dir_fd=tmp_descriptor,
        )
        opened_guard = os.fstat(guard_descriptor)
        if (
            (opened_guard.st_dev, opened_guard.st_ino)
            != (guard_metadata.st_dev, guard_metadata.st_ino)
            or any(
                opened_guard.st_dev != output_device
                for output_device in (
                    resolved_output.parent.stat().st_dev,
                    resolved_companion.parent.stat().st_dev,
                )
            )
        ):
            raise DevelopmentRuntimeSequencePatchError(
                "E0-DLS guards and final outputs must share one stable filesystem"
            )
    except OSError as exc:
        raise DevelopmentRuntimeSequencePatchError(
            "E0-DLS coordination directory could not be created or opened safely"
        ) from exc
    finally:
        if guard_descriptor is not None:
            os.close(guard_descriptor)
        if tmp_descriptor is not None:
            os.close(tmp_descriptor)
        os.close(repository_descriptor)
    return (
        OUTPUT_GUARD_DIRECTORY / OUTPUT_GUARD_NAMES[0],
        OUTPUT_GUARD_DIRECTORY / OUTPUT_GUARD_NAMES[1],
    )


def _refuse_existing_outputs(output: Path, companion_output: Path) -> None:
    resolved_output = _closed_output(output, DEFAULT_SEQUENCE_PATCH_LOCK_PATH)
    resolved_companion = _closed_output(
        companion_output,
        DEFAULT_SEQUENCE_PATCH_MANIFEST_PATH,
    )
    guards = _output_guard_paths(
        output,
        companion_output,
        create_directory=False,
    )
    candidates = (
        resolved_output,
        resolved_output.with_suffix(resolved_output.suffix + ".tmp"),
        resolved_companion,
        resolved_companion.with_suffix(resolved_companion.suffix + ".tmp"),
        *guards,
    )
    existing = [str(path) for path in candidates if os.path.lexists(path)]
    if existing:
        raise DevelopmentRuntimeSequencePatchError(
            f"Refusing to overwrite an existing E0-DLS lock bundle: {existing}"
        )


def _release_output_guard(guard: _OutputGuard) -> None:
    anchored = _OwnedFile(
        path=guard.owned.path,
        device=guard.owned.device,
        inode=guard.owned.inode,
        directory_file_descriptor=guard.directory_file_descriptor,
    )
    try:
        _unlink_if_owned(anchored)
    finally:
        try:
            os.close(guard.file_descriptor)
        finally:
            os.close(guard.directory_file_descriptor)


def _acquire_output_guards(
    output: Path,
    companion_output: Path,
) -> tuple[_OutputGuard, ...]:
    _refuse_existing_outputs(output, companion_output)
    guard_paths = _output_guard_paths(
        output,
        companion_output,
        create_directory=True,
    )
    guards: list[_OutputGuard] = []
    try:
        for path in guard_paths:
            guards.append(_open_output_guard(path))
    except BaseException:
        for guard in reversed(guards):
            _release_output_guard(guard)
        raise
    return tuple(guards)


def _publish_guarded_bytes(
    payload: bytes,
    path: Path,
    expected: Path,
    guard: _OutputGuard,
) -> _OwnedFile:
    resolved = _closed_output(path, expected)
    if not _guard_is_owned(guard):
        raise DevelopmentRuntimeSequencePatchError(
            "E0-DLS output guard changed before publication"
        )
    os.ftruncate(guard.file_descriptor, 0)
    os.lseek(guard.file_descriptor, 0, os.SEEK_SET)
    offset = 0
    while offset < len(payload):
        written = os.write(guard.file_descriptor, payload[offset:])
        if written <= 0:
            raise DevelopmentRuntimeSequencePatchError(
                "Short write while preparing an E0-DLS output"
            )
        offset += written
    os.fsync(guard.file_descriptor)
    if not _guard_is_owned(guard):
        raise DevelopmentRuntimeSequencePatchError(
            "E0-DLS output guard changed while writing"
        )
    destination_directory = _open_real_directory(
        resolved.parent,
        context="E0-DLS final-output parent",
    )
    try:
        os.link(
            guard.owned.path.name,
            resolved.name,
            src_dir_fd=guard.directory_file_descriptor,
            dst_dir_fd=destination_directory,
            follow_symlinks=False,
        )
    except FileExistsError as exc:
        os.close(destination_directory)
        raise DevelopmentRuntimeSequencePatchError(
            f"Refusing to overwrite an E0-DLS output created during checks: {path}"
        ) from exc
    except BaseException:
        os.close(destination_directory)
        raise
    published = _OwnedFile(
        path=resolved,
        device=guard.owned.device,
        inode=guard.owned.inode,
        directory_file_descriptor=destination_directory,
    )
    try:
        os.fsync(destination_directory)
        if not _is_owned(published):
            raise DevelopmentRuntimeSequencePatchError(
                "E0-DLS no-clobber publication identity drifted"
            )
        return published
    except BaseException:
        _unlink_if_owned(published)
        os.close(destination_directory)
        raise


def _owned_file_record(owned: _OwnedFile, *, role: str) -> dict[str, Any]:
    if not _is_owned(owned) or owned.directory_file_descriptor is None:
        raise DevelopmentRuntimeSequencePatchError(
            "E0-DLS published output ownership drifted before hashing"
        )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(
        owned.path.name,
        flags,
        dir_fd=owned.directory_file_descriptor,
    )
    try:
        metadata = os.fstat(descriptor)
        if (metadata.st_dev, metadata.st_ino) != (owned.device, owned.inode):
            raise DevelopmentRuntimeSequencePatchError(
                "E0-DLS published output changed before hashing"
            )
        digest = hashlib.sha256()
        total = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            total += len(chunk)
    finally:
        os.close(descriptor)
    if not _is_owned(owned):
        raise DevelopmentRuntimeSequencePatchError(
            "E0-DLS published output changed while hashing"
        )
    return {
        "path": owned.path.relative_to(PROJECT_ROOT.resolve()).as_posix(),
        "role": role,
        "bytes": total,
        "sha256": digest.hexdigest(),
    }


def _companion_payload(
    lock_payload: Mapping[str, Any],
    lock_record: Mapping[str, Any],
) -> dict[str, Any]:
    components = lock_payload["patch_components"]
    if not isinstance(components, Mapping):
        raise DevelopmentRuntimeSequencePatchError("E0-DLS components are malformed")
    raw_records = components.get("records")
    if not isinstance(raw_records, Sequence) or isinstance(raw_records, (str, bytes)):
        raise DevelopmentRuntimeSequencePatchError("E0-DLS component records are malformed")
    records = [record for record in raw_records if isinstance(record, Mapping)]
    by_path = {str(record["path"]): record for record in records}

    def component(path: str, role: str) -> dict[str, Any]:
        record = by_path[path]
        return {
            "path": path,
            "role": role,
            "bytes": record["bytes"],
            "sha256": record["sha256"],
        }

    authority = lock_payload["base_authority"]
    if not isinstance(authority, Mapping):
        raise DevelopmentRuntimeSequencePatchError("E0-DLS base authority is malformed")
    authority_records = authority.get("records")
    if not isinstance(authority_records, Sequence) or isinstance(
        authority_records, (str, bytes)
    ):
        raise DevelopmentRuntimeSequencePatchError("E0-DLS authority records are malformed")
    base_lock = next(
        record
        for record in authority_records
        if isinstance(record, Mapping)
        and record.get("path")
        == "reports/closure_v1/00_protocol/development_runtime_patch_lock.json"
    )
    return {
        "manifest_version": "closure_development_runtime_sequence_patch_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": lock_payload["created_at_utc"],
        "outputs": [dict(lock_record)],
        "script": component(
            "src/experiments/lock_closure_development_runtime_sequence_patch.py",
            "generating_script",
        ),
        "inputs": [
            {
                "path": base_lock["path"],
                "role": "base_development_runtime_patch_lock",
                "bytes": base_lock["bytes"],
                "sha256": base_lock["sha256"],
            },
            component(
                "configs/closure_v1/development_runtime_sequence_patch_lock.schema.json",
                "sequence_patch_lock_schema",
            ),
            component(
                "src/experiments/closure_development_runtime_sequence_patch.py",
                "sequence_patch_validator",
            ),
        ],
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "authoritative_contract": False,
        "authoritative_lock_path": DEFAULT_SEQUENCE_PATCH_LOCK_PATH.as_posix(),
    }


def _assert_p0_snapshot(expected: Mapping[str, Any]) -> None:
    if assert_p0_one_shot_outputs_absent() != expected:
        raise DevelopmentRuntimeSequencePatchError(
            "E0-DLS P0 one-shot namespace changed during locking"
        )


def _assert_guarded_publication_state(
    lock_path: Path,
    companion_path: Path,
    guards: Sequence[_OutputGuard],
    owners: Sequence[_OwnedFile],
) -> None:
    if len(guards) != 2 or not all(_guard_is_owned(guard) for guard in guards):
        raise DevelopmentRuntimeSequencePatchError(
            "E0-DLS output guards changed during locking"
        )
    owner_by_path = {owner.path: owner for owner in owners}
    if len(owner_by_path) != len(owners):
        raise DevelopmentRuntimeSequencePatchError(
            "E0-DLS published output ownership is ambiguous"
        )
    for path in (lock_path, companion_path):
        temporary = path.with_suffix(path.suffix + ".tmp")
        if os.path.lexists(temporary):
            raise DevelopmentRuntimeSequencePatchError(
                f"E0-DLS temporary output appeared during locking: {temporary}"
            )
        owner = owner_by_path.get(path)
        if owner is None:
            if os.path.lexists(path):
                raise DevelopmentRuntimeSequencePatchError(
                    f"Unowned E0-DLS final output appeared during locking: {path}"
                )
        elif not _is_owned(owner):
            raise DevelopmentRuntimeSequencePatchError(
                f"Owned E0-DLS final output drifted during locking: {path}"
            )


def execute_lock() -> dict[str, Any]:
    lock_path = _closed_output(
        DEFAULT_SEQUENCE_PATCH_LOCK_PATH,
        DEFAULT_SEQUENCE_PATCH_LOCK_PATH,
    )
    companion_path = _closed_output(
        DEFAULT_SEQUENCE_PATCH_MANIFEST_PATH,
        DEFAULT_SEQUENCE_PATCH_MANIFEST_PATH,
    )
    guards = _acquire_output_guards(lock_path, companion_path)
    created_outputs: list[_OwnedFile] = []
    lock_record: dict[str, Any] | None = None
    companion_record: dict[str, Any] | None = None
    lock_payload: dict[str, Any] | None = None
    try:
        _assert_guarded_publication_state(
            lock_path,
            companion_path,
            guards,
            created_outputs,
        )
        before = collect_sequence_patch_prelock_state(
            require_physical_artifacts=True,
            verify_remote=True,
        )
        verification = run_sequence_patch_verification()
        after = collect_sequence_patch_prelock_state(
            require_physical_artifacts=True,
            verify_remote=True,
        )
        if before != after:
            raise DevelopmentRuntimeSequencePatchError(
                "E0-DLS prelock state changed during verification"
            )
        _assert_p0_snapshot(after["p0_outputs"])
        _assert_guarded_publication_state(
            lock_path,
            companion_path,
            guards,
            created_outputs,
        )
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        lock_payload = build_sequence_patch_lock_payload(
            after,
            verification,
            created_at_utc=created_at,
        )
        schema_path = PROJECT_ROOT / DEFAULT_SEQUENCE_PATCH_LOCK_SCHEMA
        with schema_path.open(encoding="utf-8") as handle:
            schema = json.load(handle)
        if not isinstance(schema, Mapping):
            raise DevelopmentRuntimeSequencePatchError("E0-DLS schema must be an object")
        validate_development_runtime_sequence_patch_lock_payload(
            lock_payload,
            schema,
            require_physical_artifacts=True,
        )
        lock_bytes = _canonical_json(lock_payload)
        owned_lock = _publish_guarded_bytes(
            lock_bytes,
            lock_path,
            DEFAULT_SEQUENCE_PATCH_LOCK_PATH,
            guards[0],
        )
        created_outputs.append(owned_lock)
        lock_record = _owned_file_record(
            owned_lock,
            role="external_development_runtime_sequence_patch_lock",
        )
        _assert_p0_snapshot(after["p0_outputs"])
        _assert_guarded_publication_state(
            lock_path,
            companion_path,
            guards,
            created_outputs,
        )
        companion = _companion_payload(lock_payload, lock_record)
        companion_bytes = _canonical_json(companion)
        owned_companion = _publish_guarded_bytes(
            companion_bytes,
            companion_path,
            DEFAULT_SEQUENCE_PATCH_MANIFEST_PATH,
            guards[1],
        )
        created_outputs.append(owned_companion)
        companion_record = _owned_file_record(
            owned_companion,
            role="development_runtime_sequence_patch_companion",
        )
        _assert_p0_snapshot(after["p0_outputs"])
        _assert_guarded_publication_state(
            lock_path,
            companion_path,
            guards,
            created_outputs,
        )
        load_and_validate_development_runtime_sequence_patch_lock(
            require_published=False,
            require_physical_artifacts=True,
        )
        _assert_p0_snapshot(after["p0_outputs"])
        _assert_guarded_publication_state(
            lock_path,
            companion_path,
            guards,
            created_outputs,
        )
    except BaseException:
        for owner in reversed(created_outputs):
            _unlink_if_owned(owner)
        raise
    finally:
        try:
            for owner in reversed(created_outputs):
                _close_owned_directory(owner)
        finally:
            for guard in reversed(guards):
                _release_output_guard(guard)
    if lock_payload is None or lock_record is None or companion_record is None:
        raise DevelopmentRuntimeSequencePatchError(
            "E0-DLS publication completed without a closed result"
        )
    return {
        "status": "locked_unpublished",
        "gate": PATCH_GATE,
        "patch_head": lock_payload["patch_repository"]["head"],
        "lock": lock_record,
        "companion": companion_record,
        "development_fit_authorized": False,
        "publication_required": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check-only",
        action="store_true",
        help="Validate H-DLS and the one-shot namespace without running tests or writing outputs.",
    )
    mode.add_argument(
        "--execute-lock",
        action="store_true",
        help="Run the closed verification harness and create lock plus companion once.",
    )
    args = parser.parse_args()
    if args.check_only:
        lock_path = _closed_output(
            DEFAULT_SEQUENCE_PATCH_LOCK_PATH,
            DEFAULT_SEQUENCE_PATCH_LOCK_PATH,
        )
        companion_path = _closed_output(
            DEFAULT_SEQUENCE_PATCH_MANIFEST_PATH,
            DEFAULT_SEQUENCE_PATCH_MANIFEST_PATH,
        )
        _refuse_existing_outputs(lock_path, companion_path)
        state = collect_sequence_patch_prelock_state(
            require_physical_artifacts=True,
            verify_remote=True,
        )
        result = {
            "status": "ready_to_lock",
            "gate": PATCH_GATE,
            "patch_head": state["patch_repository"]["head"],
            "patch_path_count": state["patch_components"]["count"],
            "p0_one_shot_path_count": state["p0_outputs"]["count"],
            "outputs_written": False,
            "verification_commands_executed": False,
            "development_fit_authorized": False,
            "evaluation_authorized": False,
            "e0_u_authorized": False,
            "future_outcomes_accessed": False,
        }
    else:
        result = execute_lock()
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
