#!/usr/bin/env python
"""Check, publish, and audit the E0-MCALI owned-run-guard-revalidation authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments import (  # noqa: E402
    closure_final_calibration_owned_run_guard_revalidation_patch as patch,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_SUMMARY_RE = re.compile(
    r"\b(?:warnings?|skipped|deselected|xfailed|xpassed|errors?|failed)\b",
    flags=re.IGNORECASE,
)


def _error(message: str) -> patch.FinalCalibrationOwnedRunGuardRevalidationPatchError:
    return patch.FinalCalibrationOwnedRunGuardRevalidationPatchError(message)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _command_evidence(
    command: Sequence[str], stdout: str, stderr: str
) -> dict[str, Any]:
    return {
        "command": list(command),
        "returncode": 0,
        "stdout_sha256": _sha256_text(stdout),
        "stderr_sha256": _sha256_text(stderr),
        "stdout_line_count": len(stdout.splitlines()),
        "stderr_line_count": len(stderr.splitlines()),
    }


def _run_command(
    command: Sequence[str], *, sanitize_pytest_environment: bool = False
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
        raise _error(
            f"Verification command failed ({result.returncode}): "
            f"{' '.join(command)}\n{result.stdout}\n{result.stderr}"
        )
    return (
        _command_evidence(command, result.stdout, result.stderr),
        result.stdout,
        result.stderr,
    )


def _require_marker(stdout: str, stderr: str, marker: str, *, context: str) -> None:
    if marker not in stdout + "\n" + stderr:
        raise _error(f"{context} success marker is absent")


def _require_empty_output(stdout: str, stderr: str, *, context: str) -> None:
    if stdout.strip() or stderr.strip():
        raise _error(f"{context} unexpectedly produced output")


def _require_publication_guard_success(stdout: str, stderr: str) -> None:
    expected = [
        "Checking tracked files before publication...",
        "OK: tracked files look publication-ready.",
    ]
    if stderr.strip() or stdout.splitlines() != expected:
        raise _error("publication guard did not emit the exact success result")


def _parse_focused_summary(stdout: str, stderr: str) -> dict[str, int]:
    count = patch.FOCUSED_TEST_COUNT
    if type(count) is not int or count <= 0:
        raise _error("E0-MCALI focused-test count is not frozen")
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
        raise _error("Focused pytest summary is not one clean exact result")
    match = pattern.fullmatch(matches[0])
    if match is None or int(match.group("count")) != count:
        raise _error("Focused pytest count drifted")
    return {"test_count": count, "skipped_count": 0, "deselected_count": 0}


def run_final_calibration_owned_run_guard_revalidation_patch_verification(
    *, expected_schema_preflight: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Run closed repository checks without science, DVC, or egress."""

    schema_preflight = (
        patch.preflight_final_calibration_owned_run_guard_revalidation_patch_schema()
    )
    if (
        expected_schema_preflight is not None
        and dict(expected_schema_preflight) != schema_preflight
    ):
        raise _error("E0-MCALI schema changed before verification")

    full_type_check, stdout, stderr = _run_command(patch.TYPE_CHECK_COMMAND)
    _require_marker(stdout, stderr, "All checks passed!", context="full type check")

    focused_tests, stdout, stderr = _run_command(
        patch.FOCUSED_TEST_COMMAND, sanitize_pytest_environment=True
    )
    focused_tests.update(_parse_focused_summary(stdout, stderr))

    poetry_check, stdout, stderr = _run_command(patch.POETRY_CHECK_COMMAND)
    _require_marker(stdout, stderr, "All set!", context="Poetry check")

    publication_guard, stdout, stderr = _run_command(
        patch.PUBLICATION_GUARD_COMMAND
    )
    _require_publication_guard_success(stdout, stderr)

    diff_check, stdout, stderr = _run_command(patch.DIFF_CHECK_COMMAND)
    _require_empty_output(stdout, stderr, context="git diff --check")
    return {
        "schema_preflight": schema_preflight,
        "full_type_check": full_type_check,
        "focused_tests": focused_tests,
        "poetry_check": poetry_check,
        "publication_guard": publication_guard,
        "git_diff_check": diff_check,
    }


def check_only() -> dict[str, Any]:
    schema = patch.preflight_final_calibration_owned_run_guard_revalidation_patch_schema()
    prelock = (
        patch.collect_final_calibration_owned_run_guard_revalidation_patch_prelock_state(
            verify_remote=True
        )
    )
    return {
        "status": "ready_to_lock",
        "gate": patch.PATCH_GATE,
        "schema_preflight": schema,
        "prelock": prelock,
        "component_count": 9,
        "writes_performed": False,
        "verification_commands_run": False,
        "calibration_run": False,
        "learning_curve_run": False,
        "dvc_commands_run": False,
        "scientific_network_commands_run": False,
        "future_outcomes_accessed": False,
    }


def execute_lock() -> dict[str, Any]:
    schema = patch.preflight_final_calibration_owned_run_guard_revalidation_patch_schema()
    before = (
        patch.collect_final_calibration_owned_run_guard_revalidation_patch_prelock_state(
            verify_remote=True
        )
    )
    verification = run_final_calibration_owned_run_guard_revalidation_patch_verification(
        expected_schema_preflight=schema
    )
    after = patch.collect_final_calibration_owned_run_guard_revalidation_patch_prelock_state(
        verify_remote=True
    )
    if before != after:
        raise _error("E0-MCALI prelock state changed during verification")
    payload = patch.build_final_calibration_owned_run_guard_revalidation_patch_lock_payload(
        prelock=before, verification=verification
    )
    patch.validate_final_calibration_owned_run_guard_revalidation_patch_lock_payload(
        payload, verify_remote=True
    )
    lock, companion = (
        patch.publish_final_calibration_owned_run_guard_revalidation_patch_lock_bundle(
            payload
        )
    )
    return {
        "status": "locked_unpublished",
        "gate": patch.PATCH_GATE,
        "lock": lock,
        "companion": companion,
        "calibration_run": False,
        "learning_curve_run": False,
        "dvc_commands_run": False,
        "scientific_network_commands_run": False,
        "future_outcomes_accessed": False,
    }


def check_effective() -> dict[str, Any]:
    return patch.load_effective_final_calibration_owned_run_guard_revalidation_patch_authority(
        verify_remote=True
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--execute-lock", action="store_true")
    mode.add_argument("--check-effective", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.check_only:
            payload = check_only()
        elif args.execute_lock:
            payload = execute_lock()
        else:
            payload = check_effective()
    except patch.FinalCalibrationOwnedRunGuardRevalidationPatchError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(_canonical_json_bytes(payload).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
