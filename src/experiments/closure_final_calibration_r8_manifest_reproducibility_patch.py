"""Adopt the exact R8 manifest dialect under E0-MCALK.

The already-materialized R8 bundle is scientifically valid and immutable.  Its
two manifests deliberately use ``completed_unpublished`` and ``terminal`` and
omit a generic ``script`` field.  E0-MCALK binds those exact bytes, validates
them through the published E0-MCALJ output parsers, and exposes a fail-closed
adapter for the generic precommit consumer without rewriting any R output.
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
    closure_final_calibration_platt_parameter_dialect_patch as mcalj,
)

mcal = mcalj.mcal
mt = mcalj.mt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_P_MCALJ_COMMIT = "97f12b00b952829474a2937dccba6add783df074"
H_MCALJ_COMMIT = "05e846cfc3804a35f7550d6a2de9687b4450568d"
H_MCALJ_PARENT = "fbbb9ebb8260c43146ce6407d6629c20ce8cf4d9"
PATCH_GATE = "E0-MCALK"
FINAL_CALIBRATION_GATE = PATCH_GATE
EXPERIMENT_ID = "closure_v1"
LOCK_SCHEMA_VERSION = (
    "closure_final_calibration_r8_manifest_reproducibility_patch_lock_v1"
)
COMPANION_SCHEMA_VERSION = (
    "closure_final_calibration_r8_manifest_reproducibility_patch_lock_manifest_v1"
)

DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/"
    "final_calibration_r8_manifest_reproducibility_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "final_calibration_r8_manifest_reproducibility_patch_lock.json"
)
DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "final_calibration_r8_manifest_reproducibility_patch_lock_manifest.json"
)
DEFAULT_PATCH_MANIFEST_PATH = DEFAULT_PATCH_LOCK_MANIFEST_PATH
LOCKER_PATH = Path(
    "src/experiments/"
    "lock_closure_final_calibration_r8_manifest_reproducibility_patch.py"
)
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_e0_mcalk/"
    "final_calibration_r8_manifest_reproducibility_patch_lock.guard"
)

PRECOMMIT_PATH = "src/data/prepare_commit_artifacts.py"
CORE_PATH = (
    "src/experiments/"
    "closure_final_calibration_r8_manifest_reproducibility_patch.py"
)
TEST_PATH = (
    "tests/test_closure_final_calibration_r8_manifest_reproducibility_patch.py"
)
PATCH_PATHS = tuple(
    sorted(
        {
            DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
            "docs/closure_v1/"
            "E0_M_FINAL_CALIBRATION_R8_MANIFEST_REPRODUCIBILITY_PATCH_1.md",
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
P_MCALJ_PATHS = (
    mcalj.DEFAULT_PATCH_LOCK_PATH.as_posix(),
    mcalj.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
)
P_PATCH_PATHS = tuple(sorted(FINAL_CALIBRATION_P_STAGED_SCOPE))
R_OUTPUT_PATHS = tuple(mcalj.R_OUTPUT_PATHS)
R8_STAGED_SCOPE = {path.as_posix(): "A" for path in R_OUTPUT_PATHS}
FINAL_CALIBRATION_R_STAGED_SCOPE = dict(R8_STAGED_SCOPE)
CALIBRATION_MANIFEST_PATH = mcal.FINAL_CALIBRATION_MANIFEST_PATH
E7_MANIFEST_PATH = mcal.ANFIS_LEARNING_CURVE_MANIFEST_PATH

R8_OUTPUT_CONTRACT = (
    {
        "path": "reports/closure_v1/03_calibration/calibrator_specs.json",
        "bytes": 78958,
        "sha256": "151a1263879cb6838a69e974d763cc84fe01f36edb4c5836122afe19dcd10b76",
    },
    {
        "path": "reports/closure_v1/03_calibration/calibration_metrics.csv",
        "bytes": 7759,
        "sha256": "1d9a8db1d3b6ad0b314d354e27b3f5d525a04b2c81c2b57ee8b30586e7c33035",
    },
    {
        "path": "reports/closure_v1/03_calibration/alert_thresholds.csv",
        "bytes": 6180,
        "sha256": "2954b5767f45a954b205329c3abe4bb4b94bd9ad0e2bd469b71af422a69dcd3f",
    },
    {
        "path": "reports/closure_v1/03_calibration/ordinal_cutpoints.csv",
        "bytes": 4171,
        "sha256": "1cf261bc432c18ae31d2f27fb2a930a493a271d46b9e0b131feef41f5ec50329",
    },
    {
        "path": "reports/closure_v1/03_calibration/model_availability.csv",
        "bytes": 2918,
        "sha256": "0ab0103579248a3e3898e87db9fcbaa011b0a4238c664f11fdd7f5db26b225fb",
    },
    {
        "path": "reports/closure_v1/03_calibration/final_calibration_manifest.json",
        "bytes": 23325,
        "sha256": "e752ae806f3f2643c97c1054475b4ff1dfde886f4ffdaa45a060f8fae05a9310",
    },
    {
        "path": "reports/closure_v1/07_anfis_ablation/anfis_learning_curve.csv",
        "bytes": 7322,
        "sha256": "8a323af9719607ce663890ac174513c6b4f2343409d121b09c2a59d2b12bc0c7",
    },
    {
        "path": "reports/closure_v1/07_anfis_ablation/anfis_learning_curve_manifest.json",
        "bytes": 4991770,
        "sha256": "88dd2786aa4b8a442560301df7e9fa93aa63c3a95a51a2e855c98a9aab6ba9d1",
    },
)

GENERIC_MANIFEST_FINDINGS_CONTRACT = (
    {
        "level": "fail",
        "check": "manifest",
        "path": CALIBRATION_MANIFEST_PATH.as_posix(),
        "message": (
            "Experiment manifest status is `completed_unpublished`, "
            "expected `completed`."
        ),
    },
    {
        "level": "warn",
        "check": "manifest",
        "path": CALIBRATION_MANIFEST_PATH.as_posix(),
        "message": "Experiment manifest does not record the generating script.",
    },
    {
        "level": "fail",
        "check": "manifest",
        "path": E7_MANIFEST_PATH.as_posix(),
        "message": "Experiment manifest status is `terminal`, expected `completed`.",
    },
    {
        "level": "warn",
        "check": "manifest",
        "path": E7_MANIFEST_PATH.as_posix(),
        "message": "Experiment manifest does not record the generating script.",
    },
)

MANIFEST_REPRODUCIBILITY_CONTRACT = {
    "calibration_manifest_status": "completed_unpublished",
    "e7_manifest_status": "terminal",
    "generic_expected_status": "completed",
    "generic_script_field": "script",
    "r8_script_field_present": False,
    "generic_non_ok_finding_count": 4,
    "generic_failure_count": 2,
    "generic_warning_count": 2,
    "adoption_policy": "exact_multiset_after_strict_r8_validation_only",
    "r8_rewrite_authorized": False,
    "scientific_rerun_authorized": False,
    "staging_authorized": True,
}

FAILED_ATTEMPT = {
    "attempted_gate": "R-E0-MCALJ",
    "status": "failed_closed_exact_r8_preserved",
    "phase": "precommit_generic_manifest_validation",
    "failure_code": "sealed_r8_lifecycle_statuses_rejected_by_generic_completed_dialect",
    "precommit_exit_code": 1,
    "report_path": "tmp/pre_commit_artifacts_20260812T180346Z.md",
    "generic_failure_count": 2,
    "generic_warning_count": 2,
    "publication_guard_passed": True,
    "r8_output_count": 8,
    "r8_bytes_changed": False,
    "r8_rewrite_performed": False,
    "scientific_rerun_performed": False,
    "dvc_commands_run": False,
    "dvc_push_performed": False,
    "git_commit_performed": False,
    "git_push_performed": False,
    "retry_authorized": False,
}

PRODUCER_PROVENANCE_CONTRACT = (
    {
        "role": "final_calibration_manifest_producer",
        "path": "src/experiments/calibrate_closure_final_models.py",
        "commit": H_MCALJ_COMMIT,
        "git_mode": "100644",
        "git_oid": "f44db2f5402e9fc8acb2fb0ed52cb4aa6ffe5bd3",
        "bytes": 165719,
        "sha256": "a58e02444e7b7674dba9ce3f66eae8782990b7a566bd4daa8abbcc1c793eace6",
    },
    {
        "role": "anfis_learning_curve_manifest_producer",
        "path": "src/experiments/run_closure_anfis_learning_curve.py",
        "commit": H_MCALJ_COMMIT,
        "git_mode": "100644",
        "git_oid": "eab633cb8e8a8ae42fe9835a7df25493310aae22",
        "bytes": 78641,
        "sha256": "32d1ebc7953d2306a3807601ae7ffc60995ac6c9f2927c3784158544ec927634",
    },
)

EXPECTED_COMPANION_INPUT_COUNT = 16
EXPECTED_HISTORICAL_INPUT_COUNT = 1
EXPECTED_COMPANION_OUTPUT_COUNT = 1

TYPE_CHECK_COMMAND = mcalj.TYPE_CHECK_COMMAND
FOCUSED_TEST_COMMAND = (
    "poetry",
    "run",
    "pytest",
    "-q",
    "tests/test_prepare_commit_artifacts.py",
    TEST_PATH,
)
FOCUSED_TEST_COUNT = 48
POETRY_CHECK_COMMAND = mcalj.POETRY_CHECK_COMMAND
PUBLICATION_GUARD_COMMAND = mcalj.PUBLICATION_GUARD_COMMAND
DIFF_CHECK_COMMAND = mcalj.DIFF_CHECK_COMMAND
UNPUBLISHED_AUTHORIZATIONS = {
    **mcalj.UNPUBLISHED_AUTHORIZATIONS,
    "r8_staging_authorized": False,
}
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


class FinalCalibrationR8ManifestReproducibilityPatchError(
    mcalj.FinalCalibrationPlattParameterDialectPatchError
):
    """Raised when the E0-MCALK adoption authority is not exact."""


FinalCalibrationError = mcalj.FinalCalibrationError
P = ParamSpec("P")
R = TypeVar("R")


def _error(message: str) -> FinalCalibrationR8ManifestReproducibilityPatchError:
    return FinalCalibrationR8ManifestReproducibilityPatchError(message)


def _translate_predecessor_error(message: str) -> str:
    for prefix in (
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
        except FinalCalibrationR8ManifestReproducibilityPatchError:
            raise
        except mcalj.FinalCalibrationError as exc:
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


def _validate_r8_bundle(*, repo_root: Path) -> dict[str, Any]:
    """Validate the immutable R8 bytes with the sealed MCALJ parsers."""

    records: list[dict[str, Any]] = []
    for expected in R8_OUTPUT_CONTRACT:
        path = Path(cast(str, expected["path"]))
        payload, metadata = mcal._read_regular_bytes_and_metadata(
            path, repo_root=repo_root, expected_mode=0o644, require_nlink_one=True
        )
        observed = {
            "path": path.as_posix(),
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
        }
        if observed != expected or not stat.S_ISREG(metadata.st_mode):
            raise _error(f"E0-MCALK immutable R8 output drifted: {path.as_posix()}")
        records.append(observed)
    calibration_count = mcalj._require_exact_output_group(
        mcal.CALIBRATION_OUTPUT_PATHS,
        manifest_path=CALIBRATION_MANIFEST_PATH,
        repo_root=repo_root,
        context="calibration",
    )
    e7_count = mcalj._require_exact_output_group(
        mcal.E7_OUTPUT_PATHS,
        manifest_path=E7_MANIFEST_PATH,
        repo_root=repo_root,
        context="E7",
    )
    namespace = mcalj._validate_effective_namespace(repo_root=repo_root)
    if (
        calibration_count != 6
        or e7_count != 2
        or namespace
        != {
            "calibration_output_present_count": 6,
            "e7_output_present_count": 2,
            "r_output_present_count": 8,
            "r_lifecycle_state": "both_bundles_completed_unpublished",
        }
    ):
        raise _error("E0-MCALK immutable R8 lifecycle drifted")
    calibration_manifest = mcal._load_json_object(
        CALIBRATION_MANIFEST_PATH, repo_root=repo_root
    )
    e7_manifest = mcal._load_json_object(E7_MANIFEST_PATH, repo_root=repo_root)
    if (
        set(calibration_manifest)
        != {
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
        or calibration_manifest.get("status") != "completed_unpublished"
        or "script" in calibration_manifest
        or set(e7_manifest)
        != {
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
        or e7_manifest.get("status") != "terminal"
        or "script" in e7_manifest
        or calibration_manifest.get("authority_sha256")
        != e7_manifest.get("authority_sha256")
    ):
        raise _error("E0-MCALK sealed R8 manifest dialect drifted")
    producer_records: list[dict[str, Any]] = []
    for expected in PRODUCER_PROVENANCE_CONTRACT:
        path = Path(cast(str, expected["path"]))
        mode, oid = mcal._git_mode_oid(repo_root, H_MCALJ_COMMIT, path)
        git_payload = mcal._git_blob_bytes(repo_root, H_MCALJ_COMMIT, path)
        physical = mcal._read_regular_bytes(path, repo_root=repo_root)
        observed = {
            "role": expected["role"],
            "path": path.as_posix(),
            "commit": H_MCALJ_COMMIT,
            "git_mode": mode,
            "git_oid": oid,
            "bytes": len(git_payload),
            "sha256": _sha256_bytes(git_payload),
        }
        if observed != expected or physical != git_payload:
            raise _error(f"E0-MCALK R8 producer provenance drifted: {path}")
        producer_records.append(observed)
    return {
        "gate": PATCH_GATE,
        "status": "immutable_r8_validated",
        "r8_output_count": 8,
        "calibration_output_count": 6,
        "e7_output_count": 2,
        "r_lifecycle_state": "both_bundles_completed_unpublished",
        "authority_sha256": calibration_manifest["authority_sha256"],
        "r8_outputs": records,
        "r8_outputs_sha256": mcal._digest_records(records),
        "producer_provenance": producer_records,
        "producer_provenance_sha256": mcal._digest_records(producer_records),
        "manifest_reproducibility_contract": _deep_copy(
            MANIFEST_REPRODUCIBILITY_CONTRACT
        ),
    }


def _require_exact_r8_staged_scope(*, repo_root: Path) -> None:
    try:
        staged = cast(
            str,
            mcal._git(
                repo_root, "diff", "--cached", "--name-status", "--no-renames"
            ),
        )
        observed: dict[str, str] = {}
        for line in staged.splitlines():
            fields = line.split("\t")
            if len(fields) != 2 or fields[0] != "A" or fields[1] in observed:
                raise _error("E0-MCALK staged R8 scope dialect drifted")
            observed[fields[1]] = fields[0]
        if observed != R8_STAGED_SCOPE:
            raise _error("E0-MCALK staged R8 scope is not exact8A")
        if cast(str, mcal._git(repo_root, "diff", "--name-status")).strip():
            raise _error("E0-MCALK staged R8 has an unstaged tracked delta")
        if mcal._workspace_status_records(repo_root) != [
            ("A ", path) for path in sorted(R8_STAGED_SCOPE)
        ]:
            raise _error("E0-MCALK staged R8 workspace scope drifted")
    except (ValueError, TypeError) as exc:
        raise _error("E0-MCALK staged R8 scope dialect drifted") from exc


@_error_boundary
def validate_final_calibration_r8_manifest_reproducibility_adoption(
    *, repo_root: Path | None = None, require_staged: bool = True
) -> dict[str, Any]:
    """Validate immutable R8 and, optionally, its exact staged publication map."""

    if type(require_staged) is not bool:
        raise _error("E0-MCALK staged policy must be an exact boolean")
    root = _root(repo_root)
    authority: dict[str, Any] | None = None
    if require_staged:
        authority = (
            load_effective_final_calibration_r8_manifest_reproducibility_patch_authority(
                verify_remote=False, repo_root=root
            )
        )
    validated = _validate_r8_bundle(repo_root=root)
    if require_staged:
        _require_exact_r8_staged_scope(repo_root=root)
    return {
        **validated,
        "status": "r8_manifest_reproducibility_adoption_validated",
        "expected_non_ok_findings": _deep_copy(GENERIC_MANIFEST_FINDINGS_CONTRACT),
        "staged_scope_verified": require_staged,
        "effective_p_mcalk_verified": authority is not None,
        "scientific_rerun_performed": False,
        "r8_rewrite_performed": False,
    }


def _git_record_at_commit(
    path: str, *, role: str, commit: str, repo_root: Path
) -> dict[str, Any]:
    relative = Path(path)
    mode, oid = mcal._git_mode_oid(repo_root, commit, relative)
    payload = mcal._git_blob_bytes(repo_root, commit, relative)
    if mode not in {"100644", "100755"}:
        raise _error(f"E0-MCALK historical Git mode drifted: {path}")
    return {
        "role": role,
        "path": path,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "git_oid": oid,
        "git_mode": mode,
    }


def _p_mcalj_authority(*, repo_root: Path) -> dict[str, Any]:
    """Reconstruct the exact published H/P-E0-MCALJ authority."""

    if (
        mcal._single_parent(repo_root, H_MCALJ_COMMIT, context="H-E0-MCALJ")
        != H_MCALJ_PARENT
    ):
        raise _error("E0-MCALK historical H-E0-MCALJ parent drifted")
    h_scope = mcal._git_scope(repo_root, H_MCALJ_PARENT, H_MCALJ_COMMIT)
    expected_h_scope = {
        "added": 5,
        "modified": 4,
        "deleted": 0,
        "path_count": 9,
        "paths": list(mcalj.PATCH_PATHS),
    }
    if h_scope != expected_h_scope:
        raise _error("E0-MCALK historical H-E0-MCALJ scope drifted")
    if (
        mcal._single_parent(repo_root, BASE_P_MCALJ_COMMIT, context="P-E0-MCALJ")
        != H_MCALJ_COMMIT
    ):
        raise _error("E0-MCALK historical P-E0-MCALJ parent drifted")
    p_scope = mcal._git_scope(repo_root, H_MCALJ_COMMIT, BASE_P_MCALJ_COMMIT)
    expected_p_scope = {
        "added": 2,
        "modified": 0,
        "deleted": 0,
        "path_count": 2,
        "paths": sorted(P_MCALJ_PATHS),
    }
    if p_scope != expected_p_scope:
        raise _error("E0-MCALK historical P-E0-MCALJ scope drifted")

    components: list[dict[str, Any]] = []
    for path in P_MCALJ_PATHS:
        role = (
            "published_p_mcalj_lock"
            if path == mcalj.DEFAULT_PATCH_LOCK_PATH.as_posix()
            else "published_p_mcalj_lock_manifest"
        )
        record = _git_record_at_commit(
            path, role=role, commit=BASE_P_MCALJ_COMMIT, repo_root=repo_root
        )
        physical = mcal._git_artifact_record(
            Path(path),
            role=role,
            repo_root=repo_root,
            commit=BASE_P_MCALJ_COMMIT,
        )
        if physical != record:
            raise _error(f"E0-MCALK published P-MCALJ component drifted: {path}")
        components.append(record)

    lock_bytes = mcal._git_blob_bytes(
        repo_root, BASE_P_MCALJ_COMMIT, mcalj.DEFAULT_PATCH_LOCK_PATH
    )
    companion_bytes = mcal._git_blob_bytes(
        repo_root, BASE_P_MCALJ_COMMIT, mcalj.DEFAULT_PATCH_LOCK_MANIFEST_PATH
    )
    lock = mcal._parse_json_bytes(lock_bytes, context="published P-E0-MCALJ lock")
    companion = mcal._parse_json_bytes(
        companion_bytes, context="published P-E0-MCALJ companion"
    )
    if (
        not isinstance(lock, Mapping)
        or not isinstance(companion, Mapping)
        or lock_bytes != mcalj._canonical_json_bytes(lock)
        or companion_bytes != mcalj._canonical_json_bytes(companion)
        or lock.get("gate") != mcalj.PATCH_GATE
        or cast(Mapping[str, Any], lock.get("repository", {})).get(
            "h_patch_head"
        )
        != H_MCALJ_COMMIT
    ):
        raise _error("E0-MCALK historical P-E0-MCALJ JSON drifted")
    mcalj._validate_published_lock_payload(lock, repo_root=repo_root)
    lock_record = {
        "role": "final_calibration_platt_parameter_dialect_patch_lock",
        "path": mcalj.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "bytes": len(lock_bytes),
        "sha256": _sha256_bytes(lock_bytes),
    }
    if companion_bytes != mcalj._canonical_json_bytes(
        mcalj._expected_companion(lock, lock_record)
    ):
        raise _error("E0-MCALK historical P-E0-MCALJ companion drifted")
    return {
        "gate": "P-E0-MCALJ",
        "commit": BASE_P_MCALJ_COMMIT,
        "parent_h_mcalj": H_MCALJ_COMMIT,
        "h_mcalj_parent": H_MCALJ_PARENT,
        "h_scope": h_scope,
        "p_scope": p_scope,
        "p_component_count": 2,
        "p_components": components,
        "p_components_sha256": mcal._digest_records(components),
        "lock_payload_sha256": _sha256_bytes(lock_bytes),
        "companion_sha256": _sha256_bytes(companion_bytes),
        "manifest_written_last": companion.get("manifest_written_last") is True,
        "effective_authority_binding_sha256": (
            "8da4f1bc20916c91a083dad2e12bf0976b36390ad6eddf313f03726ed529fc3a"
        ),
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
        raise _error("E0-MCALK remote policy must be an exact boolean")
    head = mcal._git_head(repo_root)
    branch = cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
    if branch != "main":
        raise _error("E0-MCALK requires branch main")
    expected_scope = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(PATCH_PATHS),
    }
    candidate = head == BASE_P_MCALJ_COMMIT
    if candidate:
        if not _candidate_status_is_exact(repo_root):
            raise _error("E0-MCALK candidate workspace is not exact 1M+5A plus R8")
        component_commit: str | None = None
        h_head = BASE_P_MCALJ_COMMIT
        scope = expected_scope
    else:
        if (
            mcal._single_parent(repo_root, head, context="H-E0-MCALK")
            != BASE_P_MCALJ_COMMIT
        ):
            raise _error("E0-MCALK published H parent drifted")
        scope = mcal._git_scope(repo_root, BASE_P_MCALJ_COMMIT, head)
        expected_r = [
            ("??", path)
            for path in sorted(output.as_posix() for output in R_OUTPUT_PATHS)
        ]
        if scope != expected_scope or mcal._workspace_status_records(repo_root) != expected_r:
            raise _error("E0-MCALK published H scope/worktree drifted")
        component_commit = head
        h_head = head
    components = [
        mcal._git_artifact_record(
            Path(path),
            role="final_calibration_r8_manifest_reproducibility_patch_component",
            repo_root=repo_root,
            commit=component_commit,
            expected_mode=PATCH_COMPONENT_GIT_MODES[path],
        )
        for path in PATCH_PATHS
    ]
    tracking = mcal._git_head(repo_root, "origin/main")
    expected_ref = BASE_P_MCALJ_COMMIT if candidate else head
    if tracking != expected_ref:
        raise _error("E0-MCALK H tracking ref drifted")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if remote != expected_ref:
        raise _error("E0-MCALK H remote ref drifted")
    return (
        {
            "base_p_mcalj_commit": BASE_P_MCALJ_COMMIT,
            "h_patch_head": h_head,
            "branch": branch,
            "remote_head": remote,
            "scope": scope,
        },
        {
            "gate": "H-E0-MCALK",
            "component_count": 6,
            "added_count": 5,
            "modified_count": 1,
            "components": components,
            "components_sha256": mcal._digest_records(components),
        },
    )


def _namespace_paths() -> tuple[Path, ...]:
    return (
        DEFAULT_PATCH_LOCK_PATH,
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        mcal._temporary_path(DEFAULT_PATCH_LOCK_PATH),
        mcal._temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        LOCKER_GUARD_PATH,
        mcalj.LOCKER_GUARD_PATH,
        mcal.CALIBRATION_GUARD_PATH,
        mcal.E7_GUARD_PATH,
    )


def _require_prelock_namespace(*, repo_root: Path) -> None:
    missing = [
        path.as_posix()
        for path in (mcalj.DEFAULT_PATCH_LOCK_PATH, mcalj.DEFAULT_PATCH_LOCK_MANIFEST_PATH)
        if not mcal._entry_exists(path, repo_root=repo_root)
    ]
    if missing:
        raise _error(f"E0-MCALK base P-MCALJ authority is absent: {missing}")
    occupied = [
        path.as_posix()
        for path in _namespace_paths()
        if mcal._entry_exists(path, repo_root=repo_root)
    ]
    if occupied:
        raise _error(f"E0-MCALK prelock namespace is occupied: {occupied}")
    if mcal._entry_exists(Path(mcal.mze.OUTCOME_ACCESS_LOG), repo_root=repo_root):
        raise _error("E0-MCALK outcome access log must remain absent")


@_error_boundary
def preflight_final_calibration_r8_manifest_reproducibility_patch_schema(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    validator = getattr(mcal.closure_contract, "_assert_supported_json_schema", None)
    if validator is None:
        raise _error("E0-MCALK closed schema preflight is unavailable")
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
                role="final_calibration_r8_manifest_reproducibility_patch_lock_schema",
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
    schema = preflight_final_calibration_r8_manifest_reproducibility_patch_schema(
        repo_root=repo_root
    )
    predecessor = _p_mcalj_authority(repo_root=repo_root)
    r8 = _validate_r8_bundle(repo_root=repo_root)
    if require_empty_namespace:
        _require_prelock_namespace(repo_root=repo_root)
    historical = {
        **_git_record_at_commit(
            PRECOMMIT_PATH,
            role="superseded_p_mcalj_precommit_component",
            commit=BASE_P_MCALJ_COMMIT,
            repo_root=repo_root,
        ),
        "commit": BASE_P_MCALJ_COMMIT,
    }
    boundary = {
        "development_only": True,
        "holdout_row_count": 0,
        "post_2021_row_count": 0,
        "outcome_path_count": 0,
        "outcome_access_authorized": False,
        "scientific_rerun_authorized": False,
    }
    prelock = {
        "base_p_mcalj_output_present_count": 2,
        "p_output_present_count": 0,
        "r8_output_present_count": 8,
        "temporary_present_count": 0,
        "coordination_present_count": 0,
        "exact_r8_untracked": True,
        "r8_bytes_preserved": True,
        "r8_inodes_preserved_during_lock_required": True,
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
    }
    return {
        "repository": _deep_copy(repository),
        "failed_attempt": _deep_copy(FAILED_ATTEMPT),
        "p_mcalj_authority": predecessor,
        "h_patch": _deep_copy(h_patch),
        "manifest_reproducibility_contract": _deep_copy(
            MANIFEST_REPRODUCIBILITY_CONTRACT
        ),
        "generic_manifest_findings_contract": _deep_copy(
            GENERIC_MANIFEST_FINDINGS_CONTRACT
        ),
        "historical_inputs": [historical],
        "historical_inputs_sha256": mcal._digest_records([historical]),
        "r8_bundle": r8,
        "scientific_boundary": boundary,
        "prelock": prelock,
        "schema_preflight": schema,
    }


@_error_boundary
def collect_final_calibration_r8_manifest_reproducibility_patch_prelock_state(
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
        "r8_files_touched": False,
        "r8_files_staged": False,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
    }


@_error_boundary
def build_final_calibration_r8_manifest_reproducibility_patch_lock_payload(
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
        "p_mcalj_authority",
        "h_patch",
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
        raise _error("E0-MCALK prelock dialect drifted")
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
        raise _error("E0-MCALK generated timestamp is absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _error("E0-MCALK generated timestamp is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _error("E0-MCALK generated timestamp must be timezone-aware")


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
        raise _error("E0-MCALK verification evidence dialect drifted")
    if _canonical_json_bytes(value["schema_preflight"]) != _canonical_json_bytes(
        preflight_final_calibration_r8_manifest_reproducibility_patch_schema(
            repo_root=repo_root
        )
    ):
        raise _error("E0-MCALK schema verification evidence drifted")
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
    expected_count = FOCUSED_TEST_COUNT
    if (
        not isinstance(focused, Mapping)
        or set(focused)
        != base_keys | {"test_count", "skipped_count", "deselected_count"}
        or type(focused.get("test_count")) is not int
        or cast(int, focused.get("test_count")) <= 0
        or (expected_count > 0 and focused.get("test_count") != expected_count)
        or focused.get("skipped_count") != 0
        or focused.get("deselected_count") != 0
    ):
        raise _error("E0-MCALK focused verification evidence drifted")
    mcal._validate_command_evidence(
        {key: focused[key] for key in base_keys},
        expected_command=FOCUSED_TEST_COMMAND,
        context="focused_tests",
    )


@_error_boundary
def validate_final_calibration_r8_manifest_reproducibility_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    verify_remote: bool = False,
) -> dict[str, Any]:
    root = _root(repo_root)
    if not isinstance(payload, Mapping):
        raise _error("E0-MCALK lock payload must be an object")
    schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    try:
        mcal.validate_json_schema(payload, schema)
    except mcal.ClosureContractError as exc:
        raise _error(_translate_predecessor_error(str(exc))) from exc
    _validate_timestamp(payload.get("generated_at_utc"))
    _validate_verification(payload.get("verification"), repo_root=root)
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise _error("E0-MCALK unpublished authorizations drifted")
    state = collect_final_calibration_r8_manifest_reproducibility_patch_prelock_state(
        verify_remote=verify_remote, repo_root=root
    )
    expected = build_final_calibration_r8_manifest_reproducibility_patch_lock_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=cast(str, payload["generated_at_utc"]),
    )
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("E0-MCALK lock semantic reconstruction drifted")
    return dict(payload)


_OwnedOutput = mcalj._OwnedOutput


def _public_artifact_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in ("role", "path", "bytes", "sha256")}


def _expected_companion(
    payload: Mapping[str, Any], lock_record: Mapping[str, Any]
) -> dict[str, Any]:
    predecessor = cast(Mapping[str, Any], payload["p_mcalj_authority"])
    patch = cast(Mapping[str, Any], payload["h_patch"])
    r8 = cast(Mapping[str, Any], payload["r8_bundle"])
    current = cast(Sequence[Mapping[str, Any]], patch["components"])
    prior = cast(Sequence[Mapping[str, Any]], predecessor["p_components"])
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
        raise _error("E0-MCALK companion physical input set drifted")
    historical = [
        dict(record)
        for record in cast(Sequence[Mapping[str, Any]], payload["historical_inputs"])
    ]
    historical.sort(key=lambda record: cast(str, record["path"]))
    if len(historical) != EXPECTED_HISTORICAL_INPUT_COUNT:
        raise _error("E0-MCALK companion historical input set drifted")
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
        raise _error("E0-MCALK publication requires frozen verification evidence")
    _validate_verification(verification, repo_root=repo_root)


def _physical_snapshot(repo_root: Path) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for path_text in (*P_MCALJ_PATHS, *PATCH_PATHS):
        path = Path(path_text)
        payload, metadata = mcal._read_regular_bytes_and_metadata(
            path,
            repo_root=repo_root,
            expected_mode=int(PATCH_COMPONENT_GIT_MODES.get(path_text, "100644")[-3:], 8),
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
        observed_contract = {
            "path": path_text,
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
        }
        if observed_contract != expected:
            raise _error(f"E0-MCALK immutable R8 snapshot drifted: {path_text}")
        records.append(
            {
                "path": path_text,
                "device": int(metadata.st_dev),
                "inode": int(metadata.st_ino),
                "mode": int(metadata.st_mode),
                "nlink": int(metadata.st_nlink),
                "size": observed_contract["bytes"],
                "mtime_ns": int(metadata.st_mtime_ns),
                "ctime_ns": int(metadata.st_ctime_ns),
                "sha256": observed_contract["sha256"],
            }
        )
    records.sort(key=lambda record: cast(str, record["path"]))
    if len(records) != EXPECTED_COMPANION_INPUT_COUNT:
        raise _error("E0-MCALK physical snapshot cardinality drifted")
    return tuple(records)


def _require_physical_snapshot(
    expected: Sequence[Mapping[str, Any]], *, repo_root: Path, context: str
) -> None:
    if _canonical_json_bytes(expected) != _canonical_json_bytes(
        _physical_snapshot(repo_root)
    ):
        raise _error(f"E0-MCALK physical/R8 identity changed {context}")


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
        expected_paths.extend(path.as_posix() for path in (
            DEFAULT_PATCH_LOCK_PATH,
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        ))
    if (
        cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
        != "main"
        or mcal._git_head(repo_root) != expected_head
        or mcal._git_head(repo_root, "origin/main") != expected_head
        or mcal._workspace_status_records(repo_root)
        != [("??", path) for path in sorted(expected_paths)]
    ):
        raise _error(f"E0-MCALK repository changed {context}")
    if verify_remote and mcal._live_remote_main_head(repo_root) != expected_head:
        raise _error(f"E0-MCALK live remote changed {context}")


def _require_publication_boundary(
    *, repo_root: Path, owned_guard: Any | None, outputs_present: bool
) -> None:
    allowed = (
        {DEFAULT_PATCH_LOCK_PATH, DEFAULT_PATCH_LOCK_MANIFEST_PATH}
        if outputs_present
        else set()
    )
    if owned_guard is not None:
        mcalj._require_owned_guard_identity(owned_guard)
        allowed.add(LOCKER_GUARD_PATH)
    occupied = [
        path.as_posix()
        for path in _namespace_paths()
        if path not in allowed and mcal._entry_exists(path, repo_root=repo_root)
    ]
    if occupied:
        raise _error(f"E0-MCALK publication namespace is occupied: {occupied}")


@_error_boundary
def publish_final_calibration_r8_manifest_reproducibility_patch_lock_bundle(
    payload: Mapping[str, Any], *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _root(repo_root)
    try:
        lock_bytes = _canonical_json_bytes(payload)
        frozen = json.loads(lock_bytes)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise _error("E0-MCALK publication payload is not canonical JSON") from exc
    if not isinstance(frozen, dict) or _canonical_json_bytes(frozen) != lock_bytes:
        raise _error("E0-MCALK publication payload must be a canonical object")
    payload = frozen
    repository = payload.get("repository")
    if (
        not isinstance(repository, Mapping)
        or repository.get("h_patch_head") == BASE_P_MCALJ_COMMIT
    ):
        raise _error("E0-MCALK H must be published before P publication")
    _require_publication_verification(payload, repo_root=root)
    validate_final_calibration_r8_manifest_reproducibility_patch_lock_payload(
        payload, repo_root=root, verify_remote=True
    )
    snapshot = _physical_snapshot(root)
    initial_head = mcal._git_head(root)
    if initial_head != repository.get("h_patch_head"):
        raise _error("E0-MCALK H refs drifted before publication")
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
            b"E0-MCALK final calibration R8 manifest lock publication\n",
            repo_root=root,
        )
        _require_physical_snapshot(snapshot, repo_root=root, context="after guard")
        _require_publication_boundary(
            repo_root=root, owned_guard=guard, outputs_present=False
        )
        lock_output = mcalj._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_PATH, lock_bytes, repo_root=root
        )
        published.append(lock_output)
        lock_record = {
            "role": "final_calibration_r8_manifest_reproducibility_patch_lock",
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "bytes": len(lock_bytes),
            "sha256": _sha256_bytes(lock_bytes),
        }
        companion = _expected_companion(payload, lock_record)
        companion_bytes = _canonical_json_bytes(companion)
        companion_output = mcalj._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH, companion_bytes, repo_root=root
        )
        published.append(companion_output)
        publication = ((lock_output, lock_bytes), (companion_output, companion_bytes))
        for output, expected in publication:
            mcalj._validate_owned_output_bytes(
                output, expected, repo_root=root, context="after publication"
            )
        _require_physical_snapshot(
            snapshot, repo_root=root, context="after companion publication"
        )
        _require_publication_boundary(
            repo_root=root, owned_guard=guard, outputs_present=True
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
                mcalj._validate_owned_output_bytes(
                    output,
                    expected,
                    repo_root=root,
                    context=f"ownership transfer pass {pass_index}",
                )
            mcalj.mcali._require_owned_identity_set(
                [output for output, _ in publication],
                context=f"MCALK ownership transfer pass {pass_index}",
            )
        committed = True
        return dict(payload), companion
    except BaseException as exc:
        rollback = mcalj._rollback_outputs_best_effort(published)
        if rollback is not None:
            exc.add_note(str(rollback))
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, FinalCalibrationR8ManifestReproducibilityPatchError):
            raise
        raise _error("E0-MCALK lock bundle publication failed") from exc
    finally:
        if guard is not None:
            try:
                mt._release_publication_guard(guard, tolerate_foreign=True)
            except Exception:
                pass
        if committed:
            for output in reversed(published):
                try:
                    mcalj._close_owned_output(output)
                except Exception:
                    pass


def _parse_canonical_json_with_metadata(
    path: Path, *, repo_root: Path
) -> tuple[dict[str, Any], bytes, os.stat_result]:
    payload, metadata = mcal._read_regular_bytes_and_metadata(
        path, repo_root=repo_root, expected_mode=0o644, require_nlink_one=True
    )
    value = mcal._parse_json_bytes(payload, context=path.as_posix())
    if not isinstance(value, dict) or payload != _canonical_json_bytes(value):
        raise _error(f"E0-MCALK canonical JSON drifted: {path.as_posix()}")
    return value, payload, metadata


def _published_h_state(h_head: str, *, repo_root: Path) -> dict[str, Any]:
    if h_head == BASE_P_MCALJ_COMMIT or re.fullmatch(r"[0-9a-f]{40}", h_head) is None:
        raise _error("E0-MCALK published H commit is absent")
    if (
        mcal._single_parent(repo_root, h_head, context="H-E0-MCALK")
        != BASE_P_MCALJ_COMMIT
    ):
        raise _error("E0-MCALK published H parent drifted")
    scope = mcal._git_scope(repo_root, BASE_P_MCALJ_COMMIT, h_head)
    expected_scope = {
        "added": 5,
        "modified": 1,
        "deleted": 0,
        "path_count": 6,
        "paths": list(PATCH_PATHS),
    }
    if scope != expected_scope:
        raise _error("E0-MCALK published H scope drifted")
    components = [
        mcal._git_artifact_record(
            Path(path),
            role="final_calibration_r8_manifest_reproducibility_patch_component",
            repo_root=repo_root,
            commit=h_head,
            expected_mode=PATCH_COMPONENT_GIT_MODES[path],
        )
        for path in PATCH_PATHS
    ]
    return _state_for_h(
        repository={
            "base_p_mcalj_commit": BASE_P_MCALJ_COMMIT,
            "h_patch_head": h_head,
            "branch": "main",
            "remote_head": h_head,
            "scope": scope,
        },
        h_patch={
            "gate": "H-E0-MCALK",
            "component_count": 6,
            "added_count": 5,
            "modified_count": 1,
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
        raise _error(_translate_predecessor_error(str(exc))) from exc
    _validate_timestamp(payload.get("generated_at_utc"))
    _validate_verification(payload.get("verification"), repo_root=repo_root)
    _require_publication_verification(payload, repo_root=repo_root)
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise _error("E0-MCALK published authorizations drifted")
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("E0-MCALK published H binding is absent")
    state = _published_h_state(cast(str, repository["h_patch_head"]), repo_root=repo_root)
    expected = build_final_calibration_r8_manifest_reproducibility_patch_lock_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=cast(str, payload["generated_at_utc"]),
    )
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("E0-MCALK published lock reconstruction drifted")


def _validate_unpublished_p_repository(
    *,
    h_head: str,
    verify_remote: bool,
    repo_root: Path,
) -> str:
    if type(verify_remote) is not bool:
        raise _error("E0-MCALK unpublished P remote policy must be exact boolean")
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
        or mcal._single_parent(repo_root, h_head, context="H-E0-MCALK")
        != BASE_P_MCALJ_COMMIT
        or mcal._git_scope(repo_root, BASE_P_MCALJ_COMMIT, h_head)
        != expected_h_scope
    ):
        raise _error("E0-MCALK unpublished P requires exact published H topology")
    tracking = mcal._git_head(repo_root, "origin/main")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != h_head or remote != h_head:
        raise _error("E0-MCALK unpublished P H refs drifted")
    r_status = [("??", path.as_posix()) for path in R_OUTPUT_PATHS]
    p_untracked = [
        ("??", path.as_posix())
        for path in (DEFAULT_PATCH_LOCK_PATH, DEFAULT_PATCH_LOCK_MANIFEST_PATH)
    ]
    p_staged = [
        ("A ", path.as_posix())
        for path in (DEFAULT_PATCH_LOCK_PATH, DEFAULT_PATCH_LOCK_MANIFEST_PATH)
    ]
    observed = sorted(mcal._workspace_status_records(repo_root))
    if observed == sorted((*p_untracked, *r_status)):
        return "untracked"
    if observed == sorted((*p_staged, *r_status)):
        return "staged"
    raise _error("E0-MCALK unpublished P workspace is not exact P2 plus R8")


@_error_boundary
def validate_final_calibration_r8_manifest_reproducibility_unpublished_lock_bundle(
    *, repo_root: Path | None = None, verify_remote: bool = True
) -> dict[str, Any]:
    """Validate exact unpublished P2 without treating it as effective authority."""

    root = _root(repo_root)
    lock, lock_bytes, lock_metadata = _parse_canonical_json_with_metadata(
        DEFAULT_PATCH_LOCK_PATH, repo_root=root
    )
    repository = lock.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("E0-MCALK unpublished P H binding is absent")
    h_head = cast(str, repository["h_patch_head"])
    stage_state = _validate_unpublished_p_repository(
        h_head=h_head, verify_remote=verify_remote, repo_root=root
    )
    _validate_published_lock_payload(lock, repo_root=root)
    lock_record = mcal._file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="final_calibration_r8_manifest_reproducibility_patch_lock",
        repo_root=root,
    )
    companion, companion_bytes, companion_metadata = (
        _parse_canonical_json_with_metadata(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
        )
    )
    expected_companion = _expected_companion(lock, lock_record)
    if _canonical_json_bytes(companion) != _canonical_json_bytes(
        expected_companion
    ):
        raise _error("E0-MCALK unpublished P companion drifted")
    snapshot = _physical_snapshot(root)
    r8 = _validate_r8_bundle(repo_root=root)
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
        or mcalj._metadata_identity(recaptured_lock_metadata)
        != mcalj._metadata_identity(lock_metadata)
        or mcalj._metadata_identity(recaptured_companion_metadata)
        != mcalj._metadata_identity(companion_metadata)
    ):
        raise _error("E0-MCALK unpublished P changed during semantic validation")
    _require_physical_snapshot(
        snapshot, repo_root=root, context="during unpublished P validation"
    )
    if (
        _validate_unpublished_p_repository(
            h_head=h_head, verify_remote=verify_remote, repo_root=root
        )
        != stage_state
    ):
        raise _error("E0-MCALK unpublished P stage state changed during validation")
    return {
        "gate": PATCH_GATE,
        "status": "unpublished_p_mcalk_lock_bundle_validated",
        "h_patch_head": h_head,
        "p_stage_state": stage_state,
        "p_output_count": 2,
        "physical_input_count": EXPECTED_COMPANION_INPUT_COUNT,
        "historical_input_count": EXPECTED_HISTORICAL_INPUT_COUNT,
        "companion_output_count": EXPECTED_COMPANION_OUTPUT_COUNT,
        "lock": lock_record,
        "companion": mcal._file_record(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            role="final_calibration_r8_manifest_reproducibility_patch_lock_manifest",
            repo_root=root,
        ),
        "r8_output_count": r8["r8_output_count"],
        "r8_outputs_sha256": r8["r8_outputs_sha256"],
        "r8_staging_authorized": False,
        "effective_authority": False,
        "scientific_rerun_authorized": False,
        "writes_performed": False,
    }


def _validate_p_publication(
    payload: Mapping[str, Any], *, verify_remote: bool, repo_root: Path
) -> dict[str, str]:
    if type(verify_remote) is not bool:
        raise _error("E0-MCALK remote policy must be an exact boolean")
    repository = cast(Mapping[str, Any], payload["repository"])
    h_head = cast(str, repository["h_patch_head"])
    head = mcal._git_head(repo_root)
    workspace = mcal._workspace_status_records(repo_root)
    r_paths = {path.as_posix() for path in R_OUTPUT_PATHS}
    if (
        {path for _, path in workspace} != r_paths
        or {code for code, _ in workspace} not in ({"??"}, {"A "})
    ):
        raise _error("E0-MCALK published P worktree is not exact R8")
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
        or mcal._single_parent(repo_root, head, context="P-E0-MCALK") != h_head
        or mcal._git_scope(repo_root, h_head, head) != expected_scope
    ):
        raise _error("E0-MCALK published P topology drifted")
    tracking = mcal._git_head(repo_root, "origin/main")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != head or remote != head:
        raise _error("E0-MCALK published P refs drifted")
    for path in (DEFAULT_PATCH_LOCK_PATH, DEFAULT_PATCH_LOCK_MANIFEST_PATH):
        physical = mcal._read_regular_bytes(path, repo_root=repo_root)
        mode, _ = mcal._git_mode_oid(repo_root, head, path)
        if mode != "100644" or physical != mcal._git_blob_bytes(repo_root, head, path):
            raise _error(f"E0-MCALK published P physical/Git binding drifted: {path}")
    return {"h_patch_head": h_head, "p_patch_head": head, "remote_head": remote}


@_error_boundary
def load_effective_final_calibration_r8_manifest_reproducibility_patch_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    lock, lock_bytes, lock_metadata = _parse_canonical_json_with_metadata(
        DEFAULT_PATCH_LOCK_PATH, repo_root=root
    )
    _validate_published_lock_payload(lock, repo_root=root)
    lock_record = mcal._file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="final_calibration_r8_manifest_reproducibility_patch_lock",
        repo_root=root,
    )
    companion, companion_bytes, companion_metadata = _parse_canonical_json_with_metadata(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
    )
    if _canonical_json_bytes(companion) != _canonical_json_bytes(
        _expected_companion(lock, lock_record)
    ):
        raise _error("E0-MCALK published companion drifted")
    publication = _validate_p_publication(
        lock, verify_remote=verify_remote, repo_root=root
    )
    if any(
        mcal._entry_exists(path, repo_root=root)
        for path in (
            LOCKER_GUARD_PATH,
            mcal._temporary_path(DEFAULT_PATCH_LOCK_PATH),
            mcal._temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
            mcal.CALIBRATION_GUARD_PATH,
            mcal.E7_GUARD_PATH,
        )
    ):
        raise _error("E0-MCALK effective namespace contains a guard or temporary")
    r8 = _validate_r8_bundle(repo_root=root)
    snapshot = _physical_snapshot(root)
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
        or mcalj._metadata_identity(recaptured_metadata)
        != mcalj._metadata_identity(lock_metadata)
        or mcalj._metadata_identity(recaptured_companion_metadata)
        != mcalj._metadata_identity(companion_metadata)
    ):
        raise _error("E0-MCALK P authority changed during effective loading")
    _require_physical_snapshot(snapshot, repo_root=root, context="during effective loading")
    if _validate_p_publication(lock, verify_remote=verify_remote, repo_root=root) != publication:
        raise _error("E0-MCALK publication changed during effective loading")
    return {
        "gate": PATCH_GATE,
        "status": "effective",
        **publication,
        "lock": lock_record,
        "companion": mcal._file_record(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            role="final_calibration_r8_manifest_reproducibility_patch_lock_manifest",
            repo_root=root,
        ),
        "authority_binding_sha256": _sha256_bytes(
            _canonical_json_bytes(
                {
                    "p_patch_head": publication["p_patch_head"],
                    "lock": lock_record,
                    "companion_sha256": _sha256_bytes(companion_bytes),
                    "r8_outputs_sha256": r8["r8_outputs_sha256"],
                }
            )
        ),
        "manifest_reproducibility_adoption": _deep_copy(
            MANIFEST_REPRODUCIBILITY_CONTRACT
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
def require_final_calibration_r8_manifest_reproducibility_patch_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    return load_effective_final_calibration_r8_manifest_reproducibility_patch_authority(
        verify_remote=verify_remote, repo_root=repo_root
    )


@_error_boundary
def require_final_calibration_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    return require_final_calibration_r8_manifest_reproducibility_patch_authority(
        verify_remote=verify_remote, repo_root=repo_root
    )


@_error_boundary
def require_final_calibration_run_namespace(
    *, runner: str, repo_root: Path | None = None
) -> dict[str, Any]:
    del repo_root
    if type(runner) is not str or runner not in {"calibration", "e7"}:
        raise _error("E0-MCALK run namespace requires calibration or e7")
    raise _error("E0-MCALK R8 is terminal; scientific rerun is not authorized")


def __getattr__(name: str) -> Any:
    return getattr(mcalj, name)
