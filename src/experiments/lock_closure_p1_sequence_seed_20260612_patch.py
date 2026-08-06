#!/usr/bin/env python
"""Create and verify the additive Closure V1 E0-MH lock bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments import (  # noqa: E402
    lock_closure_development_runtime_temporal_consumer_patch as hardened,
)
from src.experiments.closure_p1_sequence_seed_20260612_patch import (  # noqa: E402
    DEFAULT_PATCH_LOCK_PATH,
    DEFAULT_PATCH_LOCK_SCHEMA,
    DEFAULT_PATCH_MANIFEST_PATH,
    DIFF_CHECK_COMMAND,
    FOCUSED_TEST_COMMAND,
    FOCUSED_TEST_COUNT,
    POETRY_CHECK_COMMAND,
    PUBLICATION_GUARD_COMMAND,
    TYPE_CHECK_COMMAND,
    P1SequenceSeed20260612PatchError,
    _expected_companion,
    _load_regular_json,
    _load_unpublished_p1_sequence_seed_20260612_patch_lock,
    build_p1_sequence_seed_20260612_patch_lock_payload,
    closure_progression_namespace_absence,
    collect_p1_sequence_seed_20260612_patch_prelock_state,
    p1_sequence_namespace_absence,
    preflight_p1_sequence_seed_20260612_patch_schema,
    require_p1_sequence_seed_20260612_authorized,
    validate_p1_sequence_seed_20260612_patch_lock_payload,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_GUARD_DIRECTORY = PROJECT_ROOT / "tmp" / "closure_v1_e0_mh_locker"
OUTPUT_GUARD_NAMES = (
    "p1_sequence_seed_20260612_patch_lock.guard",
    "p1_sequence_seed_20260612_patch_lock_manifest.guard",
)
AUTHORIZED_MODEL_ID = "P1"
AUTHORIZED_BASE_SEED = 20260612
FORBIDDEN_PYTEST_SUMMARY_RE = re.compile(
    r"\b(?:warnings?|skipped|deselected|xfailed|xpassed|errors?|failed)\b",
    flags=re.IGNORECASE,
)


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return hardened._canonical_json(payload)


def _run_command(
    command: Sequence[str],
    *,
    sanitize_pytest_environment: bool = False,
) -> tuple[dict[str, Any], str, str]:
    try:
        return hardened._run_command(
            command,
            sanitize_pytest_environment=sanitize_pytest_environment,
        )
    except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceSeed20260612PatchError(str(exc)) from exc


def _preflight_schema() -> dict[str, Any]:
    observed = preflight_p1_sequence_seed_20260612_patch_schema()
    expected_fields = {
        "gate",
        "schema_path",
        "schema_bytes",
        "schema_sha256",
        "supported_subset_verified",
        "minimum_keyword_absent",
        "format_keyword_absent",
    }
    digest = observed.get("schema_sha256")
    size = observed.get("schema_bytes")
    if (
        set(observed) != expected_fields
        or observed.get("gate") != "E0-MH"
        or observed.get("schema_path") != DEFAULT_PATCH_LOCK_SCHEMA.as_posix()
        or type(size) is not int
        or size <= 0
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
        or observed.get("supported_subset_verified") is not True
        or observed.get("minimum_keyword_absent") is not True
        or observed.get("format_keyword_absent") is not True
    ):
        raise P1SequenceSeed20260612PatchError(
            "E0-MH schema-subset preflight evidence drifted"
        )
    return dict(observed)


def _parse_focused_summary(stdout: str, stderr: str) -> int:
    combined = stdout + "\n" + stderr
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    summary_re = re.compile(
        rf"^{FOCUSED_TEST_COUNT} passed in "
        r"(?P<duration>[0-9]+(?:\.[0-9]+)?)s"
        r"(?: \((?P<clock>(?:[0-9]+ days?, )?[0-9]+:[0-9]{2}:[0-9]{2})\))?$"
    )
    matches = [line for line in lines if summary_re.fullmatch(line)]
    if (
        FOCUSED_TEST_COUNT <= 0
        or not lines
        or matches != [lines[-1]]
        or FORBIDDEN_PYTEST_SUMMARY_RE.search(combined) is not None
    ):
        raise P1SequenceSeed20260612PatchError(
            "E0-MH focused pytest summary is not one exact clean result"
        )
    match = summary_re.fullmatch(matches[0])
    if match is None:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH focused pytest summary could not be parsed"
        )
    try:
        duration = Decimal(match.group("duration"))
        expected_clock = str(timedelta(seconds=int(duration)))
    except (InvalidOperation, OverflowError) as exc:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH focused pytest duration is malformed"
        ) from exc
    clock = match.group("clock")
    if (duration < Decimal(60) and clock is not None) or (
        duration >= Decimal(60) and clock != expected_clock
    ):
        raise P1SequenceSeed20260612PatchError(
            "E0-MH focused pytest duration clock drifted"
        )
    return FOCUSED_TEST_COUNT


def _require_success_marker(stdout: str, stderr: str, marker: str) -> None:
    if marker not in stdout + "\n" + stderr:
        raise P1SequenceSeed20260612PatchError(
            f"E0-MH verification marker is absent: {marker}"
        )


def _require_empty_output(stdout: str, stderr: str, *, context: str) -> None:
    if stdout.strip() or stderr.strip():
        raise P1SequenceSeed20260612PatchError(
            f"E0-MH expected empty output from {context}"
        )


def run_p1_sequence_seed_20260612_patch_verification(
    *,
    expected_schema_preflight: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the closed H-E0-MH verification set; intentionally heavy."""
    schema_preflight = _preflight_schema()
    if (
        expected_schema_preflight is not None
        and dict(expected_schema_preflight) != schema_preflight
    ):
        raise P1SequenceSeed20260612PatchError(
            "E0-MH schema changed before verification"
        )
    if FOCUSED_TEST_COUNT <= 0:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH focused-test count has not been finalized"
        )
    try:
        hardened._require_fixed_venv_executable(TYPE_CHECK_COMMAND)
        hardened._require_fixed_venv_executable(FOCUSED_TEST_COMMAND)
    except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceSeed20260612PatchError(str(exc)) from exc

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
    return {
        "schema_subset_preflight": schema_preflight,
        "full_type_check": type_check,
        "focused_tests": focused,
        "poetry_check": poetry_check,
        "publication_guard": publication_guard,
        "git_diff_check": diff_check,
    }


