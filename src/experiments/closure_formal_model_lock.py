"""Build and validate the outcome-free Closure V1 formal model lock.

The published H-E0-M prerequisite remains immutable history.  This superseding
H-E0-MBATCH slice adds the eleven sealed-batch scientific components while
keeping every outcome path closed.  Only after this exact implementation is
published may P-E0-M authorize one no-outcome materialization of the five
formal lock files; E0-U and evaluation remain separate later gates.
"""

from __future__ import annotations

import hashlib
import csv
import io
import json
import os
import stat
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from src.experiments import (
    closure_locked_evaluation_input_manifest_dialect_patch as mid,
)
from src.experiments import run_closure_benchmark as runner


mcal = mid.mcal

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_R_MID_COMMIT = "53947df3b826ee10be8cf3b137bae913bc73d2bb"
BASE_P_MCALM_COMMIT = "81c1fc485902d484264fccc53cf88888c359930d"
BASE_H_E0_M_PREREQUISITE_COMMIT = "4bf1953660462b63115a47f97b1041e44d33d873"
PATCH_GATE = "E0-M"
H_GATE = "H-E0-MBATCH"
P_GATE = "P-E0-M"
R_GATE = "R-E0-M"
EXPERIMENT_ID = "closure_v1"
LOCK_SCHEMA_VERSION = "closure_formal_model_lock_authority_v1"
COMPANION_SCHEMA_VERSION = "closure_formal_model_lock_authority_manifest_v1"

DEFAULT_SCHEMA_PATH = Path("configs/closure_v1/formal_model_lock.schema.json")
DEFAULT_AUTHORITY_PATH = Path(
    "configs/closure_v1/formal_model_lock_authority.json"
)
DEFAULT_AUTHORITY_MANIFEST_PATH = Path(
    "configs/closure_v1/formal_model_lock_authority_manifest.json"
)
PRECOMMIT_PATH = "src/data/prepare_commit_artifacts.py"
CORE_PATH = "src/experiments/closure_formal_model_lock.py"
LOCKER_PATH = Path("src/experiments/lock_closure_formal_model_lock.py")
RUNNER_PATH = runner.SCRIPT_PATH
TEST_PATH = "tests/test_closure_formal_model_lock.py"
DOCUMENTATION_PATH = "docs/closure_v1/E0_M_FORMAL_MODEL_LOCK.md"

MODEL_LOCK_PATH = Path("reports/closure_v1/00_protocol/model_lock.yaml")
CALIBRATION_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/calibration_lock.yaml"
)
HYPOTHESIS_REGISTRY_PATH = Path(
    "reports/closure_v1/00_protocol/hypothesis_registry.csv"
)
LOCKED_BATCH_COMMAND_PATH = Path(
    "reports/closure_v1/00_protocol/locked_batch_command.txt"
)
OUTCOME_ACCESS_LOG_PATH = Path(
    "reports/closure_v1/00_protocol/outcome_access_log.jsonl"
)
FORMAL_OUTPUT_PATHS = (
    CALIBRATION_LOCK_PATH,
    HYPOTHESIS_REGISTRY_PATH,
    LOCKED_BATCH_COMMAND_PATH,
    OUTCOME_ACCESS_LOG_PATH,
    MODEL_LOCK_PATH,
)

SUPPORT_PATHS = (
    DEFAULT_SCHEMA_PATH.as_posix(),
    DOCUMENTATION_PATH,
    PRECOMMIT_PATH,
    CORE_PATH,
    LOCKER_PATH.as_posix(),
    RUNNER_PATH.as_posix(),
    TEST_PATH,
)
BATCH_COMPONENT_PATHS = tuple(
    sorted(component.source_path for component in runner.BATCH_COMPONENTS)
)
PATCH_PATHS = tuple(sorted({*SUPPORT_PATHS, *BATCH_COMPONENT_PATHS}))
PATCH_COMPONENT_GIT_MODES = {
    path: ("100755" if path == PRECOMMIT_PATH else "100644")
    for path in PATCH_PATHS
}
FORMAL_MODEL_LOCK_H_STAGED_SCOPE = {
    path: ("A" if path in BATCH_COMPONENT_PATHS else "M") for path in PATCH_PATHS
}
FORMAL_MODEL_LOCK_P_STAGED_SCOPE = {
    DEFAULT_AUTHORITY_PATH.as_posix(): "A",
    DEFAULT_AUTHORITY_MANIFEST_PATH.as_posix(): "A",
}
FORMAL_MODEL_LOCK_R_STAGED_SCOPE = {
    path.as_posix(): "A" for path in FORMAL_OUTPUT_PATHS
}
FINAL_CALIBRATION_H_STAGED_SCOPE = dict(FORMAL_MODEL_LOCK_H_STAGED_SCOPE)
FINAL_CALIBRATION_P_STAGED_SCOPE = dict(FORMAL_MODEL_LOCK_P_STAGED_SCOPE)
FINAL_CALIBRATION_R_STAGED_SCOPE = dict(FORMAL_MODEL_LOCK_R_STAGED_SCOPE)

CURRENT_LOCK_PATHS = (DEFAULT_AUTHORITY_PATH, DEFAULT_AUTHORITY_MANIFEST_PATH)
LOCK_TEMPORARY_PATHS = tuple(
    Path(f"{path.as_posix()}.tmp") for path in CURRENT_LOCK_PATHS
)
FORMAL_OUTPUT_TEMPORARY_PATHS = tuple(
    Path(f"{path.as_posix()}.tmp") for path in FORMAL_OUTPUT_PATHS
)
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_e0_m/formal_model_lock_authority.guard"
)
FORMAL_RUN_GUARD_PATH = Path(
    "tmp/closure_v1_e0_m/formal_model_lock_materialization.guard"
)
FORBIDDEN_CURRENT_NAMESPACE = (
    *CURRENT_LOCK_PATHS,
    *LOCK_TEMPORARY_PATHS,
    *FORMAL_OUTPUT_PATHS,
    *FORMAL_OUTPUT_TEMPORARY_PATHS,
    LOCKER_GUARD_PATH,
    FORMAL_RUN_GUARD_PATH,
)
PREDECESSOR_COORDINATION_NAMESPACE_PATHS = tuple(
    sorted(
        {
            *mid.mic.mcalm.COORDINATION_NAMESPACE_PATHS,
            *mid.mic.mib.COORDINATION_NAMESPACE_PATHS,
            *mid.mic.LOCK_TEMPORARY_PATHS,
            mid.mic.LOCKER_GUARD_PATH,
            *mid.LOCK_TEMPORARY_PATHS,
            mid.LOCKER_GUARD_PATH,
        },
        key=lambda path: path.as_posix(),
    )
)

MODEL_POLICY_PATHS = (
    Path("configs/closure_v1/analysis_plan.yaml"),
    Path("configs/closure_v1/final_calibration_runtime.yaml"),
    Path("configs/closure_v1/model_benchmark.yaml"),
    Path("configs/closure_v1/model_lock_availability_policy.schema.json"),
    Path("configs/closure_v1/model_lock_availability_policy.yaml"),
)
MODEL_AVAILABILITY_PATH = Path(
    "reports/closure_v1/03_calibration/model_availability.csv"
)
HOLDOUT_LEAKAGE_AUDIT_PATH = Path(
    "reports/closure_v1/00_protocol/holdout_leakage_audit.json"
)
MODEL_MANIFEST_PATHS = (
    Path("reports/closure_v1/01_surface/expert/expert_no_current_state_manifest.json"),
    *(Path(f"reports/closure_v1/01_surface/anfis/seed_{seed}/manifest.json") for seed in runner.REGISTERED_SEEDS),
    Path("reports/closure_v1/02_models/baselines/manifest.json"),
    Path("reports/closure_v1/02_models/M0/manifest.json"),
    *(Path(f"reports/closure_v1/02_models/{model}/seed_{seed}_manifest.json") for model in ("P0", "P1", "A0", "A1") for seed in runner.REGISTERED_SEEDS),
)
MODEL_MANIFEST_COUNT = 28
MODEL_ARTIFACT_RECORD_COUNT = 220
MODEL_DVC_PAYLOAD_PATHS = (
    Path("data/closure_v1/development/expert/expert_no_current_state.parquet"),
    *(
        Path(
            f"data/closure_v1/development/anfis/seed_{seed}/"
            "adaptive_no_current_state.parquet"
        )
        for seed in runner.REGISTERED_SEEDS
    ),
    *(
        Path(f"data/closure_v1/development/baselines/{model}/raw_scores.parquet")
        for model in ("B0", "B1", "B2")
    ),
    Path("data/closure_v1/development/mifal/M0/raw_scores.parquet"),
)
MODEL_DVC_POINTER_PATHS = tuple(
    Path(f"{path.as_posix()}.dvc") for path in MODEL_DVC_PAYLOAD_PATHS
)
MODEL_DVC_POINTER_COUNT = 10
SCIENTIFIC_GIT_INPUT_COUNT = 40
UNAVAILABLE_MODEL_FORBIDDEN_PATHS = tuple(
    path
    for model_id in ("P0", "P1")
    for seed in runner.REGISTERED_SEEDS
    for path in (
        Path(f"models/closure_v1/pipe/{model_id}/seed_{seed}.pt"),
        Path(f"models/closure_v1/pipe/{model_id}/seed_{seed}.checkpoint.pt"),
        Path(f"reports/closure_v1/02_models/{model_id}/seed_{seed}_preprocessor.json"),
        Path(f"reports/closure_v1/02_models/{model_id}/seed_{seed}_metrics.csv"),
        Path(f"reports/closure_v1/02_models/{model_id}/seed_{seed}_training_curve.csv"),
        Path(f"reports/closure_v1/02_models/{model_id}/seed_{seed}_blend_weights.csv"),
        Path(f"reports/closure_v1/02_models/{model_id}/seed_{seed}_blend_search.csv"),
    )
)
A2_FORBIDDEN_PATHS = (
    Path("models/closure_v1/anfis_ablation/A2"),
    Path("reports/closure_v1/02_models/A2"),
)
FAMILY_A_COMPARISONS = (
    ("H2_P1_vs_B1", "P1_vs_B1"),
    ("H2_P1_vs_B2", "P1_vs_B2"),
    ("H1_P1_vs_P0", "P1_vs_P0"),
)
FAMILY_B_COMPARISONS = (
    "M0_vs_P1_control",
    "M0_vs_P1_mcar_10",
    "M0_vs_P1_mcar_25",
    "M0_vs_P1_mcar_50",
    "M0_vs_P1_block_1m_10",
    "M0_vs_P1_block_3m_10",
    "M0_vs_P1_block_6m_25",
    "M0_vs_P1_ablate_nutrients",
    "M0_vs_P1_ablate_physchem",
    "M0_vs_P1_ablate_light",
    "M0_vs_P1_ablate_temperature",
    "M0_vs_P1_combined_moderate",
    "M0_vs_P1_combined_severe",
)
FAMILY_D_COMPARISONS = (
    "tp_reduction_10_vs_no_action",
    "tp_reduction_25_vs_no_action",
    "tn_reduction_10_vs_no_action",
    "tp_tn_reduction_10_vs_no_action",
    "clarity_mild_vs_no_action",
    "clarity_strong_vs_no_action",
    "oxygen_support_05_vs_no_action",
    "nutrient_clarity_mild_vs_no_action",
    "nutrient_clarity_strong_vs_no_action",
)
HYPOTHESIS_REGISTRY_FIELDS = (
    "hypothesis_id",
    "multiplicity_family",
    "comparison_id",
    "endpoints",
    "estimand",
    "alternative",
    "evaluation_cohort",
    "horizons_months",
    "multiplicity_universe_size",
    "correction_method",
    "family_wise_alpha",
    "availability_condition",
    "status",
    "availability_reason",
    "p_value",
    "effect_estimate",
    "confidence_interval",
    "holm_universe_retained",
)
GENERIC_MANIFEST_FINDINGS_CONTRACT = (
    {
        "level": "fail",
        "check": "manifest",
        "path": HYPOTHESIS_REGISTRY_PATH.as_posix(),
        "message": "Staged report artifact is not listed in any experiment manifest output.",
    },
    {
        "level": "fail",
        "check": "manifest",
        "path": LOCKED_BATCH_COMMAND_PATH.as_posix(),
        "message": "Staged report artifact is not listed in any experiment manifest output.",
    },
)
R8_OUTPUT_CONTRACT = tuple(mid.R8_OUTPUT_CONTRACT)
LOCKED_INPUT_OUTPUT_CONTRACT = tuple(mid.R_OUTPUT_CONTRACT)
LOCKED_INPUT_OUTPUTS_SHA256 = mid.R_OUTPUTS_SHA256
EXPECTED_MISSING_COMPONENT_COUNT = 0

TYPE_CHECK_COMMAND = ("poetry", "run", "ty", "check")
FOCUSED_TEST_COMMAND = (
    "poetry",
    "run",
    "pytest",
    "-q",
    "tests/test_prepare_commit_artifacts.py",
    TEST_PATH,
)
FOCUSED_TEST_COUNT = 48
POETRY_CHECK_COMMAND = ("poetry", "check")
PUBLICATION_GUARD_COMMAND = ("scripts/check_repo_publication_ready.sh",)
DIFF_CHECK_COMMAND = ("git", "diff", "--check")

AUTHORITY_REQUIRED_FIELDS = (
    "schema_version",
    "experiment_id",
    "gate",
    "status",
    "generated_at_utc",
    "base_head",
    "repository",
    "h_patch",
    "runner_readiness",
    "calibration_evidence",
    "locked_input_evidence",
    "model_policy_evidence",
    "formal_outputs",
    "verification",
    "authorizations",
)
UNPUBLISHED_AUTHORIZATIONS = {
    "p_authority_generation_authorized": False,
    "formal_lock_execution_authorized": False,
    "e0_m_authorized": False,
    "e0_u_authorized": False,
    "evaluation_authorized": False,
    "outcome_access_authorized": False,
    "target_access_authorized": False,
    "dvc_add_authorized": False,
    "dvc_push_authorized": False,
    "git_commit_authorized": False,
    "git_push_authorized": False,
}


def _default_unrun_verification() -> dict[str, Any]:
    return {
        "status": "not_run_by_payload_builder",
        "commands_run": False,
        "scientific_execution_run": False,
        "formal_outputs_touched": False,
        "formal_outputs_staged": False,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
    }


