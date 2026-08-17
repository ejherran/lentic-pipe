#!/usr/bin/env python
"""Validate H-SYN and publish the immutable, outcome-free P-SYN authority.

``--check-only`` is deliberately non-writing and supports both legitimate
states of the H-SYN transaction: the exact local patch over the Phase 3
source commit, and the clean published H-SYN commit.  ``--generate`` accepts
only the latter and publishes the two P-SYN JSON files atomically, with the
companion manifest linked last.
"""

from __future__ import annotations

import argparse
import errno
import os
import re
import secrets
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence, cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.reporting import closure_synthesis_contract as synthesis  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GATE = "P-SYN"
AUTHORITY_VERSION = "closure_v1_phase4_synthesis_authority_v1"
MANIFEST_VERSION = "closure_v1_phase4_synthesis_authority_manifest_v1"
SOURCE_COMMIT = "ea8ddce7f8edb9a61db97e29178e52603fa371b1"
BUILDER_PATH = "src/reporting/build_closure_synthesis.py"
H_SCOPE: Mapping[str, str] = {
    "configs/closure_v1/phase4_synthesis.schema.json": "A",
    "configs/closure_v1/phase4_synthesis.yaml": "A",
    "docs/closure_v1/PHASE4_SYNTHESIS_FREEZE.md": "A",
    "src/data/prepare_commit_artifacts.py": "M",
    "src/experiments/lock_closure_synthesis.py": "A",
    "src/reporting/build_closure_synthesis.py": "A",
    "src/reporting/closure_synthesis_contract.py": "A",
    "tests/test_build_closure_synthesis.py": "A",
    "tests/test_closure_synthesis_contract.py": "A",
    "tests/test_lock_closure_synthesis.py": "A",
    "tests/test_prepare_commit_artifacts.py": "M",
}
H_GIT_MODES: Mapping[str, str] = {
    path: "100755" if path == "src/data/prepare_commit_artifacts.py" else "100644"
    for path in H_SCOPE
}
SCHEMA_AND_TEST_PATHS = (
    "configs/closure_v1/phase4_synthesis.schema.json",
    "tests/test_build_closure_synthesis.py",
    "tests/test_closure_synthesis_contract.py",
    "tests/test_lock_closure_synthesis.py",
)
AUTHORITY_PATH = synthesis.AUTHORITY_PATH
MANIFEST_PATH = synthesis.AUTHORITY_MANIFEST_PATH
GUARD_PATH = Path("tmp/closure_v1_phase4_synthesis/authority.guard")
TEMP_PREFIX = ".closure_v1_phase4_synthesis_authority."
MUTATING_AUTHORIZATIONS: Mapping[str, bool] = {
    "dvc_add_authorized": False,
    "dvc_push_authorized": False,
    "model_fit_authorized": False,
    "model_reconstruction_authorized": False,
    "raw_target_access_authorized": False,
    "raw_outcome_access_authorized": False,
    "r_syn_build_authorized": False,
    "scientific_network_access_authorized": False,
}
GIT_OID_RE = re.compile(r"^[0-9a-f]{40,64}$")
HASH_CHUNK_SIZE = 1024 * 1024


def _error(message: str) -> synthesis.SynthesisContractError:
    return synthesis.SynthesisContractError(message)


def _git(
    root: Path, *args: str, text: bool = True
) -> str | bytes:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    process = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=text,
        env=environment,
    )
    if process.returncode != 0:
        stderr = (
            process.stderr.strip()
            if text
            else process.stderr.decode("utf-8", "replace").strip()
        )
        raise _error(f"git {' '.join(args)} failed: {stderr}")
    return process.stdout


def _one_oid(root: Path, ref: str) -> str:
    value = cast(str, _git(root, "rev-parse", "--verify", ref)).strip()
    if GIT_OID_RE.fullmatch(value) is None:
        raise _error(f"Git ref did not resolve to one commit: {ref}")
    return value


def _remote_main_oid(root: Path) -> str:
    output = cast(
        str,
        _git(root, "ls-remote", "--exit-code", "origin", "HEAD", "refs/heads/main"),
    )
    records: dict[str, str] = {}
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or GIT_OID_RE.fullmatch(fields[0]) is None:
            raise _error("Remote refs have an invalid representation")
        if fields[1] in records:
            raise _error("Remote ref was returned more than once")
        records[fields[1]] = fields[0]
    expected = {"HEAD", "refs/heads/main"}
    if set(records) != expected or len(set(records.values())) != 1:
        raise _error("Remote HEAD and main are absent or misaligned")
    return records["refs/heads/main"]


def _parse_status(root: Path) -> dict[str, str]:
    raw = cast(
        str,
        _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all"),
    )
    records: dict[str, str] = {}
    for item in raw.split("\0"):
        if not item:
            continue
        if len(item) < 4 or item[2] != " ":
            raise _error("Git status contains an unsupported record")
        code, path = item[:2], item[3:]
        if code[0] in {"R", "C"} or code[1] in {"R", "C"}:
            raise _error("Renames and copies are forbidden in H-SYN")
        if path in records:
            raise _error(f"Git status repeats a path: {path}")
        records[path] = code
    return records