def _closed_output(path: Path, expected: Path) -> Path:
    try:
        return hardened._closed_output(path, expected)
    except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceSeed20260612PatchError(str(exc)) from exc


def _guard_paths(*, create_directory: bool) -> tuple[Path, Path]:
    tmp_root = PROJECT_ROOT / "tmp"
    if OUTPUT_GUARD_DIRECTORY != tmp_root / "closure_v1_e0_mh_locker":
        raise P1SequenceSeed20260612PatchError(
            "E0-MH coordination directory escaped tmp/"
        )
    for path, context in (
        (tmp_root, "E0-MH tmp root"),
        (OUTPUT_GUARD_DIRECTORY, "E0-MH guard directory"),
    ):
        if not os.path.lexists(path):
            continue
        try:
            descriptor = hardened._open_real_directory(path, context=context)
        except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
            raise P1SequenceSeed20260612PatchError(str(exc)) from exc
        else:
            os.close(descriptor)
    if create_directory:
        try:
            hardened._ensure_real_directory(
                tmp_root,
                parent=PROJECT_ROOT,
                context="E0-MH tmp root",
            )
            hardened._ensure_real_directory(
                OUTPUT_GUARD_DIRECTORY,
                parent=tmp_root,
                context="E0-MH guard directory",
            )
        except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
            raise P1SequenceSeed20260612PatchError(str(exc)) from exc
    return (
        OUTPUT_GUARD_DIRECTORY / OUTPUT_GUARD_NAMES[0],
        OUTPUT_GUARD_DIRECTORY / OUTPUT_GUARD_NAMES[1],
    )


