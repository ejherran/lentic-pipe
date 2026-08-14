#!/usr/bin/env python
"""Check, publish, and audit the Closure V1 E0-M formal-model authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments import closure_formal_model_lock as patch  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_SUMMARY_RE = re.compile(
    r"\b(?:warnings?|skipped|deselected|xfailed|xpassed|errors?|failed)\b",
    flags=re.IGNORECASE,
)


def _error(message: str) -> patch.ClosureFormalModelLockError:
    return patch.ClosureFormalModelLockError(message)


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
    if type(count) is not int or count != 48:
        raise _error("E0-M focused-test count is not frozen at exact48")
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


def run_formal_model_lock_verification(
    *, expected_schema_preflight: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Run only the frozen H checks; never build R or open outcomes."""

    schema_preflight = patch.preflight_formal_model_lock_schema(
        repo_root=PROJECT_ROOT
    )
    if (
        expected_schema_preflight is not None
        and dict(expected_schema_preflight) != schema_preflight
    ):
        raise _error("E0-M schema changed before verification")

    full_type_check, stdout, stderr = _run_command(patch.TYPE_CHECK_COMMAND)
    _require_marker(stdout, stderr, "All checks passed!", context="full type check")

    focused_tests, stdout, stderr = _run_command(
        patch.FOCUSED_TEST_COMMAND,
        sanitize_pytest_environment=True,
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


def _capture_prelock_state() -> tuple[Any, dict[str, Any]]:
    """Capture immutable physical inputs before any P publication."""

    physical = patch._physical_snapshot(PROJECT_ROOT)
    prelock = patch.collect_formal_model_lock_prelock_state(
        verify_remote=True,
        repo_root=PROJECT_ROOT,
    )
    return physical, prelock


def check_only() -> dict[str, Any]:
    """Revalidate the complete outcome-free H-E0-MBATCH candidate."""

    schema = patch.preflight_formal_model_lock_schema(repo_root=PROJECT_ROOT)
    physical_before, prelock_before = _capture_prelock_state()
    physical_after, prelock_after = _capture_prelock_state()
    if physical_before != physical_after:
        raise _error("E0-M immutable physical inputs changed during check-only")
    if prelock_before != prelock_after:
        raise _error("E0-M topology, refs, namespace, or prelock state changed")
    if (
        prelock_before.get("status") != "ready_to_lock"
        or prelock_before.get("formal_model_lock_ready") is not True
        or prelock_before.get("missing_component_count") != 0
        or prelock_before.get("p_authority_generation_authorized") is not False
        or not isinstance(prelock_before.get("runner_readiness"), Mapping)
        or prelock_before["runner_readiness"].get("status")
        != "sealed_batch_runner_ready_for_formal_lock"
    ):
        raise _error("H-E0-MBATCH candidate readiness drifted")
    return {
        "status": "ready_to_lock",
        "gate": patch.PATCH_GATE,
        "schema_preflight": schema,
        "prelock": prelock_before,
        "component_count": len(patch.PATCH_PATHS),
        "physical_input_count": len(physical_before),
        "p_output_count": len(patch.FORMAL_MODEL_LOCK_P_STAGED_SCOPE),
        "r_output_count": len(patch.FORMAL_MODEL_LOCK_R_STAGED_SCOPE),
        "physical_snapshot_revalidated": True,
        "prelock_revalidated": True,
        "formal_model_lock_ready": True,
        "missing_component_count": 0,
        "p_authority_generation_authorized": False,
        "writes_performed": False,
        "verification_commands_run": False,
        "formal_model_lock_run": False,
        "sealed_batch_run": False,
        "evaluation_run": False,
        "publication_assistant_run": False,
        "dvc_commands_run": False,
        "git_commands_mutating_run": False,
        "e0_u_authorized": False,
        "outcome_access_authorized": False,
        "future_outcomes_accessed": False,
    }


def execute_lock() -> dict[str, Any]:
    """Verify H and publish only the P authority/companion pair."""

    schema = patch.preflight_formal_model_lock_schema(repo_root=PROJECT_ROOT)
    physical_before, prelock_before = _capture_prelock_state()
    if prelock_before.get("p_authority_generation_authorized") is not True:
        raise _error(
            "E0-M P generation requires published H-E0-MBATCH"
        )
    verification = run_formal_model_lock_verification(
        expected_schema_preflight=schema
    )
    physical_after, prelock_after = _capture_prelock_state()
    if physical_before != physical_after:
        raise _error("E0-M immutable physical inputs changed during verification")
    if prelock_before != prelock_after:
        raise _error("E0-M topology, refs, namespace, or prelock state changed")

    payload = patch.build_formal_model_lock_authority_payload(
        prelock=prelock_before,
        verification=verification,
        repo_root=PROJECT_ROOT,
    )
    patch.validate_formal_model_lock_authority_payload(
        payload,
        verify_remote=True,
        repo_root=PROJECT_ROOT,
    )
    authority, companion = patch.publish_formal_model_lock_authority_bundle(
        payload,
        repo_root=PROJECT_ROOT,
    )
    patch.validate_formal_model_lock_unpublished_authority_bundle(
        require_staged=False,
        verify_remote=True,
        repo_root=PROJECT_ROOT,
    )
    physical_published = patch._physical_snapshot(PROJECT_ROOT)
    if physical_published != physical_before:
        raise _error("E0-M P publisher changed immutable physical inputs")
    return {
        "status": "locked_unpublished",
        "gate": patch.P_GATE,
        "authority": authority,
        "companion": companion,
        "p_output_count": len(patch.FORMAL_MODEL_LOCK_P_STAGED_SCOPE),
        "r_output_count": 0,
        "physical_identity_preserved": True,
        "formal_model_lock_run": False,
        "sealed_batch_run": False,
        "evaluation_run": False,
        "publication_assistant_run": False,
        "dvc_commands_run": False,
        "git_commands_mutating_run": False,
        "e0_u_authorized": False,
        "outcome_access_authorized": False,
        "future_outcomes_accessed": False,
    }


def check_effective() -> dict[str, Any]:
    """Load the published P authority without creating an R output."""

    return patch.load_effective_formal_model_lock_authority(
        verify_remote=True,
        repo_root=PROJECT_ROOT,
    )


def execute_formal_model_lock() -> dict[str, Any]:
    """Materialize exact R-E0-M without executing the sealed batch."""

    result = patch.execute_formal_model_lock(
        verify_remote=True,
        repo_root=PROJECT_ROOT,
    )
    validated = patch.validate_formal_model_lock_bundle(
        require_staged=False,
        verify_remote=True,
        repo_root=PROJECT_ROOT,
    )
    if (
        result.get("status") != "formal_model_lock_written_unpublished"
        or validated.get("status") != "formal_model_lock_validated"
        or validated.get("r_stage_state") != "exact5_untracked"
    ):
        raise _error("R-E0-M post-publication validation drifted")
    return {"materialization": result, "validation": validated}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--execute-lock", action="store_true")
    mode.add_argument("--check-effective", action="store_true")
    mode.add_argument("--execute-formal-model-lock", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.check_only:
            payload = check_only()
        elif args.execute_lock:
            payload = execute_lock()
        elif args.check_effective:
            payload = check_effective()
        else:
            payload = execute_formal_model_lock()
    except patch.ClosureFormalModelLockError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(_canonical_json_bytes(payload).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
