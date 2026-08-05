#!/usr/bin/env python
"""Create the one-time additive Closure V1 E0-DLTVM lock bundle."""

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

from src.experiments.closure_development_runtime_temporal_validation_manifest_patch import (
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
    DevelopmentRuntimeTemporalValidationManifestPatchError,
    _expected_companion,
    _load_regular_json,
    build_temporal_validation_manifest_patch_lock_payload,
    collect_temporal_validation_manifest_patch_prelock_state,
    load_and_validate_development_runtime_temporal_validation_manifest_patch_lock,
    validate_development_runtime_temporal_validation_manifest_patch_lock_payload,
)
from src.experiments.closure_development_runtime_temporal_consumer_patch import (
    consumer_namespace_absence,
)
from src.experiments import lock_closure_development_runtime_temporal_consumer_patch as hardened


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_GUARD_DIRECTORY = PROJECT_ROOT / "tmp" / "closure_v1_e0_dltvm_locker"
OUTPUT_GUARD_NAMES = (
    "development_runtime_temporal_validation_manifest_patch_lock.guard",
    "development_runtime_temporal_validation_manifest_patch_lock_manifest.guard",
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
    environment: Mapping[str, str] | None = None,
    sanitize_pytest_environment: bool = False,
) -> tuple[dict[str, Any], str, str]:
    try:
        return hardened._run_command(
            command,
            environment=environment,
            sanitize_pytest_environment=sanitize_pytest_environment,
        )
    except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise DevelopmentRuntimeTemporalValidationManifestPatchError(str(exc)) from exc


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
        raise DevelopmentRuntimeTemporalValidationManifestPatchError(
            "E0-DLTVM focused pytest summary is not one exact clean result"
        )
    return FOCUSED_TEST_COUNT


def _require_fixed_venv_executable(command: Sequence[str]) -> None:
    try:
        hardened._require_fixed_venv_executable(command)
    except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise DevelopmentRuntimeTemporalValidationManifestPatchError(str(exc)) from exc


def _require_success_marker(stdout: str, stderr: str, marker: str) -> None:
    if marker not in stdout + "\n" + stderr:
        raise DevelopmentRuntimeTemporalValidationManifestPatchError(
            f"E0-DLTVM verification marker is absent: {marker}"
        )


