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
import copy
import ctypes
import errno
import fcntl
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
    load_contract,
    load_effective_authority,
    parse_dvc_pointer_bytes,
    sha256_bytes,
    validate_local_dvc_remote_configuration,
)


SCHEMA_VERSION = "closure_v1_phase4_final_certification_bundle_v1"
PUBLIC_SUITE_KIND = "closure_phase4_final_public"
E2E_SUITE_KIND = "closure_phase4_final_synthetic_e2e"
PLUGIN_MODE_ENV = "CLOSURE_PHASE4_CERTIFICATION_SUITE_KIND"
PLUGIN_ROOT_ENV = "CLOSURE_PHASE4_CERTIFICATION_REPO_ROOT"
DB_SOCKET_ROOT = "/cert-db"
DB_NAME = "closure_phase4_cert"
POSTGRES_IMAGE = (
    "postgres:16-alpine@sha256:"
    "16bc17c64a573ef34162af9298258d1aec548232985b33ed7b1eac33ba35c229"
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
SAFE_DB_URL = (
    "postgresql+asyncpg://postgres@/closure_phase4_cert?host=/cert-db"
)
GIT_EXECUTABLE = "/usr/bin/git"
FORBIDDEN_COMMAND_TOKENS = (
    "--execute-sealed-batch",
    "data/targets",
    "data/closure_v1/unblinded",
    "data/closure_v1/evaluation_outcomes",
    "outcome_access_log",
    "private/",
)
SANDBOX_MASKED_FORBIDDEN_PREFIXES = (
    "private/",
    "data/targets/",
)
SANDBOX_ABSENT_FORBIDDEN_PREFIXES = (
    "data/closure_v1/unblinded/",
    "data/closure_v1/evaluation_outcomes/",
)
SANDBOX_ABSENT_FORBIDDEN_PATHS = (
    "reports/closure_v1/00_protocol/outcome_access_log.jsonl",
)
JUNIT_SKIP_TYPE = "pytest.skip"


class FinalCertificationBuildError(FinalCertificationContractError):
    """Raised when certification cannot proceed without weakening P-CERT."""


def _error(message: str) -> FinalCertificationBuildError:
    return FinalCertificationBuildError(message)


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


@dataclass(frozen=True)
class OwnedPostgres:
    """Private Docker identity; neither field may enter public evidence."""

    name: str
    container_id: str


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
    sandbox_handle: DirectoryHandle
    socket_handle: DirectoryHandle
    mask_handle: DirectoryHandle
    work_handle: DirectoryHandle
    source_before: Mapping[str, Any]
    lease_parent_binding: tuple[Any, ...]
    work_binding: tuple[Any, ...]
    repository_root_binding: tuple[Any, ...]
    mask_inventory: Mapping[str, WorkInventoryEntry]


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
        if token.startswith("/"):
            raise _error("absolute command paths may not be serialized")
        lowered = token.lower()
        if any(marker in lowered for marker in ("password=", "token=", "secret=")):
            raise _error("credential-bearing command token may not be serialized")
        if "://" in token:
            raise _error("remote or database URLs may not be serialized")
        rendered.append(token)
    return rendered


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
    except subprocess.TimeoutExpired as exc:
        raise _error(f"verification command exceeded {timeout_seconds}s: {recorded}") from exc
    # Stdout/stderr commonly contain elapsed times, random temporary paths, or
    # DVC transfer speeds.  They are used to diagnose a failing invocation but
    # deliberately excluded from the deterministic public evidence record.
    record = {"argv": recorded, "returncode": completed.returncode}
    if require_success and completed.returncode != 0:
        raise _error(f"verification command failed: {recorded}")
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


def _dvc_status(root: Path, *, executable_root: Path | None = None) -> str:
    runtime = _open_python_script_runtime(
        executable_root or root,
        Path(".venv/bin/dvc"),
        context="DVC runtime",
    )
    try:
        return _dvc_status_with_executable(root, runtime)
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
) -> CommandResult:
    """Execute exact retained script bytes with the exact retained interpreter."""

    runtime.revalidate(context=f"{context} before execution")
    command_environment = {
        **({} if environment is None else environment),
        "__PYVENV_LAUNCHER__": f"{runtime.interpreter.venv_proc_path}/bin/python",
    }
    result = _run(
        (runtime.interpreter.proc_path, runtime.script.proc_path, *arguments),
        cwd=cwd,
        portable_argv=portable_argv,
        environment=command_environment,
        timeout_seconds=timeout_seconds,
        require_success=require_success,
        pass_fds=(
            runtime.interpreter.fd,
            runtime.interpreter.venv_fd,
            runtime.script.fd,
        ),
    )
    runtime.revalidate(context=f"{context} after execution")
    return result


