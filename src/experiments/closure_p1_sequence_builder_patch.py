#!/usr/bin/env python
"""Validate the additive Closure V1 P1 sequence-builder authority.

E0-MB preserves the published E0-DLTVM and E0-MA bundles as immutable
historical authorities while adopting a transactionally hardened sequence
builder.  It authorizes exactly the one-shot P1 sequence build for seed 1729;
it never authorizes model fitting, evaluation, E0-M, E0-U, holdout access, or
post-2021 outcome access.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from src.experiments import audit_closure_p0_model_availability as availability
from src.experiments import (
    closure_development_runtime_temporal_validation_manifest_patch as dltvm,
)
from src.experiments.closure_contract import ClosureContractError, validate_json_schema

dlt = dltvm.dlt


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOCK_VERSION = "closure_p1_sequence_builder_patch_lock_v1"
PATCH_GATE = "E0-MB"
PATCH_ID = "p1_sequence_builder_authorization_atomicity_patch_1"
PATCH_STATUS = "locked"
EXPERIMENT_ID = "closure_v1"
SURFACE_ID = "closure_v1_wqp_adaptive_no_current_chla"
PUBLISHED_REF = "origin/main"

REGISTRY_COMMIT = "9851211bdc7b14d07ccfef997e7681a232f1f611"
REGISTRY_H_COMMIT = "1e9ea62448b6ba0df22397ce9e5da703e2841eb3"
DLTVM_H_COMMIT = "3ee008faef331f40cf73d1f1e3db59608b0deab1"
DLTVM_LOCK_COMMIT = "4ba5ecd45da7f0b25277c0a13602999413fa2849"
PATCH_BASE_COMMIT = REGISTRY_COMMIT
AUTHORIZED_MODEL_ID = "P1"
AUTHORIZED_BASE_SEED = 1729

DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/p1_sequence_builder_patch_lock.json"
)
DEFAULT_PATCH_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/p1_sequence_builder_patch_lock_manifest.json"
)
DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/p1_sequence_builder_patch_lock.schema.json"
)

SUPERSEDED_DLTVM_COMPONENT_PATHS = (
    "src/experiments/build_closure_pipe_sequences.py",
    "tests/test_build_closure_pipe_sequences.py",
)
PRESERVED_DLTVM_COMPONENT_PATHS = tuple(
    path
    for path in dltvm.PATCH_PATHS
    if path not in SUPERSEDED_DLTVM_COMPONENT_PATHS
)

PATCH_COMPONENT_ROLES = {
    DEFAULT_PATCH_LOCK_SCHEMA.as_posix(): "p1_sequence_builder_patch_lock_schema",
    "docs/closure_v1/E0_M_P1_SEQUENCE_BUILDER_PATCH_1.md": (
        "p1_sequence_builder_patch_protocol"
    ),
    "src/experiments/build_closure_pipe_sequences.py": (
        "transactional_p1_sequence_builder"
    ),
    "src/experiments/closure_p1_sequence_builder_patch.py": (
        "p1_sequence_builder_patch_validator"
    ),
    "src/experiments/lock_closure_p1_sequence_builder_patch.py": (
        "p1_sequence_builder_patch_locker"
    ),
    "tests/test_build_closure_pipe_sequences.py": (
        "transactional_p1_sequence_builder_tests"
    ),
    "tests/test_closure_p1_sequence_builder_patch.py": (
        "p1_sequence_builder_patch_tests"
    ),
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))
PATCH_MODIFIED_PATHS = (
    "src/experiments/build_closure_pipe_sequences.py",
    "tests/test_build_closure_pipe_sequences.py",
)
PATCH_ADDED_PATHS = tuple(path for path in PATCH_PATHS if path not in PATCH_MODIFIED_PATHS)

TYPE_CHECK_COMMAND = (".venv/bin/ty", "check")
FOCUSED_TEST_COMMAND = (
    ".venv/bin/pytest",
    "tests/test_closure_p1_sequence_builder_patch.py",
    "tests/test_build_closure_pipe_sequences.py",
    "-q",
)
# Finalized from the exact closed H-E0-MB collection after focal hardening.
FOCUSED_TEST_COUNT = 79
POETRY_CHECK_COMMAND = ("poetry", "check")
PUBLICATION_GUARD_COMMAND = ("scripts/check_repo_publication_ready.sh",)
DIFF_CHECK_COMMAND = ("git", "diff", "--check")

PATCH_ATOMICITY = {
    "bundle_outputs": ["sequence_parquet", "summary_csv", "manifest_json"],
    "publication_order": ["sequence_parquet", "summary_csv", "manifest_json"],
    "completion_marker": "manifest_json",
    "completion_marker_written_last": True,
    "exclusive_slot_guard": True,
    "parent_walk_no_follow": True,
    "temporary_creation": "exclusive_regular_inode",
    "publication": "hardlink_no_clobber",
    "rollback": "reverse_owned_inode_only",
    "foreign_replacement_preserved": True,
    "directory_fsync": True,
    "owned_bytes_rehashed_at_commit": True,
    "dependencies_revalidated_at_commit": True,
    "dvc_pointer_checks": [
        "preflight",
        "before_manifest",
        "after_manifest",
        "transaction_commit_before_output_rehash",
        "transaction_commit_after_dependency_revalidation",
    ],
    "uncoordinated_external_dvc_creator_excluded": False,
    "sigkill_between_distinct_directories_is_detected_not_atomic": True,
}
PATCH_AUTHORIZATIONS = {
    "p1_sequence_builder_authorized": False,
    "effective_in_payload": False,
    "publication_required": True,
    "authorized_model_id": AUTHORIZED_MODEL_ID,
    "authorized_base_seed": AUTHORIZED_BASE_SEED,
    "batch_seed_execution_authorized": False,
    "p1_fit_authorized": False,
    "e0_m_authorized": False,
    "evaluation_authorized": False,
    "e0_u_authorized": False,
    "future_outcomes_accessed": False,
}
EFFECTIVE_AUTHORIZATIONS = {
    **PATCH_AUTHORIZATIONS,
    "p1_sequence_builder_authorized": True,
    "publication_required": False,
    "authorization_effective": True,
}
PATCH_SEALS = {
    "e0_dltvm_preserved_as_historical_authority": True,
    "e0_ma_registry_preserved_as_historical_authority": True,
    "p0_artifacts_rewritten": False,
    "scientific_sequence_contract_changed": False,
    "state_mapping_changed": False,
    "denominator_changed": False,
    "seed_order_changed": False,
    "holdout_accessed": False,
    "post_2021_outcomes_accessed": False,
    "does_not_replace_e0_m": True,
}


class P1SequenceBuilderPatchError(RuntimeError):
    """Raised when E0-MB cannot prove its closed authorization chain."""


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
        return dlt._git(*args)
    except dlt.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceBuilderPatchError(str(exc)) from exc


def _require_commit(value: str, *, context: str) -> str:
    try:
        return dlt._require_commit(value, context=context)
    except dlt.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceBuilderPatchError(str(exc)) from exc


def _require_ancestor(ancestor: str, descendant: str) -> None:
    try:
        dlt._require_ancestor(ancestor, descendant)
    except dlt.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceBuilderPatchError(str(exc)) from exc


def _git_blob(commit: str, path: str) -> bytes:
    try:
        payload = dlt._git_blob(commit, path)
    except dlt.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceBuilderPatchError(str(exc)) from exc
    if payload is None:
        raise P1SequenceBuilderPatchError(f"Git blob is absent: {commit}:{path}")
    return payload


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
        return dlt._file_record(path, role=role)
    except dlt.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceBuilderPatchError(str(exc)) from exc


def _physical_git_record(commit: str, path: str, *, role: str) -> dict[str, Any]:
    expected = _git_record(commit, path, role=role)
    physical = _file_record(Path(path), role=role)
    if physical != expected:
        raise P1SequenceBuilderPatchError(
            f"Physical artifact differs from historical Git authority: {path}"
        )
    return expected


def _load_regular_json(path: Path, *, context: str) -> dict[str, Any]:
    try:
        return dltvm._load_regular_json(path, context=context)
    except dltvm.DevelopmentRuntimeTemporalValidationManifestPatchError as exc:
        raise P1SequenceBuilderPatchError(str(exc)) from exc


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
        raise P1SequenceBuilderPatchError(str(exc)) from exc


def _observed_diff_entries(base: str, head: str) -> list[dict[str, str]]:
    try:
        return dlt._observed_diff_entries(base, head)
    except dlt.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceBuilderPatchError(str(exc)) from exc


def _introduced_commit(path: str) -> str:
    try:
        return dlt._introduced_commit(path)
    except dlt.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceBuilderPatchError(str(exc)) from exc


def _remote_main_oid() -> str:
    try:
        return dlt._remote_main_oid()
    except dlt.DevelopmentRuntimeTemporalConsumerPatchError as exc:
        raise P1SequenceBuilderPatchError(str(exc)) from exc


def patch_git_diff_payload(patch_head: str) -> dict[str, Any]:
    patch_head = _require_commit(patch_head, context="H-E0-MB")
    ancestry = _git("rev-list", "--parents", "-n", "1", patch_head).split()
    if ancestry != [patch_head, PATCH_BASE_COMMIT]:
        raise P1SequenceBuilderPatchError(
            "H-E0-MB must be the direct non-merge child of the E0-MA registry"
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
        raise P1SequenceBuilderPatchError(
            f"H-E0-MB diff differs from its closed 2M+5A allowlist: {observed}"
        )
    return {
        "base_commit": PATCH_BASE_COMMIT,
        "patch_head": patch_head,
        "modified_count": len(PATCH_MODIFIED_PATHS),
        "added_count": len(PATCH_ADDED_PATHS),
        "entries": expected,
        "paths": list(PATCH_PATHS),
        "paths_sha256": _path_digest(PATCH_PATHS),
        "only_allowed_additions_and_modifications": True,
    }


def patch_component_bundle(patch_head: str) -> dict[str, Any]:
    patch_head = _require_commit(patch_head, context="H-E0-MB")
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


def _validate_historical_manifest_records(
    raw_records: Any,
    *,
    expected_count: int,
    context: str,
    closure_head: str,
) -> list[dict[str, Any]]:
    if not isinstance(raw_records, Sequence) or isinstance(raw_records, (str, bytes)):
        raise P1SequenceBuilderPatchError(f"{context} must be an array")
    if len(raw_records) != expected_count:
        raise P1SequenceBuilderPatchError(
            f"{context} must contain {expected_count} records, observed {len(raw_records)}"
        )
    builder_path = "src/experiments/build_closure_pipe_sequences.py"
    observed: list[dict[str, Any]] = []
    for index, raw_record in enumerate(raw_records):
        if not isinstance(raw_record, Mapping) or set(raw_record) != {
            "path",
            "bytes",
            "sha256",
        }:
            raise P1SequenceBuilderPatchError(f"{context}[{index}] record dialect drifted")
        record = dict(cast(Mapping[str, Any], raw_record))
        path = str(record["path"])
        if path == builder_path:
            historical = _git_record(
                closure_head,
                builder_path,
                role="historical_p0_consumer_runtime_builder",
            )
            expected = {key: historical[key] for key in ("path", "bytes", "sha256")}
        else:
            physical = availability._file_record(path)
            expected = dict(physical)
        if record != expected:
            raise P1SequenceBuilderPatchError(
                f"{context}[{index}] differs from its closed authority: {path}"
            )
        observed.append(record)
    return observed


def _validate_historical_p0_slot(
    seed: int,
    evidence: Mapping[str, Any],
    *,
    closure_head: str,
) -> dict[str, Any]:
    namespace = availability.p0_slot_paths(seed)
    present_roles = [
        role for role, relative in namespace.items() if availability._path_entry_exists(relative)
    ]
    if present_roles != ["report", "manifest"]:
        raise P1SequenceBuilderPatchError(
            f"P0 seed {seed} must retain exactly report+manifest; observed {present_roles}"
        )
    report = namespace["report"]
    manifest = namespace["manifest"]
    payload = availability._load_json(manifest)
    availability.validate_p0_manifest_semantics(payload, seed=seed)
    inputs = _validate_historical_manifest_records(
        payload.get("inputs"),
        expected_count=availability.EXPECTED_INPUT_RECORDS,
        context=f"P0 seed {seed} inputs",
        closure_head=closure_head,
    )
    sources = _validate_historical_manifest_records(
        payload.get("source_code"),
        expected_count=availability.EXPECTED_SOURCE_RECORDS,
        context=f"P0 seed {seed} source_code",
        closure_head=closure_head,
    )
    expected_report = {**availability._file_record(report), "artifact_role": "report"}
    if payload.get("outputs") != [expected_report]:
        raise P1SequenceBuilderPatchError(f"P0 seed {seed} output record drifted")
    script = payload.get("script")
    expected_script = availability._file_record("src/experiments/train_closure_pipe.py")
    if not isinstance(script, Mapping) or dict(script) != expected_script:
        raise P1SequenceBuilderPatchError(f"P0 seed {seed} script record drifted")
    expected_report_text = (
        f"# Closure V1 P0 seed {seed}\n\n"
        "Status: `model_unavailable`\n"
        "Failure reason: `sequence_fit_rows_unavailable`\n\n"
        "No model/checkpoint was emitted and the failed slot was not replaced.\n"
    ).encode("utf-8")
    if availability._secure_read_bytes(report, context="P0 report") != expected_report_text:
        raise P1SequenceBuilderPatchError(f"P0 seed {seed} report content drifted")

    commit = str(evidence["commit"])
    parent = str(evidence["parent"])
    if int(evidence["base_seed"]) != seed or availability._commit_parent(commit) != parent:
        raise P1SequenceBuilderPatchError(f"P0 seed {seed} evidence binding drifted")
    expected_paths = sorted((manifest.as_posix(), report.as_posix()))
    additions = availability._commit_additions(commit)
    if sorted(record["path"] for record in additions) != expected_paths:
        raise P1SequenceBuilderPatchError(
            f"P0 seed {seed} evidence commit must add exactly report+manifest"
        )
    manifest_record = availability._git_bound_record(commit, manifest)
    report_record = availability._git_bound_record(commit, report)
    closure_manifest = availability._git_bound_record(closure_head, manifest)
    closure_report = availability._git_bound_record(closure_head, report)
    if (
        availability._generic_record(manifest_record)
        != availability._generic_record(closure_manifest)
        or availability._generic_record(report_record)
        != availability._generic_record(closure_report)
    ):
        raise P1SequenceBuilderPatchError(
            f"P0 seed {seed} evidence changed before the fixed closure head"
        )
    if availability._git(
        "status",
        "--short",
        "--untracked-files=all",
        "--",
        manifest.as_posix(),
        report.as_posix(),
    ):
        raise P1SequenceBuilderPatchError(f"P0 seed {seed} evidence is modified")
    absent = [
        {"artifact_role": role, "path": path.as_posix(), "state": "absent"}
        for role, path in namespace.items()
        if role not in {"report", "manifest"}
    ]
    registered = [
        {
            "artifact_role": role,
            "path": path.as_posix(),
            "state": "present" if role in {"report", "manifest"} else "absent",
        }
        for role, path in namespace.items()
    ]
    return {
        "base_seed": seed,
        "slot_status": "model_unavailable",
        "fit_status": "not_attempted",
        "failure_reason": "sequence_fit_rows_unavailable",
        "available_fit_role_sequences": availability.EXPECTED_SUCCESS_COUNT,
        "unavailable_fit_role_sequences": availability.EXPECTED_UNAVAILABLE_COUNT,
        "failure_code": "missing_target_state",
        "failed_slot_replaced": False,
        "replacement_used": False,
        "model_artifact_emitted": False,
        "calibration_status": "not_attempted_upstream_model_unavailable",
        "calibration_artifacts": "forbidden",
        "evidence_commit": {
            "commit": commit,
            "parent": parent,
            "exact_addition_count": len(additions),
            "additions": additions,
        },
        "manifest": manifest_record,
        "report": report_record,
        "input_record_count": len(inputs),
        "input_records_sha256": availability._records_digest(inputs),
        "source_code_record_count": len(sources),
        "source_code_records_sha256": availability._records_digest(sources),
        "registered_namespace_path_count": len(registered),
        "present_path_count": availability.EXPECTED_PRESENT_PATHS,
        "registered_namespace": registered,
        "absent_artifacts": absent,
        "normalized_manifest": availability._normalized_manifest(payload),
    }


def _reconstruct_historical_p0_audit(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Rebuild the registry-time audit without imposing current P1 absence."""
    closure_head = str(
        cast(Mapping[str, Any], policy["p0_closure"])["published_closure_head"]
    )
    chain = availability._evidence_chain(policy)
    slots = [
        _validate_historical_p0_slot(seed, evidence, closure_head=closure_head)
        for seed, evidence in zip(availability.EXPECTED_SEEDS, chain, strict=True)
    ]
    reference = slots[0]["normalized_manifest"]
    if any(slot["normalized_manifest"] != reference for slot in slots[1:]):
        raise P1SequenceBuilderPatchError(
            "Historical P0 slot semantics differ beyond allowed metadata"
        )
    for slot in slots:
        slot.pop("normalized_manifest")
    denominator = availability._audit_denominator_authority(policy)
    return {
        "experiment_id": EXPERIMENT_ID,
        "gate": "E0-MA",
        "status": "ready_to_register",
        "p0_published_closure_head": closure_head,
        "seed_slots": list(availability.EXPECTED_SEEDS),
        "slot_count": len(slots),
        "slot_status_counts": {"model_unavailable": len(slots)},
        "available_fit_role_sequences_per_slot": availability.EXPECTED_SUCCESS_COUNT,
        "unavailable_fit_role_sequences_per_slot": availability.EXPECTED_UNAVAILABLE_COUNT,
        "denominator_authority": denominator,
        "slots": slots,
        "p1_materialized_path_count": 0,
        "e0_m_output_count": 0,
        "outcome_access_log_current_e0_ma_state": "absent",
        "outcome_access_log_required_e0_m_state": "present_empty",
        "outcome_access_log_required_e0_m_records": 0,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "side_effects": {
            "writes_performed": False,
            "network_commands_executed": False,
            "dvc_commands_executed": False,
            "outcome_paths_opened": False,
        },
    }