def _refuse_existing_outputs(output: Path, companion: Path) -> None:
    lock_path = _closed_output(output, DEFAULT_PATCH_LOCK_PATH)
    companion_path = _closed_output(companion, DEFAULT_PATCH_MANIFEST_PATH)
    candidates = (
        lock_path,
        lock_path.with_suffix(lock_path.suffix + ".tmp"),
        companion_path,
        companion_path.with_suffix(companion_path.suffix + ".tmp"),
        *_guard_paths(create_directory=False),
    )
    existing = [str(path) for path in candidates if os.path.lexists(path)]
    if existing:
        raise P1SequenceSeed20260612PatchError(
            f"Refusing to overwrite an existing E0-MH lock bundle: {existing}"
        )


def _acquire_guards(output: Path, companion: Path) -> tuple[Any, ...]:
    _refuse_existing_outputs(output, companion)
    guards: list[Any] = []
    try:
        for path in _guard_paths(create_directory=True):
            guards.append(hardened._open_guard(path))
    except BaseException:
        for guard in reversed(guards):
            _release_guard_strict(guard)
        raise
    return tuple(guards)


def _release_guard_strict(guard: Any) -> None:
    """Release one guard and fail if its owned name was lost or replaced."""
    try:
        owned_before = hardened._guard_is_owned(guard)
    except (hardened.DevelopmentRuntimeTemporalConsumerPatchError, OSError) as exc:
        try:
            hardened._release_guard(guard)
        except (hardened.DevelopmentRuntimeTemporalConsumerPatchError, OSError):
            pass
        raise P1SequenceSeed20260612PatchError(
            "E0-MH guard ownership could not be verified before release"
        ) from exc
    release_error: BaseException | None = None
    try:
        hardened._release_guard(guard)
    except (hardened.DevelopmentRuntimeTemporalConsumerPatchError, OSError) as exc:
        release_error = exc
    residual = os.path.lexists(guard.path)
    if not owned_before or residual or release_error is not None:
        error = P1SequenceSeed20260612PatchError(
            "E0-MH guard release lost ownership or left a residual path"
        )
        if release_error is not None:
            raise error from release_error
        raise error


def _anchored_owner_state(owner: Any) -> str:
    try:
        directory = os.fstat(owner.directory_file_descriptor)
        observed = os.stat(
            owner.path.name,
            dir_fd=owner.directory_file_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return "absent"
    except OSError as exc:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH anchored output ownership could not be inspected"
        ) from exc
    if not stat.S_ISDIR(directory.st_mode):
        raise P1SequenceSeed20260612PatchError(
            "E0-MH anchored output parent is no longer a directory"
        )
    if (
        stat.S_ISREG(observed.st_mode)
        and (observed.st_dev, observed.st_ino) == (owner.device, owner.inode)
    ):
        return "owned"
    return "foreign"


def _rollback_owner_anchored(owner: Any) -> None:
    state = _anchored_owner_state(owner)
    if state == "foreign":
        raise P1SequenceSeed20260612PatchError(
            "E0-MH rollback preserved a foreign replacement"
        )
    if state == "owned":
        try:
            os.unlink(owner.path.name, dir_fd=owner.directory_file_descriptor)
        except OSError as exc:
            raise P1SequenceSeed20260612PatchError(
                "E0-MH anchored output rollback failed"
            ) from exc
    if _anchored_owner_state(owner) != "absent":
        raise P1SequenceSeed20260612PatchError(
            "E0-MH rollback did not establish output absence"
        )
    try:
        os.fsync(owner.directory_file_descriptor)
    except OSError as exc:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH rollback could not synchronize its anchored parent"
        ) from exc


