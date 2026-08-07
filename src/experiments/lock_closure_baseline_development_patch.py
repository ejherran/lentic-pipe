#!/usr/bin/env python
"""Create the scientific-egress-closed E0-MP bundle with read-only Git alignment."""

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

from src.experiments.closure_baseline_development_patch import (  # noqa: E402
    DEFAULT_PATCH_LOCK_PATH,
    DEFAULT_PATCH_MANIFEST_PATH,
    DIFF_CHECK_COMMAND,
    FOCUSED_TEST_COMMAND,
    FOCUSED_TEST_COUNT,
    POETRY_CHECK_COMMAND,
    PUBLICATION_GUARD_COMMAND,
    TYPE_CHECK_COMMAND,
    BaselineDevelopmentPatchError,
    _canonical_json,
    _expected_companion,
    _file_record,
    build_baseline_development_patch_lock_payload,
    collect_baseline_development_patch_prelock_state,
    load_effective_baseline_development_authority,
    preflight_baseline_development_patch_schema,
    validate_baseline_development_patch_lock_payload,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_GUARD_DIRECTORY = PROJECT_ROOT / "tmp" / "closure_v1_e0_mp_locker"
OUTPUT_GUARD_PATH = OUTPUT_GUARD_DIRECTORY / "baseline_development_patch_lock.guard"
FORBIDDEN_SUMMARY_RE = re.compile(
    r"\b(?:warnings?|skipped|deselected|xfailed|xpassed|errors?|failed)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class OwnedFile:
    path: Path
    relative_parent: Path
    device: int
    inode: int
    file_descriptor: int
    directory_file_descriptor: int


@dataclass(frozen=True)
class OutputGuard:
    path: Path
    relative_parent: Path
    device: int
    inode: int
    file_descriptor: int
    directory_file_descriptor: int


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _line_count(value: str) -> int:
    return len(value.splitlines())


def _command_evidence(command: Sequence[str], stdout: str, stderr: str) -> dict[str, Any]:
    return {
        "command": list(command),
        "returncode": 0,
        "stdout_sha256": _sha256_text(stdout),
        "stderr_sha256": _sha256_text(stderr),
        "stdout_line_count": _line_count(stdout),
        "stderr_line_count": _line_count(stderr),
    }


def _run_command(
    command: Sequence[str],
    *,
    sanitize_pytest_environment: bool = False,
) -> tuple[dict[str, Any], str, str]:
    environment = os.environ.copy()
    if sanitize_pytest_environment:
        environment.pop("PYTEST_ADDOPTS", None)
        environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    result = subprocess.run(
        list(command),
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    if result.returncode != 0:
        raise BaselineDevelopmentPatchError(
            f"Verification command failed ({result.returncode}): {' '.join(command)}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return _command_evidence(command, result.stdout, result.stderr), result.stdout, result.stderr


def _require_marker(stdout: str, stderr: str, marker: str, *, context: str) -> None:
    if marker not in stdout + "\n" + stderr:
        raise BaselineDevelopmentPatchError(f"{context} success marker is absent")


def _require_empty_output(stdout: str, stderr: str, *, context: str) -> None:
    if stdout.strip() or stderr.strip():
        raise BaselineDevelopmentPatchError(f"{context} unexpectedly produced output")


def _parse_focused_summary(stdout: str, stderr: str) -> dict[str, Any]:
    if FOCUSED_TEST_COUNT <= 0:
        raise BaselineDevelopmentPatchError(
            "E0-MP focused-test count must be frozen before execute-lock"
        )
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    pattern = re.compile(
        r"^(?P<count>[1-9][0-9]*) passed in (?P<seconds>[0-9]+\.[0-9]{2})s"
        r"(?: \((?P<clock>(?:[0-9]+ days?, )?[0-9]+:[0-9]{2}:[0-9]{2})\))?$"
    )
    matches = [line for line in lines if pattern.fullmatch(line)]
    combined = stdout + "\n" + stderr
    if (
        stderr.strip()
        or len(matches) != 1
        or not lines
        or matches[0] != lines[-1]
        or FORBIDDEN_SUMMARY_RE.search(combined) is not None
    ):
        raise BaselineDevelopmentPatchError("Focused pytest summary is not one clean exact result")
    match = pattern.fullmatch(matches[0])
    if match is None or int(match.group("count")) != FOCUSED_TEST_COUNT:
        raise BaselineDevelopmentPatchError("Focused pytest count drifted")
    return {
        "test_count": FOCUSED_TEST_COUNT,
        "skipped_count": 0,
        "deselected_count": 0,
    }


def run_baseline_development_patch_verification(
    *,
    expected_schema_preflight: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run only repository checks; never DVC, science, auditors, or network."""
    schema_preflight = preflight_baseline_development_patch_schema()
    if expected_schema_preflight is not None and dict(expected_schema_preflight) != schema_preflight:
        raise BaselineDevelopmentPatchError("E0-MP schema changed before verification")
    full_type_check, stdout, stderr = _run_command(TYPE_CHECK_COMMAND)
    _require_marker(stdout, stderr, "All checks passed!", context="full type check")
    focused_tests, stdout, stderr = _run_command(
        FOCUSED_TEST_COMMAND,
        sanitize_pytest_environment=True,
    )
    focused_tests.update(_parse_focused_summary(stdout, stderr))
    poetry_check, stdout, stderr = _run_command(POETRY_CHECK_COMMAND)
    _require_marker(stdout, stderr, "All set!", context="Poetry check")
    publication_guard, stdout, stderr = _run_command(PUBLICATION_GUARD_COMMAND)
    _require_marker(stdout, stderr, "Repository publication guard passed.", context="publication guard")
    diff_check, stdout, stderr = _run_command(DIFF_CHECK_COMMAND)
    _require_empty_output(stdout, stderr, context="git diff --check")
    return {
        "schema_preflight": schema_preflight,
        "full_type_check": full_type_check,
        "focused_tests": focused_tests,
        "poetry_check": poetry_check,
        "publication_guard": publication_guard,
        "git_diff_check": diff_check,
    }


def _repo_relative(path: Path, *, context: str) -> Path:
    root = Path(os.path.abspath(PROJECT_ROOT))
    candidate = Path(os.path.abspath(path))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise BaselineDevelopmentPatchError(f"{context} escaped the repository") from exc
    if any(component in {"", ".", ".."} for component in relative.parts):
        raise BaselineDevelopmentPatchError(f"{context} is not a closed path")
    return relative


def _directory_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def _open_real_directory(path: Path, *, context: str) -> int:
    try:
        descriptor = os.open(path, _directory_flags())
    except OSError as exc:
        raise BaselineDevelopmentPatchError(
            f"{context} is unavailable or not a real directory"
        ) from exc
    try:
        opened = os.fstat(descriptor)
        lexical = os.lstat(path)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or not stat.S_ISDIR(lexical.st_mode)
            or (opened.st_dev, opened.st_ino) != (lexical.st_dev, lexical.st_ino)
        ):
            raise BaselineDevelopmentPatchError(f"{context} identity drifted")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_repo_directory(relative: Path, *, context: str) -> int:
    if relative.is_absolute() or any(
        component in {"", ".", ".."} for component in relative.parts
    ):
        raise BaselineDevelopmentPatchError(f"{context} escaped the repository root")
    descriptor = _open_real_directory(
        Path(os.path.abspath(PROJECT_ROOT)),
        context="E0-MP repository root",
    )
    try:
        for component in relative.parts:
            try:
                child = os.open(component, _directory_flags(), dir_fd=descriptor)
            except OSError as exc:
                raise BaselineDevelopmentPatchError(
                    f"{context} contains an unavailable or linked ancestor"
                ) from exc
            try:
                if not stat.S_ISDIR(os.fstat(child).st_mode):
                    raise BaselineDevelopmentPatchError(
                        f"{context} contains a non-directory ancestor"
                    )
            except BaseException:
                os.close(child)
                raise
            parent = descriptor
            descriptor = child
            os.close(parent)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _ensure_repo_directory(relative: Path, *, context: str) -> int:
    if relative.is_absolute() or any(
        component in {"", ".", ".."} for component in relative.parts
    ):
        raise BaselineDevelopmentPatchError(f"{context} escaped the repository root")
    descriptor = _open_real_directory(
        Path(os.path.abspath(PROJECT_ROOT)),
        context="E0-MP repository root",
    )
    try:
        for component in relative.parts:
            try:
                os.mkdir(component, mode=0o700, dir_fd=descriptor)
                os.fsync(descriptor)
            except FileExistsError:
                pass
            except OSError as exc:
                raise BaselineDevelopmentPatchError(
                    f"{context} could not be created safely"
                ) from exc
            try:
                child = os.open(component, _directory_flags(), dir_fd=descriptor)
            except OSError as exc:
                raise BaselineDevelopmentPatchError(
                    f"{context} contains an unavailable or linked ancestor"
                ) from exc
            if not stat.S_ISDIR(os.fstat(child).st_mode):
                os.close(child)
                raise BaselineDevelopmentPatchError(
                    f"{context} contains a non-directory ancestor"
                )
            parent = descriptor
            descriptor = child
            os.close(parent)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _write_all(descriptor: int, payload: bytes, *, context: str) -> None:
    offset = 0
    while offset < len(payload):
        try:
            written = os.write(descriptor, payload[offset:])
        except OSError as exc:
            raise BaselineDevelopmentPatchError(f"{context} write failed") from exc
        if written <= 0:
            raise BaselineDevelopmentPatchError(f"{context} produced a short write")
        offset += written
    os.fsync(descriptor)


def _descriptor_stat(descriptor: int) -> os.stat_result:
    """Anchor descriptor identity even when a monkeypatched fstat fails."""
    try:
        return os.stat(descriptor)
    except OSError:
        return os.fstat(descriptor)


def _owner_state(owner: OwnedFile | OutputGuard) -> str:
    try:
        anchored_directory = _descriptor_stat(owner.directory_file_descriptor)
        opened_file = _descriptor_stat(owner.file_descriptor)
        current_descriptor = _open_repo_directory(
            owner.relative_parent,
            context="E0-MP owned-file parent",
        )
    except OSError as exc:
        raise BaselineDevelopmentPatchError(
            "E0-MP owned-file descriptors could not be inspected"
        ) from exc
    except BaselineDevelopmentPatchError:
        return "foreign"
    try:
        current_directory = _descriptor_stat(current_descriptor)
        if (
            not stat.S_ISDIR(anchored_directory.st_mode)
            or not stat.S_ISDIR(current_directory.st_mode)
            or (anchored_directory.st_dev, anchored_directory.st_ino)
            != (current_directory.st_dev, current_directory.st_ino)
        ):
            return "foreign"
        try:
            anchored_name = os.stat(
                owner.path.name,
                dir_fd=owner.directory_file_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            anchored_name = None
        try:
            current_name = os.stat(
                owner.path.name,
                dir_fd=current_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            current_name = None
        if anchored_name is None and current_name is None:
            return "absent"
        if anchored_name is None or current_name is None:
            return "foreign"
        expected = (owner.device, owner.inode)
        if (
            stat.S_ISREG(opened_file.st_mode)
            and stat.S_ISREG(anchored_name.st_mode)
            and stat.S_ISREG(current_name.st_mode)
            and (opened_file.st_dev, opened_file.st_ino) == expected
            and (anchored_name.st_dev, anchored_name.st_ino) == expected
            and (current_name.st_dev, current_name.st_ino) == expected
        ):
            return "owned"
        return "foreign"
    except OSError as exc:
        raise BaselineDevelopmentPatchError(
            "E0-MP owned-file identity could not be inspected"
        ) from exc
    finally:
        os.close(current_descriptor)


def _close_owner(owner: OwnedFile | OutputGuard) -> None:
    errors: list[OSError] = []
    for descriptor in (owner.file_descriptor, owner.directory_file_descriptor):
        try:
            os.close(descriptor)
        except OSError as exc:
            errors.append(exc)
    if errors:
        raise BaselineDevelopmentPatchError(
            "E0-MP owned-file descriptors could not be closed"
        ) from errors[0]


def _rollback_if_owned(owner: OwnedFile | OutputGuard, *, context: str) -> None:
    state = _owner_state(owner)
    if state == "foreign":
        raise BaselineDevelopmentPatchError(f"{context} preserved a foreign replacement")
    if state == "owned":
        try:
            os.unlink(owner.path.name, dir_fd=owner.directory_file_descriptor)
            os.fsync(owner.directory_file_descriptor)
        except OSError as exc:
            raise BaselineDevelopmentPatchError(f"{context} rollback failed") from exc
    if _owner_state(owner) != "absent":
        raise BaselineDevelopmentPatchError(
            f"{context} rollback did not establish absence"
        )


def _guard_is_owned(guard: OutputGuard) -> bool:
    return _owner_state(guard) == "owned"


def _acquire_guard() -> OutputGuard:
    expected = Path(os.path.abspath(PROJECT_ROOT)) / "tmp" / "closure_v1_e0_mp_locker"
    if Path(os.path.abspath(OUTPUT_GUARD_DIRECTORY)) != expected:
        raise BaselineDevelopmentPatchError("E0-MP guard directory escaped ignored tmp/")
    relative_parent = _repo_relative(
        OUTPUT_GUARD_DIRECTORY,
        context="E0-MP guard directory",
    )
    directory_descriptor = _ensure_repo_directory(
        relative_parent,
        context="E0-MP guard directory",
    )
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(
            OUTPUT_GUARD_PATH.name,
            flags,
            0o600,
            dir_fd=directory_descriptor,
        )
    except FileExistsError as exc:
        os.close(directory_descriptor)
        raise BaselineDevelopmentPatchError("E0-MP locker guard already exists") from exc
    except BaseException:
        os.close(directory_descriptor)
        raise
    guard: OutputGuard | None = None
    try:
        metadata = _descriptor_stat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise BaselineDevelopmentPatchError("E0-MP guard is not regular")
        guard = OutputGuard(
            path=OUTPUT_GUARD_PATH,
            relative_parent=relative_parent,
            device=int(metadata.st_dev),
            inode=int(metadata.st_ino),
            file_descriptor=descriptor,
            directory_file_descriptor=directory_descriptor,
        )
        if not _guard_is_owned(guard):
            raise BaselineDevelopmentPatchError("E0-MP guard identity drifted")
        _write_all(
            descriptor,
            f"pid={os.getpid()}\n".encode("ascii"),
            context="E0-MP guard",
        )
        if not _guard_is_owned(guard):
            raise BaselineDevelopmentPatchError("E0-MP guard identity drifted")
        return guard
    except BaseException as exc:
        cleanup_errors: list[BaseException] = []
        if guard is not None:
            try:
                _rollback_if_owned(guard, context="E0-MP guard")
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        for owned_descriptor in (descriptor, directory_descriptor):
            try:
                os.close(owned_descriptor)
            except OSError as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        if cleanup_errors:
            cleanup_error = BaselineDevelopmentPatchError(
                "E0-MP guard creation cleanup failed closed"
            )
            cleanup_error.add_note(
                "; ".join(f"{type(item).__name__}: {item}" for item in cleanup_errors)
            )
            raise cleanup_error from exc
        raise


def _release_guard(guard: OutputGuard) -> None:
    error: BaseException | None = None
    try:
        if _owner_state(guard) != "owned":
            raise BaselineDevelopmentPatchError(
                "E0-MP guard ownership was lost; foreign state was preserved"
            )
        os.unlink(guard.path.name, dir_fd=guard.directory_file_descriptor)
        os.fsync(guard.directory_file_descriptor)
        if _owner_state(guard) != "absent":
            raise BaselineDevelopmentPatchError(
                "E0-MP guard release did not establish absence"
            )
    except BaseException as exc:
        error = exc
    try:
        _close_owner(guard)
    except BaseException as exc:
        if error is None:
            error = exc
        else:
            error.add_note(f"Guard descriptor cleanup: {type(exc).__name__}: {exc}")
    if error is not None:
        raise error


def _closed_output(path: Path, expected: Path, *, context: str) -> tuple[Path, Path]:
    candidate = path if path.is_absolute() else PROJECT_ROOT / path
    lexical = Path(os.path.abspath(candidate))
    required = Path(os.path.abspath(PROJECT_ROOT / expected))
    if lexical != required:
        raise BaselineDevelopmentPatchError(f"{context} must use {expected.as_posix()}")
    return lexical, _repo_relative(lexical.parent, context=f"{context} parent")


def _write_temp(path: Path, expected: Path, payload: bytes) -> OwnedFile:
    lexical, relative_parent = _closed_output(path, expected, context="E0-MP temporary")
    directory_descriptor = _open_repo_directory(
        relative_parent,
        context="E0-MP temporary parent",
    )
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(
            lexical.name,
            flags,
            0o600,
            dir_fd=directory_descriptor,
        )
    except FileExistsError as exc:
        os.close(directory_descriptor)
        raise BaselineDevelopmentPatchError(
            f"Refusing to clobber E0-MP temporary: {expected.as_posix()}"
        ) from exc
    except BaseException:
        os.close(directory_descriptor)
        raise
    owner: OwnedFile | None = None
    try:
        metadata = _descriptor_stat(descriptor)
        owner = OwnedFile(
            path=lexical,
            relative_parent=relative_parent,
            device=int(metadata.st_dev),
            inode=int(metadata.st_ino),
            file_descriptor=descriptor,
            directory_file_descriptor=directory_descriptor,
        )
        if not stat.S_ISREG(metadata.st_mode):
            raise BaselineDevelopmentPatchError("E0-MP temporary is not regular")
        _write_all(descriptor, payload, context="E0-MP temporary")
        if _owner_state(owner) != "owned":
            raise BaselineDevelopmentPatchError("E0-MP temporary identity drifted")
        return owner
    except BaseException as exc:
        cleanup_errors: list[BaseException] = []
        if owner is not None:
            try:
                _rollback_if_owned(owner, context="E0-MP temporary")
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        for owned_descriptor in (descriptor, directory_descriptor):
            try:
                os.close(owned_descriptor)
            except OSError as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        if cleanup_errors:
            cleanup_error = BaselineDevelopmentPatchError(
                "E0-MP temporary creation cleanup failed closed"
            )
            cleanup_error.add_note(
                "; ".join(f"{type(item).__name__}: {item}" for item in cleanup_errors)
            )
            raise cleanup_error from exc
        raise


def _publish_temp(
    temp: OwnedFile,
    final_path: Path,
    expected: Path,
    guard: OutputGuard,
) -> OwnedFile:
    final, relative_parent = _closed_output(final_path, expected, context="E0-MP output")
    if not _guard_is_owned(guard):
        raise BaselineDevelopmentPatchError("E0-MP guard changed before publication")
    if _owner_state(temp) != "owned":
        raise BaselineDevelopmentPatchError("E0-MP temporary ownership drifted")
    destination_descriptor = _open_repo_directory(
        relative_parent,
        context="E0-MP output parent",
    )
    duplicate_descriptor = os.dup(temp.file_descriptor)
    owner: OwnedFile | None = None
    try:
        os.link(
            temp.path.name,
            final.name,
            src_dir_fd=temp.directory_file_descriptor,
            dst_dir_fd=destination_descriptor,
            follow_symlinks=False,
        )
        owner = OwnedFile(
            path=final,
            relative_parent=relative_parent,
            device=temp.device,
            inode=temp.inode,
            file_descriptor=duplicate_descriptor,
            directory_file_descriptor=destination_descriptor,
        )
        os.fsync(destination_descriptor)
        if _owner_state(owner) != "owned":
            raise BaselineDevelopmentPatchError("E0-MP published output identity drifted")
        if not _guard_is_owned(guard):
            raise BaselineDevelopmentPatchError("E0-MP guard changed during publication")
        _rollback_if_owned(temp, context="E0-MP published temporary")
        _close_owner(temp)
        return owner
    except FileExistsError as exc:
        os.close(duplicate_descriptor)
        os.close(destination_descriptor)
        raise BaselineDevelopmentPatchError(
            f"Refusing to clobber E0-MP output: {expected.as_posix()}"
        ) from exc
    except BaseException as exc:
        cleanup_errors: list[BaseException] = []
        if owner is not None:
            try:
                _rollback_if_owned(owner, context="E0-MP output")
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        for descriptor in (duplicate_descriptor, destination_descriptor):
            try:
                os.close(descriptor)
            except OSError as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        if cleanup_errors:
            cleanup_error = BaselineDevelopmentPatchError(
                "E0-MP publication rollback could not be completed safely"
            )
            cleanup_error.add_note(
                "; ".join(f"{type(item).__name__}: {item}" for item in cleanup_errors)
            )
            raise cleanup_error from exc
        raise


def _read_owned_bytes(owner: OwnedFile) -> bytes:
    if _owner_state(owner) != "owned":
        raise BaselineDevelopmentPatchError("E0-MP output changed before verification")
    os.lseek(owner.file_descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(owner.file_descriptor, 1024 * 1024)
        if not chunk:
            break
        chunks.append(chunk)
    payload = b"".join(chunks)
    if _owner_state(owner) != "owned":
        raise BaselineDevelopmentPatchError("E0-MP output changed during verification")
    return payload


def _logical_record(path: Path, role: str, payload: bytes) -> dict[str, Any]:
    return {
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "role": role,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _publish_lock_bundle(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    lock_path = PROJECT_ROOT / DEFAULT_PATCH_LOCK_PATH
    manifest_path = PROJECT_ROOT / DEFAULT_PATCH_MANIFEST_PATH
    lock_temp_path = Path(lock_path.as_posix() + ".tmp")
    manifest_temp_path = Path(manifest_path.as_posix() + ".tmp")
    guard = _acquire_guard()
    temps: list[OwnedFile] = []
    published: list[OwnedFile] = []
    result: tuple[dict[str, Any], dict[str, Any]] | None = None
    active_error: BaseException | None = None
    try:
        lock_bytes = _canonical_json(payload)
        lock_record = _logical_record(
            lock_path,
            "baseline_development_patch_lock",
            lock_bytes,
        )
        companion = _expected_companion(payload, lock_record)
        companion_bytes = _canonical_json(companion)
        lock_temp_relative = Path(DEFAULT_PATCH_LOCK_PATH.as_posix() + ".tmp")
        manifest_temp_relative = Path(DEFAULT_PATCH_MANIFEST_PATH.as_posix() + ".tmp")
        lock_temp = _write_temp(lock_temp_path, lock_temp_relative, lock_bytes)
        temps.append(lock_temp)
        manifest_temp = _write_temp(
            manifest_temp_path,
            manifest_temp_relative,
            companion_bytes,
        )
        temps.append(manifest_temp)
        published_lock = _publish_temp(
            lock_temp,
            lock_path,
            DEFAULT_PATCH_LOCK_PATH,
            guard,
        )
        temps.remove(lock_temp)
        published.append(published_lock)
        # Completion marker is deliberately the final publication.
        published_manifest = _publish_temp(
            manifest_temp,
            manifest_path,
            DEFAULT_PATCH_MANIFEST_PATH,
            guard,
        )
        temps.remove(manifest_temp)
        published.append(published_manifest)
        if _read_owned_bytes(published_lock) != lock_bytes:
            raise BaselineDevelopmentPatchError("Published E0-MP lock bytes drifted")
        if _read_owned_bytes(published_manifest) != companion_bytes:
            raise BaselineDevelopmentPatchError("Published E0-MP companion bytes drifted")
        result = (dict(payload), companion)
    except BaseException as exc:
        active_error = exc

    cleanup_errors: list[BaseException] = []
    if active_error is not None:
        for owner in reversed(published):
            try:
                _rollback_if_owned(owner, context="E0-MP published output")
            except BaseException as exc:
                cleanup_errors.append(exc)
        for owner in reversed(temps):
            try:
                _rollback_if_owned(owner, context="E0-MP temporary")
            except BaseException as exc:
                cleanup_errors.append(exc)
    try:
        _release_guard(guard)
    except BaseException as exc:
        cleanup_errors.append(exc)
        if active_error is None:
            for owner in reversed(published):
                try:
                    _rollback_if_owned(owner, context="E0-MP published output")
                except BaseException as rollback_exc:
                    cleanup_errors.append(rollback_exc)
    if active_error is None and not cleanup_errors:
        for owner in published:
            try:
                if _owner_state(owner) != "owned":
                    raise BaselineDevelopmentPatchError(
                        "E0-MP published output changed after guard release"
                    )
            except BaseException as exc:
                cleanup_errors.append(exc)
        if cleanup_errors:
            for owner in reversed(published):
                try:
                    _rollback_if_owned(owner, context="E0-MP published output")
                except BaseException as rollback_exc:
                    cleanup_errors.append(rollback_exc)
    for owner in reversed((*published, *temps)):
        try:
            _close_owner(owner)
        except BaseException as exc:
            cleanup_errors.append(exc)
    if cleanup_errors:
        cleanup_error = BaselineDevelopmentPatchError(
            "E0-MP lock resource cleanup failed closed"
        )
        cleanup_error.add_note(
            "; ".join(f"{type(item).__name__}: {item}" for item in cleanup_errors)
        )
        if active_error is not None:
            raise cleanup_error from active_error
        raise cleanup_error from cleanup_errors[0]
    if active_error is not None:
        raise active_error
    if result is None:
        raise BaselineDevelopmentPatchError("E0-MP publication produced no result")
    return result


def check_only() -> dict[str, Any]:
    schema_preflight = preflight_baseline_development_patch_schema()
    prelock = collect_baseline_development_patch_prelock_state()
    return {
        "status": "ready_to_lock",
        "gate": "E0-MP",
        "schema_preflight": schema_preflight,
        "patch_head": prelock["repository"]["head"],
        "h_added_count": prelock["h_patch"]["added_count"],
        "minimum_final_path_count": prelock["runtime_contract"][
            "minimum_final_path_count"
        ],
        "maximum_final_path_count": prelock["runtime_contract"][
            "maximum_final_path_count"
        ],
        "writes_performed": False,
        "verification_commands_run": False,
        "dvc_commands_run": False,
        "network_commands_run": True,
        "data_execution_run": False,
        "auditor_run": False,
        "future_outcomes_accessed": False,
    }


def execute_lock() -> dict[str, Any]:
    schema_preflight = preflight_baseline_development_patch_schema()
    prelock = collect_baseline_development_patch_prelock_state()
    verification = run_baseline_development_patch_verification(
        expected_schema_preflight=schema_preflight
    )
    if collect_baseline_development_patch_prelock_state() != prelock:
        raise BaselineDevelopmentPatchError("E0-MP prelock state changed during verification")
    payload = build_baseline_development_patch_lock_payload(
        prelock,
        verification,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    validate_baseline_development_patch_lock_payload(payload)
    _publish_lock_bundle(payload)
    return {
        "status": "locked_unpublished",
        "gate": "E0-MP",
        "lock_path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "manifest_path": DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        "published_output_count": 2,
        "baseline_one_shot_authorized": False,
        "dvc_commands_run": False,
        "network_commands_run": True,
        "data_execution_run": False,
        "auditor_run": False,
        "future_outcomes_accessed": False,
    }


def check_effective() -> dict[str, Any]:
    return load_effective_baseline_development_authority()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--execute-lock", action="store_true")
    mode.add_argument("--check-effective", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.check_only:
        result = check_only()
    elif args.execute_lock:
        result = execute_lock()
    else:
        result = check_effective()
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