def _historical_registry_authority(*, execution_head: str) -> dict[str, Any]:
    _require_ancestor(REGISTRY_COMMIT, execution_head)
    if _introduced_commit(availability.DEFAULT_REGISTRY.as_posix()) != REGISTRY_COMMIT:
        raise P1SequenceBuilderPatchError("E0-MA registry commit drifted")
    if _introduced_commit(availability.DEFAULT_COMPANION.as_posix()) != REGISTRY_COMMIT:
        raise P1SequenceBuilderPatchError("E0-MA companion commit drifted")
    if availability._commit_parent(REGISTRY_COMMIT) != REGISTRY_H_COMMIT:
        raise P1SequenceBuilderPatchError("E0-MA registry parent drifted")
    if availability._commit_parent(REGISTRY_H_COMMIT) != availability.P0_CLOSURE_HEAD:
        raise P1SequenceBuilderPatchError("H-E0-MA parent drifted")
    additions = availability._commit_additions(REGISTRY_COMMIT)
    expected_registry_paths = sorted(
        (
            availability.DEFAULT_REGISTRY.as_posix(),
            availability.DEFAULT_COMPANION.as_posix(),
        )
    )
    if sorted(record["path"] for record in additions) != expected_registry_paths:
        raise P1SequenceBuilderPatchError("E0-MA registry commit is not exactly 2A")
    _assert_paths_untouched(
        REGISTRY_COMMIT,
        execution_head,
        expected_registry_paths,
        context="E0-MA registry publication",
    )
    registry_git = availability._git_bound_record(
        REGISTRY_COMMIT,
        availability.DEFAULT_REGISTRY,
    )
    companion_git = availability._git_bound_record(
        REGISTRY_COMMIT,
        availability.DEFAULT_COMPANION,
    )
    policy = availability._closed_policy()
    registry = availability._load_canonical_json(
        availability.DEFAULT_REGISTRY,
        context="historical E0-MA registry",
    )
    companion = availability._load_canonical_json(
        availability.DEFAULT_COMPANION,
        context="historical E0-MA registry companion",
    )
    repository = registry.get("repository_binding")
    if not isinstance(repository, Mapping) or repository.get("h_slice_head") != REGISTRY_H_COMMIT:
        raise P1SequenceBuilderPatchError("E0-MA registry H binding drifted")
    audit = _reconstruct_historical_p0_audit(policy)
    publication = availability._reconstruct_h_slice_publication(
        policy,
        h_slice_head=REGISTRY_H_COMMIT,
    )
    registry_record = availability._generic_record(
        registry_git,
        role="p0_model_availability_registry",
    )
    validation = availability.validate_registry_bundle_payloads(
        policy,
        audit,
        publication,
        registry,
        companion,
        registry_record,
    )
    return {
        "gate": "E0-MA",
        "registry_commit": REGISTRY_COMMIT,
        "registry_parent": REGISTRY_H_COMMIT,
        "registry": {
            **availability._generic_record(registry_git),
            "role": "p0_model_availability_registry",
        },
        "companion_manifest": {
            **availability._generic_record(companion_git),
            "role": "p0_model_availability_registry_companion",
        },
        "p0_closure_head": availability.P0_CLOSURE_HEAD,
        "slot_count": audit["slot_count"],
        "seed_slots": audit["seed_slots"],
        "available_fit_role_sequences_per_slot": (
            audit["available_fit_role_sequences_per_slot"]
        ),
        "unavailable_fit_role_sequences_per_slot": (
            audit["unavailable_fit_role_sequences_per_slot"]
        ),
        "registry_reconstruction": validation,
        "registry_effective_as_historical_authority": True,
        "p1_materialized_path_count": 0,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }


