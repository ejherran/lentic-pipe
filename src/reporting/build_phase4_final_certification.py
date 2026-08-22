#!/usr/bin/env python
"""Build the final Closure V1 Phase 4 software certification bundle.

This module is intentionally independent from the historical E10 generator.
The real transaction is enabled only by a published P-CERT authority.  It
clones that exact commit into an owned temporary namespace and lets DVC alone
transport/authenticate the eight sealed objects, one pointer at a time, into
an initially empty cache.  Python validates only pointer declarations,
content-addressed cache names, and filesystem metadata; it never opens a
restored Parquet or cache object.  The locked public/OpenAPI/E2E verification
then runs in a read-only sandbox.  The eight public artifacts are linked into
place atomically, with the manifest last.

``--check-only`` never clones, pulls, starts a database, runs tests, or writes
outputs.  Git commit, push, and tag operations are never performed here.
"""

from __future__ import annotations

import argparse
import configparser
import copy
import ctypes
import errno
import fcntl
import io
import json
import os
import pwd
import re
import secrets
import socket
import stat
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, cast

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.reporting.phase4_final_certification_contract import (  # noqa: E402
    AUTHORITY_MANIFEST_PATH,
    AUTHORITY_PATH,
    CERTIFICATION_ROOT,
    GUARD_PATH,
    LOCAL_DVC_CONFIG_PATH,
    OUTPUT_PATHS,
    PROJECT_ROOT,
    FinalCertificationContract,
    FinalCertificationContractError,
    canonical_json_bytes,
    collect_anchor_input_records,
    collect_dvc_pointer_records,
    digest_records,
    digest_strings,
    expected_dvc_status_policy,
    expected_cleanup_diagnostic_policy,
    expected_environment_dvc_record,
    expected_manifest_clone_dvc_site_caches_record,
    expected_p9_failure_record,
    expected_p10_failure_record,
    expected_p11_failure_record,
    expected_p12_failure_record,
    expected_h13_failure_record,
    expected_p14_failure_record,
    expected_p15_failure_record,
    expected_p16_failure_record,
    expected_p17_failure_record,
    expected_postgres_cleanup_policy,
    expected_postgres_connection_policy,
    expected_postgres_destroy_poll_policy,
    expected_postgres_portable_path_policy,
    expected_postgres_startup_stability_policy,
    expected_sandbox_mountpoint_policy,
    expected_sandbox_smoke_policy,
    expected_test_access_guard_policy,
    expected_public_tests_junit_diagnostic_policy,
    load_contract,
    load_effective_authority,
    main_dvc_static_boundary_record,
    parse_dvc_pointer_bytes,
    sha256_bytes,
    validate_local_dvc_remote_configuration,
)


SCHEMA_VERSION = "closure_v1_phase4_final_certification_bundle_v1"
PUBLIC_SUITE_KIND = "closure_phase4_final_public"
E2E_SUITE_KIND = "closure_phase4_final_synthetic_e2e"
PLUGIN_MODE_ENV = "CLOSURE_PHASE4_CERTIFICATION_SUITE_KIND"
PLUGIN_ROOT_ENV = "CLOSURE_PHASE4_CERTIFICATION_REPO_ROOT"
PLUGIN_RETAINED_PYTHON_ENV = "CLOSURE_PHASE4_CERTIFICATION_RETAINED_PYTHON"
TRUSTED_SYSTEM_PYTHON_ROOT = Path("/usr")
SANDBOX_RETAINED_PYTHON_ALIAS = Path("/cert-python")
SANDBOX_RETAINED_POETRY_ROOT = Path("/cert-poetry")
PROC_SELF_EXE_PATH = Path("/proc/self/exe")
DB_SOCKET_ROOT = "/cert-db"
DB_NAME = "closure_phase4_cert"
CONTAINER_POSTGRES_SOCKET_ROOT = "/var/run/postgresql"
POSTGRES_PID1_COMM_PATH = "/proc/1/comm"
POSTGRES_FINAL_PID1_COMM = "postgres"
POSTGRES_IMAGE = (
    "postgres:16-alpine@sha256:"
    "16bc17c64a573ef34162af9298258d1aec548232985b33ed7b1eac33ba35c229"
)
POSTGRES_GRACEFUL_STOP_TIMEOUT_SECONDS = 30
POSTGRES_DESTROY_POLL_MAX_ATTEMPTS = 120
POSTGRES_DESTROY_POLL_INTERVAL_SECONDS = 0.1
POSTGRES_STABILITY_MAX_ATTEMPTS = 120
POSTGRES_STABILITY_INTERVAL_SECONDS = 0.25
POSTGRES_SOCKET_ENTRY_SPECS = (
    (".s.PGSQL.5432", "socket"),
    (".s.PGSQL.5432.lock", "regular_file"),
)
HTTP_METHODS = frozenset(
    {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
)
DOCUMENTED_API_PATHS = (
    "docs/API_DATASET_CONTRACT.md",
    "docs/API_PROTOCOL.md",
)
DOCUMENTED_OPERATION_RE = re.compile(
    r"\b(GET|PUT|POST|DELETE|PATCH|OPTIONS|HEAD)\s+"
    r"(/(?:[A-Za-z0-9_.~:@!$&'()*+,;=\-/]|\{[A-Za-z0-9_]+\})+)"
)
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
MD5_RE = re.compile(r"^[0-9a-f]{32}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_DB_URL = "postgresql+asyncpg://postgres@/closure_phase4_cert"
GIT_EXECUTABLE = "/usr/bin/git"
FORBIDDEN_COMMAND_TOKENS = (
    "--execute-sealed-batch",
    "data/targets",
    "data/closure_v1/unblinded",
    "data/closure_v1/evaluation_outcomes",
    "outcome_access_log",
    "private/",
)
SANDBOX_ABSENT_FORBIDDEN_PREFIXES = (
    "private/",
    "data/targets/",
    "data/closure_v1/unblinded/",
    "data/closure_v1/evaluation_outcomes/",
)
SANDBOX_MASKED_FORBIDDEN_PATHS = (
    "reports/closure_v1/00_protocol/outcome_access_log.jsonl",
)
JUNIT_SKIP_TYPE = "pytest.skip"

SAFE_COMMAND_FAILURE_CATEGORIES = frozenset(
    {
        "authn",
        "authz",
        "network",
        "remote_object_missing",
        "nonzero_exit",
        "sandbox_launch_failure",
        "sandbox_handshake_failure",
    }
)

SANDBOX_MOUNTPOINT_NAMES = (".venv", "tmp")
SANDBOX_MOUNTPOINT_MODE = 0o700
SANDBOX_SMOKE_MARKER_NAME = ".phase4-final-certification-sandbox-smoke"
SANDBOX_SMOKE_PORTABLE_COMMAND = ("<SANDBOX_SMOKE>",)
CLEANUP_REASON_CODES = frozenset(
    {
        "database_owner_retained",
        "frozen_inventory_drift",
        "socket_inventory_nonempty",
        "owned_site_cache_drift",
        "sandbox_inventory_drift",
        "work_tree_remove_failed",
        "unclassified_cleanup_failure",
    }
)
SAFE_INTERNAL_FAILURE_POLICIES: Mapping[str, tuple[str, str]] = {
    "namespace_validation": (
        "namespace_invariant_mismatch",
        "in_process_namespace_validation",
    ),
    "sandbox_projection": (
        "forbidden_path_kind_mismatch",
        "in_process_sandbox_projection",
    ),
    "verification_runtime_acquisition": (
        "runtime_binding_failure",
        "in_process_verification_runtime_acquisition",
    ),
}
PUBLIC_TESTS_FAILURE_STATUSES = frozenset(
    {"failure_identity_available", "failure_identity_unavailable"}
)
PUBLIC_TESTS_JUNIT_UNAVAILABLE_REASONS = frozenset(
    {
        "junit_absent",
        "junit_unsafe_identity",
        "junit_oversized",
        "junit_malformed_or_hostile",
        "junit_sealed_suite_drift",
    }
)


@dataclass(frozen=True)
class CommandFailureEvidence:
    """Sanitized command-failure facts safe to retain after cleanup failure."""

    stage: str
    sanitized_command: tuple[str, ...]
    returncode: int | None
    safe_stderr_category: str

    def as_record(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "sanitized_command": list(self.sanitized_command),
            "returncode": self.returncode,
            "safe_stderr_category": self.safe_stderr_category,
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        }


@dataclass(frozen=True)
class InternalFailureEvidence:
    """Allowlisted in-process failure facts safe after cleanup failure."""

    stage: str
    safe_error: str
    failure_kind: str

    def __post_init__(self) -> None:
        if SAFE_INTERNAL_FAILURE_POLICIES.get(self.stage) != (
            self.safe_error,
            self.failure_kind,
        ):
            raise ValueError("internal failure evidence is not allowlisted")

    def as_record(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "safe_error": self.safe_error,
            "failure_kind": self.failure_kind,
            "sanitized_command": [],
            "returncode": None,
            "safe_stderr_category": "unavailable_not_persisted",
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        }


@dataclass(frozen=True)
class PublicTestsFailureEvidence:
    """Strict, path-free projection of one non-passing public pytest run."""

    status: str
    returncode: int
    totals: Mapping[str, int]
    failed_nodeids: tuple[str, ...]
    failed_nodeids_sha256: str
    error_nodeids: tuple[str, ...]
    error_nodeids_sha256: str
    collected_test_count: int | None
    collected_nodeids_sha256: str | None
    unavailable_reason: str | None

    def __post_init__(self) -> None:
        if (
            self.status not in PUBLIC_TESTS_FAILURE_STATUSES
            or type(self.returncode) is not int
            or tuple(sorted(self.failed_nodeids)) != self.failed_nodeids
            or tuple(sorted(self.error_nodeids)) != self.error_nodeids
            or len(set(self.failed_nodeids)) != len(self.failed_nodeids)
            or len(set(self.error_nodeids)) != len(self.error_nodeids)
            or self.failed_nodeids_sha256 != digest_strings(self.failed_nodeids)
            or self.error_nodeids_sha256 != digest_strings(self.error_nodeids)
        ):
            raise ValueError("public-tests failure evidence is malformed")
        for nodeid in (*self.failed_nodeids, *self.error_nodeids):
            path_text, separator, suffix = nodeid.partition("::")
            path = PurePosixPath(path_text)
            if (
                not separator
                or not suffix
                or not path_text.endswith(".py")
                or path.is_absolute()
                or path.as_posix() != path_text
                or any(part in {"", ".", ".."} for part in path.parts)
            ):
                raise ValueError("public-tests failure node-id is not repository-relative")
        if self.status == "failure_identity_available":
            expected_total_keys = {
                "tests",
                "passed",
                "failures",
                "errors",
                "skipped",
            }
            if (
                set(self.totals) != expected_total_keys
                or any(type(value) is not int or value < 0 for value in self.totals.values())
                or self.totals["tests"]
                + len(set(self.failed_nodeids).intersection(self.error_nodeids))
                != self.totals["passed"]
                + self.totals["failures"]
                + self.totals["errors"]
                + self.totals["skipped"]
                or self.totals["failures"] != len(self.failed_nodeids)
                or self.totals["errors"] != len(self.error_nodeids)
                or not self.failed_nodeids
                and not self.error_nodeids
                or self.returncode == 0
                or type(self.collected_test_count) is not int
                or self.collected_test_count != self.totals["tests"]
                or not isinstance(self.collected_nodeids_sha256, str)
                or SHA256_RE.fullmatch(self.collected_nodeids_sha256) is None
                or self.unavailable_reason is not None
            ):
                raise ValueError("available public-tests failure evidence is malformed")
        elif (
            dict(self.totals)
            or self.failed_nodeids
            or self.error_nodeids
            or self.collected_test_count is not None
            or self.collected_nodeids_sha256 is not None
            or self.unavailable_reason not in PUBLIC_TESTS_JUNIT_UNAVAILABLE_REASONS
        ):
            raise ValueError("unavailable public-tests failure evidence is malformed")

    def as_record(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "returncode": self.returncode,
            "totals": dict(self.totals),
            "failed_nodeids": list(self.failed_nodeids),
            "failed_nodeids_sha256": self.failed_nodeids_sha256,
            "error_nodeids": list(self.error_nodeids),
            "error_nodeids_sha256": self.error_nodeids_sha256,
            "collected_test_count": self.collected_test_count,
            "collected_nodeids_sha256": self.collected_nodeids_sha256,
            "unavailable_reason": self.unavailable_reason,
            "messages_preserved": False,
            "tracebacks_preserved": False,
            "raw_junit_preserved": False,
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        }


class _PublicTestsJunitUnavailable(Exception):
    """Internal path-free classification; never serialized with its cause."""

    def __init__(self, reason: str) -> None:
        if reason not in PUBLIC_TESTS_JUNIT_UNAVAILABLE_REASONS:
            raise ValueError("public-tests JUnit unavailable reason is not allowlisted")
        super().__init__(reason)
        self.reason = reason


class FinalCertificationBuildError(FinalCertificationContractError):
    """Raised when certification cannot proceed without weakening P-CERT."""

    def __init__(
        self,
        message: str,
        *,
        command_failure: CommandFailureEvidence | None = None,
        internal_failure: InternalFailureEvidence | None = None,
        public_tests_failure: PublicTestsFailureEvidence | None = None,
    ) -> None:
        super().__init__(message)
        if sum(
            evidence is not None
            for evidence in (
                command_failure,
                internal_failure,
                public_tests_failure,
            )
        ) > 1:
            raise ValueError("failure evidence kinds are mutually exclusive")
        self.command_failure = command_failure
        self.internal_failure = internal_failure
        self.public_tests_failure = public_tests_failure


def _error(
    message: str,
    *,
    command_failure: CommandFailureEvidence | None = None,
    internal_failure: InternalFailureEvidence | None = None,
    public_tests_failure: PublicTestsFailureEvidence | None = None,
) -> FinalCertificationBuildError:
    return FinalCertificationBuildError(
        message,
        command_failure=command_failure,
        internal_failure=internal_failure,
        public_tests_failure=public_tests_failure,
    )


def _internal_error(
    message: str,
    *,
    stage: str,
    category: str,
) -> FinalCertificationBuildError:
    """Build one path-free, raw-free in-process diagnostic."""

    policy = SAFE_INTERNAL_FAILURE_POLICIES.get(stage)
    if policy is None or policy[0] != category:
        raise ValueError("internal failure stage/category is not allowlisted")
    return _error(
        message,
        internal_failure=InternalFailureEvidence(
            stage=stage,
            safe_error=category,
            failure_kind=policy[1],
        ),
    )


@dataclass(frozen=True)
class CommandResult:
    """A subprocess result plus a deterministic, redacted evidence record."""

    record: Mapping[str, Any]
    stdout: str
    stderr: str


@dataclass
class AnchoredExecutable:
    """Regular executable retained by FD and rebound through held ancestors."""

    root: Path
    chain: list[DirectoryHandle]
    name: str
    fd: int
    device: int
    inode: int

    @property
    def proc_path(self) -> str:
        return f"/proc/self/fd/{self.fd}"

    def revalidate(self, *, context: str) -> None:
        _rebind_directory_chain(self.root, self.chain, context=context)
        opened = os.fstat(self.fd)
        named = os.stat(
            self.name,
            dir_fd=self.chain[-1].fd,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or opened.st_nlink != 1
            or named.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) & 0o111 == 0
            or stat.S_IMODE(named.st_mode) & 0o111 == 0
            or (opened.st_dev, opened.st_ino) != (self.device, self.inode)
            or (named.st_dev, named.st_ino) != (self.device, self.inode)
        ):
            raise _error(f"{context} executable binding drifted")

    def close(self) -> None:
        try:
            os.close(self.fd)
        finally:
            for handle in reversed(self.chain):
                handle.close()


@dataclass
class DirectoryHandle:
    """Open, identity-bound directory used for anchored mutation."""

    path: Path
    fd: int
    device: int
    inode: int
    closed: bool = False

    def close(self) -> None:
        if not self.closed:
            os.close(self.fd)
            self.closed = True


def _stat_identity(metadata: os.stat_result) -> tuple[int, ...]:
    """Stable identity used for retained executable and launcher bindings."""

    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


@dataclass
class AnchoredPythonInterpreter:
    """A venv launcher symlink plus its retained trusted ``/usr`` target."""

    root: Path
    chain: list[DirectoryHandle]
    name: str
    target: str
    fd: int
    link_identity: tuple[int, ...]
    target_identity: tuple[int, ...]

    @property
    def proc_path(self) -> str:
        return f"/proc/self/fd/{self.fd}"

    @property
    def venv_fd(self) -> int:
        if len(self.chain) < 2 or self.chain[-1].path.name != "bin":
            raise _error("retained Python launcher has no exact venv binding")
        return self.chain[-2].fd

    @property
    def venv_proc_path(self) -> str:
        return f"/proc/self/fd/{self.venv_fd}"

    def revalidate(self, *, context: str) -> None:
        _rebind_directory_chain(self.root, self.chain, context=context)
        try:
            link = os.stat(
                self.name,
                dir_fd=self.chain[-1].fd,
                follow_symlinks=False,
            )
            target = os.readlink(self.name, dir_fd=self.chain[-1].fd)
            followed = os.stat(
                self.name,
                dir_fd=self.chain[-1].fd,
                follow_symlinks=True,
            )
            opened = os.fstat(self.fd)
        except OSError as exc:
            raise _error(f"{context} Python launcher/interpreter vanished") from exc
        if (
            not stat.S_ISLNK(link.st_mode)
            or link.st_nlink != 1
            or _stat_identity(link) != self.link_identity
            or target != self.target
            or not stat.S_ISREG(followed.st_mode)
            or not stat.S_ISREG(opened.st_mode)
            or stat.S_IMODE(opened.st_mode) != 0o755
            or _stat_identity(followed) != self.target_identity
            or _stat_identity(opened) != self.target_identity
        ):
            raise _error(f"{context} Python launcher/interpreter binding drifted")

    def close(self) -> None:
        try:
            os.close(self.fd)
        finally:
            for handle in reversed(self.chain):
                handle.close()


@dataclass
class AnchoredPythonScriptRuntime:
    """Both retained layers of one Python console-script invocation."""

    script: AnchoredExecutable
    interpreter: AnchoredPythonInterpreter

    def revalidate(self, *, context: str) -> None:
        self.script.revalidate(context=f"{context} script")
        self.interpreter.revalidate(context=f"{context} interpreter")

    def close(self) -> None:
        first_error: OSError | None = None
        try:
            self.script.close()
        except OSError as exc:
            first_error = exc
        try:
            self.interpreter.close()
        except OSError as exc:
            first_error = first_error or exc
        if first_error is not None:
            raise first_error


@dataclass
class RetainedRegularFile:
    """A non-executable regular bind source retained under an owned dirfd."""

    parent: DirectoryHandle
    name: str
    fd: int
    identity: tuple[int, ...]
    allowed_modes: frozenset[int]

    @property
    def proc_path(self) -> str:
        return f"/proc/self/fd/{self.fd}"

    def revalidate(self, *, context: str) -> None:
        opened = os.fstat(self.fd)
        try:
            named = os.stat(self.name, dir_fd=self.parent.fd, follow_symlinks=False)
        except OSError as exc:
            raise _error(f"{context} retained file name vanished") from exc
        if (
            not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or opened.st_nlink != 1
            or named.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) not in self.allowed_modes
            or stat.S_IMODE(named.st_mode) not in self.allowed_modes
            or _stat_identity(opened) != self.identity
            or _stat_identity(named) != self.identity
        ):
            raise _error(f"{context} retained file binding drifted")

    def close(self) -> None:
        os.close(self.fd)


@dataclass(frozen=True)
class OwnedFileAt:
    """File capability bound to an already-open parent directory."""

    parent: DirectoryHandle
    name: str
    device: int
    inode: int

    @property
    def path(self) -> Path:
        return self.parent.path / self.name


@dataclass(frozen=True)
class WorkInventoryEntry:
    """One inode/type binding in the owned temporary tree."""

    path: str
    device: int
    inode: int
    kind: str
    link_count: int
    mode: int


@dataclass
class CloneMountpointLease:
    """Exact empty clone directories retained as nested bwrap mount targets."""

    clone: DirectoryHandle
    handles: tuple[DirectoryHandle, DirectoryHandle]
    inventory_after_creation: Mapping[str, WorkInventoryEntry]

    def revalidate(self, *, context: str) -> None:
        clone_metadata = os.fstat(self.clone.fd)
        if (
            not stat.S_ISDIR(clone_metadata.st_mode)
            or (clone_metadata.st_dev, clone_metadata.st_ino)
            != (self.clone.device, self.clone.inode)
            or tuple(handle.path.name for handle in self.handles)
            != SANDBOX_MOUNTPOINT_NAMES
        ):
            raise _error(f"{context} clone mountpoint lease drifted")
        for expected_name, handle in zip(
            SANDBOX_MOUNTPOINT_NAMES, self.handles, strict=True
        ):
            if handle.closed:
                raise _error(f"{context} retained clone mountpoint FD closed")
            try:
                named = os.stat(
                    expected_name,
                    dir_fd=self.clone.fd,
                    follow_symlinks=False,
                )
                opened = os.fstat(handle.fd)
            except OSError as exc:
                raise _error(f"{context} clone mountpoint vanished") from exc
            if (
                not stat.S_ISDIR(named.st_mode)
                or not stat.S_ISDIR(opened.st_mode)
                or (named.st_dev, named.st_ino)
                != (handle.device, handle.inode)
                or (opened.st_dev, opened.st_ino)
                != (handle.device, handle.inode)
                or stat.S_IMODE(named.st_mode) != SANDBOX_MOUNTPOINT_MODE
                or stat.S_IMODE(opened.st_mode) != SANDBOX_MOUNTPOINT_MODE
                or os.listdir(handle.fd)
            ):
                raise _error(f"{context} clone mountpoint identity drifted")

    def close(self) -> None:
        for handle in reversed(self.handles):
            handle.close()


@dataclass(frozen=True)
class CleanupAssessment:
    """Closed cleanup disposition containing only contract-allowlisted enums."""

    status: str
    namespace_preserved: bool
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in {"ready_for_owned_cleanup", "failed_closed"}:
            raise ValueError("cleanup assessment status is not allowlisted")
        if (
            len(self.reason_codes) != len(set(self.reason_codes))
            or any(reason not in CLEANUP_REASON_CODES for reason in self.reason_codes)
            or self.reason_codes != tuple(sorted(self.reason_codes))
            or (self.status == "ready_for_owned_cleanup")
            != (not self.reason_codes and not self.namespace_preserved)
        ):
            raise ValueError("cleanup assessment reasons are not allowlisted")

    def as_record(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "namespace_preserved": self.namespace_preserved,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True)
class OwnedPostgresSocketEntry:
    """One exact PostgreSQL socket artifact claimed under a retained dirfd."""

    name: str
    device: int
    inode: int
    kind: str
    link_count: int


@dataclass(frozen=True)
class OwnedPostgres:
    """Private Docker identity; neither field may enter public evidence."""

    name: str
    container_id: str
    socket_inventory: tuple[OwnedPostgresSocketEntry, ...] = ()


@dataclass
class RepositoryRootLease:
    """Retained parent/root binding that detects rename-and-restore attacks."""

    canonical: Path
    grandparent: DirectoryHandle
    parent: DirectoryHandle
    root: DirectoryHandle
    grandparent_binding: tuple[Any, ...]
    parent_binding: tuple[Any, ...]

    def revalidate(self, *, context: str) -> None:
        for ancestor in (self.grandparent, self.parent, self.root):
            opened = os.fstat(ancestor.fd)
            if (
                opened.st_dev,
                opened.st_ino,
                stat.S_ISDIR(opened.st_mode),
            ) != (ancestor.device, ancestor.inode, True):
                raise _error(f"{context} retained repository ancestor drifted")
        named_parent = os.stat(
            self.parent.path.name,
            dir_fd=self.grandparent.fd,
            follow_symlinks=False,
        )
        named_root = os.stat(
            self.root.path.name,
            dir_fd=self.parent.fd,
            follow_symlinks=False,
        )
        if (
            named_parent.st_dev,
            named_parent.st_ino,
            stat.S_ISDIR(named_parent.st_mode),
        ) != (self.parent.device, self.parent.inode, True) or (
            named_root.st_dev,
            named_root.st_ino,
            stat.S_ISDIR(named_root.st_mode),
        ) != (self.root.device, self.root.inode, True):
            raise _error(f"{context} repository path binding drifted")
        if _directory_binding(self.grandparent) != self.grandparent_binding:
            raise _error(f"{context} repository grandparent namespace drifted")
        if _directory_binding(self.parent) != self.parent_binding:
            raise _error(f"{context} repository parent namespace drifted")
        fresh = os.open(
            self.canonical,
            os.O_RDONLY
            | os.O_DIRECTORY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
        try:
            observed = os.fstat(fresh)
            if (observed.st_dev, observed.st_ino) != (
                self.root.device,
                self.root.inode,
            ):
                raise _error(f"{context} absolute repository rebind drifted")
        finally:
            os.close(fresh)
        # Detect a swap between the named checks and the fresh absolute open.
        repeated = os.stat(
            self.root.path.name,
            dir_fd=self.parent.fd,
            follow_symlinks=False,
        )
        if (repeated.st_dev, repeated.st_ino) != (
            self.root.device,
            self.root.inode,
        ):
            raise _error(f"{context} repository root changed during rebind")

    def close(self) -> None:
        first_error: OSError | None = None
        for handle in (self.root, self.parent, self.grandparent):
            try:
                handle.close()
            except OSError as exc:
                first_error = first_error or exc
        if first_error is not None:
            raise first_error


@dataclass
class RunGuard:
    """Cooperative whole-run lease and its anchored ignored namespace.

    Exclusivity is carried only by ``flock`` on the retained ``.git``
    directory descriptor.  The historical guard pathname is a negative
    invariant: this runner never creates, opens, adopts, or deletes it.
    """

    chain: list[DirectoryHandle]
    created_chain_indexes: list[int]
    git_chain: list[DirectoryHandle]
    legacy_guard_name: str
    lock_held: bool = True
    work: DirectoryHandle | None = None
    work_subdirectories: dict[str, DirectoryHandle] = field(default_factory=dict)
    work_inventory: Mapping[str, WorkInventoryEntry] | None = None
    removed: bool = False

    @property
    def parent(self) -> DirectoryHandle:
        return self.chain[-1]

    def create_work_directory(self) -> tuple[Path, tuple[int, int]]:
        self.require_legacy_guard_absent(context="before work creation")
        if self.work is not None:
            raise _error("owned certification work directory already exists")
        name = f"run-{secrets.token_hex(16)}"
        self.work = _mkdir_owned_at(
            self.parent,
            name,
            mode=0o700,
            context="owned certification work directory",
        )
        return self.work.path, (self.work.device, self.work.inode)

    def require_legacy_guard_absent(self, *, context: str) -> None:
        try:
            os.stat(
                self.legacy_guard_name,
                dir_fd=self.parent.fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return
        except OSError as exc:
            raise _error(f"{context}: legacy guard absence could not be proven") from exc
        raise _error(f"{context}: legacy final-certification guard path appeared")

    def revalidate_work_namespace(self, *, context: str) -> None:
        self.require_legacy_guard_absent(context=context)
        if self.work is None:
            raise _error(f"{context}: owned work namespace is absent")
        _rebind_directory_chain(
            self.chain[0].path,
            [*self.chain, self.work],
            context=f"{context} work namespace",
        )
        for name, child in self.work_subdirectories.items():
            try:
                metadata = os.stat(name, dir_fd=self.work.fd, follow_symlinks=False)
            except OSError as exc:
                raise _error(f"{context}: owned work subdirectory vanished") from exc
            if (
                metadata.st_dev,
                metadata.st_ino,
                stat.S_ISDIR(metadata.st_mode),
            ) != (child.device, child.inode, True):
                raise _error(f"{context}: owned work subdirectory identity drifted")

    def create_work_subdirectory(self, name: str, *, mode: int) -> DirectoryHandle:
        if self.work is None or not re.fullmatch(r"[a-z][a-z0-9-]*", name):
            raise _error("owned work subdirectory request is unsafe")
        if name in self.work_subdirectories:
            raise _error("owned work subdirectory already exists")
        self.revalidate_work_namespace(context=f"before creating {name}")
        child = _mkdir_owned_at(
            self.work,
            name,
            mode=mode,
            context=f"owned work subdirectory {name}",
        )
        self.work_subdirectories[name] = child
        self.revalidate_work_namespace(context=f"after creating {name}")
        return child

    def open_work_subdirectory(self, name: str) -> DirectoryHandle:
        if self.work is None or name in self.work_subdirectories:
            raise _error("owned work subdirectory registration is unsafe")
        self.revalidate_work_namespace(context=f"before opening {name}")
        descriptor = os.open(
            name,
            os.O_RDONLY
            | os.O_DIRECTORY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=self.work.fd,
        )
        metadata = os.fstat(descriptor)
        child = DirectoryHandle(
            self.work.path / name,
            descriptor,
            metadata.st_dev,
            metadata.st_ino,
        )
        self.work_subdirectories[name] = child
        self.revalidate_work_namespace(context=f"after opening {name}")
        return child

    def remove_work_directory(
        self,
        path: Path,
        identity: tuple[int, int],
        *,
        cleanup_callback: Callable[[str], None] | None = None,
    ) -> None:
        if path.parent != self.parent.path or not re.fullmatch(
            r"run-[0-9a-f]{32}", path.name
        ):
            raise _error("owned certification work directory escaped its lease")
        self.revalidate_work_namespace(context="before work cleanup")
        if self.work_inventory is None:
            raise _error("owned certification work inventory was not sealed")
        if self.work is None:
            raise _error("owned work handle vanished before cleanup")
        if _scan_work_inventory(self.work) != dict(self.work_inventory):
            raise _error("owned certification work inventory drifted before cleanup")
        for child in reversed(tuple(self.work_subdirectories.values())):
            child.close()
        self.work_subdirectories.clear()
        tombstone = _detach_owned_name_at(
            self.parent,
            path.name,
            device=identity[0],
            inode=identity[1],
            require_directory=True,
            context="owned certification work directory",
            owned_fd=self.work.fd,
        )
        root_cleanup_name = tombstone
        try:
            if cleanup_callback is not None:
                cleanup_callback("after_root_detach")
            _remove_sealed_work_tree(
                self.work,
                self.work_inventory,
                cleanup_callback=cleanup_callback,
            )
            _remove_owned_empty_directory_at(
                self.parent,
                tombstone,
                device=identity[0],
                inode=identity[1],
                context="empty owned certification work directory",
            )
            root_cleanup_name = ""
        except BaseException:
            # Restore the remaining temporary tree to its original ignored
            # name when possible.  Detected identity mismatches are preserved;
            # the same-UID mutation window inside a pathname syscall is the
            # explicit out-of-scope boundary recorded in the manifest.
            try:
                if root_cleanup_name:
                    _rename_noreplace_at(
                        self.parent.fd,
                        root_cleanup_name,
                        self.parent.fd,
                        path.name,
                    )
            except OSError:
                pass
            raise
        finally:
            self.work.close()
            self.work = None
            self.work_inventory = None

    def seal_work_inventory(self) -> Mapping[str, WorkInventoryEntry]:
        self.revalidate_work_namespace(context="before sealing work inventory")
        if self.work is None:
            raise _error("owned work namespace is absent while sealing inventory")
        first = _scan_work_inventory(self.work)
        second = _scan_work_inventory(self.work)
        if first != second:
            raise _error("owned work inventory changed while sealing")
        self.work_inventory = first
        return first

    def release(self) -> None:
        if self.removed:
            return
        self.require_legacy_guard_absent(context="before cooperative lease release")
        for index in reversed(self.created_chain_indexes):
            current = self.chain[index]
            parent = self.chain[index - 1]
            _remove_owned_empty_directory_at(
                parent,
                current.path.name,
                device=current.device,
                inode=current.inode,
                context="certification work namespace directory",
            )
        self.removed = True

    def close(self) -> None:
        for handle in reversed(tuple(self.work_subdirectories.values())):
            handle.close()
        self.work_subdirectories.clear()
        if self.work is not None:
            self.work.close()
            self.work = None
        for handle in reversed(self.chain):
            handle.close()
        if self.lock_held:
            try:
                fcntl.flock(self.git_chain[-1].fd, fcntl.LOCK_UN)
            finally:
                self.lock_held = False
        for handle in reversed(self.git_chain):
            handle.close()


@dataclass(frozen=True)
class ExecutionProducts:
    """In-memory products created before the publication transaction."""

    artifacts: Mapping[str, bytes]
    manifest: Mapping[str, Any]


@dataclass(frozen=True)
class PreparedWorkspace:
    """All retained capabilities established before any external execution."""

    owned_tmp: Path
    owned_tmp_identity: tuple[int, int]
    clone_root: Path
    cache_handle: DirectoryHandle
    site_cache_handle: DirectoryHandle
    version_site_cache_handle: DirectoryHandle
    sandbox_handle: DirectoryHandle
    socket_handle: DirectoryHandle
    mask_handle: DirectoryHandle
    work_handle: DirectoryHandle
    source_before: Mapping[str, Any]
    lease_parent_binding: tuple[Any, ...]
    work_binding: tuple[Any, ...]
    repository_root_binding: tuple[Any, ...]
    mask_inventory: Mapping[str, WorkInventoryEntry]
    cache_inventory: Mapping[str, WorkInventoryEntry]
    site_cache_inventory: Mapping[str, WorkInventoryEntry]
    version_site_cache_inventory: Mapping[str, WorkInventoryEntry]
    site_cache_root_identity: tuple[int, ...]
    version_site_cache_root_identity: tuple[int, ...]


@dataclass
class RetainedPrivateCredential:
    """Private credential file retained by inode without exposing its path."""

    root: Path
    chain: list[DirectoryHandle]
    name: str
    fd: int
    identity: tuple[int, ...]

    @property
    def proc_path(self) -> str:
        return f"/proc/self/fd/{self.fd}"

    def revalidate(self, *, context: str) -> None:
        _rebind_directory_chain(self.root, self.chain, context=context)
        opened = os.fstat(self.fd)
        try:
            named = os.stat(
                self.name,
                dir_fd=self.chain[-1].fd,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise _error(f"{context} private credential vanished") from exc
        if (
            not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or opened.st_nlink != 1
            or named.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) & 0o022
            or stat.S_IMODE(named.st_mode) & 0o022
            or _stat_identity(opened) != self.identity
            or _stat_identity(named) != self.identity
        ):
            raise _error(f"{context} private credential binding drifted")

    def close(self) -> None:
        try:
            os.close(self.fd)
        finally:
            for handle in reversed(self.chain):
                handle.close()


@dataclass
class InstalledDvcConfiguration:
    """Retained private config plus rebased credential descriptor bridges."""

    source_root: Path
    clone_root: Path
    source_chain: list[DirectoryHandle]
    clone_chain: list[DirectoryHandle]
    source_fd: int
    clone_fd: int
    source_identity: tuple[int, ...]
    credentials: tuple[RetainedPrivateCredential, ...]
    credential_sections: tuple[str, ...]
    public_record: Mapping[str, Any]
    owned_cache_root: Path | None = None

    @property
    def pass_fds(self) -> tuple[int, ...]:
        return tuple(item.fd for item in self.credentials)

    def bind_owned_cache(self, cache_root: Path) -> None:
        if self.owned_cache_root is not None or not cache_root.is_absolute():
            raise _error("owned DVC cache binding is malformed or already set")
        metadata = cache_root.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise _error("owned DVC cache binding is not a real directory")
        self.owned_cache_root = cache_root

    def revalidate(self, *, allow_operational_cache: bool, context: str) -> None:
        _rebind_directory_chain(
            self.source_root,
            self.source_chain,
            context=f"{context} source configuration",
        )
        _rebind_directory_chain(
            self.clone_root,
            self.clone_chain,
            context=f"{context} clone configuration",
        )
        source = _revalidate_open_file_name(
            self.source_chain[-1],
            LOCAL_DVC_CONFIG_PATH.name,
            self.source_fd,
            expected_modes=frozenset({0o600, 0o644}),
            context=f"{context} source configuration",
        )
        clone = _revalidate_open_file_name(
            self.clone_chain[-1],
            LOCAL_DVC_CONFIG_PATH.name,
            self.clone_fd,
            expected_modes=frozenset({0o600}),
            context=f"{context} clone configuration",
        )
        if _stat_identity(source) != self.source_identity:
            raise _error(f"{context} source DVC configuration drifted")
        for credential in self.credentials:
            credential.revalidate(context=context)
        source_payload = _read_open_regular_fd(
            self.source_fd,
            context=f"{context} source DVC configuration",
        )
        clone_payload = _read_open_regular_fd(
            self.clone_fd,
            context=f"{context} clone DVC configuration",
        )
        _require_private_dvc_config_equivalence(
            source_payload,
            clone_payload,
            credential_sections=self.credential_sections,
            credential_proc_paths=tuple(item.proc_path for item in self.credentials),
            allow_operational_cache=allow_operational_cache,
            owned_cache_dir=(
                os.fspath(self.owned_cache_root)
                if self.owned_cache_root is not None
                else None
            ),
        )
        if clone.st_size != len(clone_payload):
            raise _error(f"{context} clone DVC configuration size drifted")

    def close(self) -> None:
        errors: list[OSError] = []
        for credential in reversed(self.credentials):
            try:
                credential.close()
            except OSError as exc:
                errors.append(exc)
        for descriptor in (self.clone_fd, self.source_fd):
            try:
                os.close(descriptor)
            except OSError as exc:
                errors.append(exc)
        for chain in (self.clone_chain, self.source_chain):
            for handle in reversed(chain):
                try:
                    handle.close()
                except OSError as exc:
                    errors.append(exc)
        if errors:
            raise errors[0]


@dataclass
class MainDvcSiteCacheLease:
    """Private snapshot proving the configured main DVC site-cache is immutable."""

    root: Path
    config_chain: list[DirectoryHandle]
    config_fd: int
    config_identity: tuple[int, ...]
    site_cache_chain: list[DirectoryHandle]
    site_cache_identity: tuple[int, ...]
    inventory: Mapping[str, tuple[int, ...]]

    def revalidate(self, *, context: str) -> None:
        _rebind_directory_chain(
            self.root,
            self.config_chain,
            context=f"{context} source configuration",
        )
        config = _revalidate_open_file_name(
            self.config_chain[-1],
            LOCAL_DVC_CONFIG_PATH.name,
            self.config_fd,
            expected_modes=frozenset({0o600, 0o644}),
            context=f"{context} source configuration",
        )
        if _stat_identity(config) != self.config_identity:
            raise _error(f"{context} main DVC configuration changed")
        _require_exact_main_dvc_site_cache_path(
            _parse_private_dvc_config(
                _read_open_regular_fd(
                    self.config_fd,
                    context=f"{context} source configuration",
                )
            ),
            root=self.root,
        )
        _rebind_directory_chain(
            Path("/"), self.site_cache_chain, context=context
        )
        root_before = _site_cache_root_identity(
            self.site_cache_chain[-1],
            expected_mode=None,
            context=f"{context} main DVC site cache",
        )
        if root_before != self.site_cache_identity:
            raise _error(f"{context} main DVC site cache root changed")
        if _scan_private_metadata_tree(self.site_cache_chain[-1]) != dict(
            self.inventory
        ):
            raise _error(f"{context} main DVC site cache changed")
        root_after = _site_cache_root_identity(
            self.site_cache_chain[-1],
            expected_mode=None,
            context=f"{context} main DVC site cache",
        )
        if root_after != self.site_cache_identity:
            raise _error(f"{context} main DVC site cache root changed")

    def close(self) -> None:
        errors: list[OSError] = []
        try:
            os.close(self.config_fd)
        except OSError as exc:
            errors.append(exc)
        for chain in (self.site_cache_chain, self.config_chain):
            for handle in reversed(chain):
                try:
                    handle.close()
                except OSError as exc:
                    errors.append(exc)
        if errors:
            raise errors[0]


_ACCESS_GUARD_INSTALLED = False


def _require_relative(path_text: str, *, context: str) -> Path:
    pure = PurePosixPath(path_text)
    if (
        not path_text
        or pure.is_absolute()
        or ".." in pure.parts
        or pure.as_posix() != path_text
    ):
        raise _error(f"{context} must be a normalized repository-relative path")
    return Path(*pure.parts)


def _require_commit(value: str, *, context: str) -> str:
    if not COMMIT_RE.fullmatch(value):
        raise _error(f"{context} is not an exact commit")
    return value


def _canonical_json(value: Any) -> bytes:
    return canonical_json_bytes(value)


def _portable_argv(argv: Sequence[str]) -> list[str]:
    """Reject secrets/absolute paths in serialized command evidence."""

    rendered: list[str] = []
    for token in argv:
        if not isinstance(token, str) or not token or "\x00" in token:
            raise _error("command argv contains an invalid token")
        if re.search(r"(?<![A-Za-z0-9._~+@%-])/", token):
            raise _error("absolute command paths may not be serialized")
        lowered = token.lower()
        if any(marker in lowered for marker in ("password=", "token=", "secret=")):
            raise _error("credential-bearing command token may not be serialized")
        if "://" in token:
            raise _error("remote or database URLs may not be serialized")
        rendered.append(token)
    return rendered


def _safe_command_failure_stage(value: str) -> str:
    """Project an internal static context onto a path-free diagnostic token."""

    if (
        not isinstance(value, str)
        or re.fullmatch(r"[A-Za-z0-9 ._-]{1,96}", value) is None
    ):
        raise _error("command failure stage is not a safe static label")
    stage = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    if stage == "directed_dvc_pull_1":
        return "first_directed_dvc_pull"
    if not stage:
        raise _error("command failure stage is empty")
    return stage


def _classify_command_stderr(stderr: str) -> str:
    """Reduce an ephemeral stderr stream to one closed, non-sensitive enum."""

    lowered = stderr.casefold() if isinstance(stderr, str) else ""
    categories = (
        (
            "authn",
            (
                "unauthenticated",
                "authentication failed",
                "invalid credential",
                "credentials are invalid",
                "could not automatically determine credentials",
                "default credentials were not found",
                "anonymous caller",
                "refresherror",
                "invalid_grant",
                "http 401",
                "status code 401",
                "401 unauthorized",
            ),
        ),
        (
            "authz",
            (
                "permission denied",
                "access denied",
                "forbidden",
                "not authorized",
                "authorization failed",
                "storage.objects.",
                "http 403",
                "status code 403",
                "403 forbidden",
            ),
        ),
        (
            "remote_object_missing",
            (
                "remote object missing",
                "remote object was not found",
                "no such object",
                "nosuchkey",
                "blobnotfound",
                "missing cache file",
                "not in cache",
                "checkout failed for following targets",
                "is your cache up to date",
                "does not exist in remote storage",
                "http 404",
                "status code 404",
                "404 not found",
                "404 get",
            ),
        ),
        (
            "network",
            (
                "network is unreachable",
                "connection refused",
                "connection reset",
                "connection aborted",
                "temporary failure in name resolution",
                "name or service not known",
                "could not resolve",
                "dns failure",
                "connectionerror",
                "max retries exceeded",
                "service unavailable",
                "httpsconnectionpool",
                "timed out",
                "timeout",
                "proxyerror",
                "ssl error",
                "tls error",
            ),
        ),
    )
    for category, markers in categories:
        if any(marker in lowered for marker in markers):
            return category
    return "nonzero_exit"


def _command_failure_error(
    *,
    stage: str,
    command: Sequence[str],
    returncode: int | None,
    stderr: str,
) -> FinalCertificationBuildError:
    safe_command = tuple(_portable_argv(command))
    category = _classify_command_stderr(stderr)
    if category not in SAFE_COMMAND_FAILURE_CATEGORIES:
        category = "nonzero_exit"
    evidence = CommandFailureEvidence(
        stage=_safe_command_failure_stage(stage),
        sanitized_command=safe_command,
        returncode=returncode,
        safe_stderr_category=category,
    )
    diagnostic = json.dumps(
        evidence.as_record(),
        sort_keys=True,
        separators=(",", ":"),
    )
    return _error(
        f"verification command failed closed: {diagnostic}",
        command_failure=evidence,
    )


def _public_tests_failure_error(
    evidence: PublicTestsFailureEvidence,
) -> FinalCertificationBuildError:
    """Raiseable public-test failure with no raw pytest/JUnit diagnostics."""

    record = evidence.as_record()
    policy = expected_public_tests_junit_diagnostic_policy()
    if list(record) != policy.get("serialized_fields") or any(
        record[field]
        for field in (
            "messages_preserved",
            "tracebacks_preserved",
            "raw_junit_preserved",
            "raw_stdout_preserved",
            "raw_stderr_preserved",
            "credentials_preserved",
            "absolute_paths_preserved",
        )
    ):
        raise ValueError("public-tests failure evidence projection drifted")
    diagnostic = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
    )
    return _error(
        f"public tests failed closed: {diagnostic}",
        public_tests_failure=evidence,
    )


def _execution_cleanup_composite_error(
    active_error: BaseException,
    *,
    namespace_preserved: bool,
    reason_codes: Sequence[str],
) -> FinalCertificationBuildError:
    """Retain safe primary facts and the observed cleanup disposition."""

    command_evidence = (
        active_error.command_failure
        if isinstance(active_error, FinalCertificationBuildError)
        else None
    )
    internal_evidence = (
        active_error.internal_failure
        if isinstance(active_error, FinalCertificationBuildError)
        else None
    )
    public_tests_evidence = (
        active_error.public_tests_failure
        if isinstance(active_error, FinalCertificationBuildError)
        else None
    )
    primary = (
        command_evidence.as_record()
        if command_evidence is not None
        else internal_evidence.as_record()
        if internal_evidence is not None
        else public_tests_evidence.as_record()
        if public_tests_evidence is not None
        else {
            "stage": "execution",
            "sanitized_command": [],
            "returncode": None,
            "safe_stderr_category": "unavailable_not_persisted",
            "raw_stdout_preserved": False,
            "raw_stderr_preserved": False,
            "credentials_preserved": False,
            "absolute_paths_preserved": False,
        }
    )
    normalized_reasons = tuple(sorted(set(reason_codes)))
    if not normalized_reasons:
        normalized_reasons = ("unclassified_cleanup_failure",)
    cleanup = CleanupAssessment(
        status="failed_closed",
        namespace_preserved=namespace_preserved,
        reason_codes=normalized_reasons,
    )
    diagnostic = json.dumps(
        {
            "status": "execution_and_cleanup_failed_closed",
            "active_error": primary,
            "cleanup": cleanup.as_record(),
            "retry_authorized": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return _error(
        "final certification execution failed and temporary cleanup failed closed: "
        f"{diagnostic}",
        command_failure=command_evidence,
        internal_failure=internal_evidence,
        public_tests_failure=public_tests_evidence,
    )


def _run(
    argv: Sequence[str],
    *,
    cwd: Path,
    execution_argv: Sequence[str] | None = None,
    environment: Mapping[str, str] | None = None,
    inherit_environment: bool = True,
    timeout_seconds: int = 1800,
    require_success: bool = True,
    portable_argv: Sequence[str] | None = None,
    pass_fds: Sequence[int] = (),
    failure_stage: str = "verification command",
) -> CommandResult:
    if type(timeout_seconds) is not int or timeout_seconds <= 0:
        raise _error("command timeout must be a positive integer")
    recorded = _portable_argv(portable_argv or argv)
    env = os.environ.copy() if inherit_environment else {}
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "TZ": "UTC",
            "LC_ALL": "C.UTF-8",
            "LANG": "C.UTF-8",
        }
    )
    if environment:
        env.update(environment)
    inherited_descriptors = tuple(pass_fds)
    if any(type(descriptor) is not int or descriptor < 0 for descriptor in inherited_descriptors):
        raise _error("command inherited descriptor set is invalid")
    try:
        completed = subprocess.run(
            list(execution_argv or argv),
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
            pass_fds=inherited_descriptors,
        )
    except subprocess.TimeoutExpired:
        raise _command_failure_error(
            stage=failure_stage,
            command=recorded,
            returncode=None,
            stderr="",
        ) from None
    # Stdout/stderr commonly contain elapsed times, random temporary paths, or
    # DVC transfer speeds.  They are used to diagnose a failing invocation but
    # deliberately excluded from the deterministic public evidence record.
    record = {"argv": recorded, "returncode": completed.returncode}
    if require_success and completed.returncode != 0:
        raise _command_failure_error(
            stage=failure_stage,
            command=recorded,
            returncode=completed.returncode,
            stderr=completed.stderr,
        ) from None
    return CommandResult(record=record, stdout=completed.stdout, stderr=completed.stderr)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        [GIT_EXECUTABLE, *args],
        cwd=root,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        stdin=subprocess.DEVNULL,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if completed.returncode != 0:
        raise _error(f"Git query failed: {list(args)}")
    return completed.stdout.strip()


def _capture_main_state(root: Path) -> dict[str, Any]:
    head = _require_commit(_git(root, "rev-parse", "HEAD"), context="HEAD")
    return {
        "head": head,
        "main": _require_commit(
            _git(root, "rev-parse", "refs/heads/main"), context="main"
        ),
        "origin_main": _require_commit(
            _git(root, "rev-parse", "refs/remotes/origin/main"),
            context="origin/main",
        ),
        "origin_head": _require_commit(
            _git(root, "rev-parse", "refs/remotes/origin/HEAD^{commit}"),
            context="origin/HEAD",
        ),
        "status": _git(root, "status", "--porcelain=v1", "--untracked-files=all"),
        "cached_diff": _git(root, "diff", "--cached", "--name-status"),
        "unstaged_diff": _git(root, "diff", "--name-status"),
    }


def _require_isolated_dvc_command_root(
    *, source_root: Path, command_root: Path, context: str
) -> None:
    """Reject every pull/status command whose cwd is the main worktree."""

    try:
        source = source_root.resolve(strict=True)
        command = command_root.resolve(strict=True)
        source_metadata = source.stat()
        command_metadata = command.stat()
    except OSError as exc:
        raise _error(f"{context} root binding is unavailable") from exc
    if (
        not stat.S_ISDIR(source_metadata.st_mode)
        or not stat.S_ISDIR(command_metadata.st_mode)
        or (source_metadata.st_dev, source_metadata.st_ino)
        == (command_metadata.st_dev, command_metadata.st_ino)
    ):
        raise _error(f"{context} is restricted to the isolated clone")


def _dvc_status(
    root: Path,
    *,
    targets: Sequence[str],
    executable_root: Path | None = None,
    environment: Mapping[str, str] | None = None,
    private_pass_fds: Sequence[int] = (),
) -> str:
    explicit_targets = _explicit_dvc_status_targets(targets)
    if executable_root is None:
        raise _error("DVC status is restricted to the isolated clone")
    _require_isolated_dvc_command_root(
        source_root=executable_root,
        command_root=root,
        context="DVC status",
    )
    runtime = _open_python_script_runtime(
        executable_root,
        Path(".venv/bin/dvc"),
        context="DVC runtime",
    )
    try:
        return _dvc_status_with_executable(
            root,
            runtime,
            source_root=executable_root,
            targets=explicit_targets,
            environment=environment,
            private_pass_fds=private_pass_fds,
        )
    finally:
        runtime.close()


def _run_python_script_runtime(
    runtime: AnchoredPythonScriptRuntime,
    arguments: Sequence[str],
    *,
    cwd: Path,
    portable_argv: Sequence[str],
    environment: Mapping[str, str] | None = None,
    timeout_seconds: int,
    require_success: bool = True,
    context: str,
    private_pass_fds: Sequence[int] = (),
) -> CommandResult:
    """Execute exact retained script bytes with the exact retained interpreter."""

    runtime.revalidate(context=f"{context} before execution")
    command_environment = {
        **({} if environment is None else environment),
        "__PYVENV_LAUNCHER__": f"{runtime.interpreter.venv_proc_path}/bin/python",
    }
    inherited = tuple(
        dict.fromkeys(
            (
                runtime.interpreter.fd,
                runtime.interpreter.venv_fd,
                runtime.script.fd,
                *private_pass_fds,
            )
        )
    )
    result = _run(
        (runtime.interpreter.proc_path, runtime.script.proc_path, *arguments),
        cwd=cwd,
        portable_argv=portable_argv,
        environment=command_environment,
        timeout_seconds=timeout_seconds,
        require_success=require_success,
        pass_fds=inherited,
        failure_stage=context,
    )
    runtime.revalidate(context=f"{context} after execution")
    return result


def _dvc_status_with_executable(
    root: Path,
    executable: AnchoredPythonScriptRuntime,
    *,
    source_root: Path,
    targets: Sequence[str],
    environment: Mapping[str, str] | None = None,
    private_pass_fds: Sequence[int] = (),
) -> str:
    explicit_targets = _explicit_dvc_status_targets(targets)
    _require_isolated_dvc_command_root(
        source_root=source_root,
        command_root=root,
        context="DVC status",
    )
    result = _run_python_script_runtime(
        executable,
        ("status", "--json", *explicit_targets),
        cwd=root,
        portable_argv=(
            ".venv/bin/dvc",
            "status",
            "--json",
            *explicit_targets,
        ),
        environment={
            "DVC_NO_ANALYTICS": "1",
            **({} if environment is None else environment),
        },
        timeout_seconds=300,
        context="DVC status",
        private_pass_fds=private_pass_fds,
    )
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise _error("DVC status did not return JSON") from exc
    if parsed != {}:
        raise _error("DVC status must equal the empty object")
    return "{}"


def _explicit_dvc_status_targets(targets: Sequence[str]) -> tuple[str, ...]:
    """Return one explicit, normalized and duplicate-free status target set."""

    if isinstance(targets, (str, bytes)):
        raise _error("DVC status targets must be an explicit non-empty sequence")
    raw_targets = tuple(targets)
    if not raw_targets:
        raise _error("DVC status targets must be an explicit non-empty sequence")
    normalized: list[str] = []
    for raw_target in raw_targets:
        if not isinstance(raw_target, str):
            raise _error("DVC status target is malformed")
        segments = raw_target.split("/")
        if (
            raw_target.startswith("-")
            or "\x00" in raw_target
            or "\\" in raw_target
            or any(token in raw_target for token in "?*[]{}")
            or any(segment in {"", ".", ".."} for segment in segments)
        ):
            raise _error("DVC status target is malformed")
        normalized_target = _require_relative(
            raw_target,
            context="DVC status target",
        ).as_posix()
        if PurePosixPath(normalized_target).suffix != ".dvc":
            raise _error("DVC status target must be one canonical .dvc path")
        normalized.append(normalized_target)
    if len(set(normalized)) != len(normalized):
        raise _error("DVC status targets must be unique")
    return tuple(normalized)


def _contract_dvc_status_targets(
    contract: FinalCertificationContract,
    configured_targets: Sequence[str],
    *,
    context: str,
) -> tuple[str, ...]:
    """Bind one status checkpoint to all and only the eight sealed pointers."""

    expected = tuple(spec.path for spec in contract.dvc_pointers)
    explicit = _explicit_dvc_status_targets(configured_targets)
    if (
        contract.partial_clone_global_status_authorized
        or len(expected) != 8
        or explicit != expected
    ):
        raise _error(f"{context} DVC status scope is not exact ordered eight")
    return explicit


def _read_regular(path: Path, *, context: str, single_link: bool = True) -> bytes:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise _error(f"{context} is absent") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or (single_link and metadata.st_nlink != 1)
    ):
        raise _error(f"{context} must be a regular single-link file")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(descriptor)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
        before.st_nlink,
        stat.S_IMODE(before.st_mode),
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
        after.st_nlink,
        stat.S_IMODE(after.st_mode),
    )
    if before_identity != after_identity:
        raise _error(f"{context} changed while read")
    return b"".join(chunks)


def _open_directory_chain(
    root: Path, relative: Path, *, create_missing: bool
) -> tuple[list[DirectoryHandle], list[int]]:
    if relative.is_absolute() or ".." in relative.parts:
        raise _error("directory capability escaped repository root")
    root_metadata = root.lstat()
    if not stat.S_ISDIR(root_metadata.st_mode) or stat.S_ISLNK(root_metadata.st_mode):
        raise _error("repository root is not a real directory")
    root_fd = os.open(
        root,
        os.O_RDONLY
        | os.O_DIRECTORY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )
    opened = os.fstat(root_fd)
    repeated_root = root.lstat()
    if (
        not stat.S_ISDIR(opened.st_mode)
        or (opened.st_dev, opened.st_ino)
        != (root_metadata.st_dev, root_metadata.st_ino)
        or (repeated_root.st_dev, repeated_root.st_ino)
        != (opened.st_dev, opened.st_ino)
    ):
        os.close(root_fd)
        raise _error("repository root changed while opening directory capability")
    chain = [
        DirectoryHandle(root, root_fd, opened.st_dev, opened.st_ino)
    ]
    created: list[int] = []
    try:
        for component in relative.parts:
            if component in {"", ".", ".."} or "/" in component:
                raise _error("directory capability contains an unsafe component")
            parent = chain[-1]
            flags = (
                os.O_RDONLY
                | os.O_DIRECTORY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0)
            )
            expected_metadata: os.stat_result | None = None
            try:
                expected_metadata = os.stat(
                    component,
                    dir_fd=parent.fd,
                    follow_symlinks=False,
                )
                descriptor = os.open(component, flags, dir_fd=parent.fd)
            except FileNotFoundError:
                if not create_missing:
                    raise _error(f"required directory is absent: {relative}")
                created_handle = _mkdir_owned_at(
                    parent,
                    component,
                    mode=0o700,
                    context=f"directory capability {component}",
                )
                descriptor = created_handle.fd
                created.append(len(chain))
            metadata = os.fstat(descriptor)
            try:
                repeated = os.stat(
                    component,
                    dir_fd=parent.fd,
                    follow_symlinks=False,
                )
            except OSError as exc:
                os.close(descriptor)
                raise _error("directory capability vanished while opening") from exc
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or not stat.S_ISDIR(repeated.st_mode)
                or (metadata.st_dev, metadata.st_ino)
                != (repeated.st_dev, repeated.st_ino)
                or (
                    expected_metadata is not None
                    and (expected_metadata.st_dev, expected_metadata.st_ino)
                    != (metadata.st_dev, metadata.st_ino)
                )
            ):
                os.close(descriptor)
                raise _error("directory capability resolved a non-directory")
            chain.append(
                DirectoryHandle(
                    parent.path / component,
                    descriptor,
                    metadata.st_dev,
                    metadata.st_ino,
                )
            )
        return chain, created
    except BaseException:
        for index in reversed(created):
            current = chain[index]
            parent = chain[index - 1]
            try:
                _remove_owned_empty_directory_at(
                    parent,
                    current.path.name,
                    device=current.device,
                    inode=current.inode,
                    context="failed directory-chain creation",
                )
            except BaseException:
                pass
        for handle in reversed(chain):
            handle.close()
        raise


def _open_anchored_executable(
    root: Path,
    relative: Path,
    *,
    context: str,
) -> AnchoredExecutable:
    """Open a workspace executable once and invoke only that retained inode."""

    normalized = _require_relative(relative.as_posix(), context=context)
    chain, _ = _open_directory_chain(
        root,
        normalized.parent,
        create_missing=False,
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(
            normalized.name,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=chain[-1].fd,
        )
        opened = os.fstat(descriptor)
        named = os.stat(
            normalized.name,
            dir_fd=chain[-1].fd,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or opened.st_nlink != 1
            or named.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) & 0o111 == 0
            or stat.S_IMODE(named.st_mode) & 0o111 == 0
            or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
        ):
            raise _error(f"{context} must be one executable regular inode")
        anchored = AnchoredExecutable(
            root=root,
            chain=chain,
            name=normalized.name,
            fd=descriptor,
            device=opened.st_dev,
            inode=opened.st_ino,
        )
        anchored.revalidate(context=context)
        return anchored
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        for handle in reversed(chain):
            handle.close()
        raise


def _trusted_python_origin_policy_allows(
    *,
    base_path: Path,
    trusted_path: Path,
    trusted_identity: tuple[int, ...],
    process_identity: tuple[int, ...],
    suite_kind: str | None,
    suite_root: str | None,
    injected_target: Path | None,
    injected_canonical: Path | None,
    injected_identity: tuple[int, ...] | None,
) -> bool:
    """Accept only the system path or the exact retained sandbox alias.

    The alias branch is deliberately pure so the public regression suite can
    exercise its complete decision table without creating a privileged mount.
    Filesystem identities are captured separately by the caller.
    """

    if trusted_identity != process_identity:
        return False
    if base_path == SANDBOX_RETAINED_PYTHON_ALIAS:
        return (
            trusted_path == SANDBOX_RETAINED_PYTHON_ALIAS
            and suite_kind == PUBLIC_SUITE_KIND
            and suite_root == "/workspace"
            and injected_target is not None
            and injected_target.is_absolute()
            and ".." not in injected_target.parts
            and injected_target.is_relative_to(TRUSTED_SYSTEM_PYTHON_ROOT)
            and injected_canonical is not None
            and injected_canonical.is_relative_to(TRUSTED_SYSTEM_PYTHON_ROOT)
            and injected_identity == trusted_identity
        )
    return (
        base_path.is_absolute()
        and ".." not in base_path.parts
        and base_path.is_relative_to(TRUSTED_SYSTEM_PYTHON_ROOT)
        and trusted_path.is_relative_to(TRUSTED_SYSTEM_PYTHON_ROOT)
    )


def _trusted_python_origin_is_safe(
    *,
    base_path: Path,
    trusted_path: Path,
    trusted: os.stat_result,
) -> bool:
    """Capture and validate the current interpreter's fail-closed provenance."""

    try:
        process = PROC_SELF_EXE_PATH.stat()
    except OSError:
        return False
    if (
        not stat.S_ISREG(process.st_mode)
        or stat.S_IMODE(process.st_mode) != 0o755
    ):
        return False

    injected_target: Path | None = None
    injected_canonical: Path | None = None
    injected_identity: tuple[int, ...] | None = None
    if trusted_path == SANDBOX_RETAINED_PYTHON_ALIAS:
        raw_target = os.environ.get(PLUGIN_RETAINED_PYTHON_ENV, "")
        try:
            injected_target = Path(raw_target)
            if (
                not injected_target.is_absolute()
                or ".." in injected_target.parts
                or not injected_target.is_relative_to(TRUSTED_SYSTEM_PYTHON_ROOT)
            ):
                return False
            injected_canonical = injected_target.resolve(strict=True)
            injected = injected_canonical.stat()
        except (OSError, RuntimeError):
            return False
        if (
            not injected_canonical.is_relative_to(TRUSTED_SYSTEM_PYTHON_ROOT)
            or not stat.S_ISREG(injected.st_mode)
            or stat.S_IMODE(injected.st_mode) != 0o755
        ):
            return False
        injected_identity = _stat_identity(injected)

    return _trusted_python_origin_policy_allows(
        base_path=base_path,
        trusted_path=trusted_path,
        trusted_identity=_stat_identity(trusted),
        process_identity=_stat_identity(process),
        suite_kind=os.environ.get(PLUGIN_MODE_ENV),
        suite_root=os.environ.get(PLUGIN_ROOT_ENV),
        injected_target=injected_target,
        injected_canonical=injected_canonical,
        injected_identity=injected_identity,
    )


def _running_from_retained_sandbox_python() -> bool:
    """Prove this process is the exact sealed ``/cert-python`` bind mount."""

    base_path = Path(cast(str, getattr(sys, "_base_executable", sys.executable)))
    if base_path != SANDBOX_RETAINED_PYTHON_ALIAS:
        return False
    try:
        trusted_path = base_path.resolve(strict=True)
        trusted = trusted_path.stat()
    except (OSError, RuntimeError):
        return False
    return _trusted_python_origin_is_safe(
        base_path=base_path,
        trusted_path=trusted_path,
        trusted=trusted,
    )


def _open_anchored_python_interpreter(
    root: Path,
    relative: Path,
    *,
    context: str,
) -> AnchoredPythonInterpreter:
    """Retain a venv launcher and execute only its trusted system target FD."""

    normalized = _require_relative(relative.as_posix(), context=context)
    if normalized.name != "python" or normalized.parent.name != "bin":
        raise _error(f"{context} must be an exact venv Python launcher")
    chain, _ = _open_directory_chain(root, normalized.parent, create_missing=False)
    descriptor: int | None = None
    try:
        link_before = os.stat(
            normalized.name,
            dir_fd=chain[-1].fd,
            follow_symlinks=False,
        )
        target_before = os.readlink(normalized.name, dir_fd=chain[-1].fd)
        followed_before = os.stat(
            normalized.name,
            dir_fd=chain[-1].fd,
            follow_symlinks=True,
        )
        descriptor = os.open(
            normalized.name,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0),
            dir_fd=chain[-1].fd,
        )
        opened = os.fstat(descriptor)
        link_after = os.stat(
            normalized.name,
            dir_fd=chain[-1].fd,
            follow_symlinks=False,
        )
        target_after = os.readlink(normalized.name, dir_fd=chain[-1].fd)
        followed_after = os.stat(
            normalized.name,
            dir_fd=chain[-1].fd,
            follow_symlinks=True,
        )
        base_path = Path(cast(str, getattr(sys, "_base_executable", sys.executable)))
        trusted_path = base_path.resolve(strict=True)
        trusted = trusted_path.stat()
        if (
            not _trusted_python_origin_is_safe(
                base_path=base_path,
                trusted_path=trusted_path,
                trusted=trusted,
            )
            or not stat.S_ISLNK(link_before.st_mode)
            or link_before.st_nlink != 1
            or _stat_identity(link_before) != _stat_identity(link_after)
            or target_before != target_after
            or not stat.S_ISREG(followed_before.st_mode)
            or not stat.S_ISREG(followed_after.st_mode)
            or not stat.S_ISREG(opened.st_mode)
            or stat.S_IMODE(opened.st_mode) != 0o755
            or _stat_identity(followed_before) != _stat_identity(followed_after)
            or _stat_identity(opened) != _stat_identity(followed_before)
            or (opened.st_dev, opened.st_ino) != (trusted.st_dev, trusted.st_ino)
        ):
            raise _error(f"{context} launcher/interpreter binding is unsafe")
        anchored = AnchoredPythonInterpreter(
            root=root,
            chain=chain,
            name=normalized.name,
            target=target_before,
            fd=descriptor,
            link_identity=_stat_identity(link_before),
            target_identity=_stat_identity(opened),
        )
        anchored.revalidate(context=context)
        return anchored
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        for handle in reversed(chain):
            handle.close()
        raise


def _open_python_script_runtime(
    root: Path,
    script_relative: Path,
    *,
    interpreter_relative: Path = Path(".venv/bin/python"),
    context: str,
) -> AnchoredPythonScriptRuntime:
    script: AnchoredExecutable | None = None
    interpreter: AnchoredPythonInterpreter | None = None
    try:
        script = _open_anchored_executable(root, script_relative, context=context)
        interpreter = _open_anchored_python_interpreter(
            root,
            interpreter_relative,
            context=f"{context} Python",
        )
        runtime = AnchoredPythonScriptRuntime(script=script, interpreter=interpreter)
        runtime.revalidate(context=context)
        return runtime
    except BaseException:
        if script is not None:
            script.close()
        if interpreter is not None:
            interpreter.close()
        raise


def _open_retained_regular_file(
    parent: DirectoryHandle,
    name: str,
    *,
    allowed_modes: frozenset[int],
    context: str,
) -> RetainedRegularFile:
    if not name or "/" in name or name in {".", ".."}:
        raise _error(f"{context} retained filename is unsafe")
    descriptor: int | None = None
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent.fd,
        )
        opened = _revalidate_open_file_name(
            parent,
            name,
            descriptor,
            expected_modes=allowed_modes,
            context=context,
        )
        retained = RetainedRegularFile(
            parent=parent,
            name=name,
            fd=descriptor,
            identity=_stat_identity(opened),
            allowed_modes=allowed_modes,
        )
        retained.revalidate(context=context)
        return retained
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        raise


def _rebind_directory_chain(
    root: Path, chain: Sequence[DirectoryHandle], *, context: str
) -> None:
    """Prove that an open directory chain is still bound at its public names."""

    if not chain:
        raise _error(f"{context} directory chain is empty")
    for parent, current in zip(chain, chain[1:], strict=False):
        try:
            metadata = os.stat(
                current.path.name,
                dir_fd=parent.fd,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise _error(f"{context} directory name vanished") from exc
        if (
            metadata.st_dev,
            metadata.st_ino,
            stat.S_ISDIR(metadata.st_mode),
        ) != (current.device, current.inode, True):
            raise _error(f"{context} directory identity drifted")
    try:
        relative = chain[-1].path.relative_to(root)
    except ValueError as exc:
        raise _error(f"{context} directory escaped repository root") from exc
    fresh, _ = _open_directory_chain(root, relative, create_missing=False)
    try:
        expected = [(item.device, item.inode) for item in chain]
        observed = [(item.device, item.inode) for item in fresh]
        if observed != expected:
            raise _error(f"{context} ancestor rebind drifted")
    finally:
        for handle in reversed(fresh):
            handle.close()


def _revalidate_open_file_name(
    parent: DirectoryHandle,
    name: str,
    descriptor: int,
    *,
    expected_modes: frozenset[int],
    context: str,
) -> os.stat_result:
    """Bind an open regular file back to its name under a held parent FD."""

    opened = os.fstat(descriptor)
    try:
        named = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
    except OSError as exc:
        raise _error(f"{context} name vanished") from exc
    if (
        not stat.S_ISREG(opened.st_mode)
        or not stat.S_ISREG(named.st_mode)
        or opened.st_nlink != 1
        or named.st_nlink != 1
        or stat.S_IMODE(opened.st_mode) not in expected_modes
        or stat.S_IMODE(named.st_mode) not in expected_modes
        or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
    ):
        raise _error(f"{context} file identity/mode/link drifted")
    return opened


def _inventory_kind(metadata: os.stat_result) -> str:
    if stat.S_ISDIR(metadata.st_mode):
        return "directory"
    if stat.S_ISREG(metadata.st_mode):
        return "regular"
    if stat.S_ISLNK(metadata.st_mode):
        return "symlink"
    raise _error("owned work tree contains an unsupported inode type")


def _directory_binding(handle: DirectoryHandle) -> tuple[Any, ...]:
    metadata = os.fstat(handle.fd)
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        metadata.st_nlink,
        stat.S_IMODE(metadata.st_mode),
        tuple(sorted(os.listdir(handle.fd))),
    )


def _require_exact_clone_work_transition(
    before: tuple[Any, ...], after: tuple[Any, ...]
) -> None:
    """Accept only the directory-link transition made by one new clone.

    Creating ``clone/`` adds one child-directory link to the retained work
    directory. Its timestamps are expected to change and are intentionally
    not used as identity, but device, inode, mode, link-count delta, and the
    complete top-level name inventory are all exact.
    """

    if len(before) != 7 or len(after) != 7:
        raise _error("owned work namespace clone transition drifted")
    previous_entries = before[-1]
    if not isinstance(previous_entries, tuple) or "clone" in previous_entries:
        raise _error("owned work namespace clone transition drifted")
    expected_entries = tuple(sorted((*previous_entries, "clone")))
    if (
        after[:2] != before[:2]
        or after[4] != before[4] + 1
        or after[5] != before[5]
        or after[-1] != expected_entries
    ):
        raise _error("owned work namespace clone transition drifted")


def _open_repository_root_lease(root: Path) -> RepositoryRootLease:
    """Retain the canonical repository, parent, and grandparent as dirfds."""

    canonical = root.resolve(strict=True)
    parent_path = canonical.parent
    grandparent_path = parent_path.parent
    if canonical == parent_path or parent_path == grandparent_path:
        raise _error("repository root must be named below a retained grandparent")

    handles: list[DirectoryHandle] = []
    try:
        for path, parent in (
            (grandparent_path, None),
            (parent_path, "grandparent"),
            (canonical, "parent"),
        ):
            if parent is None:
                expected = path.lstat()
                descriptor = os.open(
                    path,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_CLOEXEC", 0),
                )
            else:
                owner = handles[-1]
                expected = os.stat(
                    path.name,
                    dir_fd=owner.fd,
                    follow_symlinks=False,
                )
                descriptor = os.open(
                    path.name,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=owner.fd,
                )
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(expected.st_mode)
                or not stat.S_ISDIR(opened.st_mode)
                or (expected.st_dev, expected.st_ino)
                != (opened.st_dev, opened.st_ino)
            ):
                os.close(descriptor)
                raise _error("repository ancestor changed while opening")
            handles.append(
                DirectoryHandle(path, descriptor, opened.st_dev, opened.st_ino)
            )
        lease = RepositoryRootLease(
            canonical=canonical,
            grandparent=handles[0],
            parent=handles[1],
            root=handles[2],
            grandparent_binding=_directory_binding(handles[0]),
            parent_binding=_directory_binding(handles[1]),
        )
        lease.revalidate(context="initial repository root lease")
        return lease
    except BaseException:
        for handle in reversed(handles):
            handle.close()
        raise


def _scan_work_inventory(root: DirectoryHandle) -> dict[str, WorkInventoryEntry]:
    records: dict[str, WorkInventoryEntry] = {}

    def scan(directory: DirectoryHandle, prefix: str) -> None:
        for name in sorted(os.listdir(directory.fd)):
            if not name or "/" in name or name in {".", ".."}:
                raise _error("owned work tree contains an unsafe name")
            metadata = os.stat(name, dir_fd=directory.fd, follow_symlinks=False)
            kind = _inventory_kind(metadata)
            if kind != "directory" and metadata.st_nlink != 1:
                raise _error("owned work tree contains a non-directory hardlink")
            relative = f"{prefix}/{name}" if prefix else name
            records[relative] = WorkInventoryEntry(
                path=relative,
                device=metadata.st_dev,
                inode=metadata.st_ino,
                kind=kind,
                link_count=metadata.st_nlink,
                mode=stat.S_IMODE(metadata.st_mode),
            )
            if kind == "directory":
                descriptor = os.open(
                    name,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=directory.fd,
                )
                opened = os.fstat(descriptor)
                if (opened.st_dev, opened.st_ino) != (
                    metadata.st_dev,
                    metadata.st_ino,
                ):
                    os.close(descriptor)
                    raise _error("owned work directory changed while inventoried")
                child = DirectoryHandle(
                    directory.path / name,
                    descriptor,
                    opened.st_dev,
                    opened.st_ino,
                )
                try:
                    scan(child, relative)
                finally:
                    child.close()

    scan(root, "")
    return records


def _create_clone_mountpoints(clone: DirectoryHandle) -> CloneMountpointLease:
    """Create exact empty ``.venv``/``tmp`` mount targets without adoption."""

    before = _scan_work_inventory(clone)
    if _scan_work_inventory(clone) != before:
        raise _error("clone inventory changed before mountpoint creation")
    created: list[DirectoryHandle] = []
    try:
        for name in SANDBOX_MOUNTPOINT_NAMES:
            created.append(
                _mkdir_owned_at(
                    clone,
                    name,
                    mode=SANDBOX_MOUNTPOINT_MODE,
                    context=f"owned clone sandbox mountpoint {name}",
                )
            )
        after = _scan_work_inventory(clone)
        if _scan_work_inventory(clone) != after:
            raise _error("clone inventory changed while freezing mountpoints")
        if set(after) != {*before, *SANDBOX_MOUNTPOINT_NAMES} or any(
            after[path] != entry for path, entry in before.items()
        ):
            raise _error("clone mountpoint inventory is not exact plus two")
        for name, handle in zip(SANDBOX_MOUNTPOINT_NAMES, created, strict=True):
            entry = after[name]
            if (
                entry.kind != "directory"
                or entry.mode != SANDBOX_MOUNTPOINT_MODE
                or (entry.device, entry.inode) != (handle.device, handle.inode)
            ):
                raise _error("clone mountpoint inventory binding drifted")
        ignored = _git(clone.path, "check-ignore", "--", *SANDBOX_MOUNTPOINT_NAMES)
        if tuple(ignored.splitlines()) != SANDBOX_MOUNTPOINT_NAMES:
            raise _error("clone sandbox mountpoints are not exactly Git-ignored")
        lease = CloneMountpointLease(
            clone=clone,
            handles=cast(
                tuple[DirectoryHandle, DirectoryHandle], tuple(created)
            ),
            inventory_after_creation=after,
        )
        lease.revalidate(context="initial clone mountpoint lease")
        return lease
    except BaseException as primary:
        cleanup_error: BaseException | None = None
        for handle in reversed(created):
            try:
                _remove_owned_empty_directory_at(
                    clone,
                    handle.path.name,
                    device=handle.device,
                    inode=handle.inode,
                    context="failed clone sandbox mountpoint",
                )
            except BaseException as exc:
                cleanup_error = cleanup_error or exc
            finally:
                handle.close()
        if cleanup_error is not None:
            raise _error(
                "clone mountpoint creation failed and rollback failed closed"
            ) from cleanup_error
        raise primary


def _remove_sealed_work_tree(
    root: DirectoryHandle,
    inventory: Mapping[str, WorkInventoryEntry],
    *,
    cleanup_callback: Callable[[str], None] | None,
) -> None:
    """Delete only exact inventoried inodes, bottom-up and dirfd anchored."""

    def direct_entries(prefix: str) -> dict[str, WorkInventoryEntry]:
        result: dict[str, WorkInventoryEntry] = {}
        for path_text, entry in inventory.items():
            parent = PurePosixPath(path_text).parent.as_posix()
            normalized_parent = "" if parent == "." else parent
            if normalized_parent == prefix:
                result[PurePosixPath(path_text).name] = entry
        return result

    def remove(directory: DirectoryHandle, prefix: str) -> None:
        remaining = direct_entries(prefix)
        while remaining:
            if cleanup_callback is not None:
                cleanup_callback(f"before_owned_remove:{prefix or '.'}")
            observed_names = set(os.listdir(directory.fd))
            if observed_names != set(remaining):
                raise _error("owned work tree gained or lost an entry during cleanup")
            name = sorted(remaining, reverse=True)[0]
            entry = remaining[name]
            metadata = os.stat(name, dir_fd=directory.fd, follow_symlinks=False)
            if (
                metadata.st_dev,
                metadata.st_ino,
                _inventory_kind(metadata),
                metadata.st_nlink,
                stat.S_IMODE(metadata.st_mode),
            ) != (
                entry.device,
                entry.inode,
                entry.kind,
                entry.link_count,
                entry.mode,
            ):
                raise _error("owned work inode binding drifted during cleanup")
            if entry.kind == "directory":
                descriptor = os.open(
                    name,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=directory.fd,
                )
                opened = os.fstat(descriptor)
                if (opened.st_dev, opened.st_ino) != (entry.device, entry.inode):
                    os.close(descriptor)
                    raise _error("owned work directory changed before traversal")
                child = DirectoryHandle(
                    directory.path / name,
                    descriptor,
                    opened.st_dev,
                    opened.st_ino,
                )
                try:
                    remove(child, entry.path)
                finally:
                    child.close()
                _remove_owned_empty_directory_at(
                    directory,
                    name,
                    device=entry.device,
                    inode=entry.inode,
                    context=f"owned work directory {entry.path}",
                )
            else:
                _unlink_owned_at(
                    OwnedFileAt(directory, name, entry.device, entry.inode),
                    context=f"owned work file {entry.path}",
                )
            remaining.pop(name)
        if os.listdir(directory.fd):
            raise _error("owned work directory is not empty after exact cleanup")

    remove(root, "")


def _create_owned_file_at(
    parent: DirectoryHandle, name: str, payload: bytes, *, mode: int = 0o600
) -> OwnedFileAt:
    if not name or "/" in name or name in {".", ".."}:
        raise _error("owned file name is unsafe")
    descriptor: int | None = None
    owner: OwnedFileAt | None = None
    try:
        descriptor = os.open(
            name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            mode,
            dir_fd=parent.fd,
        )
        created = os.fstat(descriptor)
        owner = OwnedFileAt(parent, name, created.st_dev, created.st_ino)
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise _error("owned file write made no progress")
            view = view[written:]
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        named = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or metadata.st_nlink != 1
            or named.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != mode
            or stat.S_IMODE(named.st_mode) != mode
            or (metadata.st_dev, metadata.st_ino)
            != (named.st_dev, named.st_ino)
        ):
            raise _error("owned file creation identity/mode drifted")
        os.close(descriptor)
        descriptor = None
        return owner
    except BaseException as primary:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if owner is not None:
            try:
                _unlink_owned_at(owner, context=f"failed owned file {name}")
            except BaseException as cleanup_exc:
                raise _error("owned file creation cleanup failed closed") from cleanup_exc
        raise primary


def _rename_noreplace_at(
    source_parent_fd: int,
    source_name: str,
    target_parent_fd: int,
    target_name: str,
) -> None:
    """Linux renameat2(RENAME_NOREPLACE), used as an ownership handoff."""

    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise _error("renameat2 is required for no-clobber certification cleanup")
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        source_parent_fd,
        os.fsencode(source_name),
        target_parent_fd,
        os.fsencode(target_name),
        1,  # RENAME_NOREPLACE
    )
    if result != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), source_name)


def _mkdir_owned_at(
    parent: DirectoryHandle,
    name: str,
    *,
    mode: int,
    context: str,
) -> DirectoryHandle:
    """Create one directory privately and publish its retained inode by rename."""

    if not name or "/" in name or name in {".", ".."}:
        raise _error(f"{context} has an unsafe name")
    temporary_name: str | None = None
    for _ in range(128):
        candidate = f".owned-dir-{secrets.token_hex(16)}"
        try:
            os.mkdir(candidate, mode=mode, dir_fd=parent.fd)
        except FileExistsError:
            continue
        temporary_name = candidate
        break
    if temporary_name is None:
        raise _error(f"{context} could not allocate a private directory name")

    descriptor: int | None = None
    published_name = temporary_name
    identity: tuple[int, int] | None = None
    try:
        expected = os.stat(
            temporary_name,
            dir_fd=parent.fd,
            follow_symlinks=False,
        )
        descriptor = os.open(
            temporary_name,
            os.O_RDONLY
            | os.O_DIRECTORY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent.fd,
        )
        opened = os.fstat(descriptor)
        identity = (opened.st_dev, opened.st_ino)
        if (
            not stat.S_ISDIR(expected.st_mode)
            or not stat.S_ISDIR(opened.st_mode)
            or identity != (expected.st_dev, expected.st_ino)
        ):
            raise _error(f"{context} private directory changed while opening")
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
        repeated = os.stat(
            temporary_name,
            dir_fd=parent.fd,
            follow_symlinks=False,
        )
        if (
            (repeated.st_dev, repeated.st_ino) != identity
            or not stat.S_ISDIR(repeated.st_mode)
            or stat.S_IMODE(repeated.st_mode) != mode
        ):
            raise _error(f"{context} private directory binding drifted")
        try:
            _rename_noreplace_at(parent.fd, temporary_name, parent.fd, name)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                raise _error(f"{context} already exists") from exc
            raise
        published_name = name
        os.fsync(parent.fd)
        published = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
        retained = os.fstat(descriptor)
        if (
            (published.st_dev, published.st_ino) != identity
            or (retained.st_dev, retained.st_ino) != identity
            or not stat.S_ISDIR(published.st_mode)
            or not stat.S_ISDIR(retained.st_mode)
            or stat.S_IMODE(published.st_mode) != mode
            or stat.S_IMODE(retained.st_mode) != mode
        ):
            raise _error(f"{context} published directory binding drifted")
        try:
            os.stat(temporary_name, dir_fd=parent.fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise _error(f"{context} private directory name reappeared")
        return DirectoryHandle(
            parent.path / name,
            descriptor,
            retained.st_dev,
            retained.st_ino,
        )
    except BaseException as primary:
        cleanup_error: BaseException | None = None
        if identity is not None:
            try:
                _remove_owned_empty_directory_at(
                    parent,
                    published_name,
                    device=identity[0],
                    inode=identity[1],
                    context=f"failed {context}",
                )
            except BaseException as exc:
                cleanup_error = exc
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if cleanup_error is not None:
            raise _error(f"{context} failed and owned cleanup failed closed") from cleanup_error
        raise primary


def _detach_owned_name_at(
    parent: DirectoryHandle,
    name: str,
    *,
    device: int,
    inode: int,
    require_directory: bool,
    context: str,
    owned_fd: int | None = None,
    expected_nondirectory_kind: str | None = None,
) -> str:
    """Capture an owned name twice before deletion can target it.

    The first no-clobber rename removes the public boundary.  A retained FD
    proves that capture, and a second unpredictable no-clobber rename closes
    the detach-to-delete test boundary: a replacement of the first tombstone
    is preserved and rejected rather than adopted.
    """

    if not name or "/" in name or name in {".", ".."}:
        raise _error(f"{context} has an unsafe cleanup name")
    if expected_nondirectory_kind not in {None, "regular_file", "socket"} or (
        require_directory and expected_nondirectory_kind is not None
    ):
        raise _error(f"{context} has an invalid cleanup inode kind")
    flags = getattr(os, "O_PATH", os.O_RDONLY) | getattr(os, "O_NOFOLLOW", 0)
    if require_directory:
        flags = (
            os.O_RDONLY
            | os.O_DIRECTORY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0)
        )
    retained_fd: int | None = None
    first: str | None = None
    second: str | None = None

    def allocate_capture(source: str) -> str:
        for _ in range(128):
            candidate = f".owned-cleanup-{secrets.token_hex(16)}"
            try:
                _rename_noreplace_at(parent.fd, source, parent.fd, candidate)
            except OSError as exc:
                if exc.errno == errno.EEXIST:
                    continue
                if exc.errno == errno.ENOENT:
                    raise _error(f"{context} vanished before owned cleanup") from exc
                raise _error(f"{context} could not be atomically detached") from exc
            os.fsync(parent.fd)
            return candidate
        raise _error(f"{context} could not allocate an exclusive cleanup name")

    def type_matches(metadata: os.stat_result) -> bool:
        if require_directory:
            return stat.S_ISDIR(metadata.st_mode)
        if expected_nondirectory_kind == "regular_file":
            return stat.S_ISREG(metadata.st_mode)
        if expected_nondirectory_kind == "socket":
            try:
                return _postgres_socket_entry_kind(metadata) == "socket"
            except FinalCertificationBuildError:
                return False
        return stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)

    def restore_foreign(captured_name: str) -> None:
        try:
            _rename_noreplace_at(parent.fd, captured_name, parent.fd, name)
            os.fsync(parent.fd)
        except OSError as exc:
            raise _error(
                f"{context} foreign replacement was preserved at {captured_name}"
            ) from exc

    try:
        if owned_fd is not None:
            retained = os.fstat(owned_fd)
            if (retained.st_dev, retained.st_ino) != (device, inode):
                raise _error(f"{context} retained owned FD identity drifted")
        first = allocate_capture(name)
        captured = os.stat(first, dir_fd=parent.fd, follow_symlinks=False)
        if (captured.st_dev, captured.st_ino) != (device, inode) or not type_matches(
            captured
        ):
            restore_foreign(first)
            first = None
            raise _error(f"refusing to remove foreign replacement: {context}")
        retained_fd = os.open(first, flags, dir_fd=parent.fd)
        retained = os.fstat(retained_fd)
        if (retained.st_dev, retained.st_ino) != (device, inode) or not type_matches(
            retained
        ):
            raise _error(f"{context} cleanup capture changed while opening")

        second = allocate_capture(first)
        first = None
        repeated = os.stat(second, dir_fd=parent.fd, follow_symlinks=False)
        anchored = os.fstat(retained_fd)
        if (
            (repeated.st_dev, repeated.st_ino) != (device, inode)
            or (anchored.st_dev, anchored.st_ino) != (device, inode)
            or not type_matches(repeated)
            or not type_matches(anchored)
        ):
            restore_foreign(second)
            second = None
            raise _error(f"refusing to remove cleanup-name replacement: {context}")
        return second
    except BaseException:
        captured_name = second or first
        if captured_name is not None:
            try:
                current = os.stat(
                    captured_name,
                    dir_fd=parent.fd,
                    follow_symlinks=False,
                )
            except OSError:
                current = None
            if current is not None and (current.st_dev, current.st_ino) == (
                device,
                inode,
            ):
                try:
                    _rename_noreplace_at(
                        parent.fd,
                        captured_name,
                        parent.fd,
                        name,
                    )
                    os.fsync(parent.fd)
                except OSError:
                    pass
        raise
    finally:
        if retained_fd is not None:
            os.close(retained_fd)


def _remove_owned_empty_directory_at(
    parent: DirectoryHandle,
    name: str,
    *,
    device: int,
    inode: int,
    context: str,
) -> None:
    tombstone = _detach_owned_name_at(
        parent,
        name,
        device=device,
        inode=inode,
        require_directory=True,
        context=context,
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(
            tombstone,
            os.O_RDONLY
            | os.O_DIRECTORY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent.fd,
        )
        opened = os.fstat(descriptor)
        named = os.stat(tombstone, dir_fd=parent.fd, follow_symlinks=False)
        if (
            (opened.st_dev, opened.st_ino) != (device, inode)
            or (named.st_dev, named.st_ino) != (device, inode)
            or not stat.S_ISDIR(opened.st_mode)
            or os.listdir(descriptor)
        ):
            raise _error(f"{context} cleanup directory binding drifted")
        tombstone = _detach_owned_name_at(
            parent,
            tombstone,
            device=device,
            inode=inode,
            require_directory=True,
            context=f"{context} final cleanup capture",
            owned_fd=descriptor,
        )
        final_named = os.stat(
            tombstone,
            dir_fd=parent.fd,
            follow_symlinks=False,
        )
        if (final_named.st_dev, final_named.st_ino) != (device, inode):
            raise _error(f"{context} final cleanup directory binding drifted")
        os.rmdir(tombstone, dir_fd=parent.fd)
        os.fsync(parent.fd)
        if os.fstat(descriptor).st_nlink != 0:
            raise _error(f"{context} retained directory link count did not decrement")
    except BaseException:
        try:
            _rename_noreplace_at(parent.fd, tombstone, parent.fd, name)
            os.fsync(parent.fd)
        except OSError:
            pass
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _unlink_owned_at(entry: OwnedFileAt, *, context: str) -> None:
    tombstone = _detach_owned_name_at(
        entry.parent,
        entry.name,
        device=entry.device,
        inode=entry.inode,
        require_directory=False,
        context=context,
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(
            tombstone,
            getattr(os, "O_PATH", os.O_RDONLY)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=entry.parent.fd,
        )
        opened = os.fstat(descriptor)
        named = os.stat(tombstone, dir_fd=entry.parent.fd, follow_symlinks=False)
        if (opened.st_dev, opened.st_ino) != (entry.device, entry.inode) or (
            named.st_dev,
            named.st_ino,
        ) != (entry.device, entry.inode):
            raise _error(f"{context} cleanup file binding drifted")
        link_count = opened.st_nlink
        if link_count < 1:
            raise _error(f"{context} cleanup file has no owned link")
        tombstone = _detach_owned_name_at(
            entry.parent,
            tombstone,
            device=entry.device,
            inode=entry.inode,
            require_directory=False,
            context=f"{context} final cleanup capture",
            owned_fd=descriptor,
        )
        final_named = os.stat(
            tombstone,
            dir_fd=entry.parent.fd,
            follow_symlinks=False,
        )
        if (final_named.st_dev, final_named.st_ino) != (
            entry.device,
            entry.inode,
        ):
            raise _error(f"{context} final cleanup file binding drifted")
        os.unlink(tombstone, dir_fd=entry.parent.fd)
        os.fsync(entry.parent.fd)
        if os.fstat(descriptor).st_nlink != link_count - 1:
            raise _error(f"{context} retained inode link count did not decrement")
    except BaseException:
        try:
            _rename_noreplace_at(
                entry.parent.fd,
                tombstone,
                entry.parent.fd,
                entry.name,
            )
            os.fsync(entry.parent.fd)
        except OSError:
            pass
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _acquire_run_guard(root: Path, contract: FinalCertificationContract) -> RunGuard:
    guard_relative = _require_relative(
        contract.legacy_guard_path_must_be_absent,
        context="legacy guard path",
    )
    if guard_relative != GUARD_PATH:
        raise _error("legacy final-certification guard path drifted")
    git_chain: list[DirectoryHandle] = []
    lock_held = False
    try:
        git_chain, _ = _open_directory_chain(
            root,
            Path(".git"),
            create_missing=False,
        )
        fcntl.flock(git_chain[-1].fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_held = True
    except BlockingIOError as exc:
        for handle in reversed(git_chain):
            handle.close()
        raise _error("final certification cooperative lock is already held") from exc
    except BaseException as exc:
        for handle in reversed(git_chain):
            handle.close()
        if isinstance(exc, FinalCertificationBuildError):
            raise
        raise _error("final certification cooperative lock acquisition failed") from exc

    chain: list[DirectoryHandle] = []
    created: list[int] = []
    try:
        chain, created = _open_directory_chain(
            root,
            guard_relative.parent,
            create_missing=True,
        )
        try:
            os.stat(
                guard_relative.name,
                dir_fd=chain[-1].fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            raise _error("legacy final-certification guard path must be absent")
        _rebind_directory_chain(
            root,
            chain,
            context="final-certification work namespace",
        )
    except BaseException as exc:
        cleanup_error: BaseException | None = None
        for index in reversed(created):
            current = chain[index]
            parent = chain[index - 1]
            try:
                _remove_owned_empty_directory_at(
                    parent,
                    current.path.name,
                    device=current.device,
                    inode=current.inode,
                    context="failed lease-namespace acquisition directory",
                )
            except BaseException as cleanup_exc:
                cleanup_error = cleanup_error or cleanup_exc
        for handle in reversed(chain):
            handle.close()
        if lock_held:
            try:
                fcntl.flock(git_chain[-1].fd, fcntl.LOCK_UN)
            except OSError as cleanup_exc:
                cleanup_error = cleanup_error or cleanup_exc
        for handle in reversed(git_chain):
            handle.close()
        if cleanup_error is not None:
            raise _error("cooperative lock acquisition cleanup failed closed") from cleanup_error
        if isinstance(exc, FinalCertificationBuildError):
            raise
        raise _error("final certification work namespace acquisition failed") from exc
    return RunGuard(
        chain=chain,
        created_chain_indexes=created,
        git_chain=git_chain,
        legacy_guard_name=guard_relative.name,
    )


def _restored_payload_identity(
    path: Path, *, expected_size: int, context: str
) -> tuple[int, int, int, int, int, int, int]:
    """Return metadata without ever opening a restored/cache payload.

    The sealed pointer plus successful directed DVC pull/status are the
    content-authentication evidence.  Python deliberately limits itself to
    ``lstat`` so it cannot claim an independently recomputed payload digest.
    """

    try:
        metadata = path.lstat()
    except OSError as exc:
        raise _error(f"{context} is absent") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_size != expected_size
    ):
        raise _error(f"{context} regular-file identity or declared size drifted")
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        metadata.st_nlink,
        stat.S_IMODE(metadata.st_mode),
    )


def _relative_repo_path(path: str | os.PathLike[str], root: Path) -> str | None:
    try:
        raw = os.fspath(path)
    except TypeError:
        return None
    if not isinstance(raw, str):
        return None
    candidate = Path(raw) if Path(raw).is_absolute() else Path.cwd() / raw
    resolved_root = root.resolve(strict=True)
    try:
        lexical = Path(os.path.abspath(os.fspath(candidate))).relative_to(resolved_root)
        return lexical.as_posix()
    except ValueError:
        pass
    try:
        return candidate.resolve(strict=False).relative_to(resolved_root).as_posix()
    except (OSError, ValueError):
        return None


def _forbidden_relative_paths(contract: FinalCertificationContract) -> tuple[str, ...]:
    return tuple(
        [
            *(str(value).rstrip("/") for value in contract.forbidden_read_prefixes),
            *(str(value) for value in contract.forbidden_read_paths),
            *(spec.output_path for spec in contract.dvc_pointers),
        ]
    )


def _is_forbidden_path(
    path: str | os.PathLike[str], root: Path, contract: FinalCertificationContract
) -> bool:
    relative = _relative_repo_path(path, root)
    if relative is None:
        return False
    return any(
        relative == prefix or relative.startswith(prefix.rstrip("/") + "/")
        for prefix in _forbidden_relative_paths(contract)
    )


def _guard_process(
    argv: Any,
    cwd: Any = None,
    *,
    retained_python_identity: tuple[int, int] | None = None,
) -> None:
    """Reject subprocesses that could escape the sealed verification surface."""

    tokens = (
        [os.fsdecode(os.fspath(item)) for item in argv]
        if isinstance(argv, (list, tuple))
        and all(isinstance(item, (str, bytes, os.PathLike)) for item in argv)
        else []
    )
    if not tokens:
        raise _error("certification forbids opaque subprocess commands")
    if Path(tokens[0]).name == "cert-python":
        _require_retained_cert_python_identity(
            retained_python_identity,
            executable_path=tokens[0],
        )
    executable = Path(tokens[0]).name.lower()
    if executable in {"sh", "bash", "dash", "zsh", "fish", "cmd", "powershell"}:
        raise _error("certification forbids shell command wrappers")

    # ``env -i ... python`` is used by existing isolation regressions.  Treat
    # it as a transparent launcher so it cannot be used to hide DVC/network or
    # shell commands from the process audit.
    if executable == "env":
        index = 1
        while index < len(tokens) and (
            tokens[index].startswith("-")
            or (
                "=" in tokens[index]
                and not tokens[index].startswith("=")
            )
        ):
            index += 1
        if index >= len(tokens):
            raise _error("certification forbids an opaque env launcher")
        _guard_process(
            tokens[index:],
            cwd,
            retained_python_identity=retained_python_identity,
        )
        return

    if executable in {"dvc", "docker", "podman", "curl", "wget", "ssh", "scp"}:
        raise _error("certification test sandbox attempted external or DVC execution")

    lowered = " ".join(tokens).lower()
    if executable != "git":
        if any(token in lowered for token in FORBIDDEN_COMMAND_TOKENS):
            raise _error("certification attempted a prohibited scientific/context process")
        return

    arguments = tokens[1:]
    if any(
        token in {"--git-dir", "--work-tree"}
        or token.startswith("--git-dir=")
        or token.startswith("--work-tree=")
        for token in arguments
    ):
        raise _error("certification forbids Git directory/worktree redirection")
    cwd_text = (
        os.fspath(cwd)
        if isinstance(cwd, (str, os.PathLike))
        else os.getcwd()
    )
    if not isinstance(cwd_text, str):
        raise _error("certification Git cwd is malformed")
    effective_cwd = Path(cwd_text)
    if not effective_cwd.is_absolute():
        effective_cwd = Path(os.getcwd()) / effective_cwd
    index = 0
    while index < len(arguments):
        token = arguments[index]
        if token == "-C":
            if index + 1 >= len(arguments):
                raise _error("certification Git -C is malformed")
            destination = Path(arguments[index + 1])
            effective_cwd = (
                destination
                if destination.is_absolute()
                else effective_cwd / destination
            )
            index += 2
            continue
        if token == "-c":
            if index + 1 >= len(arguments):
                raise _error("certification Git -c is malformed")
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        break
    if index >= len(arguments):
        raise _error("certification test sandbox attempted malformed Git")
    subcommand = arguments[index]
    read_only = {
        "status",
        "rev-parse",
        "show",
        "diff",
        "ls-files",
        "ls-tree",
        "cat-file",
        "check-ignore",
        "show-ref",
        "for-each-ref",
        "merge-base",
        "rev-list",
        "log",
    }
    fixture_only = {
        "init",
        "add",
        "commit",
        "config",
        "branch",
        "checkout",
        "switch",
        "restore",
        "reset",
        "merge",
        "remote",
        "push",
        "symbolic-ref",
        "update-ref",
        "tag",
        "rm",
        "mv",
        "ls-remote",
    }
    normalized_cwd = os.path.normpath(os.fspath(effective_cwd))
    owned_fixture = (
        normalized_cwd == "/tmp"
        or normalized_cwd.startswith("/tmp/")
        or normalized_cwd == "/workspace/tmp"
        or normalized_cwd.startswith("/workspace/tmp/")
    )
    if subcommand not in read_only and not (
        subcommand in fixture_only and owned_fixture
    ):
        raise _error("certification test sandbox attempted Git mutation/network")
    # A status exclusion may name a sealed prefix without reading it.  Every
    # content-bearing Git command remains subject to the forbidden-path token
    # filter.
    if subcommand != "status" and any(
        token in lowered for token in FORBIDDEN_COMMAND_TOKENS
    ):
        raise _error("certification attempted a prohibited scientific/context process")


def _capture_injected_retained_python_identity(path_text: str) -> tuple[int, int]:
    """Capture the host-injected trusted /usr interpreter identity."""

    try:
        candidate = Path(path_text)
        canonical = os.stat(candidate, follow_symlinks=False)
    except OSError as exc:
        raise _error("certification trusted Python identity is unavailable") from exc
    if (
        not candidate.is_absolute()
        or not candidate.is_relative_to(Path("/usr"))
        or ".." in candidate.parts
        or not stat.S_ISREG(canonical.st_mode)
    ):
        raise _error("certification trusted Python identity is unsafe")
    return canonical.st_dev, canonical.st_ino


def _require_retained_cert_python_identity(
    trusted_identity: tuple[int, int] | None,
    *,
    executable_path: str,
) -> None:
    """Bind the sandbox alias to the injected host-retained /usr inode."""

    if trusted_identity is None:
        raise _error("certification trusted Python identity was not captured")
    try:
        retained = os.stat(executable_path, follow_symlinks=False)
    except OSError as exc:
        raise _error("certification retained Python identity is unavailable") from exc
    if (
        not stat.S_ISREG(retained.st_mode)
        or (retained.st_dev, retained.st_ino) != trusted_identity
    ):
        raise _error("certification retained Python identity drifted")


def install_certification_access_guard(
    repo_root: Path | None = None,
    *,
    contract: FinalCertificationContract | None = None,
    retained_python_target: str | None = None,
) -> None:
    """Install the process-local audit guard for OpenAPI and E2E verification."""

    global _ACCESS_GUARD_INSTALLED
    if _ACCESS_GUARD_INSTALLED:
        return
    root = (repo_root or Path(os.environ.get(PLUGIN_ROOT_ENV, "."))).resolve(strict=True)
    sealed = contract or load_contract(root=root)
    trusted_python_identity = _capture_injected_retained_python_identity(
        retained_python_target
        or os.environ.get(PLUGIN_RETAINED_PYTHON_ENV, "")
    )

    def audit(event: str, args: tuple[Any, ...]) -> None:
        if event == "open" and args and isinstance(args[0], (str, os.PathLike)):
            if _is_forbidden_path(args[0], root, sealed):
                raise _error("certification attempted a forbidden repository read")
        elif event == "os.system":
            raise _error("certification forbids os.system")
        elif event in {"os.posix_spawn", "os.posix_spawnp"} and len(args) > 1:
            _guard_process(
                args[1], retained_python_identity=trusted_python_identity
            )
        elif event == "subprocess.Popen" and len(args) > 1:
            _guard_process(
                args[1],
                args[2] if len(args) > 2 else None,
                retained_python_identity=trusted_python_identity,
            )
        elif event == "socket.connect" and len(args) > 1:
            address = args[1]
            if isinstance(address, str):
                if not address.startswith(DB_SOCKET_ROOT + "/"):
                    raise _error("certification socket escaped the owned PostgreSQL socket")
            elif isinstance(address, tuple):
                host = str(address[0]) if address else ""
                if host not in {"127.0.0.1", "::1"}:
                    raise _error("certification attempted non-loopback network access")
            else:
                raise _error("certification attempted an unknown socket address")

    sys.addaudithook(audit)
    _ACCESS_GUARD_INSTALLED = True


def pytest_configure(config: Any) -> None:
    """Pytest plugin entrypoint used only by the sealed certification command."""

    del config
    mode = os.environ.get(PLUGIN_MODE_ENV)
    if mode not in {PUBLIC_SUITE_KIND, E2E_SUITE_KIND}:
        raise FinalCertificationBuildError(
            f"pytest plugin requires exact {PLUGIN_MODE_ENV}"
        )
    root = Path(os.environ.get(PLUGIN_ROOT_ENV, "."))
    contract = load_contract(root=root)
    if contract.test_suite.status != "locked":
        raise _error("pytest plugin refuses a pending test suite")
    # The public suite is already enclosed by the retained bubblewrap hard
    # boundary.  Its plugin role is deliberately limited to collection and
    # the sealed skip ledger: a global Python audit hook would alter the
    # behavior of tests that exercise their own process/filesystem guards.
    if mode == E2E_SUITE_KIND:
        install_certification_access_guard(root, contract=contract)


def pytest_collection_modifyitems(config: Any, items: Sequence[Any]) -> None:
    """Enforce the locked collection digest and exact justified skip ledger."""

    del config
    mode = os.environ.get(PLUGIN_MODE_ENV)
    root = Path(os.environ.get(PLUGIN_ROOT_ENV, "."))
    contract = load_contract(root=root)
    suite = contract.test_suite
    observed: list[str] = []
    for item in items:
        nodeid = getattr(item, "nodeid", None)
        if not isinstance(nodeid, str) or not nodeid:
            raise _error("pytest collected a malformed node id")
        observed.append(nodeid)
    if len(observed) != len(set(observed)):
        raise _error("pytest collection contains duplicate node ids")
    if mode == E2E_SUITE_KIND:
        if tuple(observed) != tuple(suite.e2e_nodes):
            raise _error("synthetic E2E collection drifted")
        return
    expected_skips = set(suite.exact_skipped_nodes)
    observed_skips: set[str] = set()
    import pytest

    marker = pytest.mark.skipif(True, reason=suite.exact_skip_reason)
    for item in items:
        if item.nodeid in expected_skips:
            item.add_marker(marker, append=False)
            observed_skips.add(item.nodeid)
    if observed_skips != expected_skips:
        raise _error(
            "public suite skip registry drifted: "
            f"missing={sorted(expected_skips.difference(observed_skips))}"
        )
    if len(observed) != suite.collected_test_count:
        raise _error("public suite collected test count drifted")
    digest = digest_strings(sorted(observed))
    if digest != suite.nodeids_sha256:
        raise _error("public suite node-id digest drifted")


@dataclass(frozen=True)
class JunitCaseRecord:
    """The only semantic testcase record admitted into public evidence."""

    nodeid: str
    classname: str
    name: str
    skipped: bool


def _canonical_public_tests_skip_reason(
    *, nodeid: str, raw_reason: Any, suite: Any
) -> str:
    """Admit only the sealed reason or one exact per-node historical alias."""

    if raw_reason == suite.exact_skip_reason:
        return suite.exact_skip_reason
    policy = expected_public_tests_junit_diagnostic_policy()
    aliases = policy.get("raw_skip_reason_aliases")
    if isinstance(raw_reason, str) and isinstance(aliases, Mapping):
        alias = aliases.get(nodeid)
        if isinstance(alias, str) and raw_reason == alias:
            return suite.exact_skip_reason
    raise _PublicTestsJunitUnavailable("junit_sealed_suite_drift")


def _junit_tree(
    payload: bytes,
) -> tuple[ET.Element, ET.Element, list[ET.Element]]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise _error("JUnit XML is invalid") from exc
    if root.tag != "testsuites":
        raise _error("JUnit root is not exact testsuites")
    root_children = list(root)
    if len(root_children) != 1 or root_children[0].tag != "testsuite":
        raise _error("JUnit must contain exactly one direct testsuite")
    suite_node = root_children[0]
    suite_children = list(suite_node)
    properties = [node for node in suite_children if node.tag == "properties"]
    if len(properties) > 1:
        raise _error("JUnit contains multiple properties containers")
    if any(node.tag not in {"properties", "testcase"} for node in suite_children):
        raise _error("JUnit contains system output, an unknown node, or nesting")
    cases = [node for node in suite_children if node.tag == "testcase"]
    if len(cases) != len(list(root.iter("testcase"))):
        raise _error("JUnit testcase nesting is forbidden")
    return root, suite_node, cases


def _parse_junit(payload: bytes) -> tuple[dict[str, int], list[dict[str, str]]]:
    _, _, cases = _junit_tree(payload)
    failures = 0
    errors = 0
    skipped_nodes: list[dict[str, str]] = []
    for case in cases:
        children = list(case)
        if len(children) > 1 or any(
            child.tag not in {"failure", "error", "skipped"} for child in children
        ):
            raise _error("JUnit testcase outcome grammar is not exact")
        outcome = children[0] if children else None
        if outcome is not None and outcome.tag == "failure":
            failures += 1
        elif outcome is not None and outcome.tag == "error":
            errors += 1
        elif outcome is not None and outcome.tag == "skipped":
            classname = str(case.attrib.get("classname", ""))
            name = str(case.attrib.get("name", ""))
            nodeid = _junit_nodeid(classname, name)
            skipped_nodes.append(
                {
                    "nodeid": nodeid,
                    "reason": str(outcome.attrib.get("message", "")),
                }
            )
    return (
        {
            "tests": len(cases),
            "failures": failures,
            "errors": errors,
            "skipped": len(skipped_nodes),
            "passed": len(cases) - failures - errors - len(skipped_nodes),
        },
        skipped_nodes,
    )


def _junit_nodeid(classname: str, name: str) -> str:
    if not classname or not name:
        raise _error("JUnit testcase identity is empty")
    components = classname.split(".")
    class_index = next(
        (index for index, component in enumerate(components) if component.startswith("Test")),
        len(components),
    )
    module_components = components[:class_index]
    class_components = components[class_index:]
    module = ".".join(module_components)
    if not module:
        raise _error("JUnit testcase module identity is empty")
    path = module.replace(".", "/") + ".py"
    suffix = "::".join((*class_components, name))
    return f"{path}::{suffix}"


def _canonical_junit_identity(nodeid: str, *, name: str) -> tuple[str, str]:
    path_text, separator, scopes = nodeid.partition("::")
    if (
        not separator
        or not path_text.endswith(".py")
        or path_text.startswith("/")
        or not name
    ):
        raise _error("JUnit node-id grammar is malformed")
    path = PurePosixPath(path_text)
    if path.as_posix() != path_text or any(part in {"", ".", ".."} for part in path.parts):
        raise _error("JUnit node-id path is not canonical")
    if scopes == name:
        class_scope = ""
    elif scopes.endswith("::" + name):
        class_scope = scopes[: -(len(name) + 2)]
        class_parts = class_scope.split("::")
        if (
            not class_scope
            or not class_parts[0].startswith("Test")
            or any(not part or "." in part or "/" in part for part in class_parts)
        ):
            raise _error("JUnit node-id class scope is not canonical")
    else:
        raise _error("JUnit node-id/name binding is ambiguous")
    module = path_text[:-3].replace("/", ".")
    classname = module + ("." + class_scope.replace("::", ".") if class_scope else "")
    return classname, name


def _extract_junit_case_records(
    payload: bytes,
    *,
    suite: Any,
    allow_properties: bool,
) -> list[JunitCaseRecord]:
    _, suite_node, cases = _junit_tree(payload)
    if not allow_properties and any(node.tag == "properties" for node in suite_node):
        raise _error("raw JUnit must not contain a properties container")
    records: list[JunitCaseRecord] = []
    for case in cases:
        if set(case.attrib).difference(
            {"classname", "name", "time", "timestamp", "hostname"}
        ):
            raise _error("JUnit testcase contains an unknown attribute")
        classname = case.attrib.get("classname")
        name = case.attrib.get("name")
        if not isinstance(classname, str) or not isinstance(name, str):
            raise _error("JUnit testcase identity is malformed")
        nodeid = _junit_nodeid(classname, name)
        expected_classname, expected_name = _canonical_junit_identity(
            nodeid, name=name
        )
        if (classname, name) != (expected_classname, expected_name):
            raise _error("JUnit testcase classname/name is not the canonical node-id form")
        children = list(case)
        if not children:
            skipped = False
        elif len(children) == 1 and children[0].tag == "skipped":
            skipped_node = children[0]
            if (
                set(skipped_node.attrib) != {"type", "message"}
                or skipped_node.attrib.get("type") != JUNIT_SKIP_TYPE
                or list(skipped_node)
            ):
                raise _error("JUnit skipped outcome type/reason is not exact")
            try:
                _canonical_public_tests_skip_reason(
                    nodeid=nodeid,
                    raw_reason=skipped_node.attrib.get("message"),
                    suite=suite,
                )
            except _PublicTestsJunitUnavailable:
                raise _error("JUnit skipped outcome type/reason is not exact") from None
            skipped = True
        else:
            raise _error("JUnit public suite contains failure, error, or unknown outcome")
        records.append(
            JunitCaseRecord(
                nodeid=nodeid,
                classname=classname,
                name=name,
                skipped=skipped,
            )
        )
    _validate_junit_case_records(records, suite=suite)
    return records


def _validate_junit_case_records(
    records: Sequence[JunitCaseRecord], *, suite: Any
) -> None:
    nodeids = [record.nodeid for record in records]
    skipped = [record.nodeid for record in records if record.skipped]
    if (
        len(nodeids) != suite.collected_test_count
        or len(nodeids) != len(set(nodeids))
        or digest_strings(sorted(nodeids)) != suite.nodeids_sha256
        or len(skipped) != suite.allowed_skip_count
        or set(skipped) != set(suite.exact_skipped_nodes)
    ):
        raise _error("JUnit complete node-id/outcome set drifted from the sealed suite")


def _validate_junit_nodeids(payload: bytes, suite: Any) -> list[str]:
    """Reconstruct and bind every passing, failing, error, and skipped node."""

    return [
        record.nodeid
        for record in _extract_junit_case_records(
            payload, suite=suite, allow_properties=True
        )
    ]


def _validate_skip_ledger(
    ledger: Sequence[Mapping[str, str]], suite: Any
) -> None:
    observed = [record.get("nodeid", "") for record in ledger]
    exact_nodes = list(suite.exact_skipped_nodes)
    expected = sorted(exact_nodes)
    if (
        len(observed) != len(set(observed))
        or observed != expected
        or any(
            record.get("reason") != suite.exact_skip_reason for record in ledger
        )
    ):
        raise _error("JUnit exact skip node/reason ledger drifted")


def _junit_closure_properties(
    *, execution_commit: str, suite: Any
) -> tuple[tuple[str, str], ...]:
    return (
        ("closure.execution_commit", execution_commit),
        ("closure.forbidden_read_guard", "enabled_no_access"),
        ("closure.network_policy", "unix_postgresql_only"),
        ("closure.nodeids_sha256", suite.nodeids_sha256),
        ("closure.suite_kind", PUBLIC_SUITE_KIND),
    )


def _canonical_junit_xml(
    records: Sequence[JunitCaseRecord],
    *,
    execution_commit: str,
    suite: Any,
    forbidden_absolute: Path | None = None,
) -> bytes:
    commit = _require_commit(execution_commit, context="JUnit execution commit")
    _validate_junit_case_records(records, suite=suite)
    ordered = sorted(records, key=lambda record: record.nodeid)
    counters = {
        "tests": str(len(ordered)),
        "failures": "0",
        "errors": "0",
        "skipped": str(sum(record.skipped for record in ordered)),
    }
    root = ET.Element("testsuites", counters)
    suite_node = ET.SubElement(
        root,
        "testsuite",
        {"name": PUBLIC_SUITE_KIND, **counters},
    )
    properties = ET.SubElement(suite_node, "properties")
    for name, value in _junit_closure_properties(
        execution_commit=commit, suite=suite
    ):
        ET.SubElement(properties, "property", {"name": name, "value": value})
    for record in ordered:
        case = ET.SubElement(
            suite_node,
            "testcase",
            {"classname": record.classname, "name": record.name},
        )
        if record.skipped:
            ET.SubElement(
                case,
                "skipped",
                {"type": JUNIT_SKIP_TYPE, "message": suite.exact_skip_reason},
            )
    rendered = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    rendered += b"" if rendered.endswith(b"\n") else b"\n"
    _assert_serialization_safe(rendered, forbidden_absolute=forbidden_absolute)
    return rendered


def normalize_junit_xml(
    payload: bytes,
    *,
    execution_commit: str,
    suite: Any,
    clone_root: Path | None = None,
) -> bytes:
    """Build the sole canonical public JUnit grammar from semantic records."""

    records = _extract_junit_case_records(
        payload, suite=suite, allow_properties=False
    )
    return _canonical_junit_xml(
        records,
        execution_commit=execution_commit,
        suite=suite,
        forbidden_absolute=clone_root,
    )


def _unavailable_public_tests_failure(
    *, returncode: int, reason: str
) -> PublicTestsFailureEvidence:
    empty_digest = digest_strings(())
    return PublicTestsFailureEvidence(
        status="failure_identity_unavailable",
        returncode=returncode,
        totals={},
        failed_nodeids=(),
        failed_nodeids_sha256=empty_digest,
        error_nodeids=(),
        error_nodeids_sha256=empty_digest,
        collected_test_count=None,
        collected_nodeids_sha256=None,
        unavailable_reason=reason,
    )


def _require_public_junit_directory_binding(
    sandbox_tmp: Path,
    sandbox: DirectoryHandle,
) -> None:
    """Prove the caller's path still names the retained sandbox directory."""

    descriptor = -1
    try:
        named = sandbox_tmp.lstat()
        if not stat.S_ISDIR(named.st_mode) or stat.S_ISLNK(named.st_mode):
            raise _PublicTestsJunitUnavailable("junit_unsafe_identity")
        descriptor = os.open(
            sandbox_tmp,
            os.O_RDONLY
            | os.O_DIRECTORY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
        opened = os.fstat(descriptor)
        retained = os.fstat(sandbox.fd)
        identities = {
            (named.st_dev, named.st_ino),
            (opened.st_dev, opened.st_ino),
            (retained.st_dev, retained.st_ino),
        }
        if len(identities) != 1:
            raise _PublicTestsJunitUnavailable("junit_unsafe_identity")
    except _PublicTestsJunitUnavailable:
        raise
    except OSError:
        raise _PublicTestsJunitUnavailable("junit_unsafe_identity") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _read_public_tests_junit_fd_safe(
    *,
    sandbox_tmp: Path,
    sandbox: DirectoryHandle,
    source_filename: str,
    max_junit_bytes: int,
) -> bytes:
    """Read raw pytest JUnit through a retained directory FD and hard bound."""

    if (
        not source_filename
        or PurePosixPath(source_filename).name != source_filename
        or "/" in source_filename
        or type(max_junit_bytes) is not int
        or max_junit_bytes <= 0
    ):
        raise _PublicTestsJunitUnavailable("junit_unsafe_identity")
    _require_public_junit_directory_binding(sandbox_tmp, sandbox)
    descriptor = -1
    try:
        descriptor = os.open(
            source_filename,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=sandbox.fd,
        )
    except FileNotFoundError:
        raise _PublicTestsJunitUnavailable("junit_absent") from None
    except OSError:
        raise _PublicTestsJunitUnavailable("junit_unsafe_identity") from None
    try:
        before = os.fstat(descriptor)
        try:
            named_before = os.stat(
                source_filename,
                dir_fd=sandbox.fd,
                follow_symlinks=False,
            )
        except OSError:
            raise _PublicTestsJunitUnavailable("junit_unsafe_identity") from None
        if (
            not stat.S_ISREG(before.st_mode)
            or not stat.S_ISREG(named_before.st_mode)
            or before.st_nlink != 1
            or named_before.st_nlink != 1
            or (before.st_dev, before.st_ino)
            != (named_before.st_dev, named_before.st_ino)
        ):
            raise _PublicTestsJunitUnavailable("junit_unsafe_identity")
        if before.st_size > max_junit_bytes:
            raise _PublicTestsJunitUnavailable("junit_oversized")
        chunks: list[bytes] = []
        remaining = max_junit_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) > max_junit_bytes:
            raise _PublicTestsJunitUnavailable("junit_oversized")
        after = os.fstat(descriptor)
        try:
            named_after = os.stat(
                source_filename,
                dir_fd=sandbox.fd,
                follow_symlinks=False,
            )
        except OSError:
            raise _PublicTestsJunitUnavailable("junit_unsafe_identity") from None
        identity_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        before_identity = tuple(getattr(before, field) for field in identity_fields)
        after_identity = tuple(getattr(after, field) for field in identity_fields)
        named_after_identity = tuple(
            getattr(named_after, field) for field in identity_fields
        )
        if (
            before_identity != after_identity
            or after_identity != named_after_identity
            or (named_before.st_dev, named_before.st_ino)
            != (named_after.st_dev, named_after.st_ino)
        ):
            raise _PublicTestsJunitUnavailable("junit_unsafe_identity")
        return payload
    finally:
        os.close(descriptor)


def _strict_public_tests_failure_projection(
    payload: bytes,
    *,
    suite: Any,
    returncode: int,
) -> PublicTestsFailureEvidence:
    """Parse only sealed identities/totals; discard all raw failure content."""

    try:
        decoded = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise _PublicTestsJunitUnavailable("junit_malformed_or_hostile") from None
    stripped = decoded.lstrip()
    if stripped.startswith("<?xml"):
        declaration_end = stripped.find("?>")
        if declaration_end < 0:
            raise _PublicTestsJunitUnavailable("junit_malformed_or_hostile")
        xml_body = stripped[declaration_end + 2 :]
    else:
        xml_body = stripped
    if "<!" in decoded or "<?" in xml_body:
        raise _PublicTestsJunitUnavailable("junit_malformed_or_hostile")
    try:
        root, suite_node, cases = _junit_tree(payload)
    except FinalCertificationBuildError:
        raise _PublicTestsJunitUnavailable("junit_malformed_or_hostile") from None
    allowed_suite_attributes = {
        "name",
        "tests",
        "failures",
        "errors",
        "skipped",
        "disabled",
        "time",
        "timestamp",
        "hostname",
    }
    if (
        set(root.attrib).difference(allowed_suite_attributes)
        or set(suite_node.attrib).difference(allowed_suite_attributes)
        or any(node.tag == "properties" for node in suite_node)
    ):
        raise _PublicTestsJunitUnavailable("junit_malformed_or_hostile")
    outcomes: list[tuple[JunitCaseRecord, str]] = []
    skip_ledger: list[dict[str, str]] = []
    for case in cases:
        if set(case.attrib).difference(
            {"classname", "name", "time", "timestamp", "hostname"}
        ):
            raise _PublicTestsJunitUnavailable("junit_malformed_or_hostile")
        classname = case.attrib.get("classname")
        name = case.attrib.get("name")
        if not isinstance(classname, str) or not isinstance(name, str):
            raise _PublicTestsJunitUnavailable("junit_malformed_or_hostile")
        try:
            nodeid = _junit_nodeid(classname, name)
            canonical_identity = _canonical_junit_identity(nodeid, name=name)
        except FinalCertificationBuildError:
            raise _PublicTestsJunitUnavailable(
                "junit_malformed_or_hostile"
            ) from None
        if (classname, name) != canonical_identity:
            raise _PublicTestsJunitUnavailable("junit_malformed_or_hostile")
        children = list(case)
        if not children:
            outcome = "passed"
            skipped = False
        elif len(children) == 1 and children[0].tag == "skipped":
            child = children[0]
            if (
                set(child.attrib) != {"type", "message"}
                or child.attrib.get("type") != JUNIT_SKIP_TYPE
                or list(child)
            ):
                raise _PublicTestsJunitUnavailable(
                    "junit_malformed_or_hostile"
                )
            _canonical_public_tests_skip_reason(
                nodeid=nodeid,
                raw_reason=child.attrib.get("message"),
                suite=suite,
            )
            outcome = "skipped"
            skipped = True
            skip_ledger.append(
                {"nodeid": nodeid, "reason": suite.exact_skip_reason}
            )
        elif len(children) == 1 and children[0].tag in {"failure", "error"}:
            child = children[0]
            if set(child.attrib).difference({"message", "type"}) or list(child):
                raise _PublicTestsJunitUnavailable(
                    "junit_malformed_or_hostile"
                )
            outcome = child.tag
            skipped = False
        else:
            raise _PublicTestsJunitUnavailable("junit_malformed_or_hostile")
        outcomes.append(
            (
                JunitCaseRecord(
                    nodeid=nodeid,
                    classname=classname,
                    name=name,
                    skipped=skipped,
                ),
                outcome,
            )
        )
    records = [record for record, _ in outcomes]
    outcomes_by_nodeid: dict[str, list[str]] = {}
    for record, outcome in outcomes:
        outcomes_by_nodeid.setdefault(record.nodeid, []).append(outcome)
    for node_outcomes in outcomes_by_nodeid.values():
        if len(node_outcomes) == 1:
            continue
        if len(node_outcomes) != 2 or set(node_outcomes) != {"failure", "error"}:
            raise _PublicTestsJunitUnavailable("junit_sealed_suite_drift")
    nodeids = sorted(outcomes_by_nodeid)
    if (
        len(nodeids) != suite.collected_test_count
        or digest_strings(nodeids) != suite.nodeids_sha256
        or len(skip_ledger) != suite.allowed_skip_count
    ):
        raise _PublicTestsJunitUnavailable("junit_sealed_suite_drift")
    try:
        _validate_skip_ledger(sorted(skip_ledger, key=lambda item: item["nodeid"]), suite)
    except FinalCertificationBuildError:
        raise _PublicTestsJunitUnavailable("junit_sealed_suite_drift") from None
    failed_nodeids = tuple(
        sorted(
            nodeid
            for nodeid, node_outcomes in outcomes_by_nodeid.items()
            if "failure" in node_outcomes
        )
    )
    error_nodeids = tuple(
        sorted(
            nodeid
            for nodeid, node_outcomes in outcomes_by_nodeid.items()
            if "error" in node_outcomes
        )
    )
    skipped_count = len(skip_ledger)
    failed_or_error_count = len(set(failed_nodeids).union(error_nodeids))
    totals = {
        "tests": len(nodeids),
        "passed": len(nodeids) - failed_or_error_count - skipped_count,
        "failures": len(failed_nodeids),
        "errors": len(error_nodeids),
        "skipped": skipped_count,
    }
    if not failed_nodeids and not error_nodeids:
        raise _PublicTestsJunitUnavailable("junit_malformed_or_hostile")
    for node in (root, suite_node):
        for key in ("failures", "errors", "skipped"):
            declared = node.attrib.get(key)
            if declared is not None and declared != str(totals[key]):
                raise _PublicTestsJunitUnavailable("junit_malformed_or_hostile")
        declared_tests = node.attrib.get("tests")
        if declared_tests is not None:
            if re.fullmatch(r"0|[1-9][0-9]*", declared_tests) is None:
                raise _PublicTestsJunitUnavailable("junit_malformed_or_hostile")
            declared_tests_count = int(declared_tests)
            if not (
                len(nodeids)
                <= declared_tests_count
                <= len(nodeids) + len(error_nodeids)
            ):
                raise _PublicTestsJunitUnavailable("junit_malformed_or_hostile")
    return PublicTestsFailureEvidence(
        status="failure_identity_available",
        returncode=returncode,
        totals=totals,
        failed_nodeids=failed_nodeids,
        failed_nodeids_sha256=digest_strings(failed_nodeids),
        error_nodeids=error_nodeids,
        error_nodeids_sha256=digest_strings(error_nodeids),
        collected_test_count=len(nodeids),
        collected_nodeids_sha256=digest_strings(nodeids),
        unavailable_reason=None,
    )


def _read_documented_operations(root: Path) -> tuple[set[tuple[str, str]], list[dict[str, Any]]]:
    operations: set[tuple[str, str]] = set()
    records: list[dict[str, Any]] = []
    for path_text in DOCUMENTED_API_PATHS:
        payload = _read_regular(root / path_text, context=f"API document {path_text}")
        found = {
            (method.lower(), endpoint.rstrip(".,;:)"))
            for method, endpoint in DOCUMENTED_OPERATION_RE.findall(
                payload.decode("utf-8")
            )
        }
        operations.update(found)
        records.append(
            {
                "path": path_text,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
                "documented_operation_count": len(found),
            }
        )
    if not operations:
        raise _error("API documents declare no operations")
    return operations, records


def validate_openapi_document(
    document: Mapping[str, Any],
    *,
    root: Path,
    contract: FinalCertificationContract,
) -> dict[str, Any]:
    version = document.get("openapi")
    paths = document.get("paths")
    if not isinstance(version, str) or not version.startswith("3."):
        raise _error("OpenAPI version drifted")
    if not isinstance(paths, Mapping):
        raise _error("OpenAPI paths are absent")
    operations: set[tuple[str, str]] = set()
    operation_ids: list[str] = []
    for path_text, path_item in paths.items():
        if not isinstance(path_text, str) or not isinstance(path_item, Mapping):
            raise _error("OpenAPI path item is malformed")
        encoded = set(re.findall(r"\{([^{}]+)\}", path_text))
        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            if not isinstance(operation, Mapping):
                raise _error("OpenAPI operation is malformed")
            operations.add((method, path_text))
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                raise _error("OpenAPI operationId is absent")
            operation_ids.append(operation_id)
            parameters = operation.get("parameters", [])
            if not isinstance(parameters, list):
                raise _error("OpenAPI operation parameters are malformed")
            declared = {
                str(item.get("name"))
                for item in parameters
                if isinstance(item, Mapping) and item.get("in") == "path"
            }
            if declared != encoded:
                raise _error(f"OpenAPI path parameter drifted: {method} {path_text}")
    documented, records = _read_documented_operations(root)
    missing = sorted(documented.difference(operations))
    result = {
        "valid": not missing,
        "openapi_path_count": len(paths),
        "openapi_operation_count": len(operations),
        "documented_operation_count": len(documented),
        "missing_documented_operations": [list(item) for item in missing],
        "operation_ids_unique": len(operation_ids) == len(set(operation_ids)),
        "path_parameters_exact": True,
        "documents": records,
    }
    expected = (
        contract.expected_openapi_path_count,
        contract.expected_openapi_operation_count,
        contract.expected_documented_operation_count,
    )
    observed = (
        result["openapi_path_count"],
        result["openapi_operation_count"],
        result["documented_operation_count"],
    )
    if (
        observed != expected
        or missing
        or result["operation_ids_unique"] is not True
        or result["path_parameters_exact"] is not True
    ):
        raise _error("OpenAPI/documented contract counts or invariants drifted")
    return result


def _emit_openapi(path: Path, execution_commit: str) -> None:
    contract = load_contract(root=Path.cwd())
    install_certification_access_guard(Path.cwd(), contract=contract)
    from src.api.main import create_app

    document = copy.deepcopy(create_app().openapi())
    document["x-closure-phase4-final-certification"] = {
        "execution_commit": _require_commit(
            execution_commit, context="OpenAPI execution commit"
        ),
        "scientific_efficacy_claimed": False,
        "forbidden_paths_opened": False,
    }
    payload = _canonical_json(document)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _assert_serialization_safe(
    payload: bytes, *, forbidden_absolute: Path | None = None
) -> None:
    text = payload.decode("utf-8", errors="strict")
    forbidden = (
        "postgresql+asyncpg://",
        "postgresql://",
        "https://",
        "ssh://",
        "git@",
        "password=",
        "token=",
        "secret=",
    )
    if any(value.lower() in text.lower() for value in forbidden):
        raise _error("certification artifact leaks a URL or credential marker")
    if forbidden_absolute is not None and os.fspath(forbidden_absolute) in text:
        raise _error("certification artifact leaks the temporary clone path")
    # The public bundle may name repository-relative paths, but never an
    # environment-specific workspace or home path.
    if re.search(r"(?:^|[\s`\"'])/(?:home|tmp|var/tmp)/", text):
        raise _error("certification artifact leaks an absolute host path")


def _authority_loader(
    root: Path,
    contract: FinalCertificationContract,
    *,
    require_clean: bool = True,
) -> Mapping[str, Any]:
    """Load P-CERT through the contract's strict independent reconstruction."""

    result = load_effective_authority(
        contract, root=root, verify_remote=True, require_clean=require_clean
    )
    _require_h18_authority_boundary(result, contract=contract)
    commit_binding = _require_effective_authority_commit_binding(
        result,
        contract=contract,
        execution_commit=result.get("p18_cert_commit"),
    )
    dvc_status_policy = _require_effective_authority_dvc_status_policy(
        result,
        contract=contract,
    )
    # The loader returns raw bytes for its internal equality proof.  Public
    # certification records bind their digests and decoded canonical objects,
    # never duplicate raw bytes or operational paths.
    return {
        "status": result["status"],
        "gate": result["gate"],
        **commit_binding,
        # These are historical non-commit sentinels, so the string-only
        # commit projection above intentionally cannot carry them.  Preserve
        # them explicitly to make projection revalidation idempotent.
        "p13_cert_commit": result["p13_cert_commit"],
        "h13_cert_commit": result["h13_cert_commit"],
        "dvc_status_policy": dvc_status_policy,
        "repository": result["repository"],
        "authority": result["authority"],
        "authority_bytes": len(result["authority_bytes"]),
        "authority_sha256": result["authority_sha256"],
        "manifest": result["manifest"],
        "manifest_bytes": len(result["manifest_bytes"]),
        "manifest_sha256": result["manifest_sha256"],
    }


def _require_effective_authority_commit_binding(
    value: Mapping[str, Any],
    *,
    contract: FinalCertificationContract,
    execution_commit: Any,
) -> dict[str, str]:
    """Validate active P18/H18 aliases and the complete historical lineage."""

    if (
        "p13_cert_commit" not in value
        or "h13_cert_commit" not in value
        or value.get("p13_cert_commit") is not None
        or value.get("h13_cert_commit") is not None
    ):
        raise _error("effective authority did not prove unpublished H13/P13 commits")
    fields = (
        "p_cert_commit",
        "h_cert_commit",
        "p18_cert_commit",
        "h18_cert_commit",
        "p17_cert_commit",
        "h17_cert_commit",
        "p16_cert_commit",
        "h16_cert_commit",
        "p15_cert_commit",
        "h15_cert_commit",
        "p14_cert_commit",
        "h14_cert_commit",
        "p12_cert_commit",
        "h12_cert_commit",
        "p11_cert_commit",
        "h11_cert_commit",
        "p10_cert_commit",
        "h10_cert_commit",
        "p9_cert_commit",
        "h9_cert_commit",
        "p8_cert_commit",
        "h8_cert_commit",
        "p7_cert_commit",
        "h7_cert_commit",
        "p6_cert_commit",
        "h6_cert_commit",
        "p5_cert_commit",
        "h5_cert_commit",
        "p4_cert_commit",
        "h4_cert_commit",
        "p3_cert_commit",
        "h3_cert_commit",
        "p2_cert_commit",
        "h2_cert_commit",
        "p1_cert_commit",
        "h1_cert_commit",
    )
    commits: dict[str, str] = {}
    for field in fields:
        candidate = value.get(field)
        if not isinstance(candidate, str) or COMMIT_RE.fullmatch(candidate) is None:
            raise _error("effective authority commit binding is incomplete or malformed")
        commits[field] = candidate
    if (
        not isinstance(execution_commit, str)
        or commits["p_cert_commit"] != execution_commit
        or commits["p18_cert_commit"] != execution_commit
        or commits["h_cert_commit"] != commits["h18_cert_commit"]
        or commits["p18_cert_commit"] == commits["h18_cert_commit"]
        or commits["p17_cert_commit"] != contract.p17_cert_commit
        or commits["h17_cert_commit"] != contract.h17_cert_commit
        or commits["p16_cert_commit"] != contract.p16_cert_commit
        or commits["h16_cert_commit"] != contract.h16_cert_commit
        or commits["p15_cert_commit"] != contract.p15_cert_commit
        or commits["h15_cert_commit"] != contract.h15_cert_commit
        or commits["p14_cert_commit"] != contract.p14_cert_commit
        or commits["h14_cert_commit"] != contract.h14_cert_commit
        or commits["p12_cert_commit"] != contract.p12_cert_commit
        or commits["h12_cert_commit"] != contract.h12_cert_commit
        or commits["p11_cert_commit"] != contract.p11_cert_commit
        or commits["h11_cert_commit"] != contract.h11_cert_commit
        or commits["p10_cert_commit"] != contract.p10_cert_commit
        or commits["h10_cert_commit"] != contract.h10_cert_commit
        or commits["p9_cert_commit"] != contract.p9_cert_commit
        or commits["h9_cert_commit"] != contract.h9_cert_commit
        or commits["p8_cert_commit"] != contract.p8_cert_commit
        or commits["h8_cert_commit"] != contract.h8_cert_commit
        or commits["p7_cert_commit"] != contract.p7_cert_commit
        or commits["h7_cert_commit"] != contract.h7_cert_commit
        or commits["p18_cert_commit"] == commits["p17_cert_commit"]
        or commits["h18_cert_commit"] == commits["h17_cert_commit"]
        or commits["p17_cert_commit"] == commits["p16_cert_commit"]
        or commits["h17_cert_commit"] == commits["h16_cert_commit"]
        or commits["p16_cert_commit"] == commits["p15_cert_commit"]
        or commits["h16_cert_commit"] == commits["h15_cert_commit"]
        or commits["p15_cert_commit"] == commits["p14_cert_commit"]
        or commits["h15_cert_commit"] == commits["h14_cert_commit"]
        or commits["p14_cert_commit"] == commits["p12_cert_commit"]
        or commits["h14_cert_commit"] == commits["h12_cert_commit"]
        or commits["p12_cert_commit"] == commits["p11_cert_commit"]
        or commits["h12_cert_commit"] == commits["h11_cert_commit"]
        or commits["p11_cert_commit"] == commits["p10_cert_commit"]
        or commits["h11_cert_commit"] == commits["h10_cert_commit"]
        or commits["p10_cert_commit"] == commits["p9_cert_commit"]
        or commits["h10_cert_commit"] == commits["h9_cert_commit"]
        or commits["p9_cert_commit"] == commits["p8_cert_commit"]
        or commits["h9_cert_commit"] == commits["h8_cert_commit"]
        or commits["p8_cert_commit"] == commits["p7_cert_commit"]
        or commits["h8_cert_commit"] == commits["h7_cert_commit"]
        or commits["p6_cert_commit"] != contract.p6_cert_commit
        or commits["h6_cert_commit"] != contract.h6_cert_commit
        or commits["p7_cert_commit"] == commits["p6_cert_commit"]
        or commits["h7_cert_commit"] == commits["h6_cert_commit"]
        or commits["p5_cert_commit"] != contract.p5_cert_commit
        or commits["h5_cert_commit"] != contract.h5_cert_commit
        or commits["p4_cert_commit"] != contract.p4_cert_commit
        or commits["h4_cert_commit"] != contract.h4_cert_commit
        or commits["p3_cert_commit"] != contract.p3_cert_commit
        or commits["h3_cert_commit"] != contract.h3_cert_commit
        or commits["p2_cert_commit"] != contract.p2_cert_commit
        or commits["h2_cert_commit"] != contract.h2_cert_commit
        or commits["p1_cert_commit"] != contract.p1_cert_commit
        or commits["h1_cert_commit"] != contract.h1_cert_commit
    ):
        raise _error("effective authority commit binding drifted")
    return commits


def _require_h18_authority_boundary(
    value: Mapping[str, Any], *, contract: FinalCertificationContract
) -> None:
    """Bind R18 to factual non-retry R15/R16/R17 failures and lineage."""

    if value.get("status") != "effective" or value.get("gate") != "P-CERT":
        raise _error("R18 requires effective published P18 authority")
    authority = value.get("authority")
    if not isinstance(authority, Mapping):
        raise _error("effective H18 authority payload is absent")
    isolation = authority.get("isolation")
    if (
        authority.get("p17_failure") != expected_p17_failure_record()
        or authority.get("p16_failure") != expected_p16_failure_record()
        or authority.get("p15_failure") != expected_p15_failure_record()
        or authority.get("h13_failure") != expected_h13_failure_record()
        or authority.get("p14_failure") != expected_p14_failure_record()
        or authority.get("p12_failure") != expected_p12_failure_record()
        or authority.get("p11_failure") != expected_p11_failure_record()
        or authority.get("p10_failure") != expected_p10_failure_record()
        or authority.get("p9_failure") != expected_p9_failure_record()
        or not isinstance(isolation, Mapping)
        or isolation.get("sandbox_mountpoint_policy")
        != expected_sandbox_mountpoint_policy()
        or isolation.get("sandbox_mountpoint_policy")
        != dict(contract.sandbox_mountpoint_policy)
        or isolation.get("sandbox_smoke_policy")
        != expected_sandbox_smoke_policy()
        or isolation.get("sandbox_smoke_policy")
        != dict(contract.sandbox_smoke_policy)
        or isolation.get("cleanup_diagnostic_policy")
        != expected_cleanup_diagnostic_policy()
        or isolation.get("cleanup_diagnostic_policy")
        != dict(contract.cleanup_diagnostic_policy)
        or isolation.get("postgres_connection_policy")
        != expected_postgres_connection_policy()
        or isolation.get("postgres_connection_policy")
        != dict(contract.postgres_connection_policy)
        or isolation.get("postgres_startup_stability_policy")
        != expected_postgres_startup_stability_policy()
        or isolation.get("postgres_startup_stability_policy")
        != dict(contract.postgres_startup_stability_policy)
        or isolation.get("postgres_destroy_poll_policy")
        != expected_postgres_destroy_poll_policy()
        or isolation.get("postgres_destroy_poll_policy")
        != dict(contract.postgres_destroy_poll_policy)
        or isolation.get("test_access_guard_policy")
        != expected_test_access_guard_policy()
        or isolation.get("test_access_guard_policy")
        != dict(contract.test_access_guard_policy)
        or isolation.get("public_tests_junit_diagnostic_policy")
        != expected_public_tests_junit_diagnostic_policy()
        or isolation.get("public_tests_junit_diagnostic_policy")
        != dict(contract.public_tests_junit_diagnostic_policy)
    ):
        raise _error("effective H18 failure/isolation authority drifted")


def _require_effective_authority_dvc_status_policy(
    value: Mapping[str, Any],
    *,
    contract: FinalCertificationContract,
) -> dict[str, Any]:
    """Require the effective P18 authority's exact partial-clone status policy."""

    expected = expected_dvc_status_policy(contract)
    observed = value.get("dvc_status_policy")
    if not isinstance(observed, Mapping) or dict(observed) != expected:
        raise _error("effective authority DVC status policy drifted")
    return expected


def _require_dvc_status_policy_projection(
    value: Mapping[str, Any],
    *,
    contract: FinalCertificationContract,
    context: str,
) -> None:
    """Bind one serialized DVC projection to the effective exact-eight policy."""

    expected = expected_dvc_status_policy(contract)
    if (
        expected.get("scope") != "exact_eight_published_pointer_paths"
        or expected.get("target_count") != 8
        or expected.get("ordered_targets")
        != [spec.path for spec in contract.dvc_pointers]
        or expected.get("final_status_empty_result_required") is not True
        or value.get("post_restore_status_pointer_paths")
        != expected.get("post_restore_status_pointer_paths")
        or value.get("post_verification_status_pointer_paths")
        != expected.get("post_verification_status_pointer_paths")
        or value.get("partial_clone_global_status_authorized")
        != expected.get("global_status_authorized")
    ):
        raise _error(f"{context} DVC status policy projection drifted")


def _require_public_tests_junit_diagnostic_policy(
    contract: FinalCertificationContract,
) -> dict[str, Any]:
    expected = expected_public_tests_junit_diagnostic_policy()
    observed = dict(contract.public_tests_junit_diagnostic_policy)
    raw_skip_reason_aliases = expected.get("raw_skip_reason_aliases")
    serialized_fields = [
        "status",
        "returncode",
        "totals",
        "failed_nodeids",
        "failed_nodeids_sha256",
        "error_nodeids",
        "error_nodeids_sha256",
        "collected_test_count",
        "collected_nodeids_sha256",
        "unavailable_reason",
        "messages_preserved",
        "tracebacks_preserved",
        "raw_junit_preserved",
        "raw_stdout_preserved",
        "raw_stderr_preserved",
        "credentials_preserved",
        "absolute_paths_preserved",
    ]
    if (
        observed != expected
        or expected.get("enabled_on_nonzero_exit") is not True
        or expected.get("require_success") is not False
        or expected.get("source_filename") != "public-tests-raw.xml"
        or expected.get("max_junit_bytes") != 16_777_216
        or expected.get("retained_sandbox_directory_fd_required") is not True
        or expected.get("fd_relative_no_follow_open_required") is not True
        or expected.get("regular_single_link_required") is not True
        or expected.get("identity_revalidated_before_and_after_read") is not True
        or expected.get("xml_doctype_forbidden") is not True
        or expected.get("xml_entity_declaration_forbidden") is not True
        or expected.get("duplicate_testcase_nodeid_policy")
        != "single_record_or_exact_failure_error_pair"
        or expected.get("duplicate_testcase_pair_max_records") != 2
        or expected.get("duplicate_testcase_pair_exact_outcomes")
        != ["failure", "error"]
        or expected.get("outside_sealed_suite_nodeids_forbidden") is not True
        or expected.get("unknown_elements_or_attributes_forbidden") is not True
        or expected.get("exact_collection_count_required") is not True
        or expected.get("exact_collection_digest_required") is not True
        or expected.get("exact_skip_ledger_required") is not True
        or expected.get("exact_skip_override_marker") != "skipif_true"
        or expected.get("exact_skip_override_prepend") is not True
        or expected.get("preexisting_skipif_precedence_neutralized") is not True
        or expected.get("exact_skip_reason_emitted_required") is not True
        or not isinstance(raw_skip_reason_aliases, Mapping)
        or len(raw_skip_reason_aliases) != 5
        or any(
            not isinstance(reason, str) or not reason
            for reason in raw_skip_reason_aliases.values()
        )
        or expected.get("raw_skip_reason_alias_count") != 5
        or expected.get(
            "raw_skip_reason_aliases_canonicalized_before_ledger_validation"
        )
        is not True
        or expected.get(
            "pytest_declared_tests_teardown_error_counter_accounting"
        )
        is not True
        or expected.get("declared_tests_minimum")
        != "logical_testcase_identity_count"
        or expected.get("declared_tests_maximum")
        != "logical_testcase_identity_count_plus_error_identity_count"
        or expected.get("declared_failures_errors_skipped_exact") is not True
        or expected.get("serialized_fields") != serialized_fields
        or expected.get("failure_or_error_nodeids_sorted") is not True
        or expected.get("nodeid_digest_algorithm") != "sha256_canonical_json"
        or expected.get("available_status") != "failure_identity_available"
        or expected.get("messages_serialized") is not False
        or expected.get("tracebacks_serialized") is not False
        or expected.get("raw_junit_serialized") is not False
        or expected.get("raw_stdout_serialized") is not False
        or expected.get("raw_stderr_serialized") is not False
        or expected.get("absolute_paths_serialized") is not False
        or expected.get("credentials_serialized") is not False
        or expected.get("unavailable_status") != "failure_identity_unavailable"
        or set(cast(Sequence[str], expected.get("unavailable_reasons", ())))
        != PUBLIC_TESTS_JUNIT_UNAVAILABLE_REASONS
        or expected.get("unavailable_does_not_mask_active_error") is not True
        or expected.get("composite_error_propagates_public_tests_failure")
        is not True
    ):
        raise _error("H18 public-tests JUnit diagnostic policy drifted")
    return expected


def _require_h18_runtime_policy(contract: FinalCertificationContract) -> None:
    prefix_dispositions = {
        path: "require_absent" for path in SANDBOX_ABSENT_FORBIDDEN_PREFIXES
    }
    path_dispositions = {
        path: "require_regular_then_empty_file_mask"
        for path in SANDBOX_MASKED_FORBIDDEN_PATHS
    }
    cleanup = expected_postgres_cleanup_policy()
    connection = expected_postgres_connection_policy()
    expected_connection = {
        "test_database_url_scheme": "postgresql+asyncpg",
        "test_database_url_database": DB_NAME,
        "test_database_url_query_present": False,
        "test_database_url_hostname_present": False,
        "test_database_url_port_present": False,
        "test_database_url_password_present": False,
        "pg_host_source": "owned_unix_socket_environment",
        "pg_host_required": True,
        "helper_operation": "string_rsplit_last_slash",
        "helper_database_name": DB_NAME,
        "helper_admin_database_name": "postgres",
        "helper_admin_database_rewrite_preserves_socket_routing": True,
        "test_database_url_serialized": False,
        "pg_host_value_serialized": False,
        "credentials_serialized": False,
        "absolute_paths_serialized": False,
    }
    helper_url = SAFE_DB_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
    helper_database_name = helper_url.rsplit("/", 1)[-1]
    helper_admin_url = helper_url.rsplit("/", 1)[0] + "/postgres"
    startup_stability = expected_postgres_startup_stability_policy()
    destroy_poll = expected_postgres_destroy_poll_policy()
    access_guard = expected_test_access_guard_policy()
    junit_diagnostic = _require_public_tests_junit_diagnostic_policy(contract)
    mountpoint_policy = expected_sandbox_mountpoint_policy()
    if (
        contract.forbidden_read_prefixes != SANDBOX_ABSENT_FORBIDDEN_PREFIXES
        or contract.forbidden_read_paths != SANDBOX_MASKED_FORBIDDEN_PATHS
        or dict(contract.forbidden_read_prefix_dispositions)
        != prefix_dispositions
        or dict(contract.forbidden_read_path_dispositions) != path_dispositions
        or dict(contract.postgres_connection_policy) != connection
        or connection != expected_connection
        or SAFE_DB_URL != f"postgresql+asyncpg://postgres@/{DB_NAME}"
        or "?" in SAFE_DB_URL
        or DB_SOCKET_ROOT != "/cert-db"
        or helper_database_name != DB_NAME
        or helper_admin_url != "postgresql://postgres@/postgres"
        or dict(contract.postgres_startup_stability_policy) != startup_stability
        or len(startup_stability) != 22
        or startup_stability.get("pid1_expected_executable")
        != POSTGRES_FINAL_PID1_COMM
        or startup_stability.get("pid1_checked_before_readiness") is not True
        or startup_stability.get("pid1_revalidated_after_socket_claim") is not True
        or startup_stability.get("readiness_uses_explicit_socket_directory")
        is not True
        or startup_stability.get("exact_socket_claim_count")
        != len(POSTGRES_SOCKET_ENTRY_SPECS)
        or startup_stability.get("same_claims_revalidated_before_return")
        is not True
        or startup_stability.get("max_stability_attempts")
        != POSTGRES_STABILITY_MAX_ATTEMPTS
        or startup_stability.get("stability_interval_seconds")
        != POSTGRES_STABILITY_INTERVAL_SECONDS
        or startup_stability.get("retryable_inventory_states")
        != ["empty", "expected_subset"]
        or startup_stability.get("unexpected_names_fail_closed") is not True
        or startup_stability.get("unexpected_inode_types_fail_closed") is not True
        or startup_stability.get("unexpected_link_counts_fail_closed") is not True
        or startup_stability.get("claim_replacement_fails_closed") is not True
        or startup_stability.get("recapture_after_stop_authorized") is not False
        or startup_stability.get("arbitrary_residual_adoption_authorized")
        is not False
        or startup_stability.get("observed_inventory_serialized") is not False
        or startup_stability.get("container_identity_serialized") is not False
        or startup_stability.get("absolute_paths_serialized") is not False
        or startup_stability.get(
            "container_binding_checked_before_and_after_probes"
        )
        is not True
        or startup_stability.get("readiness_revalidated_after_socket_claim")
        is not True
        or startup_stability.get(
            "pid1_probe_requires_exact_stdout_and_empty_stderr"
        )
        is not True
        or startup_stability.get(
            "handoff_updated_with_same_container_identity_and_claims"
        )
        is not True
        or dict(contract.postgres_cleanup_policy) != cleanup
        or cleanup.get("graceful_stop_required") is not True
        or cleanup.get("graceful_stop_timeout_seconds")
        != POSTGRES_GRACEFUL_STOP_TIMEOUT_SECONDS
        or cleanup.get("stop_targets_exact_owned_container_id") is not True
        or cleanup.get("residual_entries")
        != [
            {"name": name, "kind": kind}
            for name, kind in POSTGRES_SOCKET_ENTRY_SPECS
        ]
        or cleanup.get("residual_cleanup_requires_container_absent") is not True
        or cleanup.get("residual_cleanup_requires_retained_directory_fd") is not True
        or cleanup.get("residual_claim_fields")
        != ["name", "kind", "device", "inode", "link_count"]
        or cleanup.get("arbitrary_residual_adoption_authorized") is not False
        or cleanup.get("socket_directory_empty_after_cleanup_required") is not True
        or cleanup.get("safe_internal_diagnostics_authorized") is not True
        or cleanup.get("raw_internal_diagnostics_serialized") is not False
        or dict(contract.postgres_destroy_poll_policy) != destroy_poll
        or destroy_poll.get("max_attempts")
        != POSTGRES_DESTROY_POLL_MAX_ATTEMPTS
        or destroy_poll.get("interval_seconds")
        != POSTGRES_DESTROY_POLL_INTERVAL_SECONDS
        or destroy_poll.get("single_stop_command") is not True
        or destroy_poll.get("mixed_presence_same_owned_identity_allowed") is not True
        or destroy_poll.get("double_absence_required") is not True
        or destroy_poll.get("foreign_identity_fails_closed") is not True
        or destroy_poll.get("socket_cleanup_after_double_absence") is not True
        or destroy_poll.get("timeout_preserves_owner") is not True
        or dict(contract.test_access_guard_policy) != access_guard
        or access_guard.get("public_tests_boundary")
        != "bubblewrap_hard_boundary"
        or access_guard.get("public_tests_python_audit_hook") is not False
        or access_guard.get("openapi_python_audit_hook") is not True
        or access_guard.get("e2e_python_audit_hook") is not True
        or dict(contract.sandbox_mountpoint_policy) != mountpoint_policy
        or mountpoint_policy.get("retained_python_exact_alias")
        != SANDBOX_RETAINED_PYTHON_ALIAS.as_posix()
        or mountpoint_policy.get("retained_poetry_exact_root_alias")
        != SANDBOX_RETAINED_POETRY_ROOT.as_posix()
        or mountpoint_policy.get("retained_alias_public_suite_only") is not True
        or mountpoint_policy.get("retained_alias_workspace_root") != "/workspace"
        or mountpoint_policy.get("retained_python_host_target_environment")
        != PLUGIN_RETAINED_PYTHON_ENV
        or mountpoint_policy.get("retained_python_host_target_required_under_usr")
        is not True
        or mountpoint_policy.get(
            "retained_python_alias_matches_proc_self_exe_full_identity"
        )
        is not True
        or mountpoint_policy.get(
            "retained_python_alias_matches_injected_host_target_full_identity"
        )
        is not True
        or mountpoint_policy.get("retained_poetry_alias_requires_same_python_context")
        is not True
        or mountpoint_policy.get("arbitrary_retained_runtime_alias_authorized")
        is not False
        or dict(contract.sandbox_smoke_policy) != expected_sandbox_smoke_policy()
        or dict(contract.cleanup_diagnostic_policy)
        != expected_cleanup_diagnostic_policy()
        or dict(contract.public_tests_junit_diagnostic_policy)
        != junit_diagnostic
    ):
        raise _error("H18 runtime isolation policy drifted")


def check_phase4_final_certification(
    *,
    repo_root: Path = PROJECT_ROOT,
    authority_validator: Callable[[Path, FinalCertificationContract], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the non-writing P-CERT and output-namespace preflight."""

    root = repo_root.resolve(strict=True)
    contract = load_contract(root=root)
    _require_h18_runtime_policy(contract)
    if contract.test_suite.status != "locked":
        raise _error("final certification refuses a pending test-suite lock")
    state = _capture_main_state(root)
    if any(state[key] for key in ("status", "cached_diff", "unstaged_diff")):
        raise _error("P-CERT certification gate requires a clean repository")
    if len({state["head"], state["main"], state["origin_main"], state["origin_head"]}) != 1:
        raise _error("P-CERT local refs are not aligned")
    authority = (authority_validator or _authority_loader)(root, contract)
    _require_h18_authority_boundary(authority, contract=contract)
    authority_commits = _require_effective_authority_commit_binding(
        authority,
        contract=contract,
        execution_commit=authority.get("p18_cert_commit"),
    )
    _require_effective_authority_dvc_status_policy(authority, contract=contract)
    effective_commit = authority_commits["p18_cert_commit"]
    if effective_commit != state["head"]:
        raise _error("P-CERT authority is not bound to current HEAD")
    live_remote = _git(root, "ls-remote", "--exit-code", "origin", "refs/heads/main")
    live_commit = live_remote.split()[0] if live_remote else ""
    if live_commit != state["head"]:
        raise _error("live origin/main does not equal published P-CERT")
    output_root = root / CERTIFICATION_ROOT
    if os.path.lexists(output_root):
        raise _error("R-CERT output namespace already exists")
    legacy_guard = root / GUARD_PATH
    if os.path.lexists(legacy_guard):
        raise _error("legacy final-certification guard path must be absent")
    main_site_cache_lease = _open_main_dvc_site_cache_lease(root)
    try:
        local_remote = validate_local_dvc_remote_configuration(root=root)
        anchor_records, pointer_records, main_dvc_static_boundary = (
            _reconstruct_main_dvc_static_boundary(
                root=root,
                contract=contract,
                context="P-CERT check-only",
                main_site_cache_lease=main_site_cache_lease,
            )
        )
    finally:
        try:
            main_site_cache_lease.revalidate(
                context="P-CERT check-only final main DVC site-cache invariant"
            )
        finally:
            main_site_cache_lease.close()
    if len(pointer_records) != 8:
        raise _error("P-CERT does not bind exactly eight DVC pointers")
    return {
        "status": "ready_to_certify",
        "writes": False,
        "commands_executed": False,
        "execution_commit": state["head"],
        "authority": dict(authority),
        "anchor_inputs": anchor_records,
        "dvc_pointers": pointer_records,
        "output_paths": list(contract.output_paths),
        "main_dvc_static_boundary": main_dvc_static_boundary,
        "local_dvc_remote_configuration": dict(local_remote),
    }


def _clone_exact_p(
    *,
    source_root: Path,
    clone_root: Path,
    execution_commit: str,
    namespace_validator: Callable[[str], None] | None = None,
) -> Mapping[str, Any]:
    origin = _git(source_root, "config", "--get", "remote.origin.url")
    if not origin or "\n" in origin or "\x00" in origin:
        raise _error("origin URL is absent or malformed")
    if namespace_validator is not None:
        namespace_validator("before_git_clone")
    result = _run(
        (
            GIT_EXECUTABLE,
            "clone",
            "--no-local",
            "--no-hardlinks",
            "--single-branch",
            "--branch",
            "main",
            "--",
            origin,
            os.fspath(clone_root),
        ),
        cwd=source_root,
        portable_argv=(
            "git",
            "clone",
            "--no-local",
            "--no-hardlinks",
            "--single-branch",
            "--branch",
            "main",
            "<LIVE_ORIGIN_MAIN>",
            "<OWNED_CLONE>",
        ),
        timeout_seconds=600,
        failure_stage="git clone",
    )
    if namespace_validator is not None:
        namespace_validator("after_git_clone")
    head = _git(clone_root, "rev-parse", "HEAD")
    status = _git(clone_root, "status", "--porcelain=v1", "--untracked-files=all")
    parents = _git(clone_root, "show", "-s", "--format=%P", "HEAD").split()
    if head != execution_commit or status or len(parents) != 1:
        raise _error("isolated clone is not exact clean single-parent P-CERT")
    return {
        "command": dict(result.record),
        "execution_commit": execution_commit,
        "initially_clean": True,
        "single_parent": True,
        "source": "live_origin_main",
        "remote_url_serialized": False,
    }


def _read_open_regular_fd(descriptor: int, *, context: str) -> bytes:
    """Read a retained regular file without changing its shared file offset."""

    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise _error(f"{context} is not a single-link regular file")
    chunks: list[bytes] = []
    offset = 0
    while offset < before.st_size:
        chunk = os.pread(descriptor, min(64 * 1024, before.st_size - offset), offset)
        if not chunk:
            raise _error(f"{context} ended before its declared size")
        chunks.append(chunk)
        offset += len(chunk)
    after = os.fstat(descriptor)
    if _stat_identity(after) != _stat_identity(before):
        raise _error(f"{context} changed while read")
    return b"".join(chunks)


def _parse_private_dvc_config(payload: bytes) -> configparser.RawConfigParser:
    """Parse private DVC configuration without returning any private value."""

    try:
        text_payload = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _error("private DVC configuration is not UTF-8") from exc
    if "\x00" in text_payload:
        raise _error("private DVC configuration contains a NUL byte")
    parser = configparser.RawConfigParser(
        interpolation=None,
        strict=True,
        empty_lines_in_values=False,
    )
    try:
        parser.read_string(text_payload)
    except configparser.Error as exc:
        raise _error("private DVC configuration syntax is invalid") from exc
    if parser.defaults():
        raise _error("private DVC configuration defaults are unsupported")
    return parser


def _private_dvc_config_mapping(
    parser: configparser.RawConfigParser,
) -> dict[str, dict[str, str]]:
    return {
        section: {key: value for key, value in parser.items(section, raw=True)}
        for section in parser.sections()
    }


def _scan_private_metadata_tree(
    root: DirectoryHandle,
) -> dict[str, tuple[int, ...]]:
    """Snapshot a private metadata tree without opening any file payload."""

    records: dict[str, tuple[int, ...]] = {}

    def scan(directory: DirectoryHandle, prefix: str) -> None:
        for name in sorted(os.listdir(directory.fd)):
            if not name or "/" in name or name in {".", ".."}:
                raise _error("private metadata tree contains an unsafe name")
            metadata = os.stat(name, dir_fd=directory.fd, follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode):
                raise _error("private metadata tree contains a symlink")
            if not (stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode)):
                raise _error("private metadata tree contains an unsupported inode")
            if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink != 1:
                raise _error("private metadata tree contains a hardlinked file")
            relative = f"{prefix}/{name}" if prefix else name
            records[relative] = _stat_identity(metadata)
            if stat.S_ISDIR(metadata.st_mode):
                descriptor = os.open(
                    name,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=directory.fd,
                )
                opened = os.fstat(descriptor)
                if _stat_identity(opened) != _stat_identity(metadata):
                    os.close(descriptor)
                    raise _error("private metadata directory changed while opened")
                child = DirectoryHandle(
                    directory.path / name,
                    descriptor,
                    opened.st_dev,
                    opened.st_ino,
                )
                try:
                    scan(child, relative)
                finally:
                    child.close()

    scan(root, "")
    return records


def _site_cache_root_identity(
    handle: DirectoryHandle,
    *,
    expected_mode: int | None,
    context: str,
) -> tuple[int, ...]:
    """Return a complete retained root identity without following a name."""

    metadata = os.fstat(handle.fd)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or (metadata.st_dev, metadata.st_ino) != (handle.device, handle.inode)
        or (
            expected_mode is not None
            and stat.S_IMODE(metadata.st_mode) != expected_mode
        )
    ):
        raise _error(f"{context} root identity or mode drifted")
    return _stat_identity(metadata)


def _revalidate_owned_site_cache_root(
    handle: DirectoryHandle,
    expected_identity: tuple[int, ...],
    *,
    allow_successful_dvc_transition: bool,
    context: str,
) -> tuple[int, ...]:
    """Reject root drift, except a completed pre-freeze DVC mutation."""

    current = _site_cache_root_identity(
        handle,
        expected_mode=0o700,
        context=context,
    )
    if current == expected_identity:
        return expected_identity
    if allow_successful_dvc_transition:
        return current
    raise _error(f"{context} root metadata drifted")


def _require_exact_main_dvc_site_cache_path(
    parser: configparser.RawConfigParser,
    *,
    root: Path,
) -> Path:
    """Return only the canonical repository-owned main site-cache path."""

    if not parser.has_option("core", "site_cache_dir"):
        raise _error("private DVC configuration lacks core.site_cache_dir")
    raw_path = parser.get("core", "site_cache_dir", raw=True)
    candidate = Path(raw_path)
    expected = root / ".dvc/tmp/site-cache"
    if (
        not root.is_absolute()
        or not candidate.is_absolute()
        or raw_path != raw_path.strip()
        or "\x00" in raw_path
        or os.path.normpath(raw_path) != raw_path
        or candidate != expected
        or raw_path != os.fspath(expected)
    ):
        raise _error("private DVC site-cache path is not the exact owned main path")
    return candidate


def _open_main_dvc_site_cache_lease(root: Path) -> MainDvcSiteCacheLease:
    """Retain the configured main site-cache without serializing its path."""

    config_chain, _ = _open_directory_chain(
        root, LOCAL_DVC_CONFIG_PATH.parent, create_missing=False
    )
    config_fd = -1
    site_cache_chain: list[DirectoryHandle] = []
    succeeded = False
    try:
        config_fd = os.open(
            LOCAL_DVC_CONFIG_PATH.name,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=config_chain[-1].fd,
        )
        config = _revalidate_open_file_name(
            config_chain[-1],
            LOCAL_DVC_CONFIG_PATH.name,
            config_fd,
            expected_modes=frozenset({0o600, 0o644}),
            context="main DVC site-cache source configuration",
        )
        payload = _read_open_regular_fd(
            config_fd,
            context="main DVC site-cache source configuration",
        )
        parser = _parse_private_dvc_config(payload)
        candidate = _require_exact_main_dvc_site_cache_path(parser, root=root)
        relative = candidate.relative_to(Path("/"))
        try:
            site_cache_chain, _ = _open_directory_chain(
                Path("/"), relative, create_missing=False
            )
        except (OSError, FinalCertificationBuildError):
            raise _error(
                "private DVC site-cache path could not be safely retained"
            ) from None
        site_cache_identity = _site_cache_root_identity(
            site_cache_chain[-1],
            expected_mode=None,
            context="initial main DVC site cache",
        )
        inventory = _scan_private_metadata_tree(site_cache_chain[-1])
        if (
            _site_cache_root_identity(
                site_cache_chain[-1],
                expected_mode=None,
                context="initial main DVC site cache",
            )
            != site_cache_identity
        ):
            raise _error("main DVC site cache root changed while snapshotting")
        lease = MainDvcSiteCacheLease(
            root=root,
            config_chain=config_chain,
            config_fd=config_fd,
            config_identity=_stat_identity(config),
            site_cache_chain=site_cache_chain,
            site_cache_identity=site_cache_identity,
            inventory=inventory,
        )
        lease.revalidate(context="initial main DVC site-cache snapshot")
        succeeded = True
        return lease
    finally:
        if not succeeded:
            for handle in reversed(site_cache_chain):
                handle.close()
            if config_fd >= 0:
                os.close(config_fd)
            for handle in reversed(config_chain):
                handle.close()


def _reconstruct_main_dvc_static_boundary(
    *,
    root: Path,
    contract: FinalCertificationContract,
    context: str,
    expected_anchors: Sequence[Mapping[str, Any]] | None = None,
    expected_pointers: Sequence[Mapping[str, Any]] | None = None,
    main_site_cache_lease: MainDvcSiteCacheLease | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Reconstruct main DVC state from Git-bound public bytes, without DVC."""

    if main_site_cache_lease is not None:
        main_site_cache_lease.revalidate(
            context=f"before {context} static main DVC boundary"
        )
    try:
        anchor_records = collect_anchor_input_records(contract, root=root)
        pointer_records = collect_dvc_pointer_records(contract, root=root)
        if expected_anchors is not None and anchor_records != list(expected_anchors):
            raise _error(f"{context} public anchor inputs changed")
        if expected_pointers is not None and pointer_records != list(
            expected_pointers
        ):
            raise _error(f"{context} published DVC pointers changed")
        sealed = main_dvc_static_boundary_record(
            contract,
            anchor_records=anchor_records,
            pointer_records=pointer_records,
        )
        if (
            set(sealed)
            != {
                "status_executed",
                "state_source",
                "static_boundary_verified",
                "tracked_config_path",
                "tracked_config_git_blob_oid",
                "versioned_pointer_count",
                "versioned_pointer_records_digest",
                "real_dvc_execution_scope",
            }
            or sealed.get("status_executed") is not False
            or sealed.get("state_source") != "git_and_versioned_dvc_pointers"
            or sealed.get("static_boundary_verified") is not True
            or sealed.get("versioned_pointer_count") != 8
            or sealed.get("versioned_pointer_records_digest")
            != digest_records(pointer_records)
            or sealed.get("real_dvc_execution_scope")
            != "isolated_r_cert_clone_only"
        ):
            raise _error(f"{context} static main DVC boundary drifted")
        boundary = {
            "main_dvc_status_command_run": False,
            "main_dvc_static_reconstruction_from_git_and_published_pointers": True,
            "main_dvc_state_source": sealed["state_source"],
            "tracked_config_path": sealed["tracked_config_path"],
            "tracked_config_git_blob_oid": sealed["tracked_config_git_blob_oid"],
            "published_dvc_pointer_count": sealed["versioned_pointer_count"],
            "published_dvc_pointer_records_sha256": sealed[
                "versioned_pointer_records_digest"
            ],
            "real_dvc_execution_scope": sealed["real_dvc_execution_scope"],
            "parquet_payload_opened_or_decoded": False,
        }
        return anchor_records, pointer_records, boundary
    finally:
        if main_site_cache_lease is not None:
            main_site_cache_lease.revalidate(
                context=f"after {context} static main DVC boundary"
            )


def _credential_sections(
    parser: configparser.RawConfigParser,
) -> tuple[str, ...]:
    def is_remote_section(section: str) -> bool:
        normalized = (
            section[1:-1]
            if len(section) >= 2 and section.startswith("'") and section.endswith("'")
            else section
        )
        return normalized.startswith('remote "') and normalized.endswith('"')

    sections = tuple(
        section
        for section in parser.sections()
        if is_remote_section(section)
        and parser.has_option(section, "credentialpath")
    )
    if not sections:
        raise _error("private DVC configuration lacks a credential path")
    return sections


def _open_retained_private_credential(
    source_root: Path,
    raw_path: str,
) -> RetainedPrivateCredential:
    """Retain a source credential through a no-follow path below ``private``."""

    if (
        not raw_path
        or raw_path != raw_path.strip()
        or "\\" in raw_path
        or "\x00" in raw_path
    ):
        raise _error("private DVC credential path is malformed")
    configured = PurePosixPath(raw_path)
    if configured.is_absolute() or not configured.parts:
        raise _error("private DVC credential path must remain below private/")
    normalized: list[str] = list(LOCAL_DVC_CONFIG_PATH.parent.parts)
    for part in configured.parts:
        if part in {"", "."}:
            raise _error("private DVC credential path is not canonical")
        if part == "..":
            if not normalized:
                raise _error("private DVC credential path escaped repository root")
            normalized.pop()
        else:
            normalized.append(part)
    if not normalized or normalized[0] != "private":
        raise _error("private DVC credential path must resolve below private/")
    local = Path(*normalized)
    try:
        chain, _ = _open_directory_chain(
            source_root, local.parent, create_missing=False
        )
    except (OSError, FinalCertificationBuildError):
        raise _error(
            "private DVC credential parent could not be safely retained"
        ) from None
    descriptor = -1
    try:
        descriptor = os.open(
            local.name,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=chain[-1].fd,
        )
        opened = os.fstat(descriptor)
        named = os.stat(local.name, dir_fd=chain[-1].fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or opened.st_nlink != 1
            or named.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) & 0o022
            or stat.S_IMODE(named.st_mode) & 0o022
            or _stat_identity(opened) != _stat_identity(named)
            or opened.st_size <= 0
        ):
            raise _error("private DVC credential identity/mode/link is unsafe")
        retained = RetainedPrivateCredential(
            root=source_root,
            chain=chain,
            name=local.name,
            fd=descriptor,
            identity=_stat_identity(opened),
        )
        retained.revalidate(context="private DVC credential open")
        return retained
    except BaseException as exc:
        if descriptor >= 0:
            os.close(descriptor)
        for handle in reversed(chain):
            handle.close()
        if isinstance(exc, FinalCertificationBuildError):
            raise
        raise _error("private DVC credential could not be safely retained") from None


def _render_rebased_private_dvc_config(
    parser: configparser.RawConfigParser,
    *,
    sections: Sequence[str],
    credentials: Sequence[RetainedPrivateCredential],
) -> bytes:
    if len(sections) != len(credentials):
        raise _error("private DVC credential bridge cardinality drifted")
    for section, credential in zip(sections, credentials, strict=True):
        parser.set(section, "credentialpath", credential.proc_path)
    buffer = io.StringIO()
    parser.write(buffer, space_around_delimiters=True)
    return buffer.getvalue().encode("utf-8")


def _require_private_dvc_config_equivalence(
    source_payload: bytes,
    clone_payload: bytes,
    *,
    credential_sections: Sequence[str],
    credential_proc_paths: Sequence[str],
    allow_operational_cache: bool,
    owned_cache_dir: str | None = None,
) -> None:
    """Compare effective private settings without exposing any setting value."""

    if len(credential_sections) != len(credential_proc_paths):
        raise _error("private DVC equivalence bridge cardinality drifted")
    source = _private_dvc_config_mapping(_parse_private_dvc_config(source_payload))
    clone = _private_dvc_config_mapping(_parse_private_dvc_config(clone_payload))
    if allow_operational_cache:
        if (
            owned_cache_dir is None
            or not Path(owned_cache_dir).is_absolute()
            or clone.get("cache", {}).get("dir") != owned_cache_dir
            or clone.get("cache", {}).get("type") != "copy"
        ):
            raise _error("private DVC owned cache settings drifted")
        source_cache = source.setdefault("cache", {})
        clone_cache = clone.setdefault("cache", {})
        for key in ("dir", "type"):
            source_cache.pop(key, None)
            clone_cache.pop(key, None)
        if not source_cache:
            source.pop("cache", None)
        if not clone_cache:
            clone.pop("cache", None)
    elif owned_cache_dir is not None:
        raise _error("private DVC owned cache binding appeared before configuration")
    if set(source) != set(clone):
        raise _error("private DVC configuration section set drifted")
    for index, (section, proc_path) in enumerate(
        zip(credential_sections, credential_proc_paths, strict=True)
    ):
        if section not in source or section not in clone:
            raise _error("private DVC credential section drifted")
        if source[section].get("credentialpath") is None:
            raise _error("source DVC credential path disappeared")
        if clone[section].get("credentialpath") != proc_path:
            raise _error("clone DVC credential descriptor bridge drifted")
        marker = f"<retained-private-credential-{index}>"
        source[section]["credentialpath"] = marker
        clone[section]["credentialpath"] = marker
    if source != clone:
        raise _error("private DVC effective configuration drifted after safe rebasing")


def _install_local_dvc_remote_configuration(
    *, source_root: Path, clone_root: Path
) -> InstalledDvcConfiguration:
    """Install the private remote config with retained credential FD bridges.

    The file is operational state, not a scientific/public authority input.
    Its path, content, remote name, URL, and credentials are intentionally
    absent from the returned projection and every public artifact.
    """

    validation = validate_local_dvc_remote_configuration(root=source_root)
    source_chain, _ = _open_directory_chain(
        source_root, LOCAL_DVC_CONFIG_PATH.parent, create_missing=False
    )
    destination_chain, _ = _open_directory_chain(
        clone_root, LOCAL_DVC_CONFIG_PATH.parent, create_missing=False
    )
    source_fd = -1
    destination_fd = -1
    credentials: tuple[RetainedPrivateCredential, ...] = ()
    succeeded = False
    try:
        _rebind_directory_chain(
            source_root, source_chain, context="source DVC configuration"
        )
        _rebind_directory_chain(
            clone_root, destination_chain, context="clone DVC configuration"
        )
        source_fd = os.open(
            LOCAL_DVC_CONFIG_PATH.name,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=source_chain[-1].fd,
        )
        destination_fd = os.open(
            LOCAL_DVC_CONFIG_PATH.name,
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=destination_chain[-1].fd,
        )
        os.fchmod(destination_fd, 0o600)
        before = _revalidate_open_file_name(
            source_chain[-1],
            LOCAL_DVC_CONFIG_PATH.name,
            source_fd,
            expected_modes=frozenset({0o600, 0o644}),
            context="source DVC configuration",
        )
        source_payload = _read_open_regular_fd(
            source_fd,
            context="source DVC configuration",
        )
        parser = _parse_private_dvc_config(source_payload)
        sections = _credential_sections(parser)
        opened_credentials: list[RetainedPrivateCredential] = []
        try:
            for section in sections:
                opened_credentials.append(
                    _open_retained_private_credential(
                        source_root,
                        parser.get(section, "credentialpath", raw=True),
                    )
                )
        except BaseException:
            for credential in reversed(opened_credentials):
                credential.close()
            raise
        credentials = tuple(opened_credentials)
        clone_payload = _render_rebased_private_dvc_config(
            parser,
            sections=sections,
            credentials=credentials,
        )
        total = 0
        for chunk_start in range(0, len(clone_payload), 64 * 1024):
            view = memoryview(clone_payload[chunk_start : chunk_start + 64 * 1024])
            while view:
                written = os.write(destination_fd, view)
                if written <= 0:
                    raise _error("private DVC configuration copy made no progress")
                view = view[written:]
                total += written
        os.fsync(destination_fd)
        after = _revalidate_open_file_name(
            source_chain[-1],
            LOCAL_DVC_CONFIG_PATH.name,
            source_fd,
            expected_modes=frozenset({0o600, 0o644}),
            context="source DVC configuration",
        )
        copied = _revalidate_open_file_name(
            destination_chain[-1],
            LOCAL_DVC_CONFIG_PATH.name,
            destination_fd,
            expected_modes=frozenset({0o600}),
            context="clone DVC configuration",
        )
        if (
            (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
                before.st_nlink,
                stat.S_IMODE(before.st_mode),
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
            or total != len(clone_payload)
            or copied.st_size != len(clone_payload)
        ):
            raise _error("local DVC remote configuration changed during private rebase")
        _rebind_directory_chain(
            source_root, source_chain, context="source DVC configuration"
        )
        _rebind_directory_chain(
            clone_root, destination_chain, context="clone DVC configuration"
        )
        ignored = subprocess.run(
            [
                GIT_EXECUTABLE,
                "check-ignore",
                "--quiet",
                "--",
                LOCAL_DVC_CONFIG_PATH.as_posix(),
            ],
            cwd=clone_root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
            timeout=30,
        )
        if ignored.returncode != 0 or ignored.stdout or ignored.stderr:
            raise _error("copied local DVC remote configuration is not ignored")
        source_final = _revalidate_open_file_name(
            source_chain[-1],
            LOCAL_DVC_CONFIG_PATH.name,
            source_fd,
            expected_modes=frozenset({0o600, 0o644}),
            context="source DVC configuration",
        )
        destination_final = _revalidate_open_file_name(
            destination_chain[-1],
            LOCAL_DVC_CONFIG_PATH.name,
            destination_fd,
            expected_modes=frozenset({0o600}),
            context="clone DVC configuration",
        )
        if (
            (source_final.st_dev, source_final.st_ino, source_final.st_ctime_ns)
            != (after.st_dev, after.st_ino, after.st_ctime_ns)
            or (
                destination_final.st_dev,
                destination_final.st_ino,
                destination_final.st_ctime_ns,
            )
            != (copied.st_dev, copied.st_ino, copied.st_ctime_ns)
        ):
            raise _error("private DVC configuration drifted during ignore validation")
        _rebind_directory_chain(
            source_root, source_chain, context="source DVC configuration"
        )
        _rebind_directory_chain(
            clone_root, destination_chain, context="clone DVC configuration"
        )
        _require_private_dvc_config_equivalence(
            source_payload,
            _read_open_regular_fd(
                destination_fd,
                context="clone DVC configuration",
            ),
            credential_sections=sections,
            credential_proc_paths=tuple(item.proc_path for item in credentials),
            allow_operational_cache=False,
        )
        public_validation = {
            key: value
            for key, value in validation.items()
            if key
            not in {
                "content_opened",
                "content_or_path_serialized",
                "filesystem_mode",
            }
        }
        installed = InstalledDvcConfiguration(
            source_root=source_root,
            clone_root=clone_root,
            source_chain=source_chain,
            clone_chain=destination_chain,
            source_fd=source_fd,
            clone_fd=destination_fd,
            source_identity=_stat_identity(source_final),
            credentials=credentials,
            credential_sections=sections,
            public_record={
                **public_validation,
                "source_mode_accepted": "0600_or_0644",
                "clone_mode": "0600",
                "copied_only_into_owned_clone": True,
                "content_read_only_for_private_rebase": True,
                "credential_path_rebased_to_retained_fd": True,
                "credential_target_regular_single_link": True,
                "credential_target_group_or_other_writable": False,
                "effective_configuration_equivalent_except_owned_cache": True,
                "content_path_remote_url_and_credentials_serialized": False,
            },
        )
        installed.revalidate(
            allow_operational_cache=False,
            context="installed private DVC configuration",
        )
        succeeded = True
        return installed
    finally:
        if not succeeded:
            for credential in reversed(credentials):
                credential.close()
            if destination_fd >= 0:
                os.close(destination_fd)
            if source_fd >= 0:
                os.close(source_fd)
            for handle in reversed(destination_chain):
                handle.close()
            for handle in reversed(source_chain):
                handle.close()


def _restore_dvc_objects(
    *,
    source_root: Path,
    clone_root: Path,
    cache_root: Path,
    site_cache_root: Path,
    installed_configuration: InstalledDvcConfiguration,
    contract: FinalCertificationContract,
    namespace_validator: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    anchored = _open_python_script_runtime(
        source_root,
        Path(".venv/bin/dvc"),
        context="DVC runtime",
    )
    try:
        return _restore_dvc_objects_with_anchored_executable(
            source_root=source_root,
            clone_root=clone_root,
            cache_root=cache_root,
            site_cache_root=site_cache_root,
            installed_configuration=installed_configuration,
            contract=contract,
            executable=anchored,
            namespace_validator=namespace_validator,
        )
    finally:
        anchored.close()


def _restore_dvc_objects_with_anchored_executable(
    *,
    source_root: Path,
    clone_root: Path,
    cache_root: Path,
    site_cache_root: Path,
    installed_configuration: InstalledDvcConfiguration,
    contract: FinalCertificationContract,
    executable: AnchoredPythonScriptRuntime,
    namespace_validator: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    _require_isolated_dvc_command_root(
        source_root=source_root,
        command_root=clone_root,
        context="DVC restore",
    )
    if any(cache_root.iterdir()):
        raise _error("isolated DVC cache is not initially empty")
    if any(site_cache_root.iterdir()):
        raise _error("isolated DVC site cache is not initially empty")
    if stat.S_IMODE(site_cache_root.lstat().st_mode) != 0o700:
        raise _error("isolated DVC site cache mode drifted")
    isolated_environment = {
        "DVC_NO_ANALYTICS": "1",
        "DVC_SITE_CACHE_DIR": os.fspath(site_cache_root),
    }
    # DVC may update clone-local `.dvc/config.local` and create `.dvc/tmp` as soon
    # as configuration or the first pull starts.  Those writes necessarily
    # precede the post-restore inventory freeze.  A command failure in this
    # interval therefore leaves an unproven residual: cleanup must preserve
    # the namespace, never adopt it or guess which entries DVC owns.
    # The copied ignored config supplies only the remote.  Point its private
    # clone-local cache at the owned empty directory and force copy checkout so
    # every restored payload remains a single-link inode.  These operational
    # values are never serialized.
    for key, value in (
        ("cache.dir", os.fspath(cache_root)),
        ("cache.type", "copy"),
    ):
        if namespace_validator is not None:
            namespace_validator(f"before_dvc_config_{key}")
        configured = _run_python_script_runtime(
            executable,
            ("config", "--local", key, value),
            cwd=clone_root,
            portable_argv=(".venv/bin/dvc", "config", "--local", key, "<PRIVATE>"),
            environment=isolated_environment,
            timeout_seconds=120,
            context=f"DVC config {key}",
            private_pass_fds=(),
        )
        if namespace_validator is not None:
            namespace_validator(f"after_dvc_config_{key}")
    installed_configuration.bind_owned_cache(cache_root)
    installed_configuration.revalidate(
        allow_operational_cache=True,
        context="private DVC configuration after owned cache settings",
    )
    private_config = clone_root / LOCAL_DVC_CONFIG_PATH
    private_config_identity = _private_regular_identity(private_config)
    records: list[dict[str, Any]] = []
    observed_outputs: set[str] = set()
    for index, spec in enumerate(contract.dvc_pointers, start=1):
        pointer_path = _require_relative(spec.path, context="DVC pointer")
        output_path = _require_relative(spec.output_path, context="DVC output")
        pointer_payload = _read_regular(
            clone_root / pointer_path, context=f"DVC pointer {spec.path}"
        )
        parsed = parse_dvc_pointer_bytes(pointer_payload, Path(spec.path))
        if parsed["md5"] != spec.md5 or parsed["size"] != spec.size:
            raise _error(f"DVC pointer contract drifted: {spec.path}")
        portable = (
            ".venv/bin/dvc",
            "pull",
            "--no-run-cache",
            "-j",
            "1",
            spec.path,
        )
        if namespace_validator is not None:
            namespace_validator(f"before_dvc_pull_{index}")
        result = _run_python_script_runtime(
            executable,
            ("pull", "--no-run-cache", "-j", "1", spec.path),
            cwd=clone_root,
            portable_argv=portable,
            environment=isolated_environment,
            timeout_seconds=1800,
            context=f"directed DVC pull {index}",
            private_pass_fds=installed_configuration.pass_fds,
        )
        if namespace_validator is not None:
            namespace_validator(f"after_dvc_pull_{index}")
        if _private_regular_identity(private_config) != private_config_identity:
            raise _error("private DVC configuration changed during directed pulls")
        installed_configuration.revalidate(
            allow_operational_cache=True,
            context=f"private DVC configuration after directed pull {index}",
        )
        _restored_payload_identity(
            clone_root / output_path,
            expected_size=spec.size,
            context=f"restored DVC output {spec.output_path}",
        )
        cache_relative = Path("files/md5") / spec.md5[:2] / spec.md5[2:]
        _restored_payload_identity(
            cache_root / cache_relative,
            expected_size=spec.size,
            context=f"content-addressed DVC cache object for {spec.path}",
        )
        if namespace_validator is not None:
            namespace_validator(f"before_dvc_status_{index}")
        status_result = _run_python_script_runtime(
            executable,
            ("status", "--json", spec.path),
            cwd=clone_root,
            portable_argv=(
                ".venv/bin/dvc",
                "status",
                "--json",
                spec.path,
            ),
            environment=isolated_environment,
            timeout_seconds=300,
            context=f"directed DVC status {index}",
            private_pass_fds=installed_configuration.pass_fds,
        )
        if namespace_validator is not None:
            namespace_validator(f"after_dvc_status_{index}")
        try:
            directed_status = json.loads(status_result.stdout)
        except json.JSONDecodeError as exc:
            raise _error(f"directed DVC status was not JSON: {spec.path}") from exc
        if directed_status != {}:
            raise _error(f"directed DVC status is not clean: {spec.path}")
        observed_outputs.add(spec.output_path)
        records.append(
            {
                "ordinal": index,
                "pointer_path": spec.path,
                "output_path": spec.output_path,
                "role": spec.role,
                "pointer_declared_md5": spec.md5,
                "pointer_declared_bytes": spec.size,
                "pointer_sha256": sha256_bytes(pointer_payload),
                "pull_command": dict(result.record),
                "directed_status_command": dict(status_result.record),
                "one_pointer_per_command": True,
                "restored_output_regular_single_link": True,
                "cache_object_path_from_declared_md5": True,
                "dvc_transport_authentication_passed": True,
                "payload_opened_by_python": False,
                "payload_decoded": False,
            }
        )
    if observed_outputs != {spec.output_path for spec in contract.dvc_pointers}:
        raise _error("DVC restore output scope is not exact eight")
    _validate_exact_dvc_cache(cache_root=cache_root, contract=contract)
    if namespace_validator is not None:
        namespace_validator("before_dvc_final_status")
    _dvc_status_with_executable(
        clone_root,
        executable,
        source_root=source_root,
        targets=_contract_dvc_status_targets(
            contract,
            contract.post_restore_status_pointer_paths,
            context="post-restore",
        ),
        environment={"DVC_SITE_CACHE_DIR": os.fspath(site_cache_root)},
        private_pass_fds=installed_configuration.pass_fds,
    )
    if namespace_validator is not None:
        namespace_validator("after_dvc_final_status")
    installed_configuration.revalidate(
        allow_operational_cache=True,
        context="private DVC configuration after exact restore",
    )
    return records


def _private_regular_identity(path: Path) -> tuple[int, int, int, int, int, str]:
    payload = _read_regular(path, context="private operational configuration")
    metadata = path.lstat()
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise _error("private operational configuration mode drifted")
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
        sha256_bytes(payload),
    )


def _validate_exact_dvc_cache(
    *, cache_root: Path, contract: FinalCertificationContract
) -> Mapping[str, Any]:
    expected = {
        (Path("files/md5") / spec.md5[:2] / spec.md5[2:]).as_posix(): spec
        for spec in contract.dvc_pointers
    }
    observed: dict[str, tuple[int, int, int, int, int, int, int]] = {}
    observed_directories: set[str] = set()
    for directory, directory_names, file_names in os.walk(
        cache_root, topdown=True, followlinks=False
    ):
        directory_names.sort()
        file_names.sort()
        current = Path(directory)
        current_meta = current.lstat()
        if not stat.S_ISDIR(current_meta.st_mode) or stat.S_ISLNK(current_meta.st_mode):
            raise _error("isolated DVC cache contains an unsafe directory")
        observed_directories.add(
            "." if current == cache_root else current.relative_to(cache_root).as_posix()
        )
        for name in directory_names:
            child = current / name
            child_metadata = child.lstat()
            if not stat.S_ISDIR(child_metadata.st_mode) or stat.S_ISLNK(
                child_metadata.st_mode
            ):
                raise _error("isolated DVC cache contains an unsafe directory")
        for name in file_names:
            path = current / name
            relative = path.relative_to(cache_root).as_posix()
            spec = expected.get(relative)
            if spec is None:
                raise _error("isolated DVC cache object inventory is not exact eight")
            observed[relative] = _restored_payload_identity(
                path,
                expected_size=spec.size,
                context="isolated DVC cache object",
            )
    if set(observed) != set(expected):
        raise _error("isolated DVC cache object inventory is not exact eight")
    expected_directories = {"."}
    for relative in expected:
        parent = Path(relative).parent
        while parent != Path("."):
            expected_directories.add(parent.as_posix())
            parent = parent.parent
    if observed_directories != expected_directories:
        raise _error("isolated DVC cache directory inventory is not exact")
    return {
        "object_count": 8,
        "declared_payload_bytes": sum(spec.size for spec in contract.dvc_pointers),
        "exact_pointer_objects_only": True,
        "content_addressed_paths_from_declared_md5": True,
        "payload_objects_opened_by_python": False,
        "payloads_decoded": False,
    }


def _capture_transport_metadata(
    *, clone_root: Path, cache_root: Path, contract: FinalCertificationContract
) -> tuple[
    tuple[tuple[str, tuple[int, int, int, int, int, int, int]], ...],
    tuple[tuple[str, tuple[int, int, int, int, int, int, int]], ...],
]:
    """Capture non-content metadata for later TOCTOU comparison."""

    outputs = tuple(
        (
            spec.output_path,
            _restored_payload_identity(
                clone_root / _require_relative(spec.output_path, context="DVC output"),
                expected_size=spec.size,
                context=f"restored DVC output {spec.output_path}",
            ),
        )
        for spec in contract.dvc_pointers
    )
    cache_objects = tuple(
        (
            (Path("files/md5") / spec.md5[:2] / spec.md5[2:]).as_posix(),
            _restored_payload_identity(
                cache_root / "files/md5" / spec.md5[:2] / spec.md5[2:],
                expected_size=spec.size,
                context=f"content-addressed DVC cache object for {spec.path}",
            ),
        )
        for spec in contract.dvc_pointers
    )
    return outputs, cache_objects


def _require_clean_clone_status(status_payload: str) -> None:
    """Require the ignored DVC checkout/config to leave exact empty Git status."""

    if status_payload:
        raise _error("isolated clone acquired unexpected Git-visible changes")


def _poetry_runtime_root() -> Path:
    """Resolve the host pipx root or its exact retained sandbox bind alias."""

    if _running_from_retained_sandbox_python():
        try:
            retained = SANDBOX_RETAINED_POETRY_ROOT.lstat()
        except OSError as exc:
            raise _error("retained sandbox Poetry root is unavailable") from exc
        if not stat.S_ISDIR(retained.st_mode):
            raise _error("retained sandbox Poetry root is unsafe")
        return SANDBOX_RETAINED_POETRY_ROOT

    try:
        home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (KeyError, OSError) as exc:
        raise _error("local account home for Poetry runtime is unavailable") from exc
    if not home.is_absolute():
        raise _error("local account home for Poetry runtime is unsafe")
    return home / ".local/share/pipx/venvs/poetry"


@dataclass
class VerificationRuntimeLease:
    """All effect-bearing executables and mutable bwrap sources retained by FD."""

    bwrap: AnchoredExecutable
    python: AnchoredPythonInterpreter
    ty: AnchoredExecutable
    poetry: AnchoredPythonScriptRuntime
    clone: DirectoryHandle
    clone_mountpoints: CloneMountpointLease
    sandbox: DirectoryHandle
    socket: DirectoryHandle
    mask_root: DirectoryHandle
    empty_directory: DirectoryHandle
    empty_file: RetainedRegularFile
    private_config_mask: RetainedRegularFile

    @staticmethod
    def _require_directory(handle: DirectoryHandle, *, context: str) -> None:
        metadata = os.fstat(handle.fd)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or (metadata.st_dev, metadata.st_ino) != (handle.device, handle.inode)
        ):
            raise _error(f"{context} retained directory binding drifted")

    def revalidate(self, *, context: str) -> None:
        self.bwrap.revalidate(context=f"{context} bubblewrap")
        self.python.revalidate(context=f"{context} workspace Python")
        self.ty.revalidate(context=f"{context} ty")
        self.poetry.revalidate(context=f"{context} Poetry")
        self.clone_mountpoints.revalidate(
            context=f"{context} clone mountpoints"
        )
        for label, handle in (
            ("clone", self.clone),
            ("sandbox", self.sandbox),
            ("database socket", self.socket),
            ("mask root", self.mask_root),
            ("empty directory mask", self.empty_directory),
        ):
            self._require_directory(handle, context=f"{context} {label}")
        named_empty = os.stat(
            self.empty_directory.path.name,
            dir_fd=self.mask_root.fd,
            follow_symlinks=False,
        )
        if (
            (named_empty.st_dev, named_empty.st_ino)
            != (self.empty_directory.device, self.empty_directory.inode)
            or not stat.S_ISDIR(named_empty.st_mode)
            or stat.S_IMODE(named_empty.st_mode) != 0o555
            or os.listdir(self.empty_directory.fd)
        ):
            raise _error(f"{context} empty directory mask binding drifted")
        self.empty_file.revalidate(context=f"{context} empty file mask")
        self.private_config_mask.revalidate(
            context=f"{context} private configuration mask"
        )

    @property
    def pass_fds(self) -> tuple[int, ...]:
        values = (
            self.bwrap.fd,
            self.python.fd,
            self.python.venv_fd,
            self.ty.fd,
            self.poetry.script.fd,
            self.poetry.interpreter.fd,
            self.poetry.interpreter.venv_fd,
            self.clone.fd,
            *(handle.fd for handle in self.clone_mountpoints.handles),
            self.sandbox.fd,
            self.socket.fd,
            self.mask_root.fd,
            self.empty_directory.fd,
            self.empty_file.fd,
            self.private_config_mask.fd,
        )
        return tuple(dict.fromkeys(values))

    def close(self) -> None:
        first_error: OSError | None = None
        for close in (
            self.private_config_mask.close,
            self.empty_file.close,
            self.empty_directory.close,
            self.poetry.close,
            self.ty.close,
            self.python.close,
            self.bwrap.close,
        ):
            try:
                close()
            except OSError as exc:
                first_error = first_error or exc
        if first_error is not None:
            raise first_error


def _open_verification_runtime(
    *,
    source_root: Path,
    clone: DirectoryHandle,
    clone_mountpoints: CloneMountpointLease,
    sandbox: DirectoryHandle,
    socket_handle: DirectoryHandle,
    mask_root: DirectoryHandle,
) -> VerificationRuntimeLease:
    bwrap: AnchoredExecutable | None = None
    python: AnchoredPythonInterpreter | None = None
    ty: AnchoredExecutable | None = None
    poetry: AnchoredPythonScriptRuntime | None = None
    empty_directory: DirectoryHandle | None = None
    empty_file: RetainedRegularFile | None = None
    private_mask: RetainedRegularFile | None = None
    try:
        bwrap = _open_anchored_executable(
            Path("/"), Path("usr/bin/bwrap"), context="bubblewrap backend"
        )
        python = _open_anchored_python_interpreter(
            source_root,
            Path(".venv/bin/python"),
            context="workspace Python runtime",
        )
        ty = _open_anchored_executable(
            source_root, Path(".venv/bin/ty"), context="ty runtime"
        )
        poetry_root = _poetry_runtime_root()
        poetry = _open_python_script_runtime(
            poetry_root,
            Path("bin/poetry"),
            interpreter_relative=Path("bin/python"),
            context="Poetry runtime",
        )
        empty_fd = os.open(
            "empty",
            os.O_RDONLY
            | os.O_DIRECTORY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=mask_root.fd,
        )
        empty_metadata = os.fstat(empty_fd)
        empty_directory = DirectoryHandle(
            mask_root.path / "empty",
            empty_fd,
            empty_metadata.st_dev,
            empty_metadata.st_ino,
        )
        empty_file = _open_retained_regular_file(
            mask_root,
            "empty-file",
            allowed_modes=frozenset({0o400}),
            context="empty sandbox file mask",
        )
        private_mask = _open_retained_regular_file(
            mask_root,
            "empty-private-config",
            allowed_modes=frozenset({0o600}),
            context="private configuration sandbox mask",
        )
        runtime = VerificationRuntimeLease(
            bwrap=bwrap,
            python=python,
            ty=ty,
            poetry=poetry,
            clone=clone,
            clone_mountpoints=clone_mountpoints,
            sandbox=sandbox,
            socket=socket_handle,
            mask_root=mask_root,
            empty_directory=empty_directory,
            empty_file=empty_file,
            private_config_mask=private_mask,
        )
        runtime.revalidate(context="initial verification runtime")
        version = _run_python_script_runtime(
            poetry,
            ("--version",),
            cwd=source_root,
            portable_argv=("poetry", "--version"),
            environment={"POETRY_NO_INTERACTION": "1"},
            timeout_seconds=120,
            context="Poetry verification-runtime version",
        )
        if not re.fullmatch(
            r"Poetry \(version [0-9]+(?:\.[0-9]+){1,3}\)",
            version.stdout.strip(),
        ):
            raise _error("read-only Poetry runtime version probe failed")
        return runtime
    except BaseException:
        for value in (
            private_mask,
            empty_file,
            empty_directory,
            poetry,
            ty,
            python,
            bwrap,
        ):
            if value is not None:
                value.close()
        raise


def _retained_relative_kind(
    root_fd: int,
    path_text: str,
    *,
    context: str,
) -> str | None:
    """Classify one path below a retained root without following symlinks."""

    relative = _require_relative(path_text.rstrip("/"), context=context)
    descriptor = os.dup(root_fd)
    try:
        for component in relative.parts[:-1]:
            try:
                child = os.open(
                    component,
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=descriptor,
                )
            except FileNotFoundError:
                return None
            except OSError as exc:
                raise _error(f"{context} ancestor is unsafe") from exc
            os.close(descriptor)
            descriptor = child
        try:
            metadata = os.stat(
                relative.name,
                dir_fd=descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return None
        if stat.S_ISDIR(metadata.st_mode):
            return "directory"
        if stat.S_ISREG(metadata.st_mode):
            return "regular"
        raise _error(f"{context} resolves to an unsafe inode")
    finally:
        os.close(descriptor)


def _expected_bwrap_template(
    contract: FinalCertificationContract,
) -> list[str]:
    """Return the one portable bubblewrap prefix sealed by the contract."""

    if (
        contract.forbidden_read_prefixes != SANDBOX_ABSENT_FORBIDDEN_PREFIXES
        or contract.forbidden_read_paths != SANDBOX_MASKED_FORBIDDEN_PATHS
        or dict(contract.forbidden_read_prefix_dispositions)
        != {
            path: "require_absent" for path in SANDBOX_ABSENT_FORBIDDEN_PREFIXES
        }
        or dict(contract.forbidden_read_path_dispositions)
        != {
            path: "require_regular_then_empty_file_mask"
            for path in SANDBOX_MASKED_FORBIDDEN_PATHS
        }
    ):
        raise _error("bubblewrap forbidden-path topology drifted")
    template = [
        "/usr/bin/bwrap",
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--cap-drop",
        "ALL",
    ]
    for system_path in ("/usr", "/bin", "/lib", "/lib64", "/etc"):
        template.extend(["--ro-bind", system_path, system_path])
    template.extend(["--ro-bind", "<OWNED_CLONE>", "/workspace"])
    template.extend(["--ro-bind", "<READ_ONLY_HOST_VENV>", "/workspace/.venv"])
    template.extend(["--ro-bind", "<READ_ONLY_POETRY_VENV>", "/cert-poetry"])
    template.extend(["--ro-bind", "<RETAINED_SYSTEM_PYTHON>", "/cert-python"])
    template.extend(["--ro-bind", "<RETAINED_TY>", "/cert-ty"])
    template.extend(
        ["--ro-bind", "<RETAINED_POETRY_PYTHON>", "/cert-poetry-python"]
    )
    template.extend(
        ["--ro-bind", "<RETAINED_POETRY_SCRIPT>", "/cert-poetry-script"]
    )
    template.extend(["--bind", "<OWNED_SANDBOX_TMP>", "/workspace/tmp"])
    template.extend(["--bind", "<OWNED_DB_SOCKET>", DB_SOCKET_ROOT])
    for path_text in SANDBOX_MASKED_FORBIDDEN_PATHS:
        template.extend(
            ["--ro-bind", "<EMPTY_FILE_MASK>", "/workspace/" + path_text]
        )
    for spec in contract.dvc_pointers:
        template.extend(
            ["--ro-bind", "<EMPTY_FILE_MASK>", "/workspace/" + spec.output_path]
        )
    template.extend(
        [
            "--ro-bind",
            "<EMPTY_FILE_MASK>",
            "/workspace/" + LOCAL_DVC_CONFIG_PATH.as_posix(),
        ]
    )
    template.extend(
        [
            "--tmpfs",
            "/tmp",
            "--dev",
            "/dev",
            "--proc",
            "/proc",
            "--chdir",
            "/workspace",
            "--",
        ]
    )
    return template


def _make_bwrap_prefix(
    *,
    runtime: VerificationRuntimeLease,
    contract: FinalCertificationContract,
) -> tuple[list[str], list[str]]:
    real = [
        runtime.bwrap.proc_path,
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--cap-drop",
        "ALL",
    ]
    template = [
        "/usr/bin/bwrap",
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--cap-drop",
        "ALL",
    ]
    for system_path in ("/usr", "/bin", "/lib", "/lib64", "/etc"):
        real.extend(["--ro-bind", system_path, system_path])
        template.extend(["--ro-bind", system_path, system_path])
    real.extend(["--ro-bind", f"/proc/self/fd/{runtime.clone.fd}", "/workspace"])
    template.extend(["--ro-bind", "<OWNED_CLONE>", "/workspace"])
    real.extend(
        ["--ro-bind", runtime.python.venv_proc_path, "/workspace/.venv"]
    )
    template.extend(["--ro-bind", "<READ_ONLY_HOST_VENV>", "/workspace/.venv"])
    real.extend(
        [
            "--ro-bind",
            runtime.poetry.interpreter.venv_proc_path,
            "/cert-poetry",
        ]
    )
    template.extend(["--ro-bind", "<READ_ONLY_POETRY_VENV>", "/cert-poetry"])
    real.extend(["--ro-bind", runtime.python.proc_path, "/cert-python"])
    template.extend(["--ro-bind", "<RETAINED_SYSTEM_PYTHON>", "/cert-python"])
    real.extend(["--ro-bind", runtime.ty.proc_path, "/cert-ty"])
    template.extend(["--ro-bind", "<RETAINED_TY>", "/cert-ty"])
    real.extend(
        ["--ro-bind", runtime.poetry.interpreter.proc_path, "/cert-poetry-python"]
    )
    template.extend(
        ["--ro-bind", "<RETAINED_POETRY_PYTHON>", "/cert-poetry-python"]
    )
    real.extend(["--ro-bind", runtime.poetry.script.proc_path, "/cert-poetry-script"])
    template.extend(
        ["--ro-bind", "<RETAINED_POETRY_SCRIPT>", "/cert-poetry-script"]
    )
    real.extend(["--bind", f"/proc/self/fd/{runtime.sandbox.fd}", "/workspace/tmp"])
    template.extend(["--bind", "<OWNED_SANDBOX_TMP>", "/workspace/tmp"])
    real.extend(["--bind", f"/proc/self/fd/{runtime.socket.fd}", DB_SOCKET_ROOT])
    template.extend(["--bind", "<OWNED_DB_SOCKET>", DB_SOCKET_ROOT])
    for prefix in contract.forbidden_read_prefixes:
        kind = _retained_relative_kind(
            runtime.clone.fd,
            str(prefix),
            context=f"forbidden prefix {prefix}",
        )
        if (
            contract.forbidden_read_prefix_dispositions.get(prefix)
            != "require_absent"
            or kind is not None
        ):
            raise _error(f"forbidden prefix expected absent in P-CERT: {prefix}")
    for path_text in contract.forbidden_read_paths:
        kind = _retained_relative_kind(
            runtime.clone.fd,
            str(path_text),
            context=f"forbidden path {path_text}",
        )
        if (
            contract.forbidden_read_path_dispositions.get(path_text)
            != "require_regular_then_empty_file_mask"
            or kind != "regular"
        ):
            raise _error(f"forbidden path is not a regular masked file: {path_text}")
        destination = "/workspace/" + path_text
        real.extend(["--ro-bind", runtime.empty_file.proc_path, destination])
        template.extend(["--ro-bind", "<EMPTY_FILE_MASK>", destination])
    for spec in contract.dvc_pointers:
        destination = "/workspace/" + spec.output_path
        if _retained_relative_kind(
            runtime.clone.fd,
            spec.output_path,
            context=f"restored payload mask {spec.output_path}",
        ) != "regular":
            raise _error(f"restored payload mask source is absent: {spec.output_path}")
        real.extend(["--ro-bind", runtime.empty_file.proc_path, destination])
        template.extend(["--ro-bind", "<EMPTY_FILE_MASK>", destination])
    if _retained_relative_kind(
        runtime.clone.fd,
        LOCAL_DVC_CONFIG_PATH.as_posix(),
        context="private DVC configuration mask",
    ) != "regular":
        raise _error("private DVC configuration mask source is absent")
    real.extend(
        [
            "--ro-bind",
            runtime.private_config_mask.proc_path,
            "/workspace/" + LOCAL_DVC_CONFIG_PATH.as_posix(),
        ]
    )
    template.extend(
        [
            "--ro-bind",
            "<EMPTY_FILE_MASK>",
            "/workspace/" + LOCAL_DVC_CONFIG_PATH.as_posix(),
        ]
    )
    suffix = [
        "--tmpfs",
        "/tmp",
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--chdir",
        "/workspace",
        "--",
    ]
    real.extend(suffix)
    template.extend(suffix)
    expected_template = _expected_bwrap_template(contract)
    if template != expected_template:
        raise _error("bubblewrap portable template construction drifted")
    return real, expected_template


def _sandbox_smoke_error(
    *, category: str, returncode: int | None
) -> FinalCertificationBuildError:
    if category not in {"sandbox_launch_failure", "sandbox_handshake_failure"}:
        raise ValueError("sandbox smoke failure category is not allowlisted")
    evidence = CommandFailureEvidence(
        stage="sandbox_smoke",
        sanitized_command=SANDBOX_SMOKE_PORTABLE_COMMAND,
        returncode=returncode,
        safe_stderr_category=category,
    )
    return _error(
        "sandbox smoke failed closed: "
        + json.dumps(evidence.as_record(), sort_keys=True, separators=(",", ":")),
        command_failure=evidence,
    )


def _run_sandbox_smoke(
    *,
    source_root: Path,
    runtime: VerificationRuntimeLease,
    contract: FinalCertificationContract,
    namespace_validator: Callable[[str], None] | None = None,
) -> Mapping[str, Any]:
    """Prove the real bwrap/mount topology with one removable empty marker."""

    policy = dict(contract.sandbox_smoke_policy)
    if policy != expected_sandbox_smoke_policy():
        raise _error("sandbox smoke policy drifted")
    try:
        os.stat(
            SANDBOX_SMOKE_MARKER_NAME,
            dir_fd=runtime.sandbox.fd,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise _sandbox_smoke_error(
            category="sandbox_handshake_failure", returncode=None
        ) from exc
    else:
        raise _sandbox_smoke_error(
            category="sandbox_handshake_failure", returncode=None
        )
    if namespace_validator is not None:
        namespace_validator("before_sandbox_smoke")
    runtime.revalidate(context="before sandbox smoke")
    try:
        bwrap, _template = _make_bwrap_prefix(runtime=runtime, contract=contract)
        result = _run(
            SANDBOX_SMOKE_PORTABLE_COMMAND,
            cwd=source_root,
            execution_argv=(
                *bwrap,
                "/usr/bin/touch",
                f"/workspace/tmp/{SANDBOX_SMOKE_MARKER_NAME}",
            ),
            inherit_environment=False,
            timeout_seconds=120,
            require_success=False,
            portable_argv=SANDBOX_SMOKE_PORTABLE_COMMAND,
            pass_fds=runtime.pass_fds,
            failure_stage="sandbox smoke",
        )
    except BaseException as exc:
        returncode = (
            exc.command_failure.returncode
            if isinstance(exc, FinalCertificationBuildError)
            and exc.command_failure is not None
            else None
        )
        raise _sandbox_smoke_error(
            category="sandbox_launch_failure", returncode=returncode
        ) from None
    try:
        runtime.revalidate(context="after sandbox smoke")
    except BaseException:
        raise _sandbox_smoke_error(
            category="sandbox_handshake_failure",
            returncode=cast(int | None, result.record.get("returncode")),
        ) from None
    marker: OwnedFileAt | None = None
    marker_valid = False
    try:
        metadata = os.stat(
            SANDBOX_SMOKE_MARKER_NAME,
            dir_fd=runtime.sandbox.fd,
            follow_symlinks=False,
        )
    except OSError:
        metadata = None
    if metadata is not None:
        marker = OwnedFileAt(
            runtime.sandbox,
            SANDBOX_SMOKE_MARKER_NAME,
            metadata.st_dev,
            metadata.st_ino,
        )
        marker_valid = (
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_nlink == 1
            and metadata.st_size == 0
            and stat.S_IMODE(metadata.st_mode) in {0o600, 0o644}
        )
    if marker_valid and marker is not None:
        try:
            _unlink_owned_at(marker, context="owned sandbox smoke marker")
        except BaseException:
            raise _sandbox_smoke_error(
                category="sandbox_handshake_failure",
                returncode=cast(int | None, result.record.get("returncode")),
            ) from None
    if (
        result.record.get("returncode") != 0
        or not marker_valid
        or result.stdout
        or result.stderr
    ):
        category = (
            "sandbox_launch_failure"
            if result.record.get("returncode") != 0 and metadata is None
            else "sandbox_handshake_failure"
        )
        raise _sandbox_smoke_error(
            category=category,
            returncode=cast(int | None, result.record.get("returncode")),
        )
    try:
        os.stat(
            SANDBOX_SMOKE_MARKER_NAME,
            dir_fd=runtime.sandbox.fd,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        pass
    else:
        raise _sandbox_smoke_error(
            category="sandbox_handshake_failure", returncode=0
        )
    runtime.revalidate(context="after sandbox smoke marker cleanup")
    if namespace_validator is not None:
        namespace_validator("after_sandbox_smoke")
    return {"status": "passed", **policy}


def _prepare_masks(mask_root: DirectoryHandle) -> None:
    empty: DirectoryHandle | None = None
    files: list[OwnedFileAt] = []
    try:
        empty = _mkdir_owned_at(
            mask_root,
            "empty",
            mode=0o555,
            context="empty sandbox directory mask",
        )
        for name, mode in (("empty-file", 0o400), ("empty-private-config", 0o600)):
            files.append(_create_owned_file_at(mask_root, name, b"", mode=mode))
        os.fsync(mask_root.fd)
    except BaseException:
        for entry in reversed(files):
            try:
                _unlink_owned_at(entry, context=f"failed sandbox mask {entry.name}")
            except BaseException:
                pass
        if empty is not None:
            try:
                _remove_owned_empty_directory_at(
                    mask_root,
                    empty.path.name,
                    device=empty.device,
                    inode=empty.inode,
                    context="failed empty sandbox directory mask",
                )
            except BaseException:
                pass
        raise
    finally:
        if empty is not None:
            empty.close()


def _require_postgres_socket_directory(
    socket_handle: DirectoryHandle,
    *,
    context: str,
) -> None:
    metadata = os.fstat(socket_handle.fd)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or (metadata.st_dev, metadata.st_ino)
        != (socket_handle.device, socket_handle.inode)
    ):
        raise _error(f"{context} retained socket directory binding drifted")


def _postgres_socket_entry_kind(metadata: os.stat_result) -> str:
    if stat.S_ISSOCK(metadata.st_mode):
        return "socket"
    if stat.S_ISREG(metadata.st_mode):
        return "regular_file"
    raise _error("PostgreSQL socket inventory contains an unsupported inode type")


def _observe_owned_postgres_socket_inventory(
    socket_handle: DirectoryHandle,
    *,
    retry_expected_subset: bool,
) -> tuple[OwnedPostgresSocketEntry, ...] | None:
    """Claim exact2, allowing only a metadata-safe expected subset to retry."""

    _require_postgres_socket_directory(
        socket_handle,
        context="PostgreSQL socket inventory capture",
    )
    expected = dict(POSTGRES_SOCKET_ENTRY_SPECS)
    expected_names = set(expected)
    observed_names = set(os.listdir(socket_handle.fd))
    if not observed_names.issubset(expected_names):
        raise _error("PostgreSQL socket inventory contains an unexpected name")

    claims: list[OwnedPostgresSocketEntry] = []
    for name, expected_kind in POSTGRES_SOCKET_ENTRY_SPECS:
        if name not in observed_names:
            continue
        try:
            first = os.stat(name, dir_fd=socket_handle.fd, follow_symlinks=False)
            second = os.stat(name, dir_fd=socket_handle.fd, follow_symlinks=False)
        except FileNotFoundError as exc:
            raise _error(
                "PostgreSQL socket inventory changed while being inspected"
            ) from exc
        first_kind = _postgres_socket_entry_kind(first)
        second_kind = _postgres_socket_entry_kind(second)
        if first_kind != expected_kind or second_kind != expected_kind:
            raise _error("PostgreSQL socket inventory inode type drifted")
        if first.st_nlink != 1 or second.st_nlink != 1:
            raise _error("PostgreSQL socket inventory link count drifted")
        if (first.st_dev, first.st_ino) != (second.st_dev, second.st_ino):
            raise _error("PostgreSQL socket inventory identity drifted")
        claims.append(
            OwnedPostgresSocketEntry(
                name=name,
                device=first.st_dev,
                inode=first.st_ino,
                kind=first_kind,
                link_count=first.st_nlink,
            )
        )

    repeated_names = set(os.listdir(socket_handle.fd))
    if not repeated_names.issubset(expected_names):
        raise _error("PostgreSQL socket inventory contains an unexpected name")
    if repeated_names != observed_names:
        raise _error("PostgreSQL socket inventory changed while being inspected")
    if observed_names != expected_names:
        if not retry_expected_subset:
            raise _error("PostgreSQL socket inventory is not exact two")
        # Only a stable, fully inspected subset is retryable.  A changed set
        # was rejected above rather than silently adopting its new entries.
        return None
    return tuple(claims)


def _capture_owned_postgres_socket_inventory(
    socket_handle: DirectoryHandle,
) -> tuple[OwnedPostgresSocketEntry, ...]:
    """Claim only the exact server socket and lock by retained-dirfd identity."""

    claims = _observe_owned_postgres_socket_inventory(
        socket_handle,
        retry_expected_subset=False,
    )
    if claims is None:  # pragma: no cover - closed by retry_expected_subset=False
        raise _error("PostgreSQL socket inventory is not exact two")
    return claims


def _revalidate_owned_postgres_socket_inventory(
    socket_handle: DirectoryHandle,
    claims: Sequence[OwnedPostgresSocketEntry],
) -> None:
    """Revalidate the same exact2 claims without adopting current names."""

    _require_postgres_socket_directory(
        socket_handle,
        context="PostgreSQL socket inventory revalidation",
    )
    expected = dict(POSTGRES_SOCKET_ENTRY_SPECS)
    claim_by_name = {claim.name: claim for claim in claims}
    if (
        len(claim_by_name) != len(claims)
        or set(claim_by_name) != set(expected)
        or any(
            claim.kind != expected.get(claim.name) or claim.link_count != 1
            for claim in claims
        )
    ):
        raise _error("PostgreSQL socket revalidation claim set is invalid")
    if set(os.listdir(socket_handle.fd)) != set(expected):
        raise _error("PostgreSQL socket claims changed before revalidation")
    for name, expected_kind in POSTGRES_SOCKET_ENTRY_SPECS:
        claim = claim_by_name[name]
        try:
            first = os.stat(name, dir_fd=socket_handle.fd, follow_symlinks=False)
            second = os.stat(name, dir_fd=socket_handle.fd, follow_symlinks=False)
        except FileNotFoundError as exc:
            raise _error("PostgreSQL socket claim disappeared") from exc
        for metadata in (first, second):
            if (
                _postgres_socket_entry_kind(metadata) != expected_kind
                or metadata.st_nlink != claim.link_count
                or (metadata.st_dev, metadata.st_ino)
                != (claim.device, claim.inode)
            ):
                raise _error("PostgreSQL socket claim replacement detected")
    if set(os.listdir(socket_handle.fd)) != set(expected):
        raise _error("PostgreSQL socket claims changed during revalidation")


def _unlink_owned_postgres_socket_entry(
    socket_handle: DirectoryHandle,
    claim: OwnedPostgresSocketEntry,
) -> None:
    """Detach one claimed residual twice before unlinking its retained inode."""

    tombstone = _detach_owned_name_at(
        socket_handle,
        claim.name,
        device=claim.device,
        inode=claim.inode,
        require_directory=False,
        context=f"owned PostgreSQL residual {claim.kind}",
        expected_nondirectory_kind=claim.kind,
    )
    descriptor: int | None = None
    try:
        descriptor = os.open(
            tombstone,
            getattr(os, "O_PATH", os.O_RDONLY)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=socket_handle.fd,
        )
        opened = os.fstat(descriptor)
        named = os.stat(
            tombstone,
            dir_fd=socket_handle.fd,
            follow_symlinks=False,
        )
        if (
            (opened.st_dev, opened.st_ino) != (claim.device, claim.inode)
            or (named.st_dev, named.st_ino) != (claim.device, claim.inode)
            or _postgres_socket_entry_kind(opened) != claim.kind
            or _postgres_socket_entry_kind(named) != claim.kind
            or opened.st_nlink != claim.link_count
            or named.st_nlink != claim.link_count
        ):
            raise _error("PostgreSQL residual cleanup capture drifted")
        tombstone = _detach_owned_name_at(
            socket_handle,
            tombstone,
            device=claim.device,
            inode=claim.inode,
            require_directory=False,
            context=f"owned PostgreSQL residual {claim.kind} final capture",
            owned_fd=descriptor,
            expected_nondirectory_kind=claim.kind,
        )
        final_named = os.stat(
            tombstone,
            dir_fd=socket_handle.fd,
            follow_symlinks=False,
        )
        if (
            (final_named.st_dev, final_named.st_ino)
            != (claim.device, claim.inode)
            or _postgres_socket_entry_kind(final_named) != claim.kind
            or final_named.st_nlink != claim.link_count
        ):
            raise _error("PostgreSQL residual final cleanup capture drifted")
        os.unlink(tombstone, dir_fd=socket_handle.fd)
        os.fsync(socket_handle.fd)
        retained = os.fstat(descriptor)
        if (
            (retained.st_dev, retained.st_ino) != (claim.device, claim.inode)
            or retained.st_nlink != claim.link_count - 1
        ):
            raise _error("PostgreSQL residual retained inode was not unlinked")
    except BaseException:
        try:
            _rename_noreplace_at(
                socket_handle.fd,
                tombstone,
                socket_handle.fd,
                claim.name,
            )
            os.fsync(socket_handle.fd)
        except OSError:
            pass
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _cleanup_owned_postgres_socket_inventory(
    socket_handle: DirectoryHandle,
    claims: Sequence[OwnedPostgresSocketEntry],
) -> int:
    """Remove only unchanged, previously claimed socket artifacts by dirfd."""

    _require_postgres_socket_directory(
        socket_handle,
        context="PostgreSQL socket cleanup",
    )
    expected_specs = dict(POSTGRES_SOCKET_ENTRY_SPECS)
    claim_by_name = {claim.name: claim for claim in claims}
    if (
        len(claim_by_name) != len(claims)
        or set(claim_by_name) not in (set(), set(expected_specs))
        or any(
            claim.kind != expected_specs.get(claim.name)
            or claim.link_count != 1
            for claim in claims
        )
    ):
        raise _error("PostgreSQL socket cleanup claim set is invalid")
    current_names = set(os.listdir(socket_handle.fd))
    if not current_names.issubset(claim_by_name):
        raise _error("PostgreSQL socket cleanup refuses an unclaimed entry")
    observed: dict[str, tuple[int, int, str, int]] = {}
    for name in current_names:
        metadata = os.stat(name, dir_fd=socket_handle.fd, follow_symlinks=False)
        observed[name] = (
            metadata.st_dev,
            metadata.st_ino,
            _postgres_socket_entry_kind(metadata),
            metadata.st_nlink,
        )
        claim = claim_by_name[name]
        if observed[name] != (
            claim.device,
            claim.inode,
            claim.kind,
            claim.link_count,
        ):
            raise _error("PostgreSQL socket cleanup identity drifted")
    if set(os.listdir(socket_handle.fd)) != current_names:
        raise _error("PostgreSQL socket cleanup inventory changed before unlink")
    removed = 0
    for name, _kind in POSTGRES_SOCKET_ENTRY_SPECS:
        if name not in current_names:
            continue
        claim = claim_by_name[name]
        if observed[name] != (
            claim.device,
            claim.inode,
            claim.kind,
            claim.link_count,
        ):
            raise _error("PostgreSQL socket cleanup identity changed before detach")
        _unlink_owned_postgres_socket_entry(socket_handle, claim)
        removed += 1
    os.fsync(socket_handle.fd)
    if os.listdir(socket_handle.fd):
        raise _error("PostgreSQL socket directory is not empty after cleanup")
    _require_postgres_socket_directory(
        socket_handle,
        context="PostgreSQL socket cleanup completion",
    )
    return removed


def _probe_owned_postgres_pid1(
    owner: OwnedPostgres,
    *,
    context: str,
) -> tuple[bool, Mapping[str, Any]]:
    """Distinguish entrypoint initialization from the final PID1 postgres."""

    _require_owned_postgres_binding(owner, context=f"{context} before PID1 probe")
    probe = _run(
        (
            "/usr/bin/docker",
            "exec",
            owner.container_id,
            "cat",
            POSTGRES_PID1_COMM_PATH,
        ),
        cwd=PROJECT_ROOT,
        portable_argv=(
            "docker",
            "exec",
            "<OWNED_CONTAINER>",
            "<POSTGRES_PID1_COMM_PROBE>",
        ),
        timeout_seconds=10,
        require_success=False,
        failure_stage="postgres final PID1 probe",
    )
    _require_owned_postgres_binding(owner, context=f"{context} after PID1 probe")
    if probe.record.get("returncode") != 0 or probe.stderr:
        raise _error("PostgreSQL final PID1 probe failed closed")
    if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}\n", probe.stdout) is None:
        raise _error("PostgreSQL PID1 probe output is malformed")
    return probe.stdout == f"{POSTGRES_FINAL_PID1_COMM}\n", dict(probe.record)


def _probe_owned_postgres_readiness(
    owner: OwnedPostgres,
    *,
    context: str,
) -> CommandResult:
    """Probe the exact owned Unix socket without serializing its absolute path."""

    _require_owned_postgres_binding(owner, context=f"{context} before readiness")
    probe = _run(
        (
            "/usr/bin/docker",
            "exec",
            owner.container_id,
            "pg_isready",
            "-q",
            "-h",
            CONTAINER_POSTGRES_SOCKET_ROOT,
            "-p",
            "5432",
            "-U",
            "postgres",
            "-d",
            DB_NAME,
        ),
        cwd=PROJECT_ROOT,
        portable_argv=(
            "docker",
            "exec",
            "<OWNED_CONTAINER>",
            "pg_isready",
            "-q",
            "-h",
            "<CONTAINER_POSTGRES_SOCKET>",
            "-p",
            "5432",
            "-U",
            "postgres",
            "-d",
            DB_NAME,
        ),
        timeout_seconds=10,
        require_success=False,
        failure_stage="postgres final readiness probe",
    )
    _require_owned_postgres_binding(owner, context=f"{context} after readiness")
    if probe.stdout or probe.stderr:
        raise _error("PostgreSQL quiet readiness probe emitted output")
    return probe


def _start_owned_postgres(
    socket_handle: DirectoryHandle,
    *,
    namespace_validator: Callable[[str], None] | None = None,
    owner_handoff: Callable[[OwnedPostgres], None] | None = None,
) -> tuple[OwnedPostgres, Mapping[str, Any]]:
    _require_postgres_socket_directory(
        socket_handle,
        context="PostgreSQL startup",
    )
    if os.listdir(socket_handle.fd):
        raise _error("PostgreSQL socket directory is not initially empty")
    socket_root = socket_handle.path
    container_name = f"closure-phase4-cert-{secrets.token_hex(12)}"
    portable_paths = expected_postgres_portable_path_policy()
    if namespace_validator is not None:
        namespace_validator("before_postgres_start")
    preexisting_returncode, preexisting_identity = _inspect_container_identity(
        container_name
    )
    if preexisting_returncode == 0 or preexisting_identity:
        raise _error("random PostgreSQL container name was already occupied")
    try:
        run = _run(
            (
                "/usr/bin/docker",
                "run",
                "--detach",
                "--rm",
                "--pull=never",
                "--network",
                "none",
                "--name",
                container_name,
                "--env",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                "--env",
                f"POSTGRES_DB={DB_NAME}",
                "--volume",
                f"{socket_root}:{CONTAINER_POSTGRES_SOCKET_ROOT}",
                "--tmpfs",
                "/var/lib/postgresql/data:rw,size=512m",
                "--tmpfs",
                "/tmp:rw,size=64m",
                POSTGRES_IMAGE,
                "-c",
                f"unix_socket_directories={CONTAINER_POSTGRES_SOCKET_ROOT}",
                "-c",
                "listen_addresses=",
            ),
            cwd=PROJECT_ROOT,
            portable_argv=(
                "docker",
                "run",
                "--detach",
                "--rm",
                "--pull=never",
                "--network",
                "none",
                "--name",
                "<OWNED_CONTAINER>",
                "--env",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                "--env",
                f"POSTGRES_DB={DB_NAME}",
                "--volume",
                portable_paths["volume"],
                "--tmpfs",
                portable_paths["data_tmpfs"],
                "--tmpfs",
                portable_paths["runtime_tmpfs"],
                POSTGRES_IMAGE,
                "-c",
                portable_paths["unix_socket_directories"],
                "-c",
                "listen_addresses=",
            ),
            timeout_seconds=120,
            failure_stage="postgres start",
        )
    except BaseException as primary:
        # Docker can accept ``run`` and then lose the client response.  Since
        # the cryptographically random name was proven absent immediately
        # beforehand, bind a subsequently visible exact ID and remove only
        # that ID.  Ambiguous/malformed reuse is preserved and fails closed.
        try:
            returncode, recovered_id = _inspect_container_identity(container_name)
            if returncode != 0:
                raise primary
            if not SHA256_RE.fullmatch(recovered_id):
                raise _error("Docker run failure recovery identity is ambiguous")
            recovered = OwnedPostgres(
                name=container_name,
                container_id=recovered_id,
            )
            _require_owned_postgres_binding(
                recovered,
                context="PostgreSQL failed-run recovery",
            )
            if owner_handoff is not None:
                owner_handoff(recovered)
                raise primary
            _stop_owned_postgres(recovered, socket_handle=socket_handle)
        except BaseException as cleanup_exc:
            if cleanup_exc is primary:
                raise
            raise _error("Docker run failure cleanup failed closed") from cleanup_exc
        raise primary
    container_id = run.stdout.strip()
    malformed_run_identity = not bool(SHA256_RE.fullmatch(container_id))
    if malformed_run_identity:
        inspect_returncode, inspected_identity = _inspect_container_identity(
            container_name
        )
        if inspect_returncode != 0 or not SHA256_RE.fullmatch(inspected_identity):
            raise _error(
                "Docker run identity was malformed and no owned container could be bound"
            )
        container_id = inspected_identity
    owner = OwnedPostgres(name=container_name, container_id=container_id)
    try:
        _require_owned_postgres_binding(owner, context="PostgreSQL startup")
        if owner_handoff is not None:
            owner_handoff(owner)
        if malformed_run_identity:
            raise _error("Docker did not return one exact owned container ID")
        if namespace_validator is not None:
            namespace_validator("after_postgres_start")
        for attempt in range(POSTGRES_STABILITY_MAX_ATTEMPTS):
            if namespace_validator is not None:
                namespace_validator(f"before_postgres_probe_{attempt}")
            # Do not observe or claim the socket inventory until the final
            # PID1 and explicit readiness probes both pass.  The image's
            # entrypoint can own an exact-two temporary postmaster inventory;
            # the retryable-inventory policy applies only once a capture is
            # eligible below, so that transient inventory is never adopted.
            final_pid1, pid1_record = _probe_owned_postgres_pid1(
                owner,
                context=f"PostgreSQL stability attempt {attempt}",
            )
            if not final_pid1:
                if namespace_validator is not None:
                    namespace_validator(f"after_postgres_probe_{attempt}")
                if attempt + 1 < POSTGRES_STABILITY_MAX_ATTEMPTS:
                    time.sleep(POSTGRES_STABILITY_INTERVAL_SECONDS)
                continue
            probe = _probe_owned_postgres_readiness(
                owner,
                context=f"PostgreSQL stability attempt {attempt}",
            )
            if probe.record.get("returncode") != 0:
                if namespace_validator is not None:
                    namespace_validator(f"after_postgres_probe_{attempt}")
                if attempt + 1 < POSTGRES_STABILITY_MAX_ATTEMPTS:
                    time.sleep(POSTGRES_STABILITY_INTERVAL_SECONDS)
                continue
            _require_owned_postgres_binding(
                owner,
                context=f"PostgreSQL socket capture {attempt} before",
            )
            socket_inventory = _observe_owned_postgres_socket_inventory(
                socket_handle,
                retry_expected_subset=True,
            )
            _require_owned_postgres_binding(
                owner,
                context=f"PostgreSQL socket capture {attempt} after",
            )
            if socket_inventory is None:
                if namespace_validator is not None:
                    namespace_validator(f"after_postgres_probe_{attempt}")
                if attempt + 1 < POSTGRES_STABILITY_MAX_ATTEMPTS:
                    time.sleep(POSTGRES_STABILITY_INTERVAL_SECONDS)
                continue
            owner = OwnedPostgres(
                name=owner.name,
                container_id=owner.container_id,
                socket_inventory=socket_inventory,
            )
            if owner_handoff is not None:
                owner_handoff(owner)
            final_pid1_after_claim, pid1_revalidation_record = (
                _probe_owned_postgres_pid1(
                    owner,
                    context=f"PostgreSQL post-claim stability {attempt}",
                )
            )
            if not final_pid1_after_claim:
                raise _error("PostgreSQL final PID1 changed after socket claim")
            readiness_revalidation = _probe_owned_postgres_readiness(
                owner,
                context=f"PostgreSQL post-claim stability {attempt}",
            )
            if readiness_revalidation.record.get("returncode") != 0:
                raise _error("PostgreSQL readiness changed after socket claim")
            if namespace_validator is not None:
                namespace_validator(f"before_postgres_claim_revalidation_{attempt}")
            _require_owned_postgres_binding(
                owner,
                context=f"PostgreSQL socket revalidation {attempt} before",
            )
            _revalidate_owned_postgres_socket_inventory(
                socket_handle,
                owner.socket_inventory,
            )
            _require_owned_postgres_binding(
                owner,
                context=f"PostgreSQL socket revalidation {attempt} after",
            )
            if namespace_validator is not None:
                namespace_validator(f"after_postgres_probe_{attempt}")
            return owner, {
                "image": POSTGRES_IMAGE,
                "network": "none",
                "transport": "owned_unix_socket",
                "database": DB_NAME,
                "credentials_serialized": False,
                "run_command": dict(run.record),
                "pid1_command": dict(pid1_record),
                "readiness_command": dict(probe.record),
                "pid1_revalidation_command": dict(pid1_revalidation_record),
                "readiness_revalidation_command": dict(
                    readiness_revalidation.record
                ),
                "startup_stability_policy": (
                    expected_postgres_startup_stability_policy()
                ),
            }
        raise _error("owned PostgreSQL container did not become stably ready")
    except BaseException:
        if owner_handoff is not None:
            raise
        try:
            _stop_owned_postgres(owner, socket_handle=socket_handle)
        except BaseException as cleanup_exc:
            raise _error("owned PostgreSQL startup cleanup failed closed") from cleanup_exc
        raise


def _inspect_container_identity(target: str) -> tuple[int, str]:
    result = _run(
        (
            "/usr/bin/docker",
            "inspect",
            "--format",
            "{{.Id}}",
            target,
        ),
        cwd=PROJECT_ROOT,
        portable_argv=(
            "docker",
            "inspect",
            "--format",
            "<CONTAINER_ID>",
            "<OWNED_CONTAINER>",
        ),
        timeout_seconds=30,
        require_success=False,
        failure_stage="postgres identity inspection",
    )
    value = result.stdout.strip()
    returncode = cast(int, result.record["returncode"])
    stderr = result.stderr.strip()
    if returncode == 0:
        if not SHA256_RE.fullmatch(value) or stderr:
            raise _error("Docker inspect returned an ambiguous container identity")
        return returncode, value
    exact_absence_errors = {
        f"Error: No such object: {target}",
        f"Error: No such container: {target}",
        f"error: no such object: {target}",
        f"error: no such container: {target}",
    }
    if returncode != 1 or value or stderr not in exact_absence_errors:
        raise _error("Docker inspect did not prove exact container absence")
    return returncode, ""


def _require_owned_postgres_binding(owner: OwnedPostgres, *, context: str) -> None:
    if (
        not re.fullmatch(r"closure-phase4-cert-[0-9a-f]{24}", owner.name)
        or not SHA256_RE.fullmatch(owner.container_id)
    ):
        raise _error("owned PostgreSQL container identity drifted")
    name_returncode, name_identity = _inspect_container_identity(owner.name)
    id_returncode, id_identity = _inspect_container_identity(owner.container_id)
    if (
        name_returncode != 0
        or id_returncode != 0
        or name_identity != owner.container_id
        or id_identity != owner.container_id
    ):
        raise _error(f"{context} container name/ID binding drifted")


def _poll_owned_postgres_destroyed(owner: OwnedPostgres) -> Mapping[str, Any]:
    """Wait for Docker auto-remove to prove name-and-ID absence."""

    transient_owned_presence = False
    for attempt in range(1, POSTGRES_DESTROY_POLL_MAX_ATTEMPTS + 1):
        name_returncode, name_identity = _inspect_container_identity(owner.name)
        id_returncode, id_identity = _inspect_container_identity(owner.container_id)
        present_identities = tuple(
            identity
            for returncode, identity in (
                (name_returncode, name_identity),
                (id_returncode, id_identity),
            )
            if returncode == 0
        )
        if any(identity != owner.container_id for identity in present_identities):
            raise _error("foreign PostgreSQL container appeared during cleanup")
        if name_returncode == 1 and id_returncode == 1:
            return {
                "status": "confirmed_absent",
                "attempts": attempt,
                "name_and_id_absent": True,
                "transient_owned_presence_observed": transient_owned_presence,
                "foreign_or_ambiguous_identity_observed": False,
                "container_name_or_id_serialized": False,
            }
        transient_owned_presence = True
        if attempt < POSTGRES_DESTROY_POLL_MAX_ATTEMPTS:
            time.sleep(POSTGRES_DESTROY_POLL_INTERVAL_SECONDS)
    raise _error("owned PostgreSQL container destroy poll timed out")


def _finish_owned_postgres_cleanup(
    owner: OwnedPostgres,
    *,
    socket_handle: DirectoryHandle,
) -> Mapping[str, Any]:
    """Finish destroy polling and socket cleanup without issuing a stop."""

    destroy_poll = _poll_owned_postgres_destroyed(owner)
    removed_socket_entries = _cleanup_owned_postgres_socket_inventory(
        socket_handle,
        owner.socket_inventory,
    )
    return {
        "removed": True,
        "owned_container_only": True,
        "graceful_stop": True,
        "stop_timeout_seconds": POSTGRES_GRACEFUL_STOP_TIMEOUT_SECONDS,
        "identity_verified_before_stop": True,
        "container_absent_after_stop": True,
        "stop_target_exact_owned_container_id": True,
        "destroy_poll": dict(destroy_poll),
        "socket_inventory_claimed": len(owner.socket_inventory),
        "socket_entries_removed_after_stop": removed_socket_entries,
        "socket_cleanup_by_retained_directory_fd": True,
        "socket_cleanup_identity_fields": [
            "name",
            "kind",
            "device",
            "inode",
            "link_count",
        ],
        "arbitrary_residual_adoption": False,
        "socket_directory_empty": True,
    }


def _stop_owned_postgres(
    owner: OwnedPostgres,
    *,
    socket_handle: DirectoryHandle,
    before_stop: Callable[[], None] | None = None,
) -> Mapping[str, Any]:
    _require_owned_postgres_binding(owner, context="PostgreSQL cleanup")
    if before_stop is not None:
        before_stop()
    result = _run(
        (
            "/usr/bin/docker",
            "stop",
            "--time",
            str(POSTGRES_GRACEFUL_STOP_TIMEOUT_SECONDS),
            owner.container_id,
        ),
        cwd=PROJECT_ROOT,
        portable_argv=(
            "docker",
            "stop",
            "--time",
            str(POSTGRES_GRACEFUL_STOP_TIMEOUT_SECONDS),
            "<OWNED_CONTAINER>",
        ),
        timeout_seconds=120,
        failure_stage="postgres cleanup",
    )
    return {
        "command": dict(result.record),
        **_finish_owned_postgres_cleanup(owner, socket_handle=socket_handle),
    }


def _suite_environment(
    kind: str,
    *,
    retained_python_target: str | None = None,
) -> dict[str, str]:
    environment = {
        PLUGIN_MODE_ENV: kind,
        PLUGIN_ROOT_ENV: "/workspace",
        "TEST_DATABASE_URL": SAFE_DB_URL,
        "PGHOST": DB_SOCKET_ROOT,
        "HOME": "/tmp",
        "XDG_CACHE_HOME": "/tmp/cache",
        "PATH": "/usr/bin:/bin",
    }
    if retained_python_target is not None:
        candidate = Path(retained_python_target)
        if (
            not candidate.is_absolute()
            or not candidate.is_relative_to(Path("/usr"))
            or ".." in candidate.parts
        ):
            raise _error("retained Python target environment binding is unsafe")
        environment[PLUGIN_RETAINED_PYTHON_ENV] = retained_python_target
    if kind == PUBLIC_SUITE_KIND:
        # The sealed suite contains historical E10 sandbox regressions.  They
        # recognize this closed compatibility marker and verify the already
        # recorded denial template instead of trying a nested user namespace.
        environment.update(
            {
                "CLOSURE_E10_OUTCOME_GUARD": "1",
                "CLOSURE_E10_REPO_ROOT": "/workspace",
                "CLOSURE_E10_SUITE_KIND": "closure_phase3_public",
            }
        )
    return environment


def _public_command(contract: FinalCertificationContract) -> tuple[str, ...]:
    suite = contract.test_suite
    return (
        ".venv/bin/python",
        "-m",
        "pytest",
        *suite.selectors,
        "-ra",
        "-q",
        "-p",
        "src.reporting.build_phase4_final_certification",
        "-p",
        "no:cacheprovider",
        "--junitxml=tmp/public-tests-raw.xml",
    )


def _e2e_command(contract: FinalCertificationContract) -> tuple[str, ...]:
    return (
        ".venv/bin/python",
        "-m",
        "pytest",
        *contract.test_suite.e2e_nodes,
        "-q",
        "-p",
        "src.reporting.build_phase4_final_certification",
        "-p",
        "no:cacheprovider",
        "--junitxml=tmp/e2e-raw.xml",
    )


def _acquire_verification_runtime(
    *,
    source_root: Path,
    clone_handle: DirectoryHandle,
    clone_mountpoints: CloneMountpointLease,
    sandbox_handle: DirectoryHandle,
    socket_handle: DirectoryHandle,
    mask_handle: DirectoryHandle,
) -> VerificationRuntimeLease:
    try:
        return _open_verification_runtime(
            source_root=source_root,
            clone=clone_handle,
            clone_mountpoints=clone_mountpoints,
            sandbox=sandbox_handle,
            socket_handle=socket_handle,
            mask_root=mask_handle,
        )
    except FinalCertificationBuildError as exc:
        if exc.command_failure is not None or exc.internal_failure is not None:
            raise
        raise _internal_error(
            "verification runtime acquisition failed closed",
            stage="verification_runtime_acquisition",
            category="runtime_binding_failure",
        ) from None
    except BaseException:
        raise _internal_error(
            "verification runtime acquisition failed closed",
            stage="verification_runtime_acquisition",
            category="runtime_binding_failure",
        ) from None


def _run_verification(
    *,
    source_root: Path,
    clone_handle: DirectoryHandle,
    clone_mountpoints: CloneMountpointLease,
    sandbox_handle: DirectoryHandle,
    socket_handle: DirectoryHandle,
    mask_handle: DirectoryHandle,
    contract: FinalCertificationContract,
    execution_commit: str,
    namespace_validator: Callable[[str], None] | None = None,
) -> tuple[Mapping[str, bytes], Mapping[str, Any]]:
    runtime: VerificationRuntimeLease | None = None
    if namespace_validator is not None:
        namespace_validator("before_verification_runtime_acquisition")
    try:
        runtime = _acquire_verification_runtime(
            source_root=source_root,
            clone_handle=clone_handle,
            clone_mountpoints=clone_mountpoints,
            sandbox_handle=sandbox_handle,
            socket_handle=socket_handle,
            mask_handle=mask_handle,
        )
        if namespace_validator is not None:
            namespace_validator("after_verification_runtime_acquisition")
        sandbox_smoke = _run_sandbox_smoke(
            source_root=source_root,
            runtime=runtime,
            contract=contract,
            namespace_validator=namespace_validator,
        )
        return _run_verification_with_runtime(
            source_root=source_root,
            clone_root=clone_handle.path,
            sandbox_tmp=sandbox_handle.path,
            contract=contract,
            execution_commit=execution_commit,
            runtime=runtime,
            sandbox_smoke=sandbox_smoke,
            namespace_validator=namespace_validator,
        )
    finally:
        if runtime is not None:
            runtime.close()


def _run_verification_with_runtime(
    *,
    source_root: Path,
    clone_root: Path,
    sandbox_tmp: Path,
    contract: FinalCertificationContract,
    execution_commit: str,
    runtime: VerificationRuntimeLease,
    sandbox_smoke: Mapping[str, Any],
    namespace_validator: Callable[[str], None] | None = None,
) -> tuple[Mapping[str, bytes], Mapping[str, Any]]:
    try:
        bwrap, bwrap_template = _make_bwrap_prefix(
            runtime=runtime,
            contract=contract,
        )
    except FinalCertificationBuildError as exc:
        if exc.command_failure is not None or exc.internal_failure is not None:
            raise
        raise _internal_error(
            "sandbox projection failed closed",
            stage="sandbox_projection",
            category="forbidden_path_kind_mismatch",
        ) from None
    except BaseException:
        raise _internal_error(
            "sandbox projection failed closed",
            stage="sandbox_projection",
            category="forbidden_path_kind_mismatch",
        ) from None
    public_command = _public_command(contract)
    if namespace_validator is not None:
        namespace_validator("before_public_tests")
    runtime.revalidate(context="before public test execution")
    public: CommandResult | None = None
    public_invocation_error: BaseException | None = None
    try:
        public = _run(
            public_command,
            cwd=source_root,
            execution_argv=(*bwrap, "/cert-python", *public_command[1:]),
            environment={
                **_suite_environment(
                    PUBLIC_SUITE_KIND,
                    retained_python_target=runtime.python.target,
                ),
                "__PYVENV_LAUNCHER__": "/workspace/.venv/bin/python",
            },
            inherit_environment=False,
            timeout_seconds=3600,
            require_success=False,
            pass_fds=runtime.pass_fds,
            failure_stage="public tests",
        )
    except BaseException as exc:
        public_invocation_error = exc
    if public is not None:
        # Pytest console streams are intentionally non-evidence.  Discard them
        # before any post-run validation can raise and retain this frame.
        public = CommandResult(record=dict(public.record), stdout="", stderr="")
    post_public_error: BaseException | None = None
    try:
        runtime.revalidate(context="after public test execution")
    except BaseException as exc:
        post_public_error = exc
    if namespace_validator is not None:
        try:
            namespace_validator("after_public_tests")
        except BaseException as exc:
            post_public_error = post_public_error or exc
    if post_public_error is not None:
        raise post_public_error
    if public_invocation_error is not None:
        raise public_invocation_error
    if public is None:
        raise _error("public test invocation returned no result")
    returncode = public.record.get("returncode")
    if type(returncode) is not int:
        raise _public_tests_failure_error(
            _unavailable_public_tests_failure(
                returncode=0,
                reason="junit_malformed_or_hostile",
            )
        )
    junit_policy = dict(contract.public_tests_junit_diagnostic_policy)
    try:
        raw_junit = _read_public_tests_junit_fd_safe(
            sandbox_tmp=sandbox_tmp,
            sandbox=runtime.sandbox,
            source_filename=cast(str, junit_policy.get("source_filename")),
            max_junit_bytes=cast(int, junit_policy.get("max_junit_bytes")),
        )
    except _PublicTestsJunitUnavailable as exc:
        raise _public_tests_failure_error(
            _unavailable_public_tests_failure(
                returncode=returncode,
                reason=exc.reason,
            )
        ) from None
    if returncode != 0:
        try:
            failure_evidence = _strict_public_tests_failure_projection(
                raw_junit,
                suite=contract.test_suite,
                returncode=returncode,
            )
        except _PublicTestsJunitUnavailable as exc:
            failure_evidence = _unavailable_public_tests_failure(
                returncode=returncode,
                reason=exc.reason,
            )
        raw_junit = b""
        raise _public_tests_failure_error(failure_evidence)
    raw_totals, _ = _parse_junit(raw_junit)
    if (
        raw_totals["tests"] != contract.test_suite.collected_test_count
        or raw_totals["failures"]
        or raw_totals["errors"]
        or raw_totals["skipped"] != contract.test_suite.allowed_skip_count
    ):
        raise _error("public test totals or exact skip ledger drifted")
    junit = normalize_junit_xml(
        raw_junit,
        execution_commit=execution_commit,
        suite=contract.test_suite,
        clone_root=clone_root,
    )
    totals, skip_ledger = _validate_junit_certification_properties(
        junit,
        contract=contract,
        execution_commit=execution_commit,
    )
    _validate_skip_ledger(skip_ledger, contract.test_suite)

    openapi_command = (
        ".venv/bin/python",
        "-B",
        "src/reporting/build_phase4_final_certification.py",
        "--emit-openapi",
        "tmp/openapi-raw.json",
        "--execution-commit",
        execution_commit,
    )
    if namespace_validator is not None:
        namespace_validator("before_openapi_generation")
    runtime.revalidate(context="before OpenAPI execution")
    openapi_run = _run(
        openapi_command,
        cwd=source_root,
        execution_argv=(*bwrap, "/cert-python", *openapi_command[1:]),
        environment={
            **_suite_environment(
                E2E_SUITE_KIND,
                retained_python_target=runtime.python.target,
            ),
            "__PYVENV_LAUNCHER__": "/workspace/.venv/bin/python",
        },
        inherit_environment=False,
        timeout_seconds=600,
        pass_fds=runtime.pass_fds,
        failure_stage="openapi generation",
    )
    runtime.revalidate(context="after OpenAPI execution")
    if namespace_validator is not None:
        namespace_validator("after_openapi_generation")
    openapi_payload = _read_regular(
        sandbox_tmp / "openapi-raw.json", context="generated OpenAPI"
    )
    try:
        openapi_document = json.loads(openapi_payload)
    except json.JSONDecodeError as exc:
        raise _error("generated OpenAPI JSON is invalid") from exc
    if not isinstance(openapi_document, Mapping):
        raise _error("generated OpenAPI is not an object")
    openapi_validation = validate_openapi_document(
        cast(Mapping[str, Any], openapi_document), root=clone_root, contract=contract
    )

    e2e_command = _e2e_command(contract)
    if namespace_validator is not None:
        namespace_validator("before_synthetic_e2e")
    runtime.revalidate(context="before synthetic E2E execution")
    e2e = _run(
        e2e_command,
        cwd=source_root,
        execution_argv=(*bwrap, "/cert-python", *e2e_command[1:]),
        environment={
            **_suite_environment(
                E2E_SUITE_KIND,
                retained_python_target=runtime.python.target,
            ),
            "__PYVENV_LAUNCHER__": "/workspace/.venv/bin/python",
        },
        inherit_environment=False,
        timeout_seconds=1800,
        pass_fds=runtime.pass_fds,
        failure_stage="synthetic e2e",
    )
    runtime.revalidate(context="after synthetic E2E execution")
    if namespace_validator is not None:
        namespace_validator("after_synthetic_e2e")
    e2e_raw = _read_regular(sandbox_tmp / "e2e-raw.xml", context="raw E2E JUnit")
    e2e_totals, e2e_skips = _parse_junit(e2e_raw)
    if e2e_totals != {
        "tests": 3,
        "passed": 3,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
    } or e2e_skips:
        raise _error("synthetic E2E suite is not exact 3/3/0/0/0")

    ty_command = (".venv/bin/ty", "check")
    if namespace_validator is not None:
        namespace_validator("before_ty_check")
    runtime.revalidate(context="before ty execution")
    ty = _run(
        ty_command,
        cwd=source_root,
        execution_argv=(*bwrap, "/cert-ty", *ty_command[1:]),
        environment=_suite_environment(
            E2E_SUITE_KIND,
            retained_python_target=runtime.python.target,
        ),
        inherit_environment=False,
        timeout_seconds=1800,
        pass_fds=runtime.pass_fds,
        failure_stage="ty check",
    )
    runtime.revalidate(context="after ty execution")
    if namespace_validator is not None:
        namespace_validator("after_ty_check")
    poetry_command = ("poetry", "check", "--lock")
    poetry_execution_command = (
        "/cert-poetry-python",
        "/cert-poetry-script",
        "check",
        "--lock",
    )
    if namespace_validator is not None:
        namespace_validator("before_poetry_lock_check")
    runtime.revalidate(context="before Poetry execution")
    poetry = _run(
        poetry_command,
        cwd=source_root,
        execution_argv=(*bwrap, *poetry_execution_command),
        environment={
            **_suite_environment(
                E2E_SUITE_KIND,
                retained_python_target=runtime.python.target,
            ),
            "__PYVENV_LAUNCHER__": "/cert-poetry/bin/python",
        },
        inherit_environment=False,
        timeout_seconds=600,
        pass_fds=runtime.pass_fds,
        failure_stage="poetry lock check",
    )
    runtime.revalidate(context="after Poetry execution")
    if namespace_validator is not None:
        namespace_validator("after_poetry_lock_check")

    test_report = _build_test_report(
        execution_commit=execution_commit,
        command=public_command,
        totals=totals,
        skip_ledger=skip_ledger,
        suite=contract.test_suite,
    )
    contract_report = _build_openapi_report(
        execution_commit=execution_commit,
        validation=openapi_validation,
        openapi_sha256=sha256_bytes(openapi_payload),
    )
    e2e_report = _build_e2e_report(
        execution_commit=execution_commit,
        command=e2e_command,
        totals=e2e_totals,
    )
    commands = {
        "public_tests": dict(public.record),
        "openapi_generation": dict(openapi_run.record),
        "end_to_end": dict(e2e.record),
        "ty_check": dict(ty.record),
        "poetry_lock_check": dict(poetry.record),
    }
    artifacts = {
        "public_tests.xml": junit,
        "test_report.md": test_report,
        "openapi.json": _canonical_json(openapi_document),
        "openapi_contract_report.md": contract_report,
        "end_to_end_report.md": e2e_report,
    }
    evidence = {
        "commands": commands,
        "sandbox_smoke": dict(sandbox_smoke),
        "public_test_totals": totals,
        "public_skip_ledger": skip_ledger,
        "e2e_totals": e2e_totals,
        "openapi_validation": openapi_validation,
        "sandbox": {
            "backend": "bubblewrap",
            "argv_template_prefix": bwrap_template,
            "network": "unshared",
            "postgresql_transport": "owned_unix_socket_only",
            "source_tree": "read_only",
            "host_virtualenv": "read_only",
            "effect_sources_retained_by_fd": True,
            "python_console_scripts_interpreter_retained_by_fd": True,
            "private_dvc_configuration_masked": True,
            "forbidden_prefixes_absent": list(contract.forbidden_read_prefixes),
            "forbidden_paths_masked": list(contract.forbidden_read_paths),
            "restored_payloads_masked": [
                spec.output_path for spec in contract.dvc_pointers
            ],
            "sandbox_mountpoint_policy": dict(
                contract.sandbox_mountpoint_policy
            ),
            "sandbox_smoke_policy": dict(contract.sandbox_smoke_policy),
            "cleanup_diagnostic_policy": dict(
                contract.cleanup_diagnostic_policy
            ),
            "public_tests_junit_diagnostic_policy": dict(
                contract.public_tests_junit_diagnostic_policy
            ),
            "postgres_connection_policy": dict(
                contract.postgres_connection_policy
            ),
            "postgres_startup_stability_policy": dict(
                contract.postgres_startup_stability_policy
            ),
            "postgres_destroy_poll_policy": dict(
                contract.postgres_destroy_poll_policy
            ),
            "test_access_guard_policy": dict(
                contract.test_access_guard_policy
            ),
        },
    }
    return artifacts, evidence


def _command_markdown(argv: Sequence[str]) -> str:
    return " ".join(f"`{value}`" for value in argv)


def _build_test_report(
    *,
    execution_commit: str,
    command: Sequence[str],
    totals: Mapping[str, int],
    skip_ledger: Sequence[Mapping[str, str]],
    suite: Any,
) -> bytes:
    lines = [
        "# Phase 4 final public test certification",
        "",
        f"- Executable commit (P-CERT): `{execution_commit}`",
        f"- Suite: `{PUBLIC_SUITE_KIND}`",
        f"- Locked selectors: `{len(suite.selectors)}`",
        f"- Locked collected node IDs: `{suite.collected_test_count}`",
        f"- Node-ID SHA-256: `{suite.nodeids_sha256}`",
        f"- Command: {_command_markdown(command)}",
        f"- Passed/skipped/failures/errors: `{totals['passed']}/{totals['skipped']}/0/0`",
        "- Forbidden target, outcome, restored-Parquet, and private reads: `0`.",
        "- General network access: `disabled`; PostgreSQL used an owned Unix socket.",
        "",
        "## Exact justified skip ledger",
        "",
    ]
    for item in sorted(skip_ledger, key=lambda value: value["nodeid"]):
        lines.append(f"- `{item['nodeid']}` — `{suite.exact_skip_reason}`.")
    lines.extend(
        [
            "",
            "This is software certification evidence. It does not rerun the sealed "
            "scientific experiments and does not establish scientific efficacy.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def _build_openapi_report(
    *, execution_commit: str, validation: Mapping[str, Any], openapi_sha256: str
) -> bytes:
    lines = [
        "# Phase 4 final OpenAPI contract certification",
        "",
        f"- Executable commit (P-CERT): `{execution_commit}`",
        "- Status: `passed`",
        f"- OpenAPI SHA-256: `{openapi_sha256}`",
        f"- Paths/operations/documented operations: `{validation['openapi_path_count']}/{validation['openapi_operation_count']}/{validation['documented_operation_count']}`",
        "- Missing documented operations: `0`",
        "- Unique operation IDs: `true`",
        "- Exact path parameters: `true`",
        "",
        "## Bound public API documents",
        "",
    ]
    for record in cast(Sequence[Mapping[str, Any]], validation["documents"]):
        lines.append(
            f"- `{record['path']}` — `{record['sha256']}` "
            f"({record['documented_operation_count']} operations)."
        )
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def _build_e2e_report(
    *, execution_commit: str, command: Sequence[str], totals: Mapping[str, int]
) -> bytes:
    return (
        "# Phase 4 final synthetic API end-to-end certification\n\n"
        f"- Executable commit (P-CERT): `{execution_commit}`\n"
        f"- Command: {_command_markdown(command)}\n"
        f"- Tests/passed/failures/errors/skips: `{totals['tests']}/{totals['passed']}/0/0/0`\n"
        "- Workflow status: `passed`\n"
        "- Fixture scope: `synthetic_external_non_closure_outcome`\n"
        "- Covered flows: prediction/alert, bounded current-state counterfactual, and run-artifact list/preview/summary.\n"
        "- Closure outcomes, targets, restored Parquets, and private context were not opened.\n\n"
        "This checks software behavior only; the counterfactual is not field-causal evidence.\n"
    ).encode("utf-8")


def _run_anchored_executable(
    executable: AnchoredExecutable,
    arguments: Sequence[str],
    *,
    cwd: Path,
    portable_argv: Sequence[str],
    timeout_seconds: int,
    context: str,
) -> CommandResult:
    executable.revalidate(context=f"{context} before execution")
    result = _run(
        (executable.proc_path, *arguments),
        cwd=cwd,
        portable_argv=portable_argv,
        timeout_seconds=timeout_seconds,
        pass_fds=(executable.fd,),
        failure_stage=context,
    )
    executable.revalidate(context=f"{context} after execution")
    return result


def _revalidate_owned_dvc_version_boundary(
    *,
    source_root: Path,
    clone_handle: DirectoryHandle,
    site_cache_handle: DirectoryHandle,
    context: str,
) -> None:
    """Bind the DVC version cwd/cache to the retained R-CERT workspace."""

    source = source_root.resolve(strict=True)
    expected_parent = source / "tmp/closure_v1_phase4_final_certification"
    run_root = clone_handle.path.parent
    if (
        run_root.parent != expected_parent
        or re.fullmatch(r"run-[0-9a-f]{32}", run_root.name) is None
        or clone_handle.path != run_root / "clone"
        or site_cache_handle.path != run_root / "dvc-version-site-cache"
    ):
        raise _error(f"{context} escaped the owned R-CERT workspace")
    _require_isolated_dvc_command_root(
        source_root=source,
        command_root=clone_handle.path,
        context=context,
    )
    for handle, expected_mode, label in (
        (clone_handle, None, "clone"),
        (site_cache_handle, 0o700, "site cache"),
    ):
        try:
            named = handle.path.lstat()
            opened = os.fstat(handle.fd)
        except OSError as exc:
            raise _error(f"{context} owned {label} binding vanished") from exc
        if (
            not stat.S_ISDIR(named.st_mode)
            or stat.S_ISLNK(named.st_mode)
            or not stat.S_ISDIR(opened.st_mode)
            or (named.st_dev, named.st_ino)
            != (handle.device, handle.inode)
            or (opened.st_dev, opened.st_ino)
            != (handle.device, handle.inode)
            or (
                expected_mode is not None
                and (
                    stat.S_IMODE(named.st_mode) != expected_mode
                    or stat.S_IMODE(opened.st_mode) != expected_mode
                )
            )
        ):
            raise _error(f"{context} owned {label} binding drifted")


def _revalidate_retained_dvc_runtime(
    runtime: AnchoredPythonScriptRuntime,
    *,
    source_root: Path,
    context: str,
) -> None:
    """Prove every DVC call still uses the one source-anchored runtime."""

    source = source_root.resolve(strict=True)
    if (
        runtime.script.root != source
        or runtime.interpreter.root != source
        or runtime.script.name != "dvc"
        or runtime.interpreter.name != "python"
        or runtime.script.chain[-1].path != source / ".venv/bin"
        or runtime.interpreter.chain[-1].path != source / ".venv/bin"
    ):
        raise _error(f"{context} retained DVC runtime provenance drifted")
    runtime.revalidate(context=context)


def _runtime_versions(
    root: Path,
    *,
    dvc_runtime: AnchoredPythonScriptRuntime,
    dvc_clone_handle: DirectoryHandle,
    dvc_site_cache_handle: DirectoryHandle,
    dvc_private_pass_fds: Sequence[int] = (),
    namespace_validator: Callable[[str], None] | None = None,
) -> Mapping[str, str]:
    python: AnchoredPythonInterpreter | None = None
    ty: AnchoredExecutable | None = None
    poetry: AnchoredPythonScriptRuntime | None = None
    bwrap: AnchoredExecutable | None = None
    try:
        _revalidate_owned_dvc_version_boundary(
            source_root=root,
            clone_handle=dvc_clone_handle,
            site_cache_handle=dvc_site_cache_handle,
            context="DVC version",
        )
        _revalidate_retained_dvc_runtime(
            dvc_runtime,
            source_root=root,
            context="retained DVC version runtime",
        )
        python = _open_anchored_python_interpreter(
            root, Path(".venv/bin/python"), context="Python version runtime"
        )
        ty = _open_anchored_executable(
            root, Path(".venv/bin/ty"), context="ty version runtime"
        )
        poetry_root = _poetry_runtime_root()
        poetry = _open_python_script_runtime(
            poetry_root,
            Path("bin/poetry"),
            interpreter_relative=Path("bin/python"),
            context="Poetry version runtime",
        )
        bwrap = _open_anchored_executable(
            Path("/"), Path("usr/bin/bwrap"), context="bubblewrap version runtime"
        )
        versions: dict[str, str] = {}

        def capture(key: str, operation: Callable[[], CommandResult]) -> None:
            if namespace_validator is not None:
                namespace_validator(f"before_{key}_version")
            result = operation()
            if namespace_validator is not None:
                namespace_validator(f"after_{key}_version")
            value = (result.stdout or result.stderr).strip()
            if not value or "\n" in value:
                raise _error(f"{key} version probe drifted")
            versions[key] = value

        def python_probe() -> CommandResult:
            assert python is not None
            python.revalidate(context="Python version before execution")
            result = _run(
                (python.proc_path, "--version"),
                cwd=root,
                portable_argv=(".venv/bin/python", "--version"),
                environment={
                    "__PYVENV_LAUNCHER__": f"{python.venv_proc_path}/bin/python"
                },
                timeout_seconds=120,
                pass_fds=(python.fd, python.venv_fd),
                failure_stage="python version",
            )
            python.revalidate(context="Python version after execution")
            return result

        def dvc_probe() -> CommandResult:
            _revalidate_owned_dvc_version_boundary(
                source_root=root,
                clone_handle=dvc_clone_handle,
                site_cache_handle=dvc_site_cache_handle,
                context="DVC version before execution",
            )
            _revalidate_retained_dvc_runtime(
                dvc_runtime,
                source_root=root,
                context="retained DVC runtime before version execution",
            )
            result = _run_python_script_runtime(
                dvc_runtime,
                ("--version",),
                cwd=dvc_clone_handle.path,
                portable_argv=(".venv/bin/dvc", "--version"),
                environment={
                    "DVC_NO_ANALYTICS": "1",
                    "DVC_SITE_CACHE_DIR": os.fspath(dvc_site_cache_handle.path),
                },
                timeout_seconds=120,
                context="DVC version",
                private_pass_fds=dvc_private_pass_fds,
            )
            _revalidate_retained_dvc_runtime(
                dvc_runtime,
                source_root=root,
                context="retained DVC runtime after version execution",
            )
            _revalidate_owned_dvc_version_boundary(
                source_root=root,
                clone_handle=dvc_clone_handle,
                site_cache_handle=dvc_site_cache_handle,
                context="DVC version after execution",
            )
            return result

        capture("python", python_probe)
        capture("dvc", dvc_probe)
        capture(
            "ty",
            lambda: _run_anchored_executable(
                ty,
                ("--version",),
                cwd=root,
                portable_argv=(".venv/bin/ty", "--version"),
                timeout_seconds=120,
                context="ty version",
            ),
        )
        capture(
            "git",
            lambda: _run(
                (GIT_EXECUTABLE, "--version"),
                cwd=root,
                portable_argv=("git", "--version"),
                timeout_seconds=120,
                failure_stage="git version",
            ),
        )
        capture(
            "poetry",
            lambda: _run_python_script_runtime(
                poetry,
                ("--version",),
                cwd=root,
                portable_argv=("poetry", "--version"),
                environment={"POETRY_NO_INTERACTION": "1"},
                timeout_seconds=120,
                context="Poetry version",
            ),
        )
        capture(
            "bubblewrap",
            lambda: _run_anchored_executable(
                bwrap,
                ("--version",),
                cwd=root,
                portable_argv=("bwrap", "--version"),
                timeout_seconds=120,
                context="bubblewrap version",
            ),
        )
        for key, field in (
            ("docker_client", "{{.Client.Version}}"),
            ("docker_server", "{{.Server.Version}}"),
        ):
            capture(
                key,
                lambda field=field, key=key: _run(
                    ("/usr/bin/docker", "version", "--format", field),
                    cwd=root,
                    portable_argv=(
                        "docker",
                        "version",
                        "--format",
                        "<CLIENT_VERSION>" if key == "docker_client" else "<SERVER_VERSION>",
                    ),
                    timeout_seconds=120,
                    failure_stage=f"{key} version",
                ),
            )
        return versions
    finally:
        for value in (bwrap, poetry, ty, python):
            if value is not None:
                value.close()


def _sealed_runtime_versions(
    root: Path,
    *,
    contract: FinalCertificationContract,
    dvc_runtime: AnchoredPythonScriptRuntime,
    dvc_clone_handle: DirectoryHandle,
    dvc_site_cache_handle: DirectoryHandle,
    dvc_private_pass_fds: Sequence[int] = (),
    namespace_validator: Callable[[str], None] | None = None,
) -> dict[str, str]:
    """Capture all eight runtime versions and require the sealed exact map."""

    observed = dict(
        _runtime_versions(
            root,
            dvc_runtime=dvc_runtime,
            dvc_clone_handle=dvc_clone_handle,
            dvc_site_cache_handle=dvc_site_cache_handle,
            dvc_private_pass_fds=dvc_private_pass_fds,
            namespace_validator=namespace_validator,
        )
    )
    if observed != dict(contract.expected_runtime_versions):
        raise _error("runtime version probes differ from the sealed contract")
    return observed


def _artifact_record(path_text: str, payload: bytes) -> dict[str, Any]:
    return {"path": path_text, "bytes": len(payload), "sha256": sha256_bytes(payload)}


def _environment_object(
    *,
    contract: FinalCertificationContract,
    execution_commit: str,
    anchor_records: Sequence[Mapping[str, Any]],
    restore_records: Sequence[Mapping[str, Any]],
    verification: Mapping[str, Any],
    database: Mapping[str, Any],
    runtime_versions: Mapping[str, str],
) -> dict[str, Any]:
    dvc_record = expected_environment_dvc_record()
    _require_dvc_status_policy_projection(
        dvc_record,
        contract=contract,
        context="environment",
    )
    return {
        "schema_version": "closure_v1_phase4_final_environment_v1",
        "execution_commit": execution_commit,
        "certification_tree": "P-CERT",
        "paths_outside_exact8_equal_p_cert": True,
        "runtime_versions": dict(sorted(runtime_versions.items())),
        "dependency_lock": next(
            record for record in anchor_records if record["path"] == "poetry.lock"
        ),
        "project_configuration": next(
            record for record in anchor_records if record["path"] == "pyproject.toml"
        ),
        "database": {
            "image": database["image"],
            "network": "none",
            "transport": "owned_unix_socket",
            "cleaned_after_execution": database.get("cleaned_after_execution") is True,
            "url_path_or_credentials_serialized": False,
        },
        "isolation": verification["sandbox"],
        "dvc": dvc_record,
        "timestamps_hostnames_absolute_paths_remote_urls_credentials": "omitted",
    }


def _final_report(execution_commit: str) -> bytes:
    return (
        "# Final doctoral software certification — Closure V1 Phase 4\n\n"
        f"Execution commit: P-CERT `{execution_commit}`. The later R-CERT commit adds only "
        "this exact eight-file evidence bundle; every tracked path outside exact8 "
        "must remain byte-identical to P-CERT. No command is represented as having "
        "run literally against the later R commit.\n\n"
        "## Result\n\n"
        "- Locked public test suite: passed with only the exact justified skip ledger.\n"
        "- OpenAPI/documented contract: passed.\n"
        "- Three synthetic end-to-end workflows: passed.\n"
        "- Full static type check and Poetry lock check: passed.\n"
        "- Eight directed DVC restores: DVC authenticated the sealed pointer MD5/size in an initially empty isolated cache; Python opened no restored/cache payload and decoded no Parquet.\n"
        "- Main worktree/cache: no DVC command, including version/status/pull, ran there. Two separate owned 0700 site-caches served runtime-version and restore/status roles; one retained DVC runtime was sealed before private configuration/pull and revalidated through final status/version. Main state was reconstructed statically from Git-bound configuration and the eight published DVC pointers under an immutable metadata/inode/inventory lease.\n"
        "- Concurrency: one cooperative flock is retained on the Git directory; the legacy guard path stays absent, and detected external namespace mutation is a stop condition. Non-cooperating same-UID namespace mutation is explicitly outside the guarantee.\n"
        "- E0-U and E1–E10 were not rerun; no model was fit, scored, recalibrated, or changed.\n\n"
        "## Claim boundary\n\n"
        "This certifies software execution, artifact restorability, and reproducibility "
        "controls. It does **not** establish, strengthen, or rerun scientific efficacy. "
        "Scientific conclusions remain bounded by the published R-SYN claim/evidence "
        "matrix and the editorial manuscript receipt. No post-Phase-4 work is authorized.\n"
    ).encode("utf-8")


def build_final_certification_payloads(
    *,
    contract: FinalCertificationContract,
    execution_commit: str,
    authority: Mapping[str, Any],
    anchor_records: Sequence[Mapping[str, Any]],
    pointer_records: Sequence[Mapping[str, Any]],
    restore_records: Sequence[Mapping[str, Any]],
    clone_record: Mapping[str, Any],
    verification_artifacts: Mapping[str, bytes],
    verification: Mapping[str, Any],
    database: Mapping[str, Any],
    runtime_versions: Mapping[str, str],
) -> ExecutionProducts:
    """Create deterministic exact8 payloads from already-verified evidence."""

    commit = _require_commit(execution_commit, context="P-CERT execution commit")
    _require_h18_authority_boundary(authority, contract=contract)
    authority_commits = _require_effective_authority_commit_binding(
        authority,
        contract=contract,
        execution_commit=commit,
    )
    _require_effective_authority_dvc_status_policy(authority, contract=contract)
    if dict(runtime_versions) != dict(contract.expected_runtime_versions):
        raise _error("runtime version probes differ from the sealed contract")
    if set(verification_artifacts) != {
        "public_tests.xml",
        "test_report.md",
        "openapi.json",
        "openapi_contract_report.md",
        "end_to_end_report.md",
    }:
        raise _error("verification artifact scope is not exact five")
    environment = _environment_object(
        contract=contract,
        execution_commit=commit,
        anchor_records=anchor_records,
        restore_records=restore_records,
        verification=verification,
        database=database,
        runtime_versions=runtime_versions,
    )
    environment_payload = _canonical_json(environment)
    artifacts: dict[str, bytes] = {
        **dict(verification_artifacts),
        "environment.json": environment_payload,
    }
    final_report = _final_report(commit)
    artifacts["FINAL_DOCTORAL_CERTIFICATION_REPORT.md"] = final_report
    pre_manifest_paths = list(contract.output_paths[:-1])
    if [Path(path).name for path in pre_manifest_paths] != list(artifacts):
        raise _error("R-CERT pre-manifest output order drifted")
    records = [
        _artifact_record(path_text, artifacts[Path(path_text).name])
        for path_text in pre_manifest_paths
    ]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "completed",
        "execution_commit": commit,
        "certification_commit_role": "P-CERT",
        "paths_outside_exact8_equal_p_cert": True,
        "r_cert_additions_only": [spec.path for spec in contract.r_scope],
        "p_cert_authority": {
            "path": AUTHORITY_PATH.as_posix(),
            **authority_commits,
            "bytes": authority["authority_bytes"],
            "sha256": authority["authority_sha256"],
        },
        "p_cert_companion_manifest": {
            "path": AUTHORITY_MANIFEST_PATH.as_posix(),
            **authority_commits,
            "bytes": authority["manifest_bytes"],
            "sha256": authority["manifest_sha256"],
        },
        "published_anchors": list(anchor_records),
        "published_anchor_records_sha256": digest_records(anchor_records),
        "dvc_pointer_records": list(pointer_records),
        "dvc_pointer_records_sha256": digest_records(pointer_records),
        "dvc_restores": list(restore_records),
        "dvc_restore_records_sha256": digest_records(restore_records),
        "clone": dict(clone_record),
        "verification": dict(verification),
        "artifacts": records,
        "artifact_records_sha256": digest_records(records),
        "publication": {
            "ordered_paths": list(contract.output_paths),
            "output_count": 8,
            "manifest_written_last": True,
            "no_clobber": contract.no_clobber,
            "concurrency_lock": contract.concurrency_lock,
            "legacy_guard_path_must_be_absent": (
                contract.legacy_guard_path_must_be_absent
            ),
            "external_namespace_mutation_is_stop_condition": (
                contract.external_namespace_mutation_is_stop_condition
            ),
            "noncooperating_same_uid_namespace_mutation": (
                contract.noncooperating_same_uid_namespace_mutation
            ),
            "identity_revalidated_before_and_after_name_cleanup": (
                contract.identity_revalidated_before_and_after_name_cleanup
            ),
            "conditional_unlink_by_inode_claimed": (
                contract.conditional_unlink_by_inode_claimed
            ),
            "cleanup_before_precommit": contract.cleanup_before_precommit,
        },
        "scientific_boundary": {
            "software_restorability_and_reproducibility_certified": True,
            "scientific_efficacy_claimed": False,
            "e0_u_or_e1_e10_rerun": False,
            "refit_rescore_or_recalibration": False,
            "parquet_payload_opened_by_python": False,
            "parquet_payload_decoded": False,
            "phase5_started": False,
        },
        "redaction": {
            "timestamps": "omitted",
            "hostnames": "omitted",
            "absolute_paths": "omitted",
            "remote_urls": "omitted",
            "database_urls": "omitted",
            "credentials": "omitted",
        },
    }
    manifest_payload = _canonical_json(manifest)
    for payload in (*artifacts.values(), manifest_payload):
        _assert_serialization_safe(payload)
    return ExecutionProducts(artifacts=artifacts, manifest=manifest)


def _validate_command_record(
    value: Any, *, expected_argv: Sequence[str], context: str
) -> None:
    if not isinstance(value, Mapping) or set(value) != {"argv", "returncode"}:
        raise _error(f"{context} command record is not exact")
    if value.get("argv") != list(expected_argv) or value.get("returncode") != 0:
        raise _error(f"{context} command record drifted or did not pass")


def _validate_junit_certification_properties(
    payload: bytes, *, contract: FinalCertificationContract, execution_commit: str
) -> tuple[dict[str, int], list[dict[str, str]]]:
    """Validate the entire canonical public JUnit grammar and exact bytes."""

    commit = _require_commit(execution_commit, context="JUnit execution commit")
    root, suite_node, cases = _junit_tree(payload)
    if any(node.text is not None or node.tail is not None for node in (root, suite_node)):
        raise _error("published JUnit contains non-canonical whitespace or text")
    suite_children = list(suite_node)
    if (
        len(suite_children) != len(cases) + 1
        or not suite_children
        or suite_children[0].tag != "properties"
        or any(node.tag != "testcase" for node in suite_children[1:])
    ):
        raise _error("published JUnit suite child grammar/order is not exact")
    properties = suite_children[0]
    if properties.attrib or properties.text is not None or properties.tail is not None:
        raise _error("published JUnit properties container is not minimal")
    expected_properties = _junit_closure_properties(
        execution_commit=commit, suite=contract.test_suite
    )
    property_nodes = list(properties)
    if len(property_nodes) != len(expected_properties):
        raise _error("published JUnit must contain exact five closure properties")
    for node, (name, value) in zip(
        property_nodes, expected_properties, strict=True
    ):
        if (
            node.tag != "property"
            or node.attrib != {"name": name, "value": value}
            or node.text is not None
            or node.tail is not None
            or list(node)
        ):
            raise _error("published JUnit closure properties are not exact")

    records: list[JunitCaseRecord] = []
    for case in cases:
        if (
            set(case.attrib) != {"classname", "name"}
            or case.text is not None
            or case.tail is not None
        ):
            raise _error("published JUnit testcase shape is not minimal")
        classname = case.attrib["classname"]
        name = case.attrib["name"]
        nodeid = _junit_nodeid(classname, name)
        if (classname, name) != _canonical_junit_identity(nodeid, name=name):
            raise _error("published JUnit classname/name aliases are forbidden")
        children = list(case)
        if not children:
            skipped = False
        elif len(children) == 1 and children[0].tag == "skipped":
            skipped_node = children[0]
            if (
                skipped_node.attrib
                != {
                    "type": JUNIT_SKIP_TYPE,
                    "message": contract.test_suite.exact_skip_reason,
                }
                or skipped_node.text is not None
                or skipped_node.tail is not None
                or list(skipped_node)
            ):
                raise _error("published JUnit skipped outcome is not exact")
            skipped = True
        else:
            raise _error(
                "published JUnit contains failure, error, system output, or unknown outcome"
            )
        records.append(
            JunitCaseRecord(
                nodeid=nodeid,
                classname=classname,
                name=name,
                skipped=skipped,
            )
        )
    _validate_junit_case_records(records, suite=contract.test_suite)
    ordered_nodeids = [record.nodeid for record in records]
    if ordered_nodeids != sorted(ordered_nodeids):
        raise _error("published JUnit testcases are not in canonical node-id order")
    counters = {
        "tests": str(len(records)),
        "failures": "0",
        "errors": "0",
        "skipped": str(sum(record.skipped for record in records)),
    }
    if root.attrib != counters or suite_node.attrib != {
        "name": PUBLIC_SUITE_KIND,
        **counters,
    }:
        raise _error("published JUnit root/suite counters or attributes drifted")
    reconstructed = _canonical_junit_xml(
        records,
        execution_commit=commit,
        suite=contract.test_suite,
    )
    if payload != reconstructed:
        raise _error("published JUnit bytes are not the canonical reconstruction")
    totals = {
        "tests": len(records),
        "failures": 0,
        "errors": 0,
        "skipped": sum(record.skipped for record in records),
        "passed": sum(not record.skipped for record in records),
    }
    ledger = [
        {
            "nodeid": record.nodeid,
            "reason": contract.test_suite.exact_skip_reason,
        }
        for record in records
        if record.skipped
    ]
    return totals, ledger


def _validate_clone_record(
    value: Any, *, contract: FinalCertificationContract, execution_commit: str
) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "command",
        "execution_commit",
        "initially_clean",
        "single_parent",
        "source",
        "remote_url_serialized",
        "sandbox_mountpoints",
        "local_dvc_remote_configuration",
        "dvc_site_caches",
        "dvc_cache",
    }:
        raise _error("isolated clone record is not exact")
    _validate_command_record(
        value["command"],
        expected_argv=(
            "git",
            "clone",
            "--no-local",
            "--no-hardlinks",
            "--single-branch",
            "--branch",
            "main",
            "<LIVE_ORIGIN_MAIN>",
            "<OWNED_CLONE>",
        ),
        context="isolated clone",
    )
    if {
        "execution_commit": value.get("execution_commit"),
        "initially_clean": value.get("initially_clean"),
        "single_parent": value.get("single_parent"),
        "source": value.get("source"),
        "remote_url_serialized": value.get("remote_url_serialized"),
    } != {
        "execution_commit": execution_commit,
        "initially_clean": True,
        "single_parent": True,
        "source": "live_origin_main",
        "remote_url_serialized": False,
    }:
        raise _error("isolated clone topology/source record drifted")
    if value.get("sandbox_mountpoints") != expected_sandbox_mountpoint_policy() or value.get(
        "sandbox_mountpoints"
    ) != dict(contract.sandbox_mountpoint_policy):
        raise _error("isolated clone sandbox mountpoint record drifted")
    local = value.get("local_dvc_remote_configuration")
    if not isinstance(local, Mapping) or dict(local) != {
        "present": True,
        "regular_file": True,
        "single_link": True,
        "git_ignored": True,
        "source_mode_accepted": "0600_or_0644",
        "clone_mode": "0600",
        "copied_only_into_owned_clone": True,
        "content_read_only_for_private_rebase": True,
        "credential_path_rebased_to_retained_fd": True,
        "credential_target_regular_single_link": True,
        "credential_target_group_or_other_writable": False,
        "effective_configuration_equivalent_except_owned_cache": True,
        "content_path_remote_url_and_credentials_serialized": False,
    }:
        raise _error("private clone-local DVC configuration record drifted")
    expected_site_cache = expected_manifest_clone_dvc_site_caches_record()
    _require_dvc_status_policy_projection(
        expected_site_cache,
        contract=contract,
        context="manifest clone",
    )
    site_cache = value.get("dvc_site_caches")
    if (
        not isinstance(site_cache, Mapping)
        or dict(site_cache) != expected_site_cache
    ):
        raise _error("isolated DVC site-cache record drifted")
    cache = value.get("dvc_cache")
    if not isinstance(cache, Mapping) or dict(cache) != {
        "object_count": 8,
        "declared_payload_bytes": sum(spec.size for spec in contract.dvc_pointers),
        "exact_pointer_objects_only": True,
        "content_addressed_paths_from_declared_md5": True,
        "payload_objects_opened_by_python": False,
        "payloads_decoded": False,
    }:
        raise _error("isolated DVC cache inventory record drifted")


def _validate_restore_records(
    value: Any, *, contract: FinalCertificationContract
) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or len(value) != 8:
        raise _error("DVC restore evidence is not exact eight")
    for ordinal, (record, spec) in enumerate(
        zip(value, contract.dvc_pointers, strict=True), start=1
    ):
        if not isinstance(record, Mapping) or set(record) != {
            "ordinal",
            "pointer_path",
            "output_path",
            "role",
            "pointer_declared_md5",
            "pointer_declared_bytes",
            "pointer_sha256",
            "pull_command",
            "directed_status_command",
            "one_pointer_per_command",
            "restored_output_regular_single_link",
            "cache_object_path_from_declared_md5",
            "dvc_transport_authentication_passed",
            "payload_opened_by_python",
            "payload_decoded",
        }:
            raise _error("one DVC restore record is malformed")
        typed_record = cast(Mapping[str, Any], record)
        if {
            "ordinal": typed_record.get("ordinal"),
            "pointer_path": typed_record.get("pointer_path"),
            "output_path": typed_record.get("output_path"),
            "role": typed_record.get("role"),
            "pointer_declared_md5": typed_record.get("pointer_declared_md5"),
            "pointer_declared_bytes": typed_record.get("pointer_declared_bytes"),
            "one_pointer_per_command": typed_record.get("one_pointer_per_command"),
            "restored_output_regular_single_link": typed_record.get(
                "restored_output_regular_single_link"
            ),
            "cache_object_path_from_declared_md5": typed_record.get(
                "cache_object_path_from_declared_md5"
            ),
            "dvc_transport_authentication_passed": typed_record.get(
                "dvc_transport_authentication_passed"
            ),
            "payload_opened_by_python": typed_record.get(
                "payload_opened_by_python"
            ),
            "payload_decoded": typed_record.get("payload_decoded"),
        } != {
            "ordinal": ordinal,
            "pointer_path": spec.path,
            "output_path": spec.output_path,
            "role": spec.role,
            "pointer_declared_md5": spec.md5,
            "pointer_declared_bytes": spec.size,
            "one_pointer_per_command": True,
            "restored_output_regular_single_link": True,
            "cache_object_path_from_declared_md5": True,
            "dvc_transport_authentication_passed": True,
            "payload_opened_by_python": False,
            "payload_decoded": False,
        }:
            raise _error("one DVC restore identity record drifted")
        pointer_sha = typed_record.get("pointer_sha256")
        if not isinstance(pointer_sha, str) or not SHA256_RE.fullmatch(pointer_sha):
            raise _error("one DVC pointer SHA-256 is malformed")
        _validate_command_record(
            typed_record["pull_command"],
            expected_argv=(
                ".venv/bin/dvc",
                "pull",
                "--no-run-cache",
                "-j",
                "1",
                spec.path,
            ),
            context=f"DVC restore {ordinal}",
        )
        _validate_command_record(
            typed_record["directed_status_command"],
            expected_argv=(
                ".venv/bin/dvc",
                "status",
                "--json",
                spec.path,
            ),
            context=f"directed DVC status {ordinal}",
        )
    return cast(list[Mapping[str, Any]], value)


def _validate_verification_record(
    value: Any,
    *,
    contract: FinalCertificationContract,
    execution_commit: str,
    junit_totals: Mapping[str, int],
    junit_skips: Sequence[Mapping[str, str]],
    openapi_validation: Mapping[str, Any],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "commands",
        "sandbox_smoke",
        "public_test_totals",
        "public_skip_ledger",
        "e2e_totals",
        "openapi_validation",
        "sandbox",
    }:
        raise _error("verification evidence record is not exact")
    if value.get("public_test_totals") != dict(junit_totals) or value.get(
        "public_skip_ledger"
    ) != list(junit_skips):
        raise _error("verification/JUnit totals or skip ledger cross-binding drifted")
    e2e_totals = {
        "tests": 3,
        "passed": 3,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
    }
    if value.get("e2e_totals") != e2e_totals:
        raise _error("verification synthetic E2E totals drifted")
    if value.get("openapi_validation") != dict(openapi_validation):
        raise _error("verification OpenAPI validation record drifted")
    if value.get("sandbox_smoke") != {
        "status": "passed",
        **expected_sandbox_smoke_policy(),
    }:
        raise _error("verification sandbox smoke record drifted")
    commands = value.get("commands")
    if not isinstance(commands, Mapping) or set(commands) != {
        "public_tests",
        "openapi_generation",
        "end_to_end",
        "ty_check",
        "poetry_lock_check",
    }:
        raise _error("verification command registry is not exact")
    _validate_command_record(
        commands["public_tests"],
        expected_argv=_public_command(contract),
        context="public tests",
    )
    _validate_command_record(
        commands["openapi_generation"],
        expected_argv=(
            ".venv/bin/python",
            "-B",
            "src/reporting/build_phase4_final_certification.py",
            "--emit-openapi",
            "tmp/openapi-raw.json",
            "--execution-commit",
            execution_commit,
        ),
        context="OpenAPI generation",
    )
    _validate_command_record(
        commands["end_to_end"],
        expected_argv=_e2e_command(contract),
        context="synthetic E2E",
    )
    _validate_command_record(
        commands["ty_check"], expected_argv=(".venv/bin/ty", "check"), context="ty"
    )
    _validate_command_record(
        commands["poetry_lock_check"],
        expected_argv=("poetry", "check", "--lock"),
        context="Poetry lock",
    )
    sandbox = value.get("sandbox")
    if not isinstance(sandbox, Mapping) or set(sandbox) != {
        "backend",
        "argv_template_prefix",
        "network",
        "postgresql_transport",
        "source_tree",
        "host_virtualenv",
        "effect_sources_retained_by_fd",
        "python_console_scripts_interpreter_retained_by_fd",
        "private_dvc_configuration_masked",
        "forbidden_prefixes_absent",
        "forbidden_paths_masked",
        "restored_payloads_masked",
        "sandbox_mountpoint_policy",
        "sandbox_smoke_policy",
        "cleanup_diagnostic_policy",
        "public_tests_junit_diagnostic_policy",
        "postgres_connection_policy",
        "postgres_startup_stability_policy",
        "postgres_destroy_poll_policy",
        "test_access_guard_policy",
    }:
        raise _error("verification sandbox record is not exact")
    template = sandbox.get("argv_template_prefix")
    startup_stability = sandbox.get("postgres_startup_stability_policy")
    if (
        sandbox.get("backend") != "bubblewrap"
        or sandbox.get("network") != "unshared"
        or sandbox.get("postgresql_transport") != "owned_unix_socket_only"
        or sandbox.get("source_tree") != "read_only"
        or sandbox.get("host_virtualenv") != "read_only"
        or sandbox.get("effect_sources_retained_by_fd") is not True
        or sandbox.get("python_console_scripts_interpreter_retained_by_fd") is not True
        or sandbox.get("private_dvc_configuration_masked") is not True
        or sandbox.get("forbidden_prefixes_absent")
        != list(contract.forbidden_read_prefixes)
        or sandbox.get("forbidden_paths_masked")
        != list(contract.forbidden_read_paths)
        or sandbox.get("restored_payloads_masked")
        != [spec.output_path for spec in contract.dvc_pointers]
        or sandbox.get("postgres_connection_policy")
        != expected_postgres_connection_policy()
        or sandbox.get("postgres_connection_policy")
        != dict(contract.postgres_connection_policy)
        or not isinstance(startup_stability, Mapping)
        or len(startup_stability) != 22
        or startup_stability != expected_postgres_startup_stability_policy()
        or startup_stability != dict(contract.postgres_startup_stability_policy)
        or sandbox.get("postgres_destroy_poll_policy")
        != expected_postgres_destroy_poll_policy()
        or sandbox.get("postgres_destroy_poll_policy")
        != dict(contract.postgres_destroy_poll_policy)
        or sandbox.get("test_access_guard_policy")
        != expected_test_access_guard_policy()
        or sandbox.get("test_access_guard_policy")
        != dict(contract.test_access_guard_policy)
        or sandbox.get("sandbox_mountpoint_policy")
        != expected_sandbox_mountpoint_policy()
        or sandbox.get("sandbox_mountpoint_policy")
        != dict(contract.sandbox_mountpoint_policy)
        or sandbox.get("sandbox_smoke_policy")
        != expected_sandbox_smoke_policy()
        or sandbox.get("sandbox_smoke_policy")
        != dict(contract.sandbox_smoke_policy)
        or sandbox.get("cleanup_diagnostic_policy")
        != expected_cleanup_diagnostic_policy()
        or sandbox.get("cleanup_diagnostic_policy")
        != dict(contract.cleanup_diagnostic_policy)
        or sandbox.get("public_tests_junit_diagnostic_policy")
        != expected_public_tests_junit_diagnostic_policy()
        or sandbox.get("public_tests_junit_diagnostic_policy")
        != dict(contract.public_tests_junit_diagnostic_policy)
        or template != _expected_bwrap_template(contract)
    ):
        raise _error("verification sandbox controls drifted")
    _assert_serialization_safe(_canonical_json(sandbox))
    return cast(Mapping[str, Any], value)


def validate_final_certification_payloads(
    *,
    contract: FinalCertificationContract,
    artifacts: Mapping[str, bytes],
    manifest: Mapping[str, Any],
    execution_commit: str,
    repo_root: Path = PROJECT_ROOT,
) -> None:
    expected_names = [Path(path).name for path in contract.output_paths[:-1]]
    if list(artifacts) != expected_names or len(artifacts) != 7:
        raise _error("final certification artifact order/scope is not exact seven")
    expected_manifest_keys = {
        "schema_version",
        "status",
        "execution_commit",
        "certification_commit_role",
        "paths_outside_exact8_equal_p_cert",
        "r_cert_additions_only",
        "p_cert_authority",
        "p_cert_companion_manifest",
        "published_anchors",
        "published_anchor_records_sha256",
        "dvc_pointer_records",
        "dvc_pointer_records_sha256",
        "dvc_restores",
        "dvc_restore_records_sha256",
        "clone",
        "verification",
        "artifacts",
        "artifact_records_sha256",
        "publication",
        "scientific_boundary",
        "redaction",
    }
    if set(manifest) != expected_manifest_keys:
        raise _error("final certification manifest keys are not exact")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise _error("final certification manifest schema drifted")
    if (
        manifest.get("status") != "completed"
        or manifest.get("certification_commit_role") != "P-CERT"
        or manifest.get("paths_outside_exact8_equal_p_cert") is not True
        or manifest.get("r_cert_additions_only")
        != [spec.path for spec in contract.r_scope]
    ):
        raise _error("final certification status/topology projection drifted")
    if manifest.get("execution_commit") != execution_commit:
        raise _error("final certification manifest execution commit drifted")
    records = manifest.get("artifacts")
    if not isinstance(records, list) or records != [
        _artifact_record(path, artifacts[Path(path).name])
        for path in contract.output_paths[:-1]
    ]:
        raise _error("final certification artifact bindings drifted")
    if manifest.get("artifact_records_sha256") != digest_records(records):
        raise _error("final certification artifact record digest drifted")
    for records_key, digest_key, expected_count in (
        ("published_anchors", "published_anchor_records_sha256", 10),
        ("dvc_pointer_records", "dvc_pointer_records_sha256", 8),
        ("dvc_restores", "dvc_restore_records_sha256", 8),
    ):
        bound = manifest.get(records_key)
        if (
            not isinstance(bound, list)
            or len(bound) != expected_count
            or manifest.get(digest_key) != digest_records(bound)
        ):
            raise _error(f"final certification {records_key} binding drifted")
    effective_root = repo_root.resolve(strict=True)
    effective = _authority_loader(effective_root, contract, require_clean=False)
    effective_commits = _require_effective_authority_commit_binding(
        effective,
        contract=contract,
        execution_commit=execution_commit,
    )
    expected_authority_bindings = {
        "p_cert_authority": {
            "path": AUTHORITY_PATH.as_posix(),
            "bytes": effective["authority_bytes"],
            "sha256": effective["authority_sha256"],
            **effective_commits,
        },
        "p_cert_companion_manifest": {
            "path": AUTHORITY_MANIFEST_PATH.as_posix(),
            "bytes": effective["manifest_bytes"],
            "sha256": effective["manifest_sha256"],
            **effective_commits,
        },
    }
    expected_binding_keys = {
        "path",
        "bytes",
        "sha256",
        *effective_commits,
    }
    for key, expected_binding in expected_authority_bindings.items():
        binding = manifest.get(key)
        if (
            not isinstance(binding, Mapping)
            or set(binding) != expected_binding_keys
            or dict(binding) != expected_binding
        ):
            raise _error(f"final certification {key} effective binding drifted")
    expected_anchors = collect_anchor_input_records(contract, root=effective_root)
    if manifest.get("published_anchors") != expected_anchors:
        raise _error("final certification published anchors are not reconstructible")
    expected_pointers = collect_dvc_pointer_records(contract, root=effective_root)
    if manifest.get("dvc_pointer_records") != expected_pointers:
        raise _error("final certification DVC pointer records are not reconstructible")
    publication = manifest.get("publication")
    if not isinstance(publication, Mapping) or publication != {
        "ordered_paths": list(contract.output_paths),
        "output_count": 8,
        "manifest_written_last": True,
        "no_clobber": contract.no_clobber,
        "concurrency_lock": contract.concurrency_lock,
        "legacy_guard_path_must_be_absent": (
            contract.legacy_guard_path_must_be_absent
        ),
        "external_namespace_mutation_is_stop_condition": (
            contract.external_namespace_mutation_is_stop_condition
        ),
        "noncooperating_same_uid_namespace_mutation": (
            contract.noncooperating_same_uid_namespace_mutation
        ),
        "identity_revalidated_before_and_after_name_cleanup": (
            contract.identity_revalidated_before_and_after_name_cleanup
        ),
        "conditional_unlink_by_inode_claimed": (
            contract.conditional_unlink_by_inode_claimed
        ),
        "cleanup_before_precommit": contract.cleanup_before_precommit,
    }:
        raise _error("final certification publication contract drifted")
    boundary = manifest.get("scientific_boundary")
    if not isinstance(boundary, Mapping) or dict(boundary) != {
        "software_restorability_and_reproducibility_certified": True,
        "scientific_efficacy_claimed": False,
        "e0_u_or_e1_e10_rerun": False,
        "refit_rescore_or_recalibration": False,
        "parquet_payload_opened_by_python": False,
        "parquet_payload_decoded": False,
        "phase5_started": False,
    }:
        raise _error("final certification scientific claim boundary drifted")
    redaction = manifest.get("redaction")
    if not isinstance(redaction, Mapping) or dict(redaction) != {
        "timestamps": "omitted",
        "hostnames": "omitted",
        "absolute_paths": "omitted",
        "remote_urls": "omitted",
        "database_urls": "omitted",
        "credentials": "omitted",
    }:
        raise _error("final certification redaction record drifted")
    for payload in (*artifacts.values(), _canonical_json(manifest)):
        _assert_serialization_safe(payload)
    totals, skips = _validate_junit_certification_properties(
        artifacts["public_tests.xml"],
        contract=contract,
        execution_commit=execution_commit,
    )
    _validate_skip_ledger(skips, contract.test_suite)
    if (
        totals["tests"] != contract.test_suite.collected_test_count
        or totals["skipped"] != contract.test_suite.allowed_skip_count
        or totals["failures"]
        or totals["errors"]
    ):
        raise _error("published JUnit totals or skips drifted")
    try:
        openapi = json.loads(artifacts["openapi.json"])
    except json.JSONDecodeError as exc:
        raise _error("published OpenAPI JSON is invalid") from exc
    if not isinstance(openapi, Mapping):
        raise _error("published OpenAPI is not an object")
    if _canonical_json(openapi) != artifacts["openapi.json"]:
        raise _error("published OpenAPI is not canonical JSON")
    if openapi.get("x-closure-phase4-final-certification") != {
        "execution_commit": execution_commit,
        "scientific_efficacy_claimed": False,
        "forbidden_paths_opened": False,
    }:
        raise _error("published OpenAPI certification binding drifted")
    from src.api.main import create_app

    expected_openapi = copy.deepcopy(create_app().openapi())
    expected_openapi["x-closure-phase4-final-certification"] = {
        "execution_commit": execution_commit,
        "scientific_efficacy_claimed": False,
        "forbidden_paths_opened": False,
    }
    if openapi != expected_openapi:
        raise _error("published OpenAPI is not reconstructible from the P-CERT app")
    openapi_validation = validate_openapi_document(
        cast(Mapping[str, Any], openapi),
        root=repo_root,
        contract=contract,
    )
    verification = _validate_verification_record(
        manifest.get("verification"),
        contract=contract,
        execution_commit=execution_commit,
        junit_totals=totals,
        junit_skips=skips,
        openapi_validation=openapi_validation,
    )
    if artifacts["test_report.md"] != _build_test_report(
        execution_commit=execution_commit,
        command=_public_command(contract),
        totals=totals,
        skip_ledger=skips,
        suite=contract.test_suite,
    ):
        raise _error("published public-test report is not reconstructible")
    if artifacts["openapi_contract_report.md"] != _build_openapi_report(
        execution_commit=execution_commit,
        validation=openapi_validation,
        openapi_sha256=sha256_bytes(artifacts["openapi.json"]),
    ):
        raise _error("published OpenAPI report is not reconstructible")
    e2e_totals = cast(Mapping[str, int], verification["e2e_totals"])
    if artifacts["end_to_end_report.md"] != _build_e2e_report(
        execution_commit=execution_commit,
        command=_e2e_command(contract),
        totals=e2e_totals,
    ):
        raise _error("published E2E report is not reconstructible")
    if artifacts["FINAL_DOCTORAL_CERTIFICATION_REPORT.md"] != _final_report(
        execution_commit
    ):
        raise _error("final doctoral certification report is not reconstructible")

    _validate_clone_record(
        manifest.get("clone"),
        contract=contract,
        execution_commit=execution_commit,
    )
    restore_records = _validate_restore_records(
        manifest.get("dvc_restores"), contract=contract
    )
    pointer_records = cast(Sequence[Mapping[str, Any]], manifest["dvc_pointer_records"])
    for restore, pointer, spec in zip(
        restore_records,
        pointer_records,
        contract.dvc_pointers,
        strict=True,
    ):
        if (
            pointer.get("path") != spec.path
            or pointer.get("role") != spec.role
            or pointer.get("output_path") != spec.output_path
            or pointer.get("payload_md5") != spec.md5
            or pointer.get("payload_bytes") != spec.size
            or pointer.get("sha256") != restore.get("pointer_sha256")
        ):
            raise _error("DVC pointer/restore binding is not reconstructible")
    try:
        environment = json.loads(artifacts["environment.json"])
    except json.JSONDecodeError as exc:
        raise _error("published environment JSON is invalid") from exc
    if not isinstance(environment, Mapping) or _canonical_json(environment) != artifacts[
        "environment.json"
    ]:
        raise _error("published environment is not canonical JSON")
    expected_environment_keys = {
        "schema_version",
        "execution_commit",
        "certification_tree",
        "paths_outside_exact8_equal_p_cert",
        "runtime_versions",
        "dependency_lock",
        "project_configuration",
        "database",
        "isolation",
        "dvc",
        "timestamps_hostnames_absolute_paths_remote_urls_credentials",
    }
    runtime_versions = environment.get("runtime_versions")
    expected_environment_dvc = expected_environment_dvc_record()
    _require_dvc_status_policy_projection(
        expected_environment_dvc,
        contract=contract,
        context="environment",
    )
    if (
        not isinstance(runtime_versions, Mapping)
        or dict(runtime_versions) != dict(contract.expected_runtime_versions)
    ):
        raise _error("published runtime versions differ from the sealed contract")
    if (
        set(environment) != expected_environment_keys
        or environment.get("schema_version")
        != "closure_v1_phase4_final_environment_v1"
        or environment.get("execution_commit") != execution_commit
        or environment.get("certification_tree") != "P-CERT"
        or environment.get("paths_outside_exact8_equal_p_cert") is not True
        or environment.get("dependency_lock")
        != next(
            record
            for record in cast(list[Mapping[str, Any]], manifest["published_anchors"])
            if record["path"] == "poetry.lock"
        )
        or environment.get("project_configuration")
        != next(
            record
            for record in cast(list[Mapping[str, Any]], manifest["published_anchors"])
            if record["path"] == "pyproject.toml"
        )
        or environment.get("database")
        != {
            "image": POSTGRES_IMAGE,
            "network": "none",
            "transport": "owned_unix_socket",
            "cleaned_after_execution": True,
            "url_path_or_credentials_serialized": False,
        }
        or environment.get("isolation") != verification["sandbox"]
        or environment.get("dvc") != expected_environment_dvc
        or environment.get(
            "timestamps_hostnames_absolute_paths_remote_urls_credentials"
        )
        != "omitted"
        or not all(
            isinstance(value, str)
            and value
            and "\n" not in value
            and "://" not in value
            and not value.startswith("/")
            for value in runtime_versions.values()
        )
        or not re.fullmatch(
            r"Python [0-9]+(?:\.[0-9]+){1,3}",
            cast(str, runtime_versions.get("python", "")),
        )
        or not re.fullmatch(
            r"[0-9]+(?:\.[0-9]+){1,3}",
            cast(str, runtime_versions.get("dvc", "")),
        )
        or not re.fullmatch(
            r"ty [0-9]+(?:\.[0-9]+){1,3}",
            cast(str, runtime_versions.get("ty", "")),
        )
        or not re.fullmatch(
            r"git version [0-9]+(?:\.[0-9]+){1,3}",
            cast(str, runtime_versions.get("git", "")),
        )
        or not re.fullmatch(
            r"Poetry \(version [0-9]+(?:\.[0-9]+){1,3}\)",
            cast(str, runtime_versions.get("poetry", "")),
        )
        or not re.fullmatch(
            r"bubblewrap [0-9]+(?:\.[0-9]+){1,3}",
            cast(str, runtime_versions.get("bubblewrap", "")),
        )
        or not re.fullmatch(
            r"[0-9]+(?:\.[0-9]+){1,3}",
            cast(str, runtime_versions.get("docker_client", "")),
        )
        or not re.fullmatch(
            r"[0-9]+(?:\.[0-9]+){1,3}",
            cast(str, runtime_versions.get("docker_server", "")),
        )
    ):
        raise _error("published environment record is not reconstructible")


def _read_regular_at(directory: DirectoryHandle, name: str) -> bytes:
    descriptor = os.open(
        name,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
        dir_fd=directory.fd,
    )
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) != 0o644
        ):
            raise _error("published R-CERT file identity/mode drifted")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
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
            raise _error("published R-CERT file changed during final readback")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _verify_final_publication_root(
    *,
    root: Path,
    contract: FinalCertificationContract,
    products: ExecutionProducts,
    expected_directory_identity: tuple[int, int],
) -> None:
    if os.path.lexists(root / GUARD_PATH):
        raise _error("legacy final-certification guard path appeared")
    try:
        chain, _ = _open_directory_chain(
            root, CERTIFICATION_ROOT, create_missing=False
        )
    except BaseException as exc:
        raise _error("R-CERT final root rebind failed") from exc
    try:
        directory = chain[-1]
        if (directory.device, directory.inode) != expected_directory_identity:
            raise _error("R-CERT root changed after run-namespace cleanup")
        expected_payloads = {
            **dict(products.artifacts),
            Path(contract.output_paths[-1]).name: _canonical_json(products.manifest),
        }
        if set(os.listdir(directory.fd)) != set(expected_payloads):
            raise _error("R-CERT final root scope drifted after run-namespace cleanup")
        for name, expected in expected_payloads.items():
            if _read_regular_at(directory, name) != expected:
                raise _error(f"R-CERT final bytes drifted: {name}")
        if os.path.lexists(root / GUARD_PATH):
            raise _error("legacy final-certification guard path appeared")
    finally:
        for handle in reversed(chain):
            handle.close()


def publish_final_certification_bundle(
    *,
    repo_root: Path,
    contract: FinalCertificationContract,
    products: ExecutionProducts,
    failure_after_links: int | None = None,
    run_guard: RunGuard | None = None,
    publication_validator: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Publish exact8 with anchored hardlink no-clobber and owned rollback."""

    root = repo_root.resolve(strict=True)
    lease = run_guard or _acquire_run_guard(root, contract)
    output_chain: list[DirectoryHandle] = []
    output_handle: DirectoryHandle | None = None
    stage_handle: DirectoryHandle | None = None
    output_created = False
    stage_created = False
    output_identity: tuple[int, int] | None = None
    stage_identity: tuple[int, int] | None = None
    staged: list[OwnedFileAt] = []
    published: list[OwnedFileAt] = []
    succeeded = False
    error: BaseException | None = None
    try:
        payloads = {
            **dict(products.artifacts),
            Path(contract.output_paths[-1]).name: _canonical_json(products.manifest),
        }
        expected_names = [Path(path).name for path in contract.output_paths]
        if list(payloads) != expected_names:
            raise _error("R-CERT publication order is not exact8 manifest-last")
        stage_name = f"stage-{secrets.token_hex(16)}"
        stage_handle = _mkdir_owned_at(
            lease.parent,
            stage_name,
            mode=0o700,
            context="R-CERT private stage directory",
        )
        stage_created = True
        stage_identity = (stage_handle.device, stage_handle.inode)
        for name, payload in payloads.items():
            staged.append(_create_owned_file_at(stage_handle, name, payload))

        output_relative = Path(contract.output_paths[0]).parent
        if output_relative != CERTIFICATION_ROOT:
            raise _error("R-CERT root drifted from the sealed contract")
        output_chain, _ = _open_directory_chain(
            root, output_relative.parent, create_missing=False
        )
        output_parent = output_chain[-1]
        try:
            os.stat(output_relative.name, dir_fd=output_parent.fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise _error("R-CERT namespace already exists")
        if publication_validator is not None:
            publication_validator("before_first_link")
        output_handle = _mkdir_owned_at(
            output_parent,
            output_relative.name,
            mode=0o755,
            context="R-CERT output directory",
        )
        output_created = True
        output_identity = (output_handle.device, output_handle.inode)
        for index, (path_text, staged_entry) in enumerate(
            zip(contract.output_paths, staged, strict=True), start=1
        ):
            if Path(path_text).parent != output_relative:
                raise _error("R-CERT output escaped the exact namespace")
            if index == len(contract.output_paths) and publication_validator is not None:
                publication_validator("before_manifest_link")
            os.link(
                staged_entry.name,
                Path(path_text).name,
                src_dir_fd=stage_handle.fd,
                dst_dir_fd=output_handle.fd,
                follow_symlinks=False,
            )
            target_meta = os.stat(
                Path(path_text).name,
                dir_fd=output_handle.fd,
                follow_symlinks=False,
            )
            if (
                (target_meta.st_dev, target_meta.st_ino)
                != (staged_entry.device, staged_entry.inode)
                or not stat.S_ISREG(target_meta.st_mode)
                or target_meta.st_nlink != 2
            ):
                raise _error("R-CERT hardlink identity drifted")
            published.append(
                OwnedFileAt(
                    output_handle,
                    Path(path_text).name,
                    target_meta.st_dev,
                    target_meta.st_ino,
                )
            )
            if failure_after_links == index:
                raise _error("synthetic R-CERT publication failure")
        while staged:
            entry = staged[-1]
            os.chmod(
                entry.name,
                0o644,
                dir_fd=stage_handle.fd,
                follow_symlinks=False,
            )
            _unlink_owned_at(entry, context=f"R-CERT staged {entry.name}")
            staged.pop()
        os.fsync(output_handle.fd)
        os.fsync(output_parent.fd)
        for entry in published:
            metadata = os.stat(
                entry.name, dir_fd=output_handle.fd, follow_symlinks=False
            )
            if (
                (metadata.st_dev, metadata.st_ino) != (entry.device, entry.inode)
                or metadata.st_nlink != 1
                or stat.S_IMODE(metadata.st_mode) != 0o644
            ):
                raise _error("published R-CERT mode/link/identity drifted")
        if publication_validator is not None:
            publication_validator("after_all_links")
        succeeded = True
    except BaseException as exc:
        error = exc

    cleanup_error: BaseException | None = None
    outputs_rolled_back = False

    def rollback_outputs() -> None:
        nonlocal outputs_rolled_back, output_created
        if outputs_rolled_back or not output_created or not output_chain:
            return
        while published:
            entry = published[-1]
            _unlink_owned_at(entry, context=f"R-CERT output {entry.name}")
            published.pop()
        parent = output_chain[-1]
        if output_identity is None:
            raise _error("R-CERT output directory identity is absent")
        _remove_owned_empty_directory_at(
            parent,
            CERTIFICATION_ROOT.name,
            device=output_identity[0],
            inode=output_identity[1],
            context="R-CERT output directory",
        )
        output_created = False
        outputs_rolled_back = True

    # Stage cleanup is mandatory before the cooperative lease can be released.
    if stage_handle is not None:
        while staged:
            entry = staged[-1]
            try:
                _unlink_owned_at(entry, context=f"R-CERT staged {entry.name}")
            except BaseException as exc:
                cleanup_error = cleanup_error or exc
                break
            staged.pop()
        stage_handle.close()
    if stage_created:
        try:
            if stage_identity is None:
                raise _error("R-CERT stage identity is absent")
            _remove_owned_empty_directory_at(
                lease.parent,
                stage_name,
                device=stage_identity[0],
                inode=stage_identity[1],
                context="R-CERT stage directory",
            )
            stage_created = False
        except BaseException as exc:
            cleanup_error = cleanup_error or exc

    if not succeeded or cleanup_error is not None:
        succeeded = False
        try:
            rollback_outputs()
        except BaseException as exc:
            cleanup_error = cleanup_error or exc

    try:
        if not lease.removed:
            lease.release()
    except BaseException as exc:
        cleanup_error = cleanup_error or exc
        if succeeded:
            succeeded = False
            error = _error("R-CERT run-namespace cleanup failed after publication")
            try:
                rollback_outputs()
            except BaseException as rollback_error:
                cleanup_error = cleanup_error or rollback_error

    # Rebind from the repository root only after the ignored run namespace is
    # gone.  The original output/parent descriptors stay open so a parent
    # rename or replacement can still be rolled back without touching foreign
    # paths.
    if succeeded and cleanup_error is None:
        try:
            if output_identity is None:
                raise _error("R-CERT output identity is absent at final rebind")
            if publication_validator is not None:
                publication_validator("after_run_namespace_cleanup")
            _verify_final_publication_root(
                root=root,
                contract=contract,
                products=products,
                expected_directory_identity=output_identity,
            )
            if publication_validator is not None:
                publication_validator("before_success_return")
            _verify_final_publication_root(
                root=root,
                contract=contract,
                products=products,
                expected_directory_identity=output_identity,
            )
            if publication_validator is not None:
                publication_validator("after_final_readback")
        except BaseException as exc:
            succeeded = False
            error = exc
            try:
                rollback_outputs()
            except BaseException as rollback_error:
                cleanup_error = cleanup_error or rollback_error

    if output_handle is not None:
        output_handle.close()
    for handle in reversed(output_chain):
        handle.close()
    lease.close()
    if cleanup_error is not None:
        raise _error("R-CERT publication cleanup failed closed") from cleanup_error
    if not succeeded:
        if isinstance(error, FinalCertificationBuildError):
            raise error
        raise _error("R-CERT publication failed") from error
    manifest_payload = _canonical_json(products.manifest)
    return {
        "status": "certification_bundle_written_unpublished",
        "execution_commit": products.manifest["execution_commit"],
        "output_count": 8,
        "manifest_written_last": True,
        "outputs": [
            *cast(list[dict[str, Any]], products.manifest["artifacts"]),
            _artifact_record(contract.output_paths[-1], manifest_payload),
        ],
    }


def _revalidate_publication_gate(
    *,
    root: Path,
    contract: FinalCertificationContract,
    execution_commit: str,
    expected_authority: Mapping[str, Any],
    expected_anchors: Sequence[Mapping[str, Any]],
    expected_pointers: Sequence[Mapping[str, Any]],
    expected_local_remote: Mapping[str, Any],
    stage: str,
    repository_lease: RepositoryRootLease | None = None,
    main_site_cache_lease: MainDvcSiteCacheLease | None = None,
) -> None:
    stage_counts = {
        "before_first_link": 0,
        "before_manifest_link": 7,
        "after_all_links": 8,
        "after_run_namespace_cleanup": 8,
        "before_success_return": 8,
        "after_final_readback": 8,
    }
    if stage not in stage_counts:
        raise _error("unknown R-CERT publication validation stage")
    if repository_lease is not None:
        repository_lease.revalidate(context=f"before publication gate {stage}")
    if main_site_cache_lease is not None:
        main_site_cache_lease.revalidate(
            context=f"before publication gate {stage}"
        )
    if os.path.lexists(root / GUARD_PATH):
        raise _error("legacy final-certification guard path appeared during publication")
    state = _capture_main_state(root)
    if (
        state["head"] != execution_commit
        or state["main"] != execution_commit
        or state["origin_main"] != execution_commit
        or state["origin_head"] != execution_commit
        or state["cached_diff"]
        or state["unstaged_diff"]
    ):
        raise _error("P-CERT refs or tracked tree drifted during publication")
    lines = [line for line in cast(str, state["status"]).splitlines() if line]
    observed_untracked: set[str] = set()
    for line in lines:
        if not line.startswith("?? "):
            raise _error("non-R-CERT repository state appeared during publication")
        observed_untracked.add(line[3:])
    expected_untracked = set(contract.output_paths[: stage_counts[stage]])
    if observed_untracked != expected_untracked:
        raise _error("R-CERT output publication scope/order checkpoint drifted")
    current_authority = _authority_loader(root, contract, require_clean=False)
    if current_authority != expected_authority:
        raise _error("P-CERT authority changed during R-CERT publication")
    _reconstruct_main_dvc_static_boundary(
        root=root,
        contract=contract,
        context=f"R-CERT publication gate {stage}",
        expected_anchors=expected_anchors,
        expected_pointers=expected_pointers,
        main_site_cache_lease=main_site_cache_lease,
    )
    if validate_local_dvc_remote_configuration(root=root) != dict(
        expected_local_remote
    ):
        raise _error("private local DVC remote metadata changed during publication")
    if main_site_cache_lease is not None:
        main_site_cache_lease.revalidate(
            context=f"after publication gate {stage}"
        )
    if repository_lease is not None:
        repository_lease.revalidate(context=f"after publication gate {stage}")


def _prepare_owned_workspace(
    *,
    root: Path,
    lease: RunGuard,
    repository_lease: RepositoryRootLease,
) -> PreparedWorkspace:
    """Create the private namespace with fail-closed cooperative cleanup."""

    owned_tmp: Path | None = None
    owned_tmp_identity: tuple[int, int] | None = None
    try:
        owned_tmp, owned_tmp_identity = lease.create_work_directory()
        clone_root = owned_tmp / "clone"
        cache_handle = lease.create_work_subdirectory("dvc-cache", mode=0o700)
        site_cache_handle = lease.create_work_subdirectory(
            "dvc-site-cache", mode=0o700
        )
        version_site_cache_handle = lease.create_work_subdirectory(
            "dvc-version-site-cache", mode=0o700
        )
        sandbox_handle = lease.create_work_subdirectory("sandbox-tmp", mode=0o700)
        socket_handle = lease.create_work_subdirectory("postgres-socket", mode=0o700)
        mask_handle = lease.create_work_subdirectory("masks", mode=0o700)
        os.fchmod(socket_handle.fd, 0o777)
        _prepare_masks(mask_handle)
        lease.revalidate_work_namespace(context="after work namespace preparation")
        repository_lease.revalidate(context="before initial main-state snapshot")
        source_before = _capture_main_state(root)
        repository_lease.revalidate(context="after initial main-state snapshot")
        if lease.work is None:
            raise _error("owned work handle is absent after preparation")
        work_handle = lease.work
        mask_inventory = _scan_work_inventory(mask_handle)
        if _scan_work_inventory(mask_handle) != mask_inventory:
            raise _error("sandbox mask inventory changed while freezing")
        cache_inventory = _scan_work_inventory(cache_handle)
        if cache_inventory or _scan_work_inventory(cache_handle):
            raise _error("owned DVC cache was not empty after workspace preparation")
        site_cache_inventory = _scan_work_inventory(site_cache_handle)
        if site_cache_inventory or _scan_work_inventory(site_cache_handle):
            raise _error(
                "owned DVC site cache was not empty after workspace preparation"
            )
        version_site_cache_inventory = _scan_work_inventory(
            version_site_cache_handle
        )
        if version_site_cache_inventory or _scan_work_inventory(
            version_site_cache_handle
        ):
            raise _error(
                "owned DVC version site cache was not empty after workspace preparation"
            )
        site_cache_root_identity = _site_cache_root_identity(
            site_cache_handle,
            expected_mode=0o700,
            context="owned DVC site cache after workspace preparation",
        )
        version_site_cache_root_identity = _site_cache_root_identity(
            version_site_cache_handle,
            expected_mode=0o700,
            context="owned DVC version site cache after workspace preparation",
        )
        return PreparedWorkspace(
            owned_tmp=owned_tmp,
            owned_tmp_identity=owned_tmp_identity,
            clone_root=clone_root,
            cache_handle=cache_handle,
            site_cache_handle=site_cache_handle,
            version_site_cache_handle=version_site_cache_handle,
            sandbox_handle=sandbox_handle,
            socket_handle=socket_handle,
            mask_handle=mask_handle,
            work_handle=work_handle,
            source_before=source_before,
            lease_parent_binding=_directory_binding(lease.parent),
            work_binding=_directory_binding(work_handle),
            repository_root_binding=_directory_binding(repository_lease.root),
            mask_inventory=mask_inventory,
            cache_inventory=cache_inventory,
            site_cache_inventory=site_cache_inventory,
            version_site_cache_inventory=version_site_cache_inventory,
            site_cache_root_identity=site_cache_root_identity,
            version_site_cache_root_identity=version_site_cache_root_identity,
        )
    except BaseException as primary:
        cleanup_error: BaseException | None = None
        if owned_tmp is not None and owned_tmp_identity is not None and lease.work is not None:
            try:
                observed_top = set(os.listdir(lease.work.fd))
                expected_top = set(lease.work_subdirectories)
                known_state = observed_top == expected_top
                for name, handle in lease.work_subdirectories.items():
                    inventory = _scan_work_inventory(handle)
                    if name == "masks":
                        expected_mask_paths = {
                            "empty",
                            "empty-file",
                            "empty-private-config",
                        }
                        known_state = known_state and (
                            not inventory
                            or (
                                set(inventory) == expected_mask_paths
                                and inventory["empty"].kind == "directory"
                                and inventory["empty"].mode == 0o555
                                and inventory["empty-file"].kind == "regular"
                                and inventory["empty-file"].mode == 0o400
                                and inventory["empty-file"].link_count == 1
                                and inventory["empty-private-config"].kind
                                == "regular"
                                and inventory["empty-private-config"].mode == 0o600
                                and inventory["empty-private-config"].link_count == 1
                            )
                        )
                    else:
                        known_state = known_state and not inventory
                if not known_state:
                    raise _error(
                        "failed workspace contains an unowned entry; preserved"
                    )
                lease.seal_work_inventory()
                lease.remove_work_directory(owned_tmp, owned_tmp_identity)
            except BaseException as exc:
                cleanup_error = exc
        try:
            if not lease.removed:
                lease.release()
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
        finally:
            lease.close()
        if cleanup_error is not None:
            raise _error("failed workspace preparation cleanup failed closed") from cleanup_error
        raise primary


def build_phase4_final_certification(*, repo_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Execute one complete P-CERT -> R-CERT certification transaction."""

    root = repo_root.resolve(strict=True)
    preflight = check_phase4_final_certification(repo_root=root)
    contract = load_contract(root=root)
    execution_commit = cast(str, preflight["execution_commit"])
    authority = cast(Mapping[str, Any], preflight["authority"])
    repository_lease = _open_repository_root_lease(root)
    try:
        lease = _acquire_run_guard(root, contract)
    except BaseException:
        repository_lease.close()
        raise
    try:
        prepared = _prepare_owned_workspace(
            root=root,
            lease=lease,
            repository_lease=repository_lease,
        )
    except BaseException:
        repository_lease.close()
        raise
    owned_tmp = prepared.owned_tmp
    owned_tmp_identity = prepared.owned_tmp_identity
    clone_root = prepared.clone_root
    cache_handle = prepared.cache_handle
    site_cache_handle = prepared.site_cache_handle
    version_site_cache_handle = prepared.version_site_cache_handle
    sandbox_handle = prepared.sandbox_handle
    socket_handle = prepared.socket_handle
    mask_handle = prepared.mask_handle
    cache_root = cache_handle.path
    site_cache_root = site_cache_handle.path
    sandbox_tmp = sandbox_handle.path
    mask_root = mask_handle.path
    source_before = prepared.source_before
    work_handle = prepared.work_handle
    lease_parent_binding = prepared.lease_parent_binding
    work_binding = prepared.work_binding
    repository_root_binding = prepared.repository_root_binding
    site_cache_root_identity = prepared.site_cache_root_identity
    version_site_cache_root_identity = prepared.version_site_cache_root_identity
    site_cache_root_frozen = False
    version_site_cache_root_frozen = False
    frozen_execution_inventories: dict[
        str, tuple[DirectoryHandle, Mapping[str, WorkInventoryEntry]]
    ] = {
        "sandbox masks": (mask_handle, prepared.mask_inventory),
    }
    cleanup_execution_inventories: dict[
        str, tuple[DirectoryHandle, Mapping[str, WorkInventoryEntry]]
    ] = {
        "sandbox masks": (mask_handle, prepared.mask_inventory),
        "DVC cache": (cache_handle, prepared.cache_inventory),
        "DVC site cache": (
            site_cache_handle,
            prepared.site_cache_inventory,
        ),
        "DVC version site cache": (
            version_site_cache_handle,
            prepared.version_site_cache_inventory,
        ),
    }
    main_site_cache_lease: MainDvcSiteCacheLease | None = None

    def _validate_execution_namespace(stage: str) -> None:
        nonlocal work_binding, site_cache_root_identity
        nonlocal version_site_cache_root_identity
        nonlocal clone_mountpoints
        repository_lease.revalidate(context=f"before execution checkpoint {stage}")
        lease.revalidate_work_namespace(context=stage)
        if _directory_binding(lease.parent) != lease_parent_binding:
            raise _error(f"owned lease-parent namespace drifted at checkpoint: {stage}")
        if _directory_binding(repository_lease.root) != repository_root_binding:
            raise _error(f"repository-root namespace drifted at checkpoint: {stage}")
        current_work_binding = _directory_binding(work_handle)
        if stage == "after_git_clone":
            _require_exact_clone_work_transition(work_binding, current_work_binding)
            clone_handle = lease.open_work_subdirectory("clone")
            clone_mountpoints = _create_clone_mountpoints(clone_handle)
            repeated_work_binding = _directory_binding(work_handle)
            if repeated_work_binding != current_work_binding:
                raise _error("owned work namespace drifted while registering clone")
            first_clone_inventory = _scan_work_inventory(clone_handle)
            if _scan_work_inventory(clone_handle) != first_clone_inventory:
                raise _error("owned clone inventory changed while registering")
            cleanup_execution_inventories["clone"] = (
                clone_handle,
                first_clone_inventory,
            )
            work_binding = current_work_binding
        elif current_work_binding != work_binding:
            raise _error(f"owned work namespace drifted at checkpoint: {stage}")
        if clone_mountpoints is not None:
            clone_mountpoints.revalidate(
                context=f"execution checkpoint {stage} clone mountpoints"
            )
        for name, (handle, expected_inventory) in frozen_execution_inventories.items():
            if _scan_work_inventory(handle) != dict(expected_inventory):
                raise _error(
                    f"frozen owned {name} inventory drifted at checkpoint: {stage}"
                )
        successful_prefreeze_restore_transition = (
            not site_cache_root_frozen
            and stage.startswith("after_dvc_")
            and stage != "after_dvc_version"
        )
        site_cache_root_identity = _revalidate_owned_site_cache_root(
            site_cache_handle,
            site_cache_root_identity,
            allow_successful_dvc_transition=(
                successful_prefreeze_restore_transition
            ),
            context=f"owned DVC site cache at checkpoint {stage}",
        )
        successful_prefreeze_version_transition = (
            not version_site_cache_root_frozen and stage == "after_dvc_version"
        )
        version_site_cache_root_identity = _revalidate_owned_site_cache_root(
            version_site_cache_handle,
            version_site_cache_root_identity,
            allow_successful_dvc_transition=(
                successful_prefreeze_version_transition
            ),
            context=f"owned DVC version site cache at checkpoint {stage}",
        )
        if main_site_cache_lease is not None:
            main_site_cache_lease.revalidate(
                context=f"execution checkpoint {stage}"
            )
        current_source = _capture_main_state(root)
        repository_lease.revalidate(context=f"after execution checkpoint {stage}")
        if current_source != source_before:
            raise _error(f"main source tree drifted at execution checkpoint: {stage}")

    def validate_execution_namespace(stage: str) -> None:
        try:
            _validate_execution_namespace(stage)
        except FinalCertificationBuildError as exc:
            if exc.command_failure is not None or exc.internal_failure is not None:
                raise
            raise _internal_error(
                "owned execution namespace validation failed closed",
                stage="namespace_validation",
                category="namespace_invariant_mismatch",
            ) from None
        except BaseException:
            raise _internal_error(
                "owned execution namespace validation failed closed",
                stage="namespace_validation",
                category="namespace_invariant_mismatch",
            ) from None

    def bracket(stage: str, operation: Callable[[], Any]) -> Any:
        validate_execution_namespace(f"before_{stage}")
        value = operation()
        validate_execution_namespace(f"after_{stage}")
        return value

    def failed_tree_cleanup_assessment() -> CleanupAssessment:
        reason_codes: set[str] = set()
        if database_owner is not None:
            reason_codes.add("database_owner_retained")
        if lease.work is None:
            reason_codes.add("frozen_inventory_drift")
        elif set(os.listdir(lease.work.fd)) != set(lease.work_subdirectories):
            reason_codes.add("frozen_inventory_drift")
        if clone_mountpoints is None:
            reason_codes.add("frozen_inventory_drift")
        else:
            try:
                clone_mountpoints.revalidate(
                    context="failed clone mountpoint cleanup assessment"
                )
            except FinalCertificationBuildError:
                reason_codes.add("frozen_inventory_drift")
        for frozen_name in (
            "sandbox masks",
            "clone",
            "DVC cache",
            "DVC site cache",
            "DVC version site cache",
        ):
            frozen = cleanup_execution_inventories.get(frozen_name)
            try:
                if frozen is None or _scan_work_inventory(frozen[0]) != dict(
                    frozen[1]
                ):
                    reason_codes.add("frozen_inventory_drift")
            except FinalCertificationBuildError:
                reason_codes.add("frozen_inventory_drift")
        try:
            if _scan_work_inventory(socket_handle):
                reason_codes.add("socket_inventory_nonempty")
        except FinalCertificationBuildError:
            reason_codes.add("socket_inventory_nonempty")
        try:
            _revalidate_owned_site_cache_root(
                site_cache_handle,
                site_cache_root_identity,
                allow_successful_dvc_transition=False,
                context="failed owned DVC site cache",
            )
        except FinalCertificationBuildError:
            reason_codes.add("owned_site_cache_drift")
        try:
            _revalidate_owned_site_cache_root(
                version_site_cache_handle,
                version_site_cache_root_identity,
                allow_successful_dvc_transition=False,
                context="failed owned DVC version site cache",
            )
        except FinalCertificationBuildError:
            reason_codes.add("owned_site_cache_drift")
        allowed_sandbox = {
            "public-tests-raw.xml",
            "openapi-raw.json",
            "e2e-raw.xml",
        }
        try:
            sandbox_inventory = _scan_work_inventory(sandbox_handle)
            if not set(sandbox_inventory).issubset(allowed_sandbox) or not all(
                entry.kind == "regular"
                and entry.link_count == 1
                and entry.mode in {0o600, 0o644}
                for entry in sandbox_inventory.values()
            ):
                reason_codes.add("sandbox_inventory_drift")
        except FinalCertificationBuildError:
            reason_codes.add("sandbox_inventory_drift")
        if reason_codes:
            return CleanupAssessment(
                status="failed_closed",
                namespace_preserved=True,
                reason_codes=tuple(sorted(reason_codes)),
            )
        return CleanupAssessment(
            status="ready_for_owned_cleanup",
            namespace_preserved=False,
            reason_codes=(),
        )

    database_owner: OwnedPostgres | None = None
    database_stop_attempted = False
    clone_mountpoints: CloneMountpointLease | None = None
    verification_runtime: VerificationRuntimeLease | None = None
    installed_configuration: InstalledDvcConfiguration | None = None
    dvc_runtime: AnchoredPythonScriptRuntime | None = None
    active_error: BaseException | None = None
    result: dict[str, Any] | None = None
    work_removed = False
    publisher_consumed_lease = False

    def mark_database_stop_attempted() -> None:
        nonlocal database_stop_attempted
        if database_stop_attempted:
            raise _error("owned PostgreSQL stop command was already attempted")
        database_stop_attempted = True

    def retain_database_owner(owner: OwnedPostgres) -> None:
        nonlocal database_owner
        if database_owner is not None and (
            database_owner.name != owner.name
            or database_owner.container_id != owner.container_id
        ):
            raise _error("owned PostgreSQL handoff identity drifted")
        database_owner = owner

    try:
        main_site_cache_lease = _open_main_dvc_site_cache_lease(root)
        # Close the preflight-to-flock race before any clone or egress.
        validate_execution_namespace("before P-CERT authority revalidation")
        if _authority_loader(root, contract) != authority:
            raise _error("P-CERT authority drifted while acquiring the run lease")
        validate_execution_namespace("after P-CERT authority revalidation")
        clone_record = _clone_exact_p(
            source_root=root,
            clone_root=clone_root,
            execution_commit=execution_commit,
            namespace_validator=validate_execution_namespace,
        )
        if "clone" not in lease.work_subdirectories:
            raise _error("isolated clone was not identity-bound during creation")
        if clone_mountpoints is None:
            raise _error("clone sandbox mountpoints were not identity-bound")
        clone_record = {
            **clone_record,
            "sandbox_mountpoints": dict(contract.sandbox_mountpoint_policy),
        }
        validate_execution_namespace("after isolated clone registration")
        clone_handle = lease.work_subdirectories["clone"]
        dvc_runtime = bracket(
            "retained_dvc_runtime_open",
            lambda: _open_python_script_runtime(
                root,
                Path(".venv/bin/dvc"),
                context="retained DVC certification runtime",
            ),
        )
        if dvc_runtime is None:
            raise _error("retained DVC runtime disappeared after opening")
        retained_dvc_runtime = dvc_runtime
        runtime_before = bracket(
            "runtime_versions_before_private_config_or_pull",
            lambda: _sealed_runtime_versions(
                root,
                contract=contract,
                dvc_runtime=retained_dvc_runtime,
                dvc_clone_handle=clone_handle,
                dvc_site_cache_handle=version_site_cache_handle,
                dvc_private_pass_fds=(),
                namespace_validator=validate_execution_namespace,
            ),
        )
        first_version_site_cache_inventory = _scan_work_inventory(
            version_site_cache_handle
        )
        if (
            _scan_work_inventory(version_site_cache_handle)
            != first_version_site_cache_inventory
        ):
            raise _error("DVC version site-cache inventory changed while freezing")
        frozen_execution_inventories["DVC version site cache"] = (
            version_site_cache_handle,
            first_version_site_cache_inventory,
        )
        cleanup_execution_inventories["DVC version site cache"] = (
            version_site_cache_handle,
            first_version_site_cache_inventory,
        )
        _revalidate_owned_site_cache_root(
            version_site_cache_handle,
            version_site_cache_root_identity,
            allow_successful_dvc_transition=False,
            context="owned DVC version site cache at initial version seal",
        )
        version_site_cache_root_frozen = True
        _revalidate_retained_dvc_runtime(
            retained_dvc_runtime,
            source_root=root,
            context="retained DVC runtime after initial version seal",
        )
        validate_execution_namespace("after frozen DVC version site cache")
        installed_configuration = bracket(
            "private_dvc_configuration_rebase",
            lambda: _install_local_dvc_remote_configuration(
                source_root=root, clone_root=clone_root
            ),
        )
        clone_record = {
            **clone_record,
            "local_dvc_remote_configuration": dict(
                installed_configuration.public_record
            ),
            "dvc_site_caches": expected_manifest_clone_dvc_site_caches_record(),
        }
        configured_clone_inventory = _scan_work_inventory(clone_handle)
        if _scan_work_inventory(clone_handle) != configured_clone_inventory:
            raise _error("clone inventory changed after private configuration")
        cleanup_execution_inventories["clone"] = (
            clone_handle,
            configured_clone_inventory,
        )
        validate_execution_namespace("after private DVC configuration copy")
        # Keep the exact pre-DVC snapshot until every config/pull/status step
        # has succeeded and the resulting clone/cache inventories can be
        # frozen atomically below.  Refreshing it from a failing command's
        # partial tree would silently adopt `.dvc/config.local`, `.dvc/tmp`, or a
        # foreign concurrent entry and make destructive cleanup unsafe.
        _revalidate_retained_dvc_runtime(
            retained_dvc_runtime,
            source_root=root,
            context="retained DVC runtime before exact restore",
        )
        restores = _restore_dvc_objects_with_anchored_executable(
            source_root=root,
            clone_root=clone_root,
            cache_root=cache_root,
            site_cache_root=site_cache_root,
            installed_configuration=installed_configuration,
            contract=contract,
            executable=retained_dvc_runtime,
            namespace_validator=validate_execution_namespace,
        )
        _revalidate_retained_dvc_runtime(
            retained_dvc_runtime,
            source_root=root,
            context="retained DVC runtime after exact restore",
        )
        installed_configuration.revalidate(
            allow_operational_cache=True,
            context="private DVC configuration after exact restore",
        )
        first_clone_inventory = _scan_work_inventory(clone_handle)
        first_cache_inventory = _scan_work_inventory(cache_handle)
        first_site_cache_inventory = _scan_work_inventory(site_cache_handle)
        if (
            _scan_work_inventory(clone_handle) != first_clone_inventory
            or _scan_work_inventory(cache_handle) != first_cache_inventory
            or _scan_work_inventory(site_cache_handle)
            != first_site_cache_inventory
        ):
            raise _error(
                "clone/cache/site-cache inventory changed while freezing verification"
            )
        frozen_execution_inventories.update(
            {
                "clone": (clone_handle, first_clone_inventory),
                "DVC cache": (cache_handle, first_cache_inventory),
                "DVC site cache": (
                    site_cache_handle,
                    first_site_cache_inventory,
                ),
            }
        )
        cleanup_execution_inventories.update(
            {
                "clone": (clone_handle, first_clone_inventory),
                "DVC cache": (cache_handle, first_cache_inventory),
                "DVC site cache": (
                    site_cache_handle,
                    first_site_cache_inventory,
                ),
            }
        )
        _revalidate_owned_site_cache_root(
            site_cache_handle,
            site_cache_root_identity,
            allow_successful_dvc_transition=False,
            context="owned DVC site cache at verification freeze",
        )
        site_cache_root_frozen = True
        validate_execution_namespace("after frozen clone/cache inventory")
        transport_metadata_before = bracket(
            "transport_metadata_before_verification",
            lambda: _capture_transport_metadata(
                clone_root=clone_root,
                cache_root=cache_root,
                contract=contract,
            ),
        )
        clone_record = {
            **clone_record,
            "dvc_cache": bracket(
                "exact_dvc_cache_before_verification",
                lambda: _validate_exact_dvc_cache(
                    cache_root=cache_root, contract=contract
                ),
            ),
        }
        if clone_mountpoints is None:
            raise _error("clone sandbox mountpoint lease disappeared")
        verification_runtime = bracket(
            "verification_runtime_acquisition",
            lambda: _acquire_verification_runtime(
                source_root=root,
                clone_handle=clone_handle,
                clone_mountpoints=clone_mountpoints,
                sandbox_handle=sandbox_handle,
                socket_handle=socket_handle,
                mask_handle=mask_handle,
            ),
        )
        active_verification_runtime = cast(
            VerificationRuntimeLease, verification_runtime
        )
        sandbox_smoke = bracket(
            "sandbox_smoke",
            lambda: _run_sandbox_smoke(
                source_root=root,
                runtime=active_verification_runtime,
                contract=contract,
            ),
        )
        database_owner, database_record = _start_owned_postgres(
            socket_handle,
            namespace_validator=validate_execution_namespace,
            owner_handoff=retain_database_owner,
        )
        verification_artifacts, verification = _run_verification_with_runtime(
            source_root=root,
            clone_root=clone_root,
            sandbox_tmp=sandbox_handle.path,
            contract=contract,
            execution_commit=execution_commit,
            runtime=active_verification_runtime,
            sandbox_smoke=sandbox_smoke,
            namespace_validator=validate_execution_namespace,
        )
        active_verification_runtime.close()
        verification_runtime = None
        cleanup = _stop_owned_postgres(
            database_owner,
            socket_handle=socket_handle,
            before_stop=mark_database_stop_attempted,
        )
        database_owner = None
        database_record = {
            **database_record,
            **cleanup,
            "cleaned_after_execution": True,
        }
        validate_execution_namespace("after PostgreSQL cleanup")
        clone_status = bracket(
            "clone_git_status_after_verification",
            lambda: _git(
                clone_root, "status", "--porcelain=v1", "--untracked-files=all"
            ),
        )
        _require_clean_clone_status(clone_status)
        transport_metadata_after = bracket(
            "transport_metadata_after_verification",
            lambda: _capture_transport_metadata(
                clone_root=clone_root,
                cache_root=cache_root,
                contract=contract,
            ),
        )
        if transport_metadata_after != transport_metadata_before:
            raise _error("restored DVC transport metadata changed after verification")
        bracket(
            "exact_dvc_cache_after_verification",
            lambda: _validate_exact_dvc_cache(
                cache_root=cache_root, contract=contract
            ),
        )
        if installed_configuration is None:
            raise _error("private DVC configuration lease disappeared")
        active_configuration = installed_configuration
        bracket(
            "clone_dvc_status_after_verification",
            lambda: _dvc_status_with_executable(
                clone_root,
                retained_dvc_runtime,
                source_root=root,
                targets=_contract_dvc_status_targets(
                    contract,
                    contract.post_verification_status_pointer_paths,
                    context="post-verification",
                ),
                environment={"DVC_SITE_CACHE_DIR": os.fspath(site_cache_root)},
                private_pass_fds=active_configuration.pass_fds,
            ),
        )
        _revalidate_retained_dvc_runtime(
            retained_dvc_runtime,
            source_root=root,
            context="retained DVC runtime after final clone status",
        )
        active_configuration.revalidate(
            allow_operational_cache=True,
            context="private DVC configuration after final clone status",
        )
        source_after = bracket(
            "main_state_after_verification",
            lambda: _capture_main_state(root),
        )
        if source_after != source_before:
            raise _error("main source worktree changed during isolated verification")
        bracket(
            "main_dvc_static_boundary_after_verification",
            lambda: _reconstruct_main_dvc_static_boundary(
                root=root,
                contract=contract,
                context="post-verification",
                expected_anchors=cast(
                    Sequence[Mapping[str, Any]], preflight["anchor_inputs"]
                ),
                expected_pointers=cast(
                    Sequence[Mapping[str, Any]], preflight["dvc_pointers"]
                ),
                main_site_cache_lease=main_site_cache_lease,
            ),
        )
        runtime_after = bracket(
            "runtime_versions_after_verification",
            lambda: _sealed_runtime_versions(
                root,
                contract=contract,
                dvc_runtime=retained_dvc_runtime,
                dvc_clone_handle=clone_handle,
                dvc_site_cache_handle=version_site_cache_handle,
                dvc_private_pass_fds=active_configuration.pass_fds,
                namespace_validator=validate_execution_namespace,
            ),
        )
        if runtime_after != runtime_before:
            raise _error("runtime versions drifted during final certification")
        products = bracket(
            "payload_build",
            lambda: build_final_certification_payloads(
                contract=contract,
                execution_commit=execution_commit,
                authority=authority,
                anchor_records=cast(
                    Sequence[Mapping[str, Any]], preflight["anchor_inputs"]
                ),
                pointer_records=cast(
                    Sequence[Mapping[str, Any]], preflight["dvc_pointers"]
                ),
                restore_records=restores,
                clone_record=clone_record,
                verification_artifacts=verification_artifacts,
                verification=verification,
                database=database_record,
                runtime_versions=runtime_before,
            ),
        )
        bracket(
            "payload_validation",
            lambda: validate_final_certification_payloads(
                contract=contract,
                artifacts=products.artifacts,
                manifest=products.manifest,
                execution_commit=execution_commit,
                repo_root=root,
            ),
        )
        _revalidate_retained_dvc_runtime(
            retained_dvc_runtime,
            source_root=root,
            context="retained DVC runtime before successful close",
        )
        retained_dvc_runtime.close()
        dvc_runtime = None
        installed_configuration.close()
        installed_configuration = None
        if main_site_cache_lease is None:
            raise _error("main DVC site-cache lease disappeared")
        active_main_site_cache_lease = main_site_cache_lease
        # No ignored clone/cache/socket/mask namespace survives publication.
        validate_execution_namespace("before owned work cleanup")
        if clone_mountpoints is None:
            raise _error("clone mountpoint lease disappeared before cleanup")
        clone_mountpoints.close()
        lease.seal_work_inventory()
        lease.remove_work_directory(owned_tmp, owned_tmp_identity)
        work_removed = True
        publication_validator = lambda stage: _revalidate_publication_gate(
            root=root,
            contract=contract,
            execution_commit=execution_commit,
            expected_authority=authority,
            expected_anchors=cast(
                Sequence[Mapping[str, Any]], preflight["anchor_inputs"]
            ),
            expected_pointers=cast(
                Sequence[Mapping[str, Any]], preflight["dvc_pointers"]
            ),
            expected_local_remote=cast(
                Mapping[str, Any], preflight["local_dvc_remote_configuration"]
            ),
            stage=stage,
            repository_lease=repository_lease,
            main_site_cache_lease=active_main_site_cache_lease,
        )
        # The publisher owns and closes the lease on every success/failure path.
        publisher_consumed_lease = True
        result = publish_final_certification_bundle(
            repo_root=root,
            contract=contract,
            products=products,
            run_guard=lease,
            publication_validator=publication_validator,
        )
        active_main_site_cache_lease.close()
        main_site_cache_lease = None
    except BaseException as exc:
        active_error = exc
    cleanup_error: BaseException | None = None
    cleanup_reason_codes: set[str] = set()
    if verification_runtime is not None:
        try:
            verification_runtime.revalidate(
                context="failed execution verification runtime invariant"
            )
        except BaseException as exc:
            cleanup_error = exc
            cleanup_reason_codes.add("frozen_inventory_drift")
        try:
            verification_runtime.close()
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
            cleanup_reason_codes.add("unclassified_cleanup_failure")
        verification_runtime = None
    if dvc_runtime is not None:
        try:
            _revalidate_retained_dvc_runtime(
                dvc_runtime,
                source_root=root,
                context="failed execution retained DVC runtime invariant",
            )
        except BaseException as exc:
            cleanup_error = exc
            cleanup_reason_codes.add("frozen_inventory_drift")
        try:
            dvc_runtime.close()
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
            cleanup_reason_codes.add("unclassified_cleanup_failure")
        dvc_runtime = None
    if installed_configuration is not None:
        try:
            installed_configuration.close()
            installed_configuration = None
        except BaseException as exc:
            cleanup_error = exc
            cleanup_reason_codes.add("unclassified_cleanup_failure")
    if main_site_cache_lease is not None:
        try:
            main_site_cache_lease.revalidate(
                context="failed execution main DVC site-cache invariant"
            )
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
            cleanup_reason_codes.add("owned_site_cache_drift")
        try:
            main_site_cache_lease.close()
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
            cleanup_reason_codes.add("unclassified_cleanup_failure")
        main_site_cache_lease = None
    if database_owner is not None:
        try:
            if database_stop_attempted:
                _finish_owned_postgres_cleanup(
                    database_owner,
                    socket_handle=socket_handle,
                )
            else:
                _stop_owned_postgres(
                    database_owner,
                    socket_handle=socket_handle,
                    before_stop=mark_database_stop_attempted,
                )
            database_owner = None
        except BaseException as exc:
            cleanup_error = exc
            cleanup_reason_codes.add("database_owner_retained")
    if not work_removed:
        try:
            assessment: CleanupAssessment | None = None
            if lease.work_inventory is None:
                assessment = failed_tree_cleanup_assessment()
            if clone_mountpoints is not None:
                clone_mountpoints.close()
                clone_mountpoints = None
            if (
                assessment is not None
                and assessment.status != "ready_for_owned_cleanup"
            ):
                cleanup_reason_codes.update(assessment.reason_codes)
                raise _error(
                    "failed execution tree ownership is not exact; preserved"
                )
            if lease.work_inventory is None:
                lease.seal_work_inventory()
            lease.remove_work_directory(owned_tmp, owned_tmp_identity)
            work_removed = True
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
            if not cleanup_reason_codes:
                cleanup_reason_codes.add("work_tree_remove_failed")
            elif lease.work_inventory is not None:
                cleanup_reason_codes.add("work_tree_remove_failed")
    if not publisher_consumed_lease:
        try:
            # A failed-closed owned tree is intentionally retained as one
            # namespace.  Its created parent chain therefore cannot be
            # removed and is not itself an additional cleanup failure.
            if not lease.removed and work_removed:
                lease.release()
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
            cleanup_reason_codes.add("unclassified_cleanup_failure")
        finally:
            lease.close()
    try:
        repository_lease.close()
    except BaseException as exc:
        cleanup_error = cleanup_error or exc
        cleanup_reason_codes.add("unclassified_cleanup_failure")
    if cleanup_error is not None:
        if active_error is not None:
            raise _execution_cleanup_composite_error(
                active_error,
                namespace_preserved=not work_removed,
                reason_codes=tuple(sorted(cleanup_reason_codes)),
            ) from None
        raise _error(
            "final certification temporary cleanup failed closed; namespace preserved"
        ) from None
    if active_error is not None:
        if isinstance(active_error, FinalCertificationBuildError):
            raise active_error
        raise _error("final certification execution failed") from active_error
    if result is None:
        raise _error("final certification returned no result")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check-only", action="store_true")
    action.add_argument("--build", action="store_true")
    action.add_argument("--emit-openapi", type=Path)
    parser.add_argument("--execution-commit")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.emit_openapi is not None:
            if args.execution_commit is None:
                raise _error("--emit-openapi requires --execution-commit")
            _emit_openapi(args.emit_openapi, args.execution_commit)
            result: Mapping[str, Any] = {
                "status": "openapi_written",
                "execution_commit": args.execution_commit,
            }
        elif args.check_only:
            result = check_phase4_final_certification()
        else:
            result = build_phase4_final_certification()
    except FinalCertificationContractError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