def _validate_regular_file(root: Path, path_text: str) -> tuple[Path, os.stat_result]:
    if "\\" in path_text or "\x00" in path_text:
        raise _error(f"H-SYN path is not canonical: {path_text!r}")
    relative = PurePosixPath(path_text)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise _error(f"H-SYN path is not repository-relative: {path_text!r}")
    cursor = root
    for part in relative.parts[:-1]:
        cursor = cursor / part
        try:
            parent_metadata = cursor.lstat()
        except OSError as exc:
            raise _error(f"H-SYN parent is absent: {cursor}") from exc
        if cursor.is_symlink() or not stat.S_ISDIR(parent_metadata.st_mode):
            raise _error(f"H-SYN parent must be a non-symlink directory: {cursor}")
    path = root.joinpath(*relative.parts)
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise _error(f"Required H-SYN file is absent: {path_text}") from exc
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise _error(f"H-SYN path must be a regular non-symlink file: {path_text}")
    if metadata.st_nlink != 1:
        raise _error(f"H-SYN path must be single-link: {path_text}")
    expected_filesystem_mode = int(H_GIT_MODES[path_text][-3:], 8)
    if stat.S_IMODE(metadata.st_mode) != expected_filesystem_mode:
        raise _error(f"H-SYN file mode drifted: {path_text}")
    return path, metadata


def _read_regular_file(path: Path, expected: os.stat_result) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or (before.st_dev, before.st_ino) != (expected.st_dev, expected.st_ino)
        ):
            raise _error(f"H-SYN file identity changed before read: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, HASH_CHUNK_SIZE)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ) != (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ):
            raise _error(f"H-SYN file identity changed during read: {path}")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _validate_local_h_scope(root: Path) -> None:
    status = _parse_status(root)
    if set(status) != set(H_SCOPE):
        raise _error("Local H-SYN scope is not the exact frozen 9A+2M path set")
    for path_text, expected_kind in H_SCOPE.items():
        code = status[path_text]
        accepted = {"A ", "??"} if expected_kind == "A" else {"M ", " M"}
        if code not in accepted:
            raise _error(f"Local H-SYN status drifted for {path_text}: {code!r}")
        path, metadata = _validate_regular_file(root, path_text)
        source_tree = cast(
            str, _git(root, "ls-tree", SOURCE_COMMIT, "--", path_text)
        ).strip()
        if expected_kind == "A":
            if source_tree:
                raise _error(f"H-SYN addition already exists at source: {path_text}")
            continue
        fields = source_tree.split(None, 3)
        if (
            len(fields) != 4
            or fields[0] != H_GIT_MODES[path_text]
            or fields[1] != "blob"
            or GIT_OID_RE.fullmatch(fields[2]) is None
            or fields[3] != path_text
        ):
            raise _error(f"H-SYN modification lacks one source blob: {path_text}")
        source_bytes = cast(bytes, _git(root, "cat-file", "blob", fields[2], text=False))
        if _read_regular_file(path, metadata) == source_bytes:
            raise _error(f"H-SYN modification has unchanged bytes: {path_text}")


def _commit_scope(root: Path, commit: str) -> dict[str, str]:
    output = cast(
        str,
        _git(
            root,
            "diff-tree",
            "--no-commit-id",
            "--name-status",
            "--no-renames",
            "-r",
            f"{commit}^",
            commit,
        ),
    )
    records: dict[str, str] = {}
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] not in {"A", "M", "D"}:
            raise _error("H-SYN commit contains an unsupported diff record")
        if fields[1] in records:
            raise _error("H-SYN commit repeats a path")
        records[fields[1]] = fields[0]
    return records


def _validate_published_h(root: Path, head: str) -> list[dict[str, Any]]:
    parents = cast(str, _git(root, "rev-list", "--parents", "-n", "1", head)).split()
    if parents != [head, SOURCE_COMMIT]:
        raise _error("Published H-SYN must be the direct, single-parent child of source")
    if _commit_scope(root, head) != dict(H_SCOPE):
        raise _error("Published H-SYN commit scope is not the exact frozen 9A+2M set")
    return [
        _component_record(root, head, path_text) for path_text in sorted(H_SCOPE)
    ]


def _validate_refs(root: Path, expected: str, *, verify_remote: bool) -> dict[str, str]:
    refs = {
        "head": _one_oid(root, "HEAD"),
        "main": _one_oid(root, "main"),
        "origin_main": _one_oid(root, "origin/main"),
        "origin_head": _one_oid(root, "origin/HEAD"),
    }
    if set(refs.values()) != {expected}:
        raise _error(f"Local/tracking refs are not aligned at {expected}")
    if verify_remote:
        refs["remote_main"] = _remote_main_oid(root)
        if refs["remote_main"] != expected:
            raise _error("Live remote main is not aligned with the expected commit")
    return refs


def _assert_absent(path: Path, *, context: str) -> None:
    try:
        path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise _error(f"Cannot establish {context} absence: {path}") from exc
    raise _error(f"{context} must be absent: {path}")