def _publish_guarded_bytes(
    payload: bytes,
    destination: Path,
    expected: Path,
    guard: Any,
) -> Any:
    final = _closed_output(destination, expected)
    try:
        guard_owned = hardened._guard_is_owned(guard)
    except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceSeed20260612PatchError(str(exc)) from exc
    if not guard_owned:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH output guard changed before publication"
        )
    try:
        os.ftruncate(guard.file_descriptor, 0)
        os.lseek(guard.file_descriptor, 0, os.SEEK_SET)
        offset = 0
        while offset < len(payload):
            written = os.write(guard.file_descriptor, payload[offset:])
            if written <= 0:
                raise P1SequenceSeed20260612PatchError(
                    "Short write while preparing an E0-MH output"
                )
            offset += written
        os.fsync(guard.file_descriptor)
        if not hardened._guard_is_owned(guard):
            raise P1SequenceSeed20260612PatchError(
                "E0-MH output guard changed while writing"
            )
    except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceSeed20260612PatchError(str(exc)) from exc
    except OSError as exc:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH output preparation failed"
        ) from exc

    try:
        destination_descriptor = hardened._open_repo_directory(
            expected.parent,
            context="E0-MH final-output parent",
        )
    except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceSeed20260612PatchError(str(exc)) from exc
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
        raise P1SequenceSeed20260612PatchError(
            f"Refusing to clobber an E0-MH output: {destination}"
        ) from exc
    except BaseException:
        os.close(destination_descriptor)
        raise
    owner = hardened._OwnedFile(
        path=final,
        device=guard.device,
        inode=guard.inode,
        directory_file_descriptor=destination_descriptor,
    )
    try:
        os.fsync(destination_descriptor)
        if not hardened._owned(owner):
            raise P1SequenceSeed20260612PatchError(
                "E0-MH published output identity drifted"
            )
        return owner
    except BaseException as error:
        cleanup_errors: list[Exception] = []
        try:
            _rollback_owner_anchored(owner)
        except (P1SequenceSeed20260612PatchError, OSError) as exc:
            cleanup_errors.append(exc)
        try:
            os.close(destination_descriptor)
        except OSError as exc:
            cleanup_errors.append(exc)
        if cleanup_errors:
            cleanup_error = P1SequenceSeed20260612PatchError(
                "E0-MH output rollback could not be completed safely"
            )
            cleanup_error.add_note(
                "Output rollback failures: "
                + "; ".join(
                    f"{type(exc).__name__}: {exc}" for exc in cleanup_errors
                )
            )
            raise cleanup_error from error
        if isinstance(error, P1SequenceSeed20260612PatchError):
            raise error
        raise P1SequenceSeed20260612PatchError(
            "E0-MH output publication failed"
        ) from error


def _cleanup_lock_resources(
    owners: Sequence[Any],
    guards: Sequence[Any],
    *,
    succeeded: bool,
    active_error: BaseException | None,
) -> None:
    cleanup_errors: list[Exception] = []

    def rollback_outputs() -> None:
        for owner in reversed(owners):
            try:
                _rollback_owner_anchored(owner)
            except (P1SequenceSeed20260612PatchError, OSError) as exc:
                cleanup_errors.append(exc)

    if not succeeded:
        rollback_outputs()
    guard_errors_before = len(cleanup_errors)
    for guard in reversed(guards):
        try:
            _release_guard_strict(guard)
        except (P1SequenceSeed20260612PatchError, OSError) as exc:
            cleanup_errors.append(exc)
    guard_release_failed = len(cleanup_errors) > guard_errors_before
    final_validation_failed = False
    if succeeded and not guard_release_failed:
        for owner in owners:
            try:
                if not hardened._owned(owner):
                    raise P1SequenceSeed20260612PatchError(
                        "E0-MH published output changed after guard release"
                    )
            except (
                P1SequenceSeed20260612PatchError,
                hardened.DevelopmentRuntimeTemporalConsumerPatchError,
                OSError,
            ) as exc:
                cleanup_errors.append(exc)
                final_validation_failed = True
    if succeeded and (guard_release_failed or final_validation_failed):
        rollback_outputs()
    close_errors: list[Exception] = []
    for owner in reversed(owners):
        try:
            os.close(owner.directory_file_descriptor)
        except OSError as exc:
            close_errors.append(exc)
    if not succeeded or guard_release_failed or final_validation_failed:
        cleanup_errors.extend(close_errors)
    if cleanup_errors:
        cleanup_error = P1SequenceSeed20260612PatchError(
            "E0-MH lock resource cleanup failed closed"
        )
        cleanup_error.add_note(
            "Cleanup failures: "
            + "; ".join(
                f"{type(error).__name__}: {error}" for error in cleanup_errors
            )
        )
        if active_error is not None:
            raise cleanup_error from active_error
        raise cleanup_error from cleanup_errors[0]