class ClosureFormalModelLockError(RuntimeError):
    """Raised when formal E0-M evidence or its fail-closed boundary drifts."""


def _error(message: str) -> ClosureFormalModelLockError:
    return ClosureFormalModelLockError(f"E0-M {message}")


def _root(repo_root: Path | None) -> Path:
    return PROJECT_ROOT if repo_root is None else Path(repo_root).resolve()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _deep_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


def _blob_oid(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _read_record(
    path: Path,
    *,
    role: str,
    repo_root: Path,
    expected_mode: int = 0o644,
) -> dict[str, Any]:
    try:
        payload, metadata = mcal._read_regular_bytes_and_metadata(
            path,
            repo_root=repo_root,
            expected_mode=expected_mode,
            require_nlink_one=True,
        )
    except Exception as exc:
        raise _error(f"cannot read one stable regular input: {path.as_posix()}") from exc
    return {
        "role": role,
        "path": path.as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "git_oid": _blob_oid(payload),
        "git_mode": f"100{expected_mode & 0o777:03o}",
        "device": int(metadata.st_dev),
        "inode": int(metadata.st_ino),
        "mode": stat.S_IMODE(metadata.st_mode),
        "nlink": int(metadata.st_nlink),
        "mtime_ns": int(metadata.st_mtime_ns),
        "ctime_ns": int(metadata.st_ctime_ns),
    }


def _require_git_binding(
    record: Mapping[str, Any], *, commit: str, repo_root: Path
) -> None:
    path = Path(cast(str, record["path"]))
    try:
        mode, oid = mcal._git_mode_oid(repo_root, commit, path)
        payload = mcal._git_blob_bytes(repo_root, commit, path)
    except Exception as exc:
        raise _error(f"Git binding is absent: {path.as_posix()}@{commit}") from exc
    if (
        mode != "100644"
        or oid != record["git_oid"]
        or len(payload) != record["bytes"]
        or _sha256_bytes(payload) != record["sha256"]
    ):
        raise _error(f"physical/Git binding drifted: {path.as_posix()}")


def _contract_records(
    contract: Sequence[Mapping[str, Any]],
    *,
    role: str,
    repo_root: Path,
    bind_git: bool,
) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for expected in contract:
        path = Path(cast(str, expected["path"]))
        mode = int(cast(int, expected.get("mode", 0o644)))
        record = _read_record(
            path,
            role=role,
            repo_root=repo_root,
            expected_mode=mode,
        )
        if (
            record["bytes"] != expected["bytes"]
            or record["sha256"] != expected["sha256"]
        ):
            raise _error(f"immutable contract bytes drifted: {path.as_posix()}")
        if bind_git:
            _require_git_binding(record, commit=BASE_R_MID_COMMIT, repo_root=repo_root)
        records.append(record)
    if len(records) != len(contract) or len({r["path"] for r in records}) != len(
        contract
    ):
        raise _error(f"{role} contract path set drifted")
    return tuple(records)


def _component_records(repo_root: Path) -> tuple[dict[str, Any], ...]:
    records = tuple(
        _read_record(
            Path(raw_path),
            role="formal_model_lock_h_component",
            repo_root=repo_root,
            expected_mode=int(PATCH_COMPONENT_GIT_MODES[raw_path][-3:], 8),
        )
        for raw_path in PATCH_PATHS
    )
    if len(records) != len(PATCH_PATHS):
        raise _error("H-E0-MBATCH component count is not exact17")
    return records


def _portable_git_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: record[key]
        for key in ("role", "path", "bytes", "sha256", "git_oid", "git_mode")
    }


def _portable_content_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: record[key]
        for key in ("role", "path", "bytes", "sha256", "mode")
    }


def _scientific_binding_commit(
    repo_root: Path, git_commit: str | None = None
) -> str:
    """Resolve the exact commit that owns the scientific prerequisite blobs."""

    if git_commit is None:
        try:
            head = mcal._git_head(repo_root)
            parent = mcal._single_parent(
                repo_root, head, context="scientific Git authority"
            )
            scope = mcal._git_scope(repo_root, parent, head)
        except Exception as exc:
            raise _error("scientific Git authority commit cannot be resolved") from exc
        exact_r_scope = {
            "added": len(FORMAL_OUTPUT_PATHS),
            "modified": 0,
            "deleted": 0,
            "path_count": len(FORMAL_OUTPUT_PATHS),
            "paths": sorted(path.as_posix() for path in FORMAL_OUTPUT_PATHS),
        }
        # Only the exact R5 publication changes the authority commit from HEAD
        # to its P parent.  H, P, and candidate commits bind to HEAD itself.
        git_commit = parent if scope == exact_r_scope else head
    if (
        not isinstance(git_commit, str)
        or len(git_commit) != 40
        or any(character not in "0123456789abcdef" for character in git_commit)
    ):
        raise _error("scientific Git authority commit drifted")
    return git_commit


def _scientific_git_record(
    path: Path,
    *,
    role: str,
    repo_root: Path,
    git_commit: str,
) -> dict[str, Any]:
    _payload, record = _read_scientific_git_bytes_and_record(
        path,
        role=role,
        repo_root=repo_root,
        git_commit=git_commit,
    )
    return record


def _read_scientific_git_bytes_and_record(
    path: Path,
    *,
    role: str,
    repo_root: Path,
    git_commit: str,
) -> tuple[bytes, dict[str, Any]]:
    try:
        payload, metadata = mcal._read_regular_bytes_and_metadata(
            path,
            repo_root=repo_root,
            expected_mode=0o644,
            require_nlink_one=True,
        )
    except Exception as exc:
        raise _error(
            f"cannot read one stable scientific Git input: {path.as_posix()}"
        ) from exc
    record = {
        "role": role,
        "path": path.as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "git_oid": _blob_oid(payload),
        "git_mode": "100644",
        "device": int(metadata.st_dev),
        "inode": int(metadata.st_ino),
        "mode": stat.S_IMODE(metadata.st_mode),
        "nlink": int(metadata.st_nlink),
        "mtime_ns": int(metadata.st_mtime_ns),
        "ctime_ns": int(metadata.st_ctime_ns),
        "git_commit": git_commit,
    }
    _require_git_binding(record, commit=git_commit, repo_root=repo_root)
    return payload, record


def _portable_scientific_git_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        key: record[key]
        for key in (
            "role",
            "path",
            "bytes",
            "sha256",
            "git_oid",
            "git_mode",
            "git_commit",
        )
    }


def _scientific_input_snapshot(
    repo_root: Path, *, git_commit: str | None = None
) -> tuple[dict[str, Any], ...]:
    commit = _scientific_binding_commit(repo_root, git_commit)
    if (
        len(MODEL_MANIFEST_PATHS) != MODEL_MANIFEST_COUNT
        or len(set(MODEL_MANIFEST_PATHS)) != MODEL_MANIFEST_COUNT
        or len(MODEL_DVC_PAYLOAD_PATHS) != MODEL_DVC_POINTER_COUNT
        or len(set(MODEL_DVC_PAYLOAD_PATHS)) != MODEL_DVC_POINTER_COUNT
        or len(MODEL_DVC_POINTER_PATHS) != MODEL_DVC_POINTER_COUNT
        or len(set(MODEL_DVC_POINTER_PATHS)) != MODEL_DVC_POINTER_COUNT
    ):
        raise _error("scientific Git input path contract drifted")
    records = [
        *(
            _scientific_git_record(
                path,
                role="formal_model_manifest_git_input",
                repo_root=repo_root,
                git_commit=commit,
            )
            for path in MODEL_MANIFEST_PATHS
        ),
        _scientific_git_record(
            MODEL_AVAILABILITY_PATH,
            role="model_availability_git_input",
            repo_root=repo_root,
            git_commit=commit,
        ),
        _scientific_git_record(
            HOLDOUT_LEAKAGE_AUDIT_PATH,
            role="holdout_leakage_git_input",
            repo_root=repo_root,
            git_commit=commit,
        ),
        *(
            _scientific_git_record(
                path,
                role="model_dvc_pointer_git_input",
                repo_root=repo_root,
                git_commit=commit,
            )
            for path in MODEL_DVC_POINTER_PATHS
        ),
    ]
    records.sort(key=lambda record: cast(str, record["path"]))
    if len(records) != SCIENTIFIC_GIT_INPUT_COUNT or len(
        {cast(str, record["path"]) for record in records}
    ) != SCIENTIFIC_GIT_INPUT_COUNT:
        raise _error("scientific Git input snapshot count drifted")
    return tuple(records)


def _require_h_component_git_binding(
    record: Mapping[str, Any], *, h_head: str, repo_root: Path
) -> None:
    path = Path(cast(str, record["path"]))
    try:
        mode, oid = mcal._git_mode_oid(repo_root, h_head, path)
        payload = mcal._git_blob_bytes(repo_root, h_head, path)
    except Exception as exc:
        raise _error(f"H component Git binding is absent: {path.as_posix()}") from exc
    if (
        mode != record["git_mode"]
        or oid != record["git_oid"]
        or len(payload) != record["bytes"]
        or _sha256_bytes(payload) != record["sha256"]
    ):
        raise _error(f"H component Git binding drifted: {path.as_posix()}")


def _expected_h_scope() -> dict[str, Any]:
    return {
        "added": len(BATCH_COMPONENT_PATHS),
        "modified": len(SUPPORT_PATHS),
        "deleted": 0,
        "path_count": len(PATCH_PATHS),
        "paths": list(PATCH_PATHS),
    }


def _status_map(repo_root: Path) -> dict[str, str]:
    try:
        records = mcal._workspace_status_records(repo_root)
    except Exception as exc:
        raise _error("workspace status cannot be collected") from exc
    value = {path: code for code, path in records}
    if len(value) != len(records):
        raise _error("workspace status contains duplicate paths")
    return value


