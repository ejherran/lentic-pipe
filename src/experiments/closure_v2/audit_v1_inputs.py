#!/usr/bin/env python
"""Audit the immutable Closure V1 Git authorities without opening data payloads.

The auditor uses Git object metadata only.  It never invokes DVC and never
opens Parquet files.  With ``--write-receipts`` it may materialize the four
Phase-0 receipts exclusively below ``reports/closure_v2/00_protocol``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TAG_NAME = "thesis-closure-v1"
EXPECTED_TAG_OBJECT = "d6c241f6b89d98d6206563739fab3b7b2f28020f"
EXPECTED_CERTIFICATION_COMMIT = "eb07598aa54a0944d1a87fe46d62415d0a4454aa"
EXPECTED_SCIENCE_COMMIT = "ea8ddce7f8edb9a61db97e29178e52603fa371b1"
EXPECTED_SYNTHESIS_COMMIT = "528dcb74a7c08b65f262901e4562a67b784db8c9"
EXPECTED_EDITORIAL_COMMIT = "d1daa3059462854d6ddf5199fbc05515cec76982"
V1_NAMESPACE_ROOTS = (
    "configs/closure_v1",
    "data/closure_v1",
    "docs/closure_v1",
    "models/closure_v1",
    "reports/closure_v1",
)
RECEIPT_ROOT = Path("reports/closure_v2/00_protocol")
RECEIPT_PATHS = {
    "entry": RECEIPT_ROOT / "entry_receipt.json",
    "reference": RECEIPT_ROOT / "v1_reference_manifest.json",
    "state": RECEIPT_ROOT / "implementation_state.json",
    "log": RECEIPT_ROOT / "EXECUTION_LOG.md",
}


class V1AuditError(RuntimeError):
    """Raised when an immutable Closure V1 authority does not match."""


def _git(repo_root: Path, args: Sequence[str], *, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=not binary,
    )
    return result.stdout


def _git_text(repo_root: Path, args: Sequence[str]) -> str:
    value = _git(repo_root, args)
    if not isinstance(value, str):
        raise AssertionError("Expected textual Git output")
    return value.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_v1_authorities(repo_root: Path) -> dict[str, Any]:
    tag_type = _git_text(repo_root, ["cat-file", "-t", TAG_NAME])
    if tag_type != "tag":
        raise V1AuditError(f"{TAG_NAME} must be an annotated tag, found {tag_type!r}")
    tag_object = _git_text(repo_root, ["rev-parse", TAG_NAME])
    peeled_commit = _git_text(repo_root, ["rev-parse", f"{TAG_NAME}^{{}}"])
    if tag_object != EXPECTED_TAG_OBJECT:
        raise V1AuditError(f"Closure V1 tag object drifted: {tag_object}")
    if peeled_commit != EXPECTED_CERTIFICATION_COMMIT:
        raise V1AuditError(f"Closure V1 peeled commit drifted: {peeled_commit}")

    commits = {
        "certification": EXPECTED_CERTIFICATION_COMMIT,
        "science": EXPECTED_SCIENCE_COMMIT,
        "synthesis": EXPECTED_SYNTHESIS_COMMIT,
        "editorial": EXPECTED_EDITORIAL_COMMIT,
    }
    for role, commit in commits.items():
        _git_text(repo_root, ["cat-file", "-e", f"{commit}^{{commit}}"])
        ancestry = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, peeled_commit],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if ancestry.returncode != 0:
            raise V1AuditError(f"{role} commit is not an ancestor of the V1 certification commit")
    return {
        "tag_name": TAG_NAME,
        "tag_type": tag_type,
        "tag_object": tag_object,
        "peeled_commit": peeled_commit,
        "authority_commits": commits,
    }


def build_v1_inventory(repo_root: Path, commit: str) -> tuple[list[dict[str, str]], str]:
    raw = _git(
        repo_root,
        ["ls-tree", "-r", "-z", "--full-tree", commit, "--", *V1_NAMESPACE_ROOTS],
        binary=True,
    )
    if not isinstance(raw, bytes):
        raise AssertionError("Expected binary Git tree output")
    records: list[dict[str, str]] = []
    digest = hashlib.sha256()
    for item in raw.split(b"\0"):
        if not item:
            continue
        metadata, path_bytes = item.split(b"\t", maxsplit=1)
        mode, object_type, object_id = metadata.decode("ascii").split(" ")
        path = path_bytes.decode("utf-8")
        record = {"mode": mode, "object_type": object_type, "object_id": object_id, "path": path}
        records.append(record)
        digest.update(mode.encode("ascii"))
        digest.update(b"\0")
        digest.update(object_type.encode("ascii"))
        digest.update(b"\0")
        digest.update(object_id.encode("ascii"))
        digest.update(b"\0")
        digest.update(path_bytes)
        digest.update(b"\n")
    if not records:
        raise V1AuditError("Closure V1 inventory is empty")
    if [record["path"] for record in records] != sorted(record["path"] for record in records):
        raise V1AuditError("Closure V1 Git inventory is not path ordered")
    return records, digest.hexdigest()


def changed_paths(repo_root: Path) -> list[str]:
    commands = (
        ["diff", "--name-only"],
        ["diff", "--cached", "--name-only"],
        ["ls-files", "--others", "--exclude-standard"],
    )
    paths: set[str] = set()
    for command in commands:
        output = _git_text(repo_root, command)
        paths.update(line for line in output.splitlines() if line)
    return sorted(paths)


def protected_v1_changes(repo_root: Path) -> list[str]:
    prefixes = tuple(f"{root}/" for root in V1_NAMESPACE_ROOTS)
    return [path for path in changed_paths(repo_root) if path.startswith(prefixes)]


def audit_repository(repo_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    authorities = resolve_v1_authorities(repo_root)
    inventory, inventory_digest = build_v1_inventory(repo_root, authorities["peeled_commit"])
    protected_changes = protected_v1_changes(repo_root)
    if protected_changes:
        raise V1AuditError(f"Unauthorized Closure V1 worktree changes: {protected_changes}")

    head = _git_text(repo_root, ["rev-parse", "HEAD"])
    branch = _git_text(repo_root, ["branch", "--show-current"])
    if branch != "closure-v2":
        raise V1AuditError(f"Closure V2 must run on branch 'closure-v2', found {branch!r}")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", authorities["peeled_commit"], head],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if ancestry.returncode != 0:
        raise V1AuditError("Closure V1 terminal commit is not an ancestor of the V2 base")

    guide = repo_root / "docs/closure_v2/EXECUTION_GUIDE.md"
    if not guide.is_file():
        raise V1AuditError("The public Closure V2 execution guide is missing")
    return {
        "schema_version": "closure_v2_v1_input_audit_v1",
        "status": "passed",
        "branch": branch,
        "head": head,
        "v1_is_ancestor": True,
        "v1_authorities": authorities,
        "namespace_roots": list(V1_NAMESPACE_ROOTS),
        "inventory": inventory,
        "inventory_record_count": len(inventory),
        "inventory_digest_sha256": inventory_digest,
        "protected_v1_changes": protected_changes,
        "parquet_files_opened": False,
        "dvc_commands_executed": False,
        "execution_guide": {
            "path": guide.relative_to(repo_root).as_posix(),
            "bytes": guide.stat().st_size,
            "sha256": sha256_file(guide),
        },
    }


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _assert_receipt_path(repo_root: Path, relative: Path) -> Path:
    if relative not in RECEIPT_PATHS.values():
        raise V1AuditError(f"Undeclared Phase-0 receipt path: {relative}")
    destination = (repo_root / relative).resolve()
    allowed_root = (repo_root / RECEIPT_ROOT).resolve()
    if destination.parent != allowed_root:
        raise V1AuditError(f"Receipt path escapes the Closure V2 protocol directory: {relative}")
    return destination


def _write_deterministic(repo_root: Path, relative: Path, content: bytes) -> None:
    destination = _assert_receipt_path(repo_root, relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.is_symlink() or not destination.is_file():
            raise V1AuditError(f"Receipt destination is not a regular file: {relative}")
        if destination.read_bytes() != content:
            raise V1AuditError(f"Refusing to overwrite a different receipt: {relative}")
        return
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def receipt_payloads(audit: Mapping[str, Any], repo_root: Path = PROJECT_ROOT) -> dict[str, bytes]:
    base_time = _git_text(repo_root, ["show", "-s", "--format=%cI", str(audit["head"])])
    authorities = audit["v1_authorities"]
    if not isinstance(authorities, Mapping):
        raise AssertionError("v1_authorities must be a mapping")
    entry = {
        "schema_version": "closure_v2_entry_receipt_v1",
        "status": "initialized",
        "branch": audit["branch"],
        "base_commit": audit["head"],
        "capture_time": base_time,
        "capture_time_basis": "base_commit_committer_date",
        "entry_worktree_status": "clean_before_phase_0_materialization",
        "v1_tag_object": authorities["tag_object"],
        "v1_peeled_commit": authorities["peeled_commit"],
        "v1_is_ancestor": audit["v1_is_ancestor"],
        "protected_v1_changes": audit["protected_v1_changes"],
        "parquet_files_opened": False,
        "dvc_commands_executed": False,
    }
    state = {
        "schema_version": "closure_v2_implementation_state_v1",
        "experiment_id": "closure_v2",
        "status": "phase_0_materialized_unpublished",
        "current_prompt": "P01",
        "completed_prompts": ["P00", "P01"],
        "next_prompt": "P02",
        "outcome_access_authorized": False,
        "outcome_accessed": False,
        "model_fit_authorized": False,
        "evaluation_authorized": False,
        "v1_immutable": True,
        "git_commit_performed_by_codex": False,
        "git_push_performed_by_codex": False,
        "authority_head": audit["head"],
    }
    log = f"""# Closure V2 Execution Log

