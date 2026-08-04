#!/usr/bin/env python
"""Create the one-time additive Closure V1 E0-DLT lock bundle."""

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

from src.experiments.closure_development_runtime_temporal_consumer_patch import (
    DEFAULT_PATCH_LOCK_PATH,
    DEFAULT_PATCH_LOCK_SCHEMA,
    DEFAULT_PATCH_MANIFEST_PATH,
    DIFF_CHECK_COMMAND,
    DVC_PUSH_COMMAND,
    FOCUSED_TEST_COMMAND,
    FOCUSED_TEST_COUNT,
    POETRY_CHECK_COMMAND,
    PUBLICATION_GUARD_COMMAND,
    TYPE_CHECK_COMMAND,
    DevelopmentRuntimeTemporalConsumerPatchError,
    _expected_companion,
    _load_regular_json,
    build_temporal_consumer_patch_lock_payload,
    collect_temporal_consumer_patch_prelock_state,
    consumer_namespace_absence,
    load_and_validate_development_runtime_temporal_consumer_patch_lock,
    validate_development_runtime_temporal_consumer_patch_lock_payload,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_GUARD_DIRECTORY = PROJECT_ROOT / "tmp" / "closure_v1_e0_dlt_locker"
OUTPUT_GUARD_NAMES = (
    "development_runtime_temporal_consumer_patch_lock.guard",
    "development_runtime_temporal_consumer_patch_lock_manifest.guard",
)
FORBIDDEN_PYTEST_SUMMARY_RE = re.compile(
    r"\b(?:warnings?|skipped|deselected|xfailed|xpassed|errors?|failed)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class _OwnedFile:
    path: Path
    device: int
    inode: int
    directory_file_descriptor: int


@dataclass(frozen=True)
class _OutputGuard:
    path: Path
    device: int
    inode: int
    file_descriptor: int
    directory_file_descriptor: int


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _line_count(payload: str) -> int:
    return len(payload.splitlines())


def _command_evidence(
    command: Sequence[str],
    result: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    return {
        "command": list(command),
        "returncode": result.returncode,
        "stdout_sha256": _sha256(result.stdout.encode("utf-8")),
        "stderr_sha256": _sha256(result.stderr.encode("utf-8")),
        "stdout_line_count": _line_count(result.stdout),
        "stderr_line_count": _line_count(result.stderr),
    }


def _run_command(
    command: Sequence[str],
    *,
    environment: Mapping[str, str] | None = None,
    sanitize_pytest_environment: bool = False,
) -> tuple[dict[str, Any], str, str]:
    env = os.environ.copy()
    for key in (
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "PYTHONINSPECT",
        "PYTHONUSERBASE",
        "PYTHONWARNINGS",
        "VIRTUAL_ENV",
        "POETRY_ACTIVE",
    ):
        env.pop(key, None)
    env["PYTHONNOUSERSITE"] = "1"
    env["DVC_BIN"] = str(PROJECT_ROOT / ".venv/bin/dvc")
    env["PATH"] = os.pathsep.join(
        (
            str(PROJECT_ROOT / ".venv/bin"),
            str(Path.home() / ".local/bin"),
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
        )
    )
    if sanitize_pytest_environment:
        for key in tuple(env):
            if key.startswith("PYTEST_") or key == "PY_COLORS":
                env.pop(key)
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    if environment is not None:
        if dict(environment) != {"DVC_NO_ANALYTICS": "1"}:
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                "E0-DLT command environment override escaped the closed DVC policy"
            )
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
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"E0-DLT verification timed out: {' '.join(command)}"
        ) from exc
    if result.returncode != 0:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"E0-DLT verification failed: {' '.join(command)}"
        )
    return _command_evidence(command, result), result.stdout, result.stderr


def _require_fixed_venv_executable(command: Sequence[str]) -> None:
    if not command or Path(command[0]).parent != Path(".venv/bin"):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT fixed Python verification escaped .venv/bin"
        )
    executable = Path(command[0])
    try:
        directory_descriptor = _open_repo_directory(
            executable.parent,
            context="E0-DLT fixed verification executable parent",
        )
    except DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"E0-DLT verification executable is absent: {command[0]}"
        ) from exc
    try:
        metadata = os.stat(
            executable.name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        executable_ok = stat.S_ISREG(metadata.st_mode) and os.access(
            executable.name,
            os.X_OK,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"E0-DLT verification executable is absent: {command[0]}"
        ) from exc
    finally:
        os.close(directory_descriptor)
    if not executable_ok:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"E0-DLT verification executable is unsafe: {command[0]}"
        )