def _dvc_status_with_executable(
    root: Path,
    executable: AnchoredPythonScriptRuntime,
) -> str:
    result = _run_python_script_runtime(
        executable,
        ("status", "--json"),
        cwd=root,
        portable_argv=(".venv/bin/dvc", "status", "--json"),
        environment={"DVC_NO_ANALYTICS": "1"},
        timeout_seconds=300,
        context="DVC status",
    )
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise _error("DVC status did not return JSON") from exc
    if parsed != {}:
        raise _error("DVC status must equal the empty object")
    return "{}"


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
            not trusted_path.is_relative_to(Path("/usr"))
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
) -> str:
    """Capture an owned name twice before deletion can target it.

    The first no-clobber rename removes the public boundary.  A retained FD
    proves that capture, and a second unpredictable no-clobber rename closes
    the detach-to-delete test boundary: a replacement of the first tombstone
    is preserved and rejected rather than adopted.
    """

    if not name or "/" in name or name in {".", ".."}:
        raise _error(f"{context} has an unsafe cleanup name")
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
        return (
            stat.S_ISDIR(metadata.st_mode)
            if require_directory
            else stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
        )

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
) -> None:
    """Reject subprocesses that could escape the sealed verification surface."""

    tokens = [str(item) for item in argv] if isinstance(argv, (list, tuple)) else []
    if not tokens:
        raise _error("certification forbids opaque subprocess commands")
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
        _guard_process(tokens[index:], cwd)
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


def install_certification_access_guard(
    repo_root: Path | None = None,
    *,
    contract: FinalCertificationContract | None = None,
) -> None:
    """Install a process-local audit guard for public and E2E verification."""

    global _ACCESS_GUARD_INSTALLED
    if _ACCESS_GUARD_INSTALLED:
        return
    root = (repo_root or Path(os.environ.get(PLUGIN_ROOT_ENV, "."))).resolve(strict=True)
    sealed = contract or load_contract(root=root)

    def audit(event: str, args: tuple[Any, ...]) -> None:
        if event == "open" and args and isinstance(args[0], (str, os.PathLike)):
            if _is_forbidden_path(args[0], root, sealed):
                raise _error("certification attempted a forbidden repository read")
        elif event == "os.system":
            raise _error("certification forbids os.system")
        elif event in {"os.posix_spawn", "os.posix_spawnp"} and len(args) > 1:
            _guard_process(args[1])
        elif event == "subprocess.Popen" and len(args) > 1:
            _guard_process(args[1], args[2] if len(args) > 2 else None)
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

    marker = pytest.mark.skip(reason=suite.exact_skip_reason)
    for item in items:
        if item.nodeid in expected_skips:
            item.add_marker(marker)
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
                or skipped_node.attrib.get("message") != suite.exact_skip_reason
            ):
                raise _error("JUnit skipped outcome type/reason is not exact")
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
    # The loader returns raw bytes for its internal equality proof.  Public
    # certification records bind their digests and decoded canonical objects,
    # never duplicate raw bytes or operational paths.
    return {
        "status": result["status"],
        "gate": result["gate"],
        "p_cert_commit": result["p_cert_commit"],
        "h_cert_commit": result["h_cert_commit"],
        "repository": result["repository"],
        "authority": result["authority"],
        "authority_bytes": len(result["authority_bytes"]),
        "authority_sha256": result["authority_sha256"],
        "manifest": result["manifest"],
        "manifest_bytes": len(result["manifest_bytes"]),
        "manifest_sha256": result["manifest_sha256"],
    }