def _static_consumer_prelock() -> dict[str, Any]:
    paths = [dlt._relative(path) for path in dlt.temporal_consumer_output_paths()]
    return {
        "model_id": "P0",
        "base_seeds": list(dlt.REGISTERED_SEEDS),
        "count": len(paths),
        "paths": paths,
        "paths_sha256": _path_digest(paths),
        "all_absent_at_lock": True,
    }


def _historical_dltvm_authority(*, execution_head: str) -> dict[str, Any]:
    _require_ancestor(DLTVM_LOCK_COMMIT, execution_head)
    if _introduced_commit(dltvm.DEFAULT_PATCH_LOCK_PATH.as_posix()) != DLTVM_LOCK_COMMIT:
        raise P1SequenceBuilderPatchError("P-DLTVM lock commit drifted")
    if _introduced_commit(dltvm.DEFAULT_PATCH_MANIFEST_PATH.as_posix()) != DLTVM_LOCK_COMMIT:
        raise P1SequenceBuilderPatchError("P-DLTVM companion commit drifted")
    ancestry = _git("rev-list", "--parents", "-n", "1", DLTVM_LOCK_COMMIT).split()
    if ancestry != [DLTVM_LOCK_COMMIT, DLTVM_H_COMMIT]:
        raise P1SequenceBuilderPatchError("P-DLTVM is not the exact child of H-DLTVM")
    lock_paths = (
        dltvm.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        dltvm.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
    )
    expected_diff = [{"status": "A", "path": path} for path in sorted(lock_paths)]
    if _observed_diff_entries(DLTVM_H_COMMIT, DLTVM_LOCK_COMMIT) != expected_diff:
        raise P1SequenceBuilderPatchError("P-DLTVM is not exactly lock plus companion")
    _assert_paths_untouched(
        DLTVM_LOCK_COMMIT,
        execution_head,
        lock_paths,
        context="P-DLTVM publication",
    )

    payload = _load_regular_json(dltvm.DEFAULT_PATCH_LOCK_PATH, context="P-DLTVM lock")
    schema = _load_regular_json(dltvm.DEFAULT_PATCH_LOCK_SCHEMA, context="P-DLTVM schema")
    companion = _load_regular_json(
        dltvm.DEFAULT_PATCH_MANIFEST_PATH,
        context="P-DLTVM companion",
    )
    try:
        validate_json_schema(payload, schema, instance_path="$.historical_p_dltvm")
    except ClosureContractError as exc:
        raise P1SequenceBuilderPatchError(str(exc)) from exc
    fixed = {
        "lock_version": dltvm.LOCK_VERSION,
        "status": dltvm.PATCH_STATUS,
        "experiment_id": dltvm.EXPERIMENT_ID,
        "gate": dltvm.PATCH_GATE,
        "patch_id": dltvm.PATCH_ID,
        "correction": dltvm.PATCH_CORRECTION,
        "authorizations": dltvm.PATCH_AUTHORIZATIONS,
        "seals": dltvm.PATCH_SEALS,
        "lock_artifact": {
            "path": dltvm.DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "role": "external_development_runtime_temporal_validation_dialect_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
    }
    for field, expected in fixed.items():
        if payload.get(field) != expected:
            raise P1SequenceBuilderPatchError(f"Historical P-DLTVM field drifted: {field}")
    repository = payload.get("patch_repository")
    if repository != {
        "head": DLTVM_H_COMMIT,
        "parent": dltvm.PATCH_BASE_COMMIT,
        "branch": "main",
        "published_ref": dltvm.PUBLISHED_REF,
        "published_head": DLTVM_H_COMMIT,
        "remote_main_oid": DLTVM_H_COMMIT,
        "worktree_status": "clean",
        "exact_diff_verified": True,
    }:
        raise P1SequenceBuilderPatchError("Historical P-DLTVM repository binding drifted")
    if payload.get("git_diff") != dltvm.patch_git_diff_payload(DLTVM_H_COMMIT):
        raise P1SequenceBuilderPatchError("Historical H-DLTVM diff drifted")
    component_bundle = dltvm.patch_component_bundle(DLTVM_H_COMMIT)
    if payload.get("patch_components") != component_bundle:
        raise P1SequenceBuilderPatchError("Historical H-DLTVM components drifted")
    try:
        base_authority = dltvm._historical_dltv_authority(
            require_physical_artifacts=True
        )
    except dltvm.DevelopmentRuntimeTemporalValidationManifestPatchError as exc:
        raise P1SequenceBuilderPatchError(str(exc)) from exc
    if payload.get("base_authority") != base_authority:
        raise P1SequenceBuilderPatchError("Historical P-DLTVM base authority drifted")
    provenance = {
        "p0_artifact_builder_record": dict(dltvm.P0_ARTIFACT_BUILDER_RECORD),
        "h_dltv_runtime_builder_record": dltvm._builder_record_at_commit(
            dltvm.H_DLTV_COMMIT
        ),
        "current_runtime_builder_record": dltvm._builder_record_at_commit(
            DLTVM_H_COMMIT
        ),
        "all_records_are_distinct": True,
        "historical_record_source": "git_blob_at_p0_bundle_commit",
        "h_dltv_record_source": "git_blob_at_h_dltv_commit",
        "runtime_record_source": "physical_bytes_at_h_dltvm_head",
    }
    if payload.get("builder_provenance") != provenance:
        raise P1SequenceBuilderPatchError("Historical P-DLTVM builder provenance drifted")
    if payload.get("consumer_prelock") != _static_consumer_prelock():
        raise P1SequenceBuilderPatchError("Historical P-DLTVM prelock drifted")
    try:
        dltvm.validate_temporal_validation_manifest_patch_verification(
            cast(Mapping[str, Any], payload["verification"])
        )
    except dltvm.DevelopmentRuntimeTemporalValidationManifestPatchError as exc:
        raise P1SequenceBuilderPatchError(str(exc)) from exc

    lock_record = _physical_git_record(
        DLTVM_LOCK_COMMIT,
        dltvm.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        role="external_development_runtime_temporal_validation_dialect_patch_lock",
    )
    companion_record = _physical_git_record(
        DLTVM_LOCK_COMMIT,
        dltvm.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
        role="development_runtime_temporal_validation_manifest_patch_companion",
    )
    try:
        expected_companion = dltvm._expected_companion(payload, lock_record=lock_record)
    except dltvm.DevelopmentRuntimeTemporalValidationManifestPatchError as exc:
        raise P1SequenceBuilderPatchError(str(exc)) from exc
    if companion != expected_companion:
        raise P1SequenceBuilderPatchError("Historical P-DLTVM companion drifted")

    raw_records = cast(Sequence[Mapping[str, Any]], component_bundle["records"])
    by_path = {str(record["path"]): dict(record) for record in raw_records}
    if set(by_path) != set(dltvm.PATCH_PATHS):
        raise P1SequenceBuilderPatchError("Historical H-DLTVM component paths drifted")
    preserved_records = [by_path[path] for path in PRESERVED_DLTVM_COMPONENT_PATHS]
    superseded_records = [by_path[path] for path in SUPERSEDED_DLTVM_COMPONENT_PATHS]
    for record in preserved_records:
        physical = _file_record(Path(str(record["path"])), role=str(record["role"]))
        if physical != record:
            raise P1SequenceBuilderPatchError(
                f"Preserved H-DLTVM component drifted: {record['path']}"
            )
        if _git_record(execution_head, str(record["path"]), role=str(record["role"])) != record:
            raise P1SequenceBuilderPatchError(
                f"Preserved H-DLTVM Git component drifted: {record['path']}"
            )
    _assert_paths_untouched(
        DLTVM_H_COMMIT,
        execution_head,
        PRESERVED_DLTVM_COMPONENT_PATHS,
        context="preserved H-DLTVM components",
    )
    return {
        "gate": dltvm.PATCH_GATE,
        "patch_head": DLTVM_H_COMMIT,
        "lock_commit": DLTVM_LOCK_COMMIT,
        "lock": lock_record,
        "companion_manifest": companion_record,
        "superseded_components": {
            "count": len(superseded_records),
            "paths": list(SUPERSEDED_DLTVM_COMPONENT_PATHS),
            "records": superseded_records,
            "records_sha256": _record_digest(superseded_records),
            "current_bytes_required_to_match_historical": False,
        },
        "preserved_components": {
            "count": len(preserved_records),
            "paths": list(PRESERVED_DLTVM_COMPONENT_PATHS),
            "records": preserved_records,
            "records_sha256": _record_digest(preserved_records),
            "current_bytes_required_to_match_historical": True,
        },
        "builder_provenance": provenance,
        "historical_development_fit_authorized": True,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }


def p1_sequence_namespace_paths(base_seed: int = AUTHORIZED_BASE_SEED) -> tuple[Path, ...]:
    if base_seed != AUTHORIZED_BASE_SEED:
        raise P1SequenceBuilderPatchError(
            f"E0-MB does not register P1 sequence seed {base_seed}"
        )
    paths = availability._p1_absence_paths(base_seed)
    if len(paths) != 28 or len({path.as_posix() for path in paths}) != 28:
        raise P1SequenceBuilderPatchError("E0-MB P1 namespace drifted")
    return paths


def _sequence_prelock_contract() -> dict[str, Any]:
    paths = p1_sequence_namespace_paths()
    relative = [path.as_posix() for path in paths]
    return {
        "model_id": AUTHORIZED_MODEL_ID,
        "base_seed": AUTHORIZED_BASE_SEED,
        "count": len(relative),
        "paths": relative,
        "paths_sha256": _path_digest(relative),
        "all_absent_at_lock": True,
    }


def p1_sequence_namespace_absence() -> dict[str, Any]:
    contract = _sequence_prelock_contract()
    existing = [
        path.as_posix()
        for path in p1_sequence_namespace_paths()
        if availability._path_entry_exists(path)
    ]
    if existing:
        raise P1SequenceBuilderPatchError(
            f"P1 seed 1729 namespace is not pristine: {existing}"
        )
    return contract


def _progression_prelock_contract() -> dict[str, Any]:
    p1_paths = tuple(
        path
        for seed in availability.EXPECTED_SEEDS
        for path in availability._p1_absence_paths(seed)
    )
    if len(p1_paths) != 140 or len({path.as_posix() for path in p1_paths}) != 140:
        raise P1SequenceBuilderPatchError("Closure P1 progression namespace drifted")
    paths = [path.as_posix() for path in p1_paths]
    return {
        "p1_seed_order": list(availability.EXPECTED_SEEDS),
        "p1_path_count": len(paths),
        "p1_paths_sha256": _path_digest(paths),
        "p1_all_absent": True,
        "e0_m_output_count": 0,
        "outcome_access_log_state": "absent",
        "future_outcomes_accessed": False,
    }


def closure_progression_namespace_absence() -> dict[str, Any]:
    contract = _progression_prelock_contract()
    p1_paths = tuple(
        path
        for seed in availability.EXPECTED_SEEDS
        for path in availability._p1_absence_paths(seed)
    )
    existing_p1 = [
        path.as_posix() for path in p1_paths if availability._path_entry_exists(path)
    ]
    existing_e0_m = [
        path.as_posix()
        for path in availability.E0_M_OUTPUTS
        if availability._path_entry_exists(path)
    ]
    outcome_log_present = availability._path_entry_exists(availability.OUTCOME_ACCESS_LOG)
    if existing_p1 or existing_e0_m or outcome_log_present:
        raise P1SequenceBuilderPatchError(
            "Closure progression is not pristine before P1 seed 1729: "
            f"p1={existing_p1}, e0_m={existing_e0_m}, "
            f"outcome_log_present={outcome_log_present}"
        )
    return contract


def _locked_builder_record(patch_head: str) -> dict[str, Any]:
    path = "src/experiments/build_closure_pipe_sequences.py"
    expected = _git_record(patch_head, path, role="current_runtime_builder")
    historical = dltvm._builder_record_at_commit(DLTVM_H_COMMIT)
    if {key: expected[key] for key in ("path", "bytes", "sha256")} == historical:
        raise P1SequenceBuilderPatchError("H-E0-MB did not supersede the historical builder")
    return expected


def _current_builder_record(patch_head: str) -> dict[str, Any]:
    expected = _locked_builder_record(patch_head)
    physical = _file_record(
        Path("src/experiments/build_closure_pipe_sequences.py"),
        role="current_runtime_builder",
    )
    if physical != expected:
        raise P1SequenceBuilderPatchError("Current P1 sequence builder differs from H-E0-MB")
    return expected


def collect_p1_sequence_builder_patch_prelock_state(
    *,
    verify_remote: bool,
) -> dict[str, Any]:
    status = _git("status", "--porcelain", "--untracked-files=all")
    if status:
        raise P1SequenceBuilderPatchError(
            f"H-E0-MB lock requires a clean worktree and index: {status}"
        )
    head = _require_commit(_git("rev-parse", "HEAD"), context="H-E0-MB HEAD")
    if _git("branch", "--show-current") != "main":
        raise P1SequenceBuilderPatchError("H-E0-MB requires branch main")
    published = _require_commit(_git("rev-parse", PUBLISHED_REF), context=PUBLISHED_REF)
    if published != head:
        raise P1SequenceBuilderPatchError("H-E0-MB HEAD differs from origin/main")
    remote = _remote_main_oid() if verify_remote else published
    if remote != head:
        raise P1SequenceBuilderPatchError("H-E0-MB HEAD differs from live origin/main")
    git_diff = patch_git_diff_payload(head)
    components = patch_component_bundle(head)
    for record in cast(Sequence[Mapping[str, Any]], components["records"]):
        if _file_record(Path(str(record["path"])), role=str(record["role"])) != record:
            raise P1SequenceBuilderPatchError(
                f"Physical H-E0-MB component drifted: {record['path']}"
            )
    dltvm_authority = _historical_dltvm_authority(execution_head=head)
    registry_authority = _historical_registry_authority(execution_head=head)
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
            "e0_dltvm": dltvm_authority,
            "e0_ma": registry_authority,
        },
        "current_runtime_builder_record": _current_builder_record(head),
        "sequence_prelock": p1_sequence_namespace_absence(),
        "progression_prelock": closure_progression_namespace_absence(),
    }


