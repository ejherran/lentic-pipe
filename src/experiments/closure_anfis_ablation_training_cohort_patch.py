"""Fail-closed E0-MU correction authority for A0/A1 training cohorts.

E0-MU is deliberately additive.  It keeps the immutable E0-MT scientific
runtime, reconstructs the published H/P-E0-MT authority, and authorizes only
the corrected unique-origin cohort implementation after a separate P-E0-MU
publication.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from src.experiments import (
    closure_contract,
    closure_anfis_ablation_training_development_patch as mt,
)
from src.experiments.closure_contract import ClosureContractError, validate_json_schema


PROJECT_ROOT = mt.PROJECT_ROOT
DEFAULT_RUNTIME_CONFIG = mt.DEFAULT_RUNTIME_CONFIG
DEFAULT_RUNTIME_PATH = DEFAULT_RUNTIME_CONFIG
DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/anfis_ablation_training_cohort_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/anfis_ablation_training_cohort_patch_lock.json"
)
DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "anfis_ablation_training_cohort_patch_lock_manifest.json"
)
DEFAULT_PATCH_MANIFEST_PATH = DEFAULT_PATCH_LOCK_MANIFEST_PATH
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_anfis_ablation_training_cohort_patch/lock_bundle.guard"
)

BASE_COMMIT = "1b68c24da4efe8fcf5eeb4b90ad0a99e95c96d93"
MT_H_HEAD = "f371786bc1e8d6c22b4d911145a57c623303b296"
MT_H_PARENT = "e22fd44d8a1e13c5587237d9f7a38856ae262864"
MT_P_HEAD = BASE_COMMIT

LOCKER_PATH = Path(
    "src/experiments/lock_closure_anfis_ablation_training_cohort_patch.py"
)
PATCH_COMPONENT_ROLES = {
    DEFAULT_PATCH_LOCK_SCHEMA.as_posix(): (
        "anfis_ablation_training_cohort_patch_lock_schema"
    ),
    "docs/closure_v1/E0_M_ANFIS_ABLATION_TRAINING_COHORT_PATCH_1.md": (
        "anfis_ablation_training_cohort_patch_protocol"
    ),
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py": (
        "corrected_anfis_ablation_model_bundle_auditor"
    ),
    "src/experiments/closure_anfis_ablation_training_cohort_patch.py": (
        "anfis_ablation_training_cohort_patch_validator"
    ),
    LOCKER_PATH.as_posix(): "anfis_ablation_training_cohort_patch_locker",
    "src/experiments/train_closure_anfis_ablation.py": (
        "corrected_anfis_ablation_trainer"
    ),
    "tests/test_audit_closure_anfis_ablation_model_bundle.py": (
        "corrected_anfis_ablation_model_bundle_auditor_tests"
    ),
    "tests/test_closure_anfis_ablation_training_cohort_patch.py": (
        "anfis_ablation_training_cohort_patch_tests"
    ),
    "tests/test_train_closure_anfis_ablation.py": (
        "corrected_anfis_ablation_trainer_tests"
    ),
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))

SUPERSEDED_MT_PATHS = (
    "src/experiments/audit_closure_anfis_ablation_model_bundle.py",
    "src/experiments/train_closure_anfis_ablation.py",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py",
    "tests/test_train_closure_anfis_ablation.py",
)
PRESERVED_MT_PATHS = tuple(
    path for path in mt.PATCH_PATHS if path not in SUPERSEDED_MT_PATHS
)
P_MT_COMPONENT_ROLES = {
    mt.DEFAULT_PATCH_LOCK_PATH.as_posix(): (
        "published_anfis_ablation_training_development_patch_lock"
    ),
    mt.DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(): (
        "published_anfis_ablation_training_development_patch_lock_manifest"
    ),
}
P_MT_PATHS = tuple(sorted(P_MT_COMPONENT_ROLES))

TYPE_CHECK_COMMAND = mt.TYPE_CHECK_COMMAND
FOCUSED_TEST_COMMAND = (
    ".venv/bin/python",
    "-m",
    "pytest",
    "-q",
    "tests/test_closure_anfis_ablation_training_cohort_patch.py",
    "tests/test_train_closure_anfis_ablation.py",
    "tests/test_audit_closure_anfis_ablation_model_bundle.py",
)
FOCUSED_TEST_COUNT = 103
POETRY_CHECK_COMMAND = mt.POETRY_CHECK_COMMAND
PUBLICATION_GUARD_COMMAND = mt.PUBLICATION_GUARD_COMMAND
DIFF_CHECK_COMMAND = mt.DIFF_CHECK_COMMAND

REGISTERED_SEEDS = mt.REGISTERED_SEEDS
ORDERED_SLOTS = mt.ORDERED_SLOTS
E0_M_PATHS = mt.E0_M_PATHS
OUTCOME_ACCESS_LOG = mt.OUTCOME_ACCESS_LOG
EMPTY_SHA256 = mt.EMPTY_SHA256
SHA1_RE = mt.SHA1_RE
SHA256_RE = mt.SHA256_RE
FOCUSED_SUMMARY_RE = re.compile(
    r"^(?P<count>[1-9][0-9]*) passed in (?P<seconds>[0-9]+\.[0-9]{2})s"
    r"(?: \((?P<clock>(?:[0-9]+ days?, )?[0-9]+:[0-9]{2}:[0-9]{2})\))?$"
)
FORBIDDEN_FOCUSED_SUMMARY_RE = re.compile(
    r"\b(?:warnings?|skipped|deselected|xfailed|xpassed|errors?|failed)\b",
    flags=re.IGNORECASE,
)
FOCUSED_PYTEST_ENVIRONMENT = {
    "PYTEST_ADDOPTS": "",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    "PYTEST_PLUGINS": "",
    "PY_COLORS": "0",
}

UNPUBLISHED_AUTHORIZATIONS = dict(mt.UNPUBLISHED_AUTHORIZATIONS)
LOCK_SEALS = {
    **mt.LOCK_SEALS,
    "runtime_contract_unchanged": True,
    "failed_check_only_not_consumed": True,
    "input_only_scaler_origin_count": 8352,
    "supervised_training_origin_count": 5932,
    "supervised_selection_origin_count": 658,
    "horizon_expansion_removed_before_model_fit": True,
    "all_reconstructed_git_modes_100644": True,
    "development_preflight_loader_run": True,
    "development_targets_through_2020_read_during_verification": True,
    "development_preprocessing_and_priors_reconstructed_during_verification": True,
    "trainer_entrypoint_run": False,
    "model_fit_or_optimization_run": False,
    "calibration_2021_targets_read_during_verification": False,
    "holdout_or_post_2021_targets_read_during_verification": False,
}
CORRECTION_EVIDENCE = {
    "invocation_mode": "--check-only",
    "p_mt_gate_status": "effective_preflight_passed",
    "pandas4warning_count": 2,
    "deprecated_operation": "set_index_verify_integrity",
    "terminal_error": "Raw observed count drifted for x_mean_TP_ugL",
    "trainer_cli_started": True,
    "check_only_preflight_started": True,
    "execute_one_shot_invoked": False,
    "fit_started": False,
    "guard_created": False,
    "writes_created": False,
    "dvc_commands_run": False,
    "future_outcomes_accessed": False,
    "development_targets_through_2020_read": True,
    "calibration_2021_targets_read": False,
    "holdout_or_post_2021_targets_read": False,
    "pseudo_training_rows": 17796,
    "pseudo_selection_rows": 1974,
    "observed_tp_value_count": 163839,
    "sealed_tp_value_count": 80271,
    "input_only_scaler_origin_count": 8352,
    "supervised_training_origin_count": 5932,
    "supervised_selection_origin_count": 658,
    "evidence_source": "derived_from_published_inputs_and_failed_check_only_facts",
    "stdout_persisted": False,
}
VERIFICATION_EXECUTION_BOUNDARIES = {
    "development_preflight_loader_run": True,
    "development_targets_through_2020_read_during_verification": True,
    "development_preprocessing_and_priors_reconstructed_during_verification": True,
    "trainer_entrypoint_run": False,
    "model_fit_or_optimization_run": False,
    "calibration_2021_targets_read_during_verification": False,
    "holdout_or_post_2021_targets_read_during_verification": False,
    "future_outcomes_accessed": False,
    "pytest_environment": dict(FOCUSED_PYTEST_ENVIRONMENT),
}


class AnfisAblationTrainingCohortPatchError(RuntimeError):
    """Raised when E0-MU authority, correction, or progression is not exact."""


def _translate(exc: BaseException) -> AnfisAblationTrainingCohortPatchError:
    return AnfisAblationTrainingCohortPatchError(str(exc).replace("E0-MT", "E0-MU"))


def _canonical_json(value: Any) -> bytes:
    return mt._canonical_json(value)


def _root(repo_root: Path | None = None) -> Path:
    return mt._root(repo_root)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _digest_records(records: Sequence[Mapping[str, Any]]) -> str:
    return _sha256_bytes(_canonical_json([dict(record) for record in records]))


def _read_regular_bytes(path: Path, *, repo_root: Path | None = None) -> bytes:
    try:
        return mt._read_regular_bytes(path, repo_root=repo_root)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _load_json(path: Path, *, repo_root: Path | None = None) -> dict[str, Any]:
    try:
        return mt._load_json(path, repo_root=repo_root)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _file_record(
    path: Path,
    *,
    role: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    try:
        return mt._file_record(path, role=role, repo_root=repo_root)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _git(repo_root: Path, *arguments: str) -> str:
    try:
        return mt._git(repo_root, *arguments)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _git_head(repo_root: Path, ref: str = "HEAD") -> str:
    try:
        return mt._git_head(repo_root, ref)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _git_parent(repo_root: Path, head: str) -> str:
    try:
        return mt._git_parent(repo_root, head)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _single_parent(repo_root: Path, commit: str, *, context: str) -> str:
    fields = _git(repo_root, "rev-list", "--parents", "-n", "1", commit).split()
    if len(fields) != 2 or fields[0] != commit:
        raise AnfisAblationTrainingCohortPatchError(
            f"{context} must be a direct non-merge commit"
        )
    return fields[1]


def _require_git_modes(
    repo_root: Path,
    commit: str,
    paths: Sequence[str],
    *,
    context: str,
) -> None:
    drifted = [
        path for path in paths if mt._git_mode(repo_root, commit, path) != "100644"
    ]
    if drifted:
        raise AnfisAblationTrainingCohortPatchError(
            f"{context} Git modes must all be 100644: {drifted}"
        )


def _git_scope(repo_root: Path, parent: str, head: str) -> dict[str, Any]:
    try:
        return mt._git_scope(repo_root, parent, head)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _git_blob_record(
    repo_root: Path,
    commit: str,
    path: str,
    *,
    role: str,
) -> dict[str, Any]:
    try:
        return mt._git_blob_record(repo_root, commit, path, role=role)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _live_remote_main_head(repo_root: Path) -> str:
    try:
        return mt._live_remote_main_head(repo_root)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _lexists(path: Path) -> bool:
    return mt._lexists(path)


validate_model_seed = mt.validate_model_seed
anfis_ablation_training_slot_paths = mt.anfis_ablation_training_slot_paths


def load_anfis_ablation_training_runtime(
    path: Path = DEFAULT_RUNTIME_CONFIG,
    *,
    verify_physical_pins: bool = True,
    allow_models_dvc_drift: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Load the immutable E0-MT runtime under the corrective E0-MU gate."""
    try:
        return mt.load_anfis_ablation_training_runtime(
            path,
            verify_physical_pins=verify_physical_pins,
            allow_models_dvc_drift=allow_models_dvc_drift,
            repo_root=repo_root,
        )
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _historical_mt_components(repo_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in SUPERSEDED_MT_PATHS:
        record = _git_blob_record(
            repo_root,
            MT_H_HEAD,
            path,
            role=f"superseded_mt_{mt.PATCH_COMPONENT_ROLES[path]}",
        )
        record.update(
            {
                "commit": MT_H_HEAD,
                "hash_source": "git_blob_at_commit",
                "current_bytes_required_to_match_historical": False,
            }
        )
        records.append(record)
    return sorted(records, key=lambda record: str(record["path"]))


def _preserved_mt_components(repo_root: Path) -> list[dict[str, Any]]:
    records = [
        _git_blob_record(
            repo_root,
            MT_H_HEAD,
            path,
            role=f"preserved_mt_{mt.PATCH_COMPONENT_ROLES[path]}",
        )
        for path in PRESERVED_MT_PATHS
    ]
    for record in records:
        current = _file_record(
            Path(str(record["path"])),
            role=str(record["role"]),
            repo_root=repo_root,
        )
        if current != record:
            raise AnfisAblationTrainingCohortPatchError(
                f"Preserved H-E0-MT component drifted: {record['path']}"
            )
    return sorted(records, key=lambda record: str(record["path"]))


def _p_mt_components(repo_root: Path) -> list[dict[str, Any]]:
    records = [
        _git_blob_record(
            repo_root,
            MT_P_HEAD,
            path,
            role=P_MT_COMPONENT_ROLES[path],
        )
        for path in P_MT_PATHS
    ]
    for record in records:
        current = _file_record(
            Path(str(record["path"])),
            role=str(record["role"]),
            repo_root=repo_root,
        )
        if current != record:
            raise AnfisAblationTrainingCohortPatchError(
                f"Published P-E0-MT component drifted: {record['path']}"
            )
    return sorted(records, key=lambda record: str(record["path"]))


def _h_mu_components(head: str, repo_root: Path) -> list[dict[str, Any]]:
    records = [
        _git_blob_record(
            repo_root,
            head,
            path,
            role=PATCH_COMPONENT_ROLES[path],
        )
        for path in PATCH_PATHS
    ]
    for record in records:
        current = _file_record(
            Path(str(record["path"])),
            role=str(record["role"]),
            repo_root=repo_root,
        )
        if current != record:
            raise AnfisAblationTrainingCohortPatchError(
                f"H-E0-MU component differs from Git blob: {record['path']}"
            )
    return sorted(records, key=lambda record: str(record["path"]))


def _validate_mt_topology(repo_root: Path) -> None:
    if (
        _single_parent(repo_root, MT_H_HEAD, context="H-E0-MT") != MT_H_PARENT
        or _git_scope(repo_root, MT_H_PARENT, MT_H_HEAD)
        != {
            "added": 10,
            "modified": 0,
            "deleted": 0,
            "paths": list(mt.PATCH_PATHS),
        }
        or _single_parent(repo_root, MT_P_HEAD, context="P-E0-MT") != MT_H_HEAD
        or _git_scope(repo_root, MT_H_HEAD, MT_P_HEAD)
        != {
            "added": 2,
            "modified": 0,
            "deleted": 0,
            "paths": list(P_MT_PATHS),
        }
    ):
        raise AnfisAblationTrainingCohortPatchError(
            "Published H/P-E0-MT topology drifted"
        )
    _require_git_modes(
        repo_root,
        MT_H_HEAD,
        mt.PATCH_PATHS,
        context="H-E0-MT",
    )
    _require_git_modes(
        repo_root,
        MT_P_HEAD,
        P_MT_PATHS,
        context="P-E0-MT",
    )


def _runtime_contract(
    *,
    repo_root: Path,
    allow_models_dvc_drift: bool = False,
) -> dict[str, Any]:
    runtime = load_anfis_ablation_training_runtime(
        repo_root=repo_root,
        allow_models_dvc_drift=allow_models_dvc_drift,
    )
    physical = [dict(record) for record in runtime["authority"]["physical_inputs"]]
    runtime_record = _file_record(
        DEFAULT_RUNTIME_CONFIG,
        role="anfis_ablation_training_runtime_contract",
        repo_root=repo_root,
    )
    return {
        "runtime": runtime_record,
        "runtime_sha256": runtime_record["sha256"],
        "physical_input_count": 47,
        "physical_inputs": physical,
        "physical_inputs_sha256": _digest_records(physical),
        "target_contract": dict(runtime["targets"]),
        "preprocessing": dict(runtime["preprocessing"]),
        "model": dict(runtime["model"]),
        "slots": dict(runtime["slots"]),
        "outputs": dict(runtime["outputs"]),
    }


def _companion_physical_inputs(
    *,
    h_components: Sequence[Mapping[str, Any]],
    preserved: Sequence[Mapping[str, Any]],
    p_components: Sequence[Mapping[str, Any]],
    runtime_contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    physical = runtime_contract.get("physical_inputs")
    if not isinstance(physical, list):
        raise AnfisAblationTrainingCohortPatchError(
            "Runtime physical-input records are absent"
        )
    inputs = [
        dict(record)
        for record in (*physical, *preserved, *h_components, *p_components)
    ]
    inputs.sort(key=lambda record: str(record.get("path")))
    paths = [str(record.get("path")) for record in inputs]
    if len(inputs) != 64 or len(set(paths)) != 64:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU companion must bind exactly 64 unique physical inputs"
        )
    return inputs


def preflight_anfis_ablation_training_cohort_patch_schema(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    schema = _load_json(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    encoded = _canonical_json(schema)
    forbidden = {"minimum", "maximum", "format", "minLength", "maxLength"}
    observed: set[str] = set()
    numeric_const_issues: list[str] = []

    def walk(value: Any, *, path: str = "$") -> None:
        if isinstance(value, Mapping):
            observed.update(str(key) for key in value)
            if "const" in value:
                constant = value["const"]
                if type(constant) in {int, float} and (
                    type(constant) is not int or value.get("type") != "integer"
                ):
                    numeric_const_issues.append(path)
            for key, child in value.items():
                walk(child, path=f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, path=f"{path}[{index}]")

    walk(schema)
    bad = sorted(forbidden.intersection(observed))
    supported_subset_validator = getattr(
        closure_contract,
        "_assert_supported_json_schema",
        None,
    )
    if not callable(supported_subset_validator):
        raise AnfisAblationTrainingCohortPatchError(
            "Closure JSON-schema definition validator is unavailable"
        )
    try:
        supported_subset_validator(schema)
    except ClosureContractError as exc:
        raise AnfisAblationTrainingCohortPatchError(str(exc)) from exc
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        raise AnfisAblationTrainingCohortPatchError("E0-MU schema properties absent")
    h_properties = cast(Mapping[str, Any], properties.get("h_patch", {})).get(
        "properties", {}
    )
    companion_properties = cast(
        Mapping[str, Any], properties.get("companion_contract", {})
    ).get("properties", {})
    if (
        bad
        or numeric_const_issues
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
        or cast(Mapping[str, Any], properties.get("gate", {})).get("const") != "E0-MU"
        or cast(Mapping[str, Any], h_properties).get("component_count", {}).get("const")
        != 9
        or cast(Mapping[str, Any], companion_properties)
        .get("physical_input_count", {})
        .get("const")
        != 64
        or cast(Mapping[str, Any], companion_properties)
        .get("historical_input_count", {})
        .get("const")
        != 4
    ):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU schema preflight drifted: "
            f"unsupported={bad}, numeric_consts={numeric_const_issues}"
        )
    return {
        "status": "schema_preflight_passed",
        "schema": _file_record(
            DEFAULT_PATCH_LOCK_SCHEMA,
            role="anfis_ablation_training_cohort_patch_lock_schema",
            repo_root=root,
        ),
        "canonical_schema_sha256": _sha256_bytes(encoded),
        "supported_subset_verified": True,
        "unsupported_semantic_keywords": [],
    }


def _training_namespace_absence(repo_root: Path) -> dict[str, Any]:
    finals = mt._all_slot_paths()
    temporaries = tuple(mt._temporary_path(path) for path in finals)
    guards = tuple(mt._guard_path(model, seed) for model, seed in ORDERED_SLOTS)
    pointers = tuple(mt._pointer_path(model, seed) for model, seed in ORDERED_SLOTS)
    pointer_temporaries = tuple(
        Path(f"{pointer.as_posix()}.tmp") for pointer in pointers
    )
    state = {
        "completed_prefix_count": 0,
        "final_paths_present": [
            path.as_posix() for path in finals if _lexists(repo_root / path)
        ],
        "temporary_paths_present": [
            path.as_posix() for path in temporaries if _lexists(repo_root / path)
        ],
        "guard_paths_present": [
            path.as_posix() for path in guards if _lexists(repo_root / path)
        ],
        "prediction_pointers_present": [
            path.as_posix() for path in pointers if _lexists(repo_root / path)
        ],
        "prediction_pointer_temporaries_present": [
            path.as_posix()
            for path in pointer_temporaries
            if _lexists(repo_root / path)
        ],
        "output_namespace_sha256": _sha256_bytes(
            _canonical_json(
                [
                    *(path.as_posix() for path in finals),
                    *(path.as_posix() for path in temporaries),
                    *(path.as_posix() for path in guards),
                    *(path.as_posix() for path in pointers),
                    *(path.as_posix() for path in pointer_temporaries),
                ]
            )
        ),
    }
    occupied = [
        path
        for key, values in state.items()
        if key.endswith("_present") and isinstance(values, list)
        for path in values
    ]
    if occupied:
        raise AnfisAblationTrainingCohortPatchError(
            f"E0-MU prelock training namespace is not empty: {occupied}"
        )
    return state


def collect_anfis_ablation_training_cohort_patch_prelock_state(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    preflight_anfis_ablation_training_cohort_patch_schema(repo_root=root)
    runtime_contract = _runtime_contract(repo_root=root)
    _validate_mt_topology(root)
    head = _git_head(root)
    parent = _single_parent(root, head, context="H-E0-MU")
    expected_scope = {
        "added": 5,
        "modified": 4,
        "deleted": 0,
        "paths": list(PATCH_PATHS),
    }
    if parent != BASE_COMMIT or _git_scope(root, parent, head) != expected_scope:
        raise AnfisAblationTrainingCohortPatchError(
            "H-E0-MU must be the exact 4M+5A child of P-E0-MT"
        )
    _require_git_modes(root, head, PATCH_PATHS, context="H-E0-MU")
    status_lines = [
        line
        for line in _git(root, "status", "--porcelain", "--untracked-files=all").splitlines()
        if line
    ]
    if status_lines:
        raise AnfisAblationTrainingCohortPatchError(
            f"E0-MU prelock requires a clean worktree: {status_lines}"
        )
    branch = _git(root, "branch", "--show-current").strip()
    tracking = _git_head(root, "origin/main")
    remote = _live_remote_main_head(root) if verify_remote else tracking
    if branch != "main" or tracking != head or remote != head:
        raise AnfisAblationTrainingCohortPatchError(
            "H-E0-MU refs are not aligned with live remote main"
        )
    h_components = _h_mu_components(head, root)
    preserved = _preserved_mt_components(root)
    historical = _historical_mt_components(root)
    p_components = _p_mt_components(root)
    physical_inputs = _companion_physical_inputs(
        h_components=h_components,
        preserved=preserved,
        p_components=p_components,
        runtime_contract=runtime_contract,
    )
    training_namespace = _training_namespace_absence(root)
    control = {
        "mu_lock_absent": not _lexists(root / DEFAULT_PATCH_LOCK_PATH),
        "mu_companion_absent": not _lexists(root / DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        "mu_lock_temp_absent": not _lexists(
            root / mt._temporary_path(DEFAULT_PATCH_LOCK_PATH)
        ),
        "mu_companion_temp_absent": not _lexists(
            root / mt._temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH)
        ),
        "mu_locker_guard_absent": not _lexists(root / LOCKER_GUARD_PATH),
        "p_mt_lock_present": _lexists(root / mt.DEFAULT_PATCH_LOCK_PATH),
        "p_mt_companion_present": _lexists(root / mt.DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        "p_mt_lock_temp_absent": not _lexists(
            root / mt._temporary_path(mt.DEFAULT_PATCH_LOCK_PATH)
        ),
        "p_mt_companion_temp_absent": not _lexists(
            root / mt._temporary_path(mt.DEFAULT_PATCH_LOCK_MANIFEST_PATH)
        ),
        "p_mt_locker_guard_absent": not _lexists(root / mt.LOCKER_GUARD_PATH),
    }
    if not all(control.values()):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU/P-E0-MT control namespace drifted"
        )
    prohibited = {
        "e0_m_paths_absent": not any(_lexists(root / path) for path in E0_M_PATHS),
        "outcome_access_log_absent": not _lexists(root / OUTCOME_ACCESS_LOG),
    }
    if not all(prohibited.values()):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-M or outcome namespace is present"
        )
    return {
        "repository": {
            "branch": branch,
            "head": head,
            "parent": parent,
            "tracking_head": tracking,
            "remote_head": remote,
            "remote_verification_mode": (
                "live_remote_main_verified" if verify_remote else "tracking_ref_only"
            ),
            "worktree_scope": "exact_h_patch_components_only",
        },
        "h_patch": {
            "base_commit": BASE_COMMIT,
            "head": head,
            "parent": parent,
            "component_count": 9,
            "components": h_components,
            "components_sha256": _digest_records(h_components),
            "components_git_mode": "100644",
            "scope": {"added": 5, "modified": 4, "deleted": 0},
        },
        "mt_authority": {
            "h_head": MT_H_HEAD,
            "h_parent": MT_H_PARENT,
            "h_scope": {"added": 10, "modified": 0, "deleted": 0},
            "p_head": MT_P_HEAD,
            "p_parent": MT_H_HEAD,
            "p_scope": {"added": 2, "modified": 0, "deleted": 0},
            "preserved_component_count": 6,
            "preserved_components": preserved,
            "preserved_components_sha256": _digest_records(preserved),
            "historical_component_count": 4,
            "historical_components": historical,
            "historical_components_sha256": _digest_records(historical),
            "p_component_count": 2,
            "p_components": p_components,
            "p_components_sha256": _digest_records(p_components),
            "h_components_git_mode": "100644",
            "p_components_git_mode": "100644",
        },
        "runtime_contract": runtime_contract,
        "correction_evidence": dict(CORRECTION_EVIDENCE),
        "companion_contract": {
            "physical_input_count": 64,
            "historical_input_count": 4,
            "output_count": 1,
            "script_path": LOCKER_PATH.as_posix(),
            "physical_inputs_sha256": _digest_records(physical_inputs),
            "historical_inputs_sha256": _digest_records(historical),
            "manifest_written_last": True,
        },
        "prelock": {
            **training_namespace,
            "control_paths": control,
            "prohibited_namespaces": prohibited,
        },
    }


def build_anfis_ablation_training_cohort_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any],
    *,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    required = {
        "repository",
        "h_patch",
        "mt_authority",
        "runtime_contract",
        "correction_evidence",
        "companion_contract",
        "prelock",
    }
    if set(prelock) != required:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU prelock bundle dialect drifted"
        )
    timestamp = created_at_utc or datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": "closure_anfis_ablation_training_cohort_patch_lock_v1",
        "status": "locked_unpublished",
        "gate": "E0-MU",
        "created_at_utc": timestamp,
        "repository": dict(prelock["repository"]),
        "h_patch": dict(prelock["h_patch"]),
        "mt_authority": dict(prelock["mt_authority"]),
        "runtime_contract": dict(prelock["runtime_contract"]),
        "correction_evidence": dict(prelock["correction_evidence"]),
        "companion_contract": dict(prelock["companion_contract"]),
        "prelock": dict(prelock["prelock"]),
        "verification": dict(verification),
        "authorizations": dict(UNPUBLISHED_AUTHORIZATIONS),
        "seals": dict(LOCK_SEALS),
    }


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU lock timestamp must be a string"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU lock timestamp is malformed"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU lock timestamp must include a timezone"
        )


