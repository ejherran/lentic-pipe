"""Corrective publication authority for Closure V1 final calibration.

E0-MCALP wraps the sealed E0-MCAL scientific contract.  It changes only the
publication authority and keeps the former runtime/read helpers available to
the calibration and E7 runners through explicit delegation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, ParamSpec, TypeVar, cast

from src.experiments import closure_final_calibration as mcal
from src.experiments import closure_anfis_ablation_training_development_patch as mt


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_H_MCAL_COMMIT = "5d096e8ca560a592a65ab231ae173c4d3b5a4ff6"
BASE_H_MCAL_PARENT = "2f46d3e258195315e2473be6cf7d62db22c55bcf"
PATCH_GATE = "E0-MCALP"
FINAL_CALIBRATION_GATE = PATCH_GATE
EXPERIMENT_ID = "closure_v1"
LOCK_SCHEMA_VERSION = "closure_final_calibration_publication_guard_patch_lock_v1"
COMPANION_SCHEMA_VERSION = (
    "closure_final_calibration_publication_guard_patch_lock_manifest_v1"
)

DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/final_calibration_publication_guard_patch_lock.schema.json"
)
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "final_calibration_publication_guard_patch_lock.json"
)
DEFAULT_PATCH_LOCK_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "final_calibration_publication_guard_patch_lock_manifest.json"
)
DEFAULT_PATCH_MANIFEST_PATH = DEFAULT_PATCH_LOCK_MANIFEST_PATH
LOCKER_PATH = Path(
    "src/experiments/lock_closure_final_calibration_publication_guard_patch.py"
)
LOCKER_GUARD_PATH = Path(
    "tmp/closure_v1_e0_mcalp/final_calibration_publication_guard_patch_lock.guard"
)

H_MCAL_SUPERSEDED_PATHS = tuple(
    sorted(
        {
            "src/experiments/calibrate_closure_final_models.py",
            "src/experiments/run_closure_anfis_learning_curve.py",
            "tests/test_calibrate_closure_final_models.py",
            "tests/test_closure_anfis_learning_curve.py",
        }
    )
)
H_MCAL_PRESERVED_PATHS = tuple(
    path for path in mcal.PATCH_PATHS if path not in H_MCAL_SUPERSEDED_PATHS
)
PATCH_PATHS = tuple(
    sorted(
        {
            DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
            "docs/closure_v1/E0_M_FINAL_CALIBRATION_PUBLICATION_GUARD_PATCH_1.md",
            *H_MCAL_SUPERSEDED_PATHS,
            __file__.replace(f"{PROJECT_ROOT.as_posix()}/", ""),
            LOCKER_PATH.as_posix(),
            "tests/test_closure_final_calibration_publication_guard_patch.py",
        }
    )
)
PATCH_COMPONENT_GIT_MODES = {path: "100644" for path in PATCH_PATHS}
FINAL_CALIBRATION_H_STAGED_SCOPE = {
    path: ("M" if path in H_MCAL_SUPERSEDED_PATHS else "A")
    for path in PATCH_PATHS
}
FINAL_CALIBRATION_P_STAGED_SCOPE = {
    DEFAULT_PATCH_LOCK_PATH.as_posix(): "A",
    DEFAULT_PATCH_LOCK_MANIFEST_PATH.as_posix(): "A",
}
FINAL_CALIBRATION_R_STAGED_SCOPE = dict(mcal.FINAL_CALIBRATION_R_STAGED_SCOPE)
R_OUTPUT_PATHS = mcal.R_OUTPUT_PATHS

EXPECTED_COMPANION_INPUT_COUNT = 17
EXPECTED_HISTORICAL_INPUT_COUNT = 4
EXPECTED_COMPANION_OUTPUT_COUNT = 1

INTERRUPTED_ATTEMPT: dict[str, Any] = {
    "attempted_gate": "E0-MCAL",
    "status": "interrupted_no_authority",
    "phase": "indeterminate",
    "authority_created": False,
    "final_output_count": 0,
    "temporary_output_count": 0,
    "active_guard_count": 0,
    "scientific_execution_run": False,
    "dvc_commands_run": False,
    "side_effect_count": 0,
}

TYPE_CHECK_COMMAND = mcal.TYPE_CHECK_COMMAND
FOCUSED_TEST_COMMAND = (
    "poetry",
    "run",
    "pytest",
    "-q",
    "tests/test_calibrate_closure_final_models.py",
    "tests/test_closure_anfis_learning_curve.py",
    "tests/test_closure_final_calibration_publication_guard_patch.py",
)
FOCUSED_TEST_COUNT = 48
POETRY_CHECK_COMMAND = mcal.POETRY_CHECK_COMMAND
PUBLICATION_GUARD_COMMAND = mcal.PUBLICATION_GUARD_COMMAND
DIFF_CHECK_COMMAND = mcal.DIFF_CHECK_COMMAND
UNPUBLISHED_AUTHORIZATIONS = dict(mcal.UNPUBLISHED_AUTHORIZATIONS)
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class FinalCalibrationPublicationGuardPatchError(mcal.FinalCalibrationError):
    """Raised when the E0-MCALP authority or publication is not exact."""


FinalCalibrationError = mcal.FinalCalibrationError
P = ParamSpec("P")
R = TypeVar("R")


def _error(message: str) -> FinalCalibrationPublicationGuardPatchError:
    return FinalCalibrationPublicationGuardPatchError(message)


def _error_boundary(function: Callable[P, R]) -> Callable[P, R]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return function(*args, **kwargs)
        except FinalCalibrationPublicationGuardPatchError:
            raise
        except mcal.FinalCalibrationError as exc:
            raise _error(str(exc).replace("E0-MCAL", "E0-MCALP")) from exc

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
        raise _error(f"E0-MCALP historical Git mode drifted: {path}")
    return {
        "role": role,
        "path": path,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
        "git_oid": oid,
        "git_mode": mode,
    }


def _h_mcal_authority(*, repo_root: Path) -> dict[str, Any]:
    if (
        mcal._single_parent(repo_root, BASE_H_MCAL_COMMIT, context="H-E0-MCAL")
        != BASE_H_MCAL_PARENT
    ):
        raise _error("E0-MCALP historical H-E0-MCAL parent drifted")
    scope = mcal._git_scope(repo_root, BASE_H_MCAL_PARENT, BASE_H_MCAL_COMMIT)
    expected_scope = {
        "added": 12,
        "modified": 0,
        "deleted": 0,
        "path_count": 12,
        "paths": list(mcal.PATCH_PATHS),
    }
    if scope != expected_scope:
        raise _error("E0-MCALP historical H-E0-MCAL scope drifted")
    components = [
        _git_record_at_commit(
            path,
            role="final_calibration_h_component",
            commit=BASE_H_MCAL_COMMIT,
            repo_root=repo_root,
        )
        for path in mcal.PATCH_PATHS
    ]
    preserved: list[dict[str, Any]] = []
    for path in H_MCAL_PRESERVED_PATHS:
        record = _git_record_at_commit(
            path,
            role="preserved_h_mcal_component",
            commit=BASE_H_MCAL_COMMIT,
            repo_root=repo_root,
        )
        physical = mcal._git_artifact_record(
            Path(path),
            role="preserved_h_mcal_component",
            repo_root=repo_root,
            commit=BASE_H_MCAL_COMMIT,
        )
        if physical != record:
            raise _error(f"E0-MCALP preserved H component drifted: {path}")
        preserved.append(record)
    historical = []
    for path in H_MCAL_SUPERSEDED_PATHS:
        record = _git_record_at_commit(
            path,
            role="superseded_h_mcal_component",
            commit=BASE_H_MCAL_COMMIT,
            repo_root=repo_root,
        )
        historical.append({**record, "commit": BASE_H_MCAL_COMMIT})
    return {
        "gate": "H-E0-MCAL",
        "commit": BASE_H_MCAL_COMMIT,
        "parent": BASE_H_MCAL_PARENT,
        "component_count": 12,
        "preserved_count": 8,
        "superseded_count": 4,
        "components": components,
        "components_sha256": mcal._digest_records(components),
        "preserved_components": preserved,
        "preserved_components_sha256": mcal._digest_records(preserved),
        "historical_inputs": historical,
        "historical_inputs_sha256": mcal._digest_records(historical),
    }


def _candidate_status_is_exact(repo_root: Path) -> bool:
    records = mcal._workspace_status_records(repo_root)
    if {path for _, path in records} != set(PATCH_PATHS):
        return False
    by_path = {path: code for code, path in records}
    return all(
        by_path[path] in ({" M", "M ", "MM"} if path in H_MCAL_SUPERSEDED_PATHS else {"??", "A "})
        for path in PATCH_PATHS
    )


def _h_patch_authority(
    *, repo_root: Path, verify_remote: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    if type(verify_remote) is not bool:
        raise _error("E0-MCALP remote policy must be an exact boolean")
    head = mcal._git_head(repo_root)
    branch = cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
    if branch != "main":
        raise _error("E0-MCALP H authority requires branch main")
    candidate = head == BASE_H_MCAL_COMMIT
    expected_scope = {
        "added": 5,
        "modified": 4,
        "deleted": 0,
        "path_count": 9,
        "paths": list(PATCH_PATHS),
    }
    if candidate:
        if not _candidate_status_is_exact(repo_root):
            raise _error("E0-MCALP candidate workspace is not exact 4M+5A")
        commit_for_components: str | None = None
        h_head = BASE_H_MCAL_COMMIT
        scope = expected_scope
    else:
        if (
            mcal._single_parent(repo_root, head, context="H-E0-MCALP")
            != BASE_H_MCAL_COMMIT
        ):
            raise _error("E0-MCALP published H parent drifted")
        scope = mcal._git_scope(repo_root, BASE_H_MCAL_COMMIT, head)
        if scope != expected_scope or mcal._workspace_status_records(repo_root):
            raise _error("E0-MCALP published H scope/worktree drifted")
        commit_for_components = head
        h_head = head
    components = [
        mcal._git_artifact_record(
            Path(path),
            role="final_calibration_publication_guard_patch_component",
            repo_root=repo_root,
            commit=commit_for_components,
        )
        for path in PATCH_PATHS
    ]
    tracking = mcal._git_head(repo_root, "origin/main")
    expected_ref = BASE_H_MCAL_COMMIT if candidate else head
    if tracking != expected_ref:
        raise _error("E0-MCALP H tracking ref drifted")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if remote != expected_ref:
        raise _error("E0-MCALP H remote ref drifted")
    repository = {
        "base_h_mcal_commit": BASE_H_MCAL_COMMIT,
        "h_patch_head": h_head,
        "branch": branch,
        "remote_head": remote,
        "scope": scope,
    }
    return repository, {
        "gate": "H-E0-MCALP",
        "component_count": 9,
        "added_count": 5,
        "modified_count": 4,
        "components": components,
        "components_sha256": mcal._digest_records(components),
    }


def _namespace_paths() -> tuple[Path, ...]:
    legacy = (
        mcal.DEFAULT_PATCH_LOCK_PATH,
        mcal.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
    )
    finals = (
        *legacy,
        DEFAULT_PATCH_LOCK_PATH,
        DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        *R_OUTPUT_PATHS,
    )
    temporaries = tuple(mcal._temporary_path(path) for path in finals)
    return (
        *finals,
        *temporaries,
        mcal.LOCKER_GUARD_PATH,
        LOCKER_GUARD_PATH,
        mcal.CALIBRATION_GUARD_PATH,
        mcal.E7_GUARD_PATH,
    )


def _require_prelock_namespace(*, repo_root: Path) -> None:
    occupied = [
        path.as_posix()
        for path in _namespace_paths()
        if mcal._entry_exists(path, repo_root=repo_root)
    ]
    if occupied:
        raise _error(f"E0-MCALP prelock namespace is occupied: {occupied}")
    if mcal._entry_exists(Path(mcal.mze.OUTCOME_ACCESS_LOG), repo_root=repo_root):
        raise _error("E0-MCALP outcome access log must remain absent")
    if any(
        mcal._entry_exists(Path(path), repo_root=repo_root)
        for path in mcal.mze.E0_M_PATHS
    ):
        raise _error("E0-MCALP final E0-M namespace must remain absent")


@_error_boundary
def preflight_final_calibration_publication_guard_patch_schema(
    *, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    validator = getattr(mcal.closure_contract, "_assert_supported_json_schema", None)
    if not callable(validator):
        raise _error("E0-MCALP supported JSON-schema validator is unavailable")
    try:
        validator(schema)
    except mcal.ClosureContractError as exc:
        raise _error(str(exc)) from exc
    return {
        "status": "schema_ready",
        "gate": PATCH_GATE,
        "schema_count": 1,
        "schemas": [
            mcal._file_record(
                DEFAULT_PATCH_LOCK_SCHEMA,
                role="final_calibration_publication_guard_patch_lock_schema",
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
    schema_preflight = preflight_final_calibration_publication_guard_patch_schema(
        repo_root=repo_root
    )
    runtime = mcal.load_and_validate_final_calibration_runtime(repo_root=repo_root)
    h_mcal = _h_mcal_authority(repo_root=repo_root)
    scientific_inputs = mcal._scientific_input_inventory(repo_root=repo_root)
    base = mcal._base_r_mze_authority(repo_root=repo_root)
    historical_e7 = mcal._historical_e7_blockers(repo_root=repo_root)
    if cast(Mapping[str, Any], runtime["e7_terminal_record"]).get(
        "historical_blockers_adopted"
    ) != historical_e7:
        raise _error("E0-MCALP historical E7 authority drifted")
    if require_empty_namespace:
        _require_prelock_namespace(repo_root=repo_root)
    preserved = cast(list[dict[str, Any]], h_mcal["preserved_components"])
    runtime_contract = {
        "physical_input_count": 12,
        "historical_input_count": 0,
        "runtime": next(
            record
            for record in preserved
            if record["path"] == mcal.DEFAULT_RUNTIME_PATH.as_posix()
        ),
        "runtime_schema": next(
            record
            for record in preserved
            if record["path"] == mcal.DEFAULT_RUNTIME_SCHEMA.as_posix()
        ),
        "lock_schema": next(
            record
            for record in preserved
            if record["path"] == mcal.DEFAULT_LOCK_SCHEMA.as_posix()
        ),
        "runtime_payload_sha256": _sha256_bytes(_canonical_json_bytes(runtime)),
        "scientific_authority_record_count": scientific_inputs[
            "authority_record_count"
        ],
        "scientific_payload_binding_count": scientific_inputs[
            "payload_binding_count"
        ],
        "scientific_authority_records_sha256": scientific_inputs[
            "authority_records_sha256"
        ],
        "scientific_payload_bindings_sha256": scientific_inputs[
            "payload_bindings_sha256"
        ],
        "supported_schema_subset_verified": schema_preflight[
            "supported_subset_verified"
        ],
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
        "legacy_p_output_present_count": 0,
        "p_output_present_count": 0,
        "r_output_present_count": 0,
        "temporary_present_count": 0,
        "coordination_present_count": 0,
        "outcome_access_log_absent": True,
        "holdout_rows_opened": False,
        "post_2021_rows_opened": False,
        "dvc_commands_run": False,
        "scientific_writes_performed": False,
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
        "h_mcal_authority": h_mcal,
        "h_patch": _deep_copy(h_patch),
        "runtime": runtime_contract,
        "scientific_input_inventory": scientific_inputs,
        "scientific_boundary": boundary,
        "model_matrix": _deep_copy(runtime["model_matrix"]),
        "calibration_group_matrix": _deep_copy(runtime["calibration_group_matrix"]),
        "e7_terminal_record": _deep_copy(runtime["e7_terminal_record"]),
        "output_contract": mcal._output_contract(runtime),
        "prelock": prelock,
        "base_r_mze_authority": base,
    }


@_error_boundary
def collect_final_calibration_publication_guard_patch_prelock_state(
    *, verify_remote: bool = False, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    repository, h_patch = _h_patch_authority(
        repo_root=root, verify_remote=verify_remote
    )
    state = _state_for_h(
        repository=repository,
        h_patch=h_patch,
        repo_root=root,
        require_empty_namespace=True,
    )
    state.pop("base_r_mze_authority")
    return state


def _default_unrun_verification() -> dict[str, Any]:
    return {
        "status": "not_run_by_payload_builder",
        "commands_run": False,
        "scientific_execution_run": False,
        "dvc_commands_run": False,
        "outcome_paths_opened": False,
    }


@_error_boundary
def build_final_calibration_publication_guard_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any] | None = None,
    *,
    generated_at_utc: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root
    required = {
        "repository",
        "h_mcal_authority",
        "h_patch",
        "runtime",
        "scientific_input_inventory",
        "scientific_boundary",
        "model_matrix",
        "calibration_group_matrix",
        "e7_terminal_record",
        "output_contract",
        "prelock",
    }
    if set(prelock) != required:
        raise _error("E0-MCALP prelock dialect drifted")
    timestamp = generated_at_utc or datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": LOCK_SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "status": "locked_unpublished",
        "generated_at_utc": timestamp,
        "repository": _deep_copy(prelock["repository"]),
        "interrupted_attempt": dict(INTERRUPTED_ATTEMPT),
        "h_mcal_authority": _deep_copy(prelock["h_mcal_authority"]),
        "h_patch": _deep_copy(prelock["h_patch"]),
        "runtime": _deep_copy(prelock["runtime"]),
        "scientific_input_inventory": _deep_copy(
            prelock["scientific_input_inventory"]
        ),
        "scientific_boundary": _deep_copy(prelock["scientific_boundary"]),
        "model_matrix": _deep_copy(prelock["model_matrix"]),
        "calibration_group_matrix": _deep_copy(
            prelock["calibration_group_matrix"]
        ),
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
        raise _error("E0-MCALP generated timestamp is absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _error("E0-MCALP generated timestamp is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _error("E0-MCALP generated timestamp must be timezone-aware")


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
        raise _error("E0-MCALP verification evidence dialect drifted")
    expected_preflight = preflight_final_calibration_publication_guard_patch_schema(
        repo_root=repo_root
    )
    if _canonical_json_bytes(value["schema_preflight"]) != _canonical_json_bytes(
        expected_preflight
    ):
        raise _error("E0-MCALP schema verification evidence drifted")
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
        except mcal.FinalCalibrationError as exc:
            raise _error(str(exc)) from exc
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
        raise _error("E0-MCALP focused verification evidence drifted")
    try:
        mcal._validate_command_evidence(
            {key: focused[key] for key in base_keys},
            expected_command=FOCUSED_TEST_COMMAND,
            context="focused_tests",
        )
    except mcal.FinalCalibrationError as exc:
        raise _error(str(exc)) from exc


@_error_boundary
def validate_final_calibration_publication_guard_patch_lock_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    verify_remote: bool = False,
) -> dict[str, Any]:
    root = _root(repo_root)
    if not isinstance(payload, Mapping):
        raise _error("E0-MCALP lock payload must be an object")
    schema = mcal._load_json_object(DEFAULT_PATCH_LOCK_SCHEMA, repo_root=root)
    try:
        mcal.validate_json_schema(payload, schema)
    except mcal.ClosureContractError as exc:
        raise _error(str(exc)) from exc
    _validate_timestamp(payload.get("generated_at_utc"))
    _validate_verification(payload.get("verification"), repo_root=root)
    if payload.get("authorizations") != UNPUBLISHED_AUTHORIZATIONS:
        raise _error("E0-MCALP unpublished authorizations drifted")
    state = collect_final_calibration_publication_guard_patch_prelock_state(
        verify_remote=verify_remote, repo_root=root
    )
    expected = build_final_calibration_publication_guard_patch_lock_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=cast(str, payload["generated_at_utc"]),
    )
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("E0-MCALP lock semantic reconstruction drifted")
    return dict(payload)


_OwnedOutput = mt._OwnedOutput


def _publish_bytes_no_clobber(
    final_path: Path, payload: bytes, *, repo_root: Path
) -> _OwnedOutput:
    """Publish through one owned temporary identity and never adopt a final."""

    root = _root(repo_root)
    if type(payload) is not bytes:
        raise _error("E0-MCALP publication payload must be exact bytes")
    temporary = mcal._temporary_path(final_path)
    try:
        relative = mt._relative_path(final_path, root)
        temporary_relative = mt._relative_path(temporary, root)
        lexical_parent = root / relative.parent
        parent_fd, final_name = mt._open_parent_directory(
            final_path, repo_root=root, create=True
        )
    except Exception as exc:
        raise _error(
            f"E0-MCALP output parent is invalid: {final_path.as_posix()}"
        ) from exc
    temporary_name = temporary_relative.name
    descriptor: int | None = None
    temp_identity: tuple[int, int] | None = None
    parent_identity: tuple[int, int] | None = None
    retained = False
    cleanup_errors: list[BaseException] = []
    try:
        parent = os.fstat(parent_fd)
        if not stat.S_ISDIR(parent.st_mode):
            raise _error(
                f"E0-MCALP output parent is not a directory: {final_path.as_posix()}"
            )
        parent_identity = (int(parent.st_dev), int(parent.st_ino))
        if mt._named_identity(parent_fd, final_name) is not None:
            raise _error(
                f"E0-MCALP refuses to overwrite final: {final_path.as_posix()}"
            )
        if mt._named_identity(parent_fd, temporary_name) is not None:
            raise _error(
                f"E0-MCALP refuses occupied temporary: {temporary.as_posix()}"
            )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temporary_name, flags, 0o644, dir_fd=parent_fd)
        before = os.fstat(descriptor)
        temp_identity = (int(before.st_dev), int(before.st_ino))
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o644
            or before.st_nlink != 1
        ):
            raise _error(f"E0-MCALP temporary mode drifted: {temporary.as_posix()}")
        mt._write_all(descriptor, payload)
        os.fsync(descriptor)
        after_write = os.fstat(descriptor)
        if (
            not stat.S_ISREG(after_write.st_mode)
            or (after_write.st_dev, after_write.st_ino) != temp_identity
            or stat.S_IMODE(after_write.st_mode) != 0o644
            or after_write.st_nlink != 1
            or after_write.st_size != len(payload)
            or mt._named_identity(parent_fd, temporary_name) != temp_identity
        ):
            raise _error(
                f"E0-MCALP temporary changed during write: {temporary.as_posix()}"
            )
        os.link(
            temporary_name,
            final_name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
            follow_symlinks=False,
        )
        after_link = os.fstat(descriptor)
        if (
            (after_link.st_dev, after_link.st_ino) != temp_identity
            or after_link.st_nlink != 2
            or mt._named_identity(parent_fd, temporary_name) != temp_identity
            or mt._named_identity(parent_fd, final_name) != temp_identity
        ):
            raise _error(
                f"E0-MCALP final identity drifted: {final_path.as_posix()}"
            )
        os.fsync(parent_fd)
        if mt._named_identity(parent_fd, temporary_name) != temp_identity:
            raise _error(f"E0-MCALP temporary was replaced: {temporary.as_posix()}")
        os.unlink(temporary_name, dir_fd=parent_fd)
        os.fsync(parent_fd)
        after_unlink = os.fstat(descriptor)
        if (
            (after_unlink.st_dev, after_unlink.st_ino) != temp_identity
            or after_unlink.st_nlink != 1
            or after_unlink.st_size != len(payload)
            or mt._named_identity(parent_fd, final_name) != temp_identity
        ):
            raise _error(
                f"E0-MCALP final changed after temporary release: {final_path.as_posix()}"
            )
        os.close(descriptor)
        descriptor = None
        retained = True
        return _OwnedOutput(
            path=final_path,
            lexical_parent=lexical_parent,
            name=final_name,
            parent_descriptor=parent_fd,
            device=temp_identity[0],
            inode=temp_identity[1],
            parent_device=parent_identity[0],
            parent_inode=parent_identity[1],
        )
    except BaseException as exc:
        if temp_identity is not None:
            for name in (temporary_name, final_name):
                try:
                    if mt._named_identity(parent_fd, name) == temp_identity:
                        os.unlink(name, dir_fd=parent_fd)
                except BaseException as cleanup_exc:
                    cleanup_errors.append(cleanup_exc)
            try:
                os.fsync(parent_fd)
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        if cleanup_errors:
            for cleanup_exc in cleanup_errors:
                exc.add_note(str(cleanup_exc))
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, FinalCalibrationPublicationGuardPatchError):
            raise
        raise _error(
            f"E0-MCALP no-clobber publication failed: {final_path.as_posix()}"
        ) from exc
    finally:
        close_errors: list[OSError] = []
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as exc:
                close_errors.append(exc)
        if not retained:
            try:
                os.close(parent_fd)
            except OSError as exc:
                close_errors.append(exc)
        if close_errors:
            active = sys.exception()
            detail = "E0-MCALP descriptor cleanup failed: " + "; ".join(
                str(exc) for exc in close_errors
            )
            if active is not None:
                active.add_note(detail)
            else:
                raise _error(detail)


def _validate_owned_output(output: _OwnedOutput) -> None:
    if output.closed:
        raise _error(f"E0-MCALP owned output is closed: {output.path.as_posix()}")
    try:
        parent = os.fstat(output.parent_descriptor)
        lexical_parent = output.lexical_parent.lstat()
        named = mt._named_identity(output.parent_descriptor, output.name)
    except OSError as exc:
        raise _error(
            f"E0-MCALP owned output metadata failed: {output.path.as_posix()}"
        ) from exc
    if (
        not stat.S_ISDIR(parent.st_mode)
        or (parent.st_dev, parent.st_ino)
        != (output.parent_device, output.parent_inode)
        or not stat.S_ISDIR(lexical_parent.st_mode)
        or (lexical_parent.st_dev, lexical_parent.st_ino)
        != (output.parent_device, output.parent_inode)
        or named != (output.device, output.inode)
    ):
        raise _error(
            f"E0-MCALP owned output identity drifted: {output.path.as_posix()}"
        )


def _close_owned_output(output: _OwnedOutput) -> None:
    if output.closed:
        return
    try:
        os.close(output.parent_descriptor)
    except OSError as exc:
        raise _error(
            f"E0-MCALP owned output close failed: {output.path.as_posix()}"
        ) from exc
    finally:
        output.closed = True


def _rollback_owned_output(output: _OwnedOutput) -> None:
    """Remove a name only when it still resolves to ``temp_identity``."""

    if output.closed:
        return
    error: BaseException | None = None
    try:
        parent = os.fstat(output.parent_descriptor)
        named = mt._named_identity(output.parent_descriptor, output.name)
        if (
            not stat.S_ISDIR(parent.st_mode)
            or (parent.st_dev, parent.st_ino)
            != (output.parent_device, output.parent_inode)
        ):
            raise _error(
                f"E0-MCALP owned output parent drifted: {output.path.as_posix()}"
            )
        if named != (output.device, output.inode):
            raise _error(
                f"E0-MCALP refuses rollback of foreign output: {output.path.as_posix()}"
            )
        os.unlink(output.name, dir_fd=output.parent_descriptor)
        os.fsync(output.parent_descriptor)
    except BaseException as exc:
        error = exc
    finally:
        try:
            os.close(output.parent_descriptor)
        except OSError as exc:
            if error is None:
                error = exc
        output.closed = True
    if error is not None:
        if isinstance(error, FinalCalibrationPublicationGuardPatchError):
            raise error
        raise _error(
            f"E0-MCALP owned output rollback failed: {output.path.as_posix()}"
        ) from error


def _public_artifact_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: record[key] for key in ("role", "path", "bytes", "sha256")
    }


def _expected_companion(
    payload: Mapping[str, Any], lock_record: Mapping[str, Any]
) -> dict[str, Any]:
    h_mcal = cast(Mapping[str, Any], payload["h_mcal_authority"])
    h_patch = cast(Mapping[str, Any], payload["h_patch"])
    preserved = cast(Sequence[Mapping[str, Any]], h_mcal["preserved_components"])
    current = cast(Sequence[Mapping[str, Any]], h_patch["components"])
    historical = cast(Sequence[Mapping[str, Any]], h_mcal["historical_inputs"])
    inputs = [_public_artifact_record(record) for record in (*preserved, *current)]
    inputs.sort(key=lambda record: cast(str, record["path"]))
    if len(inputs) != 17 or len({record["path"] for record in inputs}) != 17:
        raise _error("E0-MCALP companion physical input set drifted")
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
            "E0-MCALP publication requires the exact frozen verification evidence"
        )
    _validate_verification(verification, repo_root=repo_root)


def _physical_snapshot(
    repo_root: Path, *, scientific_inventory: Mapping[str, Any]
) -> tuple[dict[str, Any], ...]:
    records = [
        dict(record)
        for record in mcal._physical_snapshot(
            repo_root, scientific_inventory=scientific_inventory
        )
    ]
    known = {cast(str, record["path"]) for record in records}
    for path_text in PATCH_PATHS:
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
    observed = _physical_snapshot(
        repo_root, scientific_inventory=scientific_inventory
    )
    if _canonical_json_bytes(expected) != _canonical_json_bytes(observed):
        raise _error(f"E0-MCALP physical authority changed {context}")


def _validate_owned_output_bytes(
    output: _OwnedOutput,
    expected: bytes,
    *,
    repo_root: Path,
    context: str,
) -> os.stat_result:
    _validate_owned_output(output)
    payload, metadata = mcal._read_regular_bytes_and_metadata(
        output.path, repo_root=repo_root
    )
    if (
        payload != expected
        or (metadata.st_dev, metadata.st_ino) != (output.device, output.inode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o644
    ):
        raise _error(
            f"E0-MCALP owned output drifted {context}: {output.path.as_posix()}"
        )
    return metadata


def _require_owned_identity_set(
    outputs: Sequence[_OwnedOutput], *, context: str
) -> None:
    """Checkpoint every retained name against its original temporary inode."""

    observed: list[
        tuple[_OwnedOutput, os.stat_result, os.stat_result, tuple[int, int] | None]
    ] = []
    for output in outputs:
        if output.closed:
            raise _error(
                f"E0-MCALP owned output closed {context}: {output.path.as_posix()}"
            )
        try:
            observed.append(
                (
                    output,
                    os.fstat(output.parent_descriptor),
                    output.lexical_parent.lstat(),
                    mt._named_identity(output.parent_descriptor, output.name),
                )
            )
        except OSError as exc:
            raise _error(
                f"E0-MCALP owned identity checkpoint failed {context}"
            ) from exc
    for output, parent, lexical_parent, named in observed:
        if (
            not stat.S_ISDIR(parent.st_mode)
            or (parent.st_dev, parent.st_ino)
            != (output.parent_device, output.parent_inode)
            or not stat.S_ISDIR(lexical_parent.st_mode)
            or (lexical_parent.st_dev, lexical_parent.st_ino)
            != (output.parent_device, output.parent_inode)
            or named != (output.device, output.inode)
        ):
            raise _error(
                f"E0-MCALP owned identity set drifted {context}: "
                f"{output.path.as_posix()}"
            )


def _rollback_outputs_best_effort(
    outputs: Sequence[_OwnedOutput],
) -> FinalCalibrationPublicationGuardPatchError | None:
    errors: list[BaseException] = []
    for output in reversed(outputs):
        try:
            _rollback_owned_output(output)
        except BaseException as exc:
            errors.append(exc)
    if not errors:
        return None
    error = _error("E0-MCALP owned-output rollback was incomplete")
    for nested in errors:
        error.add_note(str(nested))
    return error


def _close_outputs(outputs: Sequence[_OwnedOutput]) -> None:
    errors: list[BaseException] = []
    for output in reversed(outputs):
        try:
            _close_owned_output(output)
        except BaseException as exc:
            errors.append(exc)
    if errors:
        error = _error("E0-MCALP owned-output descriptor cleanup failed")
        for nested in errors:
            error.add_note(str(nested))
        raise error


@_error_boundary
def publish_final_calibration_publication_guard_patch_lock_bundle(
    payload: Mapping[str, Any], *, repo_root: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _root(repo_root)
    repository = payload.get("repository")
    if (
        not isinstance(repository, Mapping)
        or repository.get("h_patch_head") == BASE_H_MCAL_COMMIT
    ):
        raise _error("E0-MCALP H must be published before P publication")
    _require_publication_verification(payload, repo_root=root)
    validate_final_calibration_publication_guard_patch_lock_payload(
        payload, repo_root=root, verify_remote=True
    )
    scientific_inventory = payload.get("scientific_input_inventory")
    if not isinstance(scientific_inventory, Mapping):
        raise _error("E0-MCALP scientific inventory is absent")
    snapshot = _physical_snapshot(
        root, scientific_inventory=scientific_inventory
    )
    initial_head = mcal._git_head(root)
    initial_tracking = mcal._git_head(root, "origin/main")
    if (
        initial_head != repository.get("h_patch_head")
        or initial_tracking != initial_head
    ):
        raise _error("E0-MCALP H refs drifted before publication")
    _require_prelock_namespace(repo_root=root)
    guard: mt._OwnedGuard | None = None
    published: list[_OwnedOutput] = []
    committed = False
    try:
        try:
            guard = mt._acquire_publication_guard(
                LOCKER_GUARD_PATH,
                b"E0-MCALP final calibration guard patch lock publication\n",
                repo_root=root,
            )
        except Exception as exc:
            raise _error("E0-MCALP publication guard acquisition failed") from exc
        _require_physical_snapshot(
            snapshot,
            scientific_inventory=scientific_inventory,
            repo_root=root,
            context="after guard acquisition",
        )
        lock_bytes = _canonical_json_bytes(payload)
        lock_output = _publish_bytes_no_clobber(
            DEFAULT_PATCH_LOCK_PATH, lock_bytes, repo_root=root
        )
        published.append(lock_output)
        _validate_owned_output_bytes(
            lock_output,
            lock_bytes,
            repo_root=root,
            context="after lock publication",
        )
        lock_record = {
            "role": "final_calibration_publication_guard_patch_lock",
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
        for output, expected in (
            (lock_output, lock_bytes),
            (companion_output, companion_bytes),
        ):
            _validate_owned_output_bytes(
                output,
                expected,
                repo_root=root,
                context="after companion publication",
            )
        _require_physical_snapshot(
            snapshot,
            scientific_inventory=scientific_inventory,
            repo_root=root,
            context="after companion publication",
        )
        if (
            mcal._git_head(root) != initial_head
            or mcal._git_head(root, "origin/main") != initial_tracking
        ):
            raise _error("E0-MCALP refs changed during publication")
        try:
            mt._release_publication_guard(guard)
        except Exception as exc:
            raise _error("E0-MCALP publication guard release failed") from exc
        guard = None
        post_release_metadata: dict[Path, os.stat_result] = {}
        for output, expected in (
            (lock_output, lock_bytes),
            (companion_output, companion_bytes),
        ):
            post_release_metadata[output.path] = _validate_owned_output_bytes(
                output,
                expected,
                repo_root=root,
                context="after guard release",
            )
        _require_physical_snapshot(
            snapshot,
            scientific_inventory=scientific_inventory,
            repo_root=root,
            context="after guard release",
        )
        publication_set = (
            (lock_output, lock_bytes),
            (companion_output, companion_bytes),
        )
        for pass_index in (1, 2):
            for output, expected in publication_set:
                final_metadata = _validate_owned_output_bytes(
                    output,
                    expected,
                    repo_root=root,
                    context=(
                        "joint ownership transfer pass " + str(pass_index)
                    ),
                )
                before = post_release_metadata[output.path]
                if (
                    final_metadata.st_dev,
                    final_metadata.st_ino,
                    final_metadata.st_mode,
                    final_metadata.st_nlink,
                    final_metadata.st_size,
                    final_metadata.st_mtime_ns,
                    final_metadata.st_ctime_ns,
                ) != (
                    before.st_dev,
                    before.st_ino,
                    before.st_mode,
                    before.st_nlink,
                    before.st_size,
                    before.st_mtime_ns,
                    before.st_ctime_ns,
                ):
                    raise _error(
                        "E0-MCALP owned output changed before ownership transfer"
                    )
            _require_owned_identity_set(
                [output for output, _ in publication_set],
                context="after joint validation pass " + str(pass_index),
            )
        _require_owned_identity_set(
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
        if isinstance(exc, FinalCalibrationPublicationGuardPatchError):
            raise
        raise _error("E0-MCALP lock bundle publication failed") from exc
    finally:
        if guard is not None:
            try:
                mt._release_publication_guard(guard, tolerate_foreign=True)
            except Exception:
                pass
        if committed:
            # The joint identity checkpoint above is the publication
            # linearization point.  Descriptor closure cannot revoke that
            # durable success; a close error is therefore non-fatal and the
            # short-lived locker process remains the final cleanup backstop.
            for output in reversed(published):
                try:
                    _close_owned_output(output)
                except Exception:
                    pass


def _parse_canonical_json_with_metadata(
    path: Path, *, repo_root: Path
) -> tuple[dict[str, Any], bytes, os.stat_result]:
    try:
        payload, metadata = mcal._read_regular_bytes_and_metadata(
            path, repo_root=repo_root
        )
        value = mcal._parse_json_bytes(payload, context=path.as_posix())
    except Exception as exc:
        raise _error(f"E0-MCALP published JSON is absent: {path.as_posix()}") from exc
    if not isinstance(value, dict) or payload != _canonical_json_bytes(value):
        raise _error(f"E0-MCALP published JSON is not canonical: {path.as_posix()}")
    return value, payload, metadata


def _parse_canonical_json(path: Path, *, repo_root: Path) -> dict[str, Any]:
    value, _, _ = _parse_canonical_json_with_metadata(path, repo_root=repo_root)
    return value


def _published_h_state(h_head: str, *, repo_root: Path) -> dict[str, Any]:
    if h_head == BASE_H_MCAL_COMMIT or SHA1_RE.fullmatch(h_head) is None:
        raise _error("E0-MCALP published H commit is absent")
    if (
        mcal._single_parent(repo_root, h_head, context="H-E0-MCALP")
        != BASE_H_MCAL_COMMIT
    ):
        raise _error("E0-MCALP published H parent drifted")
    scope = mcal._git_scope(repo_root, BASE_H_MCAL_COMMIT, h_head)
    expected_scope = {
        "added": 5,
        "modified": 4,
        "deleted": 0,
        "path_count": 9,
        "paths": list(PATCH_PATHS),
    }
    if scope != expected_scope:
        raise _error("E0-MCALP published H scope drifted")
    components = [
        mcal._git_artifact_record(
            Path(path),
            role="final_calibration_publication_guard_patch_component",
            repo_root=repo_root,
            commit=h_head,
        )
        for path in PATCH_PATHS
    ]
    repository = {
        "base_h_mcal_commit": BASE_H_MCAL_COMMIT,
        "h_patch_head": h_head,
        "branch": "main",
        "remote_head": h_head,
        "scope": scope,
    }
    h_patch = {
        "gate": "H-E0-MCALP",
        "component_count": 9,
        "added_count": 5,
        "modified_count": 4,
        "components": components,
        "components_sha256": mcal._digest_records(components),
    }
    state = _state_for_h(
        repository=repository,
        h_patch=h_patch,
        repo_root=repo_root,
        require_empty_namespace=False,
    )
    state.pop("base_r_mze_authority")
    return state


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
        raise _error("E0-MCALP published authorizations drifted")
    repository = payload.get("repository")
    if not isinstance(repository, Mapping) or not isinstance(
        repository.get("h_patch_head"), str
    ):
        raise _error("E0-MCALP published H binding is absent")
    state = _published_h_state(str(repository["h_patch_head"]), repo_root=repo_root)
    expected = build_final_calibration_publication_guard_patch_lock_payload(
        state,
        cast(Mapping[str, Any], payload["verification"]),
        generated_at_utc=cast(str, payload["generated_at_utc"]),
    )
    if _canonical_json_bytes(payload) != _canonical_json_bytes(expected):
        raise _error("E0-MCALP published lock reconstruction drifted")


def _validate_p_publication(
    payload: Mapping[str, Any], *, verify_remote: bool, repo_root: Path
) -> dict[str, str]:
    if type(verify_remote) is not bool:
        raise _error("E0-MCALP remote policy must be an exact boolean")
    repository = cast(Mapping[str, Any], payload["repository"])
    h_head = cast(str, repository["h_patch_head"])
    head = mcal._git_head(repo_root)
    if (
        cast(str, mcal._git(repo_root, "branch", "--show-current")).strip()
        != "main"
        or mcal._single_parent(repo_root, head, context="P-E0-MCALP") != h_head
        or mcal._git_scope(repo_root, h_head, head)
        != {
            "added": 2,
            "modified": 0,
            "deleted": 0,
            "path_count": 2,
            "paths": sorted(FINAL_CALIBRATION_P_STAGED_SCOPE),
        }
    ):
        raise _error("E0-MCALP published P topology drifted")
    tracking = mcal._git_head(repo_root, "origin/main")
    remote = mcal._live_remote_main_head(repo_root) if verify_remote else tracking
    if tracking != head or remote != head:
        raise _error("E0-MCALP published P refs drifted")
    for path in (DEFAULT_PATCH_LOCK_PATH, DEFAULT_PATCH_LOCK_MANIFEST_PATH):
        physical = mcal._read_regular_bytes(path, repo_root=repo_root)
        mode, _ = mcal._git_mode_oid(repo_root, head, path)
        if mode != "100644" or physical != mcal._git_blob_bytes(repo_root, head, path):
            raise _error(
                f"E0-MCALP published P physical/Git binding drifted: {path.as_posix()}"
            )
    return {"h_patch_head": h_head, "p_patch_head": head, "remote_head": remote}


def _effective_authority_binding_sha256(
    *,
    repo_root: Path,
    scientific_inventory: Mapping[str, Any],
    p_patch_head: str | None = None,
    lock_record: Mapping[str, Any] | None = None,
) -> str:
    effective_head = (
        mcal._git_head(repo_root) if p_patch_head is None else p_patch_head
    )
    effective_lock = (
        mcal._file_record(
            DEFAULT_PATCH_LOCK_PATH,
            role="final_calibration_publication_guard_patch_lock",
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


def _require_static_effective_boundary(*, repo_root: Path) -> None:
    missing = [
        path.as_posix()
        for path in (DEFAULT_PATCH_LOCK_PATH, DEFAULT_PATCH_LOCK_MANIFEST_PATH)
        if not mcal._entry_exists(path, repo_root=repo_root)
    ]
    if missing:
        raise _error(f"E0-MCALP effective P authority is absent: {missing}")
    forbidden = (
        mcal.DEFAULT_PATCH_LOCK_PATH,
        mcal.DEFAULT_PATCH_LOCK_MANIFEST_PATH,
        mcal._temporary_path(mcal.DEFAULT_PATCH_LOCK_PATH),
        mcal._temporary_path(mcal.DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        mcal.LOCKER_GUARD_PATH,
        mcal._temporary_path(DEFAULT_PATCH_LOCK_PATH),
        mcal._temporary_path(DEFAULT_PATCH_LOCK_MANIFEST_PATH),
        LOCKER_GUARD_PATH,
    )
    occupied = [
        path.as_posix()
        for path in forbidden
        if mcal._entry_exists(path, repo_root=repo_root)
    ]
    if occupied:
        raise _error(f"E0-MCALP effective P namespace drifted: {occupied}")
    if mcal._entry_exists(Path(mcal.mze.OUTCOME_ACCESS_LOG), repo_root=repo_root):
        raise _error("E0-MCALP outcome access log appeared")
    if any(
        mcal._entry_exists(Path(path), repo_root=repo_root)
        for path in mcal.mze.E0_M_PATHS
    ):
        raise _error("E0-MCALP final E0-M outputs appeared")


def _scientific_input_inventory(*, repo_root: Path) -> dict[str, Any]:
    return mcal._scientific_input_inventory(repo_root=repo_root)


def _validate_calibrator_specs(
    value: Any,
) -> dict[tuple[str, int, int], Mapping[str, Any]]:
    """Adapt only the authority token, then reuse the sealed strict parser."""

    if not isinstance(value, Mapping) or value.get("gate") != PATCH_GATE:
        raise _error("E0-MCALP calibrator spec gate drifted")
    adapted = _deep_copy(value)
    adapted["gate"] = "E0-MCAL"
    try:
        return mcal._validate_calibrator_specs(adapted)
    except mcal.FinalCalibrationError as exc:
        raise _error(str(exc).replace("E0-MCAL", "E0-MCALP")) from exc


def _require_exact_output_group(
    paths: Sequence[Path],
    *,
    manifest_path: Path,
    repo_root: Path,
    context: str,
) -> int:
    """Validate one R group with MCALP bindings and sealed MCAL semantics."""

    present = [
        path for path in paths if mcal._entry_exists(path, repo_root=repo_root)
    ]
    if present and len(present) != len(paths):
        raise _error(f"E0-MCALP {context} output bundle is partial")
    if not present:
        return 0
    payloads: dict[Path, bytes] = {}
    metadata: dict[Path, os.stat_result] = {}
    json_values: dict[Path, Any] = {}
    for path in paths:
        payload, observed_metadata = mcal._read_regular_bytes_and_metadata(
            path, repo_root=repo_root
        )
        payloads[path] = payload
        metadata[path] = observed_metadata
        if path.suffix == ".json":
            value = mcal._parse_json_bytes(payload, context=path.as_posix())
            if payload != _canonical_json_bytes(value):
                raise _error(
                    f"E0-MCALP {context} JSON output is not canonical: "
                    f"{path.as_posix()}"
                )
            json_values[path] = value
    manifest = json_values.get(manifest_path)
    if not isinstance(manifest, Mapping):
        raise _error(f"E0-MCALP {context} manifest is absent")
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
        raise _error(f"E0-MCALP {context} manifest output bindings drifted")
    inventory = _scientific_input_inventory(repo_root=repo_root)
    expected_authority_sha256 = _effective_authority_binding_sha256(
        repo_root=repo_root, scientific_inventory=inventory
    )
    common_boundary = {
        "development_only": True,
        "holdout_accessed": False,
        "post_2021_rows_accessed": False,
        "final_evaluation_run": False,
        "future_outcomes_accessed": False,
    }
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
            or manifest.get("scientific_boundary") != common_boundary
            or manifest.get("authority_sha256") != expected_authority_sha256
            or not isinstance(manifest.get("execution_policy"), Mapping)
        ):
            raise _error("E0-MCALP calibration manifest scientific dialect drifted")
        evidence = manifest.get("input_filter_evidence")
        if not isinstance(evidence, list):
            raise _error("E0-MCALP calibration input-filter evidence is absent")
        try:
            mcal._validate_calibration_filter_evidence(evidence)
        except mcal.FinalCalibrationError as exc:
            raise _error(str(exc).replace("E0-MCAL", "E0-MCALP")) from exc
        target_evidence = [
            record
            for record in evidence
            if isinstance(record, Mapping)
            and record.get("role") == "target_predicate_scan"
        ]
        if len(target_evidence) != 1 or (
            target_evidence[0].get("scanner")
            != "pyarrow_dataset_anchored_fd_predicate_pushdown"
            or target_evidence[0].get("predicate")
            != (
                "source_id=wqp AND site_id IN development AND "
                "origin<=2021-12 AND 2019-01<=target<=2021-12"
            )
            or target_evidence[0].get("boundary_crossing_rows") != 0
            or target_evidence[0].get("holdout_rows_materialized") != 0
            or str(target_evidence[0].get("maximum_origin_year_month"))
            > "2021-12"
            or str(target_evidence[0].get("maximum_target_year_month"))
            > "2021-12"
        ):
            raise _error("E0-MCALP target predicate scan evidence drifted")
        execution_policy = cast(Mapping[str, Any], manifest["execution_policy"])
        if (
            set(execution_policy)
            != {
                "torch_cpu_execution_policy",
                "development_runtime_schema_version",
                "development_runtime_audit_sha256",
                "threadpool_limit",
            }
            or execution_policy.get("threadpool_limit") != 1
            or execution_policy.get("development_runtime_schema_version")
            != mcal.EXPECTED_DEVELOPMENT_RUNTIME_SCHEMA_VERSION
            or execution_policy.get("development_runtime_audit_sha256")
            != mcal.EXPECTED_DEVELOPMENT_RUNTIME_AUDIT_SHA256
        ):
            raise _error("E0-MCALP calibration execution policy drifted")
        try:
            mcal._validate_torch_cpu_execution_policy(
                execution_policy.get("torch_cpu_execution_policy"),
                context="calibration",
            )
        except mcal.FinalCalibrationError as exc:
            raise _error(str(exc).replace("E0-MCAL", "E0-MCALP")) from exc
        calibrators = _validate_calibrator_specs(
            json_values.get(mcal.CALIBRATOR_SPECS_PATH)
        )
        try:
            mcal._validate_calibration_csv_outputs(
                payloads, calibrators=calibrators
            )
        except mcal.FinalCalibrationError as exc:
            raise _error(str(exc).replace("E0-MCAL", "E0-MCALP")) from exc
    elif context == "E7":
        expected_keys = {
            "schema_version",
            "experiment_id",
            "gate",
            "status",
            "authority_sha256",
            "terminal_row_count",
            "completed_slot_count",
            "resource_failure_count",
            "completed_module_fit_count",
            "new_e7_fit_count",
            "primary_fit_reuse_count",
            "primary_slots_untouched",
            "saturation_claim_authorized",
            "post_hoc_substitution_performed",
            "silent_omission",
            "slot_order",
            "terminal_evidence",
            "inputs",
            "outputs",
            "scientific_boundary",
        }
        expected_slot_order = [
            {"training_rows_per_module": size, "base_seed": seed}
            for size in (4096, 16384, 65536)
            for seed in mcal.REGISTERED_SEEDS
        ]
        expected_terminal = {
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
        if (
            set(manifest) != expected_keys
            or manifest.get("schema_version")
            != "closure_anfis_learning_curve_manifest_v1"
            or manifest.get("experiment_id") != "E7"
            or manifest.get("gate") != PATCH_GATE
            or manifest.get("status") != "terminal"
            or any(
                manifest.get(key) != value
                for key, value in expected_terminal.items()
            )
            or manifest.get("slot_order") != expected_slot_order
            or manifest.get("inputs") != inventory["e7_required_inputs"]
            or manifest.get("scientific_boundary") != common_boundary
            or manifest.get("authority_sha256") != expected_authority_sha256
            or not isinstance(manifest.get("terminal_evidence"), Mapping)
        ):
            raise _error("E0-MCALP E7 manifest scientific dialect drifted")
        terminal_evidence = cast(Mapping[str, Any], manifest["terminal_evidence"])
        if any(
            terminal_evidence.get(key) != value
            for key, value in expected_terminal.items()
        ) or not isinstance(
            terminal_evidence.get("sample_evidence"), list
        ) or len(cast(list[Any], terminal_evidence["sample_evidence"])) != 45:
            raise _error("E0-MCALP E7 terminal evidence drifted")
        execution_policy = terminal_evidence.get("execution_policy")
        if (
            not isinstance(execution_policy, Mapping)
            or set(execution_policy)
            != {"torch_cpu_execution_policy", "threadpool_limit"}
            or execution_policy.get("threadpool_limit") != 1
        ):
            raise _error("E0-MCALP E7 execution policy drifted")
        try:
            mcal._validate_torch_cpu_execution_policy(
                execution_policy.get("torch_cpu_execution_policy"), context="E7"
            )
            mcal._validate_e7_csv_output(
                payloads[mcal.ANFIS_LEARNING_CURVE_PATH],
                terminal_evidence=terminal_evidence,
            )
        except mcal.FinalCalibrationError as exc:
            raise _error(str(exc).replace("E0-MCAL", "E0-MCALP")) from exc
    else:
        raise _error("E0-MCALP output group context drifted")
    for path in paths:
        payload, observed_metadata = mcal._read_regular_bytes_and_metadata(
            path, repo_root=repo_root
        )
        before = metadata[path]
        if payload != payloads[path] or (
            observed_metadata.st_dev,
            observed_metadata.st_ino,
            observed_metadata.st_mode,
            observed_metadata.st_nlink,
            observed_metadata.st_size,
            observed_metadata.st_mtime_ns,
            observed_metadata.st_ctime_ns,
        ) != (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ):
            raise _error(f"E0-MCALP {context} output changed during validation")
    return len(paths)


def _validate_effective_namespace(*, repo_root: Path) -> dict[str, Any]:
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
        if mcal._entry_exists(path, repo_root=repo_root)
    ]
    if occupied:
        raise _error(
            f"E0-MCALP effective coordination/temporary namespace is occupied: "
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
        raise _error("E0-MCALP R bundle order drifted")
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


@_error_boundary
def load_effective_final_calibration_publication_guard_patch_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    payload, lock_bytes, lock_metadata = _parse_canonical_json_with_metadata(
        DEFAULT_PATCH_LOCK_PATH, repo_root=root
    )
    _validate_published_lock_payload(payload, repo_root=root)
    lock_record = mcal._file_record(
        DEFAULT_PATCH_LOCK_PATH,
        role="final_calibration_publication_guard_patch_lock",
        repo_root=root,
    )
    companion, companion_bytes, companion_metadata = (
        _parse_canonical_json_with_metadata(
        DEFAULT_PATCH_LOCK_MANIFEST_PATH, repo_root=root
        )
    )
    expected_companion = _expected_companion(payload, lock_record)
    if _canonical_json_bytes(companion) != _canonical_json_bytes(expected_companion):
        raise _error("E0-MCALP published companion drifted")
    publication = _validate_p_publication(
        payload, verify_remote=verify_remote, repo_root=root
    )
    _require_static_effective_boundary(repo_root=root)
    namespace = _validate_effective_namespace(repo_root=root)
    scientific_inventory = cast(
        Mapping[str, Any], payload["scientific_input_inventory"]
    )
    base = mcal._base_r_mze_authority(repo_root=root)
    authority_binding_sha256 = _effective_authority_binding_sha256(
        repo_root=root,
        scientific_inventory=scientific_inventory,
        p_patch_head=publication["p_patch_head"],
        lock_record=lock_record,
    )
    lifecycle = cast(str, namespace["r_lifecycle_state"])
    calibration_authorized = lifecycle == "ready_for_calibration_bundle"
    e7_authorized = (
        lifecycle == "calibration_completed_unpublished_ready_for_e7_bundle"
    )
    result = {
        "gate": PATCH_GATE,
        "status": "effective",
        **publication,
        "lock": lock_record,
        "companion": mcal._file_record(
            DEFAULT_PATCH_LOCK_MANIFEST_PATH,
            role="final_calibration_publication_guard_patch_lock_manifest",
            repo_root=root,
        ),
        "authority_binding_sha256": authority_binding_sha256,
        "scientific_input_inventory": _deep_copy(scientific_inventory),
        "calibration_required_inputs": _deep_copy(
            scientific_inventory["calibration_required_inputs"]
        ),
        "calibration_required_inputs_sha256": scientific_inventory[
            "calibration_required_inputs_sha256"
        ],
        "e7_required_inputs": _deep_copy(scientific_inventory["e7_required_inputs"]),
        "e7_required_inputs_sha256": scientific_inventory[
            "e7_required_inputs_sha256"
        ],
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
        "calibration_development_run_authorized": calibration_authorized,
        "e7_learning_curve_run_authorized": e7_authorized,
        "calibration_one_shot_consumed": not calibration_authorized,
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
        or (
            final_lock_metadata.st_dev,
            final_lock_metadata.st_ino,
            final_lock_metadata.st_mode,
            final_lock_metadata.st_nlink,
            final_lock_metadata.st_size,
            final_lock_metadata.st_mtime_ns,
            final_lock_metadata.st_ctime_ns,
        )
        != (
            lock_metadata.st_dev,
            lock_metadata.st_ino,
            lock_metadata.st_mode,
            lock_metadata.st_nlink,
            lock_metadata.st_size,
            lock_metadata.st_mtime_ns,
            lock_metadata.st_ctime_ns,
        )
        or (
            final_companion_metadata.st_dev,
            final_companion_metadata.st_ino,
            final_companion_metadata.st_mode,
            final_companion_metadata.st_nlink,
            final_companion_metadata.st_size,
            final_companion_metadata.st_mtime_ns,
            final_companion_metadata.st_ctime_ns,
        )
        != (
            companion_metadata.st_dev,
            companion_metadata.st_ino,
            companion_metadata.st_mode,
            companion_metadata.st_nlink,
            companion_metadata.st_size,
            companion_metadata.st_mtime_ns,
            companion_metadata.st_ctime_ns,
        )
    ):
        raise _error("E0-MCALP P authority changed during effective loading")
    return result


@_error_boundary
def require_final_calibration_authority(
    *, verify_remote: bool = True, repo_root: Path | None = None
) -> dict[str, Any]:
    return load_effective_final_calibration_publication_guard_patch_authority(
        verify_remote=verify_remote, repo_root=repo_root
    )


@_error_boundary
def require_final_calibration_run_namespace(
    *, runner: str, repo_root: Path | None = None
) -> dict[str, Any]:
    root = _root(repo_root)
    if type(runner) is not str or runner not in {"calibration", "e7"}:
        raise _error("E0-MCALP run namespace requires calibration or e7")
    namespace = _validate_effective_namespace(repo_root=root)
    required_state = (
        "ready_for_calibration_bundle"
        if runner == "calibration"
        else "calibration_completed_unpublished_ready_for_e7_bundle"
    )
    if namespace["r_lifecycle_state"] != required_state:
        raise _error(f"E0-MCALP {runner} one-shot namespace is not ready")
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
    """Delegate unchanged scientific/runtime surfaces to sealed E0-MCAL."""

    return getattr(mcal, name)
