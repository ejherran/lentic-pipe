"""Permit exact owned-run guard revalidation without weakening public loading.

E0-MCALI is an additive authority over published P-E0-MCALH.  The public
loader remains fail-closed whenever a run guard exists.  A private transaction
surface may revalidate only an anchored guard capability that it already owns,
the exact output bundle it just published, and the expected R0->R6 or R6->R8
lifecycle transition.  No scientific data, model, prediction, or result path
is rewritten.
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
    closure_final_calibration_observed_risk_precision_patch as mcalh,
)

mcal = mcalh.mcal
mt = mcalh.mt
TARGET_FILTER_EVIDENCE_CONTRACT = mcalh.TARGET_FILTER_EVIDENCE_CONTRACT
INFERENCE_ROLE_CONTRACT = mcalh.INFERENCE_ROLE_CONTRACT
RAW_SCORE_CANDIDATE_VALUES = mcalh.RAW_SCORE_CANDIDATE_VALUES
RAW_EXCLUSION_EVIDENCE_CONTRACT = mcalh.RAW_EXCLUSION_EVIDENCE_CONTRACT
ORDINAL_LABEL_REPRESENTATION_CONTRACT = (
    mcalh.ORDINAL_LABEL_REPRESENTATION_CONTRACT
)
OBSERVED_RISK_PRECISION_CONTRACT = mcalh.OBSERVED_RISK_PRECISION_CONTRACT


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_P_MCALH_COMMIT = "c6dbe43f01e484c7270c6a19f9a69d0b753036c7"
H_MCALH_COMMIT = "e107316cbe302fc806676f620af00df6244530a5"
H_MCALH_PARENT = mcalh.BASE_P_MCALG_COMMIT
PATCH_GATE = "E0-MCALI"
FINAL_CALIBRATION_GATE = PATCH_GATE
EXPERIMENT_ID = "closure_v1"
LOCK_SCHEMA_VERSION = "closure_final_calibration_owned_run_guard_revalidation_patch_lock_v1"
COMPANION_SCHEMA_VERSION = (
    "closure_final_calibration_owned_run_guard_revalidation_patch_lock_manifest_v1"
)

DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/final_calibration_owned_run_guard_revalidation_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/final_calibration_owned_run_guard_revalidation_patch_lock.json"
)
DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "final_calibration_owned_run_guard_revalidation_patch_lock_manifest.json"
)
DEFAULT_PATCH_MANIFEST_PATH = DEFAULT_PATCH_LOCK_MANIFEST_PATH
LOCKER_PATH = Path(
    "src/experiments/lock_closure_final_calibration_owned_run_guard_revalidation_patch.py"
)
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_e0_mcali/final_calibration_owned_run_guard_revalidation_patch_lock.guard"
)

H_MCALH_SUPERSEDED_PATHS = tuple(
    sorted(
        {
            "src/experiments/calibrate_closure_final_models.py",
            "src/experiments/run_closure_anfis_learning_curve.py",
            "tests/test_calibrate_closure_final_models.py",
            "tests/test_closure_anfis_learning_curve.py",
        }
    )
)
H_MCALH_PRESERVED_PATHS = tuple(
    path for path in mcalh.PATCH_PATHS if path not in H_MCALH_SUPERSEDED_PATHS
)
P_MCALH_PATHS = (
    mcalh.DEFAULT_PATCH_LOCK_PATH.as_posix(),
    mcalh.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
)
PATCH_PATHS = tuple(
    sorted(
        {
            DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
            "docs/closure_v1/E0_M_FINAL_CALIBRATION_OWNED_RUN_GUARD_REVALIDATION_PATCH_1.md",
            *H_MCALH_SUPERSEDED_PATHS,
            "src/experiments/closure_final_calibration_owned_run_guard_revalidation_patch.py",
            LOCKER_PATH.as_posix(),
            "tests/test_closure_final_calibration_owned_run_guard_revalidation_patch.py",
        }
    )
)
PATCH_COMPONENT_GIT_MODES = {path: "100644" for path in PATCH_PATHS}
FINAL_CALIBRATION_H_STAGED_SCOPE = {
    path: ("M" if path in H_MCALH_SUPERSEDED_PATHS else "A")
    for path in PATCH_PATHS
}
FINAL_CALIBRATION_P_STAGED_SCOPE = {
    DEFAULT_PATCH_LOCK_PATH.as_posix(): "A",
    DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(): "A",
}
FINAL_CALIBRATION_R_STAGED_SCOPE = dict(mcalh.FINAL_CALIBRATION_R_STAGED_SCOPE)
R_OUTPUT_PATHS = mcalh.R_OUTPUT_PATHS

EXPECTED_COMPANION_INPUT_COUNT = 16
EXPECTED_HISTORICAL_INPUT_COUNT = 4
EXPECTED_COMPANION_OUTPUT_COUNT = 1

FAILED_ATTEMPT = {
    "attempted_gate": "E0-MCALH",
    "status": "failed_closed_rolled_back_no_outputs",
    "phase": "calibration_bundle_publication_authority_revalidation",
    "failure_code": (
        "owned_calibration_guard_rejected_by_effective_namespace_revalidation"
    ),
    "authorization_consumed": True,
    "retry_authorized": False,
    "scientific_input_reads_performed": True,
    "anfis_inference_slot_count": 10,
    "model_inference_performed": True,
    "calibration_fit_performed": True,
    "bundle_payload_built": True,
    "owned_guard_acquired": True,
    "provisional_output_count": 6,
    "rollback_performed": True,
    "rollback_complete": True,
    "final_output_count": 0,
    "temporary_output_count": 0,
    "active_guard_count": 0,
    "dvc_commands_run": False,
    "outcome_paths_opened": False,
    "holdout_rows_opened": False,
    "post_2021_rows_opened": False,
    "filesystem_side_effect_count": 0,
}
OWNED_RUN_GUARD_REVALIDATION_CONTRACT = {
    "supported_runners": ["calibration", "e7"],
    "supported_phases": ["active_guard", "post_release"],
    "capability_keys": [
        "path",
        "device",
        "inode",
        "mode",
        "nlink",
        "size",
        "mtime_ns",
        "ctime_ns",
        "sha256",
    ],
    "capability_integer_fields": [
        "device",
        "inode",
        "mode",
        "nlink",
        "size",
        "mtime_ns",
        "ctime_ns",
    ],
    "guard_paths": {
        "calibration": "tmp/closure_v1_e0_mcal/final_calibration.guard",
        "e7": "tmp/closure_v1_e0_mcal/anfis_learning_curve.guard",
    },
    "guard_payload_utf8": "E0-MCAL active light-output transaction\n",
    "guard_payload_bytes": 40,
    "guard_payload_sha256": (
        "31b7ba37195e14da436932e280b6cd388f8de9083f7429358fe0f374ad2724ef"
    ),
    "guard_mode": 384,
    "output_mode": 420,
    "required_nlink": 1,
    "active_guard_output_counts": {"calibration": 6, "e7": 2},
    "active_guard_transitions": {
        "calibration": [
            "ready_for_calibration_bundle",
            "calibration_completed_unpublished_ready_for_e7_bundle",
        ],
        "e7": [
            "calibration_completed_unpublished_ready_for_e7_bundle",
            "both_bundles_completed_unpublished",
        ],
    },
    "post_release_guard_policy": "absent",
    "public_loader_guard_policy": "reject_all",
    "foreign_guard_authorized": False,
    "partial_output_bundle_authorized": False,
    "data_rewrite_performed": False,
}

TYPE_CHECK_COMMAND = mcalh.TYPE_CHECK_COMMAND
FOCUSED_TEST_COMMAND = (
    "poetry",
    "run",
    "pytest",
    "-q",
    "tests/test_calibrate_closure_final_models.py",
    "tests/test_closure_anfis_learning_curve.py",
    "tests/test_closure_final_calibration_owned_run_guard_revalidation_patch.py",
)
FOCUSED_TEST_COUNT = 48
POETRY_CHECK_COMMAND = mcalh.POETRY_CHECK_COMMAND
PUBLICATION_GUARD_COMMAND = mcalh.PUBLICATION_GUARD_COMMAND
DIFF_CHECK_COMMAND = mcalh.DIFF_CHECK_COMMAND
UNPUBLISHED_AUTHORIZATIONS = dict(mcalh.UNPUBLISHED_AUTHORIZATIONS)
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


class FinalCalibrationOwnedRunGuardRevalidationPatchError(
    mcalh.FinalCalibrationObservedRiskPrecisionPatchError
):
    """Raised when the E0-MCALI correction authority is not exact."""


FinalCalibrationError = mcalh.FinalCalibrationError
P = ParamSpec("P")
R = TypeVar("R")


def _error(message: str) -> FinalCalibrationOwnedRunGuardRevalidationPatchError:
    return FinalCalibrationOwnedRunGuardRevalidationPatchError(message)


def _error_boundary(function: Callable[P, R]) -> Callable[P, R]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return function(*args, **kwargs)
        except FinalCalibrationOwnedRunGuardRevalidationPatchError:
            raise
        except mcalh.FinalCalibrationError as exc:
            raise _error(str(exc).replace("E0-MCALH", "E0-MCALI")) from exc

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


def _git_record_at_commit(
    path: str, *, role: str, commit: str, repo_root: Path
) -> dict[str, Any]:
    relative = Path(path)
    mode, oid = mcal._git_mode_oid(repo_root, commit, relative)
    payload = mcal._git_blob_bytes(repo_root, commit, relative)
    if mode != "100644":
        raise _error(f"E0-MCALI historical Git mode drifted: {path}")
    return {
        "role": role,
        "path": path,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "git_oid": oid,
        "git_mode": mode,
    }


def _p_mcalh_authority(*, repo_root: Path) -> dict[str, Any]:
    """Reconstruct the published MCALH H/P authority and its transitive base."""

    if (
        mcal._single_parent(repo_root, H_MCALH_COMMIT, context="H-E0-MCALH")
        != H_MCALH_PARENT
    ):
        raise _error("E0-MCALI historical H-E0-MCALH parent drifted")
    h_scope = mcal._git_scope(repo_root, H_MCALH_PARENT, H_MCALH_COMMIT)
    if h_scope != {
        "added": 5,
        "modified": 4,
        "deleted": 0,
        "path_count": 9,
        "paths": list(mcalh.PATCH_PATHS),
    }:
        raise _error("E0-MCALI historical H-E0-MCALH scope drifted")
    if (
        mcal._single_parent(repo_root, BASE_P_MCALH_COMMIT, context="P-E0-MCALH")
        != H_MCALH_COMMIT
    ):
        raise _error("E0-MCALI historical P-E0-MCALH parent drifted")
    p_scope = mcal._git_scope(repo_root, H_MCALH_COMMIT, BASE_P_MCALH_COMMIT)
    if p_scope != {
        "added": 2,
        "modified": 0,
        "deleted": 0,
        "path_count": 2,
        "paths": sorted(P_MCALH_PATHS),
    }:
        raise _error("E0-MCALI historical P-E0-MCALH scope drifted")

    h_components = [
        _git_record_at_commit(
            path,
            role="final_calibration_observed_risk_precision_patch_component",
            commit=H_MCALH_COMMIT,
            repo_root=repo_root,
        )
        for path in mcalh.PATCH_PATHS
    ]
    preserved: list[dict[str, Any]] = []
    for path in H_MCALH_PRESERVED_PATHS:
        record = _git_record_at_commit(
            path,
            role="preserved_h_mcalh_component",
            commit=H_MCALH_COMMIT,
            repo_root=repo_root,
        )
        physical = mcal._git_artifact_record(
            Path(path),
            role="preserved_h_mcalh_component",
            repo_root=repo_root,
            commit=H_MCALH_COMMIT,
        )
        if physical != record:
            raise _error(f"E0-MCALI preserved H-MCALH component drifted: {path}")
        preserved.append(record)
    historical = [
        {
            **_git_record_at_commit(
                path,
                role="superseded_h_mcalh_component",
                commit=H_MCALH_COMMIT,
                repo_root=repo_root,
            ),
            "commit": H_MCALH_COMMIT,
        }
        for path in H_MCALH_SUPERSEDED_PATHS
    ]
    p_components: list[dict[str, Any]] = []
    for path in P_MCALH_PATHS:
        role = (
            "published_p_mcalh_lock"
            if path == mcalh.DEFAULT_PATCH_LOCK_PATH.as_posix()
            else "published_p_mcalh_lock_manifest"
        )
        record = _git_record_at_commit(
            path,
            role=role,
            commit=BASE_P_MCALH_COMMIT,
            repo_root=repo_root,
        )
        physical = mcal._git_artifact_record(
            Path(path),
            role=role,
            repo_root=repo_root,
            commit=BASE_P_MCALH_COMMIT,
        )
        if physical != record:
            raise _error(f"E0-MCALI published P-MCALH component drifted: {path}")
        p_components.append(record)

    lock_bytes = mcal._git_blob_bytes(
        repo_root, BASE_P_MCALH_COMMIT, mcalh.DEFAULT_PATCH_LOCK_PATH
    )
    companion_bytes = mcal._git_blob_bytes(
        repo_root,
        BASE_P_MCALH_COMMIT,
        mcalh.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
    )
    try:
        lock_payload = mcal._parse_json_bytes(
            lock_bytes, context="published P-E0-MCALH lock"
        )
        companion = mcal._parse_json_bytes(
            companion_bytes, context="published P-E0-MCALH companion"
        )
    except mcalh.FinalCalibrationError as exc:
        raise _error("E0-MCALI historical P-E0-MCALH JSON drifted") from exc
    if (
        not isinstance(lock_payload, Mapping)
        or not isinstance(companion, Mapping)
        or lock_bytes != mcalh._canonical_json_bytes(lock_payload)
        or companion_bytes != mcalh._canonical_json_bytes(companion)
        or lock_payload.get("gate") != mcalh.PATCH_GATE
        or cast(Mapping[str, Any], lock_payload.get("repository", {})).get(
            "h_patch_head"
        )
        != H_MCALH_COMMIT
    ):
        raise _error("E0-MCALI historical P-E0-MCALH payload drifted")
    try:
        prior_schema = mcal._load_json_object(
            mcalh.DEFAULT_PATCH_LOCK_SCHEMA, repo_root=repo_root
        )
        mcal.validate_json_schema(lock_payload, prior_schema)
        mcalh._validate_timestamp(lock_payload.get("generated_at_utc"))
        mcalh._validate_verification(
            lock_payload.get("verification"), repo_root=repo_root
        )
        prior_state = mcalh._state_for_h(
            repository={
                "base_p_mcalg_commit": H_MCALH_PARENT,
                "h_patch_head": H_MCALH_COMMIT,
                "branch": "main",
                "remote_head": H_MCALH_COMMIT,
                "scope": h_scope,
            },
            h_patch={
                "gate": "H-E0-MCALH",
                "component_count": 9,
                "added_count": 5,
                "modified_count": 4,
                "components": h_components,
                "components_sha256": mcal._digest_records(h_components),
            },
            repo_root=repo_root,
            require_empty_namespace=False,
        )
        expected_prior = mcalh.build_final_calibration_observed_risk_precision_patch_lock_payload(
            prior_state,
            cast(Mapping[str, Any], lock_payload["verification"]),
            generated_at_utc=cast(str, lock_payload["generated_at_utc"]),
        )
    except (KeyError, mcalh.FinalCalibrationError) as exc:
        raise _error("E0-MCALI historical P-E0-MCALH authority drifted") from exc
    if _canonical_json_bytes(lock_payload) != _canonical_json_bytes(expected_prior):
        raise _error("E0-MCALI historical P-E0-MCALH reconstruction drifted")
    lock_record = {
        "role": "final_calibration_observed_risk_precision_patch_lock",
        "path": mcalh.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "bytes": len(lock_bytes),
        "sha256": _sha256_bytes(lock_bytes),
    }
    if companion_bytes != mcalh._canonical_json_bytes(
        mcalh._expected_companion(lock_payload, lock_record)
    ):
        raise _error("E0-MCALI historical P-E0-MCALH companion drifted")
    transitive = mcalh._p_mcalg_authority(repo_root=repo_root)
    if _canonical_json_bytes(lock_payload.get("p_mcalg_authority")) != (
        _canonical_json_bytes(transitive)
    ):
        raise _error("E0-MCALI transitive P-E0-MCALG authority drifted")
    sealed_runtime = lock_payload.get("runtime")
    if not isinstance(sealed_runtime, Mapping):
        raise _error("E0-MCALI historical P-E0-MCALH runtime binding is absent")
    return {
        "gate": "P-E0-MCALH",
        "commit": BASE_P_MCALH_COMMIT,
        "parent_h_mcalh": H_MCALH_COMMIT,
        "h_mcalh_parent": H_MCALH_PARENT,
        "h_scope": h_scope,
        "p_scope": p_scope,
        "h_component_count": 9,
        "h_components": h_components,
        "h_components_sha256": mcal._digest_records(h_components),
        "preserved_count": 5,
        "preserved_components": preserved,
        "preserved_components_sha256": mcal._digest_records(preserved),
        "superseded_count": 4,
        "historical_inputs": historical,
        "historical_inputs_sha256": mcal._digest_records(historical),
        "p_component_count": 2,
        "p_components": p_components,
        "p_components_sha256": mcal._digest_records(p_components),
        "lock_payload_sha256": _sha256_bytes(lock_bytes),
        "companion_sha256": _sha256_bytes(companion_bytes),
        "manifest_written_last": companion.get("manifest_written_last") is True,
        "sealed_runtime": _deep_copy(sealed_runtime),
    }


def _candidate_status_is_exact(repo_root: Path) -> bool:
    records = mcal._workspace_status_records(repo_root)
    if {path for _, path in records} != set(PATCH_PATHS):
        return False
    by_path = {path: code for code, path in records}
    return all(
        by_path[path]
        in (
            {" M", "M ", "MM"}
            if path in H_MCALH_SUPERSEDED_PATHS
            else {"??", "A "}
        )
        for path in PATCH_PATHS
    )


def _h_patch_authority(
    *, repo_root: Path, verify_remote: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    if type(verify_remote) is not bool:
        raise _error("E0-MCALI remote policy must be an exact boolean")
    head = mcal._git_head(repo_root)
    branch = cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
    if branch != "main":
        raise _error("E0-MCALI requires branch main")
    expected_scope = {
        "added": 5,
        "modified": 4,
        "deleted": 0,
        "path_count": 9,
        "paths": list(PATCH_PATHS),
    }
    candidate = head == BASE_P_MCALH_COMMIT
    if candidate:
        if not _candidate_status_is_exact(repo_root):
            raise _error("E0-MCALI candidate workspace is not exact 4M+5A")
        component_commit: str | None = None
        h_head = BASE_P_MCALH_COMMIT
        scope = expected_scope
    else:
        if (
            mcal._single_parent(repo_root, head, context="H-E0-MCALI")
            != BASE_P_MCALH_COMMIT
        ):
            raise _error("E0-MCALI published H parent drifted")
        scope = mcal._git_scope(repo_root, BASE_P_MCALH_COMMIT, head)
        if scope != expected_scope or mcal._workspace_status_records(repo_root):
            raise _error("E0-MCALI published H scope/worktree drifted")
        component_commit = head
        h_head = head
    components = [
        mcal._git_artifact_record(
            Path(path),
            role="final_calibration_owned_run_guard_revalidation_patch_component",
            repo_root=repo_root,
            commit=component_commit,
        )
        for path in PATCH_PATHS
    ]
    tracking = mcal._git_head(repo_root, "origin/main")
    expected_ref = BASE_P_MCALH_COMMIT if candidate else head
    if tracking != expected_ref:
        raise _error("E0-MCALI H tracking ref drifted")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if remote != expected_ref:
        raise _error("E0-MCALI H remote ref drifted")
    return (
        {
            "base_p_mcalh_commit": BASE_P_MCALH_COMMIT,
            "h_patch_head": h_head,
            "branch": branch,
            "remote_head": remote,
            "scope": scope,
        },
        {
            "gate": "H-E0-MCALI",
            "component_count": 9,
            "added_count": 5,
            "modified_count": 4,
            "components": components,
            "components_sha256": mcal._digest_records(components),
        },
    )


def _namespace_paths() -> tuple[Path, ...]:
    forbidden_finals = (
        mcal.DEFAULT_PATCH_LOCK_PATH,
        mcal.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        DEFAULT_PATCH_LOCK_PATH,
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        *R_OUTPUT_PATHS,
    )
    temporary_bases = (
        *forbidden_finals,
        mcalh.mcale.mcalp.DEFAULT_PATCH_LOCK_PATH,
        mcalh.mcale.mcalp.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        mcalh.mcale.mcalc.DEFAULT_PATCH_LOCK_PATH,
        mcalh.mcale.mcalc.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        mcalh.mcale.mcald.DEFAULT_PATCH_LOCK_PATH,
        mcalh.mcale.mcald.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        mcalh.mcale.DEFAULT_PATCH_LOCK_PATH,
        mcalh.mcale.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        mcalh.DEFAULT_PATCH_LOCK_PATH,
        mcalh.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
    )
    return (
        *forbidden_finals,
        *(mcal._temporary_path(path) for path in temporary_bases),
        mcal.LOCKER_GUARD_PATH,
        mcalh.mcale.mcalp.LOCKER_GUARD_PATH,
        mcalh.mcale.mcalc.LOCKER_GUARD_PATH,
        mcalh.mcale.mcald.LOCKER_GUARD_PATH,
        mcalh.mcale.LOCKER_GUARD_PATH,
        mcalh.LOCKER_GUARD_PATH,
        LOCKER_GUARD_PATH,
        mcal.CALIBRATION_GUARD_PATH,
        mcal.E7_GUARD_PATH,
    )


def _require_prelock_namespace(*, repo_root: Path) -> None:
    missing_base = [
        path.as_posix()
        for path in (
            mcalh.DEFAULT_PATCH_LOCK_PATH,
            mcalh.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        )
        if not mcal._entry_exists(path, repo_root=repo_root)
    ]
    if missing_base:
        raise _error(f"E0-MCALI base P-MCALH authority is absent: {missing_base}")
    occupied = [
        path.as_posix()
        for path in _namespace_paths()
        if mcal._entry_exists(path, repo_root=repo_root)
    ]
    if occupied:
        raise _error(f"E0-MCALI prelock namespace is occupied: {occupied}")
    if mcal._entry_exists(Path(mcal.mze.OUTCOME_ACCESS_LOG), repo_root=repo_root):
        raise _error("E0-MCALI outcome access log must remain absent")
    if any(
        mcal._entry_exists(Path(path), repo_root=repo_root)
        for path in mcal.mze.E0_M_PATHS
    ):
        raise _error("E0-MCALI final E0-M namespace must remain absent")


@_error_boundary
def preflight_final_calibration_owned_run_guard_revalidation_patch_schema(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    schema = mcalh.mcale.mcalp.mcal._load_json_object(
        DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root
    )
    validator = getattr(
        mcalh.mcale.mcalp.mcal.closure_contract, "_assert_supported_json_schema", None
    )
    if validator is None:
        raise _error("E0-MCALI closed schema preflight is unavailable")
    try:
        validator(schema)
    except mcalh.mcale.mcalp.mcal.ClosureContractError as exc:
        raise _error(str(exc)) from exc
    return {
        "status": "schema_ready",
        "gate": PATCH_GATE,
        "schema_count": 1,
        "schemas": [
            mcalh.mcale.mcalp.mcal._file_record(
                DEFAULT_PATCH_LOCK_SCHEMA,
                role="final_calibration_owned_run_guard_revalidation_patch_lock_schema",
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
    require_empty_namespace: bool,
) -> dict[str, Any]:
    schema_preflight = preflight_final_calibration_owned_run_guard_revalidation_patch_schema(
        repo_root=repo_root
    )
    runtime = mcal.load_and_validate_final_calibration_runtime(repo_root=repo_root)
    p_mcalh = _p_mcalh_authority(repo_root=repo_root)
    scientific_inputs = mcal._scientific_input_inventory(repo_root=repo_root)
    if require_empty_namespace:
        _require_prelock_namespace(repo_root=repo_root)
    sealed_runtime = cast(Mapping[str, Any], p_mcalh["sealed_runtime"])
    h_components = cast(Sequence[Mapping[str, Any]], h_patch["components"])
    runtime_contract = {
        "physical_input_count": EXPECTED_COMPANION_INPUT_COUNT,
        "historical_input_count": EXPECTED_HISTORICAL_INPUT_COUNT,
        "runtime": _deep_copy(sealed_runtime["runtime"]),
        "runtime_schema": _deep_copy(sealed_runtime["runtime_schema"]),
        "lock_schema": _deep_copy(
            next(
                record
                for record in h_components
                if record["path"] == DEFAULT_PATCH_LOCK_SCHEMA.as_posix()
            )
        ),
        "runtime_payload_sha256": _sha256_bytes(_canonical_json_bytes(runtime)),
        "scientific_authority_record_count": scientific_inputs[
            "authority_record_count"
        ],
        "scientific_payload_binding_count": scientific_inputs["payload_binding_count"],
        "scientific_authority_records_sha256": scientific_inputs[
            "authority_records_sha256"
        ],
        "scientific_payload_bindings_sha256": scientific_inputs[
            "payload_bindings_sha256"
        ],
        "supported_schema_subset_verified": schema_preflight[
            "supported_subset_verified"
        ],
        "raw_score_candidate_values": _deep_copy(
            sealed_runtime["raw_score_candidate_values"]
        ),
        "raw_score_data_rewrite_authorized": False,
        "raw_exclusion_evidence_contract": _deep_copy(
            sealed_runtime["raw_exclusion_evidence_contract"]
        ),
        "ordinal_label_representation_contract": _deep_copy(
            sealed_runtime["ordinal_label_representation_contract"]
        ),
        "observed_risk_precision_contract": _deep_copy(
            sealed_runtime["observed_risk_precision_contract"]
        ),
        "owned_run_guard_revalidation_contract": _deep_copy(
            OWNED_RUN_GUARD_REVALIDATION_CONTRACT
        ),
    }
    boundary = {
        **_deep_copy(runtime["scientific_boundary"]),
        "calibration_protocol": _deep_copy(runtime["calibration_protocol"]),
        "holdout_row_count": 0,
        "post_2021_row_count": 0,
        "outcome_path_count": 0,
        "evaluation_batch_authorized": False,
    }
    prelock = {
        "git_status_clean": True,
        "base_p_mcalh_output_present_count": 2,
        "p_output_present_count": 0,
        "r_output_present_count": 0,
        "temporary_present_count": 0,
        "coordination_present_count": 0,
        "outcome_access_log_absent": True,
        "holdout_rows_opened": False,
        "post_2021_rows_opened": False,
        "dvc_commands_run": False,
        "scientific_writes_performed": False,
        "failed_attempt_retry_authorized": False,
        "companion_contract": {
            "physical_input_count": EXPECTED_COMPANION_INPUT_COUNT,
            "historical_input_count": EXPECTED_HISTORICAL_INPUT_COUNT,
            "output_count": EXPECTED_COMPANION_OUTPUT_COUNT,
            "script_path": LOCKER_PATH.as_posix(),
            "manifest_written_last": True,
        },
    }
    return {
        "repository": _deep_copy(repository),
        "failed_attempt": _deep_copy(FAILED_ATTEMPT),
        "p_mcalh_authority": p_mcalh,
        "h_patch": _deep_copy(h_patch),
        "runtime": runtime_contract,
        "owned_run_guard_revalidation_contract": _deep_copy(
            OWNED_RUN_GUARD_REVALIDATION_CONTRACT
        ),
        "scientific_input_inventory": scientific_inputs,
        "scientific_boundary": boundary,
        "model_matrix": _deep_copy(runtime["model_matrix"]),
        "calibration_group_matrix": _deep_copy(runtime["calibration_group_matrix"]),
        "e7_terminal_record": _deep_copy(runtime["e7_terminal_record"]),
        "output_contract": mcal._output_contract(runtime),
        "prelock": prelock,
    }


@_error_boundary
def collect_final_calibration_owned_run_guard_revalidation_patch_prelock_state(
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
        require_empty_namespace=True,
    )


def _default_unrun_verification() -> dict[str, Any]:
    return {
        "status": "not_run_by_payload_builder",
        "commands_run": False,
        "scientific_execution_run": False,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
    }


@_error_boundary
def build_final_calibration_owned_run_guard_revalidation_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any] | None = None,
    *,
    generated_at_utc: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root
    required = {
        "repository",
        "failed_attempt",
        "p_mcalh_authority",
        "h_patch",
        "runtime",
        "owned_run_guard_revalidation_contract",
        "scientific_input_inventory",
        "scientific_boundary",
        "model_matrix",
        "calibration_group_matrix",
        "e7_terminal_record",
        "output_contract",
        "prelock",
    }
    if set(prelock) != required:
        raise _error("E0-MCALI prelock dialect drifted")
    timestamp = generated_at_utc or datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": LOCK_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "status": "locked_unpublished",
        "generated_at_utc": timestamp,
        "repository": _deep_copy(prelock["repository"]),
        "failed_attempt": _deep_copy(prelock["failed_attempt"]),
        "p_mcalh_authority": _deep_copy(prelock["p_mcalh_authority"]),
        "h_patch": _deep_copy(prelock["h_patch"]),
        "runtime": _deep_copy(prelock["runtime"]),
        "owned_run_guard_revalidation_contract": _deep_copy(
            prelock["owned_run_guard_revalidation_contract"]
        ),
        "scientific_input_inventory": _deep_copy(
            prelock["scientific_input_inventory"]
        ),
        "scientific_boundary": _deep_copy(prelock["scientific_boundary"]),
        "model_matrix": _deep_copy(prelock["model_matrix"]),
        "calibration_group_matrix": _deep_copy(prelock["calibration_group_matrix"]),
        "e7_terminal_record": _deep_copy(prelock["e7_terminal_record"]),
        "output_contract": _deep_copy(prelock["output_contract"]),
        "prelock": _deep_copy(prelock["prelock"]),
        "verification": _deep_copy(
            verification if verification is not None else _default_unrun_verification()
        ),
        "authorizations": dict(UNPUBLISHED_AUTHORIZATIONS),
    }


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise _error("E0-MCALI generated timestamp is absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _error("E0-MCALI generated timestamp is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _error("E0-MCALI generated timestamp must be timezone-aware")


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
        raise _error("E0-MCALI verification evidence dialect drifted")
    if _canonical_json_bytes(value["schema_preflight"]) != _canonical_json_bytes(
        preflight_final_calibration_owned_run_guard_revalidation_patch_schema(repo_root=repo_root)
    ):
        raise _error("E0-MCALI schema verification evidence drifted")
    for key, command in (
        ("full_type_check", TYPE_CHECK_COMMAND),
        ("poetry_check", POETRY_CHECK_COMMAND),
        ("publication_guard", PUBLICATION_GUARD_COMMAND),
        ("git_diff_check", DIFF_CHECK_COMMAND),
    ):
        try:
            mcal._validate_command_evidence(
                value[key], expected_command=command, context=key
            )
        except mcalh.FinalCalibrationError as exc:
            raise _error(str(exc).replace("E0-MCAL", "E0-MCALI")) from exc
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
        or type(focused.get("test_count")) is not int
        or focused.get("test_count") != FOCUSED_TEST_COUNT
        or type(focused.get("skipped_count")) is not int
        or focused.get("skipped_count") != 0
        or type(focused.get("deselected_count")) is not int
        or focused.get("deselected_count") != 0
    ):
        raise _error("E0-MCALI focused verification evidence drifted")
    try:
        mcal._validate_command_evidence(
            {key: focused[key] for key in base_keys},
            expected_command=FOCUSED_TEST_COMMAND,
            context="focused_tests",
        )
    except mcalh.FinalCalibrationError as exc:
        raise _error(str(exc).replace("E0-MCAL", "E0-MCALI")) from exc


@_error_boundary
def validate_final_calibration_owned_run_guard_revalidation_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    verify_remote: bool = False,
) -> dict[str, Any]:
    root = _root(repo_root)
    if not isinstance(payload, Mapping):
        raise _error("E0-MCALI lock payload must be an object")
    schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    try:
        mcal.validate_json_schema(payload, schema)
    except mcal.ClosureContractError as exc:
        raise _error(str(exc)) from exc
    _validate_timestamp(payload.get("generated_at_utc"))
    _validate_verification(payload.get("verification"), repo_root=root)
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise _error("E0-MCALI unpublished authorizations drifted")
    state = collect_final_calibration_owned_run_guard_revalidation_patch_prelock_state(
        verify_remote=verify_remote, repo_root=root
    )
    expected = build_final_calibration_owned_run_guard_revalidation_patch_lock_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=cast(str, payload["generated_at_utc"]),
    )
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("E0-MCALI lock semantic reconstruction drifted")
    return dict(payload)


_OwnedOutput = mcalh._OwnedOutput


def _publish_bytes_no_clobber(
    final_path: Path, payload: bytes, *, repo_root: Path
) -> _OwnedOutput:
    try:
        return mcalh._publish_bytes_no_clobber(
            final_path, payload, repo_root=repo_root
        )
    except mcalh.FinalCalibrationError as exc:
        raise _error(str(exc).replace("E0-MCALH", "E0-MCALI")) from exc


def _rollback_owned_output(output: _OwnedOutput) -> None:
    try:
        mcalh._rollback_owned_output(output)
    except mcalh.FinalCalibrationError as exc:
        raise _error(str(exc).replace("E0-MCALH", "E0-MCALI")) from exc


def _close_owned_output(output: _OwnedOutput) -> None:
    try:
        mcalh._close_owned_output(output)
    except mcalh.FinalCalibrationError as exc:
        raise _error(str(exc).replace("E0-MCALH", "E0-MCALI")) from exc


def _public_artifact_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in ("role", "path", "bytes", "sha256")}


def _expected_companion(
    payload: Mapping[str, Any], lock_record: Mapping[str, Any]
) -> dict[str, Any]:
    base = cast(Mapping[str, Any], payload["p_mcalh_authority"])
    patch = cast(Mapping[str, Any], payload["h_patch"])
    preserved = cast(Sequence[Mapping[str, Any]], base["preserved_components"])
    p_components = cast(Sequence[Mapping[str, Any]], base["p_components"])
    current = cast(Sequence[Mapping[str, Any]], patch["components"])
    historical = cast(Sequence[Mapping[str, Any]], base["historical_inputs"])
    inputs = [
        _public_artifact_record(record)
        for record in (*preserved, *p_components, *current)
    ]
    inputs.sort(key=lambda record: cast(str, record["path"]))
    if (
        len(inputs) != EXPECTED_COMPANION_INPUT_COUNT
        or len({record["path"] for record in inputs})
        != EXPECTED_COMPANION_INPUT_COUNT
    ):
        raise _error("E0-MCALI companion physical input set drifted")
    historical_inputs = [dict(record) for record in historical]
    historical_inputs.sort(key=lambda record: cast(str, record["path"]))
    script = next(
        record for record in inputs if record["path"] == LOCKER_PATH.as_posix()
    )
    return {
        "schema_version": COMPANION_SCHEMA_VERSION,
        "status": "completed",
        "gate": PATCH_GATE,
        "script": script,
        "inputs": inputs,
        "historical_inputs": historical_inputs,
        "outputs": [dict(lock_record)],
        "manifest_written_last": True,
        "scientific_execution_run": False,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
    }


def _require_publication_verification(
    payload: Mapping[str, Any], *, repo_root: Path
) -> None:
    verification = payload.get("verification")
    if verification == _default_unrun_verification():
        raise _error(
            "E0-MCALI publication requires the exact frozen verification evidence"
        )
    _validate_verification(verification, repo_root=repo_root)


def _physical_snapshot(
    repo_root: Path, *, scientific_inventory: Mapping[str, Any]
) -> tuple[dict[str, Any], ...]:
    records = [
        dict(record)
        for record in mcalh._physical_snapshot(
            repo_root, scientific_inventory=scientific_inventory
        )
    ]
    known = {cast(str, record["path"]) for record in records}
    current_paths = [*H_MCALH_PRESERVED_PATHS, *P_MCALH_PATHS, *PATCH_PATHS]
    current_paths.extend(
        path.as_posix()
        for path in R_OUTPUT_PATHS
        if mcal._entry_exists(path, repo_root=repo_root)
    )
    for path_text in current_paths:
        if path_text in known:
            continue
        path = Path(path_text)
        payload, metadata = mcal._read_regular_bytes_and_metadata(
            path, repo_root=repo_root
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
    return tuple(records)


def _require_physical_snapshot(
    expected: Sequence[Mapping[str, Any]],
    *,
    scientific_inventory: Mapping[str, Any],
    repo_root: Path,
    context: str,
) -> None:
    if _canonical_json_bytes(expected) != _canonical_json_bytes(
        _physical_snapshot(repo_root, scientific_inventory=scientific_inventory)
    ):
        raise _error(f"E0-MCALI physical authority changed {context}")


def _validate_owned_output_bytes(
    output: _OwnedOutput,
    expected: bytes,
    *,
    repo_root: Path,
    context: str,
) -> os.stat_result:
    try:
        mcalh._validate_owned_output(output)
        payload, metadata = mcal._read_regular_bytes_and_metadata(
            output.path, repo_root=repo_root
        )
    except Exception as exc:
        raise _error(f"E0-MCALI owned output validation failed {context}") from exc
    if (
        payload != expected
        or (metadata.st_dev, metadata.st_ino) != (output.device, output.inode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o644
    ):
        raise _error(
            f"E0-MCALI owned output drifted {context}: {output.path.as_posix()}"
        )
    return metadata


def _rollback_outputs_best_effort(
    outputs: Sequence[_OwnedOutput],
) -> FinalCalibrationOwnedRunGuardRevalidationPatchError | None:
    errors: list[BaseException] = []
    for output in reversed(outputs):
        try:
            _rollback_owned_output(output)
        except BaseException as exc:
            errors.append(exc)
    if not errors:
        return None
    error = _error("E0-MCALI owned-output rollback was incomplete")
    for nested in errors:
        error.add_note(str(nested))
    return error


def _require_owned_guard_identity(guard: Any) -> None:
    try:
        parent = os.fstat(guard.parent_descriptor)
        lexical_parent = guard.lexical_parent.lstat()
        opened = os.fstat(guard.file_descriptor)
        named = mt._named_identity(guard.parent_descriptor, guard.name)
    except (AttributeError, OSError) as exc:
        raise _error("E0-MCALI publication guard identity check failed") from exc
    if (
        not stat.S_ISDIR(parent.st_mode)
        or (parent.st_dev, parent.st_ino)
        != (guard.parent_device, guard.parent_inode)
        or not stat.S_ISDIR(lexical_parent.st_mode)
        or (lexical_parent.st_dev, lexical_parent.st_ino)
        != (guard.parent_device, guard.parent_inode)
        or not stat.S_ISREG(opened.st_mode)
        or (opened.st_dev, opened.st_ino) != (guard.device, guard.inode)
        or named != (guard.device, guard.inode)
    ):
        raise _error("E0-MCALI publication guard identity drifted")


def _require_publication_boundary(
    *, repo_root: Path, owned_guard: Any | None, outputs_present: bool
) -> None:
    missing_base = [
        path.as_posix()
        for path in (
            mcalh.DEFAULT_PATCH_LOCK_PATH,
            mcalh.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        )
        if not mcal._entry_exists(path, repo_root=repo_root)
    ]
    if missing_base:
        raise _error(f"E0-MCALI base P-MCALH authority is absent: {missing_base}")
    allowed = (
        {DEFAULT_PATCH_LOCK_PATH, DEFAULT_PATCH_LOCK_MANIFEST_PATH}
        if outputs_present
        else set()
    )
    if owned_guard is not None:
        _require_owned_guard_identity(owned_guard)
        allowed.add(LOCKER_GUARD_PATH)
    occupied = [
        path.as_posix()
        for path in _namespace_paths()
        if path not in allowed
        if mcal._entry_exists(path, repo_root=repo_root)
    ]
    if occupied:
        raise _error(f"E0-MCALI publication namespace is occupied: {occupied}")
    if mcal._entry_exists(Path(mcal.mze.OUTCOME_ACCESS_LOG), repo_root=repo_root):
        raise _error("E0-MCALI outcome access log must remain absent")
    if any(
        mcal._entry_exists(Path(path), repo_root=repo_root)
        for path in mcal.mze.E0_M_PATHS
    ):
        raise _error("E0-MCALI final E0-M namespace must remain absent")


def _require_repository_checkpoint(
    *,
    repo_root: Path,
    expected_head: str,
    verify_remote: bool,
    expected_untracked_paths: Sequence[Path],
    context: str,
) -> None:
    branch = cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
    head = mcal._git_head(repo_root)
    tracking = mcal._git_head(repo_root, "origin/main")
    expected_status = sorted(
        ("??", path.as_posix()) for path in expected_untracked_paths
    )
    status = sorted(mcal._workspace_status_records(repo_root))
    if (
        branch != "main"
        or head != expected_head
        or tracking != expected_head
        or status != expected_status
    ):
        raise _error(f"E0-MCALI repository changed {context}")
    if verify_remote and mcal._live_remote_main_head(repo_root) != expected_head:
        raise _error(f"E0-MCALI live remote changed {context}")


def _metadata_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


@_error_boundary
def publish_final_calibration_owned_run_guard_revalidation_patch_lock_bundle(
    payload: Mapping[str, Any], *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _root(repo_root)
    try:
        lock_bytes = _canonical_json_bytes(payload)
        frozen_payload = json.loads(lock_bytes)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise _error("E0-MCALI publication payload is not canonical JSON") from exc
    if (
        not isinstance(frozen_payload, dict)
        or _canonical_json_bytes(frozen_payload) != lock_bytes
    ):
        raise _error("E0-MCALI publication payload must be a canonical object")
    payload = frozen_payload
    repository = payload.get("repository")
    if (
        not isinstance(repository, Mapping)
        or repository.get("h_patch_head") == BASE_P_MCALH_COMMIT
    ):
        raise _error("E0-MCALI H must be published before P publication")
    _require_publication_verification(payload, repo_root=root)
    validate_final_calibration_owned_run_guard_revalidation_patch_lock_payload(
        payload, repo_root=root, verify_remote=True
    )
    inventory = payload.get("scientific_input_inventory")
    if not isinstance(inventory, Mapping):
        raise _error("E0-MCALI scientific inventory is absent")
    snapshot = _physical_snapshot(root, scientific_inventory=inventory)
    initial_head = mcal._git_head(root)
    if initial_head != repository.get("h_patch_head"):
        raise _error("E0-MCALI H refs drifted before publication")
    validate_final_calibration_owned_run_guard_revalidation_patch_lock_payload(
        payload, repo_root=root, verify_remote=True
    )
    _require_physical_snapshot(
        snapshot,
        scientific_inventory=inventory,
        repo_root=root,
        context="after semantic baseline recapture",
    )
    _require_repository_checkpoint(
        repo_root=root,
        expected_head=initial_head,
        verify_remote=True,
        expected_untracked_paths=(),
        context="during semantic baseline recapture",
    )
    _require_prelock_namespace(repo_root=root)
    guard: Any | None = None
    published: list[_OwnedOutput] = []
    committed = False
    try:
        try:
            guard = mt._acquire_publication_guard(
                LOCKER_GUARD_PATH,
                b"E0-MCALI final calibration owned run guard lock publication\n",
                repo_root=root,
            )
        except Exception as exc:
            raise _error("E0-MCALI publication guard acquisition failed") from exc
        _require_physical_snapshot(
            snapshot,
            scientific_inventory=inventory,
            repo_root=root,
            context="after guard acquisition",
        )
        _require_publication_boundary(
            repo_root=root, owned_guard=guard, outputs_present=False
        )
        _require_repository_checkpoint(
            repo_root=root,
            expected_head=initial_head,
            verify_remote=True,
            expected_untracked_paths=(),
            context="after guard acquisition",
        )
        lock_output = _publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_PATH, lock_bytes, repo_root=root
        )
        published.append(lock_output)
        lock_record = {
            "role": "final_calibration_owned_run_guard_revalidation_patch_lock",
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "bytes": len(lock_bytes),
            "sha256": _sha256_bytes(lock_bytes),
        }
        companion = _expected_companion(payload, lock_record)
        companion_bytes = _canonical_json_bytes(companion)
        companion_output = _publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH, companion_bytes, repo_root=root
        )
        published.append(companion_output)
        publication_set = (
            (lock_output, lock_bytes),
            (companion_output, companion_bytes),
        )
        for output, expected in publication_set:
            _validate_owned_output_bytes(
                output,
                expected,
                repo_root=root,
                context="after companion publication",
            )
        _require_physical_snapshot(
            snapshot,
            scientific_inventory=inventory,
            repo_root=root,
            context="after companion publication",
        )
        _require_publication_boundary(
            repo_root=root, owned_guard=guard, outputs_present=True
        )
        expected_p = (DEFAULT_PATCH_LOCK_PATH, DEFAULT_PATCH_LOCK_MANIFEST_PATH)
        _require_repository_checkpoint(
            repo_root=root,
            expected_head=initial_head,
            verify_remote=True,
            expected_untracked_paths=expected_p,
            context="during publication",
        )
        try:
            mt._release_publication_guard(guard)
        except Exception as exc:
            raise _error("E0-MCALI publication guard release failed") from exc
        guard = None
        post_release_metadata = {
            output.path: _validate_owned_output_bytes(
                output,
                expected,
                repo_root=root,
                context="after guard release",
            )
            for output, expected in publication_set
        }
        for pass_index in (1, 2):
            _require_repository_checkpoint(
                repo_root=root,
                expected_head=initial_head,
                verify_remote=True,
                expected_untracked_paths=expected_p,
                context=f"during joint ownership transfer pass {pass_index}",
            )
            _require_physical_snapshot(
                snapshot,
                scientific_inventory=inventory,
                repo_root=root,
                context=f"during joint ownership transfer pass {pass_index}",
            )
            _require_publication_boundary(
                repo_root=root, owned_guard=None, outputs_present=True
            )
            for output, expected in publication_set:
                observed = _validate_owned_output_bytes(
                    output,
                    expected,
                    repo_root=root,
                    context=f"joint ownership transfer pass {pass_index}",
                )
                if _metadata_identity(observed) != _metadata_identity(
                    post_release_metadata[output.path]
                ):
                    raise _error(
                        "E0-MCALI owned output changed before ownership transfer"
                    )
            mcalh._require_owned_identity_set(
                [output for output, _ in publication_set],
                context=f"joint ownership transfer pass {pass_index}",
            )
        _require_repository_checkpoint(
            repo_root=root,
            expected_head=initial_head,
            verify_remote=True,
            expected_untracked_paths=expected_p,
            context="at final ownership transfer checkpoint",
        )
        _require_physical_snapshot(
            snapshot,
            scientific_inventory=inventory,
            repo_root=root,
            context="at final ownership transfer checkpoint",
        )
        _require_publication_boundary(
            repo_root=root, owned_guard=None, outputs_present=True
        )
        for output, expected in publication_set:
            observed = _validate_owned_output_bytes(
                output,
                expected,
                repo_root=root,
                context="at final ownership transfer checkpoint",
            )
            if _metadata_identity(observed) != _metadata_identity(
                post_release_metadata[output.path]
            ):
                raise _error("E0-MCALI owned output changed at ownership transfer")
        mcalh._require_owned_identity_set(
            [output for output, _ in publication_set],
            context="final ownership transfer checkpoint",
        )
        committed = True
        return dict(payload), companion
    except BaseException as exc:
        rollback_error = _rollback_outputs_best_effort(published)
        if rollback_error is not None:
            exc.add_note(str(rollback_error))
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, FinalCalibrationOwnedRunGuardRevalidationPatchError):
            raise
        raise _error("E0-MCALI lock bundle publication failed") from exc
    finally:
        if guard is not None:
            try:
                mt._release_publication_guard(guard, tolerate_foreign=True)
            except Exception:
                pass
        if committed:
            for output in reversed(published):
                try:
                    _close_owned_output(output)
                except Exception:
                    pass


def _scientific_input_inventory(*, repo_root: Path) -> dict[str, Any]:
    return mcal._scientific_input_inventory(repo_root=repo_root)


def _validate_calibration_filter_evidence(value: Any) -> None:
    """Validate the inherited target projection and corrected raw exclusions."""

    if not isinstance(value, list) or len(value) != 5:
        raise _error("E0-MCALI calibration filter evidence cardinality drifted")
    target = value[0]
    integer_keys = {
        "materialized_row_count",
        "projected_complete_target_row_count",
        "outside_common_origin_projection_row_count",
        "boundary_crossing_rows",
        "holdout_rows_materialized",
        "development_site_count",
    }
    if (
        not isinstance(target, Mapping)
        or set(target) != set(TARGET_FILTER_EVIDENCE_CONTRACT)
        or any(type(target.get(key)) is not int for key in integer_keys)
        or any(
            type(target.get(key)) is not str
            for key in set(TARGET_FILTER_EVIDENCE_CONTRACT) - integer_keys
        )
        or dict(target) != TARGET_FILTER_EVIDENCE_CONTRACT
        or target["materialized_row_count"]
        != target["projected_complete_target_row_count"]
        + target["outside_common_origin_projection_row_count"]
    ):
        raise _error("E0-MCALI target filter evidence drifted")

    for raw, expected in zip(
        value[1:], RAW_EXCLUSION_EVIDENCE_CONTRACT, strict=True
    ):
        model_id = cast(str, expected["model_id"])
        candidate = cast(int, expected["candidate_row_count"])
        matched = cast(int, expected["matched_target_row_count"])
        excluded = cast(int, expected["excluded_incomplete_target_row_count"])
        if (
            not isinstance(raw, Mapping)
            or set(raw) != set(expected)
            or type(raw.get("model_id")) is not str
            or type(raw.get("source_path")) is not str
            or type(raw.get("candidate_row_count")) is not int
            or type(raw.get("matched_target_row_count")) is not int
            or type(raw.get("excluded_incomplete_target_row_count")) is not int
            or type(raw.get("excluded_target_keys_sha256")) is not str
            or dict(raw) != expected
            or candidate != matched + excluded
        ):
            raise _error(f"E0-MCALI raw exclusion evidence drifted: {model_id}")


def _validate_calibrator_specs(
    value: Any,
) -> dict[tuple[str, int, int], Mapping[str, Any]]:
    if not isinstance(value, Mapping) or value.get("gate") != PATCH_GATE:
        raise _error("E0-MCALI calibrator spec gate drifted")
    adapted = _deep_copy(value)
    adapted["gate"] = mcalh.PATCH_GATE
    try:
        return mcalh._validate_calibrator_specs(adapted)
    except mcalh.FinalCalibrationError as exc:
        raise _error(str(exc).replace("E0-MCALH", "E0-MCALI")) from exc


def _effective_authority_binding_sha256(
    *,
    repo_root: Path,
    scientific_inventory: Mapping[str, Any],
    p_patch_head: str | None = None,
    lock_record: Mapping[str, Any] | None = None,
) -> str:
    effective_head = mcal._git_head(repo_root) if p_patch_head is None else p_patch_head
    effective_lock = (
        mcal._file_record(
            DEFAULT_PATCH_LOCK_PATH,
            role="final_calibration_owned_run_guard_revalidation_patch_lock",
            repo_root=repo_root,
        )
        if lock_record is None
        else lock_record
    )
    return _sha256_bytes(
        _canonical_json_bytes(
            {
                "gate": PATCH_GATE,
                "p_patch_head": effective_head,
                "lock_sha256": effective_lock["sha256"],
                "scientific_authority_records_sha256": scientific_inventory[
                    "authority_records_sha256"
                ],
                "scientific_payload_bindings_sha256": scientific_inventory[
                    "payload_bindings_sha256"
                ],
            }
        )
    )


def _require_exact_output_group(
    paths: Sequence[Path],
    *,
    manifest_path: Path,
    repo_root: Path,
    context: str,
) -> int:
    present = [path for path in paths if mcal._entry_exists(path, repo_root=repo_root)]
    if present and len(present) != len(paths):
        raise _error(f"E0-MCALI {context} output bundle is partial")
    if not present:
        return 0
    payloads: dict[Path, bytes] = {}
    metadata: dict[Path, os.stat_result] = {}
    json_values: dict[Path, Any] = {}
    for path in paths:
        payload, observed = mcal._read_regular_bytes_and_metadata(
            path, repo_root=repo_root
        )
        payloads[path] = payload
        metadata[path] = observed
        if path.suffix == ".json":
            value = mcal._parse_json_bytes(payload, context=path.as_posix())
            if payload != _canonical_json_bytes(value):
                raise _error(
                    f"E0-MCALI {context} JSON output is not canonical: "
                    f"{path.as_posix()}"
                )
            json_values[path] = value
    manifest = json_values.get(manifest_path)
    if not isinstance(manifest, Mapping):
        raise _error(f"E0-MCALI {context} manifest is absent")
    output_records = [
        {
            "path": path.as_posix(),
            "bytes": len(payloads[path]),
            "sha256": _sha256_bytes(payloads[path]),
        }
        for path in paths
        if path != manifest_path
    ]
    if manifest.get("outputs") != output_records:
        raise _error(f"E0-MCALI {context} manifest output bindings drifted")
    inventory = _scientific_input_inventory(repo_root=repo_root)
    expected_authority = _effective_authority_binding_sha256(
        repo_root=repo_root, scientific_inventory=inventory
    )
    boundary = {
        "development_only": True,
        "holdout_accessed": False,
        "post_2021_rows_accessed": False,
        "final_evaluation_run": False,
        "future_outcomes_accessed": False,
    }
    observed_boundary = manifest.get("scientific_boundary")
    if (
        not isinstance(observed_boundary, Mapping)
        or set(observed_boundary) != set(boundary)
        or any(type(observed_boundary.get(key)) is not bool for key in boundary)
        or dict(observed_boundary) != boundary
    ):
        raise _error(f"E0-MCALI {context} scientific boundary drifted")
    if context == "calibration":
        expected_keys = {
            "schema_version",
            "experiment_id",
            "gate",
            "status",
            "authority_sha256",
            "group_counts",
            "temporal_protocol",
            "inputs",
            "input_filter_evidence",
            "execution_policy",
            "outputs",
            "scientific_boundary",
        }
        if (
            set(manifest) != expected_keys
            or manifest.get("schema_version")
            != "closure_final_calibration_manifest_v1"
            or manifest.get("experiment_id") != EXPERIMENT_ID
            or manifest.get("gate") != PATCH_GATE
            or manifest.get("status") != "completed_unpublished"
            or manifest.get("authority_sha256") != expected_authority
            or not isinstance(manifest.get("group_counts"), Mapping)
            or any(
                type(cast(Mapping[str, Any], manifest["group_counts"]).get(key))
                is not int
                for key in ("bloom", "ordinal", "uncertainty", "q_c")
            )
            or manifest.get("group_counts")
            != {"bloom": 66, "ordinal": 33, "uncertainty": 30, "q_c": 90}
            or manifest.get("temporal_protocol")
            != {
                "fit": "2019",
                "assessment": "2020",
                "refit_threshold_cutpoint_q_c": "2021",
                "time_column": "target_year_month",
            }
            or manifest.get("inputs") != inventory["calibration_required_inputs"]
            or not isinstance(manifest.get("execution_policy"), Mapping)
        ):
            raise _error("E0-MCALI calibration manifest scientific dialect drifted")
        evidence = manifest.get("input_filter_evidence")
        if not isinstance(evidence, list):
            raise _error("E0-MCALI calibration input-filter evidence is absent")
        _validate_calibration_filter_evidence(evidence)
        execution = cast(Mapping[str, Any], manifest["execution_policy"])
        if (
            set(execution)
            != {
                "torch_cpu_execution_policy",
                "development_runtime_schema_version",
                "development_runtime_audit_sha256",
                "threadpool_limit",
            }
            or type(execution.get("threadpool_limit")) is not int
            or execution.get("threadpool_limit") != 1
            or execution.get("development_runtime_schema_version")
            != mcal.EXPECTED_DEVELOPMENT_RUNTIME_SCHEMA_VERSION
            or execution.get("development_runtime_audit_sha256")
            != mcal.EXPECTED_DEVELOPMENT_RUNTIME_AUDIT_SHA256
            or not mcalh._torch_policy_has_exact_integer_fields(
                execution.get("torch_cpu_execution_policy")
            )
        ):
            raise _error("E0-MCALI calibration execution policy drifted")
        try:
            mcal._validate_torch_cpu_execution_policy(
                execution.get("torch_cpu_execution_policy"), context="calibration"
            )
            calibrators = _validate_calibrator_specs(
                json_values.get(mcal.CALIBRATOR_SPECS_PATH)
            )
            mcal._validate_calibration_csv_outputs(payloads, calibrators=calibrators)
        except mcalh.FinalCalibrationError as exc:
            raise _error(str(exc).replace("E0-MCAL", "E0-MCALI")) from exc
    elif context == "E7":
        terminal = {
            "terminal_row_count": 15,
            "completed_slot_count": 5,
            "resource_failure_count": 10,
            "completed_module_fit_count": 15,
            "new_e7_fit_count": 15,
            "primary_fit_reuse_count": 0,
            "primary_slots_untouched": True,
            "saturation_claim_authorized": False,
            "post_hoc_substitution_performed": False,
            "silent_omission": False,
        }
        slot_order = [
            {"training_rows_per_module": size, "base_seed": seed}
            for size in (4096, 16384, 65536)
            for seed in mcal.REGISTERED_SEEDS
        ]
        evidence = manifest.get("terminal_evidence")
        expected_manifest_keys = {
            "schema_version",
            "experiment_id",
            "gate",
            "status",
            "authority_sha256",
            *terminal,
            "slot_order",
            "terminal_evidence",
            "inputs",
            "outputs",
            "scientific_boundary",
        }
        expected_evidence_keys = {
            "experiment_id",
            *terminal,
            "sample_evidence",
            "execution_policy",
        }
        count_keys = {
            "terminal_row_count",
            "completed_slot_count",
            "resource_failure_count",
            "completed_module_fit_count",
            "new_e7_fit_count",
            "primary_fit_reuse_count",
        }
        flag_keys = set(terminal) - count_keys
        if (
            set(manifest) != expected_manifest_keys
            or manifest.get("schema_version")
            != "closure_anfis_learning_curve_manifest_v1"
            or manifest.get("experiment_id") != "E7"
            or manifest.get("gate") != PATCH_GATE
            or manifest.get("status") != "terminal"
            or any(type(manifest.get(key)) is not int for key in count_keys)
            or any(type(manifest.get(key)) is not bool for key in flag_keys)
            or any(manifest.get(key) != value for key, value in terminal.items())
            or manifest.get("slot_order") != slot_order
            or manifest.get("inputs") != inventory["e7_required_inputs"]
            or manifest.get("authority_sha256") != expected_authority
            or not isinstance(evidence, Mapping)
            or set(evidence) != expected_evidence_keys
            or evidence.get("experiment_id") != "E7"
            or any(type(evidence.get(key)) is not int for key in count_keys)
            or any(type(evidence.get(key)) is not bool for key in flag_keys)
            or any(evidence.get(key) != value for key, value in terminal.items())
            or not isinstance(evidence.get("sample_evidence"), list)
            or len(cast(list[Any], evidence["sample_evidence"])) != 45
        ):
            raise _error("E0-MCALI E7 manifest scientific dialect drifted")
        execution = cast(Mapping[str, Any], evidence.get("execution_policy", {}))
        if (
            set(execution) != {"torch_cpu_execution_policy", "threadpool_limit"}
            or type(execution.get("threadpool_limit")) is not int
            or execution.get("threadpool_limit") != 1
            or not mcalh._torch_policy_has_exact_integer_fields(
                execution.get("torch_cpu_execution_policy")
            )
        ):
            raise _error("E0-MCALI E7 execution policy drifted")
        try:
            mcalh._require_exact_e7_sample_evidence_types(
                evidence.get("sample_evidence")
            )
            mcal._validate_torch_cpu_execution_policy(
                execution.get("torch_cpu_execution_policy"), context="E7"
            )
            mcal._validate_e7_csv_output(
                payloads[mcal.ANFIS_LEARNING_CURVE_PATH],
                terminal_evidence=evidence,
            )
        except mcalh.FinalCalibrationError as exc:
            raise _error(str(exc).replace("E0-MCAL", "E0-MCALI")) from exc
    else:
        raise _error("E0-MCALI output group context drifted")
    for path in paths:
        payload, observed = mcal._read_regular_bytes_and_metadata(
            path, repo_root=repo_root
        )
        if payload != payloads[path] or _metadata_identity(observed) != (
            _metadata_identity(metadata[path])
        ):
            raise _error(f"E0-MCALI {context} output changed during validation")
    return len(paths)


def _parse_canonical_json_with_metadata(
    path: Path, *, repo_root: Path
) -> tuple[dict[str, Any], bytes, os.stat_result]:
    try:
        payload, metadata = mcal._read_regular_bytes_and_metadata(
            path, repo_root=repo_root
        )
        value = mcal._parse_json_bytes(payload, context=path.as_posix())
    except Exception as exc:
        raise _error(f"E0-MCALI published JSON is absent: {path.as_posix()}") from exc
    if not isinstance(value, dict) or payload != _canonical_json_bytes(value):
        raise _error(f"E0-MCALI published JSON is not canonical: {path.as_posix()}")
    return value, payload, metadata


def _published_h_state(h_head: str, *, repo_root: Path) -> dict[str, Any]:
    if h_head == BASE_P_MCALH_COMMIT or re.fullmatch(r"[0-9a-f]{40}", h_head) is None:
        raise _error("E0-MCALI published H commit is absent")
    if (
        mcal._single_parent(repo_root, h_head, context="H-E0-MCALI")
        != BASE_P_MCALH_COMMIT
    ):
        raise _error("E0-MCALI published H parent drifted")
    scope = mcal._git_scope(repo_root, BASE_P_MCALH_COMMIT, h_head)
    expected_scope = {
        "added": 5,
        "modified": 4,
        "deleted": 0,
        "path_count": 9,
        "paths": list(PATCH_PATHS),
    }
    if scope != expected_scope:
        raise _error("E0-MCALI published H scope drifted")
    components = [
        mcal._git_artifact_record(
            Path(path),
            role="final_calibration_owned_run_guard_revalidation_patch_component",
            repo_root=repo_root,
            commit=h_head,
        )
        for path in PATCH_PATHS
    ]
    return _state_for_h(
        repository={
            "base_p_mcalh_commit": BASE_P_MCALH_COMMIT,
            "h_patch_head": h_head,
            "branch": "main",
            "remote_head": h_head,
            "scope": scope,
        },
        h_patch={
            "gate": "H-E0-MCALI",
            "component_count": 9,
            "added_count": 5,
            "modified_count": 4,
            "components": components,
            "components_sha256": mcal._digest_records(components),
        },
        repo_root=repo_root,
        require_empty_namespace=False,
    )


def _validate_published_lock_payload(
    payload: Mapping[str, Any], *, repo_root: Path
) -> None:
    schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=repo_root)
    try:
        mcal.validate_json_schema(payload, schema)
    except mcal.ClosureContractError as exc:
        raise _error(str(exc)) from exc
    _validate_timestamp(payload.get("generated_at_utc"))
    _validate_verification(payload.get("verification"), repo_root=repo_root)
    _require_publication_verification(payload, repo_root=repo_root)
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise _error("E0-MCALI published authorizations drifted")
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("E0-MCALI published H binding is absent")
    state = _published_h_state(
        cast(str, repository["h_patch_head"]), repo_root=repo_root
    )
    expected = build_final_calibration_owned_run_guard_revalidation_patch_lock_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=cast(str, payload["generated_at_utc"]),
    )
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("E0-MCALI published lock reconstruction drifted")


def _validate_p_publication(
    payload: Mapping[str, Any], *, verify_remote: bool, repo_root: Path
) -> dict[str, str]:
    if type(verify_remote) is not bool:
        raise _error("E0-MCALI remote policy must be an exact boolean")
    repository = cast(Mapping[str, Any], payload["repository"])
    h_head = cast(str, repository["h_patch_head"])
    head = mcal._git_head(repo_root)
    workspace = mcal._workspace_status_records(repo_root)
    allowed_r_paths = {path.as_posix() for path in R_OUTPUT_PATHS}
    if any(code != "??" or path not in allowed_r_paths for code, path in workspace):
        raise _error("E0-MCALI published P worktree drifted")
    if (
        cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
        != "main"
        or mcal._single_parent(repo_root, head, context="P-E0-MCALI") != h_head
        or mcal._git_scope(repo_root, h_head, head)
        != {
            "added": 2,
            "modified": 0,
            "deleted": 0,
            "path_count": 2,
            "paths": sorted(FINAL_CALIBRATION_P_STAGED_SCOPE),
        }
    ):
        raise _error("E0-MCALI published P topology drifted")
    tracking = mcal._git_head(repo_root, "origin/main")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != head or remote != head:
        raise _error("E0-MCALI published P refs drifted")
    for path in (DEFAULT_PATCH_LOCK_PATH, DEFAULT_PATCH_LOCK_MANIFEST_PATH):
        physical = mcal._read_regular_bytes(path, repo_root=repo_root)
        mode, _ = mcal._git_mode_oid(repo_root, head, path)
        if mode != "100644" or physical != mcal._git_blob_bytes(
            repo_root, head, path
        ):
            raise _error(
                f"E0-MCALI published P physical/Git binding drifted: {path.as_posix()}"
            )
    return {"h_patch_head": h_head, "p_patch_head": head, "remote_head": remote}


def _require_static_effective_boundary(*, repo_root: Path) -> None:
    required = (
        mcalh.mcale.mcalc.DEFAULT_PATCH_LOCK_PATH,
        mcalh.mcale.mcalc.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        mcalh.mcale.mcald.DEFAULT_PATCH_LOCK_PATH,
        mcalh.mcale.mcald.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        mcalh.mcale.DEFAULT_PATCH_LOCK_PATH,
        mcalh.mcale.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        mcalh.DEFAULT_PATCH_LOCK_PATH,
        mcalh.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        DEFAULT_PATCH_LOCK_PATH,
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
    )
    missing = [
        path.as_posix()
        for path in required
        if not mcal._entry_exists(path, repo_root=repo_root)
    ]
    if missing:
        raise _error(f"E0-MCALI effective authority is absent: {missing}")
    forbidden = (
        mcal.DEFAULT_PATCH_LOCK_PATH,
        mcal.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        mcal._temporary_path(mcal.DEFAULT_PATCH_LOCK_PATH),
        mcal._temporary_path(mcal.DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        mcal._temporary_path(mcalh.mcale.mcalp.DEFAULT_PATCH_LOCK_PATH),
        mcal._temporary_path(mcalh.mcale.mcalp.DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        mcal._temporary_path(mcalh.mcale.mcalc.DEFAULT_PATCH_LOCK_PATH),
        mcal._temporary_path(mcalh.mcale.mcalc.DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        mcal._temporary_path(mcalh.mcale.mcald.DEFAULT_PATCH_LOCK_PATH),
        mcal._temporary_path(mcalh.mcale.mcald.DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        mcal._temporary_path(mcalh.mcale.DEFAULT_PATCH_LOCK_PATH),
        mcal._temporary_path(mcalh.mcale.DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        mcal._temporary_path(mcalh.DEFAULT_PATCH_LOCK_PATH),
        mcal._temporary_path(mcalh.DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        mcal._temporary_path(DEFAULT_PATCH_LOCK_PATH),
        mcal._temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        mcal.LOCKER_GUARD_PATH,
        mcalh.mcale.mcalp.LOCKER_GUARD_PATH,
        mcalh.mcale.mcalc.LOCKER_GUARD_PATH,
        mcalh.mcale.mcald.LOCKER_GUARD_PATH,
        mcalh.mcale.LOCKER_GUARD_PATH,
        mcalh.LOCKER_GUARD_PATH,
        LOCKER_GUARD_PATH,
    )
    occupied = [
        path.as_posix()
        for path in forbidden
        if mcal._entry_exists(path, repo_root=repo_root)
    ]
    if occupied:
        raise _error(f"E0-MCALI effective P namespace drifted: {occupied}")
    if mcal._entry_exists(Path(mcal.mze.OUTCOME_ACCESS_LOG), repo_root=repo_root):
        raise _error("E0-MCALI outcome access log appeared")
    if any(
        mcal._entry_exists(Path(path), repo_root=repo_root)
        for path in mcal.mze.E0_M_PATHS
    ):
        raise _error("E0-MCALI final E0-M outputs appeared")


_OWNED_CAPABILITY_KEYS = frozenset(
    cast(Sequence[str], OWNED_RUN_GUARD_REVALIDATION_CONTRACT["capability_keys"])
)
_OWNED_CAPABILITY_INTEGER_FIELDS = tuple(
    cast(
        Sequence[str],
        OWNED_RUN_GUARD_REVALIDATION_CONTRACT["capability_integer_fields"],
    )
)
_GUARD_PAYLOAD = cast(
    str, OWNED_RUN_GUARD_REVALIDATION_CONTRACT["guard_payload_utf8"]
).encode("utf-8")


def _validate_owned_capability(
    capability: Mapping[str, Any],
    *,
    expected_path: Path,
    expected_mode: int,
    repo_root: Path,
    context: str,
    expected_payload: bytes | None = None,
) -> None:
    """Bind one caller capability to the same anchored regular-file inode."""

    if not isinstance(capability, Mapping) or set(capability) != _OWNED_CAPABILITY_KEYS:
        raise _error(f"E0-MCALI {context} capability dialect drifted")
    path = capability.get("path")
    if type(path) is not str or path != expected_path.as_posix():
        raise _error(f"E0-MCALI {context} capability path drifted")
    if any(
        type(capability.get(field)) is not int
        for field in _OWNED_CAPABILITY_INTEGER_FIELDS
    ):
        raise _error(f"E0-MCALI {context} capability identity types drifted")
    if (
        cast(int, capability["device"]) < 0
        or cast(int, capability["inode"]) <= 0
        or capability["mode"] != expected_mode
        or capability["nlink"]
        != OWNED_RUN_GUARD_REVALIDATION_CONTRACT["required_nlink"]
        or cast(int, capability["size"]) < 0
        or cast(int, capability["mtime_ns"]) < 0
        or cast(int, capability["ctime_ns"]) < 0
    ):
        raise _error(f"E0-MCALI {context} capability identity drifted")
    sha256 = capability.get("sha256")
    if type(sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
        raise _error(f"E0-MCALI {context} capability digest drifted")
    try:
        payload, metadata = mcal._read_regular_bytes_and_metadata(
            expected_path,
            repo_root=repo_root,
            expected_mode=expected_mode,
            require_nlink_one=True,
        )
    except mcalh.FinalCalibrationError as exc:
        raise _error(f"E0-MCALI {context} owned name is not stable") from exc
    observed = {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode": stat.S_IMODE(metadata.st_mode),
        "nlink": metadata.st_nlink,
        "size": metadata.st_size,
        "mtime_ns": metadata.st_mtime_ns,
        "ctime_ns": metadata.st_ctime_ns,
        "sha256": _sha256_bytes(payload),
    }
    if any(capability[key] != value for key, value in observed.items()):
        raise _error(f"E0-MCALI {context} capability no longer owns the name")
    if expected_payload is not None and payload != expected_payload:
        raise _error(f"E0-MCALI {context} payload drifted")


def _validate_owned_guard_capability(
    capability: Mapping[str, Any], *, repo_root: Path, runner: str | None = None
) -> Path:
    guard_paths = cast(
        Mapping[str, str], OWNED_RUN_GUARD_REVALIDATION_CONTRACT["guard_paths"]
    )
    path_value = capability.get("path") if isinstance(capability, Mapping) else None
    allowed = {name: Path(value) for name, value in guard_paths.items()}
    if runner is not None:
        if runner not in allowed:
            raise _error("E0-MCALI owned guard runner drifted")
        expected_path = allowed[runner]
    else:
        matches = [path for path in allowed.values() if path.as_posix() == path_value]
        if len(matches) != 1:
            raise _error("E0-MCALI owned guard path is not registered")
        expected_path = matches[0]
    _validate_owned_capability(
        capability,
        expected_path=expected_path,
        expected_mode=cast(
            int, OWNED_RUN_GUARD_REVALIDATION_CONTRACT["guard_mode"]
        ),
        repo_root=repo_root,
        context="owned run guard",
        expected_payload=_GUARD_PAYLOAD,
    )
    if (
        capability["size"]
        != OWNED_RUN_GUARD_REVALIDATION_CONTRACT["guard_payload_bytes"]
        or capability["sha256"]
        != OWNED_RUN_GUARD_REVALIDATION_CONTRACT["guard_payload_sha256"]
    ):
        raise _error("E0-MCALI owned guard sealed payload drifted")
    return expected_path


def _expected_owned_output_paths(runner: str) -> tuple[Path, ...]:
    if runner == "calibration":
        return tuple(mcal.CALIBRATION_OUTPUT_PATHS)
    if runner == "e7":
        return tuple(mcal.E7_OUTPUT_PATHS)
    raise _error("E0-MCALI owned output runner drifted")


def _validate_owned_output_capabilities(
    capabilities: Sequence[Mapping[str, Any]], *, runner: str, repo_root: Path
) -> None:
    if isinstance(capabilities, (str, bytes, bytearray, Mapping)):
        raise _error("E0-MCALI owned outputs must be a capability sequence")
    expected = _expected_owned_output_paths(runner)
    if len(capabilities) != len(expected):
        raise _error("E0-MCALI owned output capability count drifted")
    by_path: dict[str, Mapping[str, Any]] = {}
    for capability in capabilities:
        if not isinstance(capability, Mapping) or type(capability.get("path")) is not str:
            raise _error("E0-MCALI owned output capability dialect drifted")
        path = cast(str, capability["path"])
        if path in by_path:
            raise _error("E0-MCALI owned output capability path is duplicated")
        by_path[path] = capability
    if set(by_path) != {path.as_posix() for path in expected}:
        raise _error("E0-MCALI owned output capability set drifted")
    for path in expected:
        _validate_owned_capability(
            by_path[path.as_posix()],
            expected_path=path,
            expected_mode=cast(
                int, OWNED_RUN_GUARD_REVALIDATION_CONTRACT["output_mode"]
            ),
            repo_root=repo_root,
            context=f"owned output {path.as_posix()}",
        )


def _validate_effective_namespace(
    *, repo_root: Path, owned_guard: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    allowed_guard_path: Path | None = None
    if owned_guard is not None:
        allowed_guard_path = _validate_owned_guard_capability(
            owned_guard, repo_root=repo_root
        )
    forbidden = (
        mcal._temporary_path(DEFAULT_PATCH_LOCK_PATH),
        mcal._temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        *(mcal._temporary_path(path) for path in R_OUTPUT_PATHS),
        LOCKER_GUARD_PATH,
        mcal.CALIBRATION_GUARD_PATH,
        mcal.E7_GUARD_PATH,
    )
    occupied = [
        path.as_posix()
        for path in forbidden
        if path != allowed_guard_path
        if mcal._entry_exists(path, repo_root=repo_root)
    ]
    if occupied:
        raise _error(
            "E0-MCALI effective coordination/temporary namespace is occupied: "
            f"{occupied}"
        )
    calibration_count = _require_exact_output_group(
        mcal.CALIBRATION_OUTPUT_PATHS,
        manifest_path=mcal.FINAL_CALIBRATION_MANIFEST_PATH,
        repo_root=repo_root,
        context="calibration",
    )
    e7_count = _require_exact_output_group(
        mcal.E7_OUTPUT_PATHS,
        manifest_path=mcal.ANFIS_LEARNING_CURVE_MANIFEST_PATH,
        repo_root=repo_root,
        context="E7",
    )
    if (calibration_count, e7_count) not in {(0, 0), (6, 0), (6, 2)}:
        raise _error("E0-MCALI R bundle order drifted")
    lifecycle = {
        (0, 0): "ready_for_calibration_bundle",
        (6, 0): "calibration_completed_unpublished_ready_for_e7_bundle",
        (6, 2): "both_bundles_completed_unpublished",
    }[(calibration_count, e7_count)]
    return {
        "calibration_output_present_count": calibration_count,
        "e7_output_present_count": e7_count,
        "r_output_present_count": calibration_count + e7_count,
        "r_lifecycle_state": lifecycle,
    }


def _effective_namespace_for_owned_guard(
    *, repo_root: Path, owned_guard: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Keep the public/no-guard call surface compatible with strict probes."""

    if owned_guard is None:
        return _validate_effective_namespace(repo_root=repo_root)
    return _validate_effective_namespace(
        repo_root=repo_root, owned_guard=owned_guard
    )


