"""Seal the published final-calibration R8 authority under E0-MCALM.

R-E0-MCALL committed the immutable eight-file R8 bundle after the predecessor
loader had frozen a pre-publication workspace shape.  This additive overlay
validates the terminal R commit without reopening scientific inputs, then
publishes a new H/P authority for downstream formal E0-M preparation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, ParamSpec, TypeVar, cast

from src.experiments import (
    closure_final_calibration_r8_coordination_namespace_revalidation_patch as mcall,
)

mcal = mcall.mcal
mt = mcall.mt
mcalk = mcall.mcalk
mcalj = mcall.mcalj

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_R_MCALL_COMMIT = "09309c2d16820f5d93fe9fd38dadef92377fd005"
HISTORICAL_P_MCALL_COMMIT = "c798d2ec2041baa011237fd26fc7f55d7596f300"
HISTORICAL_H_MCALL_COMMIT = "fc82108e9f45a28ef1a0543d7fae956ca642aca3"
BASE_P_MCALL_COMMIT = HISTORICAL_P_MCALL_COMMIT
H_MCALL_PARENT = "6f078da52c5dd699ea312df209bfef5a8d120d00"
PATCH_GATE = "E0-MCALM"
FINAL_CALIBRATION_GATE = PATCH_GATE
EXPERIMENT_ID = "closure_v1"
LOCK_SCHEMA_VERSION = (
    "closure_final_calibration_r8_post_publication_authority_patch_lock_v1"
)
COMPANION_SCHEMA_VERSION = (
    "closure_final_calibration_r8_post_publication_authority_patch_lock_manifest_v1"
)

DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/"
    "final_calibration_r8_post_publication_authority_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "final_calibration_r8_post_publication_authority_patch_lock.json"
)
DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "final_calibration_r8_post_publication_authority_patch_lock_manifest.json"
)
DEFAULT_PATCH_MANIFEST_PATH = DEFAULT_PATCH_LOCK_MANIFEST_PATH
LOCKER_PATH = Path(
    "src/experiments/"
    "lock_closure_final_calibration_r8_post_publication_authority_patch.py"
)
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_e0_mcalm/"
    "final_calibration_r8_post_publication_authority_patch_lock.guard"
)

PRECOMMIT_PATH = "src/data/prepare_commit_artifacts.py"
CORE_PATH = (
    "src/experiments/"
    "closure_final_calibration_r8_post_publication_authority_patch.py"
)
TEST_PATH = (
    "tests/test_closure_final_calibration_r8_post_publication_authority_patch.py"
)
DOCUMENTATION_PATH = (
    "docs/closure_v1/"
    "E0_M_FINAL_CALIBRATION_R8_POST_PUBLICATION_AUTHORITY_PATCH_1.md"
)
PATCH_PATHS = tuple(
    sorted(
        {
            DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
            DOCUMENTATION_PATH,
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
FINAL_CALIBRATION_H_STAGED_SCOPE = {
    path: ("M" if path == PRECOMMIT_PATH else "A") for path in PATCH_PATHS
}
FINAL_CALIBRATION_P_STAGED_SCOPE = {
    DEFAULT_PATCH_LOCK_PATH.as_posix(): "A",
    DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(): "A",
}
P_PATCH_PATHS = tuple(sorted(FINAL_CALIBRATION_P_STAGED_SCOPE))
P_MCALL_PATHS = tuple(path.as_posix() for path in mcall.CURRENT_LOCK_PATHS)
H_MCALL_PATHS = tuple(mcall.PATCH_PATHS)
R_OUTPUT_PATHS = tuple(mcall.R_OUTPUT_PATHS)
R8_OUTPUT_CONTRACT = tuple(mcall.R8_OUTPUT_CONTRACT)
R8_STAGED_SCOPE = {path.as_posix(): "A" for path in R_OUTPUT_PATHS}
FINAL_CALIBRATION_R_STAGED_SCOPE = dict(R8_STAGED_SCOPE)
GENERIC_MANIFEST_FINDINGS_CONTRACT = tuple(
    mcall.GENERIC_MANIFEST_FINDINGS_CONTRACT
)
MANIFEST_REPRODUCIBILITY_CONTRACT = dict(
    mcall.MANIFEST_REPRODUCIBILITY_CONTRACT
)

E0_M_OUTPUT_PATHS = (
    Path("reports/closure_v1/00_protocol/model_lock.yaml"),
    Path("reports/closure_v1/00_protocol/calibration_lock.yaml"),
    Path("reports/closure_v1/00_protocol/hypothesis_registry.csv"),
    Path("reports/closure_v1/00_protocol/locked_batch_command.txt"),
)
OUTCOME_ACCESS_LOG_PATH = Path(
    "reports/closure_v1/00_protocol/outcome_access_log.jsonl"
)

EXPECTED_COMPANION_INPUT_COUNT = 16
EXPECTED_HISTORICAL_INPUT_COUNT = 6
EXPECTED_COMPANION_OUTPUT_COUNT = 1

TYPE_CHECK_COMMAND = mcall.TYPE_CHECK_COMMAND
FOCUSED_TEST_COMMAND = (
    "poetry",
    "run",
    "pytest",
    "-q",
    "tests/test_prepare_commit_artifacts.py",
    TEST_PATH,
)
FOCUSED_TEST_COUNT = 48
POETRY_CHECK_COMMAND = mcall.POETRY_CHECK_COMMAND
PUBLICATION_GUARD_COMMAND = mcall.PUBLICATION_GUARD_COMMAND
DIFF_CHECK_COMMAND = mcall.DIFF_CHECK_COMMAND
UNPUBLISHED_AUTHORIZATIONS = {
    **mcall.UNPUBLISHED_AUTHORIZATIONS,
    "r8_staging_authorized": False,
    "e0_m_authorized": False,
    "outcome_access_authorized": False,
}

HISTORICAL_PUBLISHED_LOCK_PATHS = tuple(
    sorted(
        (*mcall.HISTORICAL_PUBLISHED_LOCK_PATHS, *mcall.CURRENT_LOCK_PATHS),
        key=lambda path: path.as_posix(),
    )
)
NEVER_PUBLISHED_LOCK_PATHS = tuple(mcall.NEVER_PUBLISHED_LOCK_PATHS)
CURRENT_LOCK_PATHS = tuple(
    sorted(
        (DEFAULT_PATCH_LOCK_PATH, DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        key=lambda path: path.as_posix(),
    )
)
_LOCK_MODULES = (*mcall._LOCK_MODULES, mcall)
LOCK_TEMPORARY_PATHS = tuple(
    sorted(
        [
            mcal._temporary_path(path)
            for module in _LOCK_MODULES
            for path in (
                module.DEFAULT_PATCH_LOCK_PATH,
                module.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            )
        ]
        + [
            mcal._temporary_path(DEFAULT_PATCH_LOCK_PATH),
            mcal._temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        ],
        key=lambda path: path.as_posix(),
    )
)
LOCKER_GUARD_PATHS = tuple(
    sorted(
        [module.LOCKER_GUARD_PATH for module in _LOCK_MODULES]
        + [LOCKER_GUARD_PATH],
        key=lambda path: path.as_posix(),
    )
)
R8_TEMPORARY_PATHS = tuple(mcall.R8_TEMPORARY_PATHS)
SCIENTIFIC_RUN_GUARD_PATHS = tuple(mcall.SCIENTIFIC_RUN_GUARD_PATHS)
COORDINATION_NAMESPACE_PATHS = tuple(
    sorted(
        (
            *LOCK_TEMPORARY_PATHS,
            *LOCKER_GUARD_PATHS,
            *R8_TEMPORARY_PATHS,
            *SCIENTIFIC_RUN_GUARD_PATHS,
        ),
        key=lambda path: path.as_posix(),
    )
)
COORDINATION_NAMESPACE_CONTRACT = {
    "historical_published_lock_count": 20,
    "historical_published_lock_paths": [
        path.as_posix() for path in HISTORICAL_PUBLISHED_LOCK_PATHS
    ],
    "never_published_lock_count": 4,
    "never_published_lock_paths": [
        path.as_posix() for path in NEVER_PUBLISHED_LOCK_PATHS
    ],
    "current_lock_count": 2,
    "current_lock_paths": [path.as_posix() for path in CURRENT_LOCK_PATHS],
    "lock_temporary_count": 26,
    "lock_temporary_paths": [path.as_posix() for path in LOCK_TEMPORARY_PATHS],
    "locker_guard_count": 13,
    "locker_guard_paths": [path.as_posix() for path in LOCKER_GUARD_PATHS],
    "r8_temporary_count": 8,
    "r8_temporary_paths": [path.as_posix() for path in R8_TEMPORARY_PATHS],
    "scientific_run_guard_count": 2,
    "scientific_run_guard_paths": [
        path.as_posix() for path in SCIENTIFIC_RUN_GUARD_PATHS
    ],
    "coordination_forbidden_count": 49,
    "terminal_r_commit": BASE_R_MCALL_COMMIT,
    "terminal_r_clean_loader_required": True,
    "post_release_revalidation_required": True,
    "effective_loader_revalidation_required": True,
}


class FinalCalibrationR8PostPublicationAuthorityPatchError(
    mcall.FinalCalibrationR8CoordinationNamespaceRevalidationPatchError
):
    """Raised when E0-MCALM post-publication authority drifts."""


FinalCalibrationError = mcall.FinalCalibrationError
P = ParamSpec("P")
R = TypeVar("R")


def _error(message: str) -> FinalCalibrationR8PostPublicationAuthorityPatchError:
    return FinalCalibrationR8PostPublicationAuthorityPatchError(message)


def _translate_predecessor_error(message: str) -> str:
    for prefix in (
        "E0-MCALL",
        "E0-MCALK",
        "E0-MCALJ",
        "E0-MCALI",
        "E0-MCALH",
        "E0-MCALG",
        "E0-MCALF",
        "E0-MCALE",
        "E0-MCALD",
        "E0-MCALC",
        "E0-MCALP",
        "E0-MCAL",
    ):
        if message == prefix or message.startswith(prefix + " "):
            return PATCH_GATE + message[len(prefix) :]
    return f"{PATCH_GATE} predecessor error: {message}"


def _error_boundary(function: Callable[P, R]) -> Callable[P, R]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return function(*args, **kwargs)
        except FinalCalibrationR8PostPublicationAuthorityPatchError:
            raise
        except mcall.FinalCalibrationError as exc:
            raise _error(_translate_predecessor_error(str(exc))) from exc

    return wrapped


def _root(repo_root: Path | None = None) -> Path:
    return PROJECT_ROOT if repo_root is None else Path(repo_root).resolve()


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _deep_copy(value: Any) -> Any:
    return json.loads(_canonical_json_bytes(value))


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _path_exists(path: Path, *, repo_root: Path) -> bool:
    return mcal._entry_exists(path, repo_root=repo_root)


def _git_record_at_commit(
    path: str, *, role: str, commit: str, repo_root: Path
) -> dict[str, Any]:
    relative = Path(path)
    mode, oid = mcal._git_mode_oid(repo_root, commit, relative)
    payload = mcal._git_blob_bytes(repo_root, commit, relative)
    if mode not in {"100644", "100755"}:
        raise _error(f"E0-MCALM historical Git mode drifted: {path}")
    return {
        "role": role,
        "path": path,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "git_oid": oid,
        "git_mode": mode,
    }


def _historical_p_mcall_git_authority(*, repo_root: Path) -> dict[str, Any]:
    """Validate P-E0-MCALL without invoking its obsolete workspace loader."""

    p_commit = HISTORICAL_P_MCALL_COMMIT
    h_commit = mcal._single_parent(repo_root, p_commit, context="P-E0-MCALL")
    h_parent = mcal._single_parent(repo_root, h_commit, context="H-E0-MCALL")
    expected_h_scope = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(H_MCALL_PATHS),
    }
    expected_p_scope = {
        "added": 2,
        "modified": 0,
        "deleted": 0,
        "path_count": 2,
        "paths": sorted(P_MCALL_PATHS),
    }
    if (
        h_commit != HISTORICAL_H_MCALL_COMMIT
        or h_parent != H_MCALL_PARENT
        or mcal._git_scope(repo_root, h_parent, h_commit) != expected_h_scope
        or mcal._git_scope(repo_root, h_commit, p_commit) != expected_p_scope
    ):
        raise _error("E0-MCALM historical P-E0-MCALL topology drifted")

    records: list[dict[str, Any]] = []
    for path_text in P_MCALL_PATHS:
        role = (
            "published_p_mcall_lock"
            if path_text == mcall.DEFAULT_PATCH_LOCK_PATH.as_posix()
            else "published_p_mcall_lock_manifest"
        )
        record = _git_record_at_commit(
            path_text, role=role, commit=p_commit, repo_root=repo_root
        )
        physical = mcal._git_artifact_record(
            Path(path_text),
            role=role,
            repo_root=repo_root,
            commit=p_commit,
            expected_mode="100644",
        )
        if record != physical:
            raise _error(
                f"E0-MCALM historical P-E0-MCALL binding drifted: {path_text}"
            )
        records.append(record)

    lock_bytes = mcal._git_blob_bytes(
        repo_root, p_commit, mcall.DEFAULT_PATCH_LOCK_PATH
    )
    companion_bytes = mcal._git_blob_bytes(
        repo_root, p_commit, mcall.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    )
    lock = mcal._parse_json_bytes(lock_bytes, context="historical P-E0-MCALL lock")
    companion = mcal._parse_json_bytes(
        companion_bytes, context="historical P-E0-MCALL companion"
    )
    if (
        not isinstance(lock, Mapping)
        or not isinstance(companion, Mapping)
        or lock_bytes != mcall._canonical_json_bytes(lock)
        or companion_bytes != mcall._canonical_json_bytes(companion)
        or lock.get("gate") != mcall.PATCH_GATE
        or lock.get("schema_version") != mcall.LOCK_SCHEMA_VERSION
        or cast(Mapping[str, Any], lock.get("repository", {})).get(
            "h_patch_head"
        )
        != h_commit
    ):
        raise _error("E0-MCALM historical P-E0-MCALL canonical payload drifted")
    schema = mcal._load_json_object(mcall.DEFAULT_PATCH_LOCK_SCHEMA, repo_root=repo_root)
    try:
        mcal.validate_json_schema(lock, schema)
    except mcal.ClosureContractError as exc:
        raise _error("E0-MCALM historical P-E0-MCALL schema drifted") from exc
    mcall._validate_timestamp(lock.get("generated_at_utc"))
    mcall._validate_verification(lock.get("verification"), repo_root=repo_root)
    if lock.get("authorizations") != mcall.UNPUBLISHED_AUTHORIZATIONS:
        raise _error("E0-MCALM historical P-E0-MCALL authorizations drifted")
    lock_record = {
        "role": "final_calibration_r8_coordination_namespace_revalidation_patch_lock",
        "path": mcall.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "bytes": len(lock_bytes),
        "sha256": _sha256_bytes(lock_bytes),
    }
    if companion_bytes != mcall._canonical_json_bytes(
        mcall._expected_companion(lock, lock_record)
    ):
        raise _error("E0-MCALM historical P-E0-MCALL companion drifted")
    return {
        "gate": "P-E0-MCALL",
        "commit": p_commit,
        "parent_h_mcall": h_commit,
        "h_mcall_parent": h_parent,
        "h_scope": expected_h_scope,
        "p_scope": expected_p_scope,
        "p_component_count": 2,
        "p_components": records,
        "p_components_sha256": mcal._digest_records(records),
        "lock_payload_sha256": _sha256_bytes(lock_bytes),
        "companion_sha256": _sha256_bytes(companion_bytes),
        "manifest_written_last": companion.get("manifest_written_last") is True,
        "historical_scientific_inputs_rehashed": False,
        "science_payloads_opened": False,
    }


def _validate_r8_bundle_post_publication(*, repo_root: Path) -> dict[str, Any]:
    """Validate exact8 against the R commit and the science-free R8 parser."""

    if (
        mcal._single_parent(repo_root, BASE_R_MCALL_COMMIT, context="R-E0-MCALL")
        != HISTORICAL_P_MCALL_COMMIT
        or mcal._git_scope(
            repo_root, HISTORICAL_P_MCALL_COMMIT, BASE_R_MCALL_COMMIT
        )
        != {
            "added": 8,
            "modified": 0,
            "deleted": 0,
            "path_count": 8,
            "paths": sorted(path.as_posix() for path in R_OUTPUT_PATHS),
        }
    ):
        raise _error("E0-MCALM terminal R-E0-MCALL topology drifted")
    records: list[dict[str, Any]] = []
    for expected in R8_OUTPUT_CONTRACT:
        path_text = cast(str, expected["path"])
        path = Path(path_text)
        mode, oid = mcal._git_mode_oid(repo_root, BASE_R_MCALL_COMMIT, path)
        git_payload = mcal._git_blob_bytes(repo_root, BASE_R_MCALL_COMMIT, path)
        physical, metadata = mcal._read_regular_bytes_and_metadata(
            path,
            repo_root=repo_root,
            expected_mode=0o644,
            require_nlink_one=True,
        )
        observed = {
            "path": path_text,
            "bytes": len(physical),
            "sha256": _sha256_bytes(physical),
        }
        if (
            mode != "100644"
            or physical != git_payload
            or observed != expected
            or not stat.S_ISREG(metadata.st_mode)
        ):
            raise _error(f"E0-MCALM published R8 binding drifted: {path_text}")
        records.append({**observed, "git_mode": mode, "git_oid": oid})
    semantic = mcall._validate_r8_bundle_science_free(repo_root=repo_root)
    if semantic.get("r8_outputs") != [dict(record) for record in R8_OUTPUT_CONTRACT]:
        raise _error("E0-MCALM R8 semantic output set drifted")
    return {
        **semantic,
        "gate": PATCH_GATE,
        "status": "published_r8_authority_validated",
        "r_commit": BASE_R_MCALL_COMMIT,
        "r_parent_p_mcall": HISTORICAL_P_MCALL_COMMIT,
        "r8_published": True,
        "r8_staging_authorized": False,
        "r8_git_records": records,
        "r8_git_records_sha256": mcal._digest_records(records),
        "scientific_inputs_rehashed": False,
        "outcome_paths_opened": False,
    }


def _terminal_r_mcall_authority(*, repo_root: Path) -> dict[str, Any]:
    predecessor = _historical_p_mcall_git_authority(repo_root=repo_root)
    r8 = _validate_r8_bundle_post_publication(repo_root=repo_root)
    return {
        "gate": "R-E0-MCALL",
        "status": "published_terminal_r_validated",
        "r_commit": BASE_R_MCALL_COMMIT,
        "p_mcall_commit": HISTORICAL_P_MCALL_COMMIT,
        "h_mcall_commit": HISTORICAL_H_MCALL_COMMIT,
        "p_mcall_authority_sha256": _sha256_bytes(
            _canonical_json_bytes(predecessor)
        ),
        "r8_outputs_sha256": r8["r8_outputs_sha256"],
        "r8_git_records_sha256": r8["r8_git_records_sha256"],
        "r8_output_count": 8,
        "workspace_shape": "terminal_r_committed_clean",
        "scientific_inputs_rehashed": False,
        "outcome_paths_opened": False,
    }


def _historical_h_mcall_authority(*, repo_root: Path) -> dict[str, Any]:
    if (
        mcal._single_parent(
            repo_root, HISTORICAL_H_MCALL_COMMIT, context="H-E0-MCALL"
        )
        != H_MCALL_PARENT
    ):
        raise _error("E0-MCALM historical H-E0-MCALL parent drifted")
    scope = mcal._git_scope(repo_root, H_MCALL_PARENT, HISTORICAL_H_MCALL_COMMIT)
    expected = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(H_MCALL_PATHS),
    }
    if scope != expected:
        raise _error("E0-MCALM historical H-E0-MCALL scope drifted")
    records = [
        {
            **_git_record_at_commit(
                path,
                role="superseded_h_mcall_component",
                commit=HISTORICAL_H_MCALL_COMMIT,
                repo_root=repo_root,
            ),
            "commit": HISTORICAL_H_MCALL_COMMIT,
        }
        for path in H_MCALL_PATHS
    ]
    return {
        "gate": "H-E0-MCALL",
        "commit": HISTORICAL_H_MCALL_COMMIT,
        "parent": H_MCALL_PARENT,
        "scope": scope,
        "component_count": 6,
        "components": records,
        "components_sha256": mcal._digest_records(records),
        "historical_scientific_inputs_rehashed": False,
    }


def _require_coordination_namespace(
    *,
    repo_root: Path,
    current_outputs_state: str,
    owned_guard: Any | None = None,
) -> dict[str, Any]:
    if current_outputs_state not in {"absent", "present"}:
        raise _error("E0-MCALM current output policy drifted")
    predecessor_namespace = mcall._require_coordination_namespace(
        repo_root=repo_root, current_outputs_state="present"
    )
    predecessor = _historical_p_mcall_git_authority(repo_root=repo_root)
    current_present = [
        path.as_posix()
        for path in CURRENT_LOCK_PATHS
        if _path_exists(path, repo_root=repo_root)
    ]
    expected_current = (
        []
        if current_outputs_state == "absent"
        else [path.as_posix() for path in CURRENT_LOCK_PATHS]
    )
    if current_present != expected_current:
        raise _error("E0-MCALM current lock bundle state drifted")
    if current_outputs_state == "present":
        for path in CURRENT_LOCK_PATHS:
            mcal._read_regular_bytes_and_metadata(
                path,
                repo_root=repo_root,
                expected_mode=0o644,
                require_nlink_one=True,
            )
    allowed_guard: Path | None = None
    if owned_guard is not None:
        mcall.mcalk.mcalj._require_owned_guard_identity(owned_guard)
        allowed_guard = LOCKER_GUARD_PATH
    occupied = [
        path.as_posix()
        for path in COORDINATION_NAMESPACE_PATHS
        if path != allowed_guard
        if _path_exists(path, repo_root=repo_root)
    ]
    if occupied:
        raise _error(f"E0-MCALM coordination namespace is occupied: {occupied}")
    if _path_exists(OUTCOME_ACCESS_LOG_PATH, repo_root=repo_root):
        raise _error("E0-MCALM outcome access log must remain absent")
    e0_m_present = [
        path.as_posix()
        for path in E0_M_OUTPUT_PATHS
        if _path_exists(path, repo_root=repo_root)
    ]
    if e0_m_present:
        raise _error(f"E0-MCALM formal E0-M outputs appeared: {e0_m_present}")
    historical = [
        dict(record)
        for record in cast(
            Sequence[Mapping[str, Any]],
            predecessor_namespace["historical_published_locks"],
        )
    ]
    historical.extend(
        dict(record)
        for record in cast(
            Sequence[Mapping[str, Any]], predecessor["p_components"]
        )
    )
    historical.sort(key=lambda record: cast(str, record["path"]))
    if (
        len(historical) != 20
        or len({record["path"] for record in historical}) != 20
    ):
        raise _error("E0-MCALM historical published lock set drifted")
    return {
        "historical_published_lock_count": 20,
        "historical_published_locks": historical,
        "historical_published_locks_sha256": mcal._digest_records(historical),
        "never_published_lock_present_count": 0,
        "current_lock_present_count": len(current_present),
        "coordination_present_count": 0,
        "coordination_forbidden_count": 49,
        "owned_current_guard_present": owned_guard is not None,
        "formal_e0_m_output_present_count": 0,
        "outcome_access_log_absent": True,
    }


def _candidate_status_is_exact(repo_root: Path) -> bool:
    records = mcal._workspace_status_records(repo_root)
    if {path for _, path in records} != set(PATCH_PATHS):
        return False
    by_path = {path: code for code, path in records}
    for path in PATCH_PATHS:
        allowed = {" M", "M ", "MM"} if path == PRECOMMIT_PATH else {"??", "A "}
        if by_path[path] not in allowed:
            return False
    return True


def _h_patch_authority(
    *, repo_root: Path, verify_remote: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    if type(verify_remote) is not bool:
        raise _error("E0-MCALM remote policy must be exact boolean")
    head = mcal._git_head(repo_root)
    branch = cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
    if branch != "main":
        raise _error("E0-MCALM requires branch main")
    expected_scope = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(PATCH_PATHS),
    }
    candidate = head == BASE_R_MCALL_COMMIT
    if candidate:
        if not _candidate_status_is_exact(repo_root):
            raise _error("E0-MCALM candidate workspace is not exact 1M+5A")
        component_commit: str | None = None
        h_head = BASE_R_MCALL_COMMIT
        scope = expected_scope
    else:
        if (
            mcal._single_parent(repo_root, head, context="H-E0-MCALM")
            != BASE_R_MCALL_COMMIT
            or mcal._git_scope(repo_root, BASE_R_MCALL_COMMIT, head)
            != expected_scope
            or mcal._workspace_status_records(repo_root)
        ):
            raise _error("E0-MCALM published H topology/worktree drifted")
        component_commit = head
        h_head = head
        scope = expected_scope
    components = [
        mcal._git_artifact_record(
            Path(path),
            role="final_calibration_r8_post_publication_authority_patch_component",
            repo_root=repo_root,
            commit=component_commit,
            expected_mode=PATCH_COMPONENT_GIT_MODES[path],
        )
        for path in PATCH_PATHS
    ]
    tracking = mcal._git_head(repo_root, "origin/main")
    expected_ref = BASE_R_MCALL_COMMIT if candidate else head
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != expected_ref or remote != expected_ref:
        raise _error("E0-MCALM H refs drifted")
    return (
        {
            "base_r_mcall_commit": BASE_R_MCALL_COMMIT,
            "historical_p_mcall_commit": HISTORICAL_P_MCALL_COMMIT,
            "h_patch_head": h_head,
            "branch": branch,
            "remote_head": remote,
            "scope": scope,
        },
        {
            "gate": "H-E0-MCALM",
            "component_count": 6,
            "added_count": 5,
            "modified_count": 1,
            "components": components,
            "components_sha256": mcal._digest_records(components),
        },
    )


@_error_boundary
def preflight_final_calibration_r8_post_publication_authority_patch_schema(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    validator = getattr(mcal.closure_contract, "_assert_supported_json_schema", None)
    if validator is None:
        raise _error("E0-MCALM closed schema preflight is unavailable")
    try:
        validator(schema)
    except mcal.ClosureContractError as exc:
        raise _error(_translate_predecessor_error(str(exc))) from exc
    return {
        "status": "schema_ready",
        "gate": PATCH_GATE,
        "schema_count": 1,
        "schemas": [
            mcal._file_record(
                DEFAULT_PATCH_LOCK_SCHEMA,
                role="final_calibration_r8_post_publication_authority_patch_lock_schema",
                repo_root=root,
            )
        ],
        "supported_subset_verified": True,
    }


def _state_for_h(
    *,
    repository: Mapping[str, Any],
    h_patch: Mapping[str, Any],
    repo_root: Path,
    require_prelock_namespace: bool,
) -> dict[str, Any]:
    schema = preflight_final_calibration_r8_post_publication_authority_patch_schema(
        repo_root=repo_root
    )
    terminal = _terminal_r_mcall_authority(repo_root=repo_root)
    predecessor = _historical_p_mcall_git_authority(repo_root=repo_root)
    historical_h = _historical_h_mcall_authority(repo_root=repo_root)
    r8 = _validate_r8_bundle_post_publication(repo_root=repo_root)
    namespace = _require_coordination_namespace(
        repo_root=repo_root,
        current_outputs_state="absent" if require_prelock_namespace else "present",
    )
    if not require_prelock_namespace:
        namespace = {**namespace, "current_lock_present_count": 0}
    historical = cast(Sequence[Mapping[str, Any]], historical_h["components"])
    return {
        "repository": _deep_copy(repository),
        "terminal_r_mcall_authority": terminal,
        "p_mcall_authority": predecessor,
        "historical_h_mcall_authority": historical_h,
        "h_patch": _deep_copy(h_patch),
        "coordination_namespace_contract": _deep_copy(
            COORDINATION_NAMESPACE_CONTRACT
        ),
        "coordination_namespace": namespace,
        "historical_inputs": _deep_copy(historical),
        "historical_inputs_sha256": mcal._digest_records(historical),
        "r8_bundle": r8,
        "formal_e0_m_boundary": {
            "e0_m_output_count": 0,
            "outcome_access_log_state": "absent",
            "outcome_access_log_required_e0_m_state": "present_empty",
            "formal_e0_m_entrypoint_present": False,
            "formal_e0_m_execution_authorized": False,
            "e0_u_authorized": False,
            "holdout_access_authorized": False,
            "post_2021_access_authorized": False,
            "outcome_access_authorized": False,
        },
        "prelock": {
            "terminal_r_commit": BASE_R_MCALL_COMMIT,
            "historical_published_lock_count": 20,
            "never_published_lock_present_count": 0,
            "p_output_present_count": 0,
            "r8_output_present_count": 8,
            "r8_committed_output_count": 8,
            "coordination_present_count": 0,
            "coordination_forbidden_count": 49,
            "r8_bytes_preserved": True,
            "scientific_writes_performed": False,
            "dvc_commands_run": False,
            "outcome_paths_opened": False,
            "companion_contract": {
                "physical_input_count": EXPECTED_COMPANION_INPUT_COUNT,
                "historical_input_count": EXPECTED_HISTORICAL_INPUT_COUNT,
                "output_count": EXPECTED_COMPANION_OUTPUT_COUNT,
                "script_path": LOCKER_PATH.as_posix(),
                "manifest_written_last": True,
            },
        },
        "schema_preflight": schema,
    }


@_error_boundary
def collect_final_calibration_r8_post_publication_authority_patch_prelock_state(
    *, verify_remote: bool = False, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    repository, h_patch = _h_patch_authority(
        repo_root=root, verify_remote=verify_remote
    )
    return _state_for_h(
        repository=repository,
        h_patch=h_patch,
        repo_root=root,
        require_prelock_namespace=True,
    )


def _default_unrun_verification() -> dict[str, Any]:
    return {
        "status": "not_run_by_payload_builder",
        "commands_run": False,
        "scientific_execution_run": False,
        "r8_files_touched": False,
        "r8_files_staged": False,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
    }


@_error_boundary
def build_final_calibration_r8_post_publication_authority_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any] | None = None,
    *,
    generated_at_utc: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root
    required = {
        "repository",
        "terminal_r_mcall_authority",
        "p_mcall_authority",
        "historical_h_mcall_authority",
        "h_patch",
        "coordination_namespace_contract",
        "coordination_namespace",
        "historical_inputs",
        "historical_inputs_sha256",
        "r8_bundle",
        "formal_e0_m_boundary",
        "prelock",
        "schema_preflight",
    }
    if not isinstance(prelock, Mapping) or set(prelock) != required:
        raise _error("E0-MCALM prelock dialect drifted")
    return {
        "schema_version": LOCK_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "status": "locked_unpublished",
        "generated_at_utc": generated_at_utc or datetime.now(timezone.utc).isoformat(),
        **{key: _deep_copy(prelock[key]) for key in required},
        "verification": _deep_copy(
            verification if verification is not None else _default_unrun_verification()
        ),
        "authorizations": dict(UNPUBLISHED_AUTHORIZATIONS),
    }


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise _error("E0-MCALM generated timestamp is absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _error("E0-MCALM generated timestamp is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _error("E0-MCALM generated timestamp must be timezone-aware")


def _validate_verification(value: Any, *, repo_root: Path) -> None:
    if value == _default_unrun_verification():
        return
    if not isinstance(value, Mapping) or set(value) != {
        "schema_preflight",
        "full_type_check",
        "focused_tests",
        "poetry_check",
        "publication_guard",
        "git_diff_check",
    }:
        raise _error("E0-MCALM verification evidence dialect drifted")
    if _canonical_json_bytes(value["schema_preflight"]) != _canonical_json_bytes(
        preflight_final_calibration_r8_post_publication_authority_patch_schema(
            repo_root=repo_root
        )
    ):
        raise _error("E0-MCALM schema verification evidence drifted")
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
        raise _error("E0-MCALM focused verification evidence drifted")
    mcal._validate_command_evidence(
        {key: focused[key] for key in base_keys},
        expected_command=FOCUSED_TEST_COMMAND,
        context="focused_tests",
    )


@_error_boundary
def validate_final_calibration_r8_post_publication_authority_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    verify_remote: bool = False,
) -> dict[str, Any]:
    root = _root(repo_root)
    if not isinstance(payload, Mapping):
        raise _error("E0-MCALM lock payload must be an object")
    schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    try:
        mcal.validate_json_schema(payload, schema)
    except mcal.ClosureContractError as exc:
        raise _error(_translate_predecessor_error(str(exc))) from exc
    _validate_timestamp(payload.get("generated_at_utc"))
    _validate_verification(payload.get("verification"), repo_root=root)
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise _error("E0-MCALM unpublished authorizations drifted")
    state = collect_final_calibration_r8_post_publication_authority_patch_prelock_state(
        verify_remote=verify_remote, repo_root=root
    )
    expected = build_final_calibration_r8_post_publication_authority_patch_lock_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=cast(str, payload["generated_at_utc"]),
    )
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("E0-MCALM lock semantic reconstruction drifted")
    return dict(payload)


_OwnedOutput = mcall._OwnedOutput


def _public_artifact_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in ("role", "path", "bytes", "sha256")}


def _expected_companion(
    payload: Mapping[str, Any], lock_record: Mapping[str, Any]
) -> dict[str, Any]:
    predecessor = cast(Mapping[str, Any], payload["p_mcall_authority"])
    patch = cast(Mapping[str, Any], payload["h_patch"])
    r8 = cast(Mapping[str, Any], payload["r8_bundle"])
    prior = cast(Sequence[Mapping[str, Any]], predecessor["p_components"])
    current = cast(Sequence[Mapping[str, Any]], patch["components"])
    outputs = cast(Sequence[Mapping[str, Any]], r8["r8_outputs"])
    r8_inputs = [
        {
            "role": "published_immutable_r8_output",
            "path": record["path"],
            "bytes": record["bytes"],
            "sha256": record["sha256"],
        }
        for record in outputs
    ]
    inputs = [
        _public_artifact_record(record) for record in (*prior, *current, *r8_inputs)
    ]
    inputs.sort(key=lambda record: cast(str, record["path"]))
    if (
        len(inputs) != EXPECTED_COMPANION_INPUT_COUNT
        or len({record["path"] for record in inputs})
        != EXPECTED_COMPANION_INPUT_COUNT
    ):
        raise _error("E0-MCALM companion physical input set drifted")
    historical = [
        dict(record)
        for record in cast(Sequence[Mapping[str, Any]], payload["historical_inputs"])
    ]
    historical.sort(key=lambda record: cast(str, record["path"]))
    if (
        len(historical) != EXPECTED_HISTORICAL_INPUT_COUNT
        or len({record["path"] for record in historical})
        != EXPECTED_HISTORICAL_INPUT_COUNT
    ):
        raise _error("E0-MCALM companion historical input set drifted")
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
        "r8_files_touched": False,
        "r8_files_staged": False,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
    }


def _require_publication_verification(
    payload: Mapping[str, Any], *, repo_root: Path
) -> None:
    verification = payload.get("verification")
    if verification == _default_unrun_verification():
        raise _error("E0-MCALM publication requires frozen verification evidence")
    _validate_verification(verification, repo_root=repo_root)


def _physical_snapshot(repo_root: Path) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for path_text in (*P_MCALL_PATHS, *PATCH_PATHS):
        path = Path(path_text)
        expected_mode = PATCH_COMPONENT_GIT_MODES.get(path_text, "100644")
        payload, metadata = mcal._read_regular_bytes_and_metadata(
            path,
            repo_root=repo_root,
            expected_mode=int(expected_mode[-3:], 8),
            require_nlink_one=True,
        )
        records.append(
            {
                "path": path_text,
                "device": int(metadata.st_dev),
                "inode": int(metadata.st_ino),
                "mode": int(metadata.st_mode),
                "nlink": int(metadata.st_nlink),
                "size": len(payload),
                "mtime_ns": int(metadata.st_mtime_ns),
                "ctime_ns": int(metadata.st_ctime_ns),
                "sha256": _sha256_bytes(payload),
            }
        )
    for expected in R8_OUTPUT_CONTRACT:
        path_text = cast(str, expected["path"])
        payload, metadata = mcal._read_regular_bytes_and_metadata(
            Path(path_text),
            repo_root=repo_root,
            expected_mode=0o644,
            require_nlink_one=True,
        )
        observed = {
            "path": path_text,
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
        }
        if observed != expected:
            raise _error(f"E0-MCALM immutable R8 snapshot drifted: {path_text}")
        records.append(
            {
                "path": path_text,
                "device": int(metadata.st_dev),
                "inode": int(metadata.st_ino),
                "mode": int(metadata.st_mode),
                "nlink": int(metadata.st_nlink),
                "size": observed["bytes"],
                "mtime_ns": int(metadata.st_mtime_ns),
                "ctime_ns": int(metadata.st_ctime_ns),
                "sha256": observed["sha256"],
            }
        )
    records.sort(key=lambda record: cast(str, record["path"]))
    if len(records) != 16 or len({record["path"] for record in records}) != 16:
        raise _error("E0-MCALM physical input snapshot is not exact16")
    return tuple(records)


def _require_physical_snapshot(
    expected: Sequence[Mapping[str, Any]], *, repo_root: Path, context: str
) -> None:
    if _canonical_json_bytes(expected) != _canonical_json_bytes(
        _physical_snapshot(repo_root)
    ):
        raise _error(f"E0-MCALM physical/R8 identity changed {context}")


def _parse_canonical_json_with_metadata(
    path: Path, *, repo_root: Path
) -> tuple[dict[str, Any], bytes, os.stat_result]:
    payload, metadata = mcal._read_regular_bytes_and_metadata(
        path, repo_root=repo_root, expected_mode=0o644, require_nlink_one=True
    )
    value = mcal._parse_json_bytes(payload, context=path.as_posix())
    if not isinstance(value, dict) or payload != _canonical_json_bytes(value):
        raise _error(f"E0-MCALM canonical JSON drifted: {path.as_posix()}")
    return value, payload, metadata


def _published_h_state(h_head: str, *, repo_root: Path) -> dict[str, Any]:
    if h_head == BASE_R_MCALL_COMMIT or re.fullmatch(r"[0-9a-f]{40}", h_head) is None:
        raise _error("E0-MCALM published H commit is absent")
    if (
        mcal._single_parent(repo_root, h_head, context="H-E0-MCALM")
        != BASE_R_MCALL_COMMIT
    ):
        raise _error("E0-MCALM published H parent drifted")
    scope = mcal._git_scope(repo_root, BASE_R_MCALL_COMMIT, h_head)
    expected_scope = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(PATCH_PATHS),
    }
    if scope != expected_scope:
        raise _error("E0-MCALM published H scope drifted")
    components = [
        mcal._git_artifact_record(
            Path(path),
            role="final_calibration_r8_post_publication_authority_patch_component",
            repo_root=repo_root,
            commit=h_head,
            expected_mode=PATCH_COMPONENT_GIT_MODES[path],
        )
        for path in PATCH_PATHS
    ]
    return _state_for_h(
        repository={
            "base_r_mcall_commit": BASE_R_MCALL_COMMIT,
            "historical_p_mcall_commit": HISTORICAL_P_MCALL_COMMIT,
            "h_patch_head": h_head,
            "branch": "main",
            "remote_head": h_head,
            "scope": scope,
        },
        h_patch={
            "gate": "H-E0-MCALM",
            "component_count": 6,
            "added_count": 5,
            "modified_count": 1,
            "components": components,
            "components_sha256": mcal._digest_records(components),
        },
        repo_root=repo_root,
        require_prelock_namespace=False,
    )


def _validate_published_lock_payload(
    payload: Mapping[str, Any], *, repo_root: Path
) -> None:
    schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=repo_root)
    try:
        mcal.validate_json_schema(payload, schema)
    except mcal.ClosureContractError as exc:
        raise _error(_translate_predecessor_error(str(exc))) from exc
    _validate_timestamp(payload.get("generated_at_utc"))
    _validate_verification(payload.get("verification"), repo_root=repo_root)
    _require_publication_verification(payload, repo_root=repo_root)
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise _error("E0-MCALM published authorizations drifted")
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("E0-MCALM published H binding is absent")
    state = _published_h_state(
        cast(str, repository["h_patch_head"]), repo_root=repo_root
    )
    expected = build_final_calibration_r8_post_publication_authority_patch_lock_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=cast(str, payload["generated_at_utc"]),
    )
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("E0-MCALM published lock reconstruction drifted")


def _require_repository_checkpoint(
    *,
    repo_root: Path,
    expected_head: str,
    verify_remote: bool,
    p_outputs_present: bool,
    context: str,
) -> None:
    expected_status = (
        [("??", path.as_posix()) for path in CURRENT_LOCK_PATHS]
        if p_outputs_present
        else []
    )
    if (
        cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
        != "main"
        or mcal._git_head(repo_root) != expected_head
        or mcal._git_head(repo_root, "origin/main") != expected_head
        or mcal._workspace_status_records(repo_root) != expected_status
    ):
        raise _error(f"E0-MCALM repository changed {context}")
    if verify_remote and mcal._live_remote_main_head(repo_root) != expected_head:
        raise _error(f"E0-MCALM live remote changed {context}")


@_error_boundary
def publish_final_calibration_r8_post_publication_authority_patch_lock_bundle(
    payload: Mapping[str, Any], *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _root(repo_root)
    try:
        lock_bytes = _canonical_json_bytes(payload)
        frozen = json.loads(lock_bytes)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise _error("E0-MCALM publication payload is not canonical JSON") from exc
    if not isinstance(frozen, dict) or _canonical_json_bytes(frozen) != lock_bytes:
        raise _error("E0-MCALM publication payload must be a canonical object")
    payload = frozen
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("E0-MCALM publication H binding is absent")
    initial_head = cast(str, repository["h_patch_head"])
    if mcal._git_head(root) != initial_head or initial_head == BASE_R_MCALL_COMMIT:
        raise _error("E0-MCALM publication requires published H")
    validate_final_calibration_r8_post_publication_authority_patch_lock_payload(
        payload, repo_root=root, verify_remote=True
    )
    _require_publication_verification(payload, repo_root=root)
    _require_repository_checkpoint(
        repo_root=root,
        expected_head=initial_head,
        verify_remote=True,
        p_outputs_present=False,
        context="before publication",
    )
    _require_coordination_namespace(
        repo_root=root, current_outputs_state="absent"
    )
    snapshot = _physical_snapshot(root)
    published: list[Any] = []
    guard: Any | None = None
    committed = False
    try:
        guard = mt._acquire_publication_guard(
            LOCKER_GUARD_PATH,
            b"E0-MCALM final calibration post-publication authority lock\n",
            repo_root=root,
        )
        _require_coordination_namespace(
            repo_root=root, current_outputs_state="absent", owned_guard=guard
        )
        _require_physical_snapshot(snapshot, repo_root=root, context="after guard")
        lock_output = mcall.mcalk._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_PATH, lock_bytes, repo_root=root
        )
        published.append(lock_output)
        lock_record = {
            "role": "final_calibration_r8_post_publication_authority_patch_lock",
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "bytes": len(lock_bytes),
            "sha256": _sha256_bytes(lock_bytes),
        }
        companion = _expected_companion(payload, lock_record)
        companion_bytes = _canonical_json_bytes(companion)
        companion_output = mcall.mcalk._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH, companion_bytes, repo_root=root
        )
        published.append(companion_output)
        publication = ((lock_output, lock_bytes), (companion_output, companion_bytes))
        for output, expected in publication:
            mcall.mcalk.mcalj._validate_owned_output_bytes(
                output, expected, repo_root=root, context="after publication"
            )
        _require_coordination_namespace(
            repo_root=root, current_outputs_state="present", owned_guard=guard
        )
        _require_physical_snapshot(
            snapshot, repo_root=root, context="after companion publication"
        )
        _require_repository_checkpoint(
            repo_root=root,
            expected_head=initial_head,
            verify_remote=True,
            p_outputs_present=True,
            context="during publication",
        )
        mt._release_publication_guard(guard)
        guard = None
        for pass_index in (1, 2):
            _require_coordination_namespace(
                repo_root=root, current_outputs_state="present"
            )
            _require_physical_snapshot(
                snapshot,
                repo_root=root,
                context=f"during ownership transfer pass {pass_index}",
            )
            _require_repository_checkpoint(
                repo_root=root,
                expected_head=initial_head,
                verify_remote=True,
                p_outputs_present=True,
                context=f"during ownership transfer pass {pass_index}",
            )
            for output, expected in publication:
                mcall.mcalk.mcalj._validate_owned_output_bytes(
                    output,
                    expected,
                    repo_root=root,
                    context=f"ownership transfer pass {pass_index}",
                )
            mcall.mcalk.mcalj.mcali._require_owned_identity_set(
                [output for output, _ in publication],
                context=f"MCALM ownership transfer pass {pass_index}",
            )
        _require_coordination_namespace(
            repo_root=root, current_outputs_state="present"
        )
        committed = True
        return dict(payload), companion
    except BaseException as exc:
        rollback = mcall.mcalk._rollback_outputs_best_effort(published)
        if rollback is not None:
            exc.add_note(str(rollback))
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, FinalCalibrationR8PostPublicationAuthorityPatchError):
            raise
        raise _error("E0-MCALM lock bundle publication failed") from exc
    finally:
        if guard is not None:
            try:
                mt._release_publication_guard(guard, tolerate_foreign=True)
            except Exception:
                pass
        if committed:
            for output in reversed(published):
                try:
                    mcall.mcalk.mcalj._close_owned_output(output)
                except Exception:
                    pass


def _validate_unpublished_p_repository(
    *, h_head: str, verify_remote: bool, repo_root: Path
) -> str:
    if type(verify_remote) is not bool:
        raise _error("E0-MCALM unpublished P remote policy must be exact boolean")
    expected_h_scope = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(PATCH_PATHS),
    }
    if (
        cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
        != "main"
        or mcal._git_head(repo_root) != h_head
        or mcal._single_parent(repo_root, h_head, context="H-E0-MCALM")
        != BASE_R_MCALL_COMMIT
        or mcal._git_scope(repo_root, BASE_R_MCALL_COMMIT, h_head)
        != expected_h_scope
    ):
        raise _error("E0-MCALM unpublished P requires exact published H topology")
    tracking = mcal._git_head(repo_root, "origin/main")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != h_head or remote != h_head:
        raise _error("E0-MCALM unpublished P H refs drifted")
    p_untracked = [("??", path.as_posix()) for path in CURRENT_LOCK_PATHS]
    p_staged = [("A ", path.as_posix()) for path in CURRENT_LOCK_PATHS]
    observed = sorted(mcal._workspace_status_records(repo_root))
    if observed == sorted(p_untracked):
        return "untracked"
    if observed == sorted(p_staged):
        return "staged"
    raise _error("E0-MCALM unpublished P workspace is not exact P2")


@_error_boundary
def validate_final_calibration_r8_post_publication_authority_unpublished_lock_bundle(
    *, repo_root: Path | None = None, verify_remote: bool = True
) -> dict[str, Any]:
    root = _root(repo_root)
    lock, lock_bytes, lock_metadata = _parse_canonical_json_with_metadata(
        DEFAULT_PATCH_LOCK_PATH, repo_root=root
    )
    repository = lock.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("E0-MCALM unpublished P H binding is absent")
    h_head = cast(str, repository["h_patch_head"])
    stage_state = _validate_unpublished_p_repository(
        h_head=h_head, verify_remote=verify_remote, repo_root=root
    )
    _validate_published_lock_payload(lock, repo_root=root)
    lock_record = mcal._file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="final_calibration_r8_post_publication_authority_patch_lock",
        repo_root=root,
    )
    companion, companion_bytes, companion_metadata = (
        _parse_canonical_json_with_metadata(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
        )
    )
    if _canonical_json_bytes(companion) != _canonical_json_bytes(
        _expected_companion(lock, lock_record)
    ):
        raise _error("E0-MCALM unpublished P companion drifted")
    namespace = _require_coordination_namespace(
        repo_root=root, current_outputs_state="present"
    )
    snapshot = _physical_snapshot(root)
    r8 = _validate_r8_bundle_post_publication(repo_root=root)
    recaptured_lock, recaptured_lock_bytes, recaptured_lock_metadata = (
        _parse_canonical_json_with_metadata(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    )
    (
        recaptured_companion,
        recaptured_companion_bytes,
        recaptured_companion_metadata,
    ) = _parse_canonical_json_with_metadata(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
    )
    if (
        recaptured_lock != lock
        or recaptured_companion != companion
        or recaptured_lock_bytes != lock_bytes
        or recaptured_companion_bytes != companion_bytes
        or mcall.mcalk.mcalj._metadata_identity(recaptured_lock_metadata)
        != mcall.mcalk.mcalj._metadata_identity(lock_metadata)
        or mcall.mcalk.mcalj._metadata_identity(recaptured_companion_metadata)
        != mcall.mcalk.mcalj._metadata_identity(companion_metadata)
    ):
        raise _error("E0-MCALM unpublished P changed during semantic validation")
    _require_physical_snapshot(
        snapshot, repo_root=root, context="during unpublished P validation"
    )
    if _require_coordination_namespace(
        repo_root=root, current_outputs_state="present"
    ) != namespace:
        raise _error("E0-MCALM namespace changed during unpublished P validation")
    if (
        _validate_unpublished_p_repository(
            h_head=h_head, verify_remote=verify_remote, repo_root=root
        )
        != stage_state
    ):
        raise _error("E0-MCALM unpublished P stage state changed during validation")
    return {
        "gate": PATCH_GATE,
        "status": "unpublished_p_mcalm_lock_bundle_validated",
        "h_patch_head": h_head,
        "p_stage_state": stage_state,
        "p_output_count": 2,
        "physical_input_count": EXPECTED_COMPANION_INPUT_COUNT,
        "historical_input_count": EXPECTED_HISTORICAL_INPUT_COUNT,
        "companion_output_count": EXPECTED_COMPANION_OUTPUT_COUNT,
        "coordination_forbidden_count": 49,
        "coordination_present_count": 0,
        "r8_output_count": r8["r8_output_count"],
        "r8_outputs_sha256": r8["r8_outputs_sha256"],
        "r8_published": True,
        "r8_staging_authorized": False,
        "effective_authority": False,
        "e0_m_authorized": False,
        "scientific_rerun_authorized": False,
        "dvc_commands_authorized": False,
        "dvc_push_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
        "writes_performed": False,
    }


def _validate_p_publication(
    payload: Mapping[str, Any], *, verify_remote: bool, repo_root: Path
) -> dict[str, str]:
    if type(verify_remote) is not bool:
        raise _error("E0-MCALM remote policy must be exact boolean")
    repository = cast(Mapping[str, Any], payload["repository"])
    h_head = cast(str, repository["h_patch_head"])
    head = mcal._git_head(repo_root)
    expected_scope = {
        "added": 2,
        "modified": 0,
        "deleted": 0,
        "path_count": 2,
        "paths": sorted(FINAL_CALIBRATION_P_STAGED_SCOPE),
    }
    if (
        cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
        != "main"
        or mcal._workspace_status_records(repo_root)
        or mcal._single_parent(repo_root, head, context="P-E0-MCALM") != h_head
        or mcal._git_scope(repo_root, h_head, head) != expected_scope
    ):
        raise _error("E0-MCALM published P topology/clean worktree drifted")
    tracking = mcal._git_head(repo_root, "origin/main")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != head or remote != head:
        raise _error("E0-MCALM published P refs drifted")
    for path in CURRENT_LOCK_PATHS:
        physical = mcal._read_regular_bytes(path, repo_root=repo_root)
        mode, _ = mcal._git_mode_oid(repo_root, head, path)
        if mode != "100644" or physical != mcal._git_blob_bytes(repo_root, head, path):
            raise _error(f"E0-MCALM published P binding drifted: {path}")
    return {"h_patch_head": h_head, "p_patch_head": head, "remote_head": remote}


@_error_boundary
def load_effective_final_calibration_r8_post_publication_authority_patch_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    lock, lock_bytes, lock_metadata = _parse_canonical_json_with_metadata(
        DEFAULT_PATCH_LOCK_PATH, repo_root=root
    )
    _validate_published_lock_payload(lock, repo_root=root)
    lock_record = mcal._file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="final_calibration_r8_post_publication_authority_patch_lock",
        repo_root=root,
    )
    companion, companion_bytes, companion_metadata = (
        _parse_canonical_json_with_metadata(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
        )
    )
    if _canonical_json_bytes(companion) != _canonical_json_bytes(
        _expected_companion(lock, lock_record)
    ):
        raise _error("E0-MCALM published companion drifted")
    publication = _validate_p_publication(
        lock, verify_remote=verify_remote, repo_root=root
    )
    namespace = _require_coordination_namespace(
        repo_root=root, current_outputs_state="present"
    )
    r8 = _validate_r8_bundle_post_publication(repo_root=root)
    snapshot = _physical_snapshot(root)
    recaptured_lock, recaptured_bytes, recaptured_metadata = (
        _parse_canonical_json_with_metadata(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    )
    (
        recaptured_companion,
        recaptured_companion_bytes,
        recaptured_companion_metadata,
    ) = _parse_canonical_json_with_metadata(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
    )
    if (
        recaptured_lock != lock
        or recaptured_companion != companion
        or recaptured_bytes != lock_bytes
        or recaptured_companion_bytes != companion_bytes
        or mcall.mcalk.mcalj._metadata_identity(recaptured_metadata)
        != mcall.mcalk.mcalj._metadata_identity(lock_metadata)
        or mcall.mcalk.mcalj._metadata_identity(recaptured_companion_metadata)
        != mcall.mcalk.mcalj._metadata_identity(companion_metadata)
    ):
        raise _error("E0-MCALM P authority changed during effective loading")
    _require_physical_snapshot(
        snapshot, repo_root=root, context="during effective loading"
    )
    if _require_coordination_namespace(
        repo_root=root, current_outputs_state="present"
    ) != namespace:
        raise _error("E0-MCALM namespace changed during effective loading")
    if _validate_p_publication(
        lock, verify_remote=verify_remote, repo_root=root
    ) != publication:
        raise _error("E0-MCALM publication changed during effective loading")
    if _canonical_json_bytes(
        _validate_r8_bundle_post_publication(repo_root=root)
    ) != _canonical_json_bytes(r8):
        raise _error("E0-MCALM R8 semantics changed during effective loading")
    return {
        "gate": PATCH_GATE,
        "status": "effective",
        **publication,
        "terminal_r_commit": BASE_R_MCALL_COMMIT,
        "lock": lock_record,
        "companion": mcal._file_record(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            role="final_calibration_r8_post_publication_authority_patch_lock_manifest",
            repo_root=root,
        ),
        "authority_binding_sha256": _sha256_bytes(
            _canonical_json_bytes(
                {
                    "p_patch_head": publication["p_patch_head"],
                    "terminal_r_commit": BASE_R_MCALL_COMMIT,
                    "lock": lock_record,
                    "companion_sha256": _sha256_bytes(companion_bytes),
                    "r8_outputs_sha256": r8["r8_outputs_sha256"],
                    "coordination_namespace": namespace,
                }
            )
        ),
        "coordination_namespace_revalidation": _deep_copy(
            COORDINATION_NAMESPACE_CONTRACT
        ),
        "r8_output_paths": [path.as_posix() for path in R_OUTPUT_PATHS],
        "calibration_output_present_count": 6,
        "e7_output_present_count": 2,
        "r_output_present_count": 8,
        "r_lifecycle_state": "both_bundles_published_terminal",
        "r8_published": True,
        "r_outputs_published": True,
        "r_outputs_ready_for_staging": False,
        "r8_staging_authorized": False,
        "effective_authority": True,
        "formal_e0_m_entrypoint_present": False,
        "formal_e0_m_execution_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "scientific_rerun_authorized": False,
        "holdout_access_authorized": False,
        "post_2021_access_authorized": False,
        "outcome_access_authorized": False,
        "dvc_commands_authorized": False,
        "dvc_push_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
        "writes_performed": False,
    }


@_error_boundary
def require_final_calibration_r8_post_publication_authority_patch_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    return load_effective_final_calibration_r8_post_publication_authority_patch_authority(
        verify_remote=verify_remote, repo_root=repo_root
    )


@_error_boundary
def validate_final_calibration_r8_post_publication_authority_model_lock_readiness(
    *,
    repo_root: Path | None = None,
    verify_remote: bool = True,
    require_effective: bool = True,
) -> dict[str, Any]:
    if type(require_effective) is not bool or type(verify_remote) is not bool:
        raise _error("E0-MCALM readiness policies must be exact booleans")
    root = _root(repo_root)
    authority: dict[str, Any] | None = None
    if require_effective:
        authority = require_final_calibration_r8_post_publication_authority_patch_authority(
            verify_remote=verify_remote, repo_root=root
        )
    else:
        _h_patch_authority(repo_root=root, verify_remote=verify_remote)
        _terminal_r_mcall_authority(repo_root=root)
        _require_coordination_namespace(
            repo_root=root, current_outputs_state="absent"
        )
    r8 = _validate_r8_bundle_post_publication(repo_root=root)
    if any(_path_exists(path, repo_root=root) for path in E0_M_OUTPUT_PATHS):
        raise _error("E0-MCALM formal E0-M outputs already exist")
    if _path_exists(OUTCOME_ACCESS_LOG_PATH, repo_root=root):
        raise _error("E0-MCALM outcome access log must remain absent before E0-M")
    return {
        "gate": PATCH_GATE,
        "status": "formal_e0_m_static_readiness_validated",
        "effective_p_mcalm_verified": authority is not None,
        "terminal_r_commit": BASE_R_MCALL_COMMIT,
        "r8_output_count": r8["r8_output_count"],
        "r8_outputs_sha256": r8["r8_outputs_sha256"],
        "r8_published": True,
        "e0_m_output_count": 0,
        "outcome_access_log_state": "absent",
        "outcome_access_log_required_e0_m_state": "present_empty",
        "formal_e0_m_entrypoint_present": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "outcome_access_authorized": False,
        "scientific_rerun_authorized": False,
        "writes_performed": False,
    }


@_error_boundary
def require_final_calibration_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    return require_final_calibration_r8_post_publication_authority_patch_authority(
        verify_remote=verify_remote, repo_root=repo_root
    )


@_error_boundary
def require_final_calibration_run_namespace(
    *, runner: str, repo_root: Path | None = None
) -> dict[str, Any]:
    del repo_root
    if type(runner) is not str or runner not in {"calibration", "e7"}:
        raise _error("E0-MCALM run namespace requires calibration or e7")
    raise _error("E0-MCALM R8 is published terminal; scientific rerun is forbidden")


def revalidate_final_calibration_owned_run_publication(
    *, runner: str, repo_root: Path | None = None
) -> dict[str, Any]:
    return require_final_calibration_run_namespace(runner=runner, repo_root=repo_root)