def _validate_empty_publication_namespace(
    root: Path, contract: synthesis.SynthesisContract
) -> None:
    _assert_absent(root / AUTHORITY_PATH, context="P-SYN authority")
    _assert_absent(root / MANIFEST_PATH, context="P-SYN companion")
    _assert_absent(root / GUARD_PATH.parent, context="P-SYN coordination namespace")
    synthesis_root = root / synthesis.SYNTHESIS_ROOT
    _assert_absent(synthesis_root, context="R-SYN namespace")
    parent = root / AUTHORITY_PATH.parent
    if parent.is_symlink() or not parent.is_dir():
        raise _error("P-SYN output parent must be a regular directory")
    for path in parent.iterdir():
        if path.name.startswith(TEMP_PREFIX):
            raise _error(f"P-SYN temporary namespace is not empty: {path}")
    if tuple(contract.output_paths)[-1] != (
        "reports/closure_v1/11_synthesis/synthesis_bundle_manifest.json"
    ):
        raise _error("R-SYN manifest-last order drifted")


def _component_record(root: Path, commit: str, path_text: str) -> dict[str, Any]:
    path, metadata = _validate_regular_file(root, path_text)
    output = cast(str, _git(root, "ls-tree", commit, "--", path_text)).strip()
    fields = output.split(None, 3)
    if (
        len(fields) != 4
        or fields[0] != H_GIT_MODES[path_text]
        or fields[1] != "blob"
        or GIT_OID_RE.fullmatch(fields[2]) is None
        or fields[3] != path_text
    ):
        raise _error(f"H-SYN component is not one exact Git blob: {path_text}")
    git_mode, oid = fields[0], fields[2]
    payload = _read_regular_file(path, metadata)
    source = cast(bytes, _git(root, "cat-file", "blob", oid, text=False))
    if payload != source:
        raise _error(f"H-SYN component differs from its Git blob: {path_text}")
    return {
        "path": path_text,
        "bytes": len(payload),
        "sha256": synthesis.sha256_bytes(payload),
        "git_mode": git_mode,
        "git_blob_oid": oid,
        "filesystem_mode": stat.S_IMODE(metadata.st_mode),
    }


def _collect_published_state(
    root: Path,
    *,
    verify_remote: bool,
    publication_phase: str | None = None,
) -> dict[str, Any]:
    head = _one_oid(root, "HEAD")
    if head == SOURCE_COMMIT:
        raise _error("P-SYN generation requires a published H-SYN commit")
    if publication_phase not in {None, "guarded_prelink", "guarded_postlink"}:
        raise _error("P-SYN publication phase is invalid")
    expected_status = (
        {
            AUTHORITY_PATH.as_posix(): "??",
            MANIFEST_PATH.as_posix(): "??",
        }
        if publication_phase == "guarded_postlink"
        else {}
    )
    if _parse_status(root) != expected_status:
        raise _error("P-SYN generation requires the exact clean worktree/index scope")
    components = _validate_published_h(root, head)
    refs = _validate_refs(root, head, verify_remote=verify_remote)
    contract = synthesis.load_contract(root=root, verify_inputs=False)
    if contract.closure_source_commit != SOURCE_COMMIT:
        raise _error("Synthesis contract source commit drifted")
    if publication_phase is None:
        _validate_empty_publication_namespace(root, contract)
    else:
        _validate_guarded_publication_namespace(
            root,
            contract,
            outputs_present=publication_phase == "guarded_postlink",
        )
    inputs = synthesis.collect_input_records(contract, root=root)
    return {
        "repository": refs,
        "closure_source_commit": SOURCE_COMMIT,
        "synthesis_implementation_commit": head,
        "h_scope": dict(H_SCOPE),
        "h_components": components,
        "allowed_inputs": inputs,
        "allowed_input_paths": list(contract.allowed_input_paths),
        "output_paths": list(contract.output_paths),
        "required_unavailable_models": list(contract.required_unavailable_models),
        "required_hypotheses": list(contract.required_hypotheses),
        "holm_universes": dict(contract.holm_universes),
        "final_closure_row_count": contract.final_closure_row_count,
        "claim_evidence_row_count": contract.claim_evidence_row_count,
        "table_row_counts": dict(contract.table_row_counts),
    }


def check_only(
    *, root: Path = PROJECT_ROOT, verify_remote: bool = True
) -> dict[str, Any]:
    """Validate H-SYN without creating guards, directories, or outputs."""

    root = root.resolve()
    head = _one_oid(root, "HEAD")
    if head == SOURCE_COMMIT:
        refs = _validate_refs(root, SOURCE_COMMIT, verify_remote=verify_remote)
        _validate_local_h_scope(root)
        contract = synthesis.load_contract(root=root, verify_inputs=True)
        _validate_empty_publication_namespace(root, contract)
        state = "ready_to_publish_h"
        implementation_commit: str | None = None
        component_count = len(H_SCOPE)
        input_count = len(contract.allowed_inputs)
    else:
        published = _collect_published_state(root, verify_remote=verify_remote)
        refs = cast(dict[str, str], published["repository"])
        state = "ready_to_generate"
        implementation_commit = cast(str, published["synthesis_implementation_commit"])
        component_count = len(cast(list[Any], published["h_components"]))
        input_count = len(cast(list[Any], published["allowed_inputs"]))
    return {
        "status": state,
        "gate": GATE,
        "closure_source_commit": SOURCE_COMMIT,
        "synthesis_implementation_commit": implementation_commit,
        "repository": refs,
        "h_component_count": component_count,
        "allowed_input_count": input_count,
        "writes_performed": False,
        "verification_commands_run": False,
        "dvc_commands_run": False,
        "raw_targets_accessed": False,
        "raw_outcomes_accessed": False,
        "scientific_network_commands_run": False,
    }


