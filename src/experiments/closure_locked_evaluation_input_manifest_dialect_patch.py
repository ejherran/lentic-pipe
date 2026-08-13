"""Adopt the immutable R-E0-MI manifest dialect under E0-MID.

The input bundle is not rewritten or rerun.  This overlay binds the published
P-E0-MIC authority, records the exact portable ten-file R contract, and lets
the generic publication assistant adopt only its exact three known findings
after the strict input-only reconstruction succeeds.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from src.experiments import (
    closure_locked_evaluation_input_panel_dvc_identity_patch as mic,
)

mib = mic.mib
mcal = mic.mcal
mcalm = mic.mcalm
mt = mic.mt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_H_MIC_COMMIT = "6e01932fa6380ac4ed9614ad1ef2cc412d6fab3e"
BASE_P_MIC_COMMIT = "707fbe92c7147d281c2a272178289e948a137b1b"
PATCH_GATE = "E0-MID"
R_ADOPTION_GATE = "R-E0-MID"
UNDERLYING_R_GATE = "R-E0-MI"
EXPERIMENT_ID = "closure_v1"
LOCK_SCHEMA_VERSION = "closure_locked_evaluation_input_manifest_dialect_patch_lock_v1"
COMPANION_SCHEMA_VERSION = (
    "closure_locked_evaluation_input_manifest_dialect_patch_lock_manifest_v1"
)

DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/locked_evaluation_input_manifest_dialect_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "configs/closure_v1/locked_evaluation_input_manifest_dialect_patch_lock.json"
)
DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "configs/closure_v1/locked_evaluation_input_manifest_dialect_patch_lock_manifest.json"
)
DEFAULT_PATCH_MANIFEST_PATH = DEFAULT_PATCH_LOCK_MANIFEST_PATH
LOCKER_PATH = Path(
    "src/experiments/lock_closure_locked_evaluation_input_manifest_dialect_patch.py"
)
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_e0_mid/locked_evaluation_input_manifest_dialect_patch_lock.guard"
)
R_ARCHIVE_ROOT = Path(
    "tmp/r_e0_mi_manifest_dialect_blocked_20260813T143904Z"
)
PRECOMMIT_PATH = "src/data/prepare_commit_artifacts.py"
CORE_PATH = "src/experiments/closure_locked_evaluation_input_manifest_dialect_patch.py"
TEST_PATH = "tests/test_closure_locked_evaluation_input_manifest_dialect_patch.py"
DOC_PATH = "docs/closure_v1/E0_M_LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_PATCH.md"
PATCH_PATHS = tuple(
    sorted(
        {
            DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
            DOC_PATH,
            PRECOMMIT_PATH,
            CORE_PATH,
            LOCKER_PATH.as_posix(),
            TEST_PATH,
        }
    )
)
PATCH_COMPONENT_GIT_MODES = {
    path: ("100755" if path == PRECOMMIT_PATH else "100644")
    for path in PATCH_PATHS
}
LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_H_STAGED_SCOPE = {
    path: ("M" if path == PRECOMMIT_PATH else "A") for path in PATCH_PATHS
}
LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_P_STAGED_SCOPE = {
    DEFAULT_PATCH_LOCK_PATH.as_posix(): "A",
    DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(): "A",
}
R_PHYSICAL_OUTPUT_PATHS = tuple(mic.R_PHYSICAL_OUTPUT_PATHS)
R_POINTER_PATHS = tuple(mic.R_POINTER_PATHS)
R_LIGHT_OUTPUT_PATHS = tuple(mic.R_LIGHT_OUTPUT_PATHS)
R_TRACKED_OUTPUT_PATHS = tuple(mic.R_TRACKED_OUTPUT_PATHS)
R_OUTPUT_PATHS = (*R_PHYSICAL_OUTPUT_PATHS, *R_POINTER_PATHS, *R_LIGHT_OUTPUT_PATHS)
LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_R_STAGED_SCOPE = {
    path.as_posix(): "A" for path in R_TRACKED_OUTPUT_PATHS
}
FINAL_CALIBRATION_H_STAGED_SCOPE = dict(
    LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_H_STAGED_SCOPE
)
FINAL_CALIBRATION_P_STAGED_SCOPE = dict(
    LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_P_STAGED_SCOPE
)
FINAL_CALIBRATION_R_STAGED_SCOPE = dict(
    LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_R_STAGED_SCOPE
)
P_MIC_PATHS = tuple(path.as_posix() for path in mic.CURRENT_LOCK_PATHS)
H_MIC_PATHS = tuple(mic.PATCH_PATHS)
CURRENT_LOCK_PATHS = (DEFAULT_PATCH_LOCK_PATH, DEFAULT_PATCH_LOCK_MANIFEST_PATH)
LOCK_TEMPORARY_PATHS = tuple(mcal._temporary_path(path) for path in CURRENT_LOCK_PATHS)
R8_OUTPUT_CONTRACT = tuple(mic.R8_OUTPUT_CONTRACT)
EXPECTED_COMPANION_INPUT_COUNT = 16
EXPECTED_HISTORICAL_INPUT_COUNT = 6
EXPECTED_COMPANION_OUTPUT_COUNT = 1

R_OUTPUT_CONTRACT = (
    {"path": "data/closure_v1/locked_evaluation/input_history.parquet", "bytes": 480855, "sha256": "70b25305b861467a0c253abc9bb44f5038120341dfe77a8143560dc05eb391c0", "mode": 420, "kind": "physical"},
    {"path": "data/closure_v1/locked_evaluation/intent_origins.parquet", "bytes": 171047, "sha256": "de6be0c7a8eefa282f7db25510373801d0839249fbbbb8c6c62188b80ce2d578", "mode": 420, "kind": "physical"},
    {"path": "data/closure_v1/locked_evaluation/origin_features.parquet", "bytes": 238955, "sha256": "8099942097f5544d35ecee9640e68ec2be79dbf0f17483b3c5c64b963d252d6d", "mode": 420, "kind": "physical"},
    {"path": "data/closure_v1/locked_evaluation/sequence_features.parquet", "bytes": 436677, "sha256": "b5f37c326ef19852a96ebf970970e4be60006a0dc0d21a3181b918e7a3a2f1a7", "mode": 420, "kind": "physical"},
    {"path": "data/closure_v1/locked_evaluation/input_history.parquet.dvc", "bytes": 103, "sha256": "a479daefc0a3ba596dbd06350eefd991eeeda00857d8ea423a535547f1632077", "mode": 420, "kind": "pointer"},
    {"path": "data/closure_v1/locked_evaluation/intent_origins.parquet.dvc", "bytes": 104, "sha256": "943900d54a0f99fef5c72c6341edb28c8dffd5831fcc2c2b34ae4527888e27ff", "mode": 420, "kind": "pointer"},
    {"path": "data/closure_v1/locked_evaluation/origin_features.parquet.dvc", "bytes": 105, "sha256": "5cc90a4cb90796a6c96f57a745e9a72fb325ecd92816a1314c0321ef69fee851", "mode": 420, "kind": "pointer"},
    {"path": "data/closure_v1/locked_evaluation/sequence_features.parquet.dvc", "bytes": 107, "sha256": "ad5b266d68098365350f3d8532a3f4bba1b12a85b3a90dda93a6205f83f0c46b", "mode": 420, "kind": "pointer"},
    {"path": "reports/closure_v1/01_surface/locked_evaluation_input_summary.json", "bytes": 443, "sha256": "217b495f811517a0c3f94cc6f98910175f54c4b017dc4fd81efd7691326b9ea0", "mode": 420, "kind": "summary"},
    {"path": "reports/closure_v1/01_surface/locked_evaluation_input_manifest.json", "bytes": 20049, "sha256": "c8d7b4f0f207f217eb0289cbc3563877c0ffd592dc41120559d7a24ddd6a03df", "mode": 420, "kind": "manifest"},
)
R_OUTPUTS_SHA256 = "2b1e89ffa6816ad3bbaa8e1e8c5122b6b0b014dfc4645886443ffabe84036c17"
ARCHIVED_R_IDENTITY_CONTRACT = (
    {"path": "data/closure_v1/locked_evaluation/input_history.parquet", "device": 2069, "inode": 77866321, "mode": 420, "nlink": 1, "size": 480855, "mtime_ns": 1786631399087982955, "ctime_ns": 1786632608998770766},
    {"path": "data/closure_v1/locked_evaluation/input_history.parquet.dvc", "device": 2069, "inode": 77866327, "mode": 420, "nlink": 1, "size": 103, "mtime_ns": 1786631947190541903, "ctime_ns": 1786632609000770813},
    {"path": "data/closure_v1/locked_evaluation/intent_origins.parquet", "device": 2069, "inode": 77866322, "mode": 420, "nlink": 1, "size": 171047, "mtime_ns": 1786631399177762777, "ctime_ns": 1786632608999770790},
    {"path": "data/closure_v1/locked_evaluation/intent_origins.parquet.dvc", "device": 2069, "inode": 77866329, "mode": 420, "nlink": 1, "size": 104, "mtime_ns": 1786631948099821769, "ctime_ns": 1786632609001770836},
    {"path": "data/closure_v1/locked_evaluation/origin_features.parquet", "device": 2069, "inode": 77866323, "mode": 420, "nlink": 1, "size": 238955, "mtime_ns": 1786631399266661975, "ctime_ns": 1786632608999770790},
    {"path": "data/closure_v1/locked_evaluation/origin_features.parquet.dvc", "device": 2069, "inode": 77866330, "mode": 420, "nlink": 1, "size": 105, "mtime_ns": 1786631949019082029, "ctime_ns": 1786632609002770859},
    {"path": "data/closure_v1/locked_evaluation/sequence_features.parquet", "device": 2069, "inode": 77866324, "mode": 420, "nlink": 1, "size": 436677, "mtime_ns": 1786631399366389002, "ctime_ns": 1786632609000770813},
    {"path": "data/closure_v1/locked_evaluation/sequence_features.parquet.dvc", "device": 2069, "inode": 77866331, "mode": 420, "nlink": 1, "size": 107, "mtime_ns": 1786631950094840074, "ctime_ns": 1786632609003770882},
    {"path": "reports/closure_v1/01_surface/locked_evaluation_input_manifest.json", "device": 2069, "inode": 77072773, "mode": 420, "nlink": 1, "size": 20049, "mtime_ns": 1786631399566552083, "ctime_ns": 1786632609004770905},
    {"path": "reports/closure_v1/01_surface/locked_evaluation_input_summary.json", "device": 2069, "inode": 77072772, "mode": 420, "nlink": 1, "size": 443, "mtime_ns": 1786631399477478834, "ctime_ns": 1786632609003770882},
)
ARCHIVED_R_IDENTITY_SHA256 = (
    "7c73775ae17797dc08381a3aab78048387bc2eb4ee0041c74e21cdd72368a54c"
)
GENERIC_MANIFEST_FINDINGS_CONTRACT = (
    {"level": "fail", "check": "manifest", "path": "reports/closure_v1/01_surface/locked_evaluation_input_manifest.json", "message": "Experiment manifest status is `completed_unpublished`, expected `completed`."},
    {"level": "fail", "check": "manifest", "path": "reports/closure_v1/01_surface/locked_evaluation_input_manifest.json", "message": "Experiment manifest must contain a non-empty `outputs` list."},
    {"level": "fail", "check": "manifest", "path": "reports/closure_v1/01_surface/locked_evaluation_input_summary.json", "message": "Staged report artifact is not listed in any experiment manifest output."},
)
MANIFEST_DIALECT_CONTRACT = {
    "manifest_status": "completed_unpublished",
    "generic_expected_status": "completed",
    "generic_output_field": "outputs",
    "strict_physical_output_field": "physical_outputs",
    "strict_summary_field": "summary",
    "generic_non_ok_finding_count": 3,
    "adoption_policy": "exact_multiset_after_strict_input_only_validation_only",
    "r_rewrite_authorized": False,
    "scientific_rerun_authorized": False,
}
FAILED_ATTEMPT = {
    "attempted_gate": "R-E0-MI",
    "status": "failed_closed_exact_r_preserved",
    "phase": "precommit_generic_manifest_validation",
    "failure_code": "sealed_input_manifest_dialect_rejected_by_generic_dialect",
    "precommit_exit_code": 1,
    "report_sha256": "d843c34f2260f8f5a7a0745492099265a44a85c9240956589a8caf9b219d8aef",
    "generic_failure_count": 3,
    "r_output_count": 10,
    "r_bytes_changed": False,
    "r_rewrite_performed": False,
    "scientific_rerun_performed": False,
    "dvc_add_completed": True,
    "dvc_push_performed": False,
    "git_commit_performed": False,
    "git_push_performed": False,
    "retry_authorized": False,
}
UNPUBLISHED_AUTHORIZATIONS = {
    "r_adoption_authorized": False,
    "scientific_rerun_authorized": False,
    "input_bundle_execution_authorized": False,
    "dvc_add_authorized": False,
    "dvc_push_authorized": False,
    "evaluation_authorized": False,
    "e0_m_authorized": False,
    "e0_u_authorized": False,
    "outcome_access_authorized": False,
    "target_access_authorized": False,
    "git_commit_authorized": False,
    "git_push_authorized": False,
}

TYPE_CHECK_COMMAND = ("poetry", "run", "ty", "check")
FOCUSED_TEST_COMMAND = (
    "poetry", "run", "pytest", "-q",
    "tests/test_prepare_commit_artifacts.py", TEST_PATH,
)
POETRY_CHECK_COMMAND = ("poetry", "check")
PUBLICATION_GUARD_COMMAND = ("scripts/check_repo_publication_ready.sh",)
DIFF_CHECK_COMMAND = ("git", "diff", "--check")
FOCUSED_TEST_COUNT = 48
EXPECTED_MIC_AUTHORITY_BINDING_SHA256 = (
    "86cb101f0150b1fa79b999832decb95a5625d8f9630f5b6dfb13f95c99cf806b"
)


class ClosureLockedEvaluationInputManifestDialectPatchError(RuntimeError):
    """Raised when E0-MID topology, bytes, or adoption policy drifts."""


def _error(message: str) -> ClosureLockedEvaluationInputManifestDialectPatchError:
    return ClosureLockedEvaluationInputManifestDialectPatchError(f"E0-MID {message}")


def _root(repo_root: Path | None) -> Path:
    return PROJECT_ROOT if repo_root is None else Path(repo_root)


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8") + b"\n"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _deep_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


def _git_head(repo_root: Path, revision: str = "HEAD") -> str:
    return cast(str, mcal._git(repo_root, "rev-parse", revision)).strip()


def _file_record(path: Path, *, role: str, repo_root: Path) -> dict[str, Any]:
    try:
        return mic._file_record(path, role=role, repo_root=repo_root)
    except Exception as exc:
        raise _error(f"physical record failed: {path}") from exc


def _git_record_at_commit(path: str | Path, *, role: str, commit: str, repo_root: Path, expected_mode: str = "100644") -> dict[str, Any]:
    try:
        return mic._git_record_at_commit(Path(path), role=role, commit=commit, repo_root=repo_root, expected_mode=expected_mode)
    except Exception as exc:
        raise _error(f"historical Git record failed: {path}@{commit}") from exc


def _artifact_record(path: Path, *, role: str, repo_root: Path, commit: str | None = None, expected_mode: str = "100644") -> dict[str, Any]:
    try:
        return mcal._git_artifact_record(
            path,
            role=role,
            repo_root=repo_root,
            commit=commit,
            expected_mode=expected_mode,
        )
    except Exception as exc:
        raise _error(f"physical/Git binding drifted: {path}") from exc


def _base_p_mic_authority(*, repo_root: Path) -> dict[str, Any]:
    if mcal._single_parent(repo_root, BASE_P_MIC_COMMIT, context="P-E0-MIC") != BASE_H_MIC_COMMIT:
        raise _error("published P-E0-MIC parent drifted")
    expected_h = {"added": 5, "modified": 1, "deleted": 0, "path_count": 6, "paths": list(mic.PATCH_PATHS)}
    expected_p = {"added": 2, "modified": 0, "deleted": 0, "path_count": 2, "paths": sorted(P_MIC_PATHS)}
    if mcal._git_scope(repo_root, mcal._single_parent(repo_root, BASE_H_MIC_COMMIT, context="H-E0-MIC"), BASE_H_MIC_COMMIT) != expected_h or mcal._git_scope(repo_root, BASE_H_MIC_COMMIT, BASE_P_MIC_COMMIT) != expected_p:
        raise _error("published E0-MIC topology/scope drifted")
    components = [_artifact_record(Path(path), role="published_p_mic_component", repo_root=repo_root, commit=BASE_P_MIC_COMMIT) for path in P_MIC_PATHS]
    return {"gate": mic.PATCH_GATE, "status": "published_p_mic_authority_validated", "h_commit": BASE_H_MIC_COMMIT, "p_commit": BASE_P_MIC_COMMIT, "p_components": components, "p_components_sha256": mcal._digest_records(components), "outcome_paths_opened": False}


def _candidate_status_is_exact(repo_root: Path) -> bool:
    records = mcal._workspace_status_records(repo_root)
    if {path for _, path in records} != set(PATCH_PATHS):
        return False
    by_path = {path: code for code, path in records}
    return all(by_path[path] in ({" M", "M ", "MM"} if path == PRECOMMIT_PATH else {"??", "A "}) for path in PATCH_PATHS)


def _h_patch_authority(*, repo_root: Path, verify_remote: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    if cast(str, mcal._git(repo_root, "branch", "--show-current")).strip() != "main":
        raise _error("requires branch main")
    head = _git_head(repo_root)
    expected_scope = {"added": 5, "modified": 1, "deleted": 0, "path_count": 6, "paths": list(PATCH_PATHS)}
    if head == BASE_P_MIC_COMMIT:
        if not _candidate_status_is_exact(repo_root):
            raise _error("candidate H workspace is not exact 1M+5A")
        component_commit: str | None = None
        h_head = head
    else:
        if mcal._single_parent(repo_root, head, context="H-E0-MID") != BASE_P_MIC_COMMIT or mcal._git_scope(repo_root, BASE_P_MIC_COMMIT, head) != expected_scope or mcal._workspace_status_records(repo_root):
            raise _error("published H topology/worktree drifted")
        component_commit, h_head = head, head
    components = [_artifact_record(Path(path), role="locked_evaluation_input_manifest_dialect_patch_h_component", repo_root=repo_root, commit=component_commit, expected_mode=PATCH_COMPONENT_GIT_MODES[path]) if component_commit else _artifact_record(Path(path), role="locked_evaluation_input_manifest_dialect_patch_h_component", repo_root=repo_root, expected_mode=PATCH_COMPONENT_GIT_MODES[path]) for path in PATCH_PATHS]
    tracking = _git_head(repo_root, "origin/main")
    expected_ref = BASE_P_MIC_COMMIT if component_commit is None else head
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != expected_ref or remote != expected_ref:
        raise _error("H refs drifted")
    return ({"base_p_mic_commit": BASE_P_MIC_COMMIT, "h_patch_head": h_head, "branch": "main", "remote_head": remote, "scope": expected_scope}, {"gate": "H-E0-MID", "component_count": 6, "added_count": 5, "modified_count": 1, "components": components, "components_sha256": mcal._digest_records(components)})


def _historical_h_mic_records(*, repo_root: Path) -> list[dict[str, Any]]:
    records = [{**_git_record_at_commit(path, role="superseded_h_mic_component", repo_root=repo_root, commit=BASE_H_MIC_COMMIT, expected_mode=mic.PATCH_COMPONENT_GIT_MODES[path]), "commit": BASE_H_MIC_COMMIT} for path in H_MIC_PATHS]
    records.sort(key=lambda record: cast(str, record["path"]))
    if len(records) != 6:
        raise _error("historical H-E0-MIC set is not exact6")
    return records


def _namespace_state(
    *,
    repo_root: Path,
    p_present: bool,
    r_present: bool,
    owned_lock_guard: Any | None = None,
) -> dict[str, Any]:
    try:
        predecessor = mic._require_namespace(
            repo_root=repo_root,
            current_lock_state="present",
            r_state="complete" if r_present else "absent",
        )
    except Exception as exc:
        raise _error("predecessor namespace drifted") from exc
    if (
        predecessor.get("coordination_present_count") != 0
        or predecessor.get("formal_e0_m_output_present_count") != 0
        or predecessor.get("outcome_access_log_absent") is not True
    ):
        raise _error("predecessor E0-M/outcome/coordination namespace drifted")
    p = [
        path
        for path in CURRENT_LOCK_PATHS
        if mcal._entry_exists(path, repo_root=repo_root)
    ]
    if len(p) != (2 if p_present else 0):
        raise _error("P namespace state drifted")
    if p_present:
        for path in CURRENT_LOCK_PATHS:
            try:
                mcal._read_regular_bytes_and_metadata(
                    path,
                    repo_root=repo_root,
                    expected_mode=0o644,
                    require_nlink_one=True,
                )
            except Exception as exc:
                raise _error(f"P namespace output drifted: {path}") from exc
    r = [
        Path(cast(str, record["path"]))
        for record in R_OUTPUT_CONTRACT
        if mcal._entry_exists(Path(cast(str, record["path"])), repo_root=repo_root)
    ]
    if len(r) != (10 if r_present else 0):
        raise _error("R namespace is partial or unexpected")
    allowed: set[Path] = set()
    if owned_lock_guard is not None:
        mic.mcalm.mcall.mcalk.mcalj._require_owned_guard_identity(
            owned_lock_guard
        )
        allowed.add(LOCKER_GUARD_PATH)
    occupied = [
        path
        for path in (*LOCK_TEMPORARY_PATHS, LOCKER_GUARD_PATH)
        if path not in allowed and mcal._entry_exists(path, repo_root=repo_root)
    ]
    if occupied:
        raise _error(
            "coordination namespace occupied: "
            + ", ".join(path.as_posix() for path in occupied)
        )
    return {
        "p_output_present_count": len(p),
        "r_output_present_count": len(r),
        "r_state": "complete" if r_present else "absent",
        "temporary_present_count": 0,
        "coordination_present_count": 0,
        "guard_present": owned_lock_guard is not None,
        "predecessor_coordination_present_count": 0,
        "formal_e0_m_output_present_count": 0,
        "outcome_access_log_absent": True,
        "outcome_paths_opened": False,
    }


def _r_archive_metadata_snapshot(
    repo_root: Path | None = None,
) -> tuple[dict[str, Any], ...]:
    """Capture the exact ignored archive through anchored no-follow dirfds."""
    root = _root(repo_root)
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise _error("R archive inspection requires O_DIRECTORY/O_NOFOLLOW")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory_flags |= getattr(os, "O_CLOEXEC", 0)
    descriptors: list[int] = []
    try:
        current = os.open(root, directory_flags)
        descriptors.append(current)
        name_bindings: list[tuple[int, str, str, os.stat_result]] = []
        archive_prefix: list[str] = []
        for component in R_ARCHIVE_ROOT.parts:
            if component in {"", ".", ".."}:
                raise _error("R archive path is not a closed relative path")
            parent = current
            archive_prefix.append(component)
            metadata = os.stat(
                component,
                dir_fd=parent,
                follow_symlinks=False,
            )
            if not stat.S_ISDIR(metadata.st_mode):
                raise _error("R archive ancestor is not a directory")
            current = os.open(component, directory_flags, dir_fd=parent)
            descriptors.append(current)
            opened = os.fstat(current)
            if (
                opened.st_dev != metadata.st_dev
                or opened.st_ino != metadata.st_ino
            ):
                raise _error("R archive ancestor changed while opening")
            name_bindings.append(
                (parent, component, "/".join(archive_prefix), metadata)
            )
        archive_descriptor = current
        observed: dict[str, os.stat_result] = {}
        observed_directories: set[str] = set()

        def walk(directory_descriptor: int, prefix: tuple[str, ...]) -> None:
            try:
                names = sorted(entry.name for entry in os.scandir(directory_descriptor))
            except OSError as exc:
                raise _error("R archive directory enumeration failed") from exc
            for name in names:
                if name in {"", ".", ".."} or "/" in name:
                    raise _error("R archive contains an invalid entry name")
                relative = "/".join((*prefix, name))
                try:
                    metadata = os.stat(
                        name,
                        dir_fd=directory_descriptor,
                        follow_symlinks=False,
                    )
                except OSError as exc:
                    raise _error(f"R archive entry inspection failed: {relative}") from exc
                name_bindings.append(
                    (directory_descriptor, name, relative, metadata)
                )
                if stat.S_ISDIR(metadata.st_mode):
                    observed_directories.add(relative)
                    try:
                        child = os.open(
                            name,
                            directory_flags,
                            dir_fd=directory_descriptor,
                        )
                    except OSError as exc:
                        raise _error(
                            f"R archive directory is not stable/no-follow: {relative}"
                        ) from exc
                    descriptors.append(child)
                    opened = os.fstat(child)
                    if (
                        opened.st_dev != metadata.st_dev
                        or opened.st_ino != metadata.st_ino
                    ):
                        raise _error(f"R archive directory changed: {relative}")
                    walk(child, (*prefix, name))
                elif stat.S_ISREG(metadata.st_mode):
                    if relative in observed:
                        raise _error(f"R archive duplicate entry: {relative}")
                    observed[relative] = metadata
                else:
                    raise _error(f"R archive contains a non-regular entry: {relative}")

        walk(archive_descriptor, ())
        for parent_descriptor, name, relative, initial in name_bindings:
            try:
                final = os.stat(
                    name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
            except OSError as exc:
                raise _error(f"R archive entry disappeared: {relative}") from exc
            if (
                final.st_dev,
                final.st_ino,
                final.st_mode,
                final.st_nlink,
                final.st_size,
                final.st_mtime_ns,
                final.st_ctime_ns,
            ) != (
                initial.st_dev,
                initial.st_ino,
                initial.st_mode,
                initial.st_nlink,
                initial.st_size,
                initial.st_mtime_ns,
                initial.st_ctime_ns,
            ):
                raise _error(f"R archive entry changed during inspection: {relative}")
    except ClosureLockedEvaluationInputManifestDialectPatchError:
        raise
    except OSError as exc:
        raise _error("R archive root/ancestor is absent or not no-follow") from exc
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass
    expected_paths = {
        cast(str, record["path"]) for record in ARCHIVED_R_IDENTITY_CONTRACT
    }
    expected_directories = {
        parent.as_posix()
        for raw_path in expected_paths
        for parent in Path(raw_path).parents
        if parent != Path(".")
    }
    if (
        set(observed) != expected_paths | {"SNAPSHOT.md"}
        or observed_directories != expected_directories
    ):
        raise _error("R archive tree is not exact10 plus SNAPSHOT.md")
    snapshot_metadata = observed["SNAPSHOT.md"]
    if (
        stat.S_IMODE(snapshot_metadata.st_mode) != 0o644
        or int(snapshot_metadata.st_nlink) != 1
    ):
        raise _error("R archive SNAPSHOT.md metadata drifted")
    records = [
        {
            "path": raw_path,
            "device": int(observed[raw_path].st_dev),
            "inode": int(observed[raw_path].st_ino),
            "mode": stat.S_IMODE(observed[raw_path].st_mode),
            "nlink": int(observed[raw_path].st_nlink),
            "size": int(observed[raw_path].st_size),
            "mtime_ns": int(observed[raw_path].st_mtime_ns),
            "ctime_ns": int(observed[raw_path].st_ctime_ns),
        }
        for raw_path in sorted(expected_paths)
    ]
    if (
        _sha256_bytes(_canonical_json_bytes(ARCHIVED_R_IDENTITY_CONTRACT))
        != ARCHIVED_R_IDENTITY_SHA256
        or _canonical_json_bytes(records)
        != _canonical_json_bytes(ARCHIVED_R_IDENTITY_CONTRACT)
    ):
        raise _error("R archive exact identity contract drifted")
    return tuple(records)


def preflight_closure_locked_evaluation_input_manifest_dialect_patch_schema(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = _root(repo_root)
    try:
        schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
        validator = getattr(mcal.closure_contract, "_assert_supported_json_schema")
        validator(schema)
    except Exception as exc:
        raise _error("closed schema preflight failed") from exc
    return {"status": "schema_ready", "gate": PATCH_GATE, "schema_count": 1, "schema_version": LOCK_SCHEMA_VERSION, "schemas": [_file_record(DEFAULT_PATCH_LOCK_SCHEMA, role="locked_evaluation_input_manifest_dialect_patch_lock_schema", repo_root=root)], "supported_subset_verified": True, "duplicate_keys_rejected": True}


def collect_closure_locked_evaluation_input_manifest_dialect_patch_prelock_state(*, verify_remote: bool = False, repo_root: Path | None = None) -> dict[str, Any]:
    root = _root(repo_root)
    repository, h_patch = _h_patch_authority(repo_root=root, verify_remote=verify_remote)
    base = _base_p_mic_authority(repo_root=root)
    historical = _historical_h_mic_records(repo_root=root)
    namespace = _namespace_state(repo_root=root, p_present=False, r_present=False)
    archive_before = _r_archive_metadata_snapshot(root)
    archive_after = _r_archive_metadata_snapshot(root)
    if archive_before != archive_after:
        raise _error("R archive metadata changed during prelock collection")
    return {"repository": repository, "h_patch": h_patch, "base_authority": base, "failed_attempt": _deep_copy(FAILED_ATTEMPT), "manifest_dialect_contract": _deep_copy(MANIFEST_DIALECT_CONTRACT), "generic_manifest_findings_contract": _deep_copy(GENERIC_MANIFEST_FINDINGS_CONTRACT), "r_output_contract": _deep_copy(R_OUTPUT_CONTRACT), "r_outputs_sha256": R_OUTPUTS_SHA256, "archived_r_identity_contract": _deep_copy(ARCHIVED_R_IDENTITY_CONTRACT), "archived_r_identity_sha256": ARCHIVED_R_IDENTITY_SHA256, "historical_inputs": historical, "historical_inputs_sha256": mcal._digest_records(historical), "coordination_namespace": namespace, "schema_preflight": preflight_closure_locked_evaluation_input_manifest_dialect_patch_schema(repo_root=root), "prelock": {"base_p_mic_output_present_count": 2, "p_output_present_count": 0, "r_output_present_count": 0, "component_count": 6, "physical_input_count": 16, "historical_input_count": 6, "companion_output_count": 1, "companion_contract": {"physical_input_count": 16, "historical_input_count": 6, "output_count": 1, "script_path": LOCKER_PATH.as_posix(), "manifest_written_last": True}, "archived_r_preserved": True, "archived_r_count": 10, "archive_identity_verified": True, "archive_identity_sha256": ARCHIVED_R_IDENTITY_SHA256, "archive_parent_walk_no_follow": True, "archive_metadata_inspected": True, "archive_bytes_opened": False, "scientific_execution_run": False, "r_files_touched": False, "r_files_staged": False, "dvc_commands_run": False, "outcome_paths_opened": False}}


def _default_unrun_verification() -> dict[str, Any]:
    return {"status": "not_run_by_payload_builder", "commands_run": False, "scientific_execution_run": False, "r_files_touched": False, "r_files_staged": False, "dvc_commands_run": False, "outcome_paths_opened": False}


def build_closure_locked_evaluation_input_manifest_dialect_patch_lock_payload(prelock: Mapping[str, Any], verification: Mapping[str, Any] | None = None, *, generated_at_utc: str | None = None, repo_root: Path | None = None) -> dict[str, Any]:
    del repo_root
    required = {"repository", "h_patch", "base_authority", "failed_attempt", "manifest_dialect_contract", "generic_manifest_findings_contract", "r_output_contract", "r_outputs_sha256", "archived_r_identity_contract", "archived_r_identity_sha256", "historical_inputs", "historical_inputs_sha256", "coordination_namespace", "schema_preflight", "prelock"}
    if not isinstance(prelock, Mapping) or set(prelock) != required:
        raise _error("prelock dialect drifted")
    return {"schema_version": LOCK_SCHEMA_VERSION, "experiment_id": EXPERIMENT_ID, "gate": PATCH_GATE, "status": "locked_unpublished", "generated_at_utc": generated_at_utc or datetime.now(timezone.utc).isoformat(), **{key: _deep_copy(prelock[key]) for key in required}, "verification": _deep_copy(verification if verification is not None else _default_unrun_verification()), "authorizations": dict(UNPUBLISHED_AUTHORIZATIONS)}


def validate_closure_locked_evaluation_input_manifest_dialect_patch_lock_payload(payload: Mapping[str, Any], *, verify_remote: bool = False, repo_root: Path | None = None) -> dict[str, Any]:
    root = _root(repo_root)
    try:
        schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
        mcal.validate_json_schema(payload, schema)
    except Exception as exc:
        raise _error("lock schema validation failed") from exc
    value = payload.get("generated_at_utc")
    if not isinstance(value, str):
        raise _error("generated timestamp absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _error("generated timestamp malformed") from exc
    if parsed.tzinfo is None or payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise _error("timestamp/authorizations drifted")
    state = collect_closure_locked_evaluation_input_manifest_dialect_patch_prelock_state(verify_remote=verify_remote, repo_root=root)
    expected = build_closure_locked_evaluation_input_manifest_dialect_patch_lock_payload(state, cast(Mapping[str, Any], payload["verification"]), generated_at_utc=value)
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("lock semantic reconstruction drifted")
    return dict(payload)


def _public_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in ("role", "path", "bytes", "sha256")}


def _expected_companion(
    payload: Mapping[str, Any], lock_record: Mapping[str, Any]
) -> dict[str, Any]:
    base = cast(Mapping[str, Any], payload["base_authority"])
    patch = cast(Mapping[str, Any], payload["h_patch"])
    prior = cast(Sequence[Mapping[str, Any]], base["p_components"])
    current = cast(Sequence[Mapping[str, Any]], patch["components"])
    r8 = [
        {
            "role": "published_immutable_r8_output",
            "path": record["path"],
            "bytes": record["bytes"],
            "sha256": record["sha256"],
        }
        for record in R8_OUTPUT_CONTRACT
    ]
    inputs = [_public_record(record) for record in (*prior, *current, *r8)]
    inputs.sort(key=lambda record: cast(str, record["path"]))
    if (
        len(inputs) != EXPECTED_COMPANION_INPUT_COUNT
        or len({record["path"] for record in inputs})
        != EXPECTED_COMPANION_INPUT_COUNT
    ):
        raise _error("companion physical input set drifted")
    historical = [
        dict(record)
        for record in cast(
            Sequence[Mapping[str, Any]], payload["historical_inputs"]
        )
    ]
    historical.sort(key=lambda record: cast(str, record["path"]))
    if (
        len(historical) != EXPECTED_HISTORICAL_INPUT_COUNT
        or len({record["path"] for record in historical})
        != EXPECTED_HISTORICAL_INPUT_COUNT
    ):
        raise _error("companion historical input set drifted")
    script = next(
        record for record in inputs if record["path"] == LOCKER_PATH.as_posix()
    )
    return {
        "schema_version": COMPANION_SCHEMA_VERSION,
        "status": "completed",
        "gate": PATCH_GATE,
        "script": script,
        "inputs": inputs,
        "historical_inputs": historical,
        "outputs": [dict(lock_record)],
        "manifest_written_last": True,
        "scientific_execution_run": False,
        "input_bundle_run": False,
        "r_files_touched": False,
        "r_files_staged": False,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
    }


def _parse_canonical_json(
    path: Path, *, repo_root: Path
) -> tuple[dict[str, Any], bytes, os.stat_result]:
    try:
        payload, metadata = mcal._read_regular_bytes_and_metadata(
            path,
            repo_root=repo_root,
            expected_mode=0o644,
            require_nlink_one=True,
        )
        value = mcal._parse_json_bytes(payload, context=path.as_posix())
    except Exception as exc:
        raise _error(f"canonical JSON read failed: {path}") from exc
    if not isinstance(value, dict) or payload != _canonical_json_bytes(value):
        raise _error(f"canonical JSON drifted: {path}")
    return value, payload, metadata


def _physical_snapshot(repo_root: Path | None = None) -> tuple[dict[str, Any], ...]:
    """Snapshot only P-MIC2, H-MID6, and immutable R8 (exact16)."""
    root = _root(repo_root)
    records: list[dict[str, Any]] = []
    for raw_path in (*P_MIC_PATHS, *PATCH_PATHS):
        path = Path(raw_path)
        git_mode = PATCH_COMPONENT_GIT_MODES.get(raw_path, "100644")
        try:
            payload, metadata = mcal._read_regular_bytes_and_metadata(
                path,
                repo_root=root,
                expected_mode=int(git_mode[-3:], 8),
                require_nlink_one=True,
            )
        except Exception as exc:
            raise _error(f"physical input drifted: {raw_path}") from exc
        records.append(
            {
                "path": raw_path,
                "device": int(metadata.st_dev),
                "inode": int(metadata.st_ino),
                "mode": stat.S_IMODE(metadata.st_mode),
                "nlink": int(metadata.st_nlink),
                "size": len(payload),
                "mtime_ns": int(metadata.st_mtime_ns),
                "ctime_ns": int(metadata.st_ctime_ns),
                "sha256": _sha256_bytes(payload),
            }
        )
    for expected in R8_OUTPUT_CONTRACT:
        raw_path = cast(str, expected["path"])
        try:
            payload, metadata = mcal._read_regular_bytes_and_metadata(
                Path(raw_path),
                repo_root=root,
                expected_mode=0o644,
                require_nlink_one=True,
            )
        except Exception as exc:
            raise _error(f"immutable R8 input drifted: {raw_path}") from exc
        if {
            "path": raw_path,
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
        } != expected:
            raise _error(f"immutable R8 content drifted: {raw_path}")
        records.append(
            {
                "path": raw_path,
                "device": int(metadata.st_dev),
                "inode": int(metadata.st_ino),
                "mode": stat.S_IMODE(metadata.st_mode),
                "nlink": int(metadata.st_nlink),
                "size": len(payload),
                "mtime_ns": int(metadata.st_mtime_ns),
                "ctime_ns": int(metadata.st_ctime_ns),
                "sha256": _sha256_bytes(payload),
            }
        )
    records.sort(key=lambda record: cast(str, record["path"]))
    if (
        len(records) != EXPECTED_COMPANION_INPUT_COUNT
        or len({record["path"] for record in records})
        != EXPECTED_COMPANION_INPUT_COUNT
    ):
        raise _error("physical snapshot is not exact16")
    return tuple(records)


def _require_physical_snapshot(
    expected: Sequence[Mapping[str, Any]], *, repo_root: Path, context: str
) -> None:
    if _canonical_json_bytes(expected) != _canonical_json_bytes(
        _physical_snapshot(repo_root)
    ):
        raise _error(f"physical authority changed {context}")


def _validate_verification(value: Any, *, repo_root: Path) -> None:
    if value == _default_unrun_verification():
        return
    keys = {
        "schema_preflight",
        "full_type_check",
        "focused_tests",
        "poetry_check",
        "publication_guard",
        "git_diff_check",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise _error("verification evidence dialect drifted")
    if _canonical_json_bytes(value["schema_preflight"]) != _canonical_json_bytes(
        preflight_closure_locked_evaluation_input_manifest_dialect_patch_schema(
            repo_root=repo_root
        )
    ):
        raise _error("schema verification evidence drifted")
    for key, command in (
        ("full_type_check", TYPE_CHECK_COMMAND),
        ("poetry_check", POETRY_CHECK_COMMAND),
        ("publication_guard", PUBLICATION_GUARD_COMMAND),
        ("git_diff_check", DIFF_CHECK_COMMAND),
    ):
        mcal._validate_command_evidence(
            value[key], expected_command=command, context=key
        )
    focused = value["focused_tests"]
    base_keys = {
        "command",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
    }
    if (
        not isinstance(focused, Mapping)
        or set(focused)
        != base_keys | {"test_count", "skipped_count", "deselected_count"}
        or focused.get("test_count") != FOCUSED_TEST_COUNT
        or focused.get("skipped_count") != 0
        or focused.get("deselected_count") != 0
    ):
        raise _error("focused verification evidence drifted")
    mcal._validate_command_evidence(
        {key: focused[key] for key in base_keys},
        expected_command=FOCUSED_TEST_COMMAND,
        context="focused_tests",
    )


def _require_publication_verification(
    payload: Mapping[str, Any], *, repo_root: Path
) -> None:
    verification = payload.get("verification")
    if verification == _default_unrun_verification():
        raise _error("publication requires frozen verification evidence")
    _validate_verification(verification, repo_root=repo_root)


def _validate_published_lock_payload(
    payload: Mapping[str, Any], *, h_head: str, repo_root: Path
) -> None:
    try:
        schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=repo_root)
        mcal.validate_json_schema(payload, schema)
    except Exception as exc:
        raise _error("published lock schema validation failed") from exc
    generated = payload.get("generated_at_utc")
    if not isinstance(generated, str):
        raise _error("published lock generated timestamp is absent")
    try:
        parsed = datetime.fromisoformat(generated.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _error("published lock generated timestamp is malformed") from exc
    if parsed.tzinfo is None or payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise _error("published lock timestamp/authorizations drifted")
    _validate_verification(payload.get("verification"), repo_root=repo_root)
    _require_publication_verification(payload, repo_root=repo_root)
    state = _published_h_state(h_head, repo_root=repo_root)
    expected = build_closure_locked_evaluation_input_manifest_dialect_patch_lock_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=cast(str, payload["generated_at_utc"]),
    )
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("published lock reconstruction drifted")


def _published_h_state(h_head: str, *, repo_root: Path) -> dict[str, Any]:
    expected_scope = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(PATCH_PATHS),
    }
    if (
        h_head == BASE_P_MIC_COMMIT
        or mcal._single_parent(repo_root, h_head, context="H-E0-MID")
        != BASE_P_MIC_COMMIT
        or mcal._git_scope(repo_root, BASE_P_MIC_COMMIT, h_head) != expected_scope
    ):
        raise _error("published H topology drifted")
    components = [
        _artifact_record(
            Path(path),
            role="locked_evaluation_input_manifest_dialect_patch_h_component",
            repo_root=repo_root,
            commit=h_head,
            expected_mode=PATCH_COMPONENT_GIT_MODES[path],
        )
        for path in PATCH_PATHS
    ]
    historical = _historical_h_mic_records(repo_root=repo_root)
    return {
        "repository": {
            "base_p_mic_commit": BASE_P_MIC_COMMIT,
            "h_patch_head": h_head,
            "branch": "main",
            "remote_head": h_head,
            "scope": expected_scope,
        },
        "h_patch": {
            "gate": "H-E0-MID",
            "component_count": 6,
            "added_count": 5,
            "modified_count": 1,
            "components": components,
            "components_sha256": mcal._digest_records(components),
        },
        "base_authority": _base_p_mic_authority(repo_root=repo_root),
        "failed_attempt": _deep_copy(FAILED_ATTEMPT),
        "manifest_dialect_contract": _deep_copy(MANIFEST_DIALECT_CONTRACT),
        "generic_manifest_findings_contract": _deep_copy(
            GENERIC_MANIFEST_FINDINGS_CONTRACT
        ),
        "r_output_contract": _deep_copy(R_OUTPUT_CONTRACT),
        "r_outputs_sha256": R_OUTPUTS_SHA256,
        "archived_r_identity_contract": _deep_copy(
            ARCHIVED_R_IDENTITY_CONTRACT
        ),
        "archived_r_identity_sha256": ARCHIVED_R_IDENTITY_SHA256,
        "historical_inputs": historical,
        "historical_inputs_sha256": mcal._digest_records(historical),
        "coordination_namespace": {
            "p_output_present_count": 0,
            "r_output_present_count": 0,
            "r_state": "absent",
            "temporary_present_count": 0,
            "coordination_present_count": 0,
            "guard_present": False,
            "predecessor_coordination_present_count": 0,
            "formal_e0_m_output_present_count": 0,
            "outcome_access_log_absent": True,
            "outcome_paths_opened": False,
        },
        "schema_preflight": preflight_closure_locked_evaluation_input_manifest_dialect_patch_schema(
            repo_root=repo_root
        ),
        "prelock": {
            "base_p_mic_output_present_count": 2,
            "p_output_present_count": 0,
            "r_output_present_count": 0,
            "component_count": 6,
            "physical_input_count": 16,
            "historical_input_count": 6,
            "companion_output_count": 1,
            "companion_contract": {
                "physical_input_count": 16,
                "historical_input_count": 6,
                "output_count": 1,
                "script_path": LOCKER_PATH.as_posix(),
                "manifest_written_last": True,
            },
            "archived_r_preserved": True,
            "archived_r_count": 10,
            "archive_identity_verified": True,
            "archive_identity_sha256": ARCHIVED_R_IDENTITY_SHA256,
            "archive_parent_walk_no_follow": True,
            "archive_metadata_inspected": True,
            "archive_bytes_opened": False,
            "scientific_execution_run": False,
            "r_files_touched": False,
            "r_files_staged": False,
            "dvc_commands_run": False,
            "outcome_paths_opened": False,
        },
    }


def _repository_status_map(repo_root: Path) -> dict[str, str]:
    records = mcal._workspace_status_records(repo_root)
    observed: dict[str, str] = {}
    for code, path in records:
        if path in observed:
            raise _error("workspace contains a duplicate path")
        observed[path] = code
    return observed


def _validate_unpublished_p_repository(
    *, h_head: str, verify_remote: bool, repo_root: Path
) -> str:
    if (
        cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
        != "main"
        or _git_head(repo_root) != h_head
        or mcal._single_parent(repo_root, h_head, context="H-E0-MID")
        != BASE_P_MIC_COMMIT
        or mcal._git_scope(repo_root, BASE_P_MIC_COMMIT, h_head)
        != {
            "added": 5,
            "modified": 1,
            "deleted": 0,
            "path_count": 6,
            "paths": list(PATCH_PATHS),
        }
    ):
        raise _error("unpublished P requires exact published H topology")
    tracking = _git_head(repo_root, "origin/main")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != h_head or remote != h_head:
        raise _error("unpublished P refs drifted")
    observed = _repository_status_map(repo_root)
    untracked = {path.as_posix(): "??" for path in CURRENT_LOCK_PATHS}
    staged = {path.as_posix(): "A " for path in CURRENT_LOCK_PATHS}
    if observed == untracked:
        return "untracked"
    if observed == staged:
        return "staged"
    raise _error("unpublished P workspace is not exact2")


def _p_pair_snapshot(repo_root: Path) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for path in CURRENT_LOCK_PATHS:
        _value, payload, metadata = _parse_canonical_json(path, repo_root=repo_root)
        records.append(
            {
                "path": path.as_posix(),
                "bytes": len(payload),
                "sha256": _sha256_bytes(payload),
                "device": int(metadata.st_dev),
                "inode": int(metadata.st_ino),
                "mode": stat.S_IMODE(metadata.st_mode),
                "nlink": int(metadata.st_nlink),
                "mtime_ns": int(metadata.st_mtime_ns),
                "ctime_ns": int(metadata.st_ctime_ns),
            }
        )
    return tuple(records)


def validate_closure_locked_evaluation_input_manifest_dialect_patch_unpublished_lock_bundle(
    *, repo_root: Path | None = None, verify_remote: bool = True
) -> dict[str, Any]:
    root = _root(repo_root)
    archive_before = _r_archive_metadata_snapshot(root)
    lock, lock_bytes, lock_metadata = _parse_canonical_json(
        DEFAULT_PATCH_LOCK_PATH, repo_root=root
    )
    repository = lock.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("unpublished P H binding is absent")
    h_head = cast(str, repository["h_patch_head"])
    stage_state = _validate_unpublished_p_repository(
        h_head=h_head, verify_remote=verify_remote, repo_root=root
    )
    _validate_published_lock_payload(lock, h_head=h_head, repo_root=root)
    lock_record = {
        "role": "locked_evaluation_input_manifest_dialect_patch_lock",
        "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "bytes": len(lock_bytes),
        "sha256": _sha256_bytes(lock_bytes),
    }
    companion, companion_bytes, companion_metadata = _parse_canonical_json(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
    )
    if _canonical_json_bytes(companion) != _canonical_json_bytes(
        _expected_companion(lock, lock_record)
    ):
        raise _error("unpublished P companion drifted")
    snapshot = _physical_snapshot(root)
    p_snapshot = _p_pair_snapshot(root)
    if _namespace_state(repo_root=root, p_present=True, r_present=False)[
        "coordination_present_count"
    ] != 0:
        raise _error("unpublished P coordination namespace drifted")
    recaptured_lock, recaptured_lock_bytes, recaptured_lock_metadata = (
        _parse_canonical_json(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    )
    recaptured_companion, recaptured_companion_bytes, recaptured_companion_metadata = (
        _parse_canonical_json(DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root)
    )
    identity = mic.mcalm.mcall.mcalk.mcalj._metadata_identity
    if (
        recaptured_lock != lock
        or recaptured_companion != companion
        or recaptured_lock_bytes != lock_bytes
        or recaptured_companion_bytes != companion_bytes
        or identity(recaptured_lock_metadata) != identity(lock_metadata)
        or identity(recaptured_companion_metadata) != identity(companion_metadata)
        or _p_pair_snapshot(root) != p_snapshot
        or _r_archive_metadata_snapshot(root) != archive_before
    ):
        raise _error("unpublished P changed during validation")
    _require_physical_snapshot(snapshot, repo_root=root, context="during P validation")
    if _validate_unpublished_p_repository(
        h_head=h_head, verify_remote=verify_remote, repo_root=root
    ) != stage_state:
        raise _error("unpublished P stage state changed")
    return {
        "gate": PATCH_GATE,
        "status": "locked_unpublished",
        "h_patch_head": h_head,
        "p_stage_state": stage_state,
        "p_output_count": 2,
        "physical_input_count": 16,
        "historical_input_count": 6,
        "companion_output_count": 1,
        "coordination_present_count": 0,
        "r_state": "absent",
        "r_adoption_authorized": False,
        "effective_authority": False,
        "scientific_rerun_authorized": False,
        "dvc_commands_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
        "outcome_access_authorized": False,
        "writes_performed": False,
    }


def _require_repository_checkpoint(
    *,
    repo_root: Path,
    expected_head: str,
    verify_remote: bool,
    p_outputs_present: bool,
    context: str,
) -> None:
    expected = (
        {path.as_posix(): "??" for path in CURRENT_LOCK_PATHS}
        if p_outputs_present
        else {}
    )
    if (
        cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
        != "main"
        or _git_head(repo_root) != expected_head
        or _git_head(repo_root, "origin/main") != expected_head
        or _repository_status_map(repo_root) != expected
    ):
        raise _error(f"repository changed {context}")
    if verify_remote and mcal._live_remote_main_head(repo_root) != expected_head:
        raise _error(f"live remote changed {context}")


def publish_closure_locked_evaluation_input_manifest_dialect_patch_lock_bundle(
    payload: Mapping[str, Any], *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _root(repo_root)
    frozen = cast(dict[str, Any], _deep_copy(payload))
    repository = frozen.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("publication H binding is absent")
    h_head = cast(str, repository["h_patch_head"])
    if _git_head(root) != h_head or h_head == BASE_P_MIC_COMMIT:
        raise _error("publication requires published H")
    validate_closure_locked_evaluation_input_manifest_dialect_patch_lock_payload(
        frozen, verify_remote=True, repo_root=root
    )
    _require_publication_verification(frozen, repo_root=root)
    _require_repository_checkpoint(
        repo_root=root,
        expected_head=h_head,
        verify_remote=True,
        p_outputs_present=False,
        context="before publication",
    )
    _namespace_state(repo_root=root, p_present=False, r_present=False)
    archive_snapshot = _r_archive_metadata_snapshot(root)
    physical_snapshot = _physical_snapshot(root)
    published: list[Any] = []
    guard: Any | None = None
    committed = False
    try:
        guard = mt._acquire_publication_guard(
            LOCKER_GUARD_PATH,
            b"E0-MID input manifest dialect patch lock\n",
            repo_root=root,
        )
        _namespace_state(
            repo_root=root,
            p_present=False,
            r_present=False,
            owned_lock_guard=guard,
        )
        _require_physical_snapshot(
            physical_snapshot, repo_root=root, context="after publication guard"
        )
        if _r_archive_metadata_snapshot(root) != archive_snapshot:
            raise _error("R archive changed after publication guard")
        lock_bytes = _canonical_json_bytes(frozen)
        lock_output = mic.mcalm.mcall.mcalk._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_PATH, lock_bytes, repo_root=root
        )
        published.append(lock_output)
        lock_record = {
            "role": "locked_evaluation_input_manifest_dialect_patch_lock",
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "bytes": len(lock_bytes),
            "sha256": _sha256_bytes(lock_bytes),
        }
        companion = _expected_companion(frozen, lock_record)
        companion_bytes = _canonical_json_bytes(companion)
        companion_output = mic.mcalm.mcall.mcalk._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH, companion_bytes, repo_root=root
        )
        published.append(companion_output)
        publication = (
            (lock_output, lock_bytes),
            (companion_output, companion_bytes),
        )
        for output, expected in publication:
            mic.mcalm.mcall.mcalk.mcalj._validate_owned_output_bytes(
                output, expected, repo_root=root, context="after publication"
            )
        _namespace_state(
            repo_root=root,
            p_present=True,
            r_present=False,
            owned_lock_guard=guard,
        )
        _require_physical_snapshot(
            physical_snapshot, repo_root=root, context="after companion"
        )
        if _r_archive_metadata_snapshot(root) != archive_snapshot:
            raise _error("R archive changed during publication")
        _require_repository_checkpoint(
            repo_root=root,
            expected_head=h_head,
            verify_remote=True,
            p_outputs_present=True,
            context="during publication",
        )
        mt._release_publication_guard(guard)
        guard = None
        for pass_index in (1, 2):
            _namespace_state(
                repo_root=root, p_present=True, r_present=False
            )
            _require_physical_snapshot(
                physical_snapshot,
                repo_root=root,
                context=f"during transfer pass {pass_index}",
            )
            if _r_archive_metadata_snapshot(root) != archive_snapshot:
                raise _error("R archive changed during ownership transfer")
            _require_repository_checkpoint(
                repo_root=root,
                expected_head=h_head,
                verify_remote=True,
                p_outputs_present=True,
                context=f"during transfer pass {pass_index}",
            )
            for output, expected in publication:
                mic.mcalm.mcall.mcalk.mcalj._validate_owned_output_bytes(
                    output,
                    expected,
                    repo_root=root,
                    context=f"ownership transfer pass {pass_index}",
                )
        committed = True
        return dict(frozen), companion
    except BaseException as exc:
        rollback = mic.mcalm.mcall.mcalk._rollback_outputs_best_effort(published)
        if rollback is not None:
            exc.add_note(str(rollback))
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, ClosureLockedEvaluationInputManifestDialectPatchError):
            raise
        raise _error("lock bundle publication failed") from exc
    finally:
        if guard is not None:
            try:
                mt._release_publication_guard(guard, tolerate_foreign=True)
            except Exception:
                pass
        if committed:
            for output in reversed(published):
                try:
                    mic.mcalm.mcall.mcalk.mcalj._close_owned_output(output)
                except Exception:
                    pass


def _p_publication_state(
    *, h_head: str, verify_remote: bool, repo_root: Path
) -> dict[str, Any]:
    head = _git_head(repo_root)
    parent = mcal._single_parent(repo_root, head, context="P/R-E0-MID")
    p_scope = {
        "added": 2,
        "modified": 0,
        "deleted": 0,
        "path_count": 2,
        "paths": sorted(path.as_posix() for path in CURRENT_LOCK_PATHS),
    }
    r_scope = {
        "added": 6,
        "modified": 0,
        "deleted": 0,
        "path_count": 6,
        "paths": sorted(LOCKED_EVALUATION_INPUT_MANIFEST_DIALECT_R_STAGED_SCOPE),
    }
    if parent == h_head:
        p_head, r_head = head, None
        if mcal._git_scope(repo_root, h_head, p_head) != p_scope:
            raise _error("published P scope drifted")
    else:
        r_head, p_head = head, parent
        if (
            mcal._single_parent(repo_root, p_head, context="P-E0-MID") != h_head
            or mcal._git_scope(repo_root, h_head, p_head) != p_scope
            or mcal._git_scope(repo_root, p_head, r_head) != r_scope
        ):
            raise _error("published R topology drifted")
    if cast(str, mcal._git(repo_root, "branch", "--show-current")).strip() != "main":
        raise _error("effective authority requires main")
    tracking = _git_head(repo_root, "origin/main")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != head or remote != head:
        raise _error("effective refs drifted")
    for path in CURRENT_LOCK_PATHS:
        physical, _ = mcal._read_regular_bytes_and_metadata(
            path,
            repo_root=repo_root,
            expected_mode=0o644,
            require_nlink_one=True,
        )
        mode, _oid = mcal._git_mode_oid(repo_root, p_head, path)
        if mode != "100644" or physical != mcal._git_blob_bytes(repo_root, p_head, path):
            raise _error(f"published P binding drifted: {path}")
    r_present = all(
        mcal._entry_exists(Path(cast(str, record["path"])), repo_root=repo_root)
        for record in R_OUTPUT_CONTRACT
    )
    r_absent = not any(
        mcal._entry_exists(Path(cast(str, record["path"])), repo_root=repo_root)
        for record in R_OUTPUT_CONTRACT
    )
    if not (r_present or r_absent):
        raise _error("R namespace is partial")
    observed = _repository_status_map(repo_root)
    if r_head is not None:
        if not r_present or observed:
            raise _error("published R worktree drifted")
        for path in R_TRACKED_OUTPUT_PATHS:
            payload, _ = mcal._read_regular_bytes_and_metadata(
                path,
                repo_root=repo_root,
                expected_mode=0o644,
                require_nlink_one=True,
            )
            mode, _oid = mcal._git_mode_oid(repo_root, r_head, path)
            if mode != "100644" or payload != mcal._git_blob_bytes(repo_root, r_head, path):
                raise _error(f"published R Git binding drifted: {path}")
        r_stage_state = "published"
    elif r_absent:
        if observed:
            raise _error("published P clean workspace drifted")
        r_stage_state = "absent"
    else:
        untracked = {path.as_posix(): "??" for path in R_TRACKED_OUTPUT_PATHS}
        staged = {path.as_posix(): "A " for path in R_TRACKED_OUTPUT_PATHS}
        if observed == untracked:
            r_stage_state = "exact6_untracked"
        elif observed == staged:
            r_stage_state = "exact6_staged"
        else:
            raise _error("unpublished complete R workspace drifted")
    _namespace_state(
        repo_root=repo_root,
        p_present=True,
        r_present=r_present,
    )
    return {
        "h_patch_head": h_head,
        "p_patch_head": p_head,
        "r_patch_head": r_head,
        "remote_head": remote,
        "r_state": "complete" if r_present else "absent",
        "r_stage_state": r_stage_state,
    }


def load_effective_closure_locked_evaluation_input_manifest_dialect_patch_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    lock, lock_bytes, lock_metadata = _parse_canonical_json(
        DEFAULT_PATCH_LOCK_PATH, repo_root=root
    )
    repository = lock.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("published lock H binding is absent")
    h_head = cast(str, repository["h_patch_head"])
    _validate_published_lock_payload(lock, h_head=h_head, repo_root=root)
    lock_record = {
        "role": "locked_evaluation_input_manifest_dialect_patch_lock",
        "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "bytes": len(lock_bytes),
        "sha256": _sha256_bytes(lock_bytes),
    }
    companion, companion_bytes, companion_metadata = _parse_canonical_json(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
    )
    if _canonical_json_bytes(companion) != _canonical_json_bytes(
        _expected_companion(lock, lock_record)
    ):
        raise _error("published companion drifted")
    publication = _p_publication_state(
        h_head=h_head, verify_remote=verify_remote, repo_root=root
    )
    r_snapshot = (
        _r_bundle_snapshot(root)
        if publication["r_state"] == "complete"
        else None
    )
    p_snapshot = _p_pair_snapshot(root)
    physical_snapshot = _physical_snapshot(root)
    recaptured_lock, recaptured_lock_bytes, recaptured_lock_metadata = (
        _parse_canonical_json(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    )
    recaptured_companion, recaptured_companion_bytes, recaptured_companion_metadata = (
        _parse_canonical_json(DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root)
    )
    identity = mic.mcalm.mcall.mcalk.mcalj._metadata_identity
    if (
        recaptured_lock != lock
        or recaptured_companion != companion
        or recaptured_lock_bytes != lock_bytes
        or recaptured_companion_bytes != companion_bytes
        or identity(recaptured_lock_metadata) != identity(lock_metadata)
        or identity(recaptured_companion_metadata) != identity(companion_metadata)
        or _p_pair_snapshot(root) != p_snapshot
        or _p_publication_state(
            h_head=h_head, verify_remote=verify_remote, repo_root=root
        )
        != publication
    ):
        raise _error("effective authority changed during loading")
    _require_physical_snapshot(
        physical_snapshot, repo_root=root, context="during effective loading"
    )
    if r_snapshot is not None and _r_bundle_snapshot(root) != r_snapshot:
        raise _error("R bundle changed during effective authority loading")
    adoptable = (
        r_snapshot is not None
        and publication["r_stage_state"]
        in {"exact6_untracked", "exact6_staged"}
    )
    return {
        "gate": PATCH_GATE,
        "status": "effective",
        **publication,
        "lock": lock_record,
        "companion": {
            "role": "locked_evaluation_input_manifest_dialect_patch_lock_manifest",
            "path": DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
            "bytes": len(companion_bytes),
            "sha256": _sha256_bytes(companion_bytes),
        },
        "r_output_count": 10 if publication["r_state"] == "complete" else 0,
        "r_outputs_sha256": (
            R_OUTPUTS_SHA256 if publication["r_state"] == "complete" else None
        ),
        "r_adoption_gate": R_ADOPTION_GATE,
        "r_adoption_authorized": adoptable,
        "effective_authority": True,
        "scientific_rerun_authorized": False,
        "input_bundle_execution_authorized": False,
        "dvc_add_authorized": False,
        "dvc_push_authorized": False,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "target_access_authorized": False,
        "outcome_access_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
        "writes_performed": False,
    }


def require_closure_locked_evaluation_input_manifest_dialect_patch_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    authority = load_effective_closure_locked_evaluation_input_manifest_dialect_patch_authority(
        verify_remote=verify_remote, repo_root=repo_root
    )
    if authority.get("effective_authority") is not True:
        raise _error("effective authority is false")
    return authority


def _r_bundle_snapshot(repo_root: Path | None = None) -> tuple[dict[str, Any], ...]:
    root = _root(repo_root)
    records: list[dict[str, Any]] = []
    for expected in R_OUTPUT_CONTRACT:
        raw_path = cast(str, expected["path"])
        try:
            payload, metadata = mcal._read_regular_bytes_and_metadata(
                Path(raw_path),
                repo_root=root,
                expected_mode=cast(int, expected["mode"]),
                require_nlink_one=True,
            )
        except Exception as exc:
            raise _error(f"R output read failed: {raw_path}") from exc
        if len(payload) != expected["bytes"] or _sha256_bytes(payload) != expected["sha256"]:
            raise _error(f"R output bytes drifted: {raw_path}")
        records.append(
            {
                "path": raw_path,
                "device": int(metadata.st_dev),
                "inode": int(metadata.st_ino),
                "mode": stat.S_IMODE(metadata.st_mode),
                "nlink": int(metadata.st_nlink),
                "size": len(payload),
                "mtime_ns": int(metadata.st_mtime_ns),
                "ctime_ns": int(metadata.st_ctime_ns),
                "sha256": _sha256_bytes(payload),
            }
        )
    return tuple(records)


def _validate_r_science(*, repo_root: Path) -> dict[str, Any]:
    mic_lock, _bytes, _metadata = _parse_canonical_json(
        mic.DEFAULT_PATCH_LOCK_PATH, repo_root=repo_root
    )
    input_contract = mic_lock.get("input_contract")
    if not isinstance(input_contract, Mapping):
        raise _error("published P-MIC input contract is absent")
    with mic._patched_mib_contract(input_contract, repo_root=repo_root):
        materialization = mib._build_expected_r_materialization(
            {
                "input_contract": input_contract,
                "authority_binding_sha256": EXPECTED_MIC_AUTHORITY_BINDING_SHA256,
            },
            repo_root=repo_root,
        )
        before = mib._validate_r_bundle_semantics(
            repo_root=repo_root, pointers_required=True
        )
        mib._require_expected_r_materialization(before, materialization)
        after = mib._validate_r_bundle_semantics(
            repo_root=repo_root, pointers_required=True
        )
        mib._require_expected_r_materialization(after, materialization)
    if _canonical_json_bytes(before) != _canonical_json_bytes(after):
        raise _error("strict R semantics changed during validation")
    manifest = cast(Mapping[str, Any], before["manifest"])
    if (
        manifest.get("gate") != UNDERLYING_R_GATE
        or manifest.get("status") != "completed_unpublished"
        or manifest.get("authority_binding_sha256")
        != EXPECTED_MIC_AUTHORITY_BINDING_SHA256
        or before.get("r_outputs_sha256") != R_OUTPUTS_SHA256
    ):
        raise _error("strict R manifest authority/digest drifted")
    return before


def validate_locked_evaluation_input_manifest_dialect_adoption(
    *,
    repo_root: Path | None = None,
    require_staged: bool = True,
    verify_remote: bool = True,
) -> dict[str, Any]:
    if type(require_staged) is not bool or type(verify_remote) is not bool:
        raise _error("R adoption policies must be exact booleans")
    root = _root(repo_root)
    authority = require_closure_locked_evaluation_input_manifest_dialect_patch_authority(
        verify_remote=verify_remote, repo_root=root
    )
    expected_stage = "exact6_staged" if require_staged else "exact6_untracked"
    if (
        authority.get("r_adoption_authorized") is not True
        or authority.get("r_stage_state") != expected_stage
        or authority.get("r_adoption_gate") != R_ADOPTION_GATE
    ):
        raise _error(f"{R_ADOPTION_GATE} requires {expected_stage}")
    snapshot = _r_bundle_snapshot(root)
    semantics = _validate_r_science(repo_root=root)
    if _r_bundle_snapshot(root) != snapshot:
        raise _error("R physical identity changed during strict validation")
    if require_closure_locked_evaluation_input_manifest_dialect_patch_authority(
        verify_remote=verify_remote, repo_root=root
    ).get("r_stage_state") != expected_stage:
        raise _error("R stage state changed during strict validation")
    return {
        "gate": PATCH_GATE,
        "r_gate": R_ADOPTION_GATE,
        "underlying_r_gate": UNDERLYING_R_GATE,
        "status": "locked_evaluation_input_manifest_dialect_adoption_validated",
        "r_stage_state": expected_stage,
        "physical_output_count": 4,
        "tracked_output_count": 6,
        "pointer_count": 4,
        "summary_count": 1,
        "manifest_count": 1,
        "r_output_count": 10,
        "r_outputs_sha256": semantics["r_outputs_sha256"],
        "expected_non_ok_findings": _deep_copy(GENERIC_MANIFEST_FINDINGS_CONTRACT),
        "staged_scope_verified": require_staged,
        "input_only": True,
        "target_paths_opened": False,
        "target_availability_inspected": False,
        "outcome_paths_opened": False,
        "future_outcomes_accessed": False,
        "evaluation_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "writes_performed": False,
    }


validate_closure_locked_evaluation_input_manifest_dialect_adoption = (
    validate_locked_evaluation_input_manifest_dialect_adoption
)
