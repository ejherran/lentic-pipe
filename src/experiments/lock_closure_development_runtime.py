#!/usr/bin/env python
"""Create the external Closure V1 E0-DL lock from a clean pre-fit HEAD."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments.closure_development_runtime_lock import (
    DEFAULT_LOCK_PATH,
    DEFAULT_LOCK_SCHEMA,
    DEFAULT_RUNTIME_CONFIG,
    DEFAULT_RUNTIME_SCHEMA,
    TYPE_CHECK_COMMAND,
    DevelopmentRuntimeLockError,
    build_development_runtime_lock_payload,
    collect_prelock_state,
    command_evidence,
    dvc_remote_push_command,
    focused_test_command,
    validate_development_runtime_lock_payload,
    verify_dvc_remote_by_idempotent_push,
)
from src.experiments.closure_contract import load_json_mapping


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    """Write the single completion manifest last and remove partial output."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _summary(prelock: dict[str, Any], *, device: str) -> dict[str, Any]:
    planned = prelock["planned_artifacts"]
    return {
        "status": "ready_to_lock",
        "gate": "E0-DL",
        "locked_repository_head": prelock["locked_repository"]["head"],
        "component_count": len(prelock["components"]),
        "runtime_dependency_count": len(prelock["runtime_dependencies"]),
        "parent_count": len(prelock["parents"]),
        "planned_artifact_path_count": planned["count"],
        "planned_artifact_paths_sha256": planned["sha256"],
        "common_origin_output_verified": True,
        "expert_state_output_verified": True,
        "canonical_origin_identity_verified": True,
        "locked_parent_local_tracking_verified": prelock[
            "locked_parent_publication"
        ]["local_tracking_verified"],
        "locked_parent_remote_verified": prelock["locked_parent_publication"][
            "remote_verified"
        ],
        "device": device,
        "full_type_check_command": list(TYPE_CHECK_COMMAND),
        "focused_test_command": list(focused_test_command(prelock["runtime"])),
        "dvc_remote_verification_command": list(
            dvc_remote_push_command(
                prelock["runtime"],
                prelock["common_origin"],
                prelock["expert_state"],
            )
        ),
        "dvc_remote_verification_environment": {
            "LC_ALL": "C",
            "LANG": "C",
            "DVC_NO_ANALYTICS": "1",
        },
        "dvc_remote_verified_at_lock": False,
        "development_fit_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "outputs_written": [],
    }


def create_development_runtime_lock(
    *,
    runtime_config: Path,
    runtime_schema: Path,
    lock_schema: Path,
    output: Path,
    device: str,
    verify_dvc_remote_by_idempotent_push_flag: bool,
) -> Path:
    """Run fixed checks, prove state stability, and atomically write E0-DL."""
    if output.exists() or output.with_suffix(output.suffix + ".tmp").exists():
        raise DevelopmentRuntimeLockError(
            f"Refusing to overwrite an existing E0-DL output: {output.as_posix()}"
        )
    if not verify_dvc_remote_by_idempotent_push_flag:
        raise DevelopmentRuntimeLockError(
            "--execute-lock requires --verify-dvc-remote-by-idempotent-push"
        )
    before = collect_prelock_state(
        runtime_config=runtime_config,
        runtime_schema=runtime_schema,
        lock_schema=lock_schema,
        lock_path=output,
        device=device,
        verify_parent_remote_publication=True,
    )
    type_check = command_evidence(TYPE_CHECK_COMMAND)
    tests = command_evidence(focused_test_command(before["runtime"]))
    dvc_remote_verification = verify_dvc_remote_by_idempotent_push(
        before["runtime"],
        before["common_origin"],
        before["expert_state"],
    )
    after = collect_prelock_state(
        runtime_config=runtime_config,
        runtime_schema=runtime_schema,
        lock_schema=lock_schema,
        lock_path=output,
        device=device,
        verify_parent_remote_publication=True,
    )
    if before != after:
        raise DevelopmentRuntimeLockError(
            "Repository, parents, environment, or DVC ownership changed during E0-DL checks"
        )
    payload = build_development_runtime_lock_payload(
        after,
        full_type_check=type_check,
        focused_tests=tests,
        dvc_remote_verification=dvc_remote_verification,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    schema = load_json_mapping(lock_schema)
    validate_development_runtime_lock_payload(payload, schema)
    try:
        _write_json_atomic(payload, output)
    except BaseException:
        output.unlink(missing_ok=True)
        output.with_suffix(output.suffix + ".tmp").unlink(missing_ok=True)
        raise
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-config", type=Path, default=DEFAULT_RUNTIME_CONFIG)
    parser.add_argument("--runtime-schema", type=Path, default=DEFAULT_RUNTIME_SCHEMA)
    parser.add_argument("--lock-schema", type=Path, default=DEFAULT_LOCK_SCHEMA)
    parser.add_argument("--output", type=Path, default=DEFAULT_LOCK_PATH)
    parser.add_argument(
        "--device",
        required=True,
        choices=("cpu",),
        help="Explicit Closure V1 E0-DL device; v1 is locked to cpu.",
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--check-only",
        action="store_true",
        help=(
            "Validate outcome-free preconditions, including the expert-state semantic audit, "
            "and print commands without running checks or writing output."
        ),
    )
    action.add_argument(
        "--execute-lock",
        action="store_true",
        help="Run the fixed type/test checks and atomically create the one-time E0-DL manifest.",
    )
    parser.add_argument(
        "--verify-dvc-remote-by-idempotent-push",
        action="store_true",
        help=(
            "Required with --execute-lock: run two exact targeted DVC pushes and "
            "write the lock only when both prove the remote was already up to date."
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.check_only:
        if args.output.exists() or args.output.with_suffix(args.output.suffix + ".tmp").exists():
            raise DevelopmentRuntimeLockError(
                f"Refusing to replace existing E0-DL output: {args.output.as_posix()}"
            )
        prelock = collect_prelock_state(
            runtime_config=args.runtime_config,
            runtime_schema=args.runtime_schema,
            lock_schema=args.lock_schema,
            lock_path=args.output,
            device=args.device,
            verify_parent_remote_publication=False,
        )
        print(json.dumps(_summary(prelock, device=args.device), indent=2, sort_keys=True))
        return
    output = create_development_runtime_lock(
        runtime_config=args.runtime_config,
        runtime_schema=args.runtime_schema,
        lock_schema=args.lock_schema,
        output=args.output,
        device=args.device,
        verify_dvc_remote_by_idempotent_push_flag=(
            args.verify_dvc_remote_by_idempotent_push
        ),
    )
    print(f"Wrote locked development runtime manifest: {output.as_posix()}")


if __name__ == "__main__":
    main()