def _validate_role_record(value: Any) -> dict[str, Any]:
    try:
        return mt._validate_file_record(value)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _validate_command_evidence(
    value: Any,
    *,
    expected_command: Sequence[str],
    context: str,
    exact_stdout: str | None = None,
) -> None:
    keys = {
        "command",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise AnfisAblationTrainingCohortPatchError(
            f"E0-MU {context} evidence dialect drifted"
        )
    if (
        value.get("command") != list(expected_command)
        or type(value.get("returncode")) is not int
        or value.get("returncode") != 0
    ):
        raise AnfisAblationTrainingCohortPatchError(
            f"E0-MU {context} command/result drifted"
        )
    if any(
        not isinstance(value.get(key), str)
        or SHA256_RE.fullmatch(str(value[key])) is None
        for key in ("stdout_sha256", "stderr_sha256")
    ):
        raise AnfisAblationTrainingCohortPatchError(
            f"E0-MU {context} digest drifted"
        )
    if any(
        type(value.get(key)) is not int
        or int(value[key]) < 0
        for key in ("stdout_line_count", "stderr_line_count")
    ):
        raise AnfisAblationTrainingCohortPatchError(
            f"E0-MU {context} line-count drifted"
        )
    if value.get("stderr_sha256") != EMPTY_SHA256 or value.get("stderr_line_count") != 0:
        raise AnfisAblationTrainingCohortPatchError(
            f"E0-MU {context} stderr evidence drifted"
        )
    if exact_stdout is not None and (
        value.get("stdout_sha256") != _sha256_bytes(exact_stdout.encode("utf-8"))
        or value.get("stdout_line_count") != len(exact_stdout.splitlines())
    ):
        raise AnfisAblationTrainingCohortPatchError(
            f"E0-MU {context} stdout evidence drifted"
        )


def _command_evidence(
    command: Sequence[str], stdout: str, stderr: str
) -> dict[str, Any]:
    return {
        "command": list(command),
        "returncode": 0,
        "stdout_sha256": _sha256_bytes(stdout.encode("utf-8")),
        "stderr_sha256": _sha256_bytes(stderr.encode("utf-8")),
        "stdout_line_count": len(stdout.splitlines()),
        "stderr_line_count": len(stderr.splitlines()),
    }


def _run_command(
    command: Sequence[str],
    *,
    repo_root: Path,
    sanitize_pytest_environment: bool = False,
) -> tuple[dict[str, Any], str, str]:
    environment = os.environ.copy()
    if sanitize_pytest_environment:
        environment.update(FOCUSED_PYTEST_ENVIRONMENT)
    result = subprocess.run(
        list(command),
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    if result.returncode != 0:
        raise AnfisAblationTrainingCohortPatchError(
            f"Verification command failed ({result.returncode}): "
            f"{' '.join(command)}\n{result.stdout}\n{result.stderr}"
        )
    return (
        _command_evidence(command, result.stdout, result.stderr),
        result.stdout,
        result.stderr,
    )


def _parse_focused_summary(stdout: str, stderr: str) -> dict[str, int]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    matches = [line for line in lines if FOCUSED_SUMMARY_RE.fullmatch(line)]
    match = FOCUSED_SUMMARY_RE.fullmatch(matches[0]) if len(matches) == 1 else None
    if (
        stderr.strip()
        or not lines
        or len(matches) != 1
        or matches[0] != lines[-1]
        or FORBIDDEN_FOCUSED_SUMMARY_RE.search(stdout + "\n" + stderr) is not None
        or match is None
        or int(match.group("count")) != FOCUSED_TEST_COUNT
    ):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU focused pytest summary is not one clean exact result"
        )
    return {
        "test_count": FOCUSED_TEST_COUNT,
        "skipped_count": 0,
        "deselected_count": 0,
    }


def run_anfis_ablation_training_cohort_patch_verification(
    *,
    expected_schema_preflight: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Run the exact gate checks once and retain the parsed pytest bytes."""
    root = _root(repo_root)
    schema_preflight = preflight_anfis_ablation_training_cohort_patch_schema(
        repo_root=root
    )
    if (
        expected_schema_preflight is not None
        and dict(expected_schema_preflight) != schema_preflight
    ):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU schema changed before verification"
        )
    full_type_check, stdout, stderr = _run_command(TYPE_CHECK_COMMAND, repo_root=root)
    if stdout != "All checks passed!\n" or stderr:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU full type check output drifted"
        )
    focused_tests, stdout, stderr = _run_command(
        FOCUSED_TEST_COMMAND,
        repo_root=root,
        sanitize_pytest_environment=True,
    )
    focused_tests.update(_parse_focused_summary(stdout, stderr))
    focused_tests["stdout_text"] = stdout
    poetry_check, stdout, stderr = _run_command(POETRY_CHECK_COMMAND, repo_root=root)
    if stdout != "All set!\n" or stderr:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU poetry-check output drifted"
        )
    publication_guard, stdout, stderr = _run_command(
        PUBLICATION_GUARD_COMMAND,
        repo_root=root,
    )
    if stdout != (
        "Checking tracked files before publication...\n"
        "OK: tracked files look publication-ready.\n"
    ) or stderr:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU publication-guard output drifted"
        )
    git_diff_check, stdout, stderr = _run_command(DIFF_CHECK_COMMAND, repo_root=root)
    if stdout or stderr:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU git diff-check output drifted"
        )
    return {
        "schema_preflight": schema_preflight,
        "full_type_check": full_type_check,
        "focused_tests": focused_tests,
        "poetry_check": poetry_check,
        "publication_guard": publication_guard,
        "git_diff_check": git_diff_check,
        "execution_boundaries": dict(VERIFICATION_EXECUTION_BOUNDARIES),
    }


def _validate_verification(value: Any, *, repo_root: Path) -> None:
    keys = {
        "schema_preflight",
        "full_type_check",
        "focused_tests",
        "poetry_check",
        "publication_guard",
        "git_diff_check",
        "execution_boundaries",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU verification bundle drifted"
        )
    if value.get("schema_preflight") != preflight_anfis_ablation_training_cohort_patch_schema(
        repo_root=repo_root
    ):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU schema-preflight evidence drifted"
        )
    if value.get("execution_boundaries") != VERIFICATION_EXECUTION_BOUNDARIES:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU verification execution boundaries drifted"
        )
    _validate_command_evidence(
        value.get("full_type_check"),
        expected_command=TYPE_CHECK_COMMAND,
        context="full type check",
        exact_stdout="All checks passed!\n",
    )
    _validate_command_evidence(
        value.get("poetry_check"),
        expected_command=POETRY_CHECK_COMMAND,
        context="poetry check",
        exact_stdout="All set!\n",
    )
    _validate_command_evidence(
        value.get("publication_guard"),
        expected_command=PUBLICATION_GUARD_COMMAND,
        context="publication guard",
        exact_stdout=(
            "Checking tracked files before publication...\n"
            "OK: tracked files look publication-ready.\n"
        ),
    )
    _validate_command_evidence(
        value.get("git_diff_check"),
        expected_command=DIFF_CHECK_COMMAND,
        context="git diff check",
        exact_stdout="",
    )
    focused = value.get("focused_tests")
    if not isinstance(focused, Mapping):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU focused-test evidence is absent"
        )
    common_keys = (
        "command",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
    )
    common = {key: focused.get(key) for key in common_keys}
    _validate_command_evidence(
        common,
        expected_command=FOCUSED_TEST_COMMAND,
        context="focused tests",
    )
    if set(focused) != {
        *common_keys,
        "stdout_text",
        "test_count",
        "skipped_count",
        "deselected_count",
    } or any(
        type(focused.get(key)) is not int or focused.get(key) != expected
        for key, expected in (
            ("test_count", FOCUSED_TEST_COUNT),
            ("skipped_count", 0),
            ("deselected_count", 0),
        )
    ):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU focused-test summary drifted"
        )
    stdout_text = focused.get("stdout_text")
    if not isinstance(stdout_text, str):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU focused-test stdout text is absent"
        )
    if (
        focused.get("stdout_sha256")
        != _sha256_bytes(stdout_text.encode("utf-8"))
        or focused.get("stdout_line_count") != len(stdout_text.splitlines())
    ):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU focused-test stdout binding drifted"
        )
    if _parse_focused_summary(stdout_text, "") != {
        "test_count": FOCUSED_TEST_COUNT,
        "skipped_count": 0,
        "deselected_count": 0,
    }:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU focused pytest parsed summary drifted"
        )


def _expected_prelock() -> dict[str, Any]:
    finals = mt._all_slot_paths()
    temporaries = tuple(mt._temporary_path(path) for path in finals)
    guards = tuple(mt._guard_path(model, seed) for model, seed in ORDERED_SLOTS)
    pointers = tuple(mt._pointer_path(model, seed) for model, seed in ORDERED_SLOTS)
    pointer_temporaries = tuple(
        Path(f"{pointer.as_posix()}.tmp") for pointer in pointers
    )
    namespace = [
        *(path.as_posix() for path in finals),
        *(path.as_posix() for path in temporaries),
        *(path.as_posix() for path in guards),
        *(path.as_posix() for path in pointers),
        *(path.as_posix() for path in pointer_temporaries),
    ]
    return {
        "completed_prefix_count": 0,
        "final_paths_present": [],
        "temporary_paths_present": [],
        "guard_paths_present": [],
        "prediction_pointers_present": [],
        "prediction_pointer_temporaries_present": [],
        "output_namespace_sha256": _sha256_bytes(_canonical_json(namespace)),
        "control_paths": {
            "mu_lock_absent": True,
            "mu_companion_absent": True,
            "mu_lock_temp_absent": True,
            "mu_companion_temp_absent": True,
            "mu_locker_guard_absent": True,
            "p_mt_lock_present": True,
            "p_mt_companion_present": True,
            "p_mt_lock_temp_absent": True,
            "p_mt_companion_temp_absent": True,
            "p_mt_locker_guard_absent": True,
        },
        "prohibited_namespaces": {
            "e0_m_paths_absent": True,
            "outcome_access_log_absent": True,
        },
    }


def _expected_mt_authority(repo_root: Path) -> dict[str, Any]:
    _validate_mt_topology(repo_root)
    preserved = _preserved_mt_components(repo_root)
    historical = _historical_mt_components(repo_root)
    p_components = _p_mt_components(repo_root)
    return {
        "h_head": MT_H_HEAD,
        "h_parent": MT_H_PARENT,
        "h_scope": {"added": 10, "modified": 0, "deleted": 0},
        "p_head": MT_P_HEAD,
        "p_parent": MT_H_HEAD,
        "p_scope": {"added": 2, "modified": 0, "deleted": 0},
        "preserved_component_count": 6,
        "preserved_components": preserved,
        "preserved_components_sha256": _digest_records(preserved),
        "historical_component_count": 4,
        "historical_components": historical,
        "historical_components_sha256": _digest_records(historical),
        "p_component_count": 2,
        "p_components": p_components,
        "p_components_sha256": _digest_records(p_components),
        "h_components_git_mode": "100644",
        "p_components_git_mode": "100644",
    }


def validate_anfis_ablation_training_cohort_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    allow_models_dvc_drift: bool = False,
) -> None:
    root = _root(repo_root)
    schema = _load_json(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    try:
        validate_json_schema(payload, schema)
    except ClosureContractError as exc:
        raise AnfisAblationTrainingCohortPatchError(str(exc)) from exc
    _validate_timestamp(payload.get("created_at_utc"))
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU unpublished authorizations drifted"
        )
    if payload.get("seals") != LOCK_SEALS:
        raise AnfisAblationTrainingCohortPatchError("E0-MU seals drifted")
    if payload.get("correction_evidence") != CORRECTION_EVIDENCE:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU correction evidence drifted"
        )
    repository = payload.get("repository")
    repository_keys = {
        "branch",
        "head",
        "parent",
        "tracking_head",
        "remote_head",
        "remote_verification_mode",
        "worktree_scope",
    }
    if not isinstance(repository, Mapping) or set(repository) != repository_keys:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU repository dialect drifted"
        )
    h_head = repository.get("head")
    expected_scope = {
        "added": 5,
        "modified": 4,
        "deleted": 0,
        "paths": list(PATCH_PATHS),
    }
    if (
        repository.get("branch") != "main"
        or not isinstance(h_head, str)
        or SHA1_RE.fullmatch(h_head) is None
        or repository.get("parent") != BASE_COMMIT
        or repository.get("tracking_head") != h_head
        or repository.get("remote_head") != h_head
        or repository.get("remote_verification_mode")
        != "live_remote_main_verified"
        or repository.get("worktree_scope") != "exact_h_patch_components_only"
        or _single_parent(root, h_head, context="H-E0-MU") != BASE_COMMIT
        or _git_scope(root, BASE_COMMIT, h_head) != expected_scope
    ):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU repository/H topology drifted"
        )
    _require_git_modes(root, h_head, PATCH_PATHS, context="H-E0-MU")
    h_components = _h_mu_components(h_head, root)
    expected_h = {
        "base_commit": BASE_COMMIT,
        "head": h_head,
        "parent": BASE_COMMIT,
        "component_count": 9,
        "components": h_components,
        "components_sha256": _digest_records(h_components),
        "components_git_mode": "100644",
        "scope": {"added": 5, "modified": 4, "deleted": 0},
    }
    if payload.get("h_patch") != expected_h:
        raise AnfisAblationTrainingCohortPatchError("E0-MU H binding drifted")
    mt_authority = _expected_mt_authority(root)
    if payload.get("mt_authority") != mt_authority:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU H/P-E0-MT reconstruction drifted"
        )
    runtime_contract = _runtime_contract(
        repo_root=root,
        allow_models_dvc_drift=allow_models_dvc_drift,
    )
    if payload.get("runtime_contract") != runtime_contract:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU immutable runtime binding drifted"
        )
    physical_inputs = _companion_physical_inputs(
        h_components=h_components,
        preserved=cast(list[dict[str, Any]], mt_authority["preserved_components"]),
        p_components=cast(list[dict[str, Any]], mt_authority["p_components"]),
        runtime_contract=runtime_contract,
    )
    historical = cast(list[dict[str, Any]], mt_authority["historical_components"])
    expected_companion_contract = {
        "physical_input_count": 64,
        "historical_input_count": 4,
        "output_count": 1,
        "script_path": LOCKER_PATH.as_posix(),
        "physical_inputs_sha256": _digest_records(physical_inputs),
        "historical_inputs_sha256": _digest_records(historical),
        "manifest_written_last": True,
    }
    if payload.get("companion_contract") != expected_companion_contract:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU companion contract drifted"
        )
    if payload.get("prelock") != _expected_prelock():
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU complete prelock binding drifted"
        )
    _validate_verification(payload.get("verification"), repo_root=root)


def _expected_companion(
    payload: Mapping[str, Any],
    lock_record: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root
    h_patch = payload.get("h_patch")
    mt_authority = payload.get("mt_authority")
    runtime_contract = payload.get("runtime_contract")
    if not all(
        isinstance(section, Mapping)
        for section in (h_patch, mt_authority, runtime_contract)
    ):
        raise AnfisAblationTrainingCohortPatchError(
            "Cannot construct E0-MU companion sections"
        )
    h_patch = cast(Mapping[str, Any], h_patch)
    mt_authority = cast(Mapping[str, Any], mt_authority)
    runtime_contract = cast(Mapping[str, Any], runtime_contract)
    h_components = h_patch.get("components")
    preserved = mt_authority.get("preserved_components")
    historical = mt_authority.get("historical_components")
    p_components = mt_authority.get("p_components")
    if not all(
        isinstance(records, list)
        for records in (h_components, preserved, historical, p_components)
    ):
        raise AnfisAblationTrainingCohortPatchError(
            "Cannot construct E0-MU companion records"
        )
    h_components = cast(list[dict[str, Any]], h_components)
    preserved = cast(list[dict[str, Any]], preserved)
    historical = cast(list[dict[str, Any]], historical)
    p_components = cast(list[dict[str, Any]], p_components)
    inputs = _companion_physical_inputs(
        h_components=h_components,
        preserved=preserved,
        p_components=p_components,
        runtime_contract=runtime_contract,
    )
    historical_inputs = [dict(record) for record in historical]
    historical_inputs.sort(key=lambda record: str(record.get("path")))
    if (
        len(historical_inputs) != 4
        or len({str(record.get("path")) for record in historical_inputs}) != 4
    ):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU companion must bind exactly four historical inputs"
        )
    script = next(
        (dict(record) for record in h_components if record.get("path") == LOCKER_PATH.as_posix()),
        None,
    )
    if script is None:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU companion generating script is absent"
        )
    output = _validate_role_record(lock_record)
    if (
        output.get("path") != DEFAULT_PATCH_LOCK_PATH.as_posix()
        or output.get("role") != "anfis_ablation_training_cohort_patch_lock"
    ):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU companion lock output record drifted"
        )
    return {
        "manifest_version": (
            "closure_anfis_ablation_training_cohort_patch_lock_manifest_v1"
        ),
        "gate": "E0-MU",
        "status": "completed",
        "script": script,
        "inputs": inputs,
        "historical_inputs": historical_inputs,
        "historical_inputs_compared_to_current_paths": False,
        "outputs": [output],
        "physical_inputs_only": True,
        "manifest_written_last": True,
        "dvc_commands_run": False,
        "network_commands_run": True,
        "development_preflight_loader_run": True,
        "development_targets_through_2020_read_during_verification": True,
        "development_preprocessing_and_priors_reconstructed_during_verification": True,
        "trainer_entrypoint_run": False,
        "auditor_entrypoint_run": False,
        "model_fit_or_optimization_run": False,
        "calibration_2021_targets_read_during_verification": False,
        "holdout_or_post_2021_targets_read_during_verification": False,
        "future_outcomes_accessed": False,
        "completion_marker_written_last": True,
    }


def execute_and_publish_anfis_ablation_training_cohort_lock_bundle(
    *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Collect, verify exactly once, rebuild, and atomically publish P-E0-MU."""
    root = _root(repo_root)
    schema_preflight = preflight_anfis_ablation_training_cohort_patch_schema(
        repo_root=root
    )
    before = collect_anfis_ablation_training_cohort_patch_prelock_state(
        verify_remote=True,
        repo_root=root,
    )
    verification = run_anfis_ablation_training_cohort_patch_verification(
        expected_schema_preflight=schema_preflight,
        repo_root=root,
    )
    after = collect_anfis_ablation_training_cohort_patch_prelock_state(
        verify_remote=True,
        repo_root=root,
    )
    if before != after:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU prelock state changed during verification"
        )
    payload = build_anfis_ablation_training_cohort_patch_lock_payload(
        before,
        verification,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    validate_anfis_ablation_training_cohort_patch_lock_payload(
        payload,
        repo_root=root,
    )
    # This importable I/O boundary must not trust a previously collected or
    # caller-forged prelock snapshot.  Reconstruct all physical/Git/remote
    # facts immediately before acquiring the publication guard.
    live_prelock = collect_anfis_ablation_training_cohort_patch_prelock_state(
        verify_remote=True,
        repo_root=root,
    )
    for section in (
        "repository",
        "h_patch",
        "mt_authority",
        "runtime_contract",
        "correction_evidence",
        "companion_contract",
        "prelock",
    ):
        if payload.get(section) != live_prelock.get(section):
            raise AnfisAblationTrainingCohortPatchError(
                f"E0-MU live prelock state drifted: {section}"
            )
    controlled = (
        DEFAULT_PATCH_LOCK_PATH,
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        mt._temporary_path(DEFAULT_PATCH_LOCK_PATH),
        mt._temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        LOCKER_GUARD_PATH,
    )
    occupied = [path.as_posix() for path in controlled if _lexists(root / path)]
    if occupied:
        raise AnfisAblationTrainingCohortPatchError(
            f"E0-MU lock namespace is occupied: {occupied}"
        )
    guard: mt._OwnedGuard | None = None
    published: list[mt._OwnedOutput] = []
    committed = False
    try:
        guard = mt._acquire_publication_guard(
            LOCKER_GUARD_PATH,
            b"E0-MU lock bundle publication in progress\n",
            repo_root=root,
        )
        lock_output = mt._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_PATH,
            _canonical_json(dict(payload)),
            repo_root=root,
        )
        published.append(lock_output)
        lock_record = _file_record(
            DEFAULT_PATCH_LOCK_PATH,
            role="anfis_ablation_training_cohort_patch_lock",
            repo_root=root,
        )
        companion = _expected_companion(payload, lock_record, repo_root=root)
        companion_output = mt._publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            _canonical_json(companion),
            repo_root=root,
        )
        published.append(companion_output)
        if _load_json(DEFAULT_PATCH_LOCK_PATH, repo_root=root) != dict(payload):
            raise AnfisAblationTrainingCohortPatchError(
                "Published E0-MU lock differs from its payload"
            )
        if _load_json(DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root) != companion:
            raise AnfisAblationTrainingCohortPatchError(
                "Published E0-MU companion differs from its payload"
            )
        for output in published:
            mt._validate_owned_output(output)
        mt._release_publication_guard(guard)
        guard = None
        for output in published:
            mt._validate_owned_output(output)
        committed = True
        return dict(payload), companion
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        for output in reversed(published):
            mt._rollback_owned_output(output)
        raise _translate(exc) from exc
    except BaseException:
        for output in reversed(published):
            mt._rollback_owned_output(output)
        raise
    finally:
        if guard is not None:
            mt._release_publication_guard(guard, tolerate_foreign=True)
        if committed:
            for output in published:
                mt._close_owned_output(output)