def check_phase4_final_certification(
    *,
    repo_root: Path = PROJECT_ROOT,
    authority_validator: Callable[[Path, FinalCertificationContract], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the non-writing P-CERT and output-namespace preflight."""

    root = repo_root.resolve(strict=True)
    contract = load_contract(root=root)
    if contract.test_suite.status != "locked":
        raise _error("final certification refuses a pending test-suite lock")
    state = _capture_main_state(root)
    if any(state[key] for key in ("status", "cached_diff", "unstaged_diff")):
        raise _error("P-CERT certification gate requires a clean repository")
    if len({state["head"], state["main"], state["origin_main"], state["origin_head"]}) != 1:
        raise _error("P-CERT local refs are not aligned")
    authority = (authority_validator or _authority_loader)(root, contract)
    effective_commit = authority.get("p_cert_commit") or authority.get(
        "execution_commit"
    ) or authority.get("repository_commit")
    if effective_commit != state["head"]:
        raise _error("P-CERT authority is not bound to current HEAD")
    live_remote = _git(root, "ls-remote", "--exit-code", "origin", "refs/heads/main")
    live_commit = live_remote.split()[0] if live_remote else ""
    if live_commit != state["head"]:
        raise _error("live origin/main does not equal published P-CERT")
    _dvc_status(root)
    local_remote = validate_local_dvc_remote_configuration(root=root)
    output_root = root / CERTIFICATION_ROOT
    if os.path.lexists(output_root):
        raise _error("R-CERT output namespace already exists")
    legacy_guard = root / GUARD_PATH
    if os.path.lexists(legacy_guard):
        raise _error("legacy final-certification guard path must be absent")
    anchor_records = collect_anchor_input_records(contract, root=root)
    pointer_records = collect_dvc_pointer_records(contract, root=root)
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
        "main_dvc_status": {},
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


def _install_local_dvc_remote_configuration(
    *, source_root: Path, clone_root: Path
) -> Mapping[str, Any]:
    """Copy the validated ignored remote config without exposing its bytes.

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
    try:
        _rebind_directory_chain(
            source_root, source_chain, context="source DVC configuration"
        )
        _rebind_directory_chain(
            clone_root, destination_chain, context="clone DVC configuration"
        )
        source_fd = os.open(
            LOCAL_DVC_CONFIG_PATH.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=source_chain[-1].fd,
        )
        destination_fd = os.open(
            LOCAL_DVC_CONFIG_PATH.name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
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
        total = 0
        while True:
            chunk = os.read(source_fd, 64 * 1024)
            if not chunk:
                break
            view = memoryview(chunk)
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
            or total != before.st_size
            or copied.st_size != before.st_size
        ):
            raise _error("local DVC remote configuration changed during private copy")
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
    finally:
        if destination_fd >= 0:
            os.close(destination_fd)
        if source_fd >= 0:
            os.close(source_fd)
        for handle in reversed(destination_chain):
            handle.close()
        for handle in reversed(source_chain):
            handle.close()
    public_validation = {
        key: value
        for key, value in validation.items()
        if key not in {"content_opened", "content_or_path_serialized", "filesystem_mode"}
    }
    return {
        **public_validation,
        "source_mode_accepted": "0600_or_0644",
        "clone_mode": "0600",
        "copied_only_into_owned_clone": True,
        "content_read_only_for_private_copy": True,
        "content_path_remote_url_and_credentials_serialized": False,
    }


def _restore_dvc_objects(
    *,
    source_root: Path,
    clone_root: Path,
    cache_root: Path,
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
    contract: FinalCertificationContract,
    executable: AnchoredPythonScriptRuntime,
    namespace_validator: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    if any(cache_root.iterdir()):
        raise _error("isolated DVC cache is not initially empty")
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
            environment={"DVC_NO_ANALYTICS": "1"},
            timeout_seconds=120,
            context=f"DVC config {key}",
        )
        if namespace_validator is not None:
            namespace_validator(f"after_dvc_config_{key}")
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
            environment={"DVC_NO_ANALYTICS": "1"},
            timeout_seconds=1800,
            context=f"directed DVC pull {index}",
        )
        if namespace_validator is not None:
            namespace_validator(f"after_dvc_pull_{index}")
        if _private_regular_identity(private_config) != private_config_identity:
            raise _error("private DVC configuration changed during directed pulls")
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
            environment={"DVC_NO_ANALYTICS": "1"},
            timeout_seconds=300,
            context=f"directed DVC status {index}",
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
    _dvc_status_with_executable(clone_root, executable)
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
    """Resolve the invoking UID's pipx Poetry root without trusting ``HOME``."""

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

    if contract.forbidden_read_prefixes != (
        *SANDBOX_MASKED_FORBIDDEN_PREFIXES,
        *SANDBOX_ABSENT_FORBIDDEN_PREFIXES,
    ) or contract.forbidden_read_paths != SANDBOX_ABSENT_FORBIDDEN_PATHS:
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
    for prefix in SANDBOX_MASKED_FORBIDDEN_PREFIXES:
        template.extend(
            ["--ro-bind", "<EMPTY_MASK>", "/workspace/" + prefix.rstrip("/")]
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
        destination = "/workspace/" + str(prefix).rstrip("/")
        kind = _retained_relative_kind(
            runtime.clone.fd,
            str(prefix),
            context=f"forbidden prefix {prefix}",
        )
        if prefix in SANDBOX_ABSENT_FORBIDDEN_PREFIXES:
            if kind is not None:
                raise _error(f"forbidden prefix expected absent in P-CERT: {prefix}")
            continue
        if kind != "directory":
            raise _error(f"forbidden prefix is not a directory: {prefix}")
        real.extend(
            ["--ro-bind", f"/proc/self/fd/{runtime.empty_directory.fd}", destination]
        )
        template.extend(["--ro-bind", "<EMPTY_MASK>", destination])
    for path_text in contract.forbidden_read_paths:
        kind = _retained_relative_kind(
            runtime.clone.fd,
            str(path_text),
            context=f"forbidden path {path_text}",
        )
        if path_text not in SANDBOX_ABSENT_FORBIDDEN_PATHS or kind is not None:
            raise _error(f"forbidden path expected absent in P-CERT: {path_text}")
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


def _start_owned_postgres(
    socket_root: Path,
    *,
    namespace_validator: Callable[[str], None] | None = None,
) -> tuple[OwnedPostgres, Mapping[str, Any]]:
    container_name = f"closure-phase4-cert-{secrets.token_hex(12)}"
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
                f"{socket_root}:/var/run/postgresql",
                "--tmpfs",
                "/var/lib/postgresql/data:rw,size=512m",
                "--tmpfs",
                "/tmp:rw,size=64m",
                POSTGRES_IMAGE,
                "-c",
                "unix_socket_directories=/var/run/postgresql",
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
                "<OWNED_DB_SOCKET>:/var/run/postgresql",
                "--tmpfs",
                "/var/lib/postgresql/data:rw,size=512m",
                "--tmpfs",
                "/tmp:rw,size=64m",
                POSTGRES_IMAGE,
                "-c",
                "unix_socket_directories=/var/run/postgresql",
                "-c",
                "listen_addresses=",
            ),
            timeout_seconds=120,
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
            _stop_owned_postgres(recovered)
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
        if malformed_run_identity:
            raise _error("Docker did not return one exact owned container ID")
        if namespace_validator is not None:
            namespace_validator("after_postgres_start")
        for attempt in range(120):
            if namespace_validator is not None:
                namespace_validator(f"before_postgres_probe_{attempt}")
            _require_owned_postgres_binding(
                owner,
                context=f"PostgreSQL readiness probe {attempt}",
            )
            probe = _run(
                (
                    "/usr/bin/docker",
                    "exec",
                    container_id,
                    "pg_isready",
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
                    "-U",
                    "postgres",
                    "-d",
                    DB_NAME,
                ),
                timeout_seconds=10,
                require_success=False,
            )
            if namespace_validator is not None:
                namespace_validator(f"after_postgres_probe_{attempt}")
            _require_owned_postgres_binding(
                owner,
                context=f"PostgreSQL readiness result {attempt}",
            )
            if probe.record["returncode"] == 0:
                return owner, {
                    "image": POSTGRES_IMAGE,
                    "network": "none",
                    "transport": "owned_unix_socket",
                    "database": DB_NAME,
                    "credentials_serialized": False,
                    "run_command": dict(run.record),
                    "readiness_command": dict(probe.record),
                }
            time.sleep(0.25)
        raise _error("owned PostgreSQL container did not become ready")
    except BaseException:
        try:
            _stop_owned_postgres(owner)
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
    )
    value = result.stdout.strip()
    if result.record["returncode"] == 0 and not SHA256_RE.fullmatch(value):
        raise _error("Docker inspect returned a malformed container identity")
    if result.record["returncode"] != 0 and value:
        raise _error("Docker inspect failure returned ambiguous output")
    return cast(int, result.record["returncode"]), value


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