def _build_authority(state: Mapping[str, Any]) -> dict[str, Any]:
    records = cast(list[dict[str, Any]], state["allowed_inputs"])
    paths = cast(list[str], state["allowed_input_paths"])
    outputs = cast(list[str], state["output_paths"])
    components = cast(list[dict[str, Any]], state["h_components"])
    component_by_path = {record["path"]: record for record in components}
    schema_and_tests = [component_by_path[path] for path in SCHEMA_AND_TEST_PATHS]
    builder = component_by_path[BUILDER_PATH]
    authority: dict[str, Any] = {
        "authority_version": AUTHORITY_VERSION,
        "gate": GATE,
        "status": "locked_unpublished",
        "closure_source_commit": SOURCE_COMMIT,
        "synthesis_implementation_commit": state["synthesis_implementation_commit"],
        "synthesis_builder_blob_sha256": builder["sha256"],
        "synthesis_schema_and_tests_digest": synthesis.digest_records(schema_and_tests),
        "allowed_input_paths_digest": synthesis.digest_strings(paths),
        "allowed_input_records_digest": synthesis.digest_records(records),
        "output_paths_and_order_digest": synthesis.digest_strings(outputs),
        "allowed_input_paths": paths,
        "allowed_input_records": records,
        "ordered_output_paths": outputs,
        "h_component_records": components,
        "invariants": {
            "required_unavailable_models": state["required_unavailable_models"],
            "required_hypotheses": state["required_hypotheses"],
            "holm_universes": state["holm_universes"],
            "final_closure_row_count": state["final_closure_row_count"],
            "claim_evidence_row_count": state["claim_evidence_row_count"],
            "table_row_counts": state["table_row_counts"],
            "unavailable_models_must_remain_visible": True,
            "holm_universes_must_not_shrink": True,
            "non_estimable_is_never_zero": True,
        },
        "authorizations": dict(MUTATING_AUTHORIZATIONS),
    }
    validate_authority(authority)
    return authority


def validate_authority(payload: Mapping[str, Any]) -> None:
    required = {
        "authority_version",
        "gate",
        "status",
        "closure_source_commit",
        "synthesis_implementation_commit",
        "synthesis_builder_blob_sha256",
        "synthesis_schema_and_tests_digest",
        "allowed_input_paths_digest",
        "allowed_input_records_digest",
        "output_paths_and_order_digest",
        "allowed_input_paths",
        "allowed_input_records",
        "ordered_output_paths",
        "h_component_records",
        "invariants",
        "authorizations",
    }
    if set(payload) != required:
        raise _error("P-SYN authority keys drifted")
    if (
        payload["authority_version"] != AUTHORITY_VERSION
        or payload["gate"] != GATE
        or payload["status"] != "locked_unpublished"
        or payload["closure_source_commit"] != SOURCE_COMMIT
    ):
        raise _error("P-SYN fixed identity drifted")
    implementation = payload["synthesis_implementation_commit"]
    if not isinstance(implementation, str) or GIT_OID_RE.fullmatch(implementation) is None:
        raise _error("P-SYN implementation commit is invalid")
    paths = payload["allowed_input_paths"]
    records = payload["allowed_input_records"]
    outputs = payload["ordered_output_paths"]
    components = payload["h_component_records"]
    if not all(isinstance(value, list) for value in (paths, records, outputs, components)):
        raise _error("P-SYN record collections must be lists")
    if [record.get("path") for record in records] != paths:
        raise _error("P-SYN allowed paths and records differ")
    if payload["allowed_input_paths_digest"] != synthesis.digest_strings(paths):
        raise _error("P-SYN allowed path digest drifted")
    if payload["allowed_input_records_digest"] != synthesis.digest_records(records):
        raise _error("P-SYN allowed record digest drifted")
    if payload["output_paths_and_order_digest"] != synthesis.digest_strings(outputs):
        raise _error("P-SYN output order digest drifted")
    component_by_path = {record.get("path"): record for record in components}
    if set(component_by_path) != set(H_SCOPE) or len(component_by_path) != len(components):
        raise _error("P-SYN H component records drifted")
    if payload["synthesis_builder_blob_sha256"] != component_by_path[BUILDER_PATH].get("sha256"):
        raise _error("P-SYN builder digest drifted")
    selected = [component_by_path[path] for path in SCHEMA_AND_TEST_PATHS]
    if payload["synthesis_schema_and_tests_digest"] != synthesis.digest_records(selected):
        raise _error("P-SYN schema/tests digest drifted")
    invariants = payload["invariants"]
    if not isinstance(invariants, Mapping) or invariants != {
        "required_unavailable_models": ["P0", "P1", "A2"],
        "required_hypotheses": ["H1", "H2", "H3", "H4", "H5a", "H5b"],
        "holm_universes": {"A": 3, "B": 78, "C": 1, "D": 9, "E": 1},
        "final_closure_row_count": 130,
        "claim_evidence_row_count": 20,
        "table_row_counts": {
            "T01": 99,
            "T02": 33,
            "T03": 198,
            "T04": 24,
            "T05": 11,
            "T06": 48,
            "T07": 31,
            "T08": 92,
            "T09": 7,
            "T10": 36,
            "T11": 87,
            "T12": 5,
        },
        "unavailable_models_must_remain_visible": True,
        "holm_universes_must_not_shrink": True,
        "non_estimable_is_never_zero": True,
    }:
        raise _error("P-SYN scientific invariants drifted")
    if payload["authorizations"] != dict(MUTATING_AUTHORIZATIONS):
        raise _error("P-SYN mutating authorizations drifted")


