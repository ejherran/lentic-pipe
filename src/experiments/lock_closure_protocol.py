#!/usr/bin/env python
"""Create the external Git-bound lock for the thesis closure protocol."""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.experiments.closure_contract import (
    DEFAULT_ANALYSIS_PLAN,
    EXPERIMENT_ID,
    PLAN_VERSION,
    ClosureContractError,
    file_record,
    load_and_validate_analysis_plan,
    repository_relative,
    resolve_repo_path,
    sha256_file,
)


LOCK_VERSION = "closure_protocol_lock_v1"
DEFAULT_OUTPUT_DIR = Path("reports/closure_v1/00_protocol")
DEFAULT_LOCK_PATH = DEFAULT_OUTPUT_DIR / "protocol_lock.json"
HASH_FIELDS = ["path", "role", "bytes", "sha256"]
DVC_FIELDS = ["pointer_path", "output_path", "hash_name", "hash_value", "size", "nfiles"]


def _git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=resolve_repo_path("."),
        check=check,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def repository_state() -> dict[str, Any]:
    """Capture the repository state before any lock output is written."""
    dirty = _git("status", "--porcelain", "--untracked-files=all")
    return {
        "head": _git("rev-parse", "HEAD"),
        "branch": _git("branch", "--show-current") or "detached",
        "worktree_status": "clean" if not dirty else "dirty",
        "dirty_paths": dirty.splitlines(),
    }