def _parse_focused_summary(stdout: str, stderr: str) -> int:
    combined = stdout + "\n" + stderr
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    summary_re = re.compile(
        rf"^{FOCUSED_TEST_COUNT} passed in [0-9]+(?:\.[0-9]+)?s$"
    )
    matches = [line for line in lines if summary_re.fullmatch(line)]
    if (
        not lines
        or matches != [lines[-1]]
        or FORBIDDEN_PYTEST_SUMMARY_RE.search(combined) is not None
    ):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT focused pytest summary is not one exact clean result"
        )
    return FOCUSED_TEST_COUNT


def _require_success_marker(stdout: str, stderr: str, marker: str) -> None:
    if marker not in stdout + "\n" + stderr:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"E0-DLT verification marker is absent: {marker}"
        )


def _require_empty_output(stdout: str, stderr: str, *, context: str) -> None:
    if stdout.strip() or stderr.strip():
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"E0-DLT expected empty output from {context}"
        )


def _terminal_status(stdout: str, stderr: str) -> str:
    lines = [
        line.strip()
        for line in (stdout + "\n" + stderr).splitlines()
        if line.strip()
    ]
    marker = "Everything is up to date."
    if lines.count(marker) != 1 or any(
        re.fullmatch(r"[1-9][0-9]* files? pushed", line) for line in lines
    ):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT targeted DVC push is not exactly idempotent"
        )
    return marker


def run_temporal_consumer_patch_verification() -> dict[str, Any]:
    """Run the closed H-DLT verification set; this is intentionally heavy."""
    _require_fixed_venv_executable(TYPE_CHECK_COMMAND)
    _require_fixed_venv_executable(FOCUSED_TEST_COMMAND)

    type_check, stdout, stderr = _run_command(TYPE_CHECK_COMMAND)
    _require_success_marker(stdout, stderr, "All checks passed!")

    focused, stdout, stderr = _run_command(
        FOCUSED_TEST_COMMAND,
        sanitize_pytest_environment=True,
    )
    focused.update(
        {
            "test_count": _parse_focused_summary(stdout, stderr),
            "skipped_count": 0,
            "deselected_count": 0,
        }
    )

    poetry_check, stdout, stderr = _run_command(POETRY_CHECK_COMMAND)
    _require_success_marker(stdout, stderr, "All set!")

    publication_guard, _, _ = _run_command(PUBLICATION_GUARD_COMMAND)
    diff_check, stdout, stderr = _run_command(DIFF_CHECK_COMMAND)
    _require_empty_output(stdout, stderr, context="git diff --check")

    dvc_environment = {"DVC_NO_ANALYTICS": "1"}
    dvc_first, stdout, stderr = _run_command(
        DVC_PUSH_COMMAND,
        environment=dvc_environment,
    )
    dvc_first["terminal_status"] = _terminal_status(stdout, stderr)
    dvc_second, stdout, stderr = _run_command(
        DVC_PUSH_COMMAND,
        environment=dvc_environment,
    )
    dvc_second["terminal_status"] = _terminal_status(stdout, stderr)

    return {
        "full_type_check": type_check,
        "focused_tests": focused,
        "poetry_check": poetry_check,
        "publication_guard": publication_guard,
        "git_diff_check": diff_check,
        "dvc_push_first": dvc_first,
        "dvc_push_second": dvc_second,
    }


def _closed_output(path: Path, expected: Path) -> Path:
    candidate = path if path.is_absolute() else PROJECT_ROOT / path
    lexical = Path(os.path.abspath(candidate))
    required = PROJECT_ROOT.resolve() / expected
    if lexical != required:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"E0-DLT output must use the closed path: {expected.as_posix()}"
        )
    parent_descriptor = _open_repo_directory(
        expected.parent,
        context="E0-DLT output parent",
    )
    os.close(parent_descriptor)
    return lexical


