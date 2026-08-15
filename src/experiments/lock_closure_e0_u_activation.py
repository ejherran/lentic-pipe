#!/usr/bin/env python
"""Build and validate the data-only Closure V1 E0-U activation.

The activation is deliberately generated only after the code commit ``H`` and
the evidence/input commit ``P`` are published.  This program never resolves an
outcome or target path.  Its generation mode writes exactly one canonical JSON
file with exclusive, no-clobber, manifest-last publication.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_R_COMMIT = "4c92ed7249a91b7dd541fd22dde68b61574556b2"
LIVE_REMOTE_URL = "https://github.com/ejherran/lentic-pipe.git"
CONFIGURED_ORIGIN_URL = "git@github.com:ejherran/lentic-pipe.git"
ACTIVATION_PATH = Path(
    "reports/closure_v1/00_protocol/closure_e0_u_activation.json"
)
ACCESS_LOG_PATH = Path("reports/closure_v1/00_protocol/outcome_access_log.jsonl")
RUNNER_PATH = Path("src/experiments/run_closure_benchmark.py")
AUTHORITY_PATH = Path("src/experiments/closure_e0_u_authority.py")
E10_SOURCE_EVIDENCE_PATH = Path(
    "src/experiments/build_closure_e10_source_evidence.py"
)
PHASE3_OVERLAY_BUILDER_PATH = Path(
    "src/experiments/build_closure_phase3_input_overlay.py"
)
GUARD_PATH = Path("tmp/closure_v1_e0_u_activation/activation.guard")
TEMP_DIRECTORY = Path("tmp/closure_v1_e0_u_activation")
GENERATION_COMMAND = (
    "/usr/bin/env -i LANG=C LC_ALL=C .venv/bin/python -I -S -B "
    "src/experiments/lock_closure_e0_u_activation.py --generate\n"
)
CHECK_ONLY_COMMAND = (
    "/usr/bin/env -i LANG=C LC_ALL=C .venv/bin/python -I -S -B "
    "src/experiments/lock_closure_e0_u_activation.py --check-only\n"
)
VALIDATE_COMMAND = (
    "/usr/bin/env -i LANG=C LC_ALL=C .venv/bin/python -I -S -B "
    "src/experiments/lock_closure_e0_u_activation.py --validate-published\n"
)
EXPECTED_P_SCOPE_PATHS = (
    "data/closure_v1/locked_evaluation/adaptive_state_warmup.parquet.dvc",
    "data/closure_v1/locked_evaluation/phase3_runtime_weights.npz.dvc",
    "reports/closure_v1/00_protocol/software_evidence_source/end_to_end_report.md",
    "reports/closure_v1/00_protocol/software_evidence_source/environment.json",
    "reports/closure_v1/00_protocol/software_evidence_source/openapi.json",
    "reports/closure_v1/00_protocol/software_evidence_source/openapi_contract_report.md",
    "reports/closure_v1/00_protocol/software_evidence_source/public_tests.xml",
    "reports/closure_v1/00_protocol/software_evidence_source/software_evidence_source_manifest.json",
    "reports/closure_v1/00_protocol/software_evidence_source/test_report.md",
    "reports/closure_v1/01_surface/phase3_input_overlay_manifest.json",
)
PHASE3_OVERLAY_MANIFEST_PATH = (
    "reports/closure_v1/01_surface/phase3_input_overlay_manifest.json"
)
PHASE3_OVERLAY_OUTPUT_PATHS = (
    "data/closure_v1/locked_evaluation/phase3_runtime_weights.npz",
    "data/closure_v1/locked_evaluation/adaptive_state_warmup.parquet",
)
PHASE3_OVERLAY_DEEP_VALIDATION_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "experiment_id",
        "surface_id",
        "gate",
        "expected_h_commit",
        "builder_source",
        "source_inputs",
        "source_input_count",
        "source_inputs_sha256",
        "manifest",
        "physical_outputs",
        "checkpoint_count",
        "state_dict_array_count",
        "warmup_row_count",
        "warmup_site_count",
        "npz_regenerated_byte_equality",
        "warmup_regenerated_byte_equality",
        "manifest_regenerated_byte_equality",
        "checkpoint_identity_revalidated",
        "numpy_torch_parity_recomputed",
        "warmup_projection_recomputed",
        "history_projection",
        "panel_projection",
        "projection_contains_chlorophyll",
        "projection_contains_target",
        "opened_outcome_path_count",
        "opened_target_path_count",
        "writes_performed",
    }
)
PHASE3_OVERLAY_HISTORY_PROJECTION = (
    "source_id",
    "site_id",
    "holdout_group_id",
    "assignment_role",
    "history_year_month",
)
PHASE3_OVERLAY_PANEL_PROJECTION = (
    "source_id",
    "site_id",
    "year_month",
    "mean_TP_ugL",
    "std_TP_ugL",
    "n_obs_TP_ugL",
    "n_bad_TP_ugL",
    "qc_ok_rate_TP_ugL",
    "mean_TN_ugL",
    "std_TN_ugL",
    "n_obs_TN_ugL",
    "n_bad_TN_ugL",
    "qc_ok_rate_TN_ugL",
    "mean_temperature_C",
    "std_temperature_C",
    "n_obs_temperature_C",
    "n_bad_temperature_C",
    "qc_ok_rate_temperature_C",
    "mean_secchi_depth_m",
    "std_secchi_depth_m",
    "n_obs_secchi_depth_m",
    "n_bad_secchi_depth_m",
    "qc_ok_rate_secchi_depth_m",
    "mean_turbidity_NTU",
    "std_turbidity_NTU",
    "n_obs_turbidity_NTU",
    "n_bad_turbidity_NTU",
    "qc_ok_rate_turbidity_NTU",
    "mean_DO_mgL",
    "std_DO_mgL",
    "n_obs_DO_mgL",
    "n_bad_DO_mgL",
    "qc_ok_rate_DO_mgL",
    "mean_pH",
    "std_pH",
    "n_obs_pH",
    "n_bad_pH",
    "qc_ok_rate_pH",
    "log_TP",
    "log_TN",
    "TN_TP_ratio",
    "season_sin_1",
    "season_cos_1",
    "season_sin_2",
    "season_cos_2",
)
REQUIRED_H_SCOPE = {
    "src/experiments/closure_e0_u_authority.py": "A",
    "src/experiments/closure_phase3_context.py": "A",
    "src/experiments/run_closure_benchmark.py": "M",
}
GIT_ENVIRONMENT = {
    "LANG": "C",
    "LC_ALL": "C",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_NO_REPLACE_OBJECTS": "1",
    "GIT_ASKPASS": "/bin/false",
    "GIT_SSH_COMMAND": "/bin/false",
    "GIT_EXEC_PATH": "/usr/lib/git-core",
}


class ActivationLockError(RuntimeError):
    """Raised when the pre-outcome activation boundary is not exact."""


@dataclass
class GuardLease:
    repo_root: Path
    path: Path
    identity: tuple[int, int]
    file_identity: tuple[int, ...]
    directory_created: bool
    directory_identity: tuple[int, int]
    descriptor: int
    descriptors: list[int]
    bindings: list[tuple[int, str, int, tuple[int, ...]]]
    root_identity: tuple[int, ...]
    closed: bool = False

    @property
    def parent_fd(self) -> int:
        if self.closed or not self.descriptors:
            raise ActivationLockError("activation guard lease is closed")
        return self.descriptors[-1]


@dataclass
class ActivationPublicationLease:
    repo_root: Path
    identity: tuple[int, int]
    expected_bytes: int
    expected_sha256: str
    descriptor: int
    descriptors: list[int]
    bindings: list[tuple[int, str, int, tuple[int, ...]]]
    root_identity: tuple[int, ...]
    closed: bool = False

    @property
    def parent_fd(self) -> int:
        if self.closed or not self.descriptors:
            raise ActivationLockError("activation publication lease is closed")
        return self.descriptors[-1]


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _expected_phase3_overlay_source_identities() -> tuple[tuple[str, str], ...]:
    identities: list[tuple[str, str]] = [
        (
            "r10_input_history",
            "data/closure_v1/locked_evaluation/input_history.parquet",
        ),
        ("panel_physical_seasonal", "data/panel/panel_monthly_v0.parquet"),
    ]
    seeds = (1729, 20260612, 20260613, 20260614, 314159)
    for seed in seeds:
        names = (
            {
                "N": "ANFIS-N.pt",
                "F": "ANFIS-F.pt",
                "T": "ANFIS-T-no-current.pt",
            }
            if seed == 1729
            else {
                "N": "anfis_n.pt",
                "F": "anfis_f.pt",
                "T": "anfis_t_no_current.pt",
            }
        )
        for module in ("N", "F", "T"):
            identities.append(
                (
                    f"anfis/{seed}/{module}_checkpoint",
                    f"models/closure_v1/anfis/seed_{seed}/{names[module]}",
                )
            )
    for model_id in ("A0", "A1"):
        for seed in seeds:
            identities.append(
                (
                    f"gru/{model_id}/{seed}_checkpoint",
                    "models/closure_v1/anfis_ablation/"
                    f"{model_id}/seed_{seed}.checkpoint.pt",
                )
            )
    return tuple(sorted(identities))


PHASE3_OVERLAY_SOURCE_IDENTITIES = _expected_phase3_overlay_source_identities()


def _canonical_relative_path(value: str | Path) -> Path:
    path = Path(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in ("", ".", "..") for part in path.parts)
    ):
        raise ActivationLockError(f"non-canonical relative path: {value}")
    return path


def _file_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _directory_identity(metadata: os.stat_result) -> tuple[int, ...]:
    """Return the stable identity fields for an anchored directory.

    Directory timestamps and link counts legitimately change while activation
    creates or removes owned entries.  Device, inode, type, and permissions do
    not, and are sufficient to detect namespace substitution.
    """

    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode),
        stat.S_IMODE(metadata.st_mode),
    )


def _open_directory_chain(
    repo_root: Path,
    relative_directory: Path,
    *,
    label: str,
) -> tuple[list[int], list[tuple[int, str, int, tuple[int, ...]]], tuple[int, ...]]:
    directory = Path(relative_directory)
    if directory.is_absolute() or any(
        part in ("", "..") for part in directory.parts
    ):
        raise ActivationLockError(f"{label} directory escaped repository")
    parts = () if directory == Path(".") else directory.parts
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptors: list[int] = []
    bindings: list[tuple[int, str, int, tuple[int, ...]]] = []
    try:
        root_named = os.lstat(repo_root)
        root_fd = os.open(repo_root, flags)
        root_opened = os.fstat(root_fd)
        descriptors.append(root_fd)
        root_identity = _directory_identity(root_opened)
        if (
            stat.S_ISLNK(root_named.st_mode)
            or not stat.S_ISDIR(root_named.st_mode)
            or _directory_identity(root_named) != root_identity
        ):
            raise ActivationLockError(f"{label} repository root is unsafe")
        current = root_fd
        for component in parts:
            named = os.stat(component, dir_fd=current, follow_symlinks=False)
            child = os.open(component, flags, dir_fd=current)
            opened = os.fstat(child)
            identity = _directory_identity(opened)
            if (
                stat.S_ISLNK(named.st_mode)
                or not stat.S_ISDIR(named.st_mode)
                or not stat.S_ISDIR(opened.st_mode)
                or _directory_identity(named) != identity
            ):
                os.close(child)
                raise ActivationLockError(f"{label} ancestor is unsafe")
            descriptors.append(child)
            bindings.append((current, component, child, identity))
            current = child
        return descriptors, bindings, root_identity
    except ActivationLockError:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise
    except OSError as exc:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise ActivationLockError(
            f"{label} directory chain cannot be opened without following names"
        ) from exc


def _recapture_directory_chain(
    *,
    repo_root: Path,
    descriptors: Sequence[int],
    bindings: Sequence[tuple[int, str, int, tuple[int, ...]]],
    root_identity: tuple[int, ...],
    label: str,
) -> None:
    try:
        root_named = os.lstat(repo_root)
        if (
            stat.S_ISLNK(root_named.st_mode)
            or _directory_identity(root_named) != root_identity
            or _directory_identity(os.fstat(descriptors[0])) != root_identity
        ):
            raise ActivationLockError(f"{label} repository root was replaced")
        for parent, component, child, identity in bindings:
            named = os.stat(component, dir_fd=parent, follow_symlinks=False)
            if (
                stat.S_ISLNK(named.st_mode)
                or _directory_identity(named) != identity
                or _directory_identity(os.fstat(child)) != identity
            ):
                raise ActivationLockError(f"{label} ancestor was replaced")
    except ActivationLockError:
        raise
    except OSError as exc:
        raise ActivationLockError(f"{label} ancestor recapture failed") from exc


def _close_descriptors(descriptors: Sequence[int]) -> None:
    for descriptor in reversed(descriptors):
        os.close(descriptor)


def _regular_bytes(
    relative_path: str | Path,
    *,
    repo_root: Path,
    expected_mode: int = 0o644,
    expected_nlink: int = 1,
    expected_identity: tuple[int, int] | None = None,
) -> bytes:
    relative = _canonical_relative_path(relative_path)
    descriptors: list[int] = []
    descriptor: int | None = None
    try:
        descriptors, bindings, root_identity = _open_directory_chain(
            repo_root,
            relative.parent,
            label=f"anchored file {relative.as_posix()}",
        )
        parent = descriptors[-1]
        before = os.stat(relative.name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise ActivationLockError(f"path is not regular: {relative.as_posix()}")
        descriptor = os.open(
            relative.name,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent,
        )
        opened = os.fstat(descriptor)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after_opened = os.fstat(descriptor)
        after_named = os.stat(
            relative.name,
            dir_fd=parent,
            follow_symlinks=False,
        )
        _recapture_directory_chain(
            repo_root=repo_root,
            descriptors=descriptors,
            bindings=bindings,
            root_identity=root_identity,
            label=f"anchored file {relative.as_posix()}",
        )
        payload = b"".join(chunks)
    except ActivationLockError:
        raise
    except OSError as exc:
        raise ActivationLockError(
            f"cannot read anchored file: {relative.as_posix()}"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        _close_descriptors(descriptors)
    if (
        _file_identity(before) != _file_identity(opened)
        or _file_identity(opened) != _file_identity(after_opened)
        or _file_identity(opened) != _file_identity(after_named)
        or stat.S_IMODE(opened.st_mode) != expected_mode
        or opened.st_nlink != expected_nlink
        or len(payload) != opened.st_size
        or (
            expected_identity is not None
            and (opened.st_dev, opened.st_ino) != expected_identity
        )
    ):
        raise ActivationLockError(
            f"anchored file identity drifted: {relative.as_posix()}"
        )
    return payload


def _load_source_namespace(
    relative_path: Path,
    *,
    repo_root: Path,
    module_name: str,
    expected_git_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _regular_bytes(relative_path, repo_root=repo_root)
    if expected_git_record is not None:
        expected = dict(expected_git_record)
        if (
            set(expected) != {"path", "bytes", "sha256", "mode"}
            or expected.get("path") != relative_path.as_posix()
            or expected.get("mode") != "100644"
            or type(expected.get("bytes")) is not int
            or expected["bytes"] <= 0
            or not _is_sha256(expected.get("sha256"))
            or len(payload) != expected["bytes"]
            or _sha256_bytes(payload) != expected["sha256"]
        ):
            raise ActivationLockError(
                f"sealed source differs from Git: {relative_path.as_posix()}"
            )
    try:
        code = compile(
            payload,
            relative_path.as_posix(),
            "exec",
            dont_inherit=True,
        )
    except (SyntaxError, ValueError) as exc:
        raise ActivationLockError(
            f"cannot compile sealed source: {relative_path.as_posix()}"
        ) from exc
    module = ModuleType(module_name)
    module.__file__ = (repo_root / relative_path).as_posix()
    module.__package__ = module_name.rpartition(".")[0]
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        exec(code, module.__dict__)
    except BaseException as exc:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise ActivationLockError(
            f"cannot execute sealed source: {relative_path.as_posix()}"
        ) from exc
    return module.__dict__


def _git(
    repo_root: Path,
    arguments: Sequence[str],
    *,
    accepted_codes: tuple[int, ...] = (0,),
) -> bytes:
    command = [
        "/usr/bin/git",
        "--no-pager",
        "--literal-pathspecs",
        "--git-dir=" + (repo_root / ".git").as_posix(),
        "--work-tree=" + repo_root.as_posix(),
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "-c",
        "core.attributesFile=/dev/null",
        "-c",
        "core.excludesFile=/dev/null",
        "-c",
        "credential.helper=",
        "-c",
        "http.proxy=",
        *arguments,
    ]
    completed = subprocess.run(
        command,
        cwd=repo_root,
        env=GIT_ENVIRONMENT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode not in accepted_codes:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ActivationLockError(
            "sealed Git command failed"
            + (f": {message}" if message else "")
        )
    return completed.stdout


def _git_text(repo_root: Path, arguments: Sequence[str]) -> str:
    try:
        return _git(repo_root, arguments).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ActivationLockError("Git output is not UTF-8") from exc


def _git_oid(repo_root: Path, expression: str) -> str:
    value = _git_text(
        repo_root,
        ("rev-parse", "--verify", expression),
    ).strip()
    if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
        raise ActivationLockError(f"malformed Git object id: {expression}")
    return value


def _git_blob_record(repo_root: Path, commit: str, relative_path: str) -> dict[str, Any]:
    _canonical_relative_path(relative_path)
    tree = _git(repo_root, ("ls-tree", "-z", commit, "--", relative_path))
    if tree.count(b"\0") != 1 or not tree.endswith(b"\0"):
        raise ActivationLockError(f"Git tree binding is not unique: {relative_path}")
    try:
        header, encoded_path = tree[:-1].split(b"\t", 1)
        mode, object_type, oid = header.decode("ascii").split(" ")
        observed_path = encoded_path.decode("utf-8")
    except (UnicodeDecodeError, ValueError) as exc:
        raise ActivationLockError("Git tree record is malformed") from exc
    if (
        observed_path != relative_path
        or object_type != "blob"
        or mode not in ("100644", "100755")
    ):
        raise ActivationLockError(f"Git blob binding drifted: {relative_path}")
    blob = _git(repo_root, ("cat-file", "blob", oid))
    return {
        "path": relative_path,
        "bytes": len(blob),
        "sha256": _sha256_bytes(blob),
        "mode": mode,
    }


def _git_diff_scope(repo_root: Path, parent: str, child: str) -> list[dict[str, Any]]:
    raw = _git(
        repo_root,
        ("diff", "--name-status", "-z", "--no-renames", parent, child, "--"),
    )
    fields = raw.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    if len(fields) % 2:
        raise ActivationLockError("Git diff scope is malformed")
    records: list[dict[str, Any]] = []
    for offset in range(0, len(fields), 2):
        try:
            status = fields[offset].decode("ascii")
            path = fields[offset + 1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ActivationLockError("Git diff scope is not UTF-8") from exc
        if status not in ("A", "M"):
            raise ActivationLockError(f"forbidden Git diff status: {status}")
        blob = _git_blob_record(repo_root, child, path)
        records.append({**blob, "status": status})
    return sorted(records, key=lambda record: str(record["path"]))


def _require_clean_repository(repo_root: Path) -> None:
    if _git(
        repo_root,
        ("status", "--porcelain=v1", "-z", "--untracked-files=all"),
    ):
        raise ActivationLockError("repository worktree or index is not clean")


def _verify_live_remote(repo_root: Path, expected_head: str) -> None:
    raw = _git(
        repo_root,
        ("ls-remote", "--heads", LIVE_REMOTE_URL, "refs/heads/main"),
    )
    try:
        fields = raw.decode("ascii").strip().split()
    except UnicodeDecodeError as exc:
        raise ActivationLockError("live remote response is malformed") from exc
    if fields != [expected_head, "refs/heads/main"]:
        raise ActivationLockError("live remote main is not aligned")


def _require_direct_parent(
    repo_root: Path, *, child: str, expected_parent: str, label: str
) -> None:
    fields = _git_text(
        repo_root,
        ("rev-list", "--parents", "-n", "1", child),
    ).strip().split()
    if fields != [child, expected_parent]:
        raise ActivationLockError(
            f"{label} is not an exact direct non-merge descendant"
        )


def _topology(
    *, repo_root: Path, published_u: bool, verify_remote: bool
) -> dict[str, Any]:
    head = _git_oid(repo_root, "HEAD^{commit}")
    refs = {
        _git_oid(repo_root, "refs/heads/main^{commit}"),
        _git_oid(repo_root, "refs/remotes/origin/main^{commit}"),
        _git_oid(repo_root, "refs/remotes/origin/HEAD^{commit}"),
    }
    if refs != {head}:
        raise ActivationLockError("local Git refs are not aligned")
    if (
        _git_text(repo_root, ("symbolic-ref", "--quiet", "HEAD")).strip()
        != "refs/heads/main"
        or _git_text(
            repo_root,
            ("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"),
        ).strip()
        != "refs/remotes/origin/main"
        or _git_text(repo_root, ("remote", "get-url", "origin")).strip()
        != CONFIGURED_ORIGIN_URL
    ):
        raise ActivationLockError("branch or remote topology drifted")
    if published_u:
        p_commit = _git_oid(repo_root, "HEAD~1^{commit}")
        h_commit = _git_oid(repo_root, "HEAD~2^{commit}")
        r_commit = _git_oid(repo_root, "HEAD~3^{commit}")
        u_commit: str | None = head
    else:
        p_commit = head
        h_commit = _git_oid(repo_root, "HEAD~1^{commit}")
        r_commit = _git_oid(repo_root, "HEAD~2^{commit}")
        u_commit = None
    if r_commit != BASE_R_COMMIT or len({r_commit, h_commit, p_commit}) != 3:
        raise ActivationLockError("R-H-P commit topology drifted")
    _require_direct_parent(
        repo_root, child=h_commit, expected_parent=r_commit, label="H"
    )
    _require_direct_parent(
        repo_root, child=p_commit, expected_parent=h_commit, label="P"
    )
    if u_commit is not None:
        _require_direct_parent(
            repo_root, child=u_commit, expected_parent=p_commit, label="U"
        )
    _require_clean_repository(repo_root)
    if verify_remote:
        _verify_live_remote(repo_root, head)
    h_scope = _git_diff_scope(repo_root, r_commit, h_commit)
    p_scope = _git_diff_scope(repo_root, h_commit, p_commit)
    h_by_path = {str(record["path"]): record for record in h_scope}
    if {
        path: h_by_path.get(path, {}).get("status")
        for path in REQUIRED_H_SCOPE
    } != REQUIRED_H_SCOPE:
        raise ActivationLockError("H does not contain the required code boundary")
    if tuple(str(record["path"]) for record in p_scope) != EXPECTED_P_SCOPE_PATHS:
        raise ActivationLockError("P is not the exact ten-path data-only bundle")
    if any(record["status"] != "A" for record in p_scope):
        raise ActivationLockError("P contains a non-additive path")
    if published_u:
        u_scope = _git_diff_scope(repo_root, p_commit, head)
        if len(u_scope) != 1 or u_scope[0]["path"] != ACTIVATION_PATH.as_posix():
            raise ActivationLockError("U is not the exact activation-only commit")
    else:
        u_scope = []
        if (repo_root / ACTIVATION_PATH).exists() or (repo_root / ACTIVATION_PATH).is_symlink():
            raise ActivationLockError("activation path already exists before U")
    access_log = _regular_bytes(ACCESS_LOG_PATH, repo_root=repo_root)
    if access_log != b"":
        raise ActivationLockError("outcome access log is not empty")
    return {
        "r_commit": r_commit,
        "h_commit": h_commit,
        "p_commit": p_commit,
        "u_commit": u_commit,
        "h_scope": h_scope,
        "p_scope": p_scope,
        "u_scope": u_scope,
        "head": head,
    }


def _require_isolated_capture_environment() -> None:
    if (
        dict(os.environ) != {"LANG": "C", "LC_ALL": "C"}
        or sys.flags.isolated != 1
        or sys.flags.no_site != 1
        or not sys.dont_write_bytecode
        or "site" in sys.modules
        or Path.cwd().resolve() != PROJECT_ROOT
        or Path(sys.executable) != PROJECT_ROOT / ".venv/bin/python"
    ):
        raise ActivationLockError(
            "activation capture requires the exact isolated sanitized command"
        )


def _capture_material(*, repo_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    _require_isolated_capture_environment()
    runner = _load_source_namespace(
        RUNNER_PATH,
        repo_root=repo_root,
        module_name="closure_phase3_activation_runner",
    )
    authority = _load_source_namespace(
        AUTHORITY_PATH,
        repo_root=repo_root,
        module_name="closure_phase3_activation_authority",
    )
    collect = runner.get("collect_e0_u_activation_material")
    contract = runner.get("sealed_batch_contract")
    if not callable(collect) or not callable(contract):
        raise ActivationLockError("runner activation material API is absent")
    try:
        material = dict(collect(repo_root=repo_root))
        sealed_contract = dict(contract())
    except BaseException as exc:
        raise ActivationLockError("runner activation material capture failed") from exc
    if (
        material.get("status") != "e0_u_activation_material_ready"
        or material.get("outcome_paths_opened") is not False
        or material.get("future_outcomes_accessed") is not False
        or material.get("writes_performed") is not False
    ):
        raise ActivationLockError("runner activation material is not outcome-free")
    return material, sealed_contract, authority


def _manifest(
    *,
    topology: Mapping[str, Any],
    material: Mapping[str, Any],
    authority: Mapping[str, Any],
    phase3_overlay_deep_validation: Mapping[str, Any],
    expected_artifact_paths: Sequence[str],
    expected_artifact_formats: Mapping[str, str],
) -> dict[str, Any]:
    contract_sha = str(material["sealed_batch_contract_sha256"])
    execution_id = (
        "closure-v1-e0-u-"
        + str(topology["p_commit"])[:16]
        + "-"
        + contract_sha[:16]
    )
    value = {
        "schema_version": "closure_e0_u_activation_v1",
        "experiment_id": "closure_v1",
        "gate": "E0-U",
        "base_r_commit": BASE_R_COMMIT,
        "h_commit": topology["h_commit"],
        "p_commit": topology["p_commit"],
        "execution_id": execution_id,
        "git_remote_url": LIVE_REMOTE_URL,
        "sealed_batch_command": (
            "/usr/bin/env -i LANG=C LC_ALL=C .venv/bin/python -I -S -B "
            "src/experiments/run_closure_benchmark.py --execute-sealed-batch\n"
        ),
        "h_scope": topology["h_scope"],
        "p_scope": topology["p_scope"],
        "sealed_batch_contract_sha256": contract_sha,
        "expected_artifact_paths_sha256": material[
            "expected_artifact_paths_sha256"
        ],
        "expected_publication_order_sha256": material[
            "expected_publication_order_sha256"
        ],
        "sealed_runner_source_record": material["runner_source_record"],
        "sealed_context_builder_source_record": material[
            "context_builder_source_record"
        ],
        "sealed_component_source_records": material["component_source_records"],
        "sealed_support_source_records": material["support_source_records"],
        "sealed_runtime_environment_record": material[
            "runtime_environment_record"
        ],
        "phase3_overlay_deep_validation": dict(
            phase3_overlay_deep_validation
        ),
        "dvc_policy": material["dvc_policy"],
    }
    validate_shape = authority.get("_validate_activation_without_contract")
    validate_dvc = authority.get("_validate_dvc_policy")
    if not callable(validate_shape) or not callable(validate_dvc):
        raise ActivationLockError("authority activation validation API is absent")
    try:
        validated = dict(validate_shape(value))
        validate_dvc(
            value["dvc_policy"],
            tuple(expected_artifact_paths),
            dict(expected_artifact_formats),
        )
    except BaseException as exc:
        raise ActivationLockError("activation manifest rejected by authority") from exc
    if validated != value:
        raise ActivationLockError("authority changed the activation manifest")
    return value


def _validate_overlay_preflight_record(value: Any) -> dict[str, Any]:
    overlay_preflight = dict(value) if isinstance(value, Mapping) else {}
    if not isinstance(overlay_preflight, Mapping) or set(overlay_preflight) != {
        "manifest",
        "physical_outputs",
    }:
        raise ActivationLockError("published P overlay preflight result drifted")
    overlay_manifest = overlay_preflight.get("manifest")
    overlay_outputs = overlay_preflight.get("physical_outputs")
    if (
        not isinstance(overlay_manifest, Mapping)
        or set(overlay_manifest) != {"path", "bytes", "sha256"}
        or overlay_manifest.get("path") != PHASE3_OVERLAY_MANIFEST_PATH
        or type(overlay_manifest.get("bytes")) is not int
        or int(overlay_manifest["bytes"]) <= 0
        or type(overlay_manifest.get("sha256")) is not str
        or len(str(overlay_manifest["sha256"])) != 64
        or any(
            character not in "0123456789abcdef"
            for character in str(overlay_manifest["sha256"])
        )
        or not isinstance(overlay_outputs, list)
        or len(overlay_outputs) != len(PHASE3_OVERLAY_OUTPUT_PATHS)
    ):
        raise ActivationLockError("published P overlay preflight result drifted")
    for record, expected_path in zip(
        overlay_outputs,
        PHASE3_OVERLAY_OUTPUT_PATHS,
        strict=True,
    ):
        typed_record = dict(record) if isinstance(record, Mapping) else {}
        if (
            not isinstance(record, Mapping)
            or set(typed_record) != {"path", "bytes", "sha256"}
            or typed_record.get("path") != expected_path
            or type(typed_record.get("bytes")) is not int
            or int(typed_record["bytes"]) <= 0
            or type(typed_record.get("sha256")) is not str
            or len(str(typed_record["sha256"])) != 64
            or any(
                character not in "0123456789abcdef"
                for character in str(typed_record["sha256"])
            )
        ):
            raise ActivationLockError("published P overlay preflight result drifted")
    return overlay_preflight


def _validate_phase3_overlay_deep_validation(
    value: Any,
    *,
    expected_h_commit: str,
    expected_builder_record: Mapping[str, Any],
    expected_overlay_record: Mapping[str, Any],
) -> dict[str, Any]:
    if type(value) is not dict or set(value) != PHASE3_OVERLAY_DEEP_VALIDATION_KEYS:
        raise ActivationLockError("Phase 3 overlay deep-validation receipt drifted")
    receipt = dict(value)
    expected_scalars = {
        "schema_version": "closure_phase3_input_overlay_deep_validation_v1",
        "status": "passed",
        "experiment_id": "closure_v1",
        "surface_id": "closure_v1_phase3_input_overlay",
        "gate": "pre_E0-U",
        "expected_h_commit": expected_h_commit,
        "source_input_count": 27,
        "checkpoint_count": 25,
        "state_dict_array_count": 195,
        "warmup_row_count": 88,
        "warmup_site_count": 88,
        "npz_regenerated_byte_equality": True,
        "warmup_regenerated_byte_equality": True,
        "manifest_regenerated_byte_equality": True,
        "checkpoint_identity_revalidated": True,
        "numpy_torch_parity_recomputed": True,
        "warmup_projection_recomputed": True,
        "projection_contains_chlorophyll": False,
        "projection_contains_target": False,
        "opened_outcome_path_count": 0,
        "opened_target_path_count": 0,
        "writes_performed": False,
    }
    if any(
        type(receipt.get(key)) is not type(expected)
        or receipt.get(key) != expected
        for key, expected in expected_scalars.items()
    ):
        raise ActivationLockError("Phase 3 overlay deep-validation receipt drifted")

    git_builder = dict(expected_builder_record)
    if (
        set(git_builder) != {"path", "bytes", "sha256", "mode"}
        or git_builder.get("path") != PHASE3_OVERLAY_BUILDER_PATH.as_posix()
        or git_builder.get("mode") != "100644"
        or type(git_builder.get("bytes")) is not int
        or git_builder["bytes"] <= 0
        or not _is_sha256(git_builder.get("sha256"))
    ):
        raise ActivationLockError("Phase 3 overlay Git builder binding drifted")
    builder_source = receipt.get("builder_source")
    expected_builder_source = {
        "role": "phase3_input_overlay_builder",
        "path": git_builder["path"],
        "bytes": git_builder["bytes"],
        "sha256": git_builder["sha256"],
    }
    if (
        type(builder_source) is not dict
        or set(builder_source) != {"role", "path", "bytes", "sha256"}
        or builder_source != expected_builder_source
    ):
        raise ActivationLockError("Phase 3 overlay deep-validation builder drifted")

    source_inputs = receipt.get("source_inputs")
    if type(source_inputs) is not list or len(source_inputs) != 27:
        raise ActivationLockError("Phase 3 overlay deep-validation sources drifted")
    normalized_sources: list[dict[str, Any]] = []
    observed_identities: list[tuple[str, str]] = []
    for raw_record in source_inputs:
        if type(raw_record) is not dict or set(raw_record) != {
            "role",
            "path",
            "bytes",
            "sha256",
        }:
            raise ActivationLockError(
                "Phase 3 overlay deep-validation sources drifted"
            )
        record = dict(raw_record)
        if (
            type(record.get("role")) is not str
            or not record["role"]
            or type(record.get("path")) is not str
            or not record["path"]
            or type(record.get("bytes")) is not int
            or record["bytes"] <= 0
            or not _is_sha256(record.get("sha256"))
        ):
            raise ActivationLockError(
                "Phase 3 overlay deep-validation sources drifted"
            )
        observed_identities.append((record["role"], record["path"]))
        normalized_sources.append(record)
    if tuple(observed_identities) != PHASE3_OVERLAY_SOURCE_IDENTITIES:
        raise ActivationLockError(
            "Phase 3 overlay deep-validation source order drifted"
        )
    source_digest = receipt.get("source_inputs_sha256")
    if (
        not _is_sha256(source_digest)
        or source_digest
        != _sha256_bytes(_canonical_json_bytes(normalized_sources))
    ):
        raise ActivationLockError(
            "Phase 3 overlay deep-validation source digest drifted"
        )

    expected_overlay = _validate_overlay_preflight_record(expected_overlay_record)
    if (
        type(receipt.get("manifest")) is not dict
        or receipt["manifest"] != expected_overlay["manifest"]
        or type(receipt.get("physical_outputs")) is not list
        or receipt["physical_outputs"] != expected_overlay["physical_outputs"]
    ):
        raise ActivationLockError(
            "Phase 3 overlay deep-validation physical binding drifted"
        )
    if (
        type(receipt.get("history_projection")) is not list
        or receipt["history_projection"] != list(PHASE3_OVERLAY_HISTORY_PROJECTION)
        or type(receipt.get("panel_projection")) is not list
        or receipt["panel_projection"] != list(PHASE3_OVERLAY_PANEL_PROJECTION)
    ):
        raise ActivationLockError(
            "Phase 3 overlay deep-validation projection drifted"
        )
    return receipt


def _expected_manifest(
    *, repo_root: Path, published_u: bool, verify_remote: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    topology = _topology(
        repo_root=repo_root,
        published_u=published_u,
        verify_remote=verify_remote,
    )
    material, sealed_contract, authority = _capture_material(repo_root=repo_root)
    validate_overlay = authority.get("_validate_phase3_overlay_bundle")
    if not callable(validate_overlay):
        raise ActivationLockError("authority P-overlay validator is absent")
    try:
        overlay_record = _validate_overlay_preflight_record(
            validate_overlay(
                repo_root,
                topology["h_commit"],
                topology["p_commit"],
            )
        )
    except BaseException as exc:
        raise ActivationLockError(
            "published P overlay failed outcome-free preflight"
        ) from exc
    overlay_builder_git_record = _git_blob_record(
        repo_root,
        topology["h_commit"],
        PHASE3_OVERLAY_BUILDER_PATH.as_posix(),
    )
    overlay_builder_namespace = _load_source_namespace(
        PHASE3_OVERLAY_BUILDER_PATH,
        repo_root=repo_root,
        module_name="closure_phase3_activation_overlay_builder",
        expected_git_record=overlay_builder_git_record,
    )
    deep_validate = overlay_builder_namespace.get(
        "validate_materialized_phase3_input_overlay"
    )
    if not callable(deep_validate):
        raise ActivationLockError("Phase 3 overlay deep-validation API is absent")
    try:
        deep_validation = _validate_phase3_overlay_deep_validation(
            deep_validate(
                repo_root=repo_root,
                expected_h_commit=topology["h_commit"],
            ),
            expected_h_commit=topology["h_commit"],
            expected_builder_record=overlay_builder_git_record,
            expected_overlay_record=overlay_record,
        )
    except BaseException as exc:
        raise ActivationLockError(
            "published P overlay failed deep outcome-free validation"
        ) from exc
    e10_namespace = _load_source_namespace(
        E10_SOURCE_EVIDENCE_PATH,
        repo_root=repo_root,
        module_name="closure_phase3_activation_e10_source",
    )
    e10_loader = e10_namespace.get("load_closure_e10_software_evidence")
    if not callable(e10_loader):
        raise ActivationLockError("E10 source-evidence loader is absent")
    try:
        software_evidence = e10_loader(
            repo_root=repo_root,
            expected_h_commit=topology["h_commit"],
            require_git_publication=True,
        )
    except BaseException as exc:
        raise ActivationLockError(
            "published P E10 evidence failed outcome-free preflight"
        ) from exc
    if not isinstance(software_evidence, Mapping) or set(software_evidence) != {
        "public_tests_xml",
        "test_report",
        "openapi",
        "openapi_contract_report",
        "end_to_end_report",
        "environment",
    }:
        raise ActivationLockError("published P E10 evidence keys drifted")
    runner_namespace = sys.modules["closure_phase3_activation_runner"].__dict__
    expected_paths = tuple(runner_namespace["EXPECTED_ARTIFACT_PATHS"])
    expected_formats = dict(runner_namespace["EXPECTED_ARTIFACT_FORMATS"])
    contract_bytes = _canonical_json_bytes(sealed_contract)
    if _sha256_bytes(contract_bytes) != material["sealed_batch_contract_sha256"]:
        raise ActivationLockError("sealed batch contract digest drifted")
    if any((repo_root / path).exists() or (repo_root / path).is_symlink() for path in expected_paths):
        raise ActivationLockError("one or more sealed batch outputs already exist")
    value = _manifest(
        topology=topology,
        material=material,
        authority=authority,
        phase3_overlay_deep_validation=deep_validation,
        expected_artifact_paths=expected_paths,
        expected_artifact_formats=expected_formats,
    )
    return value, topology


def _unlink_owned_at(
    parent_fd: int,
    leaf: str,
    identity: tuple[int, int] | None,
    *,
    label: str = "owned file",
) -> bool:
    """Atomically capture and remove an owned regular-file name.

    Python does not expose Linux ``renameat2(RENAME_NOREPLACE)``.  A fresh,
    mode-0700 random directory supplies an atomically exclusive destination
    namespace, so renaming the canonical leaf to its fixed ``captured`` name
    cannot clobber an existing entry.  If the canonical leaf was exchanged at
    the rename boundary, the captured foreign inode is hard-linked back with
    no-clobber semantics before the tombstone link is removed.

    Same-UID interference with the unpredictable private tombstone namespace
    after capture is outside this process boundary's threat model: Linux has no
    conditional unlink primitive in the stdlib, and this module deliberately
    does not enlarge its TCB with ``ctypes``.
    """

    if identity is None:
        return False
    try:
        before = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if (before.st_dev, before.st_ino) != identity:
        raise ActivationLockError(f"{label} was replaced before cleanup")

    tombstone_leaf: str | None = None
    tombstone_fd: int | None = None
    tombstone_identity: tuple[int, ...] | None = None
    for _attempt in range(16):
        candidate = ".closure-owned-capture-" + os.urandom(16).hex()
        try:
            os.mkdir(candidate, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            continue
        tombstone_leaf = candidate
        try:
            tombstone_fd = os.open(
                candidate,
                os.O_RDONLY
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent_fd,
            )
            opened_directory = os.fstat(tombstone_fd)
            named_directory = os.stat(
                candidate,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
            tombstone_identity = _directory_identity(opened_directory)
            if (
                not stat.S_ISDIR(opened_directory.st_mode)
                or stat.S_IMODE(opened_directory.st_mode) != 0o700
                or _directory_identity(named_directory) != tombstone_identity
            ):
                raise ActivationLockError(
                    f"{label} tombstone namespace was replaced"
                )
        except BaseException:
            if tombstone_fd is not None:
                os.close(tombstone_fd)
                tombstone_fd = None
            try:
                current_directory = os.stat(
                    candidate,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                if (
                    tombstone_identity is not None
                    and _directory_identity(current_directory)
                    == tombstone_identity
                ):
                    os.rmdir(candidate, dir_fd=parent_fd)
            except OSError:
                pass
            raise
        break
    if tombstone_leaf is None or tombstone_fd is None:
        raise ActivationLockError(f"{label} tombstone namespace is unavailable")

    captured_leaf = "captured"
    captured_present = False
    try:
        try:
            os.rename(
                leaf,
                captured_leaf,
                src_dir_fd=parent_fd,
                dst_dir_fd=tombstone_fd,
            )
        except FileNotFoundError as exc:
            raise ActivationLockError(
                f"{label} disappeared at cleanup boundary"
            ) from exc
        captured_present = True
        os.fsync(parent_fd)
        os.fsync(tombstone_fd)
        captured = os.stat(
            captured_leaf,
            dir_fd=tombstone_fd,
            follow_symlinks=False,
        )
        captured_identity = (captured.st_dev, captured.st_ino)
        if captured_identity != identity:
            try:
                _rename_noreplace_at(
                    tombstone_fd,
                    captured_leaf,
                    parent_fd,
                    leaf,
                )
            except FileExistsError as exc:
                raise ActivationLockError(
                    f"{label} foreign inode could not be restored without clobber"
                ) from exc
            restored = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
            if (restored.st_dev, restored.st_ino) != captured_identity:
                raise ActivationLockError(
                    f"{label} foreign inode restoration drifted"
                )
            os.fsync(parent_fd)
            captured_present = False
            os.fsync(tombstone_fd)
            raise ActivationLockError(f"{label} was replaced at cleanup boundary")
        os.unlink(captured_leaf, dir_fd=tombstone_fd)
        captured_present = False
        os.fsync(tombstone_fd)
    finally:
        os.close(tombstone_fd)
        if not captured_present:
            try:
                named_directory = os.stat(
                    tombstone_leaf,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                if (
                    tombstone_identity is not None
                    and _directory_identity(named_directory)
                    == tombstone_identity
                ):
                    os.rmdir(tombstone_leaf, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
    os.fsync(parent_fd)
    return True


def _rename_noreplace_at(
    source_directory_fd: int,
    source_name: str,
    target_directory_fd: int,
    target_name: str,
) -> None:
    """Restore any captured entry type without replacing a new name."""

    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = libc.renameat2
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
        1,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))


def _remove_owned_directory_at(
    parent_fd: int,
    leaf: str,
    identity: tuple[int, int],
    *,
    label: str,
) -> bool:
    """Capture an owned directory before rmdir and restore any replacement."""

    try:
        before = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISDIR(before.st_mode)
        or (before.st_dev, before.st_ino) != identity
    ):
        raise ActivationLockError(f"{label} was replaced before cleanup")

    capture_leaf: str | None = None
    capture_fd: int | None = None
    capture_identity: tuple[int, ...] | None = None
    for _attempt in range(16):
        candidate = ".closure-owned-directory-capture-" + os.urandom(16).hex()
        try:
            os.mkdir(candidate, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            continue
        capture_leaf = candidate
        capture_fd = os.open(
            candidate,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        opened = os.fstat(capture_fd)
        named = os.stat(candidate, dir_fd=parent_fd, follow_symlinks=False)
        capture_identity = _directory_identity(opened)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or stat.S_IMODE(opened.st_mode) != 0o700
            or _directory_identity(named) != capture_identity
        ):
            os.close(capture_fd)
            raise ActivationLockError(f"{label} capture namespace drifted")
        break
    if capture_leaf is None or capture_fd is None:
        raise ActivationLockError(f"{label} capture namespace is unavailable")

    captured_leaf = "captured"
    captured_present = False
    try:
        os.rename(
            leaf,
            captured_leaf,
            src_dir_fd=parent_fd,
            dst_dir_fd=capture_fd,
        )
        captured_present = True
        captured = os.stat(
            captured_leaf,
            dir_fd=capture_fd,
            follow_symlinks=False,
        )
        captured_identity = (captured.st_dev, captured.st_ino)
        if captured_identity != identity:
            _rename_noreplace_at(capture_fd, captured_leaf, parent_fd, leaf)
            captured_present = False
            os.fsync(parent_fd)
            raise ActivationLockError(f"{label} was replaced at cleanup boundary")
        try:
            os.rmdir(captured_leaf, dir_fd=capture_fd)
        except OSError as exc:
            try:
                _rename_noreplace_at(capture_fd, captured_leaf, parent_fd, leaf)
                captured_present = False
                os.fsync(parent_fd)
            except OSError:
                pass
            raise ActivationLockError(f"{label} is not empty during cleanup") from exc
        captured_present = False
        os.fsync(capture_fd)
    finally:
        os.close(capture_fd)
        if not captured_present:
            try:
                named_capture = os.stat(
                    capture_leaf,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                if (
                    capture_identity is not None
                    and _directory_identity(named_capture) == capture_identity
                ):
                    os.rmdir(capture_leaf, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
    os.fsync(parent_fd)
    return True


def _ensure_directory_record(
    relative: Path,
    *,
    repo_root: Path,
) -> tuple[Path, bool, tuple[int, int]]:
    canonical = _canonical_relative_path(relative)
    descriptors: list[int] = []
    created = False
    identity: tuple[int, int] | None = None
    try:
        descriptors, bindings, root_identity = _open_directory_chain(
            repo_root,
            canonical.parent,
            label=f"temporary directory {canonical.as_posix()}",
        )
        parent = descriptors[-1]
        try:
            metadata = os.stat(
                canonical.name,
                dir_fd=parent,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            os.mkdir(canonical.name, 0o700, dir_fd=parent)
            os.fsync(parent)
            created = True
            metadata = os.stat(
                canonical.name,
                dir_fd=parent,
                follow_symlinks=False,
            )
        identity = (metadata.st_dev, metadata.st_ino)
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o700
        ):
            raise ActivationLockError("temporary directory is not anchored")
        opened = os.open(
            canonical.name,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent,
        )
        try:
            if _directory_identity(os.fstat(opened)) != _directory_identity(metadata):
                raise ActivationLockError("temporary directory identity drifted")
        finally:
            os.close(opened)
        current = os.stat(
            canonical.name,
            dir_fd=parent,
            follow_symlinks=False,
        )
        if _directory_identity(current) != _directory_identity(metadata):
            raise ActivationLockError("temporary directory identity drifted")
        _recapture_directory_chain(
            repo_root=repo_root,
            descriptors=descriptors,
            bindings=bindings,
            root_identity=root_identity,
            label=f"temporary directory {canonical.as_posix()}",
        )
        return repo_root / canonical, created, identity
    except BaseException:
        cleanup_error: BaseException | None = None
        if created and identity is not None and descriptors:
            parent = descriptors[-1]
            try:
                _remove_owned_directory_at(
                    parent,
                    canonical.name,
                    identity,
                    label="temporary directory",
                )
            except BaseException as exc:
                cleanup_error = exc
        if cleanup_error is not None:
            raise ActivationLockError(
                "temporary directory setup and cleanup failed closed"
            ) from cleanup_error
        raise
    finally:
        _close_descriptors(descriptors)


def _ensure_directory(relative: Path, *, repo_root: Path) -> tuple[Path, bool]:
    physical, created, _ = _ensure_directory_record(relative, repo_root=repo_root)
    return physical, created


def _relative_owned_path(path: Path, *, repo_root: Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            candidate = candidate.relative_to(repo_root)
        except ValueError as exc:
            raise ActivationLockError("owned path escaped repository") from exc
    return _canonical_relative_path(candidate)


def _unlink_owned(
    path: Path,
    identity: tuple[int, int] | None,
    *,
    repo_root: Path,
) -> bool:
    relative = _relative_owned_path(path, repo_root=repo_root)
    descriptors: list[int] = []
    try:
        descriptors, bindings, root_identity = _open_directory_chain(
            repo_root,
            relative.parent,
            label=f"owned file {relative.as_posix()}",
        )
        try:
            current = os.stat(
                relative.name,
                dir_fd=descriptors[-1],
                follow_symlinks=False,
            )
        except FileNotFoundError as exc:
            raise ActivationLockError(
                f"owned file disappeared before cleanup: {relative.as_posix()}"
            ) from exc
        if identity is None or (current.st_dev, current.st_ino) != identity:
            raise ActivationLockError(
                f"owned file was replaced before cleanup: {relative.as_posix()}"
            )
        removed = _unlink_owned_at(descriptors[-1], relative.name, identity)
        if not removed:
            raise ActivationLockError(
                f"owned file could not be removed: {relative.as_posix()}"
            )
        _recapture_directory_chain(
            repo_root=repo_root,
            descriptors=descriptors,
            bindings=bindings,
            root_identity=root_identity,
            label=f"owned file {relative.as_posix()}",
        )
        return removed
    finally:
        _close_descriptors(descriptors)


def _rmdir_owned(
    relative: Path,
    identity: tuple[int, int] | None,
    *,
    repo_root: Path,
) -> bool:
    canonical = _canonical_relative_path(relative)
    if identity is None:
        return False
    descriptors: list[int] = []
    try:
        descriptors, bindings, root_identity = _open_directory_chain(
            repo_root,
            canonical.parent,
            label=f"owned directory {canonical.as_posix()}",
        )
        parent = descriptors[-1]
        try:
            metadata = os.stat(
                canonical.name,
                dir_fd=parent,
                follow_symlinks=False,
            )
        except FileNotFoundError as exc:
            raise ActivationLockError(
                f"owned directory disappeared before cleanup: {canonical.as_posix()}"
            ) from exc
        else:
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or (metadata.st_dev, metadata.st_ino) != identity
            ):
                raise ActivationLockError(
                    f"owned directory was replaced before cleanup: {canonical.as_posix()}"
                )
            removed = _remove_owned_directory_at(
                parent,
                canonical.name,
                identity,
                label=f"owned directory {canonical.as_posix()}",
            )
        _recapture_directory_chain(
            repo_root=repo_root,
            descriptors=descriptors,
            bindings=bindings,
            root_identity=root_identity,
            label=f"owned directory {canonical.as_posix()}",
        )
        return removed
    finally:
        _close_descriptors(descriptors)


def _acquire_guard(*, repo_root: Path) -> GuardLease:
    directory, created, directory_identity = _ensure_directory_record(
        TEMP_DIRECTORY,
        repo_root=repo_root,
    )
    descriptors: list[int] = []
    descriptor: int | None = None
    guard_identity: tuple[int, int] | None = None
    try:
        descriptors, bindings, root_identity = _open_directory_chain(
            repo_root,
            TEMP_DIRECTORY,
            label="activation guard",
        )
        if (
            os.fstat(descriptors[-1]).st_dev,
            os.fstat(descriptors[-1]).st_ino,
        ) != directory_identity:
            raise ActivationLockError("activation guard directory was replaced")
        flags = (
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(
            GUARD_PATH.name,
            flags,
            0o600,
            dir_fd=descriptors[-1],
        )
        metadata = os.fstat(descriptor)
        guard_identity = (metadata.st_dev, metadata.st_ino)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
            or metadata.st_size != 0
        ):
            raise ActivationLockError("exclusive activation guard identity drifted")
        payload = _canonical_json_bytes(
            {"gate": "E0-U", "pid": os.getpid(), "purpose": "activation_write"}
        )
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise ActivationLockError("short activation guard write")
            offset += written
        os.fsync(descriptor)
        final_metadata = os.fstat(descriptor)
        named = os.stat(
            GUARD_PATH.name,
            dir_fd=descriptors[-1],
            follow_symlinks=False,
        )
        if (
            _file_identity(final_metadata) != _file_identity(named)
            or (final_metadata.st_dev, final_metadata.st_ino) != guard_identity
            or final_metadata.st_size != len(payload)
        ):
            raise ActivationLockError("exclusive activation guard identity drifted")
        _recapture_directory_chain(
            repo_root=repo_root,
            descriptors=descriptors,
            bindings=bindings,
            root_identity=root_identity,
            label="activation guard",
        )
        lease = GuardLease(
            repo_root=repo_root,
            path=directory / GUARD_PATH.name,
            identity=guard_identity,
            file_identity=_file_identity(final_metadata),
            directory_created=created,
            directory_identity=directory_identity,
            descriptor=descriptor,
            descriptors=descriptors,
            bindings=bindings,
            root_identity=root_identity,
        )
        descriptor = None
        descriptors = []
        return lease
    except BaseException as exc:
        if descriptor is not None:
            os.close(descriptor)
            descriptor = None
        if descriptors:
            _unlink_owned_at(descriptors[-1], GUARD_PATH.name, guard_identity)
        _close_descriptors(descriptors)
        descriptors = []
        if created:
            _rmdir_owned(
                TEMP_DIRECTORY,
                directory_identity,
                repo_root=repo_root,
            )
        if isinstance(exc, ActivationLockError):
            raise
        raise ActivationLockError("exclusive activation guard is unavailable") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        _close_descriptors(descriptors)
    raise ActivationLockError("exclusive activation guard identity is absent")


def _assert_guard_lease(lease: GuardLease, *, label: str) -> None:
    if lease.closed:
        raise ActivationLockError(f"{label} guard lease is closed")
    try:
        opened = os.fstat(lease.descriptor)
        named = os.stat(
            GUARD_PATH.name,
            dir_fd=lease.parent_fd,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise ActivationLockError(f"{label} activation guard disappeared") from exc
    if (
        _file_identity(opened) != lease.file_identity
        or _file_identity(named) != lease.file_identity
        or (opened.st_dev, opened.st_ino) != lease.identity
        or (named.st_dev, named.st_ino) != lease.identity
    ):
        raise ActivationLockError(f"{label} activation guard was replaced")
    _recapture_directory_chain(
        repo_root=lease.repo_root,
        descriptors=lease.descriptors,
        bindings=lease.bindings,
        root_identity=lease.root_identity,
        label=f"{label} activation guard",
    )


def _close_guard_lease(lease: GuardLease) -> None:
    if lease.closed:
        return
    try:
        os.close(lease.descriptor)
    except OSError:
        pass
    _close_descriptors(lease.descriptors)
    lease.descriptors.clear()
    lease.closed = True


def _release_guard_lease(lease: GuardLease) -> None:
    errors: list[BaseException] = []
    try:
        _assert_guard_lease(lease, label="release")
    except BaseException as exc:
        errors.append(exc)
    try:
        removed = _unlink_owned_at(
            lease.parent_fd,
            GUARD_PATH.name,
            lease.identity,
            label="activation guard",
        )
        if not removed and not errors:
            errors.append(ActivationLockError("activation guard disappeared"))
    except BaseException as exc:
        errors.append(exc)
    try:
        _recapture_directory_chain(
            repo_root=lease.repo_root,
            descriptors=lease.descriptors,
            bindings=lease.bindings,
            root_identity=lease.root_identity,
            label="activation guard release",
        )
    except BaseException as exc:
        errors.append(exc)
    if lease.directory_created and lease.bindings:
        parent, component, _child, identity = lease.bindings[-1]
        try:
            named_directory = os.stat(
                component,
                dir_fd=parent,
                follow_symlinks=False,
            )
            if (
                (named_directory.st_dev, named_directory.st_ino)
                == lease.directory_identity
                and _directory_identity(named_directory) == identity
            ):
                if not _remove_owned_directory_at(
                    parent,
                    component,
                    lease.directory_identity,
                    label="activation temporary directory",
                ):
                    errors.append(
                        ActivationLockError(
                            "activation temporary directory disappeared"
                        )
                    )
            else:
                errors.append(
                    ActivationLockError(
                        "activation temporary directory was replaced"
                    )
                )
        except FileNotFoundError:
            pass
        except BaseException as exc:
            errors.append(exc)
    _close_guard_lease(lease)
    if errors:
        raise ActivationLockError("activation guard release was not exact") from errors[0]


def _publish_activation(
    payload: bytes,
    *,
    repo_root: Path,
    expected_temp_directory_identity: tuple[int, int] | None = None,
    guard_lease: GuardLease | None = None,
    retain_anchor: bool = False,
) -> dict[str, Any] | tuple[dict[str, Any], ActivationPublicationLease]:
    temp_leaf = f"activation.{os.getpid()}.tmp"
    final_descriptors: list[int] = []
    temp_descriptors: list[int] = []
    descriptor: int | None = None
    temp_identity: tuple[int, int] | None = None
    final_identity: tuple[int, int] | None = None
    try:
        if guard_lease is not None:
            _assert_guard_lease(guard_lease, label="pre-publication")
        final_descriptors, final_bindings, final_root_identity = (
            _open_directory_chain(
                repo_root,
                ACTIVATION_PATH.parent,
                label="activation publication",
            )
        )
        temp_descriptors, temp_bindings, temp_root_identity = (
            _open_directory_chain(
                repo_root,
                TEMP_DIRECTORY,
                label="activation temporary publication",
            )
        )
        final_parent = final_descriptors[-1]
        temp_parent = temp_descriptors[-1]
        if guard_lease is not None and (
            final_root_identity != guard_lease.root_identity
            or temp_root_identity != guard_lease.root_identity
        ):
            raise ActivationLockError(
                "activation publication root differs from guard root"
            )
        temp_directory_metadata = os.fstat(temp_parent)
        if (
            expected_temp_directory_identity is not None
            and (
                temp_directory_metadata.st_dev,
                temp_directory_metadata.st_ino,
            )
            != expected_temp_directory_identity
        ):
            raise ActivationLockError("activation temporary directory was replaced")
        descriptor = os.open(
            temp_leaf,
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=temp_parent,
        )
        os.fchmod(descriptor, 0o644)
        opened = os.fstat(descriptor)
        temp_identity = (opened.st_dev, opened.st_ino)
        if (
            not stat.S_ISREG(opened.st_mode)
            or stat.S_IMODE(opened.st_mode) != 0o644
            or opened.st_nlink != 1
            or opened.st_size != 0
        ):
            raise ActivationLockError("activation temporary identity drifted")
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise ActivationLockError("short activation manifest write")
            offset += written
        os.fsync(descriptor)
        written_metadata = os.fstat(descriptor)
        temp_named = os.stat(temp_leaf, dir_fd=temp_parent, follow_symlinks=False)
        if (
            _file_identity(written_metadata) != _file_identity(temp_named)
            or (written_metadata.st_dev, written_metadata.st_ino) != temp_identity
            or written_metadata.st_size != len(payload)
        ):
            raise ActivationLockError("activation temporary identity drifted")
        _recapture_directory_chain(
            repo_root=repo_root,
            descriptors=temp_descriptors,
            bindings=temp_bindings,
            root_identity=temp_root_identity,
            label="activation temporary publication",
        )
        _recapture_directory_chain(
            repo_root=repo_root,
            descriptors=final_descriptors,
            bindings=final_bindings,
            root_identity=final_root_identity,
            label="activation publication",
        )
        if guard_lease is not None:
            _assert_guard_lease(guard_lease, label="activation pre-link")
        os.link(
            temp_leaf,
            ACTIVATION_PATH.name,
            src_dir_fd=temp_parent,
            dst_dir_fd=final_parent,
            follow_symlinks=False,
        )
        final_identity = temp_identity
        if guard_lease is not None:
            _assert_guard_lease(guard_lease, label="activation post-link")
        linked = os.stat(
            ACTIVATION_PATH.name,
            dir_fd=final_parent,
            follow_symlinks=False,
        )
        linked_opened = os.fstat(descriptor)
        if (
            final_identity != temp_identity
            or _file_identity(linked) != _file_identity(linked_opened)
            or linked.st_nlink != 2
        ):
            raise ActivationLockError("activation hardlink identity drifted")
        if not _unlink_owned_at(
            temp_parent,
            temp_leaf,
            temp_identity,
            label="activation publication temporary",
        ):
            raise ActivationLockError("activation publication temporary disappeared")
        temp_identity = None
        os.fsync(final_parent)
        final_named = os.stat(
            ACTIVATION_PATH.name,
            dir_fd=final_parent,
            follow_symlinks=False,
        )
        final_opened = os.fstat(descriptor)
        if (
            final_identity != (final_opened.st_dev, final_opened.st_ino)
            or _file_identity(final_named) != _file_identity(final_opened)
            or final_opened.st_nlink != 1
            or final_opened.st_size != len(payload)
        ):
            raise ActivationLockError("published activation identity drifted")
        _recapture_directory_chain(
            repo_root=repo_root,
            descriptors=temp_descriptors,
            bindings=temp_bindings,
            root_identity=temp_root_identity,
            label="activation temporary publication",
        )
        _recapture_directory_chain(
            repo_root=repo_root,
            descriptors=final_descriptors,
            bindings=final_bindings,
            root_identity=final_root_identity,
            label="activation publication",
        )
        if guard_lease is not None:
            _assert_guard_lease(guard_lease, label="activation post-publication")
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        observed = b"".join(chunks)
        after_read = os.fstat(descriptor)
        named_after_read = os.stat(
            ACTIVATION_PATH.name,
            dir_fd=final_parent,
            follow_symlinks=False,
        )
        if (
            observed != payload
            or _file_identity(after_read) != _file_identity(named_after_read)
            or (after_read.st_dev, after_read.st_ino) != final_identity
        ):
            raise ActivationLockError("published activation bytes drifted")
        _recapture_directory_chain(
            repo_root=repo_root,
            descriptors=temp_descriptors,
            bindings=temp_bindings,
            root_identity=temp_root_identity,
            label="activation temporary publication after readback",
        )
        _recapture_directory_chain(
            repo_root=repo_root,
            descriptors=final_descriptors,
            bindings=final_bindings,
            root_identity=final_root_identity,
            label="activation publication after readback",
        )
        if guard_lease is not None:
            _assert_guard_lease(guard_lease, label="activation final readback")
        record = {
            "path": ACTIVATION_PATH.as_posix(),
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
            "manifest_written_last": True,
            "no_clobber": True,
        }
        if retain_anchor:
            if final_identity is None:
                raise ActivationLockError("published activation identity is absent")
            lease = ActivationPublicationLease(
                repo_root=repo_root,
                identity=final_identity,
                expected_bytes=len(payload),
                expected_sha256=_sha256_bytes(payload),
                descriptor=descriptor,
                descriptors=final_descriptors,
                bindings=final_bindings,
                root_identity=final_root_identity,
            )
            descriptor = None
            final_descriptors = []
            return record, lease
        return record
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
            descriptor = None
        if temp_descriptors:
            _unlink_owned_at(temp_descriptors[-1], temp_leaf, temp_identity)
        if final_descriptors:
            _unlink_owned_at(
                final_descriptors[-1],
                ACTIVATION_PATH.name,
                final_identity,
            )
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
        _close_descriptors(temp_descriptors)
        _close_descriptors(final_descriptors)


def _close_activation_publication_lease(
    lease: ActivationPublicationLease,
    *,
    suppress_errors: bool = False,
) -> None:
    if lease.closed:
        return
    errors: list[OSError] = []
    try:
        os.close(lease.descriptor)
    except OSError as exc:
        errors.append(exc)
    for descriptor in reversed(lease.descriptors):
        try:
            os.close(descriptor)
        except OSError as exc:
            errors.append(exc)
    lease.descriptors.clear()
    lease.closed = True
    if errors and not suppress_errors:
        raise errors[0]


def _assert_activation_publication_lease(
    lease: ActivationPublicationLease,
    *,
    label: str,
) -> None:
    if lease.closed:
        raise ActivationLockError(f"{label} activation lease is closed")
    try:
        before_named = os.stat(
            ACTIVATION_PATH.name,
            dir_fd=lease.parent_fd,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise ActivationLockError(f"{label} activation disappeared") from exc
    try:
        before_opened = os.fstat(lease.descriptor)
        os.lseek(lease.descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(lease.descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after_opened = os.fstat(lease.descriptor)
        after_named = os.stat(
            ACTIVATION_PATH.name,
            dir_fd=lease.parent_fd,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise ActivationLockError(f"{label} activation recapture failed") from exc
    payload = b"".join(chunks)
    if (
        not stat.S_ISREG(before_named.st_mode)
        or stat.S_IMODE(before_named.st_mode) != 0o644
        or before_named.st_nlink != 1
        or before_named.st_size != lease.expected_bytes
        or (before_named.st_dev, before_named.st_ino) != lease.identity
        or _file_identity(before_named) != _file_identity(before_opened)
        or _file_identity(before_opened) != _file_identity(after_opened)
        or _file_identity(after_opened) != _file_identity(after_named)
        or len(payload) != lease.expected_bytes
        or _sha256_bytes(payload) != lease.expected_sha256
    ):
        raise ActivationLockError(f"{label} activation was replaced")
    _recapture_directory_chain(
        repo_root=lease.repo_root,
        descriptors=lease.descriptors,
        bindings=lease.bindings,
        root_identity=lease.root_identity,
        label=f"{label} activation",
    )


def _commit_activation_publication(lease: ActivationPublicationLease) -> None:
    _assert_activation_publication_lease(lease, label="transaction commit")
    # The guard has already been released and the activation was recaptured.
    # Descriptor-close diagnostics cannot make that durable commit rollbackable,
    # so they must not turn success into an ambiguous reported failure.
    _close_activation_publication_lease(lease, suppress_errors=True)


def _rollback_activation_publication(lease: ActivationPublicationLease) -> None:
    errors: list[BaseException] = []
    if lease.closed:
        return
    try:
        named = os.stat(
            ACTIVATION_PATH.name,
            dir_fd=lease.parent_fd,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        pass
    except OSError as exc:
        errors.append(exc)
    else:
        try:
            _unlink_owned_at(
                lease.parent_fd,
                ACTIVATION_PATH.name,
                lease.identity,
                label="activation manifest rollback",
            )
        except BaseException as exc:
            errors.append(exc)
    try:
        _recapture_directory_chain(
            repo_root=lease.repo_root,
            descriptors=lease.descriptors,
            bindings=lease.bindings,
            root_identity=lease.root_identity,
            label="activation rollback",
        )
    except BaseException as exc:
        errors.append(exc)
    finally:
        _close_activation_publication_lease(lease)
    if errors:
        raise ActivationLockError("activation publication rollback was not exact") from (
            errors[0]
        )


def check_only(
    *, repo_root: Path = PROJECT_ROOT, verify_remote: bool = True
) -> dict[str, Any]:
    value, topology = _expected_manifest(
        repo_root=repo_root,
        published_u=False,
        verify_remote=verify_remote,
    )
    payload = _canonical_json_bytes(value)
    return {
        "gate": "E0-U",
        "status": "ready_to_generate_activation",
        "h_commit": topology["h_commit"],
        "p_commit": topology["p_commit"],
        "activation_path": ACTIVATION_PATH.as_posix(),
        "activation_bytes": len(payload),
        "activation_sha256": _sha256_bytes(payload),
        "outcome_paths_opened": False,
        "future_outcomes_accessed": False,
        "writes_performed": False,
    }


def generate(
    *, repo_root: Path = PROJECT_ROOT, verify_remote: bool = True
) -> dict[str, Any]:
    guard = _acquire_guard(repo_root=repo_root)
    publication_lease: ActivationPublicationLease | None = None
    try:
        value, topology = _expected_manifest(
            repo_root=repo_root,
            published_u=False,
            verify_remote=verify_remote,
        )
        payload = _canonical_json_bytes(value)
        publication = _publish_activation(
            payload,
            repo_root=repo_root,
            expected_temp_directory_identity=guard.directory_identity,
            guard_lease=guard,
            retain_anchor=True,
        )
        if (
            not isinstance(publication, tuple)
            or len(publication) != 2
            or not isinstance(publication[0], dict)
            or not isinstance(publication[1], ActivationPublicationLease)
        ):
            raise ActivationLockError("activation publication lease is malformed")
        publication_record, publication_lease = publication
        _assert_guard_lease(guard, label="post-publication")
    except BaseException as primary_error:
        try:
            _release_guard_lease(guard)
        except BaseException:
            if not guard.closed:
                _close_guard_lease(guard)
        rollback_error = None
        if publication_lease is not None:
            try:
                _rollback_activation_publication(publication_lease)
            except BaseException as exc:
                rollback_error = exc
        if rollback_error is not None:
            raise ActivationLockError(
                "activation transaction rollback was not exact"
            ) from rollback_error
        raise primary_error
    if publication_lease is None:
        raise ActivationLockError("activation publication lease is absent")
    try:
        _release_guard_lease(guard)
    except BaseException as guard_error:
        try:
            _rollback_activation_publication(publication_lease)
        except BaseException as rollback_error:
            raise ActivationLockError(
                "activation transaction rollback was not exact"
            ) from rollback_error
        raise ActivationLockError(
            "activation guard failed after publication; activation rolled back"
        ) from guard_error
    try:
        _commit_activation_publication(publication_lease)
    except BaseException as commit_error:
        try:
            _rollback_activation_publication(publication_lease)
        except BaseException as rollback_error:
            raise ActivationLockError(
                "activation transaction rollback was not exact"
            ) from rollback_error
        raise commit_error
    return {
        "gate": "E0-U",
        "status": "activation_written_unpublished",
        "h_commit": topology["h_commit"],
        "p_commit": topology["p_commit"],
        "publication": publication_record,
        "outcome_paths_opened": False,
        "future_outcomes_accessed": False,
        "writes_performed": True,
    }


def validate_published(
    *, repo_root: Path = PROJECT_ROOT, verify_remote: bool = True
) -> dict[str, Any]:
    expected, topology = _expected_manifest(
        repo_root=repo_root,
        published_u=True,
        verify_remote=verify_remote,
    )
    payload = _regular_bytes(ACTIVATION_PATH, repo_root=repo_root)
    try:
        observed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ActivationLockError("published activation is not JSON") from exc
    if not isinstance(observed, dict) or _canonical_json_bytes(observed) != payload:
        raise ActivationLockError("published activation is not canonical")
    if observed != expected:
        raise ActivationLockError("published activation differs from recaptured material")
    return {
        "gate": "E0-U",
        "status": "published_activation_valid",
        "h_commit": topology["h_commit"],
        "p_commit": topology["p_commit"],
        "u_commit": topology["u_commit"],
        "activation_path": ACTIVATION_PATH.as_posix(),
        "activation_bytes": len(payload),
        "activation_sha256": _sha256_bytes(payload),
        "outcome_paths_opened": False,
        "future_outcomes_accessed": False,
        "writes_performed": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check-only", action="store_true")
    modes.add_argument("--generate", action="store_true")
    modes.add_argument("--validate-published", action="store_true")
    parser.add_argument(
        "--no-verify-remote",
        action="store_true",
        help="test-only/local diagnostic; never use for an authorization bundle",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    verify_remote = not arguments.no_verify_remote
    try:
        if arguments.check_only:
            result = check_only(verify_remote=verify_remote)
        elif arguments.generate:
            result = generate(verify_remote=verify_remote)
        else:
            result = validate_published(verify_remote=verify_remote)
    except ActivationLockError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(_canonical_json_bytes(result).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
