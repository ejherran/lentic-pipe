#!/usr/bin/env python
"""Create the one-time additive Closure V1 E0-MB lock bundle."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments import (  # noqa: E402
    lock_closure_development_runtime_temporal_consumer_patch as hardened,
)
from src.experiments.closure_p1_sequence_builder_patch import (  # noqa: E402
    DEFAULT_PATCH_LOCK_PATH,
    DEFAULT_PATCH_LOCK_SCHEMA,
    DEFAULT_PATCH_MANIFEST_PATH,
    DIFF_CHECK_COMMAND,
    FOCUSED_TEST_COMMAND,
    FOCUSED_TEST_COUNT,
    POETRY_CHECK_COMMAND,
    PUBLICATION_GUARD_COMMAND,
    TYPE_CHECK_COMMAND,
    P1SequenceBuilderPatchError,
    _expected_companion,
    _load_unpublished_p1_sequence_builder_patch_lock,
    _load_regular_json,
    build_p1_sequence_builder_patch_lock_payload,
    collect_p1_sequence_builder_patch_prelock_state,
    closure_progression_namespace_absence,
    p1_sequence_namespace_absence,
    validate_p1_sequence_builder_patch_lock_payload,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_GUARD_DIRECTORY = PROJECT_ROOT / "tmp" / "closure_v1_e0_mb_locker"
OUTPUT_GUARD_NAMES = (
    "p1_sequence_builder_patch_lock.guard",
    "p1_sequence_builder_patch_lock_manifest.guard",
)
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
        raise P1SequenceBuilderPatchError(str(exc)) from exc


def _parse_focused_summary(stdout: str, stderr: str) -> int:
    combined = stdout + "\n" + stderr
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    summary_re = re.compile(
        rf"^{FOCUSED_TEST_COUNT} passed in [0-9]+(?:\.[0-9]+)?s$"
    )
    matches = [line for line in lines if summary_re.fullmatch(line)]
    if (
        FOCUSED_TEST_COUNT <= 0
        or not lines
        or matches != [lines[-1]]
        or FORBIDDEN_PYTEST_SUMMARY_RE.search(combined) is not None
    ):
        raise P1SequenceBuilderPatchError(
            "E0-MB focused pytest summary is not one exact clean result"
        )
    return FOCUSED_TEST_COUNT


def _require_success_marker(stdout: str, stderr: str, marker: str) -> None:
    if marker not in stdout + "\n" + stderr:
        raise P1SequenceBuilderPatchError(
            f"E0-MB verification marker is absent: {marker}"
        )


def _require_empty_output(stdout: str, stderr: str, *, context: str) -> None:
    if stdout.strip() or stderr.strip():
        raise P1SequenceBuilderPatchError(
            f"E0-MB expected empty output from {context}"
        )


def run_p1_sequence_builder_patch_verification() -> dict[str, Any]:
    """Run the closed H-E0-MB verification set; intentionally heavy."""
    try:
        hardened._require_fixed_venv_executable(TYPE_CHECK_COMMAND)
        hardened._require_fixed_venv_executable(FOCUSED_TEST_COMMAND)
    except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceBuilderPatchError(str(exc)) from exc

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
        raise P1SequenceBuilderPatchError(str(exc)) from exc


def _guard_paths(*, create_directory: bool) -> tuple[Path, Path]:
    tmp_root = PROJECT_ROOT / "tmp"
    if OUTPUT_GUARD_DIRECTORY != tmp_root / "closure_v1_e0_mb_locker":
        raise P1SequenceBuilderPatchError("E0-MB coordination directory escaped tmp/")
    for path, context in (
        (tmp_root, "E0-MB tmp root"),
        (OUTPUT_GUARD_DIRECTORY, "E0-MB guard directory"),
    ):
        if not os.path.lexists(path):
            continue
        try:
            descriptor = hardened._open_real_directory(path, context=context)
        except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
            raise P1SequenceBuilderPatchError(str(exc)) from exc
        else:
            os.close(descriptor)
    if create_directory:
        try:
            hardened._ensure_real_directory(
                tmp_root,
                parent=PROJECT_ROOT,
                context="E0-MB tmp root",
            )
            hardened._ensure_real_directory(
                OUTPUT_GUARD_DIRECTORY,
                parent=tmp_root,
                context="E0-MB guard directory",
            )
        except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
            raise P1SequenceBuilderPatchError(str(exc)) from exc
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
        raise P1SequenceBuilderPatchError(
            f"Refusing to overwrite an existing E0-MB lock bundle: {existing}"
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
        raise P1SequenceBuilderPatchError(
            "E0-MB guard ownership could not be verified before release"
        ) from exc
    release_error: BaseException | None = None
    try:
        hardened._release_guard(guard)
    except (hardened.DevelopmentRuntimeTemporalConsumerPatchError, OSError) as exc:
        release_error = exc
    residual = os.path.lexists(guard.path)
    if not owned_before or residual or release_error is not None:
        error = P1SequenceBuilderPatchError(
            "E0-MB guard release lost ownership or left a residual path"
        )
        if release_error is not None:
            raise error from release_error
        raise error


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
                hardened._unlink_if_owned(owner)
            except (hardened.DevelopmentRuntimeTemporalConsumerPatchError, OSError) as exc:
                cleanup_errors.append(exc)
            try:
                os.fsync(owner.directory_file_descriptor)
            except OSError as exc:
                cleanup_errors.append(exc)

    if not succeeded:
        rollback_outputs()
    guard_errors_before = len(cleanup_errors)
    for guard in reversed(guards):
        try:
            _release_guard_strict(guard)
        except (P1SequenceBuilderPatchError, OSError) as exc:
            cleanup_errors.append(exc)
    guard_release_failed = len(cleanup_errors) > guard_errors_before
    if succeeded and guard_release_failed:
        rollback_outputs()
    close_errors: list[Exception] = []
    for owner in reversed(owners):
        try:
            os.close(owner.directory_file_descriptor)
        except OSError as exc:
            close_errors.append(exc)
    if not succeeded or guard_release_failed:
        cleanup_errors.extend(close_errors)
    if cleanup_errors:
        cleanup_error = P1SequenceBuilderPatchError(
            "E0-MB lock resource cleanup failed closed"
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
    lock_path = _closed_output(output, DEFAULT_PATCH_LOCK_PATH)
    companion_path = _closed_output(companion, DEFAULT_PATCH_MANIFEST_PATH)
    guards = _acquire_guards(lock_path, companion_path)
    owners: list[Any] = []
    succeeded = False
    result: dict[str, Any] | None = None
    active_error: BaseException | None = None
    try:
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)
        prelock = collect_p1_sequence_builder_patch_prelock_state(verify_remote=True)
        verification = run_p1_sequence_builder_patch_verification()
        p1_sequence_namespace_absence()
        closure_progression_namespace_absence()
        repeated = collect_p1_sequence_builder_patch_prelock_state(verify_remote=True)
        if repeated != prelock:
            raise P1SequenceBuilderPatchError(
                "E0-MB authority changed during verification"
            )
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)

        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload = build_p1_sequence_builder_patch_lock_payload(
            prelock,
            verification,
            created_at_utc=timestamp,
        )
        schema = _load_regular_json(DEFAULT_PATCH_LOCK_SCHEMA, context="E0-MB schema")
        validate_p1_sequence_builder_patch_lock_payload(payload, schema)

        lock_owner = hardened._publish_guarded_bytes(
            _canonical_json(payload),
            lock_path,
            DEFAULT_PATCH_LOCK_PATH,
            guards[0],
        )
        owners.append(lock_owner)
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)
        lock_record = hardened._owned_file_record(
            lock_owner,
            role="external_p1_sequence_builder_patch_lock",
        )
        companion_payload = _expected_companion(payload, lock_record=lock_record)
        companion_owner = hardened._publish_guarded_bytes(
            _canonical_json(companion_payload),
            companion_path,
            DEFAULT_PATCH_MANIFEST_PATH,
            guards[1],
        )
        owners.append(companion_owner)
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)
        companion_record = hardened._owned_file_record(
            companion_owner,
            role="p1_sequence_builder_patch_companion",
        )
        _load_unpublished_p1_sequence_builder_patch_lock()
        p1_sequence_namespace_absence()
        closure_progression_namespace_absence()
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)
        result = {
            "status": "locked_unpublished",
            "gate": "E0-MB",
            "patch_head": payload["patch_repository"]["head"],
            "lock": lock_record,
            "companion": companion_record,
            "authorized_model_id": "P1",
            "authorized_base_seed": 1729,
            "p1_sequence_builder_authorized": False,
            "publication_required": True,
            "p1_fit_authorized": False,
            "e0_m_authorized": False,
            "evaluation_authorized": False,
            "e0_u_authorized": False,
            "future_outcomes_accessed": False,
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
        raise P1SequenceBuilderPatchError(
            "E0-MB lock transaction cleanup failed closed"
        ) from exc
    if active_error is not None:
        if isinstance(active_error, P1SequenceBuilderPatchError):
            raise active_error
        raise P1SequenceBuilderPatchError("E0-MB lock transaction failed") from active_error
    if result is None:
        raise P1SequenceBuilderPatchError("E0-MB lock transaction produced no result")
    return result


def _check_only(output: Path, companion: Path) -> dict[str, Any]:
    _refuse_existing_outputs(output, companion)
    prelock = collect_p1_sequence_builder_patch_prelock_state(verify_remote=True)
    return {
        "status": "ready_to_lock",
        "gate": "E0-MB",
        "patch_repository": prelock["patch_repository"],
        "patch_component_count": prelock["patch_components"]["count"],
        "sequence_prelock": prelock["sequence_prelock"],
        "progression_prelock": prelock["progression_prelock"],
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
    parser.add_argument("--output", type=Path, default=DEFAULT_PATCH_LOCK_PATH)
    parser.add_argument(
        "--companion-output",
        type=Path,
        default=DEFAULT_PATCH_MANIFEST_PATH,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result = (
        _check_only(args.output, args.companion_output)
        if args.check_only
        else _execute_lock(args.output, args.companion_output)
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
