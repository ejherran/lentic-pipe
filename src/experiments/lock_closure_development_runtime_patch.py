#!/usr/bin/env python
"""Create the one-time additive Closure V1 E0-DLP lock bundle."""

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
from typing import Any, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments.closure_contract import load_json_mapping
from src.experiments.closure_development_runtime_lock import (
    DEFAULT_LOCK_PATH,
    DEFAULT_LOCK_SCHEMA,
    DEFAULT_RUNTIME_CONFIG,
    DEFAULT_RUNTIME_SCHEMA,
    command_evidence,
)
from src.experiments.closure_development_runtime_patch import (
    DEFAULT_PATCH_LOCK_MANIFEST_PATH,
    DEFAULT_PATCH_LOCK_PATH,
    DEFAULT_PATCH_LOCK_SCHEMA,
    PATCH_FOCUSED_TEST_COMMAND,
    PATCH_FOCUSED_TEST_COUNT,
    PATCH_GATE,
    PATCH_ID,
    PATCH_TEST_ENVIRONMENT,
    PATCH_TYPE_CHECK_COMMAND,
    DevelopmentRuntimePatchError,
    build_development_runtime_patch_lock_payload,
    collect_patch_prelock_state,
    patch_dvc_remote_push_command,
    validate_development_runtime_patch_lock_payload,
    verify_patch_dvc_remote_by_idempotent_push,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCKER_PATH = Path("src/experiments/lock_closure_development_runtime_patch.py")
PATCH_VALIDATOR_PATH = Path("src/experiments/closure_development_runtime_patch.py")
OUTPUT_GUARD_DIRECTORY = PROJECT_ROOT / "tmp" / "closure_v1_e0_dlp_locker"
OUTPUT_GUARD_NAMES = (
    "development_runtime_patch_lock.guard",
    "development_runtime_patch_lock_manifest.guard",
)
@dataclass(frozen=True)
class _OwnedPath:
    path: Path
    device: int
    inode: int
    directory_file_descriptor: int | None = None


@dataclass(frozen=True)
class _OutputGuard:
    owned: _OwnedPath
    file_descriptor: int
    directory_file_descriptor: int


def _resolve(path: Path) -> Path:
    candidate = path if path.is_absolute() else PROJECT_ROOT / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise DevelopmentRuntimePatchError(f"Path escapes repository: {path}") from exc
    return resolved


def _lexical_repository_path(path: Path) -> Path:
    candidate = path if path.is_absolute() else PROJECT_ROOT / path
    lexical = Path(os.path.abspath(candidate))
    try:
        lexical.relative_to(PROJECT_ROOT.resolve())
        lexical.parent.resolve(strict=True).relative_to(PROJECT_ROOT.resolve())
    except (FileNotFoundError, ValueError) as exc:
        raise DevelopmentRuntimePatchError(f"Path escapes repository: {path}") from exc
    return lexical


def _relative(path: Path) -> str:
    return _lexical_repository_path(path).relative_to(PROJECT_ROOT.resolve()).as_posix()


def _file_record(
    path: Path,
    *,
    role: str,
    expected_owner: _OwnedPath | None = None,
) -> dict[str, Any]:
    resolved = _lexical_repository_path(path)
    try:
        before = resolved.lstat()
    except FileNotFoundError as exc:
        raise DevelopmentRuntimePatchError(
            f"Required E0-DLP companion file is absent: {_relative(path)}"
        ) from exc
    if not stat.S_ISREG(before.st_mode):
        raise DevelopmentRuntimePatchError(
            f"Required E0-DLP companion path is not a regular file: {_relative(path)}"
        )
    if expected_owner is not None and (before.st_dev, before.st_ino) != (
        expected_owner.device,
        expected_owner.inode,
    ):
        raise DevelopmentRuntimePatchError(
            f"Required E0-DLP companion file ownership drifted: {_relative(path)}"
        )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(resolved, flags)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise DevelopmentRuntimePatchError(
                f"Required E0-DLP companion file changed before reading: {_relative(path)}"
            )
        digest = hashlib.sha256()
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
        content_sha256 = digest.hexdigest()
    finally:
        os.close(descriptor)
    after = resolved.lstat()
    if (before.st_dev, before.st_ino, before.st_size) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
    ):
        raise DevelopmentRuntimePatchError(
            f"Required E0-DLP companion file changed while reading: {_relative(path)}"
        )
    if expected_owner is not None and (after.st_dev, after.st_ino) != (
        expected_owner.device,
        expected_owner.inode,
    ):
        raise DevelopmentRuntimePatchError(
            f"Required E0-DLP companion file ownership drifted: {_relative(path)}"
        )
    return {
        "path": _relative(path),
        "role": role,
        "bytes": before.st_size,
        "sha256": content_sha256,
    }