def _validate_command_evidence(
    value: Any,
    command: Sequence[str],
    *,
    context: str,
) -> None:
    if not isinstance(value, Mapping) or value.get("command") != list(command):
        raise P1SequenceBuilderPatchError(f"E0-MB {context} command drifted")
    if value.get("returncode") != 0:
        raise P1SequenceBuilderPatchError(f"E0-MB {context} did not pass")
    for field in ("stdout_sha256", "stderr_sha256"):
        digest = value.get(field)
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise P1SequenceBuilderPatchError(f"E0-MB {context} {field} drifted")
    for field in ("stdout_line_count", "stderr_line_count"):
        if type(value.get(field)) is not int or value[field] < 0:
            raise P1SequenceBuilderPatchError(f"E0-MB {context} {field} drifted")


def validate_p1_sequence_builder_patch_verification(payload: Mapping[str, Any]) -> None:
    commands = {
        "full_type_check": TYPE_CHECK_COMMAND,
        "focused_tests": FOCUSED_TEST_COMMAND,
        "poetry_check": POETRY_CHECK_COMMAND,
        "publication_guard": PUBLICATION_GUARD_COMMAND,
        "git_diff_check": DIFF_CHECK_COMMAND,
    }
    if set(payload) != set(commands):
        raise P1SequenceBuilderPatchError("E0-MB verification fields drifted")
    for field, command in commands.items():
        _validate_command_evidence(payload[field], command, context=field)
    focused = cast(Mapping[str, Any], payload["focused_tests"])
    if (
        focused.get("test_count") != FOCUSED_TEST_COUNT
        or focused.get("skipped_count") != 0
        or focused.get("deselected_count") != 0
    ):
        raise P1SequenceBuilderPatchError("E0-MB focused-test evidence drifted")