def _require_effective_loading_checkpoint(
    *,
    repo_root: Path,
    expected_head: str,
    verify_remote: bool,
    authority_snapshot: Sequence[Mapping[str, Any]],
    scientific_inventory: Mapping[str, Any],
    expected_namespace: Mapping[str, Any],
    context: str,
    owned_guard: Mapping[str, Any] | None = None,
) -> None:
    expected_r_paths: list[Path] = []
    if expected_namespace.get("calibration_output_present_count") == 6:
        expected_r_paths.extend(mcal.CALIBRATION_OUTPUT_PATHS)
    if expected_namespace.get("e7_output_present_count") == 2:
        expected_r_paths.extend(mcal.E7_OUTPUT_PATHS)
    _require_repository_checkpoint(
        repo_root=repo_root,
        expected_head=expected_head,
        verify_remote=verify_remote,
        expected_untracked_paths=expected_r_paths,
        context=context,
    )
    _require_physical_snapshot(
        authority_snapshot,
        scientific_inventory=scientific_inventory,
        repo_root=repo_root,
        context=context,
    )
    _require_static_effective_boundary(repo_root=repo_root)
    observed = _effective_namespace_for_owned_guard(
        repo_root=repo_root, owned_guard=owned_guard
    )
    if _canonical_json_bytes(observed) != _canonical_json_bytes(expected_namespace):
        raise _error(f"E0-MCALI R namespace changed {context}")


