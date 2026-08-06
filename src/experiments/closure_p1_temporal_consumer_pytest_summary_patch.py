#!/usr/bin/env python
"""Validate the additive Closure V1 E0-MF consumer-pytest-summary authority."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from src.experiments import audit_closure_p1_sequence_bundle as p1_audit
from src.experiments import (
    closure_p1_temporal_consumer_verification_patch as e0_me,
)
from src.experiments.closure_contract import ClosureContractError, validate_json_schema


PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOCK_VERSION = "closure_p1_temporal_consumer_pytest_summary_patch_lock_v1"
PATCH_GATE = "E0-MF"
PATCH_ID = "p1_temporal_consumer_pytest_summary_patch_1"
PATCH_STATUS = "locked"
EXPERIMENT_ID = "closure_v1"
SURFACE_ID = "closure_v1_wqp_adaptive_no_current_chla"
PUBLISHED_REF = "origin/main"

AUTHORIZED_MODEL_ID = "P1"
AUTHORIZED_BASE_SEED = 1729
AUTHORIZED_DEVICE = "cpu"

H_E0_ME_COMMIT = "1b30cd658acc9e46779e907e3efb30511f646983"
P1_BUNDLE_COMMIT = "82c0bc10a8b17ab700a8f0c28491a60572a11d81"
PATCH_BASE_COMMIT = H_E0_ME_COMMIT

DEFAULT_PATCH_LOCK_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "p1_temporal_consumer_pytest_summary_patch_lock.json"
)
DEFAULT_PATCH_MANIFEST_PATH = Path(
    "reports/closure_v1/00_protocol/"
    "p1_temporal_consumer_pytest_summary_patch_lock_manifest.json"
)
DEFAULT_PATCH_LOCK_SCHEMA = Path(
    "configs/closure_v1/p1_temporal_consumer_pytest_summary_patch_lock.schema.json"
)

PATCH_COMPONENT_ROLES = {
    DEFAULT_PATCH_LOCK_SCHEMA.as_posix(): (
        "p1_temporal_consumer_pytest_summary_patch_lock_schema"
    ),
    "docs/closure_v1/E0_M_P1_TEMPORAL_CONSUMER_PYTEST_SUMMARY_PATCH_1.md": (
        "p1_temporal_consumer_pytest_summary_patch_protocol"
    ),
    "src/experiments/closure_p1_temporal_consumer_pytest_summary_patch.py": (
        "p1_temporal_consumer_pytest_summary_patch_validator"
    ),
    "src/experiments/lock_closure_p1_temporal_consumer_pytest_summary_patch.py": (
        "p1_temporal_consumer_pytest_summary_patch_locker"
    ),
    "src/experiments/train_closure_pipe.py": "p1_temporal_consumer_mf_gate_routing",
    "tests/test_closure_p1_temporal_consumer_pytest_summary_patch.py": (
        "p1_temporal_consumer_pytest_summary_patch_tests"
    ),
    "tests/test_train_closure_pipe.py": "p1_temporal_consumer_mf_gate_tests",
}
PATCH_PATHS = tuple(sorted(PATCH_COMPONENT_ROLES))
PATCH_MODIFIED_PATHS = (
    "src/experiments/train_closure_pipe.py",
    "tests/test_train_closure_pipe.py",
)
PATCH_ADDED_PATHS = tuple(
    path for path in PATCH_PATHS if path not in PATCH_MODIFIED_PATHS
)

ME_SUPERSEDED_PATHS = PATCH_MODIFIED_PATHS
ME_PRESERVED_PATHS = tuple(
    path for path in e0_me.PATCH_PATHS if path not in ME_SUPERSEDED_PATHS
)

FIT_AVAILABILITY = dict(e0_me.FIT_AVAILABILITY)
P1_ARTIFACT_BUILDER_RECORD = dict(e0_me.P1_ARTIFACT_BUILDER_RECORD)

PATCH_CORRECTION = {
    "issue_id": "p1_consumer_pytest_duration_suffix_parser_1",
    "classification": "verification_parser_only",
    "failed_execute_lock_stage": "post_pytest_pre_poetry_pre_audit_pre_dvc_pre_output",
    "failed_execute_lock_authorization_consumed": True,
    "failed_execute_lock_process_started": True,
    "failed_execute_lock_prelock_completed": True,
    "failed_execute_lock_guards_acquired": True,
    "failed_execute_lock_guards_rolled_back": True,
    "failed_execute_lock_full_type_check_run": True,
    "failed_execute_lock_full_type_check_passed": True,
    "failed_execute_lock_focused_pytest_run": True,
    "failed_execute_lock_focused_pytest_returncode_zero": True,
    "failed_execute_lock_focused_pytest_parser_rejected": True,
    "failed_execute_lock_focused_pytest_stdout_preserved": False,
    "failed_execute_lock_poetry_check_run": False,
    "failed_execute_lock_publication_guard_run": False,
    "failed_execute_lock_diff_check_run": False,
    "failed_execute_lock_in_process_audit_run": False,
    "failed_execute_lock_dvc_commands_run": False,
    "failed_execute_lock_payload_built": False,
    "failed_execute_lock_outputs_written": False,
    "auditor_execution_mode": "in_process_callable",
    "pytest_summary_parser_policy": "pytest_9_0_3_duration_clock_closed_v1",
    "pytest_summary_reference_version": "9.0.3",
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
    "h_e0_me_git_bound": True,
    "p_e0_me_absent": True,
    "me_preserved_component_count": 5,
    "me_superseded_component_count": 2,
    "p1_sequence_bundle_preserved": True,
    "consumer_outputs_absent_at_lock": True,
    "model_artifact_expected": False,
    "holdout_accessed": False,
    "post_2021_outcomes_accessed": False,
    "does_not_replace_e0_m": True,
}

TYPE_CHECK_COMMAND = (".venv/bin/ty", "check")
FOCUSED_TEST_COMMAND = (
    ".venv/bin/pytest",
    "tests/test_closure_p1_temporal_consumer_pytest_summary_patch.py",
    "tests/test_train_closure_pipe.py",
    "tests/test_closure_p1_temporal_consumer_verification_patch.py",
    "tests/test_closure_p1_temporal_consumer_patch.py",
    "tests/test_closure_development_runtime_temporal_consumer_patch.py",
    "tests/test_closure_development_runtime_temporal_validation_manifest_patch.py",
    "tests/test_audit_closure_p1_sequence_bundle.py",
    "-q",
)
# Exact collection closed by FOCUSED_TEST_COMMAND for H-E0-MF.
FOCUSED_TEST_COUNT = 262
POETRY_CHECK_COMMAND = ("poetry", "check")
PUBLICATION_GUARD_COMMAND = ("scripts/check_repo_publication_ready.sh",)
DIFF_CHECK_COMMAND = ("git", "diff", "--check")
DVC_PUSH_COMMAND = tuple(e0_me.DVC_PUSH_COMMAND)

AUDITOR_MODULE = "src.experiments.audit_closure_p1_sequence_bundle"
AUDITOR_NAME = "audit_p1_sequence_bundle"
AUDITOR_QUALNAME = "audit_p1_sequence_bundle"
AUDITOR_SOURCE_PATH = p1_audit.AUDITOR_PATH.as_posix()


class P1TemporalConsumerPytestSummaryPatchError(RuntimeError):
    """Raised when E0-MF cannot prove its closed authority."""


def _translate(error: BaseException) -> P1TemporalConsumerPytestSummaryPatchError:
    return P1TemporalConsumerPytestSummaryPatchError(str(error))


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
        return e0_me._git(*args)
    except e0_me.P1TemporalConsumerVerificationPatchError as exc:
        raise _translate(exc) from exc


def _require_commit(value: str, *, context: str) -> str:
    try:
        return e0_me._require_commit(value, context=context)
    except e0_me.P1TemporalConsumerVerificationPatchError as exc:
        raise _translate(exc) from exc


def _require_ancestor(ancestor: str, descendant: str) -> None:
    try:
        e0_me._require_ancestor(ancestor, descendant)
    except e0_me.P1TemporalConsumerVerificationPatchError as exc:
        raise _translate(exc) from exc


def _git_blob(commit: str, path: str) -> bytes:
    try:
        return e0_me._git_blob(commit, path)
    except e0_me.P1TemporalConsumerVerificationPatchError as exc:
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
        return e0_me._file_record(path, role=role)
    except e0_me.P1TemporalConsumerVerificationPatchError as exc:
        raise _translate(exc) from exc


def _load_regular_json(path: Path, *, context: str) -> dict[str, Any]:
    try:
        return e0_me._load_regular_json(path, context=context)
    except e0_me.P1TemporalConsumerVerificationPatchError as exc:
        raise _translate(exc) from exc


def _observed_diff_entries(base: str, head: str) -> list[dict[str, str]]:
    try:
        return e0_me._observed_diff_entries(base, head)
    except e0_me.P1TemporalConsumerVerificationPatchError as exc:
        raise _translate(exc) from exc


def _assert_paths_untouched(
    base: str,
    descendant: str,
    paths: Sequence[str],
    *,
    context: str,
) -> None:
    try:
        e0_me._assert_paths_untouched(base, descendant, paths, context=context)
    except e0_me.P1TemporalConsumerVerificationPatchError as exc:
        raise _translate(exc) from exc


def _introduced_commit(path: str) -> str:
    try:
        return e0_me._introduced_commit(path)
    except e0_me.P1TemporalConsumerVerificationPatchError as exc:
        raise _translate(exc) from exc


def _remote_main_oid() -> str:
    try:
        return e0_me._remote_main_oid()
    except e0_me.P1TemporalConsumerVerificationPatchError as exc:
        raise _translate(exc) from exc


def _path_entry_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def patch_git_diff_payload(patch_head: str) -> dict[str, Any]:
    patch_head = _require_commit(patch_head, context="H-E0-MF")
    ancestry = _git("rev-list", "--parents", "-n", "1", patch_head).split()
    if ancestry != [patch_head, PATCH_BASE_COMMIT]:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "H-E0-MF must be the direct non-merge child of H-E0-ME"
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
        raise P1TemporalConsumerPytestSummaryPatchError(
            f"H-E0-MF diff differs from its closed 2M+5A allowlist: {observed}"
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
    patch_head = _require_commit(patch_head, context="H-E0-MF")
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


def _assert_p_e0_me_absent() -> dict[str, Any]:
    paths = (
        e0_me.DEFAULT_PATCH_LOCK_PATH.as_posix(),
        e0_me.DEFAULT_PATCH_MANIFEST_PATH.as_posix(),
    )
    physical = [path for path in paths if _path_entry_exists(PROJECT_ROOT / path)]
    if physical:
        raise P1TemporalConsumerPytestSummaryPatchError(
            f"P-E0-ME must remain physically absent: {physical}"
        )
    introduced = {
        path: _git("log", "--all", "--format=%H", "--diff-filter=A", "--", path)
        for path in paths
    }
    if any(value for value in introduced.values()):
        raise P1TemporalConsumerPytestSummaryPatchError(
            "P-E0-ME lock paths unexpectedly exist in Git history"
        )
    return {
        "paths": list(paths),
        "paths_sha256": _path_digest(paths),
        "physical_entries_present": [],
        "git_introductions_present": [],
        "p_e0_me_absent": True,
    }


def _historical_e0_me_authority(*, execution_head: str) -> dict[str, Any]:
    ancestry = _git("rev-list", "--parents", "-n", "1", H_E0_ME_COMMIT).split()
    if ancestry != [H_E0_ME_COMMIT, e0_me.PATCH_BASE_COMMIT]:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "H-E0-ME publication topology drifted"
        )
    try:
        git_diff = e0_me.patch_git_diff_payload(H_E0_ME_COMMIT)
        components = e0_me.patch_component_bundle(H_E0_ME_COMMIT)
    except e0_me.P1TemporalConsumerVerificationPatchError as exc:
        raise _translate(exc) from exc
    records = [
        dict(record)
        for record in cast(
            Sequence[Mapping[str, Any]],
            cast(Mapping[str, Any], components)["records"],
        )
    ]
    by_path = {str(record["path"]): record for record in records}
    if set(by_path) != set(e0_me.PATCH_PATHS) or len(by_path) != len(records):
        raise P1TemporalConsumerPytestSummaryPatchError(
            "Historical H-E0-ME component paths drifted"
        )
    superseded = [by_path[path] for path in ME_SUPERSEDED_PATHS]
    preserved = [by_path[path] for path in ME_PRESERVED_PATHS]
    for record in records:
        expected = _git_record(
            H_E0_ME_COMMIT,
            str(record["path"]),
            role=str(record["role"]),
        )
        if record != expected:
            raise P1TemporalConsumerPytestSummaryPatchError(
                f"Historical H-E0-ME Git record drifted: {record['path']}"
            )
    for record in preserved:
        if _file_record(Path(str(record["path"])), role=str(record["role"])) != record:
            raise P1TemporalConsumerPytestSummaryPatchError(
                f"Preserved H-E0-ME component drifted physically: {record['path']}"
            )
    _assert_paths_untouched(
        H_E0_ME_COMMIT,
        execution_head,
        ME_PRESERVED_PATHS,
        context="preserved H-E0-ME components",
    )
    try:
        e0_md_authority = e0_me._historical_e0_md_authority(
            execution_head=execution_head
        )
    except e0_me.P1TemporalConsumerVerificationPatchError as exc:
        raise _translate(exc) from exc
    e0_md_context = dict(
        cast(Mapping[str, Any], e0_md_authority["e0_md_context_authorization"])
    )
    e0_mc_context = dict(
        cast(Mapping[str, Any], e0_md_authority["e0_mc_context_authorization"])
    )
    e0_me_context = {
        "gate": "E0-ME",
        "patch_head": H_E0_ME_COMMIT,
        "p_e0_me_absent": True,
        "historical_git_authority_verified": True,
        "historical_e0_md_verified": True,
        "historical_e0_dltvm_verified": True,
        "historical_me_effective_loader_called": False,
        "effective_loader_called": False,
        "p1_consumer_authorized": False,
        "p1_fit_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }
    return {
        "gate": "E0-ME",
        "patch_head": H_E0_ME_COMMIT,
        "parent": e0_me.PATCH_BASE_COMMIT,
        "git_diff": git_diff,
        "patch_components": components,
        "superseded_components": _component_set(
            superseded,
            current_bytes_required_to_match_historical=False,
        ),
        "preserved_components": _component_set(
            preserved,
            current_bytes_required_to_match_historical=True,
        ),
        "p_e0_me": _assert_p_e0_me_absent(),
        "e0_md": e0_md_authority,
        "e0_me_context_authorization": e0_me_context,
        "e0_md_context_authorization": e0_md_context,
        "e0_mc_context_authorization": e0_mc_context,
        "historical_git_authority_verified": True,
        "effective_loader_called": False,
        "future_outcomes_accessed": False,
    }


def _auditor_identity_record() -> dict[str, Any]:
    callable_object = p1_audit.audit_p1_sequence_bundle
    source = inspect.getsourcefile(callable_object)
    code = getattr(callable_object, "__code__", None)
    if (
        callable_object.__module__ != AUDITOR_MODULE
        or callable_object.__name__ != AUDITOR_NAME
        or callable_object.__qualname__ != AUDITOR_QUALNAME
        or source is None
        or code is None
    ):
        raise P1TemporalConsumerPytestSummaryPatchError(
            "P1 auditor callable identity drifted"
        )
    expected_path = (PROJECT_ROOT / AUDITOR_SOURCE_PATH).resolve(strict=True)
    if Path(source).resolve(strict=True) != expected_path:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "P1 auditor callable source path drifted"
        )
    if Path(str(code.co_filename)).resolve(strict=True) != expected_path:
        raise P1TemporalConsumerPytestSummaryPatchError(
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
        raise P1TemporalConsumerPytestSummaryPatchError(
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
        raise P1TemporalConsumerPytestSummaryPatchError(
            "P1 in-process audit count evidence is malformed"
        )
    expected = {
        "audit_version": p1_audit.AUDIT_VERSION,
        "status": "validated",
        "model_id": "P1",
        "base_seed": 1729,
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
        raise P1TemporalConsumerPytestSummaryPatchError(
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
        raise P1TemporalConsumerPytestSummaryPatchError(
            "P1 in-process audit read-only evidence drifted: "
            f"fit={fit_drift}, safety={safety_drift}"
        )
    identity = _auditor_identity_record()
    try:
        encoded = _canonical_audit_result(result)
    except (TypeError, ValueError) as exc:
        raise P1TemporalConsumerPytestSummaryPatchError(
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
    """Invoke exactly the published read-only P1 auditor in this process."""
    _auditor_identity_record()
    try:
        result = p1_audit.audit_p1_sequence_bundle()
    except p1_audit.ClosureP1SequenceAuditError as exc:
        raise _translate(exc) from exc
    if not isinstance(result, Mapping):
        raise P1TemporalConsumerPytestSummaryPatchError(
            "P1 in-process auditor returned a non-mapping result"
        )
    return _closed_audit_evidence(result)


def p1_consumer_namespace_absence() -> dict[str, Any]:
    paths = [path.as_posix() for path in p1_audit.P1_CONSUMER_PATHS]
    existing = [path for path in paths if _path_entry_exists(PROJECT_ROOT / path)]
    if existing:
        raise P1TemporalConsumerPytestSummaryPatchError(
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


def collect_p1_temporal_consumer_pytest_summary_patch_prelock_state(
    *,
    verify_remote: bool,
) -> dict[str, Any]:
    status = _git("status", "--porcelain", "--untracked-files=all")
    if status:
        raise P1TemporalConsumerPytestSummaryPatchError(
            f"H-E0-MF lock requires a clean worktree: {status}"
        )
    head = _require_commit(_git("rev-parse", "HEAD"), context="H-E0-MF HEAD")
    if _git("branch", "--show-current") != "main":
        raise P1TemporalConsumerPytestSummaryPatchError(
            "H-E0-MF lock requires branch main"
        )
    published = _require_commit(_git("rev-parse", PUBLISHED_REF), context=PUBLISHED_REF)
    if published != head:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "H-E0-MF HEAD differs from origin/main"
        )
    remote = _remote_main_oid() if verify_remote else published
    if remote != head:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "H-E0-MF HEAD differs from live origin/main"
        )
    git_diff = patch_git_diff_payload(head)
    components = patch_component_bundle(head)
    for record in cast(Sequence[Mapping[str, Any]], components["records"]):
        if _file_record(Path(str(record["path"])), role=str(record["role"])) != record:
            raise P1TemporalConsumerPytestSummaryPatchError(
                f"Physical H-E0-MF component drifted: {record['path']}"
            )
    historical = _historical_e0_me_authority(execution_head=head)
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
        "base_authority": {"e0_me": historical},
        "consumer_prelock": p1_consumer_namespace_absence(),
        "fit_availability": dict(FIT_AVAILABILITY),
    }


def build_p1_temporal_consumer_pytest_summary_patch_lock_payload(
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
        "base_authority": dict(cast(Mapping[str, Any], prelock["base_authority"])),
        "consumer_prelock": dict(cast(Mapping[str, Any], prelock["consumer_prelock"])),
        "fit_availability": dict(cast(Mapping[str, Any], prelock["fit_availability"])),
        "correction": dict(PATCH_CORRECTION),
        "verification": dict(verification),
        "authorizations": dict(PATCH_AUTHORIZATIONS),
        "seals": dict(PATCH_SEALS),
        "lock_artifact": {
            "path": DEFAULT_PATCH_LOCK_PATH.as_posix(),
            "role": "external_p1_temporal_consumer_pytest_summary_patch_lock",
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
        raise P1TemporalConsumerPytestSummaryPatchError(
            f"E0-MF {context} evidence has unexpected fields"
        )
    if not required.issubset(evidence) or evidence.get("command") != list(command):
        raise P1TemporalConsumerPytestSummaryPatchError(
            f"E0-MF {context} evidence drifted"
        )
    if evidence.get("returncode") != 0:
        raise P1TemporalConsumerPytestSummaryPatchError(
            f"E0-MF {context} did not pass"
        )


def _validate_focused_duration_evidence(evidence: Mapping[str, Any]) -> None:
    duration_text = evidence.get("duration_seconds")
    if not isinstance(duration_text, str):
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF focused pytest duration evidence is malformed"
        )
    try:
        duration = Decimal(duration_text)
    except InvalidOperation as exc:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF focused pytest duration evidence is malformed"
        ) from exc
    if not duration.is_finite() or duration < 0:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF focused pytest duration evidence is malformed"
        )
    summary_format = evidence.get("summary_format")
    clock = evidence.get("duration_clock")
    if duration < Decimal(60):
        valid = summary_format == "pytest_short" and clock is None
    else:
        try:
            expected_clock = str(timedelta(seconds=int(duration)))
        except OverflowError as exc:
            raise P1TemporalConsumerPytestSummaryPatchError(
                "E0-MF focused pytest duration evidence is out of range"
            ) from exc
        valid = summary_format == "pytest_timedelta" and clock == expected_clock
    if not valid:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF focused pytest duration/clock evidence drifted"
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
        "base_seed": 1729,
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
        raise P1TemporalConsumerPytestSummaryPatchError(
            f"E0-MF in-process audit evidence drifted: {drifted}"
        )
    identity = _auditor_identity_record()
    for field, identity_field in (
        ("callable_source_git", "git_source_record"),
        ("callable_source_physical", "physical_source_record"),
    ):
        if evidence.get(field) != identity[identity_field]:
            raise P1TemporalConsumerPytestSummaryPatchError(
                f"E0-MF auditor {field} drifted"
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
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF canonical audit hash evidence is malformed"
        )


def validate_p1_temporal_consumer_pytest_summary_patch_verification(
    verification: Mapping[str, Any],
) -> None:
    expected_fields = {
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
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF verification fields drifted"
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
            raise P1TemporalConsumerPytestSummaryPatchError(
                f"E0-MF {field} evidence is malformed"
            )
        _validate_command_evidence(value, command=command, context=field)
    focused = cast(Mapping[str, Any], verification["focused_tests"])
    if (
        FOCUSED_TEST_COUNT <= 0
        or focused.get("test_count") != FOCUSED_TEST_COUNT
        or focused.get("skipped_count") != 0
        or focused.get("deselected_count") != 0
    ):
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF focused-test evidence drifted"
        )
    _validate_focused_duration_evidence(focused)
    first = cast(Mapping[str, Any], verification["dvc_push_first"])
    second = cast(Mapping[str, Any], verification["dvc_push_second"])
    if first.get("terminal_status") not in {
        "1 file pushed",
        "Everything is up to date.",
    }:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF first targeted DVC push evidence drifted"
        )
    if second.get("terminal_status") != "Everything is up to date.":
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF second targeted DVC push is not idempotent"
        )
    audit = verification.get("p1_bundle_audit")
    if not isinstance(audit, Mapping):
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF in-process audit evidence is malformed"
        )
    _validate_audit_evidence_shape(audit)


def validate_p1_temporal_consumer_pytest_summary_patch_lock_payload(
    payload: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    require_physical_audit: bool,
) -> None:
    try:
        validate_json_schema(
            payload,
            schema,
            instance_path="$.p1_temporal_consumer_pytest_summary_patch_lock",
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
            "role": "external_p1_temporal_consumer_pytest_summary_patch_lock",
            "self_hash_policy": "verified_from_committed_and_published_bytes",
        },
    }
    for field, expected in fixed.items():
        if payload.get(field) != expected:
            raise P1TemporalConsumerPytestSummaryPatchError(
                f"E0-MF fixed field drifted: {field}"
            )
    created = payload.get("created_at_utc")
    if not isinstance(created, str):
        raise P1TemporalConsumerPytestSummaryPatchError("E0-MF timestamp is invalid")
    try:
        timestamp = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF timestamp is invalid"
        ) from exc
    if timestamp.utcoffset() is None:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF timestamp requires a timezone"
        )
    repository = cast(Mapping[str, Any], payload["patch_repository"])
    patch_head = _require_commit(str(repository.get("head", "")), context="H-E0-MF")
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
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF patch repository record drifted"
        )
    if payload.get("git_diff") != patch_git_diff_payload(patch_head):
        raise P1TemporalConsumerPytestSummaryPatchError("E0-MF Git diff drifted")
    components = patch_component_bundle(patch_head)
    if payload.get("patch_components") != components:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF component bundle drifted"
        )
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    _require_ancestor(patch_head, execution_head)
    for record in cast(Sequence[Mapping[str, Any]], components["records"]):
        if _file_record(Path(str(record["path"])), role=str(record["role"])) != record:
            raise P1TemporalConsumerPytestSummaryPatchError(
                f"Physical H-E0-MF component drifted: {record['path']}"
            )
    _assert_paths_untouched(
        patch_head,
        execution_head,
        PATCH_PATHS,
        context="H-E0-MF components",
    )
    expected_me = _historical_e0_me_authority(execution_head=execution_head)
    if payload.get("base_authority") != {"e0_me": expected_me}:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF historical E0-ME authority drifted"
        )
    if payload.get("consumer_prelock") != p1_consumer_namespace_absence():
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF consumer prelock drifted"
        )
    verification = cast(Mapping[str, Any], payload["verification"])
    validate_p1_temporal_consumer_pytest_summary_patch_verification(verification)
    if require_physical_audit:
        observed = run_p1_bundle_audit_in_process()
        if verification.get("p1_bundle_audit") != observed:
            raise P1TemporalConsumerPytestSummaryPatchError(
                "E0-MF physical in-process re-audit differs from locked evidence"
            )


def _expected_companion(
    payload: Mapping[str, Any],
    *,
    lock_record: Mapping[str, Any],
) -> dict[str, Any]:
    components = cast(Mapping[str, Any], payload["patch_components"])
    records = cast(Sequence[Mapping[str, Any]], components["records"])
    by_path = {str(record["path"]): record for record in records}
    me_authority = cast(
        Mapping[str, Any],
        cast(Mapping[str, Any], payload["base_authority"])["e0_me"],
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
            "p1_temporal_consumer_pytest_summary_patch_lock_schema",
        ),
        component(
            "src/experiments/closure_p1_temporal_consumer_pytest_summary_patch.py",
            "p1_temporal_consumer_pytest_summary_patch_validator",
        ),
        *[
            dict(record)
            for record in cast(
                Sequence[Mapping[str, Any]],
                cast(Mapping[str, Any], me_authority["preserved_components"])["records"],
            )
        ],
    ]
    inputs.sort(key=lambda record: str(record["path"]))
    historical_inputs = [
        {
            **dict(record),
            "commit": H_E0_ME_COMMIT,
            "hash_source": "git_blob_at_commit",
        }
        for record in cast(
            Sequence[Mapping[str, Any]],
            cast(Mapping[str, Any], me_authority["superseded_components"])["records"],
        )
    ]
    historical_inputs.sort(key=lambda record: str(record["path"]))
    return {
        "manifest_version": (
            "closure_p1_temporal_consumer_pytest_summary_patch_manifest_v1"
        ),
        "status": "completed",
        "experiment_id": EXPERIMENT_ID,
        "surface_id": SURFACE_ID,
        "gate": PATCH_GATE,
        "patch_id": PATCH_ID,
        "created_at_utc": payload["created_at_utc"],
        "outputs": [dict(lock_record)],
        "script": component(
            "src/experiments/lock_closure_p1_temporal_consumer_pytest_summary_patch.py",
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
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF lock and companion commits differ"
        )
    ancestry = _git("rev-list", "--parents", "-n", "1", lock_commit).split()
    if ancestry != [lock_commit, patch_head]:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "P-E0-MF must be the direct child of H-E0-MF"
        )
    expected = [
        {"status": "A", "path": lock_path},
        {"status": "A", "path": companion_path},
    ]
    if _observed_diff_entries(patch_head, lock_commit) != expected:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "P-E0-MF must add exactly lock plus companion"
        )
    if _git("branch", "--show-current") != "main":
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF effective authority requires branch main"
        )
    if execution_head != lock_commit:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF execution HEAD must equal the exact P-E0-MF lock commit"
        )
    _require_ancestor(lock_commit, execution_head)
    _assert_paths_untouched(
        lock_commit,
        execution_head,
        (lock_path, companion_path),
        context="P-E0-MF publication",
    )
    refs = {
        ref: _require_commit(_git("rev-parse", ref), context=ref)
        for ref in ("HEAD", "main", "origin/main", "origin/HEAD")
    }
    if set(refs.values()) != {lock_commit}:
        raise P1TemporalConsumerPytestSummaryPatchError(
            f"E0-MF local/tracking refs diverged: {refs}"
        )
    if verify_remote and _remote_main_oid() != lock_commit:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF execution HEAD differs from live origin/main"
        )
    return (
        lock_commit,
        _git_record(
            lock_commit,
            lock_path,
            role="external_p1_temporal_consumer_pytest_summary_patch_lock",
        ),
        _git_record(
            lock_commit,
            companion_path,
            role="p1_temporal_consumer_pytest_summary_patch_companion",
        ),
    )


def load_and_validate_p1_temporal_consumer_pytest_summary_patch_lock(
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
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF requires closed default paths"
        )
    payload = _load_regular_json(lock_path, context="E0-MF lock")
    schema = _load_regular_json(lock_schema, context="E0-MF schema")
    # Static/Git validation deliberately precedes any physical P1 audit.
    validate_p1_temporal_consumer_pytest_summary_patch_lock_payload(
        payload,
        schema,
        require_physical_audit=False,
    )
    lock_record = _file_record(
        lock_path,
        role="external_p1_temporal_consumer_pytest_summary_patch_lock",
    )
    companion = _load_regular_json(companion_path, context="E0-MF companion")
    if companion != _expected_companion(payload, lock_record=lock_record):
        raise P1TemporalConsumerPytestSummaryPatchError("E0-MF companion drifted")
    companion_record = _file_record(
        companion_path,
        role="p1_temporal_consumer_pytest_summary_patch_companion",
    )
    patch_head = str(cast(Mapping[str, Any], payload["patch_repository"])["head"])
    execution_head = _require_commit(_git("rev-parse", "HEAD"), context="execution HEAD")
    _require_ancestor(patch_head, execution_head)
    if require_published:
        status = _git("status", "--porcelain", "--untracked-files=all")
        if status:
            raise P1TemporalConsumerPytestSummaryPatchError(
                f"E0-MF execution requires a clean worktree: {status}"
            )
        lock_commit, git_lock_record, git_companion_record = _validate_publication_bundle(
            payload,
            execution_head=execution_head,
            verify_remote=verify_remote,
        )
        if lock_record != git_lock_record or companion_record != git_companion_record:
            raise P1TemporalConsumerPytestSummaryPatchError(
                "Published E0-MF bytes drifted"
            )
        validate_p1_temporal_consumer_pytest_summary_patch_lock_payload(
            payload,
            schema,
            require_physical_audit=True,
        )
        effective = True
    else:
        if execution_head != patch_head:
            raise P1TemporalConsumerPytestSummaryPatchError(
                "Unpublished E0-MF validation must run at H-E0-MF"
            )
        validate_p1_temporal_consumer_pytest_summary_patch_lock_payload(
            payload,
            schema,
            require_physical_audit=True,
        )
        lock_commit = ""
        effective = False
    me_authority = cast(
        Mapping[str, Any],
        cast(Mapping[str, Any], payload["base_authority"])["e0_me"],
    )
    e0_me_context = dict(
        cast(Mapping[str, Any], me_authority["e0_me_context_authorization"])
    )
    e0_md_context = dict(
        cast(Mapping[str, Any], me_authority["e0_md_context_authorization"])
    )
    e0_mc_context = dict(
        cast(Mapping[str, Any], me_authority["e0_mc_context_authorization"])
    )
    audit_evidence = dict(
        cast(
            Mapping[str, Any],
            cast(Mapping[str, Any], payload["verification"])["p1_bundle_audit"],
        )
    )
    summary = {
        "status": (
            "published_p1_temporal_consumer_pytest_summary_patch_valid"
            if effective
            else "locked_unpublished"
        ),
        "gate": PATCH_GATE,
        "patch_head": patch_head,
        "lock_commit": lock_commit or None,
        "execution_head": execution_head,
        "publication_verified": effective,
        "remote_publication_verified": effective and verify_remote,
        "historical_e0_me_verified": True,
        "historical_me_effective_loader_called": False,
        "p_e0_me_absent": True,
        "pytest_summary_parser_corrected": True,
        "historical_e0_md_verified": True,
        "historical_e0_dltvm_verified": True,
        "historical_dltvm_effective_loader_called": False,
        "p_e0_md_absent": True,
        "p1_sequence_bundle_verified": True,
        "in_process_audit_verified": effective,
        "in_process_audit_evidence": audit_evidence,
        "consumer_namespace_absent": True,
        "authorization_effective": effective,
        "p1_consumer_authorized": effective,
        "p1_fit_authorized": effective,
        "authorized_model_id": AUTHORIZED_MODEL_ID,
        "authorized_base_seed": AUTHORIZED_BASE_SEED,
        "authorized_device": AUTHORIZED_DEVICE,
        "p1_artifact_builder_record": dict(P1_ARTIFACT_BUILDER_RECORD),
        "current_runtime_builder_record": dict(P1_ARTIFACT_BUILDER_RECORD),
        "e0_me_context_authorization": e0_me_context,
        "e0_md_context_authorization": e0_md_context,
        "e0_mc_context_authorization": e0_mc_context,
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
        "e0_m_authorized": False,
        "evaluation_authorized": False,
        "e0_u_authorized": False,
        "future_outcomes_accessed": False,
    }
    return payload, summary


def require_p1_temporal_consumer_pytest_summary_patch_authorized(
    *,
    model_id: str,
    base_seed: int,
    device: str,
) -> dict[str, Any]:
    """Require published E0-MF for exactly the P1/1729/CPU consumer."""
    if (
        model_id != AUTHORIZED_MODEL_ID
        or base_seed != AUTHORIZED_BASE_SEED
        or device != AUTHORIZED_DEVICE
    ):
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF authorizes only the P1 seed 1729 CPU temporal consumer"
        )
    _, summary = load_and_validate_p1_temporal_consumer_pytest_summary_patch_lock(
        require_published=True,
        verify_remote=True,
    )
    required_true = (
        "publication_verified",
        "remote_publication_verified",
        "historical_e0_me_verified",
        "p_e0_me_absent",
        "pytest_summary_parser_corrected",
        "historical_e0_md_verified",
        "historical_e0_dltvm_verified",
        "p_e0_md_absent",
        "p1_sequence_bundle_verified",
        "in_process_audit_verified",
        "consumer_namespace_absent",
        "authorization_effective",
        "p1_consumer_authorized",
        "p1_fit_authorized",
    )
    failed = [field for field in required_true if summary.get(field) is not True]
    if failed:
        raise P1TemporalConsumerPytestSummaryPatchError(
            f"E0-MF authorization predicates failed: {failed}"
        )
    required_false = (
        "sequence_fit_available",
        "historical_me_effective_loader_called",
        "historical_dltvm_effective_loader_called",
        "python_auditor_subprocess_used",
        "batch_seed_execution_authorized",
        "retry_authorized",
        "e0_m_authorized",
        "evaluation_authorized",
        "e0_u_authorized",
        "future_outcomes_accessed",
    )
    drifted = [field for field in required_false if summary.get(field) is not False]
    if drifted:
        raise P1TemporalConsumerPytestSummaryPatchError(
            f"E0-MF fail-closed seals drifted: {drifted}"
        )
    if summary.get("fit_availability") != FIT_AVAILABILITY:
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF fit availability drifted"
        )
    e0_me_context = summary.get("e0_me_context_authorization")
    if (
        not isinstance(e0_me_context, Mapping)
        or e0_me_context.get("gate") != "E0-ME"
        or e0_me_context.get("p_e0_me_absent") is not True
        or e0_me_context.get("historical_git_authority_verified") is not True
        or e0_me_context.get("historical_e0_md_verified") is not True
        or e0_me_context.get("historical_e0_dltvm_verified") is not True
        or e0_me_context.get("historical_me_effective_loader_called") is not False
        or e0_me_context.get("effective_loader_called") is not False
    ):
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF e0_me_context_authorization drifted"
        )
    e0_md_context = summary.get("e0_md_context_authorization")
    if (
        not isinstance(e0_md_context, Mapping)
        or e0_md_context.get("gate") != "E0-MD"
        or e0_md_context.get("historical_e0_dltvm_verified") is not True
        or e0_md_context.get("historical_dltvm_effective_loader_called") is not False
    ):
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF e0_md_context_authorization drifted"
        )
    e0_mc_context = summary.get("e0_mc_context_authorization")
    if not isinstance(e0_mc_context, Mapping) or e0_mc_context.get("gate") != "E0-MC":
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF e0_mc_context_authorization drifted"
        )
    if not isinstance(summary.get("in_process_audit_evidence"), Mapping):
        raise P1TemporalConsumerPytestSummaryPatchError(
            "E0-MF lacks in-process audit evidence"
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
    "P1TemporalConsumerPytestSummaryPatchError",
    "build_p1_temporal_consumer_pytest_summary_patch_lock_payload",
    "collect_p1_temporal_consumer_pytest_summary_patch_prelock_state",
    "load_and_validate_p1_temporal_consumer_pytest_summary_patch_lock",
    "p1_consumer_namespace_absence",
    "patch_component_bundle",
    "patch_git_diff_payload",
    "require_p1_temporal_consumer_pytest_summary_patch_authorized",
    "run_p1_bundle_audit_in_process",
    "validate_p1_temporal_consumer_pytest_summary_patch_lock_payload",
]