def _require_empty_output(stdout: str, stderr: str, *, context: str) -> None:
    if stdout.strip() or stderr.strip():
        raise DevelopmentRuntimeTemporalValidationManifestPatchError(
            f"E0-DLTVM expected empty output from {context}"
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
        raise DevelopmentRuntimeTemporalValidationManifestPatchError(
            "E0-DLTVM targeted DVC push is not exactly idempotent"
        )
    return marker


def run_temporal_validation_manifest_patch_verification() -> dict[str, Any]:
    """Run the closed H-DLTVM verification set; this is intentionally heavy."""
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
    first, stdout, stderr = _run_command(
        DVC_PUSH_COMMAND,
        environment=dvc_environment,
    )
    first["terminal_status"] = _terminal_status(stdout, stderr)
    second, stdout, stderr = _run_command(
        DVC_PUSH_COMMAND,
        environment=dvc_environment,
    )
    second["terminal_status"] = _terminal_status(stdout, stderr)
    return {
        "full_type_check": type_check,
        "focused_tests": focused,
        "poetry_check": poetry_check,
        "publication_guard": publication_guard,
        "git_diff_check": diff_check,
        "dvc_push_first": first,
        "dvc_push_second": second,
    }


def _closed_output(path: Path, expected: Path) -> Path:
    try:
        return hardened._closed_output(path, expected)
    except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise DevelopmentRuntimeTemporalValidationManifestPatchError(str(exc)) from exc


def _guard_paths(*, create_directory: bool) -> tuple[Path, Path]:
    tmp_root = PROJECT_ROOT / "tmp"
    if OUTPUT_GUARD_DIRECTORY != tmp_root / "closure_v1_e0_dltvm_locker":
        raise DevelopmentRuntimeTemporalValidationManifestPatchError(
            "E0-DLTVM coordination directory escaped ignored tmp/"
        )
    for path, context in (
        (tmp_root, "E0-DLTVM tmp root"),
        (OUTPUT_GUARD_DIRECTORY, "E0-DLTVM guard directory"),
    ):
        if not os.path.lexists(path):
            continue
        try:
            descriptor = hardened._open_real_directory(path, context=context)
        except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
            raise DevelopmentRuntimeTemporalValidationManifestPatchError(str(exc)) from exc
        else:
            os.close(descriptor)
    if create_directory:
        hardened._ensure_real_directory(
            tmp_root,
            parent=PROJECT_ROOT,
            context="E0-DLTVM tmp root",
        )
        hardened._ensure_real_directory(
            OUTPUT_GUARD_DIRECTORY,
            parent=tmp_root,
            context="E0-DLTVM guard directory",
        )
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
        raise DevelopmentRuntimeTemporalValidationManifestPatchError(
            f"Refusing to overwrite an existing E0-DLTVM lock bundle: {existing}"
        )


def _acquire_guards(output: Path, companion: Path) -> tuple[Any, ...]:
    _refuse_existing_outputs(output, companion)
    guards: list[Any] = []
    try:
        for path in _guard_paths(create_directory=True):
            guards.append(hardened._open_guard(path))
    except BaseException:
        for guard in reversed(guards):
            hardened._release_guard(guard)
        raise
    return tuple(guards)


def _execute_lock(output: Path, companion: Path) -> dict[str, Any]:
    lock_path = _closed_output(output, DEFAULT_PATCH_LOCK_PATH)
    companion_path = _closed_output(companion, DEFAULT_PATCH_MANIFEST_PATH)
    guards = _acquire_guards(lock_path, companion_path)
    owners: list[Any] = []
    succeeded = False
    try:
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)
        prelock = collect_temporal_validation_manifest_patch_prelock_state(
            require_physical_artifacts=True,
            verify_remote=True,
        )
        verification = run_temporal_validation_manifest_patch_verification()
        consumer_namespace_absence()
        repeated = collect_temporal_validation_manifest_patch_prelock_state(
            require_physical_artifacts=True,
            verify_remote=True,
        )
        if repeated != prelock:
            raise DevelopmentRuntimeTemporalValidationManifestPatchError(
                "E0-DLTVM authority changed during verification"
            )
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)

        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload = build_temporal_validation_manifest_patch_lock_payload(
            prelock,
            verification,
            created_at_utc=timestamp,
        )
        schema = _load_regular_json(DEFAULT_PATCH_LOCK_SCHEMA, context="E0-DLTVM schema")
        validate_development_runtime_temporal_validation_manifest_patch_lock_payload(
            payload,
            schema,
            require_physical_artifacts=True,
        )

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
            role="external_development_runtime_temporal_validation_dialect_patch_lock",
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
            role="development_runtime_temporal_validation_manifest_patch_companion",
        )
        load_and_validate_development_runtime_temporal_validation_manifest_patch_lock(
            require_published=False,
            require_physical_artifacts=True,
        )
        consumer_namespace_absence()
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)
        result = {
            "status": "locked_unpublished",
            "gate": "E0-DLTVM",
            "patch_head": payload["patch_repository"]["head"],
            "lock": lock_record,
            "companion": companion_record,
            "builder_provenance": payload["builder_provenance"],
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
        hardened._cleanup_lock_resources(
            owners,
            guards,
            succeeded=succeeded,
            active_error=sys.exc_info()[1],
        )


def _check_only(output: Path, companion: Path) -> dict[str, Any]:
    _refuse_existing_outputs(output, companion)
    prelock = collect_temporal_validation_manifest_patch_prelock_state(
        require_physical_artifacts=True,
        verify_remote=True,
    )
    return {
        "status": "ready_to_lock",
        "gate": "E0-DLTVM",
        "patch_repository": prelock["patch_repository"],
        "patch_component_count": prelock["patch_components"]["count"],
        "builder_provenance": prelock["builder_provenance"],
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
    result = (
        _check_only(args.output, args.companion_output)
        if args.check_only
        else _execute_lock(args.output, args.companion_output)
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