def _repository_state(
    *, repo_root: Path, verify_remote: bool, allow_p_outputs: bool = False
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        head = mcal._git_head(repo_root)
        branch = cast(
            str, mcal._git(repo_root, "symbolic-ref", "--short", "HEAD")
        ).strip()
        main = mcal._git_head(repo_root, "main")
        tracking = mcal._git_head(repo_root, "origin/main")
        tracking_head = mcal._git_head(repo_root, "origin/HEAD")
    except Exception as exc:
        raise _error("repository refs cannot be validated") from exc
    if branch != "main":
        raise _error("formal E0-M requires branch main")
    expected_scope = _expected_h_scope()
    observed = _status_map(repo_root)
    candidate_status = {
        path: ("??" if state == "A" else " M")
        for path, state in FORMAL_MODEL_LOCK_H_STAGED_SCOPE.items()
    }
    staged_candidate_status = {
        path: ("A " if state == "A" else "M ")
        for path, state in FORMAL_MODEL_LOCK_H_STAGED_SCOPE.items()
    }
    p_untracked_status = {
        path.as_posix(): "??" for path in CURRENT_LOCK_PATHS
    }
    p_staged_status = {
        path.as_posix(): "A " for path in CURRENT_LOCK_PATHS
    }
    if (
        head == BASE_H_E0_M_PREREQUISITE_COMMIT
        and main == head
        and tracking == head
        and tracking_head == head
        and observed in (candidate_status, staged_candidate_status)
    ):
        h_state = "candidate"
        h_head: str | None = None
        expected_ref = BASE_H_E0_M_PREREQUISITE_COMMIT
    elif (
        head != BASE_H_E0_M_PREREQUISITE_COMMIT
        and main == head
        and tracking == head
        and tracking_head == head
        and (
            not observed
            or (
                allow_p_outputs
                and observed in (p_untracked_status, p_staged_status)
            )
        )
    ):
        try:
            parent = mcal._single_parent(repo_root, head, context=H_GATE)
            scope = mcal._git_scope(
                repo_root, BASE_H_E0_M_PREREQUISITE_COMMIT, head
            )
        except Exception as exc:
            raise _error("published H-E0-MBATCH topology cannot be read") from exc
        if parent != BASE_H_E0_M_PREREQUISITE_COMMIT or scope != expected_scope:
            raise _error("published H-E0-MBATCH topology drifted")
        h_state = "published"
        h_head = head
        expected_ref = head
    else:
        raise _error("formal E0-M repository is neither exact H candidate nor H publication")
    remote = tracking
    if verify_remote:
        try:
            remote = mcal._live_remote_main_head(repo_root)
        except Exception as exc:
            raise _error("live remote main cannot be validated") from exc
        if remote != expected_ref:
            raise _error("live remote main drifted from the formal H checkpoint")

    physical_components = _component_records(repo_root)
    components = tuple(_portable_git_record(record) for record in physical_components)
    return (
        {
            "base_r_mid_commit": BASE_R_MID_COMMIT,
            "base_h_e0_m_prerequisite_commit": BASE_H_E0_M_PREREQUISITE_COMMIT,
            "h_batch_head": h_head,
            "h_state": h_state,
            "head": head,
            "main": main,
            "origin_main": tracking,
            "origin_head": tracking_head,
            "remote_main": remote,
            "branch": branch,
            "verify_remote": verify_remote,
            "workspace_status": [
                {"path": path, "status": observed[path]}
                for path in sorted(observed)
            ],
        },
        {
            "gate": H_GATE,
            "component_count": len(PATCH_PATHS),
            "added_count": len(BATCH_COMPONENT_PATHS),
            "modified_count": len(SUPPORT_PATHS),
            "components": list(components),
            "components_sha256": _sha256_bytes(
                _canonical_json_bytes(list(components))
            ),
        },
    )


def _runner_readiness(repo_root: Path) -> dict[str, Any]:
    try:
        value = runner.check_only(repo_root=repo_root)
    except runner.ClosureBenchmarkError as exc:
        raise _error("sealed batch runner check-only failed") from exc
    required_true = (
        "formal_model_lock_ready",
        "evaluator_available",
        "sealed_batch_execution_ready",
    )
    required_false = (
        "e0_m_authorized",
        "e0_u_authorized",
        "evaluation_authorized",
        "outcome_access_authorized",
        "target_paths_opened",
        "outcome_paths_opened",
        "future_outcomes_accessed",
        "writes_performed",
    )
    if (
        value.get("gate") != PATCH_GATE
        or value.get("status") != "sealed_batch_runner_ready_for_formal_lock"
        or value.get("missing_component_count")
        != EXPECTED_MISSING_COMPONENT_COUNT
        or any(value.get(key) is not True for key in required_true)
        or any(value.get(key) is not False for key in required_false)
        or value.get("sealed_batch_command") != runner.SEALED_BATCH_COMMAND
    ):
        raise _error("sealed batch runner readiness contract drifted")
    return _deep_copy(value)


def _require_namespace(
    repo_root: Path,
    *,
    p_present: bool = False,
    r_present: bool = False,
    r_present_paths: Sequence[Path] = (),
    allow_locker_guard: bool = False,
    allow_formal_run_guard: bool = False,
) -> dict[str, Any]:
    allowed_r_paths = set(r_present_paths)
    if r_present:
        allowed_r_paths = set(FORMAL_OUTPUT_PATHS)
    try:
        if not allowed_r_paths:
            calibration_namespace = (
                mid.mic.mcalm._require_coordination_namespace(
                    repo_root=repo_root,
                    current_outputs_state="present",
                )
            )
        else:
            historical = (
                mid.mic.mcalm.mcall._historical_published_lock_records(
                    repo_root=repo_root
                )
            )
            historical_p = mid.mic.mcalm._historical_p_mcall_git_authority(
                repo_root=repo_root
            )
            never_present = [
                path
                for path in mid.mic.mcalm.NEVER_PUBLISHED_LOCK_PATHS
                if mcal._entry_exists(path, repo_root=repo_root)
            ]
            if (
                len(historical) != 18
                or len(cast(Sequence[Any], historical_p.get("p_components", ())))
                != 2
                or never_present
            ):
                raise _error("historical calibration namespace drifted")
            calibration_namespace = {
                "historical_published_lock_count": 20,
                "never_published_lock_present_count": 0,
                "current_lock_present_count": 2,
                "coordination_present_count": 0,
                "formal_e0_m_output_present_count": 0,
                "outcome_access_log_absent": True,
            }
        predecessor = (
            mid._namespace_state(
                repo_root=repo_root,
                p_present=True,
                r_present=True,
            )
            if not allowed_r_paths
            else None
        )
        predecessor_p = mid._p_pair_snapshot(repo_root)
        predecessor_r = mid._r_bundle_snapshot(repo_root)
    except Exception as exc:
        raise _error("published MID predecessor namespace drifted") from exc
    if (
        calibration_namespace.get("historical_published_lock_count") != 20
        or calibration_namespace.get("never_published_lock_present_count") != 0
        or calibration_namespace.get("current_lock_present_count") != 2
        or calibration_namespace.get("coordination_present_count") != 0
        or calibration_namespace.get("formal_e0_m_output_present_count") != 0
        or calibration_namespace.get("outcome_access_log_absent") is not True
        or mcal._single_parent(
            repo_root, BASE_P_MCALM_COMMIT, context="P-E0-MCALM"
        )
        != "a7dc955d6c565779a4ddd0df16bb83f1c89f687b"
        or mcal._git_scope(
            repo_root, "a7dc955d6c565779a4ddd0df16bb83f1c89f687b", BASE_P_MCALM_COMMIT
        )
        != {
            "added": 2,
            "modified": 0,
            "deleted": 0,
            "path_count": 2,
            "paths": sorted(
                path.as_posix() for path in mid.mic.mcalm.CURRENT_LOCK_PATHS
            ),
        }
        or any(
            mcal._git_mode_oid(repo_root, BASE_P_MCALM_COMMIT, path)[0]
            != "100644"
            or mcal._read_regular_bytes_and_metadata(
                path,
                repo_root=repo_root,
                expected_mode=0o644,
                require_nlink_one=True,
            )[0]
            != mcal._git_blob_bytes(repo_root, BASE_P_MCALM_COMMIT, path)
            for path in mid.mic.mcalm.CURRENT_LOCK_PATHS
        )
        or (
            predecessor is not None
            and (
                predecessor.get("p_output_present_count") != 2
                or predecessor.get("r_output_present_count") != 10
                or predecessor.get("r_state") != "complete"
                or predecessor.get("temporary_present_count") != 0
                or predecessor.get("coordination_present_count") != 0
                or predecessor.get("predecessor_coordination_present_count") != 0
                or predecessor.get("formal_e0_m_output_present_count") != 0
                or predecessor.get("outcome_access_log_absent") is not True
            )
        )
        or len(predecessor_p) != 2
        or len(predecessor_r) != 10
    ):
        raise _error("published MID predecessor namespace is incomplete")
    for path in mid.CURRENT_LOCK_PATHS:
        try:
            payload, _metadata = mcal._read_regular_bytes_and_metadata(
                path,
                repo_root=repo_root,
                expected_mode=0o644,
                require_nlink_one=True,
            )
            mode, _oid = mcal._git_mode_oid(repo_root, BASE_R_MID_COMMIT, path)
            git_payload = mcal._git_blob_bytes(repo_root, BASE_R_MID_COMMIT, path)
        except Exception as exc:
            raise _error(
                f"published MID predecessor binding cannot be read: {path.as_posix()}"
            ) from exc
        if mode != "100644" or payload != git_payload:
            raise _error(
                f"published MID predecessor binding drifted: {path.as_posix()}"
            )
    predecessor_occupied: list[str] = []
    for path in PREDECESSOR_COORDINATION_NAMESPACE_PATHS:
        try:
            if mcal._entry_exists(path, repo_root=repo_root):
                predecessor_occupied.append(path.as_posix())
        except Exception as exc:
            raise _error(
                f"cannot inspect predecessor coordination path: {path.as_posix()}"
            ) from exc
    if predecessor_occupied:
        raise _error(
            "predecessor coordination namespace is occupied: "
            + ", ".join(predecessor_occupied)
        )
    present: list[str] = []
    for path in FORBIDDEN_CURRENT_NAMESPACE:
        if (
            (p_present and path in CURRENT_LOCK_PATHS)
            or path in allowed_r_paths
            or (allow_locker_guard and path == LOCKER_GUARD_PATH)
            or (allow_formal_run_guard and path == FORMAL_RUN_GUARD_PATH)
        ):
            continue
        try:
            if mcal._entry_exists(path, repo_root=repo_root):
                present.append(path.as_posix())
        except Exception as exc:
            raise _error(f"cannot inspect closed namespace: {path.as_posix()}") from exc
    if present:
        raise _error(f"prelock namespace is not empty: {present}")
    return {
        "expected_absent_count": len(FORBIDDEN_CURRENT_NAMESPACE),
        "present_count": 0,
        "present_paths": [],
        "p_output_present_count": 2 if p_present else 0,
        "formal_output_present_count": len(allowed_r_paths),
        "outcome_access_log_state": (
            "present_empty"
            if OUTCOME_ACCESS_LOG_PATH in allowed_r_paths
            else "absent"
        ),
        "locker_guard_present": False,
        "formal_run_guard_present": False,
    }


def _require_absent_namespace(repo_root: Path) -> dict[str, Any]:
    return _require_namespace(repo_root)


def _require_owned_formal_run_guard(guard: Any) -> None:
    try:
        mid.mic.mcalm.mcall.mcalk.mcalj._require_owned_guard_identity(guard)
    except Exception as exc:
        raise _error("formal run guard identity drifted") from exc


def _evidence_state(
    repo_root: Path,
) -> tuple[
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    r8_records = _contract_records(
        R8_OUTPUT_CONTRACT,
        role="published_final_calibration_r8_output",
        repo_root=repo_root,
        bind_git=True,
    )
    locked_records: list[dict[str, Any]] = []
    for expected in LOCKED_INPUT_OUTPUT_CONTRACT:
        record = _read_record(
            Path(cast(str, expected["path"])),
            role="published_locked_evaluation_input",
            repo_root=repo_root,
            expected_mode=int(cast(int, expected.get("mode", 0o644))),
        )
        if (
            record["bytes"] != expected["bytes"]
            or record["sha256"] != expected["sha256"]
        ):
            raise _error(f"locked input bytes drifted: {record['path']}")
        if expected.get("kind") in {"pointer", "summary", "manifest"}:
            _require_git_binding(
                record, commit=BASE_R_MID_COMMIT, repo_root=repo_root
            )
        locked_records.append(record)
    if len(locked_records) != 10:
        raise _error("locked evaluation input contract is not exact10")
    policy_records = tuple(
        _read_record(
            path,
            role="formal_model_policy_input",
            repo_root=repo_root,
        )
        for path in MODEL_POLICY_PATHS
    )
    for record in policy_records:
        _require_git_binding(record, commit=BASE_R_MID_COMMIT, repo_root=repo_root)
    return r8_records, tuple(locked_records), policy_records


def _physical_snapshot(
    repo_root: Path | None = None,
) -> tuple[dict[str, Any], ...]:
    """Capture H, immutable evidence, and Git-bound scientific prerequisites."""

    root = _root(repo_root)
    components = _component_records(root)
    r8, locked, policy = _evidence_state(root)
    scientific = _scientific_input_snapshot(root)
    scientific_commit = cast(str, scientific[0]["git_commit"])
    model_artifacts = _model_artifact_snapshot(
        root, git_commit=scientific_commit
    )
    availability_binding = next(
        record
        for record in scientific
        if record["path"] == MODEL_AVAILABILITY_PATH.as_posix()
    )
    r8_with_scientific_binding = tuple(
        (
            {
                **record,
                "scientific_git_commit": availability_binding["git_commit"],
                "scientific_git_oid": availability_binding["git_oid"],
                "scientific_git_mode": availability_binding["git_mode"],
            }
            if record["path"] == MODEL_AVAILABILITY_PATH.as_posix()
            else record
        )
        for record in r8
    )
    scientific_without_r8_overlap = tuple(
        record
        for record in scientific
        if record["path"] != MODEL_AVAILABILITY_PATH.as_posix()
    )
    records: list[dict[str, Any]] = [
        *components,
        *r8_with_scientific_binding,
        *locked,
        *policy,
        *scientific_without_r8_overlap,
        *model_artifacts,
    ]
    records.sort(key=lambda record: cast(str, record["path"]))
    expected_count = len(PATCH_PATHS) + len(R8_OUTPUT_CONTRACT) + 10 + len(
        MODEL_POLICY_PATHS
    ) + SCIENTIFIC_GIT_INPUT_COUNT - 1 + len(model_artifacts)
    if len(records) != expected_count or len(
        {record["path"] for record in records}
    ) != expected_count:
        raise _error("physical prerequisite snapshot count drifted")
    return tuple(records)


def preflight_formal_model_lock_schema(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    try:
        schema = mcal._load_json_object(DEFAULT_SCHEMA_PATH, repo_root=root)
        validator = getattr(mcal.closure_contract, "_assert_supported_json_schema")
        validator(schema)
        physical_record = _read_record(
            DEFAULT_SCHEMA_PATH,
            role="formal_model_lock_authority_schema",
            repo_root=root,
        )
    except Exception as exc:
        raise _error("closed authority schema preflight failed") from exc
    return {
        "status": "schema_ready",
        "gate": PATCH_GATE,
        "schema_count": 1,
        "schema_version": LOCK_SCHEMA_VERSION,
        "schemas": [_portable_content_record(physical_record)],
        "supported_subset_verified": True,
        "duplicate_keys_rejected": True,
    }


def collect_formal_model_lock_prelock_state(
    *,
    verify_remote: bool = False,
    repo_root: Path | None = None,
    _p_outputs_present: bool = False,
) -> dict[str, Any]:
    """Collect the honest, outcome-free H prerequisite state."""

    root = _root(repo_root)
    repository, h_patch = _repository_state(
        repo_root=root,
        verify_remote=verify_remote,
        allow_p_outputs=_p_outputs_present,
    )
    if _p_outputs_present:
        repository["workspace_status"] = []
    physical_before = _physical_snapshot(root)
    readiness = _runner_readiness(root)
    if _p_outputs_present:
        _require_namespace(root, p_present=True)
        namespace = {
            "expected_absent_count": len(FORBIDDEN_CURRENT_NAMESPACE),
            "present_count": 0,
            "present_paths": [],
            "p_output_present_count": 0,
            "formal_output_present_count": 0,
            "outcome_access_log_state": "absent",
            "locker_guard_present": False,
            "formal_run_guard_present": False,
        }
    else:
        namespace = _require_absent_namespace(root)
    schema = preflight_formal_model_lock_schema(repo_root=root)
    physical_after = _physical_snapshot(root)
    if physical_before != physical_after:
        raise _error("physical prerequisite changed during prelock collection")
    r8 = [
        _portable_content_record(record)
        for record in physical_before
        if record["path"] in {item["path"] for item in R8_OUTPUT_CONTRACT}
    ]
    locked = [
        _portable_content_record(record)
        for record in physical_before
        if record["path"]
        in {item["path"] for item in LOCKED_INPUT_OUTPUT_CONTRACT}
    ]
    policy = [
        _portable_content_record(record)
        for record in physical_before
        if record["path"] in {path.as_posix() for path in MODEL_POLICY_PATHS}
    ]
    result = {
        "gate": PATCH_GATE,
        "status": "ready_to_lock",
        "base_head": BASE_H_E0_M_PREREQUISITE_COMMIT,
        "repository": repository,
        "h_patch": h_patch,
        "schema_preflight": schema,
        "runner_readiness": readiness,
        "calibration_evidence": {
            "status": "published_immutable_r8_validated",
            "output_count": 8,
            "outputs": r8,
            "outputs_sha256": _sha256_bytes(_canonical_json_bytes(r8)),
            "scientific_rows_decoded": False,
        },
        "locked_input_evidence": {
            "status": "published_input_only_bundle_validated",
            "output_count": 10,
            "outputs": locked,
            "outputs_sha256": LOCKED_INPUT_OUTPUTS_SHA256,
            "scientific_rows_decoded": False,
        },
        "model_policy_evidence": {
            "status": "published_policy_inputs_validated",
            "input_count": len(MODEL_POLICY_PATHS),
            "inputs": policy,
            "inputs_sha256": _sha256_bytes(_canonical_json_bytes(policy)),
        },
        "formal_outputs": {
            "expected_output_count": 5,
            "expected_paths": [path.as_posix() for path in FORMAL_OUTPUT_PATHS],
            **namespace,
        },
        "physical_input_count": len(physical_before),
        "formal_output_count": 0,
        "outcome_access_log_state": "absent",
        "formal_model_lock_ready": True,
        "missing_component_count": EXPECTED_MISSING_COMPONENT_COUNT,
        "p_authority_generation_authorized": repository["h_state"] == "published",
        "formal_lock_execution_authorized": False,
        "r_execution_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "evaluation_authorized": False,
        "outcome_access_authorized": False,
        "target_paths_opened": False,
        "outcome_paths_opened": False,
        "future_outcomes_accessed": False,
        "scientific_execution_run": False,
        "verification_commands_run": False,
        "dvc_commands_run": False,
        "git_commands_mutating_run": False,
        "writes_performed": False,
    }
    return result


def _blocked(operation: str) -> ClosureFormalModelLockError:
    return _error(
        f"{operation} is blocked by the current formal E0-M authority boundary"
    )


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
        preflight_formal_model_lock_schema(repo_root=repo_root)
    ):
        raise _error("schema verification evidence drifted")
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
        except Exception as exc:
            raise _error(f"{key} verification evidence drifted") from exc
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
        raise _error("focused verification count drifted")
    try:
        mcal._validate_command_evidence(
            {key: focused[key] for key in base_keys},
            expected_command=FOCUSED_TEST_COMMAND,
            context="focused_tests",
        )
    except Exception as exc:
        raise _error("focused verification evidence drifted") from exc


def build_formal_model_lock_authority_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any] | None = None,
    *,
    generated_at_utc: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    if (
        not isinstance(prelock, Mapping)
        or prelock.get("status") != "ready_to_lock"
        or prelock.get("missing_component_count") != 0
        or prelock.get("formal_model_lock_ready") is not True
        or prelock.get("p_authority_generation_authorized") is not True
    ):
        raise _error("prelock readiness boundary drifted")
    verification_value = (
        _deep_copy(verification)
        if verification is not None
        else _default_unrun_verification()
    )
    _validate_verification(verification_value, repo_root=root)
    repository = cast(Mapping[str, Any], prelock["repository"])
    if repository.get("h_state") != "published" or not isinstance(
        repository.get("h_batch_head"), str
    ):
        raise _error("P payload requires published H-E0-MBATCH")
    return {
        "schema_version": LOCK_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "status": "locked_unpublished",
        "generated_at_utc": generated_at_utc
        or datetime.now(timezone.utc).isoformat(),
        "base_head": BASE_H_E0_M_PREREQUISITE_COMMIT,
        "repository": _deep_copy(repository),
        "h_patch": _deep_copy(prelock["h_patch"]),
        "runner_readiness": _deep_copy(prelock["runner_readiness"]),
        "calibration_evidence": _deep_copy(prelock["calibration_evidence"]),
        "locked_input_evidence": _deep_copy(prelock["locked_input_evidence"]),
        "model_policy_evidence": _deep_copy(prelock["model_policy_evidence"]),
        "formal_outputs": _deep_copy(prelock["formal_outputs"]),
        "verification": verification_value,
        "authorizations": dict(UNPUBLISHED_AUTHORIZATIONS),
    }


def validate_formal_model_lock_authority_payload(
    payload: Mapping[str, Any],
    *,
    verify_remote: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    try:
        schema = mcal._load_json_object(DEFAULT_SCHEMA_PATH, repo_root=root)
        mcal.validate_json_schema(payload, schema)
    except Exception as exc:
        raise _error("authority schema validation failed") from exc
    generated = payload.get("generated_at_utc")
    if not isinstance(generated, str):
        raise _error("authority generated timestamp is absent")
    try:
        parsed = datetime.fromisoformat(generated.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _error("authority generated timestamp is malformed") from exc
    if parsed.tzinfo is None or payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise _error("authority timestamp or authorizations drifted")
    p_present = all(
        mcal._entry_exists(path, repo_root=root) for path in CURRENT_LOCK_PATHS
    )
    state = collect_formal_model_lock_prelock_state(
        verify_remote=verify_remote,
        repo_root=root,
        _p_outputs_present=p_present,
    )
    expected = build_formal_model_lock_authority_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=generated,
        repo_root=root,
    )
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("authority semantic reconstruction drifted")
    return dict(payload)


def _expected_authority_companion(
    payload: Mapping[str, Any], authority_record: Mapping[str, Any]
) -> dict[str, Any]:
    repository = cast(Mapping[str, Any], payload["repository"])
    component_inputs = [
        {
            "role": record["role"],
            "path": record["path"],
            "bytes": record["bytes"],
            "sha256": record["sha256"],
        }
        for record in cast(
            Sequence[Mapping[str, Any]], payload["h_patch"]["components"]
        )
    ]
    component_inputs.sort(key=lambda record: cast(str, record["path"]))
    return {
        "schema_version": COMPANION_SCHEMA_VERSION,
        "status": "completed",
        "gate": P_GATE,
        "h_batch_head": repository["h_batch_head"],
        "script": next(
            record
            for record in component_inputs
            if record["path"] == LOCKER_PATH.as_posix()
        ),
        "inputs": component_inputs,
        "outputs": [dict(authority_record)],
        "manifest_written_last": True,
        "formal_model_lock_run": False,
        "sealed_batch_run": False,
        "scientific_execution_run": False,
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
        raise _error(f"canonical JSON read failed: {path.as_posix()}") from exc
    if not isinstance(value, dict) or payload != _canonical_json_bytes(value):
        raise _error(f"canonical JSON drifted: {path.as_posix()}")
    return value, payload, metadata


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


def _effective_content_snapshot(
    *,
    repo_root: Path,
    p_head: str,
    r_head: str | None,
    r_present: bool,
    _owned_formal_run_guard: Any | None = None,
) -> dict[str, Any]:
    """Capture every physical, namespace, and Git-blob authority surface."""

    if _owned_formal_run_guard is not None:
        _require_owned_formal_run_guard(_owned_formal_run_guard)
    namespace_before = _require_namespace(
        repo_root,
        p_present=True,
        r_present=r_present,
        allow_formal_run_guard=_owned_formal_run_guard is not None,
    )
    git_bindings: list[tuple[str, str, str, str]] = []
    for commit, paths in (
        (p_head, CURRENT_LOCK_PATHS),
        (r_head, FORMAL_OUTPUT_PATHS if r_head is not None else ()),
    ):
        if commit is None:
            continue
        for path in paths:
            try:
                mode, oid = mcal._git_mode_oid(repo_root, commit, path)
                payload = mcal._git_blob_bytes(repo_root, commit, path)
            except Exception as exc:
                raise _error(
                    f"effective E0-M terminal Git binding failed: {path.as_posix()}"
                ) from exc
            git_bindings.append(
                (path.as_posix(), mode, oid, _sha256_bytes(payload))
            )
    result = {
        "git_bindings": tuple(git_bindings),
        "p_pair": _p_pair_snapshot(repo_root),
        "physical": _physical_snapshot(repo_root),
        "predecessor_p_pair": mid._p_pair_snapshot(repo_root),
        "predecessor_r": mid._r_bundle_snapshot(repo_root),
        "formal_r": _formal_output_snapshot(repo_root) if r_present else (),
    }
    namespace_after = _require_namespace(
        repo_root,
        p_present=True,
        r_present=r_present,
        allow_formal_run_guard=_owned_formal_run_guard is not None,
    )
    if namespace_after != namespace_before:
        raise _error("effective E0-M namespace changed during content capture")
    if _owned_formal_run_guard is not None:
        _require_owned_formal_run_guard(_owned_formal_run_guard)
    return {"namespace": namespace_after, **result}


def _effective_repository_snapshot(
    *,
    repo_root: Path,
    verify_remote: bool,
    h_head: str,
    p_head: str,
    r_head: str | None,
) -> dict[str, Any]:
    """Capture and validate refs, topology, remote, and workspace only."""

    try:
        head = mcal._git_head(repo_root)
        branch = cast(
            str, mcal._git(repo_root, "symbolic-ref", "--short", "HEAD")
        ).strip()
        main = mcal._git_head(repo_root, "main")
        tracking = mcal._git_head(repo_root, "origin/main")
        tracking_head = mcal._git_head(repo_root, "origin/HEAD")
        remote = (
            mcal._live_remote_main_head(repo_root) if verify_remote else tracking
        )
        workspace = tuple(sorted(_status_map(repo_root).items()))
        p_parent = mcal._single_parent(repo_root, p_head, context=P_GATE)
        p_scope = mcal._git_scope(repo_root, h_head, p_head)
        r_parent = (
            mcal._single_parent(repo_root, r_head, context=R_GATE)
            if r_head is not None
            else None
        )
        r_scope = (
            mcal._git_scope(repo_root, p_head, r_head)
            if r_head is not None
            else None
        )
    except Exception as exc:
        raise _error("effective E0-M terminal repository checkpoint failed") from exc
    expected_head = r_head if r_head is not None else p_head
    if (
        head != expected_head
        or branch != "main"
        or main != expected_head
        or tracking != expected_head
        or tracking_head != expected_head
        or remote != expected_head
        or p_parent != h_head
        or p_scope
        != {
            "added": 2,
            "modified": 0,
            "deleted": 0,
            "path_count": 2,
            "paths": sorted(path.as_posix() for path in CURRENT_LOCK_PATHS),
        }
        or (
            r_head is not None
            and (
                r_parent != p_head
                or r_scope
                != {
                    "added": 5,
                    "modified": 0,
                    "deleted": 0,
                    "path_count": 5,
                    "paths": sorted(path.as_posix() for path in FORMAL_OUTPUT_PATHS),
                }
            )
        )
    ):
        raise _error("effective E0-M terminal topology drifted")
    return {
        "refs": (head, branch, main, tracking, tracking_head, remote),
        "topology": (p_parent, p_scope, r_parent, r_scope),
        "workspace": workspace,
    }


def _effective_boundary_snapshot(
    *,
    repo_root: Path,
    verify_remote: bool,
    h_head: str,
    p_head: str,
    r_head: str | None,
    r_present: bool,
    _owned_formal_run_guard: Any | None = None,
) -> dict[str, Any]:
    """Double-bracket content/namespace with terminal repository captures."""

    content_before = _effective_content_snapshot(
        repo_root=repo_root,
        p_head=p_head,
        r_head=r_head,
        r_present=r_present,
        _owned_formal_run_guard=_owned_formal_run_guard,
    )
    repository_before = _effective_repository_snapshot(
        repo_root=repo_root,
        verify_remote=verify_remote,
        h_head=h_head,
        p_head=p_head,
        r_head=r_head,
    )
    content_after = _effective_content_snapshot(
        repo_root=repo_root,
        p_head=p_head,
        r_head=r_head,
        r_present=r_present,
        _owned_formal_run_guard=_owned_formal_run_guard,
    )
    if content_after != content_before:
        raise _error("effective E0-M content changed within a boundary capture")
    repository_after = _effective_repository_snapshot(
        repo_root=repo_root,
        verify_remote=verify_remote,
        h_head=h_head,
        p_head=p_head,
        r_head=r_head,
    )
    if repository_after != repository_before:
        raise _error("effective E0-M repository changed within a boundary capture")
    if _owned_formal_run_guard is not None:
        _require_owned_formal_run_guard(_owned_formal_run_guard)
    return {**repository_after, **content_after}


def _validate_published_authority_payload(
    payload: Mapping[str, Any], *, h_head: str, repo_root: Path
) -> dict[str, Any]:
    try:
        schema = mcal._load_json_object(DEFAULT_SCHEMA_PATH, repo_root=repo_root)
        mcal.validate_json_schema(payload, schema)
    except Exception as exc:
        raise _error("published authority schema validation failed") from exc
    if (
        mcal._single_parent(repo_root, h_head, context=H_GATE)
        != BASE_H_E0_M_PREREQUISITE_COMMIT
        or mcal._git_scope(
            repo_root, BASE_H_E0_M_PREREQUISITE_COMMIT, h_head
        )
        != _expected_h_scope()
    ):
        raise _error("published H-E0-MBATCH topology drifted")
    physical_components = _component_records(repo_root)
    for record in physical_components:
        _require_h_component_git_binding(record, h_head=h_head, repo_root=repo_root)
    components = [_portable_git_record(record) for record in physical_components]
    expected_repository = {
        "base_r_mid_commit": BASE_R_MID_COMMIT,
        "base_h_e0_m_prerequisite_commit": BASE_H_E0_M_PREREQUISITE_COMMIT,
        "h_batch_head": h_head,
        "h_state": "published",
        "head": h_head,
        "main": h_head,
        "origin_main": h_head,
        "origin_head": h_head,
        "remote_main": h_head,
        "branch": "main",
        "verify_remote": True,
        "workspace_status": [],
    }
    expected_h_patch = {
        "gate": H_GATE,
        "component_count": len(PATCH_PATHS),
        "added_count": len(BATCH_COMPONENT_PATHS),
        "modified_count": len(SUPPORT_PATHS),
        "components": components,
        "components_sha256": _sha256_bytes(_canonical_json_bytes(components)),
    }
    r8_physical, locked_physical, policy_physical = _evidence_state(repo_root)
    r8 = [_portable_content_record(record) for record in r8_physical]
    locked = [_portable_content_record(record) for record in locked_physical]
    policy = [_portable_content_record(record) for record in policy_physical]
    expected_calibration = {
        "status": "published_immutable_r8_validated",
        "output_count": 8,
        "outputs": r8,
        "outputs_sha256": _sha256_bytes(_canonical_json_bytes(r8)),
        "scientific_rows_decoded": False,
    }
    expected_locked = {
        "status": "published_input_only_bundle_validated",
        "output_count": 10,
        "outputs": locked,
        "outputs_sha256": LOCKED_INPUT_OUTPUTS_SHA256,
        "scientific_rows_decoded": False,
    }
    expected_policy = {
        "status": "published_policy_inputs_validated",
        "input_count": len(MODEL_POLICY_PATHS),
        "inputs": policy,
        "inputs_sha256": _sha256_bytes(_canonical_json_bytes(policy)),
    }
    expected_formal_outputs = {
        "expected_output_count": 5,
        "expected_paths": [path.as_posix() for path in FORMAL_OUTPUT_PATHS],
        "expected_absent_count": len(FORBIDDEN_CURRENT_NAMESPACE),
        "present_count": 0,
        "present_paths": [],
        "p_output_present_count": 0,
        "formal_output_present_count": 0,
        "outcome_access_log_state": "absent",
        "locker_guard_present": False,
        "formal_run_guard_present": False,
    }
    generated = payload.get("generated_at_utc")
    if not isinstance(generated, str):
        raise _error("published authority timestamp is absent")
    try:
        parsed = datetime.fromisoformat(generated.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _error("published authority timestamp is malformed") from exc
    if parsed.tzinfo is None:
        raise _error("published authority timestamp lacks timezone")
    if (
        payload.get("schema_version") != LOCK_SCHEMA_VERSION
        or payload.get("experiment_id") != EXPERIMENT_ID
        or payload.get("gate") != PATCH_GATE
        or payload.get("status") != "locked_unpublished"
        or payload.get("base_head") != BASE_H_E0_M_PREREQUISITE_COMMIT
        or payload.get("repository") != expected_repository
        or payload.get("h_patch") != expected_h_patch
        or payload.get("runner_readiness") != _runner_readiness(repo_root)
        or payload.get("calibration_evidence") != expected_calibration
        or payload.get("locked_input_evidence") != expected_locked
        or payload.get("model_policy_evidence") != expected_policy
        or payload.get("formal_outputs") != expected_formal_outputs
        or payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS
    ):
        raise _error("published authority semantic binding drifted")
    _validate_verification(payload.get("verification"), repo_root=repo_root)
    return dict(payload)


def _require_p_repository_boundary(
    *,
    h_head: str,
    expected_present: Sequence[Path],
    expected_physical_snapshot: tuple[dict[str, Any], ...],
    repo_root: Path,
    owned_guard: Any | None,
) -> None:
    try:
        head = mcal._git_head(repo_root)
        branch = cast(
            str, mcal._git(repo_root, "symbolic-ref", "--short", "HEAD")
        ).strip()
        refs = (
            mcal._git_head(repo_root, "main"),
            mcal._git_head(repo_root, "origin/main"),
            mcal._git_head(repo_root, "origin/HEAD"),
            mcal._live_remote_main_head(repo_root),
        )
    except Exception as exc:
        raise _error("P-E0-M repository checkpoint failed") from exc
    if head != h_head or branch != "main" or any(value != h_head for value in refs):
        raise _error("P-E0-M refs changed during publication")
    if _status_map(repo_root) != {
        path.as_posix(): "??" for path in expected_present
    }:
        raise _error("P-E0-M workspace changed during publication")
    if owned_guard is not None:
        try:
            mid.mic.mcalm.mcall.mcalk.mcalj._require_owned_guard_identity(
                owned_guard
            )
        except Exception as exc:
            raise _error("P-E0-M owned guard identity drifted") from exc
    namespace_before = _require_namespace(
        repo_root,
        p_present=False,
        allow_locker_guard=owned_guard is not None,
        r_present_paths=expected_present,
    )
    if _physical_snapshot(repo_root) != expected_physical_snapshot:
        raise _error("P-E0-M physical authority changed during publication")
    if owned_guard is not None:
        try:
            mid.mic.mcalm.mcall.mcalk.mcalj._require_owned_guard_identity(
                owned_guard
            )
        except Exception as exc:
            raise _error("P-E0-M owned guard identity drifted") from exc
    namespace_after = _require_namespace(
        repo_root,
        p_present=False,
        allow_locker_guard=owned_guard is not None,
        r_present_paths=expected_present,
    )
    if namespace_after != namespace_before:
        raise _error("P-E0-M namespace changed during publication boundary")
    if owned_guard is not None:
        try:
            mid.mic.mcalm.mcall.mcalk.mcalj._require_owned_guard_identity(
                owned_guard
            )
        except Exception as exc:
            raise _error("P-E0-M owned guard identity drifted") from exc


def publish_formal_model_lock_authority_bundle(
    payload: Mapping[str, Any], *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _root(repo_root)
    frozen = validate_formal_model_lock_authority_payload(
        payload, verify_remote=True, repo_root=root
    )
    repository = cast(Mapping[str, Any], frozen["repository"])
    h_head = cast(str, repository["h_batch_head"])
    _repository_state(repo_root=root, verify_remote=True)
    _require_namespace(root)
    physical = _physical_snapshot(root)
    authority_bytes = _canonical_json_bytes(frozen)
    authority_record = {
        "role": "formal_model_lock_authority",
        "path": DEFAULT_AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": _sha256_bytes(authority_bytes),
    }
    companion = _expected_authority_companion(frozen, authority_record)
    published: list[Any] = []
    guard: Any | None = None
    committed = False
    publication = mid.mic.mcalm.mcall.mcalk.mcalj
    try:
        guard = mid.mt._acquire_publication_guard(
            LOCKER_GUARD_PATH,
            b"E0-M formal model lock authority\n",
            repo_root=root,
        )
        _require_p_repository_boundary(
            h_head=h_head,
            expected_present=(),
            expected_physical_snapshot=physical,
            repo_root=root,
            owned_guard=guard,
        )
        authority_output = publication._publish_bytes_no_clobber(
            DEFAULT_AUTHORITY_PATH, authority_bytes, repo_root=root
        )
        published.append(authority_output)
        publication._validate_owned_output_bytes(
            authority_output,
            authority_bytes,
            repo_root=root,
            context="P-E0-M authority publication",
        )
        _require_p_repository_boundary(
            h_head=h_head,
            expected_present=(DEFAULT_AUTHORITY_PATH,),
            expected_physical_snapshot=physical,
            repo_root=root,
            owned_guard=guard,
        )
        companion_bytes = _canonical_json_bytes(companion)
        companion_output = publication._publish_bytes_no_clobber(
            DEFAULT_AUTHORITY_MANIFEST_PATH, companion_bytes, repo_root=root
        )
        published.append(companion_output)
        publication._require_owned_identity_set(
            published, context="P-E0-M final publication"
        )
        for output, expected in (
            (authority_output, authority_bytes),
            (companion_output, companion_bytes),
        ):
            publication._validate_owned_output_bytes(
                output, expected, repo_root=root, context="P-E0-M publication"
            )
        _require_p_repository_boundary(
            h_head=h_head,
            expected_present=CURRENT_LOCK_PATHS,
            expected_physical_snapshot=physical,
            repo_root=root,
            owned_guard=guard,
        )
        mid.mt._release_publication_guard(guard)
        guard = None
        for _pass_index in (1, 2):
            publication._require_owned_identity_set(
                published, context="P-E0-M post-release publication"
            )
            for output, expected in (
                (authority_output, authority_bytes),
                (companion_output, companion_bytes),
            ):
                publication._validate_owned_output_bytes(
                    output,
                    expected,
                    repo_root=root,
                    context="P-E0-M post-release publication",
                )
            _require_p_repository_boundary(
                h_head=h_head,
                expected_present=CURRENT_LOCK_PATHS,
                expected_physical_snapshot=physical,
                repo_root=root,
                owned_guard=None,
            )
        committed = True
        return frozen, companion
    except BaseException as exc:
        rollback = publication._rollback_outputs_best_effort(published)
        if rollback is not None:
            exc.add_note(str(rollback))
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, ClosureFormalModelLockError):
            raise
        raise _error("P authority publication failed") from exc
    finally:
        if guard is not None:
            try:
                mid.mt._release_publication_guard(guard, tolerate_foreign=True)
            except Exception:
                pass
        if committed:
            for output in reversed(published):
                try:
                    publication._close_owned_output(output)
                except Exception:
                    pass


def _unpublished_p_content_snapshot(repo_root: Path) -> dict[str, Any]:
    """Capture the complete physical P/predecessor namespace."""

    namespace_before = _require_namespace(repo_root, p_present=True)
    result = {
        "p_pair": _p_pair_snapshot(repo_root),
        "physical": _physical_snapshot(repo_root),
    }
    namespace_after = _require_namespace(repo_root, p_present=True)
    if namespace_after != namespace_before:
        raise _error("unpublished P namespace changed during content capture")
    return {"namespace": namespace_after, **result}


def _unpublished_p_repository_snapshot(
    *,
    repo_root: Path,
    verify_remote: bool,
    h_head: str,
) -> dict[str, Any]:
    """Capture only terminal refs, topology, remote, and status for P."""

    try:
        head = mcal._git_head(repo_root)
        branch = cast(
            str, mcal._git(repo_root, "symbolic-ref", "--short", "HEAD")
        ).strip()
        main = mcal._git_head(repo_root, "main")
        tracking = mcal._git_head(repo_root, "origin/main")
        tracking_head = mcal._git_head(repo_root, "origin/HEAD")
        remote = (
            mcal._live_remote_main_head(repo_root) if verify_remote else tracking
        )
        status = tuple(sorted(_status_map(repo_root).items()))
        parent = mcal._single_parent(repo_root, h_head, context=H_GATE)
        scope = mcal._git_scope(
            repo_root, BASE_H_E0_M_PREREQUISITE_COMMIT, h_head
        )
    except Exception as exc:
        raise _error("unpublished P terminal repository capture failed") from exc
    if (
        head != h_head
        or branch != "main"
        or main != h_head
        or tracking != h_head
        or tracking_head != h_head
        or remote != h_head
        or parent != BASE_H_E0_M_PREREQUISITE_COMMIT
        or scope != _expected_h_scope()
    ):
        raise _error("unpublished P terminal repository topology drifted")
    return {
        "refs": (head, branch, main, tracking, tracking_head, remote),
        "topology": (parent, scope),
        "status": status,
    }


def validate_formal_model_lock_unpublished_authority_bundle(
    *,
    require_staged: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    authority, authority_bytes, authority_metadata = _parse_canonical_json(
        DEFAULT_AUTHORITY_PATH, repo_root=root
    )
    companion, companion_bytes, companion_metadata = _parse_canonical_json(
        DEFAULT_AUTHORITY_MANIFEST_PATH, repo_root=root
    )
    repository = authority.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_batch_head"), str
    ):
        raise _error("unpublished P H binding is absent")
    h_head = cast(str, repository["h_batch_head"])
    state, h_patch = _repository_state(
        repo_root=root, verify_remote=verify_remote, allow_p_outputs=True
    )
    if state.get("h_state") != "published" or state.get("h_batch_head") != h_head:
        raise _error("unpublished P requires exact published H-E0-MBATCH")
    observed = _status_map(root)
    untracked = {path.as_posix(): "??" for path in CURRENT_LOCK_PATHS}
    staged = {path.as_posix(): "A " for path in CURRENT_LOCK_PATHS}
    if observed == untracked:
        stage_state = "untracked"
    elif observed == staged:
        stage_state = "staged"
    else:
        raise _error("unpublished P workspace is not exact2")
    if require_staged and stage_state != "staged":
        raise _error("unpublished P is not exact2 staged")
    validate_formal_model_lock_authority_payload(
        authority, verify_remote=verify_remote, repo_root=root
    )
    authority_record = {
        "role": "formal_model_lock_authority",
        "path": DEFAULT_AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": _sha256_bytes(authority_bytes),
    }
    if _canonical_json_bytes(companion) != _canonical_json_bytes(
        _expected_authority_companion(authority, authority_record)
    ):
        raise _error("unpublished P companion drifted")
    pair_snapshot = _p_pair_snapshot(root)
    physical_snapshot = _physical_snapshot(root)
    identity = mid.mic.mcalm.mcall.mcalk.mcalj._metadata_identity
    recaptured_authority, recaptured_authority_bytes, recaptured_authority_metadata = (
        _parse_canonical_json(DEFAULT_AUTHORITY_PATH, repo_root=root)
    )
    recaptured_companion, recaptured_companion_bytes, recaptured_companion_metadata = (
        _parse_canonical_json(DEFAULT_AUTHORITY_MANIFEST_PATH, repo_root=root)
    )
    terminal_state, terminal_h_patch = _repository_state(
        repo_root=root, verify_remote=verify_remote, allow_p_outputs=True
    )
    if (
        terminal_state != state
        or terminal_h_patch != h_patch
        or _status_map(root) != observed
        or recaptured_authority != authority
        or recaptured_companion != companion
        or recaptured_authority_bytes != authority_bytes
        or recaptured_companion_bytes != companion_bytes
        or identity(recaptured_authority_metadata) != identity(authority_metadata)
        or identity(recaptured_companion_metadata) != identity(companion_metadata)
        or _p_pair_snapshot(root) != pair_snapshot
        or _physical_snapshot(root) != physical_snapshot
    ):
        raise _error("unpublished P changed during validation")
    content_before = _unpublished_p_content_snapshot(root)
    repository_before = _unpublished_p_repository_snapshot(
        repo_root=root, verify_remote=verify_remote, h_head=h_head
    )
    content_after = _unpublished_p_content_snapshot(root)
    if (
        content_before != content_after
        or content_after["p_pair"] != pair_snapshot
        or content_after["physical"] != physical_snapshot
    ):
        raise _error("unpublished P content changed at the terminal boundary")
    repository_after = _unpublished_p_repository_snapshot(
        repo_root=root, verify_remote=verify_remote, h_head=h_head
    )
    if (
        repository_before != repository_after
        or repository_after["status"] != tuple(sorted(observed.items()))
    ):
        raise _error("unpublished P repository changed at the terminal boundary")
    return {
        "gate": PATCH_GATE,
        "status": "locked_unpublished",
        "h_batch_head": h_head,
        "p_stage_state": stage_state,
        "p_output_count": 2,
        "formal_model_lock_ready": True,
        "p_authority_generation_authorized": True,
        "effective_authority": False,
        "formal_lock_execution_authorized": False,
        "e0_m_authorized": False,
        "e0_u_authorized": False,
        "evaluation_authorized": False,
        "outcome_access_authorized": False,
        "target_access_authorized": False,
        "dvc_commands_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
        "writes_performed": False,
    }


def load_effective_formal_model_lock_authority(
    *,
    verify_remote: bool = True,
    repo_root: Path | None = None,
    _owned_formal_run_guard: Any | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    if _owned_formal_run_guard is not None:
        try:
            mid.mic.mcalm.mcall.mcalk.mcalj._require_owned_guard_identity(
                _owned_formal_run_guard
            )
        except Exception as exc:
            raise _error("effective E0-M formal guard identity drifted") from exc
    authority, authority_bytes, authority_metadata = _parse_canonical_json(
        DEFAULT_AUTHORITY_PATH, repo_root=root
    )
    repository = authority.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_batch_head"), str
    ):
        raise _error("published authority H binding is absent")
    h_head = cast(str, repository["h_batch_head"])
    _validate_published_authority_payload(
        authority, h_head=h_head, repo_root=root
    )
    authority_record = {
        "role": "formal_model_lock_authority",
        "path": DEFAULT_AUTHORITY_PATH.as_posix(),
        "bytes": len(authority_bytes),
        "sha256": _sha256_bytes(authority_bytes),
    }
    companion, companion_bytes, companion_metadata = _parse_canonical_json(
        DEFAULT_AUTHORITY_MANIFEST_PATH, repo_root=root
    )
    if _canonical_json_bytes(companion) != _canonical_json_bytes(
        _expected_authority_companion(authority, authority_record)
    ):
        raise _error("published authority companion drifted")
    try:
        head = mcal._git_head(root)
        branch = cast(str, mcal._git(root, "branch", "--show-current")).strip()
        parent = mcal._single_parent(root, head, context="P/R-E0-M")
    except Exception as exc:
        raise _error("effective P/R topology cannot be read") from exc
    p_scope = {
        "added": 2,
        "modified": 0,
        "deleted": 0,
        "path_count": 2,
        "paths": sorted(path.as_posix() for path in CURRENT_LOCK_PATHS),
    }
    r_scope = {
        "added": 5,
        "modified": 0,
        "deleted": 0,
        "path_count": 5,
        "paths": sorted(path.as_posix() for path in FORMAL_OUTPUT_PATHS),
    }
    if parent == h_head:
        p_head, r_head = head, None
        if mcal._git_scope(root, h_head, p_head) != p_scope:
            raise _error("published P-E0-M scope drifted")
    else:
        r_head, p_head = head, parent
        if (
            mcal._single_parent(root, p_head, context=P_GATE) != h_head
            or mcal._git_scope(root, h_head, p_head) != p_scope
            or mcal._git_scope(root, p_head, r_head) != r_scope
        ):
            raise _error("published R-E0-M topology drifted")
    tracking = mcal._git_head(root, "origin/main")
    tracking_head = mcal._git_head(root, "origin/HEAD")
    remote = mcal._live_remote_main_head(root) if verify_remote else tracking
    if branch != "main" or tracking != head or tracking_head != head or remote != head:
        raise _error("effective E0-M refs drifted")
    for path in CURRENT_LOCK_PATHS:
        payload, _metadata = mcal._read_regular_bytes_and_metadata(
            path,
            repo_root=root,
            expected_mode=0o644,
            require_nlink_one=True,
        )
        mode, _oid = mcal._git_mode_oid(root, p_head, path)
        if mode != "100644" or payload != mcal._git_blob_bytes(root, p_head, path):
            raise _error(f"published P-E0-M binding drifted: {path.as_posix()}")
    present = [mcal._entry_exists(path, repo_root=root) for path in FORMAL_OUTPUT_PATHS]
    if any(present) and not all(present):
        raise _error("formal R namespace is partial")
    r_present = all(present)
    observed = _status_map(root)
    if r_head is not None:
        if not r_present or observed:
            raise _error("published R-E0-M workspace drifted")
        for path in FORMAL_OUTPUT_PATHS:
            payload, _metadata = mcal._read_regular_bytes_and_metadata(
                path,
                repo_root=root,
                expected_mode=0o644,
                require_nlink_one=True,
            )
            mode, _oid = mcal._git_mode_oid(root, r_head, path)
            if mode != "100644" or payload != mcal._git_blob_bytes(root, r_head, path):
                raise _error(f"published R-E0-M binding drifted: {path.as_posix()}")
        r_stage_state = "published"
    elif not r_present:
        if observed:
            raise _error("published P-E0-M clean workspace drifted")
        r_stage_state = "absent"
    else:
        untracked = {path.as_posix(): "??" for path in FORMAL_OUTPUT_PATHS}
        staged = {path.as_posix(): "A " for path in FORMAL_OUTPUT_PATHS}
        if observed == untracked:
            r_stage_state = "exact5_untracked"
        elif observed == staged:
            r_stage_state = "exact5_staged"
        else:
            raise _error("unpublished formal R workspace drifted")
    _require_namespace(
        root,
        p_present=True,
        r_present=r_present,
        allow_formal_run_guard=_owned_formal_run_guard is not None,
    )
    p_snapshot = _p_pair_snapshot(root)
    physical_snapshot = _physical_snapshot(root)
    identity = mid.mic.mcalm.mcall.mcalk.mcalj._metadata_identity
    recaptured_authority, recaptured_authority_bytes, recaptured_authority_metadata = (
        _parse_canonical_json(DEFAULT_AUTHORITY_PATH, repo_root=root)
    )
    recaptured_companion, recaptured_companion_bytes, recaptured_companion_metadata = (
        _parse_canonical_json(DEFAULT_AUTHORITY_MANIFEST_PATH, repo_root=root)
    )
    if (
        recaptured_authority != authority
        or recaptured_companion != companion
        or recaptured_authority_bytes != authority_bytes
        or recaptured_companion_bytes != companion_bytes
        or identity(recaptured_authority_metadata) != identity(authority_metadata)
        or identity(recaptured_companion_metadata) != identity(companion_metadata)
        or _p_pair_snapshot(root) != p_snapshot
        or _physical_snapshot(root) != physical_snapshot
    ):
        raise _error("effective E0-M authority changed while loading")
    terminal_boundary = _effective_boundary_snapshot(
        repo_root=root,
        verify_remote=verify_remote,
        h_head=h_head,
        p_head=p_head,
        r_head=r_head,
        r_present=r_present,
        _owned_formal_run_guard=_owned_formal_run_guard,
    )
    result = {
        "gate": PATCH_GATE,
        "status": "effective",
        "h_batch_head": h_head,
        "p_patch_head": p_head,
        "r_patch_head": r_head,
        "remote_head": remote,
        "p_stage_state": "published",
        "r_state": "complete" if r_present else "absent",
        "r_stage_state": r_stage_state,
        "formal_model_lock_ready": True,
        "calibration_evidence": _deep_copy(authority["calibration_evidence"]),
        "p_authority_generation_authorized": False,
        "effective_authority": True,
        "formal_lock_execution_authorized": not r_present,
        "e0_m_authorized": r_stage_state == "published",
        "e0_u_authorized": False,
        "evaluation_authorized": False,
        "outcome_access_authorized": False,
        "target_access_authorized": False,
        "dvc_commands_authorized": False,
        "git_commit_authorized": False,
        "git_push_authorized": False,
        "writes_performed": False,
    }
    if r_present:
        expected_before = _build_formal_output_bytes(result, repo_root=root)
        snapshot_before = _formal_output_snapshot(root)
        for path, expected_payload in expected_before:
            try:
                payload, _metadata = mcal._read_regular_bytes_and_metadata(
                    path,
                    repo_root=root,
                    expected_mode=0o644,
                    require_nlink_one=True,
                )
            except Exception as exc:
                raise _error(
                    f"effective formal R output cannot be read: {path.as_posix()}"
                ) from exc
            if payload != expected_payload:
                raise _error(
                    f"effective formal R semantic bytes drifted: {path.as_posix()}"
                )
        expected_after = _build_formal_output_bytes(result, repo_root=root)
        snapshot_after = _formal_output_snapshot(root)
        if expected_before != expected_after or snapshot_before != snapshot_after:
            raise _error("effective formal R changed during semantic reconstruction")
    if _effective_boundary_snapshot(
        repo_root=root,
        verify_remote=verify_remote,
        h_head=h_head,
        p_head=p_head,
        r_head=r_head,
        r_present=r_present,
        _owned_formal_run_guard=_owned_formal_run_guard,
    ) != terminal_boundary:
        raise _error("effective E0-M boundary changed during semantic reconstruction")
    return result


def require_formal_model_lock_authority(
    *,
    verify_remote: bool = True,
    repo_root: Path | None = None,
    _owned_formal_run_guard: Any | None = None,
) -> dict[str, Any]:
    authority = load_effective_formal_model_lock_authority(
        verify_remote=verify_remote,
        repo_root=repo_root,
        _owned_formal_run_guard=_owned_formal_run_guard,
    )
    if (
        authority.get("formal_model_lock_ready") is not True
        or authority.get("effective_authority") is not True
        or authority.get("evaluation_authorized") is not False
        or authority.get("e0_u_authorized") is not False
        or authority.get("outcome_access_authorized") is not False
    ):
        raise _error("effective formal model-lock authority drifted")
    return authority


def _read_csv_rows(
    path: Path, *, expected_fields: Sequence[str], repo_root: Path
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    record = _read_record(path, role="formal_model_lock_csv_input", repo_root=repo_root)
    try:
        payload, _metadata = mcal._read_regular_bytes_and_metadata(
            path,
            repo_root=repo_root,
            expected_mode=0o644,
            require_nlink_one=True,
        )
        text = payload.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if reader.fieldnames != list(expected_fields):
            raise _error(f"CSV header drifted: {path.as_posix()}")
        rows = [dict(row) for row in reader]
    except (UnicodeDecodeError, csv.Error) as exc:
        raise _error(f"CSV parsing failed: {path.as_posix()}") from exc
    if any(set(row) != set(expected_fields) for row in rows):
        raise _error(f"CSV row dialect drifted: {path.as_posix()}")
    return rows, _portable_content_record(record)


def _model_availability_records(
    repo_root: Path, *, git_commit: str | None = None
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    fields = (
        "model_id",
        "availability",
        "availability_reason",
        "seed_policy",
        "calibration_seed_source",
        "selected_family",
        "seeds",
        "horizons_months",
        "bloom_score_source",
        "bloom_calibration",
        "ordinal_calibration",
        "uncertainty_calibration",
    )
    commit = _scientific_binding_commit(repo_root, git_commit)
    payload, physical = _read_scientific_git_bytes_and_record(
        MODEL_AVAILABILITY_PATH,
        role="model_availability_git_input",
        repo_root=repo_root,
        git_commit=commit,
    )
    try:
        reader = csv.DictReader(
            io.StringIO(payload.decode("utf-8"), newline="")
        )
        if reader.fieldnames != list(fields):
            raise _error("model availability CSV header drifted")
        rows = [dict(row) for row in reader]
    except (UnicodeDecodeError, csv.Error) as exc:
        raise _error("model availability CSV parsing failed") from exc
    if any(set(row) != set(fields) for row in rows):
        raise _error("model availability CSV row dialect drifted")
    if (
        len(rows) != len(runner.MODEL_IDS)
        or [row["model_id"] for row in rows] != list(runner.MODEL_IDS)
        or {
            row["model_id"]: row["availability"] for row in rows
        }
        != dict(runner.CURRENT_MODEL_AVAILABILITY)
    ):
        raise _error("model availability registry drifted")
    for row in rows:
        if row["model_id"] in {"P0", "P1", "A2"} and (
            row["availability"] != "unavailable"
            or "not_attempted" not in row["bloom_calibration"]
        ):
            raise _error(f"unavailable model policy drifted: {row['model_id']}")
    return rows, _portable_scientific_git_record(physical)


def _physical_manifest_output_binding(
    output: Mapping[str, Any], *, repo_root: Path
) -> tuple[dict[str, Any], int, dict[str, Any]]:
    if set(output) - {
        "role",
        "artifact_role",
        "module",
        "path",
        "bytes",
        "sha256",
    }:
        raise _error("model manifest output contains unknown fields")
    path_value = output.get("path")
    bytes_value = output.get("bytes")
    sha_value = output.get("sha256")
    role = output.get("role", output.get("artifact_role", "artifact"))
    if (
        not isinstance(path_value, str)
        or type(bytes_value) is not int
        or bytes_value < 0
        or not isinstance(sha_value, str)
        or len(sha_value) != 64
        or any(character not in "0123456789abcdef" for character in sha_value)
        or not isinstance(role, str)
    ):
        raise _error("model manifest output record drifted")
    path = Path(path_value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != path_value
    ):
        raise _error(f"model artifact path is not canonical: {path_value}")
    pointer_path = Path(f"{path_value}.dvc")
    try:
        payload, metadata = mcal._read_scientific_payload_bytes_and_metadata(
            path,
            authorized_dvc_pointers=(pointer_path,),
            repo_root=repo_root,
        )
    except Exception as exc:
        raise _error(f"model artifact cannot be read: {path_value}") from exc
    mode = stat.S_IMODE(metadata.st_mode)
    if mode == 0o444:
        try:
            pointer = mcal._load_yaml_object(pointer_path, repo_root=repo_root)
        except Exception as exc:
            raise _error(f"DVC pointer cannot be read: {pointer_path.as_posix()}") from exc
        outputs = pointer.get("outs")
        pointer_output = outputs[0] if isinstance(outputs, list) and len(outputs) == 1 else None
        payload_md5 = hashlib.md5(payload, usedforsecurity=False).hexdigest()
        if (
            set(pointer) != {"outs"}
            or not isinstance(pointer_output, Mapping)
            or set(pointer_output) != {"md5", "size", "hash", "path"}
            or pointer_output.get("md5") != payload_md5
            or pointer_output.get("size") != len(payload)
            or pointer_output.get("hash") != "md5"
            or pointer_output.get("path") != path.name
        ):
            raise _error(f"DVC pointer binding drifted: {pointer_path.as_posix()}")
    if (
        not stat.S_ISREG(metadata.st_mode)
        or (mode == 0o644 and metadata.st_nlink != 1)
        or (mode == 0o444 and metadata.st_nlink != 2)
        or mode not in {0o444, 0o644}
        or len(payload) != bytes_value
        or _sha256_bytes(payload) != sha_value
    ):
        raise _error(f"model artifact binding drifted: {path_value}")
    portable = {
            "role": role,
            "path": path_value,
            "bytes": bytes_value,
            "sha256": sha_value,
    }
    physical = {
        **portable,
        "device": int(metadata.st_dev),
        "inode": int(metadata.st_ino),
        "mode": mode,
        "nlink": int(metadata.st_nlink),
        "mtime_ns": int(metadata.st_mtime_ns),
        "ctime_ns": int(metadata.st_ctime_ns),
    }
    return portable, mode, physical


def _validate_physical_manifest_output(
    output: Mapping[str, Any], *, repo_root: Path
) -> dict[str, Any]:
    record, _mode, _physical = _physical_manifest_output_binding(
        output, repo_root=repo_root
    )
    return record


def _validate_manifest_output_record(
    output: Mapping[str, Any], *, repo_root: Path
) -> dict[str, Any]:
    """Validate an output physically, allowing only DVC hardlink fan-out."""

    return _validate_physical_manifest_output(output, repo_root=repo_root)


def _capture_model_manifest_inventory(
    repo_root: Path, *, git_commit: str | None = None
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    commit = _scientific_binding_commit(repo_root, git_commit)
    expected_dvc_payloads = set(MODEL_DVC_PAYLOAD_PATHS)
    expected_dvc_pointers = {
        payload: pointer
        for payload, pointer in zip(
            MODEL_DVC_PAYLOAD_PATHS, MODEL_DVC_POINTER_PATHS, strict=True
        )
    }
    if (
        len(MODEL_MANIFEST_PATHS) != MODEL_MANIFEST_COUNT
        or len(set(MODEL_MANIFEST_PATHS)) != MODEL_MANIFEST_COUNT
        or len(expected_dvc_payloads) != MODEL_DVC_POINTER_COUNT
        or len(expected_dvc_pointers) != MODEL_DVC_POINTER_COUNT
    ):
        raise _error("model inventory path contract drifted")
    manifests: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    physical_artifacts: dict[str, dict[str, Any]] = {}
    artifact_roles: dict[str, list[str]] = {}
    dvc_payloads: set[Path] = set()
    pointer_records: dict[Path, dict[str, Any]] = {}
    for path in MODEL_MANIFEST_PATHS:
        try:
            payload, physical = _read_scientific_git_bytes_and_record(
                path,
                role="formal_model_manifest_git_input",
                repo_root=repo_root,
                git_commit=commit,
            )
            value = mcal._parse_json_bytes(payload, context=path.as_posix())
        except Exception as exc:
            raise _error(f"model manifest cannot be loaded: {path.as_posix()}") from exc
        if not isinstance(value, dict):
            raise _error(f"model manifest is not an object: {path.as_posix()}")
        if value.get("experiment_id") != EXPERIMENT_ID:
            raise _error(f"model manifest experiment drifted: {path.as_posix()}")
        if value.get("future_outcomes_accessed") not in {False, None}:
            raise _error(f"model manifest opened future outcomes: {path.as_posix()}")
        model_id = value.get("model_id")
        matched_seeds = [
            seed
            for seed in runner.REGISTERED_SEEDS
            if f"seed_{seed}" in path.as_posix()
        ]
        if matched_seeds and (
            len(matched_seeds) != 1 or value.get("base_seed") != matched_seeds[0]
        ):
            raise _error(f"model manifest seed binding drifted: {path.as_posix()}")
        temporal_model = next(
            (
                candidate
                for candidate in ("P0", "P1", "A0", "A1")
                if f"/02_models/{candidate}/" in f"/{path.as_posix()}"
            ),
            None,
        )
        if temporal_model in {"P0", "P1"}:
            if (
                model_id != temporal_model
                or
                value.get("slot_status") != "model_unavailable"
                or value.get("fit_status") != "not_attempted"
                or value.get("failure_reason") != "sequence_fit_rows_unavailable"
                or value.get("model_artifact_emitted") is not False
            ):
                raise _error(f"unavailable temporal slot drifted: {path.as_posix()}")
        if temporal_model in {"A0", "A1"} and (
            model_id != temporal_model
            or value.get("slot_status") != "available"
            or value.get("fit_status") != "passed"
        ):
            raise _error(f"ANFIS ablation slot drifted: {path.as_posix()}")
        if path == MODEL_MANIFEST_PATHS[0] and (
            value.get("status") != "completed" or model_id != "P0"
        ):
            raise _error("expert-state manifest identity/status drifted")
        if "/01_surface/anfis/" in f"/{path.as_posix()}" and (
            model_id != "F1"
            or value.get("status") != "completed"
            or value.get("slot_status") != "available"
            or value.get("fit_status") != "passed"
        ):
            raise _error(f"F1 manifest status drifted: {path.as_posix()}")
        if path.as_posix().endswith("/baselines/manifest.json") and (
            value.get("status") != "completed"
            or value.get("models") != ["B0", "B1", "B2"]
            or value.get("seeds") != list(runner.REGISTERED_SEEDS)
        ):
            raise _error("baseline manifest model/seed/status drifted")
        if path.as_posix().endswith("/M0/manifest.json") and (
            model_id != "M0"
            or value.get("status") != "mifal_development_bundle_written_unpublished"
        ):
            raise _error("M0 manifest status drifted")
        manifests.append(_portable_scientific_git_record(physical))
        raw_outputs = value.get("outputs", [])
        if not isinstance(raw_outputs, list):
            raise _error(f"model manifest outputs drifted: {path.as_posix()}")
        manifest_outputs: list[dict[str, Any]] = []
        for output in raw_outputs:
            if not isinstance(output, Mapping):
                continue
            validated, physical_mode, physical_record = _physical_manifest_output_binding(
                output, repo_root=repo_root
            )
            payload_path = Path(cast(str, validated["path"]))
            path_text = payload_path.as_posix()
            role = cast(str, validated["role"])
            identity_record = {
                key: value
                for key, value in physical_record.items()
                if key != "role"
            }
            previous_physical = physical_artifacts.get(path_text)
            if previous_physical is not None and previous_physical != identity_record:
                raise _error(f"model artifact alias binding drifted: {path_text}")
            physical_artifacts[path_text] = identity_record
            artifact_roles.setdefault(path_text, []).append(role)
            expected_dvc = payload_path in expected_dvc_payloads
            if (physical_mode == 0o444) is not expected_dvc:
                raise _error(
                    f"model DVC payload mode contract drifted: {payload_path.as_posix()}"
                )
            if expected_dvc:
                pointer_path = expected_dvc_pointers[payload_path]
                if payload_path in dvc_payloads or pointer_path in pointer_records:
                    raise _error(
                        f"model DVC payload is duplicated: {payload_path.as_posix()}"
                    )
                dvc_payloads.add(payload_path)
                pointer_records[pointer_path] = _portable_scientific_git_record(
                    _scientific_git_record(
                        pointer_path,
                        role="model_dvc_pointer_git_input",
                        repo_root=repo_root,
                        git_commit=commit,
                    )
                )
            manifest_outputs.append(validated)
        if len(manifest_outputs) != len(raw_outputs):
            raise _error(f"model manifest output item drifted: {path.as_posix()}")
        if temporal_model in {"P0", "P1"} and any(
            output["role"] != "report" for output in manifest_outputs
        ):
            raise _error(f"unavailable slot emitted forbidden artifacts: {path.as_posix()}")
        artifacts.extend(manifest_outputs)
    manifests.sort(key=lambda record: cast(str, record["path"]))
    artifacts.sort(key=lambda record: (cast(str, record["path"]), cast(str, record["role"])))
    if len({(item["path"], item["role"]) for item in artifacts}) != len(artifacts):
        raise _error("model artifact inventory contains duplicates")
    if (
        len(manifests) != MODEL_MANIFEST_COUNT
        or len(artifacts) != MODEL_ARTIFACT_RECORD_COUNT
        or dvc_payloads != expected_dvc_payloads
        or set(pointer_records) != set(MODEL_DVC_POINTER_PATHS)
    ):
        raise _error("model manifest/artifact/DVC inventory is not exact28/exact220/exact10")
    if sum(len(roles) for roles in artifact_roles.values()) != MODEL_ARTIFACT_RECORD_COUNT:
        raise _error("model artifact role multiset is not exact220")
    artifact_snapshot = tuple(
        {
            **physical_artifacts[path],
            "roles": tuple(sorted(artifact_roles[path])),
        }
        for path in sorted(physical_artifacts)
    )
    pointers = [pointer_records[path] for path in sorted(pointer_records)]
    forbidden_present = [
        path.as_posix()
        for path in (*UNAVAILABLE_MODEL_FORBIDDEN_PATHS, *A2_FORBIDDEN_PATHS)
        if mcal._entry_exists(path, repo_root=repo_root)
    ]
    if forbidden_present:
        raise _error(
            f"unavailable model namespace contains forbidden artifacts: {forbidden_present}"
        )
    return ({
        "manifest_count": len(manifests),
        "manifests": manifests,
        "manifest_digest": _sha256_bytes(_canonical_json_bytes(manifests)),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "artifact_digest": _sha256_bytes(_canonical_json_bytes(artifacts)),
        "dvc_pointer_count": len(pointers),
        "dvc_pointers": pointers,
        "dvc_pointer_digest": _sha256_bytes(_canonical_json_bytes(pointers)),
    }, artifact_snapshot)


def _model_manifest_inventory(
    repo_root: Path, *, git_commit: str | None = None
) -> dict[str, Any]:
    inventory, _artifact_snapshot = _capture_model_manifest_inventory(
        repo_root, git_commit=git_commit
    )
    return inventory


def _model_artifact_snapshot(
    repo_root: Path, *, git_commit: str | None = None
) -> tuple[dict[str, Any], ...]:
    """Seal exact artifact identities and the manifest path/role multiset."""

    _inventory, artifact_snapshot = _capture_model_manifest_inventory(
        repo_root, git_commit=git_commit
    )
    return artifact_snapshot


def _hypothesis_registry_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(
        hypothesis_id: str,
        family: str,
        comparison: str,
        endpoints: str,
        *,
        estimand: str,
        alternative: str,
        universe_size: int,
        availability_condition: str,
    ) -> None:
        rows.append(
            {
                "hypothesis_id": hypothesis_id,
                "multiplicity_family": family,
                "comparison_id": comparison,
                "endpoints": endpoints,
                "estimand": estimand,
                "alternative": alternative,
                "evaluation_cohort": "locked_location_holdout",
                "horizons_months": "1;2;3",
                "multiplicity_universe_size": str(universe_size),
                "correction_method": "holm",
                "family_wise_alpha": "0.05",
                "availability_condition": availability_condition,
                "status": "not_estimable_model_unavailable",
                "availability_reason": "P1_model_unavailable_no_substitution",
                "p_value": "",
                "effect_estimate": "",
                "confidence_interval": "",
                "holm_universe_retained": "true",
            }
        )

    for hypothesis_id, comparison in FAMILY_A_COMPARISONS:
        add(
            hypothesis_id,
            "A",
            comparison,
            "pr_auc;brier",
            estimand="paired_observation_weighted_and_location_balanced",
            alternative="greater_pr_auc_and_lower_brier",
            universe_size=3,
            availability_condition="both_models_available_on_exact_common_rows",
        )
    for comparison in FAMILY_B_COMPARISONS:
        add(
            f"H4_{comparison}",
            "B",
            comparison,
            "pr_auc;brier",
            estimand="paired_five_seed_mean_delta_by_scenario_horizon_endpoint",
            alternative="two_sided",
            universe_size=78,
            availability_condition="M0_and_P1_available_on_exact_shared_success_rows",
        )
    add(
        "H_surface_A2_vs_P1",
        "C",
        "A2_vs_P1",
        "pr_auc;brier",
        estimand="paired_observation_weighted_and_location_balanced",
        alternative="greater_pr_auc_and_lower_brier",
        universe_size=1,
        availability_condition="A2_and_P1_available_on_exact_common_rows",
    )
    for comparison in FAMILY_D_COMPARISONS:
        add(
            f"H_D_{comparison}",
            "D",
            comparison,
            "delta_objective_vs_no_action",
            estimand="observation_weighted_mean_exact_common_origins_all_horizons",
            alternative="greater_than_zero",
            universe_size=9,
            availability_condition="P1_available_all_five_seeds_action_and_no_action",
        )
    add(
        "H_E_uncertainty_before_vs_after_recalibration",
        "E",
        "uncertainty_before_vs_after_recalibration",
        "winkler_interval_score_0_90",
        estimand="paired_mean_delta_equal_weight_endpoints_and_horizons",
        alternative="less_than_zero",
        universe_size=1,
        availability_condition="P1_available_all_five_seeds_exact_shared_rows",
    )
    return rows


def _hypothesis_registry_bytes() -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=list(HYPOTHESIS_REGISTRY_FIELDS),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(_hypothesis_registry_rows())
    return stream.getvalue().encode("utf-8")


def _build_formal_output_bytes(
    authority: Mapping[str, Any], *, repo_root: Path
) -> tuple[tuple[Path, bytes], ...]:
    h_head = authority.get("h_batch_head")
    p_head = authority.get("p_patch_head")
    if not isinstance(h_head, str) or not isinstance(p_head, str):
        raise _error("formal output authority heads are absent")
    commit = _scientific_binding_commit(repo_root, p_head)
    availability, availability_record = _model_availability_records(
        repo_root, git_commit=commit
    )
    inventory = _model_manifest_inventory(repo_root, git_commit=commit)
    try:
        leakage_bytes, leakage_physical = _read_scientific_git_bytes_and_record(
            HOLDOUT_LEAKAGE_AUDIT_PATH,
            role="holdout_leakage_git_input",
            repo_root=repo_root,
            git_commit=commit,
        )
        leakage = mcal._parse_json_bytes(
            leakage_bytes, context=HOLDOUT_LEAKAGE_AUDIT_PATH.as_posix()
        )
    except Exception as exc:
        raise _error("holdout leakage audit cannot be loaded") from exc
    if (
        not isinstance(leakage, Mapping)
        or
        leakage.get("status") != "passed"
        or leakage.get("future_outcomes_accessed") is not False
        or leakage.get("selected_internal_holdout_locations") != 88
        or not isinstance(leakage.get("checks"), Mapping)
        or any(value is not True for value in leakage["checks"].values())
    ):
        raise _error("holdout leakage audit drifted")
    leakage_record = _portable_scientific_git_record(leakage_physical)
    calibration_lock = {
        "schema_version": "closure_formal_calibration_lock_v1",
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "status": "locked",
        "h_batch_head": h_head,
        "p_authority_head": p_head,
        "model_availability": availability,
        "model_availability_record": availability_record,
        "calibration_evidence": authority.get("calibration_evidence"),
        "unavailable_model_policy": {
            "model_ids": ["P0", "P1", "A2"],
            "status": "not_attempted_upstream_model_unavailable",
            "artifact_record_count": 0,
            "null_placeholder": "forbidden",
        },
        "development_only": True,
        "evaluation_refit": "forbidden",
        "future_outcomes_accessed": False,
        "e0_u_authorized": False,
        "outcome_access_authorized": False,
    }
    calibration_bytes = _canonical_json_bytes(calibration_lock)
    registry_bytes = _hypothesis_registry_bytes()
    command_bytes = runner.SEALED_BATCH_COMMAND.encode("utf-8")
    log_bytes = b""
    output_records = [
        {
            "path": path.as_posix(),
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
        }
        for path, payload in (
            (CALIBRATION_LOCK_PATH, calibration_bytes),
            (HYPOTHESIS_REGISTRY_PATH, registry_bytes),
            (LOCKED_BATCH_COMMAND_PATH, command_bytes),
            (OUTCOME_ACCESS_LOG_PATH, log_bytes),
        )
    ]
    model_lock = {
        "schema_version": "closure_formal_model_lock_v1",
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "status": "completed_unpublished",
        "h_batch_head": h_head,
        "p_authority_head": p_head,
        "sealed_batch_command": runner.SEALED_BATCH_COMMAND,
        "sealed_batch_contract_sha256": runner.sealed_batch_contract_sha256(),
        "runner_source": runner.runner_source_record(repo_root=repo_root),
        "model_availability": availability,
        "model_availability_record": availability_record,
        "model_inventory": inventory,
        "holdout_fit_overlap_count": 0,
        "holdout_leakage_audit": leakage_record,
        "selected_internal_holdout_locations": 88,
        "failed_model_replacement": "forbidden",
        "evaluation_refit": "forbidden",
        "formal_outputs": output_records,
        "outcome_access_log_state": "present_empty",
        "outcome_access_log_record_count": 0,
        "manifest_written_last": True,
        "e0_m_authorized": False,
        "e0_m_effective_after_publication": True,
        "e0_u_authorized": False,
        "evaluation_authorized": False,
        "outcome_access_authorized": False,
        "target_access_authorized": False,
        "future_outcomes_accessed": False,
        "scientific_execution_run": False,
        "dvc_commands_run": False,
    }
    model_bytes = _canonical_json_bytes(model_lock)
    return (
        (CALIBRATION_LOCK_PATH, calibration_bytes),
        (HYPOTHESIS_REGISTRY_PATH, registry_bytes),
        (LOCKED_BATCH_COMMAND_PATH, command_bytes),
        (OUTCOME_ACCESS_LOG_PATH, log_bytes),
        (MODEL_LOCK_PATH, model_bytes),
    )


def _formal_output_snapshot(
    repo_root: Path, *, expected_paths: Sequence[Path] = FORMAL_OUTPUT_PATHS
) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for path in expected_paths:
        try:
            payload, metadata = mcal._read_regular_bytes_and_metadata(
                path,
                repo_root=repo_root,
                expected_mode=0o644,
                require_nlink_one=True,
            )
        except Exception as exc:
            raise _error(
                f"formal output cannot be read: {path.as_posix()}"
            ) from exc
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


def _require_r_repository_boundary(
    *,
    authority: Mapping[str, Any],
    expected_present: Sequence[Path],
    expected_p_snapshot: tuple[dict[str, Any], ...],
    expected_physical_snapshot: tuple[dict[str, Any], ...],
    verify_remote: bool,
    repo_root: Path,
    owned_guard: Any | None,
) -> None:
    h_head = authority.get("h_batch_head")
    p_head = authority.get("p_patch_head")
    if not isinstance(h_head, str) or not isinstance(p_head, str):
        raise _error("R-E0-M authority heads are absent")
    try:
        head = mcal._git_head(repo_root)
        branch = cast(
            str, mcal._git(repo_root, "symbolic-ref", "--short", "HEAD")
        ).strip()
        main = mcal._git_head(repo_root, "main")
        tracking = mcal._git_head(repo_root, "origin/main")
        tracking_head = mcal._git_head(repo_root, "origin/HEAD")
        remote = (
            mcal._live_remote_main_head(repo_root) if verify_remote else tracking
        )
    except Exception as exc:
        raise _error("R-E0-M repository checkpoint failed") from exc
    if (
        head != p_head
        or branch != "main"
        or main != p_head
        or tracking != p_head
        or tracking_head != p_head
        or remote != p_head
        or mcal._single_parent(repo_root, p_head, context=P_GATE) != h_head
    ):
        raise _error("R-E0-M refs changed during materialization")
    expected_status = {path.as_posix(): "??" for path in expected_present}
    if _status_map(repo_root) != expected_status:
        raise _error("R-E0-M workspace changed during materialization")
    if owned_guard is not None:
        try:
            mid.mic.mcalm.mcall.mcalk.mcalj._require_owned_guard_identity(
                owned_guard
            )
        except Exception as exc:
            raise _error("R-E0-M owned guard identity drifted") from exc
    _require_namespace(
        repo_root,
        p_present=True,
        r_present_paths=expected_present,
        allow_formal_run_guard=owned_guard is not None,
    )
    if (
        _p_pair_snapshot(repo_root) != expected_p_snapshot
        or _physical_snapshot(repo_root) != expected_physical_snapshot
    ):
        raise _error("R-E0-M physical authority changed during materialization")
    if owned_guard is not None:
        _require_owned_formal_run_guard(owned_guard)


def execute_formal_model_lock(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    published: list[Any] = []
    guard: Any | None = None
    committed = False
    publication = mid.mic.mcalm.mcall.mcalk.mcalj
    try:
        guard = mid.mt._acquire_publication_guard(
            FORMAL_RUN_GUARD_PATH,
            b"E0-M formal model lock materialization\n",
            repo_root=root,
        )
        # No P/R authority or R-builder source is opened until this guard exists.
        authority = require_formal_model_lock_authority(
            verify_remote=verify_remote,
            repo_root=root,
            _owned_formal_run_guard=guard,
        )
        if (
            authority.get("r_state") != "absent"
            or authority.get("r_stage_state") != "absent"
            or authority.get("formal_lock_execution_authorized") is not True
            or authority.get("e0_m_authorized") is not False
        ):
            raise _error("R-E0-M execution requires effective P with absent R")
        p_snapshot = _p_pair_snapshot(root)
        physical_snapshot = _physical_snapshot(root)
        h_head = cast(str, authority["h_batch_head"])
        p_head = cast(str, authority["p_patch_head"])
        guarded_boundary = _effective_boundary_snapshot(
            repo_root=root,
            verify_remote=verify_remote,
            h_head=h_head,
            p_head=p_head,
            r_head=None,
            r_present=False,
            _owned_formal_run_guard=guard,
        )
        _require_owned_formal_run_guard(guard)
        expected_outputs = _build_formal_output_bytes(authority, repo_root=root)
        _require_owned_formal_run_guard(guard)
        if tuple(path for path, _payload in expected_outputs) != FORMAL_OUTPUT_PATHS:
            raise _error("R-E0-M output order drifted")
        if _effective_boundary_snapshot(
            repo_root=root,
            verify_remote=verify_remote,
            h_head=h_head,
            p_head=p_head,
            r_head=None,
            r_present=False,
            _owned_formal_run_guard=guard,
        ) != guarded_boundary:
            raise _error("R-E0-M authority changed during guarded build")
        for path, payload in expected_outputs:
            present_paths = tuple(item.path for item in published)
            _require_r_repository_boundary(
                authority=authority,
                expected_present=present_paths,
                expected_p_snapshot=p_snapshot,
                expected_physical_snapshot=physical_snapshot,
                verify_remote=verify_remote,
                repo_root=root,
                owned_guard=guard,
            )
            _require_owned_formal_run_guard(guard)
            rebuilt_between = _build_formal_output_bytes(authority, repo_root=root)
            _require_owned_formal_run_guard(guard)
            if rebuilt_between != expected_outputs:
                raise _error("R-E0-M builder inputs changed between publications")
            output = publication._publish_bytes_no_clobber(
                path, payload, repo_root=root
            )
            published.append(output)
            publication._validate_owned_output_bytes(
                output,
                payload,
                repo_root=root,
                context="R-E0-M publication",
            )
            publication._require_owned_identity_set(
                published, context="after R-E0-M output publication"
            )
            _require_r_repository_boundary(
                authority=authority,
                expected_present=tuple(item.path for item in published),
                expected_p_snapshot=p_snapshot,
                expected_physical_snapshot=physical_snapshot,
                verify_remote=verify_remote,
                repo_root=root,
                owned_guard=guard,
            )
        _require_owned_formal_run_guard(guard)
        rebuilt = _build_formal_output_bytes(authority, repo_root=root)
        _require_owned_formal_run_guard(guard)
        if rebuilt != expected_outputs:
            raise _error("R-E0-M output semantics changed under guard")
        for output, (_path, payload) in zip(published, expected_outputs, strict=True):
            publication._validate_owned_output_bytes(
                output,
                payload,
                repo_root=root,
                context="R-E0-M terminal validation",
            )
        mid.mt._release_publication_guard(guard)
        guard = None
        for _pass_index in (1, 2):
            _require_r_repository_boundary(
                authority=authority,
                expected_present=FORMAL_OUTPUT_PATHS,
                expected_p_snapshot=p_snapshot,
                expected_physical_snapshot=physical_snapshot,
                verify_remote=verify_remote,
                repo_root=root,
                owned_guard=None,
            )
            if _build_formal_output_bytes(authority, repo_root=root) != expected_outputs:
                raise _error("R-E0-M builder inputs changed after guard release")
            for output, (_path, payload) in zip(
                published, expected_outputs, strict=True
            ):
                publication._validate_owned_output_bytes(
                    output,
                    payload,
                    repo_root=root,
                    context="R-E0-M post-release validation",
                )
        _require_r_repository_boundary(
            authority=authority,
            expected_present=FORMAL_OUTPUT_PATHS,
            expected_p_snapshot=p_snapshot,
            expected_physical_snapshot=physical_snapshot,
            verify_remote=verify_remote,
            repo_root=root,
            owned_guard=None,
        )
        committed = True
        return {
            "gate": PATCH_GATE,
            "status": "formal_model_lock_written_unpublished",
            "h_batch_head": authority["h_batch_head"],
            "p_patch_head": authority["p_patch_head"],
            "output_count": 5,
            "outputs": [
                {
                    "path": path.as_posix(),
                    "bytes": len(payload),
                    "sha256": _sha256_bytes(payload),
                }
                for path, payload in expected_outputs
            ],
            "manifest_written_last": True,
            "outcome_access_log_state": "present_empty",
            "outcome_access_log_record_count": 0,
            "e0_m_authorized": False,
            "e0_u_authorized": False,
            "evaluation_authorized": False,
            "outcome_access_authorized": False,
            "target_access_authorized": False,
            "future_outcomes_accessed": False,
            "scientific_execution_run": False,
            "dvc_commands_run": False,
            "git_commands_mutating_run": False,
            "writes_performed": True,
        }
    except BaseException as exc:
        rollback = publication._rollback_outputs_best_effort(published)
        if rollback is not None:
            exc.add_note(str(rollback))
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, ClosureFormalModelLockError):
            raise
        raise _error("R-E0-M materialization failed") from exc
    finally:
        if guard is not None:
            try:
                mid.mt._release_publication_guard(guard, tolerate_foreign=True)
            except Exception:
                pass
        if committed:
            try:
                publication._close_outputs(published)
            except Exception:
                pass


def validate_formal_model_lock_bundle(
    *,
    require_staged: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _root(repo_root)
    authority = require_formal_model_lock_authority(
        verify_remote=verify_remote, repo_root=root
    )
    stage_state = authority.get("r_stage_state")
    if (
        authority.get("r_state") != "complete"
        or stage_state not in {"exact5_untracked", "exact5_staged", "published"}
    ):
        raise _error("formal R bundle is not complete")
    if require_staged and stage_state != "exact5_staged":
        raise _error("formal R bundle is not exact5 staged")
    expected_outputs = _build_formal_output_bytes(authority, repo_root=root)
    h_head = cast(str, authority["h_batch_head"])
    p_head = cast(str, authority["p_patch_head"])
    r_head_value = authority.get("r_patch_head")
    r_head = cast(str | None, r_head_value)
    terminal_boundary = _effective_boundary_snapshot(
        repo_root=root,
        verify_remote=verify_remote,
        h_head=h_head,
        p_head=p_head,
        r_head=r_head,
        r_present=True,
    )
    before = _formal_output_snapshot(root)
    output_records: list[dict[str, Any]] = []
    for path, expected in expected_outputs:
        try:
            payload, _metadata = mcal._read_regular_bytes_and_metadata(
                path,
                repo_root=root,
                expected_mode=0o644,
                require_nlink_one=True,
            )
        except Exception as exc:
            raise _error(f"formal output read failed: {path.as_posix()}") from exc
        if payload != expected:
            raise _error(f"formal output semantic bytes drifted: {path.as_posix()}")
        output_records.append(
            {
                "path": path.as_posix(),
                "bytes": len(payload),
                "sha256": _sha256_bytes(payload),
            }
        )
    if output_records[3]["bytes"] != 0:
        raise _error("outcome access log must remain exactly empty")
    for path in (CALIBRATION_LOCK_PATH, MODEL_LOCK_PATH):
        value, payload, _metadata = _parse_canonical_json(path, repo_root=root)
        if payload != dict(expected_outputs)[path] or not isinstance(value, dict):
            raise _error(f"formal JSON/YAML lock drifted: {path.as_posix()}")
    registry_rows, _registry_record = _read_csv_rows(
        HYPOTHESIS_REGISTRY_PATH,
        expected_fields=HYPOTHESIS_REGISTRY_FIELDS,
        repo_root=root,
    )
    if registry_rows != _hypothesis_registry_rows():
        raise _error("formal hypothesis registry semantic rows drifted")
    after = _formal_output_snapshot(root)
    if before != after or _build_formal_output_bytes(authority, repo_root=root) != expected_outputs:
        raise _error("formal R bundle changed during strict validation")
    if _effective_boundary_snapshot(
        repo_root=root,
        verify_remote=verify_remote,
        h_head=h_head,
        p_head=p_head,
        r_head=r_head,
        r_present=True,
    ) != terminal_boundary:
        raise _error("formal R repository boundary changed during strict validation")
    return {
        "gate": PATCH_GATE,
        "status": "formal_model_lock_validated",
        "h_batch_head": authority["h_batch_head"],
        "p_patch_head": authority["p_patch_head"],
        "r_patch_head": authority["r_patch_head"],
        "r_stage_state": stage_state,
        "output_count": 5,
        "outputs": output_records,
        "manifest_written_last": True,
        "outcome_access_log_state": "present_empty",
        "outcome_access_log_record_count": 0,
        "formal_model_lock_ready": True,
        "e0_m_authorized": stage_state == "published",
        "e0_u_authorized": False,
        "evaluation_authorized": False,
        "outcome_access_authorized": False,
        "target_access_authorized": False,
        "future_outcomes_accessed": False,
        "scientific_execution_run": False,
        "dvc_commands_run": False,
        "git_commands_mutating_run": False,
        "writes_performed": False,
    }
