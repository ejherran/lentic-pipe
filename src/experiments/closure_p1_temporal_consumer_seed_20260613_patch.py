#!/usr/bin/env python
"""Validate the additive Closure V1 P1/20260613 temporal-consumer authority.

E0-MK is a fail-closed successor to the published P1/20260613 sequence
bundle.  It reconstructs E0-MI and E0-MJ from immutable Git history, binds
the new sequence auditor without running it during H-E0-MK, and can authorize
only the P1/20260613/CPU consumer after a future two-file P-E0-MK publication.
It never authorizes a fit, builder, retry, DVC mutation, E0-M, E0-U,
evaluation, or outcome access.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from src.experiments import audit_closure_p1_seed_20260613_sequence_bundle as p1_audit
from src.experiments import closure_p1_sequence_seed_20260613_patch as e0_mj
from src.experiments import closure_p1_temporal_consumer_seed_20260612_patch as e0_mi
from src.experiments import closure_contract
from src.experiments.closure_contract import ClosureContractError, validate_json_schema


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOCK_VERSION = "closure_p1_temporal_consumer_seed_20260613_patch_lock_v1"
PATCH_GATE = "E0-MK"
PATCH_ID = "p1_temporal_consumer_seed_20260613_authority_patch_1"
PATCH_STATUS = "locked"
EXPERIMENT_ID = "closure_v1"
SURFACE_ID = "closure_v1_wqp_adaptive_no_current_chla"
PUBLISHED_REF = "origin/main"

AUTHORIZED_MODEL_ID = "P1"
AUTHORIZED_BASE_SEED = 20_260_613
AUTHORIZED_DEVICE = "cpu"

E0_MI_H_COMMIT = "e8efbf800e1b171ba70bd3a863aec64138b6b0fb"
E0_MI_P_COMMIT = "16ee69f8fa923e4b7a9466024d4240b39a1a20d3"
E0_MJ_H_COMMIT = "3b86b75edcfa5d11eab6bb97ab7cfd71df468fab"
E0_MJ_P_COMMIT = "04b3420b60cec62773fb600c85485be396a15654"
P1_1729_CONSUMER_COMMIT = "5d8bbef0fe58e57cd2180570bd6aef5f07923781"
P1_BUNDLE_COMMIT = "a25863c05730d65d0fb3454a608243b2c9eca639"
PATCH_BASE_COMMIT = P1_BUNDLE_COMMIT

DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "p1_temporal_consumer_seed_20260613_patch_lock.json"
)
DEFAULT_PATCH_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "p1_temporal_consumer_seed_20260613_patch_lock_manifest.json"
)
DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/p1_temporal_consumer_seed_20260613_patch_lock.schema.json"
)

PATCH_COMPONENT_ROLES = {
    DEFAULT_PATCH_LOCK_SCHEMA.as_posix(): (
        "p1_temporal_consumer_seed_20260613_patch_lock_schema"
    ),
    "docs/closure_v1/E0_M_P1_TEMPORAL_CONSUMER_SEED_20260613_PATCH_1.md": (
        "p1_temporal_consumer_seed_20260613_patch_protocol"
    ),
    "src/experiments/closure_p1_temporal_consumer_seed_20260613_patch.py": (
        "p1_temporal_consumer_seed_20260613_patch_validator"
    ),
    "src/experiments/lock_closure_p1_temporal_consumer_seed_20260613_patch.py": (
        "p1_temporal_consumer_seed_20260613_patch_locker"
    ),
    "src/experiments/train_closure_pipe.py": "p1_temporal_consumer_mk_gate_routing",
    "tests/test_closure_p1_temporal_consumer_seed_20260613_patch.py": (
        "p1_temporal_consumer_seed_20260613_patch_tests"
    ),
    "tests/test_train_closure_pipe.py": "p1_temporal_consumer_mk_gate_tests",
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))
PATCH_MODIFIED_PATHS = (
    "src/experiments/train_closure_pipe.py",
    "tests/test_train_closure_pipe.py",
)
PATCH_ADDED_PATHS = tuple(
    path for path in PATCH_PATHS if path not in PATCH_MODIFIED_PATHS
)

MI_SUPERSEDED_PATHS = PATCH_MODIFIED_PATHS
MI_PRESERVED_PATHS = tuple(
    path for path in e0_mi.PATCH_PATHS if path not in MI_SUPERSEDED_PATHS
)

FIT_AVAILABILITY = {
    "sequence_fit_available": False,
    "fit_status_counts": {
        "success": 8_925,
        "autoregressive_target_unavailable": 488,
    },
    "fit_failure_reason_counts": {"missing_target_state": 488},
    "calibration_failure_count": 17,
    "expected_slot_status": "model_unavailable",
    "expected_fit_status": "not_attempted",
    "expected_failure_reason": "sequence_fit_rows_unavailable",
    "replacement_used": False,
}
P1_ARTIFACT_BUILDER_RECORD = {
    "path": "src/experiments/build_closure_pipe_sequences.py",
    "bytes": 127_846,
    "sha256": "d1af38a75dc40be60b89f23f9c4aedbea38a300902f81cbc4417fda49567a7b9",
}

PATCH_CORRECTION = {
    "issue_id": "p1_temporal_consumer_next_seed_authority_1",
    "classification": "ordered_seed_progression_authority_only",
    "historical_e0_mi_effective_loader_called": False,
    "historical_e0_mj_effective_loader_called": False,
    "p1_1729_consumer_preserved": True,
    "p1_20260612_sequence_and_consumer_preserved": True,
    "p1_20260613_sequence_bundle_preserved": True,
    "authorized_next_consumer_seed": AUTHORIZED_BASE_SEED,
    "auditor_execution_mode": "in_process_callable",
    "pytest_summary_parser_policy": "pytest_9_0_3_duration_clock_closed_v1",
    "pytest_summary_reference_version": "9.0.3",
    "schema_dialect": "closure_contract_closed_draft_2020_12_subset_v1",
    "closure_contract_modified": False,
    "scientific_runtime_contract_changed": False,
    "denominator_changed": False,
    "model_unavailable_semantics_changed": False,
    "outcome_access_changed": False,
}
PATCH_AUTHORIZATIONS = {
    "authorized_model_id": AUTHORIZED_MODEL_ID,
    "authorized_base_seed": AUTHORIZED_BASE_SEED,
    "authorized_device": AUTHORIZED_DEVICE,
    "p1_consumer_authorized": False,
    "p1_fit_authorized": False,
    "fit_attempt_authorized": False,
    "p1_sequence_builder_authorized": False,
    "dvc_commands_authorized": False,
    "effective_in_payload": False,
    "publication_required": True,
    "batch_seed_execution_authorized": False,
    "retry_authorized": False,
    "replacement_authorized": False,
    "e0_m_authorized": False,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
    "future_outcomes_accessed": False,
}
PATCH_SEALS = {
    "e0_mi_preserved_as_historical_authority": True,
    "e0_mj_preserved_as_historical_authority": True,
    "mi_preserved_component_count": 5,
    "mi_superseded_component_count": 2,
    "mj_preserved_component_count": 7,
    "schema_supported_subset_verified": True,
    "minimum_keyword_absent": True,
    "format_keyword_absent": True,
    "numeric_bounds_validated_semantically": True,
    "timestamp_validated_semantically": True,
    "closure_contract_modified": False,
    "p1_1729_sequence_and_consumer_preserved": True,
    "p1_20260612_sequence_and_consumer_preserved": True,
    "p1_20260613_sequence_bundle_preserved": True,
    "consumer_outputs_absent_at_lock": True,
    "exact_registered_namespace_at_lock": True,
    "prior_p1_residuals_absent_at_lock": True,
    "current_sequence_temps_and_guard_absent_at_lock": True,
    "model_artifact_expected": False,
    "fit_attempt_expected": False,
    "later_seed_namespaces_absent_at_lock": True,
    "holdout_accessed": False,
    "post_2021_outcomes_accessed": False,
    "does_not_replace_e0_m": True,
}

TYPE_CHECK_COMMAND = (".venv/bin/ty", "check")
FOCUSED_TEST_COMMAND = (
    ".venv/bin/pytest",
    "tests/test_closure_p1_temporal_consumer_seed_20260613_patch.py",
    "tests/test_train_closure_pipe.py",
    "tests/test_audit_closure_p1_seed_20260613_sequence_bundle.py",
    "-q",
)
# Exact collection reserved for the future P-E0-MK execute-lock.
FOCUSED_TEST_COUNT = 122
POETRY_CHECK_COMMAND = ("poetry", "check")
PUBLICATION_GUARD_COMMAND = ("scripts/check_repo_publication_ready.sh",)
DIFF_CHECK_COMMAND = ("git", "diff", "--check")
DVC_PUSH_COMMAND = (
    ".venv/bin/dvc",
    "push",
    "data/closure_v1/development/sequences/P1/seed_20260613.parquet.dvc",
)

AUDITOR_MODULE = "src.experiments.audit_closure_p1_seed_20260613_sequence_bundle"
AUDITOR_NAME = "audit_p1_seed_20260613_sequence_bundle"
AUDITOR_QUALNAME = "audit_p1_seed_20260613_sequence_bundle"
AUDITOR_SOURCE_PATH = p1_audit.AUDITOR_PATH.as_posix()


class P1TemporalConsumerSeed20260613PatchError(RuntimeError):
    """Raised when E0-MK cannot prove its closed authority."""


def _translate(error: BaseException) -> P1TemporalConsumerSeed20260613PatchError:
    return P1TemporalConsumerSeed20260613PatchError(str(error))


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_audit_result(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _path_digest(paths: Sequence[str]) -> str:
    return _sha256_bytes("\n".join(paths).encode("utf-8"))


def _record_digest(records: Sequence[Mapping[str, Any]]) -> str:
    return _sha256_bytes(
        json.dumps(
            list(records),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    )


def _git(*args: str) -> str:
    try:
        return e0_mj._git(*args)
    except e0_mj.P1SequenceSeed20260613PatchError as exc:
        raise _translate(exc) from exc


def _require_commit(value: str, *, context: str) -> str:
    try:
        return e0_mj._require_commit(value, context=context)
    except e0_mj.P1SequenceSeed20260613PatchError as exc:
        raise _translate(exc) from exc


def _require_ancestor(ancestor: str, descendant: str) -> None:
    try:
        e0_mj._require_ancestor(ancestor, descendant)
    except e0_mj.P1SequenceSeed20260613PatchError as exc:
        raise _translate(exc) from exc


def _git_blob(commit: str, path: str) -> bytes:
    try:
        return e0_mj._git_blob(commit, path)
    except e0_mj.P1SequenceSeed20260613PatchError as exc:
        raise _translate(exc) from exc


def _git_record(commit: str, path: str, *, role: str) -> dict[str, Any]:
    payload = _git_blob(commit, path)
    return {
        "path": path,
        "role": role,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def _file_record(path: Path, *, role: str) -> dict[str, Any]:
    try:
        return e0_mj._file_record(path, role=role)
    except e0_mj.P1SequenceSeed20260613PatchError as exc:
        raise _translate(exc) from exc


def _load_regular_json(path: Path, *, context: str) -> dict[str, Any]:
    try:
        return e0_mj._load_regular_json(path, context=context)
    except e0_mj.P1SequenceSeed20260613PatchError as exc:
        raise _translate(exc) from exc


def _keyword_occurrences(value: Any, keyword: str) -> int:
    if isinstance(value, Mapping):
        return sum(
            (1 if key == keyword else 0) + _keyword_occurrences(child, keyword)
            for key, child in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return sum(_keyword_occurrences(child, keyword) for child in value)
    return 0


def _assert_schema_definition_supported(schema: Mapping[str, Any]) -> None:
    validator = getattr(closure_contract, "_assert_supported_json_schema", None)
    if not callable(validator):
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK closure-contract schema-definition validator is unavailable"
        )
    try:
        validator(schema)
    except ClosureContractError as exc:
        raise _translate(exc) from exc


def preflight_p1_temporal_consumer_seed_20260613_patch_schema(
    schema_path: Path = DEFAULT_PATCH_LOCK_SCHEMA,
) -> dict[str, Any]:
    """Validate the physical MK schema before guards, commands, or egress."""
    if schema_path != DEFAULT_PATCH_LOCK_SCHEMA:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK schema preflight requires the closed default path"
        )
    schema = _load_regular_json(schema_path, context="E0-MK schema preflight")
    minimum_count = _keyword_occurrences(schema, "minimum")
    format_count = _keyword_occurrences(schema, "format")
    if minimum_count or format_count:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK schema contains keywords outside the closed contract subset: "
            f"minimum={minimum_count}, format={format_count}"
        )
    _assert_schema_definition_supported(schema)
    record = _file_record(
        schema_path,
        role="p1_temporal_consumer_seed_20260613_patch_lock_schema",
    )
    if type(record["bytes"]) is not int or int(record["bytes"]) <= 0:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK schema must be a non-empty regular JSON file"
        )
    return {
        "gate": PATCH_GATE,
        "schema_path": schema_path.as_posix(),
        "schema_bytes": record["bytes"],
        "schema_sha256": record["sha256"],
        "supported_subset_verified": True,
        "minimum_keyword_absent": True,
        "format_keyword_absent": True,
    }


def _observed_diff_entries(base: str, head: str) -> list[dict[str, str]]:
    try:
        return e0_mj._observed_diff_entries(base, head)
    except e0_mj.P1SequenceSeed20260613PatchError as exc:
        raise _translate(exc) from exc


def _assert_paths_untouched(
    base: str,
    descendant: str,
    paths: Sequence[str],
    *,
    context: str,
) -> None:
    try:
        e0_mj._assert_paths_untouched(base, descendant, paths, context=context)
    except e0_mj.P1SequenceSeed20260613PatchError as exc:
        raise _translate(exc) from exc


def _introduced_commit(path: str) -> str:
    try:
        return e0_mj._introduced_commit(path)
    except e0_mj.P1SequenceSeed20260613PatchError as exc:
        raise _translate(exc) from exc


def _remote_main_oid() -> str:
    try:
        return e0_mj._remote_main_oid()
    except e0_mj.P1SequenceSeed20260613PatchError as exc:
        raise _translate(exc) from exc


def _path_entry_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def patch_git_diff_payload(patch_head: str) -> dict[str, Any]:
    patch_head = _require_commit(patch_head, context="H-E0-MK")
    ancestry = _git("rev-list", "--parents", "-n", "1", patch_head).split()
    if ancestry != [patch_head, PATCH_BASE_COMMIT]:
        raise P1TemporalConsumerSeed20260613PatchError(
            "H-E0-MK must be the direct non-merge child of P1/20260613"
        )
    expected = [
        {
            "status": "M" if path in PATCH_MODIFIED_PATHS else "A",
            "path": path,
        }
        for path in PATCH_PATHS
    ]
    observed = _observed_diff_entries(PATCH_BASE_COMMIT, patch_head)
    if observed != expected:
        raise P1TemporalConsumerSeed20260613PatchError(
            f"H-E0-MK diff differs from its closed 2M+5A allowlist: {observed}"
        )
    return {
        "base_commit": PATCH_BASE_COMMIT,
        "patch_head": patch_head,
        "entries": expected,
        "paths": list(PATCH_PATHS),
        "paths_sha256": _path_digest(PATCH_PATHS),
        "added_count": 5,
        "modified_count": 2,
        "only_allowed_additions_and_modifications": True,
    }


def patch_component_bundle(patch_head: str) -> dict[str, Any]:
    patch_head = _require_commit(patch_head, context="H-E0-MK")
    records = [
        _git_record(patch_head, path, role=PATCH_COMPONENT_ROLES[path])
        for path in PATCH_PATHS
    ]
    return {
        "count": 7,
        "paths": list(PATCH_PATHS),
        "paths_sha256": _path_digest(PATCH_PATHS),
        "records": records,
        "records_sha256": _record_digest(records),
    }


def _component_set(
    records: Sequence[Mapping[str, Any]],
    *,
    current_bytes_required_to_match_historical: bool,
) -> dict[str, Any]:
    copied = [dict(record) for record in records]
    return {
        "count": len(copied),
        "paths": [str(record["path"]) for record in copied],
        "records": copied,
        "records_sha256": _record_digest(copied),
        "current_bytes_required_to_match_historical": (
            current_bytes_required_to_match_historical
        ),
    }


def _component_records(
    bundle: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    raw = bundle.get("records")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical component bundle records are malformed"
        )
    records = tuple(dict(cast(Mapping[str, Any], record)) for record in raw)
    paths = [str(record.get("path")) for record in records]
    if len(paths) != len(set(paths)):
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical component bundle contains duplicate paths"
        )
    return records


def _published_lock_records(
    *,
    h_commit: str,
    p_commit: str,
    lock_path: Path,
    companion_path: Path,
    lock_role: str,
    companion_role: str,
    execution_head: str,
    context: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    ancestry = _git("rev-list", "--parents", "-n", "1", p_commit).split()
    if ancestry != [p_commit, h_commit]:
        raise P1TemporalConsumerSeed20260613PatchError(
            f"{context} publication topology drifted"
        )
    expected = [
        {"status": "A", "path": lock_path.as_posix()},
        {"status": "A", "path": companion_path.as_posix()},
    ]
    if _observed_diff_entries(h_commit, p_commit) != expected:
        raise P1TemporalConsumerSeed20260613PatchError(
            f"{context} publication scope drifted"
        )
    _require_ancestor(p_commit, execution_head)
    _assert_paths_untouched(
        p_commit,
        execution_head,
        (lock_path.as_posix(), companion_path.as_posix()),
        context=f"{context} publication",
    )
    lock_record = _file_record(lock_path, role=lock_role)
    companion_record = _file_record(companion_path, role=companion_role)
    if (
        lock_record
        != _git_record(p_commit, lock_path.as_posix(), role=lock_role)
        or companion_record
        != _git_record(p_commit, companion_path.as_posix(), role=companion_role)
    ):
        raise P1TemporalConsumerSeed20260613PatchError(
            f"{context} published lock bytes drifted"
        )
    return lock_record, companion_record


def _historical_e0_mi_authority(*, execution_head: str) -> dict[str, Any]:
    """Reconstruct E0-MI with trainer and trainer tests explicitly superseded."""
    payload = _load_regular_json(e0_mi.DEFAULT_PATCH_LOCK_PATH, context="P-E0-MI lock")
    schema = _load_regular_json(e0_mi.DEFAULT_PATCH_LOCK_SCHEMA, context="H-E0-MI schema")
    try:
        validate_json_schema(payload, schema, instance_path="$.historical_e0_mi_lock")
    except ClosureContractError as exc:
        raise _translate(exc) from exc
    fixed = {
        "lock_version": e0_mi.LOCK_VERSION,
        "status": e0_mi.PATCH_STATUS,
        "experiment_id": e0_mi.EXPERIMENT_ID,
        "surface_id": e0_mi.SURFACE_ID,
        "gate": e0_mi.PATCH_GATE,
        "patch_id": e0_mi.PATCH_ID,
        "authorizations": e0_mi.PATCH_AUTHORIZATIONS,
        "seals": e0_mi.PATCH_SEALS,
    }
    if any(payload.get(field) != value for field, value in fixed.items()):
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical E0-MI fixed contract drifted"
        )
    repository = cast(Mapping[str, Any], payload.get("patch_repository", {}))
    if repository.get("head") != E0_MI_H_COMMIT:
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical E0-MI H commit drifted"
        )
    git_diff = e0_mi.patch_git_diff_payload(E0_MI_H_COMMIT)
    components = e0_mi.patch_component_bundle(E0_MI_H_COMMIT)
    if payload.get("git_diff") != git_diff or payload.get("patch_components") != components:
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical E0-MI Git authority drifted"
        )
    lock_record, companion_record = _published_lock_records(
        h_commit=E0_MI_H_COMMIT,
        p_commit=E0_MI_P_COMMIT,
        lock_path=e0_mi.DEFAULT_PATCH_LOCK_PATH,
        companion_path=e0_mi.DEFAULT_PATCH_MANIFEST_PATH,
        lock_role="external_p1_temporal_consumer_seed_20260612_patch_lock",
        companion_role="p1_temporal_consumer_seed_20260612_patch_companion",
        execution_head=execution_head,
        context="P-E0-MI",
    )
    companion = _load_regular_json(
        e0_mi.DEFAULT_PATCH_MANIFEST_PATH,
        context="P-E0-MI companion",
    )
    if companion != e0_mi._expected_companion(payload, lock_record=lock_record):
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical E0-MI companion drifted"
        )
    records = _component_records(cast(Mapping[str, Any], components))
    by_path = {str(record["path"]): record for record in records}
    if set(by_path) != set(e0_mi.PATCH_PATHS):
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical E0-MI component paths drifted"
        )
    superseded = [by_path[path] for path in MI_SUPERSEDED_PATHS]
    preserved = [by_path[path] for path in MI_PRESERVED_PATHS]
    for record in records:
        expected = _git_record(
            E0_MI_H_COMMIT,
            str(record["path"]),
            role=str(record["role"]),
        )
        if record != expected:
            raise P1TemporalConsumerSeed20260613PatchError(
                f"Historical E0-MI Git record drifted: {record['path']}"
            )
    for record in preserved:
        if _file_record(Path(str(record["path"])), role=str(record["role"])) != record:
            raise P1TemporalConsumerSeed20260613PatchError(
                f"Preserved E0-MI component drifted: {record['path']}"
            )
    _assert_paths_untouched(
        E0_MI_H_COMMIT,
        execution_head,
        MI_PRESERVED_PATHS,
        context="preserved H-E0-MI components",
    )
    return {
        "gate": "E0-MI",
        "patch_head": E0_MI_H_COMMIT,
        "lock_commit": E0_MI_P_COMMIT,
        "git_diff": git_diff,
        "patch_components": components,
        "lock": lock_record,
        "companion_manifest": companion_record,
        "superseded_components": _component_set(
            superseded,
            current_bytes_required_to_match_historical=False,
        ),
        "preserved_components": _component_set(
            preserved,
            current_bytes_required_to_match_historical=True,
        ),
        "publication_topology_verified": True,
        "historical_authority_verified": True,
        "effective_loader_called": False,
        "future_outcomes_accessed": False,
    }


def _historical_e0_mj_authority(*, execution_head: str) -> dict[str, Any]:
    """Reconstruct the published builder authority without an effective loader."""
    payload = _load_regular_json(e0_mj.DEFAULT_PATCH_LOCK_PATH, context="P-E0-MJ lock")
    schema = _load_regular_json(e0_mj.DEFAULT_PATCH_LOCK_SCHEMA, context="H-E0-MJ schema")
    try:
        validate_json_schema(payload, schema, instance_path="$.historical_e0_mj_lock")
    except ClosureContractError as exc:
        raise _translate(exc) from exc
    fixed = {
        "lock_version": e0_mj.LOCK_VERSION,
        "status": e0_mj.PATCH_STATUS,
        "experiment_id": e0_mj.EXPERIMENT_ID,
        "surface_id": e0_mj.SURFACE_ID,
        "gate": e0_mj.PATCH_GATE,
        "patch_id": e0_mj.PATCH_ID,
        "authorizations": e0_mj.PATCH_AUTHORIZATIONS,
        "seals": e0_mj.PATCH_SEALS,
    }
    if any(payload.get(field) != value for field, value in fixed.items()):
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical E0-MJ fixed contract drifted"
        )
    repository = cast(Mapping[str, Any], payload.get("patch_repository", {}))
    if repository.get("head") != E0_MJ_H_COMMIT:
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical E0-MJ H commit drifted"
        )
    git_diff = e0_mj.patch_git_diff_payload(E0_MJ_H_COMMIT)
    components = e0_mj.patch_component_bundle(E0_MJ_H_COMMIT)
    if payload.get("git_diff") != git_diff or payload.get("patch_components") != components:
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical E0-MJ Git authority drifted"
        )
    lock_record, companion_record = _published_lock_records(
        h_commit=E0_MJ_H_COMMIT,
        p_commit=E0_MJ_P_COMMIT,
        lock_path=e0_mj.DEFAULT_PATCH_LOCK_PATH,
        companion_path=e0_mj.DEFAULT_PATCH_MANIFEST_PATH,
        lock_role="external_p1_sequence_seed_20260613_patch_lock",
        companion_role="p1_sequence_seed_20260613_patch_companion",
        execution_head=execution_head,
        context="P-E0-MJ",
    )
    companion = _load_regular_json(
        e0_mj.DEFAULT_PATCH_MANIFEST_PATH,
        context="P-E0-MJ companion",
    )
    if companion != e0_mj._expected_companion(payload, lock_record=lock_record):
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical E0-MJ companion drifted"
        )
    records = _component_records(cast(Mapping[str, Any], components))
    if {str(record["path"]) for record in records} != set(e0_mj.PATCH_PATHS):
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical E0-MJ component paths drifted"
        )
    for record in records:
        if record != _git_record(
            E0_MJ_H_COMMIT,
            str(record["path"]),
            role=str(record["role"]),
        ):
            raise P1TemporalConsumerSeed20260613PatchError(
                f"Historical E0-MJ Git record drifted: {record['path']}"
            )
        if _file_record(Path(str(record["path"])), role=str(record["role"])) != record:
            raise P1TemporalConsumerSeed20260613PatchError(
                f"Preserved E0-MJ component drifted: {record['path']}"
            )
    _assert_paths_untouched(
        E0_MJ_H_COMMIT,
        execution_head,
        e0_mj.PATCH_PATHS,
        context="preserved H-E0-MJ components",
    )
    base_authorities = payload.get("base_authorities")
    if not isinstance(base_authorities, Mapping) or set(base_authorities) != {
        "e0_mh",
        "e0_mi",
    }:
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical E0-MJ base-authority dialect drifted"
        )
    sealed_mi = cast(Mapping[str, Any], base_authorities["e0_mi"])
    if (
        sealed_mi.get("gate") != "E0-MI"
        or sealed_mi.get("patch_head") != E0_MI_H_COMMIT
        or sealed_mi.get("lock_commit") != E0_MI_P_COMMIT
        or sealed_mi.get("effective_loader_called") is not False
        or sealed_mi.get("future_outcomes_accessed") is not False
    ):
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical E0-MJ sealed E0-MI authority drifted"
        )
    if payload.get("p1_1729_publication") != e0_mj._published_p1_1729_bundle(
        execution_head=execution_head
    ):
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical E0-MJ sealed P1/1729 publication drifted"
        )
    if payload.get(
        "p1_20260612_publication"
    ) != e0_mj._published_p1_20260612_bundle(execution_head=execution_head):
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical E0-MJ sealed P1/20260612 publication drifted"
        )
    builder = payload.get("current_runtime_builder_record")
    if builder != {**P1_ARTIFACT_BUILDER_RECORD, "role": "current_runtime_builder"}:
        raise P1TemporalConsumerSeed20260613PatchError(
            "Historical E0-MJ runtime builder drifted"
        )
    return {
        "gate": "E0-MJ",
        "patch_head": E0_MJ_H_COMMIT,
        "lock_commit": E0_MJ_P_COMMIT,
        "git_diff": git_diff,
        "patch_components": components,
        "lock": lock_record,
        "companion_manifest": companion_record,
        "current_runtime_builder_record": dict(cast(Mapping[str, Any], builder)),
        "preserved_components": _component_set(
            records,
            current_bytes_required_to_match_historical=True,
        ),
        "publication_topology_verified": True,
        "historical_e0_mi_seal_verified": True,
        "historical_authority_verified": True,
        "effective_loader_called": False,
        "future_outcomes_accessed": False,
    }


def _published_p1_20260613_bundle(*, execution_head: str) -> dict[str, Any]:
    ancestry = _git("rev-list", "--parents", "-n", "1", P1_BUNDLE_COMMIT).split()
    if ancestry != [P1_BUNDLE_COMMIT, E0_MJ_P_COMMIT]:
        raise P1TemporalConsumerSeed20260613PatchError(
            "P1/20260613 publication topology drifted"
        )
    versioned_roles = {
        "data/closure_v1/development/sequences/P1/seed_20260613.parquet.dvc": (
            "p1_seed_20260613_sequence_dvc_pointer"
        ),
        "reports/closure_v1/01_surface/sequences/P1/seed_20260613_manifest.json": (
            "p1_seed_20260613_sequence_manifest"
        ),
        "reports/closure_v1/01_surface/sequences/P1/seed_20260613_summary.csv": (
            "p1_seed_20260613_sequence_summary"
        ),
        "src/experiments/audit_closure_p1_seed_20260613_sequence_bundle.py": (
            "p1_seed_20260613_sequence_auditor"
        ),
        "tests/test_audit_closure_p1_seed_20260613_sequence_bundle.py": (
            "p1_seed_20260613_sequence_auditor_tests"
        ),
    }
    expected_diff = [
        {"status": "A", "path": path} for path in sorted(versioned_roles)
    ]
    if _observed_diff_entries(E0_MJ_P_COMMIT, P1_BUNDLE_COMMIT) != expected_diff:
        raise P1TemporalConsumerSeed20260613PatchError(
            "P1/20260613 publication scope drifted"
        )
    _require_ancestor(P1_BUNDLE_COMMIT, execution_head)
    _assert_paths_untouched(
        P1_BUNDLE_COMMIT,
        execution_head,
        tuple(sorted(versioned_roles)),
        context="P1/20260613 published bundle",
    )
    expected = {
        "data/closure_v1/development/sequences/P1/seed_20260613.parquet.dvc": (
            104,
            "a2b6f345ba7340abaf6791bf99d22ec8a989c940f91f3634456fa02bd9902962",
        ),
        "reports/closure_v1/01_surface/sequences/P1/seed_20260613_manifest.json": (
            6_541,
            "d2ecb7b9b25b0b60a6534d64679db44d77e2484f6e3f269c7ae3db020bcfbac3",
        ),
        "reports/closure_v1/01_surface/sequences/P1/seed_20260613_summary.csv": (
            356,
            "a6c6c837a82c13a9321233de03b588c60b7a4198b77dcf31b3c7a62027752c3e",
        ),
        "src/experiments/audit_closure_p1_seed_20260613_sequence_bundle.py": (
            68_559,
            "19345bf9986dab2aeee098aa579104e99928c1355f4cfb52a7e137147f096869",
        ),
        "tests/test_audit_closure_p1_seed_20260613_sequence_bundle.py": (
            27_310,
            "fc3936589260b2265206672986ee76f197b6c2108200be79f4f19084b3e754c7",
        ),
    }
    records: list[dict[str, Any]] = []
    for path in sorted(versioned_roles):
        record = _file_record(Path(path), role=versioned_roles[path])
        size, digest = expected[path]
        if (
            record["bytes"] != size
            or record["sha256"] != digest
            or record != _git_record(P1_BUNDLE_COMMIT, path, role=versioned_roles[path])
        ):
            raise P1TemporalConsumerSeed20260613PatchError(
                f"P1/20260613 published artifact drifted: {path}"
            )
        records.append(record)
    parquet = _file_record(
        Path("data/closure_v1/development/sequences/P1/seed_20260613.parquet"),
        role="p1_seed_20260613_sequence_payload",
    )
    if (
        parquet["bytes"] != 1_379_656
        or parquet["sha256"]
        != "4dfd3ec12e061d29730fbf005e2e4c7e24a922335da5d4512a9b8c5eb847171a"
    ):
        raise P1TemporalConsumerSeed20260613PatchError(
            "P1/20260613 Parquet payload drifted"
        )
    return {
        "commit": P1_BUNDLE_COMMIT,
        "parent": E0_MJ_P_COMMIT,
        "records": [parquet, *records],
        "records_sha256": _record_digest([parquet, *records]),
        "exact_five_addition_scope_verified": True,
        "payload_regular_and_hash_verified": True,
        "future_outcomes_accessed": False,
    }


def _auditor_identity_record() -> dict[str, Any]:
    callable_object = p1_audit.audit_p1_seed_20260613_sequence_bundle
    source = inspect.getsourcefile(callable_object)
    code = getattr(callable_object, "__code__", None)
    if (
        callable_object.__module__ != AUDITOR_MODULE
        or callable_object.__name__ != AUDITOR_NAME
        or callable_object.__qualname__ != AUDITOR_QUALNAME
        or source is None
        or code is None
    ):
        raise P1TemporalConsumerSeed20260613PatchError(
            "P1 auditor callable identity drifted"
        )
    expected_path = (PROJECT_ROOT / AUDITOR_SOURCE_PATH).resolve(strict=True)
    if Path(source).resolve(strict=True) != expected_path:
        raise P1TemporalConsumerSeed20260613PatchError(
            "P1 auditor callable source path drifted"
        )
    if Path(str(code.co_filename)).resolve(strict=True) != expected_path:
        raise P1TemporalConsumerSeed20260613PatchError(
            "P1 auditor callable code filename drifted"
        )
    git_record = _git_record(
        P1_BUNDLE_COMMIT,
        AUDITOR_SOURCE_PATH,
        role="p1_sequence_bundle_auditor_callable",
    )
    physical_record = _file_record(
        Path(AUDITOR_SOURCE_PATH),
        role="p1_sequence_bundle_auditor_callable",
    )
    if physical_record != git_record:
        raise P1TemporalConsumerSeed20260613PatchError(
            "P1 auditor callable source differs from its published Git blob"
        )
    return {
        "module": AUDITOR_MODULE,
        "name": AUDITOR_NAME,
        "qualname": AUDITOR_QUALNAME,
        "source_path": AUDITOR_SOURCE_PATH,
        "code_filename": AUDITOR_SOURCE_PATH,
        "git_commit": P1_BUNDLE_COMMIT,
        "git_source_record": git_record,
        "physical_source_record": physical_record,
    }


def _closed_audit_evidence(result: Mapping[str, Any]) -> dict[str, Any]:
    counts = result.get("counts")
    fit = result.get("fit_availability")
    if not isinstance(counts, Mapping) or not isinstance(fit, Mapping):
        raise P1TemporalConsumerSeed20260613PatchError(
            "P1 in-process audit count evidence is malformed"
        )
    expected = {
        "audit_version": p1_audit.AUDIT_VERSION,
        "status": "validated",
        "model_id": "P1",
        "base_seed": 20_260_613,
        "intent_origins": 9_732,
        "successful_origins": 9_227,
        "failed_origins": 505,
        "fit_successful_origins": 8_925,
        "fit_unavailable_origins": 488,
        "calibration_unavailable_origins": 17,
    }
    observed = {
        "audit_version": result.get("audit_version"),
        "status": result.get("status"),
        "model_id": result.get("model_id"),
        "base_seed": result.get("base_seed"),
        "intent_origins": counts.get("intent_origins"),
        "successful_origins": counts.get("successful_origins"),
        "failed_origins": counts.get("failed_origins"),
        "fit_successful_origins": cast(Mapping[str, Any], fit.get("observed_fit_status_counts", {})).get("success"),
        "fit_unavailable_origins": cast(Mapping[str, Any], fit.get("observed_fit_status_counts", {})).get("autoregressive_target_unavailable"),
        "calibration_unavailable_origins": fit.get("observed_calibration_failure_count"),
    }
    drifted = [field for field, value in expected.items() if observed.get(field) != value]
    if drifted:
        raise P1TemporalConsumerSeed20260613PatchError(
            f"P1 in-process audit closed counts drifted: {drifted}"
        )
    expected_fit = {
        "available": False,
        "observed_fit_failure_reason_counts": {"missing_target_state": 488},
        "expected_temporal_slot_status": "model_unavailable",
        "expected_fit_status": "not_attempted",
        "expected_failure_reason": "sequence_fit_rows_unavailable",
        "consumer_executed_by_auditor": False,
        "fit_or_model_construction_executed_by_auditor": False,
    }
    fit_drift = [field for field, value in expected_fit.items() if fit.get(field) != value]
    safety = {
        "audited_namespaces_unchanged": True,
        "one_shot_reconsumed_by_auditor": False,
        "builder_cli_executed": False,
        "effective_loader_called_by_auditor": False,
        "fit_or_model_construction_executed_by_auditor": False,
        "dvc_operation_executed_by_auditor": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "bundle_future_outcomes_accessed": False,
        "future_outcomes_accessed_by_auditor": False,
    }
    safety_drift = [
        field for field, value in safety.items() if result.get(field) != value
    ]
    if fit_drift or safety_drift:
        raise P1TemporalConsumerSeed20260613PatchError(
            "P1 in-process audit read-only evidence drifted: "
            f"fit={fit_drift}, safety={safety_drift}"
        )
    identity = _auditor_identity_record()
    try:
        encoded = _canonical_audit_result(result)
    except (TypeError, ValueError) as exc:
        raise P1TemporalConsumerSeed20260613PatchError(
            "P1 in-process audit result is not canonical JSON"
        ) from exc
    source_record = dict(
        cast(Mapping[str, Any], identity["physical_source_record"])
    )
    return {
        "execution_mode": "in_process_callable",
        "callable_module": identity["module"],
        "callable_name": identity["name"],
        "callable_qualname": identity["qualname"],
        "callable_source_path": identity["source_path"],
        "callable_code_filename": identity["code_filename"],
        "callable_git_commit": identity["git_commit"],
        "callable_source_git": dict(cast(Mapping[str, Any], identity["git_source_record"])),
        "callable_source_physical": source_record,
        **expected,
        "fit_failure_reason_counts": {"missing_target_state": 488},
        "sequence_fit_available": False,
        "expected_slot_status": "model_unavailable",
        "expected_fit_status": "not_attempted",
        "expected_failure_reason": "sequence_fit_rows_unavailable",
        "result_bytes": len(encoded),
        "result_sha256": _sha256_bytes(encoded),
        "auditor_read_only": True,
        "consumer_executed": False,
        "fit_executed": False,
        "dvc_operation_executed": False,
        "future_outcomes_accessed": False,
    }


def run_p1_bundle_audit_in_process() -> dict[str, Any]:
    """Invoke exactly the published P1/20260613 auditor in this process."""
    _auditor_identity_record()
    try:
        result = p1_audit.audit_p1_seed_20260613_sequence_bundle()
    except p1_audit.ClosureP1Seed20260613SequenceAuditError as exc:
        raise _translate(exc) from exc
    if not isinstance(result, Mapping):
        raise P1TemporalConsumerSeed20260613PatchError(
            "P1 in-process auditor returned a non-mapping result"
        )
    return _closed_audit_evidence(result)


def p1_consumer_namespace_absence() -> dict[str, Any]:
    paths = [path.as_posix() for path in p1_audit.P1_CONSUMER_PATHS]
    existing = [path for path in paths if _path_entry_exists(PROJECT_ROOT / path)]
    if existing:
        raise P1TemporalConsumerSeed20260613PatchError(
            f"P1/20260613 consumer namespace is not empty: {existing}"
        )
    return {
        "model_id": AUTHORIZED_MODEL_ID,
        "base_seed": AUTHORIZED_BASE_SEED,
        "count": len(paths),
        "paths": paths,
        "paths_sha256": _path_digest(paths),
        "all_absent_at_lock": True,
    }


def closure_progression_prelock() -> dict[str, Any]:
    prior = [path.as_posix() for path in p1_audit.PRIOR_P1_PATHS]
    current = [
        p1_audit.P1_SEQUENCE_PATH.as_posix(),
        p1_audit.P1_POINTER_PATH.as_posix(),
        p1_audit.P1_SUMMARY_PATH.as_posix(),
        p1_audit.P1_MANIFEST_PATH.as_posix(),
    ]
    later = [path.as_posix() for path in p1_audit.LATER_P1_PATHS]
    e0_m = [path.as_posix() for path in p1_audit.E0_M_OUTPUT_PATHS]
    registered = [path.as_posix() for path in p1_audit.REGISTERED_P1_PATHS]
    expected_present = [*prior, *current]
    if (
        len(registered) != 140
        or len(set(registered)) != 140
        or len(prior) != 12
        or len(current) != 4
        or len(p1_audit.P1_CONSUMER_PATHS) != 19
        or len(p1_audit.P1_SEQUENCE_TEMPORARY_PATHS) != 5
        or len(later) != 56
        or len(e0_m) != 4
    ):
        raise P1TemporalConsumerSeed20260613PatchError(
            "P1 registered progression universe drifted"
        )
    observed_present = [
        path for path in registered if _path_entry_exists(PROJECT_ROOT / path)
    ]
    missing_required = sorted(set(expected_present).difference(observed_present))
    unexpected_registered = sorted(
        set(observed_present).difference(expected_present)
    )
    forbidden_external = [
        path
        for path in (*e0_m, p1_audit.OUTCOME_ACCESS_LOG_PATH.as_posix())
        if _path_entry_exists(PROJECT_ROOT / path)
    ]
    if missing_required or unexpected_registered or forbidden_external:
        raise P1TemporalConsumerSeed20260613PatchError(
            "P1/20260613 progression prelock drifted: "
            f"missing={missing_required}, "
            f"unexpected_registered={unexpected_registered}, "
            f"forbidden_external={forbidden_external}"
        )
    return {
        "registered_path_count": len(registered),
        "expected_present_count": len(expected_present),
        "expected_present_paths": expected_present,
        "expected_present_paths_sha256": _path_digest(expected_present),
        "registered_absent_count": len(registered) - len(expected_present),
        "exact_registered_namespace_verified": True,
        "prior_seeds": [1729, 20_260_612],
        "prior_present_count": len(prior),
        "prior_present_paths": prior,
        "prior_present_paths_sha256": _path_digest(prior),
        "prior_residual_absent_count": 56 - len(prior),
        "current_seed": AUTHORIZED_BASE_SEED,
        "current_present_count": len(current),
        "current_present_paths": current,
        "current_present_paths_sha256": _path_digest(current),
        "current_consumer_absent_count": len(p1_audit.P1_CONSUMER_PATHS),
        "current_sequence_temporary_absent_count": len(
            p1_audit.P1_SEQUENCE_TEMPORARY_PATHS
        ),
        "later_absent_count": len(later),
        "later_paths_sha256": _path_digest(later),
        "e0_m_absent_count": len(e0_m),
        "outcome_access_log_absent": True,
        "ordered_progression_verified": True,
        "future_outcomes_accessed": False,
    }


def collect_p1_temporal_consumer_seed_20260613_patch_prelock_state(
    *,
    verify_remote: bool,
) -> dict[str, Any]:
    status = _git("status", "--porcelain", "--untracked-files=all")
    if status:
        raise P1TemporalConsumerSeed20260613PatchError(
            f"H-E0-MK lock requires a clean worktree: {status}"
        )
    head = _require_commit(_git("rev-parse", "HEAD"), context="H-E0-MK HEAD")
    if _git("branch", "--show-current") != "main":
        raise P1TemporalConsumerSeed20260613PatchError(
            "H-E0-MK lock requires branch main"
        )
    published = _require_commit(_git("rev-parse", PUBLISHED_REF), context=PUBLISHED_REF)
    if published != head:
        raise P1TemporalConsumerSeed20260613PatchError(
            "H-E0-MK HEAD differs from origin/main"
        )
    remote = _remote_main_oid() if verify_remote else published
    if remote != head:
        raise P1TemporalConsumerSeed20260613PatchError(
            "H-E0-MK HEAD differs from live origin/main"
        )
    git_diff = patch_git_diff_payload(head)
    components = patch_component_bundle(head)
    for record in cast(Sequence[Mapping[str, Any]], components["records"]):
        if _file_record(Path(str(record["path"])), role=str(record["role"])) != record:
            raise P1TemporalConsumerSeed20260613PatchError(
                f"Physical H-E0-MK component drifted: {record['path']}"
            )
    historical_mi = _historical_e0_mi_authority(execution_head=head)
    historical_mj = _historical_e0_mj_authority(execution_head=head)
    published_bundle = _published_p1_20260613_bundle(execution_head=head)
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
        "git_diff": git_diff,
        "patch_components": components,
        "base_authorities": {
            "e0_mi": historical_mi,
            "e0_mj": historical_mj,
        },
        "p1_20260613_publication": published_bundle,
        "current_runtime_builder_record": {
            **P1_ARTIFACT_BUILDER_RECORD,
            "role": "current_runtime_builder",
        },
        "consumer_prelock": p1_consumer_namespace_absence(),
        "progression_prelock": closure_progression_prelock(),
        "fit_availability": dict(FIT_AVAILABILITY),
    }


def build_p1_temporal_consumer_seed_20260613_patch_lock_payload(
    prelock: Mapping[str, Any],
    verification: Mapping[str, Any],
    *,
    created_at_utc: str,
) -> dict[str, Any]:
    return {
        "lock_version": LOCK_VERSION,
        "status": PATCH_STATUS,
        "experiment_id": EXPERIMENT_ID,
        "surface_id": SURFACE_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": created_at_utc,
        "patch_repository": dict(cast(Mapping[str, Any], prelock["patch_repository"])),
        "git_diff": dict(cast(Mapping[str, Any], prelock["git_diff"])),
        "patch_components": dict(cast(Mapping[str, Any], prelock["patch_components"])),
        "base_authorities": dict(cast(Mapping[str, Any], prelock["base_authorities"])),
        "p1_20260613_publication": dict(
            cast(Mapping[str, Any], prelock["p1_20260613_publication"])
        ),
        "current_runtime_builder_record": dict(
            cast(Mapping[str, Any], prelock["current_runtime_builder_record"])
        ),
        "consumer_prelock": dict(cast(Mapping[str, Any], prelock["consumer_prelock"])),
        "progression_prelock": dict(
            cast(Mapping[str, Any], prelock["progression_prelock"])
        ),
        "fit_availability": dict(cast(Mapping[str, Any], prelock["fit_availability"])),
        "correction": dict(PATCH_CORRECTION),
        "verification": dict(verification),
        "authorizations": dict(PATCH_AUTHORIZATIONS),
        "seals": dict(PATCH_SEALS),
        "lock_artifact": {
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "role": "external_p1_temporal_consumer_seed_20260613_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
    }


def _validate_command_evidence(
    evidence: Mapping[str, Any],
    *,
    command: Sequence[str],
    context: str,
) -> None:
    required = {
        "command",
        "returncode",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_line_count",
        "stderr_line_count",
    }
    optional = {
        "test_count",
        "skipped_count",
        "deselected_count",
        "summary_format",
        "duration_seconds",
        "duration_clock",
        "terminal_status",
    }
    if set(evidence).difference(required | optional):
        raise P1TemporalConsumerSeed20260613PatchError(
            f"E0-MK {context} evidence has unexpected fields"
        )
    if not required.issubset(evidence) or evidence.get("command") != list(command):
        raise P1TemporalConsumerSeed20260613PatchError(
            f"E0-MK {context} evidence drifted"
        )
    if evidence.get("returncode") != 0:
        raise P1TemporalConsumerSeed20260613PatchError(
            f"E0-MK {context} did not pass"
        )
    for field in ("stdout_line_count", "stderr_line_count"):
        value = evidence.get(field)
        if type(value) is not int or value < 0:
            raise P1TemporalConsumerSeed20260613PatchError(
                f"E0-MK {context} {field} must be a non-negative integer"
            )


def _validate_focused_duration_evidence(evidence: Mapping[str, Any]) -> None:
    duration_text = evidence.get("duration_seconds")
    if not isinstance(duration_text, str):
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK focused pytest duration evidence is malformed"
        )
    try:
        duration = Decimal(duration_text)
    except InvalidOperation as exc:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK focused pytest duration evidence is malformed"
        ) from exc
    if not duration.is_finite() or duration < 0:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK focused pytest duration evidence is malformed"
        )
    summary_format = evidence.get("summary_format")
    clock = evidence.get("duration_clock")
    if duration < Decimal(60):
        valid = summary_format == "pytest_short" and clock is None
    else:
        try:
            expected_clock = str(timedelta(seconds=int(duration)))
        except OverflowError as exc:
            raise P1TemporalConsumerSeed20260613PatchError(
                "E0-MK focused pytest duration evidence is out of range"
            ) from exc
        valid = summary_format == "pytest_timedelta" and clock == expected_clock
    if not valid:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK focused pytest duration/clock evidence drifted"
        )


def _validate_audit_evidence_shape(evidence: Mapping[str, Any]) -> None:
    fixed = {
        "execution_mode": "in_process_callable",
        "callable_module": AUDITOR_MODULE,
        "callable_name": AUDITOR_NAME,
        "callable_qualname": AUDITOR_QUALNAME,
        "callable_source_path": AUDITOR_SOURCE_PATH,
        "callable_code_filename": AUDITOR_SOURCE_PATH,
        "callable_git_commit": P1_BUNDLE_COMMIT,
        "audit_version": p1_audit.AUDIT_VERSION,
        "status": "validated",
        "model_id": "P1",
        "base_seed": 20_260_613,
        "intent_origins": 9_732,
        "successful_origins": 9_227,
        "failed_origins": 505,
        "fit_successful_origins": 8_925,
        "fit_unavailable_origins": 488,
        "calibration_unavailable_origins": 17,
        "fit_failure_reason_counts": {"missing_target_state": 488},
        "sequence_fit_available": False,
        "expected_slot_status": "model_unavailable",
        "expected_fit_status": "not_attempted",
        "expected_failure_reason": "sequence_fit_rows_unavailable",
        "auditor_read_only": True,
        "consumer_executed": False,
        "fit_executed": False,
        "dvc_operation_executed": False,
        "future_outcomes_accessed": False,
    }
    drifted = [field for field, expected in fixed.items() if evidence.get(field) != expected]
    if drifted:
        raise P1TemporalConsumerSeed20260613PatchError(
            f"E0-MK in-process audit evidence drifted: {drifted}"
        )
    identity = _auditor_identity_record()
    for field, identity_field in (
        ("callable_source_git", "git_source_record"),
        ("callable_source_physical", "physical_source_record"),
    ):
        if evidence.get(field) != identity[identity_field]:
            raise P1TemporalConsumerSeed20260613PatchError(
                f"E0-MK auditor {field} drifted"
            )
    size = evidence.get("result_bytes")
    digest = evidence.get("result_sha256")
    if (
        type(size) is not int
        or size <= 0
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK canonical audit hash evidence is malformed"
        )


def validate_p1_temporal_consumer_seed_20260613_patch_verification(
    verification: Mapping[str, Any],
) -> None:
    expected_fields = {
        "schema_subset_preflight",
        "full_type_check",
        "focused_tests",
        "poetry_check",
        "publication_guard",
        "git_diff_check",
        "p1_bundle_audit",
        "dvc_push_first",
        "dvc_push_second",
    }
    if set(verification) != expected_fields:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK verification fields drifted"
        )
    preflight = verification.get("schema_subset_preflight")
    if (
        not isinstance(preflight, Mapping)
        or dict(preflight)
        != preflight_p1_temporal_consumer_seed_20260613_patch_schema()
    ):
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK schema-subset preflight evidence drifted"
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
    for field, command in commands.items():
        value = verification.get(field)
        if not isinstance(value, Mapping):
            raise P1TemporalConsumerSeed20260613PatchError(
                f"E0-MK {field} evidence is malformed"
            )
        _validate_command_evidence(value, command=command, context=field)
    focused = cast(Mapping[str, Any], verification["focused_tests"])
    if (
        FOCUSED_TEST_COUNT <= 0
        or focused.get("test_count") != FOCUSED_TEST_COUNT
        or focused.get("skipped_count") != 0
        or focused.get("deselected_count") != 0
    ):
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK focused-test evidence drifted"
        )
    _validate_focused_duration_evidence(focused)
    first = cast(Mapping[str, Any], verification["dvc_push_first"])
    second = cast(Mapping[str, Any], verification["dvc_push_second"])
    if first.get("terminal_status") not in {
        "1 file pushed",
        "Everything is up to date.",
    }:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK first targeted DVC push evidence drifted"
        )
    if second.get("terminal_status") != "Everything is up to date.":
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK second targeted DVC push is not idempotent"
        )
    audit = verification.get("p1_bundle_audit")
    if not isinstance(audit, Mapping):
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK in-process audit evidence is malformed"
        )
    _validate_audit_evidence_shape(audit)


def validate_p1_temporal_consumer_seed_20260613_patch_lock_payload(
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    require_physical_audit: bool,
) -> None:
    try:
        validate_json_schema(
            payload,
            schema,
            instance_path="$.p1_temporal_consumer_seed_20260613_patch_lock",
        )
    except ClosureContractError as exc:
        raise _translate(exc) from exc
    fixed = {
        "lock_version": LOCK_VERSION,
        "status": PATCH_STATUS,
        "experiment_id": EXPERIMENT_ID,
        "surface_id": SURFACE_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "fit_availability": FIT_AVAILABILITY,
        "correction": PATCH_CORRECTION,
        "authorizations": PATCH_AUTHORIZATIONS,
        "seals": PATCH_SEALS,
        "lock_artifact": {
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "role": "external_p1_temporal_consumer_seed_20260613_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
    }
    for field, expected in fixed.items():
        if payload.get(field) != expected:
            raise P1TemporalConsumerSeed20260613PatchError(
                f"E0-MK fixed field drifted: {field}"
            )
    created = payload.get("created_at_utc")
    if not isinstance(created, str):
        raise P1TemporalConsumerSeed20260613PatchError("E0-MK timestamp is invalid")
    try:
        timestamp = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK timestamp is invalid"
        ) from exc
    if timestamp.utcoffset() is None:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK timestamp requires a timezone"
        )
    repository = cast(Mapping[str, Any], payload["patch_repository"])
    patch_head = _require_commit(str(repository.get("head", "")), context="H-E0-MK")
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
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK patch repository record drifted"
        )
    if payload.get("git_diff") != patch_git_diff_payload(patch_head):
        raise P1TemporalConsumerSeed20260613PatchError("E0-MK Git diff drifted")
    components = patch_component_bundle(patch_head)
    if payload.get("patch_components") != components:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK component bundle drifted"
        )
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    _require_ancestor(patch_head, execution_head)
    for record in cast(Sequence[Mapping[str, Any]], components["records"]):
        if _file_record(Path(str(record["path"])), role=str(record["role"])) != record:
            raise P1TemporalConsumerSeed20260613PatchError(
                f"Physical H-E0-MK component drifted: {record['path']}"
            )
    _assert_paths_untouched(
        patch_head,
        execution_head,
        PATCH_PATHS,
        context="H-E0-MK components",
    )
    expected_authorities = {
        "e0_mi": _historical_e0_mi_authority(execution_head=execution_head),
        "e0_mj": _historical_e0_mj_authority(execution_head=execution_head),
    }
    if payload.get("base_authorities") != expected_authorities:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK historical authorities drifted"
        )
    if payload.get("p1_20260613_publication") != _published_p1_20260613_bundle(
        execution_head=execution_head
    ):
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK P1/20260613 publication drifted"
        )
    if payload.get("current_runtime_builder_record") != {
        **P1_ARTIFACT_BUILDER_RECORD,
        "role": "current_runtime_builder",
    }:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK runtime builder record drifted"
        )
    if payload.get("consumer_prelock") != p1_consumer_namespace_absence():
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK consumer prelock drifted"
        )
    if payload.get("progression_prelock") != closure_progression_prelock():
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK progression prelock drifted"
        )
    verification = cast(Mapping[str, Any], payload["verification"])
    validate_p1_temporal_consumer_seed_20260613_patch_verification(verification)
    if require_physical_audit:
        observed = run_p1_bundle_audit_in_process()
        if verification.get("p1_bundle_audit") != observed:
            raise P1TemporalConsumerSeed20260613PatchError(
                "E0-MK physical in-process re-audit differs from locked evidence"
            )


def _expected_companion(
    payload: Mapping[str, Any],
    *,
    lock_record: Mapping[str, Any],
) -> dict[str, Any]:
    components = cast(Mapping[str, Any], payload["patch_components"])
    records = cast(Sequence[Mapping[str, Any]], components["records"])
    by_path = {str(record["path"]): record for record in records}
    authorities = cast(Mapping[str, Any], payload["base_authorities"])
    mi_authority = cast(Mapping[str, Any], authorities["e0_mi"])
    mj_authority = cast(Mapping[str, Any], authorities["e0_mj"])
    publication = cast(Mapping[str, Any], payload["p1_20260613_publication"])

    def component(path: str, role: str) -> dict[str, Any]:
        record = by_path[path]
        return {
            "path": path,
            "role": role,
            "bytes": record["bytes"],
            "sha256": record["sha256"],
        }

    inputs = [
        component(
            DEFAULT_PATCH_LOCK_SCHEMA.as_posix(),
            "p1_temporal_consumer_seed_20260613_patch_lock_schema",
        ),
        component(
            "src/experiments/closure_p1_temporal_consumer_seed_20260613_patch.py",
            "p1_temporal_consumer_seed_20260613_patch_validator",
        ),
        *[
            dict(record)
            for record in cast(
                Sequence[Mapping[str, Any]],
                cast(Mapping[str, Any], mi_authority["preserved_components"])["records"],
            )
        ],
        dict(cast(Mapping[str, Any], mi_authority["lock"])),
        dict(cast(Mapping[str, Any], mi_authority["companion_manifest"])),
        *[
            dict(record)
            for record in cast(
                Sequence[Mapping[str, Any]],
                cast(Mapping[str, Any], mj_authority["preserved_components"])["records"],
            )
        ],
        dict(cast(Mapping[str, Any], mj_authority["lock"])),
        dict(cast(Mapping[str, Any], mj_authority["companion_manifest"])),
        *[
            dict(record)
            for record in cast(Sequence[Mapping[str, Any]], publication["records"])
        ],
    ]
    inputs.sort(key=lambda record: (str(record["path"]), str(record.get("role", ""))))
    historical_inputs = [
        {
            **dict(record),
            "commit": E0_MI_H_COMMIT,
            "hash_source": "git_blob_at_commit",
        }
        for record in cast(
            Sequence[Mapping[str, Any]],
            cast(Mapping[str, Any], mi_authority["superseded_components"])["records"],
        )
    ]
    historical_inputs.sort(key=lambda record: str(record["path"]))
    return {
        "manifest_version": (
            "closure_p1_temporal_consumer_seed_20260613_patch_manifest_v1"
        ),
        "status": "completed",
        "experiment_id": EXPERIMENT_ID,
        "surface_id": SURFACE_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": payload["created_at_utc"],
        "outputs": [dict(lock_record)],
        "script": component(
            "src/experiments/lock_closure_p1_temporal_consumer_seed_20260613_patch.py",
            "generating_script",
        ),
        "inputs": inputs,
        "historical_inputs": historical_inputs,
        "physical_inputs_only": True,
        "historical_inputs_compared_to_current_paths": False,
        "auditor_execution_mode": "in_process_callable",
        "python_auditor_subprocess_used": False,
        "authorized_model_id": AUTHORIZED_MODEL_ID,
        "authorized_base_seed": AUTHORIZED_BASE_SEED,
        "authorized_device": AUTHORIZED_DEVICE,
        "p1_consumer_authorized": False,
        "p1_fit_authorized": False,
        "fit_attempt_authorized": False,
        "p1_sequence_builder_authorized": False,
        "dvc_commands_authorized": False,
        "effective_in_payload": False,
        "publication_required": True,
        "batch_seed_execution_authorized": False,
        "retry_authorized": False,
        "replacement_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "authoritative_contract": False,
        "authoritative_lock_path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "completion_marker_written_last": True,
    }


def _validate_publication_bundle(
    payload: Mapping[str, Any],
    *,
    execution_head: str,
    verify_remote: bool,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    lock_path = DEFAULT_PATCH_LOCK_PATH.as_posix()
    companion_path = DEFAULT_PATCH_MANIFEST_PATH.as_posix()
    lock_commit = _introduced_commit(lock_path)
    if lock_commit != _introduced_commit(companion_path):
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK lock and companion commits differ"
        )
    ancestry = _git("rev-list", "--parents", "-n", "1", lock_commit).split()
    if ancestry != [lock_commit, patch_head]:
        raise P1TemporalConsumerSeed20260613PatchError(
            "P-E0-MK must be the direct child of H-E0-MK"
        )
    expected = [
        {"status": "A", "path": lock_path},
        {"status": "A", "path": companion_path},
    ]
    if _observed_diff_entries(patch_head, lock_commit) != expected:
        raise P1TemporalConsumerSeed20260613PatchError(
            "P-E0-MK must add exactly lock plus companion"
        )
    if _git("branch", "--show-current") != "main":
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK effective authority requires branch main"
        )
    if execution_head != lock_commit:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK execution HEAD must equal the exact P-E0-MK lock commit"
        )
    _require_ancestor(lock_commit, execution_head)
    _assert_paths_untouched(
        lock_commit,
        execution_head,
        (lock_path, companion_path),
        context="P-E0-MK publication",
    )
    refs = {
        ref: _require_commit(_git("rev-parse", ref), context=ref)
        for ref in ("HEAD", "main", "origin/main", "origin/HEAD")
    }
    if set(refs.values()) != {lock_commit}:
        raise P1TemporalConsumerSeed20260613PatchError(
            f"E0-MK local/tracking refs diverged: {refs}"
        )
    if verify_remote and _remote_main_oid() != lock_commit:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK execution HEAD differs from live origin/main"
        )
    return (
        lock_commit,
        _git_record(
            lock_commit,
            lock_path,
            role="external_p1_temporal_consumer_seed_20260613_patch_lock",
        ),
        _git_record(
            lock_commit,
            companion_path,
            role="p1_temporal_consumer_seed_20260613_patch_companion",
        ),
    )


def load_and_validate_p1_temporal_consumer_seed_20260613_patch_lock(
    lock_path: Path = DEFAULT_PATCH_LOCK_PATH,
    lock_schema: Path = DEFAULT_PATCH_LOCK_SCHEMA,
    companion_path: Path = DEFAULT_PATCH_MANIFEST_PATH,
    *,
    require_published: bool = True,
    verify_remote: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if (
        lock_path != DEFAULT_PATCH_LOCK_PATH
        or lock_schema != DEFAULT_PATCH_LOCK_SCHEMA
        or companion_path != DEFAULT_PATCH_MANIFEST_PATH
    ):
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK requires closed default paths"
        )
    payload = _load_regular_json(lock_path, context="E0-MK lock")
    schema = _load_regular_json(lock_schema, context="E0-MK schema")
    # Static/Git validation deliberately precedes any physical P1 audit.
    validate_p1_temporal_consumer_seed_20260613_patch_lock_payload(
        payload,
        schema,
        require_physical_audit=False,
    )
    lock_record = _file_record(
        lock_path,
        role="external_p1_temporal_consumer_seed_20260613_patch_lock",
    )
    companion = _load_regular_json(companion_path, context="E0-MK companion")
    if companion != _expected_companion(payload, lock_record=lock_record):
        raise P1TemporalConsumerSeed20260613PatchError("E0-MK companion drifted")
    companion_record = _file_record(
        companion_path,
        role="p1_temporal_consumer_seed_20260613_patch_companion",
    )
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    _require_ancestor(patch_head, execution_head)
    if require_published:
        status = _git("status", "--porcelain", "--untracked-files=all")
        if status:
            raise P1TemporalConsumerSeed20260613PatchError(
                f"E0-MK execution requires a clean worktree: {status}"
            )
        lock_commit, git_lock_record, git_companion_record = _validate_publication_bundle(
            payload,
            execution_head=execution_head,
            verify_remote=verify_remote,
        )
        if lock_record != git_lock_record or companion_record != git_companion_record:
            raise P1TemporalConsumerSeed20260613PatchError(
                "Published E0-MK bytes drifted"
            )
        validate_p1_temporal_consumer_seed_20260613_patch_lock_payload(
            payload,
            schema,
            require_physical_audit=True,
        )
        effective = True
    else:
        if execution_head != patch_head:
            raise P1TemporalConsumerSeed20260613PatchError(
                "Unpublished E0-MK validation must run at H-E0-MK"
            )
        validate_p1_temporal_consumer_seed_20260613_patch_lock_payload(
            payload,
            schema,
            require_physical_audit=True,
        )
        lock_commit = ""
        effective = False
    authorities = cast(Mapping[str, Any], payload["base_authorities"])
    mi_authority = cast(Mapping[str, Any], authorities["e0_mi"])
    mj_authority = cast(Mapping[str, Any], authorities["e0_mj"])
    audit_evidence = dict(
        cast(
            Mapping[str, Any],
            cast(Mapping[str, Any], payload["verification"])["p1_bundle_audit"],
        )
    )
    schema_preflight_evidence = dict(
        cast(
            Mapping[str, Any],
            cast(Mapping[str, Any], payload["verification"])[
                "schema_subset_preflight"
            ],
        )
    )
    mj_lock_record = dict(cast(Mapping[str, Any], mj_authority["lock"]))
    mj_companion_record = dict(
        cast(Mapping[str, Any], mj_authority["companion_manifest"])
    )
    builder_with_role = cast(
        Mapping[str, Any], payload["current_runtime_builder_record"]
    )
    builder_record = {
        key: builder_with_role[key] for key in ("path", "bytes", "sha256")
    }
    summary = {
        "status": (
            "published_p1_temporal_consumer_seed_20260613_patch_valid"
            if effective
            else "locked_unpublished"
        ),
        "gate": PATCH_GATE,
        "patch_head": patch_head,
        "lock_commit": lock_commit or None,
        "execution_head": execution_head,
        "publication_verified": effective,
        "remote_publication_verified": effective and verify_remote,
        "historical_e0_mi_verified": True,
        "historical_mi_effective_loader_called": False,
        "historical_e0_mj_verified": True,
        "historical_mj_effective_loader_called": False,
        "p1_1729_slot_preserved": True,
        "p1_20260612_slot_preserved": True,
        "p1_20260613_sequence_bundle_verified": True,
        "schema_subset_preflight_verified": True,
        "schema_subset_preflight_evidence": schema_preflight_evidence,
        "schema_supported_subset_verified": True,
        "minimum_keyword_absent": True,
        "format_keyword_absent": True,
        "numeric_bounds_validated_semantically": True,
        "timestamp_validated_semantically": True,
        "in_process_audit_verified": effective,
        "in_process_audit_evidence": audit_evidence,
        "consumer_namespace_absent": True,
        "later_seed_namespaces_absent": True,
        "progression_prelock_verified": True,
        "authorization_effective": effective,
        "p1_consumer_authorized": effective,
        "p1_fit_authorized": False,
        "fit_attempt_authorized": False,
        "p1_sequence_builder_authorized": False,
        "dvc_commands_authorized": False,
        "authorized_model_id": AUTHORIZED_MODEL_ID,
        "authorized_base_seed": AUTHORIZED_BASE_SEED,
        "authorized_device": AUTHORIZED_DEVICE,
        "p1_artifact_builder_record": builder_record,
        "current_runtime_builder_record": dict(builder_record),
        "state_consumer_authority": None,
        "sequence_authority_input_records": [
            mj_lock_record,
            mj_companion_record,
        ],
        "authority_input_records": [lock_record, companion_record],
        "fit_availability": dict(FIT_AVAILABILITY),
        "sequence_fit_available": False,
        "expected_slot_status": FIT_AVAILABILITY["expected_slot_status"],
        "expected_fit_status": FIT_AVAILABILITY["expected_fit_status"],
        "expected_failure_reason": FIT_AVAILABILITY["expected_failure_reason"],
        "auditor_execution_mode": "in_process_callable",
        "python_auditor_subprocess_used": False,
        "batch_seed_execution_authorized": False,
        "retry_authorized": False,
        "replacement_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }
    return payload, summary


def require_p1_temporal_consumer_seed_20260613_patch_authorized(
    *,
    model_id: str,
    base_seed: int,
    device: str,
) -> dict[str, Any]:
    """Require published E0-MK for exactly the P1/20260613/CPU consumer."""
    if (
        model_id != AUTHORIZED_MODEL_ID
        or base_seed != AUTHORIZED_BASE_SEED
        or device != AUTHORIZED_DEVICE
    ):
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK authorizes only the P1 seed 20260613 CPU temporal consumer"
        )
    _, summary = load_and_validate_p1_temporal_consumer_seed_20260613_patch_lock(
        require_published=True,
        verify_remote=True,
    )
    required_true = (
        "publication_verified",
        "remote_publication_verified",
        "historical_e0_mi_verified",
        "historical_e0_mj_verified",
        "p1_1729_slot_preserved",
        "p1_20260612_slot_preserved",
        "p1_20260613_sequence_bundle_verified",
        "schema_subset_preflight_verified",
        "schema_supported_subset_verified",
        "minimum_keyword_absent",
        "format_keyword_absent",
        "numeric_bounds_validated_semantically",
        "timestamp_validated_semantically",
        "in_process_audit_verified",
        "consumer_namespace_absent",
        "later_seed_namespaces_absent",
        "progression_prelock_verified",
        "authorization_effective",
        "p1_consumer_authorized",
    )
    failed = [field for field in required_true if summary.get(field) is not True]
    if failed:
        raise P1TemporalConsumerSeed20260613PatchError(
            f"E0-MK authorization predicates failed: {failed}"
        )
    required_false = (
        "sequence_fit_available",
        "p1_fit_authorized",
        "fit_attempt_authorized",
        "p1_sequence_builder_authorized",
        "dvc_commands_authorized",
        "historical_mi_effective_loader_called",
        "historical_mj_effective_loader_called",
        "python_auditor_subprocess_used",
        "batch_seed_execution_authorized",
        "retry_authorized",
        "replacement_authorized",
        "e0_m_authorized",
        "evaluation_authorized",
        "e0_u_authorized",
        "future_outcomes_accessed",
    )
    drifted = [field for field in required_false if summary.get(field) is not False]
    if drifted:
        raise P1TemporalConsumerSeed20260613PatchError(
            f"E0-MK fail-closed seals drifted: {drifted}"
        )
    if summary.get("fit_availability") != FIT_AVAILABILITY:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK fit availability drifted"
        )
    if summary.get("schema_subset_preflight_evidence") != (
        preflight_p1_temporal_consumer_seed_20260613_patch_schema()
    ):
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK schema-subset preflight summary drifted"
        )
    if summary.get("state_consumer_authority") is not None:
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK must not apply the historical seed-1729 ANFIS exception"
        )
    for field in ("sequence_authority_input_records", "authority_input_records"):
        records = summary.get(field)
        if (
            not isinstance(records, Sequence)
            or isinstance(records, (str, bytes))
            or len(records) != 2
            or not all(isinstance(record, Mapping) for record in records)
        ):
            raise P1TemporalConsumerSeed20260613PatchError(
                f"E0-MK {field} drifted"
            )
    if not isinstance(summary.get("in_process_audit_evidence"), Mapping):
        raise P1TemporalConsumerSeed20260613PatchError(
            "E0-MK lacks in-process audit evidence"
        )
    return summary


__all__ = [
    "AUTHORIZED_BASE_SEED",
    "AUTHORIZED_DEVICE",
    "AUTHORIZED_MODEL_ID",
    "DEFAULT_PATCH_LOCK_PATH",
    "DEFAULT_PATCH_LOCK_SCHEMA",
    "DEFAULT_PATCH_MANIFEST_PATH",
    "DVC_PUSH_COMMAND",
    "FIT_AVAILABILITY",
    "FOCUSED_TEST_COMMAND",
    "FOCUSED_TEST_COUNT",
    "PATCH_ADDED_PATHS",
    "PATCH_COMPONENT_ROLES",
    "PATCH_MODIFIED_PATHS",
    "PATCH_PATHS",
    "POETRY_CHECK_COMMAND",
    "PUBLICATION_GUARD_COMMAND",
    "DIFF_CHECK_COMMAND",
    "P1TemporalConsumerSeed20260613PatchError",
    "build_p1_temporal_consumer_seed_20260613_patch_lock_payload",
    "collect_p1_temporal_consumer_seed_20260613_patch_prelock_state",
    "load_and_validate_p1_temporal_consumer_seed_20260613_patch_lock",
    "p1_consumer_namespace_absence",
    "patch_component_bundle",
    "patch_git_diff_payload",
    "preflight_p1_temporal_consumer_seed_20260613_patch_schema",
    "require_p1_temporal_consumer_seed_20260613_patch_authorized",
    "run_p1_bundle_audit_in_process",
    "validate_p1_temporal_consumer_seed_20260613_patch_lock_payload",
    "validate_p1_temporal_consumer_seed_20260613_patch_verification",
]