def _open_real_directory(path: Path, *, context: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
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
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"{context} directory identity drifted: {path}"
            )
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_repo_directory(relative: Path, *, context: str) -> int:
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"{context} escaped the repository root"
        )
    descriptor = _open_real_directory(
        PROJECT_ROOT.resolve(),
        context="E0-DLT repository root",
    )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        for component in relative.parts:
            try:
                child = os.open(component, flags, dir_fd=descriptor)
            except OSError as exc:
                raise DevelopmentRuntimeTemporalConsumerPatchError(
                    f"{context} contains an unavailable or linked ancestor"
                ) from exc
            try:
                metadata = os.fstat(child)
                if not stat.S_ISDIR(metadata.st_mode):
                    raise DevelopmentRuntimeTemporalConsumerPatchError(
                        f"{context} contains a non-directory ancestor"
                    )
            except BaseException:
                os.close(child)
                raise
            parent_descriptor = descriptor
            descriptor = child
            os.close(parent_descriptor)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _ensure_real_directory(path: Path, *, parent: Path, context: str) -> None:
    parent_descriptor = _open_real_directory(parent, context=f"{context} parent")
    try:
        try:
            os.mkdir(path.name, mode=0o700, dir_fd=parent_descriptor)
        except FileExistsError:
            pass
        metadata = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
        if not stat.S_ISDIR(metadata.st_mode):
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"{context} is not a real directory: {path}"
            )
    except OSError as exc:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"{context} could not be created safely: {path}"
        ) from exc
    finally:
        os.close(parent_descriptor)


def _guard_paths(*, create_directory: bool) -> tuple[Path, Path]:
    tmp_root = PROJECT_ROOT / "tmp"
    if OUTPUT_GUARD_DIRECTORY != tmp_root / "closure_v1_e0_dlt_locker":
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT coordination directory escaped ignored tmp/"
        )
    if create_directory:
        _ensure_real_directory(tmp_root, parent=PROJECT_ROOT, context="E0-DLT tmp root")
        _ensure_real_directory(
            OUTPUT_GUARD_DIRECTORY,
            parent=tmp_root,
            context="E0-DLT guard directory",
        )
    return (
        OUTPUT_GUARD_DIRECTORY / OUTPUT_GUARD_NAMES[0],
        OUTPUT_GUARD_DIRECTORY / OUTPUT_GUARD_NAMES[1],
    )


def _guard_is_owned(guard: _OutputGuard) -> bool:
    try:
        opened = os.fstat(guard.file_descriptor)
        observed = os.stat(
            guard.path.name,
            dir_fd=guard.directory_file_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT guard ownership could not be inspected safely"
        ) from exc
    return (
        stat.S_ISREG(opened.st_mode)
        and stat.S_ISREG(observed.st_mode)
        and (opened.st_dev, opened.st_ino) == (guard.device, guard.inode)
        and (observed.st_dev, observed.st_ino) == (guard.device, guard.inode)
    )


def _open_guard(path: Path) -> _OutputGuard:
    try:
        relative_parent = path.parent.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT guard parent escaped the repository"
        ) from exc
    directory_descriptor = _open_repo_directory(
        relative_parent,
        context="E0-DLT guard parent",
    )
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path.name, flags, 0o600, dir_fd=directory_descriptor)
    except FileExistsError as exc:
        os.close(directory_descriptor)
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"Refusing an existing E0-DLT guard: {path}"
        ) from exc
    except BaseException:
        os.close(directory_descriptor)
        raise
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"E0-DLT guard is not a regular file: {path}"
            )
        return _OutputGuard(
            path=path,
            device=metadata.st_dev,
            inode=metadata.st_ino,
            file_descriptor=descriptor,
            directory_file_descriptor=directory_descriptor,
        )
    except BaseException:
        os.close(descriptor)
        os.close(directory_descriptor)
        raise


def _release_guard(guard: _OutputGuard) -> None:
    errors: list[Exception] = []
    try:
        owned = _guard_is_owned(guard)
    except (DevelopmentRuntimeTemporalConsumerPatchError, OSError) as exc:
        errors.append(exc)
        owned = False
    if owned:
        try:
            os.unlink(guard.path.name, dir_fd=guard.directory_file_descriptor)
            os.fsync(guard.directory_file_descriptor)
        except OSError as exc:
            errors.append(exc)
    for descriptor in (guard.file_descriptor, guard.directory_file_descriptor):
        try:
            os.close(descriptor)
        except OSError as exc:
            errors.append(exc)
    if errors:
        cleanup_error = DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT guard release could not be completed safely"
        )
        cleanup_error.add_note(
            "Guard release failures: "
            + "; ".join(f"{type(error).__name__}: {error}" for error in errors)
        )
        raise cleanup_error from errors[0]


