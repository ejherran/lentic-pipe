#!/usr/bin/env python
"""Validate H-CERT3 and publish the immutable P-CERT3 authority bundle.

The check-only path is non-writing.  It accepts either the exact local H-CERT
overlay over the superseded published P-CERT2 commit or the clean, published H-CERT
commit.  Generation is narrower: it requires the latter, aligned local and
live-remote refs, an empty DVC status, a locked public-test suite, and empty
P-CERT/R-CERT namespaces.  It never pulls DVC data, runs tests, opens Parquet,
or performs Git publication.  Its local two-file publication is serialized by
an exclusive flock on a retained ``.git`` directory descriptor; the legacy
disposable guard path must stay absent.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import fcntl
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence, cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.reporting import phase4_final_certification_contract as certification  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GATE = "P-CERT"
AUTHORITY_VERSION = certification.AUTHORITY_VERSION
MANIFEST_VERSION = certification.AUTHORITY_MANIFEST_VERSION
CLOSURE_SOURCE_COMMIT = "ea8ddce7f8edb9a61db97e29178e52603fa371b1"
R_SYN_COMMIT = "528dcb74a7c08b65f262901e4562a67b784db8c9"
EDITORIAL_COMMIT = "d1daa3059462854d6ddf5199fbc05515cec76982"
H1_CERT_COMMIT = certification.H1_CERT_COMMIT
P1_CERT_COMMIT = certification.P1_CERT_COMMIT
H2_CERT_COMMIT = certification.H2_CERT_COMMIT
P2_CERT_COMMIT = certification.P2_CERT_COMMIT
AUTHORITY_PATH = certification.AUTHORITY_PATH
MANIFEST_PATH = certification.AUTHORITY_MANIFEST_PATH
H1_AUTHORITY_PATH = certification.H1_AUTHORITY_PATH
H1_MANIFEST_PATH = certification.H1_AUTHORITY_MANIFEST_PATH
H2_AUTHORITY_PATH = certification.H2_AUTHORITY_PATH
H2_MANIFEST_PATH = certification.H2_AUTHORITY_MANIFEST_PATH
GUARD_PATH = certification.GUARD_PATH
TEMP_PREFIX = ".phase4_final_certification_authority."
CLEANUP_TOMBSTONE_PREFIX = ".phase4_final_certification_cleanup_"
DIRECTORY_TEMP_PREFIX = ".phase4_final_certification_mkdir_"
HASH_CHUNK_SIZE = 1024 * 1024
GIT_OID_RE = re.compile(r"^[0-9a-f]{40,64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MD5_RE = re.compile(r"^[0-9a-f]{32}$")

H1_SCOPE: Mapping[str, str] = {
    "configs/closure_v1/phase4_final_certification.schema.json": "A",
    "configs/closure_v1/phase4_final_certification.yaml": "A",
    "docs/closure_v1/PHASE4_FINAL_CERTIFICATION.md": "A",
    "src/data/prepare_commit_artifacts.py": "M",
    "src/experiments/lock_phase4_final_certification.py": "A",
    "src/reporting/build_phase4_final_certification.py": "A",
    "src/reporting/phase4_final_certification_contract.py": "A",
    "tests/test_build_phase4_final_certification.py": "A",
    "tests/test_lock_phase4_final_certification.py": "A",
    "tests/test_phase4_final_certification_contract.py": "A",
    "tests/test_prepare_commit_artifacts.py": "M",
}
H_GIT_MODES: Mapping[str, str] = {
    path: "100755" if path == "src/data/prepare_commit_artifacts.py" else "100644"
    for path in H1_SCOPE
}
H2_SCOPE: Mapping[str, str] = {path: "M" for path in H1_SCOPE}
H_SCOPE: Mapping[str, str] = {path: "M" for path in H1_SCOPE}
P1_SCOPE: Mapping[str, str] = {
    H1_AUTHORITY_PATH.as_posix(): "A",
    H1_MANIFEST_PATH.as_posix(): "A",
}
P2_SCOPE: Mapping[str, str] = {
    H2_AUTHORITY_PATH.as_posix(): "A",
    H2_MANIFEST_PATH.as_posix(): "A",
}
P_SCOPE: Mapping[str, str] = {
    AUTHORITY_PATH.as_posix(): "A",
    MANIFEST_PATH.as_posix(): "A",
}
R_SCOPE: Mapping[str, str] = {
    "reports/closure_v1/12_certification/public_tests.xml": "A",
    "reports/closure_v1/12_certification/test_report.md": "A",
    "reports/closure_v1/12_certification/openapi.json": "A",
    "reports/closure_v1/12_certification/openapi_contract_report.md": "A",
    "reports/closure_v1/12_certification/end_to_end_report.md": "A",
    "reports/closure_v1/12_certification/environment.json": "A",
    "reports/closure_v1/12_certification/FINAL_DOCTORAL_CERTIFICATION_REPORT.md": "A",
    "reports/closure_v1/12_certification/final_certification_manifest.json": "A",
}
ANCHOR_PATHS = (
    ".dvc/config",
    "docs/API_DATASET_CONTRACT.md",
    "docs/API_PROTOCOL.md",
    "poetry.lock",
    "pyproject.toml",
    "reports/closure_v1/11_synthesis/THESIS_CLAIM_EVIDENCE_MATRIX.csv",
    "reports/closure_v1/11_synthesis/synthesis_bundle_manifest.json",
    "reports/thesis/chapter_iv_evidence_matrix_manifest.json",
    "reports/thesis/phase4_manuscript_build_receipt.json",
    "reports/thesis/phase4_manuscript_build_receipt_manifest.json",
)


def _error(message: str) -> certification.FinalCertificationContractError:
    return certification.FinalCertificationContractError(message)


def _git(root: Path, *args: str, text: bool = True) -> str | bytes:
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
    if set(records) != {"HEAD", "refs/heads/main"}:
        raise _error("Remote HEAD and main are absent or contain extra records")
    if len(set(records.values())) != 1:
        raise _error("Remote HEAD and main are misaligned")
    return records["refs/heads/main"]


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
            raise _error("Renames and copies are forbidden in H-CERT")
        if path in records:
            raise _error(f"Git status repeats a path: {path}")
        records[path] = code
    return records


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
            raise _error("Certification commit contains an unsupported diff record")
        if fields[1] in records:
            raise _error("Certification commit repeats a path")
        records[fields[1]] = fields[0]
    return records


def _validate_parent(root: Path, commit: str, parent: str, *, context: str) -> None:
    values = cast(
        str, _git(root, "rev-list", "--parents", "-n", "1", commit)
    ).split()
    if values != [commit, parent]:
        raise _error(f"{context} must be the direct single-parent child of {parent}")


def _validate_relative(path_text: str, *, context: str) -> PurePosixPath:
    if "\\" in path_text or "\x00" in path_text:
        raise _error(f"{context} path is not canonical: {path_text!r}")
    relative = PurePosixPath(path_text)
    if relative.is_absolute() or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise _error(f"{context} path is not repository-relative: {path_text!r}")
    return relative


def _regular_file(
    root: Path,
    path_text: str,
    *,
    expected_mode: int | None,
    context: str,
) -> certification._AnchoredRegularFile:
    _validate_relative(path_text, context=context)
    modes = None if expected_mode is None else frozenset({expected_mode})
    return certification._open_anchored_regular_file(
        root,
        path_text,
        expected_modes=modes,
        context=context,
    )


def _read_regular(
    anchored: certification._AnchoredRegularFile,
    *,
    context: str,
) -> bytes:
    if anchored.context != context:
        raise _error(f"{context} anchored read context drifted")
    return certification._read_stable_file(anchored)


def _tree_blob(
    root: Path,
    commit: str,
    path_text: str,
    *,
    expected_mode: str,
    context: str,
) -> tuple[str, bytes]:
    output = cast(str, _git(root, "ls-tree", commit, "--", path_text)).strip()
    fields = output.split(None, 3)
    if (
        len(fields) != 4
        or fields[0] != expected_mode
        or fields[1] != "blob"
        or GIT_OID_RE.fullmatch(fields[2]) is None
        or fields[3] != path_text
    ):
        raise _error(f"{context} is not one exact Git blob: {path_text}")
    return fields[2], cast(
        bytes, _git(root, "cat-file", "blob", fields[2], text=False)
    )


def _component_record(root: Path, commit: str, path_text: str) -> dict[str, Any]:
    git_mode = H_GIT_MODES[path_text]
    oid, git_payload = _tree_blob(
        root,
        commit,
        path_text,
        expected_mode=git_mode,
        context="Published H-CERT component",
    )
    anchored = _regular_file(
        root,
        path_text,
        expected_mode=int(git_mode[-3:], 8),
        context="H-CERT component",
    )
    try:
        payload = _read_regular(anchored, context="H-CERT component")
        certification._revalidate_anchored_file(anchored)
        if payload != git_payload:
            raise _error(f"H-CERT component differs from its Git blob: {path_text}")
        if not payload:
            raise _error(f"H-CERT component must be non-empty: {path_text}")
        return {
            "path": path_text,
            "bytes": len(payload),
            "sha256": certification.sha256_bytes(payload),
            "git_mode": git_mode,
            "git_blob_oid": oid,
            "filesystem_mode": stat.S_IMODE(anchored.metadata.st_mode),
        }
    finally:
        certification._close_anchored_file(anchored)


def _validate_editorial_topology(root: Path) -> None:
    common = cast(
        str, _git(root, "merge-base", CLOSURE_SOURCE_COMMIT, R_SYN_COMMIT)
    ).strip()
    if common != CLOSURE_SOURCE_COMMIT:
        raise _error("Closure source must remain an ancestor of R-SYN")
    _validate_parent(
        root,
        EDITORIAL_COMMIT,
        R_SYN_COMMIT,
        context="Published editorial commit",
    )
    _validate_parent(
        root,
        H1_CERT_COMMIT,
        EDITORIAL_COMMIT,
        context="Published historical H-CERT1 commit",
    )
    if _commit_scope(root, H1_CERT_COMMIT) != dict(H1_SCOPE):
        raise _error("Published historical H-CERT1 scope is not exact 9A+2M")
    _validate_parent(
        root,
        P1_CERT_COMMIT,
        H1_CERT_COMMIT,
        context="Published superseded P-CERT1 commit",
    )
    if _commit_scope(root, P1_CERT_COMMIT) != dict(P1_SCOPE):
        raise _error("Published superseded P-CERT1 scope is not exact 2A")
    _validate_parent(
        root,
        H2_CERT_COMMIT,
        P1_CERT_COMMIT,
        context="Published historical H-CERT2 commit",
    )
    if _commit_scope(root, H2_CERT_COMMIT) != dict(H2_SCOPE):
        raise _error("Published historical H-CERT2 scope is not exact 11M")
    _validate_parent(
        root,
        P2_CERT_COMMIT,
        H2_CERT_COMMIT,
        context="Published superseded P-CERT2 commit",
    )
    if _commit_scope(root, P2_CERT_COMMIT) != dict(P2_SCOPE):
        raise _error("Published superseded P-CERT2 scope is not exact 2A")


def _validate_local_h(root: Path) -> None:
    _validate_editorial_topology(root)
    status = _parse_status(root)
    if set(status) != set(H_SCOPE):
        raise _error("Local H-CERT3 scope is not the exact frozen 11M path set")
    for path_text in H_SCOPE:
        code = status[path_text]
        if code not in {"M ", " M"}:
            raise _error(f"Local H-CERT3 status drifted for {path_text}: {code!r}")
        mode = H_GIT_MODES[path_text]
        anchored = _regular_file(
            root,
            path_text,
            expected_mode=int(mode[-3:], 8),
            context="Local H-CERT component",
        )
        try:
            parent_entry = cast(
                str, _git(root, "ls-tree", P2_CERT_COMMIT, "--", path_text)
            ).strip()
            payload = _read_regular(
                anchored,
                context="Local H-CERT component",
            )
            certification._revalidate_anchored_file(anchored)
            if not payload:
                raise _error(
                    f"Local H-CERT component must be non-empty: {path_text}"
                )
            if not parent_entry:
                raise _error(f"H-CERT3 parent component is absent at P-CERT2: {path_text}")
            _, parent_payload = _tree_blob(
                root,
                P2_CERT_COMMIT,
                path_text,
                expected_mode=mode,
                context="P-CERT2 parent component",
            )
            certification._revalidate_anchored_file(anchored)
            if payload == parent_payload:
                raise _error(f"H-CERT3 modification has unchanged bytes: {path_text}")
        finally:
            certification._close_anchored_file(anchored)


def _validate_published_h(root: Path, head: str) -> list[dict[str, Any]]:
    _validate_editorial_topology(root)
    _validate_parent(root, head, P2_CERT_COMMIT, context="Published H-CERT3 commit")
    if _commit_scope(root, head) != dict(H_SCOPE):
        raise _error("Published H-CERT3 scope is not the exact frozen 11M set")
    records: list[dict[str, Any]] = []
    for path_text in H_SCOPE:
        mode = H_GIT_MODES[path_text]
        oid, _payload = _tree_blob(
            root,
            head,
            path_text,
            expected_mode=mode,
            context="Published H-CERT component",
        )
        parent_entry = cast(
            str, _git(root, "ls-tree", P2_CERT_COMMIT, "--", path_text)
        ).strip()
        if not parent_entry:
            raise _error(f"Published H-CERT3 parent is absent at P-CERT2: {path_text}")
        parent_oid, _ = _tree_blob(
            root,
            P2_CERT_COMMIT,
            path_text,
            expected_mode=mode,
            context="P-CERT2 parent component",
        )
        if oid == parent_oid:
            raise _error(f"Published H-CERT3 modification is unchanged: {path_text}")
        records.append(_component_record(root, head, path_text))
    return records


def _assert_absent(path: Path, *, context: str) -> None:
    try:
        path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise _error(f"Cannot establish {context} absence: {path}") from exc
    raise _error(f"{context} must be absent: {path}")


def _validate_empty_namespaces(root: Path) -> None:
    _assert_absent(root / AUTHORITY_PATH, context="P-CERT authority")
    _assert_absent(root / MANIFEST_PATH, context="P-CERT companion")
    _assert_absent(root / GUARD_PATH, context="P-CERT legacy guard")
    _assert_absent(
        root / certification.CERTIFICATION_ROOT,
        context="R-CERT output namespace",
    )
    parent = root / AUTHORITY_PATH.parent
    metadata = parent.lstat()
    if parent.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise _error("P-CERT output parent must be a non-symlink directory")
    for child in parent.iterdir():
        if child.name.startswith((TEMP_PREFIX, CLEANUP_TOMBSTONE_PREFIX)):
            raise _error(f"P-CERT temporary namespace is not empty: {child}")


def _dvc_status(root: Path) -> dict[str, Any]:
    anchored = _regular_file(
        root,
        ".venv/bin/dvc",
        expected_mode=0o755,
        context="Pinned DVC executable",
    )
    try:
        executable_metadata = certification._revalidate_anchored_file(anchored)
        if stat.S_IMODE(executable_metadata.st_mode) != 0o755:
            raise _error("Pinned DVC executable mode drifted")
        descriptor_path = f"/proc/self/fd/{anchored.fd}"
        if not Path("/proc/self/fd").is_dir():
            raise _error("Pinned DVC descriptor execution is unavailable")
        environment = os.environ.copy()
        environment["DVC_NO_ANALYTICS"] = "1"
        process = subprocess.run(
            [descriptor_path, "status", "--json"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            pass_fds=(anchored.fd,),
        )
        certification._revalidate_anchored_file(anchored)
        if process.returncode != 0:
            raise _error(f"DVC status failed: {process.stderr.strip()}")
        try:
            payload = json.loads(process.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise _error("DVC status did not return JSON") from exc
        if not isinstance(payload, dict):
            raise _error("DVC status must return one JSON object")
        if payload:
            raise _error("P-CERT requires exact empty repository DVC status")
        return payload
    finally:
        certification._close_anchored_file(anchored)


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if hasattr(value, "__dict__"):
        return {
            str(key): _plain(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return value


def _contract_value(contract: Any, *names: str) -> Any:
    for name in names:
        if hasattr(contract, name):
            return getattr(contract, name)
    raise _error(f"Final certification contract lacks required field: {names[0]}")


def _suite_snapshot(contract: Any) -> dict[str, Any]:
    suite = _contract_value(contract, "test_suite", "test_certification")
    plain = _plain(suite)
    if not isinstance(plain, Mapping):
        raise _error("Final certification suite has an invalid representation")
    lock = {
        "status": plain.get("status"),
        "selector_count": plain.get("selector_count"),
        "collected_test_count": plain.get("collected_test_count"),
        "nodeids_sha256": plain.get("nodeids_sha256"),
        "allowed_skip_count": plain.get("allowed_skip_count"),
    }
    if lock != {
        "status": certification.LOCKED_SUITE_STATUS,
        "selector_count": certification.LOCKED_SUITE_SELECTOR_COUNT,
        "collected_test_count": certification.LOCKED_SUITE_COLLECTED_TEST_COUNT,
        "nodeids_sha256": certification.LOCKED_SUITE_NODEIDS_SHA256,
        "allowed_skip_count": certification.LOCKED_SUITE_ALLOWED_SKIP_COUNT,
    }:
        raise _error("P-CERT generation requires the exact locked public-test suite")
    selectors = plain.get("positive_test_paths")
    if not isinstance(selectors, list) or not selectors:
        raise _error("P-CERT public-test selector set is absent")
    resolved_selectors = list(_contract_value(suite, "selectors"))
    if not resolved_selectors:
        raise _error("P-CERT resolved test selector set is absent")
    return {
        "suite_kind": plain.get("suite_kind"),
        "positive_test_paths": selectors,
        "exact_skipped_nodes": plain.get("exact_skipped_nodes"),
        "exact_skip_reason": plain.get("exact_skip_reason"),
        "e2e_nodes": plain.get("e2e_nodes"),
        "selectors": resolved_selectors,
        "command_template": plain.get("command_template"),
        "static_commands": plain.get("static_commands"),
        "suite_lock": lock,
    }


def _assert_contract_identity(contract: Any) -> None:
    expected = {
        "closure_source_commit": CLOSURE_SOURCE_COMMIT,
        "r_syn_commit": R_SYN_COMMIT,
        "editorial_commit": EDITORIAL_COMMIT,
        "h1_cert_commit": H1_CERT_COMMIT,
        "p1_cert_commit": P1_CERT_COMMIT,
        "h2_cert_commit": H2_CERT_COMMIT,
        "p2_cert_commit": P2_CERT_COMMIT,
    }
    for name, value in expected.items():
        observed = _contract_value(contract, name)
        if observed != value:
            raise _error(f"Final certification contract {name} drifted")
    if dict(certification.expected_h_scope()) != dict(H_SCOPE):
        raise _error("Final certification contract H-CERT scope drifted")
    if dict(certification.expected_h1_scope()) != dict(H1_SCOPE):
        raise _error("Final certification contract H-CERT1 scope drifted")
    if dict(certification.expected_p1_scope()) != dict(P1_SCOPE):
        raise _error("Final certification contract P-CERT1 scope drifted")
    if dict(certification.expected_h2_scope()) != dict(H2_SCOPE):
        raise _error("Final certification contract H-CERT2 scope drifted")
    if dict(certification.expected_p2_scope()) != dict(P2_SCOPE):
        raise _error("Final certification contract P-CERT2 scope drifted")
    if dict(certification.expected_p_scope()) != dict(P_SCOPE):
        raise _error("Final certification contract P-CERT scope drifted")
    if dict(certification.expected_r_scope()) != dict(R_SCOPE):
        raise _error("Final certification contract R-CERT scope drifted")
    if dict(certification.expected_h_modes()) != dict(H_GIT_MODES):
        raise _error("Final certification contract H-CERT Git modes drifted")
    if dict(certification.expected_p_modes()) != {
        path: "100644" for path in P_SCOPE
    }:
        raise _error("Final certification contract P-CERT Git modes drifted")
    if dict(certification.expected_h2_modes()) != dict(H_GIT_MODES):
        raise _error("Final certification contract H-CERT2 Git modes drifted")
    if dict(certification.expected_p2_modes()) != {
        path: "100644" for path in P2_SCOPE
    }:
        raise _error("Final certification contract P-CERT2 Git modes drifted")
    if dict(certification.expected_r_modes()) != {
        path: "100644" for path in R_SCOPE
    }:
        raise _error("Final certification contract R-CERT Git modes drifted")


def _collect_contract_state(contract: Any, root: Path) -> dict[str, Any]:
    h1_records, p1_records, h2_records, p2_records = (
        certification._historical_h1_p1_h2_p2_records(
        contract,
        root=root,
        )
    )
    anchors = certification.collect_anchor_input_records(contract, root=root)
    pointer_records = certification.collect_dvc_pointer_records(contract, root=root)
    anchor_paths = [record["path"] for record in anchors]
    if tuple(anchor_paths) != ANCHOR_PATHS:
        raise _error("P-CERT anchor input path order drifted")
    if len(pointer_records) != 8 or len({r["path"] for r in pointer_records}) != 8:
        raise _error("P-CERT requires exactly eight distinct DVC pointer records")
    output_paths = list(R_SCOPE)
    contract_outputs = list(_contract_value(contract, "output_paths"))
    if contract_outputs != output_paths:
        raise _error("P-CERT ordered R-CERT outputs drifted")
    return {
        "h1_component_records": h1_records,
        "p1_component_records": p1_records,
        "h2_component_records": h2_records,
        "p2_component_records": p2_records,
        "anchor_input_records": anchors,
        "dvc_pointer_records": pointer_records,
        "suite": _suite_snapshot(contract),
        "ordered_output_paths": output_paths,
    }


def _validate_publication_namespace(root: Path, *, outputs_present: bool) -> None:
    _assert_absent(root / GUARD_PATH, context="P-CERT legacy guard")
    _assert_absent(
        root / certification.CERTIFICATION_ROOT,
        context="R-CERT output namespace",
    )
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
                raise _error(f"P-CERT publication output identity drifted: {relative}")
        else:
            _assert_absent(path, context=f"P-CERT publication output {relative}")


def _collect_published_state(
    root: Path,
    *,
    verify_remote: bool,
    publication_phase: str | None = None,
    check_dvc: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    if publication_phase not in {None, "flock_prelink", "flock_postlink"}:
        raise _error("P-CERT publication phase is invalid")
    head = _one_oid(root, "HEAD")
    if head in {
        R_SYN_COMMIT,
        EDITORIAL_COMMIT,
        H1_CERT_COMMIT,
        P1_CERT_COMMIT,
        H2_CERT_COMMIT,
        P2_CERT_COMMIT,
    }:
        raise _error("P-CERT3 requires a separately published H-CERT3 commit")
    expected_status = (
        {
            AUTHORITY_PATH.as_posix(): "??",
            MANIFEST_PATH.as_posix(): "??",
        }
        if publication_phase == "flock_postlink"
        else {}
    )
    if _parse_status(root) != expected_status:
        raise _error("P-CERT generation requires the exact clean worktree/index scope")
    components = _validate_published_h(root, head)
    refs = _validate_refs(root, head, verify_remote=verify_remote)
    contract = certification.load_contract(
        root=root,
        verify_inputs=True,
        allow_pending_suite=False,
    )
    _assert_contract_identity(contract)
    contract_state = _collect_contract_state(contract, root)
    if publication_phase is None:
        _validate_empty_namespaces(root)
    else:
        _validate_publication_namespace(
            root, outputs_present=publication_phase == "flock_postlink"
        )
    dvc_status = _dvc_status(root) if check_dvc else {}
    return {
        "repository": refs,
        "closure_source_commit": CLOSURE_SOURCE_COMMIT,
        "r_syn_commit": R_SYN_COMMIT,
        "editorial_commit": EDITORIAL_COMMIT,
        "h1_cert_commit": H1_CERT_COMMIT,
        "p1_cert_commit": P1_CERT_COMMIT,
        "h2_cert_commit": H2_CERT_COMMIT,
        "p2_cert_commit": P2_CERT_COMMIT,
        "h3_cert_commit": head,
        "h_cert_commit": head,
        "h1_scope": dict(H1_SCOPE),
        "p1_scope": dict(P1_SCOPE),
        "h_scope": dict(H_SCOPE),
        "h_component_records": components,
        **contract_state,
        "dvc_status": dvc_status,
    }


def check_only(
    *, root: Path = PROJECT_ROOT, verify_remote: bool = True
) -> dict[str, Any]:
    """Validate the current H-CERT gate without writing any path."""

    root = root.resolve()
    head = _one_oid(root, "HEAD")
    if head == P2_CERT_COMMIT:
        refs = _validate_refs(root, P2_CERT_COMMIT, verify_remote=verify_remote)
        _validate_local_h(root)
        contract = certification.load_contract(
            root=root,
            verify_inputs=True,
            allow_pending_suite=True,
        )
        _assert_contract_identity(contract)
        certification._historical_h1_p1_h2_p2_records(contract, root=root)
        if dict(certification.expected_h_scope()) != dict(H_SCOPE):
            raise _error("Local H-CERT scope differs from its contract")
        _validate_empty_namespaces(root)
        status = "ready_to_publish_h"
        implementation_commit: str | None = None
        dvc_checked = False
    else:
        published = _collect_published_state(
            root,
            verify_remote=verify_remote,
            check_dvc=True,
        )
        refs = cast(dict[str, str], published["repository"])
        status = "ready_to_generate"
        implementation_commit = cast(str, published["h_cert_commit"])
        dvc_checked = True
    return {
        "status": status,
        "gate": GATE,
        "closure_source_commit": CLOSURE_SOURCE_COMMIT,
        "r_syn_commit": R_SYN_COMMIT,
        "editorial_commit": EDITORIAL_COMMIT,
        "h1_cert_commit": H1_CERT_COMMIT,
        "p1_cert_commit": P1_CERT_COMMIT,
        "h2_cert_commit": H2_CERT_COMMIT,
        "p2_cert_commit": P2_CERT_COMMIT,
        "h3_cert_commit": implementation_commit,
        "h_cert_commit": implementation_commit,
        "repository": refs,
        "h_component_count": len(H_SCOPE),
        "anchor_input_count": len(ANCHOR_PATHS),
        "dvc_pointer_count": 8,
        "r_cert_output_count": len(R_SCOPE),
        "writes_performed": False,
        "dvc_status_checked": dvc_checked,
        "dvc_pull_commands_run": False,
        "test_commands_run": False,
        "parquet_payloads_opened": False,
        "raw_targets_accessed": False,
        "raw_outcomes_accessed": False,
        "git_publication_commands_run": False,
    }


def _build_authority(state: Mapping[str, Any]) -> dict[str, Any]:
    h1_components = cast(list[dict[str, Any]], state["h1_component_records"])
    p1_components = cast(list[dict[str, Any]], state["p1_component_records"])
    h2_components = cast(list[dict[str, Any]], state["h2_component_records"])
    p2_components = cast(list[dict[str, Any]], state["p2_component_records"])
    components = cast(list[dict[str, Any]], state["h_component_records"])
    anchors = cast(list[dict[str, Any]], state["anchor_input_records"])
    pointers = cast(list[dict[str, Any]], state["dvc_pointer_records"])
    suite = cast(dict[str, Any], state["suite"])
    outputs = cast(list[str], state["ordered_output_paths"])
    authority: dict[str, Any] = {
        "authority_version": AUTHORITY_VERSION,
        "gate": GATE,
        "status": "locked_unpublished",
        "topology": {
            "closure_source_commit": CLOSURE_SOURCE_COMMIT,
            "r_syn_commit": R_SYN_COMMIT,
            "editorial_commit": EDITORIAL_COMMIT,
            "h1_cert_commit": H1_CERT_COMMIT,
            "p1_cert_commit": P1_CERT_COMMIT,
            "h2_cert_commit": H2_CERT_COMMIT,
            "p2_cert_commit": P2_CERT_COMMIT,
            "h3_cert_commit": state["h_cert_commit"],
            "p3_cert_commit": None,
            "h_cert_commit": state["h_cert_commit"],
            "p_cert_commit": None,
            "r_cert_executable_tree_must_equal_p_cert": True,
        },
        "p1_failure": {
            "status": "superseded_failed",
            "failure_stage": "after_git_clone_namespace_validation",
            "dvc_pull_count": 0,
            "r_cert_output_count": 0,
            "retry_authorized": False,
        },
        "p2_failure": certification.expected_p2_failure_record(),
        "h1_scope": dict(H1_SCOPE),
        "h1_component_records": h1_components,
        "h1_component_records_digest": certification.digest_records(h1_components),
        "p1_scope": dict(P1_SCOPE),
        "p1_component_records": p1_components,
        "p1_component_records_digest": certification.digest_records(p1_components),
        "h2_scope": dict(H2_SCOPE),
        "h2_component_records": h2_components,
        "h2_component_records_digest": certification.digest_records(h2_components),
        "p2_scope": dict(P2_SCOPE),
        "p2_component_records": p2_components,
        "p2_component_records_digest": certification.digest_records(p2_components),
        "h_scope": dict(H_SCOPE),
        "h_component_records": components,
        "h_component_records_digest": certification.digest_records(components),
        "h3_scope": dict(H_SCOPE),
        "h3_component_records": components,
        "h3_component_records_digest": certification.digest_records(components),
        "p_scope": dict(P_SCOPE),
        "p3_scope": dict(P_SCOPE),
        "anchor_input_records": anchors,
        "anchor_input_records_digest": certification.digest_records(anchors),
        "dvc_pointer_records": pointers,
        "dvc_pointer_records_digest": certification.digest_records(pointers),
        "test_suite": suite,
        "test_suite_digest": certification.sha256_bytes(
            certification.canonical_json_bytes(suite)
        ),
        "ordered_r_cert_output_paths": outputs,
        "r_cert_output_paths_digest": certification.digest_strings(outputs),
        "isolation": dict(certification._expected_isolation()),
        "failure_diagnostics": dict(certification.FAILURE_DIAGNOSTICS_POLICY),
        "authorizations": dict(certification.AUTHORIZATION_POLICY),
        "prohibitions": dict(certification.PROHIBITIONS),
    }
    validate_authority(authority)
    return authority


def validate_authority(payload: Mapping[str, Any]) -> None:
    required = {
        "authority_version",
        "gate",
        "status",
        "topology",
        "p1_failure",
        "p2_failure",
        "h1_scope",
        "h1_component_records",
        "h1_component_records_digest",
        "p1_scope",
        "p1_component_records",
        "p1_component_records_digest",
        "h2_scope",
        "h2_component_records",
        "h2_component_records_digest",
        "p2_scope",
        "p2_component_records",
        "p2_component_records_digest",
        "h_scope",
        "h_component_records",
        "h_component_records_digest",
        "h3_scope",
        "h3_component_records",
        "h3_component_records_digest",
        "p_scope",
        "p3_scope",
        "anchor_input_records",
        "anchor_input_records_digest",
        "dvc_pointer_records",
        "dvc_pointer_records_digest",
        "test_suite",
        "test_suite_digest",
        "ordered_r_cert_output_paths",
        "r_cert_output_paths_digest",
        "isolation",
        "failure_diagnostics",
        "authorizations",
        "prohibitions",
    }
    if set(payload) != required:
        raise _error("P-CERT authority keys drifted")
    if (
        payload["authority_version"] != AUTHORITY_VERSION
        or payload["gate"] != GATE
        or payload["status"] != "locked_unpublished"
    ):
        raise _error("P-CERT authority identity drifted")
    topology = payload["topology"]
    if not isinstance(topology, Mapping) or set(topology) != {
        "closure_source_commit",
        "r_syn_commit",
        "editorial_commit",
        "h1_cert_commit",
        "p1_cert_commit",
        "h2_cert_commit",
        "p2_cert_commit",
        "h3_cert_commit",
        "p3_cert_commit",
        "h_cert_commit",
        "p_cert_commit",
        "r_cert_executable_tree_must_equal_p_cert",
    }:
        raise _error("P-CERT topology keys drifted")
    if (
        topology["closure_source_commit"] != CLOSURE_SOURCE_COMMIT
        or topology["r_syn_commit"] != R_SYN_COMMIT
        or topology["editorial_commit"] != EDITORIAL_COMMIT
        or topology["h1_cert_commit"] != H1_CERT_COMMIT
        or topology["p1_cert_commit"] != P1_CERT_COMMIT
        or topology["h2_cert_commit"] != H2_CERT_COMMIT
        or topology["p2_cert_commit"] != P2_CERT_COMMIT
        or topology["h3_cert_commit"] != topology["h_cert_commit"]
        or topology["p3_cert_commit"] is not None
        or topology["p_cert_commit"] is not None
        or topology["r_cert_executable_tree_must_equal_p_cert"] is not True
    ):
        raise _error("P-CERT topology authority drifted")
    h_commit = topology["h_cert_commit"]
    if not isinstance(h_commit, str) or GIT_OID_RE.fullmatch(h_commit) is None:
        raise _error("P-CERT H-CERT commit is invalid")
    if h_commit in {
        CLOSURE_SOURCE_COMMIT,
        R_SYN_COMMIT,
        EDITORIAL_COMMIT,
        H1_CERT_COMMIT,
        P1_CERT_COMMIT,
        H2_CERT_COMMIT,
        P2_CERT_COMMIT,
    }:
        raise _error("P-CERT3 H-CERT3 commit predates H-CERT3")
    if payload["p1_failure"] != {
        "status": "superseded_failed",
        "failure_stage": "after_git_clone_namespace_validation",
        "dvc_pull_count": 0,
        "r_cert_output_count": 0,
        "retry_authorized": False,
    }:
        raise _error("P-CERT1 failure record drifted")
    if payload["p2_failure"] != certification.expected_p2_failure_record():
        raise _error("P-CERT2 failure record drifted")
    if payload["h1_scope"] != dict(H1_SCOPE):
        raise _error("P-CERT historical H-CERT1 scope drifted")
    if payload["p1_scope"] != dict(P1_SCOPE):
        raise _error("P-CERT historical P-CERT1 scope drifted")
    if payload["h2_scope"] != dict(H2_SCOPE):
        raise _error("P-CERT historical H-CERT2 scope drifted")
    if payload["p2_scope"] != dict(P2_SCOPE):
        raise _error("P-CERT historical P-CERT2 scope drifted")
    if payload["h_scope"] != dict(H_SCOPE):
        raise _error("P-CERT H scope drifted")
    if payload["h3_scope"] != dict(H_SCOPE) or payload["h3_scope"] != payload["h_scope"]:
        raise _error("P-CERT explicit H-CERT3 scope drifted")
    if payload["p_scope"] != dict(P_SCOPE) or payload["p3_scope"] != dict(P_SCOPE):
        raise _error("P-CERT explicit P-CERT3 scope drifted")
    collections = (
        "h1_component_records",
        "p1_component_records",
        "h2_component_records",
        "p2_component_records",
        "h_component_records",
        "h3_component_records",
        "anchor_input_records",
        "dvc_pointer_records",
        "ordered_r_cert_output_paths",
    )
    if not all(isinstance(payload[name], list) for name in collections):
        raise _error("P-CERT record collections must be lists")
    h1_components = cast(list[dict[str, Any]], payload["h1_component_records"])
    p1_components = cast(list[dict[str, Any]], payload["p1_component_records"])
    h2_components = cast(list[dict[str, Any]], payload["h2_component_records"])
    p2_components = cast(list[dict[str, Any]], payload["p2_component_records"])
    components = cast(list[dict[str, Any]], payload["h_component_records"])
    h3_components = cast(list[dict[str, Any]], payload["h3_component_records"])
    anchors = cast(list[dict[str, Any]], payload["anchor_input_records"])
    pointers = cast(list[dict[str, Any]], payload["dvc_pointer_records"])
    outputs = cast(list[str], payload["ordered_r_cert_output_paths"])
    if [record.get("path") for record in h1_components] != list(H1_SCOPE):
        raise _error("P-CERT historical H-CERT1 component order drifted")
    if [record.get("path") for record in p1_components] != list(P1_SCOPE):
        raise _error("P-CERT historical P-CERT1 component order drifted")
    if [record.get("path") for record in h2_components] != list(H2_SCOPE):
        raise _error("P-CERT historical H-CERT2 component order drifted")
    if [record.get("path") for record in p2_components] != list(P2_SCOPE):
        raise _error("P-CERT historical P-CERT2 component order drifted")
    if [record.get("path") for record in components] != list(H_SCOPE):
        raise _error("P-CERT H component order drifted")
    if h3_components != components:
        raise _error("P-CERT explicit H-CERT3 component records drifted")
    if [record.get("path") for record in anchors] != list(ANCHOR_PATHS):
        raise _error("P-CERT anchor record order drifted")
    if len(pointers) != 8 or len({record.get("path") for record in pointers}) != 8:
        raise _error("P-CERT DVC pointer records are not exact8")
    if outputs != list(R_SCOPE):
        raise _error("P-CERT R-CERT output order drifted")
    for records, modes, label in (
        (h1_components, H_GIT_MODES, "historical H-CERT1"),
        (p1_components, {path: "100644" for path in P1_SCOPE}, "historical P-CERT1"),
        (p2_components, {path: "100644" for path in P2_SCOPE}, "historical P-CERT2"),
    ):
        for record, path_text in zip(records, modes, strict=True):
            if set(record) != {
                "path",
                "bytes",
                "sha256",
                "git_mode",
                "git_blob_oid",
            }:
                raise _error(f"P-CERT {label} component keys drifted: {path_text}")
            if (
                record["path"] != path_text
                or type(record["bytes"]) is not int
                or record["bytes"] <= 0
                or not isinstance(record["sha256"], str)
                or SHA256_RE.fullmatch(record["sha256"]) is None
                or record["git_mode"] != modes[path_text]
                or not isinstance(record["git_blob_oid"], str)
                or GIT_OID_RE.fullmatch(record["git_blob_oid"]) is None
            ):
                raise _error(f"P-CERT {label} component identity drifted: {path_text}")
    for record, path_text in zip(h2_components, H2_SCOPE, strict=True):
        if set(record) != {
            "path",
            "bytes",
            "sha256",
            "git_mode",
            "git_blob_oid",
            "filesystem_mode",
        }:
            raise _error(f"P-CERT historical H-CERT2 component keys drifted: {path_text}")
        if (
            record["path"] != path_text
            or type(record["bytes"]) is not int
            or record["bytes"] <= 0
            or not isinstance(record["sha256"], str)
            or SHA256_RE.fullmatch(record["sha256"]) is None
            or record["git_mode"] != H_GIT_MODES[path_text]
            or not isinstance(record["git_blob_oid"], str)
            or GIT_OID_RE.fullmatch(record["git_blob_oid"]) is None
            or record["filesystem_mode"] != int(H_GIT_MODES[path_text][-3:], 8)
        ):
            raise _error(f"P-CERT historical H-CERT2 identity drifted: {path_text}")
    for record, path_text in zip(components, H_SCOPE, strict=True):
        if set(record) != {
            "path",
            "bytes",
            "sha256",
            "git_mode",
            "git_blob_oid",
            "filesystem_mode",
        }:
            raise _error(f"P-CERT H component keys drifted: {path_text}")
        if (
            type(record["bytes"]) is not int
            or record["bytes"] <= 0
            or not isinstance(record["sha256"], str)
            or SHA256_RE.fullmatch(record["sha256"]) is None
            or record["git_mode"] != H_GIT_MODES[path_text]
            or not isinstance(record["git_blob_oid"], str)
            or GIT_OID_RE.fullmatch(record["git_blob_oid"]) is None
            or record["filesystem_mode"] != int(H_GIT_MODES[path_text][-3:], 8)
        ):
            raise _error(f"P-CERT H component identity drifted: {path_text}")
    for record, spec in zip(
        anchors, certification.ANCHOR_INPUTS, strict=True
    ):
        if set(record) != {
            "path",
            "role",
            "bytes",
            "sha256",
            "git_mode",
            "git_blob_oid",
            "repository_commit",
        }:
            raise _error(f"P-CERT anchor keys drifted: {spec.path}")
        if (
            record["path"] != spec.path
            or record["role"] != spec.role
            or type(record["bytes"]) is not int
            or record["bytes"] <= 0
            or not isinstance(record["sha256"], str)
            or SHA256_RE.fullmatch(record["sha256"]) is None
            or record["git_mode"] != "100644"
            or not isinstance(record["git_blob_oid"], str)
            or GIT_OID_RE.fullmatch(record["git_blob_oid"]) is None
            or record["repository_commit"] != EDITORIAL_COMMIT
        ):
            raise _error(f"P-CERT anchor identity drifted: {spec.path}")
    for record, spec in zip(
        pointers, certification.DVC_POINTERS, strict=True
    ):
        if set(record) != {
            "path",
            "role",
            "bytes",
            "sha256",
            "git_mode",
            "git_blob_oid",
            "repository_commit",
            "output_path",
            "payload_md5",
            "payload_bytes",
            "parquet_payload_opened",
        }:
            raise _error(f"P-CERT DVC pointer keys drifted: {spec.path}")
        if (
            record["path"] != spec.path
            or record["role"] != spec.role
            or record["output_path"] != spec.output_path
            or record["payload_md5"] != spec.md5
            or MD5_RE.fullmatch(cast(str, record["payload_md5"])) is None
            or record["payload_bytes"] != spec.size
            or type(record["bytes"]) is not int
            or record["bytes"] <= 0
            or not isinstance(record["sha256"], str)
            or SHA256_RE.fullmatch(record["sha256"]) is None
            or record["git_mode"] != "100644"
            or not isinstance(record["git_blob_oid"], str)
            or GIT_OID_RE.fullmatch(record["git_blob_oid"]) is None
            or record["repository_commit"] != EDITORIAL_COMMIT
            or record["parquet_payload_opened"] is not False
        ):
            raise _error(f"P-CERT DVC pointer identity drifted: {spec.path}")
    digest_pairs = (
        (
            "h1_component_records_digest",
            certification.digest_records(h1_components),
        ),
        (
            "p1_component_records_digest",
            certification.digest_records(p1_components),
        ),
        (
            "h2_component_records_digest",
            certification.digest_records(h2_components),
        ),
        (
            "p2_component_records_digest",
            certification.digest_records(p2_components),
        ),
        ("h_component_records_digest", certification.digest_records(components)),
        ("h3_component_records_digest", certification.digest_records(h3_components)),
        ("anchor_input_records_digest", certification.digest_records(anchors)),
        ("dvc_pointer_records_digest", certification.digest_records(pointers)),
        ("r_cert_output_paths_digest", certification.digest_strings(outputs)),
    )
    for key, expected in digest_pairs:
        if payload[key] != expected:
            raise _error(f"P-CERT {key} drifted")
    suite = payload["test_suite"]
    if not isinstance(suite, Mapping):
        raise _error("P-CERT test suite is invalid")
    if set(suite) != {
        "suite_kind",
        "positive_test_paths",
        "exact_skipped_nodes",
        "exact_skip_reason",
        "e2e_nodes",
        "selectors",
        "command_template",
        "static_commands",
        "suite_lock",
    }:
        raise _error("P-CERT test suite keys drifted")
    expected_selectors = [
        *certification.POSITIVE_TEST_PATHS,
        *(
            node
            for node in certification.EXACT_SKIPPED_NODES
            if node.split("::", 1)[0]
            not in set(certification.POSITIVE_TEST_PATHS)
        ),
    ]
    if (
        suite["suite_kind"] != "closure_phase4_final_public"
        or suite["positive_test_paths"] != list(certification.POSITIVE_TEST_PATHS)
        or suite["exact_skipped_nodes"] != list(certification.EXACT_SKIPPED_NODES)
        or suite["exact_skip_reason"] != certification.EXACT_SKIP_REASON
        or suite["e2e_nodes"] != list(certification.E2E_NODES)
        or suite["selectors"] != expected_selectors
        or suite["command_template"] != list(certification.TEST_COMMAND_TEMPLATE)
        or suite["static_commands"]
        != [list(command) for command in certification.STATIC_COMMANDS]
    ):
        raise _error("P-CERT test suite definition drifted")
    lock = suite.get("suite_lock")
    if not isinstance(lock, Mapping) or set(lock) != {
        "status",
        "selector_count",
        "collected_test_count",
        "nodeids_sha256",
        "allowed_skip_count",
    }:
        raise _error("P-CERT test suite lock keys drifted")
    if (
        len(expected_selectors) != certification.LOCKED_SUITE_SELECTOR_COUNT
        or lock.get("status") != certification.LOCKED_SUITE_STATUS
        or lock.get("selector_count") != certification.LOCKED_SUITE_SELECTOR_COUNT
        or lock.get("collected_test_count")
        != certification.LOCKED_SUITE_COLLECTED_TEST_COUNT
        or lock.get("nodeids_sha256")
        != certification.LOCKED_SUITE_NODEIDS_SHA256
        or lock.get("allowed_skip_count")
        != certification.LOCKED_SUITE_ALLOWED_SKIP_COUNT
    ):
        raise _error("P-CERT test suite is not locked")
    if payload["test_suite_digest"] != certification.sha256_bytes(
        certification.canonical_json_bytes(suite)
    ):
        raise _error("P-CERT test suite digest drifted")
    if payload["isolation"] != dict(certification._expected_isolation()):
        raise _error("P-CERT isolation boundary drifted")
    if payload["failure_diagnostics"] != dict(
        certification.FAILURE_DIAGNOSTICS_POLICY
    ):
        raise _error("P-CERT failure diagnostics policy drifted")
    if payload["authorizations"] != dict(certification.AUTHORIZATION_POLICY):
        raise _error("P-CERT authorization policy drifted")
    if payload["prohibitions"] != dict(certification.PROHIBITIONS):
        raise _error("P-CERT prohibitions drifted")


def _build_manifest(authority_bytes: bytes, h_cert_commit: str) -> dict[str, Any]:
    authority_record = {
        "path": AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": certification.sha256_bytes(authority_bytes),
    }
    return {
        "manifest_version": MANIFEST_VERSION,
        "gate": GATE,
        "status": "locked_unpublished",
        "h1_cert_commit": H1_CERT_COMMIT,
        "p1_cert_commit": P1_CERT_COMMIT,
        "h2_cert_commit": H2_CERT_COMMIT,
        "p2_cert_commit": P2_CERT_COMMIT,
        "h3_cert_commit": h_cert_commit,
        "p3_cert_commit": None,
        "h_cert_commit": h_cert_commit,
        "p_cert_commit": None,
        "supersedes_p2": True,
        "supersedes_p1": True,
        "manifest_last": True,
        "ordered_paths": [AUTHORITY_PATH.as_posix(), MANIFEST_PATH.as_posix()],
        "outputs": [authority_record],
        "authority": authority_record,
        "authorizations": dict(certification.AUTHORIZATION_POLICY),
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


@dataclass(frozen=True)
class _RepositoryRootAt:
    canonical_path: Path
    grandparent_fd: int
    parent: _OwnedDirectoryAt
    root: _OwnedDirectoryAt


@dataclass(frozen=True)
class _LegacyGuardBoundary:
    tmp_directory: _OwnedDirectoryAt | None
    legacy_namespace: _OwnedDirectoryAt | None


def _stat_optional_at(parent_fd: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _rename_noreplace_at(
    source_directory_fd: int,
    source_name: str,
    target_directory_fd: int,
    target_name: str,
) -> None:
    """Atomically rename one entry without replacing its destination."""

    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise _error("Atomic P-CERT cleanup requires renameat2")
    renameat2 = cast(Any, renameat2)
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    result = renameat2(
        source_directory_fd,
        os.fsencode(source_name),
        target_directory_fd,
        os.fsencode(target_name),
        1,  # RENAME_NOREPLACE
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(
            error_number,
            os.strerror(error_number),
            source_name,
            target_name,
        )


def _close_fd_noexcept(descriptor: int) -> None:
    try:
        os.close(descriptor)
    except BaseException:
        pass


def _remove_owned_name_atomic(
    directory_fd: int,
    name: str,
    identity: tuple[int, int],
    *,
    context: str,
    missing_is_error: bool,
    owned_fd: int | None = None,
    expected_directory: bool = False,
) -> None:
    """Best-effort cleanup with no-clobber capture and identity revalidation.

    A boundary replacement is first moved to an unpredictable no-clobber
    tombstone and restored to its canonical name after its foreign identity is
    observed.  POSIX removal remains name-based: conditional unlink by inode is
    not claimed, and non-cooperating same-UID namespace mutation is out of
    scope.  Cooperating publishers are serialized by the retained ``.git``
    flock.
    """

    if not name or "/" in name or name in {".", ".."}:
        raise _error(f"{context} has an unsafe cleanup name")
    tombstone: str | None = None
    for _ in range(128):
        candidate = f"{CLEANUP_TOMBSTONE_PREFIX}{secrets.token_hex(16)}"
        try:
            _rename_noreplace_at(directory_fd, name, directory_fd, candidate)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                continue
            if exc.errno == errno.ENOENT:
                if missing_is_error:
                    raise _error(
                        f"{context} owned entry is missing during cleanup"
                    ) from exc
                return
            raise _error(f"{context} atomic cleanup rename failed") from exc
        tombstone = candidate
        break
    if tombstone is None:
        raise _error(f"{context} could not allocate an exclusive tombstone")
    os.fsync(directory_fd)

    tombstone_fd: int | None = None
    try:
        captured = os.stat(
            tombstone,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        captured_identity = (captured.st_dev, captured.st_ino)
        captured_type_matches = (
            stat.S_ISDIR(captured.st_mode)
            if expected_directory
            else stat.S_ISREG(captured.st_mode)
        )
        if (
            captured_identity != identity
            or stat.S_ISLNK(captured.st_mode)
            or not captured_type_matches
        ):
            try:
                _rename_noreplace_at(
                    directory_fd,
                    tombstone,
                    directory_fd,
                    name,
                )
                os.fsync(directory_fd)
            except OSError as exc:
                raise _error(
                    f"{context} foreign replacement was preserved at "
                    f"{tombstone} because its canonical name reappeared"
                ) from exc
            raise _error(
                f"{context} owned entry was replaced during cleanup; "
                "the foreign entry was restored"
            )

        tombstone_fd = os.open(
            tombstone,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | (getattr(os, "O_DIRECTORY", 0) if expected_directory else 0),
            dir_fd=directory_fd,
        )
        anchored = os.fstat(tombstone_fd)
        anchored_type_matches = (
            stat.S_ISDIR(anchored.st_mode)
            if expected_directory
            else stat.S_ISREG(anchored.st_mode)
        )
        if (
            (anchored.st_dev, anchored.st_ino) != identity
            or not anchored_type_matches
        ):
            raise _error(f"{context} cleanup tombstone changed while opening")
        if owned_fd is not None:
            retained = os.fstat(owned_fd)
            if (retained.st_dev, retained.st_ino) != identity:
                raise _error(f"{context} retained owned FD identity drifted")
        repeated = os.stat(
            tombstone,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        if (
            (repeated.st_dev, repeated.st_ino) != identity
            or stat.S_ISLNK(repeated.st_mode)
        ):
            raise _error(f"{context} cleanup tombstone was replaced")

        if expected_directory:
            if os.listdir(tombstone_fd):
                raise _error(f"{context} owned cleanup directory is not empty")
            os.rmdir(tombstone, dir_fd=directory_fd)
            os.fsync(directory_fd)
            if os.fstat(tombstone_fd).st_nlink != 0:
                raise _error(
                    f"{context} cleanup did not remove its exact directory"
                )
        else:
            link_count = anchored.st_nlink
            if link_count < 1:
                raise _error(f"{context} cleanup tombstone has no owned link")
            os.unlink(tombstone, dir_fd=directory_fd)
            os.fsync(directory_fd)
            if os.fstat(tombstone_fd).st_nlink != link_count - 1:
                raise _error(f"{context} cleanup did not remove its exact inode")
    except BaseException as primary:
        try:
            captured_after_failure = os.stat(
                tombstone,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            raise primary
        except OSError as exc:
            raise _error(
                f"{context} failed and its captured tombstone could not be inspected"
            ) from exc
        try:
            _rename_noreplace_at(
                directory_fd,
                tombstone,
                directory_fd,
                name,
            )
            os.fsync(directory_fd)
            restored = os.stat(
                name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise _error(
                f"{context} failed; its captured entry was preserved at "
                f"{tombstone} because canonical restoration was not possible"
            ) from exc
        if (restored.st_dev, restored.st_ino) != (
            captured_after_failure.st_dev,
            captured_after_failure.st_ino,
        ):
            raise _error(f"{context} restored entry identity drifted") from primary
        raise primary
    finally:
        if tombstone_fd is not None:
            _close_fd_noexcept(tombstone_fd)


def _open_directory_at(parent_fd: int, name: str, *, context: str) -> _OwnedDirectoryAt:
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
        parent_fd, name, descriptor, observed.st_dev, observed.st_ino
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
        or (mode is not None and stat.S_IMODE(descriptor_metadata.st_mode) != mode)
    ):
        raise _error(f"{context} ownership/path binding drifted")


def _open_repository_root(root: Path) -> _RepositoryRootAt:
    try:
        canonical = root.resolve(strict=True)
    except OSError as exc:
        raise _error("P-CERT repository root is unavailable") from exc
    parent_path = canonical.parent
    grandparent_path = parent_path.parent
    if canonical == parent_path or parent_path == grandparent_path:
        raise _error(
            "P-CERT repository root and its canonical parent must be named "
            "directories below the filesystem root"
        )
    grandparent_fd = os.open(
        grandparent_path,
        os.O_RDONLY
        | os.O_DIRECTORY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    parent: _OwnedDirectoryAt | None = None
    repository: _OwnedDirectoryAt | None = None
    try:
        parent = _open_directory_at(
            grandparent_fd,
            parent_path.name,
            context="P-CERT repository parent",
        )
        repository = _open_directory_at(
            parent.fd,
            canonical.name,
            context="P-CERT repository root",
        )
        binding = _RepositoryRootAt(
            canonical,
            grandparent_fd,
            parent,
            repository,
        )
        _require_repository_path_binding(binding)
        return binding
    except BaseException:
        if repository is not None:
            _close_fd_noexcept(repository.fd)
        if parent is not None:
            _close_fd_noexcept(parent.fd)
        _close_fd_noexcept(grandparent_fd)
        raise


def _require_repository_path_binding(repository: _RepositoryRootAt) -> None:
    """Rebind the canonical repository parent and root around one check."""

    _require_owned_directory_at(
        repository.parent,
        context="P-CERT repository parent",
    )
    _require_owned_directory_at(
        repository.root,
        context="P-CERT repository root",
    )
    _require_owned_directory_at(
        repository.parent,
        context="P-CERT repository parent",
    )


def _acquire_repository_lock(
    repository: _RepositoryRootAt,
) -> _OwnedDirectoryAt:
    """Retain and exclusively lock the repository Git directory.

    The lock serializes cooperating Phase 4 publishers.  The legacy disposable
    guard path is never created, adopted, renamed, or removed.
    """

    git_directory = _open_directory_at(
        repository.root.fd,
        ".git",
        context="P-CERT Git directory",
    )
    try:
        try:
            fcntl.flock(git_directory.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise _error(
                "Another cooperating Phase 4 publication holds the repository lock"
            ) from exc
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise _error(
                    "Another cooperating Phase 4 publication holds the repository lock"
                ) from exc
            raise _error("P-CERT repository lock could not be acquired") from exc
        _require_repository_lock(repository, git_directory)
        return git_directory
    except BaseException:
        _close_fd_noexcept(git_directory.fd)
        raise


def _require_repository_lock(
    repository: _RepositoryRootAt,
    git_directory: _OwnedDirectoryAt,
) -> None:
    """Revalidate the root/.git bindings while the retained flock is held."""

    _require_repository_path_binding(repository)
    _require_owned_directory_at(
        git_directory,
        context="P-CERT Git directory",
    )
    _require_repository_path_binding(repository)


def _capture_legacy_guard_boundary(root_fd: int) -> _LegacyGuardBoundary:
    """Snapshot existing ancestors without creating the legacy namespace."""

    tmp_metadata = _stat_optional_at(root_fd, GUARD_PATH.parts[0])
    if tmp_metadata is None:
        return _LegacyGuardBoundary(None, None)
    if stat.S_ISLNK(tmp_metadata.st_mode) or not stat.S_ISDIR(tmp_metadata.st_mode):
        raise _error("P-CERT legacy guard ancestor is not a no-follow directory")
    tmp_directory = _open_directory_at(
        root_fd,
        GUARD_PATH.parts[0],
        context="P-CERT legacy guard tmp ancestor",
    )
    legacy_namespace: _OwnedDirectoryAt | None = None
    try:
        namespace_metadata = _stat_optional_at(
            tmp_directory.fd,
            GUARD_PATH.parts[1],
        )
        if namespace_metadata is None:
            boundary = _LegacyGuardBoundary(tmp_directory, None)
            _require_legacy_guard_boundary(root_fd, boundary)
            return boundary
        if stat.S_ISLNK(namespace_metadata.st_mode) or not stat.S_ISDIR(
            namespace_metadata.st_mode
        ):
            raise _error(
                "P-CERT legacy guard ancestor is not a no-follow directory"
            )
        legacy_namespace = _open_directory_at(
            tmp_directory.fd,
            GUARD_PATH.parts[1],
            context="P-CERT legacy guard namespace ancestor",
        )
        boundary = _LegacyGuardBoundary(tmp_directory, legacy_namespace)
        _require_legacy_guard_boundary(root_fd, boundary)
        return boundary
    except BaseException:
        if legacy_namespace is not None:
            _close_fd_noexcept(legacy_namespace.fd)
        _close_fd_noexcept(tmp_directory.fd)
        raise


def _require_legacy_guard_boundary(
    root_fd: int,
    boundary: _LegacyGuardBoundary,
) -> None:
    """Revalidate the captured legacy path and require its final name absent."""

    tmp_directory = boundary.tmp_directory
    legacy_namespace = boundary.legacy_namespace
    if tmp_directory is None:
        if _stat_optional_at(root_fd, GUARD_PATH.parts[0]) is not None:
            raise _error("P-CERT legacy guard ancestor appeared during publication")
        return
    _require_owned_directory_at(
        tmp_directory,
        context="P-CERT legacy guard tmp ancestor",
    )
    if legacy_namespace is None:
        if _stat_optional_at(tmp_directory.fd, GUARD_PATH.parts[1]) is not None:
            raise _error("P-CERT legacy guard namespace appeared during publication")
        _require_owned_directory_at(
            tmp_directory,
            context="P-CERT legacy guard tmp ancestor",
        )
        return
    _require_owned_directory_at(
        legacy_namespace,
        context="P-CERT legacy guard namespace ancestor",
    )
    if _stat_optional_at(legacy_namespace.fd, GUARD_PATH.name) is not None:
        raise _error("P-CERT legacy guard must be absent")
    _require_owned_directory_at(
        tmp_directory,
        context="P-CERT legacy guard tmp ancestor",
    )
    _require_owned_directory_at(
        legacy_namespace,
        context="P-CERT legacy guard namespace ancestor",
    )


def _require_relative_absent_at(
    root_fd: int,
    path_text: str,
    *,
    context: str,
) -> None:
    """Establish path absence through a retained, no-follow dirfd walk."""

    relative = _validate_relative(path_text, context=context)
    current_fd = root_fd
    retained: list[_OwnedDirectoryAt] = []

    def revalidate_retained() -> None:
        for owner in retained:
            _require_owned_directory_at(owner, context=f"{context} ancestor")
        for owner in reversed(retained):
            _require_owned_directory_at(owner, context=f"{context} ancestor")

    try:
        for part in relative.parts[:-1]:
            observed = _stat_optional_at(current_fd, part)
            if observed is None:
                revalidate_retained()
                if _stat_optional_at(current_fd, part) is not None:
                    raise _error(f"{context} ancestor appeared during validation")
                revalidate_retained()
                return
            if stat.S_ISLNK(observed.st_mode) or not stat.S_ISDIR(observed.st_mode):
                raise _error(f"{context} ancestor is not a no-follow directory")
            owner = _open_directory_at(
                current_fd,
                part,
                context=f"{context} ancestor",
            )
            retained.append(owner)
            current_fd = owner.fd

        final_name = relative.parts[-1]
        if _stat_optional_at(current_fd, final_name) is not None:
            raise _error(f"{context} must be absent")
        revalidate_retained()
        if _stat_optional_at(current_fd, final_name) is not None:
            raise _error(f"{context} appeared during validation")
        revalidate_retained()
    finally:
        for owner in reversed(retained):
            _close_fd_noexcept(owner.fd)


def _require_publication_path_binding(
    configs: _OwnedDirectoryAt,
    output_parent: _OwnedDirectoryAt,
) -> None:
    """Rebind both ancestors of the P-CERT destination to retained dirfds."""

    _require_owned_directory_at(configs, context="configs root")
    _require_owned_directory_at(
        output_parent,
        context="P-CERT output parent",
    )
    _require_owned_directory_at(configs, context="configs root")


def _mkdir_owned_at(
    parent_fd: int, name: str, *, mode: int, context: str
) -> _OwnedDirectoryAt:
    if not name or "/" in name or name in {".", ".."}:
        raise _error(f"{context} has an unsafe name")
    temporary_name: str | None = None
    for _ in range(128):
        candidate = f"{DIRECTORY_TEMP_PREFIX}{secrets.token_hex(16)}"
        try:
            os.mkdir(candidate, mode=mode, dir_fd=parent_fd)
        except FileExistsError:
            continue
        temporary_name = candidate
        break
    if temporary_name is None:
        raise _error(f"{context} could not allocate an exclusive directory name")

    temporary_owner: _OwnedDirectoryAt | None = None
    published_owner: _OwnedDirectoryAt | None = None
    descriptor: int | None = None
    try:
        descriptor = os.open(
            temporary_name,
            os.O_RDONLY
            | os.O_DIRECTORY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        opened = os.fstat(descriptor)
        named = os.stat(
            temporary_name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISDIR(opened.st_mode)
            or not stat.S_ISDIR(named.st_mode)
            or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
        ):
            raise _error(f"{context} temporary directory changed while opening")
        temporary_owner = _OwnedDirectoryAt(
            parent_fd,
            temporary_name,
            descriptor,
            opened.st_dev,
            opened.st_ino,
        )
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
        _require_owned_directory_at(
            temporary_owner,
            context=f"{context} temporary directory",
            mode=mode,
        )
        try:
            _rename_noreplace_at(
                parent_fd,
                temporary_name,
                parent_fd,
                name,
            )
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                raise _error(f"{context} already exists") from exc
            raise
        published_owner = _OwnedDirectoryAt(
            parent_fd,
            name,
            descriptor,
            opened.st_dev,
            opened.st_ino,
        )
        os.fsync(parent_fd)
        _require_owned_directory_at(
            published_owner,
            context=context,
            mode=mode,
        )
        if _stat_optional_at(parent_fd, temporary_name) is not None:
            raise _error(f"{context} temporary directory name reappeared")
        return published_owner
    except BaseException as primary:
        cleanup_owner = published_owner or temporary_owner
        cleanup_error: BaseException | None = None
        try:
            if cleanup_owner is None:
                cleanup_error = _error(
                    f"{context} temporary directory could not be bound safely; "
                    f"preserved at {temporary_name}"
                )
            else:
                _rmdir_owned_at(
                    cleanup_owner,
                    context=f"{context} failed creation",
                )
        except BaseException as exc:
            cleanup_error = exc
        finally:
            if descriptor is not None:
                _close_fd_noexcept(descriptor)
        if cleanup_error is not None:
            raise _error(
                f"{context} failed and its owned temporary directory could "
                f"not be removed safely: {cleanup_error}"
            ) from cleanup_error
        raise primary


def _rmdir_owned_at(
    owner: _OwnedDirectoryAt,
    *,
    context: str,
    missing_is_error: bool = True,
) -> None:
    _remove_owned_name_atomic(
        owner.parent_fd,
        owner.name,
        (owner.device, owner.inode),
        context=context,
        missing_is_error=missing_is_error,
        owned_fd=owner.fd,
        expected_directory=True,
    )


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
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise _error(f"{context} write made no progress")
            view = view[written:]
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
        os.close(descriptor)
        _require_owned_file_at(owner, context=context, link_count=1, mode=mode)
        return owner
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        _unlink_owned_file_at(owner, context=context)
        raise


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
    owner: _OwnedFileAt, *, context: str, link_count: int, mode: int
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
        named = _stat_optional_at(owner.parent_fd, owner.name)
        if (
            named is None
            or not stat.S_ISREG(named.st_mode)
            or (
                named.st_dev,
                named.st_ino,
                named.st_size,
                named.st_mtime_ns,
                named.st_ctime_ns,
                named.st_nlink,
                stat.S_IMODE(named.st_mode),
            )
            != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
                after.st_nlink,
                stat.S_IMODE(after.st_mode),
            )
        ):
            raise _error(f"{context} name changed during read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _unlink_owned_file_at(
    owner: _OwnedFileAt,
    *,
    context: str,
    missing_is_error: bool = True,
) -> None:
    _remove_owned_name_atomic(
        owner.parent_fd,
        owner.name,
        (owner.device, owner.inode),
        context=context,
        missing_is_error=missing_is_error,
    )


def _link_no_clobber(
    source: _OwnedFileAt,
    destination_parent_fd: int,
    destination_name: str,
) -> _OwnedFileAt:
    _require_owned_file_at(
        source, context="P-CERT link source", link_count=1, mode=0o644
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
        raise _error(f"P-CERT output already exists: {destination_name}") from exc
    except OSError as exc:
        current = _stat_optional_at(destination_parent_fd, destination_name)
        if current is not None and (current.st_dev, current.st_ino) == (
            source.device,
            source.inode,
        ):
            _unlink_owned_file_at(
                _OwnedFileAt(
                    destination_parent_fd,
                    destination_name,
                    source.device,
                    source.inode,
                ),
                context="P-CERT partial link",
            )
        if exc.errno == errno.EXDEV:
            raise _error("P-CERT publication requires one filesystem") from exc
        raise
    published = _OwnedFileAt(
        destination_parent_fd, destination_name, source.device, source.inode
    )
    try:
        _require_owned_file_at(
            published,
            context="P-CERT published output",
            link_count=2,
            mode=0o644,
        )
    except BaseException:
        _unlink_owned_file_at(published, context="P-CERT invalid published link")
        raise
    return published


def publish_authority_bundle(
    root: Path,
    authority: Mapping[str, Any],
    *,
    prepublish_validator: Callable[[], None] | None = None,
    postpublish_validator: Callable[[], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Publish exact2A under the retained ``.git`` flock, manifest-last."""

    validate_authority(authority)
    authority_bytes = certification.canonical_json_bytes(authority)
    h_cert_commit = cast(str, cast(Mapping[str, Any], authority["topology"])["h_cert_commit"])
    manifest_bytes = certification.canonical_json_bytes(
        _build_manifest(authority_bytes, h_cert_commit)
    )
    authority_record = {
        "path": AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": certification.sha256_bytes(authority_bytes),
    }
    manifest_record = {
        "path": MANIFEST_PATH.as_posix(),
        "bytes": len(manifest_bytes),
        "sha256": certification.sha256_bytes(manifest_bytes),
    }
    repository = _open_repository_root(root)
    root = repository.canonical_path
    root_fd = repository.root.fd
    open_fds: list[int] = [
        repository.grandparent_fd,
        repository.parent.fd,
        repository.root.fd,
    ]
    configs: _OwnedDirectoryAt | None = None
    output_parent: _OwnedDirectoryAt | None = None
    git_directory: _OwnedDirectoryAt | None = None
    legacy_boundary: _LegacyGuardBoundary | None = None
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
        _require_repository_path_binding(repository)
        git_directory = _acquire_repository_lock(repository)
        open_fds.append(git_directory.fd)
        _require_repository_lock(repository, git_directory)
        legacy_boundary = _capture_legacy_guard_boundary(root_fd)
        if legacy_boundary.tmp_directory is not None:
            open_fds.append(legacy_boundary.tmp_directory.fd)
        if legacy_boundary.legacy_namespace is not None:
            open_fds.append(legacy_boundary.legacy_namespace.fd)
        _require_legacy_guard_boundary(root_fd, legacy_boundary)
        configs = _open_directory_at(root_fd, "configs", context="configs root")
        open_fds.append(configs.fd)
        output_parent = _open_directory_at(
            configs.fd,
            AUTHORITY_PATH.parent.name,
            context="P-CERT output parent",
        )
        open_fds.append(output_parent.fd)
        for name, context in (
            (AUTHORITY_PATH.name, "P-CERT authority"),
            (MANIFEST_PATH.name, "P-CERT companion"),
        ):
            if _stat_optional_at(output_parent.fd, name) is not None:
                raise _error(f"{context} must be absent")
        if any(
            name.startswith((TEMP_PREFIX, CLEANUP_TOMBSTONE_PREFIX))
            for name in os.listdir(output_parent.fd)
        ):
            raise _error("P-CERT publication namespace is not empty")
        _require_publication_path_binding(configs, output_parent)
        _require_relative_absent_at(
            root_fd,
            certification.CERTIFICATION_ROOT.as_posix(),
            context="R-CERT output namespace",
        )
        _require_repository_lock(repository, git_directory)

        for directory, context in (
            (configs, "configs root"),
            (output_parent, "P-CERT output parent"),
        ):
            _require_owned_directory_at(directory, context=context)
        _require_legacy_guard_boundary(root_fd, legacy_boundary)
        _require_repository_lock(repository, git_directory)
        if prepublish_validator is not None:
            prepublish_validator()
        _require_repository_lock(repository, git_directory)
        _require_legacy_guard_boundary(root_fd, legacy_boundary)
        _require_publication_path_binding(configs, output_parent)

        for name, payload in zip(temporary_names, payloads, strict=True):
            _require_repository_lock(repository, git_directory)
            _require_legacy_guard_boundary(root_fd, legacy_boundary)
            _require_publication_path_binding(configs, output_parent)
            temporary = _create_owned_file_at(
                output_parent.fd,
                name,
                payload,
                mode=0o644,
                context="P-CERT temporary",
            )
            temporaries.append(temporary)
            if _read_owned_file_at(
                temporary,
                context="P-CERT temporary",
                link_count=1,
                mode=0o644,
            ) != payload:
                raise _error("P-CERT temporary bytes drifted")
            _require_publication_path_binding(configs, output_parent)
            _require_legacy_guard_boundary(root_fd, legacy_boundary)
            _require_repository_lock(repository, git_directory)
        os.fsync(output_parent.fd)

        # Authority first; companion manifest is intentionally the last link.
        for index, destination_name in enumerate(output_names):
            _require_repository_lock(repository, git_directory)
            _require_legacy_guard_boundary(root_fd, legacy_boundary)
            _require_publication_path_binding(configs, output_parent)
            published.append(
                _link_no_clobber(temporaries[index], output_parent.fd, destination_name)
            )
            os.fsync(output_parent.fd)
            _require_publication_path_binding(configs, output_parent)
            _require_legacy_guard_boundary(root_fd, legacy_boundary)
            _require_repository_lock(repository, git_directory)

        for owner, payload in zip(published, payloads, strict=True):
            if _read_owned_file_at(
                owner,
                context="P-CERT linked output",
                link_count=2,
                mode=0o644,
            ) != payload:
                raise _error("P-CERT linked output bytes drifted")
        while temporaries:
            owner = temporaries[-1]
            _unlink_owned_file_at(owner, context="P-CERT temporary")
            temporaries.pop()
        os.fsync(output_parent.fd)
        _require_publication_path_binding(configs, output_parent)
        _require_legacy_guard_boundary(root_fd, legacy_boundary)
        if postpublish_validator is not None:
            postpublish_validator()
        _require_repository_lock(repository, git_directory)
        _require_legacy_guard_boundary(root_fd, legacy_boundary)
        _require_publication_path_binding(configs, output_parent)
        for owner, payload in zip(published, payloads, strict=True):
            if _read_owned_file_at(
                owner,
                context="P-CERT final output",
                link_count=1,
                mode=0o644,
            ) != payload:
                raise _error("P-CERT final output bytes drifted")
        _require_repository_lock(repository, git_directory)
        _require_legacy_guard_boundary(root_fd, legacy_boundary)
        _require_publication_path_binding(configs, output_parent)
        for owner, payload in zip(published, payloads, strict=True):
            if _read_owned_file_at(
                owner,
                context="P-CERT committed output",
                link_count=1,
                mode=0o644,
            ) != payload:
                raise _error("P-CERT committed output bytes drifted")
        if any(
            name.startswith((TEMP_PREFIX, CLEANUP_TOMBSTONE_PREFIX))
            for name in os.listdir(output_parent.fd)
        ):
            raise _error("P-CERT temporary output namespace remains before success")
        _require_publication_path_binding(configs, output_parent)
        _require_repository_lock(repository, git_directory)
        _require_legacy_guard_boundary(root_fd, legacy_boundary)
        _require_relative_absent_at(
            root_fd,
            certification.CERTIFICATION_ROOT.as_posix(),
            context="R-CERT output namespace",
        )
        _require_repository_lock(repository, git_directory)
        _require_legacy_guard_boundary(root_fd, legacy_boundary)
    except BaseException as exc:
        primary = exc
        while published:
            owner = published[-1]
            try:
                _unlink_owned_file_at(owner, context="P-CERT published output")
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
            finally:
                published.pop()
    finally:
        while temporaries:
            owner = temporaries[-1]
            try:
                _unlink_owned_file_at(owner, context="P-CERT temporary")
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
            finally:
                temporaries.pop()
        if git_directory is not None:
            try:
                fcntl.flock(git_directory.fd, fcntl.LOCK_UN)
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        for descriptor in reversed(open_fds):
            try:
                os.close(descriptor)
            except OSError:
                pass

    if cleanup_errors:
        message = "; ".join(f"{type(exc).__name__}: {exc}" for exc in cleanup_errors)
        raise _error(f"P-CERT cleanup could not complete safely: {message}") from cleanup_errors[0]
    if primary is not None:
        raise primary
    return authority_record, manifest_record