def _assert_alignment_base(plan: dict[str, Any], head: str) -> str:
    provenance = plan.get("provenance")
    if not isinstance(provenance, dict):
        raise ClosureContractError("analysis_plan.provenance must be a mapping")
    base = provenance.get("alignment_base_commit")
    if not isinstance(base, str) or len(base) != 40:
        raise ClosureContractError("provenance.alignment_base_commit must be a full Git SHA")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base, head],
        cwd=resolve_repo_path("."),
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise ClosureContractError(f"Alignment base {base} is not an ancestor of HEAD {head}")
    return base


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    resolved = resolve_repo_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = resolved.with_suffix(resolved.suffix + ".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
        tmp_path.replace(resolved)
    finally:
        tmp_path.unlink(missing_ok=True)


def _write_text_atomic(value: str, path: Path) -> None:
    resolved = resolve_repo_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = resolved.with_suffix(resolved.suffix + ".tmp")
    try:
        tmp_path.write_text(value, encoding="utf-8")
        tmp_path.replace(resolved)
    finally:
        tmp_path.unlink(missing_ok=True)


def _write_csv_atomic(rows: list[dict[str, Any]], path: Path, *, fieldnames: list[str]) -> None:
    resolved = resolve_repo_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = resolved.with_suffix(resolved.suffix + ".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in fieldnames})
        tmp_path.replace(resolved)
    finally:
        tmp_path.unlink(missing_ok=True)


def _component_records(plan: dict[str, Any]) -> list[dict[str, Any]]:
    locking = plan["locking"]
    component_roles = locking.get("component_roles", {})
    if not isinstance(component_roles, dict):
        raise ClosureContractError("locking.component_roles must be a mapping")
    records: list[dict[str, Any]] = []
    for item in locking["protocol_components"]:
        if isinstance(item, str):
            path = item
            role = str(component_roles.get(path, "protocol_component"))
        else:
            path = str(item["path"])
            role = str(item.get("role", "protocol_component"))
        records.append(file_record(path, role=role))
    return sorted(records, key=lambda record: str(record["path"]))


def _source_artifact_records(plan: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in plan["locking"]["source_artifacts"]:
        records.append(file_record(str(item["path"]), role=str(item["role"])))
    return sorted(records, key=lambda record: str(record["path"]))


def _assert_protocol_components_tracked(records: list[dict[str, Any]]) -> None:
    """Require every protocol component to belong to the locked Git commit."""

    untracked: list[str] = []
    for record in records:
        path = str(record["path"])
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", path],
            cwd=resolve_repo_path("."),
            check=False,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            untracked.append(path)
    if untracked:
        raise ClosureContractError(
            "Every protocol component must be tracked by the locked Git commit; "
            f"untracked components: {untracked}"
        )


def dvc_inventory() -> list[dict[str, Any]]:
    """Read every Git-tracked DVC pointer without contacting the remote."""
    pointer_paths = [line for line in _git("ls-files", "*.dvc").splitlines() if line]
    rows: list[dict[str, Any]] = []
    for pointer_path in sorted(pointer_paths):
        payload = yaml.safe_load(resolve_repo_path(pointer_path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("outs"), list):
            raise ClosureContractError(f"Malformed DVC pointer: {pointer_path}")
        for output in payload["outs"]:
            if not isinstance(output, dict):
                raise ClosureContractError(f"Malformed DVC output record: {pointer_path}")
            hash_name = str(output.get("hash", "md5"))
            hash_value = output.get(hash_name, output.get("md5"))
            if not isinstance(hash_value, str):
                raise ClosureContractError(f"DVC pointer has no content hash: {pointer_path}")
            rows.append(
                {
                    "pointer_path": pointer_path,
                    "output_path": str(output.get("path", "")),
                    "hash_name": hash_name,
                    "hash_value": hash_value,
                    "size": output.get("size", ""),
                    "nfiles": output.get("nfiles", ""),
                }
            )
    return rows


def environment_payload() -> dict[str, Any]:
    """Capture package versions and platform details without network access."""
    packages = sorted(
        (
            {"name": distribution.metadata["Name"], "version": distribution.version}
            for distribution in importlib.metadata.distributions()
            if distribution.metadata["Name"]
        ),
        key=lambda item: str(item["name"]).lower(),
    )
    tracked_environment_files: list[dict[str, Any]] = []
    for path in (Path("pyproject.toml"), Path("poetry.lock")):
        if resolve_repo_path(path).is_file():
            tracked_environment_files.append(file_record(path, role="environment_definition"))
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable_name": Path(sys.executable).name,
        "platform": platform.platform(),
        "packages": packages,
        "environment_files": tracked_environment_files,
    }


def environment_text(payload: dict[str, Any]) -> str:
    lines = [
        f"python_version={payload['python_version']}",
        f"python_implementation={payload['python_implementation']}",
        f"python_executable_name={payload['python_executable_name']}",
        f"platform={payload['platform']}",
    ]
    for record in payload["environment_files"]:
        lines.append(f"file={record['path']} sha256={record['sha256']}")
    for package in payload["packages"]:
        lines.append(f"package={package['name']}=={package['version']}")
    return "\n".join(lines) + "\n"


def build_lock_payload(
    *,
    plan_path: Path,
    plan: dict[str, Any],
    state: dict[str, Any],
    alignment_base: str,
    component_records: list[dict[str, Any]],
    source_records: list[dict[str, Any]],
    output_records: list[dict[str, Any]],
    dvc_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the non-self-referential external lock manifest."""
    return {
        "lock_version": LOCK_VERSION,
        "status": "locked",
        "experiment_id": EXPERIMENT_ID,
        "plan_version": PLAN_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "analysis_plan": repository_relative(plan_path),
        "analysis_plan_sha256": sha256_file(plan_path),
        "alignment_base_commit": alignment_base,
        "locked_repository": state,
        "protocol_components": component_records,
        "source_artifacts": source_records,
        "generated_lock_companions": output_records,
        "dvc_pointer_count": len({str(row["pointer_path"]) for row in dvc_rows}),
        "dvc_output_count": len(dvc_rows),
        "freeze_generation_dirty_state_preserved": True,
        "future_outcomes_accessed": False,
        "outcome_access_definition": plan["outcome_access"]["outcome_access_definition"],
        "lock_command_reads_complete_source_bytes_for_sha256": True,
        "lock_command_semantically_decodes_post_2021_outcomes": False,
        "holdout_assignment_created": False,
        "authorized_claim": "internal Git-locked pseudoprospective evaluation at held-out WQP monitoring locations",
        "forbidden_claims": [
            "external validation",
            "real prospective validation",
            "transfer to unseen waterbodies",
        ],
        "change_control": plan["change_control"],
    }


def create_protocol_lock(plan_path: Path, output_dir: Path) -> Path:
    """Validate inputs, require a clean commit, and write the E0-P lock bundle."""
    plan, _ = load_and_validate_analysis_plan(plan_path, require_files=True, reject_unresolved=True)
    locking = plan["locking"]
    configured_lock_path = Path(str(locking["lock_manifest"]))
    configured_repository_state_path = Path(str(locking["repository_state"]))
    if resolve_repo_path(output_dir) != resolve_repo_path(configured_lock_path.parent):
        raise ClosureContractError(
            "Protocol lock output directory must match locking.lock_manifest"
        )
    if resolve_repo_path(output_dir / "repository_state.json") != resolve_repo_path(
        configured_repository_state_path
    ):
        raise ClosureContractError(
            "Protocol repository-state output must match locking.repository_state"
        )
    repository_state_path = output_dir / "repository_state.json"
    artifact_hashes_path = output_dir / "artifact_hashes.csv"
    code_hashes_path = output_dir / "code_hashes.csv"
    dvc_inventory_path = output_dir / "dvc_inventory_snapshot.csv"
    environment_json_path = output_dir / "environment.json"
    environment_text_path = output_dir / "environment.txt"
    lock_path = output_dir / DEFAULT_LOCK_PATH.name
    planned_outputs = [
        repository_state_path,
        artifact_hashes_path,
        code_hashes_path,
        dvc_inventory_path,
        environment_json_path,
        environment_text_path,
        lock_path,
    ]
    existing_outputs = [repository_relative(path) for path in planned_outputs if resolve_repo_path(path).exists()]
    if existing_outputs:
        raise ClosureContractError(
            "Refusing to overwrite an existing protocol lock bundle; review these paths first: "
            f"{existing_outputs}"
        )

    state = repository_state()
    if state["worktree_status"] != "clean":
        raise ClosureContractError(
            "Protocol locking requires a clean worktree; commit the reviewed protocol and code first"
        )
    alignment_base = _assert_alignment_base(plan, str(state["head"]))

    component_records = _component_records(plan)
    _assert_protocol_components_tracked(component_records)
    source_records = _source_artifact_records(plan)
    dvc_rows = dvc_inventory()
    environment = environment_payload()

    code_records = [record for record in component_records if str(record["path"]).startswith("src/")]
    artifact_records = source_records + [
        record for record in component_records if not str(record["path"]).startswith("src/")
    ]
    try:
        _write_json_atomic(state, repository_state_path)
        _write_csv_atomic(artifact_records, artifact_hashes_path, fieldnames=HASH_FIELDS)
        _write_csv_atomic(code_records, code_hashes_path, fieldnames=HASH_FIELDS)
        _write_csv_atomic(dvc_rows, dvc_inventory_path, fieldnames=DVC_FIELDS)
        _write_json_atomic(environment, environment_json_path)
        _write_text_atomic(environment_text(environment), environment_text_path)

        companion_paths = [
            repository_state_path,
            artifact_hashes_path,
            code_hashes_path,
            dvc_inventory_path,
            environment_json_path,
            environment_text_path,
        ]
        output_records = [file_record(path, role="lock_companion") for path in companion_paths]
        lock_payload = build_lock_payload(
            plan_path=plan_path,
            plan=plan,
            state=state,
            alignment_base=alignment_base,
            component_records=component_records,
            source_records=source_records,
            output_records=output_records,
            dvc_rows=dvc_rows,
        )
        _write_json_atomic(lock_payload, lock_path)
    except BaseException:
        for path in planned_outputs:
            resolve_repo_path(path).unlink(missing_ok=True)
        raise
    return lock_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_ANALYSIS_PLAN)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate the draft contract and inputs without requiring a clean tree or writing a lock.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.check_only:
        _, summary = load_and_validate_analysis_plan(args.plan, require_files=True, reject_unresolved=True)
        print(json.dumps({"status": "ready_to_lock", **summary}, indent=2))
        return
    lock_path = create_protocol_lock(args.plan, args.output_dir)
    print(f"Wrote locked protocol manifest: {repository_relative(lock_path)}")


if __name__ == "__main__":
    main()
