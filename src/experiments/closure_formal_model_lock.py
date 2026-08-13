"""Validate the outcome-free H-E0-M formal-model-lock prerequisite.

This module deliberately publishes only infrastructure.  The sealed batch
runner is present, but its eleven scientific components are not.  Therefore
the current H slice can be audited and published while every P/R authority,
formal-lock materialization, E0-U, evaluation, and outcome operation remains
fail-closed.  A later reviewed H overlay must provide the missing components
and replace this source hash before P-E0-M can exist.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from src.experiments import (
    closure_locked_evaluation_input_manifest_dialect_patch as mid,
)
from src.experiments import run_closure_benchmark as runner


mcal = mid.mcal

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_R_MID_COMMIT = "53947df3b826ee10be8cf3b137bae913bc73d2bb"
PATCH_GATE = "E0-M"
H_GATE = "H-E0-M"
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

PATCH_PATHS = tuple(
    sorted(
        {
            DEFAULT_SCHEMA_PATH.as_posix(),
            DOCUMENTATION_PATH,
            PRECOMMIT_PATH,
            CORE_PATH,
            LOCKER_PATH.as_posix(),
            RUNNER_PATH.as_posix(),
            TEST_PATH,
        }
    )
)
PATCH_COMPONENT_GIT_MODES = {
    path: ("100755" if path == PRECOMMIT_PATH else "100644")
    for path in PATCH_PATHS
}
FORMAL_MODEL_LOCK_H_STAGED_SCOPE = {
    path: ("M" if path == PRECOMMIT_PATH else "A") for path in PATCH_PATHS
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

MODEL_POLICY_PATHS = (
    Path("configs/closure_v1/analysis_plan.yaml"),
    Path("configs/closure_v1/final_calibration_runtime.yaml"),
    Path("configs/closure_v1/model_benchmark.yaml"),
    Path("configs/closure_v1/model_lock_availability_policy.schema.json"),
    Path("configs/closure_v1/model_lock_availability_policy.yaml"),
)
R8_OUTPUT_CONTRACT = tuple(mid.R8_OUTPUT_CONTRACT)
LOCKED_INPUT_OUTPUT_CONTRACT = tuple(mid.R_OUTPUT_CONTRACT)
LOCKED_INPUT_OUTPUTS_SHA256 = mid.R_OUTPUTS_SHA256
EXPECTED_MISSING_COMPONENT_COUNT = 11

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
    if len(records) != 7:
        raise _error("H-E0-M component count is not exact7")
    return records


def _status_map(repo_root: Path) -> dict[str, str]:
    try:
        records = mcal._workspace_status_records(repo_root)
    except Exception as exc:
        raise _error("workspace status cannot be collected") from exc
    value = {path: code for code, path in records}
    if len(value) != len(records):
        raise _error("workspace status contains duplicate paths")
    return value


def _candidate_repository(
    *, repo_root: Path, verify_remote: bool
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
    if (
        head != BASE_R_MID_COMMIT
        or branch != "main"
        or main != BASE_R_MID_COMMIT
        or tracking != BASE_R_MID_COMMIT
        or tracking_head != BASE_R_MID_COMMIT
    ):
        raise _error("H-E0-M requires the exact published R-E0-MID base")
    remote = tracking
    if verify_remote:
        try:
            remote = mcal._live_remote_main_head(repo_root)
        except Exception as exc:
            raise _error("live remote main cannot be validated") from exc
        if remote != BASE_R_MID_COMMIT:
            raise _error("live remote main drifted from the R-E0-MID base")

    observed = _status_map(repo_root)
    if set(observed) != set(FORMAL_MODEL_LOCK_H_STAGED_SCOPE):
        raise _error("H-E0-M workspace is not the exact seven-path candidate")
    for path, state in FORMAL_MODEL_LOCK_H_STAGED_SCOPE.items():
        allowed = {" M", "M "} if state == "M" else {"??", "A "}
        if observed[path] not in allowed:
            raise _error(f"H-E0-M candidate status drifted: {path}")

    components = _component_records(repo_root)
    return (
        {
            "base_r_mid_commit": BASE_R_MID_COMMIT,
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
            "component_count": 7,
            "added_count": 6,
            "modified_count": 1,
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
    required_false = (
        "formal_model_lock_ready",
        "evaluator_available",
        "sealed_batch_execution_ready",
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
        or value.get("status") != "sealed_batch_runner_incomplete"
        or value.get("missing_component_count")
        != EXPECTED_MISSING_COMPONENT_COUNT
        or any(value.get(key) is not False for key in required_false)
        or value.get("sealed_batch_command") != runner.SEALED_BATCH_COMMAND
    ):
        raise _error("sealed batch runner incompleteness contract drifted")
    return _deep_copy(value)


def _require_absent_namespace(repo_root: Path) -> dict[str, Any]:
    present: list[str] = []
    for path in FORBIDDEN_CURRENT_NAMESPACE:
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
        "p_output_present_count": 0,
        "formal_output_present_count": 0,
        "outcome_access_log_state": "absent",
        "locker_guard_present": False,
        "formal_run_guard_present": False,
    }


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
    """Capture H7 plus immutable R8/R10/policy evidence without science."""

    root = _root(repo_root)
    components = _component_records(root)
    r8, locked, policy = _evidence_state(root)
    records: list[dict[str, Any]] = [*components, *r8, *locked, *policy]
    records.sort(key=lambda record: cast(str, record["path"]))
    if len(records) != 30 or len({record["path"] for record in records}) != 30:
        raise _error("physical prerequisite snapshot is not exact30")
    return tuple(records)


def preflight_formal_model_lock_schema(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    try:
        schema = mcal._load_json_object(DEFAULT_SCHEMA_PATH, repo_root=root)
        validator = getattr(mcal.closure_contract, "_assert_supported_json_schema")
        validator(schema)
        record = _read_record(
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
        "schemas": [record],
        "supported_subset_verified": True,
        "duplicate_keys_rejected": True,
    }


def collect_formal_model_lock_prelock_state(
    *, verify_remote: bool = False, repo_root: Path | None = None
) -> dict[str, Any]:
    """Collect the honest, outcome-free H prerequisite state."""

    root = _root(repo_root)
    repository, h_patch = _candidate_repository(
        repo_root=root, verify_remote=verify_remote
    )
    physical_before = _physical_snapshot(root)
    readiness = _runner_readiness(root)
    namespace = _require_absent_namespace(root)
    schema = preflight_formal_model_lock_schema(repo_root=root)
    physical_after = _physical_snapshot(root)
    if physical_before != physical_after:
        raise _error("physical prerequisite changed during prelock collection")
    r8 = [
        record
        for record in physical_before
        if record["path"] in {item["path"] for item in R8_OUTPUT_CONTRACT}
    ]
    locked = [
        record
        for record in physical_before
        if record["path"]
        in {item["path"] for item in LOCKED_INPUT_OUTPUT_CONTRACT}
    ]
    policy = [
        record
        for record in physical_before
        if record["path"] in {path.as_posix() for path in MODEL_POLICY_PATHS}
    ]
    return {
        "gate": PATCH_GATE,
        "status": "formal_model_lock_infrastructure_incomplete",
        "base_head": BASE_R_MID_COMMIT,
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
        "formal_model_lock_ready": False,
        "missing_component_count": EXPECTED_MISSING_COMPONENT_COUNT,
        "p_authority_generation_authorized": False,
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


def _blocked(operation: str) -> ClosureFormalModelLockError:
    return _error(
        f"{operation} is blocked: sealed batch infrastructure has exact11 "
        "missing scientific components; publish a reviewed superseding H overlay first"
    )


def build_formal_model_lock_authority_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any] | None = None,
    *,
    generated_at_utc: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del verification, generated_at_utc, repo_root
    if (
        not isinstance(prelock, Mapping)
        or prelock.get("status")
        != "formal_model_lock_infrastructure_incomplete"
        or prelock.get("missing_component_count")
        != EXPECTED_MISSING_COMPONENT_COUNT
        or prelock.get("p_authority_generation_authorized") is not False
    ):
        raise _error("prelock incompleteness boundary drifted")
    raise _blocked("P-E0-M authority generation")


def validate_formal_model_lock_authority_payload(
    payload: Mapping[str, Any],
    *,
    verify_remote: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del payload, verify_remote, repo_root
    raise _blocked("P-E0-M authority validation")


def publish_formal_model_lock_authority_bundle(
    payload: Mapping[str, Any], *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    del payload, repo_root
    raise _blocked("P-E0-M authority publication")


def validate_formal_model_lock_unpublished_authority_bundle(
    *,
    require_staged: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del require_staged, verify_remote, repo_root
    raise _blocked("P-E0-M unpublished authority loading")


def load_effective_formal_model_lock_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    del verify_remote, repo_root
    raise _blocked("P-E0-M effective authority loading")


def require_formal_model_lock_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    del verify_remote, repo_root
    raise _blocked("R-E0-M authority requirement")


def execute_formal_model_lock(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    del verify_remote, repo_root
    raise _blocked("R-E0-M formal lock execution")


def validate_formal_model_lock_bundle(
    *,
    require_staged: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del require_staged, verify_remote, repo_root
    raise _blocked("R-E0-M formal lock validation")