def _load_effective_final_calibration_owned_run_guard_revalidation_patch_authority(
    *,
    verify_remote: bool,
    repo_root: Path | None,
    owned_guard: Mapping[str, Any] | None,
) -> dict[str, Any]:
    root = _root(repo_root)
    payload, lock_bytes, lock_metadata = _parse_canonical_json_with_metadata(
        DEFAULT_PATCH_LOCK_PATH, repo_root=root
    )
    _validate_published_lock_payload(payload, repo_root=root)
    lock_record = mcal._file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="final_calibration_owned_run_guard_revalidation_patch_lock",
        repo_root=root,
    )
    companion, companion_bytes, companion_metadata = (
        _parse_canonical_json_with_metadata(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
        )
    )
    if _canonical_json_bytes(companion) != _canonical_json_bytes(
        _expected_companion(payload, lock_record)
    ):
        raise _error("E0-MCALI published companion drifted")
    publication = _validate_p_publication(
        payload, verify_remote=verify_remote, repo_root=root
    )
    _require_static_effective_boundary(repo_root=root)
    namespace = _effective_namespace_for_owned_guard(
        repo_root=root, owned_guard=owned_guard
    )
    inventory = cast(Mapping[str, Any], payload["scientific_input_inventory"])
    snapshot = _physical_snapshot(root, scientific_inventory=inventory)
    initial_head = mcal._git_head(root)
    if initial_head != publication["p_patch_head"]:
        raise _error("E0-MCALI P refs do not match the captured baseline")
    _validate_published_lock_payload(payload, repo_root=root)
    recaptured = _validate_p_publication(
        payload, verify_remote=verify_remote, repo_root=root
    )
    if recaptured != publication:
        raise _error("E0-MCALI P publication changed during baseline recapture")
    _require_effective_loading_checkpoint(
        repo_root=root,
        expected_head=initial_head,
        verify_remote=verify_remote,
        authority_snapshot=snapshot,
        scientific_inventory=inventory,
        expected_namespace=namespace,
        context="during effective semantic baseline recapture",
        owned_guard=owned_guard,
    )
    base = mcal._base_r_mze_authority(repo_root=root)
    authority_sha256 = _effective_authority_binding_sha256(
        repo_root=root,
        scientific_inventory=inventory,
        p_patch_head=publication["p_patch_head"],
        lock_record=lock_record,
    )
    lifecycle = cast(str, namespace["r_lifecycle_state"])
    result = {
        "gate": PATCH_GATE,
        "status": "effective",
        **publication,
        "lock": lock_record,
        "companion": mcal._file_record(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            role="final_calibration_owned_run_guard_revalidation_patch_lock_manifest",
            repo_root=root,
        ),
        "authority_binding_sha256": authority_sha256,
        "owned_run_guard_revalidation_correction": _deep_copy(
            OWNED_RUN_GUARD_REVALIDATION_CONTRACT
        ),
        "observed_risk_precision_correction": _deep_copy(
            OBSERVED_RISK_PRECISION_CONTRACT
        ),
        "ordinal_label_representation_correction": _deep_copy(
            ORDINAL_LABEL_REPRESENTATION_CONTRACT
        ),
        "raw_exclusion_evidence_correction": _deep_copy(
            RAW_EXCLUSION_EVIDENCE_CONTRACT
        ),
        "target_filter_evidence_correction": _deep_copy(
            TARGET_FILTER_EVIDENCE_CONTRACT
        ),
        "inference_role_correction": _deep_copy(INFERENCE_ROLE_CONTRACT),
        "candidate_semantics_correction": {
            "data_rewrite_performed": False,
            "failed_mcalp_retry_authorized": False,
            "raw_score_candidate_values": _deep_copy(
                RAW_SCORE_CANDIDATE_VALUES
            ),
        },
        "failed_attempt": _deep_copy(FAILED_ATTEMPT),
        "scientific_input_inventory": _deep_copy(inventory),
        "calibration_required_inputs": _deep_copy(
            inventory["calibration_required_inputs"]
        ),
        "calibration_required_inputs_sha256": inventory[
            "calibration_required_inputs_sha256"
        ],
        "e7_required_inputs": _deep_copy(inventory["e7_required_inputs"]),
        "e7_required_inputs_sha256": inventory["e7_required_inputs_sha256"],
        "model_ids": list(mcal.MODEL_IDS),
        "bloom_group_count": mcal.BLOOM_GROUP_COUNT,
        "ordinal_group_count": mcal.ORDINAL_GROUP_COUNT,
        "uncertainty_group_count": mcal.UNCERTAINTY_GROUP_COUNT,
        "q_c_levels": list(mcal.Q_C_LEVELS),
        "e7_training_rows_per_module": [4096, 16384, 65536],
        "e7_expected_completed_slot_count": 5,
        "e7_expected_completed_module_fit_count": 15,
        "e7_expected_resource_failure_record_count": 10,
        "historical_e7_blocker_adopted": True,
        "historical_e7_blockers": mcal._historical_e7_blockers(repo_root=root),
        "e7_authority_correction": {
            "historical_blocker_count": 3,
            "historical_e7_blocker_adopted": True,
            "supersession_scope": "e7_only_additive_authority",
            "final_runtime_path": mcal.DEFAULT_RUNTIME_PATH.as_posix(),
        },
        "r_output_paths": [path.as_posix() for path in R_OUTPUT_PATHS],
        "family_final_count": base["family_final_count"],
        "family_records_sha256": base["family_records_sha256"],
        **namespace,
        "run_namespace_required": True,
        "calibration_development_run_authorized": lifecycle
        == "ready_for_calibration_bundle",
        "e7_learning_curve_run_authorized": lifecycle
        == "calibration_completed_unpublished_ready_for_e7_bundle",
        "calibration_one_shot_consumed": lifecycle
        != "ready_for_calibration_bundle",
        "e7_one_shot_consumed": lifecycle == "both_bundles_completed_unpublished",
        "r_outputs_ready_for_staging": lifecycle
        == "both_bundles_completed_unpublished",
        "holdout_access_authorized": False,
        "post_2021_access_authorized": False,
        "locked_evaluation_authorized": False,
        "outcome_access_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "dvc_commands_authorized": False,
        "dvc_push_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
        "scientific_network_authorized": False,
        "future_outcomes_accessed": False,
        "writes_performed": False,
    }
    final_lock, final_lock_bytes, final_lock_metadata = (
        _parse_canonical_json_with_metadata(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    )
    final_companion, final_companion_bytes, final_companion_metadata = (
        _parse_canonical_json_with_metadata(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
        )
    )
    if (
        final_lock != payload
        or final_companion != companion
        or final_lock_bytes != lock_bytes
        or final_companion_bytes != companion_bytes
        or _metadata_identity(final_lock_metadata) != _metadata_identity(lock_metadata)
        or _metadata_identity(final_companion_metadata)
        != _metadata_identity(companion_metadata)
    ):
        raise _error("E0-MCALI P authority changed during effective loading")
    _require_effective_loading_checkpoint(
        repo_root=root,
        expected_head=initial_head,
        verify_remote=verify_remote,
        authority_snapshot=snapshot,
        scientific_inventory=inventory,
        expected_namespace=namespace,
        context="during effective loading",
        owned_guard=owned_guard,
    )
    _require_effective_loading_checkpoint(
        repo_root=root,
        expected_head=initial_head,
        verify_remote=verify_remote,
        authority_snapshot=snapshot,
        scientific_inventory=inventory,
        expected_namespace=namespace,
        context="at effective loading linearization",
        owned_guard=owned_guard,
    )
    terminal_lock, terminal_lock_bytes, terminal_lock_metadata = (
        _parse_canonical_json_with_metadata(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    )
    terminal_companion, terminal_companion_bytes, terminal_companion_metadata = (
        _parse_canonical_json_with_metadata(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
        )
    )
    if (
        terminal_lock != payload
        or terminal_companion != companion
        or terminal_lock_bytes != lock_bytes
        or terminal_companion_bytes != companion_bytes
        or _metadata_identity(terminal_lock_metadata) != _metadata_identity(lock_metadata)
        or _metadata_identity(terminal_companion_metadata)
        != _metadata_identity(companion_metadata)
    ):
        raise _error("E0-MCALI P authority changed at effective linearization")
    terminal_namespace = _effective_namespace_for_owned_guard(
        repo_root=root, owned_guard=owned_guard
    )
    if _canonical_json_bytes(terminal_namespace) != _canonical_json_bytes(namespace):
        raise _error("E0-MCALI R namespace changed at effective linearization")
    return result


@_error_boundary
def load_effective_final_calibration_owned_run_guard_revalidation_patch_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    """Load published authority; every active run guard remains forbidden."""

    return _load_effective_final_calibration_owned_run_guard_revalidation_patch_authority(
        verify_remote=verify_remote,
        repo_root=repo_root,
        owned_guard=None,
    )


_LIFECYCLE_AUTHORITY_KEYS = frozenset(
    {
        "calibration_output_present_count",
        "e7_output_present_count",
        "r_output_present_count",
        "r_lifecycle_state",
        "calibration_development_run_authorized",
        "e7_learning_curve_run_authorized",
        "calibration_one_shot_consumed",
        "e7_one_shot_consumed",
        "r_outputs_ready_for_staging",
    }
)
_LIFECYCLE_COUNT_KEYS = frozenset(
    {
        "calibration_output_present_count",
        "e7_output_present_count",
        "r_output_present_count",
    }
)
_LIFECYCLE_FLAG_KEYS = _LIFECYCLE_AUTHORITY_KEYS - _LIFECYCLE_COUNT_KEYS - {
    "r_lifecycle_state"
}
_LIFECYCLE_AUTHORITY_STATES: dict[str, dict[str, Any]] = {
    "ready_for_calibration_bundle": {
        "calibration_output_present_count": 0,
        "e7_output_present_count": 0,
        "r_output_present_count": 0,
        "r_lifecycle_state": "ready_for_calibration_bundle",
        "calibration_development_run_authorized": True,
        "e7_learning_curve_run_authorized": False,
        "calibration_one_shot_consumed": False,
        "e7_one_shot_consumed": False,
        "r_outputs_ready_for_staging": False,
    },
    "calibration_completed_unpublished_ready_for_e7_bundle": {
        "calibration_output_present_count": 6,
        "e7_output_present_count": 0,
        "r_output_present_count": 6,
        "r_lifecycle_state": (
            "calibration_completed_unpublished_ready_for_e7_bundle"
        ),
        "calibration_development_run_authorized": False,
        "e7_learning_curve_run_authorized": True,
        "calibration_one_shot_consumed": True,
        "e7_one_shot_consumed": False,
        "r_outputs_ready_for_staging": False,
    },
    "both_bundles_completed_unpublished": {
        "calibration_output_present_count": 6,
        "e7_output_present_count": 2,
        "r_output_present_count": 8,
        "r_lifecycle_state": "both_bundles_completed_unpublished",
        "calibration_development_run_authorized": False,
        "e7_learning_curve_run_authorized": False,
        "calibration_one_shot_consumed": True,
        "e7_one_shot_consumed": True,
        "r_outputs_ready_for_staging": True,
    },
}


def _require_lifecycle_authority(
    authority: Mapping[str, Any], *, expected_state: str, context: str
) -> None:
    expected = _LIFECYCLE_AUTHORITY_STATES[expected_state]
    if (
        any(key not in authority for key in _LIFECYCLE_AUTHORITY_KEYS)
        or any(type(authority[key]) is not int for key in _LIFECYCLE_COUNT_KEYS)
        or type(authority["r_lifecycle_state"]) is not str
        or any(type(authority[key]) is not bool for key in _LIFECYCLE_FLAG_KEYS)
        or {key: authority[key] for key in _LIFECYCLE_AUTHORITY_KEYS} != expected
    ):
        raise _error(f"E0-MCALI {context} lifecycle authority drifted")


def _without_lifecycle_authority(authority: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: _deep_copy(value)
        for key, value in authority.items()
        if key not in _LIFECYCLE_AUTHORITY_KEYS
    }


@_error_boundary
def revalidate_final_calibration_owned_run_publication(
    captured: Mapping[str, Any],
    *,
    runner: str,
    phase: str,
    owned_guard: Mapping[str, Any] | None,
    owned_outputs: Sequence[Mapping[str, Any]],
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Revalidate one exact owned R transition while its transaction is live."""

    if type(runner) is not str or runner not in {"calibration", "e7"}:
        raise _error("E0-MCALI owned publication runner drifted")
    if type(phase) is not str or phase not in {"active_guard", "post_release"}:
        raise _error("E0-MCALI owned publication phase drifted")
    if type(verify_remote) is not bool:
        raise _error("E0-MCALI owned publication remote policy drifted")
    if not isinstance(captured, Mapping):
        raise _error("E0-MCALI captured authority must be an object")
    try:
        frozen_captured = cast(dict[str, Any], _deep_copy(dict(captured)))
        if isinstance(owned_outputs, (str, bytes, bytearray, Mapping)):
            raise TypeError("owned outputs are not a sequence")
        frozen_outputs = tuple(
            cast(Mapping[str, Any], _deep_copy(dict(capability)))
            for capability in owned_outputs
        )
        frozen_guard = (
            None
            if owned_guard is None
            else cast(Mapping[str, Any], _deep_copy(dict(owned_guard)))
        )
    except (TypeError, ValueError, KeyError, OverflowError, RecursionError) as exc:
        raise _error("E0-MCALI owned publication capabilities are not canonical") from exc
    root = _root(repo_root)
    transitions = cast(
        Mapping[str, Sequence[str]],
        OWNED_RUN_GUARD_REVALIDATION_CONTRACT["active_guard_transitions"],
    )
    initial_state, terminal_state = transitions[runner]
    _require_lifecycle_authority(
        frozen_captured,
        expected_state=initial_state,
        context="captured",
    )
    _validate_owned_output_capabilities(
        frozen_outputs, runner=runner, repo_root=root
    )
    expected_guard_path = Path(
        cast(
            Mapping[str, str],
            OWNED_RUN_GUARD_REVALIDATION_CONTRACT["guard_paths"],
        )[runner]
    )
    if phase == "active_guard":
        if frozen_guard is None:
            raise _error("E0-MCALI active phase requires the owned guard capability")
        _validate_owned_guard_capability(
            frozen_guard, repo_root=root, runner=runner
        )
    else:
        if frozen_guard is not None:
            raise _error("E0-MCALI post-release phase forbids a guard capability")
        if mcal._entry_exists(expected_guard_path, repo_root=root):
            raise _error("E0-MCALI post-release owned guard is still present")
    current = (
        _load_effective_final_calibration_owned_run_guard_revalidation_patch_authority(
            verify_remote=verify_remote,
            repo_root=root,
            owned_guard=frozen_guard,
        )
    )
    _validate_owned_output_capabilities(
        frozen_outputs, runner=runner, repo_root=root
    )
    if phase == "active_guard":
        assert frozen_guard is not None
        _validate_owned_guard_capability(
            frozen_guard, repo_root=root, runner=runner
        )
    elif mcal._entry_exists(expected_guard_path, repo_root=root):
        raise _error("E0-MCALI owned guard reappeared after release")
    _require_lifecycle_authority(
        current,
        expected_state=terminal_state,
        context="revalidated",
    )
    if _canonical_json_bytes(_without_lifecycle_authority(frozen_captured)) != (
        _canonical_json_bytes(_without_lifecycle_authority(current))
    ):
        raise _error("E0-MCALI non-lifecycle authority changed during publication")
    return current


@_error_boundary
def require_final_calibration_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    return load_effective_final_calibration_owned_run_guard_revalidation_patch_authority(
        verify_remote=verify_remote, repo_root=repo_root
    )


@_error_boundary
def require_final_calibration_run_namespace(
    *, runner: str, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    if type(runner) is not str or runner not in {"calibration", "e7"}:
        raise _error("E0-MCALI run namespace requires calibration or e7")
    namespace = _validate_effective_namespace(repo_root=root)
    required_state = (
        "ready_for_calibration_bundle"
        if runner == "calibration"
        else "calibration_completed_unpublished_ready_for_e7_bundle"
    )
    if namespace["r_lifecycle_state"] != required_state:
        raise _error(f"E0-MCALI {runner} one-shot namespace is not ready")
    return {
        "gate": PATCH_GATE,
        "runner": runner,
        "status": "ready_before_scientific_io",
        "registration_execution_order": ["calibration_bundle", "e7_bundle"],
        **namespace,
        "own_bundle_present_count": 0,
        "temporary_present_count": 0,
        "coordination_present_count": 0,
        "rerun_allowed": False,
        "scientific_io_performed": False,
    }


def __getattr__(name: str) -> Any:
    """Delegate unchanged scientific/runtime surfaces to predecessor E0-MCALH."""

    return getattr(mcalh, name)