def _temporary_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".tmp")


def _closed_output_path(path: Path, expected: Path) -> Path:
    candidate = path if path.is_absolute() else PROJECT_ROOT / path
    lexical = Path(os.path.abspath(candidate))
    required = PROJECT_ROOT.resolve() / expected
    if lexical != required:
        raise DevelopmentRuntimePatchError(
            f"E0-DLP lock output must use the closed default path: {expected.as_posix()}"
        )
    try:
        parent = lexical.parent.resolve(strict=True)
        parent.relative_to(PROJECT_ROOT.resolve())
    except (FileNotFoundError, ValueError) as exc:
        raise DevelopmentRuntimePatchError(
            f"E0-DLP output parent is unavailable or escapes the repository: {expected.as_posix()}"
        ) from exc
    if parent != required.parent.resolve(strict=True):
        raise DevelopmentRuntimePatchError(
            f"E0-DLP output parent is not the closed repository directory: {expected.as_posix()}"
        )
    return lexical


def _owned_path(path: Path, *, context: str) -> _OwnedPath:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise DevelopmentRuntimePatchError(f"{context} disappeared: {path}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise DevelopmentRuntimePatchError(f"{context} is not a regular file: {path}")
    return _OwnedPath(path=path, device=metadata.st_dev, inode=metadata.st_ino)


def _is_owned(owned: _OwnedPath) -> bool:
    if owned.directory_file_descriptor is not None:
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
            and (metadata.st_dev, metadata.st_ino)
            == (owned.device, owned.inode)
            and (lexical.st_dev, lexical.st_ino)
            == (owned.device, owned.inode)
        )
    try:
        metadata = owned.path.lstat()
    except FileNotFoundError:
        return False
    return (
        stat.S_ISREG(metadata.st_mode)
        and metadata.st_dev == owned.device
        and metadata.st_ino == owned.inode
    )


def _unlink_if_owned(owned: _OwnedPath) -> None:
    if owned.directory_file_descriptor is not None:
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
        return
    if _is_owned(owned):
        owned.path.unlink()


def _close_owned_directory(owned: _OwnedPath) -> None:
    if owned.directory_file_descriptor is not None:
        os.close(owned.directory_file_descriptor)