def build_p1_sequence_builder_patch_lock_payload(
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
        "current_runtime_builder_record": dict(
            cast(Mapping[str, Any], prelock["current_runtime_builder_record"])
        ),
        "sequence_prelock": dict(cast(Mapping[str, Any], prelock["sequence_prelock"])),
        "progression_prelock": dict(
            cast(Mapping[str, Any], prelock["progression_prelock"])
        ),
        "atomicity": PATCH_ATOMICITY,
        "verification": dict(verification),
        "authorizations": PATCH_AUTHORIZATIONS,
        "seals": PATCH_SEALS,
        "lock_artifact": {
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "role": "external_p1_sequence_builder_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
    }


def validate_p1_sequence_builder_patch_lock_payload(
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    require_physical_patch_components: bool = True,
) -> None:
    try:
        validate_json_schema(
            payload,
            schema,
            instance_path="$.p1_sequence_builder_patch_lock",
        )
    except ClosureContractError as exc:
        raise P1SequenceBuilderPatchError(str(exc)) from exc
    fixed = {
        "lock_version": LOCK_VERSION,
        "status": PATCH_STATUS,
        "experiment_id": EXPERIMENT_ID,
        "surface_id": SURFACE_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "atomicity": PATCH_ATOMICITY,
        "authorizations": PATCH_AUTHORIZATIONS,
        "seals": PATCH_SEALS,
        "lock_artifact": {
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "role": "external_p1_sequence_builder_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
    }
    for field, expected in fixed.items():
        if payload.get(field) != expected:
            raise P1SequenceBuilderPatchError(f"E0-MB fixed field drifted: {field}")
    created = payload.get("created_at_utc")
    if not isinstance(created, str):
        raise P1SequenceBuilderPatchError("E0-MB timestamp is invalid")
    try:
        timestamp = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P1SequenceBuilderPatchError("E0-MB timestamp is invalid") from exc
    if timestamp.utcoffset() is None:
        raise P1SequenceBuilderPatchError("E0-MB timestamp requires a timezone")

    repository = cast(Mapping[str, Any], payload["patch_repository"])
    patch_head = _require_commit(str(repository.get("head", "")), context="locked H-E0-MB")
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
        raise P1SequenceBuilderPatchError("E0-MB patch repository record drifted")
    if payload.get("git_diff") != patch_git_diff_payload(patch_head):
        raise P1SequenceBuilderPatchError("E0-MB Git diff drifted")
    components = patch_component_bundle(patch_head)
    if payload.get("patch_components") != components:
        raise P1SequenceBuilderPatchError("E0-MB component bundle drifted")
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    _require_ancestor(patch_head, execution_head)
    if require_physical_patch_components:
        for record in cast(Sequence[Mapping[str, Any]], components["records"]):
            physical = _file_record(Path(str(record["path"])), role=str(record["role"]))
            if physical != record:
                raise P1SequenceBuilderPatchError(
                    f"Physical H-E0-MB component drifted: {record['path']}"
                )
        _assert_paths_untouched(
            patch_head,
            execution_head,
            PATCH_PATHS,
            context="H-E0-MB components",
        )
    expected_authorities = {
        "e0_dltvm": _historical_dltvm_authority(execution_head=execution_head),
        "e0_ma": _historical_registry_authority(execution_head=execution_head),
    }
    if payload.get("base_authorities") != expected_authorities:
        raise P1SequenceBuilderPatchError("E0-MB base authorities drifted")
    expected_builder = (
        _current_builder_record(patch_head)
        if require_physical_patch_components
        else _locked_builder_record(patch_head)
    )
    if payload.get("current_runtime_builder_record") != expected_builder:
        raise P1SequenceBuilderPatchError("E0-MB runtime builder record drifted")
    if payload.get("sequence_prelock") != _sequence_prelock_contract():
        raise P1SequenceBuilderPatchError("E0-MB sequence prelock drifted")
    if payload.get("progression_prelock") != _progression_prelock_contract():
        raise P1SequenceBuilderPatchError("E0-MB progression prelock drifted")
    validate_p1_sequence_builder_patch_verification(
        cast(Mapping[str, Any], payload["verification"])
    )


def _generic_record(record: Mapping[str, Any], *, role: str) -> dict[str, Any]:
    return {
        "path": record["path"],
        "role": role,
        "bytes": record["bytes"],
        "sha256": record["sha256"],
    }


def _expected_companion(
    payload: Mapping[str, Any],
    *,
    lock_record: Mapping[str, Any],
) -> dict[str, Any]:
    components = cast(Mapping[str, Any], payload["patch_components"])
    records = cast(Sequence[Mapping[str, Any]], components["records"])
    by_path = {str(record["path"]): record for record in records}
    authorities = cast(Mapping[str, Any], payload["base_authorities"])
    registry = cast(Mapping[str, Any], authorities["e0_ma"])
    dltvm_authority = cast(Mapping[str, Any], authorities["e0_dltvm"])
    inputs = [
        _generic_record(
            by_path[DEFAULT_PATCH_LOCK_SCHEMA.as_posix()],
            role="p1_sequence_builder_patch_lock_schema",
        ),
        _generic_record(
            by_path["src/experiments/closure_p1_sequence_builder_patch.py"],
            role="p1_sequence_builder_patch_validator",
        ),
        _generic_record(
            by_path["src/experiments/build_closure_pipe_sequences.py"],
            role="current_runtime_builder",
        ),
        dict(cast(Mapping[str, Any], registry["registry"])),
        dict(cast(Mapping[str, Any], registry["companion_manifest"])),
        dict(cast(Mapping[str, Any], dltvm_authority["lock"])),
        dict(cast(Mapping[str, Any], dltvm_authority["companion_manifest"])),
    ]
    inputs = sorted(inputs, key=lambda record: str(record["path"]))
    historical = cast(Mapping[str, Any], dltvm_authority["superseded_components"])
    historical_inputs = [
        {
            **dict(record),
            "commit": DLTVM_H_COMMIT,
            "hash_source": "git_blob_at_commit",
        }
        for record in cast(Sequence[Mapping[str, Any]], historical["records"])
    ]
    return {
        "manifest_version": "closure_p1_sequence_builder_patch_manifest_v1",
        "status": "completed",
        "experiment_id": EXPERIMENT_ID,
        "surface_id": SURFACE_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": payload["created_at_utc"],
        "outputs": [dict(lock_record)],
        "script": _generic_record(
            by_path["src/experiments/lock_closure_p1_sequence_builder_patch.py"],
            role="generating_script",
        ),
        "inputs": inputs,
        "historical_inputs": historical_inputs,
        "physical_inputs_only": True,
        "historical_inputs_compared_to_current_paths": False,
        "p1_sequence_builder_authorized": False,
        "effective_in_payload": False,
        "publication_required": True,
        "authorized_model_id": AUTHORIZED_MODEL_ID,
        "authorized_base_seed": AUTHORIZED_BASE_SEED,
        "p1_fit_authorized": False,
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
        "authoritative_contract": False,
        "authoritative_lock_path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
        "completion_marker_written_last": True,
    }


def _canonical_json_record(
    payload: Mapping[str, Any],
    path: Path,
    *,
    role: str,
    context: str,
) -> dict[str, Any]:
    record = _file_record(path, role=role)
    canonical = _canonical_json(payload)
    if (
        record["bytes"] != len(canonical)
        or record["sha256"] != _sha256_bytes(canonical)
    ):
        raise P1SequenceBuilderPatchError(f"{context} bytes are not canonical")
    return record


def _validate_p_commit_topology(
    payload: Mapping[str, Any],
    *,
    execution_head: str,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    lock_path = DEFAULT_PATCH_LOCK_PATH.as_posix()
    companion_path = DEFAULT_PATCH_MANIFEST_PATH.as_posix()
    lock_commit = _introduced_commit(lock_path)
    if lock_commit != _introduced_commit(companion_path):
        raise P1SequenceBuilderPatchError("E0-MB lock and companion commits differ")
    ancestry = _git("rev-list", "--parents", "-n", "1", lock_commit).split()
    if ancestry != [lock_commit, patch_head]:
        raise P1SequenceBuilderPatchError("P-E0-MB must be the direct child of H-E0-MB")
    expected = [
        {"status": "A", "path": lock_path},
        {"status": "A", "path": companion_path},
    ]
    if _observed_diff_entries(patch_head, lock_commit) != expected:
        raise P1SequenceBuilderPatchError("P-E0-MB must add exactly lock plus companion")
    _require_ancestor(lock_commit, execution_head)
    _assert_paths_untouched(
        lock_commit,
        execution_head,
        (lock_path, companion_path),
        context="P-E0-MB publication",
    )
    lock_record = _physical_git_record(
        lock_commit,
        lock_path,
        role="external_p1_sequence_builder_patch_lock",
    )
    companion_record = _physical_git_record(
        lock_commit,
        companion_path,
        role="p1_sequence_builder_patch_companion",
    )
    return lock_commit, lock_record, companion_record


def _validate_effective_publication(
    payload: Mapping[str, Any],
    *,
    execution_head: str,
) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
    lock_commit, lock_record, companion_record = _validate_p_commit_topology(
        payload,
        execution_head=execution_head,
    )
    if execution_head != lock_commit:
        raise P1SequenceBuilderPatchError(
            "The one-shot E0-MB authorization requires HEAD at the exact P commit"
        )
    if _git("branch", "--show-current") != "main":
        raise P1SequenceBuilderPatchError("E0-MB effective authorization requires branch main")
    refs = {
        "head": execution_head,
        "main": _require_commit(_git("rev-parse", "main"), context="main"),
        "tracking": _require_commit(
            _git("rev-parse", PUBLISHED_REF),
            context=PUBLISHED_REF,
        ),
        "origin_head": _require_commit(
            _git("rev-parse", "origin/HEAD"),
            context="origin/HEAD",
        ),
    }
    if set(refs.values()) != {lock_commit}:
        raise P1SequenceBuilderPatchError(f"E0-MB publication refs diverged: {refs}")
    published = refs["tracking"]
    remote = _remote_main_oid()
    if remote != published:
        raise P1SequenceBuilderPatchError("Local and live origin/main differ")
    return lock_commit, published, lock_record, companion_record


def _load_unpublished_p1_sequence_builder_patch_lock(
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = _load_regular_json(DEFAULT_PATCH_LOCK_PATH, context="E0-MB lock")
    schema = _load_regular_json(DEFAULT_PATCH_LOCK_SCHEMA, context="E0-MB schema")
    validate_p1_sequence_builder_patch_lock_payload(payload, schema)
    lock_record = _canonical_json_record(
        payload,
        DEFAULT_PATCH_LOCK_PATH,
        role="external_p1_sequence_builder_patch_lock",
        context="E0-MB lock",
    )
    companion = _load_regular_json(DEFAULT_PATCH_MANIFEST_PATH, context="E0-MB companion")
    if companion != _expected_companion(payload, lock_record=lock_record):
        raise P1SequenceBuilderPatchError("E0-MB companion drifted")
    _canonical_json_record(
        companion,
        DEFAULT_PATCH_MANIFEST_PATH,
        role="p1_sequence_builder_patch_companion",
        context="E0-MB companion",
    )
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    if execution_head != patch_head:
        raise P1SequenceBuilderPatchError(
            "Unpublished E0-MB validation must run at H-E0-MB"
        )
    summary = {
        "status": "locked_unpublished",
        "gate": PATCH_GATE,
        "patch_head": patch_head,
        "lock_commit": None,
        "execution_head": execution_head,
        "published_head": None,
        "publication_verified": False,
        "remote_publication_verified": False,
        "historical_dltvm_verified": True,
        "historical_e0_ma_registry_verified": True,
        "transactional_builder_verified": True,
        "sequence_namespace_absent": False,
        "authorization_effective": False,
        **PATCH_AUTHORIZATIONS,
    }
    return payload, summary


def load_published_p1_sequence_builder_patch_historical_authority(
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the published E0-MB evidence without authorizing execution."""
    payload = _load_regular_json(DEFAULT_PATCH_LOCK_PATH, context="E0-MB lock")
    schema = _load_regular_json(DEFAULT_PATCH_LOCK_SCHEMA, context="E0-MB schema")
    validate_p1_sequence_builder_patch_lock_payload(
        payload,
        schema,
        require_physical_patch_components=False,
    )
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    lock_commit, lock_record, companion_record = _validate_p_commit_topology(
        payload,
        execution_head=execution_head,
    )
    if lock_record != _canonical_json_record(
        payload,
        DEFAULT_PATCH_LOCK_PATH,
        role="external_p1_sequence_builder_patch_lock",
        context="E0-MB lock",
    ):
        raise P1SequenceBuilderPatchError("Published E0-MB lock record drifted")
    companion = _load_regular_json(DEFAULT_PATCH_MANIFEST_PATH, context="E0-MB companion")
    if companion != _expected_companion(payload, lock_record=lock_record):
        raise P1SequenceBuilderPatchError("E0-MB companion drifted")
    if companion_record != _canonical_json_record(
        companion,
        DEFAULT_PATCH_MANIFEST_PATH,
        role="p1_sequence_builder_patch_companion",
        context="E0-MB companion",
    ):
        raise P1SequenceBuilderPatchError("Published E0-MB companion record drifted")
    return payload, {
        "status": "published_p1_sequence_builder_patch_historical_authority_valid",
        "gate": PATCH_GATE,
        "patch_head": payload["patch_repository"]["head"],
        "lock_commit": lock_commit,
        "execution_head": execution_head,
        "publication_topology_verified": True,
        "authorization_effective": False,
        **PATCH_AUTHORIZATIONS,
    }


def load_and_validate_p1_sequence_builder_patch_lock(
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the exact published P commit and return the one-shot authority."""
    sequence_before = p1_sequence_namespace_absence()
    progression_before = closure_progression_namespace_absence()
    payload = _load_regular_json(DEFAULT_PATCH_LOCK_PATH, context="E0-MB lock")
    schema = _load_regular_json(DEFAULT_PATCH_LOCK_SCHEMA, context="E0-MB schema")
    validate_p1_sequence_builder_patch_lock_payload(payload, schema)
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    status = _git("status", "--porcelain", "--untracked-files=all")
    if status:
        raise P1SequenceBuilderPatchError(
            f"E0-MB execution requires a clean worktree and index: {status}"
        )
    lock_commit, published, lock_record, companion_record = (
        _validate_effective_publication(payload, execution_head=execution_head)
    )
    if lock_record != _canonical_json_record(
        payload,
        DEFAULT_PATCH_LOCK_PATH,
        role="external_p1_sequence_builder_patch_lock",
        context="E0-MB lock",
    ):
        raise P1SequenceBuilderPatchError("Published E0-MB lock record drifted")
    companion = _load_regular_json(DEFAULT_PATCH_MANIFEST_PATH, context="E0-MB companion")
    if companion != _expected_companion(payload, lock_record=lock_record):
        raise P1SequenceBuilderPatchError("E0-MB companion drifted")
    if companion_record != _canonical_json_record(
        companion,
        DEFAULT_PATCH_MANIFEST_PATH,
        role="p1_sequence_builder_patch_companion",
        context="E0-MB companion",
    ):
        raise P1SequenceBuilderPatchError("Published E0-MB companion record drifted")
    if p1_sequence_namespace_absence() != sequence_before:
        raise P1SequenceBuilderPatchError("E0-MB sequence namespace changed during gate")
    if closure_progression_namespace_absence() != progression_before:
        raise P1SequenceBuilderPatchError("E0-MB progression namespace changed during gate")
    summary = {
        "status": "published_p1_sequence_builder_patch_valid",
        "gate": PATCH_GATE,
        "patch_head": payload["patch_repository"]["head"],
        "lock_commit": lock_commit,
        "execution_head": execution_head,
        "published_head": published,
        "publication_verified": True,
        "remote_publication_verified": True,
        "historical_dltvm_verified": True,
        "historical_e0_ma_registry_verified": True,
        "transactional_builder_verified": True,
        "sequence_namespace_absent": True,
        "authorization_inputs": [lock_record, companion_record],
        **EFFECTIVE_AUTHORIZATIONS,
    }
    return payload, summary


def require_p1_sequence_builder_authorized(
    *,
    model_id: str,
    base_seed: int | None,
) -> dict[str, Any]:
    """Fail before runtime/state I/O unless exactly P1 seed 1729 is unlocked."""
    if model_id != AUTHORIZED_MODEL_ID or base_seed != AUTHORIZED_BASE_SEED:
        raise P1SequenceBuilderPatchError(
            "E0-MB authorizes only the one-shot P1 sequence build for seed 1729"
        )
    _, summary = load_and_validate_p1_sequence_builder_patch_lock()
    required_true = (
        "publication_verified",
        "remote_publication_verified",
        "historical_dltvm_verified",
        "historical_e0_ma_registry_verified",
        "transactional_builder_verified",
        "sequence_namespace_absent",
        "p1_sequence_builder_authorized",
        "authorization_effective",
    )
    failed = [field for field in required_true if summary.get(field) is not True]
    if failed:
        raise P1SequenceBuilderPatchError(
            f"E0-MB authorization predicates failed: {failed}"
        )
    required_false = (
        "batch_seed_execution_authorized",
        "effective_in_payload",
        "publication_required",
        "p1_fit_authorized",
        "e0_m_authorized",
        "evaluation_authorized",
        "e0_u_authorized",
        "future_outcomes_accessed",
    )
    drifted = [field for field in required_false if summary.get(field) is not False]
    if drifted:
        raise P1SequenceBuilderPatchError(f"E0-MB fail-closed seals drifted: {drifted}")
    p1_sequence_namespace_absence()
    closure_progression_namespace_absence()
    return summary


__all__ = [
    "AUTHORIZED_BASE_SEED",
    "AUTHORIZED_MODEL_ID",
    "DEFAULT_PATCH_LOCK_PATH",
    "DEFAULT_PATCH_LOCK_SCHEMA",
    "DEFAULT_PATCH_MANIFEST_PATH",
    "DIFF_CHECK_COMMAND",
    "EFFECTIVE_AUTHORIZATIONS",
    "FOCUSED_TEST_COMMAND",
    "FOCUSED_TEST_COUNT",
    "PATCH_ADDED_PATHS",
    "PATCH_AUTHORIZATIONS",
    "PATCH_COMPONENT_ROLES",
    "PATCH_MODIFIED_PATHS",
    "PATCH_PATHS",
    "POETRY_CHECK_COMMAND",
    "PUBLICATION_GUARD_COMMAND",
    "P1SequenceBuilderPatchError",
    "TYPE_CHECK_COMMAND",
    "_expected_companion",
    "_load_regular_json",
    "build_p1_sequence_builder_patch_lock_payload",
    "closure_progression_namespace_absence",
    "collect_p1_sequence_builder_patch_prelock_state",
    "load_and_validate_p1_sequence_builder_patch_lock",
    "load_published_p1_sequence_builder_patch_historical_authority",
    "p1_sequence_namespace_absence",
    "p1_sequence_namespace_paths",
    "patch_component_bundle",
    "patch_git_diff_payload",
    "require_p1_sequence_builder_authorized",
    "validate_p1_sequence_builder_patch_lock_payload",
    "validate_p1_sequence_builder_patch_verification",
]