## P00–P01 — Reentry and V1 immutability

- Result: PASS (unpublished).
- Branch: `{audit['branch']}`.
- Base commit: `{audit['head']}`.
- Closure V1 tag object: `{authorities['tag_object']}`.
- Closure V1 peeled commit: `{authorities['peeled_commit']}`.
- V1 inventory records: {audit['inventory_record_count']}.
- V1 inventory digest: `{audit['inventory_digest_sha256']}`.
- Protected V1 changes: none.
- Parquet files opened: no.
- DVC commands executed: no.
- Outcome access: forbidden and not performed.
- Next gate: P02 protocol and schemas.
"""
    entry_bytes = _canonical_json(entry)
    state_bytes = _canonical_json(state)
    log_bytes = log.encode("utf-8")

    def output_record(relative: Path, content: bytes) -> dict[str, Any]:
        return {
            "path": relative.as_posix(),
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    reference = {
        "schema_version": "closure_v2_v1_reference_manifest_v1",
        "status": "completed",
        "captured_at": base_time,
        "capture_time_basis": "base_commit_committer_date",
        "base_commit_v2": audit["head"],
        "tag": authorities,
        "namespace_roots": audit["namespace_roots"],
        "path_record_count": audit["inventory_record_count"],
        "ordered_path_object_digest_sha256": audit["inventory_digest_sha256"],
        "records": audit["inventory"],
        "execution_guide": audit["execution_guide"],
        "outputs": [
            output_record(RECEIPT_PATHS["entry"], entry_bytes),
            output_record(RECEIPT_PATHS["state"], state_bytes),
            output_record(RECEIPT_PATHS["log"], log_bytes),
        ],
        "manifest_written_last": True,
    }
    return {
        "entry": entry_bytes,
        "reference": _canonical_json(reference),
        "state": state_bytes,
        "log": log_bytes,
    }


def write_receipts(audit: Mapping[str, Any], repo_root: Path = PROJECT_ROOT) -> None:
    payloads = receipt_payloads(audit, repo_root)
    for role in ("entry", "reference", "state", "log"):
        _write_deterministic(repo_root, RECEIPT_PATHS[role], payloads[role])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-receipts", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    audit = audit_repository(PROJECT_ROOT)
    if args.write_receipts:
        write_receipts(audit, PROJECT_ROOT)
    summary = {
        key: audit[key]
        for key in (
            "schema_version",
            "status",
            "branch",
            "head",
            "v1_is_ancestor",
            "inventory_record_count",
            "inventory_digest_sha256",
            "protected_v1_changes",
            "parquet_files_opened",
            "dvc_commands_executed",
        )
    }
    summary["receipts_written"] = bool(args.write_receipts)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