def _execute_lock(output: Path, companion: Path) -> dict[str, Any]:
    # Schema-definition safety must precede guards, remote checks, and commands.
    schema_preflight = _preflight_schema()
    lock_path = _closed_output(output, DEFAULT_PATCH_LOCK_PATH)
    companion_path = _closed_output(companion, DEFAULT_PATCH_MANIFEST_PATH)
    guards = _acquire_guards(lock_path, companion_path)
    owners: list[Any] = []
    succeeded = False
    result: dict[str, Any] | None = None
    active_error: BaseException | None = None
    try:
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)
        prelock = collect_p1_sequence_seed_20260612_patch_prelock_state(
            verify_remote=True
        )
        verification = run_p1_sequence_seed_20260612_patch_verification(
            expected_schema_preflight=schema_preflight
        )
        p1_sequence_namespace_absence()
        closure_progression_namespace_absence()
        repeated = collect_p1_sequence_seed_20260612_patch_prelock_state(
            verify_remote=True
        )
        if repeated != prelock:
            raise P1SequenceSeed20260612PatchError(
                "E0-MH authority changed during verification"
            )
        if _preflight_schema() != schema_preflight:
            raise P1SequenceSeed20260612PatchError(
                "E0-MH schema changed during verification"
            )
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)

        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload = build_p1_sequence_seed_20260612_patch_lock_payload(
            prelock,
            verification,
            created_at_utc=timestamp,
        )
        schema = _load_regular_json(DEFAULT_PATCH_LOCK_SCHEMA, context="E0-MH schema")
        validate_p1_sequence_seed_20260612_patch_lock_payload(payload, schema)

        lock_owner = _publish_guarded_bytes(
            _canonical_json(payload),
            lock_path,
            DEFAULT_PATCH_LOCK_PATH,
            guards[0],
        )
        owners.append(lock_owner)
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)
        lock_record = hardened._owned_file_record(
            lock_owner,
            role="external_p1_sequence_seed_20260612_patch_lock",
        )
        companion_payload = _expected_companion(payload, lock_record=lock_record)
        companion_owner = _publish_guarded_bytes(
            _canonical_json(companion_payload),
            companion_path,
            DEFAULT_PATCH_MANIFEST_PATH,
            guards[1],
        )
        owners.append(companion_owner)
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)
        companion_record = hardened._owned_file_record(
            companion_owner,
            role="p1_sequence_seed_20260612_patch_companion",
        )
        _load_unpublished_p1_sequence_seed_20260612_patch_lock()
        p1_sequence_namespace_absence()
        closure_progression_namespace_absence()
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)
        result = {
            "status": "locked_unpublished",
            "gate": "E0-MH",
            "patch_head": payload["patch_repository"]["head"],
            "lock": lock_record,
            "companion": companion_record,
            "authorized_model_id": AUTHORIZED_MODEL_ID,
            "authorized_base_seed": AUTHORIZED_BASE_SEED,
            "prior_p1_1729_slot_completed": True,
            "p1_sequence_builder_authorized": False,
            "authorization_effective": False,
            "batch_seed_execution_authorized": False,
            "retry_authorized": False,
            "p1_consumer_authorized": False,
            "publication_required": True,
            "p1_fit_authorized": False,
            "dvc_commands_authorized": False,
            "e0_m_authorized": False,
            "evaluation_authorized": False,
            "e0_u_authorized": False,
            "future_outcomes_accessed": False,
            "writes_performed": True,
            "verification_commands_run": True,
            "dvc_commands_run": False,
            "network_commands_run": True,
            "outcome_paths_opened": False,
        }
        succeeded = True
    except BaseException as exc:
        active_error = exc
    try:
        _cleanup_lock_resources(
            owners,
            guards,
            succeeded=succeeded,
            active_error=active_error,
        )
    except BaseException as exc:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH lock transaction cleanup failed closed"
        ) from exc
    if active_error is not None:
        if isinstance(active_error, P1SequenceSeed20260612PatchError):
            raise active_error
        raise P1SequenceSeed20260612PatchError(
            "E0-MH lock transaction failed"
        ) from active_error
    if result is None:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH lock transaction produced no result"
        )
    return result