def _build_manifest(authority_bytes: bytes, implementation_commit: str) -> dict[str, Any]:
    authority_record = {
        "path": AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": synthesis.sha256_bytes(authority_bytes),
    }
    return {
        "manifest_version": MANIFEST_VERSION,
        "gate": GATE,
        "status": "locked_unpublished",
        "closure_source_commit": SOURCE_COMMIT,
        "synthesis_implementation_commit": implementation_commit,
        "manifest_last": True,
        "ordered_paths": [AUTHORITY_PATH.as_posix(), MANIFEST_PATH.as_posix()],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(MUTATING_AUTHORIZATIONS),
    }


@dataclass(frozen=True)
class _OwnedFileAt:
    parent_fd: int
    name: str
    device: int
    inode: int


@dataclass(frozen=True)
class _OwnedDirectoryAt:
    parent_fd: int
    name: str
    fd: int
    device: int
    inode: int


def _stat_optional_at(parent_fd: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _open_directory_at(
    parent_fd: int, name: str, *, context: str
) -> _OwnedDirectoryAt:
    if not name or "/" in name or name in {".", ".."}:
        raise _error(f"{context} has an unsafe name")
    try:
        expected = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        raise _error(f"{context} is absent") from exc
    if not stat.S_ISDIR(expected.st_mode):
        raise _error(f"{context} is not a no-follow directory")
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=parent_fd,
    )
    observed = os.fstat(descriptor)
    if (observed.st_dev, observed.st_ino) != (expected.st_dev, expected.st_ino):
        os.close(descriptor)
        raise _error(f"{context} changed while opening")
    return _OwnedDirectoryAt(
        parent_fd,
        name,
        descriptor,
        observed.st_dev,
        observed.st_ino,
    )


def _require_owned_directory_at(
    owner: _OwnedDirectoryAt, *, context: str, mode: int | None = None
) -> None:
    current = _stat_optional_at(owner.parent_fd, owner.name)
    descriptor_metadata = os.fstat(owner.fd)
    if (
        current is None
        or not stat.S_ISDIR(current.st_mode)
        or (current.st_dev, current.st_ino) != (owner.device, owner.inode)
        or (descriptor_metadata.st_dev, descriptor_metadata.st_ino)
        != (owner.device, owner.inode)
        or (mode is not None and stat.S_IMODE(current.st_mode) != mode)
        or (
            mode is not None
            and stat.S_IMODE(descriptor_metadata.st_mode) != mode
        )
    ):
        raise _error(f"{context} ownership/path binding drifted")


def _mkdir_owned_at(
    parent_fd: int, name: str, *, mode: int, context: str
) -> _OwnedDirectoryAt:
    try:
        os.mkdir(name, mode=mode, dir_fd=parent_fd)
    except FileExistsError as exc:
        raise _error(f"{context} already exists") from exc
    metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    descriptor: int | None = None
    try:
        owner = _open_directory_at(parent_fd, name, context=context)
        descriptor = owner.fd
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
        _require_owned_directory_at(owner, context=context, mode=mode)
        return owner
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        current = _stat_optional_at(parent_fd, name)
        if current is not None and (
            current.st_dev,
            current.st_ino,
        ) == (metadata.st_dev, metadata.st_ino):
            os.rmdir(name, dir_fd=parent_fd)
        raise


def _rmdir_owned_at(owner: _OwnedDirectoryAt, *, context: str) -> None:
    current = _stat_optional_at(owner.parent_fd, owner.name)
    if current is None:
        return
    if (
        not stat.S_ISDIR(current.st_mode)
        or (current.st_dev, current.st_ino) != (owner.device, owner.inode)
    ):
        raise _error(f"{context} preserved a foreign replacement")
    try:
        os.rmdir(owner.name, dir_fd=owner.parent_fd)
    except OSError as exc:
        raise _error(f"{context} could not remove its owned directory") from exc
    if _stat_optional_at(owner.parent_fd, owner.name) is not None:
        raise _error(f"{context} rollback did not establish absence")


def _create_owned_file_at(
    parent_fd: int,
    name: str,
    payload: bytes,
    *,
    mode: int,
    context: str,
) -> _OwnedFileAt:
    if not name or "/" in name or name in {".", ".."}:
        raise _error(f"{context} has an unsafe name")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(name, flags, mode, dir_fd=parent_fd)
    metadata = os.fstat(descriptor)
    owner = _OwnedFileAt(parent_fd, name, metadata.st_dev, metadata.st_ino)
    primary: BaseException | None = None
    cleanup: BaseException | None = None
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise _error(f"{context} write made no progress")
            view = view[written:]
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
    except BaseException as exc:
        primary = exc
    try:
        os.close(descriptor)
    except BaseException as exc:
        cleanup = exc
    if primary is not None or cleanup is not None:
        try:
            _unlink_owned_file_at(owner, context=context)
        except BaseException as exc:
            cleanup = exc
        if cleanup is not None:
            raise _error(f"{context} partial-file cleanup failed") from cleanup
        if primary is not None:
            raise primary
    _require_owned_file_at(owner, context=context, link_count=1, mode=mode)
    return owner