def _stop_owned_postgres(owner: OwnedPostgres) -> Mapping[str, Any]:
    _require_owned_postgres_binding(owner, context="PostgreSQL cleanup")
    result = _run(
        ("/usr/bin/docker", "rm", "--force", owner.container_id),
        cwd=PROJECT_ROOT,
        portable_argv=("docker", "rm", "--force", "<OWNED_CONTAINER>"),
        timeout_seconds=120,
    )
    name_returncode, name_identity = _inspect_container_identity(owner.name)
    id_returncode, id_identity = _inspect_container_identity(owner.container_id)
    if name_returncode == 0 or id_returncode == 0:
        # Never adopt/delete a replacement that reused the random name.
        if name_identity != owner.container_id or id_identity != owner.container_id:
            raise _error("foreign PostgreSQL container appeared during cleanup")
        raise _error("owned PostgreSQL container survived forced cleanup")
    return {
        "command": dict(result.record),
        "removed": True,
        "owned_container_only": True,
    }


def _suite_environment(kind: str) -> dict[str, str]:
    environment = {
        PLUGIN_MODE_ENV: kind,
        PLUGIN_ROOT_ENV: "/workspace",
        "TEST_DATABASE_URL": SAFE_DB_URL,
        "HOME": "/tmp",
        "XDG_CACHE_HOME": "/tmp/cache",
        "PATH": "/usr/bin:/bin",
    }
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