def _check_only(output: Path, companion: Path) -> dict[str, Any]:
    schema_preflight = _preflight_schema()
    _refuse_existing_outputs(output, companion)
    prelock = collect_p1_sequence_seed_20260612_patch_prelock_state(
        verify_remote=True
    )
    return {
        "status": "ready_to_lock",
        "gate": "E0-MH",
        "schema_subset_preflight": schema_preflight,
        "patch_repository": prelock["patch_repository"],
        "patch_component_count": prelock["patch_components"]["count"],
        "sequence_prelock": prelock["sequence_prelock"],
        "progression_prelock": prelock["progression_prelock"],
        "prior_p1_1729_slot_completed": True,
        "p1_sequence_builder_authorized": False,
        "retry_authorized": False,
        "writes_performed": False,
        "verification_commands_run": False,
        "dvc_commands_run": False,
        "network_commands_run": True,
        "outcome_paths_opened": False,
    }


def _regular_final_identity(
    directory_descriptor: int,
    name: str,
    *,
    context: str,
) -> tuple[int, int, int, str]:
    if Path(name).name != name or name in {"", ".", ".."}:
        raise P1SequenceSeed20260612PatchError(
            f"{context} name escaped its anchored parent"
        )
    try:
        metadata = os.stat(
            name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise P1SequenceSeed20260612PatchError(
            f"{context} is absent or unreadable"
        ) from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise P1SequenceSeed20260612PatchError(
            f"{context} must be a regular non-symlink file"
        )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=directory_descriptor)
    except OSError as exc:
        raise P1SequenceSeed20260612PatchError(
            f"{context} cannot be opened without following links"
        ) from exc
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise P1SequenceSeed20260612PatchError(
                f"{context} changed while opening"
            )
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        completed = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        final = os.stat(
            name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise P1SequenceSeed20260612PatchError(
            f"{context} disappeared while hashing"
        ) from exc
    identity = (metadata.st_dev, metadata.st_ino)
    if (
        (completed.st_dev, completed.st_ino) != identity
        or (final.st_dev, final.st_ino) != identity
        or size != metadata.st_size
        or size != completed.st_size
        or size != final.st_size
    ):
        raise P1SequenceSeed20260612PatchError(
            f"{context} changed while hashing"
        )
    return metadata.st_dev, metadata.st_ino, size, digest.hexdigest()


def _open_effective_bundle_parent() -> int:
    try:
        return hardened._open_repo_directory(
            DEFAULT_PATCH_LOCK_PATH.parent,
            context="E0-MH effective bundle parent",
        )
    except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceSeed20260612PatchError(str(exc)) from exc


def _require_effective_parent_current(directory_descriptor: int) -> None:
    try:
        current_descriptor = hardened._open_repo_directory(
            DEFAULT_PATCH_LOCK_PATH.parent,
            context="E0-MH current effective bundle parent",
        )
    except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceSeed20260612PatchError(str(exc)) from exc
    try:
        anchored = os.fstat(directory_descriptor)
        current = os.fstat(current_descriptor)
    except OSError as exc:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH effective bundle parent could not be inspected"
        ) from exc
    finally:
        os.close(current_descriptor)
    if (
        not stat.S_ISDIR(anchored.st_mode)
        or not stat.S_ISDIR(current.st_mode)
        or (anchored.st_dev, anchored.st_ino) != (current.st_dev, current.st_ino)
    ):
        raise P1SequenceSeed20260612PatchError(
            "E0-MH effective bundle parent identity changed"
        )


def _anchored_entry_exists(directory_descriptor: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH effective bundle residual could not be inspected"
        ) from exc
    return True


def _effective_bundle_identities(
    directory_descriptor: int,
    lock_path: Path,
    companion_path: Path,
) -> tuple[tuple[int, int, int, str], tuple[int, int, int, str]]:
    anchored_residuals = (
        lock_path.name + ".tmp",
        companion_path.name + ".tmp",
    )
    existing = [
        str(lock_path.parent / name)
        for name in anchored_residuals
        if _anchored_entry_exists(directory_descriptor, name)
    ]
    guard_paths = _guard_paths(create_directory=False)
    existing.extend(str(path) for path in guard_paths if os.path.lexists(path))
    if existing:
        raise P1SequenceSeed20260612PatchError(
            f"E0-MH effective preflight found temporary or guard paths: {existing}"
        )
    return (
        _regular_final_identity(
            directory_descriptor,
            lock_path.name,
            context="E0-MH lock",
        ),
        _regular_final_identity(
            directory_descriptor,
            companion_path.name,
            context="E0-MH companion",
        ),
    )