def _require_owned_file_at(
    owner: _OwnedFileAt,
    *,
    context: str,
    link_count: int | None = None,
    mode: int | None = None,
) -> os.stat_result:
    current = _stat_optional_at(owner.parent_fd, owner.name)
    if (
        current is None
        or not stat.S_ISREG(current.st_mode)
        or (current.st_dev, current.st_ino) != (owner.device, owner.inode)
        or (link_count is not None and current.st_nlink != link_count)
        or (mode is not None and stat.S_IMODE(current.st_mode) != mode)
    ):
        raise _error(f"{context} ownership/link identity drifted")
    return current


def _read_owned_file_at(
    owner: _OwnedFileAt,
    *,
    context: str,
    link_count: int,
    mode: int,
) -> bytes:
    expected = _require_owned_file_at(
        owner, context=context, link_count=link_count, mode=mode
    )
    descriptor = os.open(
        owner.name,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=owner.parent_fd,
    )
    try:
        before = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (expected.st_dev, expected.st_ino):
            raise _error(f"{context} changed before read")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, HASH_CHUNK_SIZE)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
            after.st_nlink,
            stat.S_IMODE(after.st_mode),
        ) != (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
            before.st_nlink,
            stat.S_IMODE(before.st_mode),
        ):
            raise _error(f"{context} changed during read")
    finally:
        os.close(descriptor)
    return b"".join(chunks)


def _unlink_owned_file_at(owner: _OwnedFileAt, *, context: str) -> None:
    current = _stat_optional_at(owner.parent_fd, owner.name)
    if current is None:
        return
    if (
        not stat.S_ISREG(current.st_mode)
        or (current.st_dev, current.st_ino) != (owner.device, owner.inode)
    ):
        raise _error(f"{context} preserved a foreign replacement")
    os.unlink(owner.name, dir_fd=owner.parent_fd)
    if _stat_optional_at(owner.parent_fd, owner.name) is not None:
        raise _error(f"{context} rollback did not establish absence")


def _link_no_clobber(
    source: _OwnedFileAt,
    destination_parent_fd: int,
    destination_name: str,
) -> _OwnedFileAt:
    _require_owned_file_at(
        source, context="P-SYN link source", link_count=1, mode=0o644
    )
    try:
        os.link(
            source.name,
            destination_name,
            src_dir_fd=source.parent_fd,
            dst_dir_fd=destination_parent_fd,
            follow_symlinks=False,
        )
    except FileExistsError as exc:
        raise _error(f"P-SYN output already exists: {destination_name}") from exc
    except OSError as exc:
        current = _stat_optional_at(destination_parent_fd, destination_name)
        if current is not None and (
            current.st_dev,
            current.st_ino,
        ) == (source.device, source.inode):
            partial = _OwnedFileAt(
                destination_parent_fd,
                destination_name,
                source.device,
                source.inode,
            )
            try:
                _unlink_owned_file_at(partial, context="P-SYN partial link")
            except BaseException as cleanup_exc:
                raise _error("P-SYN partial-link cleanup failed closed") from cleanup_exc
        if exc.errno == errno.EXDEV:
            raise _error("P-SYN publication requires one filesystem") from exc
        raise
    published = _OwnedFileAt(
        destination_parent_fd,
        destination_name,
        source.device,
        source.inode,
    )
    try:
        _require_owned_file_at(
            published, context="P-SYN published output", link_count=2, mode=0o644
        )
    except BaseException:
        _unlink_owned_file_at(published, context="P-SYN invalid published link")
        raise
    return published


def _acquire_guard(
    tmp_directory: _OwnedDirectoryAt,
) -> tuple[_OwnedDirectoryAt, _OwnedFileAt]:
    coordination = _mkdir_owned_at(
        tmp_directory.fd,
        GUARD_PATH.parent.name,
        mode=0o700,
        context="P-SYN coordination namespace",
    )
    try:
        guard = _create_owned_file_at(
            coordination.fd,
            GUARD_PATH.name,
            synthesis.canonical_json_bytes(
                {"gate": GATE, "pid": os.getpid(), "nonce": secrets.token_hex(16)}
            ),
            mode=0o600,
            context="P-SYN guard",
        )
        os.fsync(coordination.fd)
        return coordination, guard
    except BaseException:
        try:
            _rmdir_owned_at(
                coordination, context="P-SYN coordination namespace"
            )
        finally:
            os.close(coordination.fd)
        raise


def _validate_guarded_publication_namespace(
    root: Path,
    contract: synthesis.SynthesisContract,
    *,
    outputs_present: bool,
) -> None:
    coordination = root / GUARD_PATH.parent
    guard = root / GUARD_PATH
    coordination_metadata = coordination.lstat()
    guard_metadata = guard.lstat()
    if (
        coordination.is_symlink()
        or not stat.S_ISDIR(coordination_metadata.st_mode)
        or stat.S_IMODE(coordination_metadata.st_mode) != 0o700
        or guard.is_symlink()
        or not stat.S_ISREG(guard_metadata.st_mode)
        or guard_metadata.st_nlink != 1
        or stat.S_IMODE(guard_metadata.st_mode) != 0o600
    ):
        raise _error("P-SYN guarded coordination identity drifted")
    _assert_absent(root / synthesis.SYNTHESIS_ROOT, context="R-SYN namespace")
    parent = root / AUTHORITY_PATH.parent
    if parent.is_symlink() or not parent.is_dir():
        raise _error("P-SYN output parent must be a regular directory")
    for path in parent.iterdir():
        if path.name.startswith(TEMP_PREFIX):
            raise _error(f"P-SYN temporary namespace is not empty: {path}")
    for relative in (AUTHORITY_PATH, MANIFEST_PATH):
        path = root / relative
        if outputs_present:
            metadata = path.lstat()
            if (
                path.is_symlink()
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
                or stat.S_IMODE(metadata.st_mode) != 0o644
            ):
                raise _error(f"P-SYN guarded output identity drifted: {relative}")
        else:
            _assert_absent(path, context=f"P-SYN guarded output {relative}")
    if tuple(contract.output_paths)[-1] != (
        "reports/closure_v1/11_synthesis/synthesis_bundle_manifest.json"
    ):
        raise _error("R-SYN manifest-last order drifted")