def _refuse_existing_outputs(output: Path, companion: Path) -> None:
    lock_path = _closed_output(output, DEFAULT_PATCH_LOCK_PATH)
    companion_path = _closed_output(companion, DEFAULT_PATCH_MANIFEST_PATH)
    guards = _guard_paths(create_directory=False)
    candidates = (
        lock_path,
        lock_path.with_suffix(lock_path.suffix + ".tmp"),
        companion_path,
        companion_path.with_suffix(companion_path.suffix + ".tmp"),
        *guards,
    )
    existing = [str(path) for path in candidates if os.path.lexists(path)]
    if existing:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"Refusing to overwrite an existing E0-DLT lock bundle: {existing}"
        )


def _acquire_guards(output: Path, companion: Path) -> tuple[_OutputGuard, ...]:
    _refuse_existing_outputs(output, companion)
    guard_paths = _guard_paths(create_directory=True)
    guards: list[_OutputGuard] = []
    try:
        for path in guard_paths:
            guards.append(_open_guard(path))
    except BaseException:
        for guard in reversed(guards):
            _release_guard(guard)
        raise
    return tuple(guards)


def _owned(owned: _OwnedFile) -> bool:
    try:
        relative = owned.path.relative_to(PROJECT_ROOT.resolve())
        current_directory_descriptor = _open_repo_directory(
            relative.parent,
            context="E0-DLT owned-output parent",
        )
    except (DevelopmentRuntimeTemporalConsumerPatchError, ValueError):
        return False
    try:
        anchored_directory = os.fstat(owned.directory_file_descriptor)
        current_directory = os.fstat(current_directory_descriptor)
        observed = os.stat(
            owned.path.name,
            dir_fd=owned.directory_file_descriptor,
            follow_symlinks=False,
        )
        current = os.stat(
            owned.path.name,
            dir_fd=current_directory_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT output ownership could not be inspected safely"
        ) from exc
    finally:
        os.close(current_directory_descriptor)
    return (
        stat.S_ISDIR(anchored_directory.st_mode)
        and stat.S_ISDIR(current_directory.st_mode)
        and (anchored_directory.st_dev, anchored_directory.st_ino)
        == (current_directory.st_dev, current_directory.st_ino)
        and stat.S_ISREG(observed.st_mode)
        and stat.S_ISREG(current.st_mode)
        and (observed.st_dev, observed.st_ino) == (owned.device, owned.inode)
        and (current.st_dev, current.st_ino) == (owned.device, owned.inode)
    )


def _unlink_if_owned(owned: _OwnedFile) -> None:
    if _owned(owned):
        os.unlink(owned.path.name, dir_fd=owned.directory_file_descriptor)


