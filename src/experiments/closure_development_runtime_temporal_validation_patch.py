#!/usr/bin/env python
"""Validate the additive Closure V1 temporal provenance patch authority.

E0-DLTV preserves the published P-DLT authority and immutable P0 sequence
bundle.  It separates the builder bytes recorded by that historical artifact
from the current builder bytes imported by the temporal consumer.  It never
authorizes evaluation, E0-U, holdout, or post-2021 outcome access.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from src.experiments.closure_contract import ClosureContractError, validate_json_schema
from src.experiments import closure_development_runtime_temporal_consumer_patch as dlt


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOCK_VERSION = "closure_development_runtime_temporal_validation_patch_lock_v1"
PATCH_GATE = "E0-DLTV"
PATCH_ID = "development_runtime_temporal_sequence_provenance_patch_1"
PATCH_STATUS = "locked"
EXPERIMENT_ID = "closure_v1"
PUBLISHED_REF = "origin/main"

DLT_PATCH_HEAD = "928ee7d17441de93478ad0ad076b76d0afe29de6"
P_DLT_COMMIT = "7ddacf6577f55508f37c5fb627117613efc8cbd3"
PATCH_BASE_COMMIT = P_DLT_COMMIT
P0_BUNDLE_COMMIT = dlt.P0_BUNDLE_COMMIT

DEFAULT_DLT_LOCK_PATH = dlt.DEFAULT_PATCH_LOCK_PATH
DEFAULT_DLT_MANIFEST_PATH = dlt.DEFAULT_PATCH_MANIFEST_PATH
DEFAULT_DLT_SCHEMA_PATH = dlt.DEFAULT_PATCH_LOCK_SCHEMA
DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/development_runtime_temporal_validation_patch_lock.json"
)
DEFAULT_PATCH_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "development_runtime_temporal_validation_patch_lock_manifest.json"
)
DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/development_runtime_temporal_validation_patch_lock.schema.json"
)

DLT_AUTHORITY_RECORDS = {
    DEFAULT_DLT_LOCK_PATH.as_posix(): {
        "path": DEFAULT_DLT_LOCK_PATH.as_posix(),
        "role": "base_development_runtime_temporal_consumer_patch_lock",
        "bytes": 37_435,
        "sha256": "acde72b2de683b452c99799cbe5024a38397386e806e31469a3ada4a9cd9a0e7",
    },
    DEFAULT_DLT_MANIFEST_PATH.as_posix(): {
        "path": DEFAULT_DLT_MANIFEST_PATH.as_posix(),
        "role": "base_development_runtime_temporal_consumer_patch_companion",
        "bytes": 2_755,
        "sha256": "db69c38b37cf867be2fd738b5f47719e2d248f8a3bd7f219272bc9f9b394b49a",
    },
    DEFAULT_DLT_SCHEMA_PATH.as_posix(): {
        "path": DEFAULT_DLT_SCHEMA_PATH.as_posix(),
        "role": "base_development_runtime_temporal_consumer_patch_schema",
        "bytes": 16_685,
        "sha256": "1a2e2b147a7af90d6c4749dcd4b2954e0fdedd2327c43d0705f020e258699185",
    },
}

SUPERSEDED_COMPONENT_PATHS = (
    "src/experiments/build_closure_pipe_sequences.py",
    "src/experiments/rollout_closure_pipe.py",
    "src/experiments/train_closure_pipe.py",
    "tests/test_build_closure_pipe_sequences.py",
    "tests/test_rollout_closure_pipe.py",
    "tests/test_train_closure_pipe.py",
)
PRESERVED_DLT_COMPONENT_PATHS = (
    "configs/closure_v1/development_runtime_temporal_consumer_patch_lock.schema.json",
    "docs/closure_v1/E0_D_RUNTIME_TEMPORAL_CONSUMER_PATCH_1.md",
    "src/experiments/closure_development_runtime_temporal_consumer_patch.py",
    "src/experiments/lock_closure_development_runtime_temporal_consumer_patch.py",
    "tests/test_closure_development_runtime_temporal_consumer_patch.py",
)

PATCH_COMPONENT_ROLES = {
    "configs/closure_v1/development_runtime_temporal_validation_patch_lock.schema.json": (
        "temporal_validation_patch_lock_schema"
    ),
    "docs/closure_v1/E0_D_RUNTIME_TEMPORAL_VALIDATION_PATCH_1.md": (
        "temporal_validation_patch_protocol"
    ),
    "src/experiments/build_closure_pipe_sequences.py": "sequence_builder_gate_routing",
    "src/experiments/closure_development_runtime_temporal_validation_patch.py": (
        "temporal_validation_patch_validator"
    ),
    "src/experiments/lock_closure_development_runtime_temporal_validation_patch.py": (
        "temporal_validation_patch_locker"
    ),
    "src/experiments/rollout_closure_pipe.py": "rollout_gate_routing",
    "src/experiments/train_closure_pipe.py": "temporal_consumer_provenance_validation",
    "tests/test_build_closure_pipe_sequences.py": "sequence_builder_gate_tests",
    "tests/test_closure_development_runtime_temporal_validation_patch.py": (
        "temporal_validation_patch_tests"
    ),
    "tests/test_rollout_closure_pipe.py": "rollout_gate_tests",
    "tests/test_train_closure_pipe.py": "temporal_consumer_provenance_tests",
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))
PATCH_ADDED_PATHS = tuple(
    path for path in PATCH_PATHS if path not in SUPERSEDED_COMPONENT_PATHS
)

P0_ARTIFACT_BUILDER_RECORD = {
    "path": "src/experiments/build_closure_pipe_sequences.py",
    "bytes": 110_034,
    "sha256": "dc500d94c8ca4b3705d2cb849a037524e33915624cd86f9d355e5c4eebb347f6",
}

PATCH_CORRECTION = {
    "classification": "implementation_provenance_validation_only",
    "scientific_runtime_contract_changed": False,
    "seed_set_changed": False,
    "denominator_changed": False,
    "state_mapping_changed": False,
    "model_unavailable_semantics_changed": False,
    "historical_artifact_builder_policy": "git_blob_at_p0_bundle_commit",
    "current_runtime_builder_policy": "physical_bytes_at_h_dltv_head",
    "builder_domains_separated": True,
    "failed_attempt_classification": "technical_pre_parquet_pre_output",
    "expected_p0_slot_status": "model_unavailable",
    "expected_p0_fit_status": "not_attempted",
    "expected_p0_failure_reason": "sequence_fit_rows_unavailable",
    "failed_slot_replacement": False,
}
PATCH_AUTHORIZATIONS = {
    "development_fit_authorized": True,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
    "future_outcomes_accessed": False,
}
PATCH_SEALS = {
    "base_e0_dlt_preserved_as_historical_authority": True,
    "p0_sequence_bundle_preserved": True,
    "p0_artifact_manifest_rewritten": False,
    "holdout_accessed": False,
    "post_2021_outcomes_accessed": False,
    "does_not_replace_e0_m": True,
}

TYPE_CHECK_COMMAND = (".venv/bin/ty", "check")
FOCUSED_TEST_COMMAND = (
    ".venv/bin/pytest",
    "tests/test_closure_development_runtime_sequence_patch.py",
    "tests/test_build_closure_pipe_sequences.py",
    "tests/test_train_closure_pipe.py",
    "tests/test_rollout_closure_pipe.py",
    "tests/test_closure_development_runtime_temporal_consumer_patch.py",
    "tests/test_closure_development_runtime_temporal_validation_patch.py",
    "-q",
)
# Finalized from the exact closed collection after all six H-DLTV modifications.
FOCUSED_TEST_COUNT = 175
POETRY_CHECK_COMMAND = ("poetry", "check")
PUBLICATION_GUARD_COMMAND = ("scripts/check_repo_publication_ready.sh",)
DIFF_CHECK_COMMAND = ("git", "diff", "--check")
DVC_PUSH_COMMAND = dlt.DVC_PUSH_COMMAND

COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class DevelopmentRuntimeTemporalValidationPatchError(RuntimeError):
    """Raised when the additive E0-DLTV authority is not exact."""


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return dlt._canonical_json(payload)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _path_digest(paths: Sequence[str]) -> str:
    return dlt._path_digest(paths)


def _record_digest(records: Sequence[Mapping[str, Any]]) -> str:
    return dlt._record_digest(records)


def _file_record(path: Path, *, role: str) -> dict[str, Any]:
    return dlt._file_record(path, role=role)


def _load_regular_json(path: Path, *, context: str) -> dict[str, Any]:
    return dlt._load_regular_json(path, context=context)


def _git(*args: str) -> str:
    return dlt._git(*args)


def _require_commit(value: str, *, context: str) -> str:
    try:
        return dlt._require_commit(value, context=context)
    except dlt.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise DevelopmentRuntimeTemporalValidationPatchError(str(exc)) from exc


def _git_blob(commit: str, path: str) -> bytes | None:
    return dlt._git_blob(commit, path)


def _assert_record_at_commit(record: Mapping[str, Any], commit: str) -> None:
    path = str(record.get("path", ""))
    blob = _git_blob(commit, path)
    if (
        blob is None
        or len(blob) != record.get("bytes")
        or _sha256_bytes(blob) != record.get("sha256")
    ):
        raise DevelopmentRuntimeTemporalValidationPatchError(
            f"Historical Git component drifted: {path}"
        )


def _record_without_role(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": record.get("path"),
        "bytes": record.get("bytes"),
        "sha256": record.get("sha256"),
    }


def _observed_diff_entries(base: str, head: str) -> list[dict[str, str]]:
    try:
        return dlt._observed_diff_entries(base, head)
    except dlt.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise DevelopmentRuntimeTemporalValidationPatchError(str(exc)) from exc


def _assert_paths_untouched(
    base: str,
    descendant: str,
    paths: Sequence[str],
    *,
    context: str,
) -> None:
    try:
        dlt._assert_paths_untouched(base, descendant, paths, context=context)
    except dlt.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise DevelopmentRuntimeTemporalValidationPatchError(str(exc)) from exc


def patch_git_diff_payload(patch_head: str) -> dict[str, Any]:
    patch_head = _require_commit(patch_head, context="H-DLTV")
    ancestry = _git("rev-list", "--parents", "-n", "1", patch_head).split()
    if ancestry != [patch_head, PATCH_BASE_COMMIT]:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "H-DLTV must be a direct non-merge child of published P-DLT"
        )
    expected = [
        {
            "status": "M" if path in SUPERSEDED_COMPONENT_PATHS else "A",
            "path": path,
        }
        for path in PATCH_PATHS
    ]
    observed = _observed_diff_entries(PATCH_BASE_COMMIT, patch_head)
    if observed != expected:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            f"H-DLTV diff differs from its closed allowlist: {observed}"
        )
    return {
        "base_commit": PATCH_BASE_COMMIT,
        "patch_head": patch_head,
        "entries": expected,
        "paths": list(PATCH_PATHS),
        "paths_sha256": _path_digest(PATCH_PATHS),
        "only_allowed_additions_and_modifications": True,
    }


def patch_component_bundle(patch_head: str) -> dict[str, Any]:
    patch_head = _require_commit(patch_head, context="H-DLTV")
    records: list[dict[str, Any]] = []
    for path in PATCH_PATHS:
        blob = _git_blob(patch_head, path)
        if blob is None:
            raise DevelopmentRuntimeTemporalValidationPatchError(
                f"H-DLTV component is absent: {path}"
            )
        records.append(
            {
                "path": path,
                "role": PATCH_COMPONENT_ROLES[path],
                "bytes": len(blob),
                "sha256": _sha256_bytes(blob),
            }
        )
    return {
        "count": len(records),
        "paths": list(PATCH_PATHS),
        "paths_sha256": _path_digest(PATCH_PATHS),
        "records": records,
        "records_sha256": _record_digest(records),
    }


def partition_dlt_component_records(
    records: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_path = {str(record.get("path")): dict(record) for record in records}
    expected = set(SUPERSEDED_COMPONENT_PATHS).union(PRESERVED_DLT_COMPONENT_PATHS)
    if set(by_path) != expected or len(by_path) != len(records):
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "P-DLT component paths differ from the closed 6+5 partition"
        )
    return (
        [by_path[path] for path in SUPERSEDED_COMPONENT_PATHS],
        [by_path[path] for path in PRESERVED_DLT_COMPONENT_PATHS],
    )


def _validate_p0_artifact_builder_provenance(
    dlt_payload: Mapping[str, Any],
) -> dict[str, Any]:
    builder_path = str(P0_ARTIFACT_BUILDER_RECORD["path"])
    blob = _git_blob(P0_BUNDLE_COMMIT, builder_path)
    if (
        blob is None
        or len(blob) != P0_ARTIFACT_BUILDER_RECORD["bytes"]
        or _sha256_bytes(blob) != P0_ARTIFACT_BUILDER_RECORD["sha256"]
    ):
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "P0 artifact builder Git blob drifted"
        )

    manifest = _load_regular_json(dlt.P0_MANIFEST_PATH, context="P0 sequence manifest")
    expected = dict(P0_ARTIFACT_BUILDER_RECORD)
    if manifest.get("script") != expected or manifest.get("source_code") != [expected]:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "P0 manifest does not bind the historical artifact builder"
        )
    inputs = manifest.get("inputs")
    if not isinstance(inputs, list):
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "P0 manifest inputs are malformed"
        )
    builder_inputs = [
        record
        for record in inputs
        if isinstance(record, Mapping)
        and record.get("path") == P0_ARTIFACT_BUILDER_RECORD["path"]
    ]
    if builder_inputs != [expected]:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "P0 manifest input does not bind the historical artifact builder"
        )

    base_authority = dlt_payload.get("base_authority")
    if not isinstance(base_authority, Mapping):
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "P-DLT base authority is malformed"
        )
    superseded = base_authority.get("superseded_components")
    if not isinstance(superseded, Mapping):
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "P-DLT superseded component authority is malformed"
        )
    records = superseded.get("historical_records")
    if not isinstance(records, list):
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "P-DLT superseded records are malformed"
        )
    locked = [
        record
        for record in records
        if isinstance(record, Mapping)
        and record.get("path") == P0_ARTIFACT_BUILDER_RECORD["path"]
    ]
    if len(locked) != 1 or _record_without_role(locked[0]) != expected:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "P-DLT does not independently anchor the P0 artifact builder"
        )
    return {
        "artifact_commit": P0_BUNDLE_COMMIT,
        "p0_artifact_builder_record": expected,
        "git_blob_verified": True,
        "p_dlt_authority_verified": True,
        "manifest_script_verified": True,
        "manifest_source_code_verified": True,
        "manifest_input_verified": True,
        "manifest_trusted_as_authority": False,
    }


def _current_runtime_builder_record(patch_head: str) -> dict[str, Any]:
    path = str(P0_ARTIFACT_BUILDER_RECORD["path"])
    blob = _git_blob(patch_head, path)
    if blob is None:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "Current H-DLTV runtime builder is absent"
        )
    record = {"path": path, "bytes": len(blob), "sha256": _sha256_bytes(blob)}
    physical = _file_record(Path(path), role="current_runtime_builder")
    if _record_without_role(physical) != record:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "Current runtime builder differs from H-DLTV Git bytes"
        )
    if record == P0_ARTIFACT_BUILDER_RECORD:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "Historical artifact and current runtime builder domains were not separated"
        )
    return record


def _historical_dlt_authority(*, require_physical_artifacts: bool) -> dict[str, Any]:
    parent = _git("rev-list", "--parents", "-n", "1", P_DLT_COMMIT).split()
    if parent != [P_DLT_COMMIT, DLT_PATCH_HEAD]:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "P-DLT must remain a direct child of H-DLT"
        )
    expected_diff = [
        {"status": "A", "path": DEFAULT_DLT_LOCK_PATH.as_posix()},
        {"status": "A", "path": DEFAULT_DLT_MANIFEST_PATH.as_posix()},
    ]
    if _observed_diff_entries(DLT_PATCH_HEAD, P_DLT_COMMIT) != expected_diff:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "P-DLT Git scope drifted"
        )

    records: list[dict[str, Any]] = []
    for path, expected in DLT_AUTHORITY_RECORDS.items():
        physical = _file_record(Path(path), role=str(expected["role"]))
        if physical != expected:
            raise DevelopmentRuntimeTemporalValidationPatchError(
                f"P-DLT authority component drifted: {path}"
            )
        _assert_record_at_commit(physical, P_DLT_COMMIT)
        records.append(physical)

    lock = _load_regular_json(DEFAULT_DLT_LOCK_PATH, context="P-DLT lock")
    schema = _load_regular_json(DEFAULT_DLT_SCHEMA_PATH, context="P-DLT schema")
    try:
        dlt.validate_development_runtime_temporal_consumer_patch_lock_payload(
            lock,
            schema,
            require_physical_artifacts=require_physical_artifacts,
        )
    except dlt.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise DevelopmentRuntimeTemporalValidationPatchError(str(exc)) from exc
    companion_lock_record = _file_record(
        DEFAULT_DLT_LOCK_PATH,
        role="external_development_runtime_temporal_consumer_patch_lock",
    )
    companion = _load_regular_json(DEFAULT_DLT_MANIFEST_PATH, context="P-DLT companion")
    if companion != dlt._expected_companion(
        lock,
        lock_record=companion_lock_record,
    ):
        raise DevelopmentRuntimeTemporalValidationPatchError("P-DLT companion drifted")

    components = lock.get("patch_components")
    if not isinstance(components, Mapping) or not isinstance(components.get("records"), list):
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "P-DLT component bundle is malformed"
        )
    superseded, preserved = partition_dlt_component_records(
        cast(list[Mapping[str, Any]], components["records"])
    )
    for record in (*superseded, *preserved):
        _assert_record_at_commit(record, DLT_PATCH_HEAD)
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    for record in preserved:
        physical = _file_record(Path(str(record["path"])), role=str(record["role"]))
        if physical != record:
            raise DevelopmentRuntimeTemporalValidationPatchError(
                f"Preserved H-DLT component drifted: {record['path']}"
            )
        _assert_record_at_commit(record, execution_head)
    _assert_paths_untouched(
        P_DLT_COMMIT,
        execution_head,
        (DEFAULT_DLT_LOCK_PATH.as_posix(), DEFAULT_DLT_MANIFEST_PATH.as_posix()),
        context="P-DLT publication",
    )
    provenance = _validate_p0_artifact_builder_provenance(lock)
    return {
        "patch_head": DLT_PATCH_HEAD,
        "lock_commit": P_DLT_COMMIT,
        "records": records,
        "records_sha256": _record_digest(records),
        "superseded_components": {
            "count": len(superseded),
            "paths": list(SUPERSEDED_COMPONENT_PATHS),
            "records": superseded,
            "records_sha256": _record_digest(superseded),
            "current_bytes_required_to_match_h_dlt": False,
        },
        "preserved_components": {
            "count": len(preserved),
            "paths": list(PRESERVED_DLT_COMPONENT_PATHS),
            "records": preserved,
            "records_sha256": _record_digest(preserved),
            "current_bytes_required_to_match_h_dlt": True,
        },
        "nested_base_authority": lock["base_authority"],
        "p0_bundle": lock["base_authority"]["p0_bundle"],
        "p0_artifact_builder_provenance": provenance,
        "historical_lock_verified": True,
        "historical_companion_verified": True,
        "future_outcomes_accessed": False,
    }


def _remote_main_oid() -> str:
    try:
        return dlt._remote_main_oid()
    except dlt.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise DevelopmentRuntimeTemporalValidationPatchError(str(exc)) from exc


def collect_temporal_validation_patch_prelock_state(
    *,
    require_physical_artifacts: bool,
    verify_remote: bool,
) -> dict[str, Any]:
    status = _git("status", "--porcelain", "--untracked-files=all")
    if status:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            f"H-DLTV lock requires a clean worktree: {status}"
        )
    head = _require_commit(_git("rev-parse", "HEAD"), context="H-DLTV HEAD")
    if _git("branch", "--show-current") != "main":
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "H-DLTV lock requires branch main"
        )
    published = _require_commit(_git("rev-parse", PUBLISHED_REF), context=PUBLISHED_REF)
    if published != head:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "H-DLTV HEAD differs from origin/main"
        )
    remote = _remote_main_oid() if verify_remote else published
    if remote != head:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "H-DLTV HEAD differs from live origin/main"
        )
    authority = _historical_dlt_authority(
        require_physical_artifacts=require_physical_artifacts
    )
    historical = dict(P0_ARTIFACT_BUILDER_RECORD)
    current = _current_runtime_builder_record(head)
    return {
        "patch_repository": {
            "head": head,
            "parent": PATCH_BASE_COMMIT,
            "branch": "main",
            "published_ref": PUBLISHED_REF,
            "published_head": published,
            "remote_main_oid": remote,
            "worktree_status": "clean",
            "exact_diff_verified": True,
        },
        "git_diff": patch_git_diff_payload(head),
        "patch_components": patch_component_bundle(head),
        "base_authority": authority,
        "builder_provenance": {
            "p0_artifact_builder_record": historical,
            "current_runtime_builder_record": current,
            "records_are_distinct": True,
            "historical_record_source": "git_blob_at_p0_bundle_commit",
            "runtime_record_source": "physical_bytes_at_h_dltv_head",
        },
        "consumer_prelock": dlt.consumer_namespace_absence(),
    }


def _validate_command_evidence(
    value: Any,
    command: Sequence[str],
    *,
    context: str,
) -> None:
    if not isinstance(value, Mapping) or value.get("command") != list(command):
        raise DevelopmentRuntimeTemporalValidationPatchError(
            f"E0-DLTV {context} command drifted"
        )
    if value.get("returncode") != 0:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            f"E0-DLTV {context} did not pass"
        )
    for field in ("stdout_sha256", "stderr_sha256"):
        digest = value.get(field)
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise DevelopmentRuntimeTemporalValidationPatchError(
                f"E0-DLTV {context} {field} drifted"
            )
    for field in ("stdout_line_count", "stderr_line_count"):
        if type(value.get(field)) is not int or value[field] < 0:
            raise DevelopmentRuntimeTemporalValidationPatchError(
                f"E0-DLTV {context} {field} drifted"
            )


def validate_temporal_validation_patch_verification(payload: Mapping[str, Any]) -> None:
    expected_fields = {
        "full_type_check",
        "focused_tests",
        "poetry_check",
        "publication_guard",
        "git_diff_check",
        "dvc_push_first",
        "dvc_push_second",
    }
    if set(payload) != expected_fields:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "E0-DLTV verification fields drifted"
        )
    commands = {
        "full_type_check": TYPE_CHECK_COMMAND,
        "focused_tests": FOCUSED_TEST_COMMAND,
        "poetry_check": POETRY_CHECK_COMMAND,
        "publication_guard": PUBLICATION_GUARD_COMMAND,
        "git_diff_check": DIFF_CHECK_COMMAND,
        "dvc_push_first": DVC_PUSH_COMMAND,
        "dvc_push_second": DVC_PUSH_COMMAND,
    }
    for key, command in commands.items():
        _validate_command_evidence(payload[key], command, context=key)
    focused = cast(Mapping[str, Any], payload["focused_tests"])
    if (
        focused.get("test_count") != FOCUSED_TEST_COUNT
        or focused.get("skipped_count") != 0
        or focused.get("deselected_count") != 0
    ):
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "E0-DLTV focused-test evidence drifted"
        )
    for key in ("dvc_push_first", "dvc_push_second"):
        if cast(Mapping[str, Any], payload[key]).get("terminal_status") != (
            "Everything is up to date."
        ):
            raise DevelopmentRuntimeTemporalValidationPatchError(
                f"E0-DLTV {key} is not an exact idempotent push"
            )


def build_temporal_validation_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any],
    *,
    created_at_utc: str,
) -> dict[str, Any]:
    return {
        "lock_version": LOCK_VERSION,
        "status": PATCH_STATUS,
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": created_at_utc,
        "patch_repository": dict(cast(Mapping[str, Any], prelock["patch_repository"])),
        "git_diff": dict(cast(Mapping[str, Any], prelock["git_diff"])),
        "patch_components": dict(cast(Mapping[str, Any], prelock["patch_components"])),
        "base_authority": dict(cast(Mapping[str, Any], prelock["base_authority"])),
        "builder_provenance": dict(
            cast(Mapping[str, Any], prelock["builder_provenance"])
        ),
        "consumer_prelock": dict(cast(Mapping[str, Any], prelock["consumer_prelock"])),
        "correction": PATCH_CORRECTION,
        "verification": dict(verification),
        "authorizations": PATCH_AUTHORIZATIONS,
        "seals": PATCH_SEALS,
        "lock_artifact": {
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "role": "external_development_runtime_temporal_validation_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
    }


def validate_development_runtime_temporal_validation_patch_lock_payload(
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    require_physical_artifacts: bool = False,
) -> None:
    try:
        validate_json_schema(
            payload,
            schema,
            instance_path="$.development_runtime_temporal_validation_patch_lock",
        )
    except ClosureContractError as exc:
        raise DevelopmentRuntimeTemporalValidationPatchError(str(exc)) from exc
    fixed = {
        "lock_version": LOCK_VERSION,
        "status": PATCH_STATUS,
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "correction": PATCH_CORRECTION,
        "authorizations": PATCH_AUTHORIZATIONS,
        "seals": PATCH_SEALS,
        "lock_artifact": {
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "role": "external_development_runtime_temporal_validation_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
    }
    for field, expected in fixed.items():
        if payload.get(field) != expected:
            raise DevelopmentRuntimeTemporalValidationPatchError(
                f"E0-DLTV fixed field drifted: {field}"
            )
    created = payload.get("created_at_utc")
    if not isinstance(created, str):
        raise DevelopmentRuntimeTemporalValidationPatchError("E0-DLTV timestamp is invalid")
    try:
        timestamp = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "E0-DLTV timestamp is invalid"
        ) from exc
    if timestamp.utcoffset() is None:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "E0-DLTV timestamp requires a timezone"
        )
    repository = cast(Mapping[str, Any], payload["patch_repository"])
    patch_head = _require_commit(str(repository.get("head", "")), context="locked H-DLTV")
    if repository != {
        "head": patch_head,
        "parent": PATCH_BASE_COMMIT,
        "branch": "main",
        "published_ref": PUBLISHED_REF,
        "published_head": patch_head,
        "remote_main_oid": patch_head,
        "worktree_status": "clean",
        "exact_diff_verified": True,
    }:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "E0-DLTV patch repository record drifted"
        )
    if payload.get("git_diff") != patch_git_diff_payload(patch_head):
        raise DevelopmentRuntimeTemporalValidationPatchError("E0-DLTV Git diff drifted")
    if payload.get("patch_components") != patch_component_bundle(patch_head):
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "E0-DLTV component bundle drifted"
        )
    authority = _historical_dlt_authority(
        require_physical_artifacts=require_physical_artifacts
    )
    if payload.get("base_authority") != authority:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "E0-DLTV historical P-DLT authority drifted"
        )
    expected_provenance = {
        "p0_artifact_builder_record": dict(P0_ARTIFACT_BUILDER_RECORD),
        "current_runtime_builder_record": _current_runtime_builder_record(patch_head),
        "records_are_distinct": True,
        "historical_record_source": "git_blob_at_p0_bundle_commit",
        "runtime_record_source": "physical_bytes_at_h_dltv_head",
    }
    if payload.get("builder_provenance") != expected_provenance:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "E0-DLTV builder provenance drifted"
        )
    expected_absence = {
        "model_id": "P0",
        "base_seeds": list(dlt.REGISTERED_SEEDS),
        "count": len(dlt.temporal_consumer_output_paths()),
        "paths": [dlt._relative(path) for path in dlt.temporal_consumer_output_paths()],
        "paths_sha256": _path_digest(
            [dlt._relative(path) for path in dlt.temporal_consumer_output_paths()]
        ),
        "all_absent_at_lock": True,
    }
    if payload.get("consumer_prelock") != expected_absence:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "E0-DLTV consumer prelock evidence drifted"
        )
    validate_temporal_validation_patch_verification(
        cast(Mapping[str, Any], payload["verification"])
    )


def _expected_companion(
    payload: Mapping[str, Any],
    *,
    lock_record: Mapping[str, Any],
) -> dict[str, Any]:
    components = cast(Mapping[str, Any], payload["patch_components"])
    records = cast(Sequence[Mapping[str, Any]], components["records"])
    by_path = {str(record["path"]): record for record in records}

    def component(path: str, role: str) -> dict[str, Any]:
        record = by_path[path]
        return {
            "path": path,
            "role": role,
            "bytes": record["bytes"],
            "sha256": record["sha256"],
        }

    authority = cast(Mapping[str, Any], payload["base_authority"])
    authority_records = cast(Sequence[Mapping[str, Any]], authority["records"])
    dlt_by_path = {str(record["path"]): record for record in authority_records}
    return {
        "manifest_version": "closure_development_runtime_temporal_validation_patch_manifest_v1",
        "status": "completed",
        "experiment_id": EXPERIMENT_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": payload["created_at_utc"],
        "outputs": [dict(lock_record)],
        "script": component(
            "src/experiments/lock_closure_development_runtime_temporal_validation_patch.py",
            "generating_script",
        ),
        "inputs": [
            dict(dlt_by_path[DEFAULT_DLT_LOCK_PATH.as_posix()]),
            dict(dlt_by_path[DEFAULT_DLT_MANIFEST_PATH.as_posix()]),
            component(
                DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
                "temporal_validation_patch_lock_schema",
            ),
            component(
                "src/experiments/closure_development_runtime_temporal_validation_patch.py",
                "temporal_validation_patch_validator",
            ),
            {
                **dict(P0_ARTIFACT_BUILDER_RECORD),
                "role": "historical_p0_artifact_builder",
            },
        ],
        "development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "authoritative_contract": False,
        "authoritative_lock_path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
    }


def _introduced_commit(path: str) -> str:
    try:
        return dlt._introduced_commit(path)
    except dlt.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise DevelopmentRuntimeTemporalValidationPatchError(str(exc)) from exc


def _validate_publication_bundle(
    payload: Mapping[str, Any],
    *,
    execution_head: str,
    verify_remote: bool,
) -> tuple[str, str]:
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    lock_path = DEFAULT_PATCH_LOCK_PATH.as_posix()
    companion_path = DEFAULT_PATCH_MANIFEST_PATH.as_posix()
    lock_commit = _introduced_commit(lock_path)
    if lock_commit != _introduced_commit(companion_path):
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "P-DLTV lock and companion commits differ"
        )
    ancestry = _git("rev-list", "--parents", "-n", "1", lock_commit).split()
    if ancestry != [lock_commit, patch_head]:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "P-DLTV must be a direct child of H-DLTV"
        )
    expected = [
        {"status": "A", "path": lock_path},
        {"status": "A", "path": companion_path},
    ]
    if _observed_diff_entries(patch_head, lock_commit) != expected:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "P-DLTV must add exactly lock plus companion"
        )
    published = _require_commit(_git("rev-parse", PUBLISHED_REF), context=PUBLISHED_REF)
    if execution_head != published:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "Execution HEAD differs from origin/main"
        )
    remote = _remote_main_oid() if verify_remote else published
    if remote != published:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "Local and live origin/main differ"
        )
    try:
        dlt._require_ancestor(lock_commit, execution_head)
    except dlt.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise DevelopmentRuntimeTemporalValidationPatchError(str(exc)) from exc
    _assert_paths_untouched(
        lock_commit,
        execution_head,
        (lock_path, companion_path),
        context="E0-DLTV publication",
    )
    return lock_commit, published


def load_and_validate_development_runtime_temporal_validation_patch_lock(
    lock_path: Path = DEFAULT_PATCH_LOCK_PATH,
    lock_schema: Path = DEFAULT_PATCH_LOCK_SCHEMA,
    companion_path: Path = DEFAULT_PATCH_MANIFEST_PATH,
    *,
    require_published: bool = True,
    require_physical_artifacts: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if (
        dlt._relative(lock_path) != DEFAULT_PATCH_LOCK_PATH.as_posix()
        or dlt._relative(lock_schema) != DEFAULT_PATCH_LOCK_SCHEMA.as_posix()
        or dlt._relative(companion_path) != DEFAULT_PATCH_MANIFEST_PATH.as_posix()
    ):
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "E0-DLTV requires closed default paths"
        )
    payload = _load_regular_json(lock_path, context="E0-DLTV lock")
    schema = _load_regular_json(lock_schema, context="E0-DLTV schema")
    validate_development_runtime_temporal_validation_patch_lock_payload(
        payload,
        schema,
        require_physical_artifacts=require_physical_artifacts,
    )
    lock_record = _file_record(
        lock_path,
        role="external_development_runtime_temporal_validation_patch_lock",
    )
    companion = _load_regular_json(companion_path, context="E0-DLTV companion")
    if companion != _expected_companion(payload, lock_record=lock_record):
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "E0-DLTV companion drifted"
        )
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    try:
        dlt._require_ancestor(patch_head, execution_head)
    except dlt.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise DevelopmentRuntimeTemporalValidationPatchError(str(exc)) from exc
    component_records = cast(
        Sequence[Mapping[str, Any]],
        cast(Mapping[str, Any], payload["patch_components"])["records"],
    )
    for record in component_records:
        physical = _file_record(Path(str(record["path"])), role=str(record["role"]))
        if physical != record:
            raise DevelopmentRuntimeTemporalValidationPatchError(
                f"Physical H-DLTV component drifted: {record['path']}"
            )
        _assert_record_at_commit(record, execution_head)
    _assert_paths_untouched(
        patch_head,
        execution_head,
        PATCH_PATHS,
        context="E0-DLTV components",
    )
    status = _git("status", "--porcelain", "--untracked-files=all")
    if require_published and status:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            f"E0-DLTV execution requires a clean worktree: {status}"
        )
    if require_published:
        lock_commit, published = _validate_publication_bundle(
            payload,
            execution_head=execution_head,
            verify_remote=require_physical_artifacts,
        )
    else:
        if execution_head != patch_head:
            raise DevelopmentRuntimeTemporalValidationPatchError(
                "Unpublished E0-DLTV validation must run at H-DLTV"
            )
        lock_commit = ""
        published = ""
    effective = require_published and require_physical_artifacts
    provenance = cast(Mapping[str, Any], payload["builder_provenance"])
    summary = {
        "lock_path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "lock_sha256": lock_record["sha256"],
        "lock_version": LOCK_VERSION,
        "status": "locked",
        "gate": PATCH_GATE,
        "patch_head": patch_head,
        "lock_commit": lock_commit or None,
        "execution_head": execution_head,
        "published_ref": PUBLISHED_REF if require_published else None,
        "published_head": published or None,
        "publication_verified": require_published,
        "remote_publication_verified": effective,
        "physical_artifacts_verified": require_physical_artifacts,
        "historical_authority_verified": True,
        "patch_components_verified": True,
        "builder_provenance_verified": True,
        "locked_head_is_ancestor": True,
        "p0_artifact_builder_record": dict(
            cast(Mapping[str, Any], provenance["p0_artifact_builder_record"])
        ),
        "current_runtime_builder_record": dict(
            cast(Mapping[str, Any], provenance["current_runtime_builder_record"])
        ),
        "development_fit_authorized": effective,
        "fit_authorized": effective,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }
    return payload, summary


def require_development_fit_authorized_with_temporal_validation_patch(
    *,
    device: str | None = None,
) -> dict[str, Any]:
    """Fail closed until the additive P-DLTV lock is published."""
    if device is not None and device != "cpu":
        raise DevelopmentRuntimeTemporalValidationPatchError(
            f"E0-DLTV only authorizes the locked CPU device, not {device!r}"
        )
    _, summary = load_and_validate_development_runtime_temporal_validation_patch_lock(
        require_published=True,
        require_physical_artifacts=True,
    )
    required = {
        "publication_verified": True,
        "remote_publication_verified": True,
        "physical_artifacts_verified": True,
        "historical_authority_verified": True,
        "patch_components_verified": True,
        "builder_provenance_verified": True,
        "locked_head_is_ancestor": True,
        "development_fit_authorized": True,
        "fit_authorized": True,
    }
    failed = [field for field, expected in required.items() if summary.get(field) is not expected]
    if failed:
        raise DevelopmentRuntimeTemporalValidationPatchError(
            f"E0-DLTV did not satisfy development-fit predicates: {failed}"
        )
    if (
        summary.get("evaluation_authorized") is not False
        or summary.get("e0_u_authorized") is not False
        or summary.get("future_outcomes_accessed") is not False
    ):
        raise DevelopmentRuntimeTemporalValidationPatchError(
            "E0-DLTV evaluation seals drifted"
        )
    return summary


__all__ = [
    "DEFAULT_PATCH_LOCK_PATH",
    "DEFAULT_PATCH_LOCK_SCHEMA",
    "DEFAULT_PATCH_MANIFEST_PATH",
    "DevelopmentRuntimeTemporalValidationPatchError",
    "FOCUSED_TEST_COMMAND",
    "FOCUSED_TEST_COUNT",
    "P0_ARTIFACT_BUILDER_RECORD",
    "PATCH_ADDED_PATHS",
    "PATCH_COMPONENT_ROLES",
    "PATCH_PATHS",
    "SUPERSEDED_COMPONENT_PATHS",
    "build_temporal_validation_patch_lock_payload",
    "collect_temporal_validation_patch_prelock_state",
    "load_and_validate_development_runtime_temporal_validation_patch_lock",
    "patch_component_bundle",
    "patch_git_diff_payload",
    "require_development_fit_authorized_with_temporal_validation_patch",
    "validate_development_runtime_temporal_validation_patch_lock_payload",
]
