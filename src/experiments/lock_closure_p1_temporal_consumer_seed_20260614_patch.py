#!/usr/bin/env python
"""Create and verify the additive Closure V1 E0-MM lock bundle."""

from __future__ import annotations

import argparse
import json
import os
import re
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
from src.experiments.closure_p1_temporal_consumer_seed_20260614_patch import (  # noqa: E402
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
    P1TemporalConsumerSeed20260614PatchError,
    _canonical_json,
    _expected_companion,
    _file_record,
    _load_regular_json,
    build_p1_temporal_consumer_seed_20260614_patch_lock_payload,
    collect_p1_temporal_consumer_seed_20260614_patch_prelock_state,
    load_and_validate_p1_temporal_consumer_seed_20260614_patch_lock,
    p1_consumer_namespace_absence,
    preflight_p1_temporal_consumer_seed_20260614_patch_schema,
    require_p1_temporal_consumer_seed_20260614_patch_authorized,
    run_p1_bundle_audit_in_process,
    validate_p1_temporal_consumer_seed_20260614_patch_lock_payload,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_GUARD_DIRECTORY = PROJECT_ROOT / "tmp" / "closure_v1_e0_mm_locker"
OUTPUT_GUARD_NAMES = (
    "p1_temporal_consumer_seed_20260614_patch_lock.guard",
    "p1_temporal_consumer_seed_20260614_patch_lock_manifest.guard",
)
SCHEMA_PREFLIGHT_FIELDS = frozenset(
    {
        "gate",
        "schema_path",
        "schema_bytes",
        "schema_sha256",
        "supported_subset_verified",
        "minimum_keyword_absent",
        "format_keyword_absent",
    }
)
FORBIDDEN_PYTEST_SUMMARY_RE = re.compile(
    r"\b(?:warnings?|skipped|deselected|xfailed|xpassed|errors?|failed)\b",
    flags=re.IGNORECASE,
)


def _translate(error: BaseException) -> P1TemporalConsumerSeed20260614PatchError:
    return P1TemporalConsumerSeed20260614PatchError(str(error))


def _run_command(
    command: Sequence[str],
    *,
    sanitize_pytest_environment: bool = False,
    environment: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], str, str]:
    try:
        return hardened._run_command(
            command,
            sanitize_pytest_environment=sanitize_pytest_environment,
            environment=environment,
        )
    except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise _translate(exc) from exc


def _require_success_marker(stdout: str, stderr: str, marker: str) -> None:
    if marker not in stdout + "\n" + stderr:
        raise P1TemporalConsumerSeed20260614PatchError(
            f"E0-MM verification marker is absent: {marker}"
        )


def _require_empty_output(stdout: str, stderr: str, *, context: str) -> None:
    if stdout.strip() or stderr.strip():
        raise P1TemporalConsumerSeed20260614PatchError(
            f"E0-MM expected empty output from {context}"
        )


def _preflight_schema() -> dict[str, Any]:
    """Prove the physical MK schema uses the repository's supported subset."""
    observed = preflight_p1_temporal_consumer_seed_20260614_patch_schema()
    if not isinstance(observed, Mapping) or set(observed) != SCHEMA_PREFLIGHT_FIELDS:
        raise P1TemporalConsumerSeed20260614PatchError(
            "E0-MM schema-subset preflight evidence is malformed"
        )
    result = dict(observed)
    digest = result.get("schema_sha256")
    size = result.get("schema_bytes")
    if (
        result.get("gate") != "E0-MM"
        or result.get("schema_path") != DEFAULT_PATCH_LOCK_SCHEMA.as_posix()
        or type(size) is not int
        or size <= 0
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
        or result.get("supported_subset_verified") is not True
        or result.get("minimum_keyword_absent") is not True
        or result.get("format_keyword_absent") is not True
    ):
        raise P1TemporalConsumerSeed20260614PatchError(
            "E0-MM schema-subset preflight evidence drifted"
        )
    return result


