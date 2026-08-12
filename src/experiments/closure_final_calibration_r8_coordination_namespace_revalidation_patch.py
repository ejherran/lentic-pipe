"""Close the complete final-calibration coordination namespace under E0-MCALL.

H-E0-MCALK was published without a P-E0-MCALK lock.  This additive overlay
preserves that historical commit and the immutable R8 outputs while requiring
every historical/current lock temporary and locker/run guard to remain absent
at each publication and effective-loading linearization point.
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
    closure_final_calibration_r8_manifest_reproducibility_patch as mcalk,
)

mcalj = mcalk.mcalj
mcal = mcalk.mcal
mt = mcalk.mt
mcali = mcalj.mcali
mcalh = mcali.mcalh
mcalg = mcalh.mcalg
mcalf = mcalg.mcalf
mcale = mcalf.mcale
mcald = mcale.mcald
mcalc = mcald.mcalc
mcalp = mcalc.mcalp

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_H_MCALK_COMMIT = "6f078da52c5dd699ea312df209bfef5a8d120d00"
HISTORICAL_P_MCALJ_COMMIT = "97f12b00b952829474a2937dccba6add783df074"
BASE_P_MCALJ_COMMIT = HISTORICAL_P_MCALJ_COMMIT
H_MCALK_PARENT = HISTORICAL_P_MCALJ_COMMIT
PATCH_GATE = "E0-MCALL"
FINAL_CALIBRATION_GATE = PATCH_GATE
EXPERIMENT_ID = "closure_v1"
LOCK_SCHEMA_VERSION = (
    "closure_final_calibration_r8_coordination_namespace_revalidation_patch_lock_v1"
)
COMPANION_SCHEMA_VERSION = (
    "closure_final_calibration_r8_coordination_namespace_revalidation_patch_lock_manifest_v1"
)

DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/"
    "final_calibration_r8_coordination_namespace_revalidation_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "final_calibration_r8_coordination_namespace_revalidation_patch_lock.json"
)
DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "final_calibration_r8_coordination_namespace_revalidation_patch_lock_manifest.json"
)
DEFAULT_PATCH_MANIFEST_PATH = DEFAULT_PATCH_LOCK_MANIFEST_PATH
LOCKER_PATH = Path(
    "src/experiments/"
    "lock_closure_final_calibration_r8_coordination_namespace_revalidation_patch.py"
)
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_e0_mcall/"
    "final_calibration_r8_coordination_namespace_revalidation_patch_lock.guard"
)

PRECOMMIT_PATH = "src/data/prepare_commit_artifacts.py"
CORE_PATH = (
    "src/experiments/"
    "closure_final_calibration_r8_coordination_namespace_revalidation_patch.py"
)
TEST_PATH = (
    "tests/test_closure_final_calibration_r8_coordination_namespace_revalidation_patch.py"
)
PATCH_PATHS = tuple(
    sorted(
        {
            DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
            "docs/closure_v1/"
            "E0_M_FINAL_CALIBRATION_R8_COORDINATION_NAMESPACE_REVALIDATION_PATCH_1.md",
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
P_MCALJ_PATHS = (
    mcalj.DEFAULT_PATCH_LOCK_PATH.as_posix(),
    mcalj.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
)
H_MCALK_PATHS = tuple(mcalk.PATCH_PATHS)
R_OUTPUT_PATHS = tuple(mcalk.R_OUTPUT_PATHS)
R8_OUTPUT_CONTRACT = tuple(mcalk.R8_OUTPUT_CONTRACT)
R8_STAGED_SCOPE = {path.as_posix(): "A" for path in R_OUTPUT_PATHS}
FINAL_CALIBRATION_R_STAGED_SCOPE = dict(R8_STAGED_SCOPE)
GENERIC_MANIFEST_FINDINGS_CONTRACT = tuple(
    mcalk.GENERIC_MANIFEST_FINDINGS_CONTRACT
)
MANIFEST_REPRODUCIBILITY_CONTRACT = dict(
    mcalk.MANIFEST_REPRODUCIBILITY_CONTRACT
)

EXPECTED_COMPANION_INPUT_COUNT = 16
EXPECTED_HISTORICAL_INPUT_COUNT = 6
EXPECTED_COMPANION_OUTPUT_COUNT = 1

TYPE_CHECK_COMMAND = mcalk.TYPE_CHECK_COMMAND
FOCUSED_TEST_COMMAND = (
    "poetry",
    "run",
    "pytest",
    "-q",
    "tests/test_prepare_commit_artifacts.py",
    TEST_PATH,
)
FOCUSED_TEST_COUNT = 48
POETRY_CHECK_COMMAND = mcalk.POETRY_CHECK_COMMAND
PUBLICATION_GUARD_COMMAND = mcalk.PUBLICATION_GUARD_COMMAND
DIFF_CHECK_COMMAND = mcalk.DIFF_CHECK_COMMAND
UNPUBLISHED_AUTHORIZATIONS = {
    **mcalk.UNPUBLISHED_AUTHORIZATIONS,
    "r8_staging_authorized": False,
}

_PUBLISHED_LOCK_MODULES = (
    mcalp,
    mcalc,
    mcald,
    mcale,
    mcalf,
    mcalg,
    mcalh,
    mcali,
    mcalj,
)
HISTORICAL_PUBLISHED_LOCK_PATHS = tuple(
    sorted(
        (
            path
            for module in _PUBLISHED_LOCK_MODULES
            for path in (
                module.DEFAULT_PATCH_LOCK_PATH,
                module.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            )
        ),
        key=lambda path: path.as_posix(),
    )
)
NEVER_PUBLISHED_LOCK_PATHS = tuple(
    sorted(
        (
            mcal.DEFAULT_PATCH_LOCK_PATH,
            mcal.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            mcalk.DEFAULT_PATCH_LOCK_PATH,
            mcalk.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        ),
        key=lambda path: path.as_posix(),
    )
)
CURRENT_LOCK_PATHS = tuple(
    sorted(
        (DEFAULT_PATCH_LOCK_PATH, DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        key=lambda path: path.as_posix(),
    )
)
_LOCK_MODULES = (
    mcal,
    mcalp,
    mcalc,
    mcald,
    mcale,
    mcalf,
    mcalg,
    mcalh,
    mcali,
    mcalj,
    mcalk,
)
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
R8_TEMPORARY_PATHS = tuple(
    sorted(
        (mcal._temporary_path(path) for path in R_OUTPUT_PATHS),
        key=lambda path: path.as_posix(),
    )
)
SCIENTIFIC_RUN_GUARD_PATHS = tuple(
    sorted(
        (mcal.CALIBRATION_GUARD_PATH, mcal.E7_GUARD_PATH),
        key=lambda path: path.as_posix(),
    )
)
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
    "historical_published_lock_count": 18,
    "historical_published_lock_paths": [
        path.as_posix() for path in HISTORICAL_PUBLISHED_LOCK_PATHS
    ],
    "never_published_lock_count": 4,
    "never_published_lock_paths": [
        path.as_posix() for path in NEVER_PUBLISHED_LOCK_PATHS
    ],
    "current_lock_count": 2,
    "current_lock_paths": [path.as_posix() for path in CURRENT_LOCK_PATHS],
    "lock_temporary_count": 24,
    "lock_temporary_paths": [path.as_posix() for path in LOCK_TEMPORARY_PATHS],
    "locker_guard_count": 12,
    "locker_guard_paths": [path.as_posix() for path in LOCKER_GUARD_PATHS],
    "r8_temporary_count": 8,
    "r8_temporary_paths": [path.as_posix() for path in R8_TEMPORARY_PATHS],
    "scientific_run_guard_count": 2,
    "scientific_run_guard_paths": [
        path.as_posix() for path in SCIENTIFIC_RUN_GUARD_PATHS
    ],
    "coordination_forbidden_count": 46,
    "predecessor_guard_race_path": mcalj.LOCKER_GUARD_PATH.as_posix(),
    "post_release_revalidation_required": True,
    "effective_loader_revalidation_required": True,
}
SUPERSEDED_CHECK_ONLY = {
    "attempted_gate": "P-E0-MCALK",
    "mode": "check_only",
    "status": "superseded_check_only_interrupted_after_static_blocker_detected",
    "interruption": "KeyboardInterrupt",
    "phase": "read_only_historical_input_rehash",
    "last_observed_path": "data/fuzzy/state_vector_v0.parquet",
    "static_blocker": "predecessor_coordination_guard_race_and_loader_omission",
    "publication_started": False,
    "authorization_consumed": False,
    "writes_performed": False,
    "guard_created": False,
    "guard_removed": False,
    "p_output_count": 0,
    "temporary_output_count": 0,
    "coordination_present_count": 0,
    "r8_output_count": 8,
    "r8_bytes_changed": False,
    "r8_rewrite_performed": False,
    "scientific_rerun_performed": False,
    "dvc_commands_run": False,
    "outcome_paths_opened": False,
}


class FinalCalibrationR8CoordinationNamespaceRevalidationPatchError(
    mcalk.FinalCalibrationR8ManifestReproducibilityPatchError
):
    """Raised when the exact E0-MCALL coordination authority drifts."""


FinalCalibrationError = mcalk.FinalCalibrationError
P = ParamSpec("P")
R = TypeVar("R")


def _error(
    message: str,
) -> FinalCalibrationR8CoordinationNamespaceRevalidationPatchError:
    return FinalCalibrationR8CoordinationNamespaceRevalidationPatchError(message)


def _translate_predecessor_error(message: str) -> str:
    for prefix in (
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
        except FinalCalibrationR8CoordinationNamespaceRevalidationPatchError:
            raise
        except mcalk.FinalCalibrationError as exc:
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


def _git_record_at_commit(
    path: str, *, role: str, commit: str, repo_root: Path
) -> dict[str, Any]:
    relative = Path(path)
    mode, oid = mcal._git_mode_oid(repo_root, commit, relative)
    payload = mcal._git_blob_bytes(repo_root, commit, relative)
    if mode not in {"100644", "100755"}:
        raise _error(f"E0-MCALL historical Git mode drifted: {path}")
    return {
        "role": role,
        "path": path,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "git_oid": oid,
        "git_mode": mode,
    }


def _historical_p_mcalj_git_authority(*, repo_root: Path) -> dict[str, Any]:
    """Validate P-E0-MCALJ from Git/canonical metadata without science rehash."""

    p_mcalj = HISTORICAL_P_MCALJ_COMMIT
    h_mcalj = mcal._single_parent(repo_root, p_mcalj, context="P-E0-MCALJ")
    if (
        h_mcalj != mcalk.H_MCALJ_COMMIT
        or mcal._single_parent(repo_root, h_mcalj, context="H-E0-MCALJ")
        != mcalk.H_MCALJ_PARENT
        or mcal._git_scope(repo_root, mcalk.H_MCALJ_PARENT, h_mcalj)
        != {
            "added": 5,
            "modified": 4,
            "deleted": 0,
            "path_count": 9,
            "paths": list(mcalj.PATCH_PATHS),
        }
        or mcal._git_scope(repo_root, h_mcalj, p_mcalj)
        != {
            "added": 2,
            "modified": 0,
            "deleted": 0,
            "path_count": 2,
            "paths": sorted(P_MCALJ_PATHS),
        }
    ):
        raise _error("E0-MCALL historical P-E0-MCALJ topology drifted")
    records: list[dict[str, Any]] = []
    for path_text in P_MCALJ_PATHS:
        role = (
            "published_p_mcalj_lock"
            if path_text == mcalj.DEFAULT_PATCH_LOCK_PATH.as_posix()
            else "published_p_mcalj_lock_manifest"
        )
        record = _git_record_at_commit(
            path_text,
            role=role,
            commit=p_mcalj,
            repo_root=repo_root,
        )
        physical = mcal._git_artifact_record(
            Path(path_text),
            role=role,
            repo_root=repo_root,
            commit=p_mcalj,
        )
        if record != physical or record["git_mode"] != "100644":
            raise _error(
                f"E0-MCALL historical P-E0-MCALJ binding drifted: {path_text}"
            )
        records.append(record)
    lock_bytes = mcal._git_blob_bytes(
        repo_root, p_mcalj, mcalj.DEFAULT_PATCH_LOCK_PATH
    )
    companion_bytes = mcal._git_blob_bytes(
        repo_root, p_mcalj, mcalj.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    )
    lock = mcal._parse_json_bytes(lock_bytes, context="historical P-E0-MCALJ lock")
    companion = mcal._parse_json_bytes(
        companion_bytes, context="historical P-E0-MCALJ companion"
    )
    if (
        not isinstance(lock, Mapping)
        or not isinstance(companion, Mapping)
        or lock_bytes != mcalj._canonical_json_bytes(lock)
        or companion_bytes != mcalj._canonical_json_bytes(companion)
        or lock.get("gate") != mcalj.PATCH_GATE
        or lock.get("schema_version") != mcalj.LOCK_SCHEMA_VERSION
        or cast(Mapping[str, Any], lock.get("repository", {})).get(
            "h_patch_head"
        )
        != h_mcalj
    ):
        raise _error("E0-MCALL historical P-E0-MCALJ canonical payload drifted")
    schema = mcal._load_json_object(mcalj.DEFAULT_PATCH_LOCK_SCHEMA, repo_root=repo_root)
    try:
        mcal.validate_json_schema(lock, schema)
    except mcal.ClosureContractError as exc:
        raise _error("E0-MCALL historical P-E0-MCALJ schema drifted") from exc
    mcalj._validate_timestamp(lock.get("generated_at_utc"))
    mcalj._validate_verification(lock.get("verification"), repo_root=repo_root)
    if lock.get("authorizations") != mcalj.UNPUBLISHED_AUTHORIZATIONS:
        raise _error("E0-MCALL historical P-E0-MCALJ authorizations drifted")
    lock_record = {
        "role": "final_calibration_platt_parameter_dialect_patch_lock",
        "path": mcalj.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "bytes": len(lock_bytes),
        "sha256": _sha256_bytes(lock_bytes),
    }
    if companion_bytes != mcalj._canonical_json_bytes(
        mcalj._expected_companion(lock, lock_record)
    ):
        raise _error("E0-MCALL historical P-E0-MCALJ companion drifted")
    return {
        "gate": "P-E0-MCALJ",
        "commit": p_mcalj,
        "parent_h_mcalj": h_mcalj,
        "p_component_count": 2,
        "p_components": records,
        "p_components_sha256": mcal._digest_records(records),
        "lock_payload_sha256": _sha256_bytes(lock_bytes),
        "companion_sha256": _sha256_bytes(companion_bytes),
        "manifest_written_last": companion.get("manifest_written_last") is True,
        "historical_scientific_inputs_rehashed": False,
        "science_payloads_opened": False,
    }


def _validate_r8_bundle_science_free(*, repo_root: Path) -> dict[str, Any]:
    """Validate the sealed R8 bytes without following scientific inputs."""

    records: list[dict[str, Any]] = []
    payloads: dict[str, bytes] = {}
    for expected in R8_OUTPUT_CONTRACT:
        path_text = cast(str, expected["path"])
        path = Path(path_text)
        payload, metadata = mcal._read_regular_bytes_and_metadata(
            path,
            repo_root=repo_root,
            expected_mode=0o644,
            require_nlink_one=True,
        )
        observed = {
            "path": path_text,
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
        }
        if observed != expected or not stat.S_ISREG(metadata.st_mode):
            raise _error(f"E0-MCALL immutable R8 output drifted: {path_text}")
        records.append(observed)
        payloads[path_text] = payload

    specs_path = mcal.CALIBRATOR_SPECS_PATH.as_posix()
    calibration_manifest_path = mcal.FINAL_CALIBRATION_MANIFEST_PATH.as_posix()
    e7_manifest_path = mcal.ANFIS_LEARNING_CURVE_MANIFEST_PATH.as_posix()
    specs = mcal._parse_json_bytes(
        payloads[specs_path], context="sealed MCALL calibrator specs"
    )
    calibration_manifest = mcal._parse_json_bytes(
        payloads[calibration_manifest_path],
        context="sealed MCALL calibration manifest",
    )
    e7_manifest = mcal._parse_json_bytes(
        payloads[e7_manifest_path], context="sealed MCALL E7 manifest"
    )
    if (
        not isinstance(specs, Mapping)
        or not isinstance(calibration_manifest, Mapping)
        or not isinstance(e7_manifest, Mapping)
        or payloads[specs_path] != mcalj._canonical_json_bytes(specs)
        or payloads[calibration_manifest_path]
        != mcalj._canonical_json_bytes(calibration_manifest)
        or payloads[e7_manifest_path] != mcalj._canonical_json_bytes(e7_manifest)
    ):
        raise _error("E0-MCALL sealed R8 JSON canonicality drifted")

    expected_boundary = {
        "development_only": True,
        "final_evaluation_run": False,
        "future_outcomes_accessed": False,
        "holdout_accessed": False,
        "post_2021_rows_accessed": False,
    }
    calibration_keys = {
        "authority_sha256",
        "execution_policy",
        "experiment_id",
        "gate",
        "group_counts",
        "input_filter_evidence",
        "inputs",
        "outputs",
        "schema_version",
        "scientific_boundary",
        "status",
        "temporal_protocol",
    }
    e7_keys = {
        "authority_sha256",
        "completed_module_fit_count",
        "completed_slot_count",
        "experiment_id",
        "gate",
        "inputs",
        "new_e7_fit_count",
        "outputs",
        "post_hoc_substitution_performed",
        "primary_fit_reuse_count",
        "primary_slots_untouched",
        "resource_failure_count",
        "saturation_claim_authorized",
        "schema_version",
        "scientific_boundary",
        "silent_omission",
        "slot_order",
        "status",
        "terminal_evidence",
        "terminal_row_count",
    }
    authority_sha256 = calibration_manifest.get("authority_sha256")
    if (
        set(calibration_manifest) != calibration_keys
        or calibration_manifest.get("gate") != mcalj.PATCH_GATE
        or calibration_manifest.get("status") != "completed_unpublished"
        or calibration_manifest.get("schema_version")
        != "closure_final_calibration_manifest_v1"
        or calibration_manifest.get("scientific_boundary") != expected_boundary
        or not isinstance(calibration_manifest.get("inputs"), list)
        or len(cast(list[Any], calibration_manifest["inputs"])) != 97
        or calibration_manifest.get("outputs")
        != [dict(record) for record in R8_OUTPUT_CONTRACT[:5]]
        or set(e7_manifest) != e7_keys
        or e7_manifest.get("gate") != mcalj.PATCH_GATE
        or e7_manifest.get("status") != "terminal"
        or e7_manifest.get("schema_version")
        != "closure_anfis_learning_curve_manifest_v1"
        or e7_manifest.get("authority_sha256") != authority_sha256
        or e7_manifest.get("scientific_boundary") != expected_boundary
        or not isinstance(e7_manifest.get("inputs"), list)
        or len(cast(list[Any], e7_manifest["inputs"])) != 15
        or e7_manifest.get("outputs") != [dict(R8_OUTPUT_CONTRACT[6])]
        or e7_manifest.get("terminal_row_count") != 15
        or e7_manifest.get("completed_slot_count") != 5
        or e7_manifest.get("resource_failure_count") != 10
        or e7_manifest.get("completed_module_fit_count") != 15
        or e7_manifest.get("new_e7_fit_count") != 15
        or e7_manifest.get("primary_fit_reuse_count") != 0
        or e7_manifest.get("primary_slots_untouched") is not True
        or e7_manifest.get("silent_omission") is not False
        or e7_manifest.get("saturation_claim_authorized") is not False
        or e7_manifest.get("post_hoc_substitution_performed") is not False
    ):
        raise _error("E0-MCALL sealed R8 manifest dialect drifted")

    try:
        calibrators = mcalj._validate_calibrator_specs(specs)
    except mcalj.FinalCalibrationError as exc:
        raise _error(_translate_predecessor_error(str(exc))) from exc
    if (
        len(calibrators) != 66
        or not isinstance(specs.get("split_conformal_q_c"), list)
        or len(cast(list[Any], specs["split_conformal_q_c"])) != 90
    ):
        raise _error("E0-MCALL sealed calibrator specification drifted")

    producer_records: list[dict[str, Any]] = []
    for expected in mcalk.PRODUCER_PROVENANCE_CONTRACT:
        path = Path(cast(str, expected["path"]))
        mode, oid = mcal._git_mode_oid(repo_root, mcalk.H_MCALJ_COMMIT, path)
        git_payload = mcal._git_blob_bytes(repo_root, mcalk.H_MCALJ_COMMIT, path)
        physical = mcal._read_regular_bytes(path, repo_root=repo_root)
        observed = {
            "role": expected["role"],
            "path": path.as_posix(),
            "commit": mcalk.H_MCALJ_COMMIT,
            "git_mode": mode,
            "git_oid": oid,
            "bytes": len(git_payload),
            "sha256": _sha256_bytes(git_payload),
        }
        if observed != expected or physical != git_payload:
            raise _error(f"E0-MCALL R8 producer provenance drifted: {path}")
        producer_records.append(observed)

    return {
        "gate": mcalk.PATCH_GATE,
        "status": "immutable_r8_validated",
        "r8_output_count": 8,
        "calibration_output_count": 6,
        "e7_output_count": 2,
        "r_lifecycle_state": "both_bundles_completed_unpublished",
        "authority_sha256": authority_sha256,
        "r8_outputs": records,
        "r8_outputs_sha256": mcal._digest_records(records),
        "producer_provenance": producer_records,
        "producer_provenance_sha256": mcal._digest_records(producer_records),
        "manifest_reproducibility_contract": _deep_copy(
            MANIFEST_REPRODUCIBILITY_CONTRACT
        ),
    }


def _historical_h_mcalk_authority(*, repo_root: Path) -> dict[str, Any]:
    if (
        mcal._single_parent(repo_root, BASE_H_MCALK_COMMIT, context="H-E0-MCALK")
        != HISTORICAL_P_MCALJ_COMMIT
    ):
        raise _error("E0-MCALL historical H-E0-MCALK parent drifted")
    scope = mcal._git_scope(
        repo_root, HISTORICAL_P_MCALJ_COMMIT, BASE_H_MCALK_COMMIT
    )
    expected_scope = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(H_MCALK_PATHS),
    }
    if scope != expected_scope:
        raise _error("E0-MCALL historical H-E0-MCALK scope drifted")
    records = [
        {
            **_git_record_at_commit(
                path,
                role="superseded_h_mcalk_component",
                commit=BASE_H_MCALK_COMMIT,
                repo_root=repo_root,
            ),
            "commit": BASE_H_MCALK_COMMIT,
        }
        for path in H_MCALK_PATHS
    ]
    for record in records:
        path_text = cast(str, record["path"])
        if path_text == PRECOMMIT_PATH:
            continue
        physical = mcal._read_regular_bytes(Path(path_text), repo_root=repo_root)
        historical = mcal._git_blob_bytes(
            repo_root, BASE_H_MCALK_COMMIT, Path(path_text)
        )
        if physical != historical:
            raise _error(
                f"E0-MCALL preserved H-MCALK component drifted: {path_text}"
            )
    predecessor = _historical_p_mcalj_git_authority(repo_root=repo_root)
    if (
        predecessor.get("gate") != "P-E0-MCALJ"
        or predecessor.get("commit") != HISTORICAL_P_MCALJ_COMMIT
    ):
        raise _error("E0-MCALL P-E0-MCALJ predecessor authority drifted")
    return {
        "gate": "H-E0-MCALK",
        "commit": BASE_H_MCALK_COMMIT,
        "parent_p_mcalj": HISTORICAL_P_MCALJ_COMMIT,
        "scope": scope,
        "component_count": 6,
        "components": records,
        "components_sha256": mcal._digest_records(records),
        "p_mcalk_published": False,
        "p_mcalk_lock_present": False,
        "r8_rewrite_performed": False,
    }


def _historical_published_lock_records(*, repo_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in HISTORICAL_PUBLISHED_LOCK_PATHS:
        physical = mcal._read_regular_bytes(path, repo_root=repo_root)
        mode, oid = mcal._git_mode_oid(repo_root, BASE_H_MCALK_COMMIT, path)
        historical = mcal._git_blob_bytes(repo_root, BASE_H_MCALK_COMMIT, path)
        if mode != "100644" or physical != historical:
            raise _error(
                f"E0-MCALL historical published lock drifted: {path.as_posix()}"
            )
        records.append(
            {
                "role": "historical_published_final_calibration_lock",
                "path": path.as_posix(),
                "bytes": len(physical),
                "sha256": _sha256_bytes(physical),
                "git_oid": oid,
                "git_mode": mode,
            }
        )
    if len(records) != 18 or len({record["path"] for record in records}) != 18:
        raise _error("E0-MCALL historical published lock inventory drifted")
    return records


def _require_coordination_namespace(
    *,
    repo_root: Path,
    current_outputs_state: str,
    owned_guard: Any | None = None,
) -> dict[str, Any]:
    if current_outputs_state not in {"absent", "present"}:
        raise _error("E0-MCALL current-output namespace state drifted")
    historical = _historical_published_lock_records(repo_root=repo_root)
    occupied_never = [
        path.as_posix()
        for path in NEVER_PUBLISHED_LOCK_PATHS
        if mcal._entry_exists(path, repo_root=repo_root)
    ]
    if occupied_never:
        raise _error(
            f"E0-MCALL never-published lock namespace is occupied: {occupied_never}"
        )
    current_present = [
        path.as_posix()
        for path in CURRENT_LOCK_PATHS
        if mcal._entry_exists(path, repo_root=repo_root)
    ]
    expected_current = (
        []
        if current_outputs_state == "absent"
        else [path.as_posix() for path in CURRENT_LOCK_PATHS]
    )
    if current_present != expected_current:
        raise _error("E0-MCALL current lock namespace state drifted")
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
        mcalk.mcalj._require_owned_guard_identity(owned_guard)
        allowed_guard = LOCKER_GUARD_PATH
    occupied_coordination = [
        path.as_posix()
        for path in COORDINATION_NAMESPACE_PATHS
        if path != allowed_guard
        if mcal._entry_exists(path, repo_root=repo_root)
    ]
    if occupied_coordination:
        raise _error(
            "E0-MCALL coordination namespace is occupied: "
            f"{occupied_coordination}"
        )
    if mcal._entry_exists(Path(mcal.mze.OUTCOME_ACCESS_LOG), repo_root=repo_root):
        raise _error("E0-MCALL outcome access log must remain absent")
    if any(
        mcal._entry_exists(Path(path), repo_root=repo_root)
        for path in mcal.mze.E0_M_PATHS
    ):
        raise _error("E0-MCALL final E0-M namespace must remain absent")
    return {
        "historical_published_lock_count": 18,
        "historical_published_locks": historical,
        "historical_published_locks_sha256": mcal._digest_records(historical),
        "never_published_lock_present_count": 0,
        "current_lock_present_count": len(current_present),
        "coordination_present_count": 0,
        "coordination_forbidden_count": 46,
        "owned_current_guard_present": owned_guard is not None,
        "outcome_access_log_absent": True,
    }


def _candidate_status_is_exact(repo_root: Path) -> bool:
    records = mcal._workspace_status_records(repo_root)
    expected_paths = set(PATCH_PATHS) | {path.as_posix() for path in R_OUTPUT_PATHS}
    if {path for _, path in records} != expected_paths:
        return False
    by_path = {path: code for code, path in records}
    for path in PATCH_PATHS:
        allowed = {" M", "M ", "MM"} if path == PRECOMMIT_PATH else {"??", "A "}
        if by_path[path] not in allowed:
            return False
    return all(by_path[path.as_posix()] == "??" for path in R_OUTPUT_PATHS)


def _h_patch_authority(
    *, repo_root: Path, verify_remote: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    if type(verify_remote) is not bool:
        raise _error("E0-MCALL remote policy must be an exact boolean")
    head = mcal._git_head(repo_root)
    branch = cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
    if branch != "main":
        raise _error("E0-MCALL requires branch main")
    expected_scope = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(PATCH_PATHS),
    }
    candidate = head == BASE_H_MCALK_COMMIT
    if candidate:
        if not _candidate_status_is_exact(repo_root):
            raise _error("E0-MCALL candidate workspace is not exact 1M+5A plus R8")
        component_commit: str | None = None
        h_head = BASE_H_MCALK_COMMIT
        scope = expected_scope
    else:
        if (
            mcal._single_parent(repo_root, head, context="H-E0-MCALL")
            != BASE_H_MCALK_COMMIT
        ):
            raise _error("E0-MCALL published H parent drifted")
        scope = mcal._git_scope(repo_root, BASE_H_MCALK_COMMIT, head)
        expected_r = [
            ("??", path)
            for path in sorted(output.as_posix() for output in R_OUTPUT_PATHS)
        ]
        if scope != expected_scope or mcal._workspace_status_records(repo_root) != expected_r:
            raise _error("E0-MCALL published H scope/worktree drifted")
        component_commit = head
        h_head = head
    components = [
        mcal._git_artifact_record(
            Path(path),
            role="final_calibration_r8_coordination_namespace_revalidation_patch_component",
            repo_root=repo_root,
            commit=component_commit,
            expected_mode=PATCH_COMPONENT_GIT_MODES[path],
        )
        for path in PATCH_PATHS
    ]
    tracking = mcal._git_head(repo_root, "origin/main")
    expected_ref = BASE_H_MCALK_COMMIT if candidate else head
    if tracking != expected_ref:
        raise _error("E0-MCALL H tracking ref drifted")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if remote != expected_ref:
        raise _error("E0-MCALL H remote ref drifted")
    return (
        {
            "base_h_mcalk_commit": BASE_H_MCALK_COMMIT,
            "historical_p_mcalj_commit": HISTORICAL_P_MCALJ_COMMIT,
            "h_patch_head": h_head,
            "branch": branch,
            "remote_head": remote,
            "scope": scope,
        },
        {
            "gate": "H-E0-MCALL",
            "component_count": 6,
            "added_count": 5,
            "modified_count": 1,
            "components": components,
            "components_sha256": mcal._digest_records(components),
        },
    )


@_error_boundary
def preflight_final_calibration_r8_coordination_namespace_revalidation_patch_schema(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    validator = getattr(mcal.closure_contract, "_assert_supported_json_schema", None)
    if validator is None:
        raise _error("E0-MCALL closed schema preflight is unavailable")
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
                role="final_calibration_r8_coordination_namespace_revalidation_patch_lock_schema",
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
    schema = preflight_final_calibration_r8_coordination_namespace_revalidation_patch_schema(
        repo_root=repo_root
    )
    historical_h = _historical_h_mcalk_authority(repo_root=repo_root)
    predecessor = _historical_p_mcalj_git_authority(repo_root=repo_root)
    r8 = _validate_r8_bundle_science_free(repo_root=repo_root)
    namespace = _require_coordination_namespace(
        repo_root=repo_root,
        current_outputs_state="absent" if require_prelock_namespace else "present",
    )
    if not require_prelock_namespace:
        namespace = {**namespace, "current_lock_present_count": 0}
    historical = cast(Sequence[Mapping[str, Any]], historical_h["components"])
    return {
        "repository": _deep_copy(repository),
        "superseded_check_only": _deep_copy(SUPERSEDED_CHECK_ONLY),
        "historical_h_mcalk_authority": historical_h,
        "p_mcalj_authority": predecessor,
        "h_patch": _deep_copy(h_patch),
        "coordination_namespace_contract": _deep_copy(
            COORDINATION_NAMESPACE_CONTRACT
        ),
        "coordination_namespace": namespace,
        "manifest_reproducibility_contract": _deep_copy(
            MANIFEST_REPRODUCIBILITY_CONTRACT
        ),
        "generic_manifest_findings_contract": _deep_copy(
            GENERIC_MANIFEST_FINDINGS_CONTRACT
        ),
        "historical_inputs": _deep_copy(historical),
        "historical_inputs_sha256": mcal._digest_records(historical),
        "r8_bundle": r8,
        "scientific_boundary": {
            "development_only": True,
            "holdout_row_count": 0,
            "post_2021_row_count": 0,
            "outcome_path_count": 0,
            "outcome_access_authorized": False,
            "scientific_rerun_authorized": False,
        },
        "prelock": {
            "historical_published_lock_count": 18,
            "never_published_lock_present_count": 0,
            "p_output_present_count": 0,
            "r8_output_present_count": 8,
            "coordination_present_count": 0,
            "coordination_forbidden_count": 46,
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
def collect_final_calibration_r8_coordination_namespace_revalidation_patch_prelock_state(
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
def build_final_calibration_r8_coordination_namespace_revalidation_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any] | None = None,
    *,
    generated_at_utc: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root
    required = {
        "repository",
        "superseded_check_only",
        "historical_h_mcalk_authority",
        "p_mcalj_authority",
        "h_patch",
        "coordination_namespace_contract",
        "coordination_namespace",
        "manifest_reproducibility_contract",
        "generic_manifest_findings_contract",
        "historical_inputs",
        "historical_inputs_sha256",
        "r8_bundle",
        "scientific_boundary",
        "prelock",
        "schema_preflight",
    }
    if not isinstance(prelock, Mapping) or set(prelock) != required:
        raise _error("E0-MCALL prelock dialect drifted")
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
        raise _error("E0-MCALL generated timestamp is absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _error("E0-MCALL generated timestamp is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _error("E0-MCALL generated timestamp must be timezone-aware")


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
        raise _error("E0-MCALL verification evidence dialect drifted")
    if _canonical_json_bytes(value["schema_preflight"]) != _canonical_json_bytes(
        preflight_final_calibration_r8_coordination_namespace_revalidation_patch_schema(
            repo_root=repo_root
        )
    ):
        raise _error("E0-MCALL schema verification evidence drifted")
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
        or type(focused.get("test_count")) is not int
        or cast(int, focused.get("test_count")) <= 0
        or (FOCUSED_TEST_COUNT > 0 and focused.get("test_count") != FOCUSED_TEST_COUNT)
        or focused.get("skipped_count") != 0
        or focused.get("deselected_count") != 0
    ):
        raise _error("E0-MCALL focused verification evidence drifted")
    mcal._validate_command_evidence(
        {key: focused[key] for key in base_keys},
        expected_command=FOCUSED_TEST_COMMAND,
        context="focused_tests",
    )


@_error_boundary
def validate_final_calibration_r8_coordination_namespace_revalidation_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    verify_remote: bool = False,
) -> dict[str, Any]:
    root = _root(repo_root)
    if not isinstance(payload, Mapping):
        raise _error("E0-MCALL lock payload must be an object")
    schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    try:
        mcal.validate_json_schema(payload, schema)
    except mcal.ClosureContractError as exc:
        raise _error(_translate_predecessor_error(str(exc))) from exc
    _validate_timestamp(payload.get("generated_at_utc"))
    _validate_verification(payload.get("verification"), repo_root=root)
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise _error("E0-MCALL unpublished authorizations drifted")
    state = collect_final_calibration_r8_coordination_namespace_revalidation_patch_prelock_state(
        verify_remote=verify_remote, repo_root=root
    )
    expected = build_final_calibration_r8_coordination_namespace_revalidation_patch_lock_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=cast(str, payload["generated_at_utc"]),
    )
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("E0-MCALL lock semantic reconstruction drifted")
    return dict(payload)


_OwnedOutput = mcalk._OwnedOutput


def _public_artifact_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in ("role", "path", "bytes", "sha256")}


def _expected_companion(
    payload: Mapping[str, Any], lock_record: Mapping[str, Any]
) -> dict[str, Any]:
    predecessor = cast(Mapping[str, Any], payload["p_mcalj_authority"])
    patch = cast(Mapping[str, Any], payload["h_patch"])
    r8 = cast(Mapping[str, Any], payload["r8_bundle"])
    prior = cast(Sequence[Mapping[str, Any]], predecessor["p_components"])
    current = cast(Sequence[Mapping[str, Any]], patch["components"])
    outputs = cast(Sequence[Mapping[str, Any]], r8["r8_outputs"])
    r8_inputs = [
        {
            "role": "immutable_r8_output",
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
        raise _error("E0-MCALL companion physical input set drifted")
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
        raise _error("E0-MCALL companion historical input set drifted")
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
        raise _error("E0-MCALL publication requires frozen verification evidence")
    _validate_verification(verification, repo_root=repo_root)


def _physical_snapshot(repo_root: Path) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for path_text in (*P_MCALJ_PATHS, *PATCH_PATHS):
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
            raise _error(f"E0-MCALL immutable R8 snapshot drifted: {path_text}")
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
        raise _error("E0-MCALL physical input snapshot is not exact16")
    return tuple(records)


def _require_physical_snapshot(
    expected: Sequence[Mapping[str, Any]], *, repo_root: Path, context: str
) -> None:
    if _canonical_json_bytes(expected) != _canonical_json_bytes(
        _physical_snapshot(repo_root)
    ):
        raise _error(f"E0-MCALL physical/R8 identity changed {context}")


def _require_repository_checkpoint(
    *,
    repo_root: Path,
    expected_head: str,
    verify_remote: bool,
    p_outputs_present: bool,
    context: str,
) -> None:
    expected_paths = [path.as_posix() for path in R_OUTPUT_PATHS]
    if p_outputs_present:
        expected_paths.extend(path.as_posix() for path in CURRENT_LOCK_PATHS)
    if (
        cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
        != "main"
        or mcal._git_head(repo_root) != expected_head
        or mcal._git_head(repo_root, "origin/main") != expected_head
        or mcal._workspace_status_records(repo_root)
        != [("??", path) for path in sorted(expected_paths)]
    ):
        raise _error(f"E0-MCALL repository changed {context}")
    if verify_remote and mcal._live_remote_main_head(repo_root) != expected_head:
        raise _error(f"E0-MCALL live remote changed {context}")


def _parse_canonical_json_with_metadata(
    path: Path, *, repo_root: Path
) -> tuple[dict[str, Any], bytes, os.stat_result]:
    payload, metadata = mcal._read_regular_bytes_and_metadata(
        path, repo_root=repo_root, expected_mode=0o644, require_nlink_one=True
    )
    value = mcal._parse_json_bytes(payload, context=path.as_posix())
    if not isinstance(value, dict) or payload != _canonical_json_bytes(value):
        raise _error(f"E0-MCALL canonical JSON drifted: {path.as_posix()}")
    return value, payload, metadata


def _published_h_state(h_head: str, *, repo_root: Path) -> dict[str, Any]:
    if h_head == BASE_H_MCALK_COMMIT or re.fullmatch(r"[0-9a-f]{40}", h_head) is None:
        raise _error("E0-MCALL published H commit is absent")
    if (
        mcal._single_parent(repo_root, h_head, context="H-E0-MCALL")
        != BASE_H_MCALK_COMMIT
    ):
        raise _error("E0-MCALL published H parent drifted")
    scope = mcal._git_scope(repo_root, BASE_H_MCALK_COMMIT, h_head)
    expected_scope = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(PATCH_PATHS),
    }
    if scope != expected_scope:
        raise _error("E0-MCALL published H scope drifted")
    components = [
        mcal._git_artifact_record(
            Path(path),
            role="final_calibration_r8_coordination_namespace_revalidation_patch_component",
            repo_root=repo_root,
            commit=h_head,
            expected_mode=PATCH_COMPONENT_GIT_MODES[path],
        )
        for path in PATCH_PATHS
    ]
    return _state_for_h(
        repository={
            "base_h_mcalk_commit": BASE_H_MCALK_COMMIT,
            "historical_p_mcalj_commit": HISTORICAL_P_MCALJ_COMMIT,
            "h_patch_head": h_head,
            "branch": "main",
            "remote_head": h_head,
            "scope": scope,
        },
        h_patch={
            "gate": "H-E0-MCALL",
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
        raise _error("E0-MCALL published authorizations drifted")
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("E0-MCALL published H binding is absent")
    state = _published_h_state(cast(str, repository["h_patch_head"]), repo_root=repo_root)
    expected = build_final_calibration_r8_coordination_namespace_revalidation_patch_lock_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=cast(str, payload["generated_at_utc"]),
    )
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("E0-MCALL published lock reconstruction drifted")


def _validate_p_publication(
    payload: Mapping[str, Any], *, verify_remote: bool, repo_root: Path
) -> dict[str, str]:
    if type(verify_remote) is not bool:
        raise _error("E0-MCALL remote policy must be an exact boolean")
    repository = cast(Mapping[str, Any], payload["repository"])
    h_head = cast(str, repository["h_patch_head"])
    head = mcal._git_head(repo_root)
    workspace = mcal._workspace_status_records(repo_root)
    r_paths = {path.as_posix() for path in R_OUTPUT_PATHS}
    if (
        {path for _, path in workspace} != r_paths
        or {code for code, _ in workspace} not in ({"??"}, {"A "})
    ):
        raise _error("E0-MCALL published P worktree is not exact R8")
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
        or mcal._single_parent(repo_root, head, context="P-E0-MCALL") != h_head
        or mcal._git_scope(repo_root, h_head, head) != expected_scope
    ):
        raise _error("E0-MCALL published P topology drifted")
    tracking = mcal._git_head(repo_root, "origin/main")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != head or remote != head:
        raise _error("E0-MCALL published P refs drifted")
    for path in CURRENT_LOCK_PATHS:
        physical = mcal._read_regular_bytes(path, repo_root=repo_root)
        mode, _ = mcal._git_mode_oid(repo_root, head, path)
        if mode != "100644" or physical != mcal._git_blob_bytes(repo_root, head, path):
            raise _error(f"E0-MCALL published P physical/Git binding drifted: {path}")
    return {"h_patch_head": h_head, "p_patch_head": head, "remote_head": remote}


@_error_boundary
def publish_final_calibration_r8_coordination_namespace_revalidation_patch_lock_bundle(
    payload: Mapping[str, Any], *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _root(repo_root)
    try:
        lock_bytes = _canonical_json_bytes(payload)
        frozen = json.loads(lock_bytes)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise _error("E0-MCALL publication payload is not canonical JSON") from exc
    if not isinstance(frozen, dict) or _canonical_json_bytes(frozen) != lock_bytes:
        raise _error("E0-MCALL publication payload must be a canonical object")
    payload = frozen
    repository = payload.get("repository")
    if (
        not isinstance(repository, Mapping)
        or repository.get("h_patch_head") == BASE_H_MCALK_COMMIT
    ):
        raise _error("E0-MCALL H must be published before P publication")
    _require_publication_verification(payload, repo_root=root)
    validate_final_calibration_r8_coordination_namespace_revalidation_patch_lock_payload(
        payload, repo_root=root, verify_remote=True
    )
    snapshot = _physical_snapshot(root)
    initial_head = mcal._git_head(root)
    if initial_head != repository.get("h_patch_head"):
        raise _error("E0-MCALL H refs drifted before publication")
    _require_coordination_namespace(repo_root=root, current_outputs_state="absent")
    _require_physical_snapshot(snapshot, repo_root=root, context="at baseline")
    _require_repository_checkpoint(
        repo_root=root,
        expected_head=initial_head,
        verify_remote=True,
        p_outputs_present=False,
        context="at baseline",
    )
    guard: Any | None = None
    published: list[_OwnedOutput] = []
    committed = False
    try:
        guard = mt._acquire_publication_guard(
            LOCKER_GUARD_PATH,
            b"E0-MCALL final calibration coordination namespace lock publication\n",
            repo_root=root,
        )
        _require_coordination_namespace(
            repo_root=root, current_outputs_state="absent", owned_guard=guard
        )
        _require_physical_snapshot(snapshot, repo_root=root, context="after guard")
        lock_output = mcalk._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_PATH, lock_bytes, repo_root=root
        )
        published.append(lock_output)
        lock_record = {
            "role": "final_calibration_r8_coordination_namespace_revalidation_patch_lock",
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "bytes": len(lock_bytes),
            "sha256": _sha256_bytes(lock_bytes),
        }
        companion = _expected_companion(payload, lock_record)
        companion_bytes = _canonical_json_bytes(companion)
        companion_output = mcalk._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH, companion_bytes, repo_root=root
        )
        published.append(companion_output)
        publication = ((lock_output, lock_bytes), (companion_output, companion_bytes))
        for output, expected in publication:
            mcalk.mcalj._validate_owned_output_bytes(
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
        _require_coordination_namespace(
            repo_root=root, current_outputs_state="present"
        )
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
                mcalk.mcalj._validate_owned_output_bytes(
                    output,
                    expected,
                    repo_root=root,
                    context=f"ownership transfer pass {pass_index}",
                )
            mcalk.mcalj.mcali._require_owned_identity_set(
                [output for output, _ in publication],
                context=f"MCALL ownership transfer pass {pass_index}",
            )
        _require_coordination_namespace(repo_root=root, current_outputs_state="present")
        committed = True
        return dict(payload), companion
    except BaseException as exc:
        rollback = mcalk._rollback_outputs_best_effort(published)
        if rollback is not None:
            exc.add_note(str(rollback))
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, FinalCalibrationR8CoordinationNamespaceRevalidationPatchError):
            raise
        raise _error("E0-MCALL lock bundle publication failed") from exc
    finally:
        if guard is not None:
            try:
                mt._release_publication_guard(guard, tolerate_foreign=True)
            except Exception:
                pass
        if committed:
            for output in reversed(published):
                try:
                    mcalk.mcalj._close_owned_output(output)
                except Exception:
                    pass


def _validate_unpublished_p_repository(
    *, h_head: str, verify_remote: bool, repo_root: Path
) -> str:
    if type(verify_remote) is not bool:
        raise _error("E0-MCALL unpublished P remote policy must be exact boolean")
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
        or mcal._single_parent(repo_root, h_head, context="H-E0-MCALL")
        != BASE_H_MCALK_COMMIT
        or mcal._git_scope(repo_root, BASE_H_MCALK_COMMIT, h_head)
        != expected_h_scope
    ):
        raise _error("E0-MCALL unpublished P requires exact published H topology")
    tracking = mcal._git_head(repo_root, "origin/main")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != h_head or remote != h_head:
        raise _error("E0-MCALL unpublished P H refs drifted")
    r_status = [("??", path.as_posix()) for path in R_OUTPUT_PATHS]
    p_untracked = [("??", path.as_posix()) for path in CURRENT_LOCK_PATHS]
    p_staged = [("A ", path.as_posix()) for path in CURRENT_LOCK_PATHS]
    observed = sorted(mcal._workspace_status_records(repo_root))
    if observed == sorted((*p_untracked, *r_status)):
        return "untracked"
    if observed == sorted((*p_staged, *r_status)):
        return "staged"
    raise _error("E0-MCALL unpublished P workspace is not exact P2 plus R8")


@_error_boundary
def validate_final_calibration_r8_coordination_namespace_revalidation_unpublished_lock_bundle(
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
        raise _error("E0-MCALL unpublished P H binding is absent")
    h_head = cast(str, repository["h_patch_head"])
    stage_state = _validate_unpublished_p_repository(
        h_head=h_head, verify_remote=verify_remote, repo_root=root
    )
    _validate_published_lock_payload(lock, repo_root=root)
    lock_record = mcal._file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="final_calibration_r8_coordination_namespace_revalidation_patch_lock",
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
        raise _error("E0-MCALL unpublished P companion drifted")
    namespace = _require_coordination_namespace(
        repo_root=root, current_outputs_state="present"
    )
    snapshot = _physical_snapshot(root)
    r8 = _validate_r8_bundle_science_free(repo_root=root)
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
        or mcalk.mcalj._metadata_identity(recaptured_lock_metadata)
        != mcalk.mcalj._metadata_identity(lock_metadata)
        or mcalk.mcalj._metadata_identity(recaptured_companion_metadata)
        != mcalk.mcalj._metadata_identity(companion_metadata)
    ):
        raise _error("E0-MCALL unpublished P changed during semantic validation")
    _require_physical_snapshot(
        snapshot, repo_root=root, context="during unpublished P validation"
    )
    if _require_coordination_namespace(
        repo_root=root, current_outputs_state="present"
    ) != namespace:
        raise _error("E0-MCALL namespace changed during unpublished P validation")
    if (
        _validate_unpublished_p_repository(
            h_head=h_head, verify_remote=verify_remote, repo_root=root
        )
        != stage_state
    ):
        raise _error("E0-MCALL unpublished P stage state changed during validation")
    return {
        "gate": PATCH_GATE,
        "status": "unpublished_p_mcall_lock_bundle_validated",
        "h_patch_head": h_head,
        "p_stage_state": stage_state,
        "p_output_count": 2,
        "physical_input_count": EXPECTED_COMPANION_INPUT_COUNT,
        "historical_input_count": EXPECTED_HISTORICAL_INPUT_COUNT,
        "companion_output_count": EXPECTED_COMPANION_OUTPUT_COUNT,
        "coordination_forbidden_count": 46,
        "coordination_present_count": 0,
        "r8_output_count": r8["r8_output_count"],
        "r8_outputs_sha256": r8["r8_outputs_sha256"],
        "r8_staging_authorized": False,
        "effective_authority": False,
        "scientific_rerun_authorized": False,
        "writes_performed": False,
    }


@_error_boundary
def load_effective_final_calibration_r8_coordination_namespace_revalidation_patch_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    lock, lock_bytes, lock_metadata = _parse_canonical_json_with_metadata(
        DEFAULT_PATCH_LOCK_PATH, repo_root=root
    )
    _validate_published_lock_payload(lock, repo_root=root)
    lock_record = mcal._file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="final_calibration_r8_coordination_namespace_revalidation_patch_lock",
        repo_root=root,
    )
    companion, companion_bytes, companion_metadata = _parse_canonical_json_with_metadata(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
    )
    if _canonical_json_bytes(companion) != _canonical_json_bytes(
        _expected_companion(lock, lock_record)
    ):
        raise _error("E0-MCALL published companion drifted")
    publication = _validate_p_publication(
        lock, verify_remote=verify_remote, repo_root=root
    )
    namespace = _require_coordination_namespace(
        repo_root=root, current_outputs_state="present"
    )
    r8 = _validate_r8_bundle_science_free(repo_root=root)
    snapshot = _physical_snapshot(root)
    _require_coordination_namespace(repo_root=root, current_outputs_state="present")
    recaptured_lock, recaptured_bytes, recaptured_metadata = (
        _parse_canonical_json_with_metadata(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    )
    recaptured_companion, recaptured_companion_bytes, recaptured_companion_metadata = (
        _parse_canonical_json_with_metadata(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
        )
    )
    if (
        recaptured_lock != lock
        or recaptured_companion != companion
        or recaptured_bytes != lock_bytes
        or recaptured_companion_bytes != companion_bytes
        or mcalk.mcalj._metadata_identity(recaptured_metadata)
        != mcalk.mcalj._metadata_identity(lock_metadata)
        or mcalk.mcalj._metadata_identity(recaptured_companion_metadata)
        != mcalk.mcalj._metadata_identity(companion_metadata)
    ):
        raise _error("E0-MCALL P authority changed during effective loading")
    _require_physical_snapshot(snapshot, repo_root=root, context="during effective loading")
    if _require_coordination_namespace(
        repo_root=root, current_outputs_state="present"
    ) != namespace:
        raise _error("E0-MCALL namespace changed during effective loading")
    if _validate_p_publication(lock, verify_remote=verify_remote, repo_root=root) != publication:
        raise _error("E0-MCALL publication changed during effective loading")
    _require_coordination_namespace(repo_root=root, current_outputs_state="present")
    return {
        "gate": PATCH_GATE,
        "status": "effective",
        **publication,
        "lock": lock_record,
        "companion": mcal._file_record(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            role="final_calibration_r8_coordination_namespace_revalidation_patch_lock_manifest",
            repo_root=root,
        ),
        "authority_binding_sha256": _sha256_bytes(
            _canonical_json_bytes(
                {
                    "p_patch_head": publication["p_patch_head"],
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
        "expected_non_ok_findings": _deep_copy(GENERIC_MANIFEST_FINDINGS_CONTRACT),
        "r8_output_paths": [path.as_posix() for path in R_OUTPUT_PATHS],
        "calibration_output_present_count": 6,
        "e7_output_present_count": 2,
        "r_output_present_count": 8,
        "r_lifecycle_state": "both_bundles_completed_unpublished",
        "calibration_development_run_authorized": False,
        "e7_learning_curve_run_authorized": False,
        "calibration_one_shot_consumed": True,
        "e7_one_shot_consumed": True,
        "r_outputs_ready_for_staging": True,
        "r8_staging_authorized": True,
        "effective_authority": True,
        "scientific_rerun_authorized": False,
        "holdout_access_authorized": False,
        "post_2021_access_authorized": False,
        "outcome_access_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "dvc_commands_authorized": False,
        "dvc_push_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
        "writes_performed": False,
    }


@_error_boundary
def require_final_calibration_r8_coordination_namespace_revalidation_patch_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    return load_effective_final_calibration_r8_coordination_namespace_revalidation_patch_authority(
        verify_remote=verify_remote, repo_root=repo_root
    )


def _require_exact_r8_staged_scope(*, repo_root: Path) -> None:
    staged = cast(
        str,
        mcal._git(repo_root, "diff", "--cached", "--name-status", "--no-renames"),
    )
    observed: dict[str, str] = {}
    for line in staged.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] != "A" or fields[1] in observed:
            raise _error("E0-MCALL staged R8 scope dialect drifted")
        observed[fields[1]] = fields[0]
    if observed != R8_STAGED_SCOPE:
        raise _error("E0-MCALL staged R8 scope is not exact8A")
    if cast(str, mcal._git(repo_root, "diff", "--name-status")).strip():
        raise _error("E0-MCALL staged R8 has an unstaged tracked delta")
    if mcal._workspace_status_records(repo_root) != [
        ("A ", path) for path in sorted(R8_STAGED_SCOPE)
    ]:
        raise _error("E0-MCALL staged R8 workspace scope drifted")


@_error_boundary
def validate_final_calibration_r8_coordination_namespace_revalidation_adoption(
    *, repo_root: Path | None = None, require_staged: bool = True
) -> dict[str, Any]:
    if type(require_staged) is not bool:
        raise _error("E0-MCALL staged policy must be exact boolean")
    root = _root(repo_root)
    authority: dict[str, Any] | None = None
    if require_staged:
        authority = require_final_calibration_r8_coordination_namespace_revalidation_patch_authority(
            verify_remote=True, repo_root=root
        )
    r8 = _validate_r8_bundle_science_free(repo_root=root)
    current_present_count = sum(
        mcal._entry_exists(path, repo_root=root) for path in CURRENT_LOCK_PATHS
    )
    if current_present_count not in {0, 2}:
        raise _error("E0-MCALL current lock bundle is partial")
    namespace_state = "present" if current_present_count == 2 else "absent"
    namespace = _require_coordination_namespace(
        repo_root=root, current_outputs_state=namespace_state
    )
    if require_staged:
        _require_exact_r8_staged_scope(repo_root=root)
    return {
        **r8,
        "gate": PATCH_GATE,
        "status": "r8_coordination_namespace_revalidation_adoption_validated",
        "expected_non_ok_findings": _deep_copy(GENERIC_MANIFEST_FINDINGS_CONTRACT),
        "coordination_forbidden_count": 46,
        "coordination_present_count": namespace["coordination_present_count"],
        "staged_scope_verified": require_staged,
        "effective_p_mcall_verified": authority is not None,
        "scientific_rerun_performed": False,
        "r8_rewrite_performed": False,
    }


@_error_boundary
def require_final_calibration_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    return require_final_calibration_r8_coordination_namespace_revalidation_patch_authority(
        verify_remote=verify_remote, repo_root=repo_root
    )


@_error_boundary
def require_final_calibration_run_namespace(
    *, runner: str, repo_root: Path | None = None
) -> dict[str, Any]:
    del repo_root
    if type(runner) is not str or runner not in {"calibration", "e7"}:
        raise _error("E0-MCALL run namespace requires calibration or e7")
    raise _error("E0-MCALL R8 is terminal; scientific rerun is not authorized")


def __getattr__(name: str) -> Any:
    return getattr(mcalk, name)