def publish_anfis_ablation_training_cohort_lock_bundle(
    *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Public safe publisher; caller-supplied verification is never accepted."""
    return execute_and_publish_anfis_ablation_training_cohort_lock_bundle(
        repo_root=repo_root
    )


def _git_mode(repo_root: Path, commit: str, path: str) -> str:
    try:
        return mt._git_mode(repo_root, commit, path)
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc


def _validate_p_publication(
    payload: Mapping[str, Any], *, repo_root: Path
) -> dict[str, str]:
    repository = payload.get("repository")
    if not isinstance(repository, Mapping):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU H repository binding is absent"
        )
    h_head = repository.get("head")
    if not isinstance(h_head, str):
        raise AnfisAblationTrainingCohortPatchError("E0-MU H head is absent")
    head = _git_head(repo_root)
    tracking = _git_head(repo_root, "origin/main")
    remote = _live_remote_main_head(repo_root)
    if (
        _git(repo_root, "branch", "--show-current").strip() != "main"
        or _single_parent(repo_root, head, context="P-E0-MU") != h_head
        or tracking != head
        or remote != head
    ):
        raise AnfisAblationTrainingCohortPatchError(
            "Published P-E0-MU topology/refs drifted"
        )
    expected_paths = sorted(
        (
            DEFAULT_PATCH_LOCK_PATH.as_posix(),
            DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(),
        )
    )
    if _git_scope(repo_root, h_head, head) != {
        "added": 2,
        "modified": 0,
        "deleted": 0,
        "paths": expected_paths,
    }:
        raise AnfisAblationTrainingCohortPatchError(
            "P-E0-MU must add exactly lock plus companion"
        )
    for path in expected_paths:
        if _git_mode(repo_root, head, path) != "100644":
            raise AnfisAblationTrainingCohortPatchError(
                f"P-E0-MU Git mode drifted: {path}"
            )
    return {"h_patch_head": h_head, "p_patch_head": head, "remote_head": remote}


def _static_effective_authority(
    payload: Mapping[str, Any],
    *,
    publication: Mapping[str, str],
    lock: Mapping[str, Any],
    companion: Mapping[str, Any],
) -> dict[str, Any]:
    runtime_contract = cast(Mapping[str, Any], payload["runtime_contract"])
    h_patch = cast(Mapping[str, Any], payload["h_patch"])
    return {
        "gate": "E0-MU",
        "status": "effective_preflight_passed",
        "h_patch_head": publication["h_patch_head"],
        "p_patch_head": publication["p_patch_head"],
        "runtime": dict(cast(Mapping[str, Any], runtime_contract["runtime"])),
        "lock": dict(lock),
        "companion": dict(companion),
        "h_components_sha256": h_patch["components_sha256"],
        "physical_inputs_sha256": runtime_contract["physical_inputs_sha256"],
        "runtime_sha256": runtime_contract["runtime_sha256"],
        "lock_sha256": lock["sha256"],
        "companion_sha256": companion["sha256"],
    }


def _effective_authorizations(*, model_id: str, audit: bool) -> dict[str, bool]:
    return {
        "a0_development_fit_authorized": not audit and model_id == "A0",
        "a1_development_fit_authorized": not audit and model_id == "A1",
        "target_access_through_2020_authorized": True,
        "selection_diagnostics_authorized": True,
        "model_bundle_audit_authorized": audit,
        "calibration_authorized": False,
        "calibration_target_access_authorized": False,
        "final_e7_metrics_authorized": False,
        "rollout_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "dvc_commands_authorized": False,
        "scientific_network_authorized": False,
        "outcome_access_authorized": False,
        "future_outcomes_accessed": False,
        "batch_slot_execution_authorized": False,
    }


def _summary_authorizations() -> dict[str, bool]:
    keys = _effective_authorizations(model_id="A0", audit=False)
    return {key: False for key in keys}


def load_effective_anfis_ablation_training_cohort_authority(
    *,
    model_id: str | None = None,
    base_seed: int | None = None,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    if type(audit_current_unpublished) is not bool:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU audit mode must be an exact boolean"
        )
    target_supplied = model_id is not None or base_seed is not None
    if target_supplied and (model_id is None or base_seed is None):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU target model/seed is incomplete"
        )
    if audit_current_unpublished and not target_supplied:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU audit mode requires one explicit target"
        )
    if target_supplied:
        if type(model_id) is not str or type(base_seed) is not int:
            raise AnfisAblationTrainingCohortPatchError(
                "E0-MU target model/seed types drifted"
            )
        try:
            validate_model_seed(model_id, base_seed)
        except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
            raise _translate(exc) from exc
    if verify_remote is not True:
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU effective authority requires live remote verification"
        )
    root = _root(repo_root)
    payload = _load_json(DEFAULT_PATCH_LOCK_PATH, repo_root=root)
    if _read_regular_bytes(DEFAULT_PATCH_LOCK_PATH, repo_root=root) != _canonical_json(
        payload
    ):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU lock is not canonical JSON"
        )
    pointer_presence = [
        _lexists(root / mt._pointer_path(slot_model, slot_seed))
        for slot_model, slot_seed in ORDERED_SLOTS
    ]
    validate_anfis_ablation_training_cohort_patch_lock_payload(
        payload,
        repo_root=root,
        allow_models_dvc_drift=all(pointer_presence),
    )
    lock_record = _file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="anfis_ablation_training_cohort_patch_lock",
        repo_root=root,
    )
    companion = _load_json(DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root)
    if (
        _read_regular_bytes(DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root)
        != _canonical_json(companion)
        or companion != _expected_companion(payload, lock_record, repo_root=root)
    ):
        raise AnfisAblationTrainingCohortPatchError(
            "E0-MU lock companion drifted"
        )
    companion_record = _file_record(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        role="anfis_ablation_training_cohort_patch_lock_manifest",
        repo_root=root,
    )
    publication = _validate_p_publication(payload, repo_root=root)
    static = _static_effective_authority(
        payload,
        publication=publication,
        lock=lock_record,
        companion=companion_record,
    )
    try:
        prefix_count = mt._validate_exact_training_prefix(
            static,
            # A no-target summary is a read-only inspection mode.  It must
            # remain usable after all ten audited DVC pointers are registered,
            # while still returning an all-false authorization matrix.
            audit_mode=audit_current_unpublished or not target_supplied,
            repo_root=root,
        )
    except mt.AnfisAblationTrainingDevelopmentPatchError as exc:
        raise _translate(exc) from exc
    if model_id is None or base_seed is None:
        return {
            **static,
            **_summary_authorizations(),
            "authorized_model_id": None,
            "authorized_base_seed": None,
            "completed_prefix_count": prefix_count,
            "slot_creation_prefix_count": None,
            "audit_current_unpublished": False,
            "ordered_slots": [
                {"model_id": slot_model, "base_seed": slot_seed}
                for slot_model, slot_seed in ORDERED_SLOTS
            ],
            "progression_policy": (
                "exact_completed_untracked_prefix_no_pointers_until_all_ten"
            ),
        }
    target_index = ORDERED_SLOTS.index((model_id, base_seed))
    valid_target = (
        target_index < prefix_count
        if audit_current_unpublished
        else target_index == prefix_count
    )
    if not valid_target:
        mode = "audit" if audit_current_unpublished else "build"
        raise AnfisAblationTrainingCohortPatchError(
            f"E0-MU target is not in the exact {mode} position"
        )
    return {
        **static,
        **_effective_authorizations(
            model_id=model_id,
            audit=audit_current_unpublished,
        ),
        "authorized_model_id": model_id,
        "authorized_base_seed": base_seed,
        "completed_prefix_count": (
            prefix_count if audit_current_unpublished else target_index
        ),
        "slot_creation_prefix_count": target_index,
        "audit_current_unpublished": audit_current_unpublished,
        "ordered_slots": [
            {"model_id": slot_model, "base_seed": slot_seed}
            for slot_model, slot_seed in ORDERED_SLOTS
        ],
        "progression_policy": (
            "exact_completed_untracked_prefix_no_pointers_until_all_ten"
        ),
    }


def require_anfis_ablation_training_cohort_authority(
    model_id: str,
    base_seed: int,
    *,
    repo_root: Path | None = None,
    audit_current_unpublished: bool = False,
    verify_remote: bool = True,
) -> dict[str, Any]:
    return load_effective_anfis_ablation_training_cohort_authority(
        model_id=model_id,
        base_seed=base_seed,
        audit_current_unpublished=audit_current_unpublished,
        verify_remote=verify_remote,
        repo_root=repo_root,
    )