def _parse_focused_summary(stdout: str, stderr: str) -> dict[str, Any]:
    """Parse exactly pytest 9.0.3's short or timedelta terminal summary."""
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    summary_re = re.compile(
        r"^(?P<count>[1-9][0-9]*) passed in "
        r"(?P<duration>[0-9]+\.[0-9]{2})s"
        r"(?: \((?P<clock>(?:[0-9]+ days?, )?[0-9]+:[0-9]{2}:[0-9]{2})\))?$"
    )
    summary_like_re = re.compile(r"^[1-9][0-9]* passed in .+$")
    matches = [line for line in lines if summary_re.fullmatch(line)]
    summary_like = [line for line in lines if summary_like_re.fullmatch(line)]
    combined = stdout + "\n" + stderr
    if (
        FOCUSED_TEST_COUNT <= 0
        or stderr.strip()
        or not lines
        or len(matches) != 1
        or summary_like != matches
        or matches[0] != lines[-1]
        or FORBIDDEN_PYTEST_SUMMARY_RE.search(combined) is not None
    ):
        raise P1TemporalConsumerSeed20260614PatchError(
            "E0-MM focused pytest summary is not one exact clean result"
        )
    match = summary_re.fullmatch(matches[0])
    if match is None or int(match.group("count")) != FOCUSED_TEST_COUNT:
        raise P1TemporalConsumerSeed20260614PatchError(
            "E0-MM focused pytest count drifted"
        )
    duration_text = match.group("duration")
    clock = match.group("clock")
    try:
        duration = Decimal(duration_text)
    except InvalidOperation as exc:
        raise P1TemporalConsumerSeed20260614PatchError(
            "E0-MM focused pytest duration is malformed"
        ) from exc
    try:
        expected_clock = str(timedelta(seconds=int(duration)))
    except OverflowError as exc:
        raise P1TemporalConsumerSeed20260614PatchError(
            "E0-MM focused pytest duration is out of range"
        ) from exc
    if duration < Decimal(60):
        if clock is not None:
            raise P1TemporalConsumerSeed20260614PatchError(
                "E0-MM sub-minute pytest summary must not include a clock"
            )
        summary_format = "pytest_short"
    else:
        if clock != expected_clock:
            raise P1TemporalConsumerSeed20260614PatchError(
                "E0-MM long pytest summary clock drifted"
            )
        summary_format = "pytest_timedelta"
    return {
        "test_count": FOCUSED_TEST_COUNT,
        "skipped_count": 0,
        "deselected_count": 0,
        "summary_format": summary_format,
        "duration_seconds": duration_text,
        "duration_clock": clock,
    }


def _dvc_terminal_status(
    stdout: str,
    stderr: str,
    *,
    require_idempotent: bool,
) -> str:
    lines = [line.strip() for line in (stdout + "\n" + stderr).splitlines() if line.strip()]
    allowed = {"Everything is up to date.", "1 file pushed"}
    terminals = [line for line in lines if line in allowed]
    if len(terminals) != 1 or (
        require_idempotent and terminals[0] != "Everything is up to date."
    ):
        raise P1TemporalConsumerSeed20260614PatchError(
            "E0-MM targeted DVC push is not one closed idempotent terminal"
        )
    if any(
        re.fullmatch(r"[2-9][0-9]* files? pushed", line)
        or re.fullmatch(r"1[0-9]+ files? pushed", line)
        for line in lines
    ):
        raise P1TemporalConsumerSeed20260614PatchError(
            "E0-MM targeted DVC push exceeded one object"
        )
    return terminals[0]