def _run_verification(
    *,
    source_root: Path,
    clone_handle: DirectoryHandle,
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
        runtime = _open_verification_runtime(
            source_root=source_root,
            clone=clone_handle,
            sandbox=sandbox_handle,
            socket_handle=socket_handle,
            mask_root=mask_handle,
        )
        if namespace_validator is not None:
            namespace_validator("after_verification_runtime_acquisition")
        return _run_verification_with_runtime(
            source_root=source_root,
            clone_root=clone_handle.path,
            sandbox_tmp=sandbox_handle.path,
            contract=contract,
            execution_commit=execution_commit,
            runtime=runtime,
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
    namespace_validator: Callable[[str], None] | None = None,
) -> tuple[Mapping[str, bytes], Mapping[str, Any]]:
    bwrap, bwrap_template = _make_bwrap_prefix(
        runtime=runtime,
        contract=contract,
    )
    public_command = _public_command(contract)
    if namespace_validator is not None:
        namespace_validator("before_public_tests")
    runtime.revalidate(context="before public test execution")
    public = _run(
        public_command,
        cwd=source_root,
        execution_argv=(*bwrap, "/cert-python", *public_command[1:]),
        environment={
            **_suite_environment(PUBLIC_SUITE_KIND),
            "__PYVENV_LAUNCHER__": "/workspace/.venv/bin/python",
        },
        inherit_environment=False,
        timeout_seconds=3600,
        pass_fds=runtime.pass_fds,
    )
    runtime.revalidate(context="after public test execution")
    if namespace_validator is not None:
        namespace_validator("after_public_tests")
    raw_junit = _read_regular(
        sandbox_tmp / "public-tests-raw.xml", context="raw public JUnit"
    )
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
            **_suite_environment(E2E_SUITE_KIND),
            "__PYVENV_LAUNCHER__": "/workspace/.venv/bin/python",
        },
        inherit_environment=False,
        timeout_seconds=600,
        pass_fds=runtime.pass_fds,
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
            **_suite_environment(E2E_SUITE_KIND),
            "__PYVENV_LAUNCHER__": "/workspace/.venv/bin/python",
        },
        inherit_environment=False,
        timeout_seconds=1800,
        pass_fds=runtime.pass_fds,
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
        environment=_suite_environment(E2E_SUITE_KIND),
        inherit_environment=False,
        timeout_seconds=1800,
        pass_fds=runtime.pass_fds,
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
            **_suite_environment(E2E_SUITE_KIND),
            "__PYVENV_LAUNCHER__": "/cert-poetry/bin/python",
        },
        inherit_environment=False,
        timeout_seconds=600,
        pass_fds=runtime.pass_fds,
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
            "forbidden_prefixes_masked": list(contract.forbidden_read_prefixes),
            "forbidden_paths_masked": list(contract.forbidden_read_paths),
            "restored_payloads_masked": [
                spec.output_path for spec in contract.dvc_pointers
            ],
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
    )
    executable.revalidate(context=f"{context} after execution")
    return result


def _runtime_versions(
    root: Path,
    *,
    namespace_validator: Callable[[str], None] | None = None,
) -> Mapping[str, str]:
    python: AnchoredPythonInterpreter | None = None
    dvc: AnchoredPythonScriptRuntime | None = None
    ty: AnchoredExecutable | None = None
    poetry: AnchoredPythonScriptRuntime | None = None
    bwrap: AnchoredExecutable | None = None
    try:
        python = _open_anchored_python_interpreter(
            root, Path(".venv/bin/python"), context="Python version runtime"
        )
        dvc = _open_python_script_runtime(
            root, Path(".venv/bin/dvc"), context="DVC version runtime"
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
            )
            python.revalidate(context="Python version after execution")
            return result

        capture("python", python_probe)
        capture(
            "dvc",
            lambda: _run_python_script_runtime(
                dvc,
                ("--version",),
                cwd=root,
                portable_argv=(".venv/bin/dvc", "--version"),
                environment={"DVC_NO_ANALYTICS": "1"},
                timeout_seconds=120,
                context="DVC version",
            ),
        )
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
                ),
            )
        return versions
    finally:
        for value in (bwrap, poetry, ty, dvc, python):
            if value is not None:
                value.close()


