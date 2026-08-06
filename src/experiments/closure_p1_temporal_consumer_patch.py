#!/usr/bin/env python
"""Validate the additive Closure V1 P1 temporal-consumer authority.

E0-MD adopts the already-published P1/1729 sequence bundle for one temporal
consumer invocation.  It reconstructs E0-MC and E0-DLTVM as historical Git
authorities instead of asking their effective one-shot loaders to validate a
later runtime.  The gate never opens evaluation, E0-M, E0-U, holdout, or
post-2021 outcome access.  The locked invocation is expected to close as
``model_unavailable`` because 488 fit-role intent rows are unavailable.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from src.experiments import audit_closure_p1_sequence_bundle as p1_audit
from src.experiments import (
    closure_development_runtime_temporal_validation_manifest_patch as dltvm,
)
from src.experiments import closure_p1_sequence_historical_anfis_patch as e0_mc
from src.experiments.closure_contract import ClosureContractError, validate_json_schema


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOCK_VERSION = "closure_p1_temporal_consumer_patch_lock_v1"
PATCH_GATE = "E0-MD"
PATCH_ID = "p1_temporal_consumer_authority_patch_1"
PATCH_STATUS = "locked"
EXPERIMENT_ID = "closure_v1"
SURFACE_ID = "closure_v1_wqp_adaptive_no_current_chla"
PUBLISHED_REF = "origin/main"

AUTHORIZED_MODEL_ID = "P1"
AUTHORIZED_BASE_SEED = 1729
AUTHORIZED_DEVICE = "cpu"

E0_MC_H_COMMIT = "5bdac0fe8279297dbdb04e38146726431511fe7a"
E0_MC_P_COMMIT = "d76f35b20a0d5b5515ec31acbca1e953730afce4"
P1_BUNDLE_COMMIT = "82c0bc10a8b17ab700a8f0c28491a60572a11d81"
PATCH_BASE_COMMIT = P1_BUNDLE_COMMIT
H_DLTVM_COMMIT = "3ee008faef331f40cf73d1f1e3db59608b0deab1"
P_DLTVM_COMMIT = "4ba5ecd45da7f0b25277c0a13602999413fa2849"

DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/p1_temporal_consumer_patch_lock.json"
)
DEFAULT_PATCH_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/p1_temporal_consumer_patch_lock_manifest.json"
)
DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/p1_temporal_consumer_patch_lock.schema.json"
)

PATCH_COMPONENT_ROLES = {
    DEFAULT_PATCH_LOCK_SCHEMA.as_posix(): "p1_temporal_consumer_patch_lock_schema",
    "docs/closure_v1/E0_M_P1_TEMPORAL_CONSUMER_PATCH_1.md": (
        "p1_temporal_consumer_patch_protocol"
    ),
    "src/experiments/closure_p1_temporal_consumer_patch.py": (
        "p1_temporal_consumer_patch_validator"
    ),
    "src/experiments/lock_closure_p1_temporal_consumer_patch.py": (
        "p1_temporal_consumer_patch_locker"
    ),
    "src/experiments/train_closure_pipe.py": "p1_temporal_consumer_gate_routing",
    "tests/test_closure_p1_temporal_consumer_patch.py": (
        "p1_temporal_consumer_patch_tests"
    ),
    "tests/test_train_closure_pipe.py": "p1_temporal_consumer_gate_tests",
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))
PATCH_MODIFIED_PATHS = (
    "src/experiments/train_closure_pipe.py",
    "tests/test_train_closure_pipe.py",
)
PATCH_ADDED_PATHS = tuple(
    path for path in PATCH_PATHS if path not in PATCH_MODIFIED_PATHS
)

DLTVM_SUPERSEDED_PATHS = (
    "src/experiments/build_closure_pipe_sequences.py",
    "src/experiments/train_closure_pipe.py",
    "tests/test_build_closure_pipe_sequences.py",
    "tests/test_train_closure_pipe.py",
)
DLTVM_PRESERVED_PATHS = tuple(
    path for path in dltvm.PATCH_PATHS if path not in DLTVM_SUPERSEDED_PATHS
)

P1_ARTIFACT_BUILDER_RECORD = {
    "path": "src/experiments/build_closure_pipe_sequences.py",
    "bytes": 127_833,
    "sha256": "f0e653b29035acb11e39bc9a7776e7940394996d75f16bf3bccb4da30013c9cf",
}

P1_PUBLICATION_ROLES = {
    p1_audit.P1_POINTER_PATH.as_posix(): "p1_sequence_dvc_pointer",
    p1_audit.P1_MANIFEST_PATH.as_posix(): "p1_sequence_completion_manifest",
    p1_audit.P1_SUMMARY_PATH.as_posix(): "p1_sequence_summary",
    p1_audit.AUDITOR_PATH.as_posix(): "p1_sequence_bundle_auditor",
    "tests/test_audit_closure_p1_sequence_bundle.py": "p1_sequence_bundle_auditor_tests",
}
P1_PUBLICATION_PATHS = tuple(sorted(P1_PUBLICATION_ROLES))

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

PATCH_CORRECTION = {
    "issue_id": "p1_temporal_consumer_authority_adoption_1",
    "classification": "consumer_authority_adapter_only",
    "historical_dltvm_effective_loader_called": False,
    "historical_e0_mc_loader_mode": "git_bound_published_lock_snapshot",
    "scientific_runtime_contract_changed": False,
    "sequence_contract_changed": False,
    "denominator_changed": False,
    "state_mapping_changed": False,
    "model_unavailable_semantics_changed": False,
    "outcome_access_changed": False,
}
PATCH_AUTHORIZATIONS = {
    "authorized_model_id": AUTHORIZED_MODEL_ID,
    "authorized_base_seed": AUTHORIZED_BASE_SEED,
    "authorized_device": AUTHORIZED_DEVICE,
    "p1_consumer_authorized": False,
    "p1_fit_authorized": False,
    "effective_in_payload": False,
    "publication_required": True,
    "batch_seed_execution_authorized": False,
    "retry_authorized": False,
    "e0_m_authorized": False,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
    "future_outcomes_accessed": False,
}
PATCH_SEALS = {
    "e0_mc_preserved_as_historical_authority": True,
    "e0_mb_nested_historical_authority_preserved": True,
    "e0_dltvm_preserved_as_historical_authority": True,
    "p1_sequence_bundle_preserved": True,
    "p1_sequence_bundle_rewritten": False,
    "consumer_outputs_absent_at_lock": True,
    "failed_slot_replacement": False,
    "model_artifact_expected": False,
    "holdout_accessed": False,
    "post_2021_outcomes_accessed": False,
    "does_not_replace_e0_m": True,
}

TYPE_CHECK_COMMAND = (".venv/bin/ty", "check")
FOCUSED_TEST_COMMAND = (
    ".venv/bin/pytest",
    "tests/test_closure_p1_temporal_consumer_patch.py",
    "tests/test_train_closure_pipe.py",
    "tests/test_closure_development_runtime_temporal_consumer_patch.py",
    "tests/test_closure_development_runtime_temporal_validation_manifest_patch.py",
    "tests/test_audit_closure_p1_sequence_bundle.py",
    "-q",
)
# Finalized from the exact closed five-file H-E0-MD collection.
FOCUSED_TEST_COUNT = 188
POETRY_CHECK_COMMAND = ("poetry", "check")
PUBLICATION_GUARD_COMMAND = ("scripts/check_repo_publication_ready.sh",)
DIFF_CHECK_COMMAND = ("git", "diff", "--check")
P1_AUDIT_COMMAND = (
    ".venv/bin/python",
    "src/experiments/audit_closure_p1_sequence_bundle.py",
    "--check-only",
)
DVC_PUSH_COMMAND = (
    ".venv/bin/dvc",
    "push",
    "data/closure_v1/development/sequences/P1/seed_1729.parquet.dvc",
)


class P1TemporalConsumerPatchError(RuntimeError):
    """Raised when E0-MD cannot prove its closed consumer authority."""


def _translate(error: BaseException) -> P1TemporalConsumerPatchError:
    return P1TemporalConsumerPatchError(str(error))


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
        return e0_mc._git(*args)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _require_commit(value: str, *, context: str) -> str:
    try:
        return e0_mc._require_commit(value, context=context)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _require_ancestor(ancestor: str, descendant: str) -> None:
    try:
        e0_mc._require_ancestor(ancestor, descendant)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _git_blob(commit: str, path: str) -> bytes:
    try:
        return e0_mc._git_blob(commit, path)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _load_regular_json(path: Path, *, context: str) -> dict[str, Any]:
    try:
        return e0_mc._load_regular_json(path, context=context)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _file_record(path: Path, *, role: str) -> dict[str, Any]:
    try:
        return e0_mc._file_record(path, role=role)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _git_record(commit: str, path: str, *, role: str) -> dict[str, Any]:
    payload = _git_blob(commit, path)
    return {
        "path": path,
        "role": role,
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def _generic_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": record["path"],
        "bytes": record["bytes"],
        "sha256": record["sha256"],
    }


def _observed_diff_entries(base: str, head: str) -> list[dict[str, str]]:
    try:
        return e0_mc._observed_diff_entries(base, head)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _assert_paths_untouched(
    base: str,
    descendant: str,
    paths: Sequence[str],
    *,
    context: str,
) -> None:
    try:
        e0_mc._assert_paths_untouched(base, descendant, paths, context=context)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _introduced_commit(path: str) -> str:
    try:
        return e0_mc._introduced_commit(path)
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def _remote_main_oid() -> str:
    try:
        return e0_mc._remote_main_oid()
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc


def patch_git_diff_payload(patch_head: str) -> dict[str, Any]:
    patch_head = _require_commit(patch_head, context="H-E0-MD")
    ancestry = _git("rev-list", "--parents", "-n", "1", patch_head).split()
    if ancestry != [patch_head, PATCH_BASE_COMMIT]:
        raise P1TemporalConsumerPatchError(
            "H-E0-MD must be the direct non-merge child of the P1 bundle commit"
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
        raise P1TemporalConsumerPatchError(
            f"H-E0-MD diff differs from its closed 2M+5A allowlist: {observed}"
        )
    return {
        "base_commit": PATCH_BASE_COMMIT,
        "patch_head": patch_head,
        "entries": expected,
        "paths": list(PATCH_PATHS),
        "paths_sha256": _path_digest(PATCH_PATHS),
        "added_count": len(PATCH_ADDED_PATHS),
        "modified_count": len(PATCH_MODIFIED_PATHS),
        "only_allowed_additions_and_modifications": True,
    }


def patch_component_bundle(patch_head: str) -> dict[str, Any]:
    patch_head = _require_commit(patch_head, context="H-E0-MD")
    records = [
        _git_record(
            patch_head,
            path,
            role=PATCH_COMPONENT_ROLES[path],
        )
        for path in PATCH_PATHS
    ]
    return {
        "count": len(records),
        "paths": list(PATCH_PATHS),
        "paths_sha256": _path_digest(PATCH_PATHS),
        "records": records,
        "records_sha256": _record_digest(records),
    }


def _require_git_record_physical(record: Mapping[str, Any]) -> None:
    physical = _file_record(Path(str(record["path"])), role=str(record["role"]))
    if physical != record:
        raise P1TemporalConsumerPatchError(
            f"Physical component drifted: {record['path']}"
        )


def _validate_p1_publication_topology() -> list[dict[str, Any]]:
    ancestry = _git("rev-list", "--parents", "-n", "1", P1_BUNDLE_COMMIT).split()
    if ancestry != [P1_BUNDLE_COMMIT, E0_MC_P_COMMIT]:
        raise P1TemporalConsumerPatchError(
            "The P1/1729 bundle is not the direct child of P-E0-MC"
        )
    expected = [{"status": "A", "path": path} for path in P1_PUBLICATION_PATHS]
    observed = _observed_diff_entries(E0_MC_P_COMMIT, P1_BUNDLE_COMMIT)
    if observed != expected:
        raise P1TemporalConsumerPatchError(
            f"P1/1729 publication differs from its exact 5A bundle: {observed}"
        )
    records = [
        _git_record(P1_BUNDLE_COMMIT, path, role=P1_PUBLICATION_ROLES[path])
        for path in P1_PUBLICATION_PATHS
    ]
    for record in records:
        _require_git_record_physical(record)
    return records


def _e0_mc_historical_authority(
    *,
    execution_head: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = _load_regular_json(e0_mc.DEFAULT_PATCH_LOCK_PATH, context="P-E0-MC lock")
    schema = _load_regular_json(e0_mc.DEFAULT_PATCH_LOCK_SCHEMA, context="E0-MC schema")
    try:
        validate_json_schema(
            payload,
            schema,
            instance_path="$.historical_p1_sequence_historical_anfis_patch_lock",
        )
    except ClosureContractError as exc:
        raise _translate(exc) from exc
    fixed = {
        "lock_version": e0_mc.LOCK_VERSION,
        "status": e0_mc.PATCH_STATUS,
        "experiment_id": e0_mc.EXPERIMENT_ID,
        "surface_id": e0_mc.SURFACE_ID,
        "gate": e0_mc.PATCH_GATE,
        "patch_id": e0_mc.PATCH_ID,
        "correction": e0_mc.PATCH_CORRECTION,
        "authorizations": e0_mc.PATCH_AUTHORIZATIONS,
        "seals": e0_mc.PATCH_SEALS,
    }
    drifted = [field for field, expected in fixed.items() if payload.get(field) != expected]
    if drifted:
        raise P1TemporalConsumerPatchError(
            f"Published E0-MC fixed fields drifted: {drifted}"
        )
    repository = cast(Mapping[str, Any], payload.get("patch_repository", {}))
    if repository.get("head") != E0_MC_H_COMMIT:
        raise P1TemporalConsumerPatchError("Published E0-MC identity drifted")
    try:
        expected_git_diff = e0_mc.patch_git_diff_payload(E0_MC_H_COMMIT)
        expected_components = e0_mc.patch_component_bundle(E0_MC_H_COMMIT)
        e0_mc.validate_p1_sequence_historical_anfis_patch_verification(
            cast(Mapping[str, Any], payload["verification"])
        )
    except e0_mc.P1SequenceHistoricalAnfisPatchError as exc:
        raise _translate(exc) from exc
    if payload.get("git_diff") != expected_git_diff:
        raise P1TemporalConsumerPatchError("Published H-E0-MC Git diff drifted")
    if payload.get("patch_components") != expected_components:
        raise P1TemporalConsumerPatchError("Published H-E0-MC components drifted")
    for record in cast(Sequence[Mapping[str, Any]], expected_components["records"]):
        _require_git_record_physical(record)
    _assert_paths_untouched(
        E0_MC_H_COMMIT,
        execution_head,
        e0_mc.PATCH_PATHS,
        context="H-E0-MC components",
    )
    current_builder = cast(
        Mapping[str, Any], payload.get("current_runtime_builder_record", {})
    )
    if _generic_record(current_builder) != P1_ARTIFACT_BUILDER_RECORD:
        raise P1TemporalConsumerPatchError("E0-MC current runtime builder drifted")
    lock_record = _git_record(
        E0_MC_P_COMMIT,
        e0_mc.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        role="external_p1_sequence_historical_anfis_patch_lock",
    )
    companion_record = _git_record(
        E0_MC_P_COMMIT,
        e0_mc.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        role="p1_sequence_historical_anfis_patch_companion",
    )
    _require_git_record_physical(lock_record)
    _require_git_record_physical(companion_record)
    if (
        _introduced_commit(e0_mc.DEFAULT_PATCH_LOCK_PATH.as_posix())
        != E0_MC_P_COMMIT
        or _introduced_commit(e0_mc.DEFAULT_PATCH_MANIFEST_PATH.as_posix())
        != E0_MC_P_COMMIT
        or _git("rev-list", "--parents", "-n", "1", E0_MC_P_COMMIT).split()
        != [E0_MC_P_COMMIT, E0_MC_H_COMMIT]
    ):
        raise P1TemporalConsumerPatchError("P-E0-MC publication topology drifted")
    companion = _load_regular_json(
        e0_mc.DEFAULT_PATCH_MANIFEST_PATH,
        context="P-E0-MC companion",
    )
    if companion != e0_mc._expected_companion(payload, lock_record=lock_record):
        raise P1TemporalConsumerPatchError("Published E0-MC companion drifted")
    _assert_paths_untouched(
        E0_MC_P_COMMIT,
        execution_head,
        (
            e0_mc.DEFAULT_PATCH_LOCK_PATH.as_posix(),
            e0_mc.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        ),
        context="P-E0-MC lock bundle",
    )
    base_authorities = payload.get("base_authorities")
    if not isinstance(base_authorities, Mapping) or not isinstance(
        base_authorities.get("e0_mb"), Mapping
    ):
        raise P1TemporalConsumerPatchError(
            "E0-MC does not retain its nested historical E0-MB authority"
        )
    mb_authority = cast(Mapping[str, Any], base_authorities["e0_mb"])
    if (
        mb_authority.get("gate") != "E0-MB"
        or mb_authority.get("patch_head") != e0_mc.E0_MB_H_COMMIT
        or mb_authority.get("lock_commit") != e0_mc.E0_MB_P_COMMIT
    ):
        raise P1TemporalConsumerPatchError("Nested historical E0-MB identity drifted")
    for field in ("lock", "companion_manifest"):
        record = mb_authority.get(field)
        if not isinstance(record, Mapping):
            raise P1TemporalConsumerPatchError(
                f"Nested historical E0-MB {field} record is malformed"
            )
        _require_git_record_physical(cast(Mapping[str, Any], record))
    context = {
        "gate": "E0-MC",
        "authorized_model_id": AUTHORIZED_MODEL_ID,
        "authorized_base_seed": AUTHORIZED_BASE_SEED,
        "prior_one_shot_authorization_consumed": True,
        "p1_sequence_retry_authorized": True,
        "publication_verified": True,
        "remote_publication_verified": True,
        "historical_e0_mb_verified": True,
        "historical_e0_dlp_verified": True,
        "historical_anfis_context_verified": True,
        "transactional_builder_verified": True,
        "sequence_namespace_absent": True,
        "p1_sequence_builder_authorized": True,
        "authorization_effective": True,
        "batch_seed_execution_authorized": False,
        "retry_under_previous_authority_authorized": False,
        "effective_in_payload": False,
        "publication_required": False,
        "p1_fit_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "authorization_inputs": [lock_record, companion_record],
    }
    return (
        {
            "gate": "E0-MC",
            "patch_head": E0_MC_H_COMMIT,
            "lock_commit": E0_MC_P_COMMIT,
            "lock": lock_record,
            "companion": companion_record,
            "lock_snapshot": dict(payload),
            "nested_e0_mb": dict(cast(Mapping[str, Any], base_authorities["e0_mb"])),
            "current_runtime_builder_record": dict(current_builder),
            "publication_topology_verified": True,
            "historical_loader_used": False,
            "git_bound_lock_snapshot_used": True,
            "effective_one_shot_loader_called": False,
            "historical_authority_verified": True,
            "future_outcomes_accessed": False,
        },
        context,
    )


def _historical_dltvm_authority(*, execution_head: str) -> dict[str, Any]:
    payload = _load_regular_json(dltvm.DEFAULT_PATCH_LOCK_PATH, context="P-E0-DLTVM lock")
    schema = _load_regular_json(dltvm.DEFAULT_PATCH_LOCK_SCHEMA, context="E0-DLTVM schema")
    try:
        validate_json_schema(
            payload,
            schema,
            instance_path="$.historical_development_runtime_temporal_validation_manifest_patch_lock",
        )
    except ClosureContractError as exc:
        raise _translate(exc) from exc
    fixed = {
        "lock_version": dltvm.LOCK_VERSION,
        "status": dltvm.PATCH_STATUS,
        "experiment_id": dltvm.EXPERIMENT_ID,
        "gate": dltvm.PATCH_GATE,
        "patch_id": dltvm.PATCH_ID,
        "correction": dltvm.PATCH_CORRECTION,
        "authorizations": dltvm.PATCH_AUTHORIZATIONS,
        "seals": dltvm.PATCH_SEALS,
    }
    drifted = [field for field, expected in fixed.items() if payload.get(field) != expected]
    if drifted:
        raise P1TemporalConsumerPatchError(
            f"Historical E0-DLTVM fixed fields drifted: {drifted}"
        )
    repository = cast(Mapping[str, Any], payload.get("patch_repository", {}))
    if repository.get("head") != H_DLTVM_COMMIT:
        raise P1TemporalConsumerPatchError("Historical H-DLTVM identity drifted")
    try:
        expected_git_diff = dltvm.patch_git_diff_payload(H_DLTVM_COMMIT)
        expected_components = dltvm.patch_component_bundle(H_DLTVM_COMMIT)
    except dltvm.DevelopmentRuntimeTemporalValidationManifestPatchError as exc:
        raise _translate(exc) from exc
    if payload.get("git_diff") != expected_git_diff:
        raise P1TemporalConsumerPatchError("Historical H-DLTVM Git diff drifted")
    if payload.get("patch_components") != expected_components:
        raise P1TemporalConsumerPatchError(
            "Historical H-DLTVM component bundle drifted"
        )
    ancestry = _git("rev-list", "--parents", "-n", "1", P_DLTVM_COMMIT).split()
    if ancestry != [P_DLTVM_COMMIT, H_DLTVM_COMMIT]:
        raise P1TemporalConsumerPatchError("P-E0-DLTVM topology drifted")
    lock_record = _git_record(
        P_DLTVM_COMMIT,
        dltvm.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        role="external_development_runtime_temporal_validation_dialect_patch_lock",
    )
    companion_record = _git_record(
        P_DLTVM_COMMIT,
        dltvm.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        role="development_runtime_temporal_validation_manifest_patch_companion",
    )
    _require_git_record_physical(lock_record)
    _require_git_record_physical(companion_record)
    companion = _load_regular_json(
        dltvm.DEFAULT_PATCH_MANIFEST_PATH,
        context="P-E0-DLTVM companion",
    )
    if companion != dltvm._expected_companion(payload, lock_record=lock_record):
        raise P1TemporalConsumerPatchError("Historical E0-DLTVM companion drifted")
    _assert_paths_untouched(
        P_DLTVM_COMMIT,
        execution_head,
        (
            dltvm.DEFAULT_PATCH_LOCK_PATH.as_posix(),
            dltvm.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        ),
        context="P-E0-DLTVM lock bundle",
    )
    components = cast(Mapping[str, Any], payload.get("patch_components", {}))
    raw_records = components.get("records")
    if not isinstance(raw_records, Sequence) or isinstance(raw_records, (str, bytes)):
        raise P1TemporalConsumerPatchError("Historical H-DLTVM components are malformed")
    records = [dict(cast(Mapping[str, Any], record)) for record in raw_records]
    by_path = {str(record.get("path")): record for record in records}
    if set(by_path) != set(dltvm.PATCH_PATHS) or len(by_path) != len(records):
        raise P1TemporalConsumerPatchError("Historical H-DLTVM paths drifted")
    superseded = [by_path[path] for path in DLTVM_SUPERSEDED_PATHS]
    preserved = [by_path[path] for path in DLTVM_PRESERVED_PATHS]
    for record in records:
        if _git_record(
            H_DLTVM_COMMIT,
            str(record["path"]),
            role=str(record["role"]),
        ) != record:
            raise P1TemporalConsumerPatchError(
                f"Historical H-DLTVM Git component drifted: {record['path']}"
            )
    for record in preserved:
        _require_git_record_physical(record)
    _assert_paths_untouched(
        H_DLTVM_COMMIT,
        execution_head,
        DLTVM_PRESERVED_PATHS,
        context="preserved H-DLTVM components",
    )
    return {
        "gate": "E0-DLTVM",
        "patch_head": H_DLTVM_COMMIT,
        "lock_commit": P_DLTVM_COMMIT,
        "lock": lock_record,
        "companion": companion_record,
        "lock_snapshot": dict(payload),
        "superseded_components": {
            "count": len(superseded),
            "paths": list(DLTVM_SUPERSEDED_PATHS),
            "records": superseded,
            "records_sha256": _record_digest(superseded),
            "current_bytes_required_to_match_historical": False,
        },
        "preserved_components": {
            "count": len(preserved),
            "paths": list(DLTVM_PRESERVED_PATHS),
            "records": preserved,
            "records_sha256": _record_digest(preserved),
            "current_bytes_required_to_match_historical": True,
        },
        "historical_effective_loader_called": False,
        "historical_git_authority_verified": True,
        "future_outcomes_accessed": False,
    }


def _fit_availability_from_audit(result: Mapping[str, Any]) -> dict[str, Any]:
    observed = result.get("fit_availability")
    if not isinstance(observed, Mapping):
        raise P1TemporalConsumerPatchError("P1 audit fit availability is malformed")
    expected = {
        "available": False,
        "observed_fit_status_counts": FIT_AVAILABILITY["fit_status_counts"],
        "observed_fit_failure_reason_counts": FIT_AVAILABILITY[
            "fit_failure_reason_counts"
        ],
        "observed_calibration_failure_count": FIT_AVAILABILITY[
            "calibration_failure_count"
        ],
        "expected_temporal_slot_status": FIT_AVAILABILITY["expected_slot_status"],
        "expected_fit_status": FIT_AVAILABILITY["expected_fit_status"],
        "expected_failure_reason": FIT_AVAILABILITY["expected_failure_reason"],
        "consumer_executed_by_auditor": False,
        "fit_or_model_construction_executed_by_auditor": False,
    }
    drifted = [key for key, value in expected.items() if observed.get(key) != value]
    if drifted:
        raise P1TemporalConsumerPatchError(
            f"P1 audit model-unavailable evidence drifted: {drifted}"
        )
    return dict(FIT_AVAILABILITY)


def _p1_sequence_bundle_authority() -> dict[str, Any]:
    publication_records = _validate_p1_publication_topology()
    try:
        result = p1_audit.audit_p1_sequence_bundle()
    except p1_audit.ClosureP1SequenceAuditError as exc:
        raise _translate(exc) from exc
    namespace = result.get("namespace_evidence")
    if not isinstance(namespace, Mapping):
        raise P1TemporalConsumerPatchError("P1 audit namespace evidence is malformed")
    try:
        p1_audit._require_pre_consumer_progression_clear(namespace)
    except p1_audit.ClosureP1SequenceAuditError as exc:
        raise _translate(exc) from exc
    result["pre_consumer_progression_gate"] = "passed"
    progression = namespace.get("progression_observation")
    if not isinstance(progression, Mapping):
        raise P1TemporalConsumerPatchError("P1 progression evidence is malformed")
    expected_progression = {
        "registered_p1_path_count": 140,
        "consumer_seed_1729_present_paths": [],
        "future_seed_present_paths": [],
        "e0_m_present_paths": [],
        "outcome_access_log_present": False,
        "pre_consumer_and_pre_e0_m_clear_now": True,
    }
    progression_drift = [
        field
        for field, expected in expected_progression.items()
        if progression.get(field) != expected
    ]
    registered_present = progression.get("registered_present_paths")
    if (
        progression_drift
        or not isinstance(registered_present, list)
        or len(registered_present) != 4
    ):
        raise P1TemporalConsumerPatchError(
            "P1 pre-consumer progression evidence drifted: "
            f"fields={progression_drift}"
        )
    if (
        result.get("status") != "validated"
        or result.get("model_id") != AUTHORIZED_MODEL_ID
        or result.get("base_seed") != AUTHORIZED_BASE_SEED
        or result.get("pre_consumer_progression_gate") != "passed"
        or result.get("audited_namespaces_unchanged") is not True
        or result.get("future_outcomes_accessed_by_auditor") is not False
        or result.get("one_shot_reconsumed_by_auditor") is not False
    ):
        raise P1TemporalConsumerPatchError("P1 sequence audit safety evidence drifted")
    fit = _fit_availability_from_audit(result)
    outputs = result.get("outputs")
    if not isinstance(outputs, Sequence) or isinstance(outputs, (str, bytes)):
        raise P1TemporalConsumerPatchError("P1 sequence audit outputs are malformed")
    output_roles = {
        p1_audit.P1_SEQUENCE_PATH.as_posix(): "p1_sequence_parquet",
        p1_audit.P1_SUMMARY_PATH.as_posix(): "p1_sequence_summary",
        p1_audit.P1_MANIFEST_PATH.as_posix(): "p1_sequence_completion_manifest",
    }
    physical_outputs = []
    for raw in outputs:
        record = dict(cast(Mapping[str, Any], raw))
        path = str(record.get("path"))
        if path not in output_roles:
            raise P1TemporalConsumerPatchError("P1 audit output path drifted")
        physical_outputs.append({**record, "role": output_roles[path]})
    physical_outputs.sort(key=lambda record: str(record["path"]))
    if [str(record["path"]) for record in physical_outputs] != sorted(output_roles):
        raise P1TemporalConsumerPatchError("P1 audit output set drifted")
    return {
        "commit": P1_BUNDLE_COMMIT,
        "parent": E0_MC_P_COMMIT,
        "publication_records": publication_records,
        "physical_output_records": physical_outputs,
        "dvc_registration": dict(
            cast(Mapping[str, Any], result.get("dvc_registration", {}))
        ),
        "audit_status": "validated",
        "counts": dict(cast(Mapping[str, Any], result.get("counts", {}))),
        "fit_availability": fit,
        "namespace_evidence": dict(
            namespace
        ),
        "pre_consumer_progression_gate": "passed",
        "auditor_read_only": True,
        "consumer_executed_by_auditor": False,
        "future_outcomes_accessed_by_auditor": False,
    }


def p1_consumer_namespace_absence() -> dict[str, Any]:
    paths = [path.as_posix() for path in p1_audit.P1_CONSUMER_PATHS]
    existing = [path for path in paths if os.path.lexists(PROJECT_ROOT / path)]
    if existing:
        raise P1TemporalConsumerPatchError(
            f"P1/1729 consumer namespace is not empty: {existing}"
        )
    return {
        "model_id": AUTHORIZED_MODEL_ID,
        "base_seed": AUTHORIZED_BASE_SEED,
        "count": len(paths),
        "paths": paths,
        "paths_sha256": _path_digest(paths),
        "all_absent_at_lock": True,
    }


def collect_p1_temporal_consumer_patch_prelock_state(
    *,
    verify_remote: bool,
) -> dict[str, Any]:
    status = _git("status", "--porcelain", "--untracked-files=all")
    if status:
        raise P1TemporalConsumerPatchError(
            f"H-E0-MD lock requires a clean worktree: {status}"
        )
    head = _require_commit(_git("rev-parse", "HEAD"), context="H-E0-MD HEAD")
    if _git("branch", "--show-current") != "main":
        raise P1TemporalConsumerPatchError("H-E0-MD lock requires branch main")
    published = _require_commit(_git("rev-parse", PUBLISHED_REF), context=PUBLISHED_REF)
    main_head = _require_commit(_git("rev-parse", "main"), context="main")
    origin_head = _require_commit(_git("rev-parse", "origin/HEAD"), context="origin/HEAD")
    refs = {
        "head": head,
        "main": main_head,
        "tracking": published,
        "origin_head": origin_head,
    }
    if set(refs.values()) != {head}:
        raise P1TemporalConsumerPatchError(
            f"H-E0-MD publication refs diverged: {refs}"
        )
    remote = _remote_main_oid() if verify_remote else published
    if remote != head:
        raise P1TemporalConsumerPatchError("H-E0-MD HEAD differs from live origin/main")
    git_diff = patch_git_diff_payload(head)
    components = patch_component_bundle(head)
    for record in cast(Sequence[Mapping[str, Any]], components["records"]):
        _require_git_record_physical(record)
    e0_mc_authority, e0_mc_context = _e0_mc_historical_authority(
        execution_head=head
    )
    dltvm_authority = _historical_dltvm_authority(execution_head=head)
    bundle = _p1_sequence_bundle_authority()
    if bundle["fit_availability"] != FIT_AVAILABILITY:
        raise P1TemporalConsumerPatchError("P1 fit availability contract drifted")
    return {
        "patch_repository": {
            "head": head,
            "main_head": main_head,
            "parent": PATCH_BASE_COMMIT,
            "branch": "main",
            "published_ref": PUBLISHED_REF,
            "published_head": published,
            "origin_head": origin_head,
            "remote_main_oid": remote,
            "worktree_status": "clean",
            "exact_diff_verified": True,
        },
        "git_diff": git_diff,
        "patch_components": components,
        "base_authorities": {
            "e0_mc": {**e0_mc_authority, "context_authorization": e0_mc_context},
            "e0_dltvm": dltvm_authority,
        },
        "p1_sequence_bundle": bundle,
        "consumer_prelock": p1_consumer_namespace_absence(),
        "fit_availability": dict(FIT_AVAILABILITY),
    }


def build_p1_temporal_consumer_patch_lock_payload(
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
        "p1_sequence_bundle": dict(
            cast(Mapping[str, Any], prelock["p1_sequence_bundle"])
        ),
        "consumer_prelock": dict(cast(Mapping[str, Any], prelock["consumer_prelock"])),
        "fit_availability": dict(cast(Mapping[str, Any], prelock["fit_availability"])),
        "correction": dict(PATCH_CORRECTION),
        "verification": dict(verification),
        "authorizations": dict(PATCH_AUTHORIZATIONS),
        "seals": dict(PATCH_SEALS),
        "lock_artifact": {
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "role": "external_p1_temporal_consumer_patch_lock",
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
    if not required.issubset(evidence) or evidence.get("command") != list(command):
        raise P1TemporalConsumerPatchError(f"E0-MD {context} evidence drifted")
    if evidence.get("returncode") != 0:
        raise P1TemporalConsumerPatchError(f"E0-MD {context} did not pass")


def validate_p1_temporal_consumer_patch_verification(
    verification: Mapping[str, Any],
) -> None:
    expected = {
        "full_type_check": TYPE_CHECK_COMMAND,
        "focused_tests": FOCUSED_TEST_COMMAND,
        "poetry_check": POETRY_CHECK_COMMAND,
        "publication_guard": PUBLICATION_GUARD_COMMAND,
        "git_diff_check": DIFF_CHECK_COMMAND,
        "p1_bundle_audit": P1_AUDIT_COMMAND,
        "dvc_push_first": DVC_PUSH_COMMAND,
        "dvc_push_second": DVC_PUSH_COMMAND,
    }
    if set(verification) != set(expected):
        raise P1TemporalConsumerPatchError("E0-MD verification fields drifted")
    for field, command in expected.items():
        evidence = verification.get(field)
        if not isinstance(evidence, Mapping):
            raise P1TemporalConsumerPatchError(f"E0-MD {field} evidence is malformed")
        _validate_command_evidence(evidence, command=command, context=field)
    focused = cast(Mapping[str, Any], verification["focused_tests"])
    if (
        FOCUSED_TEST_COUNT <= 0
        or focused.get("test_count") != FOCUSED_TEST_COUNT
        or focused.get("skipped_count") != 0
        or focused.get("deselected_count") != 0
    ):
        raise P1TemporalConsumerPatchError("E0-MD focused-test evidence drifted")
    first = cast(Mapping[str, Any], verification["dvc_push_first"])
    second = cast(Mapping[str, Any], verification["dvc_push_second"])
    if first.get("terminal_status") not in {
        "1 file pushed",
        "Everything is up to date.",
    }:
        raise P1TemporalConsumerPatchError("E0-MD first DVC push evidence drifted")
    if second.get("terminal_status") != "Everything is up to date.":
        raise P1TemporalConsumerPatchError("E0-MD second DVC push is not idempotent")


def validate_p1_temporal_consumer_patch_lock_payload(
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    require_physical_artifacts: bool = True,
) -> None:
    try:
        validate_json_schema(
            payload,
            schema,
            instance_path="$.p1_temporal_consumer_patch_lock",
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
            "role": "external_p1_temporal_consumer_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
    }
    for field, expected in fixed.items():
        if payload.get(field) != expected:
            raise P1TemporalConsumerPatchError(f"E0-MD fixed field drifted: {field}")
    created = payload.get("created_at_utc")
    if not isinstance(created, str):
        raise P1TemporalConsumerPatchError("E0-MD timestamp is invalid")
    try:
        timestamp = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P1TemporalConsumerPatchError("E0-MD timestamp is invalid") from exc
    if timestamp.utcoffset() is None:
        raise P1TemporalConsumerPatchError("E0-MD timestamp requires a timezone")
    repository = cast(Mapping[str, Any], payload["patch_repository"])
    patch_head = _require_commit(str(repository.get("head", "")), context="H-E0-MD")
    if repository != {
        "head": patch_head,
        "main_head": patch_head,
        "parent": PATCH_BASE_COMMIT,
        "branch": "main",
        "published_ref": PUBLISHED_REF,
        "published_head": patch_head,
        "origin_head": patch_head,
        "remote_main_oid": patch_head,
        "worktree_status": "clean",
        "exact_diff_verified": True,
    }:
        raise P1TemporalConsumerPatchError("E0-MD patch repository record drifted")
    if payload.get("git_diff") != patch_git_diff_payload(patch_head):
        raise P1TemporalConsumerPatchError("E0-MD Git diff drifted")
    components = patch_component_bundle(patch_head)
    if payload.get("patch_components") != components:
        raise P1TemporalConsumerPatchError("E0-MD component bundle drifted")
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    _require_ancestor(patch_head, execution_head)
    if require_physical_artifacts:
        for record in cast(Sequence[Mapping[str, Any]], components["records"]):
            _require_git_record_physical(record)
        _assert_paths_untouched(
            patch_head,
            execution_head,
            PATCH_PATHS,
            context="H-E0-MD components",
        )
    e0_mc_authority, e0_mc_context = _e0_mc_historical_authority(
        execution_head=execution_head
    )
    dltvm_authority = _historical_dltvm_authority(execution_head=execution_head)
    expected_authorities = {
        "e0_mc": {**e0_mc_authority, "context_authorization": e0_mc_context},
        "e0_dltvm": dltvm_authority,
    }
    if payload.get("base_authorities") != expected_authorities:
        raise P1TemporalConsumerPatchError("E0-MD historical authorities drifted")
    if require_physical_artifacts:
        if payload.get("p1_sequence_bundle") != _p1_sequence_bundle_authority():
            raise P1TemporalConsumerPatchError("E0-MD P1 sequence bundle drifted")
        if payload.get("consumer_prelock") != p1_consumer_namespace_absence():
            raise P1TemporalConsumerPatchError("E0-MD consumer prelock drifted")
    validate_p1_temporal_consumer_patch_verification(
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
    authorities = cast(Mapping[str, Any], payload["base_authorities"])
    mc_authority = cast(Mapping[str, Any], authorities["e0_mc"])
    dltvm_authority = cast(Mapping[str, Any], authorities["e0_dltvm"])
    bundle = cast(Mapping[str, Any], payload["p1_sequence_bundle"])
    publication_records = cast(
        Sequence[Mapping[str, Any]], bundle["publication_records"]
    )

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
            "p1_temporal_consumer_patch_lock_schema",
        ),
        component(
            "src/experiments/closure_p1_temporal_consumer_patch.py",
            "p1_temporal_consumer_patch_validator",
        ),
        dict(cast(Mapping[str, Any], mc_authority["lock"])),
        dict(cast(Mapping[str, Any], mc_authority["companion"])),
        dict(cast(Mapping[str, Any], dltvm_authority["lock"])),
        dict(cast(Mapping[str, Any], dltvm_authority["companion"])),
        {
            **dict(P1_ARTIFACT_BUILDER_RECORD),
            "role": "current_runtime_builder",
        },
        *[dict(record) for record in publication_records],
    ]
    inputs = sorted(inputs, key=lambda record: str(record["path"]))
    superseded = cast(
        Mapping[str, Any], dltvm_authority["superseded_components"]
    )
    historical_inputs = [
        {
            **dict(record),
            "commit": H_DLTVM_COMMIT,
            "hash_source": "git_blob_at_commit",
        }
        for record in cast(Sequence[Mapping[str, Any]], superseded["records"])
    ]
    historical_inputs.sort(key=lambda record: str(record["path"]))
    return {
        "manifest_version": "closure_p1_temporal_consumer_patch_manifest_v1",
        "status": "completed",
        "experiment_id": EXPERIMENT_ID,
        "surface_id": SURFACE_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": payload["created_at_utc"],
        "outputs": [dict(lock_record)],
        "script": component(
            "src/experiments/lock_closure_p1_temporal_consumer_patch.py",
            "generating_script",
        ),
        "inputs": inputs,
        "historical_inputs": historical_inputs,
        "physical_inputs_only": True,
        "historical_inputs_compared_to_current_paths": False,
        "authorized_model_id": AUTHORIZED_MODEL_ID,
        "authorized_base_seed": AUTHORIZED_BASE_SEED,
        "authorized_device": AUTHORIZED_DEVICE,
        "p1_consumer_authorized": False,
        "p1_fit_authorized": False,
        "effective_in_payload": False,
        "publication_required": True,
        "batch_seed_execution_authorized": False,
        "retry_authorized": False,
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
        raise P1TemporalConsumerPatchError("E0-MD lock and companion commits differ")
    ancestry = _git("rev-list", "--parents", "-n", "1", lock_commit).split()
    if ancestry != [lock_commit, patch_head]:
        raise P1TemporalConsumerPatchError("P-E0-MD must be the direct child of H-E0-MD")
    expected = [
        {"status": "A", "path": lock_path},
        {"status": "A", "path": companion_path},
    ]
    if _observed_diff_entries(patch_head, lock_commit) != expected:
        raise P1TemporalConsumerPatchError("P-E0-MD must add exactly lock plus companion")
    _require_ancestor(lock_commit, execution_head)
    _assert_paths_untouched(
        lock_commit,
        execution_head,
        (lock_path, companion_path),
        context="P-E0-MD publication",
    )
    if _git("branch", "--show-current") != "main":
        raise P1TemporalConsumerPatchError("E0-MD effective authority requires branch main")
    refs = {
        "head": execution_head,
        "main": _require_commit(_git("rev-parse", "main"), context="main"),
        "tracking": _require_commit(_git("rev-parse", PUBLISHED_REF), context=PUBLISHED_REF),
        "origin_head": _require_commit(
            _git("rev-parse", "origin/HEAD"), context="origin/HEAD"
        ),
    }
    if set(refs.values()) != {lock_commit}:
        raise P1TemporalConsumerPatchError(
            f"E0-MD effective publication refs diverged: {refs}"
        )
    published = refs["tracking"]
    if verify_remote and _remote_main_oid() != published:
        raise P1TemporalConsumerPatchError("Local and live origin/main differ for E0-MD")
    return (
        lock_commit,
        _git_record(
            lock_commit,
            lock_path,
            role="external_p1_temporal_consumer_patch_lock",
        ),
        _git_record(
            lock_commit,
            companion_path,
            role="p1_temporal_consumer_patch_companion",
        ),
    )


def load_and_validate_p1_temporal_consumer_patch_lock(
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
        raise P1TemporalConsumerPatchError("E0-MD requires closed default paths")
    payload = _load_regular_json(lock_path, context="E0-MD lock")
    schema = _load_regular_json(lock_schema, context="E0-MD schema")
    # Effective validation must establish static authority and publication
    # before the physical P1 auditor is allowed to open the Parquet.
    validate_p1_temporal_consumer_patch_lock_payload(
        payload,
        schema,
        require_physical_artifacts=False,
    )
    lock_record = _file_record(
        lock_path,
        role="external_p1_temporal_consumer_patch_lock",
    )
    companion = _load_regular_json(companion_path, context="E0-MD companion")
    if companion != _expected_companion(payload, lock_record=lock_record):
        raise P1TemporalConsumerPatchError("E0-MD companion drifted")
    companion_record = _file_record(
        companion_path,
        role="p1_temporal_consumer_patch_companion",
    )
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    _require_ancestor(patch_head, execution_head)
    if require_published:
        status = _git("status", "--porcelain", "--untracked-files=all")
        if status:
            raise P1TemporalConsumerPatchError(
                f"E0-MD execution requires a clean worktree: {status}"
            )
        lock_commit, git_lock_record, git_companion_record = _validate_publication_bundle(
            payload,
            execution_head=execution_head,
            verify_remote=verify_remote,
        )
        if lock_record != git_lock_record or companion_record != git_companion_record:
            raise P1TemporalConsumerPatchError("Published E0-MD bytes drifted")
        validate_p1_temporal_consumer_patch_lock_payload(
            payload,
            schema,
            require_physical_artifacts=True,
        )
        effective = True
    else:
        if execution_head != patch_head:
            raise P1TemporalConsumerPatchError(
                "Unpublished E0-MD validation must run at H-E0-MD"
            )
        validate_p1_temporal_consumer_patch_lock_payload(
            payload,
            schema,
            require_physical_artifacts=True,
        )
        lock_commit = ""
        effective = False
    authorities = cast(Mapping[str, Any], payload["base_authorities"])
    mc_authority = cast(Mapping[str, Any], authorities["e0_mc"])
    e0_mc_context = dict(
        cast(Mapping[str, Any], mc_authority["context_authorization"])
    )
    bundle = cast(Mapping[str, Any], payload["p1_sequence_bundle"])
    summary = {
        "status": "published_p1_temporal_consumer_patch_valid"
        if effective
        else "locked_unpublished",
        "gate": PATCH_GATE,
        "patch_head": patch_head,
        "lock_commit": lock_commit or None,
        "execution_head": execution_head,
        "publication_verified": effective,
        "remote_publication_verified": effective and verify_remote,
        "historical_e0_mc_verified": True,
        "nested_historical_e0_mb_verified": True,
        "historical_e0_dltvm_verified": True,
        "historical_dltvm_effective_loader_called": False,
        "p1_sequence_bundle_verified": True,
        "consumer_namespace_absent": True,
        "authorization_effective": effective,
        "p1_consumer_authorized": effective,
        "p1_fit_authorized": effective,
        "authorized_model_id": AUTHORIZED_MODEL_ID,
        "authorized_base_seed": AUTHORIZED_BASE_SEED,
        "authorized_device": AUTHORIZED_DEVICE,
        "p1_artifact_builder_record": dict(P1_ARTIFACT_BUILDER_RECORD),
        "current_runtime_builder_record": dict(P1_ARTIFACT_BUILDER_RECORD),
        "e0_mc_context_authorization": e0_mc_context,
        "authority_input_records": [lock_record, companion_record],
        "fit_availability": dict(FIT_AVAILABILITY),
        "sequence_fit_available": False,
        "expected_slot_status": FIT_AVAILABILITY["expected_slot_status"],
        "expected_fit_status": FIT_AVAILABILITY["expected_fit_status"],
        "expected_failure_reason": FIT_AVAILABILITY["expected_failure_reason"],
        "p1_sequence_bundle_commit": bundle["commit"],
        "batch_seed_execution_authorized": False,
        "retry_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }
    return payload, summary


def require_p1_temporal_consumer_authorized(
    *,
    model_id: str,
    base_seed: int,
    device: str,
) -> dict[str, Any]:
    """Require the published E0-MD authority for exactly P1/1729/CPU."""
    if (
        model_id != AUTHORIZED_MODEL_ID
        or base_seed != AUTHORIZED_BASE_SEED
        or device != AUTHORIZED_DEVICE
    ):
        raise P1TemporalConsumerPatchError(
            "E0-MD authorizes only the P1 seed 1729 CPU temporal consumer"
        )
    _, summary = load_and_validate_p1_temporal_consumer_patch_lock(
        require_published=True,
        verify_remote=True,
    )
    required_true = (
        "publication_verified",
        "remote_publication_verified",
        "historical_e0_mc_verified",
        "nested_historical_e0_mb_verified",
        "historical_e0_dltvm_verified",
        "p1_sequence_bundle_verified",
        "consumer_namespace_absent",
        "authorization_effective",
        "p1_consumer_authorized",
        "p1_fit_authorized",
    )
    failed = [field for field in required_true if summary.get(field) is not True]
    if failed:
        raise P1TemporalConsumerPatchError(
            f"E0-MD authorization predicates failed: {failed}"
        )
    required_false = (
        "historical_dltvm_effective_loader_called",
        "sequence_fit_available",
        "batch_seed_execution_authorized",
        "retry_authorized",
        "e0_m_authorized",
        "evaluation_authorized",
        "e0_u_authorized",
        "future_outcomes_accessed",
    )
    drifted = [field for field in required_false if summary.get(field) is not False]
    if drifted:
        raise P1TemporalConsumerPatchError(f"E0-MD fail-closed seals drifted: {drifted}")
    if summary.get("fit_availability") != FIT_AVAILABILITY:
        raise P1TemporalConsumerPatchError("E0-MD fit availability drifted")
    return summary


__all__ = [
    "AUTHORIZED_BASE_SEED",
    "AUTHORIZED_DEVICE",
    "AUTHORIZED_MODEL_ID",
    "DEFAULT_PATCH_LOCK_PATH",
    "DEFAULT_PATCH_LOCK_SCHEMA",
    "DEFAULT_PATCH_MANIFEST_PATH",
    "FIT_AVAILABILITY",
    "FOCUSED_TEST_COMMAND",
    "FOCUSED_TEST_COUNT",
    "P1_ARTIFACT_BUILDER_RECORD",
    "PATCH_ADDED_PATHS",
    "PATCH_COMPONENT_ROLES",
    "PATCH_MODIFIED_PATHS",
    "PATCH_PATHS",
    "P1TemporalConsumerPatchError",
    "build_p1_temporal_consumer_patch_lock_payload",
    "collect_p1_temporal_consumer_patch_prelock_state",
    "load_and_validate_p1_temporal_consumer_patch_lock",
    "p1_consumer_namespace_absence",
    "patch_component_bundle",
    "patch_git_diff_payload",
    "require_p1_temporal_consumer_authorized",
    "validate_p1_temporal_consumer_patch_lock_payload",
]