def run_p1_temporal_consumer_seed_20260614_patch_verification(
    *,
    expected_schema_preflight: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the closed E0-MM verification only after a live schema preflight."""
    schema_preflight = _preflight_schema()
    if (
        expected_schema_preflight is not None
        and dict(expected_schema_preflight) != schema_preflight
    ):
        raise P1TemporalConsumerSeed20260614PatchError(
            "E0-MM schema changed before verification"
        )
    if FOCUSED_TEST_COUNT <= 0:
        raise P1TemporalConsumerSeed20260614PatchError(
            "E0-MM focused-test count has not been finalized"
        )
    try:
        hardened._require_fixed_venv_executable(TYPE_CHECK_COMMAND)
        hardened._require_fixed_venv_executable(FOCUSED_TEST_COMMAND)
        hardened._require_fixed_venv_executable(DVC_PUSH_COMMAND)
    except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise _translate(exc) from exc

    type_check, stdout, stderr = _run_command(TYPE_CHECK_COMMAND)
    _require_success_marker(stdout, stderr, "All checks passed!")

    focused, stdout, stderr = _run_command(
        FOCUSED_TEST_COMMAND,
        sanitize_pytest_environment=True,
    )
    focused.update(_parse_focused_summary(stdout, stderr))
    poetry_check, stdout, stderr = _run_command(POETRY_CHECK_COMMAND)
    _require_success_marker(stdout, stderr, "All set!")
    publication_guard, _, _ = _run_command(PUBLICATION_GUARD_COMMAND)
    diff_check, stdout, stderr = _run_command(DIFF_CHECK_COMMAND)
    _require_empty_output(stdout, stderr, context="git diff --check")

    audit_evidence = run_p1_bundle_audit_in_process()

    dvc_environment = {"DVC_NO_ANALYTICS": "1"}
    dvc_first, stdout, stderr = _run_command(
        DVC_PUSH_COMMAND,
        environment=dvc_environment,
    )
    dvc_first["terminal_status"] = _dvc_terminal_status(
        stdout,
        stderr,
        require_idempotent=False,
    )
    dvc_second, stdout, stderr = _run_command(
        DVC_PUSH_COMMAND,
        environment=dvc_environment,
    )
    dvc_second["terminal_status"] = _dvc_terminal_status(
        stdout,
        stderr,
        require_idempotent=True,
    )
    return {
        "schema_subset_preflight": schema_preflight,
        "full_type_check": type_check,
        "focused_tests": focused,
        "poetry_check": poetry_check,
        "publication_guard": publication_guard,
        "git_diff_check": diff_check,
        "p1_bundle_audit": audit_evidence,
        "dvc_push_first": dvc_first,
        "dvc_push_second": dvc_second,
    }


def _closed_output(path: Path, expected: Path) -> Path:
    try:
        return hardened._closed_output(path, expected)
    except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise _translate(exc) from exc


def _guard_paths(*, create_directory: bool) -> tuple[Path, Path]:
    tmp_root = PROJECT_ROOT / "tmp"
    if OUTPUT_GUARD_DIRECTORY != tmp_root / "closure_v1_e0_mm_locker":
        raise P1TemporalConsumerSeed20260614PatchError(
            "E0-MM coordination directory escaped ignored tmp/"
        )
    if create_directory:
        try:
            hardened._ensure_real_directory(
                tmp_root,
                parent=PROJECT_ROOT,
                context="E0-MM tmp root",
            )
            hardened._ensure_real_directory(
                OUTPUT_GUARD_DIRECTORY,
                parent=tmp_root,
                context="E0-MM guard directory",
            )
        except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
            raise _translate(exc) from exc
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
        raise P1TemporalConsumerSeed20260614PatchError(
            f"Refusing to overwrite an existing E0-MM lock bundle: {existing}"
        )


def _acquire_guards(
    output: Path,
    companion: Path,
) -> tuple[hardened._OutputGuard, hardened._OutputGuard]:
    _refuse_existing_outputs(output, companion)
    guards: list[hardened._OutputGuard] = []
    try:
        for path in _guard_paths(create_directory=True):
            guards.append(hardened._open_guard(path))
    except BaseException as exc:
        for guard in reversed(guards):
            hardened._release_guard(guard)
        if isinstance(exc, hardened.DevelopmentRuntimeTemporalConsumerPatchError):
            raise _translate(exc) from exc
        raise
    if len(guards) != 2:
        raise P1TemporalConsumerSeed20260614PatchError(
            "E0-MM requires exactly two guards"
        )
    return guards[0], guards[1]


def _execute_lock(output: Path, companion: Path) -> dict[str, Any]:
    # This must precede guards, prelock collection, commands, audit, and DVC.
    schema_preflight = _preflight_schema()
    lock_path = _closed_output(output, DEFAULT_PATCH_LOCK_PATH)
    companion_path = _closed_output(companion, DEFAULT_PATCH_MANIFEST_PATH)
    guards = _acquire_guards(output, companion)
    owners: list[hardened._OwnedFile] = []
    succeeded = False
    result: dict[str, Any] | None = None
    active_error: BaseException | None = None
    try:
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)
        prelock = collect_p1_temporal_consumer_seed_20260614_patch_prelock_state(
            verify_remote=True
        )
        verification = run_p1_temporal_consumer_seed_20260614_patch_verification(
            expected_schema_preflight=schema_preflight
        )
        p1_consumer_namespace_absence()
        repeated = collect_p1_temporal_consumer_seed_20260614_patch_prelock_state(
            verify_remote=True
        )
        if repeated != prelock:
            raise P1TemporalConsumerSeed20260614PatchError(
                "E0-MM authority changed during verification"
            )
        repeated_schema_preflight = _preflight_schema()
        if repeated_schema_preflight != schema_preflight:
            raise P1TemporalConsumerSeed20260614PatchError(
                "E0-MM schema changed during verification"
            )
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload = build_p1_temporal_consumer_seed_20260614_patch_lock_payload(
            prelock,
            verification,
            created_at_utc=timestamp,
        )
        schema = _load_regular_json(DEFAULT_PATCH_LOCK_SCHEMA, context="E0-MM schema")
        validate_p1_temporal_consumer_seed_20260614_patch_lock_payload(
            payload,
            schema,
            require_physical_audit=False,
        )
        try:
            lock_owner = hardened._publish_guarded_bytes(
                _canonical_json(payload),
                lock_path,
                DEFAULT_PATCH_LOCK_PATH,
                guards[0],
            )
        except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
            raise _translate(exc) from exc
        owners.append(lock_owner)
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)
        lock_record = hardened._owned_file_record(
            lock_owner,
            role="external_p1_temporal_consumer_seed_20260614_patch_lock",
        )
        companion_payload = _expected_companion(payload, lock_record=lock_record)
        try:
            companion_owner = hardened._publish_guarded_bytes(
                _canonical_json(companion_payload),
                companion_path,
                DEFAULT_PATCH_MANIFEST_PATH,
                guards[1],
            )
        except hardened.DevelopmentRuntimeTemporalConsumerPatchError as exc:
            raise _translate(exc) from exc
        owners.append(companion_owner)
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)
        companion_record = hardened._owned_file_record(
            companion_owner,
            role="p1_temporal_consumer_seed_20260614_patch_companion",
        )
        load_and_validate_p1_temporal_consumer_seed_20260614_patch_lock(
            require_published=False,
            verify_remote=False,
        )
        p1_consumer_namespace_absence()
        hardened._assert_lock_namespace(lock_path, companion_path, guards, owners)
        result = {
            "status": "locked_unpublished",
            "gate": "E0-MM",
            "patch_head": payload["patch_repository"]["head"],
            "lock": lock_record,
            "companion": companion_record,
            "schema_subset_preflight": schema_preflight,
            "auditor_execution_mode": "in_process_callable",
            "python_auditor_subprocess_used": False,
            "p1_consumer_authorized": False,
            "p1_fit_authorized": False,
            "sequence_fit_available": False,
            "publication_required": True,
            "e0_m_authorized": False,
            "evaluation_authorized": False,
            "e0_u_authorized": False,
            "future_outcomes_accessed": False,
        }
        succeeded = True
    except BaseException as exc:
        active_error = exc
    try:
        hardened._cleanup_lock_resources(
            owners,
            guards,
            succeeded=succeeded,
            active_error=active_error,
        )
    except BaseException as exc:
        raise P1TemporalConsumerSeed20260614PatchError(
            "E0-MM lock transaction cleanup failed closed"
        ) from exc
    if active_error is not None:
        if isinstance(active_error, P1TemporalConsumerSeed20260614PatchError):
            raise active_error
        raise P1TemporalConsumerSeed20260614PatchError(
            "E0-MM lock transaction failed"
        ) from active_error
    if result is None:
        raise P1TemporalConsumerSeed20260614PatchError(
            "E0-MM lock transaction produced no result"
        )
    return result


def _check_only(output: Path, companion: Path) -> dict[str, Any]:
    # Schema definition safety precedes even remote/read-only prelock work.
    schema_preflight = _preflight_schema()
    _refuse_existing_outputs(output, companion)
    prelock = collect_p1_temporal_consumer_seed_20260614_patch_prelock_state(
        verify_remote=True
    )
    return {
        "status": "ready_to_lock",
        "gate": "E0-MM",
        "schema_subset_preflight": schema_preflight,
        "patch_repository": prelock["patch_repository"],
        "patch_component_count": prelock["patch_components"]["count"],
        "historical_e0_mk": prelock["base_authorities"]["e0_mk"],
        "historical_e0_ml": prelock["base_authorities"]["e0_ml"],
        "p1_20260614_publication": prelock["p1_20260614_publication"],
        "consumer_prelock": prelock["consumer_prelock"],
        "progression_prelock": prelock["progression_prelock"],
        "fit_availability": prelock["fit_availability"],
        "auditor_execution_mode": "in_process_callable",
        "p1_consumer_authorized": False,
        "p1_fit_authorized": False,
        "p1_sequence_builder_authorized": False,
        "writes_performed": False,
        "verification_commands_run": False,
        "in_process_audit_run": False,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
    }


def _check_effective(output: Path, companion: Path) -> dict[str, Any]:
    schema_preflight = _preflight_schema()
    _closed_output(output, DEFAULT_PATCH_LOCK_PATH)
    _closed_output(companion, DEFAULT_PATCH_MANIFEST_PATH)
    before = (
        _file_record(
            output,
            role="external_p1_temporal_consumer_seed_20260614_patch_lock",
        ),
        _file_record(
            companion,
            role="p1_temporal_consumer_seed_20260614_patch_companion",
        ),
    )
    summary = require_p1_temporal_consumer_seed_20260614_patch_authorized(
        model_id="P1",
        base_seed=20_260_614,
        device="cpu",
    )
    after = (
        _file_record(
            output,
            role="external_p1_temporal_consumer_seed_20260614_patch_lock",
        ),
        _file_record(
            companion,
            role="p1_temporal_consumer_seed_20260614_patch_companion",
        ),
    )
    if before != after:
        raise P1TemporalConsumerSeed20260614PatchError(
            "E0-MM lock bundle changed during preflight"
        )
    return {
        "status": "effective_preflight_passed",
        "gate": "E0-MM",
        "schema_subset_preflight": schema_preflight,
        "authorization": summary,
        "writes_performed": False,
        "verification_commands_run": False,
        "dvc_commands_run": False,
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