def _sealed_runtime_versions(
    root: Path,
    *,
    contract: FinalCertificationContract,
    namespace_validator: Callable[[str], None] | None = None,
) -> dict[str, str]:
    """Capture all eight runtime versions and require the sealed exact map."""

    observed = dict(
        _runtime_versions(root, namespace_validator=namespace_validator)
    )
    if observed != dict(contract.expected_runtime_versions):
        raise _error("runtime version probes differ from the sealed contract")
    return observed


def _artifact_record(path_text: str, payload: bytes) -> dict[str, Any]:
    return {"path": path_text, "bytes": len(payload), "sha256": sha256_bytes(payload)}


def _environment_object(
    *,
    execution_commit: str,
    anchor_records: Sequence[Mapping[str, Any]],
    restore_records: Sequence[Mapping[str, Any]],
    verification: Mapping[str, Any],
    database: Mapping[str, Any],
    runtime_versions: Mapping[str, str],
) -> dict[str, Any]:
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
        "dvc": {
            "restored_pointer_count": len(restore_records),
            "cache_initially_empty": True,
            "one_pointer_per_pull": True,
            "payloads_opened_by_python": False,
            "payloads_decoded": False,
            "dvc_add_or_push": False,
            "main_worktree_written": False,
        },
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
        "- Main worktree/cache: not used for restoration or execution.\n"
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
            "p_cert_commit": authority["p_cert_commit"],
            "h_cert_commit": authority["h_cert_commit"],
            "bytes": authority["authority_bytes"],
            "sha256": authority["authority_sha256"],
        },
        "p_cert_companion_manifest": {
            "path": AUTHORITY_MANIFEST_PATH.as_posix(),
            "p_cert_commit": authority["p_cert_commit"],
            "h_cert_commit": authority["h_cert_commit"],
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
        "local_dvc_remote_configuration",
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
    local = value.get("local_dvc_remote_configuration")
    if not isinstance(local, Mapping) or dict(local) != {
        "present": True,
        "regular_file": True,
        "single_link": True,
        "git_ignored": True,
        "source_mode_accepted": "0600_or_0644",
        "clone_mode": "0600",
        "copied_only_into_owned_clone": True,
        "content_read_only_for_private_copy": True,
        "content_path_remote_url_and_credentials_serialized": False,
    }:
        raise _error("private clone-local DVC configuration record drifted")
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
        "forbidden_prefixes_masked",
        "forbidden_paths_masked",
        "restored_payloads_masked",
    }:
        raise _error("verification sandbox record is not exact")
    template = sandbox.get("argv_template_prefix")
    if (
        sandbox.get("backend") != "bubblewrap"
        or sandbox.get("network") != "unshared"
        or sandbox.get("postgresql_transport") != "owned_unix_socket_only"
        or sandbox.get("source_tree") != "read_only"
        or sandbox.get("host_virtualenv") != "read_only"
        or sandbox.get("effect_sources_retained_by_fd") is not True
        or sandbox.get("python_console_scripts_interpreter_retained_by_fd") is not True
        or sandbox.get("private_dvc_configuration_masked") is not True
        or sandbox.get("forbidden_prefixes_masked")
        != list(contract.forbidden_read_prefixes)
        or sandbox.get("forbidden_paths_masked")
        != list(contract.forbidden_read_paths)
        or sandbox.get("restored_payloads_masked")
        != [spec.output_path for spec in contract.dvc_pointers]
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
    if effective.get("p_cert_commit") != execution_commit:
        raise _error("effective P-CERT authority execution commit drifted")
    expected_authority_bindings = {
        "p_cert_authority": {
            "path": AUTHORITY_PATH.as_posix(),
            "bytes": effective["authority_bytes"],
            "sha256": effective["authority_sha256"],
            "p_cert_commit": effective["p_cert_commit"],
            "h_cert_commit": effective["h_cert_commit"],
        },
        "p_cert_companion_manifest": {
            "path": AUTHORITY_MANIFEST_PATH.as_posix(),
            "bytes": effective["manifest_bytes"],
            "sha256": effective["manifest_sha256"],
            "p_cert_commit": effective["p_cert_commit"],
            "h_cert_commit": effective["h_cert_commit"],
        },
    }
    for key, expected_binding in expected_authority_bindings.items():
        binding = manifest.get(key)
        if (
            not isinstance(binding, Mapping)
            or set(binding)
            != {"path", "bytes", "sha256", "p_cert_commit", "h_cert_commit"}
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
        or environment.get("dvc")
        != {
            "restored_pointer_count": len(restore_records),
            "cache_initially_empty": True,
            "one_pointer_per_pull": True,
            "payloads_opened_by_python": False,
            "payloads_decoded": False,
            "dvc_add_or_push": False,
            "main_worktree_written": False,
        }
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
) -> None:
    stage_counts = {
        "before_first_link": 0,
        "before_manifest_link": 7,
        "after_all_links": 8,
        "after_run_namespace_cleanup": 8,
        "before_success_return": 8,
    }
    if stage not in stage_counts:
        raise _error("unknown R-CERT publication validation stage")
    if repository_lease is not None:
        repository_lease.revalidate(context=f"before publication gate {stage}")
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
    if collect_anchor_input_records(contract, root=root) != list(expected_anchors):
        raise _error("public anchor inputs changed during R-CERT publication")
    if collect_dvc_pointer_records(contract, root=root) != list(expected_pointers):
        raise _error("DVC pointers changed during R-CERT publication")
    if validate_local_dvc_remote_configuration(root=root) != dict(
        expected_local_remote
    ):
        raise _error("private local DVC remote metadata changed during publication")
    _dvc_status(root)
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
        return PreparedWorkspace(
            owned_tmp=owned_tmp,
            owned_tmp_identity=owned_tmp_identity,
            clone_root=clone_root,
            cache_handle=cache_handle,
            sandbox_handle=sandbox_handle,
            socket_handle=socket_handle,
            mask_handle=mask_handle,
            work_handle=work_handle,
            source_before=source_before,
            lease_parent_binding=_directory_binding(lease.parent),
            work_binding=_directory_binding(work_handle),
            repository_root_binding=_directory_binding(repository_lease.root),
            mask_inventory=mask_inventory,
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
    sandbox_handle = prepared.sandbox_handle
    socket_handle = prepared.socket_handle
    mask_handle = prepared.mask_handle
    cache_root = cache_handle.path
    sandbox_tmp = sandbox_handle.path
    socket_root = socket_handle.path
    mask_root = mask_handle.path
    source_before = prepared.source_before
    work_handle = prepared.work_handle
    lease_parent_binding = prepared.lease_parent_binding
    work_binding = prepared.work_binding
    repository_root_binding = prepared.repository_root_binding
    frozen_execution_inventories: dict[
        str, tuple[DirectoryHandle, Mapping[str, WorkInventoryEntry]]
    ] = {
        "sandbox masks": (mask_handle, prepared.mask_inventory),
    }

    def validate_execution_namespace(stage: str) -> None:
        nonlocal work_binding
        repository_lease.revalidate(context=f"before execution checkpoint {stage}")
        lease.revalidate_work_namespace(context=stage)
        if _directory_binding(lease.parent) != lease_parent_binding:
            raise _error(f"owned lease-parent namespace drifted at checkpoint: {stage}")
        if _directory_binding(repository_lease.root) != repository_root_binding:
            raise _error(f"repository-root namespace drifted at checkpoint: {stage}")
        current_work_binding = _directory_binding(work_handle)
        if stage == "after_git_clone":
            expected_entries = tuple(sorted((*work_binding[-1], "clone")))
            if (
                current_work_binding[:2] != work_binding[:2]
                or current_work_binding[4:6] != work_binding[4:6]
                or current_work_binding[-1] != expected_entries
            ):
                raise _error("owned work namespace clone transition drifted")
            work_binding = current_work_binding
        elif current_work_binding != work_binding:
            raise _error(f"owned work namespace drifted at checkpoint: {stage}")
        for name, (handle, expected_inventory) in frozen_execution_inventories.items():
            if _scan_work_inventory(handle) != dict(expected_inventory):
                raise _error(
                    f"frozen owned {name} inventory drifted at checkpoint: {stage}"
                )
        current_source = _capture_main_state(root)
        repository_lease.revalidate(context=f"after execution checkpoint {stage}")
        if current_source != source_before:
            raise _error(f"main source tree drifted at execution checkpoint: {stage}")

    def bracket(stage: str, operation: Callable[[], Any]) -> Any:
        validate_execution_namespace(f"before_{stage}")
        value = operation()
        validate_execution_namespace(f"after_{stage}")
        return value

    def failed_tree_is_exactly_owned() -> bool:
        if database_owner is not None or lease.work is None:
            return False
        if set(os.listdir(lease.work.fd)) != set(lease.work_subdirectories):
            return False
        for frozen_name in ("sandbox masks", "clone", "DVC cache"):
            frozen = frozen_execution_inventories.get(frozen_name)
            if frozen is None or _scan_work_inventory(frozen[0]) != dict(frozen[1]):
                return False
        if _scan_work_inventory(socket_handle):
            return False
        allowed_sandbox = {
            "public-tests-raw.xml",
            "openapi-raw.json",
            "e2e-raw.xml",
        }
        sandbox_inventory = _scan_work_inventory(sandbox_handle)
        if not set(sandbox_inventory).issubset(allowed_sandbox):
            return False
        return all(
            entry.kind == "regular"
            and entry.link_count == 1
            and entry.mode in {0o600, 0o644}
            for entry in sandbox_inventory.values()
        )

    database_owner: OwnedPostgres | None = None
    active_error: BaseException | None = None
    result: dict[str, Any] | None = None
    work_removed = False
    publisher_consumed_lease = False
    try:
        # Close the preflight-to-flock race before any clone or egress.
        validate_execution_namespace("before P-CERT authority revalidation")
        if _authority_loader(root, contract) != authority:
            raise _error("P-CERT authority drifted while acquiring the run lease")
        validate_execution_namespace("after P-CERT authority revalidation")
        runtime_before = bracket(
            "runtime_versions_before_effects",
            lambda: _sealed_runtime_versions(
                root,
                contract=contract,
                namespace_validator=validate_execution_namespace,
            ),
        )
        clone_record = _clone_exact_p(
            source_root=root,
            clone_root=clone_root,
            execution_commit=execution_commit,
            namespace_validator=validate_execution_namespace,
        )
        lease.open_work_subdirectory("clone")
        validate_execution_namespace("after isolated clone registration")
        clone_record = {
            **clone_record,
            "local_dvc_remote_configuration": bracket(
                "private_dvc_configuration_copy",
                lambda: _install_local_dvc_remote_configuration(
                    source_root=root, clone_root=clone_root
                ),
            ),
        }
        validate_execution_namespace("after private DVC configuration copy")
        restores = _restore_dvc_objects(
            source_root=root,
            clone_root=clone_root,
            cache_root=cache_root,
            contract=contract,
            namespace_validator=validate_execution_namespace,
        )
        clone_handle = lease.work_subdirectories["clone"]
        first_clone_inventory = _scan_work_inventory(clone_handle)
        first_cache_inventory = _scan_work_inventory(cache_handle)
        if (
            _scan_work_inventory(clone_handle) != first_clone_inventory
            or _scan_work_inventory(cache_handle) != first_cache_inventory
        ):
            raise _error("clone/cache inventory changed while freezing verification")
        frozen_execution_inventories.update(
            {
                "clone": (clone_handle, first_clone_inventory),
                "DVC cache": (cache_handle, first_cache_inventory),
            }
        )
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
        database_owner, database_record = _start_owned_postgres(
            socket_root,
            namespace_validator=validate_execution_namespace,
        )
        try:
            verification_artifacts, verification = _run_verification(
                source_root=root,
                clone_handle=clone_handle,
                sandbox_handle=sandbox_handle,
                socket_handle=socket_handle,
                mask_handle=mask_handle,
                contract=contract,
                execution_commit=execution_commit,
                namespace_validator=validate_execution_namespace,
            )
        finally:
            if database_owner is not None:
                cleanup = _stop_owned_postgres(database_owner)
                database_owner = None
                database_record = {**database_record, **cleanup, "cleaned_after_execution": True}
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
        bracket(
            "clone_dvc_status_after_verification",
            lambda: _dvc_status(clone_root, executable_root=root),
        )
        source_after = bracket(
            "main_state_after_verification",
            lambda: _capture_main_state(root),
        )
        if source_after != source_before:
            raise _error("main source worktree changed during isolated verification")
        bracket("main_dvc_status_after_verification", lambda: _dvc_status(root))
        runtime_after = bracket(
            "runtime_versions_after_effects",
            lambda: _sealed_runtime_versions(
                root,
                contract=contract,
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
        # No ignored clone/cache/socket/mask namespace survives publication.
        validate_execution_namespace("before owned work cleanup")
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
    except BaseException as exc:
        active_error = exc
    cleanup_error: BaseException | None = None
    if database_owner is not None:
        try:
            _stop_owned_postgres(database_owner)
            database_owner = None
        except BaseException as exc:
            cleanup_error = exc
    if not work_removed:
        try:
            if lease.work_inventory is None:
                if not failed_tree_is_exactly_owned():
                    raise _error(
                        "failed execution tree ownership is not exact; preserved"
                    )
                lease.seal_work_inventory()
            lease.remove_work_directory(owned_tmp, owned_tmp_identity)
            work_removed = True
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
    if not publisher_consumed_lease:
        try:
            if not lease.removed:
                lease.release()
        except BaseException as exc:
            cleanup_error = cleanup_error or exc
        finally:
            lease.close()
    try:
        repository_lease.close()
    except BaseException as exc:
        cleanup_error = cleanup_error or exc
    if cleanup_error is not None:
        raise _error("final certification temporary cleanup failed closed") from cleanup_error
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