def _open_real_directory(path: Path, *, context: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise DevelopmentRuntimePatchError(
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
            raise DevelopmentRuntimePatchError(
                f"{context} directory identity drifted: {path}"
            )
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


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
        context="E0-DLP output-guard parent",
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
        raise DevelopmentRuntimePatchError(
            f"Refusing an existing E0-DLP temporary/guard path: {path.relative_to(PROJECT_ROOT)}"
        ) from exc
    except BaseException:
        os.close(directory_descriptor)
        raise
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise DevelopmentRuntimePatchError(
                f"E0-DLP output guard is not a regular file: {path.relative_to(PROJECT_ROOT)}"
            )
        return _OutputGuard(
            owned=_OwnedPath(path=path, device=metadata.st_dev, inode=metadata.st_ino),
            file_descriptor=descriptor,
            directory_file_descriptor=directory_descriptor,
        )
    except BaseException:
        os.close(descriptor)
        os.close(directory_descriptor)
        raise


def _output_guard_paths(
    output: Path,
    manifest_output: Path,
    *,
    create_directory: bool,
) -> tuple[Path, Path]:
    resolved_output = _closed_output_path(output, DEFAULT_PATCH_LOCK_PATH)
    resolved_manifest = _closed_output_path(
        manifest_output,
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
    )
    tmp_root = PROJECT_ROOT / "tmp"
    if OUTPUT_GUARD_DIRECTORY.parent != tmp_root:
        raise DevelopmentRuntimePatchError(
            "E0-DLP coordination directory escaped the ignored tmp/ root"
        )
    repository_descriptor = _open_real_directory(
        PROJECT_ROOT,
        context="E0-DLP repository root",
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
            raise DevelopmentRuntimePatchError(
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
            raise DevelopmentRuntimePatchError(
                "E0-DLP coordination path must be a real directory"
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
                    resolved_manifest.parent.stat().st_dev,
                )
            )
        ):
            raise DevelopmentRuntimePatchError(
                "E0-DLP output guards and final outputs must share one stable filesystem"
            )
    except OSError as exc:
        raise DevelopmentRuntimePatchError(
            "E0-DLP coordination directory could not be created or opened safely"
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


def _release_output_guard(guard: _OutputGuard) -> None:
    anchored = _OwnedPath(
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


def _acquire_output_guards(output: Path, manifest_output: Path) -> tuple[_OutputGuard, ...]:
    _refuse_existing_outputs(output, manifest_output)
    guard_paths = _output_guard_paths(
        output,
        manifest_output,
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


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            dict(payload),
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _publish_guarded_json(
    payload: Mapping[str, Any],
    path: Path,
    guard: _OutputGuard,
) -> _OwnedPath:
    resolved = (
        _closed_output_path(path, DEFAULT_PATCH_LOCK_PATH)
        if _relative(path) == DEFAULT_PATCH_LOCK_PATH.as_posix()
        else _closed_output_path(path, DEFAULT_PATCH_LOCK_MANIFEST_PATH)
    )
    if not _guard_is_owned(guard):
        raise DevelopmentRuntimePatchError("E0-DLP output guard changed before publication")
    encoded = _json_bytes(payload)
    os.ftruncate(guard.file_descriptor, 0)
    os.lseek(guard.file_descriptor, 0, os.SEEK_SET)
    offset = 0
    while offset < len(encoded):
        offset += os.write(guard.file_descriptor, encoded[offset:])
    os.fsync(guard.file_descriptor)
    if not _guard_is_owned(guard):
        raise DevelopmentRuntimePatchError("E0-DLP output guard changed while writing")
    destination_directory = _open_real_directory(
        resolved.parent,
        context="E0-DLP final-output parent",
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
        raise DevelopmentRuntimePatchError(
            f"Refusing to overwrite an E0-DLP output created during checks: {_relative(path)}"
        ) from exc
    except BaseException:
        os.close(destination_directory)
        raise
    published = _OwnedPath(
        path=resolved,
        device=guard.owned.device,
        inode=guard.owned.inode,
        directory_file_descriptor=destination_directory,
    )
    try:
        metadata = os.stat(
            resolved.name,
            dir_fd=destination_directory,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(metadata.st_mode)
            or (metadata.st_dev, metadata.st_ino)
            != (guard.owned.device, guard.owned.inode)
        ):
            raise DevelopmentRuntimePatchError(
                "E0-DLP no-clobber publication identity drifted"
            )
        if not _is_owned(published):
            raise DevelopmentRuntimePatchError(
                "E0-DLP final-output parent changed during publication"
            )
        return published
    except BaseException:
        _unlink_if_owned(published)
        os.close(destination_directory)
        raise


def _focused_test_evidence(command: tuple[str, ...]) -> dict[str, Any]:
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith("PYTEST_") or key == "PY_COLORS":
            environment.pop(key)
    environment.update(PATCH_TEST_ENVIRONMENT)
    try:
        result = subprocess.run(
            list(command),
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=False,
            timeout=3600,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DevelopmentRuntimePatchError(
            "E0-DLP focal verification could not complete within its fixed bound"
        ) from exc
    combined = (result.stdout + b"\n" + result.stderr).decode(
        "utf-8", errors="replace"
    )
    summaries = re.findall(r"(?m)^([1-9][0-9]*) passed in [0-9]+(?:\.[0-9]+)?s$", combined)
    if result.returncode != 0 or summaries != [str(PATCH_FOCUSED_TEST_COUNT)]:
        raise DevelopmentRuntimePatchError(
            "E0-DLP focal verification did not execute the exact no-skip test count: "
            f"exit_code={result.returncode}, summaries={summaries}, "
            f"stdout_sha256={hashlib.sha256(result.stdout).hexdigest()}, "
            f"stderr_sha256={hashlib.sha256(result.stderr).hexdigest()}"
        )
    return {
        "command": list(command),
        "environment": dict(PATCH_TEST_ENVIRONMENT),
        "test_count": PATCH_FOCUSED_TEST_COUNT,
        "exit_code": 0,
        "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
        "passed": True,
    }


def _require_fixed_verification_executable(command: tuple[str, ...]) -> None:
    if not command or not command[0].startswith(".venv/bin/"):
        raise DevelopmentRuntimePatchError(
            "E0-DLP verification command must use a fixed repository executable"
        )
    executable = _lexical_repository_path(Path(command[0]))
    try:
        metadata = executable.lstat()
    except FileNotFoundError as exc:
        raise DevelopmentRuntimePatchError(
            f"E0-DLP verification executable is absent: {command[0]}"
        ) from exc
    if not stat.S_ISREG(metadata.st_mode) or not os.access(executable, os.X_OK):
        raise DevelopmentRuntimePatchError(
            f"E0-DLP verification executable is not a regular executable: {command[0]}"
        )


def _require_default_outputs(output: Path, manifest_output: Path) -> None:
    _closed_output_path(output, DEFAULT_PATCH_LOCK_PATH)
    _closed_output_path(manifest_output, DEFAULT_PATCH_LOCK_MANIFEST_PATH)


def _require_default_inputs(
    *,
    base_lock_path: Path,
    base_lock_schema: Path,
    runtime_config: Path,
    runtime_schema: Path,
    patch_lock_schema: Path,
) -> None:
    pairs = (
        (_relative(base_lock_path), DEFAULT_LOCK_PATH.as_posix()),
        (_relative(base_lock_schema), DEFAULT_LOCK_SCHEMA.as_posix()),
        (_relative(runtime_config), DEFAULT_RUNTIME_CONFIG.as_posix()),
        (_relative(runtime_schema), DEFAULT_RUNTIME_SCHEMA.as_posix()),
        (_relative(patch_lock_schema), DEFAULT_PATCH_LOCK_SCHEMA.as_posix()),
    )
    drifted = [
        {"observed": observed, "required": required}
        for observed, required in pairs
        if observed != required
    ]
    if drifted:
        raise DevelopmentRuntimePatchError(
            f"E0-DLP locker inputs must use the closed default paths: {drifted}"
        )


def _refuse_existing_outputs(output: Path, manifest_output: Path) -> None:
    resolved_output = _closed_output_path(output, DEFAULT_PATCH_LOCK_PATH)
    resolved_manifest = _closed_output_path(
        manifest_output,
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
    )
    guard_paths = _output_guard_paths(
        output,
        manifest_output,
        create_directory=False,
    )
    candidates = (
        resolved_output,
        _temporary_path(resolved_output),
        resolved_manifest,
        _temporary_path(resolved_manifest),
        *guard_paths,
    )
    existing = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in candidates
        if os.path.lexists(path)
    ]
    if existing:
        raise DevelopmentRuntimePatchError(
            f"Refusing to overwrite an existing E0-DLP lock bundle: {existing}"
        )


def _companion_manifest(
    *, output: Path, output_owner: _OwnedPath, created_at_utc: str
) -> dict[str, Any]:
    if not _is_owned(output_owner):
        raise DevelopmentRuntimePatchError(
            "Authoritative E0-DLP output changed before companion construction"
        )
    return {
        "manifest_version": "closure_development_runtime_patch_companion_manifest_v1",
        "status": "completed",
        "experiment_id": "closure_v1",
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": created_at_utc,
        "outputs": [
            _file_record(
                output,
                role="external_development_runtime_patch_lock",
                expected_owner=output_owner,
            )
        ],
        "script": _file_record(LOCKER_PATH, role="generating_script"),
        "inputs": [
            _file_record(DEFAULT_LOCK_PATH, role="base_development_runtime_lock"),
            _file_record(
                DEFAULT_LOCK_SCHEMA,
                role="base_development_runtime_lock_schema",
            ),
            _file_record(
                DEFAULT_PATCH_LOCK_SCHEMA,
                role="development_runtime_patch_lock_schema",
            ),
            _file_record(
                PATCH_VALIDATOR_PATH,
                role="development_runtime_patch_validator",
            ),
        ],
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "authoritative_contract": False,
        "authoritative_lock_path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
    }


def _summary(prelock: Mapping[str, Any]) -> dict[str, Any]:
    runtime = prelock["runtime"]
    bundle = prelock["adopted_seed_bundle"]
    publication_sequence = prelock["publication_sequence"]
    return {
        "status": "ready_to_lock",
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "patch_parent": prelock["patch_repository"]["head"],
        "adoption_head": publication_sequence["adoption_head"],
        "base_component_drift_count": prelock["base_component_drift"]["count"],
        "patch_component_count": prelock["patch_components"]["count"],
        "adopted_seed": bundle["base_seed"],
        "type_check_command": list(PATCH_TYPE_CHECK_COMMAND),
        "focused_test_command": list(PATCH_FOCUSED_TEST_COMMAND),
        "dvc_remote_verification_command": list(
            patch_dvc_remote_push_command(runtime, bundle)
        ),
        "outputs_written": [],
        "development_fit_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }


def create_development_runtime_patch_lock(
    *,
    base_lock_path: Path,
    base_lock_schema: Path,
    runtime_config: Path,
    runtime_schema: Path,
    patch_lock_schema: Path,
    output: Path,
    manifest_output: Path,
    device: str,
    verify_dvc_remote_by_idempotent_push_flag: bool,
) -> tuple[Path, Path]:
    """Run fixed checks and atomically create the authoritative lock plus companion."""
    _require_default_outputs(output, manifest_output)
    _require_default_inputs(
        base_lock_path=base_lock_path,
        base_lock_schema=base_lock_schema,
        runtime_config=runtime_config,
        runtime_schema=runtime_schema,
        patch_lock_schema=patch_lock_schema,
    )
    if device != "cpu":
        raise DevelopmentRuntimePatchError("E0-DLP is locked to CPU")
    if not verify_dvc_remote_by_idempotent_push_flag:
        raise DevelopmentRuntimePatchError(
            "--execute-lock requires --verify-dvc-remote-by-idempotent-push"
        )

    guards = _acquire_output_guards(output, manifest_output)
    created_outputs: list[_OwnedPath] = []
    try:
        before = collect_patch_prelock_state(
            base_lock_path=base_lock_path,
            base_lock_schema=base_lock_schema,
            runtime_config=runtime_config,
            runtime_schema=runtime_schema,
            device=device,
            verify_parent_remote_publication=True,
        )
        _require_fixed_verification_executable(PATCH_TYPE_CHECK_COMMAND)
        _require_fixed_verification_executable(PATCH_FOCUSED_TEST_COMMAND)
        type_check = command_evidence(PATCH_TYPE_CHECK_COMMAND)
        focused_tests = _focused_test_evidence(PATCH_FOCUSED_TEST_COMMAND)
        dvc_remote = verify_patch_dvc_remote_by_idempotent_push(
            before["runtime"], before["adopted_seed_bundle"]
        )
        after = collect_patch_prelock_state(
            base_lock_path=base_lock_path,
            base_lock_schema=base_lock_schema,
            runtime_config=runtime_config,
            runtime_schema=runtime_schema,
            device=device,
            verify_parent_remote_publication=True,
        )
        if before != after:
            raise DevelopmentRuntimePatchError(
                "Repository, adopted seed, environment, or DVC ownership changed during E0-DLP checks"
            )

        created_at_utc = datetime.now(timezone.utc).isoformat()
        payload = build_development_runtime_patch_lock_payload(
            after,
            full_type_check=type_check,
            focused_tests=focused_tests,
            dvc_remote_verification=dvc_remote,
            created_at_utc=created_at_utc,
        )
        schema = load_json_mapping(patch_lock_schema)
        validate_development_runtime_patch_lock_payload(payload, schema)
        lock_owner = _publish_guarded_json(payload, output, guards[0])
        created_outputs.append(lock_owner)
        companion = _companion_manifest(
            output=output,
            output_owner=lock_owner,
            created_at_utc=created_at_utc,
        )
        companion_owner = _publish_guarded_json(
            companion,
            manifest_output,
            guards[1],
        )
        created_outputs.append(companion_owner)
        if not all(_is_owned(owner) for owner in created_outputs):
            raise DevelopmentRuntimePatchError(
                "E0-DLP lock bundle changed before one-shot publication completed"
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
    return output, manifest_output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-lock", type=Path, default=DEFAULT_LOCK_PATH)
    parser.add_argument("--base-lock-schema", type=Path, default=DEFAULT_LOCK_SCHEMA)
    parser.add_argument("--runtime-config", type=Path, default=DEFAULT_RUNTIME_CONFIG)
    parser.add_argument("--runtime-schema", type=Path, default=DEFAULT_RUNTIME_SCHEMA)
    parser.add_argument(
        "--patch-lock-schema", type=Path, default=DEFAULT_PATCH_LOCK_SCHEMA
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_PATCH_LOCK_PATH)
    parser.add_argument(
        "--manifest-output", type=Path, default=DEFAULT_PATCH_LOCK_MANIFEST_PATH
    )
    parser.add_argument("--device", required=True, choices=("cpu",))
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--check-only",
        action="store_true",
        help="Validate outcome-free preconditions and print commands without running or writing them.",
    )
    action.add_argument(
        "--execute-lock",
        action="store_true",
        help="Run the fixed checks and create the one-time E0-DLP lock bundle.",
    )
    parser.add_argument(
        "--verify-dvc-remote-by-idempotent-push",
        action="store_true",
        help="Required with --execute-lock; require two exact already-up-to-date pushes.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    _require_default_outputs(args.output, args.manifest_output)
    _require_default_inputs(
        base_lock_path=args.base_lock,
        base_lock_schema=args.base_lock_schema,
        runtime_config=args.runtime_config,
        runtime_schema=args.runtime_schema,
        patch_lock_schema=args.patch_lock_schema,
    )
    if args.check_only:
        if args.verify_dvc_remote_by_idempotent_push:
            raise DevelopmentRuntimePatchError(
                "--check-only cannot run DVC remote verification"
            )
        _refuse_existing_outputs(args.output, args.manifest_output)
        prelock = collect_patch_prelock_state(
            base_lock_path=args.base_lock,
            base_lock_schema=args.base_lock_schema,
            runtime_config=args.runtime_config,
            runtime_schema=args.runtime_schema,
            device=args.device,
            verify_parent_remote_publication=False,
        )
        print(json.dumps(_summary(prelock), indent=2, sort_keys=True))
        return
    output, companion = create_development_runtime_patch_lock(
        base_lock_path=args.base_lock,
        base_lock_schema=args.base_lock_schema,
        runtime_config=args.runtime_config,
        runtime_schema=args.runtime_schema,
        patch_lock_schema=args.patch_lock_schema,
        output=args.output,
        manifest_output=args.manifest_output,
        device=args.device,
        verify_dvc_remote_by_idempotent_push_flag=(
            args.verify_dvc_remote_by_idempotent_push
        ),
    )
    print(
        "Wrote locked development runtime patch bundle: "
        f"{output.as_posix()}, {companion.as_posix()}"
    )


if __name__ == "__main__":
    main()