def _publish_guarded_bytes(
    payload: bytes,
    destination: Path,
    expected: Path,
    guard: _OutputGuard,
) -> _OwnedFile:
    final = _closed_output(destination, expected)
    if not _guard_is_owned(guard):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT output guard changed before publication"
        )
    os.ftruncate(guard.file_descriptor, 0)
    os.lseek(guard.file_descriptor, 0, os.SEEK_SET)
    offset = 0
    while offset < len(payload):
        written = os.write(guard.file_descriptor, payload[offset:])
        if written <= 0:
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                "Short write while preparing an E0-DLT output"
            )
        offset += written
    os.fsync(guard.file_descriptor)
    if not _guard_is_owned(guard):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT output guard changed while writing"
        )
    destination_descriptor = _open_repo_directory(
        expected.parent,
        context="E0-DLT final-output parent",
    )
    try:
        os.link(
            guard.path.name,
            final.name,
            src_dir_fd=guard.directory_file_descriptor,
            dst_dir_fd=destination_descriptor,
            follow_symlinks=False,
        )
    except FileExistsError as exc:
        os.close(destination_descriptor)
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            f"Refusing to clobber an E0-DLT output: {destination}"
        ) from exc
    except BaseException:
        os.close(destination_descriptor)
        raise
    owned = _OwnedFile(
        path=final,
        device=guard.device,
        inode=guard.inode,
        directory_file_descriptor=destination_descriptor,
    )
    try:
        os.fsync(destination_descriptor)
        if not _owned(owned):
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                "E0-DLT published output identity drifted"
            )
        return owned
    except BaseException as error:
        cleanup_errors: list[Exception] = []
        try:
            _unlink_if_owned(owned)
        except (DevelopmentRuntimeTemporalConsumerPatchError, OSError) as exc:
            cleanup_errors.append(exc)
        try:
            os.fsync(destination_descriptor)
        except OSError as exc:
            cleanup_errors.append(exc)
        try:
            os.close(destination_descriptor)
        except OSError as exc:
            cleanup_errors.append(exc)
        if cleanup_errors:
            cleanup_error = DevelopmentRuntimeTemporalConsumerPatchError(
                "E0-DLT output rollback could not be completed safely"
            )
            cleanup_error.add_note(
                "Output rollback failures: "
                + "; ".join(
                    f"{type(exc).__name__}: {exc}" for exc in cleanup_errors
                )
            )
            raise cleanup_error from error
        raise


def _owned_file_record(owned: _OwnedFile, *, role: str) -> dict[str, Any]:
    if not _owned(owned):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT output changed before hashing"
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
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                "E0-DLT output changed while opening for hashing"
            )
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    finally:
        os.close(descriptor)
    if not _owned(owned):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT output changed while hashing"
        )
    return {
        "path": owned.path.relative_to(PROJECT_ROOT.resolve()).as_posix(),
        "role": role,
        "bytes": size,
        "sha256": digest.hexdigest(),
    }


def _assert_lock_namespace(
    output: Path,
    companion: Path,
    guards: Sequence[_OutputGuard],
    owners: Sequence[_OwnedFile],
) -> None:
    if len(guards) != 2 or not all(_guard_is_owned(guard) for guard in guards):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT output guards changed during locking"
        )
    owner_by_path = {owner.path: owner for owner in owners}
    if len(owner_by_path) != len(owners):
        raise DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT output ownership is ambiguous"
        )
    for path in (output, companion):
        if os.path.lexists(path.with_suffix(path.suffix + ".tmp")):
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"E0-DLT temporary output appeared during locking: {path}"
            )
        owner = owner_by_path.get(path)
        if owner is None and os.path.lexists(path):
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"Unowned E0-DLT final appeared during locking: {path}"
            )
        if owner is not None and not _owned(owner):
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                f"Owned E0-DLT final changed during locking: {path}"
            )


def _cleanup_lock_resources(
    owners: Sequence[_OwnedFile],
    guards: Sequence[_OutputGuard],
    *,
    succeeded: bool,
    active_error: BaseException | None,
) -> None:
    rollback_errors: list[Exception] = []

    def rollback_outputs() -> None:
        for owner in reversed(owners):
            try:
                _unlink_if_owned(owner)
            except (DevelopmentRuntimeTemporalConsumerPatchError, OSError) as exc:
                rollback_errors.append(exc)
            try:
                os.fsync(owner.directory_file_descriptor)
            except OSError as exc:
                rollback_errors.append(exc)

    if not succeeded:
        rollback_outputs()
    guard_errors_before = len(rollback_errors)
    for guard in reversed(guards):
        try:
            _release_guard(guard)
        except (DevelopmentRuntimeTemporalConsumerPatchError, OSError) as exc:
            rollback_errors.append(exc)
    guard_release_failed = len(rollback_errors) > guard_errors_before
    if succeeded and guard_release_failed:
        rollback_outputs()
    close_errors: list[Exception] = []
    for owner in reversed(owners):
        try:
            os.close(owner.directory_file_descriptor)
        except OSError as exc:
            close_errors.append(exc)
    if not succeeded or guard_release_failed:
        rollback_errors.extend(close_errors)
    if rollback_errors:
        cleanup_error = DevelopmentRuntimeTemporalConsumerPatchError(
            "E0-DLT lock resource cleanup could not be completed safely"
        )
        cleanup_error.add_note(
            "Lock cleanup failures: "
            + "; ".join(
                f"{type(error).__name__}: {error}" for error in rollback_errors
            )
        )
        if active_error is not None:
            raise cleanup_error from active_error
        raise cleanup_error from rollback_errors[0]