def publish_authority_bundle(
    root: Path,
    authority: Mapping[str, Any],
    *,
    prepublish_validator: Callable[[], None] | None = None,
    postpublish_validator: Callable[[], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Publish exact2A through anchored dirfds, manifest last."""

    validate_authority(authority)
    authority_bytes = synthesis.canonical_json_bytes(authority)
    implementation = cast(str, authority["synthesis_implementation_commit"])
    manifest_bytes = synthesis.canonical_json_bytes(
        _build_manifest(authority_bytes, implementation)
    )
    contract = synthesis.load_contract(root=root, verify_inputs=False)
    _validate_empty_publication_namespace(root, contract)

    root = root.resolve()
    root_fd = os.open(
        root, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    )
    open_fds: list[int] = [root_fd]
    configs: _OwnedDirectoryAt | None = None
    output_parent: _OwnedDirectoryAt | None = None
    tmp_directory: _OwnedDirectoryAt | None = None
    tmp_root_owned: _OwnedDirectoryAt | None = None
    coordination: _OwnedDirectoryAt | None = None
    guard: _OwnedFileAt | None = None
    temporaries: list[_OwnedFileAt] = []
    published: list[_OwnedFileAt] = []
    primary: BaseException | None = None
    cleanup_errors: list[BaseException] = []
    payloads = (authority_bytes, manifest_bytes)
    output_names = (AUTHORITY_PATH.name, MANIFEST_PATH.name)
    token = secrets.token_hex(16)
    temporary_names = (
        f"{TEMP_PREFIX}{token}.authority.tmp",
        f"{TEMP_PREFIX}{token}.manifest.tmp",
    )
    try:
        configs = _open_directory_at(root_fd, "configs", context="configs root")
        open_fds.append(configs.fd)
        output_parent = _open_directory_at(
            configs.fd,
            AUTHORITY_PATH.parent.name,
            context="P-SYN output parent",
        )
        open_fds.append(output_parent.fd)
        if any(
            _stat_optional_at(output_parent.fd, name) is not None
            for name in output_names
        ) or any(
            name.startswith(TEMP_PREFIX) for name in os.listdir(output_parent.fd)
        ):
            raise _error("P-SYN publication namespace is not empty")

        if _stat_optional_at(root_fd, "tmp") is None:
            tmp_root_owned = _mkdir_owned_at(
                root_fd, "tmp", mode=0o700, context="P-SYN temporary root"
            )
            tmp_directory = tmp_root_owned
            os.fsync(root_fd)
        else:
            tmp_directory = _open_directory_at(
                root_fd, "tmp", context="P-SYN temporary root"
            )
        open_fds.append(tmp_directory.fd)
        coordination, guard = _acquire_guard(tmp_directory)
        open_fds.append(coordination.fd)

        for directory, context, mode in (
            (configs, "configs root", None),
            (output_parent, "P-SYN output parent", None),
            (tmp_directory, "P-SYN temporary root", 0o700 if tmp_root_owned else None),
            (coordination, "P-SYN coordination namespace", 0o700),
        ):
            _require_owned_directory_at(directory, context=context, mode=mode)
        if prepublish_validator is not None:
            prepublish_validator()
        _require_owned_directory_at(
            output_parent, context="P-SYN output parent"
        )
        _require_owned_directory_at(
            tmp_directory,
            context="P-SYN temporary root",
            mode=0o700 if tmp_root_owned else None,
        )

        for name, payload in zip(temporary_names, payloads, strict=True):
            temporary = _create_owned_file_at(
                output_parent.fd,
                name,
                payload,
                mode=0o644,
                context="P-SYN temporary",
            )
            temporaries.append(temporary)
            if _read_owned_file_at(
                temporary,
                context="P-SYN temporary",
                link_count=1,
                mode=0o644,
            ) != payload:
                raise _error("P-SYN temporary bytes drifted")
        os.fsync(output_parent.fd)

        for index, destination_name in enumerate(output_names):
            _require_owned_directory_at(
                output_parent, context="P-SYN output parent"
            )
            published.append(
                _link_no_clobber(
                    temporaries[index], output_parent.fd, destination_name
                )
            )
            # Index one is the companion and therefore the final link event.
            _require_owned_directory_at(
                output_parent, context="P-SYN output parent"
            )
            os.fsync(output_parent.fd)

        for owner, payload in zip(published, payloads, strict=True):
            if _read_owned_file_at(
                owner,
                context="P-SYN linked output",
                link_count=2,
                mode=0o644,
            ) != payload:
                raise _error("P-SYN linked output bytes drifted")
        for owner in reversed(temporaries):
            _unlink_owned_file_at(owner, context="P-SYN temporary")
        os.fsync(output_parent.fd)
        for owner, payload in zip(published, payloads, strict=True):
            if _read_owned_file_at(
                owner,
                context="P-SYN final output",
                link_count=1,
                mode=0o644,
            ) != payload:
                raise _error("P-SYN final output bytes drifted")

        if postpublish_validator is not None:
            postpublish_validator()
        _require_owned_directory_at(
            output_parent, context="P-SYN output parent"
        )
        for owner, payload in zip(published, payloads, strict=True):
            if _read_owned_file_at(
                owner,
                context="P-SYN post-validation output",
                link_count=1,
                mode=0o644,
            ) != payload:
                raise _error("P-SYN post-validation output bytes drifted")

        _unlink_owned_file_at(guard, context="P-SYN guard")
        os.fsync(coordination.fd)
        _rmdir_owned_at(coordination, context="P-SYN coordination namespace")
        os.fsync(tmp_directory.fd)
        if tmp_root_owned is not None:
            _rmdir_owned_at(tmp_root_owned, context="P-SYN temporary root")
            os.fsync(root_fd)

        _require_owned_directory_at(
            output_parent, context="P-SYN output parent"
        )
        for owner, payload in zip(published, payloads, strict=True):
            if _read_owned_file_at(
                owner,
                context="P-SYN committed output",
                link_count=1,
                mode=0o644,
            ) != payload:
                raise _error("P-SYN committed output bytes drifted")
    except BaseException as exc:
        primary = exc
        for owner in reversed(published):
            try:
                _unlink_owned_file_at(owner, context="P-SYN published output")
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
    finally:
        for owner in reversed(temporaries):
            try:
                _unlink_owned_file_at(owner, context="P-SYN temporary")
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        if guard is not None:
            try:
                _unlink_owned_file_at(guard, context="P-SYN guard")
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        if coordination is not None:
            try:
                _rmdir_owned_at(
                    coordination, context="P-SYN coordination namespace"
                )
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        if tmp_root_owned is not None:
            try:
                _rmdir_owned_at(tmp_root_owned, context="P-SYN temporary root")
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        for descriptor in (
            output_parent.fd if output_parent else None,
            tmp_directory.fd if tmp_directory else None,
            root_fd,
        ):
            if descriptor is not None:
                try:
                    os.fsync(descriptor)
                except BaseException as cleanup_exc:
                    cleanup_errors.append(cleanup_exc)
        if cleanup_errors:
            for owner in reversed(published):
                try:
                    _unlink_owned_file_at(
                        owner, context="P-SYN published output"
                    )
                except BaseException as cleanup_exc:
                    cleanup_errors.append(cleanup_exc)
        for descriptor in reversed(open_fds):
            try:
                os.close(descriptor)
            except OSError:
                pass

    if cleanup_errors:
        message = "; ".join(
            f"{type(exc).__name__}: {exc}" for exc in cleanup_errors
        )
        raise _error(
            f"P-SYN cleanup could not complete safely: {message}"
        ) from cleanup_errors[0]
    if primary is not None:
        raise primary
    return (
        {
            "path": AUTHORITY_PATH.as_posix(),
            "bytes": len(authority_bytes),
            "sha256": synthesis.sha256_bytes(authority_bytes),
        },
        {
            "path": MANIFEST_PATH.as_posix(),
            "bytes": len(manifest_bytes),
            "sha256": synthesis.sha256_bytes(manifest_bytes),
        },
    )


def generate(
    *, root: Path = PROJECT_ROOT, verify_remote: bool = True
) -> dict[str, Any]:
    root = root.resolve()
    before = _collect_published_state(root, verify_remote=verify_remote)
    authority = _build_authority(before)
    after = _collect_published_state(root, verify_remote=verify_remote)
    if before != after:
        raise _error("H-SYN repository or structured inputs changed before publication")

    def revalidate_before_link() -> None:
        observed = _collect_published_state(
            root,
            verify_remote=verify_remote,
            publication_phase="guarded_prelink",
        )
        if observed != before:
            raise _error("H-SYN repository or inputs changed before P-SYN publication")

    def revalidate_after_links() -> None:
        observed = _collect_published_state(
            root,
            verify_remote=verify_remote,
            publication_phase="guarded_postlink",
        )
        if observed != before:
            raise _error("H-SYN repository or inputs changed during P-SYN publication")

    authority_record, manifest_record = publish_authority_bundle(
        root,
        authority,
        prepublish_validator=revalidate_before_link,
        postpublish_validator=revalidate_after_links,
    )
    return {
        "status": "authority_bundle_written_unpublished",
        "gate": GATE,
        "closure_source_commit": SOURCE_COMMIT,
        "synthesis_implementation_commit": before["synthesis_implementation_commit"],
        "authority": authority_record,
        "manifest": manifest_record,
        "dvc_commands_run": False,
        "raw_targets_accessed": False,
        "raw_outcomes_accessed": False,
        "scientific_network_commands_run": False,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--generate", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = check_only() if args.check_only else generate()
    except synthesis.SynthesisContractError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(synthesis.canonical_json_bytes(payload).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