def _require_anchored_authorization_inputs(
    identities: tuple[
        tuple[int, int, int, str],
        tuple[int, int, int, str],
    ],
    summary: Mapping[str, Any],
) -> None:
    raw_inputs = summary.get("authorization_inputs")
    if (
        not isinstance(raw_inputs, Sequence)
        or isinstance(raw_inputs, (str, bytes))
        or len(raw_inputs) != 2
        or not all(isinstance(record, Mapping) for record in raw_inputs)
    ):
        raise P1SequenceSeed20260612PatchError(
            "E0-MH effective authority inputs drifted"
        )
    records = {
        str(record.get("path")): record
        for record in raw_inputs
        if isinstance(record, Mapping)
    }
    expected = (
        (
            DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "external_p1_sequence_seed_20260612_patch_lock",
            identities[0],
        ),
        (
            DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
            "p1_sequence_seed_20260612_patch_companion",
            identities[1],
        ),
    )
    if set(records) != {path for path, _role, _identity in expected}:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH effective authority input paths drifted"
        )
    for path, role, identity in expected:
        record = records[path]
        if (
            set(record) != {"path", "role", "bytes", "sha256"}
            or record.get("role") != role
            or record.get("bytes") != identity[2]
            or record.get("sha256") != identity[3]
        ):
            raise P1SequenceSeed20260612PatchError(
                f"E0-MH anchored authority input differs from loader: {path}"
            )


def _check_effective(output: Path, companion: Path) -> dict[str, Any]:
    schema_preflight = _preflight_schema()
    lock_path = _closed_output(output, DEFAULT_PATCH_LOCK_PATH)
    companion_path = _closed_output(companion, DEFAULT_PATCH_MANIFEST_PATH)
    if lock_path.parent != companion_path.parent:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH lock and companion escaped their shared parent"
        )
    directory_descriptor = _open_effective_bundle_parent()
    try:
        _require_effective_parent_current(directory_descriptor)
        before = _effective_bundle_identities(
            directory_descriptor,
            lock_path,
            companion_path,
        )
        summary = require_p1_sequence_seed_20260612_authorized(
            model_id=AUTHORIZED_MODEL_ID,
            base_seed=AUTHORIZED_BASE_SEED,
        )
        _require_effective_parent_current(directory_descriptor)
        after = _effective_bundle_identities(
            directory_descriptor,
            lock_path,
            companion_path,
        )
        _require_effective_parent_current(directory_descriptor)
    finally:
        os.close(directory_descriptor)
    if before != after:
        raise P1SequenceSeed20260612PatchError(
            "E0-MH lock bundle changed during effective preflight"
        )
    _require_anchored_authorization_inputs(after, summary)
    p1_sequence_namespace_absence()
    closure_progression_namespace_absence()
    return {
        "status": "effective_preflight_passed",
        "gate": "E0-MH",
        "schema_subset_preflight": schema_preflight,
        "authorization": summary,
        "authorized_model_id": AUTHORIZED_MODEL_ID,
        "authorized_base_seed": AUTHORIZED_BASE_SEED,
        "prior_p1_1729_slot_completed": True,
        "p1_sequence_builder_authorized": True,
        "batch_seed_execution_authorized": False,
        "retry_authorized": False,
        "p1_consumer_authorized": False,
        "p1_fit_authorized": False,
        "dvc_commands_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "writes_performed": False,
        "verification_commands_run": False,
        "dvc_commands_run": False,
        "network_commands_run": True,
        "outcome_paths_opened": False,
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--execute-lock", action="store_true")
    mode.add_argument("--check-effective", action="store_true")
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
    elif args.execute_lock:
        result = _execute_lock(args.output, args.companion_output)
    else:
        result = _check_effective(args.output, args.companion_output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