def _execute_lock(output: Path, companion: Path) -> dict[str, Any]:
    lock_path = _closed_output(output, DEFAULT_PATCH_LOCK_PATH)
    companion_path = _closed_output(companion, DEFAULT_PATCH_MANIFEST_PATH)
    guards = _acquire_guards(lock_path, companion_path)
    owners: list[_OwnedFile] = []
    succeeded = False
    try:
        _assert_lock_namespace(lock_path, companion_path, guards, owners)
        prelock = collect_temporal_consumer_patch_prelock_state(
            require_physical_artifacts=True,
            verify_remote=True,
        )
        verification = run_temporal_consumer_patch_verification()
        consumer_namespace_absence()
        repeated = collect_temporal_consumer_patch_prelock_state(
            require_physical_artifacts=True,
            verify_remote=True,
        )
        if repeated != prelock:
            raise DevelopmentRuntimeTemporalConsumerPatchError(
                "E0-DLT authority changed during verification"
            )
        _assert_lock_namespace(lock_path, companion_path, guards, owners)

        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload = build_temporal_consumer_patch_lock_payload(
            prelock,
            verification,
            created_at_utc=timestamp,
        )
        schema = _load_regular_json(DEFAULT_PATCH_LOCK_SCHEMA, context="E0-DLT schema")
        validate_development_runtime_temporal_consumer_patch_lock_payload(
            payload,
            schema,
            require_physical_artifacts=True,
        )

        lock_owner = _publish_guarded_bytes(
            _canonical_json(payload),
            lock_path,
            DEFAULT_PATCH_LOCK_PATH,
            guards[0],
        )
        owners.append(lock_owner)
        _assert_lock_namespace(lock_path, companion_path, guards, owners)
        lock_record = _owned_file_record(
            lock_owner,
            role="external_development_runtime_temporal_consumer_patch_lock",
        )
        companion_payload = _expected_companion(payload, lock_record=lock_record)
        companion_owner = _publish_guarded_bytes(
            _canonical_json(companion_payload),
            companion_path,
            DEFAULT_PATCH_MANIFEST_PATH,
            guards[1],
        )
        owners.append(companion_owner)
        _assert_lock_namespace(lock_path, companion_path, guards, owners)
        companion_record = _owned_file_record(
            companion_owner,
            role="development_runtime_temporal_consumer_patch_companion",
        )
        load_and_validate_development_runtime_temporal_consumer_patch_lock(
            require_published=False,
            require_physical_artifacts=True,
        )
        consumer_namespace_absence()
        _assert_lock_namespace(lock_path, companion_path, guards, owners)
        result = {
            "status": "locked_unpublished",
            "gate": "E0-DLT",
            "patch_head": payload["patch_repository"]["head"],
            "lock": lock_record,
            "companion": companion_record,
            "consumer_prelock": prelock["consumer_prelock"],
            "development_fit_authorized": False,
            "publication_required": True,
            "evaluation_authorized": False,
            "e0_u_authorized": False,
            "future_outcomes_accessed": False,
        }
        succeeded = True
        return result
    finally:
        _cleanup_lock_resources(
            owners,
            guards,
            succeeded=succeeded,
            active_error=sys.exc_info()[1],
        )


def _check_only(output: Path, companion: Path) -> dict[str, Any]:
    _refuse_existing_outputs(output, companion)
    prelock = collect_temporal_consumer_patch_prelock_state(
        require_physical_artifacts=True,
        verify_remote=True,
    )
    return {
        "status": "ready_to_lock",
        "gate": "E0-DLT",
        "patch_repository": prelock["patch_repository"],
        "patch_component_count": prelock["patch_components"]["count"],
        "consumer_prelock": prelock["consumer_prelock"],
        "writes_performed": False,
        "verification_commands_run": False,
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--execute-lock", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_PATCH_LOCK_PATH)
    parser.add_argument(
        "--companion-output",
        type=Path,
        default=DEFAULT_PATCH_MANIFEST_PATH,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.check_only:
        result = _check_only(args.output, args.companion_output)
    else:
        result = _execute_lock(args.output, args.companion_output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