def generate(
    *, root: Path = PROJECT_ROOT, verify_remote: bool = True
) -> dict[str, Any]:
    """Generate P-CERT only; never execute R-CERT verification work."""

    root = root.resolve()
    before = _collect_published_state(root, verify_remote=verify_remote)
    authority = _build_authority(before)
    after = _collect_published_state(root, verify_remote=verify_remote)
    if before != after:
        raise _error("H-CERT repository or locked inputs changed before publication")

    def revalidate_before_link() -> None:
        observed = _collect_published_state(
            root,
            verify_remote=verify_remote,
            publication_phase="flock_prelink",
        )
        if observed != before:
            raise _error("H-CERT repository or inputs changed before P-CERT publication")

    def revalidate_after_links() -> None:
        observed = _collect_published_state(
            root,
            verify_remote=verify_remote,
            publication_phase="flock_postlink",
        )
        if observed != before:
            raise _error("H-CERT repository or inputs changed during P-CERT publication")

    authority_record, manifest_record = publish_authority_bundle(
        root,
        authority,
        prepublish_validator=revalidate_before_link,
        postpublish_validator=revalidate_after_links,
    )
    return {
        "status": "authority_bundle_written_unpublished",
        "gate": GATE,
        "h1_cert_commit": H1_CERT_COMMIT,
        "p1_cert_commit": P1_CERT_COMMIT,
        "h2_cert_commit": H2_CERT_COMMIT,
        "p2_cert_commit": P2_CERT_COMMIT,
        "h3_cert_commit": before["h_cert_commit"],
        "h_cert_commit": before["h_cert_commit"],
        "authority": authority_record,
        "manifest": manifest_record,
        "dvc_status_checked": True,
        "dvc_pull_commands_run": False,
        "test_commands_run": False,
        "parquet_payloads_opened": False,
        "raw_targets_accessed": False,
        "raw_outcomes_accessed": False,
        "git_publication_commands_run": False,
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
    except certification.FinalCertificationContractError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(certification.canonical_json_bytes(payload).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
